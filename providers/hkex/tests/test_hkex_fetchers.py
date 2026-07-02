"""HKEX fetchers tests."""

from datetime import date

import pytest
from openbb_core.app.service.user_service import UserService

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
from openbb_hkex.models.etf_performance import (
    HkexEtfPerformanceFetcher,
)
from openbb_hkex.models.etf_tracking import HkexEtfTrackingFetcher
from openbb_hkex.models.futures_curve import HkexFuturesCurveFetcher
from openbb_hkex.models.futures_historical import (
    HkexFuturesHistoricalFetcher,
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

test_credentials = UserService().default_user_settings.credentials.model_dump(
    mode="json"
)


@pytest.fixture(scope="module")
def vcr_config():
    """VCR config.

    HKEX widget URLs carry a rotating ``token`` and per-call ``qid`` timestamp.
    We rewrite both to constants on record so cassettes replay deterministically.
    Response bodies are forced to decoded UTF-8 strings (not !!binary).
    """

    def _scrub(request):
        from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

        u = urlparse(request.uri)
        if not u.query:
            return request
        qs = [
            (
                k,
                "MOCK_TOKEN"
                if k == "token"
                else "MOCK_QID"
                if k == "qid"
                else "MOCK_TS"
                if k == "_"
                else v,
            )
            for k, v in parse_qsl(u.query, keep_blank_values=True)
        ]
        request.uri = urlunparse(u._replace(query=urlencode(qs)))
        return request

    return {
        "filter_headers": [
            ("User-Agent", "MOCK_UA"),
            ("Cookie", "MOCK_COOKIE"),
            ("Set-Cookie", "MOCK_COOKIE"),
        ],
        "before_record_request": _scrub,
        # ``body`` disambiguates issuer POSTs that share a URL but differ by body
        # (e.g. CSOP's per-fund ``/cmsApi/NAV/product`` calls).
        "match_on": ["method", "scheme", "host", "port", "path", "query", "body"],
        "decode_compressed_response": True,
        "serializer": "yaml",
    }


@pytest.fixture(autouse=True)
def _clear_issuer_caches():
    """Clear the module-level issuer/index resolver caches before every test.

    The ETF adapters memoize their code->id resolvers with ``alru_cache``. Without
    clearing, the first test to touch an issuer populates the cache and later tests
    never re-issue those HTTP calls — leaving their cassettes incomplete and
    un-replayable in isolation. Clearing makes each cassette self-contained.
    """
    from openbb_hkex.utils import etf_sources

    for name in (
        "_csop_fund_index",
        "_ishares_index",
        "_globalx_index",
        "_chinaamc_index",
        "_hsim_fundlist",
    ):
        fn = getattr(etf_sources, name, None)
        if fn is not None and hasattr(fn, "cache_clear"):
            fn.cache_clear()
    yield


# ── Standard-model fetchers ────────────────────────────────────────────────


@pytest.mark.record_http
def test_hkex_equity_quote_fetcher(credentials=test_credentials):
    """Test HKEX equity quote fetcher."""
    params = {"symbol": "00005"}
    fetcher = HkexEquityQuoteFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_http
def test_hkex_equity_info_fetcher(credentials=test_credentials):
    """Test HKEX equity info fetcher."""
    params = {"symbol": "00005"}
    fetcher = HkexEquityInfoFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_http
def test_hkex_equity_search_fetcher(credentials=test_credentials):
    """Test HKEX equity search fetcher."""
    params = {"query": "tencent", "is_symbol": False, "limit": 10, "type": "EQTY"}
    fetcher = HkexEquitySearchFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_http
def test_hkex_equity_historical_fetcher(credentials=test_credentials):
    """Test HKEX equity historical fetcher."""
    params = {
        "symbol": "00700",
        "start_date": date(2026, 4, 1),
        "end_date": date(2026, 5, 1),
        "interval": "1d",
    }
    fetcher = HkexEquityHistoricalFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_http
def test_hkex_index_snapshots_fetcher(credentials=test_credentials):
    """Test HKEX index snapshots fetcher."""
    params = {"region": "hk"}
    fetcher = HkexIndexSnapshotsFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_http
def test_hkex_index_historical_fetcher(credentials=test_credentials):
    """Test HKEX index historical fetcher."""
    params = {
        "symbol": ".HSI",
        "start_date": date(2026, 4, 1),
        "end_date": date(2026, 5, 1),
        "interval": "1d",
    }
    fetcher = HkexIndexHistoricalFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_http
def test_hkex_options_chains_fetcher(credentials=test_credentials):
    """Test HKEX options chains fetcher."""
    params = {"symbol": "HSI", "contract_type": "standard"}
    fetcher = HkexOptionsChainsFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_http
def test_hkex_futures_curve_fetcher(credentials=test_credentials):
    """Test HKEX futures curve fetcher."""
    params = {"symbol": "HSI", "contract_type": "standard"}
    fetcher = HkexFuturesCurveFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_http
def test_hkex_futures_historical_fetcher(credentials=test_credentials):
    """Test HKEX futures historical fetcher."""
    params = {
        "symbol": "HSI",
        "start_date": date(2026, 4, 1),
        "end_date": date(2026, 5, 1),
        "contract_type": "standard",
        "interval": "1d",
    }
    fetcher = HkexFuturesHistoricalFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_http
def test_hkex_company_filings_fetcher(credentials=test_credentials):
    """Test HKEX company filings fetcher."""
    params = {
        "symbol": "00700",
        "form_group": "annual",
        "start_date": date(2025, 1, 1),
        "end_date": date(2025, 12, 31),
    }
    fetcher = HkexCompanyFilingsFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


# ── HKEX-specific custom fetchers ──────────────────────────────────────────


@pytest.mark.record_http
def test_hkex_securities_master_fetcher(credentials=test_credentials):
    """Test HKEX securities master fetcher."""
    params = {"code": "00700"}
    fetcher = HkexSecuritiesMasterFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


def test_hkex_derivative_products_fetcher(credentials=test_credentials):
    """Test HKEX derivative products fetcher."""
    params = {"category": "Equity-Index"}
    fetcher = HkexDerivativeProductsFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_http
def test_hkex_stock_derivatives_fetcher(credentials=test_credentials):
    """Test HKEX stock derivatives fetcher."""
    params = {"kind": "options"}
    fetcher = HkexStockDerivativesFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_http
def test_hkex_market_turnover_fetcher(credentials=test_credentials):
    """Test HKEX market turnover fetcher."""
    params: dict = {}
    fetcher = HkexMarketTurnoverFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


# ── ETF & index data fetchers (issuer-routed) ─────────────────────────────
# Issuers are chosen so no request body depends on the current date, keeping
# cassettes deterministic on replay. CSOP exercises the POST-body match path.


@pytest.mark.record_http
def test_hkex_etf_holdings_fetcher(credentials=test_credentials):
    """Test HKEX ETF holdings fetcher (CSOP)."""
    params = {"symbol": "03037"}
    fetcher = HkexEtfHoldingsFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_http
def test_hkex_etf_nav_fetcher(credentials=test_credentials):
    """Test HKEX ETF NAV-history fetcher (ChinaAMC JeecgBoot API)."""
    params = {"symbol": "03188"}
    fetcher = HkexEtfNavFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_http
def test_hkex_etf_performance_fetcher(credentials=test_credentials):
    """Test HKEX ETF performance fetcher (iShares)."""
    params = {"symbol": "02823"}
    fetcher = HkexEtfPerformanceFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_http
def test_hkex_etf_tracking_fetcher(credentials=test_credentials):
    """Test HKEX ETF tracking fetcher (Hang Seng IM)."""
    params = {"symbol": "02828"}
    fetcher = HkexEtfTrackingFetcher()
    result = fetcher.test(params, credentials)
    assert result is None


@pytest.mark.record_http
def test_hkex_index_constituents_fetcher(credentials=test_credentials):
    """Test HKEX index constituents fetcher (Hang Seng Index)."""
    params = {"symbol": "HSI"}
    fetcher = HkexIndexConstituentsFetcher()
    result = fetcher.test(params, credentials)
    assert result is None
