"""HKEX Futures Instruments fetcher (FuturesInstruments standard model)."""

from __future__ import annotations

from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.futures_instruments import (
    FuturesInstrumentsData,
    FuturesInstrumentsQueryParams,
)
from pydantic import Field, field_validator

from openbb_hkex.models.futures_curve import DerivativeProductCode
from openbb_hkex.utils.calendar import last_trading_day
from openbb_hkex.utils.client import (
    DERIVATIVE_PRODUCTS,
    call_widget,
    parse_num,
)
from openbb_hkex.utils.daily_report import index_point_value

_MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


def _con_id(con: str) -> str | None:
    parts = con.replace(" ", "").split("-")
    if len(parts) != 2 or parts[0][:3].upper() not in _MONTHS:
        return None
    mm = _MONTHS[parts[0][:3].upper()]
    yy = int(parts[1])
    return f"{mm:02d}{2000 + yy}"


class HkexFuturesInstrumentsQueryParams(FuturesInstrumentsQueryParams):
    """HKEX Futures Instruments query."""

    symbol: DerivativeProductCode = Field(
        description="HKEX derivatives product code (e.g. HSI, HHI, GDU, CUS).",
        json_schema_extra={"choices": sorted(DERIVATIVE_PRODUCTS.keys())},
    )
    contract_type: Literal["standard", "variant"] = Field(
        default="standard",
        description="standard = standard contract; variant = flex/weekly where listed.",
        json_schema_extra={"choices": ["standard", "variant"]},
    )

    @field_validator("symbol", mode="before", check_fields=False)
    @classmethod
    def to_upper(cls, v):
        """Convert the value to uppercase."""
        return v.upper() if isinstance(v, str) else v


class HkexFuturesInstrumentsData(FuturesInstrumentsData):
    """HKEX Futures Instruments data — one listed contract per row."""

    symbol: str = Field(description="Contract RIC, e.g. '1HSIM6'.")
    product: str = Field(description="HKEX product code (HSI, HHI, ...).")
    name: str | None = Field(default=None, description="Product name.")
    category: str | None = Field(default=None, description="Product category.")
    contract_month: str | None = Field(
        default=None, description="Contract month label."
    )
    expiration: str | None = Field(default=None, description="Last trading day (ISO).")
    currency: str | None = Field(default=None, description="Settlement currency.")
    point_value: float | None = Field(
        default=None,
        description="Contract multiplier (currency value per index point).",
    )


class HkexFuturesInstrumentsFetcher(
    Fetcher[HkexFuturesInstrumentsQueryParams, list[HkexFuturesInstrumentsData]]
):
    """HKEX Futures Instruments fetcher."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> HkexFuturesInstrumentsQueryParams:
        """Transform the query parameters."""
        return HkexFuturesInstrumentsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: HkexFuturesInstrumentsQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the data from the HKEX endpoints."""
        ctype = 1 if query.contract_type == "standard" else 2
        data = await call_widget("getderivativesfutures", ats=query.symbol, type=ctype)
        pv = await index_point_value(query.symbol)
        rows = data.get("futureslist") or []
        for r in rows:
            r["_pv"] = pv
        return rows

    @staticmethod
    async def atransform_data(
        query: HkexFuturesInstrumentsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[HkexFuturesInstrumentsData]:
        """Transform the raw data into the model."""
        meta = DERIVATIVE_PRODUCTS.get(query.symbol, {})
        out: list[HkexFuturesInstrumentsData] = []
        for r in data:
            con = r.get("con") or ""
            cid = _con_id(con)
            ltd = await last_trading_day(query.symbol, cid) if cid else None
            pv = r.get("_pv") or {}
            out.append(
                HkexFuturesInstrumentsData(
                    symbol=r.get("ric") or "",
                    product=query.symbol,
                    name=meta.get("name"),
                    category=meta.get("category"),
                    contract_month=r.get("con_l") or con or None,
                    expiration=ltd.isoformat() if ltd else None,
                    currency=pv.get("currency"),
                    point_value=parse_num(pv.get("value")) if pv else None,
                )
            )
        return out
