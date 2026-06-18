"""Yahoo Finance standalone Crypto router."""

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

router = Router(prefix="", description="Yahoo Finance crypto data.")
price_router = Router(prefix="/price", description="Crypto price data.")


@price_router.command(
    model="YfCryptoHistorical",
    examples=[APIEx(parameters={"symbol": "BTC-USD", "provider": "yfinance"})],
)
async def historical(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get historical price data for a cryptocurrency pair."""
    return await OBBject.from_query(Query(**locals()))


router.include_router(price_router)
