"""Yahoo Finance Historical EPS Model."""

from typing import Any

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.historical_eps import (
    HistoricalEpsData,
    HistoricalEpsQueryParams,
)
from pydantic import Field


class YFinanceHistoricalEpsQueryParams(HistoricalEpsQueryParams):
    """YFinance Historical EPS Query.

    Source: https://finance.yahoo.com/calendar/earnings
    """

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    limit: int | None = Field(
        default=None, description="The number of earnings dates to return."
    )


class YFinanceHistoricalEpsData(HistoricalEpsData):
    """YFinance Historical EPS Data."""

    surprise_percent: float | None = Field(
        default=None,
        description="The earnings surprise, as a normalized percent.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 1},
    )


class YFinanceHistoricalEpsFetcher(
    Fetcher[YFinanceHistoricalEpsQueryParams, list[YFinanceHistoricalEpsData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> YFinanceHistoricalEpsQueryParams:
        """Transform the query."""
        return YFinanceHistoricalEpsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceHistoricalEpsQueryParams,
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
            from pandas import concat

            frames: list = []
            collected = 0
            offset = 0
            while True:
                page_limit = (
                    100
                    if query.limit is None
                    else min(max(query.limit - collected, 1), 100)
                )
                page = Ticker(symbol).get_earnings_dates(
                    limit=page_limit, offset=offset
                )
                if page is None or page.empty:
                    break
                frames.append(page)
                collected += len(page)
                if (query.limit is not None and collected >= query.limit) or len(
                    page
                ) < page_limit:
                    break
                offset += len(page)

            if not frames:
                return []

            df = concat(frames)
            df = df[~df.index.duplicated(keep="first")].sort_index(ascending=False)
            if query.limit is not None:
                df = df.head(query.limit)

            rows: list[dict] = []
            for idx, row in df.iterrows():
                rows.append(
                    {
                        "symbol": symbol,
                        "date": idx,
                        "eps_estimated": row.get("EPS Estimate"),
                        "eps_actual": row.get("Reported EPS"),
                        "surprise_percent": row.get("Surprise(%)"),
                    }
                )
            return rows

        async def _get_one(symbol: str) -> None:
            try:
                rows = await asyncio.to_thread(_fetch, symbol)
            except Exception as e:  # noqa: BLE001
                warn(f"Error getting historical EPS for {symbol}: {e}")
                return
            results.extend(rows)

        await asyncio.gather(*(_get_one(s) for s in symbols))

        if not results:
            raise EmptyDataError("No EPS history was found for the given symbol(s).")

        return results

    @staticmethod
    def transform_data(
        query: YFinanceHistoricalEpsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceHistoricalEpsData]:
        """Transform the data."""
        from pandas import isna, to_datetime

        out: list[YFinanceHistoricalEpsData] = []
        for row in data:
            cleaned = {
                k: (None if (not isinstance(v, str) and isna(v)) else v)
                for k, v in row.items()
            }
            cleaned["date"] = to_datetime(row["date"]).date()
            out.append(YFinanceHistoricalEpsData.model_validate(cleaned))
        return out
