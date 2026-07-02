"""HKEX router."""

from contextlib import asynccontextmanager

from openbb_core.app.model.command_context import CommandContext
from openbb_core.app.model.example import PythonEx
from openbb_core.app.model.obbject import OBBject
from openbb_core.app.provider_interface import (
    ExtraParams,
    ProviderChoices,
    StandardParams,
)
from openbb_core.app.query import Query
from openbb_core.app.router import Router
from pydantic import BaseModel

from openbb_hkex import (
    DERIVATIVES_INSTALLED,
    EQUITY_INSTALLED,
    INDEX_INSTALLED,
)
from openbb_hkex.utils.widgets import register_widgets

router = Router(prefix="")


@router.command(
    model="HkexEtfHoldings",
    widget_config={"refetchInterval": False},
    examples=[
        PythonEx(
            description="Holdings basket of the CSOP Hang Seng Index ETF (03037).",
            code=["obb.hkex.etf_holdings('03037')"],
        ),
    ],
)
async def etf_holdings(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject[BaseModel]:
    """Return the holdings basket with per-constituent weights for an HKEX-listed ETF."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="HkexEtfNav",
    widget_config={"refetchInterval": False},
    examples=[
        PythonEx(
            description="Daily NAV history for the CSOP Hang Seng Index ETF (03037).",
            code=["obb.hkex.etf_nav('03037')"],
        ),
    ],
)
async def etf_nav(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject[BaseModel]:
    """Daily net-asset-value history for an HKEX-listed ETF."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="HkexEtfPerformance",
    widget_config={"refetchInterval": False},
    examples=[
        PythonEx(
            description="Trailing returns vs benchmark for the CSOP HS Index ETF.",
            code=["obb.hkex.etf_performance('03037')"],
        ),
    ],
)
async def etf_performance(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject[BaseModel]:
    """Trailing total returns for an HKEX-listed ETF and its benchmark index."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="HkexEtfTracking",
    widget_config={"refetchInterval": False},
    examples=[
        PythonEx(
            description="Tracking difference & error for the CSOP HS Index ETF.",
            code=["obb.hkex.etf_tracking('03037')"],
        ),
    ],
)
async def etf_tracking(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject[BaseModel]:
    """Tracking difference and tracking error of an HKEX-listed ETF vs its benchmark."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="HkexFuturesInstruments",
    widget_config={"refetchInterval": False},
    examples=[
        PythonEx(
            description="Listed HSI futures contracts with contract metadata.",
            code=["obb.hkex.futures_instruments('HSI')"],
        ),
    ],
)
async def futures_instruments(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject[BaseModel]:
    """Return listed contracts and contract metadata for an HKEX derivatives product."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="HkexSecuritiesMaster",
    widget_config={"refetchInterval": False},
    examples=[
        PythonEx(
            description="All listed REITs.",
            code=[
                "obb.hkex.securities_master(category='Real Estate Investment Trusts')"
            ],
        ),
        PythonEx(
            description="Lookup one security by code.",
            code=["obb.hkex.securities_master(code='00700')"],
        ),
    ],
)
async def securities_master(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject[BaseModel]:
    """Return the HKEX daily ListOfSecurities master (~18k rows)."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="HkexDerivativeProducts",
    widget_config={"refetchInterval": False},
    examples=[
        PythonEx(
            description="All listed derivative products.",
            code=["obb.hkex.derivative_products()"],
        ),
        PythonEx(
            description="Just the equity-index derivatives.",
            code=["obb.hkex.derivative_products(category='Equity-Index')"],
        ),
    ],
)
async def derivative_products(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject[BaseModel]:
    """Catalog of HKEX derivative product codes (index / FX / rate / commodity)."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="HkexStockDerivatives",
    widget_config={"refetchInterval": False},
    examples=[
        PythonEx(
            description="Stocks with listed single-stock options.",
            code=["obb.hkex.stock_derivatives(kind='options')"],
        ),
    ],
)
async def stock_derivatives(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject[BaseModel]:
    """Roster of HK stocks with listed single-stock options/futures (gives 3-letter ATS ticker)."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="HkexMarketStatistics",
    widget_config={"refetchInterval": False},
    examples=[
        PythonEx(
            description="Listed universe by trading venue (Main Board / GEM / SH / SZ).",
            code=["obb.hkex.market_statistics(group_by='venue')"],
        ),
        PythonEx(
            description="HKEX-listed market cap by Hang Seng industry.",
            code=["obb.hkex.market_statistics(group_by='industry', programme='hkex')"],
        ),
    ],
)
async def market_statistics(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject[BaseModel]:
    """Aggregate counts, market cap and turnover of the HKEX / Stock Connect listed universe."""
    return await OBBject.from_query(Query(**locals()))


equity_router = Router(prefix="")


@equity_router.command(
    model="HkexEquityQuote",
    widget_config={"refetchInterval": False},
    examples=[
        PythonEx(
            description="Live quote for HSBC (00005).",
            code=["obb.hkex.quote('00005')"],
        ),
    ],
)
async def quote(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject[BaseModel]:
    """Live quote for any HKEX-listed security."""
    return await OBBject.from_query(Query(**locals()))


@equity_router.command(
    model="HkexEquityInfo",
    widget_config={"refetchInterval": False},
    examples=[
        PythonEx(
            description="Profile for Tencent (00700).",
            code=["obb.hkex.info('00700')"],
        ),
    ],
)
async def info(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject[BaseModel]:
    """Profile, classification and listing details for any HKEX-listed security."""
    return await OBBject.from_query(Query(**locals()))


@equity_router.command(
    model="HkexEquitySearch",
    widget_config={"refetchInterval": False},
    examples=[
        PythonEx(
            description="Search for Tencent.",
            code=["obb.hkex.search('tencent')"],
        ),
        PythonEx(
            description="List all REITs.",
            code=["obb.hkex.search('', type='REIT')"],
        ),
    ],
)
async def search(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject[BaseModel]:
    """Search HKEX-listed securities by name or code (returns full reference metadata)."""
    return await OBBject.from_query(Query(**locals()))


@equity_router.command(
    model="HkexEquityHistorical",
    widget_config={"refetchInterval": False},
    examples=[
        PythonEx(
            description="Daily OHLCV for Tencent over the past month.",
            code=[
                "obb.hkex.historical('00700', start_date='2026-04-01', end_date='2026-05-01')"
            ],
        ),
    ],
)
async def historical(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject[BaseModel]:
    """Historical OHLCV bars for any HKEX-listed security."""
    return await OBBject.from_query(Query(**locals()))


index_router = Router(prefix="")


@index_router.command(
    model="HkexIndexSnapshots",
    widget_config={"refetchInterval": False},
    examples=[
        PythonEx(
            description="Snapshot of all HK index levels.",
            code=["obb.hkex.index_snapshots(region='hk')"],
        ),
    ],
)
async def index_snapshots(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject[BaseModel]:
    """Return current levels for all HKEX-tracked indices."""
    return await OBBject.from_query(Query(**locals()))


@index_router.command(
    model="HkexIndexConstituents",
    widget_config={"refetchInterval": False},
    examples=[
        PythonEx(
            description="Constituents and top-50 weights of the Hang Seng Index.",
            code=["obb.hkex.index_constituents('HSI')"],
        ),
    ],
)
async def index_constituents(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject[BaseModel]:
    """Constituents and weightings for a Hang Seng index (HSI / HSCEI / HSTECH)."""
    return await OBBject.from_query(Query(**locals()))


derivatives_router = Router(prefix="")


@derivatives_router.command(
    model="HkexOptionsChains",
    widget_config={"refetchInterval": False},
    examples=[
        PythonEx(
            description="HSI options chain.",
            code=["obb.hkex.options_chains('HSI')"],
        ),
    ],
)
async def options_chains(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject[BaseModel]:
    """Full options chain for an HKEX derivatives product or single-stock option."""
    return await OBBject.from_query(Query(**locals()))


@derivatives_router.command(
    model="HkexFuturesCurve",
    widget_config={"refetchInterval": False},
    examples=[
        PythonEx(
            description="Live HSI futures term structure.",
            code=["obb.hkex.futures_curve('HSI')"],
        ),
        PythonEx(
            description="Historical HSI curve on a specific date.",
            code=["obb.hkex.futures_curve('HSI', date='2026-04-15')"],
        ),
    ],
)
async def futures_curve(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject[BaseModel]:
    """Futures term structure for an HKEX derivatives product."""
    return await OBBject.from_query(Query(**locals()))


if not EQUITY_INSTALLED:
    router.include_router(equity_router)
if not INDEX_INSTALLED:
    router.include_router(index_router)
if not DERIVATIVES_INSTALLED:
    router.include_router(derivatives_router)

register_widgets(router)


@asynccontextmanager
async def _lifespan(_):
    """Warm the HKEX universe caches in the background for the API's lifetime."""
    import asyncio

    from openbb_hkex.utils.aggregates import prime_caches

    task = asyncio.create_task(prime_caches())
    try:
        yield
    finally:
        task.cancel()


router._api_router.lifespan_context = _lifespan
