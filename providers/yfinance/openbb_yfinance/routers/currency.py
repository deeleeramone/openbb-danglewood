"""Yahoo Finance standalone Currency router."""

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

router = Router(prefix="", description="Yahoo Finance currency data.")
price_router = Router(prefix="/price", description="Currency price data.")


@price_router.command(
    model="YfCurrencyHistorical",
    examples=[APIEx(parameters={"symbol": "EURUSD=X", "provider": "yfinance"})],
)
async def historical(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get historical price data for a currency pair."""
    return await OBBject.from_query(Query(**locals()))


router.include_router(price_router)
