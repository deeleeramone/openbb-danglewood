"""Tests for the yfinance hybrid provider/router registration contract."""

import openbb_yfinance as m
from openbb_yfinance import _key
from openbb_yfinance.yfinance_router import router

_SIBLING_KEYS = {
    "EQUITY_INSTALLED": ("EquityHistorical", "YfEquityHistorical"),
    "ETF_INSTALLED": ("EtfInfo", "YfEtfInfo"),
    "DERIVATIVES_INSTALLED": ("OptionsChains", "YfOptionsChains"),
    "INDEX_INSTALLED": ("IndexHistorical", "YfIndexHistorical"),
    "CRYPTO_INSTALLED": ("CryptoHistorical", "YfCryptoHistorical"),
    "CURRENCY_INSTALLED": ("CurrencyHistorical", "YfCurrencyHistorical"),
    "NEWS_INSTALLED": ("CompanyNews", "YfCompanyNews"),
}


def test_key_helper_namespacing():
    """The _key helper returns the standard key only when the sibling is installed."""
    assert _key("EquityHistorical", "YfEquityHistorical", True) == "EquityHistorical"
    assert _key("EquityHistorical", "YfEquityHistorical", False) == "YfEquityHistorical"


def test_fetcher_dict_matches_install_flags():
    """Each sibling-owned fetcher is keyed by the standard or yf alias per flag."""
    fetchers = m.yfinance_provider.fetcher_dict
    for flag, (standard, alias) in _SIBLING_KEYS.items():
        installed = getattr(m, flag)
        expected = standard if installed else alias
        unexpected = alias if installed else standard
        assert expected in fetchers, f"{expected} missing for {flag}={installed}"
        assert unexpected not in fetchers, (
            f"{unexpected} present for {flag}={installed}"
        )


def test_always_on_fetchers_registered():
    """Funds, search and news fetchers are always registered under yf keys."""
    fetchers = m.yfinance_provider.fetcher_dict
    for key in (
        "YfFundInfo",
        "YfFundHoldings",
        "YfFundAllocation",
        "YfFundHistorical",
        "YfFundPerformance",
        "YfFundRatings",
        "YfFundRisk",
        "YfSymbolSearch",
        "YfNews",
    ):
        assert key in fetchers


def test_router_always_on_commands():
    """The router always exposes search, news, funds and tv_widget."""
    paths = {r.path for r in router.api_router.routes}
    assert "/search" in paths
    assert "/news" in paths
    assert "/tv_widget/view" in paths
    for cmd in (
        "/funds/info",
        "/funds/holdings",
        "/funds/allocation",
        "/funds/historical",
        "/funds/performance",
        "/funds/ratings",
        "/funds/risk",
    ):
        assert cmd in paths


def test_router_conditional_subrouters():
    """Standalone sibling commands are mounted only when the sibling is absent."""
    paths = {r.path for r in router.api_router.routes}
    if m.EQUITY_INSTALLED:
        assert not any(p.startswith("/equity") for p in paths)
    else:
        assert "/equity/price/historical" in paths
    if m.ETF_INSTALLED:
        assert not any(p.startswith("/etf") for p in paths)
    else:
        assert "/etf/info" in paths
