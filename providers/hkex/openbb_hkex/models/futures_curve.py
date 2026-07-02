"""HKEX Futures Curve fetcher (FuturesCurve standard model).

Returns the term-structure for an HKEX derivatives product. Supports a
single ``date=`` value or multiple comma-separated dates so you can compare
"today vs N months ago" curves for the same product.

Source notes:
  * Live curve — `getderivativesfutures` widget endpoint (front, second,
    third... month with live last, OI, volume, and previous settlement).
  * Historical curves — HKEX's authoritative per-product daily market
    reports at `https://www.hkex.com.hk/eng/stat/dmstat/dayrpt/<prefix><yymmdd>.htm`.
    Each report carries the official Settlement Price, change-in-settle,
    combined volume, open interest, and change-in-OI per contract month for
    that trading day.

    HKEX's public archive at this path keeps roughly the past 7 months of
    daily reports online; older trading days return 404. Dates outside this
    window yield no rows for that snapshot.

When comparing across dates, use the ``symbol`` field (``M1``, ``M2``, ...) as
the X-axis. ``symbol`` is the contract's tenor slot from each snapshot date's
perspective (M1 = front month for that date), which keeps the curves overlayable
even though the underlying expiration calendar shifts day to day. The
``expiration`` field preserves the raw HKEX contract month label
(e.g. ``"MAY-26"``).
"""

from __future__ import annotations

import asyncio
from datetime import (
    date as dateType,
    datetime,
)
from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.futures_curve import (
    FuturesCurveData,
    FuturesCurveQueryParams,
)
from pydantic import Field, field_validator

from openbb_hkex.utils.client import (
    DERIVATIVE_PRODUCTS,
    call_widget,
    parse_int,
    parse_num,
)
from openbb_hkex.utils.daily_report import fetch_daily_report

_CONTRACT_TYPE_MAP = {"standard": 1, "variant": 2}

DerivativeProductCode = Literal[
    "HSI",
    "MHI",
    "PHS",
    "XHS",
    "HHI",
    "MCH",
    "PHH",
    "XHH",
    "HTI",
    "PTE",
    "HBI",
    "HGT",
    "HNT",
    "HHT",
    "HHN",
    "MBI",
    "VHS",
    "DHS",
    "DHH",
    "CHH",
    "GTI",
    "MCA",
    "CHI",
    "CHN",
    "MEI",
    "EMN",
    "MXC",
    "MXK",
    "EAN",
    "MAC",
    "MAK",
    "MEE",
    "MEL",
    "MXJ",
    "MJU",
    "MPC",
    "MPJ",
    "MAN",
    "MNZ",
    "MHK",
    "MND",
    "MIN",
    "MIA",
    "MDN",
    "MMA",
    "MMN",
    "MPS",
    "MPN",
    "MSG",
    "MSN",
    "MGN",
    "MTW",
    "MWN",
    "TWP",
    "TWN",
    "MTD",
    "MTN",
    "MVI",
    "MVN",
    "CUS",
    "MCS",
    "UCN",
    "CAU",
    "CEU",
    "CJP",
    "HB1",
    "HB3",
    "GDU",
    "GDR",
    "SIU",
    "SIR",
    "LUA",
    "LUC",
    "LUN",
    "LUP",
    "LUS",
    "LUZ",
    "LRA",
    "LRC",
    "LRN",
    "LRP",
    "LRS",
    "LRZ",
]


class HkexFuturesCurveQueryParams(FuturesCurveQueryParams):
    """HKEX Futures Curve query.

    Pass ``date`` as a single ``YYYY-MM-DD`` or a comma-separated list (or a
    list of strings) to pull historical curves from the HKEX daily market
    reports. Omit it for the live snapshot.
    """

    __json_schema_extra__ = {"date": {"multiple_items_allowed": True}}

    symbol: DerivativeProductCode = Field(
        description="HKEX derivatives product code (e.g. HSI, HHI, GDU, CUS). "
        "Run `obb.hkex.derivative_products()` for the full list.",
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


class HkexFuturesCurveData(FuturesCurveData):
    """HKEX Futures Curve data."""

    symbol: str | None = Field(
        default=None,
        description="Tenor slot from the snapshot date (M1 = front month, M2 = "
        "second, ...). Use this as the X-axis when overlaying curves from "
        "different dates — it lets curves line up even though the underlying "
        "expiration calendar has rolled.",
    )
    product: str | None = Field(
        default=None, description="HKEX product code (HSI, HHI, ...)."
    )
    open_interest: int | None = Field(default=None, description="Open interest.")
    volume: int | None = Field(default=None, description="Volume.")
    change_settle: float | None = Field(
        default=None,
        description="Change in settlement vs prior trading day (historical only).",
    )
    last_price: float | None = Field(default=None, description="Last traded price.")
    bid: float | None = Field(default=None, description="Bid price.")
    ask: float | None = Field(default=None, description="Ask price.")
    open: float | None = Field(default=None, description="Day open.")
    high: float | None = Field(default=None, description="Day high.")
    low: float | None = Field(default=None, description="Day low.")
    settlement_price: float | None = Field(
        default=None, description="Settlement price."
    )
    prev_close: float | None = Field(
        default=None, description="Prior-day settlement / previous close."
    )
    change: float | None = Field(default=None, description="Net change.")
    change_percent: float | None = Field(default=None, description="Percent change.")


class HkexFuturesCurveFetcher(
    Fetcher[HkexFuturesCurveQueryParams, list[HkexFuturesCurveData]]
):
    """HKEX Futures Curve fetcher."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> HkexFuturesCurveQueryParams:
        """Transform the query parameters."""
        return HkexFuturesCurveQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: HkexFuturesCurveQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the data from the HKEX endpoints."""
        if not query.date:
            live = await call_widget(
                "getderivativesfutures",
                ats=query.symbol,
                type=_CONTRACT_TYPE_MAP[query.contract_type],
            )
            today = dateType.today()
            return [
                {"_kind": "live", "as_of": today, **r}
                for r in live.get("futureslist") or []
            ]

        dates = _parse_dates(query.date)
        if not dates:
            return []

        async def _one(d: dateType) -> tuple[dateType, list[dict]]:
            return d, await fetch_daily_report(query.symbol, d)

        results = await asyncio.gather(*(_one(d) for d in dates))
        flat: list[dict] = []
        for d, rows in results:
            for r in rows:
                flat.append({"_kind": "hist", "as_of": d, **r})
        return flat

    @staticmethod
    def transform_data(
        query: HkexFuturesCurveQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[HkexFuturesCurveData]:
        """Transform the raw data into the model."""
        from collections import defaultdict

        grouped: dict[Any, list[dict]] = defaultdict(list)
        for r in data:
            grouped[r["as_of"]].append(r)

        out: list[HkexFuturesCurveData] = []
        for as_of, rows in grouped.items():
            ranked = _rank_by_expiration(rows, as_of)
            for i, r in enumerate(ranked, start=1):
                live = r.get("_kind") == "live"
                price = parse_num(r.get("ls")) if live else r.get("settle")
                if price is None:
                    continue
                pc = parse_num(r.get("pc")) if live else None
                out.append(
                    HkexFuturesCurveData(
                        date=as_of,
                        expiration=_expiration_label(r),
                        price=float(price),
                        symbol=f"M{i}",
                        product=query.symbol,
                        open_interest=(
                            parse_int(r.get("oi"))
                            if live
                            else _to_int(r.get("open_interest"))
                        ),
                        volume=(
                            parse_int(r.get("vo")) if live else _to_int(r.get("volume"))
                        ),
                        change_settle=None if live else r.get("change_settle"),
                        last_price=parse_num(r.get("ls")) if live else None,
                        bid=parse_num(r.get("bd")) if live else None,
                        ask=parse_num(r.get("as")) if live else None,
                        open=parse_num(r.get("op")) if live else r.get("day_open"),
                        high=parse_num(r.get("hi")) if live else r.get("day_high"),
                        low=parse_num(r.get("lo")) if live else r.get("day_low"),
                        settlement_price=parse_num(r.get("se"))
                        if live
                        else r.get("settle"),
                        prev_close=parse_num(r.get("hc")) if live else None,
                        change=parse_num(r.get("nc"))
                        if live
                        else r.get("change_settle"),
                        change_percent=(pc / 100 if pc is not None else None),
                    )
                )
        return out


_MONTHS = {
    m: i
    for i, m in enumerate(
        [
            "JAN",
            "FEB",
            "MAR",
            "APR",
            "MAY",
            "JUN",
            "JUL",
            "AUG",
            "SEP",
            "OCT",
            "NOV",
            "DEC",
        ],
        start=1,
    )
}


def _expiration_label(r: dict) -> str:
    """Return a stable contract-month label for a row from either source."""
    if r.get("_kind") == "live":
        return str(r.get("con_l") or r.get("con") or "").strip()
    return str(r.get("contract_month") or "").strip()


def _sort_key(label: str, as_of: dateType) -> tuple[int, int]:
    """Convert 'MAY-26' / 'May-2026' / 'MAY 2026' to (year, month) for sorting."""
    s = label.strip().upper().replace("-", " ")
    parts = s.split()
    if len(parts) < 2:
        return (9999, 99)
    mon = _MONTHS.get(parts[0][:3])
    yy = parts[1]
    try:
        year = int(yy) if len(yy) == 4 else 2000 + int(yy)
    except ValueError:
        return (9999, 99)
    if mon is None:
        return (9999, 99)
    return (year, mon)


def _rank_by_expiration(rows: list[dict], as_of: dateType) -> list[dict]:
    """Sort contracts by expiration so M1 is the nearest unexpired contract."""
    decorated = [(_sort_key(_expiration_label(r), as_of), r) for r in rows]
    cutoff = (as_of.year, as_of.month)
    decorated = [(k, r) for k, r in decorated if k >= cutoff]
    decorated.sort(key=lambda kr: kr[0])
    return [r for _, r in decorated]


def _to_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _parse_dates(value: Any) -> list[dateType]:
    """Normalize FuturesCurve.date into a list[date]."""
    if value is None:
        return []
    if isinstance(value, dateType):
        return [value]
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",") if p.strip()]
    elif isinstance(value, (list, tuple)):
        parts = [str(p).strip() for p in value if str(p).strip()]
    else:
        parts = [str(value)]
    out: list[dateType] = []
    for p in parts:
        try:
            out.append(datetime.strptime(p[:10], "%Y-%m-%d").date())
        except ValueError:
            continue
    return sorted(out)
