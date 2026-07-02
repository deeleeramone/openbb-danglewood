"""HKEX Daily Market Report — authoritative historical settlement archive.

For every trading day, HKEX publishes per-product fixed-width text reports at::

    https://www.hkex.com.hk/eng/stat/dmstat/dayrpt/<prefix><yymmdd>.htm

Each report contains, per contract month, the day's official **Settlement
Price**, change in settlement, contract high/low, combined volume, open
interest, and change in OI — the same data the FSP page displays.

This module:
  * Maps HKEX product (ATS) codes to their report-file prefixes.
  * Fetches a per-product report for a given date.
  * Parses the fixed-width text into structured rows.
"""

from __future__ import annotations

import re
from datetime import (
    date as dateType,
    datetime,
    timedelta,
)
from typing import Any

from async_lru import alru_cache
from openbb_core.provider.utils.helpers import amake_request

from openbb_hkex.utils.client import USER_AGENT, _text_callback

DAILY_REPORT_BASE = "https://www.hkex.com.hk/eng/stat/dmstat/dayrpt"
STOCK_OPTIONS_REPORT = "dqe"

PRODUCT_TO_PREFIX: dict[str, str] = {
    "HSI": "hsif",
    "MHI": "mhif",
    "HHI": "hhif",
    "MCH": "mchf",
    "HTI": "htif",
    "HBI": "hbif",
    "HGT": "trif",
    "HHT": "trif",
    "VHS": "vhsf",
    "CHH": "chhf",
    "PHS": "hsio",
    "PHH": "hhio",
    "PTE": "pteo",
    "XHS": "xhso",
    "XHH": "xhho",
    "CUS": "cusf",
    "MCS": "mcsf",
    "UCN": "ucnf",
    "GDU": "gduf",
    "GDR": "gdrf",
    "SIU": "siuf",
    "SIR": "sirf",
    "HB1": "hibor",
    "HB3": "hibor",
    "MXJ": "mxjf",
}


def _fmt_yymmdd(d: dateType) -> str:
    return d.strftime("%y%m%d")


def report_url(product_code: str, d: dateType, session: str = "combined") -> str | None:
    """Build the daily-report URL for a product + date.

    ``session`` is ``'combined'`` (default — the `<prefix>.htm` file which holds
    settlement plus combined-day-and-AH activity) or ``'ah'`` for the
    after-hours-only file `<prefix>a.htm`.
    """
    prefix = PRODUCT_TO_PREFIX.get(product_code.upper())
    if not prefix:
        return None
    suffix = "a" if session == "ah" else ""
    return f"{DAILY_REPORT_BASE}/{prefix}{suffix}{_fmt_yymmdd(d)}.htm"


_NUM = re.compile(r"[+-]?[\d,]+(?:\.\d+)?")


def _parse_num(s: str) -> float | None:
    s = s.strip()
    if not s:
        return None
    if s == "0":
        return 0.0
    if not _NUM.fullmatch(s):
        return None
    try:
        return float(s.replace(",", "").lstrip("+"))
    except ValueError:
        return None


def parse_report(text: str) -> list[dict[str, Any]]:
    """Parse the ``<PRE>`` block of a daily report into structured rows.

    Returns a list of dicts: ``{"contract_month", "settle", "change_settle",
    "contract_high", "contract_low", "volume", "open_interest", "change_oi",
    "day_open", "day_high", "day_low", "day_volume",
    "ah_open", "ah_high", "ah_low", "ah_close", "ah_volume"}``.
    """
    m = re.search(r"<PRE>([\s\S]*?)</?(?:BODY|PRE)>", text, re.I)
    body = m.group(1) if m else text
    rows: list[dict[str, Any]] = []
    contract_re = re.compile(
        r"^\s*([A-Z]{3}-\d{2,4}[A-Z]?(?:\s*[CP]\s*[\d,]+)?)\s+"
        r"(.*)$"
    )
    for line in body.splitlines():
        m2 = contract_re.match(line)
        if not m2:
            continue
        contract_month = re.sub(r"\s+", " ", m2.group(1)).strip()
        rest = m2.group(2)
        sections = [s.strip() for s in rest.split("|")]
        if len(sections) < 2:
            continue

        def _tokens(s: str) -> list[str]:
            return s.split()

        ah = _tokens(sections[0]) if len(sections) >= 1 else []
        day = _tokens(sections[1]) if len(sections) >= 2 else []
        combined = _tokens(sections[2]) if len(sections) >= 3 else []

        ah_open, ah_high, ah_low, ah_close, ah_vol = (ah + [None] * 5)[:5]
        day_open, day_high, day_low, day_vol, settle, change_settle = (
            day + [None] * 6
        )[:6]
        c_high, c_low, c_vol, c_oi, c_chg_oi = (combined + [None] * 5)[:5]

        rows.append(
            {
                "contract_month": contract_month,
                "ah_open": _parse_num(ah_open) if ah_open else None,
                "ah_high": _parse_num(ah_high) if ah_high else None,
                "ah_low": _parse_num(ah_low) if ah_low else None,
                "ah_close": _parse_num(ah_close) if ah_close else None,
                "ah_volume": _parse_num(ah_vol) if ah_vol else None,
                "day_open": _parse_num(day_open) if day_open else None,
                "day_high": _parse_num(day_high) if day_high else None,
                "day_low": _parse_num(day_low) if day_low else None,
                "day_volume": _parse_num(day_vol) if day_vol else None,
                "settle": _parse_num(settle) if settle else None,
                "change_settle": _parse_num(change_settle) if change_settle else None,
                "contract_high": _parse_num(c_high) if c_high else None,
                "contract_low": _parse_num(c_low) if c_low else None,
                "volume": _parse_num(c_vol) if c_vol else None,
                "open_interest": _parse_num(c_oi) if c_oi else None,
                "change_oi": _parse_num(c_chg_oi) if c_chg_oi else None,
            }
        )
    return rows


_MULTIPLIER_PREFIX: dict[str, str] = {
    "HSI": "hsif",
    "MHI": "mhif",
    "PHS": "hsif",
    "XHS": "hsif",
    "HHI": "hhif",
    "MCH": "mchf",
    "PHH": "hhif",
    "XHH": "hhif",
    "HTI": "htif",
    "PTE": "htif",
    "HBI": "hbif",
    "VHS": "vhsf",
    "CHH": "chhf",
}

_POINT_VALUE_RE = re.compile(
    r"(HK\$|US\$|USD|RMB|CNH)\s*([\d,]+(?:\.\d+)?)\s*per\s+index\s+point",
    re.I,
)

_point_value_cache: dict[str, dict[str, Any] | None] = {}


def _parse_point_value(text: str) -> dict[str, Any] | None:
    """Extract '(HK$)50 per index point' from a report header → {ccy, value}."""
    m = re.search(r"<PRE>([\s\S]{0,800})", text, re.I)
    block = m.group(1) if m else text[:800]
    hit = _POINT_VALUE_RE.search(block)
    if not hit:
        return None
    ccy = hit.group(1).upper().replace("$", "D")
    return {"currency": ccy, "value": float(hit.group(2).replace(",", ""))}


async def index_point_value(product_code: str) -> dict[str, Any] | None:
    """Return the HKEX-published per-index-point contract multiplier.

    ``{"currency": "HKD", "value": 50.0}`` for HSI/HHI/HTI, ``10.0`` for the
    mini contracts, etc. Sourced from the product's daily futures-report header
    ("HSI - Hang Seng Index Futures HK$50 per index point") — the authoritative
    HKEX statement of the contract spec. Cached; walks back up to 8 days to
    find the latest published report.
    """
    code = product_code.upper()
    if code in _point_value_cache:
        return _point_value_cache[code]
    prefix = _MULTIPLIER_PREFIX.get(code)
    if not prefix:
        _point_value_cache[code] = None
        return None
    from datetime import timedelta

    today = dateType.today()
    for back in range(0, 8):
        d = today - timedelta(days=back)
        url = f"{DAILY_REPORT_BASE}/{prefix}{_fmt_yymmdd(d)}.htm"
        try:
            text = await amake_request(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"},
                response_callback=_text_callback,
            )
        except Exception:  # noqa: BLE001,S112 — try the previous trading day
            continue
        if "<PRE>" not in text.upper():
            continue
        pv = _parse_point_value(text)
        if pv:
            _point_value_cache[code] = pv
            return pv
    _point_value_cache[code] = None
    return None


async def fetch_daily_report(
    product_code: str, d: dateType, session: str = "combined"
) -> list[dict[str, Any]]:
    """Fetch and parse a daily HKEX market report for a product + date.

    Returns ``[]`` if the product has no published report prefix, the date
    isn't a Hong Kong trading day, or the report file doesn't exist.
    """
    url = report_url(product_code, d, session=session)
    if not url:
        return []
    try:
        text = await amake_request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"},
            response_callback=_text_callback,
        )
    except Exception:
        return []
    if "<PRE>" not in text.upper():
        return []
    return parse_report(text)


_OPT_ROW = re.compile(
    r"^(\d{2}[A-Z]{3}\d{2})\s+([\d,]+\.\d+)\s+([CP])\s+"
    r"([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)"
    r"\s+\S+\s+([\d,]+)",
    re.M,
)
_OPT_CLOSE = re.compile(r"CLOSING PRICE\s+HK\$\s+([\d,]+\.\d+)")


@alru_cache(maxsize=4)
async def _fetch_stock_option_report(yymmdd: str) -> str | None:
    url = f"{DAILY_REPORT_BASE}/{STOCK_OPTIONS_REPORT}{yymmdd}.htm"
    try:
        text = await amake_request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"},
            response_callback=_text_callback,
        )
    except Exception:  # noqa: BLE001
        return None
    return text if text and "STOCK OPTIONS DAILY MARKET REPORT" in text else None


def _num(s: str) -> float | None:
    try:
        return float(s.replace(",", ""))
    except (TypeError, ValueError):
        return None


def parse_stock_option_settlements(text: str, ats: str) -> dict[tuple, dict]:
    """Parse a class's per-strike settlements from the dqe report.

    Returns ``{(expiry_date, strike, side): {open, high, low, close, volume}}``
    plus an ``underlying`` entry ``{("underlying",): close}``.
    """
    plain = re.sub(r"<[^>]+>", "", text)
    start = plain.find(f"CLASS {ats.upper()} - ")
    if start < 0:
        return {}
    end = plain.find("CLASS ", start + 1)
    seg = plain[start : end if end > 0 else len(text)]
    out: dict[tuple, dict] = {}
    uc = _OPT_CLOSE.search(seg)
    if uc:
        out[("underlying",)] = {"close": _num(uc.group(1))}
    for m in _OPT_ROW.finditer(seg):
        exp, strike, side, o, h, low, settle, vol = m.groups()
        sk = _num(strike)
        if sk is None:
            continue
        try:
            d = datetime.strptime(exp.title(), "%d%b%y").date()
        except ValueError:
            continue
        out[(d, round(sk, 3), "call" if side == "C" else "put")] = {
            "open": _num(o),
            "high": _num(h),
            "low": _num(low),
            "close": _num(settle),
            "volume": _num(vol),
        }
    return out


async def stock_option_settlements(ats: str) -> dict[tuple, dict]:
    """Latest available per-strike settlements for a stock-option class."""
    today = datetime.now().date()
    for back in range(0, 6):
        text = await _fetch_stock_option_report(
            (today - timedelta(days=back)).strftime("%y%m%d")
        )
        if text:
            parsed = parse_stock_option_settlements(text, ats)
            if parsed:
                return parsed
    return {}
