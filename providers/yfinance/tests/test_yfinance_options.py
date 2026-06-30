"""Tests for the yfinance options analysis views (builders, data handler, router)."""

import asyncio
import json
import pathlib

import pytest
from openbb_core.app.model.abstract.error import OpenBBError
from pandas import DataFrame

from openbb_yfinance.models import options_chains
from openbb_yfinance.models.options_chains import YFinanceOptionsChainsData
from openbb_yfinance.routers import derivatives
from openbb_yfinance.utils.options import data_handler
from openbb_yfinance.utils.options.create_smile import create_smile
from openbb_yfinance.utils.options.create_stats import create_stats
from openbb_yfinance.utils.options.create_surface import create_surface
from openbb_yfinance.utils.options.create_term_structure import create_term_structure

_DATA = pathlib.Path(__file__).parent / "data" / "options_aapl.json"


def _build_data() -> YFinanceOptionsChainsData:
    records = json.loads(_DATA.read_text())
    return YFinanceOptionsChainsData.model_validate(DataFrame(records).to_dict("list"))


@pytest.fixture
def options_data() -> YFinanceOptionsChainsData:
    return _build_data()


@pytest.fixture
def patched_cache(options_data, monkeypatch):
    """Serve the fixture chain through the fetcher and reset the symbol cache.

    Symbol ``ZZZZ`` raises, standing in for a ticker with no options.
    """

    async def _fetch(params, credentials, **kwargs):
        if params.get("symbol", "").upper() == "ZZZZ":
            raise OpenBBError("no options")
        return options_data

    monkeypatch.setattr(
        options_chains.YFinanceOptionsChainsFetcher, "fetch_data", _fetch
    )
    data_handler.LOADED_SYMBOLS.clear()
    yield
    data_handler.LOADED_SYMBOLS.clear()


# --------------------------------------------------------------------------- #
# data_handler
# --------------------------------------------------------------------------- #


def test_load_symbol_caches(patched_cache):
    first = asyncio.run(data_handler.load_symbol("aapl"))
    assert "AAPL" in data_handler.LOADED_SYMBOLS
    second = asyncio.run(data_handler.load_symbol("AAPL"))
    assert first is second


def test_load_symbol_update_refetches(patched_cache):
    asyncio.run(data_handler.load_symbol("AAPL"))
    assert asyncio.run(data_handler.load_symbol("AAPL", update=True)) is not None


def test_load_symbol_no_options_raises(patched_cache):
    with pytest.raises(OpenBBError):
        asyncio.run(data_handler.load_symbol("ZZZZ"))


def test_load_symbol_empty_result_raises(monkeypatch):
    async def _none(params, credentials, **kwargs):
        return None

    monkeypatch.setattr(
        options_chains.YFinanceOptionsChainsFetcher, "fetch_data", _none
    )
    data_handler.LOADED_SYMBOLS.clear()
    with pytest.raises(OpenBBError):
        asyncio.run(data_handler.load_symbol("AAPL"))


def test_dropdown_helpers(patched_cache):
    assert data_handler.get_expirations("AAPL") == []
    assert data_handler.get_strikes("AAPL") == []
    asyncio.run(data_handler.load_symbol("AAPL"))
    expirations = data_handler.get_expirations("AAPL")
    strikes = data_handler.get_strikes("AAPL")
    assert expirations and expirations[0]["label"] == expirations[0]["value"]
    assert strikes[0] == {"label": "Nearest OTM", "value": None}
    assert any("extraInfo" in s for s in strikes[1:])


# --------------------------------------------------------------------------- #
# create_smile
# --------------------------------------------------------------------------- #


def test_smile_default_single_expiration(options_data):
    out = create_smile(options_data)
    assert out.chart.fig.to_json()
    assert len(out.results) > 0


@pytest.mark.parametrize("otm", [False, True])
@pytest.mark.parametrize("skew", [False, True])
def test_smile_otm_skew(options_data, otm, skew):
    assert create_smile(options_data, otm=otm, skew=skew).chart.fig is not None


def test_smile_multiple_expirations(options_data):
    exps = ",".join(options_data.expirations[:2])
    out = create_smile(options_data, expirations=exps)
    assert out.chart.fig is not None


def test_smile_expirations_as_list(options_data):
    out = create_smile(options_data, expirations=list(options_data.expirations[:1]))
    assert out.chart.fig is not None


def test_smile_too_many_expirations(options_data):
    with pytest.raises(OpenBBError):
        create_smile(options_data, expirations=",".join(options_data.expirations * 3))


def test_smile_requires_iv(options_data, monkeypatch):
    monkeypatch.setattr(type(options_data), "has_iv", property(lambda self: False))
    with pytest.raises(OpenBBError):
        create_smile(options_data)


# --------------------------------------------------------------------------- #
# create_stats
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("by", ["strike", "expiration"])
@pytest.mark.parametrize("metric", ["oi", "volume"])
@pytest.mark.parametrize("unit", ["value", "percent", "pcr"])
def test_stats_matrix(options_data, by, metric, unit):
    out = create_stats(options_data, by=by, metric=metric, unit=unit)
    assert out.chart.fig is not None


def test_stats_by_date(options_data):
    out = create_stats(options_data, date=options_data.expirations[0], by="strike")
    assert out.chart.fig is not None


# --------------------------------------------------------------------------- #
# create_surface
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("option_type", ["otm", "itm", "calls", "puts"])
def test_surface_option_types(options_data, option_type):
    assert create_surface(options_data, option_type=option_type).chart.fig is not None


def test_surface_filters(options_data):
    out = create_surface(
        options_data, dte_range=[0, 120], moneyness=25, oi=True, volume=True
    )
    assert out.chart.fig is not None


def test_surface_requires_iv(options_data, monkeypatch):
    no_iv = options_data.dataframe.drop(columns=["implied_volatility"])
    monkeypatch.setattr(type(options_data), "dataframe", property(lambda self: no_iv))
    with pytest.raises(OpenBBError):
        create_surface(options_data)


# --------------------------------------------------------------------------- #
# create_term_structure
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("metric", ["iv", "price"])
@pytest.mark.parametrize("option_type", ["both", "calls", "puts"])
def test_term_structure_matrix(options_data, metric, option_type):
    out = create_term_structure(options_data, metric=metric, option_type=option_type)
    assert out.chart.fig is not None


def test_term_structure_by_strike(options_data):
    strike = options_data.strikes[len(options_data.strikes) // 2]
    assert create_term_structure(options_data, strike=strike).chart.fig is not None


def test_term_structure_by_moneyness(options_data):
    assert create_term_structure(options_data, moneyness=5).chart.fig is not None


def test_term_structure_requires_iv(options_data, monkeypatch):
    monkeypatch.setattr(type(options_data), "has_iv", property(lambda self: False))
    with pytest.raises(OpenBBError):
        create_term_structure(options_data, metric="iv")


def test_term_structure_skips_unlisted_expiration(options_data, monkeypatch):
    real = list(options_data.expirations)
    monkeypatch.setattr(
        type(options_data),
        "expirations",
        property(lambda self: [*real, "2099-12-31"]),
    )
    assert create_term_structure(options_data).chart.fig is not None


# --------------------------------------------------------------------------- #
# futures commands
# --------------------------------------------------------------------------- #


def test_futures_commands_dispatch(monkeypatch):
    async def _from_query(query):
        return "OBB"

    monkeypatch.setattr(derivatives, "Query", lambda **kwargs: kwargs)
    monkeypatch.setattr(derivatives.OBBject, "from_query", _from_query)
    assert asyncio.run(derivatives.historical(None, None, None, None)) == "OBB"
    assert asyncio.run(derivatives.curve(None, None, None, None)) == "OBB"


# --------------------------------------------------------------------------- #
# options_chains fetcher error paths
# --------------------------------------------------------------------------- #


def test_options_fetcher_no_options(monkeypatch):
    import yfinance

    class _Ticker:
        def __init__(self, *args, **kwargs):
            pass

        @property
        def options(self):
            return []

    monkeypatch.setattr(yfinance, "Ticker", _Ticker)
    with pytest.raises(OpenBBError):
        asyncio.run(
            options_chains.YFinanceOptionsChainsFetcher.fetch_data(
                {"symbol": "AAPL"}, {}
            )
        )


def test_options_fetcher_empty_chains(monkeypatch):
    import yfinance
    from openbb_core.provider.utils.errors import EmptyDataError

    class _Ticker:
        def __init__(self, *args, **kwargs):
            pass

        @property
        def options(self):
            return ["2026-07-01"]

        def option_chain(self, expiration, tz=None):
            cols = [
                "strike",
                "contractSymbol",
                "contractSize",
                "percentChange",
                "volume",
                "openInterest",
            ]
            empty = DataFrame(columns=cols)
            underlying = {
                "regularMarketPrice": 100.0,
                "exchangeTimezoneName": "America/New_York",
            }
            return (empty, empty, underlying)

    monkeypatch.setattr(yfinance, "Ticker", _Ticker)
    with pytest.raises(EmptyDataError):
        asyncio.run(
            options_chains.YFinanceOptionsChainsFetcher.fetch_data(
                {"symbol": "AAPL"}, {}
            )
        )


def test_options_transform_data_empty():
    from openbb_core.provider.utils.errors import EmptyDataError

    query = options_chains.YFinanceOptionsChainsQueryParams(symbol="AAPL")
    with pytest.raises(EmptyDataError):
        options_chains.YFinanceOptionsChainsFetcher.transform_data(query, {})


# --------------------------------------------------------------------------- #
# router — table commands
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("option_type", ["calls", "puts", "both"])
def test_chains_command(patched_cache, option_type):
    out = asyncio.run(derivatives.chains(option_type=option_type, otm_only=True))
    assert len(out.results) > 0


def test_chains_with_expiry(patched_cache):
    data = asyncio.run(data_handler.load_symbol("AAPL"))
    out = asyncio.run(derivatives.chains(expiry=data.expirations[0]))
    assert out.results


def test_straddle_strangle_spreads(patched_cache):
    assert asyncio.run(derivatives.straddle()).results
    assert asyncio.run(derivatives.strangle(moneyness=0)).results
    expected = {
        "call": {"Bull Call Spread", "Bear Call Spread"},
        "put": {"Bull Put Spread", "Bear Put Spread"},
        "both": {
            "Bull Call Spread",
            "Bear Call Spread",
            "Bull Put Spread",
            "Bear Put Spread",
        },
    }
    for spread_type, want in expected.items():
        rows = asyncio.run(derivatives.spreads(spread_type=spread_type)).results
        assert want <= {row.strategy for row in rows}, (spread_type, rows)


def test_get_tickers(patched_cache):
    assert asyncio.run(derivatives.get_tickers(symbol="")) == []
    assert asyncio.run(derivatives.get_tickers(symbol="ZZZZ")) == []
    exps = asyncio.run(derivatives.get_tickers(symbol="AAPL", expiry_list=True))
    strikes = asyncio.run(derivatives.get_tickers(symbol="AAPL", strike_list=True))
    assert exps and strikes
    assert asyncio.run(derivatives.get_tickers(symbol="AAPL")) == []


# --------------------------------------------------------------------------- #
# router — chart endpoints
# --------------------------------------------------------------------------- #


def _is_figure(payload) -> bool:
    return isinstance(payload, dict) and "data" in payload and "layout" in payload


CHART_ENDPOINTS = [
    derivatives.smile_chart,
    derivatives.surface_chart,
    derivatives.stats_chart,
    derivatives.term_structure_chart,
]


@pytest.mark.parametrize("endpoint", CHART_ENDPOINTS)
def test_chart_endpoint_chart_mode(patched_cache, endpoint):
    payload = asyncio.run(endpoint(symbol="AAPL"))
    assert _is_figure(payload)
    assert payload["config"]["scrollZoom"] is True


@pytest.mark.parametrize("endpoint", CHART_ENDPOINTS)
def test_chart_endpoint_raw_mode(patched_cache, endpoint):
    rows = asyncio.run(endpoint(symbol="AAPL", raw=True))
    assert isinstance(rows, list) and rows and isinstance(rows[0], dict)


@pytest.mark.parametrize("endpoint", CHART_ENDPOINTS)
def test_chart_endpoint_no_options(patched_cache, endpoint):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint(symbol="ZZZZ"))
    assert exc.value.status_code == 404
