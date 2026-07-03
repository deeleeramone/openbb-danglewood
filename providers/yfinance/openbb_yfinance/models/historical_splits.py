"""YFinance Historical Splits Model."""

from typing import Any

from openbb_core.app.model.abstract.error import OpenBBError
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.historical_splits import (
    HistoricalSplitsData,
    HistoricalSplitsQueryParams,
)


class YFinanceHistoricalSplitsQueryParams(HistoricalSplitsQueryParams):
    """YFinance Historical Splits Query."""


class YFinanceHistoricalSplitsData(HistoricalSplitsData):
    """YFinance Historical Splits Data."""


class YFinanceHistoricalSplitsFetcher(
    Fetcher[YFinanceHistoricalSplitsQueryParams, list[YFinanceHistoricalSplitsData]]
):
    """YFinance Historical Splits Fetcher."""

    @staticmethod
    def transform_query(
        params: dict[str, Any],
    ) -> YFinanceHistoricalSplitsQueryParams:
        """Transform the query."""
        return YFinanceHistoricalSplitsQueryParams(**params)

    @staticmethod
    def extract_data(
        query: YFinanceHistoricalSplitsQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the raw data from YFinance."""
        from yfinance import Ticker

        try:
            splits = Ticker(query.symbol).get_splits()
            if splits is None or splits.empty:
                raise OpenBBError(f"No split data found for {query.symbol}")
        except OpenBBError:
            raise
        except Exception as e:
            raise OpenBBError(f"Error getting data for {query.symbol}: {e}") from e

        splits = splits.reset_index()
        splits.columns = ["date", "ratio"]
        splits["date"] = splits.date.apply(lambda x: x.date()).astype(str)
        return splits.to_dict("records")

    @staticmethod
    def transform_data(
        query: YFinanceHistoricalSplitsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceHistoricalSplitsData]:
        """Transform the data.

        Yahoo reports each split as a single ratio (e.g. ``7.0`` for a 7:1
        forward split, ``0.125`` for a 1:8 reverse). Recover numerator and
        denominator from it.
        """
        from fractions import Fraction

        results: list[YFinanceHistoricalSplitsData] = []
        for row in data:
            ratio = row.get("ratio")
            if not ratio:
                continue
            frac = Fraction(float(ratio)).limit_denominator(1000)
            numerator, denominator = frac.numerator, frac.denominator
            results.append(
                YFinanceHistoricalSplitsData.model_validate(
                    {
                        "date": row["date"],
                        "numerator": float(numerator),
                        "denominator": float(denominator),
                        "split_ratio": f"{numerator}:{denominator}",
                    }
                )
            )
        return results
