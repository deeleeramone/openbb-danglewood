"""Yahoo Finance Symbol Search Model."""

from typing import Any, Literal

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field


class YFinanceSymbolSearchQueryParams(QueryParams):
    """YFinance Symbol Search Query.

    Source: https://finance.yahoo.com/lookup
    """

    query: str = Field(default="", description="Search query.")
    asset_type: Literal[
        "all", "equity", "etf", "index", "mutualfund", "future", "currency", "crypto"
    ] = Field(
        default="all",
        description="Restrict the search to a single asset type. Empty searches all.",
    )
    limit: int = Field(
        default=30, description="The maximum number of results to return."
    )


class YFinanceSymbolSearchData(Data):
    """YFinance Symbol Search Data."""

    symbol: str = Field(description="The ticker symbol.")
    name: str | None = Field(default=None, description="The name of the asset.")
    description: str | None = Field(
        default=None, description="A short description of the asset."
    )
    exchange: str | None = Field(
        default=None, description="The exchange the asset trades on."
    )
    asset_type: str | None = Field(
        default=None, description="The type of asset (equity, etf, index, etc.)."
    )


class YFinanceSymbolSearchFetcher(
    Fetcher[YFinanceSymbolSearchQueryParams, list[YFinanceSymbolSearchData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> YFinanceSymbolSearchQueryParams:
        """Transform query params."""
        return YFinanceSymbolSearchQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceSymbolSearchQueryParams,
        credentials: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the raw data from Yahoo Finance."""
        import asyncio

        from openbb_core.provider.utils.errors import EmptyDataError

        from openbb_yfinance.utils.search_helpers import yf_symbol_search

        results = await asyncio.to_thread(
            yf_symbol_search,
            query.query,
            query.limit,
            "" if query.asset_type == "all" else query.asset_type,
        )

        if not results:
            raise EmptyDataError("No results were found for the given query.")

        return results

    @staticmethod
    def transform_data(
        query: YFinanceSymbolSearchQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceSymbolSearchData]:
        """Transform the data."""
        return [YFinanceSymbolSearchData.model_validate(d) for d in data]
