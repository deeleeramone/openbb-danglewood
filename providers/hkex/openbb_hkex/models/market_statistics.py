"""HKEX Market Statistics fetcher (custom aggregate model).

Aggregates the listed universe into counts, market capitalisation and turnover
grouped by trading venue, programme, or Hang Seng / China industry sector.

Two programmes are distinguished:
  * **HKEX** — securities listed on the Main Board and GEM (reported in HKD).
  * **Stock Connect** — A-shares eligible via Shanghai / Shenzhen Connect
    (reported in CNY).

Because the two programmes trade in different currencies, market-cap
percentages are computed *within a currency basis* (HKD for HKEX, CNY for
Connect); ``count_pct`` is share of the total instrument count.

The sector grouping (HSIC top level: Financials, Energy, etc.) covers the Hang
Seng Composite universe (HKEX-listed equities, ~95% of market cap) and is
sourced from the Hang Seng Composite Industry sub-index constituents — a handful
of cached calls, never a per-symbol crawl. The finer *industry* level is not
exposed (it lives only on the per-symbol quote, which is deliberately not
crawled).
"""

from __future__ import annotations

from typing import Any, Literal

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field

from openbb_hkex.utils.aggregates import (
    PRIMARY_CCY,
    get_ashare_universe,
    get_equity_universe,
    get_sector_map,
    is_rmb_counter,
)

GroupBy = Literal["venue", "programme", "currency", "sector"]
GROUP_BY_CHOICES: list[str] = list(GroupBy.__args__)  # type: ignore[attr-defined]

Programme = Literal["all", "hkex", "connect"]
PROGRAMME_CHOICES: list[str] = list(Programme.__args__)  # type: ignore[attr-defined]

# Groupings that rely on Hang Seng sector classification (HKEX equities only).
_CLASSIFICATION_GROUPS = {"sector"}


class HkexMarketStatisticsQueryParams(QueryParams):
    """HKEX Market Statistics query."""

    group_by: GroupBy = Field(
        default="venue",
        description=(
            "Dimension to aggregate by: 'venue' (Main Board / GEM / Shanghai / "
            "Shenzhen), 'programme' (HKEX vs Stock Connect), 'currency', or "
            "'sector' (Hang Seng sector, HKEX equities only)."
        ),
        json_schema_extra={"choices": GROUP_BY_CHOICES},
    )
    programme: Programme = Field(
        default="all",
        description="Restrict to 'hkex', 'connect', or 'all' listed securities.",
        json_schema_extra={"choices": PROGRAMME_CHOICES},
    )


class HkexMarketStatisticsData(Data):
    """One aggregate group of the HKEX / Stock Connect listed universe."""

    group: str = Field(description="The group label for the chosen dimension.")
    programme: str | None = Field(
        default=None, description="Listing programme (HKEX / Stock Connect)."
    )
    currency: str | None = Field(
        default=None, description="Currency basis of the reported market cap."
    )
    count: int = Field(description="Number of securities in the group.")
    count_pct: float | None = Field(
        default=None, description="Share of total instrument count, percent."
    )
    market_cap: float | None = Field(
        default=None, description="Total market capitalisation (currency basis)."
    )
    market_cap_pct: float | None = Field(
        default=None,
        description="Share of total market cap within the same currency basis, percent.",
    )
    turnover: float | None = Field(
        default=None, description="Total day turnover (currency basis)."
    )


class HkexMarketStatisticsFetcher(
    Fetcher[HkexMarketStatisticsQueryParams, list[HkexMarketStatisticsData]]
):
    """HKEX Market Statistics fetcher."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> HkexMarketStatisticsQueryParams:
        """Transform the query parameters."""
        return HkexMarketStatisticsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: HkexMarketStatisticsQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the data from the HKEX endpoints."""
        rows: list[dict] = []
        want_classification = query.group_by in _CLASSIFICATION_GROUPS

        if query.programme in ("all", "hkex"):
            # Drop RMB dual-trading counters so a company is counted once.
            equities = [
                r
                for r in await get_equity_universe()
                if not is_rmb_counter(r["symbol"])
            ]
            if want_classification:
                sectors = await get_sector_map()
                rows.extend({**r, **(sectors.get(r["symbol"]) or {})} for r in equities)
            else:
                rows.extend(equities)

        # Classification has no Stock Connect coverage; skip A-shares for it.
        if query.programme in ("all", "connect") and not want_classification:
            rows.extend(await get_ashare_universe())

        return rows

    @staticmethod
    def transform_data(
        query: HkexMarketStatisticsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[HkexMarketStatisticsData]:
        """Transform the raw data into the model."""
        key = query.group_by

        default_label = "Unclassified" if key in _CLASSIFICATION_GROUPS else "Other"
        groups: dict[str, dict[str, Any]] = {}
        for r in data:
            label = r.get(key) or default_label
            g = groups.setdefault(
                label,
                {
                    "count": 0,
                    "market_cap": 0.0,
                    "turnover": 0.0,
                    "programme": r.get("programme"),
                },
            )
            g["count"] += 1
            if r.get("market_cap"):
                g["market_cap"] += r["market_cap"]
            if r.get("turnover"):
                g["turnover"] += r["turnover"]
            g["programme"] = g["programme"] or r.get("programme")

        def _basis(label: str, programme: str | None) -> str:
            # When grouping by currency the group IS one currency; otherwise the
            # programme's primary currency (HKEX -> HKD, Connect -> CNY).
            if key == "currency":
                return label
            return PRIMARY_CCY.get(programme or "", programme or "")

        total_count = sum(g["count"] for g in groups.values()) or 1
        # Market-cap % is computed within a currency basis so the two programmes
        # are never summed across currencies.
        ccy_totals: dict[str, float] = {}
        for label, g in groups.items():
            basis = _basis(label, g["programme"])
            ccy_totals[basis] = ccy_totals.get(basis, 0.0) + g["market_cap"]

        out: list[HkexMarketStatisticsData] = []
        for label, g in groups.items():
            basis = _basis(label, g["programme"])
            basis_total = ccy_totals.get(basis, 0.0)
            out.append(
                HkexMarketStatisticsData(
                    group=label,
                    programme=None if key == "currency" else g["programme"],
                    currency=basis,
                    count=g["count"],
                    count_pct=round(100.0 * g["count"] / total_count, 2),
                    market_cap=round(g["market_cap"], 2) or None,
                    market_cap_pct=(
                        round(100.0 * g["market_cap"] / basis_total, 2)
                        if basis_total
                        else None
                    ),
                    turnover=round(g["turnover"], 2) or None,
                )
            )
        out.sort(key=lambda d: d.market_cap or 0.0, reverse=True)
        return out
