"""Yahoo Finance Fund Allocation Model."""

from typing import Any, Literal

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field, field_validator


class YFinanceFundAllocationQueryParams(QueryParams):
    """YFinance Fund Allocation Query."""

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    symbol: str = Field(description="The fund or ETF ticker symbol.")
    breakdown: Literal["all", "asset_class", "sector", "bond_rating"] = Field(
        default="all",
        description="The allocation breakdown to return.",
    )

    @field_validator("symbol", mode="before", check_fields=False)
    @classmethod
    def _to_upper(cls, v):
        """Convert symbol to uppercase."""
        return v.upper() if isinstance(v, str) else ",".join(v).upper()


class YFinanceFundAllocationData(Data):
    """YFinance Fund Allocation Data."""

    symbol: str = Field(description="The fund or ETF ticker symbol.")
    breakdown: str = Field(
        description="The breakdown type (asset_class, sector, or bond_rating)."
    )
    category: str = Field(description="The allocation category name.")
    weight: float | None = Field(
        default=None,
        description="The weight of the category.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )


_ASSET_CLASS_LABELS = {
    "cashPosition": "Cash",
    "stockPosition": "Stock",
    "bondPosition": "Bond",
    "preferredPosition": "Preferred",
    "convertiblePosition": "Convertible",
    "otherPosition": "Other",
}


class YFinanceFundAllocationFetcher(
    Fetcher[YFinanceFundAllocationQueryParams, list[YFinanceFundAllocationData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> YFinanceFundAllocationQueryParams:
        """Transform query params."""
        return YFinanceFundAllocationQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceFundAllocationQueryParams,
        credentials: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the raw data from Yahoo Finance."""
        import asyncio
        from warnings import warn

        from openbb_core.provider.utils.errors import EmptyDataError

        from openbb_yfinance.utils.funds_helpers import get_funds_data

        symbols = [s.strip() for s in query.symbol.split(",") if s.strip()]
        want = query.breakdown
        results: list[dict] = []

        def _fetch(symbol: str) -> list[dict]:
            """Build allocation rows for one fund."""
            funds = get_funds_data(symbol)
            rows: list[dict] = []

            if want in ("all", "asset_class"):
                for key, value in (funds.asset_classes or {}).items():
                    if value is None:
                        continue
                    rows.append(
                        {
                            "symbol": symbol,
                            "breakdown": "asset_class",
                            "category": _ASSET_CLASS_LABELS.get(key, key),
                            "weight": value,
                        }
                    )
            if want in ("all", "sector"):
                for key, value in (funds.sector_weightings or {}).items():
                    if value is None:
                        continue
                    rows.append(
                        {
                            "symbol": symbol,
                            "breakdown": "sector",
                            "category": str(key).replace("_", " ").title(),
                            "weight": value,
                        }
                    )
            if want in ("all", "bond_rating"):
                for key, value in (funds.bond_ratings or {}).items():
                    if value is None:
                        continue
                    rows.append(
                        {
                            "symbol": symbol,
                            "breakdown": "bond_rating",
                            "category": str(key).upper(),
                            "weight": value,
                        }
                    )
            return rows

        async def _get_one(symbol: str) -> None:
            try:
                rows = await asyncio.to_thread(_fetch, symbol)
            except Exception as e:  # noqa: BLE001
                warn(f"Error getting fund allocation for {symbol}: {e}")
                return
            results.extend(rows)

        await asyncio.gather(*(_get_one(s) for s in symbols))

        if not results:
            raise EmptyDataError(
                "No allocation data was found for the given symbol(s)."
            )

        return results

    @staticmethod
    def transform_data(
        query: YFinanceFundAllocationQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceFundAllocationData]:
        """Transform the data."""
        return [YFinanceFundAllocationData.model_validate(d) for d in data]
