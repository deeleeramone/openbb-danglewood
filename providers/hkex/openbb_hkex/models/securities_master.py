"""HKEX Securities Master fetcher (custom model).

Wraps the daily ``ListOfSecurities.xlsx`` master file (~18k rows of every
listed instrument: equities, ETFs, REITs, warrants, CBBCs, bonds).
"""

from __future__ import annotations

import io
from typing import Any, Literal

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field

from openbb_hkex.utils.client import fetch_seclist_xlsx

SecuritiesMasterCategory = Literal[
    "Equity",
    "Exchange Traded Products",
    "Real Estate Investment Trusts",
    "Derivative Warrants",
    "Callable Bull/Bear Contracts",
    "Debt Securities",
]
SECURITIES_MASTER_CATEGORY_CHOICES: list[str] = list(
    SecuritiesMasterCategory.__args__  # type: ignore[attr-defined]
)

_COLS = [
    "code",
    "name",
    "category",
    "sub_category",
    "board_lot",
    "isin",
    "expiry",
    "stamp_duty",
    "shortsell",
    "cas",
    "vcm",
    "ccass",
    "debt_board_lot",
    "debt_investor_type",
    "pos",
    "spread_table",
    "ccy",
    "rmb_counter",
]
_FLAG_COLS = ("stamp_duty", "shortsell", "cas", "vcm", "ccass", "pos")
_SPREAD_TABLE_PART = {"1": "A", "3": "B", "5": "D", "4": "E", "6": "E"}


class HkexSecuritiesMasterQueryParams(QueryParams):
    """HKEX Securities Master query."""

    category: SecuritiesMasterCategory | None = Field(
        default=None,
        description="Filter by top-level security category from ListOfSecurities.xlsx.",
        json_schema_extra={"choices": SECURITIES_MASTER_CATEGORY_CHOICES},
    )
    code: str | None = Field(
        default=None,
        description="Optional 5-digit code filter (zero-padded). "
        "If set, returns just that one row.",
    )


class HkexSecuritiesMasterData(Data):
    """HKEX Securities Master row.

    Flag columns (cas / pos / vcm / ccass / shortsell / stamp_duty) are
    normalized to bool. ``spread_table`` is mapped to its part letter
    (``'A'`` most equities, ``'B'`` high-priced, ``'D'`` DWs/CBBCs,
    ``'E'`` low-priced incl. GEM).
    """

    code: str = Field(description="5-digit HKEX stock code (zero-padded).")
    name: str = Field(description="Short name of the security.")
    category: str | None = Field(default=None, description="Top-level type.")
    sub_category: str | None = Field(default=None, description="Sub-classification.")
    board_lot: int | None = Field(default=None, description="Trading lot size.")
    isin: str | None = Field(default=None, description="ISIN code.")
    expiry: str | None = Field(
        default=None, description="Expiry for derivatives; None for equities/REITs."
    )
    stamp_duty: bool = Field(
        default=False, description="Subject to HK stamp duty (0.1% per side)."
    )
    shortsell: bool = Field(
        default=False,
        description="On the Designated Securities Eligible for Short Selling list.",
    )
    cas: bool = Field(default=False, description="Closing Auction Session eligible.")
    vcm: bool = Field(
        default=False, description="Volatility Control Mechanism eligible."
    )
    ccass: bool = Field(default=False, description="Admitted to CCASS for clearing.")
    debt_board_lot: int | None = Field(
        default=None, description="Nominal board lot for debt securities."
    )
    debt_investor_type: str | None = Field(
        default=None, description="'Professional' (PI-only) or 'Public' (retail)."
    )
    pos: bool = Field(default=False, description="Pre-Opening Session eligible.")
    spread_table: str | None = Field(
        default=None, description="Minimum tick-size table letter (A/B/D/E)."
    )
    ccy: str | None = Field(default=None, description="Trading currency.")
    rmb_counter: str | None = Field(
        default=None, description="Paired RMB counter code if dual-counter listed."
    )


class HkexSecuritiesMasterFetcher(
    Fetcher[HkexSecuritiesMasterQueryParams, list[HkexSecuritiesMasterData]]
):
    """HKEX Securities Master fetcher."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> HkexSecuritiesMasterQueryParams:
        """Transform the query parameters."""
        return HkexSecuritiesMasterQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: HkexSecuritiesMasterQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the data from the HKEX endpoints."""
        try:
            import openpyxl  # noqa: F401
        except ImportError as e:
            from openbb_core.app.model.abstract.error import OpenBBError

            raise OpenBBError(
                "openpyxl is required for the HKEX securities master "
                "(`pip install openpyxl`)."
            ) from e
        blob = await fetch_seclist_xlsx()
        import openpyxl as ox

        wb = ox.load_workbook(io.BytesIO(blob), data_only=True)
        ws = wb.active
        out: list[dict] = []
        for row in ws.iter_rows(min_row=4, values_only=True):
            if row[0] is None:
                continue
            rec = dict(zip(_COLS, row))
            if query.category and rec.get("category") != query.category:
                continue
            if query.code and str(rec.get("code")) != query.code.zfill(5):
                continue
            out.append(rec)
        return out

    @staticmethod
    def transform_data(
        query: HkexSecuritiesMasterQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[HkexSecuritiesMasterData]:
        """Transform the raw data into the model."""
        rows: list[HkexSecuritiesMasterData] = []
        for rec in data:
            normalized = dict(rec)
            for c in _FLAG_COLS:
                v = normalized.get(c)
                normalized[c] = v == "Y" if isinstance(v, str) else False
            st = normalized.get("spread_table")
            if isinstance(st, str):
                normalized["spread_table"] = _SPREAD_TABLE_PART.get(
                    st.strip(), st.strip()
                )
            for int_col in ("board_lot", "debt_board_lot"):
                v = normalized.get(int_col)
                if v is not None:
                    try:
                        normalized[int_col] = int(v)
                    except (TypeError, ValueError):
                        normalized[int_col] = None
            normalized["expiry"] = (
                str(normalized["expiry"]) if normalized.get("expiry") else None
            )
            rows.append(HkexSecuritiesMasterData(**normalized))
        return rows
