"""Yahoo Finance Analyst Recommendations Model."""

from typing import Any

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field, field_validator


class YFinanceAnalystRecommendationsQueryParams(QueryParams):
    """YFinance Analyst Recommendations Query."""

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    symbol: str = Field(description="The ticker symbol.")

    @field_validator("symbol", mode="before", check_fields=False)
    @classmethod
    def _to_upper(cls, v):
        """Convert symbol to uppercase."""
        return v.upper() if isinstance(v, str) else ",".join(v).upper()


class YFinanceAnalystRecommendationsData(Data):
    """YFinance Analyst Recommendations Data."""

    __alias_dict__ = {
        "strong_buy": "strongBuy",
        "strong_sell": "strongSell",
    }

    symbol: str = Field(description="The ticker symbol.")
    period: str = Field(
        description="The recommendation-trend period (e.g. 0m, -1m, -2m, -3m)."
    )
    strong_buy: int | None = Field(
        default=None, description="Number of strong buy recommendations."
    )
    buy: int | None = Field(default=None, description="Number of buy recommendations.")
    hold: int | None = Field(
        default=None, description="Number of hold recommendations."
    )
    sell: int | None = Field(
        default=None, description="Number of sell recommendations."
    )
    strong_sell: int | None = Field(
        default=None, description="Number of strong sell recommendations."
    )


class YFinanceAnalystRecommendationsFetcher(
    Fetcher[
        YFinanceAnalystRecommendationsQueryParams,
        list[YFinanceAnalystRecommendationsData],
    ]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(
        params: dict[str, Any],
    ) -> YFinanceAnalystRecommendationsQueryParams:
        """Transform the query."""
        return YFinanceAnalystRecommendationsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceAnalystRecommendationsQueryParams,
        credentials: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> list[dict]:
        """Return the raw data from the Yahoo Finance endpoint."""
        import asyncio
        from warnings import warn

        from openbb_core.provider.utils.errors import EmptyDataError
        from pandas import isna

        from yfinance import Ticker

        symbols = [s.strip() for s in query.symbol.split(",") if s.strip()]
        results: list[dict] = []

        def _fetch(symbol: str) -> list[dict]:
            """Parse the recommendations DataFrame for one symbol."""
            recommendations = Ticker(symbol).recommendations
            if recommendations is None or recommendations.empty:
                return []
            rows: list[dict] = []
            for record in recommendations.to_dict(orient="records"):
                row: dict = {"symbol": symbol}
                for key, value in record.items():
                    row[key] = (
                        None if (not isinstance(value, str) and isna(value)) else value
                    )
                rows.append(row)
            return rows

        async def _get_one(symbol: str) -> None:
            try:
                rows = await asyncio.to_thread(_fetch, symbol)
            except Exception as e:  # noqa: BLE001
                warn(f"Error getting recommendations for {symbol}: {e}")
                return
            results.extend(rows)

        await asyncio.gather(*(_get_one(s) for s in symbols))

        if not results:
            raise EmptyDataError(
                "No recommendations were found for the given symbol(s)."
            )

        return results

    @staticmethod
    def transform_data(
        query: YFinanceAnalystRecommendationsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceAnalystRecommendationsData]:
        """Transform the data."""
        return [YFinanceAnalystRecommendationsData.model_validate(d) for d in data]
