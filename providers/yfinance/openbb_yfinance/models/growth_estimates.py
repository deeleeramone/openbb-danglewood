"""Yahoo Finance Growth Estimates Model."""

from typing import Any

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field, field_validator


class YFinanceGrowthEstimatesQueryParams(QueryParams):
    """YFinance Growth Estimates Query."""

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    symbol: str = Field(description="The ticker symbol.")

    @field_validator("symbol", mode="before", check_fields=False)
    @classmethod
    def _to_upper(cls, v):
        """Convert symbol to uppercase."""
        return v.upper() if isinstance(v, str) else ",".join(v).upper()


class YFinanceGrowthEstimatesData(Data):
    """YFinance Growth Estimates Data."""

    symbol: str = Field(description="The ticker symbol.")
    period: str = Field(description="The estimate period (e.g. 0q, +1q, 0y, +1y, LTG).")
    stock_trend: float | None = Field(
        default=None, description="The growth estimate trend for the stock."
    )
    index_trend: float | None = Field(
        default=None, description="The growth estimate trend for the index."
    )


class YFinanceGrowthEstimatesFetcher(
    Fetcher[YFinanceGrowthEstimatesQueryParams, list[YFinanceGrowthEstimatesData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> YFinanceGrowthEstimatesQueryParams:
        """Transform the query."""
        return YFinanceGrowthEstimatesQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceGrowthEstimatesQueryParams,
        credentials: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the raw data from Yahoo Finance."""
        import asyncio
        from warnings import warn

        from openbb_core.provider.utils.errors import EmptyDataError
        from pandas import isna

        from yfinance import Ticker

        symbols = [s.strip() for s in (query.symbol or "").split(",") if s.strip()]
        results: list[dict] = []

        def _clean(value):
            """Convert pandas NaN to None."""
            return None if (not isinstance(value, str) and isna(value)) else value

        def _fetch(symbol: str) -> list[dict]:
            """Parse the growth_estimates DataFrame for one symbol."""
            estimates = Ticker(symbol).growth_estimates
            rows: list[dict] = []
            if estimates is None or estimates.empty:
                return rows
            for period, row in estimates.iterrows():
                rows.append(
                    {
                        "symbol": symbol,
                        "period": str(period),
                        "stock_trend": _clean(row.get("stockTrend")),
                        "index_trend": _clean(row.get("indexTrend")),
                    }
                )
            return rows

        async def _get_one(symbol: str) -> None:
            try:
                rows = await asyncio.to_thread(_fetch, symbol)
            except Exception as e:  # noqa: BLE001
                warn(f"Error getting growth estimates for {symbol}: {e}")
                return
            results.extend(rows)

        await asyncio.gather(*(_get_one(s) for s in symbols))

        if not results:
            raise EmptyDataError(
                "No growth estimates data was found for the given symbol(s)."
            )

        return results

    @staticmethod
    def transform_data(
        query: YFinanceGrowthEstimatesQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceGrowthEstimatesData]:
        """Transform the data."""
        return [YFinanceGrowthEstimatesData.model_validate(d) for d in data]
