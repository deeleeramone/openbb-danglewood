"""HKEX Workspace widget and datafeed routes, served by the router extension."""

from typing import Any


def _compact(value: Any, prefix: str = "") -> str:
    """Format a number with a K/M/B/T suffix and an optional prefix."""
    if value is None:
        return "—"
    try:
        n = float(value)
    except (TypeError, ValueError):
        return str(value)
    for div, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(n) >= div:
            return f"{prefix}{n / div:,.2f}{suf}"
    return f"{prefix}{n:,.2f}"


def register_widgets(router) -> None:  # noqa: PLR0915
    """Register the HKEX widget, options and UDF routes on the router's API router."""
    import base64

    from async_lru import alru_cache
    from openbb_core.app.service.system_service import SystemService
    from openbb_core.provider.utils.helpers import make_request

    from openbb_hkex.models.company_filings import (
        _FORM_GROUP_CODES,
        HkexCompanyFilingsFetcher,
    )
    from openbb_hkex.utils.client import find_stock_id
    from openbb_hkex.utils.udf import add_udf_routes

    api = router.api_router
    api_prefix = SystemService().system_settings.api_settings.prefix or ""
    base = f"{api_prefix}/hkex"

    add_udf_routes(api, base)

    form_group_options = [
        {"label": "All Categories", "value": "all"},
        {"label": "Annual Report", "value": "annual"},
        {"label": "Interim / Half-Year Report", "value": "interim"},
        {"label": "Quarterly Report (GEM)", "value": "quarterly"},
        {"label": "ESG Information / Report", "value": "esg"},
        {"label": "Financial Statements (all)", "value": "financials"},
        {"label": "Announcements & Notices", "value": "announcements"},
        {"label": "Circulars", "value": "circulars"},
        {"label": "Listing Documents", "value": "listing_docs"},
        {"label": "Monthly Returns", "value": "monthly_returns"},
        {"label": "Proxy Forms", "value": "proxy"},
        {"label": "Next-Day Disclosure (Buyback)", "value": "buyback"},
        {"label": "Constitutional Documents", "value": "constitutional"},
        {"label": "Takeovers Code dealings", "value": "takeovers"},
        {"label": "Debt & Structured Products", "value": "debt"},
        {"label": "ETF Trading Information", "value": "etf_info"},
    ]

    @api.get("/apps.json", include_in_schema=False)
    async def apps_json() -> list[dict[str, Any]]:
        from openbb_hkex.utils.apps import build_hkex_apps

        return build_hkex_apps()

    @alru_cache(maxsize=1)
    async def _all_security_choices() -> list[dict[str, Any]]:
        from openbb_hkex.models.securities_master import (
            HkexSecuritiesMasterFetcher,
        )

        rows = await HkexSecuritiesMasterFetcher().fetch_data({}, {})
        out: list[dict[str, Any]] = []
        for row in rows:
            r = row.model_dump()  # type: ignore[union-attr]
            code = r.get("code")
            if not code:
                continue
            name = r.get("name") or ""
            cat = r.get("category") or ""
            label = f"{code} — {name}".strip(" —")
            if cat:
                label = f"{label} · {cat}"
            out.append({"label": label, "value": code})
        return out

    @api.get("/security_choices", include_in_schema=False)
    async def security_choices() -> list[dict[str, Any]]:
        return await _all_security_choices()

    @api.get("/option_underlyings", include_in_schema=False)
    async def option_underlyings() -> list[dict[str, Any]]:
        from openbb_hkex.utils.client import (
            DERIVATIVE_PRODUCTS,
            call_widget,
        )

        out = [
            {"label": f"{c} — {m.get('name', c)}", "value": c}
            for c, m in DERIVATIVE_PRODUCTS.items()
        ]
        try:
            roster = (await call_widget("getstockderivativeslist", type=2)).get(
                "stocklist", []
            )
        except Exception:  # noqa: BLE001
            roster = []
        for r in roster:
            cd = (r.get("cd") or "").upper()
            if cd and r.get("opt"):
                out.append(
                    {"label": f"{cd} — {r.get('nm') or ''}".strip(" —"), "value": cd}
                )
        return out

    _MARKET_STATS_GROUP_OPTIONS = [
        {"label": "Trading Venue", "value": "venue"},
        {"label": "Programme (HKEX vs Stock Connect)", "value": "programme"},
        {"label": "Currency", "value": "currency"},
        {"label": "Hang Seng Sector", "value": "sector"},
    ]
    _MARKET_STATS_PROGRAMME_OPTIONS = [
        {"label": "All Listed", "value": "all"},
        {"label": "HKEX (Main Board + GEM)", "value": "hkex"},
        {"label": "Stock Connect (A-shares)", "value": "connect"},
    ]

    @api.get(
        "/market_data",
        openapi_extra={
            "widget_config": {
                "type": "markdown",
                "name": "Market Statistics",
                "description": (
                    "Aggregate counts, market capitalisation and turnover of the "
                    "HKEX-listed and Stock Connect (A-share) universe, grouped by "
                    "trading venue, programme, currency or Hang Seng sector. "
                    "Market-cap % is computed within each currency basis (HKEX in "
                    "HKD, Connect in CNY). Sector grouping covers the Hang Seng "
                    "Composite universe (HKEX equities, ~95% of market cap)."
                ),
                "category": "Overview",
                "widgetId": "hkex_market_data",
                "refetchInterval": False,
                "params": [
                    {
                        "paramName": "group_by",
                        "label": "Group By",
                        "description": "Dimension to aggregate the listed universe by.",
                        "type": "text",
                        "value": "venue",
                        "options": _MARKET_STATS_GROUP_OPTIONS,
                    },
                    {
                        "paramName": "programme",
                        "label": "Programme",
                        "description": "Restrict to HKEX, Stock Connect, or all.",
                        "type": "text",
                        "value": "all",
                        "options": _MARKET_STATS_PROGRAMME_OPTIONS,
                    },
                ],
                "gridData": {"w": 40, "h": 16},
            },
        },
    )
    async def market_data(
        group_by: str = "venue",
        programme: str = "all",
    ) -> str:
        from openbb_hkex.models.market_statistics import (
            HkexMarketStatisticsFetcher,
        )

        rows = await HkexMarketStatisticsFetcher().fetch_data(
            {"group_by": group_by, "programme": programme}, {}
        )
        group_label = next(
            (o["label"] for o in _MARKET_STATS_GROUP_OPTIONS if o["value"] == group_by),
            group_by,
        )
        programme_label = next(
            (
                o["label"]
                for o in _MARKET_STATS_PROGRAMME_OPTIONS
                if o["value"] == programme
            ),
            programme,
        )
        lines = [
            "## HKEX Market Statistics",
            f"**By {group_label}** · {programme_label}",
            "",
            "| Group | Programme | Ccy | Count | % | Market Cap | % | Turnover |",
            "|---|---|---|--:|--:|--:|--:|--:|",
        ]
        total = 0
        for row in rows:
            r = row.model_dump()  # type: ignore[union-attr]
            ccy = r.get("currency") or ""
            pfx = f"{ccy} " if ccy else ""
            cnt = int(r.get("count") or 0)
            total += cnt
            cp, mcp = r.get("count_pct"), r.get("market_cap_pct")
            lines.append(
                f"| {r.get('group') or '—'} | {r.get('programme') or '—'} "
                f"| {ccy or '—'} | {cnt:,} "
                f"| {f'{cp:.1f}%' if cp is not None else '—'} "
                f"| {_compact(r.get('market_cap'), pfx)} "
                f"| {f'{mcp:.1f}%' if mcp is not None else '—'} "
                f"| {_compact(r.get('turnover'), pfx)} |"
            )
        lines += ["", f"**{len(rows)} groups · {total:,} securities**"]
        return "\n".join(lines)

    _LOOKUP_VENUE_OPTIONS = [
        {"label": "All Markets", "value": "all"},
        {"label": "HKEX Main Board", "value": "Main Board"},
        {"label": "HKEX GEM", "value": "GEM"},
        {"label": "Shanghai Connect", "value": "Shanghai"},
        {"label": "Shenzhen Connect", "value": "Shenzhen"},
    ]
    _LOOKUP_MAX_ROWS = 60

    @api.get(
        "/lookup",
        openapi_extra={
            "widget_config": {
                "type": "table",
                "name": "Securities Lookup",
                "description": (
                    "Search and screen the HKEX-listed and Stock Connect (A-share) "
                    "universe with an intraday price sparkline per row — the HKEX "
                    "A-share Lookup Tool, extended to HKEX equities. Filter by market "
                    "and keyword; rows are ranked by turnover."
                ),
                "category": "Securities",
                "widgetId": "hkex_lookup",
                "refetchInterval": False,
                "params": [
                    {
                        "paramName": "venue",
                        "label": "Market",
                        "description": "Restrict to a trading venue.",
                        "type": "text",
                        "value": "all",
                        "options": _LOOKUP_VENUE_OPTIONS,
                    },
                    {
                        "paramName": "keyword",
                        "label": "Stock Code / Keyword",
                        "description": "Filter by stock code or name (optional).",
                        "type": "text",
                        "value": "",
                    },
                    {
                        "paramName": "limit",
                        "label": "Rows",
                        "description": f"Max rows to display (1-{_LOOKUP_MAX_ROWS}).",
                        "type": "number",
                        "value": 25,
                    },
                ],
                "data": {
                    "table": {
                        "columnsDefs": [
                            {
                                "field": "symbol",
                                "headerName": "Code",
                                "pinned": "left",
                                "width": 90,
                                "cellDataType": "text",
                            },
                            {"field": "name", "headerName": "Name", "width": 200},
                            {"field": "venue", "headerName": "Exchange", "width": 130},
                            {"field": "currency", "headerName": "Ccy", "width": 70},
                            {"field": "last_price", "headerName": "Last", "width": 110},
                            {"field": "change_pct", "headerName": "Chg %", "width": 90},
                            {
                                "field": "turnover_b",
                                "headerName": "Turnover (B)",
                                "width": 130,
                            },
                            {
                                "field": "market_cap_b",
                                "headerName": "Mkt Cap (B)",
                                "width": 130,
                            },
                            {"field": "pe", "headerName": "P/E", "width": 90},
                            {
                                "field": "dividend_yield",
                                "headerName": "Yield %",
                                "width": 90,
                            },
                            {
                                "field": "intraday",
                                "headerName": "Intraday Movement",
                                "width": 200,
                                "sparkline": {
                                    "type": "line",
                                    "options": {
                                        "stroke": "#2563eb",
                                        "strokeWidth": 2,
                                        "pointsOfInterest": {
                                            "maximum": {
                                                "fill": "#22c55e",
                                                "stroke": "#16a34a",
                                                "size": 4,
                                            },
                                            "minimum": {
                                                "fill": "#ef4444",
                                                "stroke": "#dc2626",
                                                "size": 4,
                                            },
                                        },
                                    },
                                },
                            },
                        ]
                    }
                },
                "gridData": {"w": 40, "h": 16},
            },
        },
    )
    async def lookup(
        venue: str = "all",
        keyword: str = "",
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        import asyncio

        from openbb_hkex.models._reference import parse_num
        from openbb_hkex.utils.aggregates import (
            get_ashare_universe,
            get_equity_universe,
        )
        from openbb_hkex.utils.client import call_widget

        equities, ashares = await asyncio.gather(
            get_equity_universe(), get_ashare_universe()
        )
        rows = [*equities, *ashares]

        if venue and venue != "all":
            rows = [r for r in rows if r.get("venue") == venue]
        kw = (keyword or "").strip().lower()
        if kw:
            rows = [
                r
                for r in rows
                if kw in (r.get("name") or "").lower()
                or kw in (r.get("symbol") or "").lower()
            ]

        rows.sort(key=lambda r: r.get("turnover") or 0.0, reverse=True)
        n = max(1, min(int(limit or 25), _LOOKUP_MAX_ROWS))
        rows = rows[:n]

        sem = asyncio.Semaphore(20)

        async def _sparkline(ric: str | None) -> list[float]:
            if not ric:
                return []
            async with sem:
                try:
                    data = await call_widget(
                        "getchartdata2", ric=ric, span="1", int="5"
                    )
                except Exception:  # noqa: BLE001
                    return []
            closes: list[float] = []
            for bar in data.get("datalist", []) or []:
                if len(bar) > 4 and bar[4] is not None:
                    closes.append(float(bar[4]))
            return closes

        sparks = await asyncio.gather(*[_sparkline(r.get("ric")) for r in rows])

        out: list[dict[str, Any]] = []
        for r, spark in zip(rows, sparks):
            mc, to = r.get("market_cap"), r.get("turnover")
            out.append(
                {
                    "symbol": r.get("symbol"),
                    "name": r.get("name"),
                    "venue": r.get("venue"),
                    "currency": r.get("currency"),
                    "last_price": parse_num(r.get("last_price")),
                    "change_pct": parse_num(r.get("change_pct")),
                    "turnover_b": round(to / 1e9, 3) if to else None,
                    "market_cap_b": round(mc / 1e9, 2) if mc else None,
                    "pe": parse_num(r.get("pe")),
                    "dividend_yield": parse_num(r.get("dividend_yield")),
                    "intraday": spark,
                }
            )
        return out

    @api.get(
        "/etf_sectors",
        openapi_extra={
            "widget_config": {
                "type": "table",
                "name": "ETF Sector Weights",
                "description": (
                    "Sector allocation of an HKEX-listed ETF, aggregated from its "
                    "holdings basket by weight."
                ),
                "category": "ETFs",
                "widgetId": "hkex_etf_sectors",
                "refetchInterval": False,
                "params": [
                    {
                        "paramName": "symbol",
                        "label": "Symbol",
                        "description": "HKEX ETF stock code.",
                        "type": "endpoint",
                        "value": "03037",
                        "optionsEndpoint": f"{base}/security_choices",
                        "style": {"popupWidth": 600},
                    },
                ],
                "data": {
                    "table": {
                        "columnsDefs": [
                            {
                                "field": "sector",
                                "headerName": "Sector",
                                "pinned": "left",
                                "width": 220,
                                "cellDataType": "text",
                            },
                            {"field": "weight", "headerName": "Weight %", "width": 120},
                            {
                                "field": "holdings",
                                "headerName": "# Holdings",
                                "width": 120,
                            },
                            {
                                "field": "market_value",
                                "headerName": "Market Value",
                                "width": 160,
                            },
                        ]
                    }
                },
                "gridData": {"w": 20, "h": 14},
            },
        },
    )
    async def etf_sectors(symbol: str = "03037") -> list[dict[str, Any]]:
        from openbb_hkex.models.etf_holdings import HkexEtfHoldingsFetcher

        try:
            rows = await HkexEtfHoldingsFetcher().fetch_data({"symbol": symbol}, {})
        except Exception:  # noqa: BLE001
            return []
        agg: dict[str, dict[str, Any]] = {}
        for row in rows:
            r = row.model_dump()  # type: ignore[union-attr]
            sector = r.get("sector") or "Unclassified"
            g = agg.setdefault(
                sector,
                {"sector": sector, "weight": 0.0, "holdings": 0, "market_value": 0.0},
            )
            g["weight"] += r.get("weight") or 0.0
            g["holdings"] += 1
            g["market_value"] += r.get("market_value") or 0.0
        out = sorted(agg.values(), key=lambda x: x["weight"], reverse=True)
        for g in out:
            g["weight"] = round(g["weight"], 2)
            g["market_value"] = round(g["market_value"])
        return out

    _REPORT_TYPE_OPTIONS = [
        {
            "label": "Constituent Performance (Month-end)",
            "value": "daily-bulletin-month-end:con-pdf-1",
        },
    ]

    @api.get("/report_series_choices", include_in_schema=False)
    async def report_series_choices_route() -> list[dict[str, Any]]:
        from openbb_hkex.utils.index_sources import report_series_choices

        return await report_series_choices()

    @api.get("/report_date_choices", include_in_schema=False)
    async def report_date_choices_route(
        series: str = "hsi",
        report_type: str = "daily-bulletin-month-end:con-pdf-1",
    ) -> list[dict[str, Any]]:
        from openbb_hkex.utils.index_sources import report_date_choices

        return await report_date_choices(series, report_type)

    @api.post(
        "/open_index_report",
        openapi_extra={
            "widget_config": {
                "type": "multi_file_viewer",
                "name": "HSI Index Reports",
                "description": (
                    "Hang Seng dated index reports — Index Daily Bulletin, "
                    "Performance Summary and Constituent Performance (daily and "
                    "month-end) — for every index family, by date."
                ),
                "category": "Indices",
                "subCategory": "Reports",
                "refetchInterval": False,
                "widgetId": "hkex_index_reports",
                "params": [
                    {
                        "paramName": "series",
                        "label": "Index Family",
                        "type": "endpoint",
                        "value": "hsi",
                        "optionsEndpoint": f"{base}/report_series_choices",
                        "style": {"popupWidth": 700},
                    },
                    {
                        "paramName": "report_type",
                        "label": "Report",
                        "type": "text",
                        "value": "daily-bulletin-month-end:con-pdf-1",
                        "options": _REPORT_TYPE_OPTIONS,
                    },
                    {
                        "paramName": "document_url",
                        "label": "Date",
                        "description": "Select one or more report dates to open.",
                        "type": "endpoint",
                        "optionsEndpoint": f"{base}/report_date_choices",
                        "optionsParams": {
                            "series": "$series",
                            "report_type": "$report_type",
                        },
                        "show": False,
                        "roles": ["fileSelector"],
                        "multiSelect": True,
                        "style": {"popupWidth": 500},
                    },
                ],
                "gridData": {"w": 40, "h": 30},
            }
        },
    )
    async def post_open_index_report(params: dict) -> list:
        urls = params.get("document_url") or []
        if isinstance(urls, str):
            urls = [urls]
        documents: list = []
        for u in urls:
            if isinstance(u, str) and u.startswith("http"):
                doc = await open_document(u)
                if doc:
                    documents.append(doc)
        return documents

    @api.get(
        "/index_performance",
        openapi_extra={
            "widget_config": {
                "type": "table",
                "name": "Index Performance",
                "description": (
                    "Daily performance of every index in a Hang Seng family — close, "
                    "change, % change, dividend yield, P/E and turnover (Index Daily "
                    "Bulletin)."
                ),
                "category": "Indices",
                "widgetId": "hkex_index_performance",
                "refetchInterval": False,
                "params": [
                    {
                        "paramName": "series",
                        "label": "Index Family",
                        "type": "endpoint",
                        "value": "hsi",
                        "optionsEndpoint": f"{base}/report_series_choices",
                        "style": {"popupWidth": 700},
                    },
                    {
                        "paramName": "date",
                        "label": "Date",
                        "description": "Defaults to the latest available bulletin.",
                        "type": "endpoint",
                        "optionsEndpoint": f"{base}/report_date_choices",
                        "optionsParams": {
                            "series": "$series",
                            "report_type": "daily-bulletin:idx",
                        },
                    },
                ],
                "data": {
                    "table": {
                        "columnsDefs": [
                            {
                                "field": "index",
                                "headerName": "Index",
                                "pinned": "left",
                                "width": 280,
                                "cellDataType": "text",
                            },
                            {"field": "currency", "headerName": "Ccy", "width": 70},
                            {"field": "close", "headerName": "Close", "width": 120},
                            {"field": "change", "headerName": "Change", "width": 110},
                            {"field": "change_pct", "headerName": "% Chg", "width": 90},
                            {
                                "field": "dividend_yield",
                                "headerName": "Div Yld %",
                                "width": 100,
                            },
                            {"field": "pe_ratio", "headerName": "P/E", "width": 80},
                            {
                                "field": "index_turnover_m",
                                "headerName": "Idx Turnover (M)",
                                "width": 150,
                            },
                            {
                                "field": "market_turnover_m",
                                "headerName": "Mkt Turnover (M)",
                                "width": 150,
                            },
                            {"field": "high", "headerName": "High", "width": 110},
                            {"field": "low", "headerName": "Low", "width": 110},
                        ]
                    }
                },
                "gridData": {"w": 40, "h": 18},
            },
        },
    )
    async def index_performance(
        series: str = "hsi",
        date: str = "",
    ) -> list[dict[str, Any]]:
        from openbb_hkex.utils.index_sources import fetch_index_bulletin

        try:
            return await fetch_index_bulletin(series, date or None)
        except Exception:  # noqa: BLE001
            return []

    _SYMBOL_PARAM = {
        "paramName": "symbol",
        "label": "Symbol",
        "description": "Any HKEX-listed security code.",
        "type": "endpoint",
        "value": "00700",
        "optionsEndpoint": f"{base}/security_choices",
        "style": {"popupWidth": 600},
    }

    def _hnum(v: Any, prefix: str = "") -> str:
        if v is None:
            return "—"
        try:
            n = float(v)
        except (TypeError, ValueError):
            return str(v)
        for div, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
            if abs(n) >= div:
                return f"{prefix}{n / div:,.2f}{suf}"
        return f"{prefix}{n:,.2f}"

    @api.get(
        "/ticker",
        openapi_extra={
            "widget_config": {
                "type": "markdown",
                "name": "Ticker",
                "description": "Price snapshot, classification, identifiers and description for a security.",
                "category": "Securities",
                "widgetId": "hkex_ticker",
                "refetchInterval": False,
                "params": [_SYMBOL_PARAM],
                "gridData": {"w": 24, "h": 24},
            },
        },
    )
    async def ticker(symbol: str = "00700") -> str:
        from openbb_hkex.models._reference import (
            extract_fundamentals,
            extract_reference,
            parse_num,
            scaled,
        )
        from openbb_hkex.utils.client import call_widget, to_hk_symbol

        try:
            q = (await call_widget("getequityquote", sym=to_hk_symbol(symbol))).get(
                "quote", {}
            )
        except Exception:  # noqa: BLE001
            q = {}
        if not q:
            return f"No data for **{symbol}**."
        ref, fun = extract_reference(q), extract_fundamentals(q)
        code = (q.get("ric") or symbol).split(".")[0].zfill(5)
        ccy = ref.get("currency") or "HKD"
        last, prev = parse_num(q.get("ls")), parse_num(q.get("hc"))
        price = last if last is not None else prev
        nc, pc = parse_num(q.get("nc")), parse_num(q.get("pc"))
        vol = scaled(q.get("vo"), q.get("vo_u"))
        lo, hi = parse_num(q.get("lo52")), parse_num(q.get("hi52"))
        chg = "—"
        if nc is not None:
            chg = f"{nc:+,.3f}" + (f" ({pc:+.2f}%)" if pc is not None else "")

        lines = [
            f"## {q.get('nm') or q.get('nm_s') or code}",
            f"`{code}` · {ref.get('product_type') or ''}".rstrip(" ·"),
            "",
            f"# {ccy} {price:,.3f}" if price is not None else "# —",
            f"Day's change **{chg}** · Volume **{_hnum(vol) if vol is not None else '—'}**"
            f" · Prev close **{f'{prev:,.3f}' if prev is not None else '—'}**",
        ]
        meta = [
            f"**{k}:** {v}"
            for k, v in (
                ("Sector", ref.get("sector")),
                ("Industry", ref.get("industry_category")),
            )
            if v
        ]
        if meta:
            lines += ["", " · ".join(meta)]
        if ref.get("business_address"):
            lines += ["", ref["business_address"]]
        rows = [
            ("Type", ref.get("product_type")),
            ("ISIN", ref.get("isin")),
            ("SEDOL", ref.get("sedol")),
            ("Exchange", ref.get("stock_exchange")),
            (
                "Listing",
                f"{ref.get('listing_date') or '—'} ({ref.get('listing_category') or '—'})",
            ),
            ("Currency", ccy),
            ("Board lot", ref.get("board_lot")),
            ("Shares outstanding", _hnum(ref.get("shares_outstanding"))),
            ("Market cap", _hnum(fun.get("market_cap"), ccy + " ")),
            ("P/E", fun.get("pe_ratio")),
            (
                "EPS",
                f"{fun['eps']} {fun.get('eps_currency') or ''}".strip()
                if fun.get("eps") is not None
                else None,
            ),
            (
                "Dividend yield",
                f"{fun['dividend_yield']}%"
                if fun.get("dividend_yield") is not None
                else None,
            ),
            ("52-week range", f"{lo:,.3f} – {hi:,.3f}" if lo and hi else None),
            ("Chairman", ref.get("chairman")),
            ("Registrar", ref.get("registrar")),
            ("Incorporated", ref.get("inc_country")),
            ("Fiscal year end", ref.get("fiscal_year_end")),
        ]
        lines += ["", "| | |", "|---|---|"]
        lines += [f"| {k} | {v if v not in (None, '') else '—'} |" for k, v in rows]
        if ref.get("long_description"):
            lines += ["", "### Description", "", ref["long_description"]]
        return "\n".join(lines)

    @api.get("/symbol_choices", include_in_schema=False)
    async def symbol_choices(symbol: str | None = None) -> list[dict[str, Any]]:
        query = (symbol or "").strip() or "0"
        results = await find_stock_id(query)
        if not results:
            results = await find_stock_id(query, kind="inactive")
        out = []
        seen: set[str] = set()
        for r in results[:50]:
            code = str(r.get("code") or "").zfill(5)
            if code in seen:
                continue
            seen.add(code)
            label = f"{code} — {r.get('name')}"
            out.append({"label": label, "value": code})
        return out

    @api.get("/form_group_choices", include_in_schema=False)
    async def form_group_choices() -> list[dict[str, Any]]:
        return form_group_options

    @api.get("/document_choices", include_in_schema=False)
    async def document_choices(
        symbol: str | None = None,
        form_group: str = "all",
    ) -> list[dict[str, Any]]:
        if not symbol:
            return []
        if form_group not in _FORM_GROUP_CODES:
            form_group = "all"

        fetcher = HkexCompanyFilingsFetcher()
        params = {
            "symbol": symbol,
            "form_group": form_group,
        }
        items = await fetcher.fetch_data(params, {})

        out: list[dict[str, Any]] = []
        for it in items:
            r = it.model_dump()  # type: ignore[union-attr]
            url = r.get("report_url")
            if not url:
                continue
            label = f"{r.get('filing_date')} — {r.get('title') or r.get('report_type') or 'Filing'}"
            if r.get("file_size"):
                label = f"{label} ({r['file_size']})"
            out.append({"label": label, "value": url})
        return out

    @alru_cache(maxsize=128)
    async def _download_pdf(document_url: str) -> str:
        from urllib.parse import urlparse

        parsed = urlparse(document_url)
        response = make_request(
            document_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": f"{parsed.scheme}://{parsed.netloc}/",
            },
        )
        response.raise_for_status()
        return base64.b64encode(response.content).decode("utf-8")

    @api.get("/open_document", include_in_schema=False)
    async def open_document(document_url: str) -> dict[str, Any]:
        if not document_url or not document_url.startswith("http"):
            return {"error_type": "invalid_url", "content": "Missing document URL."}

        try:
            encoded = await _download_pdf(document_url)
        except Exception as e:  # noqa: BLE001
            return {
                "error_type": "download_error",
                "content": f"Error fetching document: {e.args[0] if e.args else e!r}",
            }

        filename = document_url.rsplit("/", 1)[-1] or "hkex_filing.pdf"
        return {
            "content": encoded,
            "data_format": {"data_type": "pdf", "filename": filename},
        }

    @api.post(
        "/open_document",
        openapi_extra={
            "widget_config": {
                "type": "multi_file_viewer",
                "name": "HKEX Filings",
                "description": (
                    "Open HKEX disclosure documents (annual reports, interim "
                    "reports, announcements, etc.) sourced from hkexnews.hk."
                ),
                "category": "Equity",
                "subCategory": "Filings",
                "refetchInterval": False,
                "widgetId": "hkex_company_filings",
                "params": [
                    {
                        "paramName": "symbol",
                        "label": "Stock Code",
                        "description": (
                            "Any HKEX-listed security (equities, ETPs, REITs, "
                            "debt, warrants, CBBCs). Type a code or name to search."
                        ),
                        "type": "endpoint",
                        "value": "00700",
                        "optionsEndpoint": f"{base}/security_choices",
                        "style": {"popupWidth": 850},
                    },
                    {
                        "paramName": "document_url",
                        "label": "Document",
                        "description": "Select one or more filings to open.",
                        "type": "endpoint",
                        "optionsEndpoint": f"{base}/document_choices",
                        "optionsParams": {
                            "symbol": "$symbol",
                            "form_group": "$form_group",
                        },
                        "show": False,
                        "roles": ["fileSelector"],
                        "multiSelect": True,
                    },
                    {
                        "paramName": "form_group",
                        "label": "Category",
                        "description": "HKEX disclosure category (optional filter).",
                        "value": "all",
                        "type": "text",
                        "options": form_group_options,
                    },
                ],
                "gridData": {"w": 40, "h": 30},
            }
        },
    )
    async def post_open_document(params: dict) -> list:
        urls = params.get("document_url") or []
        if isinstance(urls, str):
            urls = [urls]
        documents: list = []
        for u in urls:
            if isinstance(u, str) and u.startswith("http"):
                doc = await open_document(u)
                if doc:
                    documents.append(doc)
        return documents

    @api.get("/hsi_document_choices", include_in_schema=False)
    async def hsi_document_choices() -> list[dict[str, Any]]:
        from openbb_hkex.utils.index_sources import (
            HSI_BASE,
            fetch_document_catalog,
        )

        out: list[dict[str, Any]] = []
        for e in await fetch_document_catalog():
            code = f" ({e['code']})" if e.get("code") else ""
            out.append(
                {
                    "label": f"[{e['label']}] {e.get('name') or ''}{code}".strip(),
                    "value": f"{HSI_BASE}{e['file']}",
                }
            )
        return out

    @api.post(
        "/open_hsi_document",
        openapi_extra={
            "widget_config": {
                "type": "multi_file_viewer",
                "name": "HSI Index Documents",
                "description": (
                    "Hang Seng Indexes document library — factsheets, methodologies "
                    "and brochures for every published index (HSI, HSCEI, HSTECH, "
                    "Composite, sector, mainland, Stock Connect, total-return and "
                    "themed series). Search and open one or more as PDFs."
                ),
                "category": "Indices",
                "subCategory": "Documents",
                "refetchInterval": False,
                "widgetId": "hkex_hsi_documents",
                "params": [
                    {
                        "paramName": "document_url",
                        "label": "Document",
                        "description": (
                            "Search Hang Seng index factsheets, methodologies and "
                            "brochures."
                        ),
                        "type": "endpoint",
                        "value": "https://www.hsi.com.hk/static/uploads/contents/en/dl_centre/factsheets/hsie.pdf",
                        "optionsEndpoint": f"{base}/hsi_document_choices",
                        "roles": ["fileSelector"],
                        "multiSelect": True,
                        "style": {"popupWidth": 900},
                    },
                ],
                "gridData": {"w": 40, "h": 30},
            }
        },
    )
    async def post_open_hsi_document(params: dict) -> list:
        urls = params.get("document_url") or []
        if isinstance(urls, str):
            urls = [urls]
        documents: list = []
        for u in urls:
            if isinstance(u, str) and u.startswith("http"):
                doc = await open_document(u)
                if doc:
                    documents.append(doc)
        return documents
