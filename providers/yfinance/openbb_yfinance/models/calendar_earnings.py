"""Yahoo Finance Earnings Calendar Model."""

from typing import Any

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.calendar_earnings import (
    CalendarEarningsData,
    CalendarEarningsQueryParams,
)
from pydantic import Field


class YFinanceCalendarEarningsQueryParams(CalendarEarningsQueryParams):
    """YFinance Earnings Calendar Query.

    Source: https://finance.yahoo.com/calendar/earnings
    """

    limit: int = Field(
        default=100,
        description="The maximum number of results to return. Yahoo caps at 100.",
    )


class YFinanceCalendarEarningsData(CalendarEarningsData):
    """YFinance Earnings Calendar Data."""

    market_cap: float | None = Field(
        default=None, description="Market capitalization of the entity."
    )
    timing: str | None = Field(
        default=None, description="The timing of the earnings event (e.g. BMO, AMC)."
    )
    eps_surprise_percent: float | None = Field(
        default=None,
        description="The earnings surprise, as a normalized percent.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 1},
    )


class YFinanceCalendarEarningsFetcher(
    Fetcher[YFinanceCalendarEarningsQueryParams, list[YFinanceCalendarEarningsData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(
        params: dict[str, Any],
    ) -> YFinanceCalendarEarningsQueryParams:
        """Transform the query."""
        return YFinanceCalendarEarningsQueryParams(**params)

    @staticmethod
    def extract_data(
        query: YFinanceCalendarEarningsQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Return the raw data from the Yahoo Finance endpoint."""
        from openbb_core.provider.utils.errors import EmptyDataError
        from yfinance import Calendars

        df = Calendars().get_earnings_calendar(
            start=query.start_date,
            end=query.end_date,
            limit=query.limit,
        )
        if df is None or df.empty:
            raise EmptyDataError()
        return df.reset_index().to_dict("records")

    @staticmethod
    def transform_data(
        query: YFinanceCalendarEarningsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceCalendarEarningsData]:
        """Transform the data."""
        from pandas import isna, to_datetime

        def _first(row: dict, *keys: str) -> Any:
            for key in keys:
                if (
                    key in row
                    and row[key] not in (None, "")
                    and not (not isinstance(row[key], (str, list)) and isna(row[key]))
                ):
                    return row[key]
            return None

        results: list[YFinanceCalendarEarningsData] = []
        for row in data:
            symbol = _first(row, "Symbol", "symbol", "ticker", "index")
            report = _first(row, "Event Start Date", "Earnings Date")
            if not symbol or report is None:
                continue
            results.append(
                YFinanceCalendarEarningsData.model_validate(
                    {
                        "report_date": to_datetime(report).date(),
                        "symbol": str(symbol).upper(),
                        "name": _first(row, "Company", "Company Name"),
                        "eps_previous": _first(row, "Reported EPS"),
                        "eps_consensus": _first(row, "EPS Estimate"),
                        "market_cap": _first(row, "Marketcap", "Market Cap (Intraday)"),
                        "timing": _first(row, "Timing"),
                        "eps_surprise_percent": _first(
                            row, "Surprise(%)", "Surprise (%)"
                        ),
                    }
                )
            )
        if not results:
            from openbb_core.provider.utils.errors import EmptyDataError

            raise EmptyDataError("No earnings calendar data with symbols was found.")
        return results
