"""Yahoo Finance Industry router."""

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

router = Router(prefix="", description="Yahoo Finance industry comparisons.")


@router.command(
    model="YfIndustryOverview",
    examples=[
        APIEx(
            parameters={
                "industry": "software-infrastructure",
                "provider": "yfinance",
            }
        )
    ],
)
async def overview(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get an overview of an industry."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="YfIndustryTopPerforming",
    examples=[
        APIEx(
            parameters={
                "industry": "software-infrastructure",
                "provider": "yfinance",
            }
        )
    ],
)
async def top_performing(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the top-performing companies in an industry."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="YfIndustryTopGrowth",
    examples=[
        APIEx(
            parameters={
                "industry": "software-infrastructure",
                "provider": "yfinance",
            }
        )
    ],
)
async def top_growth(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the top-growth companies in an industry."""
    return await OBBject.from_query(Query(**locals()))
