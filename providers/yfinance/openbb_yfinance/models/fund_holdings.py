"""Yahoo Finance Fund Holdings Model."""

from typing import Any

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field, field_validator


class YFinanceFundHoldingsQueryParams(QueryParams):
    """YFinance Fund Holdings Query."""

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    symbol: str = Field(description="The fund or ETF ticker symbol.")

    @field_validator("symbol", mode="before", check_fields=False)
    @classmethod
    def _to_upper(cls, v):
        """Convert symbol to uppercase."""
        return v.upper() if isinstance(v, str) else ",".join(v).upper()


class YFinanceFundHoldingsData(Data):
    """YFinance Fund Holdings Data."""

    symbol: str = Field(description="The holding's ticker symbol.")
    name: str | None = Field(default=None, description="The name of the holding.")
    weight: float | None = Field(
        default=None,
        description="The weight of the holding in the fund.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    fund: str | None = Field(
        default=None, description="The parent fund or ETF ticker symbol."
    )


class YFinanceFundHoldingsFetcher(
    Fetcher[YFinanceFundHoldingsQueryParams, list[YFinanceFundHoldingsData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> YFinanceFundHoldingsQueryParams:
        """Transform query params."""
        return YFinanceFundHoldingsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceFundHoldingsQueryParams,
        credentials: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the raw data from Yahoo Finance."""
        import asyncio
        from warnings import warn

        from openbb_core.provider.utils.errors import EmptyDataError

        from openbb_yfinance.utils.funds_helpers import get_funds_data

        symbols = [s.strip() for s in query.symbol.split(",") if s.strip()]
        results: list[dict] = []

        def _fetch(symbol: str) -> list[dict]:
            """Fetch one fund's top holdings."""
            funds = get_funds_data(symbol)
            top = funds.top_holdings
            rows: list[dict] = []
            if top is None or top.empty:
                return rows
            for idx, row in top.iterrows():
                rows.append(
                    {
                        "symbol": str(idx),
                        "name": row.get("Name"),
                        "weight": row.get("Holding Percent"),
                        "fund": symbol,
                    }
                )
            return rows

        async def _get_one(symbol: str) -> None:
            try:
                rows = await asyncio.to_thread(_fetch, symbol)
            except Exception as e:  # noqa: BLE001
                warn(f"Error getting fund holdings for {symbol}: {e}")
                return
            results.extend(rows)

        await asyncio.gather(*(_get_one(s) for s in symbols))

        if not results:
            raise EmptyDataError("No holdings were found for the given symbol(s).")

        return results

    @staticmethod
    def transform_data(
        query: YFinanceFundHoldingsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceFundHoldingsData]:
        """Transform the data."""
        return [YFinanceFundHoldingsData.model_validate(d) for d in data]
