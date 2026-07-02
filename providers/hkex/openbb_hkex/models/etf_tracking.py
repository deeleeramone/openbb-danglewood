"""HKEX ETF tracking fetcher (custom model).

Tracking difference and tracking error of an HK-listed ETF versus its benchmark,
sourced from the fund's issuer and routed by ``issuer_name``.
"""

from __future__ import annotations

from typing import Any

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field

from openbb_hkex.utils.client import (
    call_widget,
    symbol_widget_config,
    to_hk_symbol,
)
from openbb_hkex.utils.etf_sources import fetch_tracking


class HkexEtfTrackingQueryParams(QueryParams):
    """HKEX ETF tracking query."""

    symbol: str = Field(
        description="HKEX ETF stock code.",
        json_schema_extra=symbol_widget_config(),
    )


class HkexEtfTrackingData(Data):
    """HKEX ETF tracking-difference / tracking-error row (one per fund counter)."""

    label: str | None = Field(default=None, description="Counter ticker.")
    tracking_difference_mtd: float | None = Field(
        default=None, description="Month-to-date tracking difference, percent."
    )
    tracking_difference_1y: float | None = Field(
        default=None, description="1-year tracking difference, percent."
    )
    tracking_error_1y: float | None = Field(
        default=None, description="1-year tracking error, percent."
    )
    as_of: str | None = Field(default=None, description="As-of date of the figures.")


class HkexEtfTrackingFetcher(
    Fetcher[HkexEtfTrackingQueryParams, list[HkexEtfTrackingData]]
):
    """HKEX ETF tracking fetcher."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> HkexEtfTrackingQueryParams:
        """Transform the query parameters."""
        return HkexEtfTrackingQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: HkexEtfTrackingQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the data from the HKEX endpoints."""
        code = to_hk_symbol(query.symbol)
        quote = (await call_widget("getequityquote", sym=code)).get("quote") or {}
        return await fetch_tracking(code, quote.get("issuer_name"))

    @staticmethod
    def transform_data(
        query: HkexEtfTrackingQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[HkexEtfTrackingData]:
        """Transform the raw data into the model."""
        return [HkexEtfTrackingData(**row) for row in data]
