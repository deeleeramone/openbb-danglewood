"""Tests for YFinance fetchers."""

from datetime import date

import pytest
from openbb_core.app.service.user_service import UserService

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
from openbb_yfinance.models.growth_estimates import YFinanceGrowthEstimatesFetcher
from openbb_yfinance.models.historical_dividends import (
    YFinanceHistoricalDividendsFetcher,
)
from openbb_yfinance.models.historical_eps import YFinanceHistoricalEpsFetcher
from openbb_yfinance.models.income_statement import YFinanceIncomeStatementFetcher
from openbb_yfinance.models.index_historical import (
    YFinanceIndexHistoricalFetcher,
)
from openbb_yfinance.models.industry_overview import YFinanceIndustryOverviewFetcher
from openbb_yfinance.models.industry_top_growth import YFinanceIndustryTopGrowthFetcher
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
from openbb_yfinance.models.yf_news import YFinanceNewsFetcher

test_credentials = UserService().default_user_settings.credentials.model_dump(
    mode="json"
)


def scrub_string(key, value):
    """Scrub a string from the response."""

    def before_record_response(response):
        if key == "<!doctype html>":
            response_body = response["body"]["string"]
            if isinstance(response_body, bytes):
                response_body = response_body.decode("utf-8", errors="ignore")

            if key.lower() in response_body.lower():
                response["body"]["string"] = bytes("MOCK_RESPONSE", "utf-8")

        if key in response["headers"]:
            response["headers"][key] = value
        return response

    return before_record_response


def trim_earnings_html(response):
    """Keep only the data table from the large earnings-calendar HTML page."""
    import re

    body = response["body"]["string"]
    text = body.decode("utf-8", "ignore") if isinstance(body, bytes) else body
    if "Earnings Date" in text and "<table" in text.lower():
        match = re.search(r"<table.*?</table>", text, re.S | re.I)
        if match:
            response["body"]["string"] = (
                f"<html><body>{match.group(0)}</body></html>".encode()
            )
    return response


@pytest.fixture(scope="module")
def vcr_config():
    """VCR configuration."""
    return {
        "allow_playback_repeats": True,
        "match_on": ["method", "uri"],
        "filter_headers": [
            ("User-Agent", None),
            ("Cookie", "MOCK_COOKIE"),
            ("crumb", "MOCK_CRUMB"),
            ("Accept", None),
            ("Accept-Encoding", None),
            ("Accept-Language", None),
            ("Cache-Control", None),
            ("Connection", None),
            ("DNT", None),
            ("Upgrade-Insecure-Requests", None),
            ("Sec-Fetch-Dest", None),
            ("Sec-Fetch-Mode", None),
            ("Sec-Fetch-Site", None),
            ("Sec-Fetch-User", None),
        ],
        "filter_query_parameters": [
            ("period1", "MOCK_PERIOD_1"),
            ("period2", "MOCK_PERIOD_2"),
            ("crumb", "MOCK_CRUMB"),
            ("date", "MOCK_DATE"),
            ("corsDomain", "MOCK_CORS"),
            ("lang", "MOCK_LANG"),
            ("region", "MOCK_REGION"),
        ],
        "filter_post_data_parameters": [
            ("query", "MOCK_QUERY"),
            ("size", "MOCK_SIZE"),
            ("offset", "MOCK_OFFSET"),
        ],
        "before_record_response": [
            scrub_string("set-cookie", "MOCK_COOKIE"),
            scrub_string("x-envoy-decorator-operation", "MOCK_OPERATION"),
            scrub_string("y-rid", "MOCK_RID"),
            scrub_string("content-security-policy", "MOCK_CSP"),
            scrub_string("link", "MOCK_LINK"),
            scrub_string("report-to", "MOCK_REPORT"),
            scrub_string("expect-ct", "MOCK_EXPECT_CT"),
            trim_earnings_html,
        ],
        "decode_compressed_response": True,
    }


@pytest.mark.record_curl
def test_y_finance_crypto_historical_fetcher(credentials=test_credentials):
    """Test YFinanceCryptoHistoricalFetcher."""
    params = {
        "symbol": "BTCUSD",
        "start_date": date(2023, 1, 1),
        "end_date": date(2023, 1, 10),
        "interval": "1d",
    }

    fetcher = YFinanceCryptoHistoricalFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_currency_historical_fetcher(credentials=test_credentials):
    """Test YFinanceCurrencyHistoricalFetcher."""
    params = {
        "symbol": "EURUSD",
        "start_date": date(2023, 1, 1),
        "end_date": date(2023, 1, 10),
    }

    fetcher = YFinanceCurrencyHistoricalFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_index_historical_fetcher(credentials=test_credentials):
    """Test YFinanceIndexHistoricalFetcher."""
    params = {
        "symbol": "^GSPC",
        "start_date": date(2023, 1, 1),
        "end_date": date(2023, 1, 10),
    }

    fetcher = YFinanceIndexHistoricalFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_equity_historical_fetcher(credentials=test_credentials):
    """Test YFinanceEquityHistoricalFetcher."""
    params = {
        "symbol": "AAPL",
        "start_date": date(2023, 1, 1),
        "end_date": date(2023, 1, 10),
        "interval": "1d",
    }

    fetcher = YFinanceEquityHistoricalFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_historical_dividends_fetcher(credentials=test_credentials):
    """Test YFinanceHistoricalDividendsFetcher."""
    params = {"symbol": "IBM"}

    fetcher = YFinanceHistoricalDividendsFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_futures_historical_fetcher(credentials=test_credentials):
    """Test YFinanceFuturesHistoricalFetcher."""
    params = {
        "symbol": "ES=F",
        "start_date": date(2023, 1, 1),
        "end_date": date(2023, 1, 10),
    }

    fetcher = YFinanceFuturesHistoricalFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_options_chains_fetcher(credentials=test_credentials):
    """Test YFinanceOptionsChainsFetcher."""

    params = {"symbol": "OXY"}

    fetcher = YFinanceOptionsChainsFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_futures_curve_fetcher(credentials=test_credentials):
    """Test YFinanceFuturesCurveFetcher."""
    params = {"symbol": "ES"}

    fetcher = YFinanceFuturesCurveFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_company_news_fetcher(credentials=test_credentials):
    """Test YFinanceCompanyNewsFetcher."""
    params = {"symbol": "AAPL,MSFT", "limit": 2}

    fetcher = YFinanceCompanyNewsFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_balance_sheet_fetcher(credentials=test_credentials):
    """Test YFinanceBalanceSheetFetcher."""
    params = {"symbol": "AAPL"}

    fetcher = YFinanceBalanceSheetFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_cash_flow_statement_fetcher(credentials=test_credentials):
    """Test YFinanceCashFlowStatementFetcher."""
    params = {"symbol": "AAPL"}

    fetcher = YFinanceCashFlowStatementFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_income_statement_fetcher(credentials=test_credentials):
    """Test YFinanceIncomeStatementFetcher."""
    params = {"symbol": "AAPL"}

    fetcher = YFinanceIncomeStatementFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


def test_y_finance_available_fetcher(credentials=test_credentials):
    """Test YFinanceAvailableIndicesFetcher."""
    params = {}

    fetcher = YFinanceAvailableIndicesFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_equity_profile_fetcher(credentials=test_credentials):
    """Test YFinanceEquityProfileFetcher."""
    params = {"symbol": "AAPL"}

    fetcher = YFinanceEquityProfileFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_equity_quote_fetcher(credentials=test_credentials):
    """Test YFinanceEquityQuoteFetcher."""
    params = {"symbol": "AAPL"}

    fetcher = YFinanceEquityQuoteFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_price_target_consensus_fetcher(credentials=test_credentials):
    """Test YFinancePriceTargetConsensusFetcher."""
    params = {"symbol": "AAPL"}

    fetcher = YFinancePriceTargetConsensusFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_share_statistics_fetcher(credentials=test_credentials):
    """Test YFinanceShareStatisticsFetcher."""
    params = {"symbol": "AAPL"}

    fetcher = YFinanceShareStatisticsFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_key_executives_fetcher(credentials=test_credentials):
    """Test YFinanceKeyExecutivesFetcher."""
    params = {"symbol": "AAPL"}

    fetcher = YFinanceKeyExecutivesFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_key_metrics_fetcher(
    credentials=test_credentials,
):
    """Test YFinanceKeyMetricsFetcher."""
    params = {"symbol": "AAPL"}

    fetcher = YFinanceKeyMetricsFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_etf_info_fetcher(credentials=test_credentials):
    """Test YFinanceEtfInfoFetcher."""
    params = {"symbol": "QQQ"}

    fetcher = YFinanceEtfInfoFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_equity_screener_fetcher(credentials=test_credentials):
    """Test YFinanceEquityScreener."""
    params = {
        "country": "us",
        "sector": "consumer_cyclical",
        "industry": "auto_manufacturers",
        "mktcap_min": 60000000000,
        "volume_min": 5000000,
        "price_min": 10,
    }

    fetcher = YFinanceEquityScreenerFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_fund_info_fetcher(credentials=test_credentials):
    """Test YFinanceFundInfoFetcher."""
    params = {"symbol": "VTSAX"}

    fetcher = YFinanceFundInfoFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_fund_holdings_fetcher(credentials=test_credentials):
    """Test YFinanceFundHoldingsFetcher."""
    params = {"symbol": "VTSAX"}

    fetcher = YFinanceFundHoldingsFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_fund_allocation_fetcher(credentials=test_credentials):
    """Test YFinanceFundAllocationFetcher."""
    params = {"symbol": "VTSAX"}

    fetcher = YFinanceFundAllocationFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_fund_historical_fetcher(credentials=test_credentials):
    """Test YFinanceFundHistoricalFetcher."""
    params = {
        "symbol": "VTSAX",
        "start_date": date(2023, 1, 1),
        "end_date": date(2023, 3, 1),
    }

    fetcher = YFinanceFundHistoricalFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_fund_performance_fetcher(credentials=test_credentials):
    """Test YFinanceFundPerformanceFetcher."""
    params = {"symbol": "VFINX"}

    fetcher = YFinanceFundPerformanceFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_fund_ratings_fetcher(credentials=test_credentials):
    """Test YFinanceFundRatingsFetcher."""
    params = {"symbol": "VFINX"}

    fetcher = YFinanceFundRatingsFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_fund_risk_fetcher(credentials=test_credentials):
    """Test YFinanceFundRiskFetcher."""
    params = {
        "symbol": "VFINX",
        "benchmark": "^GSPC",
        "start_date": date(2023, 1, 1),
        "end_date": date(2023, 12, 31),
    }

    fetcher = YFinanceFundRiskFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_symbol_search_fetcher(credentials=test_credentials):
    """Test YFinanceSymbolSearchFetcher."""
    params = {"query": "vanguard", "asset_type": "mutualfund"}

    fetcher = YFinanceSymbolSearchFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_news_fetcher(credentials=test_credentials):
    """Test YFinanceNewsFetcher."""
    params = {"symbol": "AAPL", "limit": 3}

    fetcher = YFinanceNewsFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_calendar_earnings_fetcher(credentials=test_credentials):
    """Test YFinanceCalendarEarningsFetcher."""
    params = {
        "start_date": date(2026, 6, 15),
        "end_date": date(2026, 6, 30),
        "limit": 25,
    }

    fetcher = YFinanceCalendarEarningsFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_calendar_ipo_fetcher(credentials=test_credentials):
    """Test YFinanceCalendarIpoFetcher."""
    params: dict = {}

    fetcher = YFinanceCalendarIpoFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_calendar_splits_fetcher(credentials=test_credentials):
    """Test YFinanceCalendarSplitsFetcher."""
    params: dict = {}

    fetcher = YFinanceCalendarSplitsFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_economic_calendar_fetcher(credentials=test_credentials):
    """Test YFinanceEconomicCalendarFetcher."""
    params: dict = {}

    fetcher = YFinanceEconomicCalendarFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_historical_eps_fetcher(credentials=test_credentials):
    """Test YFinanceHistoricalEpsFetcher."""
    params = {"symbol": "AAPL", "limit": 25}

    fetcher = YFinanceHistoricalEpsFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_company_filings_fetcher(credentials=test_credentials):
    """Test YFinanceCompanyFilingsFetcher."""
    params = {"symbol": "AAPL"}

    fetcher = YFinanceCompanyFilingsFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_company_calendar_fetcher(credentials=test_credentials):
    """Test YFinanceCompanyCalendarFetcher."""
    params = {"symbol": "AAPL"}

    fetcher = YFinanceCompanyCalendarFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_price_target_fetcher(credentials=test_credentials):
    """Test YFinancePriceTargetFetcher."""
    params = {"symbol": "AAPL", "limit": 10}

    fetcher = YFinancePriceTargetFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_analyst_recommendations_fetcher(credentials=test_credentials):
    """Test YFinanceAnalystRecommendationsFetcher."""
    params = {"symbol": "AAPL"}

    fetcher = YFinanceAnalystRecommendationsFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_earnings_estimates_fetcher(credentials=test_credentials):
    """Test YFinanceEarningsEstimatesFetcher."""
    params = {"symbol": "AAPL"}

    fetcher = YFinanceEarningsEstimatesFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_revenue_estimates_fetcher(credentials=test_credentials):
    """Test YFinanceRevenueEstimatesFetcher."""
    params = {"symbol": "AAPL"}

    fetcher = YFinanceRevenueEstimatesFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_eps_trend_fetcher(credentials=test_credentials):
    """Test YFinanceEpsTrendFetcher."""
    params = {"symbol": "AAPL"}

    fetcher = YFinanceEpsTrendFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_eps_revisions_fetcher(credentials=test_credentials):
    """Test YFinanceEpsRevisionsFetcher."""
    params = {"symbol": "AAPL"}

    fetcher = YFinanceEpsRevisionsFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_growth_estimates_fetcher(credentials=test_credentials):
    """Test YFinanceGrowthEstimatesFetcher."""
    params = {"symbol": "AAPL"}

    fetcher = YFinanceGrowthEstimatesFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_insider_trading_fetcher(credentials=test_credentials):
    """Test YFinanceInsiderTradingFetcher."""
    params = {"symbol": "AAPL", "limit": 10}

    fetcher = YFinanceInsiderTradingFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_institutional_holders_fetcher(credentials=test_credentials):
    """Test YFinanceInstitutionalHoldersFetcher."""
    params = {"symbol": "AAPL"}

    fetcher = YFinanceInstitutionalHoldersFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_mutualfund_holders_fetcher(credentials=test_credentials):
    """Test YFinanceMutualFundHoldersFetcher."""
    params = {"symbol": "AAPL"}

    fetcher = YFinanceMutualFundHoldersFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_major_holders_fetcher(credentials=test_credentials):
    """Test YFinanceMajorHoldersFetcher."""
    params = {"symbol": "AAPL"}

    fetcher = YFinanceMajorHoldersFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_insider_purchases_fetcher(credentials=test_credentials):
    """Test YFinanceInsiderPurchasesFetcher."""
    params = {"symbol": "AAPL"}

    fetcher = YFinanceInsiderPurchasesFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_insider_roster_fetcher(credentials=test_credentials):
    """Test YFinanceInsiderRosterFetcher."""
    params = {"symbol": "AAPL"}

    fetcher = YFinanceInsiderRosterFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_sector_overview_fetcher(credentials=test_credentials):
    """Test YFinanceSectorOverviewFetcher."""
    params = {"sector": "technology"}

    fetcher = YFinanceSectorOverviewFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_sector_top_companies_fetcher(credentials=test_credentials):
    """Test YFinanceSectorTopCompaniesFetcher."""
    params = {"sector": "technology"}

    fetcher = YFinanceSectorTopCompaniesFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_sector_top_funds_fetcher(credentials=test_credentials):
    """Test YFinanceSectorTopFundsFetcher."""
    params = {"sector": "technology", "fund_type": "etf"}

    fetcher = YFinanceSectorTopFundsFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_sector_industries_fetcher(credentials=test_credentials):
    """Test YFinanceSectorIndustriesFetcher."""
    params = {"sector": "technology"}

    fetcher = YFinanceSectorIndustriesFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_industry_overview_fetcher(credentials=test_credentials):
    """Test YFinanceIndustryOverviewFetcher."""
    params = {"industry": "software-infrastructure"}

    fetcher = YFinanceIndustryOverviewFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_industry_top_performing_fetcher(credentials=test_credentials):
    """Test YFinanceIndustryTopPerformingFetcher."""
    params = {"industry": "software-infrastructure"}

    fetcher = YFinanceIndustryTopPerformingFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_industry_top_growth_fetcher(credentials=test_credentials):
    """Test YFinanceIndustryTopGrowthFetcher."""
    params = {"industry": "software-infrastructure"}

    fetcher = YFinanceIndustryTopGrowthFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_equity_screener_preset_fetcher(credentials=test_credentials):
    """Test YFinanceEquityScreenerFetcher with an INI preset."""
    params = {"preset": "large_cap_value", "limit": 25}

    fetcher = YFinanceEquityScreenerFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_private_companies_fetcher(credentials=test_credentials):
    """Test YFinancePrivateCompaniesFetcher."""
    params = {"category": "highest_valuation", "limit": 3}

    fetcher = YFinancePrivateCompaniesFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_equity_screener_predefined_fetcher(credentials=test_credentials):
    """Test YFinanceEquityScreenerFetcher with a predefined scrId passthrough."""
    params = {"predefined": "most_actives", "limit": 10}

    fetcher = YFinanceEquityScreenerFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_curl
def test_y_finance_equity_screener_etf_metadata_fetcher(
    reset_yfinance_session, credentials=test_credentials
):
    """Test YFinanceEquityScreenerFetcher enriches ETFs with full metadata."""
    params = {"predefined": "top_etfs_us", "limit": 3}

    fetcher = YFinanceEquityScreenerFetcher()
    result = fetcher.test(params, credentials)
    assert result is None
