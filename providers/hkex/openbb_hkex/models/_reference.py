"""Shared HKEX security reference metadata."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from openbb_core.provider.abstract.data import Data
from pydantic import Field

_MULT = {"B": 1_000_000_000, "M": 1_000_000, "K": 1_000, "T": 1_000_000_000_000}


def parse_num(s: Any) -> float | None:
    """Parse an HKEX-formatted number string ('143.900', '17,936', '') to float."""
    if s is None or s in {"", "-", "—"}:
        return None
    try:
        return float(str(s).replace(",", ""))
    except (TypeError, ValueError):
        return None


def clean_addr(s: str | None) -> str | None:
    """Collapse the ``<br/>``-delimited HKEX address blob into one line."""
    if not s:
        return None
    return re.sub(r"\s*<br\s*/?>\s*", ", ", s).strip(", ").strip() or None


def parse_hk_date(s: str | None) -> str | None:
    """Parse '16 Jun 2004' → ISO 'YYYY-MM-DD'; pass through on failure."""
    if not s or s.strip() in ("-", ""):
        return None
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return s.strip()


def scaled(value: str | None, unit: str | None) -> float | None:
    """Combine '3,875.17' + 'B' → 3875170000000.0."""
    v = parse_num(value)
    if v is None:
        return None
    return v * _MULT.get((unit or "").strip().upper(), 1)


def to_int(value: str | None) -> int | None:
    """Parse an HKEX numeric string to int, or None."""
    v = parse_num(value)
    return int(v) if v is not None else None


def extract_reference(q: dict) -> dict[str, Any]:
    """Decode a ``getequityquote`` quote block into reference-metadata kwargs."""
    counters = q.get("multiple_counter") or []
    rmb_counter = counters[0].get("counter_sym") if counters else None
    return {
        "isin": q.get("isin") or None,
        "sedol": q.get("sedol") or None,
        "product_type": q.get("product_type") or None,
        "sector": q.get("hsic_ind_classification") or None,
        "industry_category": q.get("hsic_sub_sector_classification") or None,
        "stock_exchange": q.get("primaryexch") or None,
        "listing_category": q.get("listing_category") or None,
        "listing_date": parse_hk_date(q.get("listing_date")),
        "currency": q.get("ccy") or None,
        "board_lot": to_int(q.get("lot")),
        "tick_size": parse_num(q.get("tck")),
        "shares_outstanding": parse_num(q.get("amt_os")),
        "shares_issued_date": parse_hk_date(q.get("shares_issued_date")),
        "fiscal_year_end": parse_hk_date(q.get("fiscal_year_end")),
        "rmb_counter": rmb_counter,
        "legal_name": q.get("issuer_name") or None,
        "chairman": q.get("chairman") or None,
        "registrar": q.get("registrar") or None,
        "inc_country": q.get("incorpin") or None,
        "entity_status": "Active" if q.get("trdstatus") else None,
        "management_fee": parse_num(q.get("management_fee")),
        "underlying_index": q.get("underlying_index") or None,
        "replication_method": q.get("replication_method") or None,
        "inception_date": parse_hk_date(q.get("inception_date")),
        "asset_class": q.get("asset_class") or None,
        "geographic_focus": q.get("geographic_focus") or None,
        "business_address": clean_addr(q.get("office_address")),
        "short_description": q.get("investmentDesc") or None,
        "long_description": q.get("summary") or None,
    }


def extract_fundamentals(q: dict) -> dict[str, Any]:
    """Decode point-in-time valuation / fundamentals from a quote block."""
    return {
        "market_cap": scaled(q.get("mkt_cap"), q.get("mkt_cap_u")),
        "eps": parse_num(q.get("eps")),
        "eps_currency": q.get("eps_ccy") or None,
        "pe_ratio": parse_num(q.get("pe")),
        "dividend_yield": parse_num(q.get("div_yield")),
        "aum": scaled(q.get("aum"), q.get("aum_u")),
        "nav": parse_num(q.get("nav")),
    }


class HkexEquityReference(Data):
    """Non-price reference metadata shared by Equity Info and Equity Search."""

    isin: str | None = Field(default=None, description="ISIN identifier.")
    sedol: str | None = Field(default=None, description="SEDOL identifier.")
    product_type: str | None = Field(
        default=None, description="HKEX product type: EQTY / ETP / REIT."
    )
    sector: str | None = Field(
        default=None, description="HSIC industry classification."
    )
    industry_category: str | None = Field(
        default=None, description="HSIC sub-sector classification."
    )
    stock_exchange: str | None = Field(
        default=None, description="Primary listing venue."
    )
    listing_category: str | None = Field(
        default=None, description="Primary or Secondary Listing."
    )
    listing_date: str | None = Field(default=None, description="Date of listing (ISO).")
    currency: str | None = Field(default=None, description="Trading currency.")
    board_lot: int | None = Field(default=None, description="Board lot size.")
    tick_size: float | None = Field(default=None, description="Minimum tick size.")
    shares_outstanding: float | None = Field(
        default=None, description="Total shares/units in issue."
    )
    shares_issued_date: str | None = Field(
        default=None, description="As-at date for shares issued (ISO)."
    )
    fiscal_year_end: str | None = Field(default=None, description="Fiscal year end.")
    rmb_counter: str | None = Field(
        default=None, description="Paired RMB/CNY counter code, if dual-counter listed."
    )
    legal_name: str | None = Field(default=None, description="Issuer / legal name.")
    chairman: str | None = Field(default=None, description="Chairman of the board.")
    registrar: str | None = Field(default=None, description="Share registrar.")
    inc_country: str | None = Field(
        default=None, description="Country of incorporation."
    )
    entity_status: str | None = Field(default=None, description="Trading status.")
    management_fee: float | None = Field(
        default=None, description="Management fee, percent (ETP)."
    )
    underlying_index: str | None = Field(
        default=None, description="Tracked index (ETP)."
    )
    replication_method: str | None = Field(
        default=None, description="Physical or synthetic replication (ETP)."
    )
    inception_date: str | None = Field(
        default=None, description="Fund inception date, ISO (ETP)."
    )
    asset_class: str | None = Field(default=None, description="Asset class (ETP).")
    geographic_focus: str | None = Field(
        default=None, description="Geographic focus (ETP)."
    )
    business_address: str | None = Field(
        default=None, description="Registered office address."
    )
    short_description: str | None = Field(
        default=None, description="Short investment description (ETPs)."
    )
    long_description: str | None = Field(default=None, description="Business summary.")
