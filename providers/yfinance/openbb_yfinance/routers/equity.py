"""Yahoo Finance standalone Equity router."""

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

router = Router(prefix="", description="Yahoo Finance equity market data.")
price_router = Router(prefix="/price", description="Equity price data.")
fundamental_router = Router(prefix="/fundamental", description="Equity fundamentals.")
discovery_router = Router(prefix="/discovery", description="Equity discovery.")
estimates_router = Router(prefix="/estimates", description="Analyst estimates.")
ownership_router = Router(prefix="/ownership", description="Equity ownership.")
calendar_router = Router(prefix="/calendar", description="Equity calendars.")


@router.command(
    model="YfEquityInfo",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def profile(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get general information about a company."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="YfEquityScreener",
    widget_config={
        "exclude": True,
    },
    examples=[APIEx(parameters={"provider": "yfinance"})],
)
async def screener(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Screen for equities using Yahoo Finance."""
    return await OBBject.from_query(Query(**locals()))


@price_router.command(
    model="YfEquityHistorical",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def historical(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get historical price data for an equity."""
    return await OBBject.from_query(Query(**locals()))


@price_router.command(
    model="YfEquityQuote",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def quote(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the latest quote for an equity."""
    return await OBBject.from_query(Query(**locals()))


@fundamental_router.command(
    model="YfBalanceSheet",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def balance(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the balance sheet for a company."""
    return await OBBject.from_query(Query(**locals()))


@fundamental_router.command(
    model="YfCashFlowStatement",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def cash(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the cash flow statement for a company."""
    return await OBBject.from_query(Query(**locals()))


@fundamental_router.command(
    model="YfIncomeStatement",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def income(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the income statement for a company."""
    return await OBBject.from_query(Query(**locals()))


@fundamental_router.command(
    model="YfHistoricalDividends",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def dividends(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get historical dividend data for a company."""
    return await OBBject.from_query(Query(**locals()))


@fundamental_router.command(
    model="YfKeyMetrics",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def metrics(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get fundamental metrics for a company."""
    return await OBBject.from_query(Query(**locals()))


@fundamental_router.command(
    model="YfKeyExecutives",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def management(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get key executives for a company."""
    return await OBBject.from_query(Query(**locals()))


@fundamental_router.command(
    model="YfHistoricalEps",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def historical_eps(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get historical earnings-per-share for a company."""
    return await OBBject.from_query(Query(**locals()))


@fundamental_router.command(
    model="YfCompanyFilings",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def filings(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the SEC filings for a company."""
    return await OBBject.from_query(Query(**locals()))


@calendar_router.command(
    model="YfCalendarEarnings",
    examples=[APIEx(parameters={"provider": "yfinance"})],
)
async def earnings(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the earnings calendar."""
    return await OBBject.from_query(Query(**locals()))


@calendar_router.command(
    model="YfCalendarIpo",
    examples=[APIEx(parameters={"provider": "yfinance"})],
)
async def ipo(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the IPO calendar."""
    return await OBBject.from_query(Query(**locals()))


@calendar_router.command(
    model="YfCalendarSplits",
    examples=[APIEx(parameters={"provider": "yfinance"})],
)
async def splits(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the stock splits calendar."""
    return await OBBject.from_query(Query(**locals()))


@discovery_router.command(
    model="YfEquityGainers",
    examples=[APIEx(parameters={"provider": "yfinance"})],
)
async def gainers(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the top equity gainers."""
    return await OBBject.from_query(Query(**locals()))


@discovery_router.command(
    model="YfEquityLosers",
    examples=[APIEx(parameters={"provider": "yfinance"})],
)
async def losers(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the top equity losers."""
    return await OBBject.from_query(Query(**locals()))


@discovery_router.command(
    model="YfEquityActive",
    examples=[APIEx(parameters={"provider": "yfinance"})],
)
async def active(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the most active equities."""
    return await OBBject.from_query(Query(**locals()))


@discovery_router.command(
    model="YfGrowthTechEquities",
    examples=[APIEx(parameters={"provider": "yfinance"})],
)
async def growth_tech(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get growth technology equities."""
    return await OBBject.from_query(Query(**locals()))


@discovery_router.command(
    model="YfEquityUndervaluedGrowth",
    examples=[APIEx(parameters={"provider": "yfinance"})],
)
async def undervalued_growth(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get undervalued growth equities."""
    return await OBBject.from_query(Query(**locals()))


@discovery_router.command(
    model="YfEquityUndervaluedLargeCaps",
    examples=[APIEx(parameters={"provider": "yfinance"})],
)
async def undervalued_large_caps(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get undervalued large cap equities."""
    return await OBBject.from_query(Query(**locals()))


@discovery_router.command(
    model="YfEquityAggressiveSmallCaps",
    examples=[APIEx(parameters={"provider": "yfinance"})],
)
async def aggressive_small_caps(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get aggressive small cap equities."""
    return await OBBject.from_query(Query(**locals()))


@estimates_router.command(
    model="YfPriceTargetConsensus",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def consensus(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the analyst price target consensus."""
    return await OBBject.from_query(Query(**locals()))


@estimates_router.command(
    model="YfPriceTarget",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def price_target(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the analyst price target upgrades and downgrades."""
    return await OBBject.from_query(Query(**locals()))


@ownership_router.command(
    model="YfShareStatistics",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def share_statistics(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get share statistics for a company."""
    return await OBBject.from_query(Query(**locals()))


@ownership_router.command(
    model="YfInsiderTrading",
    examples=[APIEx(parameters={"symbol": "AAPL", "provider": "yfinance"})],
)
async def insider_trading(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get insider trading transactions for a company."""
    return await OBBject.from_query(Query(**locals()))


router.include_router(price_router)
router.include_router(fundamental_router)
router.include_router(discovery_router)
router.include_router(estimates_router)
router.include_router(ownership_router)
router.include_router(calendar_router)
