"""Yahoo Finance datafeed, live streamer, and marquee for the TradingView chart."""

import contextlib
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

_MARQUEE_CSS = Path(__file__).resolve().parent.parent / "assets" / "tvchart_marquee.css"


def _fmt_number(value: float | int, decimals: int = 2) -> str:
    """Format a number with thousand separators and a T/B/M suffix."""
    if abs(value) >= 1e12:
        return f"{value / 1e12:,.{decimals}f}T"
    if abs(value) >= 1e9:
        return f"{value / 1e9:,.{decimals}f}B"
    if abs(value) >= 1e6:
        return f"{value / 1e6:,.{decimals}f}M"
    return f"{value:,.{decimals}f}"


def _fmt_volume(value: float | int) -> str:
    """Format volume with a K/M/B suffix."""
    if abs(value) >= 1e9:
        return f"{value / 1e9:,.2f}B"
    if abs(value) >= 1e6:
        return f"{value / 1e6:,.2f}M"
    if abs(value) >= 1e3:
        return f"{value / 1e3:,.1f}K"
    return f"{value:,.0f}"


RESOLUTION_MAP: dict[str, dict[str, str]] = {
    "1m": {"interval": "1m", "period": "7d"},
    "5m": {"interval": "5m", "period": "60d"},
    "15m": {"interval": "15m", "period": "60d"},
    "30m": {"interval": "30m", "period": "60d"},
    "1h": {"interval": "1h", "period": "730d"},
    "1d": {"interval": "1d", "period": "max"},
    "1w": {"interval": "1wk", "period": "max"},
    "1M": {"interval": "1mo", "period": "max"},
}

DERIVED_RESOLUTIONS: dict[str, dict[str, Any]] = {
    "3m": {"source": "1m", "factor": 3},
    "45m": {"source": "15m", "factor": 3},
    "2h": {"source": "1h", "factor": 2},
    "3h": {"source": "1h", "factor": 3},
    "4h": {"source": "1h", "factor": 4},
    "3M": {"source": "1M", "factor": 3},
    "6M": {"source": "1M", "factor": 6},
    "12M": {"source": "1M", "factor": 12},
}

RESOLUTION_ALIASES: dict[str, str] = {
    "1": "1m",
    "3": "3m",
    "5": "5m",
    "15": "15m",
    "30": "30m",
    "45": "45m",
    "60": "1h",
    "120": "2h",
    "180": "3h",
    "240": "4h",
    "1D": "1d",
    "D": "1d",
    "1W": "1w",
    "W": "1w",
}

RESOLUTION_SECONDS: dict[str, int] = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "45m": 2700,
    "1h": 3600,
    "2h": 7200,
    "3h": 10800,
    "4h": 14400,
    "1d": 86400,
    "1w": 604800,
    "1M": 2592000,
    "3M": 7776000,
    "6M": 15552000,
    "12M": 31104000,
}

SUPPORTED_RESOLUTIONS = [
    "1m",
    "3m",
    "5m",
    "15m",
    "30m",
    "45m",
    "1h",
    "2h",
    "3h",
    "4h",
    "1d",
    "1w",
    "1M",
    "3M",
    "6M",
    "12M",
]

TYPE_LABELS: dict[str, str] = {
    "equity": "Stock",
    "etf": "ETF",
    "index": "Index",
    "mutualfund": "Mutual Fund",
    "cryptocurrency": "Crypto",
    "currency": "Currency",
    "future": "Futures",
    "option": "Option",
}

EXCHANGE_LABELS: dict[str, str] = {
    "NMS": "NASDAQ",
    "NGM": "NASDAQ",
    "NCM": "NASDAQ",
    "NasdaqGS": "NASDAQ",
    "NasdaqGM": "NASDAQ",
    "NasdaqCM": "NASDAQ",
    "NYQ": "NYSE",
    "NYSE": "NYSE",
    "NYSEArca": "NYSE ARCA",
    "NYSEARCA": "NYSE ARCA",
    "PCX": "NYSE ARCA",
    "NYSEAMERICAN": "NYSE AMEX",
    "ASE": "NYSE AMEX",
    "BTS": "CBOE BZX",
    "CBO": "CBOE",
    "OPR": "OTC",
    "PNK": "OTC Markets",
    "LSE": "LSE",
    "TSE": "TSE",
    "TSX": "TSX",
}

tz_cache: dict[str, str] = {}
delay_cache: dict[str, int] = {}
info_cache: dict[str, dict] = {}
reg_close_cache: dict[str, float] = {}
session_bounds_cache: dict[str, tuple[int, int, int, int]] = {}


def normalize_resolution(res: str) -> str:
    """Normalize a resolution string to the canonical key used by ``RESOLUTION_MAP``."""
    if res in RESOLUTION_MAP or res in DERIVED_RESOLUTIONS:
        return res
    if res in RESOLUTION_ALIASES:
        return RESOLUTION_ALIASES[res]
    low = res.lower()
    if low in RESOLUTION_MAP or low in DERIVED_RESOLUTIONS:
        return low
    return "1d"


def is_24_7_market(bounds: tuple[int, int, int, int]) -> bool:
    """Detect 24/7 markets (crypto) from their session bounds."""
    pre_start_m, reg_start_m, reg_end_m, post_end_m = bounds
    if pre_start_m == post_end_m:
        return True
    return (reg_end_m - reg_start_m) >= 23 * 60


def is_overnight(epoch: int, symbol: str) -> bool:
    """Return True if *epoch* falls outside the pre to post session window."""
    bounds = session_bounds_cache.get(symbol.upper())
    if bounds is None:
        return False
    if is_24_7_market(bounds):
        return False
    pre_start_m, _, _, post_end_m = bounds
    tz_name = tz_cache.get(symbol.upper(), "America/New_York")
    dt = datetime.fromtimestamp(epoch, tz=ZoneInfo(tz_name))
    hm = dt.hour * 60 + dt.minute
    return hm >= post_end_m or hm < pre_start_m


def current_session_label(symbol: str) -> tuple[str, str]:
    """Return the current (label, color) for the market session badge."""
    bounds = session_bounds_cache.get(symbol.upper())
    if bounds is None:
        return ("—", "#787b86")
    if is_24_7_market(bounds):
        return ("Market Open", "#26a69a")
    pre_start_m, reg_start_m, reg_end_m, post_end_m = bounds
    tz_name = tz_cache.get(symbol.upper(), "America/New_York")
    now = datetime.now(tz=ZoneInfo(tz_name))
    hm = now.hour * 60 + now.minute
    weekday = now.weekday()
    is_weekend = weekday >= 5

    if is_weekend:
        if weekday == 6 and hm >= post_end_m:
            return ("Overnight", "#64b5f6")
        return ("Closed", "#787b86")

    if reg_start_m <= hm < reg_end_m:
        return ("Market Open", "#26a69a")
    if pre_start_m <= hm < reg_start_m:
        return ("Pre-Market", "#ffa726")
    if reg_end_m <= hm < post_end_m:
        return ("After Hours", "#ffa726")
    if hm >= post_end_m:
        if weekday == 4:
            return ("Closed", "#787b86")
        return ("Overnight", "#64b5f6")
    if hm < pre_start_m:
        return ("Overnight", "#64b5f6")
    return ("Closed", "#787b86")


def is_extended_session(symbol: str) -> bool:
    """Return True if the current time is outside the regular session."""
    bounds = session_bounds_cache.get(symbol.upper())
    if bounds is None:
        return False
    if is_24_7_market(bounds):
        return False
    _, reg_start_m, reg_end_m, _ = bounds
    tz_name = tz_cache.get(symbol.upper(), "America/New_York")
    now = datetime.now(tz=ZoneInfo(tz_name))
    if now.weekday() >= 5:
        return True
    hm = now.hour * 60 + now.minute
    return hm < reg_start_m or hm >= reg_end_m


def _df_to_bars(df: Any) -> list[dict[str, Any]]:
    """Convert a yfinance DataFrame to a list of bar dicts."""
    bars: list[dict[str, Any]] = []
    for ts, row in df.iterrows():
        bars.append(
            {
                "time": int(ts.timestamp()),
                "open": round(float(row["Open"]), 6),
                "high": round(float(row["High"]), 6),
                "low": round(float(row["Low"]), 6),
                "close": round(float(row["Close"]), 6),
                "volume": int(float(row["Volume"])),
            }
        )
    return bars


def yf_fetch_full_history(symbol: str, resolution: str) -> list[dict[str, Any]]:
    """Fetch the maximum available history from yfinance for a symbol/resolution."""
    import yfinance as yf

    res = normalize_resolution(resolution)
    mapping = RESOLUTION_MAP.get(res, RESOLUTION_MAP["1d"])
    yf_interval = mapping["interval"]
    yf_period = mapping["period"]

    ticker = yf.Ticker(symbol)
    try:
        df = ticker.history(interval=yf_interval, period=yf_period, prepost=True)
    except Exception:
        return []

    if df is None or df.empty:
        return []

    bars = _df_to_bars(df)

    if yf_interval not in ("1d", "5d", "1wk", "1mo", "3mo"):
        bars = [b for b in bars if not is_overnight(b["time"], symbol)]

    return bars


def aggregate_bars(bars: list[dict[str, Any]], factor: int) -> list[dict[str, Any]]:
    """Aggregate *bars* by grouping every *factor* consecutive bars into one."""
    out: list[dict[str, Any]] = []
    for i in range(0, len(bars), factor):
        group = bars[i : i + factor]
        if not group:
            break
        out.append(
            {
                "time": group[0]["time"],
                "open": group[0]["open"],
                "high": max(b["high"] for b in group),
                "low": min(b["low"] for b in group),
                "close": group[-1]["close"],
                "volume": sum(b["volume"] for b in group),
            }
        )
    return out


class BarCache:
    """Thread-safe cache of bar data keyed by ``(symbol, resolution)``."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: dict[tuple[str, str], list[dict[str, Any]]] = {}

    def get(self, symbol: str, resolution: str) -> list[dict[str, Any]]:
        """Return cached bars, fetching from yfinance if not yet cached."""
        res = normalize_resolution(resolution)
        key = (symbol.upper(), res)
        with self._lock:
            if key in self._cache:
                return list(self._cache[key])

        if res in DERIVED_RESOLUTIONS:
            derived = DERIVED_RESOLUTIONS[res]
            source_bars = self.get(symbol, derived["source"])
            bars = aggregate_bars(source_bars, derived["factor"])
        else:
            bars = yf_fetch_full_history(symbol, resolution)
        with self._lock:
            self._cache[key] = bars
        return list(bars)

    def refresh(self, symbol: str, resolution: str) -> list[dict[str, Any]]:
        """Force re-fetch and return fresh bars."""
        res = normalize_resolution(resolution)
        if res in DERIVED_RESOLUTIONS:
            derived = DERIVED_RESOLUTIONS[res]
            source_bars = self.refresh(symbol, derived["source"])
            bars = aggregate_bars(source_bars, derived["factor"])
        else:
            bars = yf_fetch_full_history(symbol, res)
        key = (symbol.upper(), res)
        with self._lock:
            self._cache[key] = bars
        return list(bars)

    def append_bar(self, symbol: str, resolution: str, bar: dict[str, Any]) -> None:
        """Merge a streaming bar into the cache (update last or append)."""
        res = normalize_resolution(resolution)
        key = (symbol.upper(), res)
        with self._lock:
            bars = self._cache.get(key)
            if bars is None:
                return
            if bars and bars[-1]["time"] == bar["time"]:
                bars[-1] = bar
            elif not bars or bar["time"] > bars[-1]["time"]:
                bars.append(bar)

    def last_bar_time(self, symbol: str, resolution: str) -> int:
        """Return the epoch timestamp of the last cached bar, or 0."""
        res = normalize_resolution(resolution)
        key = (symbol.upper(), res)
        with self._lock:
            bars = self._cache.get(key, [])
            return bars[-1]["time"] if bars else 0

    def invalidate(self, symbol: str, resolution: str | None = None) -> None:
        """Remove cached data for *symbol* (optionally only one resolution)."""
        with self._lock:
            if resolution:
                self._cache.pop((symbol.upper(), resolution), None)
            else:
                keys = [k for k in self._cache if k[0] == symbol.upper()]
                for k in keys:
                    del self._cache[k]


def tv_symbol_search(
    query: str, limit: int = 30, symbol_type: str = ""
) -> list[dict[str, Any]]:
    """Search symbols and shape the result for the TradingView datafeed."""
    from openbb_yfinance.utils.search_helpers import yf_symbol_search

    items = yf_symbol_search(query, limit=limit, asset_type=symbol_type)
    return [
        {
            "symbol": item["symbol"],
            "full_name": item.get("name") or item.get("description") or item["symbol"],
            "description": item.get("description") or "",
            "exchange": item.get("exchange") or "",
            "type": item.get("asset_type") or "equity",
        }
        for item in items
    ]


def _build_session_string(
    metadata: dict[str, Any],
) -> tuple[str, str, str, str, str, dict | None]:
    """Derive TradingView session strings from Yahoo metadata."""
    ctp = metadata.get("currentTradingPeriod", {})
    reg = ctp.get("regular", {})
    pre_period = ctp.get("pre", {})
    post_period = ctp.get("post", {})

    reg_start = reg.get("start", 0)
    reg_end = reg.get("end", 0)

    instrument = (metadata.get("instrumentType") or "").upper()

    if reg_start and reg_end and (reg_end - reg_start) >= 82800:
        if instrument == "FUTURE":
            return _build_futures_session(metadata)
        return "24x7", "", "24x7", "", "", None

    tz_name = metadata.get("exchangeTimezoneName", "UTC")
    zi = ZoneInfo(tz_name)

    def _fmt(ts_start: int, ts_end: int) -> str:
        if not ts_start or not ts_end or ts_end <= ts_start:
            return ""
        s = datetime.fromtimestamp(ts_start, tz=zi)
        e = datetime.fromtimestamp(ts_end, tz=zi)
        return f"{s:%H%M}-{e:%H%M}"

    pre_str = _fmt(pre_period.get("start", 0), pre_period.get("end", 0))
    reg_str = _fmt(reg_start, reg_end)
    post_str = _fmt(post_period.get("start", 0), post_period.get("end", 0))

    overnight_str = ""
    if pre_str and post_str:
        post_end = post_str.split("-")[1]
        pre_start = pre_str.split("-")[0]
        if post_end != pre_start:
            overnight_str = f"{post_end}-{pre_start}"

    windows = [w for w in [pre_str, reg_str, post_str, overnight_str] if w]
    full = ",".join(windows) if windows else "0930-1600"

    return full, pre_str, reg_str, post_str, overnight_str, None


def _build_futures_session(
    metadata: dict[str, Any],
) -> tuple[str, str, str, str, str, dict]:
    """Build session data for futures that trade ~24h Sun-Fri with a 1h break."""
    active_days: set[str] = set()
    try:
        import pandas as pd

        tp = metadata.get("tradingPeriods")
        if isinstance(tp, pd.DataFrame) and not tp.empty:
            for idx in tp.index:
                if hasattr(idx, "strftime"):
                    active_days.add(idx.strftime("%a").upper()[:3])
    except Exception:
        pass

    if not active_days:
        active_days = {"SUN", "MON", "TUE", "WED", "THU", "FRI"}

    if "THU" in active_days:
        active_days.add("FRI")

    day_names = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
    schedule: dict[str, str] = {}
    for day in day_names:
        if day not in active_days:
            continue
        if day == "SUN":
            schedule["SUN"] = "1800-2359"
        elif day == "FRI":
            schedule["FRI"] = "0000-1700"
        else:
            schedule[day] = "0000-1700,1800-2359"

    reg_str = "0000-1700,1800-2359"
    full = reg_str

    return full, "", reg_str, "", "", schedule


def _pricescale_from_hint(price_hint: int | None) -> int:
    """Convert Yahoo's ``priceHint`` (decimal places) to LWC ``pricescale``."""
    if price_hint is None or price_hint < 0:
        return 100
    return 10**price_hint


def yf_symbol_info(symbol: str) -> dict[str, Any] | None:
    """Build TradingView ``symbolInfo`` from yfinance metadata."""
    import yfinance as yf

    try:
        ticker = yf.Ticker(symbol)
        md = ticker.get_history_metadata()
    except Exception:
        return None

    if not md:
        return None

    exchange_tz = md.get("exchangeTimezoneName", "UTC")
    tz_cache[symbol.upper()] = exchange_tz

    ctp = md.get("currentTradingPeriod", {})
    pre_ts = (ctp.get("pre") or {}).get("start", 0)
    reg_start_ts = (ctp.get("regular") or {}).get("start", 0)
    reg_end_ts = (ctp.get("regular") or {}).get("end", 0)
    post_ts = (ctp.get("post") or {}).get("end", 0)
    if pre_ts and reg_start_ts and reg_end_ts and post_ts:
        zi = ZoneInfo(exchange_tz)

        def _to_minutes(ts: int) -> int:
            dt = datetime.fromtimestamp(ts, tz=zi)
            return dt.hour * 60 + dt.minute

        session_bounds_cache[symbol.upper()] = (
            _to_minutes(pre_ts),
            _to_minutes(reg_start_ts),
            _to_minutes(reg_end_ts),
            _to_minutes(post_ts),
        )
    else:
        session_bounds_cache[symbol.upper()] = (240, 570, 960, 1200)
    raw_exchange = md.get("fullExchangeName") or md.get("exchangeName", "")
    exchange = EXCHANGE_LABELS.get(raw_exchange, raw_exchange)
    name = md.get("shortName") or md.get("longName", symbol)
    instrument = (md.get("instrumentType") or "EQUITY").lower()
    type_label = TYPE_LABELS.get(instrument, instrument.title())
    (
        session_full,
        session_pre,
        session_reg,
        session_post,
        session_overnight,
        session_schedule,
    ) = _build_session_string(md)
    pricescale = _pricescale_from_hint(md.get("priceHint"))
    currency = md.get("currency", "USD")

    sector = ""
    industry = ""
    delay_minutes = 0
    try:
        info = ticker.info
        sector = info.get("sector", "") or ""
        industry = info.get("industry", "") or ""
        delay_minutes = int(info.get("exchangeDataDelayedBy", 0) or 0)
        info_cache[symbol.upper()] = info
    except Exception:
        pass

    delay_cache[symbol.upper()] = delay_minutes

    valid_ranges = set(md.get("validRanges") or [])
    has_short_range = bool(valid_ranges & {"1d", "5d"})
    data_gran = (md.get("dataGranularity") or "1d").lower()
    has_intraday = has_short_range and data_gran != "1d"
    has_weekly_monthly = bool(valid_ranges & {"1y", "2y", "5y", "max"})
    raw_vol = md.get("regularMarketVolume")
    has_no_volume = raw_vol is None or raw_vol == 0

    if has_intraday:
        supported = list(SUPPORTED_RESOLUTIONS)
    else:
        supported = [
            r
            for r in SUPPORTED_RESOLUTIONS
            if r in ("1d", "1w", "1M", "3M", "6M", "12M")
        ]

    return {
        "name": name,
        "symbol": symbol.upper(),
        "ticker": symbol.upper(),
        "description": md.get("longName") or name,
        "exchange": exchange,
        "listed_exchange": exchange,
        "type": type_label,
        "session": session_full,
        "session_premarket": session_pre,
        "session_regular": session_reg,
        "session_postmarket": session_post,
        "session_overnight": session_overnight,
        "timezone": exchange_tz,
        "sector": sector,
        "industry": industry,
        "minmov": 1,
        "pricescale": pricescale,
        "has_intraday": has_intraday,
        "has_daily": True,
        "has_weekly_and_monthly": has_weekly_monthly,
        "supported_resolutions": supported,
        "volume_precision": 0,
        "data_status": "delayed_streaming" if delay_minutes > 0 else "streaming",
        "delay": delay_minutes * 60 if delay_minutes > 0 else 0,
        "currency_code": currency,
        "has_empty_bars": False,
        "has_no_volume": has_no_volume,
        **({"session_schedule": session_schedule} if session_schedule else {}),
    }


_SYMBOL_TYPES = [
    {"name": "All Types", "value": ""},
    {"name": "Stock", "value": "equity"},
    {"name": "ETF", "value": "etf"},
    {"name": "Index", "value": "index"},
    {"name": "Mutual Fund", "value": "mutualfund"},
    {"name": "Futures", "value": "future"},
    {"name": "Crypto", "value": "cryptocurrency"},
    {"name": "Currency", "value": "currency"},
]


class RealtimeStreamer:
    """Background ``yf.WebSocket`` listener that pushes live bars and marquee updates.

    Only 1-minute subscribers receive streaming bar updates; longer
    intervals form their bars over periods far slower than tick frequency.

    When *on_quote* is supplied the streamer runs in quote-only mode: it skips
    the bar cache, bar pushing and marquee machinery and instead forwards each
    raw tick as ``on_quote(symbol, msg)``. The Asset Info widget uses this to
    drive its live header price from the same feed without sharing the chart's
    session/marquee caches.
    """

    _STREAMABLE = frozenset({"1m"})

    def __init__(self, app: Any, cache: BarCache, on_quote: Any = None) -> None:
        self._app = app
        self._cache = cache
        self._on_quote = on_quote
        self._subs: dict[str, dict[str, str]] = {}
        self._latest: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._ws: Any = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._delay: dict[str, int] = {}
        self._bar_volume_base: dict[str, int] = {}
        self._last_day_volume: dict[str, int] = {}
        self._active_marquee_symbol: str = ""
        self._backfill_timers: dict[str, threading.Timer] = {}

    def bind(self, target: Any) -> None:
        """Point live bar-update and marquee pushes at *target*.

        *target* is the widget that made the request (native: the PyWry app),
        so streamed updates route to the chart that subscribed.
        """
        self._app = target

    def subscribe(
        self, guid: str, symbol: str, resolution: str, delay_minutes: int = 0
    ) -> None:
        """Start (or extend) live streaming for *symbol*."""
        import yfinance as yf

        if delay_minutes > 0:
            self._delay[symbol.upper()] = delay_minutes

        if resolution in self._STREAMABLE and self._on_quote is None:
            threading.Thread(
                target=self._backfill_gap,
                args=(guid, symbol, resolution),
                daemon=True,
            ).start()
            if delay_minutes > 0:
                self._start_periodic_backfill(symbol, resolution, delay_minutes)

        with self._lock:
            self._subs[guid] = {"symbol": symbol, "resolution": resolution}
            symbols = list({s["symbol"] for s in self._subs.values()})

        ws_alive = (
            self._ws is not None
            and self._thread is not None
            and self._thread.is_alive()
        )
        if not ws_alive:
            if self._ws is not None:
                with contextlib.suppress(Exception):
                    self._ws.close()
            self._ws = yf.WebSocket(verbose=False)
            self._ws.subscribe(symbols)
            self._stop.clear()
            self._thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._thread.start()
        else:
            self._ws.subscribe([symbol])

    def unsubscribe(self, guid: str) -> None:
        """Stop streaming for a listener and drop its symbol if now unused."""
        with self._lock:
            info = self._subs.pop(guid, None)
            remaining_symbols = {s["symbol"] for s in self._subs.values()}

        if info and self._ws and info["symbol"] not in remaining_symbols:
            with contextlib.suppress(Exception):
                self._ws.unsubscribe([info["symbol"]])
            key = info["symbol"].upper()
            timer = self._backfill_timers.pop(key, None)
            if timer:
                timer.cancel()

    def stop(self) -> None:
        """Close the WebSocket and join the listener thread cleanly."""
        self._stop.set()
        for timer in self._backfill_timers.values():
            timer.cancel()
        self._backfill_timers.clear()

        import logging

        yf_logger = logging.getLogger("yfinance")
        prior_level = yf_logger.level
        yf_logger.setLevel(logging.CRITICAL + 1)
        try:
            if self._ws:
                with contextlib.suppress(Exception):
                    self._ws.close()
            thread = self._thread
            if thread is not None and thread.is_alive():
                thread.join(timeout=2.0)
                self._thread = None
        finally:
            yf_logger.setLevel(prior_level)

    def _backfill_gap(self, guid: str, symbol: str, resolution: str) -> None:
        """Refresh the cache and push any newer bars to fill the gap."""
        old_last = self._cache.last_bar_time(symbol, resolution)
        new_bars = self._cache.refresh(symbol, resolution)
        gap_bars = [b for b in new_bars if b["time"] > old_last]
        for bar in gap_bars:
            self._app.respond_tvchart_bar_update(listener_guid=guid, bar=bar)

    def _start_periodic_backfill(
        self, symbol: str, resolution: str, delay_minutes: int
    ) -> None:
        """Schedule periodic cache refreshes for delayed data sources."""
        key = symbol.upper()
        remaining = delay_minutes

        def _tick() -> None:
            nonlocal remaining
            if self._stop.is_set() or remaining <= 0:
                self._backfill_timers.pop(key, None)
                return

            old_last = self._cache.last_bar_time(symbol, resolution)
            new_bars = self._cache.refresh(symbol, resolution)
            gap_bars = [b for b in new_bars if b["time"] > old_last]

            if gap_bars:
                with self._lock:
                    guids = [
                        g
                        for g, s in self._subs.items()
                        if s["symbol"] == symbol and s["resolution"] in self._STREAMABLE
                    ]
                for guid in guids:
                    for bar in gap_bars:
                        self._app.respond_tvchart_bar_update(
                            listener_guid=guid, bar=bar
                        )

            remaining -= 1
            if remaining > 0 and not self._stop.is_set():
                t = threading.Timer(60.0, _tick)
                t.daemon = True
                self._backfill_timers[key] = t
                t.start()
            else:
                self._backfill_timers.pop(key, None)

        t = threading.Timer(60.0, _tick)
        t.daemon = True
        self._backfill_timers[key] = t
        t.start()

    def _listen_loop(self) -> None:
        """Run the WebSocket listener in a background thread."""
        try:
            self._ws.listen(self._on_message)
        except Exception:
            pass
        finally:
            self._ws = None

    def _on_message(self, msg: dict[str, Any]) -> None:
        """Bucket a Yahoo tick into a 1-minute bar and push it to subscribers."""
        symbol = msg.get("id", "")
        price = msg.get("price")
        if not symbol or price is None:
            return

        if self._on_quote is not None:
            self._on_quote(symbol, msg)
            return

        epoch = msg.get("time")
        if not isinstance(epoch, int):
            epoch = int(time.time())

        bar_time = (epoch // 60) * 60
        price = float(price)
        has_day_volume = "day_volume" in msg
        cum_day_volume = int(msg["day_volume"]) if has_day_volume else None

        with self._lock:
            prev = self._latest.get(symbol)
            if prev and prev["time"] == bar_time:
                prev["high"] = max(prev["high"], price)
                prev["low"] = min(prev["low"], price)
                prev["close"] = price
                if cum_day_volume is not None:
                    base = self._bar_volume_base.get(symbol, cum_day_volume)
                    prev["volume"] = max(0, cum_day_volume - base)
                bar = dict(prev)
            else:
                if cum_day_volume is not None:
                    base = self._last_day_volume.get(symbol, cum_day_volume)
                    base = min(base, cum_day_volume)
                    self._bar_volume_base[symbol] = base
                    initial_vol = max(0, cum_day_volume - base)
                else:
                    initial_vol = 0
                bar = {
                    "time": bar_time,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": initial_vol,
                }
                self._latest[symbol] = dict(bar)
            if cum_day_volume is not None:
                self._last_day_volume[symbol] = cum_day_volume

            if not is_overnight(bar_time, symbol):
                market_hours = msg.get("market_hours")
                for guid, sub in self._subs.items():
                    if (
                        sub["symbol"] == symbol
                        and sub["resolution"] in self._STREAMABLE
                    ):
                        push_bar = (
                            bar
                            if market_hours is None
                            else {**bar, "market_hours": market_hours}
                        )
                        self._app.respond_tvchart_bar_update(
                            listener_guid=guid, bar=push_bar
                        )

            if not is_overnight(bar_time, symbol):
                self._cache.append_bar(symbol, "1m", bar)

        if symbol.upper() == self._active_marquee_symbol:
            self._update_marquee(symbol, msg)

    def _update_marquee(self, symbol: str, msg: dict[str, Any]) -> None:
        """Emit ``toolbar:marquee-set-item`` events for each live data field."""
        price = msg.get("price")

        def _emit(
            ticker: str,
            text: str,
            styles: dict | None = None,
            *,
            is_html: bool = False,
        ) -> None:
            payload: dict[str, Any] = {"ticker": ticker}
            payload["html" if is_html else "text"] = text
            if styles:
                payload["styles"] = styles
            self._app.emit("toolbar:marquee-set-item", payload)

        extended = is_extended_session(symbol)
        reg_close = reg_close_cache.get(symbol.upper())

        if extended and reg_close is not None and price is not None:
            info = info_cache.get(symbol.upper(), {})
            reg_change = info.get("regularMarketChange")
            reg_pct = info.get("regularMarketChangePercent")
            if reg_change is not None and reg_pct is not None:
                is_pos = float(reg_change) >= 0
                rc = "#26a69a" if is_pos else "#ef5350"
                arrow = "▲" if is_pos else "▼"
                sign = "+" if is_pos else ""
                _emit("ws-price", f"{reg_close:,.2f}", {"color": rc})
                _emit(
                    "ws-change",
                    f"{arrow} {sign}{float(reg_change):,.2f} ({sign}{float(reg_pct):.2f}%)",
                    {"color": rc},
                )

            ext_price = float(price)
            ext_chg = ext_price - reg_close
            ext_pct = (ext_chg / reg_close) * 100 if reg_close else 0
            ext_pos = ext_chg >= 0
            ext_color = "#26a69a" if ext_pos else "#ef5350"
            ext_arrow = "▲" if ext_pos else "▼"
            ext_sign = "+" if ext_pos else ""
            _emit("ws-ext-price", f"{ext_price:,.2f}", {"color": ext_color})
            _emit(
                "ws-ext-change",
                f"{ext_arrow} {ext_sign}{ext_chg:,.2f} ({ext_sign}{ext_pct:.2f}%)",
                {"color": ext_color},
            )
        else:
            change = msg.get("change")
            change_pct = msg.get("change_percent")
            is_positive = (change or 0) >= 0
            color = "#26a69a" if is_positive else "#ef5350"
            arrow = "▲" if is_positive else "▼"

            if price is not None:
                _emit("ws-price", f"{float(price):,.2f}", {"color": color})
                reg_close_cache[symbol.upper()] = float(price)

            if change is not None and change_pct is not None:
                sign = "+" if is_positive else ""
                _emit(
                    "ws-change",
                    f"{arrow} {sign}{float(change):,.2f} ({sign}{float(change_pct):.2f}%)",
                    {"color": color},
                )

            _emit("ws-ext-price", "")
            _emit("ws-ext-change", "")

        if "open_price" in msg:
            _emit("ws-open", f"{float(msg['open_price']):,.2f}")
        if "day_high" in msg:
            _emit("ws-high", f"{float(msg['day_high']):,.2f}")
        if "day_low" in msg:
            _emit("ws-low", f"{float(msg['day_low']):,.2f}")
        if "day_volume" in msg:
            _emit("ws-volume", _fmt_volume(float(msg["day_volume"])))
        if "market_cap" in msg:
            _emit("ws-mktcap", _fmt_number(float(msg["market_cap"]), 2))
        if "vol_24hr" in msg:
            _emit(
                "ws-vol24",
                f'<span class="ws-label">24h Vol</span> {_fmt_volume(float(msg["vol_24hr"]))}',
                is_html=True,
            )

        _emit("ws-symbol", symbol.upper())
        label, clr = current_session_label(symbol)
        _emit("ws-session", label, {"color": clr})


def _seed_marquee(app: Any, symbol: str) -> None:
    """Populate the marquee with a snapshot from the cached ``ticker.info``."""
    info = info_cache.get(symbol.upper())
    if not info:
        return

    def _emit(
        ticker: str,
        text: str,
        styles: dict | None = None,
        *,
        is_html: bool = False,
    ) -> None:
        payload: dict[str, Any] = {"ticker": ticker}
        payload["html" if is_html else "text"] = text
        if styles:
            payload["styles"] = styles
        app.emit("toolbar:marquee-set-item", payload)

    for slot in (
        "ws-price",
        "ws-change",
        "ws-session",
        "ws-ext-price",
        "ws-ext-change",
        "ws-open",
        "ws-high",
        "ws-low",
        "ws-volume",
        "ws-mktcap",
        "ws-vol24",
        "ws-symbol",
    ):
        _emit(slot, "")

    reg_price = info.get("regularMarketPrice")
    reg_change = info.get("regularMarketChange")
    reg_pct = info.get("regularMarketChangePercent")

    if reg_price is not None:
        reg_close_cache[symbol.upper()] = float(reg_price)

    is_positive = (reg_change or 0) >= 0
    color = "#26a69a" if is_positive else "#ef5350"
    arrow = "▲" if is_positive else "▼"

    if reg_price is not None:
        _emit("ws-price", f"{float(reg_price):,.2f}", {"color": color})

    if reg_change is not None and reg_pct is not None:
        sign = "+" if is_positive else ""
        _emit(
            "ws-change",
            f"{arrow} {sign}{float(reg_change):,.2f} ({sign}{float(reg_pct):.2f}%)",
            {"color": color},
        )

    ms = (info.get("marketState") or "").upper()
    ext_price = None
    if ms in ("POST", "POSTPOST"):
        ext_price = info.get("postMarketPrice")
    elif ms in ("PRE", "PREPRE"):
        ext_price = info.get("preMarketPrice")

    if ext_price is not None and reg_price is not None:
        ext_chg = float(ext_price) - float(reg_price)
        ext_pct = (ext_chg / float(reg_price)) * 100 if reg_price else 0
        ext_pos = ext_chg >= 0
        ext_color = "#26a69a" if ext_pos else "#ef5350"
        ext_arrow = "▲" if ext_pos else "▼"
        ext_sign = "+" if ext_pos else ""
        _emit("ws-ext-price", f"{float(ext_price):,.2f}", {"color": ext_color})
        _emit(
            "ws-ext-change",
            f"{ext_arrow} {ext_sign}{ext_chg:,.2f} ({ext_sign}{ext_pct:.2f}%)",
            {"color": ext_color},
        )
    else:
        _emit("ws-ext-price", "")
        _emit("ws-ext-change", "")

    open_price = info.get("regularMarketOpen") or info.get("open")
    if open_price is not None:
        _emit("ws-open", f"{float(open_price):,.2f}")

    high = info.get("regularMarketDayHigh") or info.get("dayHigh")
    if high is not None:
        _emit("ws-high", f"{float(high):,.2f}")

    low = info.get("regularMarketDayLow") or info.get("dayLow")
    if low is not None:
        _emit("ws-low", f"{float(low):,.2f}")

    volume = info.get("regularMarketVolume") or info.get("volume")
    if volume is not None:
        _emit("ws-volume", _fmt_volume(float(volume)))

    mkt_cap = info.get("marketCap")
    if mkt_cap is not None and mkt_cap > 0:
        _emit("ws-mktcap", _fmt_number(float(mkt_cap), 2))
    else:
        _emit("ws-mktcap", "—")

    is_crypto = (info.get("quoteType") or "").lower() == "cryptocurrency"
    if is_crypto:
        vol_24 = info.get("volume24Hr")
        if vol_24 is not None:
            _emit(
                "ws-vol24",
                f'<span class="ws-label">24h Vol</span> {_fmt_volume(float(vol_24))}',
                is_html=True,
            )
    else:
        _emit("ws-vol24", "")

    _emit("ws-symbol", symbol.upper())
    label, clr = current_session_label(symbol)
    _emit("ws-session", label, {"color": clr})


def make_callbacks(
    app: Any, streamer: RealtimeStreamer, cache: BarCache
) -> dict[str, Any]:
    """Build the callback dict implementing the TradingView Datafeed protocol.

    The inline transport invokes each callback as ``(data, event_type, label)``
    where *label* is the requesting widget's id, so responses are routed to that
    widget via :func:`_target`. In native mode *label* is empty and the PyWry
    app is the target.
    """

    def _target(label: str) -> Any:
        return getattr(app, "_inline_widgets", {}).get(label) or app

    def on_config(data: dict[str, Any], _event_type: str = "", label: str = "") -> None:
        _target(label).respond_tvchart_datafeed_config(
            request_id=data.get("requestId", ""),
            chart_id=data.get("chartId"),
            config={
                "supported_resolutions": list(SUPPORTED_RESOLUTIONS),
                "exchanges": [],
                "symbols_types": _SYMBOL_TYPES,
                "supports_marks": False,
                "supports_time": True,
                "supports_timescale_marks": False,
            },
        )

    def on_search(data: dict[str, Any], _event_type: str = "", label: str = "") -> None:
        request_id = data.get("requestId", "")
        query = data.get("query", "")
        items = tv_symbol_search(
            query,
            limit=data.get("limit", 30),
            symbol_type=data.get("symbolType", ""),
        )
        _target(label).respond_tvchart_symbol_search(
            request_id=request_id,
            items=items,
            chart_id=data.get("chartId"),
            query=query,
        )

    def on_resolve(
        data: dict[str, Any], _event_type: str = "", label: str = ""
    ) -> None:
        request_id = data.get("requestId", "")
        symbol = data.get("symbol", "")
        chart_id = data.get("chartId")
        tgt = _target(label)
        info = yf_symbol_info(symbol)
        if info is None:
            tgt.respond_tvchart_symbol_resolve(
                request_id=request_id,
                symbol_info=None,
                chart_id=chart_id,
                error=f"Could not resolve symbol: {symbol}",
            )
        else:
            tgt.respond_tvchart_symbol_resolve(
                request_id=request_id,
                symbol_info=info,
                chart_id=chart_id,
            )
            streamer.bind(tgt)
            streamer._active_marquee_symbol = symbol.upper()
            _seed_marquee(tgt, symbol)

    def on_history(
        data: dict[str, Any], _event_type: str = "", label: str = ""
    ) -> None:
        request_id = data.get("requestId", "")
        symbol = data.get("symbol", "")
        resolution = normalize_resolution(data.get("resolution", "1d"))
        chart_id = data.get("chartId")
        tgt = _target(label)
        bars = cache.get(symbol, resolution)
        if not bars:
            tgt.respond_tvchart_history(
                request_id=request_id,
                bars=[],
                status="no_data",
                no_data=True,
                chart_id=chart_id,
            )
        else:
            tgt.respond_tvchart_history(
                request_id=request_id,
                bars=bars,
                status="ok",
                chart_id=chart_id,
            )

    def on_subscribe(
        data: dict[str, Any], _event_type: str = "", label: str = ""
    ) -> None:
        streamer.bind(_target(label))
        symbol = data.get("symbol", "")
        streamer.subscribe(
            data.get("listenerGuid", ""),
            symbol,
            data.get("resolution", "1D"),
            delay_minutes=delay_cache.get(symbol.upper(), 0),
        )

    def on_unsubscribe(
        data: dict[str, Any], _event_type: str = "", label: str = ""
    ) -> None:
        streamer.unsubscribe(data.get("listenerGuid", ""))

    def on_server_time(
        data: dict[str, Any], _event_type: str = "", label: str = ""
    ) -> None:
        _target(label).respond_tvchart_server_time(
            request_id=data.get("requestId", ""),
            time=int(time.time()),
            chart_id=data.get("chartId"),
        )

    def on_data_request(
        data: dict[str, Any], _event_type: str = "", label: str = ""
    ) -> None:
        chart_id = data.get("chartId", "main")
        series_id = data.get("seriesId", "main")
        symbol = data.get("symbol", "")
        resolution = normalize_resolution(
            str(data.get("resolution", data.get("interval", "1d")))
        )
        if not symbol:
            return
        bars = cache.get(symbol, resolution)
        _target(label).emit(
            "tvchart:data-response",
            {
                "chartId": chart_id,
                "seriesId": series_id,
                "bars": bars,
                "fitContent": True,
                "interval": resolution,
            },
        )

    return {
        "tvchart:datafeed-config-request": on_config,
        "tvchart:datafeed-search-request": on_search,
        "tvchart:datafeed-resolve-request": on_resolve,
        "tvchart:datafeed-history-request": on_history,
        "tvchart:datafeed-subscribe": on_subscribe,
        "tvchart:datafeed-unsubscribe": on_unsubscribe,
        "tvchart:datafeed-server-time-request": on_server_time,
        "tvchart:data-request": on_data_request,
    }


def build_marquee(symbol: str) -> tuple[Any, str]:
    """Build the live-data marquee toolbar and its companion CSS."""
    from pywry.toolbar import Marquee, TickerItem, Toolbar

    ticker_items = [
        TickerItem(ticker="ws-symbol", html=f'<span class="ws-sym">{symbol}</span>'),
        TickerItem(
            ticker="ws-price",
            html='<span class="ws-val">—</span>',
            class_name="ws-price",
        ),
        TickerItem(
            ticker="ws-change",
            html='<span class="ws-val ws-muted">— (—%)</span>',
            class_name="ws-change",
        ),
        TickerItem(
            ticker="ws-session",
            html='<span class="ws-val ws-muted">—</span>',
            class_name="ws-session",
        ),
        TickerItem(ticker="ws-ext-price", html="", class_name="ws-ext-price"),
        TickerItem(ticker="ws-ext-change", html="", class_name="ws-ext-change"),
        TickerItem(
            ticker="ws-open",
            html='<span class="ws-val ws-muted">—</span>',
            class_name="ws-field",
        ),
        TickerItem(
            ticker="ws-high",
            html='<span class="ws-val ws-muted">—</span>',
            class_name="ws-field",
        ),
        TickerItem(
            ticker="ws-low",
            html='<span class="ws-val ws-muted">—</span>',
            class_name="ws-field",
        ),
        TickerItem(
            ticker="ws-volume",
            html='<span class="ws-val ws-muted">—</span>',
            class_name="ws-field",
        ),
        TickerItem(
            ticker="ws-mktcap",
            html='<span class="ws-val ws-muted">—</span>',
            class_name="ws-field",
        ),
        TickerItem(ticker="ws-vol24", html="", class_name="ws-field"),
    ]

    labels = ["", "", "", "", "", "", "O", "H", "L", "Vol", "Mkt Cap", ""]
    parts: list[str] = []
    for label, item in zip(labels, ticker_items, strict=False):
        if label:
            parts.append(f'<span class="ws-label">{label}</span>{item.build_html()}')
        else:
            parts.append(item.build_html())

    marquee_html = "  ".join(parts)

    toolbar = Toolbar(
        position="header",
        class_name="yf-marquee-strip",
        items=[
            Marquee(
                component_id="yf-live-marquee",
                text=marquee_html,
                behavior="static",
                event="toolbar:noop",
                style="width: 100%;",
            ),
        ],
    )

    return toolbar, _MARQUEE_CSS.read_text(encoding="utf-8")
