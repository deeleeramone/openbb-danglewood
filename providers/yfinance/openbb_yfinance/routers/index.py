"""Yahoo Finance standalone Index router."""

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

router = Router(prefix="", description="Yahoo Finance index data.")
price_router = Router(prefix="/price", description="Index price data.")


@router.command(
    model="YfAvailableIndices",
    examples=[APIEx(parameters={"provider": "yfinance"})],
)
async def available(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the list of available indices."""
    return await OBBject.from_query(Query(**locals()))


@price_router.command(
    model="YfIndexHistorical",
    examples=[APIEx(parameters={"symbol": "^GSPC", "provider": "yfinance"})],
)
async def historical(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get historical price data for an index."""
    return await OBBject.from_query(Query(**locals()))


router.include_router(price_router)
