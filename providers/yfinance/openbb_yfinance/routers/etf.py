"""Yahoo Finance standalone ETF router."""

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

router = Router(prefix="", description="Yahoo Finance ETF data.")


@router.command(
    model="YfEtfInfo",
    examples=[APIEx(parameters={"symbol": "SPY", "provider": "yfinance"})],
)
async def info(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get ETF information overview."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="YfEtfHistorical",
    examples=[APIEx(parameters={"symbol": "SPY", "provider": "yfinance"})],
)
async def historical(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get historical price data for an ETF."""
    return await OBBject.from_query(Query(**locals()))
