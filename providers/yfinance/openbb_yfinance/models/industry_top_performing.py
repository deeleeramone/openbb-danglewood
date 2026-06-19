"""Yahoo Finance Industry Top Performing Model."""

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


class YFinanceIndustryTopPerformingQueryParams(QueryParams):
    """YFinance Industry Top Performing Query."""

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


class YFinanceIndustryTopPerformingData(Data):
    """YFinance Industry Top Performing Data."""

    industry: str = Field(description="The Yahoo industry key/slug.")
    symbol: str = Field(description="The ticker symbol of the company.")
    name: str | None = Field(default=None, description="The name of the company.")
    ytd_return: float | None = Field(
        default=None, description="The year-to-date return of the company."
    )
    last_price: float | None = Field(
        default=None, description="The last price of the company."
    )
    target_price: float | None = Field(
        default=None, description="The target price of the company."
    )


class YFinanceIndustryTopPerformingFetcher(
    Fetcher[
        YFinanceIndustryTopPerformingQueryParams,
        list[YFinanceIndustryTopPerformingData],
    ]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(
        params: dict[str, Any],
    ) -> YFinanceIndustryTopPerformingQueryParams:
        """Transform the query."""
        return YFinanceIndustryTopPerformingQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceIndustryTopPerformingQueryParams,
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

        def _val(v):
            return None if (not isinstance(v, str) and isna(v)) else v

        def _fetch(industry: str) -> list[dict]:
            df = Industry(industry).top_performing_companies
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
                        "last_price": _val(row.get("last price")),
                        "target_price": _val(row.get("target price")),
                    }
                )
            return rows

        async def _get_one(industry: str) -> None:
            try:
                records = await asyncio.to_thread(_fetch, industry)
            except Exception as e:  # noqa: BLE001
                warn(f"Error getting top performing companies for {industry}: {e}")
                return
            results.extend(records)

        await asyncio.gather(*(_get_one(i) for i in industries))

        if not results:
            raise EmptyDataError(
                "No top performing companies were found for the given industry(s)."
            )

        return results

    @staticmethod
    def transform_data(
        query: YFinanceIndustryTopPerformingQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceIndustryTopPerformingData]:
        """Transform the data."""
        return [YFinanceIndustryTopPerformingData.model_validate(d) for d in data]
