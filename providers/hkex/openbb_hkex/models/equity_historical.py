"""HKEX Equity Historical fetcher (EquityHistorical standard model)."""

from __future__ import annotations

from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.equity_historical import (
    EquityHistoricalData,
    EquityHistoricalQueryParams,
)
from pydantic import Field

from openbb_hkex.models._chart import (
    INTERVAL_CHOICES,
    bar_datetime,
    chart_kwargs,
    is_intraday,
    maybe_resample,
)
from openbb_hkex.utils.client import (
    call_widget,
    symbol_widget_config,
    to_hk_symbol,
)


class HkexEquityHistoricalQueryParams(EquityHistoricalQueryParams):
    """HKEX Equity Historical query.

    ``interval`` selects the resolution (1m/5m intraday; 1d/1W/1M/1Q served with
    the full ~10-year history). ``[start_date, end_date]`` filters client-side.
    """

    symbol: str = Field(
        description="HKEX stock code.",
        json_schema_extra=symbol_widget_config(),
    )
    interval: Literal["1m", "5m", "15m", "30m", "1h", "1d", "1W", "1M", "1Q"] = Field(
        default="1d",
        description="Bar resolution: 1d=daily, 1W=weekly, 1M=monthly, 1Q=quarterly "
        "(~10y history each); 1h hourly / 5m / 15m / 30m / 1m intraday "
        "(today to last few days).",
        json_schema_extra={"choices": INTERVAL_CHOICES},
    )


class HkexEquityHistoricalData(EquityHistoricalData):
    """HKEX Equity Historical data."""

    turnover: float | None = Field(
        default=None, description="Turnover (notional traded) for the bar."
    )


class HkexEquityHistoricalFetcher(
    Fetcher[HkexEquityHistoricalQueryParams, list[HkexEquityHistoricalData]]
):
    """HKEX Equity Historical fetcher."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> HkexEquityHistoricalQueryParams:
        """Transform the query parameters."""
        return HkexEquityHistoricalQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: HkexEquityHistoricalQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the data from the HKEX endpoints."""
        ric = f"{int(to_hk_symbol(query.symbol)):04d}.HK"
        data = await call_widget(
            "getchartdata2",
            ric=ric,
            **chart_kwargs(query.interval),
        )
        return maybe_resample(query.interval, data.get("datalist") or [])

    @staticmethod
    def transform_data(
        query: HkexEquityHistoricalQueryParams,
        data: list[Any],
        **kwargs: Any,
    ) -> list[HkexEquityHistoricalData]:
        """Transform the raw data into the model."""
        intraday = is_intraday(query.interval)
        rows: list[HkexEquityHistoricalData] = []
        for bar in data:
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
                HkexEquityHistoricalData(
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
