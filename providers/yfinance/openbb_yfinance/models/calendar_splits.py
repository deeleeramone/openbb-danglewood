"""Yahoo Finance Splits Calendar Model."""

from typing import Any

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.calendar_splits import (
    CalendarSplitsData,
    CalendarSplitsQueryParams,
)
from pydantic import Field


class YFinanceCalendarSplitsQueryParams(CalendarSplitsQueryParams):
    """YFinance Splits Calendar Query.

    Source: https://finance.yahoo.com/calendar/splits
    """


class YFinanceCalendarSplitsData(CalendarSplitsData):
    """YFinance Splits Calendar Data."""

    symbol: str | None = Field(default=None, description="The ticker symbol.")
    name: str | None = Field(default=None, description="The name of the company.")
    optionable: bool | None = Field(
        default=None, description="Whether the company has options."
    )


class YFinanceCalendarSplitsFetcher(
    Fetcher[YFinanceCalendarSplitsQueryParams, list[YFinanceCalendarSplitsData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> YFinanceCalendarSplitsQueryParams:
        """Transform the query."""
        return YFinanceCalendarSplitsQueryParams(**params)

    @staticmethod
    def extract_data(
        query: YFinanceCalendarSplitsQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Return the raw data from the Yahoo Finance endpoint."""
        from openbb_core.provider.utils.errors import EmptyDataError

        from yfinance import Calendars

        df = Calendars(start=query.start_date, end=query.end_date).get_splits_calendar()
        if df is None or df.empty:
            raise EmptyDataError()
        return df.to_dict("records")

    @staticmethod
    def transform_data(
        query: YFinanceCalendarSplitsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceCalendarSplitsData]:
        """Transform the data."""
        from pandas import isna, to_datetime

        def _val(value: Any) -> Any:
            if value is None or (not isinstance(value, str) and isna(value)):
                return None
            return value

        results: list[YFinanceCalendarSplitsData] = []
        for row in data:
            date = _val(row.get("Payable On"))
            numerator = _val(row.get("Share Worth"))
            denominator = _val(row.get("Old Share Worth"))
            if date is None or numerator is None or denominator is None:
                continue
            results.append(
                YFinanceCalendarSplitsData.model_validate(
                    {
                        "date": to_datetime(date).date(),
                        "symbol": _val(row.get("Symbol")),
                        "name": _val(row.get("Company")),
                        "numerator": float(numerator),
                        "denominator": float(denominator),
                        "optionable": _val(row.get("Optionable")),
                    }
                )
            )
        return results
