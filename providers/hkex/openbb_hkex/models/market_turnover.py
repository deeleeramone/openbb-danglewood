"""HKEX Market Turnover fetcher (custom model — daily aggregate)."""

from __future__ import annotations

from typing import Any

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field

from openbb_hkex.utils.client import call_widget, parse_num


class HkexMarketTurnoverQueryParams(QueryParams):
    """HKEX Market Turnover query (no parameters; latest figures only)."""


class HkexMarketTurnoverData(Data):
    """HKEX Market Turnover data."""

    date: str = Field(description="Trading date (DD/MM/YYYY).")
    last_update: str | None = Field(
        default=None, description="Source-reported timestamp."
    )
    main_board_turnover: float | None = Field(
        default=None, description="Main board turnover value."
    )
    main_board_unit: str | None = Field(
        default=None, description="Main board unit ('B' = billion, 'M' = million)."
    )
    gem_turnover: float | None = Field(
        default=None, description="GEM board turnover value."
    )
    gem_unit: str | None = Field(default=None, description="GEM unit.")
    derivatives_day_volume: int | None = Field(
        default=None, description="Derivatives day-session volume (contracts)."
    )
    derivatives_night_volume: int | None = Field(
        default=None, description="Derivatives night-session volume (contracts)."
    )


class HkexMarketTurnoverFetcher(
    Fetcher[HkexMarketTurnoverQueryParams, list[HkexMarketTurnoverData]]
):
    """HKEX Market Turnover fetcher."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> HkexMarketTurnoverQueryParams:
        """Transform the query parameters."""
        return HkexMarketTurnoverQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: HkexMarketTurnoverQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the data from the HKEX endpoints."""
        return [await call_widget("getmarketturnover")]

    @staticmethod
    def transform_data(
        query: HkexMarketTurnoverQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[HkexMarketTurnoverData]:
        """Transform the raw data into the model."""
        out: list[HkexMarketTurnoverData] = []
        for r in data:
            boards = r.get("boardlist") or {}
            deriv = (r.get("marketlist") or {}).get("deriv") or {}

            def _int_or_none(v: Any) -> int | None:
                if v is None:
                    return None
                n = parse_num(v)
                return int(n) if n is not None else None

            out.append(
                HkexMarketTurnoverData(
                    date=r.get("date", ""),
                    last_update=r.get("lastupdate"),
                    main_board_turnover=parse_num((boards.get("main") or {}).get("v")),
                    main_board_unit=(boards.get("main") or {}).get("u"),
                    gem_turnover=parse_num((boards.get("gem") or {}).get("v")),
                    gem_unit=(boards.get("gem") or {}).get("u"),
                    derivatives_day_volume=_int_or_none(deriv.get("d")),
                    derivatives_night_volume=_int_or_none(deriv.get("n")),
                )
            )
        return out
