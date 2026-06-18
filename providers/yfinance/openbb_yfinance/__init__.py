"""Yahoo Finance provider module."""

from importlib.util import find_spec

from openbb_core.provider.abstract.provider import Provider

from openbb_yfinance.models.active import YFActiveFetcher
from openbb_yfinance.models.aggressive_small_caps import YFAggressiveSmallCapsFetcher
from openbb_yfinance.models.analyst_recommendations import (
    YFinanceAnalystRecommendationsFetcher,
)
from openbb_yfinance.models.available_indices import YFinanceAvailableIndicesFetcher
from openbb_yfinance.models.balance_sheet import YFinanceBalanceSheetFetcher
from openbb_yfinance.models.calendar_earnings import YFinanceCalendarEarningsFetcher
from openbb_yfinance.models.calendar_ipo import YFinanceCalendarIpoFetcher
from openbb_yfinance.models.calendar_splits import YFinanceCalendarSplitsFetcher
from openbb_yfinance.models.cash_flow import YFinanceCashFlowStatementFetcher
from openbb_yfinance.models.company_calendar import YFinanceCompanyCalendarFetcher
from openbb_yfinance.models.company_filings import YFinanceCompanyFilingsFetcher
from openbb_yfinance.models.company_news import YFinanceCompanyNewsFetcher
from openbb_yfinance.models.crypto_historical import YFinanceCryptoHistoricalFetcher
from openbb_yfinance.models.currency_historical import YFinanceCurrencyHistoricalFetcher
from openbb_yfinance.models.earnings_estimates import YFinanceEarningsEstimatesFetcher
from openbb_yfinance.models.economic_calendar import YFinanceEconomicCalendarFetcher
from openbb_yfinance.models.eps_revisions import YFinanceEpsRevisionsFetcher
from openbb_yfinance.models.eps_trend import YFinanceEpsTrendFetcher
from openbb_yfinance.models.equity_historical import YFinanceEquityHistoricalFetcher
from openbb_yfinance.models.equity_profile import YFinanceEquityProfileFetcher
from openbb_yfinance.models.equity_quote import YFinanceEquityQuoteFetcher
from openbb_yfinance.models.equity_screener import YFinanceEquityScreenerFetcher
from openbb_yfinance.models.etf_info import YFinanceEtfInfoFetcher
from openbb_yfinance.models.fund_allocation import YFinanceFundAllocationFetcher
from openbb_yfinance.models.fund_historical import YFinanceFundHistoricalFetcher
from openbb_yfinance.models.fund_holdings import YFinanceFundHoldingsFetcher
from openbb_yfinance.models.fund_info import YFinanceFundInfoFetcher
from openbb_yfinance.models.fund_performance import YFinanceFundPerformanceFetcher
from openbb_yfinance.models.fund_ratings import YFinanceFundRatingsFetcher
from openbb_yfinance.models.fund_risk import YFinanceFundRiskFetcher
from openbb_yfinance.models.futures_curve import YFinanceFuturesCurveFetcher
from openbb_yfinance.models.futures_historical import YFinanceFuturesHistoricalFetcher
from openbb_yfinance.models.gainers import YFGainersFetcher
from openbb_yfinance.models.growth_estimates import YFinanceGrowthEstimatesFetcher
from openbb_yfinance.models.growth_tech_equities import YFGrowthTechEquitiesFetcher
from openbb_yfinance.models.historical_dividends import (
    YFinanceHistoricalDividendsFetcher,
)
from openbb_yfinance.models.historical_eps import YFinanceHistoricalEpsFetcher
from openbb_yfinance.models.income_statement import YFinanceIncomeStatementFetcher
from openbb_yfinance.models.index_historical import YFinanceIndexHistoricalFetcher
from openbb_yfinance.models.industry_overview import YFinanceIndustryOverviewFetcher
from openbb_yfinance.models.industry_top_growth import (
    YFinanceIndustryTopGrowthFetcher,
)
from openbb_yfinance.models.industry_top_performing import (
    YFinanceIndustryTopPerformingFetcher,
)
from openbb_yfinance.models.insider_purchases import YFinanceInsiderPurchasesFetcher
from openbb_yfinance.models.insider_roster import YFinanceInsiderRosterFetcher
from openbb_yfinance.models.insider_trading import YFinanceInsiderTradingFetcher
from openbb_yfinance.models.institutional_holders import (
    YFinanceInstitutionalHoldersFetcher,
)
from openbb_yfinance.models.key_executives import YFinanceKeyExecutivesFetcher
from openbb_yfinance.models.key_metrics import YFinanceKeyMetricsFetcher
from openbb_yfinance.models.losers import YFLosersFetcher
from openbb_yfinance.models.major_holders import YFinanceMajorHoldersFetcher
from openbb_yfinance.models.mutualfund_holders import YFinanceMutualFundHoldersFetcher
from openbb_yfinance.models.options_chains import YFinanceOptionsChainsFetcher
from openbb_yfinance.models.price_target import YFinancePriceTargetFetcher
from openbb_yfinance.models.price_target_consensus import (
    YFinancePriceTargetConsensusFetcher,
)
from openbb_yfinance.models.private_companies import (
    YFinancePrivateCompaniesFetcher,
)
from openbb_yfinance.models.revenue_estimates import YFinanceRevenueEstimatesFetcher
from openbb_yfinance.models.sector_industries import YFinanceSectorIndustriesFetcher
from openbb_yfinance.models.sector_overview import YFinanceSectorOverviewFetcher
from openbb_yfinance.models.sector_top_companies import (
    YFinanceSectorTopCompaniesFetcher,
)
from openbb_yfinance.models.sector_top_funds import YFinanceSectorTopFundsFetcher
from openbb_yfinance.models.share_statistics import YFinanceShareStatisticsFetcher
from openbb_yfinance.models.symbol_search import YFinanceSymbolSearchFetcher
from openbb_yfinance.models.undervalued_growth_equities import (
    YFUndervaluedGrowthEquitiesFetcher,
)
from openbb_yfinance.models.undervalued_large_caps import YFUndervaluedLargeCapsFetcher
from openbb_yfinance.models.yf_news import YFinanceNewsFetcher

EQUITY_INSTALLED = find_spec("openbb_equity") is not None
ETF_INSTALLED = find_spec("openbb_etf") is not None
DERIVATIVES_INSTALLED = find_spec("openbb_derivatives") is not None
INDEX_INSTALLED = find_spec("openbb_index") is not None
CRYPTO_INSTALLED = find_spec("openbb_crypto") is not None
CURRENCY_INSTALLED = find_spec("openbb_currency") is not None
NEWS_INSTALLED = find_spec("openbb_news") is not None
ECONOMY_INSTALLED = find_spec("openbb_economy") is not None


def _key(standard: str, yf_alias: str, installed: bool) -> str:
    """Return the standard fetcher key when installed, else the yf alias."""
    return standard if installed else yf_alias


yfinance_provider = Provider(
    name="yfinance",
    website="https://finance.yahoo.com",
    description="""Yahoo! Finance is a web-based platform that offers financial news,
data, and tools for investors and individuals interested in tracking and analyzing
financial markets and assets.""",
    fetcher_dict={
        _key("BalanceSheet", "YfBalanceSheet", EQUITY_INSTALLED): (
            YFinanceBalanceSheetFetcher
        ),
        _key("CashFlowStatement", "YfCashFlowStatement", EQUITY_INSTALLED): (
            YFinanceCashFlowStatementFetcher
        ),
        _key("EquityActive", "YfEquityActive", EQUITY_INSTALLED): YFActiveFetcher,
        _key(
            "EquityAggressiveSmallCaps",
            "YfEquityAggressiveSmallCaps",
            EQUITY_INSTALLED,
        ): YFAggressiveSmallCapsFetcher,
        _key("EquityGainers", "YfEquityGainers", EQUITY_INSTALLED): YFGainersFetcher,
        _key("EquityHistorical", "YfEquityHistorical", EQUITY_INSTALLED): (
            YFinanceEquityHistoricalFetcher
        ),
        _key("EquityInfo", "YfEquityInfo", EQUITY_INSTALLED): (
            YFinanceEquityProfileFetcher
        ),
        _key("EquityLosers", "YfEquityLosers", EQUITY_INSTALLED): YFLosersFetcher,
        _key("EquityQuote", "YfEquityQuote", EQUITY_INSTALLED): (
            YFinanceEquityQuoteFetcher
        ),
        _key("EquityScreener", "YfEquityScreener", EQUITY_INSTALLED): (
            YFinanceEquityScreenerFetcher
        ),
        _key(
            "EquityUndervaluedGrowth", "YfEquityUndervaluedGrowth", EQUITY_INSTALLED
        ): YFUndervaluedGrowthEquitiesFetcher,
        _key(
            "EquityUndervaluedLargeCaps",
            "YfEquityUndervaluedLargeCaps",
            EQUITY_INSTALLED,
        ): YFUndervaluedLargeCapsFetcher,
        _key("GrowthTechEquities", "YfGrowthTechEquities", EQUITY_INSTALLED): (
            YFGrowthTechEquitiesFetcher
        ),
        _key("HistoricalDividends", "YfHistoricalDividends", EQUITY_INSTALLED): (
            YFinanceHistoricalDividendsFetcher
        ),
        _key("IncomeStatement", "YfIncomeStatement", EQUITY_INSTALLED): (
            YFinanceIncomeStatementFetcher
        ),
        _key("KeyExecutives", "YfKeyExecutives", EQUITY_INSTALLED): (
            YFinanceKeyExecutivesFetcher
        ),
        _key("KeyMetrics", "YfKeyMetrics", EQUITY_INSTALLED): YFinanceKeyMetricsFetcher,
        _key("PriceTargetConsensus", "YfPriceTargetConsensus", EQUITY_INSTALLED): (
            YFinancePriceTargetConsensusFetcher
        ),
        _key("PriceTarget", "YfPriceTarget", EQUITY_INSTALLED): (
            YFinancePriceTargetFetcher
        ),
        _key("ShareStatistics", "YfShareStatistics", EQUITY_INSTALLED): (
            YFinanceShareStatisticsFetcher
        ),
        _key("InsiderTrading", "YfInsiderTrading", EQUITY_INSTALLED): (
            YFinanceInsiderTradingFetcher
        ),
        _key("CalendarEarnings", "YfCalendarEarnings", EQUITY_INSTALLED): (
            YFinanceCalendarEarningsFetcher
        ),
        _key("CalendarIpo", "YfCalendarIpo", EQUITY_INSTALLED): (
            YFinanceCalendarIpoFetcher
        ),
        _key("CalendarSplits", "YfCalendarSplits", EQUITY_INSTALLED): (
            YFinanceCalendarSplitsFetcher
        ),
        _key("HistoricalEps", "YfHistoricalEps", EQUITY_INSTALLED): (
            YFinanceHistoricalEpsFetcher
        ),
        _key("CompanyFilings", "YfCompanyFilings", EQUITY_INSTALLED): (
            YFinanceCompanyFilingsFetcher
        ),
        _key("EconomicCalendar", "YfEconomicCalendar", ECONOMY_INSTALLED): (
            YFinanceEconomicCalendarFetcher
        ),
        _key("EtfHistorical", "YfEtfHistorical", ETF_INSTALLED): (
            YFinanceEquityHistoricalFetcher
        ),
        _key("EtfInfo", "YfEtfInfo", ETF_INSTALLED): YFinanceEtfInfoFetcher,
        _key("FuturesCurve", "YfFuturesCurve", DERIVATIVES_INSTALLED): (
            YFinanceFuturesCurveFetcher
        ),
        _key("FuturesHistorical", "YfFuturesHistorical", DERIVATIVES_INSTALLED): (
            YFinanceFuturesHistoricalFetcher
        ),
        _key("OptionsChains", "YfOptionsChains", DERIVATIVES_INSTALLED): (
            YFinanceOptionsChainsFetcher
        ),
        _key("AvailableIndices", "YfAvailableIndices", INDEX_INSTALLED): (
            YFinanceAvailableIndicesFetcher
        ),
        _key("IndexHistorical", "YfIndexHistorical", INDEX_INSTALLED): (
            YFinanceIndexHistoricalFetcher
        ),
        _key("CryptoHistorical", "YfCryptoHistorical", CRYPTO_INSTALLED): (
            YFinanceCryptoHistoricalFetcher
        ),
        _key("CurrencyHistorical", "YfCurrencyHistorical", CURRENCY_INSTALLED): (
            YFinanceCurrencyHistoricalFetcher
        ),
        _key("CompanyNews", "YfCompanyNews", NEWS_INSTALLED): (
            YFinanceCompanyNewsFetcher
        ),
        "YfFundInfo": YFinanceFundInfoFetcher,
        "YfFundHoldings": YFinanceFundHoldingsFetcher,
        "YfFundAllocation": YFinanceFundAllocationFetcher,
        "YfFundHistorical": YFinanceFundHistoricalFetcher,
        "YfFundPerformance": YFinanceFundPerformanceFetcher,
        "YfFundRatings": YFinanceFundRatingsFetcher,
        "YfFundRisk": YFinanceFundRiskFetcher,
        "YfSymbolSearch": YFinanceSymbolSearchFetcher,
        "YfNews": YFinanceNewsFetcher,
        "YfPrivateCompanies": YFinancePrivateCompaniesFetcher,
        "YfCompanyCalendar": YFinanceCompanyCalendarFetcher,
        "YfAnalystRecommendations": YFinanceAnalystRecommendationsFetcher,
        "YfEarningsEstimates": YFinanceEarningsEstimatesFetcher,
        "YfRevenueEstimates": YFinanceRevenueEstimatesFetcher,
        "YfEpsTrend": YFinanceEpsTrendFetcher,
        "YfEpsRevisions": YFinanceEpsRevisionsFetcher,
        "YfGrowthEstimates": YFinanceGrowthEstimatesFetcher,
        "YfInstitutionalHolders": YFinanceInstitutionalHoldersFetcher,
        "YfMutualFundHolders": YFinanceMutualFundHoldersFetcher,
        "YfMajorHolders": YFinanceMajorHoldersFetcher,
        "YfInsiderPurchases": YFinanceInsiderPurchasesFetcher,
        "YfInsiderRoster": YFinanceInsiderRosterFetcher,
        "YfSectorOverview": YFinanceSectorOverviewFetcher,
        "YfSectorTopCompanies": YFinanceSectorTopCompaniesFetcher,
        "YfSectorTopFunds": YFinanceSectorTopFundsFetcher,
        "YfSectorIndustries": YFinanceSectorIndustriesFetcher,
        "YfIndustryOverview": YFinanceIndustryOverviewFetcher,
        "YfIndustryTopPerforming": YFinanceIndustryTopPerformingFetcher,
        "YfIndustryTopGrowth": YFinanceIndustryTopGrowthFetcher,
    },
    repr_name="Yahoo Finance",
)
