"""YFinance Historical Dividends Model."""

from typing import Any

from openbb_core.app.model.abstract.error import OpenBBError
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.historical_dividends import (
    HistoricalDividendsData,
    HistoricalDividendsQueryParams,
)


class YFinanceHistoricalDividendsQueryParams(HistoricalDividendsQueryParams):
    """YFinance Historical Dividends Query."""


class YFinanceHistoricalDividendsData(HistoricalDividendsData):
    """YFinance Historical Dividends Data. All data is split-adjusted."""

    __alias_dict__ = {
        "ex_dividend_date": "date",
        "amount": "Dividends",
    }


class YFinanceHistoricalDividendsFetcher(
    Fetcher[
        YFinanceHistoricalDividendsQueryParams, list[YFinanceHistoricalDividendsData]
    ]
):
    """YFinance Historical Dividends Fetcher."""

    @staticmethod
    def transform_query(
        params: dict[str, Any],
    ) -> YFinanceHistoricalDividendsQueryParams:
        """Transform the query."""
        return YFinanceHistoricalDividendsQueryParams(**params)

    @staticmethod
    def extract_data(
        query: YFinanceHistoricalDividendsQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the raw data from YFinance."""
        from yfinance import Ticker

        try:
            ticker = Ticker(query.symbol).get_dividends()
            if isinstance(ticker, list) and not ticker or ticker.empty:
                raise OpenBBError(f"No dividend data found for {query.symbol}")
        except Exception as e:
            raise OpenBBError(f"Error getting data for {query.symbol}: {e}") from e

        if query.start_date is not None:
            ticker = ticker[
                ticker.index.astype(str) >= query.start_date.strftime("%Y-%m-%d")
            ]

        if query.end_date is not None:
            ticker = ticker[
                ticker.index.astype(str) <= query.end_date.strftime("%Y-%m-%d")
            ]

        ticker = ticker.reset_index().rename(columns={"Date": "date"})
        ticker["date"] = ticker.date.apply(lambda x: x.date()).astype(str)
        dividends = ticker.to_dict("records")

        return dividends

    @staticmethod
    def transform_data(
        query: YFinanceHistoricalDividendsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceHistoricalDividendsData]:
        """Transform the data."""
        return [YFinanceHistoricalDividendsData.model_validate(d) for d in data]
