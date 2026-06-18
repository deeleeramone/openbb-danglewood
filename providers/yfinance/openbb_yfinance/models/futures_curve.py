"""Yahoo Finance Futures Curve Model."""

from typing import Any

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.futures_curve import (
    FuturesCurveData,
    FuturesCurveQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError


class YFinanceFuturesCurveQueryParams(FuturesCurveQueryParams):
    """Yahoo Finance Futures Curve Query.

    Source: https://finance.yahoo.com/
    """

    __json_schema_extra__ = {
        "date": {"multiple_items_allowed": True},
    }


class YFinanceFuturesCurveData(FuturesCurveData):
    """Yahoo Finance Futures Curve Data."""


class YFinanceFuturesCurveFetcher(
    Fetcher[
        YFinanceFuturesCurveQueryParams,
        list[YFinanceFuturesCurveData],
    ]
):
    """YFiannce Futures Curve Fetcher."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> YFinanceFuturesCurveQueryParams:
        """Transform the query."""
        return YFinanceFuturesCurveQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceFuturesCurveQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the data from Yahoo."""
        from openbb_yfinance.utils.helpers import get_futures_curve

        data = await get_futures_curve(query.symbol, query.date)  # ty: ignore[invalid-argument-type]
        data = data.to_dict(orient="records")

        if not data:
            raise EmptyDataError()

        return data

    @staticmethod
    def transform_data(
        query: YFinanceFuturesCurveQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceFuturesCurveData]:
        """Transform the data to the standard format."""
        return [YFinanceFuturesCurveData.model_validate(d) for d in data]
