"""Yahoo Finance Industry Top Growth Model."""

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


class YFinanceIndustryTopGrowthQueryParams(QueryParams):
    """YFinance Industry Top Growth Query."""

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


class YFinanceIndustryTopGrowthData(Data):
    """YFinance Industry Top Growth Data."""

    industry: str = Field(description="The Yahoo industry key/slug.")
    symbol: str = Field(description="The ticker symbol of the company.")
    name: str | None = Field(default=None, description="The name of the company.")
    ytd_return: float | None = Field(
        default=None, description="The year-to-date return of the company."
    )
    growth_estimate: float | None = Field(
        default=None, description="The growth estimate of the company."
    )


class YFinanceIndustryTopGrowthFetcher(
    Fetcher[
        YFinanceIndustryTopGrowthQueryParams,
        list[YFinanceIndustryTopGrowthData],
    ]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(
        params: dict[str, Any],
    ) -> YFinanceIndustryTopGrowthQueryParams:
        """Transform the query."""
        return YFinanceIndustryTopGrowthQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceIndustryTopGrowthQueryParams,
        credentials: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> list[dict]:
        """Return the raw data from the Yahoo Finance endpoint."""
        import asyncio
        from warnings import warn

        from openbb_core.provider.utils.errors import EmptyDataError
        from pandas import isna

        from yfinance import Industry

        industries = (
            [i.strip() for i in query.industry.split(",") if i.strip()]
            if query.industry
            else industry_keys(query.sector)
        )
        results: list[dict] = []

        def _val(v: Any) -> Any:
            return None if (not isinstance(v, str) and isna(v)) else v

        def _fetch(industry: str) -> list[dict]:
            df = Industry(industry).top_growth_companies
            if df is None or df.empty:
                return []
            df = df.reset_index()
            index_col = df.columns[0]
            rows: list[dict] = []
            for _, row in df.iterrows():
                rows.append(
                    {
                        "industry": industry,
                        "symbol": _val(row.get(index_col)),
                        "name": _val(row.get("name")),
                        "ytd_return": _val(row.get("ytd return")),
                        "growth_estimate": _val(row.get("growth estimate")),
                    }
                )
            return rows

        async def _get_one(industry: str) -> None:
            try:
                rows = await asyncio.to_thread(_fetch, industry)
            except Exception as e:  # noqa: BLE001
                warn(f"Error getting top growth companies for {industry}: {e}")
                return
            results.extend(rows)

        await asyncio.gather(*(_get_one(i) for i in industries))

        if not results:
            raise EmptyDataError(
                "No top growth companies data was found for the given industry(s)."
            )

        return results

    @staticmethod
    def transform_data(
        query: YFinanceIndustryTopGrowthQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceIndustryTopGrowthData]:
        """Transform the data."""
        return [YFinanceIndustryTopGrowthData.model_validate(d) for d in data]
