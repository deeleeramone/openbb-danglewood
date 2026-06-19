"""Yahoo Finance EPS Trend Model."""

from typing import Any

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field, field_validator


class YFinanceEpsTrendQueryParams(QueryParams):
    """YFinance EPS Trend Query."""

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    symbol: str = Field(description="The ticker symbol.")

    @field_validator("symbol", mode="before", check_fields=False)
    @classmethod
    def _to_upper(cls, v):
        """Convert symbol to uppercase."""
        return v.upper() if isinstance(v, str) else ",".join(v).upper()


class YFinanceEpsTrendData(Data):
    """YFinance EPS Trend Data."""

    symbol: str = Field(description="The ticker symbol.")
    period: str = Field(description="The estimate period (0q, +1q, 0y, +1y).")
    current: float | None = Field(default=None, description="The current EPS estimate.")
    days_ago_7: float | None = Field(
        default=None, description="The EPS estimate 7 days ago."
    )
    days_ago_30: float | None = Field(
        default=None, description="The EPS estimate 30 days ago."
    )
    days_ago_60: float | None = Field(
        default=None, description="The EPS estimate 60 days ago."
    )
    days_ago_90: float | None = Field(
        default=None, description="The EPS estimate 90 days ago."
    )
    currency: str | None = Field(
        default=None, description="The currency of the estimates."
    )


class YFinanceEpsTrendFetcher(
    Fetcher[YFinanceEpsTrendQueryParams, list[YFinanceEpsTrendData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> YFinanceEpsTrendQueryParams:
        """Transform the query."""
        return YFinanceEpsTrendQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceEpsTrendQueryParams,
        credentials: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> list[dict]:
        """Return the raw data from the Yahoo Finance endpoint."""
        import asyncio
        from warnings import warn

        from openbb_core.provider.utils.errors import EmptyDataError

        from yfinance import Ticker

        symbols = [s.strip() for s in query.symbol.split(",") if s.strip()]
        results: list[dict] = []

        def _fetch(symbol: str) -> list[dict]:
            """Fetch and parse the eps_trend for one symbol."""
            df = Ticker(symbol).eps_trend
            rows: list[dict] = []
            if df is None or df.empty:
                return rows
            for period, row in df.iterrows():
                rows.append(
                    {
                        "symbol": symbol,
                        "period": str(period),
                        "current": row.get("current"),
                        "days_ago_7": row.get("7daysAgo"),
                        "days_ago_30": row.get("30daysAgo"),
                        "days_ago_60": row.get("60daysAgo"),
                        "days_ago_90": row.get("90daysAgo"),
                        "currency": row.get("currency"),
                    }
                )
            return rows

        async def _get_one(symbol: str) -> None:
            try:
                rows = await asyncio.to_thread(_fetch, symbol)
            except Exception as e:  # noqa: BLE001
                warn(f"Error getting EPS trend for {symbol}: {e}")
                return
            results.extend(rows)

        await asyncio.gather(*(_get_one(s) for s in symbols))

        if not results:
            raise EmptyDataError("No EPS trend data was found for the given symbol(s).")

        return results

    @staticmethod
    def transform_data(
        query: YFinanceEpsTrendQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceEpsTrendData]:
        """Transform the data."""
        from pandas import isna

        results: list[YFinanceEpsTrendData] = []
        for d in data:
            cleaned = {
                k: (None if (not isinstance(v, str) and isna(v)) else v)
                for k, v in d.items()
            }
            results.append(YFinanceEpsTrendData.model_validate(cleaned))
        return results
