"""Yahoo Finance yf-native ownership router."""

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

router = Router(prefix="", description="Yahoo Finance ownership data.")


@router.command(
    model="YfInstitutionalHolders",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def institutional(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the top institutional holders of a company."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="YfMutualFundHolders",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def mutual_fund(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the top mutual-fund holders of a company."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="YfMajorHolders",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def major(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the major-holders breakdown for a company."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="YfInsiderPurchases",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def insider_purchases(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the six-month insider-purchase summary for a company."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="YfInsiderRoster",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def insider_roster(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the insider roster (current insider holders) for a company."""
    return await OBBject.from_query(Query(**locals()))
