"""Yahoo Finance Sectors router."""

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

router = Router(prefix="", description="Yahoo Finance sector comparisons.")


@router.command(
    model="YfSectorOverview",
    examples=[APIEx(parameters={"sector": "technology", "provider": "yfinance"})],
)
async def overview(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get an overview of a market sector."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="YfSectorTopCompanies",
    examples=[APIEx(parameters={"sector": "technology", "provider": "yfinance"})],
)
async def top_companies(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the top companies in a market sector."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="YfSectorTopFunds",
    examples=[APIEx(parameters={"sector": "technology", "provider": "yfinance"})],
)
async def top_funds(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the top ETFs or mutual funds in a market sector."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="YfSectorIndustries",
    examples=[APIEx(parameters={"sector": "technology", "provider": "yfinance"})],
)
async def industries(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the industries within a market sector."""
    return await OBBject.from_query(Query(**locals()))
