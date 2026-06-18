"""Yahoo Finance Insider Trading Model."""

from typing import Any

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.insider_trading import (
    InsiderTradingData,
    InsiderTradingQueryParams,
)
from pydantic import Field, field_validator


class YFinanceInsiderTradingQueryParams(InsiderTradingQueryParams):
    """YFinance Insider Trading Query.

    Source: https://finance.yahoo.com/quote/AAPL/insider-transactions
    """

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    @field_validator("symbol", mode="before", check_fields=False)
    @classmethod
    def _to_upper(cls, v):
        """Convert symbol to uppercase."""
        return v.upper() if isinstance(v, str) else ",".join(v).upper()


class YFinanceInsiderTradingData(InsiderTradingData):
    """YFinance Insider Trading Data."""

    transaction_value: float | None = Field(
        default=None, description="Value of the transaction."
    )
    description: str | None = Field(
        default=None, description="Description of the transaction."
    )


class YFinanceInsiderTradingFetcher(
    Fetcher[YFinanceInsiderTradingQueryParams, list[YFinanceInsiderTradingData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> YFinanceInsiderTradingQueryParams:
        """Transform the query."""
        return YFinanceInsiderTradingQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceInsiderTradingQueryParams,
        credentials: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> list[dict]:
        """Return the raw data from the Yahoo Finance endpoint."""
        import asyncio
        from warnings import warn

        from openbb_core.provider.utils.errors import EmptyDataError
        from pandas import isna, to_datetime
        from yfinance import Ticker

        symbols = [s.strip() for s in (query.symbol or "").split(",") if s.strip()]
        if not symbols:
            raise EmptyDataError("A symbol is required for insider trading.")
        results: list[dict] = []

        def _val(v):
            """Return None for NaN values."""
            return None if (not isinstance(v, str) and isna(v)) else v

        def _fetch(symbol: str) -> list[dict]:
            transactions = Ticker(symbol).insider_transactions
            rows: list[dict] = []
            if transactions is None or transactions.empty:
                return rows
            for _, row in transactions.iterrows():
                start_date = _val(row.get("Start Date"))
                rows.append(
                    {
                        "symbol": symbol,
                        "owner_name": _val(row.get("Insider")),
                        "owner_title": _val(row.get("Position")),
                        "transaction_type": _val(row.get("Transaction")),
                        "securities_transacted": _val(row.get("Shares")),
                        "transaction_date": (
                            to_datetime(start_date).date()
                            if start_date is not None
                            else None
                        ),
                        "filing_url": _val(row.get("URL")),
                        "ownership_type": _val(row.get("Ownership")),
                        "transaction_value": _val(row.get("Value")),
                        "description": _val(row.get("Text")),
                    }
                )
            if query.limit:
                rows = rows[: query.limit]
            return rows

        async def _get_one(symbol: str) -> None:
            try:
                rows = await asyncio.to_thread(_fetch, symbol)
            except Exception as e:  # noqa: BLE001
                warn(f"Error getting insider trading for {symbol}: {e}")
                return
            results.extend(rows)

        await asyncio.gather(*(_get_one(s) for s in symbols))

        if not results:
            raise EmptyDataError(
                "No insider trading was found for the given symbol(s)."
            )

        return results

    @staticmethod
    def transform_data(
        query: YFinanceInsiderTradingQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceInsiderTradingData]:
        """Transform the data."""
        return [YFinanceInsiderTradingData.model_validate(d) for d in data]
