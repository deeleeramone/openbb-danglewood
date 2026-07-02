"""HKEX ETF NAV history fetcher (custom model).

Daily net-asset-value history for an HK-listed ETF, sourced from the fund's
issuer (HKEX publishes no central NAV feed). Routed by ``issuer_name`` via
``openbb_hkex.utils.etf_sources``.
"""

from __future__ import annotations

from datetime import (
    date,
    date as dateType,
)
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
from openbb_hkex.utils.etf_sources import fetch_nav_history


class HkexEtfNavQueryParams(QueryParams):
    """HKEX ETF NAV history query."""

    symbol: str = Field(
        description="HKEX ETF stock code.",
        json_schema_extra=symbol_widget_config(),
    )
    start_date: date | None = Field(
        default=None, description="Start date of the NAV history (defaults to 3y ago)."
    )
    end_date: date | None = Field(
        default=None, description="End date of the NAV history (defaults to today)."
    )


class HkexEtfNavData(Data):
    """HKEX ETF NAV history point."""

    date: dateType = Field(description="The date of the NAV.")
    nav: float | None = Field(default=None, description="Net asset value per unit.")
    currency: str | None = Field(default=None, description="NAV currency.")


class HkexEtfNavFetcher(Fetcher[HkexEtfNavQueryParams, list[HkexEtfNavData]]):
    """HKEX ETF NAV history fetcher."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> HkexEtfNavQueryParams:
        """Transform the query parameters."""
        return HkexEtfNavQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: HkexEtfNavQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the data from the HKEX endpoints."""
        code = to_hk_symbol(query.symbol)
        quote = (await call_widget("getequityquote", sym=code)).get("quote") or {}
        return await fetch_nav_history(
            code, quote.get("issuer_name"), query.start_date, query.end_date
        )

    @staticmethod
    def transform_data(
        query: HkexEtfNavQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[HkexEtfNavData]:
        """Transform the raw data into the model."""
        return [HkexEtfNavData(**row) for row in data]
