"""Yahoo Finance yf-native analyst estimates router."""

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

router = Router(prefix="", description="Yahoo Finance analyst estimates.")


@router.command(
    model="YfAnalystRecommendations",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def recommendations(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the analyst recommendation trends for a company."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="YfEarningsEstimates",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def earnings(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the forward earnings-per-share estimates for a company."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="YfRevenueEstimates",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def revenue(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the forward revenue estimates for a company."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="YfEpsTrend",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def eps_trend(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the trend of EPS estimates over time for a company."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="YfEpsRevisions",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def eps_revisions(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the number of upward and downward EPS estimate revisions."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="YfGrowthEstimates",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def growth(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the growth estimates for a company versus its index."""
    return await OBBject.from_query(Query(**locals()))
