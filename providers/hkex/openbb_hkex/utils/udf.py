"""Unified TradingView UDF endpoint for HKEX (equities, indices, futures)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

_HKT = timezone(timedelta(hours=8))
_UTC = timezone.utc

_SUPPORTED_RESOLUTIONS = ["1", "5", "15", "30", "60", "D", "W", "M", "3M"]
_MIN_TO_INTERVAL = {1: "1m", 5: "5m", 15: "15m", 30: "30m", 60: "1h"}


def _resolution_to_interval(res: str) -> str:
    r = (res or "D").upper()
    if r in ("3M", "Q", "1Q"):
        return "1Q"
    if r.endswith("D"):
        return "1d"
    if r.endswith("W"):
        return "1W"
    if r.endswith("M"):
        return "1M"
    try:
        return _MIN_TO_INTERVAL.get(int(r), "1d")
    except ValueError:
        return "1d"


_ASSET_META = {
    "stock": {
        "exchange": "HKEX",
        "pricescale": 1000,
        "has_volume": True,
        "session": "0930-1200,1300-1600",
    },
    "index": {
        "exchange": "HKEX",
        "pricescale": 100,
        "has_volume": False,
        "session": "0930-1200,1300-1600",
    },
    "futures": {
        "exchange": "HKFE",
        "pricescale": 1,
        "has_volume": True,
        "session": "0915-1200,1300-1630",
    },
}
_PREFIX_TO_ASSET = {"HKEX": "stock", "INDEX": "index", "HKFE": "futures"}

_EQUITY_TYPE_MAP = {
    "EQTY": "stock",
    "ETP": "fund",
    "REIT": "reit",
    "BOND": "bond",
    "DW": "warrant",
    "CBBC": "structured",
    "INLINE": "structured",
}

_SYMBOL_TYPES = [
    "stock",
    "fund",
    "reit",
    "bond",
    "warrant",
    "structured",
    "index",
    "futures",
]


def _bar_epoch(d: Any) -> int:
    if isinstance(d, datetime):
        return int(d.timestamp())
    return int(datetime(d.year, d.month, d.day, tzinfo=_UTC).timestamp())


def add_udf_routes(app, base: str = "") -> None:  # noqa: PLR0915
    """Register the TradingView UDF routes on the given API router."""
    from async_lru import alru_cache
    from fastapi import Query

    from openbb_hkex.models.equity_historical import (
        HkexEquityHistoricalFetcher,
    )
    from openbb_hkex.models.futures_historical import (
        HkexFuturesHistoricalFetcher,
    )
    from openbb_hkex.models.index_historical import (
        INDEX_RICS,
        HkexIndexHistoricalFetcher,
    )
    from openbb_hkex.models.securities_master import (
        HkexSecuritiesMasterFetcher,
    )
    from openbb_hkex.utils.client import (
        DERIVATIVE_PRODUCTS,
        call_widget,
    )

    _CATEGORY_TO_TYPE = {
        "Equity": "stock",
        "Exchange Traded Products": "fund",
        "Real Estate Investment Trusts": "reit",
        "Debt Securities": "bond",
        "Derivative Warrants": "warrant",
        "Equity Warrants (Main Board)": "warrant",
        "Equity Warrants (GEM)": "warrant",
        "Callable Bull/Bear Contracts": "structured",
    }

    @alru_cache(maxsize=1)
    async def _securities() -> list[dict]:
        rows = await HkexSecuritiesMasterFetcher().fetch_data({}, {})
        out: list[dict] = []
        for row in rows:
            r = row.model_dump()  # type: ignore[union-attr]
            code = r.get("code")
            if not code:
                continue
            out.append(
                {
                    "symbol": code,
                    "full_name": f"HKEX:{code}",
                    "ticker": f"HKEX:{code}",
                    "description": r.get("name") or "",
                    "exchange": "HKEX",
                    "type": _CATEGORY_TO_TYPE.get(r.get("category") or "", "stock"),
                }
            )
        return out

    def _parse(udf_symbol: str) -> tuple[str, str]:
        s = (udf_symbol or "").strip()
        if ":" in s:
            ex, code = s.split(":", 1)
            return _PREFIX_TO_ASSET.get(ex.upper(), "stock"), code.strip()
        return "stock", s

    async def _search_all(
        query: str,
        limit: int,
        sym_type: str = "",
        exchange: str = "",
    ) -> list[dict]:
        q = (query or "").strip().upper()
        indices = [
            {
                "symbol": ric.lstrip("."),
                "full_name": f"INDEX:{ric.lstrip('.')}",
                "ticker": f"INDEX:{ric.lstrip('.')}",
                "description": name,
                "exchange": "HKEX",
                "type": "index",
            }
            for ric, name in INDEX_RICS.items()
        ]
        futures = [
            {
                "symbol": prod,
                "full_name": f"HKFE:{prod}",
                "ticker": f"HKFE:{prod}",
                "description": f"{meta.get('name', prod)} (front month)",
                "exchange": "HKFE",
                "type": "futures",
            }
            for prod, meta in DERIVATIVE_PRODUCTS.items()
        ]
        pool = indices + futures + await _securities()
        if sym_type:
            pool = [x for x in pool if x["type"] == sym_type]
        if exchange:
            pool = [x for x in pool if x["exchange"] == exchange]
        if q:
            pool = [
                x for x in pool if q in x["symbol"] or q in x["description"].upper()
            ]
        return pool[:limit]

    async def _equity_type(code: str) -> str:
        want = code.zfill(5)
        try:
            data = await call_widget(
                "getstocksearch", keyword=code.lstrip("0") or code, pre=30
            )
            for h in data.get("stocklist", []) or []:
                if str(h.get("sym") or "").zfill(5) == want:
                    return _EQUITY_TYPE_MAP.get((h.get("type") or "").upper(), "stock")
        except Exception:  # noqa: BLE001
            pass
        return "stock"

    async def _history(asset: str, code: str, interval: str, to: int) -> list:
        end = datetime.fromtimestamp(to, tz=_HKT).date()
        if asset == "index":
            fetcher: Any = HkexIndexHistoricalFetcher()
        elif asset == "futures":
            fetcher = HkexFuturesHistoricalFetcher()
        else:
            fetcher = HkexEquityHistoricalFetcher()
        return await fetcher.fetch_data(
            {"symbol": code, "end_date": end, "interval": interval}, {}
        )

    @app.get(
        "/udf",
        openapi_extra={
            "widget_config": {
                "type": "advanced_charting",
                "name": "HKEX Advanced Chart",
                "description": "TradingView charting across all HKEX equities, "
                "indices, and futures, with unified symbol search.",
                "category": "Charting",
                "widgetId": "hkex_advanced_chart",
                "endpoint": f"{base}/udf",
                "gridData": {"w": 40, "h": 20},
                "data": {"defaultSymbol": "HKEX:00700", "updateFrequency": 60000},
            },
        },
    )
    async def udf_root() -> dict[str, Any]:
        return {"ok": True}

    @app.get("/udf/config", include_in_schema=False)
    async def udf_config() -> dict[str, Any]:
        return {
            "supported_resolutions": _SUPPORTED_RESOLUTIONS,
            "supports_group_request": False,
            "supports_marks": False,
            "supports_search": True,
            "supports_timescale_marks": False,
            "supports_time": True,
            "exchanges": [
                {"value": "", "name": "All Exchanges"},
                {"value": "HKEX", "name": "HKEX"},
                {"value": "HKFE", "name": "HK Futures Exchange"},
            ],
            "symbols_types": [{"name": "All types", "value": ""}]
            + [{"name": t.capitalize(), "value": t} for t in _SYMBOL_TYPES],
        }

    @app.get("/udf/time", include_in_schema=False)
    async def udf_time() -> int:
        return int(datetime.now(tz=_UTC).timestamp())

    @app.get("/udf/search", include_in_schema=False)
    async def udf_search(
        query: str = Query(default=""),
        limit: int = Query(default=30),
        type: str = Query(default=""),  # noqa: A002
        exchange: str = Query(default=""),
    ) -> list[dict]:
        return await _search_all(query, max(limit, 1), sym_type=type, exchange=exchange)

    @app.get("/udf/symbols", include_in_schema=False)
    async def udf_symbols(symbol: str = Query(...)) -> dict[str, Any]:
        asset, code = _parse(symbol)
        meta = _ASSET_META[asset]
        sym_type = await _equity_type(code) if asset == "stock" else asset
        display = f"{meta['exchange']}:{code}"
        return {
            "name": display,
            "ticker": symbol,
            "full_name": display,
            "description": code,
            "type": sym_type,
            "exchange": meta["exchange"],
            "listed_exchange": meta["exchange"],
            "session": meta["session"],
            "timezone": "Asia/Hong_Kong",
            "minmov": 1,
            "pricescale": meta["pricescale"],
            "has_intraday": True,
            "has_daily": True,
            "has_weekly_and_monthly": True,
            "has_no_volume": not meta["has_volume"],
            "volume_precision": 0,
            "data_status": "streaming",
            "supported_resolutions": _SUPPORTED_RESOLUTIONS,
        }

    @app.get("/udf/history", include_in_schema=False)
    async def udf_history(
        symbol: str = Query(...),
        resolution: str = Query(default="D"),
        to: int = Query(...),
        from_: int = Query(default=0, alias="from"),
        countback: int | None = Query(default=None),
    ) -> dict[str, Any]:
        interval = _resolution_to_interval(resolution)
        asset, code = _parse(symbol)
        try:
            rows = await _history(asset, code, interval, to)
        except Exception as exc:  # noqa: BLE001
            return {"s": "error", "errmsg": str(exc)}

        bars = sorted(
            (
                (b, _bar_epoch(b.date))
                for b in rows
                if b.open is not None and b.close is not None
            ),
            key=lambda x: x[1],
        )
        bars = [x for x in bars if x[1] <= to]

        if countback is not None and countback > 0:
            window = bars[-countback:]
        else:
            window = [x for x in bars if x[1] >= from_]

        if not window:
            if bars:
                return {"s": "no_data", "nextTime": bars[0][1]}
            return {"s": "no_data"}

        return {
            "s": "ok",
            "t": [e for _, e in window],
            "o": [float(b.open) for b, _ in window],
            "h": [float(b.high) for b, _ in window],
            "l": [float(b.low) for b, _ in window],
            "c": [float(b.close) for b, _ in window],
            "v": [
                float(b.volume) if getattr(b, "volume", None) is not None else 0.0
                for b, _ in window
            ],
        }
