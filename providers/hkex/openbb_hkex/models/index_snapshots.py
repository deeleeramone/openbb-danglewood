"""HKEX Index Snapshots fetcher (IndexSnapshots standard model)."""

from __future__ import annotations

import asyncio
from typing import Any, Literal

from openbb_core.app.model.abstract.error import OpenBBError
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.index_snapshots import (
    IndexSnapshotsData,
    IndexSnapshotsQueryParams,
)
from pydantic import Field

from openbb_hkex.models.index_historical import INDEX_RICS
from openbb_hkex.utils.client import call_widget, parse_num


class HkexIndexSnapshotsQueryParams(IndexSnapshotsQueryParams):
    """HKEX Index Snapshots query."""

    region: Literal["hk"] = Field(
        default="hk",
        description="HKEX only serves Hong Kong indices.",
        json_schema_extra={
            "choices": ["hk"],
            "hkex": {"x-widget_config": {"show": False}},
        },
    )


class HkexIndexSnapshotsData(IndexSnapshotsData):
    """HKEX Index Snapshots data."""


class HkexIndexSnapshotsFetcher(
    Fetcher[HkexIndexSnapshotsQueryParams, list[HkexIndexSnapshotsData]]
):
    """HKEX Index Snapshots fetcher."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> HkexIndexSnapshotsQueryParams:
        """Transform the query parameters."""
        params.setdefault("region", "hk")
        return HkexIndexSnapshotsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: HkexIndexSnapshotsQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the data from the HKEX endpoints."""
        try:
            data = await call_widget("getmarketoverview")
        except OpenBBError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise OpenBBError(
                f"HKEX market overview is temporarily unavailable: {exc}"
            ) from exc
        rows = list(data.get("indices") or [])
        present = {r.get("ric") for r in rows}
        missing = [ric for ric in INDEX_RICS if ric not in present]

        async def _snapshot(ric: str) -> dict | None:
            try:
                d = await call_widget(
                    "getchartdata2", hchart=1, span=6, ric=ric, **{"int": 1}
                )
            except Exception:  # noqa: BLE001
                return None
            bars = [b for b in (d.get("datalist") or []) if b and b[1] is not None]
            if not bars:
                return None
            last = bars[-1]
            prev_close = bars[-2][4] if len(bars) > 1 else None
            close = last[4]
            nc = (
                close - prev_close
                if close is not None and prev_close is not None
                else None
            )
            pc = nc / prev_close * 100 if nc is not None and prev_close else None
            return {
                "ric": ric,
                "nm_l": INDEX_RICS[ric],
                "ls": close,
                "op": last[1],
                "hi": last[2],
                "lo": last[3],
                "hc": prev_close,
                "nc": nc,
                "pc": pc,
            }

        extra = await asyncio.gather(*(_snapshot(r) for r in missing))
        rows.extend(e for e in extra if e)
        return rows

    @staticmethod
    def transform_data(
        query: HkexIndexSnapshotsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[HkexIndexSnapshotsData]:
        """Transform the raw data into the model."""
        rows: list[HkexIndexSnapshotsData] = []
        for r in data:
            change = parse_num(r.get("nc"))
            chg_pct = parse_num(r.get("pc"))
            rows.append(
                HkexIndexSnapshotsData(
                    symbol=(r.get("ric") or r.get("nm_s") or "").lstrip("."),
                    name=r.get("nm_l") or r.get("nm_s"),
                    currency=None,
                    price=parse_num(r.get("ls")),
                    open=parse_num(r.get("op")),
                    high=parse_num(r.get("hi")),
                    low=parse_num(r.get("lo")),
                    close=parse_num(r.get("ls")),
                    prev_close=parse_num(r.get("hc")),
                    change=change,
                    change_percent=(chg_pct / 100) if chg_pct is not None else None,
                )
            )
        return rows
