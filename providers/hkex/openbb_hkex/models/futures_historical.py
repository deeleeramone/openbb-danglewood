"""HKEX Futures Historical fetcher (FuturesHistorical standard model).

`symbol` is an HKEX derivatives product code (HSI, HHI, HTI, etc.). Pass
``expiration='YYYY-MM'`` to pick a specific contract month; without it the
fetcher returns the front-month continuous series.

The widget chart endpoint (`getchartdata2`) caps per-contract daily history at
about 6 months. Older data isn't publicly retained in machine-readable form.
"""

from __future__ import annotations

from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.futures_historical import (
    FuturesHistoricalData,
    FuturesHistoricalQueryParams,
)
from pydantic import Field, field_validator  # noqa: F401

from openbb_hkex.models._chart import (
    INTERVAL_CHOICES,
    bar_datetime,
    chart_kwargs,
    is_intraday,
    maybe_resample,
)
from openbb_hkex.models.futures_curve import DerivativeProductCode
from openbb_hkex.utils.client import (
    DERIVATIVE_PRODUCTS,
    call_widget,
)

_MONTH_CODE = {
    1: "F",
    2: "G",
    3: "H",
    4: "J",
    5: "K",
    6: "M",
    7: "N",
    8: "Q",
    9: "U",
    10: "V",
    11: "X",
    12: "Z",
}

_CONTRACT_TYPE_MAP = {"standard": 1, "variant": 2}


def _contract_ric(product: str, year: int, month: int) -> str:
    """Build the HKEX futures contract RIC, e.g. ('HSI', 2026, 5) → '1HSIK6'."""
    return f"1{product.upper()}{_MONTH_CODE[month]}{year % 10}"


class HkexFuturesHistoricalQueryParams(FuturesHistoricalQueryParams):
    """HKEX Futures Historical query.

    Pass ``expiration='YYYY-MM'`` to lock onto a specific contract month. If
    omitted, the front-month continuous series (``<PRODUCT>c1``) is returned.
    """

    symbol: DerivativeProductCode = Field(
        description="HKEX derivatives product code (HSI, HHI, GDU, CUS, ...).",
        json_schema_extra={"choices": sorted(DERIVATIVE_PRODUCTS.keys())},
    )
    contract_type: Literal["standard", "variant"] = Field(
        default="standard",
        description="standard = standard contract; variant = flex/weekly where listed.",
        json_schema_extra={"choices": ["standard", "variant"]},
    )
    interval: Literal["1m", "5m", "15m", "30m", "1h", "1d", "1W", "1M", "1Q"] = Field(
        default="1d",
        description="Bar resolution: 1d/1W/1M/1Q (~10y history each); "
        "1h/5m/15m/30m/1m intraday (today to last few days).",
        json_schema_extra={"choices": INTERVAL_CHOICES},
    )

    @field_validator("symbol", mode="before", check_fields=False)
    @classmethod
    def to_upper(cls, v):
        """Convert the value to uppercase."""
        return v.upper() if isinstance(v, str) else v


class HkexFuturesHistoricalData(FuturesHistoricalData):
    """HKEX Futures Historical data."""

    symbol: str = Field(description="Contract RIC, e.g. '1HSIK6'.")
    open: float | None = Field(default=None, description="Open price.")
    high: float | None = Field(default=None, description="High price.")
    low: float | None = Field(default=None, description="Low price.")
    close: float | None = Field(default=None, description="Close price.")
    volume: float | None = Field(default=None, description="Volume.")
    turnover: float | None = Field(
        default=None, description="Turnover (notional traded) for the bar."
    )

    @field_validator("symbol", mode="before", check_fields=False)
    @classmethod
    def date_validate(cls, v):
        """Coerce the value to a string."""
        return str(v) if v is not None else None


class HkexFuturesHistoricalFetcher(
    Fetcher[HkexFuturesHistoricalQueryParams, list[HkexFuturesHistoricalData]]
):
    """HKEX Futures Historical fetcher."""

    @staticmethod
    def transform_query(
        params: dict[str, Any],
    ) -> HkexFuturesHistoricalQueryParams:
        """Transform the query parameters."""
        return HkexFuturesHistoricalQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: HkexFuturesHistoricalQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the data from the HKEX endpoints."""
        ric: str
        if query.expiration:
            try:
                yyyy, mm = query.expiration.split("-")[:2]
                ric = _contract_ric(query.symbol, int(yyyy), int(mm))
            except (ValueError, IndexError):
                ric = f"{query.symbol}c1"
        else:
            ric = f"{query.symbol}c1"

        data = await call_widget(
            "getchartdata2",
            ric=ric,
            **chart_kwargs(query.interval),
        )
        bars = maybe_resample(query.interval, data.get("datalist") or [])
        return [{"_ric": ric, "_bar": bar} for bar in bars]

    @staticmethod
    def transform_data(
        query: HkexFuturesHistoricalQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[HkexFuturesHistoricalData]:
        """Transform the raw data into the model."""
        intraday = is_intraday(query.interval)
        rows: list[HkexFuturesHistoricalData] = []
        for r in data:
            bar = r["_bar"]
            if not bar or len(bar) < 5:
                continue
            o, h, low_, c = bar[1], bar[2], bar[3], bar[4]
            if None in (o, h, low_, c) or min(o, h, low_, c) <= 0:
                continue
            ts = bar_datetime(bar[0])
            day = ts.date()
            if query.start_date and day < query.start_date:
                continue
            if query.end_date and day > query.end_date:
                continue
            rows.append(
                HkexFuturesHistoricalData(
                    date=ts if intraday else day,
                    open=float(bar[1]),
                    high=float(bar[2]),
                    low=float(bar[3]),
                    close=float(bar[4]),
                    volume=float(bar[5])
                    if len(bar) > 5 and bar[5] is not None
                    else None,
                    turnover=float(bar[6])
                    if len(bar) > 6 and bar[6] is not None
                    else None,
                    symbol=r["_ric"],
                )
            )
        return rows
