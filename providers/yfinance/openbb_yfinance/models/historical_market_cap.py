"""YFinance Historical Market Cap Model."""

from typing import Any

from openbb_core.app.model.abstract.error import OpenBBError
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.historical_market_cap import (
    HistoricalMarketCapData,
    HistoricalMarketCapQueryParams,
)


class YFinanceHistoricalMarketCapQueryParams(HistoricalMarketCapQueryParams):
    """YFinance Historical Market Cap Query."""


class YFinanceHistoricalMarketCapData(HistoricalMarketCapData):
    """YFinance Historical Market Cap Data."""


class YFinanceHistoricalMarketCapFetcher(
    Fetcher[
        YFinanceHistoricalMarketCapQueryParams,
        list[YFinanceHistoricalMarketCapData],
    ]
):
    """YFinance Historical Market Cap Fetcher.

    Yahoo has no market-cap time series, so it is reconstructed from the daily
    (unadjusted) close and the reported shares-outstanding series, which already
    step up/down across splits — their product is the historical market cap.
    """

    @staticmethod
    def transform_query(
        params: dict[str, Any],
    ) -> YFinanceHistoricalMarketCapQueryParams:
        """Transform the query."""
        return YFinanceHistoricalMarketCapQueryParams(**params)

    @staticmethod
    def extract_data(
        query: YFinanceHistoricalMarketCapQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the raw data from YFinance."""
        from datetime import (
            date as dateType,
            timedelta,
        )

        from pandas import to_datetime
        from yfinance import Ticker

        end = query.end_date or dateType.today()
        start = query.start_date or (end - timedelta(days=365))
        ticker = Ticker(query.symbol)

        try:
            prices = ticker.history(
                start=start.strftime("%Y-%m-%d"),
                end=(end + timedelta(days=1)).strftime("%Y-%m-%d"),
                auto_adjust=False,
            )
        except Exception as e:
            raise OpenBBError(f"Error getting data for {query.symbol}: {e}") from e
        if prices is None or prices.empty or "Close" not in prices:
            raise OpenBBError(f"No price data found for {query.symbol}")

        close = prices["Close"].copy()
        close.index = to_datetime(close.index).tz_localize(None).normalize()

        # Shares outstanding — fetch with a leading buffer so the forward-fill
        # has a value for the earliest price dates.
        shares = ticker.get_shares_full(
            start=(start - timedelta(days=550)).strftime("%Y-%m-%d"),
            end=(end + timedelta(days=1)).strftime("%Y-%m-%d"),
        )
        if shares is not None and len(shares) > 0:
            shares.index = to_datetime(shares.index).tz_localize(None).normalize()
            shares = shares[~shares.index.duplicated(keep="last")].sort_index()
            aligned = shares.reindex(close.index, method="ffill")
        else:
            # Fall back to a single current shares count when no series exists.
            info = ticker.get_info() or {}
            outstanding = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
            if not outstanding:
                raise OpenBBError(
                    f"No shares outstanding data found for {query.symbol}"
                )
            aligned = close.copy()
            aligned[:] = float(outstanding)

        market_cap = (close * aligned).dropna()
        if market_cap.empty:
            raise OpenBBError(f"No market cap data found for {query.symbol}")

        symbol = query.symbol.upper()
        return [
            {"date": idx.date().isoformat(), "symbol": symbol, "market_cap": float(val)}
            for idx, val in market_cap.items()
        ]

    @staticmethod
    def transform_data(
        query: YFinanceHistoricalMarketCapQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceHistoricalMarketCapData]:
        """Transform the data."""
        return [YFinanceHistoricalMarketCapData.model_validate(d) for d in data]
