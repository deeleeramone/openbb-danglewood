"""Yahoo Finance hybrid router."""

from fastapi.responses import HTMLResponse, JSONResponse
from openbb_core.app.model.command_context import CommandContext
from openbb_core.app.model.example import APIEx, PythonEx
from openbb_core.app.model.obbject import OBBject
from openbb_core.app.provider_interface import (
    ExtraParams,
    ProviderChoices,
    StandardParams,
)
from openbb_core.app.query import Query
from openbb_core.app.router import Router
from openbb_core.app.service.system_service import SystemService

from openbb_yfinance import (
    CRYPTO_INSTALLED,
    CURRENCY_INSTALLED,
    DERIVATIVES_INSTALLED,
    ECONOMY_INSTALLED,
    EQUITY_INSTALLED,
    ETF_INSTALLED,
    INDEX_INSTALLED,
    NEWS_INSTALLED,
)
from openbb_yfinance.routers.estimates import router as estimates_router
from openbb_yfinance.routers.funds import router as funds_router
from openbb_yfinance.routers.industry import router as industry_router
from openbb_yfinance.routers.ownership import router as ownership_router
from openbb_yfinance.routers.sectors import router as sectors_router

router = Router(prefix="", description="Yahoo Finance data and analytics.")

_API_PREFIX = SystemService().system_settings.api_settings.prefix
_MCP_URL = f"{_API_PREFIX}/yfinance/mcp"


@router.command(
    model="YfSymbolSearch",
    widget_config={
        "name": "Yahoo Finance Symbol Search",
        "description": "Search Yahoo Finance for symbols; click a symbol in the table to change the grouped widgets' symbol.",
        "type": "table",
        "category": "Equity",
        "subCategory": "Search",
        "widgetId": "yfinance_search_obb",
        "gridData": {"w": 14, "h": 11},
        "data": {
            "table": {
                "columnsDefs": [
                    {
                        "field": "symbol",
                        "headerName": "Symbol",
                        "renderFn": "cellOnClick",
                        "renderFnParams": {
                            "actionType": "groupBy",
                            "groupByParamName": "symbol",
                        },
                    },
                    {"field": "name", "headerName": "Name"},
                    {"field": "exchange", "headerName": "Exchange"},
                    {"field": "asset_type", "headerName": "Type"},
                ]
            }
        },
    },
    examples=[
        APIEx(parameters={"query": "apple", "provider": "yfinance"}),
        APIEx(
            description="Narrow the search to a single asset type.",
            parameters={
                "query": "growth",
                "asset_type": "mutualfund",
                "provider": "yfinance",
            },
        ),
    ],
)
async def search(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Search Yahoo Finance for symbols, optionally narrowing by asset type."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    methods=["GET"],
    openapi_extra={"widget_config": {"exclude": True}},
)
async def industry_choices(
    sector: str | None = None,
    provider: str = "yfinance",
    is_workspace: bool = False,
) -> list:
    """Return Yahoo industry choices for a sector to drive cascading dropdowns."""
    from openbb_yfinance.utils.sectors import industry_options

    return industry_options(sector)


@router.command(
    model="YfNews",
    widget_config={
        "name": "Yahoo Finance News",
        "description": "Yahoo Finance news with the full article body.",
        "type": "newsfeed",
        "category": "News",
        "widgetId": "yfinance_news_obb",
        "gridData": {"w": 12, "h": 10},
    },
    examples=[
        APIEx(parameters={"query": "federal reserve", "provider": "yfinance"}),
        APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"}),
    ],
)
async def news(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Search Yahoo Finance news by free-text query or symbol."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="YfPrivateCompanies",
    widget_config={
        "name": "Yahoo Finance Private Companies",
        "description": "Private-company markets from Yahoo Finance (Crunchbase data):"
        + " valuation, funding, investors and more.",
        "type": "table",
        "category": "Equity",
        "subCategory": "Private Companies",
        "widgetId": "yfinance_private_companies_obb",
        "gridData": {"w": 40, "h": 15},
        "data": {
            "table": {
                "columnsDefs": [
                    {
                        "field": "name",
                        "headerName": "Company",
                        "pinned": "left",
                        "width": 170,
                    },
                    {
                        "field": "valuation",
                        "headerName": "Valuation",
                        "cellDataType": "number",
                    },
                    {
                        "field": "funding_to_date",
                        "headerName": "Funding to Date",
                        "cellDataType": "number",
                    },
                    {
                        "field": "latest_amount_raised",
                        "headerName": "Latest Round",
                        "cellDataType": "number",
                    },
                    {"field": "latest_funding_date", "headerName": "Last Funded"},
                    {"field": "lead_investor", "headerName": "Lead Investor"},
                    {
                        "field": "total_funding_rounds",
                        "headerName": "Rounds",
                        "cellDataType": "number",
                    },
                    {
                        "field": "change_52_week",
                        "headerName": "52W Change %",
                        "cellDataType": "number",
                    },
                    {"field": "sector", "headerName": "Sector"},
                    {
                        "field": "employees",
                        "headerName": "Employees",
                        "cellDataType": "number",
                    },
                    {"field": "date_founded", "headerName": "Founded"},
                    {"field": "website", "headerName": "Website"},
                ]
            }
        },
    },
    examples=[
        APIEx(parameters={"category": "highest_valuation", "provider": "yfinance"}),
        APIEx(parameters={"category": "most_funded", "provider": "yfinance"}),
    ],
)
async def private_companies(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get private-company markets from Yahoo Finance (Crunchbase data)."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="YfCompanyCalendar",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def company_calendar(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the upcoming earnings and dividend dates for a company."""
    return await OBBject.from_query(Query(**locals()))


router.include_router(funds_router, prefix="/funds")
router.include_router(estimates_router, prefix="/estimates")
router.include_router(ownership_router, prefix="/ownership")
router.include_router(sectors_router, prefix="/sectors")
router.include_router(industry_router, prefix="/industry")

if not EQUITY_INSTALLED:
    from openbb_yfinance.routers.equity import router as equity_router

    router.include_router(equity_router, prefix="/equity")

if not ETF_INSTALLED:
    from openbb_yfinance.routers.etf import router as etf_router

    router.include_router(etf_router, prefix="/etf")

if not DERIVATIVES_INSTALLED:
    from openbb_yfinance.routers.derivatives import router as derivatives_router

    router.include_router(derivatives_router, prefix="/derivatives")

if not INDEX_INSTALLED:
    from openbb_yfinance.routers.index import router as index_router

    router.include_router(index_router, prefix="/index")

if not CRYPTO_INSTALLED:
    from openbb_yfinance.routers.crypto import router as crypto_router

    router.include_router(crypto_router, prefix="/crypto")

if not CURRENCY_INSTALLED:
    from openbb_yfinance.routers.currency import router as currency_router

    router.include_router(currency_router, prefix="/currency")

if not NEWS_INSTALLED:
    from openbb_yfinance.routers.news import router as news_router

    router.include_router(news_router, prefix="/news")

if not ECONOMY_INSTALLED:
    from openbb_yfinance.routers.economy import router as economy_router

    router.include_router(economy_router, prefix="/economy")


def _is_jupyter() -> bool:
    """Return True when running inside an IPython/Jupyter kernel."""
    try:
        from IPython import get_ipython

        shell = get_ipython()
        return bool(shell) and shell.__class__.__name__ == "ZMQInteractiveShell"
    except Exception:  # noqa: BLE001
        return False


def _gui_available() -> bool:
    """Return True when a desktop display is available to host a native window."""
    import os
    import sys

    if sys.platform in ("darwin", "win32"):
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


@router.command(
    methods=["POST"],
    widget_config={"exclude": True},
    examples=[
        PythonEx(
            description="Open an interactive TradingView chart in a native window.",
            code=["obb.yfinance.tv_widget(symbol='AAPL')"],
        ),
    ],
)
async def tv_widget(
    symbol: str = "AAPL",
    interval: str = "1d",
    theme: str = "dark",
) -> OBBject:
    """Open an interactive TradingView chart powered by the Yahoo Finance datafeed.

    Opens a native desktop window, or renders inline in a Jupyter notebook, and
    returns immediately without blocking. On a headless host, returns the iframe
    endpoint to embed instead.
    """
    if not _gui_available():
        return OBBject(
            results={
                "message": "No desktop display available. Render the chart via the"
                + " GET /yfinance/tv_widget/view iframe endpoint.",
                "endpoint": "/yfinance/tv_widget/view"
                + f"?symbol={symbol}&interval={interval}&theme={theme}",
            }
        )

    import asyncio

    from openbb_yfinance.utils.tvchart_native import launch_tvchart

    theme = "light" if str(theme).lower() == "light" else "dark"
    handle = await asyncio.get_running_loop().run_in_executor(
        None, launch_tvchart, symbol, interval, theme
    )
    return OBBject(results=handle)


@router.command(
    methods=["POST"],
    widget_config={"exclude": True},
    examples=[
        PythonEx(
            description="Open the interactive screener builder in a native window.",
            code=["obb.yfinance.screener_builder()"],
        ),
    ],
)
async def screener_builder(theme: str = "dark") -> OBBject:
    """Open the interactive Yahoo Finance screener builder.

    Opens a native desktop window, or renders inline in a Jupyter notebook, and
    returns immediately without blocking. On a headless host (e.g. the REST API),
    returns the iframe endpoint to embed instead. To run a screen
    programmatically, use ``obb.yfinance.equity.screener``.
    """
    if not _gui_available():
        return OBBject(
            results={
                "message": "No desktop display available. Render the builder via"
                + " the GET /yfinance/screener_builder/view iframe endpoint.",
                "endpoint": f"/yfinance/screener_builder/view?theme={theme}",
            }
        )

    import asyncio

    from openbb_yfinance.utils.screener_native import launch_screener_builder

    theme = "light" if str(theme).lower() == "light" else "dark"
    handle = await asyncio.get_running_loop().run_in_executor(
        None, launch_screener_builder, theme
    )
    return OBBject(results=handle)


async def tv_widget_page(
    symbol: str = "AAPL", interval: str = "1d", theme: str = "dark"
) -> HTMLResponse:
    """Serve PyWry's TradingView widget HTML for the Workspace iframe."""
    from openbb_yfinance.utils.tvchart_native import tvchart_widget_html

    return HTMLResponse(content=await tvchart_widget_html(symbol, interval, theme))


router.api_router.add_api_route(
    path="/tv_widget/view",
    endpoint=tv_widget_page,
    methods=["GET"],
    response_class=HTMLResponse,
    include_in_schema=True,
    openapi_extra={
        "widget_config": {
            "name": "TradingView Chart (Yahoo Finance)",
            "description": "Interactive TradingView chart powered by Yahoo Finance.",
            "type": "iframe",
            "category": "Equity",
            "subCategory": "Charts",
            "widgetId": "yfinance_tv_widget_obb",
            "params": [
                {
                    "paramName": "symbol",
                    "label": "Symbol",
                    "value": "AAPL",
                    "description": "The ticker symbol to chart.",
                },
                {
                    "paramName": "interval",
                    "label": "Interval",
                    "value": "1d",
                    "description": "The chart interval.",
                    "options": [
                        {"label": i, "value": i}
                        for i in ("1m", "5m", "15m", "30m", "1h", "1d", "1w", "1M")
                    ],
                },
            ],
            "gridData": {"w": 40, "h": 20},
            "refetchInterval": False,
            "storage": {"mcpUrl": _MCP_URL},
        }
    },
)


async def asset_info_page(symbol: str = "AAPL", theme: str = "dark") -> HTMLResponse:
    """Serve the styled, live Asset Info overview widget HTML for the Workspace."""
    from openbb_yfinance.utils.asset_info import asset_info_widget_html

    return HTMLResponse(content=await asset_info_widget_html(symbol, theme))


router.api_router.add_api_route(
    path="/asset_info/view",
    endpoint=asset_info_page,
    methods=["GET"],
    response_class=HTMLResponse,
    include_in_schema=True,
    openapi_extra={
        "widget_config": {
            "name": "Asset Info (Yahoo Finance)",
            "description": "Styled overview with a live header price — summary, key "
            "statistics, valuation, analyst coverage, ownership, calendar, holdings "
            "and sector weightings — adapting to the asset type.",
            "type": "iframe",
            "category": "Equity",
            "subCategory": "Profile",
            "widgetId": "yfinance_asset_info_obb",
            "params": [
                {
                    "paramName": "symbol",
                    "label": "Symbol",
                    "value": "AAPL",
                    "description": "The ticker symbol.",
                },
            ],
            "gridData": {"w": 20, "h": 20},
            "refetchInterval": False,
        }
    },
)


async def screener_builder_page(theme: str = "dark") -> HTMLResponse:
    """Serve the interactive screener-builder iframe page."""
    from openbb_yfinance.utils.screener_iframe import build_screener_builder_html

    return HTMLResponse(
        content=build_screener_builder_html("light" if theme == "light" else "dark")
    )


async def screener_builder_catalog() -> JSONResponse:
    """Serve the screener field/value catalog for the builder iframe."""
    from openbb_yfinance.utils.screener_catalog import build_screener_catalog

    return JSONResponse(content=build_screener_catalog())


async def screener_builder_run(config: str = "", limit: int = 100) -> JSONResponse:
    """Run the screener for a builder config and return result rows for the table."""
    import json

    from openbb_core.app.model.abstract.error import OpenBBError
    from openbb_core.provider.utils.errors import EmptyDataError

    from openbb_yfinance.utils.helpers import get_custom_screener
    from openbb_yfinance.utils.screener_catalog import screener_body_from_config

    try:
        cfg = json.loads(config) if config else {}
    except (ValueError, TypeError) as exc:
        return JSONResponse(
            content={"error": f"Invalid config JSON: {exc}", "rows": []},
            status_code=400,
        )

    if not isinstance(cfg, dict):
        return JSONResponse(content={"rows": []})

    capped = min(max(1, int(limit or 100)), 250)
    try:
        rows = await get_custom_screener(
            screener_body_from_config(cfg), capped, keep_illiquid=True
        )
    except (EmptyDataError, OpenBBError, ValueError) as exc:
        return JSONResponse(content={"error": str(exc), "rows": []})

    return JSONResponse(content={"rows": rows})


async def screener_builder_templates() -> JSONResponse:
    """List the saved screener templates for the builder dropdown."""
    from openbb_yfinance.utils.screener_presets import list_presets

    try:
        return JSONResponse(content={"templates": list_presets()})
    except Exception as exc:  # noqa: BLE001 - templates are best-effort
        return JSONResponse(content={"templates": [], "error": str(exc)})


async def screener_builder_template_load(name: str = "") -> JSONResponse:
    """Load a named screener template and return its builder config."""
    from openbb_yfinance.utils.screener_presets import load_preset_config

    try:
        return JSONResponse(content={"config": load_preset_config(name)})
    except (FileNotFoundError, ValueError) as exc:
        return JSONResponse(content={"error": str(exc)}, status_code=404)


async def screener_builder_template_save(
    name: str = "", config: str = ""
) -> JSONResponse:
    """Save the builder config to a named template and return the refreshed list."""
    import json

    from openbb_yfinance.utils.screener_presets import list_presets, save_preset

    try:
        cfg = json.loads(config) if config else {}
    except (ValueError, TypeError) as exc:
        return JSONResponse(
            content={"error": f"Invalid config JSON: {exc}"}, status_code=400
        )
    if not isinstance(cfg, dict):
        return JSONResponse(
            content={"error": "Config must be an object."}, status_code=400
        )
    try:
        saved = save_preset(name, cfg)
    except (ValueError, OSError) as exc:
        return JSONResponse(content={"error": str(exc)}, status_code=400)
    return JSONResponse(
        content={"ok": True, "name": saved["name"], "templates": list_presets()}
    )


async def screener_builder_template_delete(name: str = "") -> JSONResponse:
    """Delete a named screener template and return the refreshed list."""
    from openbb_yfinance.utils.screener_presets import delete_preset, list_presets

    try:
        delete_preset(name)
    except FileNotFoundError as exc:
        return JSONResponse(content={"error": str(exc)}, status_code=404)
    except (ValueError, OSError) as exc:
        return JSONResponse(content={"error": str(exc)}, status_code=400)
    return JSONResponse(content={"ok": True, "templates": list_presets()})


router.api_router.add_api_route(
    path="/screener_builder/catalog",
    endpoint=screener_builder_catalog,
    methods=["GET"],
    response_class=JSONResponse,
    include_in_schema=False,
)

router.api_router.add_api_route(
    path="/screener_builder/run",
    endpoint=screener_builder_run,
    methods=["GET"],
    response_class=JSONResponse,
    include_in_schema=False,
)

for _tmpl_path, _tmpl_endpoint, _tmpl_method in (
    ("/screener_builder/templates", screener_builder_templates, "GET"),
    ("/screener_builder/templates/load", screener_builder_template_load, "GET"),
    ("/screener_builder/templates/save", screener_builder_template_save, "POST"),
    ("/screener_builder/templates/delete", screener_builder_template_delete, "POST"),
):
    router.api_router.add_api_route(
        path=_tmpl_path,
        endpoint=_tmpl_endpoint,
        methods=[_tmpl_method],
        response_class=JSONResponse,
        include_in_schema=False,
    )

router.api_router.add_api_route(
    path="/screener_builder/view",
    endpoint=screener_builder_page,
    methods=["GET"],
    response_class=HTMLResponse,
    include_in_schema=True,
    openapi_extra={
        "widget_config": {
            "name": "Screener Builder (Yahoo Finance)",
            "description": "Interactively build a screener configuration across"
            + " equities, ETFs and funds; click 'Apply' to sync the results table.",
            "type": "iframe",
            "category": "Equity",
            "subCategory": "Screener",
            "widgetId": "yfinance_screener_builder_obb",
            "params": [
                {
                    "paramName": "config",
                    "label": "Screener Config",
                    "value": "",
                    "description": "The screener configuration emitted by the builder.",
                    "show": False,
                }
            ],
            "gridData": {"w": 16, "h": 18},
            "refetchInterval": False,
        }
    },
)


async def yfinance_apps_json() -> list[dict]:
    """Serve the bundled Yahoo Finance Workspace app from ``assets/apps.json``."""
    from openbb_yfinance.utils.apps import build_yfinance_apps

    return build_yfinance_apps()


router.api_router.add_api_route(
    path="/apps.json",
    endpoint=yfinance_apps_json,
    methods=["GET"],
    include_in_schema=False,
)


from openbb_yfinance.utils.mcp_app import (  # noqa: E402
    get_mcp_asgi_app,
    make_asgi_proxy,
)

_MCP_ASGI_APP = get_mcp_asgi_app()
if _MCP_ASGI_APP is not None:
    router.api_router.add_api_route(
        path="/mcp",
        endpoint=make_asgi_proxy(_MCP_ASGI_APP),
        methods=["POST"],
        include_in_schema=False,
    )
