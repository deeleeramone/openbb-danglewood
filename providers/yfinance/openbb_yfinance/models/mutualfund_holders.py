"""Yahoo Finance Mutual Fund Holders Model."""

from datetime import date as dateType
from typing import Any

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field, field_validator


class YFinanceMutualFundHoldersQueryParams(QueryParams):
    """YFinance Mutual Fund Holders Query."""

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    symbol: str = Field(description="The ticker symbol.")

    @field_validator("symbol", mode="before", check_fields=False)
    @classmethod
    def _to_upper(cls, v):
        """Convert symbol to uppercase."""
        return v.upper() if isinstance(v, str) else ",".join(v).upper()


class YFinanceMutualFundHoldersData(Data):
    """YFinance Mutual Fund Holders Data."""

    symbol: str = Field(description="The ticker symbol.")
    date_reported: dateType | None = Field(
        default=None, description="The date of the holdings report."
    )
    holder: str | None = Field(default=None, description="The name of the holder.")
    percent_held: float | None = Field(
        default=None,
        description="The percent of shares outstanding held by the holder.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    shares: int | None = Field(
        default=None, description="The number of shares held by the holder."
    )
    value: float | None = Field(
        default=None, description="The value of the shares held by the holder."
    )
    percent_change: float | None = Field(
        default=None,
        description="The change in percent of shares held by the holder.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )


class YFinanceMutualFundHoldersFetcher(
    Fetcher[YFinanceMutualFundHoldersQueryParams, list[YFinanceMutualFundHoldersData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> YFinanceMutualFundHoldersQueryParams:
        """Transform the query."""
        return YFinanceMutualFundHoldersQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceMutualFundHoldersQueryParams,
        credentials: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the raw data from Yahoo Finance."""
        import asyncio
        from warnings import warn

        from openbb_core.provider.utils.errors import EmptyDataError
        from pandas import isna, to_datetime

        from yfinance import Ticker

        symbols = [s.strip() for s in query.symbol.split(",") if s.strip()]
        results: list[dict] = []

        def _val(v):
            """Convert NaN to None."""
            return None if (not isinstance(v, str) and isna(v)) else v

        def _fetch(symbol: str) -> list[dict]:
            """Fetch one symbol's mutual fund holders."""
            holders = Ticker(symbol).mutualfund_holders
            rows: list[dict] = []
            if holders is None or holders.empty:
                return rows
            for _, row in holders.iterrows():
                reported = _val(row.get("Date Reported"))
                rows.append(
                    {
                        "symbol": symbol,
                        "date_reported": (
                            to_datetime(reported).date()
                            if reported is not None
                            else None
                        ),
                        "holder": _val(row.get("Holder")),
                        "percent_held": _val(row.get("pctHeld")),
                        "shares": _val(row.get("Shares")),
                        "value": _val(row.get("Value")),
                        "percent_change": _val(row.get("pctChange")),
                    }
                )
            return rows

        async def _get_one(symbol: str) -> None:
            try:
                rows = await asyncio.to_thread(_fetch, symbol)
            except Exception as e:  # noqa: BLE001
                warn(f"Error getting mutual fund holders for {symbol}: {e}")
                return
            results.extend(rows)

        await asyncio.gather(*(_get_one(s) for s in symbols))

        if not results:
            raise EmptyDataError(
                "No mutual fund holders were found for the given symbol(s)."
            )

        return results

    @staticmethod
    def transform_data(
        query: YFinanceMutualFundHoldersQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceMutualFundHoldersData]:
        """Transform the data."""
        return [YFinanceMutualFundHoldersData.model_validate(d) for d in data]
