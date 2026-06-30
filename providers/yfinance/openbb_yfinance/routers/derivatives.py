"""Yahoo Finance standalone Derivatives router (options analysis + futures).

Table views (chains, underlying, straddle, strangle) are OpenBB commands.
Chart views (smile, surface, stats, term_structure) are plotly "chart" widgets:
plain routes that return ``json.loads(fig.to_json())`` per the OpenBB Workspace
plotly-chart widget spec.
"""

from datetime import date as dateType
from typing import Annotated, Any, Literal

from fastapi import Query as FastQuery
from openbb_core.app.model.command_context import CommandContext
from openbb_core.app.model.example import APIEx
from openbb_core.app.model.obbject import OBBject
from openbb_core.app.provider_interface import (
    ExtraParams,
    ProviderChoices,
    StandardParams,
)
from openbb_core.app.query import Query
from openbb_core.app.router import Router
from openbb_core.app.service.system_service import SystemService
from openbb_core.provider.abstract.data import Data
from pydantic import Field

router = Router(prefix="", description="Yahoo Finance derivatives data.")
options_router = Router(prefix="/options", description="Options analysis.")
futures_router = Router(prefix="/futures", description="Futures data.")

# Built from the configured API prefix; the options views are served at
# <prefix>/yfinance/derivatives/options/* (this router is mounted at /derivatives).
_TICKERS_ENDPOINT = (
    f"{SystemService().system_settings.api_settings.prefix.strip('/')}"
    "/yfinance/derivatives/options/get_tickers"
)
_SYMBOL_PARAM = {"x-widget_config": {"groupId": "symbol", "style": {"popupWidth": 400}}}
_CHART_CONFIG = {"scrollZoom": True, "displayModeBar": True, "responsive": True}


def _symbol_query(description: str = "The underlying ticker symbol.") -> Any:
    return FastQuery(description=description, json_schema_extra=_SYMBOL_PARAM)


def _expiry_query(description: str, multi: bool = False) -> Any:
    cfg: dict = {
        "type": "endpoint",
        "optionsEndpoint": _TICKERS_ENDPOINT,
        "optionsParams": {"expiry_list": True, "symbol": "$symbol"},
    }
    if multi:
        cfg["multiSelect"] = True
    return FastQuery(
        description=description, json_schema_extra={"x-widget_config": cfg}
    )


def _strike_query(description: str) -> Any:
    return FastQuery(
        description=description,
        json_schema_extra={
            "x-widget_config": {
                "type": "endpoint",
                "optionsEndpoint": _TICKERS_ENDPOINT,
                "optionsParams": {"strike_list": True, "symbol": "$symbol"},
            }
        },
    )


def _excluded_query(description: str = "") -> Any:
    """Drop a param from the widget UI while still receiving it on the request.

    The Workspace auto-injects ``theme`` for chart widgets and drives ``raw``
    from the chart/raw toggle (``"raw": true``), so neither belongs in the
    widget's parameter list.
    """
    return FastQuery(
        description=description,
        json_schema_extra={"x-widget_config": {"exclude": True}},
    )


def _choice_query(description: str, options: list[tuple[str, str]]) -> Any:
    return FastQuery(
        description=description,
        json_schema_extra={
            "x-widget_config": {
                "options": [
                    {"label": label, "value": value} for label, value in options
                ]
            }
        },
    )


class StrategyData(Data):
    """Options strategy pricing."""

    __alias_dict__ = {
        "expiration": "Expiration",
        "dte": "DTE",
        "underlying_price": "Underlying Price",
        "strike_1": "Strike 1",
        "strike_2": "Strike 2",
        "strike_1_premium": "Strike 1 Premium",
        "strike_2_premium": "Strike 2 Premium",
        "cost": "Cost",
        "cost_percent": "Cost Percent",
        "breakeven_upper": "Breakeven Upper",
        "breakeven_upper_percent": "Breakeven Upper Percent",
        "breakeven_lower": "Breakeven Lower",
        "breakeven_lower_percent": "Breakeven Lower Percent",
        "max_profit": "Max Profit",
        "max_loss": "Max Loss",
    }

    expiration: dateType = Field(title="Expiry")
    dte: int = Field(title="DTE")
    strike_1: int | float = Field(title="Call Strike")
    strike_2: int | float = Field(title="Put Strike")
    underlying_price: float = Field(title="Underlying Price")
    cost_percent: float = Field(
        title="Cost %", json_schema_extra={"x-unit_measurement": "percent"}
    )
    max_profit: float | None = Field(default=None, title="Max Profit")
    max_loss: float | None = Field(
        default=None,
        title="Max Loss",
        json_schema_extra={"x-unit_measurement": "percent"},
    )
    breakeven_upper: float = Field(title="Breakeven Upper")
    breakeven_upper_percent: float = Field(
        title="Breakeven Upper %", json_schema_extra={"x-unit_measurement": "percent"}
    )
    breakeven_lower: float = Field(title="Breakeven Lower")
    breakeven_lower_percent: float = Field(
        title="Breakeven Lower %", json_schema_extra={"x-unit_measurement": "percent"}
    )
    strike_1_premium: float = Field(title="Call Premium")
    strike_2_premium: float = Field(title="Put Premium")
    cost: float = Field(title="Cost")


def _strategies(df) -> list:
    from numpy import inf, nan

    df = df.drop(columns=[c for c in ("Strategy", "Payoff Ratio") if c in df.columns])
    return [
        StrategyData.model_validate(d)
        for d in df.replace({nan: None, inf: None}).to_dict("records")
    ]


class SpreadData(Data):
    """Vertical (bull/bear) spread pricing."""

    __alias_dict__ = {
        "strategy": "Strategy",
        "expiration": "Expiration",
        "dte": "DTE",
        "underlying_price": "Underlying Price",
        "sold_strike": "Strike 1",
        "bought_strike": "Strike 2",
        "sold_premium": "Strike 1 Premium",
        "bought_premium": "Strike 2 Premium",
        "cost": "Cost",
        "cost_percent": "Cost Percent",
        "breakeven_lower": "Breakeven Lower",
        "breakeven_lower_percent": "Breakeven Lower Percent",
        "breakeven_upper": "Breakeven Upper",
        "breakeven_upper_percent": "Breakeven Upper Percent",
        "max_profit": "Max Profit",
        "max_loss": "Max Loss",
    }

    strategy: str = Field(title="Strategy")
    expiration: dateType = Field(title="Expiry")
    dte: int = Field(title="DTE")
    sold_strike: float = Field(title="Short Strike")
    bought_strike: float = Field(title="Long Strike")
    underlying_price: float = Field(title="Underlying Price")
    cost: float = Field(title="Cost")
    cost_percent: float = Field(
        title="Cost %", json_schema_extra={"x-unit_measurement": "percent"}
    )
    max_profit: float | None = Field(default=None, title="Max Profit")
    max_loss: float | None = Field(default=None, title="Max Loss")
    breakeven_lower: float | None = Field(default=None, title="Breakeven Lower")
    breakeven_lower_percent: float | None = Field(
        default=None,
        title="Breakeven Lower %",
        json_schema_extra={"x-unit_measurement": "percent"},
    )
    breakeven_upper: float | None = Field(default=None, title="Breakeven Upper")
    breakeven_upper_percent: float | None = Field(
        default=None,
        title="Breakeven Upper %",
        json_schema_extra={"x-unit_measurement": "percent"},
    )
    sold_premium: float = Field(title="Short Premium")
    bought_premium: float = Field(title="Long Premium")


def _spreads(df) -> list:
    from numpy import inf, nan

    df = df.drop(columns=[c for c in ("Payoff Ratio",) if c in df.columns])
    return [
        SpreadData.model_validate(d)
        for d in df.replace({nan: None, inf: None, -inf: None}).to_dict("records")
    ]


async def _chart_json(builder, symbol: str, theme: str, raw: bool, **kwargs):
    """Load the (cached) chain and build the view.

    Returns the underlying rows when the widget's raw toggle is on, else the
    plotly figure JSON.
    """
    import json

    from fastapi import HTTPException
    from openbb_core.app.model.abstract.error import OpenBBError

    from openbb_yfinance.utils.options.data_handler import load_symbol

    try:
        data = await load_symbol(symbol)
    except OpenBBError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    output = builder(data, theme=theme, **kwargs)
    if raw:
        return [r.model_dump() for r in (output.results or [])]
    figure_json = json.loads(output.chart.fig.to_json())
    figure_json["config"] = _CHART_CONFIG
    return figure_json


# --------------------------------------------------------------------------- #
# Dropdown + table views (OpenBB commands)
# --------------------------------------------------------------------------- #


@options_router.command(
    methods=["GET"], openapi_extra={"widget_config": {"exclude": True}}
)
async def get_tickers(
    symbol: str = "",
    expiry_list: bool = False,
    strike_list: bool = False,
) -> list:
    """Serve expiry/strike dropdown choices for a symbol (loads it on first call)."""
    from openbb_core.app.model.abstract.error import OpenBBError

    from openbb_yfinance.utils.options.data_handler import (
        get_expirations,
        get_strikes,
        load_symbol,
    )

    if not symbol:
        return []
    try:
        await load_symbol(symbol)
    except OpenBBError:
        return []
    if expiry_list:
        return get_expirations(symbol)
    if strike_list:
        return get_strikes(symbol)
    return []


@options_router.command(methods=["GET"])
async def chains(
    symbol: Annotated[str, _symbol_query()] = "AAPL",
    expiry: Annotated[
        str | None, _expiry_query("Filter to the nearest expiry on or after this date.")
    ] = None,
    option_type: Annotated[
        Literal["calls", "puts", "both"],
        _choice_query(
            "Calls, puts, or both.",
            [("Calls", "calls"), ("Puts", "puts"), ("Puts & Calls", "both")],
        ),
    ] = "both",
    otm_only: Annotated[
        bool, FastQuery(description="Show only out-of-the-money contracts.")
    ] = False,
) -> OBBject:
    """Get the options chain table, filtered by expiry, type, and moneyness.

    Uses the shared per-symbol cache so it never refetches when other views have
    already loaded the symbol.
    """
    from openbb_core.app.utils import df_to_basemodel

    from openbb_yfinance.utils.options.data_handler import load_symbol

    results = await load_symbol(symbol)
    df = results.filter_data(
        date=expiry,
        moneyness="otm" if otm_only else None,
        option_type=(
            "put"
            if option_type == "puts"
            else "call"
            if option_type == "calls"
            else None
        ),
    )
    df = df.drop(columns=[c for c in ("tick", "last_trade_time") if c in df.columns])
    return OBBject(results=df_to_basemodel(df), provider="yfinance")


@options_router.command(methods=["GET"])
async def straddle(
    symbol: Annotated[str, _symbol_query()] = "AAPL",
    strike: Annotated[
        float | None, _strike_query("Target strike. Default is nearest OTM.")
    ] = None,
) -> OBBject:
    """Price a long straddle at each expiration."""
    from openbb_yfinance.utils.options.data_handler import load_symbol

    data = await load_symbol(symbol)
    df = data.strategies(days=-1, straddle_strike=strike)
    return OBBject(results=_strategies(df), provider="yfinance")


@options_router.command(methods=["GET"])
async def strangle(
    symbol: Annotated[str, _symbol_query()] = "AAPL",
    moneyness: float = 5,
) -> OBBject:
    """Price a long strangle at each expiration for a given moneyness."""
    from openbb_yfinance.utils.options.data_handler import load_symbol

    data = await load_symbol(symbol)
    df = data.strategies(days=-1, strangle_moneyness=1 if moneyness == 0 else moneyness)
    return OBBject(results=_strategies(df), provider="yfinance")


@options_router.command(methods=["GET"])
async def spreads(
    symbol: Annotated[str, _symbol_query()] = "AAPL",
    spread_type: Annotated[
        Literal["call", "put", "both"],
        _choice_query(
            "Vertical call spreads, put spreads, or both.",
            [("Call Spreads", "call"), ("Put Spreads", "put"), ("Both", "both")],
        ),
    ] = "both",
    near_moneyness: float = 2.5,
    far_moneyness: float = 7.5,
) -> OBBject:
    """Price all four vertical spreads at each expiration.

    The two legs sit ``near_moneyness`` and ``far_moneyness`` percent
    out-of-the-money. Swapping which leg is sold flips bull versus bear, so call
    spreads yield bull and bear call spreads and put spreads yield bull and bear
    put spreads; the Strategy column names each.
    """
    from pandas import concat

    from openbb_yfinance.utils.options.data_handler import load_symbol

    data = await load_symbol(symbol)
    last = data.underlying_price[0]
    near_m, far_m = near_moneyness / 100, far_moneyness / 100
    near_call, far_call = last * (1 + near_m), last * (1 + far_m)
    near_put, far_put = last * (1 - near_m), last * (1 - far_m)

    # (sold strike, bought strike) per spread; swapping the legs flips bull/bear.
    specs: list = []
    if spread_type in ("call", "both"):
        specs += [
            ("vertical_calls", (far_call, near_call)),  # Bull Call Spread
            ("vertical_calls", (near_call, far_call)),  # Bear Call Spread
        ]
    if spread_type in ("put", "both"):
        specs += [
            ("vertical_puts", (near_put, far_put)),  # Bull Put Spread
            ("vertical_puts", (far_put, near_put)),  # Bear Put Spread
        ]
    # strategies()'s vertical_puts loop only keeps the last tuple, so each spread
    # is requested in its own call with a single leg pair.
    frames = [data.strategies(days=-1, **{kind: [legs]}) for kind, legs in specs]
    return OBBject(results=_spreads(concat(frames)), provider="yfinance")


# --------------------------------------------------------------------------- #
# Chart views (plotly "chart" widgets — return plotly figure JSON)
# --------------------------------------------------------------------------- #


async def smile_chart(
    symbol: Annotated[str, _symbol_query()] = "AAPL",
    expirations: Annotated[
        str | None,
        _expiry_query("Up to five expiration dates (comma-separated).", multi=True),
    ] = None,
    otm: bool = False,
    skew: bool = False,
    raw: Annotated[bool, _excluded_query()] = False,
    theme: Annotated[str, _excluded_query()] = "dark",
):
    """Implied-volatility smile / skew across strikes."""
    from openbb_yfinance.utils.options.create_smile import create_smile

    return await _chart_json(
        create_smile, symbol, theme, raw, expirations=expirations, otm=otm, skew=skew
    )


async def surface_chart(
    symbol: Annotated[str, _symbol_query()] = "AAPL",
    option_type: Literal["otm", "itm", "puts", "calls"] = "otm",
    dte_min: int | None = None,
    dte_max: int | None = None,
    moneyness: float | None = None,
    oi: bool = False,
    volume: bool = False,
    raw: Annotated[bool, _excluded_query()] = False,
    theme: Annotated[str, _excluded_query()] = "dark",
):
    """Implied-volatility 3-D surface over DTE and strike."""
    from openbb_yfinance.utils.options.create_surface import create_surface

    dte_range = [dte_min or 0, dte_max or 5000] if (dte_min or dte_max) else None
    return await _chart_json(
        create_surface,
        symbol,
        theme,
        raw,
        option_type=option_type,
        dte_range=dte_range,
        moneyness=moneyness,
        oi=oi,
        volume=volume,
    )


async def stats_chart(
    symbol: Annotated[str, _symbol_query()] = "AAPL",
    by: Literal["strike", "expiration"] = "expiration",
    metric: Annotated[
        Literal["oi", "volume"],
        _choice_query(
            "Open interest or volume.",
            [("Open Interest", "oi"), ("Volume", "volume")],
        ),
    ] = "oi",
    date: Annotated[
        str | None,
        _expiry_query("Expiry to view by strike (switches 'by' to strike)."),
    ] = None,
    unit: Literal["value", "percent", "pcr"] = "value",
    raw: Annotated[bool, _excluded_query()] = False,
    theme: Annotated[str, _excluded_query()] = "dark",
):
    """Open-interest or volume statistics by strike or expiration."""
    from openbb_yfinance.utils.options.create_stats import create_stats

    return await _chart_json(
        create_stats, symbol, theme, raw, by=by, metric=metric, date=date, unit=unit
    )


async def term_structure_chart(
    symbol: Annotated[str, _symbol_query()] = "AAPL",
    strike: Annotated[
        float | None, _strike_query("Target strike. Default is nearest OTM per expiry.")
    ] = None,
    moneyness: float | None = None,
    metric: Annotated[
        Literal["iv", "price"],
        _choice_query(
            "Implied volatility or price.",
            [("Implied Volatility", "iv"), ("Price", "price")],
        ),
    ] = "iv",
    option_type: Literal["both", "calls", "puts"] = "both",
    raw: Annotated[bool, _excluded_query()] = False,
    theme: Annotated[str, _excluded_query()] = "dark",
):
    """Price or IV term structure across expirations."""
    from openbb_yfinance.utils.options.create_term_structure import (
        create_term_structure,
    )

    return await _chart_json(
        create_term_structure,
        symbol,
        theme,
        raw,
        strike=strike,
        moneyness=moneyness,
        metric=metric,
        option_type=option_type,
    )


def _chart_widget(name: str) -> dict:
    return {
        "widget_config": {
            "name": name,
            "type": "chart",
            "raw": True,
            "category": "Equity",
            "subCategory": "Options",
            "gridData": {"w": 40, "h": 18},
            "refetchInterval": False,
        }
    }


for _path, _endpoint, _name in (
    ("/smile", smile_chart, "Options Smile"),
    ("/surface", surface_chart, "Options Surface"),
    ("/stats", stats_chart, "Options Stats"),
    ("/term_structure", term_structure_chart, "Options Term Structure"),
):
    options_router.api_router.add_api_route(
        path=_path,
        endpoint=_endpoint,
        methods=["GET"],
        openapi_extra=_chart_widget(_name),
    )


# --------------------------------------------------------------------------- #
# Futures
# --------------------------------------------------------------------------- #


@futures_router.command(
    model="YfFuturesHistorical",
    examples=[APIEx(parameters={"symbol": "ES", "provider": "yfinance"})],
)
async def historical(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get historical price data for a futures contract."""
    return await OBBject.from_query(Query(**locals()))


@futures_router.command(
    model="YfFuturesCurve",
    examples=[APIEx(parameters={"symbol": "ES", "provider": "yfinance"})],
)
async def curve(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the futures curve for a symbol."""
    return await OBBject.from_query(Query(**locals()))


router.include_router(options_router)
router.include_router(futures_router)
