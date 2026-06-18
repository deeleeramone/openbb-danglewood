"""Yahoo Finance Fund Performance Model."""

from typing import Any

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field, field_validator


class YFinanceFundPerformanceQueryParams(QueryParams):
    """YFinance Fund Performance Query."""

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    symbol: str = Field(description="The fund or ETF ticker symbol.")

    @field_validator("symbol", mode="before", check_fields=False)
    @classmethod
    def _to_upper(cls, v):
        """Convert symbol to uppercase."""
        return v.upper() if isinstance(v, str) else ",".join(v).upper()


class YFinanceFundPerformanceData(Data):
    """YFinance Fund Performance Data."""

    symbol: str = Field(description="The fund or ETF ticker symbol.")
    measure: str = Field(
        description="The measure: 'trailing_return' or 'annual_return'."
    )
    period: str = Field(
        description="A trailing window (1m, 3m, 6m, ytd, 1y, 3y, 5y, 10y) or a"
        + " calendar year for annual returns."
    )
    cumulative_return: float | None = Field(
        default=None,
        description="Total return over the period.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    annualized_return: float | None = Field(
        default=None,
        description="Annualized return over the period, for trailing windows of"
        + " one year or more.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )


class YFinanceFundPerformanceFetcher(
    Fetcher[YFinanceFundPerformanceQueryParams, list[YFinanceFundPerformanceData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> YFinanceFundPerformanceQueryParams:
        """Transform query params."""
        return YFinanceFundPerformanceQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceFundPerformanceQueryParams,
        credentials: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the data."""
        import asyncio
        from warnings import warn

        from openbb_core.provider.utils.errors import EmptyDataError

        from openbb_yfinance.utils.funds_helpers import compute_fund_performance

        symbols = [s.strip() for s in query.symbol.split(",") if s.strip()]
        results: list[dict] = []

        async def _get_one(symbol: str) -> None:
            try:
                rows = await asyncio.to_thread(compute_fund_performance, symbol)
            except Exception as e:  # noqa: BLE001
                warn(f"Error getting fund performance for {symbol}: {e}")
                return
            results.extend(rows)

        await asyncio.gather(*(_get_one(s) for s in symbols))

        if not results:
            raise EmptyDataError(
                "No performance data was found for the given symbol(s)."
            )

        return results

    @staticmethod
    def transform_data(
        query: YFinanceFundPerformanceQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceFundPerformanceData]:
        """Transform the data."""
        return [YFinanceFundPerformanceData.model_validate(d) for d in data]
