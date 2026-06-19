"""Yahoo Finance Major Holders Model."""

from typing import Any

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field, field_validator


class YFinanceMajorHoldersQueryParams(QueryParams):
    """YFinance Major Holders Query."""

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    symbol: str = Field(description="The ticker symbol.")

    @field_validator("symbol", mode="before", check_fields=False)
    @classmethod
    def _to_upper(cls, v):
        """Convert symbol to uppercase."""
        return v.upper() if isinstance(v, str) else ",".join(v).upper()


class YFinanceMajorHoldersData(Data):
    """YFinance Major Holders Data."""

    symbol: str = Field(description="The ticker symbol.")
    insiders_percent_held: float | None = Field(
        default=None,
        description="The percent of shares held by insiders.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    institutions_percent_held: float | None = Field(
        default=None,
        description="The percent of shares held by institutions.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    institutions_float_percent_held: float | None = Field(
        default=None,
        description="The percent of float held by institutions.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    institutions_count: int | None = Field(
        default=None, description="The number of institutions holding shares."
    )


class YFinanceMajorHoldersFetcher(
    Fetcher[YFinanceMajorHoldersQueryParams, list[YFinanceMajorHoldersData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> YFinanceMajorHoldersQueryParams:
        """Transform the query."""
        return YFinanceMajorHoldersQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceMajorHoldersQueryParams,
        credentials: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the raw data from Yahoo Finance."""
        import asyncio
        from warnings import warn

        from openbb_core.provider.utils.errors import EmptyDataError
        from pandas import isna

        from yfinance import Ticker

        def _val(v):
            """Convert NaN values to None."""
            return None if (not isinstance(v, str) and isna(v)) else v

        symbols = [s.strip() for s in query.symbol.split(",") if s.strip()]
        results: list[dict] = []

        def _fetch(symbol: str) -> dict | None:
            """Fetch one symbol's major holders."""
            df = Ticker(symbol).major_holders
            if df is None or df.empty:
                return None

            def _get(metric: str):
                try:
                    return _val(df.loc[metric, "Value"])
                except Exception:  # noqa: BLE001  # pylint: disable=broad-except
                    return None

            count = _get("institutionsCount")
            return {
                "symbol": symbol,
                "insiders_percent_held": _get("insidersPercentHeld"),
                "institutions_percent_held": _get("institutionsPercentHeld"),
                "institutions_float_percent_held": _get("institutionsFloatPercentHeld"),
                "institutions_count": int(count) if count is not None else None,
            }

        async def _get_one(symbol: str) -> None:
            try:
                row = await asyncio.to_thread(_fetch, symbol)
            except Exception as e:  # noqa: BLE001
                warn(f"Error getting major holders for {symbol}: {e}")
                return
            if row is not None:
                results.append(row)

        await asyncio.gather(*(_get_one(s) for s in symbols))

        if not results:
            raise EmptyDataError("No major holders were found for the given symbol(s).")

        return results

    @staticmethod
    def transform_data(
        query: YFinanceMajorHoldersQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceMajorHoldersData]:
        """Transform the data."""
        return [YFinanceMajorHoldersData.model_validate(d) for d in data]
