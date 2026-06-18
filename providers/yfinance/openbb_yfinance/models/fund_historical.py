"""Yahoo Finance Fund Historical Price Model."""

from datetime import date as dateType
from typing import TYPE_CHECKING, Any, Literal

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from openbb_core.provider.utils.descriptions import (
    DATA_DESCRIPTIONS,
    QUERY_DESCRIPTIONS,
)
from pydantic import Field, field_validator

if TYPE_CHECKING:
    from pandas import DataFrame


class YFinanceFundHistoricalQueryParams(QueryParams):
    """YFinance Fund Historical Price Query."""

    __json_schema_extra__ = {
        "symbol": {"multiple_items_allowed": True},
        "interval": {"choices": ["1d", "5d", "1W", "1M", "1Q"]},
    }

    symbol: str = Field(description="The fund or ETF ticker symbol.")
    start_date: dateType | None = Field(
        default=None, description=QUERY_DESCRIPTIONS.get("start_date", "")
    )
    end_date: dateType | None = Field(
        default=None, description=QUERY_DESCRIPTIONS.get("end_date", "")
    )
    interval: Literal["1d", "5d", "1W", "1M", "1Q"] = Field(
        default="1d", description=QUERY_DESCRIPTIONS.get("interval", "")
    )

    @field_validator("symbol", mode="before", check_fields=False)
    @classmethod
    def _to_upper(cls, v):
        """Convert symbol to uppercase."""
        return v.upper() if isinstance(v, str) else ",".join(v).upper()


class YFinanceFundHistoricalData(Data):
    """YFinance Fund Historical Price Data."""

    date: dateType | Any = Field(description=DATA_DESCRIPTIONS.get("date", ""))
    open: float | None = Field(
        default=None, description=DATA_DESCRIPTIONS.get("open", "")
    )
    high: float | None = Field(
        default=None, description=DATA_DESCRIPTIONS.get("high", "")
    )
    low: float | None = Field(
        default=None, description=DATA_DESCRIPTIONS.get("low", "")
    )
    close: float | None = Field(
        default=None, description=DATA_DESCRIPTIONS.get("close", "")
    )
    volume: int | None = Field(
        default=None, description=DATA_DESCRIPTIONS.get("volume", "")
    )
    symbol: str | None = Field(
        default=None, description="The ticker symbol, when multiple are requested."
    )


class YFinanceFundHistoricalFetcher(
    Fetcher[YFinanceFundHistoricalQueryParams, list[YFinanceFundHistoricalData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> YFinanceFundHistoricalQueryParams:
        """Transform the query."""
        from datetime import datetime

        from dateutil.relativedelta import relativedelta

        now = datetime.now().date()
        if params.get("start_date") is None:
            params["start_date"] = now - relativedelta(years=1)
        if params.get("end_date") is None:
            params["end_date"] = now
        return YFinanceFundHistoricalQueryParams(**params)

    @staticmethod
    def extract_data(
        query: YFinanceFundHistoricalQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> "DataFrame":
        """Return the raw data from the Yahoo Finance endpoint."""
        from openbb_core.provider.utils.errors import EmptyDataError

        from openbb_yfinance.utils.helpers import yf_download
        from openbb_yfinance.utils.references import INTERVALS_DICT

        data = yf_download(
            symbol=query.symbol,
            start_date=query.start_date,
            end_date=query.end_date,
            interval=INTERVALS_DICT[query.interval],  # ty: ignore[invalid-argument-type]
            adjusted=False,
        )

        if data.empty:
            raise EmptyDataError()

        return data

    @staticmethod
    def transform_data(
        query: YFinanceFundHistoricalQueryParams,
        data: "DataFrame",
        **kwargs: Any,
    ) -> list[YFinanceFundHistoricalData]:
        """Transform the data to the standard format."""
        keep = [
            c
            for c in ("date", "open", "high", "low", "close", "volume", "symbol")
            if c in data.columns
        ]
        records = data[keep].to_dict("records")
        return [YFinanceFundHistoricalData.model_validate(d) for d in records]
