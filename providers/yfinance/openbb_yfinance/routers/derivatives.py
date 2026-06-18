"""Yahoo Finance standalone Derivatives router."""

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

router = Router(prefix="", description="Yahoo Finance derivatives data.")
options_router = Router(prefix="/options", description="Options data.")
futures_router = Router(prefix="/futures", description="Futures data.")


@options_router.command(
    model="YfOptionsChains",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def chains(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the complete options chain for a symbol."""
    return await OBBject.from_query(Query(**locals()))


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
