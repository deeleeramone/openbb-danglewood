"""HKEX ETF Holdings fetcher (EtfHoldings standard model).

The basket of an HK-listed ETF with per-holding weights. HKEX itself publishes
no central holdings feed, so the source is the fund's issuer — resolved from the
``issuer_name`` on the HKEX quote and routed by
``openbb_hkex.utils.etf_sources``.
"""

from __future__ import annotations

from typing import Any

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.etf_holdings import (
    EtfHoldingsData,
    EtfHoldingsQueryParams,
)
from pydantic import Field

from openbb_hkex.utils.client import (
    call_widget,
    symbol_widget_config,
    to_hk_symbol,
)
from openbb_hkex.utils.etf_sources import fetch_holdings


class HkexEtfHoldingsQueryParams(EtfHoldingsQueryParams):
    """HKEX ETF Holdings query. ``symbol`` accepts 2800 / 02800 / 2800.HK forms."""

    symbol: str = Field(
        description="HKEX ETF stock code.",
        json_schema_extra=symbol_widget_config(),
    )


class HkexEtfHoldingsData(EtfHoldingsData):
    """HKEX ETF Holdings row."""

    weight: float | None = Field(
        default=None, description="Weight of the holding in the fund, percent."
    )
    shares: float | None = Field(
        default=None, description="Number of shares/units held."
    )
    market_value: float | None = Field(
        default=None, description="Market value of the position, in fund currency."
    )
    price: float | None = Field(default=None, description="Last price of the holding.")
    sector: str | None = Field(default=None, description="Sector classification.")
    exchange: str | None = Field(
        default=None, description="Trading venue of the holding."
    )
    as_of: str | None = Field(default=None, description="As-of date of the basket.")


class HkexEtfHoldingsFetcher(
    Fetcher[HkexEtfHoldingsQueryParams, list[HkexEtfHoldingsData]]
):
    """HKEX ETF Holdings fetcher."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> HkexEtfHoldingsQueryParams:
        """Transform the query parameters."""
        return HkexEtfHoldingsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: HkexEtfHoldingsQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the data from the HKEX endpoints."""
        code = to_hk_symbol(query.symbol)
        quote = (await call_widget("getequityquote", sym=code)).get("quote") or {}
        issuer = quote.get("issuer_name")
        return await fetch_holdings(code, issuer)

    @staticmethod
    def transform_data(
        query: HkexEtfHoldingsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[HkexEtfHoldingsData]:
        """Transform the raw data into the model."""
        rows: list[HkexEtfHoldingsData] = []
        for row in data:
            sym = str(row.get("symbol") or "")
            item = {**row, "symbol": sym.zfill(5)} if sym.isdigit() else row
            rows.append(HkexEtfHoldingsData(**item))
        return rows
