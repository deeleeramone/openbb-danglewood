"""Yahoo Finance Revenue Estimates Model."""

from typing import Any

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field, field_validator


class YFinanceRevenueEstimatesQueryParams(QueryParams):
    """YFinance Revenue Estimates Query."""

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    symbol: str = Field(description="The ticker symbol.")

    @field_validator("symbol", mode="before", check_fields=False)
    @classmethod
    def _to_upper(cls, v):
        """Convert symbol to uppercase."""
        return v.upper() if isinstance(v, str) else ",".join(v).upper()


class YFinanceRevenueEstimatesData(Data):
    """YFinance Revenue Estimates Data."""

    symbol: str = Field(description="The ticker symbol.")
    period: str = Field(description="The estimate period (e.g. 0q, +1q, 0y, +1y).")
    mean: float | None = Field(default=None, description="The mean revenue estimate.")
    low: float | None = Field(default=None, description="The low revenue estimate.")
    high: float | None = Field(default=None, description="The high revenue estimate.")
    number_of_analysts: int | None = Field(
        default=None, description="The number of analysts providing estimates."
    )
    year_ago_revenue: float | None = Field(
        default=None, description="The revenue from the year-ago period."
    )
    growth: float | None = Field(
        default=None, description="The estimated revenue growth."
    )
    currency: str | None = Field(
        default=None, description="The currency of the values."
    )


class YFinanceRevenueEstimatesFetcher(
    Fetcher[YFinanceRevenueEstimatesQueryParams, list[YFinanceRevenueEstimatesData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(
        params: dict[str, Any],
    ) -> YFinanceRevenueEstimatesQueryParams:
        """Transform the query."""
        return YFinanceRevenueEstimatesQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceRevenueEstimatesQueryParams,
        credentials: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the raw data from Yahoo Finance."""
        import asyncio
        from warnings import warn

        from openbb_core.provider.utils.errors import EmptyDataError
        from pandas import isna

        from yfinance import Ticker

        symbols = [s.strip() for s in query.symbol.split(",") if s.strip()]
        results: list[dict] = []

        def _clean(value):
            """Convert pandas NaN to None."""
            return None if (not isinstance(value, str) and isna(value)) else value

        def _fetch(symbol: str) -> list[dict]:
            """Parse the revenue_estimate frame for one symbol."""
            estimates = Ticker(symbol).revenue_estimate
            if estimates is None or estimates.empty:
                return []
            rows: list[dict] = []
            for period, row in estimates.iterrows():
                rows.append(
                    {
                        "symbol": symbol,
                        "period": str(period),
                        "mean": _clean(row.get("avg")),
                        "low": _clean(row.get("low")),
                        "high": _clean(row.get("high")),
                        "number_of_analysts": _clean(row.get("numberOfAnalysts")),
                        "year_ago_revenue": _clean(row.get("yearAgoRevenue")),
                        "growth": _clean(row.get("growth")),
                        "currency": _clean(row.get("currency")),
                    }
                )
            return rows

        async def _get_one(symbol: str) -> None:
            try:
                rows = await asyncio.to_thread(_fetch, symbol)
            except Exception as e:  # noqa: BLE001
                warn(f"Error getting revenue estimates for {symbol}: {e}")
                return
            results.extend(rows)

        await asyncio.gather(*(_get_one(s) for s in symbols))

        if not results:
            raise EmptyDataError(
                "No revenue estimates were found for the given symbol(s)."
            )

        return results

    @staticmethod
    def transform_data(
        query: YFinanceRevenueEstimatesQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceRevenueEstimatesData]:
        """Transform the data."""
        return [YFinanceRevenueEstimatesData.model_validate(d) for d in data]
