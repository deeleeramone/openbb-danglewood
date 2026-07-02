"""HKEX Index Constituents fetcher (IndexConstituents standard model).

Constituents and weightings for a Hang Seng index. The full constituent list is
sourced from Hang Seng Indexes Company's ``constituents.do`` feed; per-constituent
weights come from the official index factsheet (top-50 only — constituents beyond
the top 50 carry ``weight=None``).
"""

from __future__ import annotations

from typing import Any

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.index_constituents import (
    IndexConstituentsData,
    IndexConstituentsQueryParams,
)
from pydantic import Field

from openbb_hkex.utils.index_sources import (
    CONSTITUENT_INDEXES,
    fetch_index_constituents,
    normalize_ric,
)


class HkexIndexConstituentsQueryParams(IndexConstituentsQueryParams):
    """HKEX Index Constituents query. ``symbol`` is a Hang Seng index RIC."""

    symbol: str = Field(
        default=".HSI",
        description="Hang Seng index RIC (leading dot optional). "
        f"Supported: {', '.join(CONSTITUENT_INDEXES)}.",
        json_schema_extra={"choices": [r.lstrip(".") for r in CONSTITUENT_INDEXES]},
    )


class HkexIndexConstituentsData(IndexConstituentsData):
    """HKEX Index Constituents row."""

    symbol: str = Field(
        description="HKEX security code.",
        json_schema_extra={"x-widget_config": {"cellDataType": "text"}},
    )
    weight: float | None = Field(
        default=None,
        description="Index weighting, percent (factsheet top-50 only; "
        "None for constituents beyond the top 50).",
    )
    isin: str | None = Field(default=None, description="ISIN identifier.")
    sector: str | None = Field(
        default=None, description="Hang Seng industry classification."
    )
    share_class: str | None = Field(
        default=None,
        description="Share-class code: O ordinary, H H-share, R red-chip, A A-share.",
    )
    share_type: str | None = Field(
        default=None, description="Factsheet share-type label (e.g. 'H Share')."
    )


class HkexIndexConstituentsFetcher(
    Fetcher[HkexIndexConstituentsQueryParams, list[HkexIndexConstituentsData]]
):
    """HKEX Index Constituents fetcher."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> HkexIndexConstituentsQueryParams:
        """Transform the query parameters."""
        return HkexIndexConstituentsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: HkexIndexConstituentsQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the data from the HKEX endpoints."""
        return await fetch_index_constituents(normalize_ric(query.symbol))

    @staticmethod
    def transform_data(
        query: HkexIndexConstituentsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[HkexIndexConstituentsData]:
        """Transform the raw data into the model."""
        rows: list[HkexIndexConstituentsData] = []
        for row in data:
            sym = str(row.get("symbol") or "")
            item = {**row, "symbol": sym.zfill(5)} if sym.isdigit() else row
            rows.append(HkexIndexConstituentsData(**item))
        return rows
