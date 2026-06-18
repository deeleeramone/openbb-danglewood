"""Yahoo Finance Sector Overview Model."""

from typing import Any

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field, field_validator

from openbb_yfinance.utils.sectors import SECTOR_OPTIONS_WITH_MARKET, sector_keys


class YFinanceSectorOverviewQueryParams(QueryParams):
    """YFinance Sector Overview Query."""

    sector: str | None = Field(
        default=None,
        description="The Yahoo sector key. Leave as 'Market (All Sectors)' for the"
        + " market-level breakdown across every sector.",
        json_schema_extra={
            "x-widget_config": {
                "options": SECTOR_OPTIONS_WITH_MARKET,
                "value": "",
            }
        },
    )

    @field_validator("sector", mode="before", check_fields=False)
    @classmethod
    def _to_lower(cls, v):
        """Lowercase the sector key(s)."""
        if v is None:
            return None
        return v.lower() if isinstance(v, str) else ",".join(v).lower()


class YFinanceSectorOverviewData(Data):
    """YFinance Sector Overview Data."""

    sector: str = Field(description="The Yahoo sector key/slug.")
    name: str | None = Field(default=None, description="The name of the sector.")
    symbol: str | None = Field(default=None, description="The symbol of the sector.")
    market_cap: float | None = Field(
        default=None, description="The market cap of the sector."
    )
    market_weight: float | None = Field(
        default=None, description="The market weight of the sector."
    )
    companies_count: int | None = Field(
        default=None, description="The number of companies in the sector."
    )
    industries_count: int | None = Field(
        default=None, description="The number of industries in the sector."
    )
    employee_count: int | None = Field(
        default=None, description="The number of employees in the sector."
    )
    description: str | None = Field(
        default=None, description="The description of the sector."
    )


class YFinanceSectorOverviewFetcher(
    Fetcher[YFinanceSectorOverviewQueryParams, list[YFinanceSectorOverviewData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(
        params: dict[str, Any],
    ) -> YFinanceSectorOverviewQueryParams:
        """Transform the query."""
        return YFinanceSectorOverviewQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceSectorOverviewQueryParams,
        credentials: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> list[dict]:
        """Return the raw data from the Yahoo Finance endpoint."""
        import asyncio
        from warnings import warn

        from openbb_core.provider.utils.errors import EmptyDataError
        from pandas import isna
        from yfinance import Sector

        sectors = sector_keys(query.sector)
        results: list[dict] = []

        def _val(v: Any) -> Any:
            return None if (not isinstance(v, str) and isna(v)) else v

        def _fetch(sector: str) -> dict | None:
            s = Sector(sector)
            overview = s.overview or {}
            if not overview:
                return None
            return {
                "sector": s.key,
                "name": _val(s.name),
                "symbol": _val(s.symbol),
                "market_cap": _val(overview.get("market_cap")),
                "market_weight": _val(overview.get("market_weight")),
                "companies_count": _val(overview.get("companies_count")),
                "industries_count": _val(overview.get("industries_count")),
                "employee_count": _val(overview.get("employee_count")),
                "description": _val(overview.get("description")),
            }

        async def _get_one(sector: str) -> None:
            try:
                record = await asyncio.to_thread(_fetch, sector)
            except Exception as e:  # noqa: BLE001
                warn(f"Error getting overview for {sector}: {e}")
                return
            if record:
                results.append(record)

        await asyncio.gather(*(_get_one(s) for s in sectors))

        if not results:
            raise EmptyDataError("No overview data was found for the given sector(s).")

        return results

    @staticmethod
    def transform_data(
        query: YFinanceSectorOverviewQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceSectorOverviewData]:
        """Transform the data."""
        return [YFinanceSectorOverviewData.model_validate(d) for d in data]
