"""HKEX Index Historical fetcher (IndexHistorical standard model).

`symbol` is an HKEX index RIC (e.g. ``.HSI``, ``.HSCE``, ``.HSTECH``,
``.CSI300``). For convenience the dot prefix is optional — pass ``HSI`` or
``.HSI`` interchangeably.
"""

from __future__ import annotations

from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.index_historical import (
    IndexHistoricalData,
    IndexHistoricalQueryParams,
)
from pydantic import Field, field_validator

from openbb_hkex.models._chart import (
    INTERVAL_CHOICES,
    bar_datetime,
    chart_kwargs,
    is_intraday,
    maybe_resample,
)
from openbb_hkex.utils.client import call_widget

INDEX_RICS: dict[str, str] = {
    ".HSI": "Hang Seng Index",
    ".HSCE": "HSCEI",
    ".HSTECH": "Hang Seng TECH Index",
    ".HKEXT100": "HKEX 100 Index",
    ".VHSI": "HSI Volatility Index",
    ".CSI300": "CSI 300 Index",
    ".HKCES120": "CES China 120",
    ".HKEXBTC": "HKEX Bitcoin Reference Index",
    ".HKEXETH": "HKEX Ether Reference Index",
    ".HKGDRSP": "USD Gold Futures – Spot Price Index",
    ".HKGDUSP": "CNH Gold Futures – Spot Price Index",
    ".HKCESG10": "CES Gaming Top 10 Index",
    ".HSMBI": "Hang Seng Mainland Banks Index",
    ".HSMPI": "Hang Seng Mainland Properties Index",
    ".HSMOGI": "Hang Seng Mainland Oil & Gas Index",
    ".HSSSI": "Hang Seng Software & Services Index",
    ".HSITHI": "Hang Seng IT Hardware Index",
    ".HSMHI": "Hang Seng Mainland Healthcare Index",
    ".HSIDPI": "HSI Dividend Point Index",
    ".HSCEIDPI": "HSCEI Dividend Point Index",
    ".RXYH": "TR/HKEX RMB Index",
    ".RXYBH": "TR/HKEX Simplified RMB Index",
    ".RXYY": "TR/HKEX Global CNY Index",
    ".RXYRH": "TR/HKEX Reference CNH Index",
    ".RXYRY": "TR/HKEX Reference CNY Index",
}

IndexRicCode = Literal[
    ".HSI",
    ".HSCE",
    ".HSTECH",
    ".HKEXT100",
    ".VHSI",
    ".CSI300",
    ".HKCES120",
    ".HKEXBTC",
    ".HKEXETH",
    ".HKGDRSP",
    ".HKGDUSP",
    ".HKCESG10",
    ".HSMBI",
    ".HSMPI",
    ".HSMOGI",
    ".HSSSI",
    ".HSITHI",
    ".HSMHI",
    ".HSIDPI",
    ".HSCEIDPI",
    ".RXYH",
    ".RXYBH",
    ".RXYY",
    ".RXYRH",
    ".RXYRY",
]


class HkexIndexHistoricalQueryParams(IndexHistoricalQueryParams):
    """HKEX Index Historical query."""

    symbol: IndexRicCode = Field(
        description="HKEX index RIC. The leading dot is optional on input "
        "(pass `HSI` or `.HSI`); it is normalized to the canonical dot-prefixed "
        "form. Run `obb.hkex.derivative_products()` plus the INDEX_RICS map for "
        "human-readable names.",
        json_schema_extra={"choices": sorted(INDEX_RICS.keys())},
    )
    interval: Literal["1m", "5m", "15m", "30m", "1h", "1d", "1W", "1M", "1Q"] = Field(
        default="1d",
        description="Bar resolution: 1d/1W/1M/1Q (~10y history each); "
        "1h/5m/15m/30m/1m intraday (today to last few days).",
        json_schema_extra={"choices": INTERVAL_CHOICES},
    )

    @field_validator("symbol", mode="before", check_fields=False)
    @classmethod
    def _normalize_symbol(cls, v):
        if not isinstance(v, str):
            return v
        s = v.strip().upper()
        return s if s.startswith(".") else f".{s}"


class HkexIndexHistoricalData(IndexHistoricalData):
    """HKEX Index Historical data."""

    turnover: float | None = Field(
        default=None, description="Turnover (notional traded) for the bar."
    )


class HkexIndexHistoricalFetcher(
    Fetcher[HkexIndexHistoricalQueryParams, list[HkexIndexHistoricalData]]
):
    """HKEX Index Historical fetcher."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> HkexIndexHistoricalQueryParams:
        """Transform the query parameters."""
        return HkexIndexHistoricalQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: HkexIndexHistoricalQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the data from the HKEX endpoints."""
        ric = query.symbol
        data = await call_widget(
            "getchartdata2",
            ric=ric,
            **chart_kwargs(query.interval),
        )
        bars = maybe_resample(query.interval, data.get("datalist") or [])
        return [{"_ric": ric, "_bar": bar} for bar in bars]

    @staticmethod
    def transform_data(
        query: HkexIndexHistoricalQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[HkexIndexHistoricalData]:
        """Transform the raw data into the model."""
        intraday = is_intraday(query.interval)
        rows: list[HkexIndexHistoricalData] = []
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
                HkexIndexHistoricalData(
                    symbol=r["_ric"].lstrip("."),
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
                )
            )
        return rows
