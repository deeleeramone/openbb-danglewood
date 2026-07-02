"""HKEX Equity Info fetcher (EquityInfo standard model).

Decoded company/instrument metadata for a listed security — works for stocks,
ETPs, and REITs. Sourced from the same ``getequityquote`` widget endpoint as
the quote, which carries a rich profile block (issuer, listing, classification,
fundamentals, and for ETPs the AUM/NAV/manager details).
"""

from __future__ import annotations

from typing import Any

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.equity_info import (
    EquityInfoData,
    EquityInfoQueryParams,
)
from pydantic import Field

from openbb_hkex.models._reference import (
    HkexEquityReference,
    extract_fundamentals,
    extract_reference,
    parse_num,
)
from openbb_hkex.utils.client import (
    call_widget,
    symbol_widget_config,
    to_hk_symbol,
)


class HkexEquityInfoQueryParams(EquityInfoQueryParams):
    """HKEX Equity Info query. ``symbol`` accepts 5/700/0700.HK forms."""

    symbol: str = Field(
        description="HKEX stock code.",
        json_schema_extra=symbol_widget_config(),
    )


class HkexEquityInfoData(EquityInfoData, HkexEquityReference):
    """HKEX Equity Info data."""

    market_cap: float | None = Field(
        default=None, description="Market capitalization (full value)."
    )
    eps: float | None = Field(default=None, description="Earnings per share (TTM).")
    eps_currency: str | None = Field(default=None, description="Currency of EPS.")
    pe_ratio: float | None = Field(default=None, description="Price-to-earnings ratio.")
    dividend_yield: float | None = Field(
        default=None, description="Dividend yield, percent."
    )
    aum: float | None = Field(
        default=None, description="Assets under management (ETP)."
    )
    nav: float | None = Field(
        default=None, description="Net asset value per unit (ETP)."
    )
    week_52_high: float | None = Field(default=None, description="52-week high.")
    week_52_low: float | None = Field(default=None, description="52-week low.")
    prev_close: float | None = Field(default=None, description="Previous close price.")


class HkexEquityInfoFetcher(
    Fetcher[HkexEquityInfoQueryParams, list[HkexEquityInfoData]]
):
    """HKEX Equity Info fetcher."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> HkexEquityInfoQueryParams:
        """Transform the query parameters."""
        return HkexEquityInfoQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: HkexEquityInfoQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the data from the HKEX endpoints."""
        sym = to_hk_symbol(query.symbol)
        data = await call_widget("getequityquote", sym=sym)
        quote = data.get("quote") or {}
        return [quote] if quote else []

    @staticmethod
    def transform_data(
        query: HkexEquityInfoQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[HkexEquityInfoData]:
        """Transform the raw data into the model."""
        rows: list[HkexEquityInfoData] = []
        for q in data:
            rows.append(
                HkexEquityInfoData(
                    symbol=q.get("ric") or q.get("sym", ""),
                    name=q.get("nm") or q.get("nm_s"),
                    **extract_reference(q),
                    **extract_fundamentals(q),
                    week_52_high=parse_num(q.get("hi52")),
                    week_52_low=parse_num(q.get("lo52")),
                    prev_close=parse_num(q.get("hc")),
                )
            )
        return rows
