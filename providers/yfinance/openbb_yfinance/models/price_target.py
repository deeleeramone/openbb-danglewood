"""Yahoo Finance Price Target Model."""

from typing import Any

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.price_target import (
    PriceTargetData,
    PriceTargetQueryParams,
)
from pydantic import Field, field_validator


class YFinancePriceTargetQueryParams(PriceTargetQueryParams):
    """YFinance Price Target Query.

    Source: https://finance.yahoo.com/quote/AAPL/analysis
    """

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    @field_validator("symbol", mode="before", check_fields=False)
    @classmethod
    def _to_upper(cls, v):
        """Convert symbol to uppercase."""
        return v.upper() if isinstance(v, str) else ",".join(v).upper()


class YFinancePriceTargetData(PriceTargetData):
    """YFinance Price Target Data."""

    price_target_action: str | None = Field(
        default=None, description="The price target action (e.g. up, down, init)."
    )


class YFinancePriceTargetFetcher(
    Fetcher[YFinancePriceTargetQueryParams, list[YFinancePriceTargetData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> YFinancePriceTargetQueryParams:
        """Transform the query."""
        return YFinancePriceTargetQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinancePriceTargetQueryParams,
        credentials: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> list[dict]:
        """Return the raw data from the Yahoo Finance endpoint."""
        import asyncio
        from warnings import warn

        from openbb_core.provider.utils.errors import EmptyDataError
        from pandas import isna
        from yfinance import Ticker

        symbols = [s.strip() for s in (query.symbol or "").split(",") if s.strip()]
        if not symbols:
            raise EmptyDataError("A symbol is required for price targets.")
        results: list[dict] = []

        def _clean(v):
            """Convert pandas NaN to None."""
            return None if (not isinstance(v, str) and isna(v)) else v

        def _fetch(symbol: str) -> list[dict]:
            df = Ticker(symbol).upgrades_downgrades
            if df is None or df.empty:
                return []
            if query.limit:
                df = df.tail(query.limit)
            df = df.iloc[::-1]
            rows: list[dict] = []
            for grade_date, row in df.iterrows():
                rows.append(
                    {
                        "published_date": grade_date.date(),
                        "symbol": symbol,
                        "analyst_firm": _clean(row.get("Firm")),
                        "rating_current": _clean(row.get("ToGrade")),
                        "rating_previous": _clean(row.get("FromGrade")),
                        "action": _clean(row.get("Action")),
                        "price_target": _clean(row.get("currentPriceTarget")),
                        "price_target_previous": _clean(row.get("priorPriceTarget")),
                        "price_target_action": _clean(row.get("priceTargetAction")),
                    }
                )
            return rows

        async def _get_one(symbol: str) -> None:
            try:
                rows = await asyncio.to_thread(_fetch, symbol)
            except Exception as e:  # noqa: BLE001
                warn(f"Error getting price targets for {symbol}: {e}")
                return
            results.extend(rows)

        await asyncio.gather(*(_get_one(s) for s in symbols))

        if not results:
            raise EmptyDataError("No price targets were found for the given symbol(s).")

        return results

    @staticmethod
    def transform_data(
        query: YFinancePriceTargetQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinancePriceTargetData]:
        """Transform the data."""
        return [YFinancePriceTargetData.model_validate(d) for d in data]
