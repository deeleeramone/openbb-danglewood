"""Yahoo Finance Sector Top Companies Model."""

from typing import Any

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field, field_validator

from openbb_yfinance.utils.sectors import SECTOR_OPTIONS_WITH_MARKET, sector_keys


class YFinanceSectorTopCompaniesQueryParams(QueryParams):
    """YFinance Sector Top Companies Query."""

    sector: str | None = Field(
        default=None,
        description="The Yahoo sector key. Leave as 'Market (All Sectors)' for the"
        + " top companies across every sector.",
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


class YFinanceSectorTopCompaniesData(Data):
    """YFinance Sector Top Companies Data."""

    sector: str = Field(description="The Yahoo sector key/slug.")
    symbol: str = Field(description="The ticker symbol of the company.")
    name: str | None = Field(default=None, description="The name of the company.")
    rating: str | None = Field(
        default=None, description="The analyst rating for the company."
    )
    market_weight: float | None = Field(
        default=None, description="The market weight of the company within the sector."
    )


class YFinanceSectorTopCompaniesFetcher(
    Fetcher[
        YFinanceSectorTopCompaniesQueryParams,
        list[YFinanceSectorTopCompaniesData],
    ]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(
        params: dict[str, Any],
    ) -> YFinanceSectorTopCompaniesQueryParams:
        """Transform the query."""
        return YFinanceSectorTopCompaniesQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceSectorTopCompaniesQueryParams,
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

        def _val(v):
            return None if (not isinstance(v, str) and isna(v)) else v

        def _fetch(sector: str) -> list[dict]:
            df = Sector(sector).top_companies
            if df is None or df.empty:
                return []
            df = df.reset_index()
            index_col = df.columns[0]
            rows: list[dict] = []
            for _, row in df.iterrows():
                rows.append(
                    {
                        "sector": sector,
                        "symbol": row.get(index_col),
                        "name": _val(row.get("name")),
                        "rating": _val(row.get("rating")),
                        "market_weight": _val(row.get("market weight")),
                    }
                )
            return rows

        async def _get_one(sector: str) -> None:
            try:
                rows = await asyncio.to_thread(_fetch, sector)
            except Exception as e:  # noqa: BLE001
                warn(f"Error getting top companies for {sector}: {e}")
                return
            results.extend(rows)

        await asyncio.gather(*(_get_one(s) for s in sectors))

        if not results:
            raise EmptyDataError(
                "No top companies data was found for the given sector(s)."
            )

        return results

    @staticmethod
    def transform_data(
        query: YFinanceSectorTopCompaniesQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceSectorTopCompaniesData]:
        """Transform the data."""
        return [YFinanceSectorTopCompaniesData.model_validate(d) for d in data]
