"""Yahoo Finance standalone Company News router."""

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

router = Router(prefix="", description="Yahoo Finance news data.")


@router.command(
    model="YfCompanyNews",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def company(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get company news for one or more symbols."""
    return await OBBject.from_query(Query(**locals()))
