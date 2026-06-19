"""Yahoo Finance Company Calendar Model."""

from datetime import date as dateType
from typing import Any

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from openbb_core.provider.utils.descriptions import QUERY_DESCRIPTIONS
from pydantic import Field, field_validator


class YFinanceCompanyCalendarQueryParams(QueryParams):
    """YFinance Company Calendar Query."""

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    symbol: str = Field(description=QUERY_DESCRIPTIONS.get("symbol", ""))

    @field_validator("symbol", mode="before", check_fields=False)
    @classmethod
    def _to_upper(cls, v):
        """Convert symbol to uppercase."""
        return v.upper() if isinstance(v, str) else ",".join(v).upper()


class YFinanceCompanyCalendarData(Data):
    """YFinance Company Calendar Data."""

    symbol: str = Field(description=QUERY_DESCRIPTIONS.get("symbol", ""))
    earnings_date: dateType | None = Field(
        default=None, description="The next earnings report date."
    )
    ex_dividend_date: dateType | None = Field(
        default=None, description="The next ex-dividend date."
    )
    dividend_date: dateType | None = Field(
        default=None, description="The next dividend payment date."
    )
    earnings_high: float | None = Field(
        default=None, description="The high end of the EPS estimate."
    )
    earnings_low: float | None = Field(
        default=None, description="The low end of the EPS estimate."
    )
    earnings_average: float | None = Field(
        default=None, description="The average EPS estimate."
    )
    revenue_high: float | None = Field(
        default=None, description="The high end of the revenue estimate."
    )
    revenue_low: float | None = Field(
        default=None, description="The low end of the revenue estimate."
    )
    revenue_average: float | None = Field(
        default=None, description="The average revenue estimate."
    )


class YFinanceCompanyCalendarFetcher(
    Fetcher[YFinanceCompanyCalendarQueryParams, list[YFinanceCompanyCalendarData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(
        params: dict[str, Any],
    ) -> YFinanceCompanyCalendarQueryParams:
        """Transform the query."""
        return YFinanceCompanyCalendarQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceCompanyCalendarQueryParams,
        credentials: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> list[dict]:
        """Return the raw data from the Yahoo Finance endpoint."""
        import asyncio
        from warnings import warn

        from openbb_core.provider.utils.errors import EmptyDataError

        from yfinance import Ticker

        symbols = [s.strip() for s in query.symbol.split(",") if s.strip()]
        results: list[dict] = []

        def _earnings_date(value: Any) -> Any:
            if isinstance(value, list):
                return value[0] if value else None
            return value

        def _fetch(symbol: str) -> dict | None:
            cal = Ticker(symbol).calendar or {}
            if not cal:
                return None
            return {
                "symbol": symbol,
                "earnings_date": _earnings_date(cal.get("Earnings Date")),
                "ex_dividend_date": cal.get("Ex-Dividend Date"),
                "dividend_date": cal.get("Dividend Date"),
                "earnings_high": cal.get("Earnings High"),
                "earnings_low": cal.get("Earnings Low"),
                "earnings_average": cal.get("Earnings Average"),
                "revenue_high": cal.get("Revenue High"),
                "revenue_low": cal.get("Revenue Low"),
                "revenue_average": cal.get("Revenue Average"),
            }

        async def _get_one(symbol: str) -> None:
            try:
                record = await asyncio.to_thread(_fetch, symbol)
            except Exception as e:  # noqa: BLE001
                warn(f"Error getting calendar for {symbol}: {e}")
                return
            if record:
                results.append(record)

        await asyncio.gather(*(_get_one(s) for s in symbols))

        if not results:
            raise EmptyDataError("No calendar data was found for the given symbol(s).")

        return results

    @staticmethod
    def transform_data(
        query: YFinanceCompanyCalendarQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceCompanyCalendarData]:
        """Transform the data."""
        return [YFinanceCompanyCalendarData.model_validate(d) for d in data]
