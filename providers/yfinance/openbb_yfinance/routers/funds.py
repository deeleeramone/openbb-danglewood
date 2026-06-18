"""Yahoo Finance Funds router."""

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

router = Router(prefix="", description="Yahoo Finance mutual fund & ETF analytics.")


@router.command(
    model="YfFundInfo",
    examples=[APIEx(parameters={"symbol": "VTSAX", "provider": "yfinance"})],
)
async def info(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the profile and operations overview for a mutual fund or ETF."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="YfFundHoldings",
    examples=[APIEx(parameters={"symbol": "VTSAX", "provider": "yfinance"})],
)
async def holdings(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the top holdings for a mutual fund or ETF."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="YfFundAllocation",
    examples=[APIEx(parameters={"symbol": "VTSAX", "provider": "yfinance"})],
)
async def allocation(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the asset-class, sector and bond-rating allocation for a fund."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="YfFundHistorical",
    examples=[APIEx(parameters={"symbol": "VTSAX", "provider": "yfinance"})],
)
async def historical(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get historical NAV/price data for a mutual fund or ETF."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="YfFundPerformance",
    examples=[APIEx(parameters={"symbol": "VTSAX", "provider": "yfinance"})],
)
async def performance(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get return performance and category comparisons for a fund."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="YfFundRatings",
    examples=[APIEx(parameters={"symbol": "VTSAX", "provider": "yfinance"})],
)
async def ratings(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get Morningstar ratings and the style box for a fund."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="YfFundRisk",
    examples=[APIEx(parameters={"symbol": "VTSAX", "provider": "yfinance"})],
)
async def risk(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Compute volatility, beta, Sharpe ratio and drawdown for a fund."""
    return await OBBject.from_query(Query(**locals()))
