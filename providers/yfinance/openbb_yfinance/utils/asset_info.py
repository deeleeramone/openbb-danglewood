"""Styled Asset Info overview rendered as a PyWry HTML widget.

A single styled overview for any symbol — quote header, summary, key statistics,
fund operations, top holdings and sector weightings — adapting to the quote type
(equity, ETF, mutual fund). Served through PyWry's ``InlineWidget`` so it shares
the same transport as the rest of the Workspace widgets.
"""

from __future__ import annotations

import contextlib
import html as _html
from pathlib import Path
from typing import Any

_CSS = Path(__file__).resolve().parent.parent / "assets" / "asset_info.css"
_LIVE_JS = Path(__file__).resolve().parent.parent / "assets" / "asset_info_live.js"

_LIVE_ASSET_INFO: list = []

_SECTOR_LABELS = {
    "technology": "Technology",
    "communication_services": "Communication Services",
    "consumer_cyclical": "Consumer Cyclical",
    "consumer_defensive": "Consumer Defensive",
    "healthcare": "Healthcare",
    "financial_services": "Financial Services",
    "industrials": "Industrials",
    "basic_materials": "Basic Materials",
    "energy": "Energy",
    "utilities": "Utilities",
    "realestate": "Real Estate",
    "real_estate": "Real Estate",
}


def _fmt_price(value: float | int | None) -> str:
    if value is None:
        return "—"
    return f"{value:,.2f}"


def _fmt_pct(value: float | int | None, scale: float = 1.0) -> str:
    if value is None:
        return "—"
    return f"{value * scale:.2f}%"


def _fmt_compact(value: float | int | None) -> str:
    if value is None:
        return "—"
    value = float(value)
    for unit, size in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(value) >= size:
            return f"{value / size:,.2f}{unit}"
    return f"{value:,.0f}"


def _fmt_date(ts: float | int | None) -> str:
    if ts is None:
        return "—"
    from datetime import datetime, timezone

    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
    except (ValueError, OSError, OverflowError):
        return "—"


def _esc(value: object) -> str:
    return _html.escape(str(value)) if value is not None else ""


def _fetch(symbol: str) -> dict:
    """Fetch and normalise the overview payload for *symbol* from yfinance."""
    import yfinance as yf

    ticker = yf.Ticker(symbol)
    try:
        info = ticker.get_info() or {}
    except Exception:
        info = {}

    payload: dict = {
        "info": info,
        "holdings": [],
        "sectors": [],
        "calendar": None,
        "history": None,
    }

    quote_type = str(info.get("quoteType") or "").upper()
    if info:
        try:
            payload["history"] = ticker.history(period="10y", interval="1d")
        except Exception:
            payload["history"] = None
    if quote_type == "EQUITY":
        try:
            payload["calendar"] = ticker.calendar
        except Exception:
            payload["calendar"] = None
    if quote_type in ("ETF", "MUTUALFUND"):
        try:
            funds = ticker.get_funds_data()
        except Exception:
            funds = None
        if funds is not None:
            overview = getattr(funds, "fund_overview", None)
            if isinstance(overview, dict):
                if not info.get("category") and overview.get("categoryName"):
                    info["category"] = overview["categoryName"]
                if not info.get("fundFamily") and overview.get("family"):
                    info["fundFamily"] = overview["family"]
                if not info.get("legalType") and overview.get("legalType"):
                    info["legalType"] = overview["legalType"]
            holdings = getattr(funds, "top_holdings", None)
            if holdings is not None and not holdings.empty:
                for sym, row in holdings.iterrows():
                    payload["holdings"].append(
                        {
                            "symbol": str(sym),
                            "name": str(row.get("Name", "")),
                            "weight": float(row.get("Holding Percent", 0) or 0),
                        }
                    )
            weightings = getattr(funds, "sector_weightings", None)
            if isinstance(weightings, dict):
                payload["sectors"] = sorted(
                    (
                        {"sector": k, "weight": float(v or 0)}
                        for k, v in weightings.items()
                    ),
                    key=lambda s: s["weight"],
                    reverse=True,
                )
    return payload


def _stat(label: str, value: str, value_id: str = "") -> str:
    attr = f' id="{value_id}"' if value_id else ""
    return (
        f'<div class="ai-stat"><span class="ai-stat-label">{_esc(label)}</span>'
        f'<span class="ai-stat-value"{attr}>{_esc(value)}</span></div>'
    )


def _range_stat(label: str, low: float, high: float, value_id: str) -> str:
    """Build a low–high range stat that carries its raw bounds for live updates."""
    return (
        f'<div class="ai-stat"><span class="ai-stat-label">{_esc(label)}</span>'
        f'<span class="ai-stat-value" id="{value_id}" '
        f'data-low="{low}" data-high="{high}">'
        f"{_fmt_price(low)} – {_fmt_price(high)}</span></div>"
    )


def _overview_stats(info: dict) -> str:
    quote_type = str(info.get("quoteType") or "").upper()
    rows: list[str] = []
    if quote_type in ("ETF", "MUTUALFUND"):
        rows.append(_stat("Category", info.get("category") or "—"))
        rows.append(_stat("Fund Family", info.get("fundFamily") or "—"))
        rows.append(
            _stat(
                "Net Assets",
                _fmt_compact(info.get("netAssets") or info.get("totalAssets")),
            )
        )
        if info.get("ytdReturn") is not None:
            rows.append(_stat("YTD Return", _fmt_pct(info.get("ytdReturn"))))
        if info.get("yield") is not None:
            rows.append(_stat("Yield", _fmt_pct(info.get("yield"), 100)))
        if info.get("annualReportExpenseRatio") is not None:
            rows.append(
                _stat(
                    "Expense Ratio", _fmt_pct(info.get("annualReportExpenseRatio"), 100)
                )
            )
        if info.get("beta3Year") is not None:
            rows.append(_stat("Beta (3Y)", f"{info['beta3Year']:.2f}"))
        if info.get("legalType"):
            rows.append(_stat("Legal Type", info.get("legalType") or ""))
    elif quote_type == "CRYPTOCURRENCY":
        rows.append(
            _stat("Market Cap", _fmt_compact(info.get("marketCap")), "ai-market-cap")
        )
        if info.get("circulatingSupply") is not None:
            rows.append(
                _stat("Circulating Supply", _fmt_compact(info.get("circulatingSupply")))
            )
        if info.get("maxSupply") is not None:
            rows.append(_stat("Max Supply", _fmt_compact(info.get("maxSupply"))))
        vol24 = info.get("volume24Hr") or info.get("regularMarketVolume")
        if vol24 is not None:
            rows.append(_stat("Volume (24h)", _fmt_compact(vol24), "ai-volume-24h"))
        if info.get("startDate"):
            rows.append(_stat("Inception", _fmt_date(info.get("startDate"))))
    elif quote_type == "FUTURE":
        if info.get("openInterest") is not None:
            rows.append(_stat("Open Interest", _fmt_compact(info.get("openInterest"))))
        if info.get("regularMarketVolume") is not None:
            rows.append(
                _stat(
                    "Volume",
                    _fmt_compact(info.get("regularMarketVolume")),
                    "ai-volume",
                )
            )
        if info.get("underlyingSymbol"):
            rows.append(_stat("Underlying", info.get("underlyingSymbol") or ""))
        if info.get("expireDate"):
            rows.append(_stat("Expiry", _fmt_date(info.get("expireDate"))))
    elif quote_type == "CURRENCY":
        bid, ask = info.get("bid"), info.get("ask")
        if bid is not None and ask is not None:
            rows.append(_stat("Bid / Ask", f"{_fmt_price(bid)} / {_fmt_price(ask)}"))
    elif quote_type == "INDEX":
        if info.get("regularMarketVolume"):
            rows.append(
                _stat(
                    "Volume",
                    _fmt_compact(info.get("regularMarketVolume")),
                    "ai-volume",
                )
            )
    else:
        rows.append(_stat("Sector", info.get("sector") or "—"))
        rows.append(_stat("Industry", info.get("industry") or "—"))
        rows.append(
            _stat("Market Cap", _fmt_compact(info.get("marketCap")), "ai-market-cap")
        )
        if info.get("dividendYield") is not None:
            rows.append(_stat("Dividend Yield", _fmt_pct(info.get("dividendYield"))))

    dlow, dhigh = info.get("regularMarketDayLow"), info.get("regularMarketDayHigh")
    if dlow is not None and dhigh is not None:
        rows.append(_range_stat("Day Range", dlow, dhigh, "ai-day-range"))
    low, high = info.get("fiftyTwoWeekLow"), info.get("fiftyTwoWeekHigh")
    if low is not None and high is not None:
        rows.append(_range_stat("52-Week Range", low, high, "ai-week-range"))
    if info.get("fiftyDayAverage") is not None:
        rows.append(_stat("50-Day Avg", _fmt_price(info.get("fiftyDayAverage"))))
    if info.get("twoHundredDayAverage") is not None:
        rows.append(_stat("200-Day Avg", _fmt_price(info.get("twoHundredDayAverage"))))
    if info.get("regularMarketPreviousClose") is not None:
        rows.append(
            _stat("Prev Close", _fmt_price(info.get("regularMarketPreviousClose")))
        )
    if info.get("currency"):
        rows.append(_stat("Currency", info.get("currency") or ""))
    return "".join(rows)


def _holdings_html(holdings: list[dict]) -> str:
    if not holdings:
        return ""
    rows = "".join(
        f'<tr><td class="ai-h-sym">{_esc(h["symbol"])}</td>'
        f'<td class="ai-h-name">{_esc(h["name"])}</td>'
        f'<td class="ai-h-pct">{_fmt_pct(h["weight"], 100)}</td></tr>'
        for h in holdings[:10]
    )
    return (
        '<section class="ai-card"><h2>Top Holdings</h2>'
        f'<table class="ai-holdings">{rows}</table></section>'
    )


def _sectors_html(sectors: list[dict]) -> str:
    if not sectors:
        return ""
    top = max((s["weight"] for s in sectors), default=0) or 1
    bars = "".join(
        '<div class="ai-sec-row">'
        f'<span class="ai-sec-name">{_esc(_SECTOR_LABELS.get(s["sector"], s["sector"].replace("_", " ").title()))}</span>'
        f'<span class="ai-sec-bar"><span style="width:{(s["weight"] / top) * 100:.1f}%"></span></span>'
        f'<span class="ai-sec-pct">{_fmt_pct(s["weight"], 100)}</span>'
        "</div>"
        for s in sectors
        if s["weight"] > 0
    )
    return f'<section class="ai-card"><h2>Sector Weightings</h2><div class="ai-sectors">{bars}</div></section>'


def _card(title: str, rows: list[str]) -> str:
    if not rows:
        return ""
    return (
        f'<section class="ai-card"><h2>{_esc(title)}</h2>'
        f'<div class="ai-stats">{"".join(rows)}</div></section>'
    )


def _analyst_html(info: dict) -> str:
    rows: list[str] = []
    rec = info.get("recommendationKey")
    if rec and rec != "none":
        rows.append(_stat("Recommendation", str(rec).replace("_", " ").title()))
    if info.get("numberOfAnalystOpinions") is not None:
        rows.append(_stat("Analysts", str(info["numberOfAnalystOpinions"])))
    if info.get("targetLowPrice") is not None:
        rows.append(_stat("Target Low", _fmt_price(info["targetLowPrice"])))
    if info.get("targetMeanPrice") is not None:
        rows.append(_stat("Target Mean", _fmt_price(info["targetMeanPrice"])))
    if info.get("targetMedianPrice") is not None:
        rows.append(_stat("Target Median", _fmt_price(info["targetMedianPrice"])))
    if info.get("targetHighPrice") is not None:
        rows.append(_stat("Target High", _fmt_price(info["targetHighPrice"])))
    return _card("Analyst Coverage", rows)


def _ownership_html(info: dict) -> str:
    rows: list[str] = []
    if info.get("heldPercentInstitutions") is not None:
        rows.append(
            _stat("Institutions", _fmt_pct(info["heldPercentInstitutions"], 100))
        )
    if info.get("heldPercentInsiders") is not None:
        rows.append(_stat("Insiders", _fmt_pct(info["heldPercentInsiders"], 100)))
    if info.get("sharesOutstanding") is not None:
        rows.append(
            _stat("Shares Outstanding", _fmt_compact(info["sharesOutstanding"]))
        )
    if info.get("floatShares") is not None:
        rows.append(_stat("Float", _fmt_compact(info["floatShares"])))
    if info.get("shortPercentOfFloat") is not None:
        rows.append(
            _stat("Short % of Float", _fmt_pct(info["shortPercentOfFloat"], 100))
        )
    if info.get("shortRatio") is not None:
        rows.append(_stat("Short Ratio", f"{info['shortRatio']:.2f}"))
    return _card("Ownership", rows)


def _valuation_html(info: dict) -> str:
    rows: list[str] = []

    def _num(label: str, key: str) -> None:
        value = info.get(key)
        if value is not None:
            rows.append(_stat(label, f"{value:.2f}"))

    _num("P/E (TTM)", "trailingPE")
    _num("Forward P/E", "forwardPE")
    _num("PEG Ratio", "trailingPegRatio")
    _num("Price/Book", "priceToBook")
    _num("Price/Sales", "priceToSalesTrailing12Months")
    if info.get("enterpriseValue") is not None:
        rows.append(_stat("Enterprise Value", _fmt_compact(info["enterpriseValue"])))
    _num("EV/Revenue", "enterpriseToRevenue")
    _num("EV/EBITDA", "enterpriseToEbitda")
    if info.get("profitMargins") is not None:
        rows.append(_stat("Profit Margin", _fmt_pct(info["profitMargins"], 100)))
    if info.get("operatingMargins") is not None:
        rows.append(_stat("Operating Margin", _fmt_pct(info["operatingMargins"], 100)))
    if info.get("returnOnEquity") is not None:
        rows.append(_stat("Return on Equity", _fmt_pct(info["returnOnEquity"], 100)))
    _num("Beta", "beta")
    return _card("Valuation", rows)


def _calendar_html(calendar: object, info: dict) -> str:
    cal: dict = calendar if isinstance(calendar, dict) else {}

    def _d(value: object) -> str:
        if isinstance(value, (list, tuple)):
            value = value[0] if value else None
        if value is None:
            return ""
        return getattr(value, "isoformat", lambda: str(value))()

    rows: list[str] = []
    earnings = _d(cal.get("Earnings Date"))
    if earnings:
        rows.append(_stat("Next Earnings", earnings))
    exdiv = _d(cal.get("Ex-Dividend Date"))
    if exdiv:
        rows.append(_stat("Ex-Dividend Date", exdiv))
    divdate = _d(cal.get("Dividend Date"))
    if divdate:
        rows.append(_stat("Dividend Date", divdate))
    if info.get("lastDividendValue") is not None:
        rows.append(_stat("Last Dividend", _fmt_price(info["lastDividendValue"])))
    if info.get("dividendRate") is not None:
        rows.append(_stat("Forward Dividend", _fmt_price(info["dividendRate"])))
    if cal.get("Earnings Average") is not None:
        rows.append(_stat("EPS Estimate", _fmt_price(cal["Earnings Average"])))
    if cal.get("Revenue Average") is not None:
        rows.append(_stat("Revenue Estimate", _fmt_compact(cal["Revenue Average"])))
    return _card("Calendar", rows)


def _performance_html(info: dict, history: Any) -> str:
    """Build a full-width strip of trailing price-performance returns."""
    import pandas as pd

    cells: list[tuple[str, float]] = []
    one_day = info.get("regularMarketChangePercent")
    if one_day is not None:
        cells.append(("1D", float(one_day)))

    closes = None
    if (
        history is not None
        and not getattr(history, "empty", True)
        and "Close" in history
    ):
        closes = history["Close"].dropna()
    if closes is not None and not closes.empty:
        last = float(closes.iloc[-1])
        last_date = closes.index[-1]

        def _ret(offset: Any = None, *, ytd: bool = False) -> float | None:
            if ytd:
                base = closes.asof(pd.Timestamp(last_date.year, 1, 1, tz=last_date.tz))
            else:
                base = closes.asof(last_date - offset)
            try:
                base = float(base)
            except (TypeError, ValueError):
                return None
            if pd.isna(base) or base == 0:
                return None
            return (last / base - 1) * 100

        windows = (
            ("1W", pd.DateOffset(days=7), False),
            ("1M", pd.DateOffset(months=1), False),
            ("3M", pd.DateOffset(months=3), False),
            ("6M", pd.DateOffset(months=6), False),
            ("YTD", None, True),
            ("1Y", pd.DateOffset(years=1), False),
            ("3Y", pd.DateOffset(years=3), False),
            ("5Y", pd.DateOffset(years=5), False),
            ("10Y", pd.DateOffset(years=10), False),
        )
        for label, offset, ytd in windows:
            value = _ret(offset, ytd=ytd)
            if value is not None:
                cells.append((label, value))

    if not cells:
        return ""

    items = []
    for label, pct in cells:
        cls = "ai-up" if pct >= 0 else "ai-down"
        sign = "+" if pct >= 0 else ""
        items.append(
            f'<div class="ai-perf-item"><span class="ai-perf-label">{_esc(label)}</span>'
            f'<span class="ai-perf-val {cls}">{sign}{pct:.2f}%</span></div>'
        )
    return (
        '<section class="ai-card ai-perf-card"><h2>Performance</h2>'
        f'<div class="ai-perf">{"".join(items)}</div></section>'
    )


def build_asset_info_fragment(symbol: str) -> str:
    """Build the inner Asset Info HTML body for *symbol*."""
    return _render_fragment(symbol, _fetch(symbol))


def _render_fragment(symbol: str, payload: dict) -> str:
    """Render the Asset Info body from an already-fetched *payload*."""
    info = payload["info"]
    if not info:
        return f'<div class="ai-empty">No data found for {_esc(symbol.upper())}.</div>'

    name = info.get("longName") or info.get("shortName") or symbol.upper()
    quote_type = str(info.get("quoteType") or "").title()
    exchange = info.get("fullExchangeName") or info.get("exchange") or ""
    currency = info.get("currency") or ""
    price = info.get("regularMarketPrice")
    change = info.get("regularMarketChange")
    change_pct = info.get("regularMarketChangePercent")
    direction = "ai-up" if (change or 0) >= 0 else "ai-down"
    sign = "+" if (change or 0) >= 0 else ""
    summary = info.get("longBusinessSummary") or ""

    quote_type_raw = str(info.get("quoteType") or "").upper()
    sections = [
        f'<section class="ai-card ai-summary"><h2>Summary</h2><p>{_esc(summary)}</p></section>'
        if summary
        else "",
        _performance_html(info, payload.get("history")),
    ]
    if quote_type_raw == "EQUITY":
        sections.append(_valuation_html(info))
        sections.append(_calendar_html(payload.get("calendar"), info))
        sections.append(_analyst_html(info))
        sections.append(_ownership_html(info))
    sections.append(_holdings_html(payload["holdings"]))
    sections.append(_sectors_html(payload["sectors"]))

    return (
        '<div class="ai-root">'
        '<header class="ai-header">'
        '<div class="ai-head-main">'
        f'<div class="ai-exch">{_esc(exchange)}{" · " + _esc(currency) if currency else ""}'
        f"{' · ' + quote_type if quote_type else ''}</div>"
        f'<div class="ai-name">{_esc(name)} <span class="ai-sym">({_esc(symbol.upper())})</span></div>'
        f'<div class="ai-quote"><span class="ai-price" id="ai-price">{_fmt_price(price)}</span>'
        f'<span class="ai-change {direction}" id="ai-change">{sign}{_fmt_price(change)} '
        f"({sign}{_fmt_pct(change_pct)})</span></div>"
        "</div>"
        f'<div class="ai-head-stats">{_overview_stats(info)}</div>'
        "</header>"
        f'<div class="ai-grid">{"".join(s for s in sections if s)}</div>'
        "</div>"
    )


def _start_live_quotes(widget: Any, symbol: str, info: dict) -> None:
    """Stream live quotes for *symbol* into the Asset Info header.

    Reuses the chart's :class:`RealtimeStreamer` in quote-only mode so the price
    and change update from the same ``yf.WebSocket`` feed that drives the chart
    marquee, emitting an ``assetinfo:quote`` event the page renders in place.
    Any previously started Asset Info streamer is stopped first so a symbol
    change never leaves a WebSocket listener running.
    """
    from openbb_yfinance.utils.tvchart_datafeed import BarCache, RealtimeStreamer

    def _num(value: Any) -> float | None:
        return float(value) if value is not None else None

    def _on_quote(_sym: str, msg: dict) -> None:
        widget.emit(
            "assetinfo:quote",
            {
                "price": _num(msg.get("price")),
                "change": _num(msg.get("change")),
                "changePercent": _num(msg.get("change_percent")),
                "dayHigh": _num(msg.get("day_high")),
                "dayLow": _num(msg.get("day_low")),
                "marketCap": _num(msg.get("market_cap")),
                "volume": _num(msg.get("day_volume")),
                "vol24": _num(msg.get("vol_24hr")),
            },
        )

    while _LIVE_ASSET_INFO:
        _prev_widget, prev_streamer = _LIVE_ASSET_INFO.pop()
        with contextlib.suppress(Exception):
            prev_streamer.stop()

    streamer = RealtimeStreamer(widget, BarCache(), on_quote=_on_quote)
    delay = int(info.get("exchangeDataDelayedBy") or 0)
    streamer.subscribe("asset-info", symbol.upper(), "1m", delay_minutes=delay)
    _LIVE_ASSET_INFO.append((widget, streamer))


def _build_live_document(
    fragment: str, widget_id: str, token: str | None, theme: str
) -> str:
    """Assemble the full Asset Info page (PyWry theme, ws-bridge, live handler).

    Mirrors the document :func:`pywry.inline.show` builds, but creates the widget
    in ``browser_only`` mode (no ipywidgets dependency) so it serves from the
    mounted inline server inside the OpenBB API.
    """
    from pywry.assets import get_pywry_css, get_scrollbar_js, get_toast_css
    from pywry.inline import _get_pywry_bridge_js
    from pywry.toolbar import wrap_content_with_toolbars

    is_light = str(theme).lower() == "light"
    html_theme = "light" if is_light else "dark"
    widget_theme = "pywry-theme-light" if is_light else "pywry-theme-dark"
    layout_css = (
        "* { margin: 0; padding: 0; box-sizing: border-box; }"
        "html, body { height: 100%; width: 100%; overflow: hidden; }"
        "body { display: flex; flex-direction: column; }"
        ".pywry-widget { width: 100%; height: 100%; display: flex;"
        " flex-direction: column; background: var(--pywry-bg-primary);"
        " color: var(--pywry-text-primary); position: relative; }"
    )
    content = wrap_content_with_toolbars(fragment, None)
    return (
        f'<!DOCTYPE html><html class="{html_theme}"><head><meta charset="utf-8">'
        "<title>OpenBB - Yahoo Finance Asset Info</title>"
        f"<style>{get_pywry_css()}</style>"
        f"<style>{get_toast_css()}</style>"
        f"<style>{layout_css}</style>"
        f'<style id="pywry-inline-css">{_CSS.read_text(encoding="utf-8")}</style>'
        f"<script>{get_scrollbar_js()}</script>"
        f"{_get_pywry_bridge_js(widget_id, token)}"
        "</head><body>"
        f'<div class="pywry-widget pywry-custom-scrollbar {widget_theme}">{content}</div>'
        f"<script>{_LIVE_JS.read_text(encoding='utf-8')}</script>"
        "</body></html>"
    )


async def asset_info_widget_html(symbol: str = "AAPL", theme: str = "dark") -> str:
    """Return the live Asset Info widget HTML for the Workspace iframe.

    Served through PyWry's inline server — the same transport as the TradingView
    chart — so the header price and change update live from the same
    ``yf.WebSocket`` feed that drives the chart's marquee.
    """
    import uuid

    from pywry.inline import InlineWidget, _generate_widget_token

    from openbb_yfinance.utils.pywry_server import bind_loop, ensure_pywry_mounted

    ensure_pywry_mounted()
    bind_loop()

    payload = _fetch(symbol)
    fragment = _render_fragment(symbol, payload)
    widget_id = uuid.uuid4().hex
    token = _generate_widget_token(widget_id)
    document = _build_live_document(fragment, widget_id, token, theme)
    widget = InlineWidget(
        html=document, widget_id=widget_id, browser_only=True, token=token
    )

    info = payload["info"]
    if info:
        with contextlib.suppress(Exception):
            _start_live_quotes(widget, symbol, info)

    return document
