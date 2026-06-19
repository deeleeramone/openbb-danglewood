"""Yahoo Finance Insider Roster Model."""

from datetime import date as dateType
from typing import Any

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field, field_validator


class YFinanceInsiderRosterQueryParams(QueryParams):
    """YFinance Insider Roster Query."""

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    symbol: str = Field(description="The ticker symbol.")

    @field_validator("symbol", mode="before", check_fields=False)
    @classmethod
    def _to_upper(cls, v):
        """Convert symbol to uppercase."""
        return v.upper() if isinstance(v, str) else ",".join(v).upper()


class YFinanceInsiderRosterData(Data):
    """YFinance Insider Roster Data."""

    symbol: str = Field(description="The ticker symbol.")
    name: str | None = Field(default=None, description="The name of the insider.")
    position: str | None = Field(
        default=None, description="The position of the insider."
    )
    url: str | None = Field(default=None, description="The URL of the insider.")
    most_recent_transaction: str | None = Field(
        default=None, description="The most recent transaction of the insider."
    )
    latest_transaction_date: dateType | None = Field(
        default=None, description="The latest transaction date of the insider."
    )
    shares_owned_directly: float | None = Field(
        default=None, description="The number of shares owned directly by the insider."
    )
    position_direct_date: dateType | None = Field(
        default=None, description="The date of the direct position."
    )


class YFinanceInsiderRosterFetcher(
    Fetcher[YFinanceInsiderRosterQueryParams, list[YFinanceInsiderRosterData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> YFinanceInsiderRosterQueryParams:
        """Transform the query."""
        return YFinanceInsiderRosterQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceInsiderRosterQueryParams,
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
            """Convert NaN values to None."""
            return None if (not isinstance(v, str) and isna(v)) else v

        def _date(v):
            """Convert a value to a date."""
            v = _val(v)
            return to_datetime(v).date() if v is not None else None

        def _fetch(symbol: str) -> list[dict]:
            """Fetch one symbol's insider roster."""
            roster = Ticker(symbol).insider_roster_holders
            rows: list[dict] = []
            if roster is None or roster.empty:
                return rows
            for _, row in roster.iterrows():
                rows.append(
                    {
                        "symbol": symbol,
                        "name": _val(row.get("Name")),
                        "position": _val(row.get("Position")),
                        "url": _val(row.get("URL")),
                        "most_recent_transaction": _val(
                            row.get("Most Recent Transaction")
                        ),
                        "latest_transaction_date": _date(
                            row.get("Latest Transaction Date")
                        ),
                        "shares_owned_directly": _val(row.get("Shares Owned Directly")),
                        "position_direct_date": _date(row.get("Position Direct Date")),
                    }
                )
            return rows

        async def _get_one(symbol: str) -> None:
            try:
                rows = await asyncio.to_thread(_fetch, symbol)
            except Exception as e:  # noqa: BLE001
                warn(f"Error getting insider roster for {symbol}: {e}")
                return
            results.extend(rows)

        await asyncio.gather(*(_get_one(s) for s in symbols))

        if not results:
            raise EmptyDataError("No insider roster was found for the given symbol(s).")

        return results

    @staticmethod
    def transform_data(
        query: YFinanceInsiderRosterQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceInsiderRosterData]:
        """Transform the data."""
        return [YFinanceInsiderRosterData.model_validate(d) for d in data]
