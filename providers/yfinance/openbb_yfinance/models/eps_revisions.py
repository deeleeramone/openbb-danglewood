"""Yahoo Finance EPS Revisions Model."""

from typing import Any

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field, field_validator


class YFinanceEpsRevisionsQueryParams(QueryParams):
    """YFinance EPS Revisions Query."""

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    symbol: str = Field(description="The ticker symbol.")

    @field_validator("symbol", mode="before", check_fields=False)
    @classmethod
    def _to_upper(cls, v):
        """Convert symbol to uppercase."""
        return v.upper() if isinstance(v, str) else ",".join(v).upper()


class YFinanceEpsRevisionsData(Data):
    """YFinance EPS Revisions Data."""

    symbol: str = Field(description="The ticker symbol.")
    period: str = Field(description="The estimate period (e.g. 0q, +1q, 0y, +1y).")
    up_last_7_days: int | None = Field(
        default=None, description="Number of upward revisions over the last 7 days."
    )
    up_last_30_days: int | None = Field(
        default=None, description="Number of upward revisions over the last 30 days."
    )
    down_last_7_days: int | None = Field(
        default=None,
        description="Number of downward revisions over the last 7 days.",
    )
    down_last_30_days: int | None = Field(
        default=None,
        description="Number of downward revisions over the last 30 days.",
    )
    currency: str | None = Field(
        default=None, description="The currency of the estimates."
    )


class YFinanceEpsRevisionsFetcher(
    Fetcher[YFinanceEpsRevisionsQueryParams, list[YFinanceEpsRevisionsData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> YFinanceEpsRevisionsQueryParams:
        """Transform the query."""
        return YFinanceEpsRevisionsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceEpsRevisionsQueryParams,
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

        def _clean(value):
            """Convert pandas NaN to None."""
            return None if (not isinstance(value, str) and isna(value)) else value

        def _fetch(symbol: str) -> list[dict]:
            """Parse the eps_revisions DataFrame for one symbol."""
            df = Ticker(symbol).eps_revisions
            rows: list[dict] = []
            if df is None or df.empty:
                return rows
            for period, row in df.iterrows():
                rows.append(
                    {
                        "symbol": symbol,
                        "period": str(period),
                        "up_last_7_days": _clean(row.get("upLast7days")),
                        "up_last_30_days": _clean(row.get("upLast30days")),
                        "down_last_7_days": _clean(row.get("downLast7Days")),
                        "down_last_30_days": _clean(row.get("downLast30days")),
                        "currency": _clean(row.get("currency")),
                    }
                )
            return rows

        async def _get_one(symbol: str) -> None:
            try:
                rows = await asyncio.to_thread(_fetch, symbol)
            except Exception as e:  # noqa: BLE001
                warn(f"Error getting EPS revisions for {symbol}: {e}")
                return
            results.extend(rows)

        await asyncio.gather(*(_get_one(s) for s in symbols))

        if not results:
            raise EmptyDataError(
                "No EPS revisions data was found for the given symbol(s)."
            )

        return results

    @staticmethod
    def transform_data(
        query: YFinanceEpsRevisionsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceEpsRevisionsData]:
        """Transform the data."""
        return [YFinanceEpsRevisionsData.model_validate(d) for d in data]
