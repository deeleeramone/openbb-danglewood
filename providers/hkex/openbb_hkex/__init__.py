"""HKEX provider module."""

from importlib.util import find_spec

from openbb_core.provider.abstract.provider import Provider

from openbb_hkex.models.company_filings import (
    HkexCompanyFilingsFetcher,
)
from openbb_hkex.models.derivative_products import (
    HkexDerivativeProductsFetcher,
)
from openbb_hkex.models.equity_historical import (
    HkexEquityHistoricalFetcher,
)
from openbb_hkex.models.equity_info import HkexEquityInfoFetcher
from openbb_hkex.models.equity_quote import HkexEquityQuoteFetcher
from openbb_hkex.models.equity_search import HkexEquitySearchFetcher
from openbb_hkex.models.etf_holdings import HkexEtfHoldingsFetcher
from openbb_hkex.models.etf_nav import HkexEtfNavFetcher
from openbb_hkex.models.etf_performance import HkexEtfPerformanceFetcher
from openbb_hkex.models.etf_tracking import HkexEtfTrackingFetcher
from openbb_hkex.models.futures_curve import HkexFuturesCurveFetcher
from openbb_hkex.models.futures_instruments import (
    HkexFuturesInstrumentsFetcher,
)
from openbb_hkex.models.index_constituents import (
    HkexIndexConstituentsFetcher,
)
from openbb_hkex.models.index_historical import (
    HkexIndexHistoricalFetcher,
)
from openbb_hkex.models.index_snapshots import (
    HkexIndexSnapshotsFetcher,
)
from openbb_hkex.models.market_statistics import (
    HkexMarketStatisticsFetcher,
)
from openbb_hkex.models.market_turnover import (
    HkexMarketTurnoverFetcher,
)
from openbb_hkex.models.options_chains import HkexOptionsChainsFetcher
from openbb_hkex.models.securities_master import (
    HkexSecuritiesMasterFetcher,
)
from openbb_hkex.models.stock_derivatives import (
    HkexStockDerivativesFetcher,
)

EQUITY_INSTALLED = find_spec("openbb_equity") is not None
INDEX_INSTALLED = find_spec("openbb_index") is not None
DERIVATIVES_INSTALLED = find_spec("openbb_derivatives") is not None


def _key(standard: str, hkex_alias: str, installed: bool) -> str:
    """Return the standard model key when the sibling is installed, else the HKEX alias."""
    return standard if installed else hkex_alias


hkex_provider = Provider(
    name="hkex",
    description=("Hong Kong Exchange open-data provider."),
    website="https://www.hkex.com.hk/",
    fetcher_dict={
        _key("EquityQuote", "HkexEquityQuote", EQUITY_INSTALLED): (
            HkexEquityQuoteFetcher
        ),
        _key("EquityInfo", "HkexEquityInfo", EQUITY_INSTALLED): (HkexEquityInfoFetcher),
        _key("EquitySearch", "HkexEquitySearch", EQUITY_INSTALLED): (
            HkexEquitySearchFetcher
        ),
        _key("EquityHistorical", "HkexEquityHistorical", EQUITY_INSTALLED): (
            HkexEquityHistoricalFetcher
        ),
        _key("CompanyFilings", "HkexCompanyFilings", EQUITY_INSTALLED): (
            HkexCompanyFilingsFetcher
        ),
        _key("IndexSnapshots", "HkexIndexSnapshots", INDEX_INSTALLED): (
            HkexIndexSnapshotsFetcher
        ),
        _key("IndexHistorical", "HkexIndexHistorical", INDEX_INSTALLED): (
            HkexIndexHistoricalFetcher
        ),
        _key("IndexConstituents", "HkexIndexConstituents", INDEX_INSTALLED): (
            HkexIndexConstituentsFetcher
        ),
        _key("OptionsChains", "HkexOptionsChains", DERIVATIVES_INSTALLED): (
            HkexOptionsChainsFetcher
        ),
        _key("FuturesCurve", "HkexFuturesCurve", DERIVATIVES_INSTALLED): (
            HkexFuturesCurveFetcher
        ),
        "HkexFuturesInstruments": HkexFuturesInstrumentsFetcher,
        "HkexEtfHoldings": HkexEtfHoldingsFetcher,
        "HkexEtfNav": HkexEtfNavFetcher,
        "HkexEtfPerformance": HkexEtfPerformanceFetcher,
        "HkexEtfTracking": HkexEtfTrackingFetcher,
        "HkexSecuritiesMaster": HkexSecuritiesMasterFetcher,
        "HkexDerivativeProducts": HkexDerivativeProductsFetcher,
        "HkexStockDerivatives": HkexStockDerivativesFetcher,
        "HkexMarketTurnover": HkexMarketTurnoverFetcher,
        "HkexMarketStatistics": HkexMarketStatisticsFetcher,
    },
    repr_name="Hong Kong Exchange (HKEX)",
)
