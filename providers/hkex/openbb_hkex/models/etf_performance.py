"""HKEX ETF performance fetcher (custom model).

Trailing total returns for an HK-listed ETF and its benchmark index, sourced
from the fund's issuer and routed by ``issuer_name``.
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
from openbb_hkex.utils.etf_sources import fetch_performance


class HkexEtfPerformanceQueryParams(QueryParams):
    """HKEX ETF performance query."""

    symbol: str = Field(
        description="HKEX ETF stock code.",
        json_schema_extra=symbol_widget_config(),
    )


class HkexEtfPerformanceData(Data):
    """HKEX ETF trailing-return row (one per fund counter and benchmark)."""

    label: str | None = Field(
        default=None, description="Counter ticker or benchmark name."
    )
    kind: str | None = Field(default=None, description="'fund' or 'benchmark'.")
    return_1m: float | None = Field(
        default=None, description="1-month return, percent."
    )
    return_3m: float | None = Field(
        default=None, description="3-month return, percent."
    )
    return_6m: float | None = Field(
        default=None, description="6-month return, percent."
    )
    return_ytd: float | None = Field(
        default=None, description="Year-to-date return, percent."
    )
    return_1y: float | None = Field(default=None, description="1-year return, percent.")
    return_3y: float | None = Field(default=None, description="3-year return, percent.")
    return_5y: float | None = Field(default=None, description="5-year return, percent.")
    return_since_inception: float | None = Field(
        default=None, description="Since-inception return, percent."
    )
    as_of: str | None = Field(default=None, description="As-of date of the figures.")


class HkexEtfPerformanceFetcher(
    Fetcher[HkexEtfPerformanceQueryParams, list[HkexEtfPerformanceData]]
):
    """HKEX ETF performance fetcher."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> HkexEtfPerformanceQueryParams:
        """Transform the query parameters."""
        return HkexEtfPerformanceQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: HkexEtfPerformanceQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the data from the HKEX endpoints."""
        code = to_hk_symbol(query.symbol)
        quote = (await call_widget("getequityquote", sym=code)).get("quote") or {}
        return await fetch_performance(code, quote.get("issuer_name"))

    @staticmethod
    def transform_data(
        query: HkexEtfPerformanceQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[HkexEtfPerformanceData]:
        """Transform the raw data into the model."""
        return [HkexEtfPerformanceData(**row) for row in data]
