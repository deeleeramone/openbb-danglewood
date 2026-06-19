"""Yahoo Finance Sector Top Funds Model."""

from typing import Any, Literal

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field, field_validator

from openbb_yfinance.utils.sectors import SECTOR_OPTIONS_WITH_MARKET, sector_keys


class YFinanceSectorTopFundsQueryParams(QueryParams):
    """YFinance Sector Top Funds Query."""

    sector: str | None = Field(
        default=None,
        description="The Yahoo sector key. Leave as 'Market (All Sectors)' for the"
        + " top funds across every sector.",
        json_schema_extra={
            "x-widget_config": {
                "options": SECTOR_OPTIONS_WITH_MARKET,
                "value": "",
            }
        },
    )
    fund_type: Literal["etf", "mutualfund"] = Field(
        default="etf",
        description="Whether to return top ETFs or top mutual funds.",
        json_schema_extra={
            "x-widget_config": {
                "options": [
                    {"label": "ETF", "value": "etf"},
                    {"label": "Mutual Fund", "value": "mutualfund"},
                ],
                "value": "etf",
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


class YFinanceSectorTopFundsData(Data):
    """YFinance Sector Top Funds Data."""

    sector: str = Field(description="The Yahoo sector key/slug.")
    fund_type: str = Field(description="The type of fund, ETF or mutual fund.")
    symbol: str = Field(description="The ticker symbol of the fund.")
    name: str | None = Field(default=None, description="The name of the fund.")


class YFinanceSectorTopFundsFetcher(
    Fetcher[YFinanceSectorTopFundsQueryParams, list[YFinanceSectorTopFundsData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(
        params: dict[str, Any],
    ) -> YFinanceSectorTopFundsQueryParams:
        """Transform the query."""
        return YFinanceSectorTopFundsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceSectorTopFundsQueryParams,
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
            entity = Sector(sector)
            funds = (
                entity.top_etfs if query.fund_type == "etf" else entity.top_mutual_funds
            ) or {}
            return [
                {
                    "sector": sector,
                    "fund_type": query.fund_type,
                    "symbol": symbol,
                    "name": _val(name),
                }
                for symbol, name in funds.items()
            ]

        async def _get_one(sector: str) -> None:
            try:
                rows = await asyncio.to_thread(_fetch, sector)
            except Exception as e:  # noqa: BLE001
                warn(f"Error getting top funds for {sector}: {e}")
                return
            results.extend(rows)

        await asyncio.gather(*(_get_one(s) for s in sectors))

        if not results:
            raise EmptyDataError("No top funds data was found for the given sector(s).")

        return results

    @staticmethod
    def transform_data(
        query: YFinanceSectorTopFundsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceSectorTopFundsData]:
        """Transform the data."""
        return [YFinanceSectorTopFundsData.model_validate(d) for d in data]
