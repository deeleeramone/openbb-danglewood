"""Yahoo Finance Earnings Estimates Model."""

from typing import Any

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field, field_validator


class YFinanceEarningsEstimatesQueryParams(QueryParams):
    """YFinance Earnings Estimates Query."""

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    symbol: str = Field(description="The ticker symbol.")

    @field_validator("symbol", mode="before", check_fields=False)
    @classmethod
    def _to_upper(cls, v):
        """Convert symbol to uppercase."""
        return v.upper() if isinstance(v, str) else ",".join(v).upper()


class YFinanceEarningsEstimatesData(Data):
    """YFinance Earnings Estimates Data."""

    symbol: str = Field(description="The ticker symbol.")
    period: str = Field(
        description="The estimate period label (e.g. 0q, +1q, 0y, +1y)."
    )
    mean: float | None = Field(default=None, description="Mean estimated EPS.")
    low: float | None = Field(default=None, description="Low estimated EPS.")
    high: float | None = Field(default=None, description="High estimated EPS.")
    number_of_analysts: int | None = Field(
        default=None, description="Number of analysts providing estimates."
    )
    year_ago_eps: float | None = Field(default=None, description="EPS a year ago.")
    growth: float | None = Field(default=None, description="Estimated EPS growth.")
    currency: str | None = Field(
        default=None, description="The currency of the values."
    )


class YFinanceEarningsEstimatesFetcher(
    Fetcher[YFinanceEarningsEstimatesQueryParams, list[YFinanceEarningsEstimatesData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(
        params: dict[str, Any],
    ) -> YFinanceEarningsEstimatesQueryParams:
        """Transform the query."""
        return YFinanceEarningsEstimatesQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceEarningsEstimatesQueryParams,
        credentials: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the earnings estimates from Yahoo Finance."""
        import asyncio
        from warnings import warn

        from openbb_core.provider.utils.errors import EmptyDataError
        from pandas import isna

        from yfinance import Ticker

        symbols = [s.strip() for s in query.symbol.split(",") if s.strip()]
        results: list[dict] = []

        def _clean(v):
            """Convert pandas NaN to None."""
            return None if (not isinstance(v, str) and isna(v)) else v

        def _fetch(symbol: str) -> list[dict]:
            """Parse the earnings_estimate frame for one symbol."""
            estimates = Ticker(symbol).earnings_estimate
            rows: list[dict] = []
            if estimates is None or estimates.empty:
                return rows
            for period, row in estimates.iterrows():
                rows.append(
                    {
                        "symbol": symbol,
                        "period": str(period),
                        "mean": _clean(row.get("avg")),
                        "low": _clean(row.get("low")),
                        "high": _clean(row.get("high")),
                        "number_of_analysts": _clean(row.get("numberOfAnalysts")),
                        "year_ago_eps": _clean(row.get("yearAgoEps")),
                        "growth": _clean(row.get("growth")),
                        "currency": _clean(row.get("currency")),
                    }
                )
            return rows

        async def _get_one(symbol: str) -> None:
            try:
                rows = await asyncio.to_thread(_fetch, symbol)
            except Exception as e:  # noqa: BLE001
                warn(f"Error getting earnings estimates for {symbol}: {e}")
                return
            results.extend(rows)

        await asyncio.gather(*(_get_one(s) for s in symbols))

        if not results:
            raise EmptyDataError(
                "No earnings estimates were found for the given symbol(s)."
            )

        return results

    @staticmethod
    def transform_data(
        query: YFinanceEarningsEstimatesQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceEarningsEstimatesData]:
        """Transform the data."""
        return [YFinanceEarningsEstimatesData.model_validate(d) for d in data]
