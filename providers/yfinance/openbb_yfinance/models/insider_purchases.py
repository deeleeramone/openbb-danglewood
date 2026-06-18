"""Yahoo Finance Insider Purchases Model."""

from typing import Any

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field, field_validator


class YFinanceInsiderPurchasesQueryParams(QueryParams):
    """YFinance Insider Purchases Query."""

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    symbol: str = Field(description="The ticker symbol.")

    @field_validator("symbol", mode="before", check_fields=False)
    @classmethod
    def _to_upper(cls, v):
        """Convert symbol to uppercase."""
        return v.upper() if isinstance(v, str) else ",".join(v).upper()


class YFinanceInsiderPurchasesData(Data):
    """YFinance Insider Purchases Data."""

    symbol: str = Field(description="The ticker symbol.")
    category: str = Field(description="The insider purchases category.")
    shares: float | None = Field(default=None, description="The number of shares.")
    transactions: float | None = Field(
        default=None, description="The number of transactions."
    )


class YFinanceInsiderPurchasesFetcher(
    Fetcher[YFinanceInsiderPurchasesQueryParams, list[YFinanceInsiderPurchasesData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> YFinanceInsiderPurchasesQueryParams:
        """Transform the query."""
        return YFinanceInsiderPurchasesQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceInsiderPurchasesQueryParams,
        credentials: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the raw data from Yahoo Finance."""
        import asyncio
        from warnings import warn

        from openbb_core.provider.utils.errors import EmptyDataError
        from pandas import isna
        from yfinance import Ticker

        symbols = [s.strip() for s in query.symbol.split(",") if s.strip()]
        results: list[dict] = []

        def _val(v):
            """Convert NaN to None."""
            return None if (not isinstance(v, str) and isna(v)) else v

        def _fetch(symbol: str) -> list[dict]:
            """Fetch one symbol's insider purchases."""
            df = Ticker(symbol).insider_purchases
            rows: list[dict] = []
            if df is None or df.empty:
                return rows
            for row in df.to_dict("records"):
                rows.append(
                    {
                        "symbol": symbol,
                        "category": row.get("Insider Purchases Last 6m"),
                        "shares": _val(row.get("Shares")),
                        "transactions": _val(row.get("Trans")),
                    }
                )
            return rows

        async def _get_one(symbol: str) -> None:
            try:
                rows = await asyncio.to_thread(_fetch, symbol)
            except Exception as e:  # noqa: BLE001
                warn(f"Error getting insider purchases for {symbol}: {e}")
                return
            results.extend(rows)

        await asyncio.gather(*(_get_one(s) for s in symbols))

        if not results:
            raise EmptyDataError(
                "No insider purchases were found for the given symbol(s)."
            )

        return results

    @staticmethod
    def transform_data(
        query: YFinanceInsiderPurchasesQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceInsiderPurchasesData]:
        """Transform the data."""
        return [YFinanceInsiderPurchasesData.model_validate(d) for d in data]
