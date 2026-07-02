"""Tests for the HKEX provider/router conditional-registration contract."""

import openbb_hkex as m
from openbb_hkex import _key
from openbb_hkex.hkex_router import router

_SIBLING_KEYS = {
    "EQUITY_INSTALLED": [
        ("EquityQuote", "HkexEquityQuote"),
        ("EquityInfo", "HkexEquityInfo"),
        ("EquitySearch", "HkexEquitySearch"),
        ("EquityHistorical", "HkexEquityHistorical"),
        ("CompanyFilings", "HkexCompanyFilings"),
    ],
    "INDEX_INSTALLED": [
        ("IndexSnapshots", "HkexIndexSnapshots"),
        ("IndexHistorical", "HkexIndexHistorical"),
        ("IndexConstituents", "HkexIndexConstituents"),
    ],
    "DERIVATIVES_INSTALLED": [
        ("OptionsChains", "HkexOptionsChains"),
        ("FuturesCurve", "HkexFuturesCurve"),
    ],
}

_ALWAYS_HKEX = (
    "HkexFuturesInstruments",
    "HkexEtfHoldings",
    "HkexEtfNav",
    "HkexEtfPerformance",
    "HkexEtfTracking",
    "HkexSecuritiesMaster",
    "HkexDerivativeProducts",
    "HkexStockDerivatives",
    "HkexMarketTurnover",
    "HkexMarketStatistics",
)

_GUARDED_COMMANDS = {
    "EQUITY_INSTALLED": ["/quote", "/info", "/search", "/historical"],
    "INDEX_INSTALLED": ["/index_snapshots", "/index_constituents"],
    "DERIVATIVES_INSTALLED": ["/options_chains", "/futures_curve"],
}


def test_key_helper():
    assert _key("EquityQuote", "HkexEquityQuote", True) == "EquityQuote"
    assert _key("EquityQuote", "HkexEquityQuote", False) == "HkexEquityQuote"


def test_fetcher_dict_matches_install_flags():
    fetchers = m.hkex_provider.fetcher_dict
    for flag, pairs in _SIBLING_KEYS.items():
        installed = getattr(m, flag)
        for standard, alias in pairs:
            expected = standard if installed else alias
            unexpected = alias if installed else standard
            assert expected in fetchers, f"{expected} missing for {flag}={installed}"
            assert unexpected not in fetchers


def test_always_hkex_fetchers_registered():
    fetchers = m.hkex_provider.fetcher_dict
    for key in _ALWAYS_HKEX:
        assert key in fetchers


def test_router_guards():
    from openbb_core.app.router import CommandMap

    paths = set(CommandMap(router).map)
    for flag, commands in _GUARDED_COMMANDS.items():
        installed = getattr(m, flag)
        for cmd in commands:
            present = any(p.endswith(cmd) for p in paths)
            assert present is not installed


def test_always_on_commands_present():
    from openbb_core.app.router import CommandMap

    paths = set(CommandMap(router).map)
    for cmd in (
        "/securities_master",
        "/derivative_products",
        "/market_statistics",
        "/etf_holdings",
        "/futures_instruments",
    ):
        assert any(p.endswith(cmd) for p in paths)


def test_widget_id_remap_all_installed():
    from openbb_hkex.utils.apps import widget_id_remap

    remap = widget_id_remap({"equity": True, "index": True, "derivatives": True})
    assert remap["hkex_quote_hkex_obb"] == "equity_price_quote_hkex_obb"
    assert remap["hkex_info_hkex_obb"] == "equity_profile_hkex_obb"
    assert remap["hkex_search_hkex_obb"] == "equity_search_hkex_obb"
    assert remap["hkex_historical_hkex_obb"] == "equity_price_historical_hkex_obb"
    assert remap["hkex_index_snapshots_hkex_obb"] == "index_snapshots_hkex_obb"
    assert remap["hkex_index_constituents_hkex_obb"] == "index_constituents_hkex_obb"
    assert (
        remap["hkex_options_chains_hkex_obb"] == "derivatives_options_chains_hkex_obb"
    )
    assert remap["hkex_futures_curve_hkex_obb"] == "derivatives_futures_curve_hkex_obb"


def test_widget_id_remap_partial_install():
    from openbb_hkex.utils.apps import widget_id_remap

    remap = widget_id_remap({"equity": True, "index": False, "derivatives": False})
    assert "hkex_quote_hkex_obb" in remap
    assert "hkex_index_snapshots_hkex_obb" not in remap
    assert "hkex_options_chains_hkex_obb" not in remap


def test_widget_id_remap_none_installed():
    from openbb_hkex.utils.apps import widget_id_remap

    assert (
        widget_id_remap({"equity": False, "index": False, "derivatives": False}) == {}
    )


def test_build_hkex_apps_matches_install_state():
    from openbb_hkex.utils.apps import _installed, build_hkex_apps, widget_id_remap

    apps = build_hkex_apps()
    remap = widget_id_remap(_installed())
    ids = {
        w.get("i")
        for a in apps
        for t in (a.get("tabs") or {}).values()
        for w in (t.get("layout") or [])
    }
    assert not (set(remap) & ids)
    if not remap:
        assert "hkex_quote_hkex_obb" in ids
