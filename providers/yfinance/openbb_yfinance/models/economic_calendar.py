"""Yahoo Finance Economic Calendar Model."""

from typing import Any

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.economic_calendar import (
    EconomicCalendarData,
    EconomicCalendarQueryParams,
)
from pydantic import Field


class YFinanceEconomicCalendarQueryParams(EconomicCalendarQueryParams):
    """YFinance Economic Calendar Query.

    Source: https://finance.yahoo.com/calendar/economic
    """


class YFinanceEconomicCalendarData(EconomicCalendarData):
    """YFinance Economic Calendar Data."""

    reference_period: str | None = Field(
        default=None, description="The reference period the release is for."
    )


class YFinanceEconomicCalendarFetcher(
    Fetcher[YFinanceEconomicCalendarQueryParams, list[YFinanceEconomicCalendarData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(
        params: dict[str, Any],
    ) -> YFinanceEconomicCalendarQueryParams:
        """Transform the query."""
        return YFinanceEconomicCalendarQueryParams(**params)

    @staticmethod
    def extract_data(
        query: YFinanceEconomicCalendarQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Return the raw data from the Yahoo Finance endpoint."""
        from openbb_core.provider.utils.errors import EmptyDataError
        from yfinance import Calendars

        df = Calendars(
            start=query.start_date, end=query.end_date
        ).get_economic_events_calendar()
        if df is None or df.empty:
            raise EmptyDataError()
        return df.to_dict("records")

    @staticmethod
    def transform_data(
        query: YFinanceEconomicCalendarQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceEconomicCalendarData]:
        """Transform the data."""
        from pandas import isna, to_datetime

        def _val(value: Any) -> Any:
            if value is None or (not isinstance(value, str) and isna(value)):
                return None
            return value

        results: list[YFinanceEconomicCalendarData] = []
        for row in data:
            event_time = _val(row.get("Event Time"))
            results.append(
                YFinanceEconomicCalendarData.model_validate(
                    {
                        "date": to_datetime(event_time)
                        if event_time is not None
                        else None,
                        "country": _val(row.get("Region")),
                        "actual": _val(row.get("Actual")),
                        "consensus": _val(row.get("Expected")),
                        "previous": _val(row.get("Last")),
                        "revised": _val(row.get("Revised")),
                        "reference_period": _val(row.get("For")),
                        "source": "Yahoo Finance",
                    }
                )
            )
        return results
