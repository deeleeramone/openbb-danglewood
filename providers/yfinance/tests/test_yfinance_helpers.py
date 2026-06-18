"""Test yfinance helpers."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from openbb_yfinance.utils.helpers import (
    df_transform_numbers,
    get_custom_screener,
    get_defined_screener,
    get_futures_data,
    get_futures_symbols,
    yf_download,
)


def test_get_futures_data():
    """The bundled futures reference CSV loads with its real schema and rows."""
    df = get_futures_data()
    assert not df.empty
    assert list(df.columns) == ["Ticker", "Description", "Exchange", "Category"]
    assert len(df) > 150
    assert df["Ticker"].notna().all()
    assert df["Exchange"].notna().all()


def test_df_transform_numbers():
    """Test df_transform_numbers."""
    data = pd.DataFrame(
        {"Value": ["1M", "2.5B", "3T"], "% Change": ["1%", "-2%", "3.5%"]}
    )
    transformed = df_transform_numbers(data, ["Value", "% Change"])
    assert transformed["Value"].equals(pd.Series([1e6, 2.5e9, 3e12]))
    assert transformed["% Change"].equals(pd.Series([1 / 100, -2 / 100, 3.5 / 100]))


@pytest.mark.asyncio
async def test_get_custom_screener_no_session():
    """Test that get_custom_screener does not pass session to yf.screen."""
    with patch("yfinance.screen") as mock_screen:
        mock_screen.return_value = {
            "quotes": [
                {
                    "symbol": "AAPL",
                    "exchangeTimezoneName": "America/New_York",
                    "regularMarketTime": 1700000000,
                    "regularMarketChange": 1.23,
                    "regularMarketVolume": 1000,
                }
            ],
            "total": 1,
        }
        body = {
            "quoteType": "EQUITY",
            "query": {
                "operator": "and",
                "operands": [
                    {"operator": "gt", "operands": ["intradaymarketcap", 1]},
                ],
            },
        }

        await get_custom_screener(body, limit=1)

        assert mock_screen.called
        for call in mock_screen.call_args_list:
            call_kwargs = call[1] if len(call) > 1 and call[1] else {}
            assert "session" not in call_kwargs, (
                "yf.screen should not be called with session parameter"
            )


@pytest.mark.asyncio
async def test_get_defined_screener_no_session():
    """Test that get_defined_screener does not pass session to yf.screen."""
    with patch("yfinance.screen") as mock_screen:
        mock_screen.return_value = {
            "quotes": [
                {
                    "symbol": "AAPL",
                    "exchangeTimezoneName": "America/New_York",
                    "regularMarketTime": 1700000000,
                    "regularMarketChange": 1.23,
                    "regularMarketVolume": 1000,
                }
            ],
            "total": 1,
        }

        await get_defined_screener("day_gainers", limit=1)

        assert mock_screen.called
        for call in mock_screen.call_args_list:
            call_kwargs = call[1] if len(call) > 1 and call[1] else {}
            assert "session" not in call_kwargs, (
                "yf.screen should not be called with session parameter"
            )


def test_get_futures_symbols_no_session():
    """Test that get_futures_symbols uses Ticker without a session."""
    with patch("yfinance.Ticker") as mock_ticker:
        mock_instance = MagicMock()
        mock_instance._quote._fetch.return_value = {
            "quoteSummary": {
                "result": [{"futuresChain": {"futures": ["ESM26.CME", "ESU26.CME"]}}]
            }
        }
        mock_ticker.return_value = mock_instance

        result = get_futures_symbols("ES")

        assert result == ["ESM26.CME", "ESU26.CME"]
        assert mock_ticker.called
        for call in mock_ticker.call_args_list:
            call_kwargs = call[1] if len(call) > 1 and call[1] else {}
            assert "session" not in call_kwargs, (
                "Ticker should not be called with session parameter"
            )


def test_yf_download_no_session():
    """Test that yf_download does not pass session to yf.download."""
    with patch("yfinance.download") as mock_download:
        columns = pd.MultiIndex.from_tuples(
            [
                ("AAPL", "Open"),
                ("AAPL", "High"),
                ("AAPL", "Low"),
                ("AAPL", "Close"),
                ("AAPL", "Adj Close"),
            ]
        )
        idx = pd.to_datetime(["2023-01-03"])
        idx.name = "Date"
        mock_data = pd.DataFrame([[100, 110, 90, 105, 105]], columns=columns, index=idx)
        mock_download.return_value = mock_data

        yf_download("AAPL", start_date="2023-01-01", end_date="2023-01-10")

        assert mock_download.called
        for call in mock_download.call_args_list:
            call_kwargs = call[1] if len(call) > 1 and call[1] else {}
            assert "session" not in call_kwargs, (
                "yf.download should not be called with session parameter"
            )
