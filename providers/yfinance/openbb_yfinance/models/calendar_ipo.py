"""Yahoo Finance IPO Calendar Model."""

from datetime import date as dateType
from typing import Any

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.calendar_ipo import (
    CalendarIpoData,
    CalendarIpoQueryParams,
)
from pydantic import Field


class YFinanceCalendarIpoQueryParams(CalendarIpoQueryParams):
    """YFinance IPO Calendar Query.

    Source: https://finance.yahoo.com/calendar/ipo
    """


class YFinanceCalendarIpoData(CalendarIpoData):
    """YFinance IPO Calendar Data."""

    name: str | None = Field(default=None, description="The name of the company.")
    exchange: str | None = Field(
        default=None, description="The exchange where the company will be listed."
    )
    filing_date: dateType | None = Field(
        default=None, description="The date of the IPO filing."
    )
    price_from: float | None = Field(
        default=None, description="The low end of the expected price range."
    )
    price_to: float | None = Field(
        default=None, description="The high end of the expected price range."
    )
    price: float | None = Field(default=None, description="The offer price.")
    currency: str | None = Field(default=None, description="The currency of the offer.")
    shares: float | None = Field(default=None, description="The number of shares.")
    action: str | None = Field(
        default=None, description="The status of the IPO (e.g. Expected, Priced)."
    )


class YFinanceCalendarIpoFetcher(
    Fetcher[YFinanceCalendarIpoQueryParams, list[YFinanceCalendarIpoData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> YFinanceCalendarIpoQueryParams:
        """Transform the query."""
        return YFinanceCalendarIpoQueryParams(**params)

    @staticmethod
    def extract_data(
        query: YFinanceCalendarIpoQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Return the raw data from the Yahoo Finance endpoint."""
        from openbb_core.provider.utils.errors import EmptyDataError
        from yfinance import Calendars

        df = Calendars(
            start=query.start_date, end=query.end_date
        ).get_ipo_info_calendar()
        if df is None or df.empty:
            raise EmptyDataError()
        return df.to_dict("records")

    @staticmethod
    def transform_data(
        query: YFinanceCalendarIpoQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceCalendarIpoData]:
        """Transform the data."""
        from pandas import isna, to_datetime

        def _val(value: Any) -> Any:
            if value is None or (not isinstance(value, str) and isna(value)):
                return None
            return value

        def _date(value: Any) -> Any:
            value = _val(value)
            return to_datetime(value).date() if value is not None else None

        results: list[YFinanceCalendarIpoData] = []
        for row in data:
            results.append(
                YFinanceCalendarIpoData.model_validate(
                    {
                        "symbol": _val(row.get("Symbol")),
                        "ipo_date": _date(row.get("Date")),
                        "name": _val(row.get("Company")),
                        "exchange": _val(row.get("Exchange")),
                        "filing_date": _date(row.get("Filing Date")),
                        "price_from": _val(row.get("Price From")),
                        "price_to": _val(row.get("Price To")),
                        "price": _val(row.get("Price")),
                        "currency": _val(row.get("Currency")),
                        "shares": _val(row.get("Shares")),
                        "action": _val(row.get("Action")),
                    }
                )
            )
        return results
