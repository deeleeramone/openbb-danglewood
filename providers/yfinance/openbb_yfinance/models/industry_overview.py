"""Yahoo Finance Industry Overview Model."""

from typing import Any

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field, field_validator

from openbb_yfinance.utils.sectors import (
    INDUSTRY_CHOICES_ENDPOINT,
    SECTOR_OPTIONS_WITH_MARKET,
    industry_keys,
)


class YFinanceIndustryOverviewQueryParams(QueryParams):
    """YFinance Industry Overview Query."""

    sector: str | None = Field(
        default="technology",
        description="The Yahoo sector key that populates the Industry choices.",
        json_schema_extra={
            "x-widget_config": {
                "options": SECTOR_OPTIONS_WITH_MARKET,
                "value": "technology",
            }
        },
    )
    industry: str | None = Field(
        default=None,
        description="The Yahoo industry key. Choices cascade from the selected"
        + " sector; leave empty to load every industry in the sector.",
        json_schema_extra={
            "x-widget_config": {
                "type": "endpoint",
                "optionsEndpoint": INDUSTRY_CHOICES_ENDPOINT,
                "optionsParams": {"sector": "$sector"},
            }
        },
    )

    @field_validator("sector", "industry", mode="before", check_fields=False)
    @classmethod
    def _to_lower(cls, v):
        """Lowercase the key(s)."""
        if v is None:
            return None
        return v.lower() if isinstance(v, str) else ",".join(v).lower()


class YFinanceIndustryOverviewData(Data):
    """YFinance Industry Overview Data."""

    industry: str = Field(description="The Yahoo industry key/slug.")
    name: str | None = Field(default=None, description="The name of the industry.")
    symbol: str | None = Field(
        default=None, description="The symbol representing the industry."
    )
    sector: str | None = Field(
        default=None, description="The sector key the industry belongs to."
    )
    sector_name: str | None = Field(
        default=None, description="The name of the sector the industry belongs to."
    )
    market_cap: float | None = Field(
        default=None, description="The total market capitalization of the industry."
    )
    market_weight: float | None = Field(
        default=None, description="The market weight of the industry within its sector."
    )
    companies_count: int | None = Field(
        default=None, description="The number of companies in the industry."
    )
    employee_count: int | None = Field(
        default=None, description="The total number of employees in the industry."
    )
    description: str | None = Field(
        default=None, description="A description of the industry."
    )


class YFinanceIndustryOverviewFetcher(
    Fetcher[YFinanceIndustryOverviewQueryParams, list[YFinanceIndustryOverviewData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(
        params: dict[str, Any],
    ) -> YFinanceIndustryOverviewQueryParams:
        """Transform the query."""
        return YFinanceIndustryOverviewQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceIndustryOverviewQueryParams,
        credentials: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> list[dict]:
        """Return the raw data from the Yahoo Finance endpoint."""
        import asyncio
        from warnings import warn

        from openbb_core.provider.utils.errors import EmptyDataError
        from pandas import isna
        from yfinance import Industry

        keys = (
            [k.strip() for k in query.industry.split(",") if k.strip()]
            if query.industry
            else industry_keys(query.sector)
        )
        results: list[dict] = []

        def _val(v):
            return None if (not isinstance(v, str) and isna(v)) else v

        def _fetch(key: str) -> dict | None:
            i = Industry(key)
            overview = i.overview or {}
            if not overview:
                return None
            return {
                "industry": i.key,
                "name": _val(i.name),
                "symbol": _val(i.symbol),
                "sector": _val(i.sector_key),
                "sector_name": _val(i.sector_name),
                "market_cap": _val(overview.get("market_cap")),
                "market_weight": _val(overview.get("market_weight")),
                "companies_count": _val(overview.get("companies_count")),
                "employee_count": _val(overview.get("employee_count")),
                "description": _val(overview.get("description")),
            }

        async def _get_one(key: str) -> None:
            try:
                record = await asyncio.to_thread(_fetch, key)
            except Exception as e:  # noqa: BLE001
                warn(f"Error getting overview for {key}: {e}")
                return
            if record:
                results.append(record)

        await asyncio.gather(*(_get_one(k) for k in keys))

        if not results:
            raise EmptyDataError(
                "No overview data was found for the given industry(ies)."
            )

        return results

    @staticmethod
    def transform_data(
        query: YFinanceIndustryOverviewQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceIndustryOverviewData]:
        """Transform the data."""
        return [YFinanceIndustryOverviewData.model_validate(d) for d in data]
