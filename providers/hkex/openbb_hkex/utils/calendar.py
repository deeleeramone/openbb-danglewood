"""HKEX Trading Calendar — authoritative Last Trading Day per contract month.

Source: https://www.hkex.com.hk/Services/Trading/Derivatives/Overview/Trading-Calendar-and-Holiday-Schedule?sc_lang=en

HKEX publishes one HTML table per product family on that page. Different
families have different expiry rules (HSI options expire the second-last
business day of the month; MSCI India options follow Mumbai's last Thursday;
USD/CNH futures follow the third-from-last business day; etc.). This module
parses every table and exposes a `last_trading_day(product_code, contract_id)`
lookup.

The parsed calendar is cached for 24h.
"""

from __future__ import annotations

import re
import time
from datetime import date, datetime
from typing import Any

from openbb_core.provider.utils.helpers import amake_request

from openbb_hkex.utils.client import USER_AGENT, _text_callback

CALENDAR_URL = (
    "https://www.hkex.com.hk/Services/Trading/Derivatives/Overview/"
    "Trading-Calendar-and-Holiday-Schedule?sc_lang=en"
)

STOCK_FAMILY = "HSI_FAMILY"

_PRODUCT_TO_TABLE: dict[str, str] = {
    "HSI": STOCK_FAMILY,
    "MHI": STOCK_FAMILY,
    "HHI": STOCK_FAMILY,
    "MCH": STOCK_FAMILY,
    "HTI": STOCK_FAMILY,
    "HBI": STOCK_FAMILY,
    "HGT": STOCK_FAMILY,
    "HNT": STOCK_FAMILY,
    "HHT": STOCK_FAMILY,
    "HHN": STOCK_FAMILY,
    "MBI": STOCK_FAMILY,
    "PHS": "WEEKLY_INDEX",
    "PHH": "WEEKLY_INDEX",
    "PTE": "WEEKLY_INDEX",
    "XHS": STOCK_FAMILY,
    "XHH": STOCK_FAMILY,
    "DHS": "DIVIDEND",
    "DHH": "DIVIDEND",
    "VHS": "VHSI",
    "CHN": "MSCI_NTR_USD",
    "MAN": "MSCI_NTR_USD",
    "MJU": "MSCI_NTR_USD",
    "MNZ": "MSCI_NTR_USD",
    "MHK": "MSCI_NTR_USD",
    "EMN": "MSCI_NTR_USD",
    "EAN": "MSCI_NTR_USD",
    "MAC": "MSCI_NTR_USD",
    "MAK": "MSCI_NTR_USD",
    "MEE": "MSCI_NTR_USD",
    "MEL": "MSCI_NTR_USD",
    "MXC": "MSCI_NTR_USD",
    "MXK": "MSCI_NTR_USD",
    "MXJ": "MSCI_NTR_USD",
    "MPC": "MSCI_NTR_USD",
    "MPJ": "MSCI_NTR_USD",
    "MCA": "MSCI_A50",
    "CHI": "MSCI_CHINA_USD",
    "MND": "MSCI_INDIA",
    "MIN": "MSCI_INDIA",
    "MIA": "MSCI_INDONESIA",
    "MDN": "MSCI_INDONESIA",
    "MMA": "MSCI_MALAYSIA",
    "MMN": "MSCI_MALAYSIA",
    "MPS": "MSCI_PHILIPPINES",
    "MPN": "MSCI_PHILIPPINES",
    "MSG": "MSCI_SINGAPORE",
    "MSN": "MSCI_SINGAPORE",
    "MGN": "MSCI_SINGAPORE",
    "MTW": "MSCI_TAIWAN",
    "MWN": "MSCI_TAIWAN",
    "TWP": "MSCI_TAIWAN_25_50",
    "TWN": "MSCI_TAIWAN_25_50",
    "MTD": "MSCI_THAILAND",
    "MTN": "MSCI_THAILAND",
    "MVI": "MSCI_VIETNAM",
    "MVN": "MSCI_VIETNAM",
    "CUS": "USDCNH",
    "MCS": "FX_CNH",
    "CEU": "FX_CNH",
    "CJP": "FX_CNH",
    "CAU": "FX_CNH",
    "UCN": "FX_CNH",
    "HB1": "HIBOR_1M",
    "HB3": "HIBOR_3M",
    "GDU": "LME_USD",
    "SIU": "LME_USD",
    "LUA": "LME_USD",
    "LUC": "LME_USD",
    "LUN": "LME_USD",
    "LUP": "LME_USD",
    "LUS": "LME_USD",
    "LUZ": "LME_USD",
    "GDR": "LME_CNH",
    "SIR": "LME_CNH",
    "LRA": "LME_CNH",
    "LRC": "LME_CNH",
    "LRN": "LME_CNH",
    "LRP": "LME_CNH",
    "LRS": "LME_CNH",
    "LRZ": "LME_CNH",
}

_TABLE_MARKERS: list[tuple[str, str]] = [
    ("WEEKLY_INDEX", "weekly hang seng"),
    ("DIVIDEND", "dividend point index"),
    ("VHSI", "volatility index futures"),
    ("MSCI_A50", "msci china a 50 connect"),
    ("MSCI_CHINA_USD", "msci china (usd) index futures"),
    ("MSCI_NTR_USD", "msci china net total return"),
    ("MSCI_INDIA", "msci india"),
    ("MSCI_INDONESIA", "msci indonesia"),
    ("MSCI_MALAYSIA", "msci malaysia"),
    ("MSCI_PHILIPPINES", "msci philippines"),
    ("MSCI_SINGAPORE", "msci singapore"),
    ("MSCI_TAIWAN_25_50", "msci taiwan 25/50"),
    ("MSCI_TAIWAN", "msci taiwan"),
    ("MSCI_THAILAND", "msci thailand"),
    ("MSCI_VIETNAM", "msci vietnam"),
    ("USDCNH", "usd/cnh futures and options"),
    ("FX_CNH", "mini usd/cnh"),
    ("HIBOR_1M", "one-month hibor"),
    ("HIBOR_3M", "three-month hibor"),
    ("LME_USD", "usd london"),
    ("LME_CNH", "cnh london"),
    ("HSI_FAMILY", "hang seng index futures and options"),
]

_cache: dict[str, Any] = {"data": None, "fetched": 0.0}


def _parse_short_date(s: str) -> date | None:
    """Parse strings like '27-Jan-25' or '3-Feb-25' into a date."""
    s = re.sub(r"<[^>]+>", "", s).strip()
    if not s or s.startswith("&"):
        return None
    for fmt in ("%d-%b-%y", "%d-%b-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _norm_month(s: str) -> str:
    """Normalize 'Jan-25' / ' Jan-25 ' / 'JAN-25' → 'Jan-25'."""
    s = re.sub(r"<[^>]+>", "", s).strip()
    return s[:3].title() + s[3:] if len(s) >= 4 and s[3] == "-" else s


async def _fetch_and_parse() -> dict[str, dict[str, date]]:
    """Fetch the calendar page and return {table_key: {contract_month: ltd_date}}."""
    html = await amake_request(
        CALENDAR_URL,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,*/*;q=0.9",
            "Accept-Language": "en-US,en;q=0.5",
        },
        response_callback=_text_callback,
    )
    tables = list(
        re.finditer(r'<table class="table migrate"[^>]*>([\s\S]*?)</table>', html, re.I)
    )
    by_key: dict[str, dict[str, date]] = {}
    used: set[str] = set()
    prev_end = 0
    for m in tables:
        preamble = re.sub(r"<[^>]+>", " ", html[prev_end : m.start()])
        preamble = re.sub(r"\s+", " ", preamble).lower()
        prev_end = m.end()

        rows = re.findall(r"<tr>([\s\S]*?)</tr>", m.group(1))
        parsed: dict[str, date] = {}
        for r in rows:
            cells = re.findall(r"<t[hd][^>]*>([\s\S]*?)</t[hd]>", r)
            if len(cells) < 2:
                continue
            month = _norm_month(cells[0])
            ltd = _parse_short_date(cells[1])
            if month and ltd and re.match(r"^[A-Za-z]{3}-\d{2}$", month):
                parsed[month] = ltd
        if not parsed:
            continue
        for key, marker in _TABLE_MARKERS:
            if key in used:
                continue
            if marker in preamble:
                by_key[key] = parsed
                used.add(key)
                break
    return by_key


async def get_calendar() -> dict[str, dict[str, date]]:
    """Return the cached (or freshly fetched) HKEX trading calendar."""
    if _cache["data"] and (time.time() - _cache["fetched"] < 86400):
        return _cache["data"]
    _cache["data"] = await _fetch_and_parse()
    _cache["fetched"] = time.time()
    return _cache["data"]


def contract_id_to_month_str(con_id: str) -> str:
    """Convert HKEX contract id ('052026') to 'May-26' as used in the calendar tables."""
    months = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    mm, yyyy = int(con_id[:2]), int(con_id[2:])
    return f"{months[mm - 1]}-{yyyy % 100:02d}"


async def last_trading_day(product_code: str, contract_id: str) -> date | None:
    """Look up the HKEX-published Last Trading Day for a contract.

    Returns ``None`` if the product or contract month isn't in the calendar
    (e.g. quarterly/LEAPS contracts beyond the published horizon).
    """
    table_key = _PRODUCT_TO_TABLE.get(product_code.upper(), STOCK_FAMILY)
    cal = await get_calendar()
    return cal.get(table_key, {}).get(contract_id_to_month_str(contract_id))
