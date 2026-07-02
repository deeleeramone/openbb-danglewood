"""Issuer data sources for HK-listed ETF holdings, NAV, performance & tracking.

HKEX does not publish a central ETF holdings / PCF feed — each ETF manager
publishes its own daily basket. This module routes an HKEX stock code to the
right issuer adapter (identified from the ``issuer_name`` on the HKEX quote)
and normalizes the result.

Implemented issuers (each via the issuer's own public JSON API or page):
  * CSOP — ``website-api.csopasset.com`` (holdings / NAV / performance / tracking)
  * iShares / BlackRock — ``blackrock.com/hk`` ajax tabs (holdings / NAV / perf / tracking)
  * Global X (Mirae) — ``globalxetfs.com.hk`` page tables (holdings / perf / tracking)
  * ChinaAMC — JeecgBoot API ``chinaamc.com.hk/jeecg-boot`` (holdings / NAV / tracking)
  * Hang Seng IM — HSBC AEM API + TraHK CSV (holdings / NAV snapshot / perf / tracking)
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import date, datetime, timedelta
from typing import Any

from async_lru import alru_cache
from openbb_core.provider.utils.helpers import amake_request

from openbb_hkex.utils.client import (
    _bytes_callback,
    _common_headers,
    _text_callback,
    parse_num,
    to_hk_symbol,
)

# --------------------------------------------------------------------------- #
# CSOP Asset Management
# --------------------------------------------------------------------------- #

CSOP_WEB = "https://www.csopasset.com"
CSOP_API = "https://website-api.csopasset.com"
_CSOP_REFERER = f"{CSOP_WEB}/en/products/hk-hsi"


def _csop_headers() -> dict[str, str]:
    h = _common_headers(_CSOP_REFERER)
    h["content-type"] = "application/json"
    h["Origin"] = CSOP_WEB
    return h


async def _csop_post(path: str, body: dict, params: str = "") -> Any:
    """POST a JSON body to a CSOP cmsApi endpoint and return the parsed JSON."""
    url = f"{CSOP_API}{path}{('?' + params) if params else ''}"
    raw = await amake_request(
        url,
        method="POST",
        headers=_csop_headers(),
        data=json.dumps(body),
        response_callback=_text_callback,
    )
    return json.loads(raw)


@alru_cache(maxsize=1)
async def _csop_fund_index() -> dict[str, str]:
    """Map HKEX stock code -> CSOP ``productName`` for every CSOP fund.

    CSOP keys all of its endpoints by the full fund name but publishes no
    code->name file, so we read the fund-name directory (``downloadFundId.json``)
    and learn each fund's primary HKEX code from its NAV record's ``Ticker``.
    Built once per process and cached.
    """
    raw = await amake_request(
        f"{CSOP_WEB}/config/downloadFundId.json",
        headers=_common_headers(_CSOP_REFERER),
        response_callback=_text_callback,
    )
    names = list(json.loads(raw).keys())

    async def _code_for(name: str) -> tuple[str, str] | None:
        try:
            rows = await _csop_post("/cmsApi/NAV/product", {"productName": name})
        except Exception:  # noqa: BLE001
            return None
        for row in rows if isinstance(rows, list) else []:
            ticker = str(row.get("Ticker") or "")  # e.g. "3037 HK" / "3037 HK - A"
            code = ticker.split(maxsplit=1)[0] if ticker else ""
            if code.isdigit():
                return to_hk_symbol(code), name
        return None

    pairs = await asyncio.gather(*(_code_for(n) for n in names))
    return {code: name for p in pairs if p for code, name in [p]}


async def csop_product_name(code: str) -> str | None:
    """Resolve an HKEX code to its CSOP ``productName`` (None if not a CSOP fund)."""
    return (await _csop_fund_index()).get(to_hk_symbol(code))


def _csop_norm_holding(r: dict) -> dict:
    """Normalize one CSOP holdings row to the shared holding shape."""
    return {
        "symbol": to_hk_symbol((r.get("ExchgTicker") or "").split()[0] or ""),
        "name": r.get("NameEN"),
        "weight": parse_num(r.get("Weighting")),
        "shares": parse_num(r.get("ShareHeld")),
        "market_value": parse_num(r.get("MarketValueFundCCY")),
        "sector": r.get("SectorEN") or None,
        "exchange": r.get("TradExchg") or None,
        "price": parse_num(r.get("MktPriceFC")),
        "as_of": r.get("DateEn"),
    }


async def csop_holdings(product_name: str) -> list[dict]:
    """Full holdings basket (weight-sorted) for a CSOP fund."""
    resp = await _csop_post(
        "/cmsApi/Holdings/product/list",
        {"productName": product_name, "sord": "desc", "sort": "Weighting"},
        params="limit=1000&offset=0",
    )
    rows = ((resp or {}).get("data") or {}).get("rows") or []
    return [_csop_norm_holding(r) for r in rows]


def _csop_date(s: Any) -> str | None:
    """Parse a CSOP English date ('29 May,2026') to an ISO string."""
    try:
        return datetime.strptime(str(s).strip(), "%d %b,%Y").date().isoformat()
    except (ValueError, TypeError):
        return None


def _is_primary_counter(ticker: str) -> bool:
    """Return True for the primary trading counter (e.g. '3037 HK'), not '3037 HK - A'."""
    return "-" not in (ticker or "")


async def csop_nav_history(
    product_name: str, start: date | None, end: date | None
) -> list[dict]:
    """Daily NAV history (primary counter) for a CSOP fund."""
    end = end or datetime.now().date()  # noqa: DTZ005
    start = start or (end - timedelta(days=365 * 3))
    resp = await _csop_post(
        "/cmsApi/performanceView/trackingDifference",
        {
            "productName": product_name,
            "beginDate": start.isoformat(),
            "endDate": end.isoformat(),
        },
    )
    series_list = ((resp or {}).get("data") or {}).get("NAV") or []
    out: list[dict] = []
    for series in series_list:
        if series and _is_primary_counter(series[0].get("Ticker", "")):
            for pt in series:
                d = _csop_date(pt.get("HstDate"))
                if d:
                    out.append(
                        {
                            "date": d,
                            "nav": parse_num(pt.get("NAV")),
                            "currency": pt.get("Currency") or None,
                        }
                    )
            break
    return out


async def csop_performance(product_name: str) -> list[dict]:
    """Trailing returns for the fund and its benchmark index."""
    resp = await _csop_post(
        "/cmsApi/performance/product", {"productName": product_name}
    )
    rows = (resp or {}).get("data") or []
    out: list[dict] = []
    for r in rows:
        item = r.get("item") or ""
        is_index = "INDEX" in item.upper()
        out.append(
            {
                "label": item,
                "kind": "benchmark" if is_index else "fund",
                "return_1m": parse_num(r.get("RtnLast1")),
                "return_3m": parse_num(r.get("RtnLast3")),
                "return_6m": parse_num(r.get("RtnLast6")),
                "return_ytd": parse_num(r.get("YearToDate")),
                "return_since_inception": parse_num(r.get("SinceInception")),
                "as_of": _csop_date(r.get("Date")),
            }
        )
    return out


async def csop_tracking(product_name: str) -> list[dict]:
    """Tracking difference & tracking error (per counter) for a CSOP fund."""
    resp = await _csop_post(
        "/cmsApi/performanceView/trackingDifference",
        {
            "productName": product_name,
            "beginDate": (datetime.now().date() - timedelta(days=400)).isoformat(),  # noqa: DTZ005
            "endDate": datetime.now().date().isoformat(),  # noqa: DTZ005
        },
    )
    rows = ((resp or {}).get("data") or {}).get("TEAndTD") or []
    return [
        {
            "label": r.get("item"),
            "tracking_difference_mtd": parse_num(r.get("TDMTD")),
            "tracking_difference_1y": parse_num(r.get("TD1YEAR")),
            "tracking_error_1y": parse_num(r.get("TE1YEAR")),
            "as_of": _csop_date(r.get("AsOfDateEn")),
        }
        for r in rows
        if "INDEX" not in (r.get("item") or "").upper()
    ]


# --------------------------------------------------------------------------- #
# Generic HTTP helpers (non-widget issuer endpoints)
# --------------------------------------------------------------------------- #

_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


async def _get_text(url: str, referer: str = "", extra: dict | None = None) -> str:
    headers = {"User-Agent": _BROWSER_UA, "Accept": "*/*"}
    if referer:
        headers["Referer"] = referer
    if extra:
        headers.update(extra)
    return await amake_request(url, headers=headers, response_callback=_text_callback)


async def _get_bytes(url: str, referer: str = "") -> bytes:
    headers = {"User-Agent": _BROWSER_UA, "Accept": "*/*"}
    if referer:
        headers["Referer"] = referer
    return await amake_request(url, headers=headers, response_callback=_bytes_callback)


def _hk_ticker(raw: str) -> str:
    """Normalize an issuer holding ticker ('5-HK', '700 HK', '981 HK') to a code."""
    return to_hk_symbol((raw or "").upper().replace("-HK", "").split()[0] or "")


# --------------------------------------------------------------------------- #
# iShares / BlackRock
# --------------------------------------------------------------------------- #

_ISHARES_SCREENER = (
    "https://www.blackrock.com/hk/en/product-screener/product-screener-v3.1.jsn"
    "?dcrPath=/templatedata/config/product-screener-v3/data/en/hk-one/"
    "product-screener/ishares-product-screener-backend-config"
)
_ISHARES_REF = "https://www.blackrock.com/hk/en/products/etf-investments"


@alru_cache(maxsize=1)
async def _ishares_index() -> dict[str, str]:
    """Map HKEX code -> BlackRock productId for all HK-listed iShares ETFs."""
    raw = await _get_text(
        _ISHARES_SCREENER, _ISHARES_REF, {"X-Requested-With": "XMLHttpRequest"}
    )
    data = json.loads(raw.lstrip("﻿"))
    out: dict[str, str] = {}
    for pid, v in data.items():
        ticker = str((v or {}).get("localExchangeTicker") or "")
        if ticker.isdigit():
            out[to_hk_symbol(ticker)] = str(pid)
    return out


def _cell(v: Any) -> Any:
    """IShares cells are either scalars or {'display','raw'} objects."""
    return v.get("raw") if isinstance(v, dict) else v


async def ishares_holdings(product_id: str) -> list[dict]:
    """Fetch the holdings basket for an iShares HK ETF."""
    url = (
        f"https://www.blackrock.com/hk/en/products/{product_id}/fund/"
        "1478358625333.ajax?tab=all&fileType=json"
    )
    raw = await _get_text(url, _ISHARES_REF)
    rows = json.loads(raw.lstrip("﻿")).get("aaData") or []
    out: list[dict] = []
    for r in rows:
        if len(r) < 12:
            continue
        out.append(
            {
                "symbol": _hk_ticker(str(r[0])),
                "name": r[1],
                "sector": r[2] or None,
                "market_value": parse_num(_cell(r[4])),
                "weight": parse_num(_cell(r[5])),
                "shares": parse_num(_cell(r[7])),
                "isin": r[9] if r[9] != "-" else None,
                "price": parse_num(_cell(r[11])),
                "exchange": r[13] if len(r) > 13 else None,
                "as_of": None,
            }
        )
    return out


_ISHARES_DATA = "1478358625284.ajax"


async def _ishares_table(product_id: str, tab: str) -> list[str]:
    """Fetch an iShares product-table tab and return its flat non-empty cells."""
    url = f"https://www.blackrock.com/hk/en/products/{product_id}/fund/{_ISHARES_DATA}?tab={tab}"
    html = await _get_text(url, _ISHARES_REF)
    m = re.search(r"product-table.*?</table>", html, re.S)
    if not m:
        return []
    cells = [
        _unescape(re.sub("<[^>]+>", "", c)).strip()
        for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", m.group(0), re.S)
    ]
    return [c for c in cells if c and c != "\xa0"]


_PERIOD_KEYS = {
    "YTD": "return_ytd",
    "1m": "return_1m",
    "3m": "return_3m",
    "6m": "return_6m",
    "1y": "return_1y",
    "3y": "return_3y",
    "5y": "return_5y",
    "Incept.": "return_since_inception",
}


async def ishares_nav_history(product_id: str) -> list[dict]:
    """Fetch the NAV history for an iShares HK ETF."""
    url = f"https://www.blackrock.com/hk/en/products/{product_id}/fund/{_ISHARES_DATA}?tab=chart"
    html = await _get_text(url, _ISHARES_REF)
    m = re.search(r"var navData\s*=\s*\[(.*?)\];", html, re.S)
    if not m:
        return []
    out: list[dict] = []
    for y, mo, d, nav in re.findall(
        r"Date\.UTC\((\d+),(\d+),(\d+)\)[^}]*?\(([\d.]+)\)\.toFixed", m.group(1)
    ):
        out.append(
            {
                "date": date(int(y), int(mo) + 1, int(d)).isoformat(),
                "nav": parse_num(nav),
                "currency": None,
            }
        )
    return out


async def ishares_performance(product_id: str) -> list[dict]:
    """Fetch the trailing performance for an iShares HK ETF."""
    cells = await _ishares_table(product_id, "cumulative")
    periods = [c for c in cells if c in _PERIOD_KEYS]
    rows: list[dict] = []
    for kind, anchor in (("fund", "Total Return (%)"), ("benchmark", "Benchmark (%)")):
        if anchor not in cells:
            continue
        vals = cells[cells.index(anchor) + 1 : cells.index(anchor) + 1 + len(periods)]
        rec = {"label": anchor, "kind": kind}
        for p, v in zip(periods, vals):
            rec[_PERIOD_KEYS[p]] = parse_num(v)
        rows.append(rec)
    return rows


async def ishares_tracking(product_id: str) -> list[dict]:
    """Fetch the tracking difference/error for an iShares HK ETF."""
    html = await _get_text(
        f"https://www.blackrock.com/hk/en/products/{product_id}/", _ISHARES_REF
    )
    text = _unescape(re.sub("<[^>]+>", " ", html))

    def _grab(pat: str) -> float | None:
        m = re.search(pat, text)
        return parse_num(m.group(1)) if m else None

    asof = re.search(
        r"Tracking Error \(%\):\s*as of\s*(\d{1,2}-[A-Za-z]{3}-\d{4})", text
    )
    return [
        {
            "label": "Rolling 1-year",
            "tracking_difference_1y": _grab(
                r"Rolling 1-year Tracking Difference \(%\):\s*(?:as of [\dA-Za-z-]+\s*)?(-?[\d.]+)"
            ),
            "tracking_error_1y": _grab(
                r"Rolling 1-year Tracking Error \(%\):\s*(?:as of [\dA-Za-z-]+\s*)?(-?[\d.]+)"
            ),
            "tracking_difference_mtd": None,
            "as_of": _parse_loose_date(asof.group(1)) if asof else None,
        }
    ]


# --------------------------------------------------------------------------- #
# Global X (Mirae)
# --------------------------------------------------------------------------- #

_GLOBALX = "https://www.globalxetfs.com.hk"


@alru_cache(maxsize=1)
async def _globalx_index() -> dict[str, str]:
    """Map HKEX code -> Global X fund slug from the AJAX fund list."""
    html = await _get_text(f"{_GLOBALX}/ajax/fund-list.html", f"{_GLOBALX}/fundlist/")
    out: dict[str, str] = {}
    for slug, code in re.findall(r'/funds/([a-z0-9-]+)/"\s*>\s*(\d{4,5})\s*<', html):
        out.setdefault(to_hk_symbol(code), slug)
    return out


async def globalx_holdings(slug: str) -> list[dict]:
    """Fetch the holdings basket for a Global X HK ETF."""
    html = await _get_text(f"{_GLOBALX}/funds/{slug}/", f"{_GLOBALX}/fundlist/")
    asof = re.search(r"holdings-daily-asofdate'?\"?[^>]*>\s*As of\s*([^<]+)<", html)
    as_of = _parse_loose_date(asof.group(1).strip()) if asof else None
    m = re.search(r'id=["\']holdingsList["\'].*?</table>', html, re.S)
    if not m:
        return []
    out: list[dict] = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(0), re.S)[1:]:
        c = [
            _unescape(re.sub("<[^>]+>", "", x)).strip()
            for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)
        ]
        if len(c) < 7:
            continue
        out.append(
            {
                "symbol": _hk_ticker(c[1]),
                "name": c[0],
                "price": parse_num(c[3]),
                "shares": parse_num(c[4]),
                "market_value": parse_num(c[5]),
                "weight": parse_num(c[6]),
                "as_of": as_of,
            }
        )
    return out


async def _globalx_page(slug: str) -> str:
    return await _get_text(f"{_GLOBALX}/funds/{slug}/", f"{_GLOBALX}/fundlist/")


def _zr(html: str, key: str) -> str | None:
    m = re.search(rf"data-zrcheck=['\"]{re.escape(key)}['\"][^>]*>([^<]+)<", html)
    return m.group(1).strip() if m else None


async def globalx_nav_history(slug: str) -> list[dict]:
    """Global X publishes no daily raw-NAV series — return the current snapshot only."""
    html = await _globalx_page(slug)
    nav = _zr(html, "official-nav")
    asof = _zr(html, "daily-nav-asofdate")
    d = _parse_loose_date((asof or "").replace("As of", "").strip())
    if nav is None or not d:
        return []
    return [{"date": d, "nav": parse_num(nav), "currency": None}]


async def globalx_performance(slug: str) -> list[dict]:
    """Fetch the trailing performance for a Global X HK ETF."""
    html = await _globalx_page(slug)
    keys = {
        "return_1m": "1m",
        "return_3m": "3m",
        "return_6m": "6m",
        "return_1y": "1y",
        "return_ytd": "yt",
        "return_since_inception": "si",
    }
    rows: list[dict] = []
    for kind, tag in (("fund", "etf"), ("benchmark", "bm")):
        rec = {"label": tag, "kind": kind}
        found = False
        for field, suffix in keys.items():
            v = _zr(html, f"returns-{tag}-{suffix}")
            if v is not None:
                rec[field] = parse_num(v)
                found = True
        if found:
            rows.append(rec)
    return rows


async def globalx_tracking(slug: str) -> list[dict]:
    """Fetch the tracking difference/error for a Global X HK ETF."""
    html = await _globalx_page(slug)
    cctd = re.search(r"id=['\"]cctd['\"][^>]*>([^<]+)<", html)
    ccte = re.search(r"id=['\"]ccte['\"][^>]*>([^<]+)<", html)
    return [
        {
            "label": "Rolling 1-year",
            "tracking_difference_1y": parse_num(cctd.group(1)) if cctd else None,
            "tracking_error_1y": parse_num(ccte.group(1)) if ccte else None,
            "tracking_difference_mtd": None,
            "as_of": _parse_loose_date(
                (_zr(html, "tracking-diff-asofdate") or "").strip()
            ),
        }
    ]


# --------------------------------------------------------------------------- #
# ChinaAMC
# --------------------------------------------------------------------------- #

# ChinaAMC's site is a Vue SPA backed by a public JeecgBoot JSON API. All fund
# data (holdings / NAV history / tracking) is keyed by the fund's ``ssFundId``
# (e.g. "CSI300"), which the fund list maps from the HKEX listing code.
_CHINAAMC_API = "https://www.chinaamc.com.hk/jeecg-boot"
_CHINAAMC_REF = "https://www.chinaamc.com.hk/"


def _chinaamc_date(s: Any) -> str | None:
    """Parse a ChinaAMC API date ('20260601') to ISO."""
    s = str(s or "")
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 and s.isdigit() else None


async def _chinaamc_get(path: str, **params: Any) -> Any:
    qs = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
    url = f"{_CHINAAMC_API}/{path}{('?' + qs) if qs else ''}"
    raw = await _get_text(url, _CHINAAMC_REF)
    return (json.loads(raw) or {}).get("result")


@alru_cache(maxsize=1)
async def _chinaamc_index() -> dict[str, str]:
    """Map HKEX code -> ssFundId for every ChinaAMC fund (from the fund list)."""
    funds = await _chinaamc_get("mainFund/fundQuery/list") or []
    out: dict[str, str] = {}
    for f in funds if isinstance(funds, list) else []:
        ss = f.get("ssFundId")
        for code in re.findall(r"(\d{4,5})\s*HK", f.get("fundShowNameEn") or ""):
            if ss:
                out.setdefault(to_hk_symbol(code), ss)
    return out


async def _chinaamc_ssid(code: str) -> str | None:
    return (await _chinaamc_index()).get(to_hk_symbol(code))


async def chinaamc_holdings(ss_fund_id: str) -> list[dict]:
    """Fetch the holdings basket for a ChinaAMC HK ETF."""
    rows = await _chinaamc_get(
        "mainFund/fundQuery/getHoldingsByFundId", fundId=ss_fund_id, groupBy="none"
    )
    out: list[dict] = []
    for r in rows if isinstance(rows, list) else []:
        out.append(
            {
                "symbol": _hk_ticker(str(r.get("securityCode") or "")),
                "name": r.get("securityNameEN"),
                "weight": parse_num(r.get("weighting")),
                "shares": parse_num(r.get("shares")),
                "price": parse_num(r.get("unitPrice")),
                "sector": r.get("sector") or None,
                "isin": r.get("isin") or None,
                "as_of": _chinaamc_date(r.get("date")),
            }
        )
    return out


async def chinaamc_nav_history(ss_fund_id: str) -> list[dict]:
    """Daily NAV history from the tracking-difference graph (base-currency series)."""
    vo = await _chinaamc_get(
        "mainFund/fundQuery/getTrackingDifferenceGraphVO", fundId=ss_fund_id
    )
    series = (vo or {}).get("productFundList") or []
    # The series may carry several share classes; keep the most-populated one.
    by_class: dict[str, list] = {}
    for p in series:
        by_class.setdefault(p.get("shareClassId") or "", []).append(p)
    points = max(by_class.values(), key=len) if by_class else []
    out: list[dict] = []
    for p in points:
        d = _chinaamc_date(p.get("date"))
        if d:
            out.append(
                {
                    "date": d,
                    "nav": parse_num(p.get("nav")),
                    "currency": p.get("shareClassId") or None,
                }
            )
    return sorted(out, key=lambda r: r["date"])


async def chinaamc_tracking(ss_fund_id: str) -> list[dict]:
    """Fetch the tracking difference/error for a ChinaAMC HK ETF."""
    rows = await _chinaamc_get(
        "mainFund/fundQuery/getEtfTdteByFundId", fundId=ss_fund_id
    )

    def _pct(v: Any) -> float | None:  # API reports TD/TE as decimal fractions
        n = parse_num(v)
        return round(n * 100, 4) if n is not None else None

    out: list[dict] = []
    for sc in rows if isinstance(rows, list) else []:
        items = {i.get("typeName"): i for i in sc.get("tdteDataList") or []}
        td = items.get("Rolling 1-Year TD") or {}
        te = items.get("Rolling 1-Year TE^") or items.get("Rolling 1-Year TE") or {}
        out.append(
            {
                "label": sc.get("shareClassNameEn") or sc.get("shareClassId"),
                "tracking_difference_mtd": None,
                "tracking_difference_1y": _pct(td.get("value")),
                "tracking_error_1y": _pct(te.get("value")),
                "as_of": _chinaamc_date(td.get("date") or te.get("date")),
            }
        )
    return out


async def chinaamc_performance(ss_fund_id: str) -> list[dict]:
    """Trailing returns per share class (fund only; ChinaAMC has no benchmark feed)."""
    vo = await _chinaamc_get(
        "mainFundPerformance/tMainFundPerformance/getShareClassPerformance",
        fundId=ss_fund_id,
    )

    def _num(v: Any) -> float | None:
        return parse_num(str(v).replace("+", "").replace("%", "")) if v else None

    out: list[dict] = []
    for sc in (vo or {}).get("shares") or []:
        p = sc.get("performances") or {}
        out.append(
            {
                "label": sc.get("shareClassNameEN") or sc.get("shareClassId"),
                "kind": "fund",
                "return_ytd": _num(p.get("ytdValue")),
                "return_1y": _num(p.get("oneYear")),
                "return_3y": _num(p.get("threeYear")),
                "return_5y": _num(p.get("fiveYear")),
                "return_since_inception": _num(p.get("sinceInception")),
                "as_of": _chinaamc_date(p.get("relativeDate")),
            }
        )
    return out


# --------------------------------------------------------------------------- #
# Hang Seng Investment Management — Tracker Fund (2800) only (fresh daily CSV).
# The generic ``{code}_report.xls`` files carry stale data, so they are not used.
# --------------------------------------------------------------------------- #

_TRAHK_CSV = (
    "https://rbwm-api.hsbc.com.hk/pws-hk-hase-hsvm2-papi-prod-proxy/v1/hsvm/csv/"
    "trahkfund/holdings?mode=daily"
)


async def trahk_holdings() -> list[dict]:
    """Fetch the holdings basket for the Tracker Fund of Hong Kong (TraHK)."""
    import csv

    text = await _get_text(_TRAHK_CSV)
    rows = list(csv.reader(text.lstrip("﻿").splitlines()))
    as_of = None
    start = None
    for i, r in enumerate(rows):
        if r and r[0].startswith("Holdings as of") and len(r) > 1:
            as_of = _parse_ddmmyyyy(r[1])
        if r and r[0] == "ISIN" and "Weight (%)" in r:
            start = i + 1
            break
    out: list[dict] = []
    for r in rows[start:] if start else []:
        if len(r) < 11 or not r[2]:
            continue
        out.append(
            {
                "symbol": _hk_ticker(r[2]),
                "name": r[4],
                "isin": r[0] or None,
                "price": parse_num(r[6]),
                "shares": parse_num(r[7]),
                "market_value": parse_num(r[8]),
                "weight": parse_num(r[9]),
                "sector": r[10] or None,
                "as_of": as_of,
            }
        )
    return out


_HSIM_API = "https://rbwm-api.hsbc.com.hk/pws-hk-hase-hsvm2-papi-prod-proxy/v1/hsvm/aem"
_HSIM_REF = "https://www.hangsenginvestment.com/"


@alru_cache(maxsize=1)
async def _hsim_fundlist() -> dict[str, dict]:
    """Map HKEX code -> {trustNo, unit-class record (prices + returns)} for HSIM funds."""
    raw = await _get_text(f"{_HSIM_API}/fundlist", _HSIM_REF)
    funds = json.loads(raw).get("Funds", {}).get("Fund", []) or []
    out: dict[str, dict] = {}
    for fund in funds:
        if not isinstance(fund, dict):
            continue
        tn = fund.get("TrustNo")
        for uc in fund.get("FundUnitClass", []) or []:
            if not isinstance(uc, dict):
                continue
            code = uc.get("FundCode")
            if code is not None:
                out.setdefault(str(code), {"trustNo": tn, "uc": uc})
    return out


async def _hsim_record(code: str) -> dict | None:
    return (await _hsim_fundlist()).get(to_hk_symbol(code))


async def hsim_top10_holdings(code: str) -> list[dict]:
    """Fresh top-10 holdings (name + weight) for a non-TraHK HSIM fund."""
    rec = await _hsim_record(code)
    if not rec or not rec.get("trustNo"):
        return []
    raw = await _get_text(
        f"{_HSIM_API}/etffunddetail?trustNo={rec['trustNo']}", _HSIM_REF
    )
    fund = (json.loads(raw) or {}).get("Fund", {})
    prev = str(fund.get("ETF_info", {}).get("PrevDate") or "")
    as_of = (
        f"{prev[:4]}-{prev[4:6]}-{prev[6:8]}"
        if len(prev) == 8 and prev.isdigit()
        else None
    )
    items = fund.get("Top_10", {}).get("Top_10_item", []) or []
    out: list[dict] = []
    for it in items if isinstance(items, list) else []:
        out.append(
            {
                "symbol": None,
                "name": it.get("Item_name_eng"),
                "weight": parse_num(it.get("Nav_per")),
                "as_of": as_of,
            }
        )
    return out


async def hsim_performance(code: str) -> list[dict]:
    """Fetch the trailing performance for a Hang Seng (HSIM) ETF."""
    rec = await _hsim_record(code)
    if not rec:
        return []
    uc = rec["uc"]
    return [
        {
            "label": str(uc.get("FundCode")),
            "kind": "fund",
            "return_ytd": parse_num((uc.get("Yr_to_date") or "").rstrip("%")),
            "return_1y": parse_num((uc.get("one_yr") or "").rstrip("%")),
            "return_3y": parse_num((uc.get("three_yr") or "").rstrip("%")),
            "return_5y": parse_num((uc.get("five_yr") or "").rstrip("%")),
            "as_of": _parse_loose_date((uc.get("Price_date") or "").replace("/", "-")),
        }
    ]


async def hsim_tracking(code: str) -> list[dict]:
    """Fetch the tracking difference/error for a Hang Seng (HSIM) ETF."""
    rec = await _hsim_record(code)
    if not rec or not rec.get("trustNo"):
        return []
    raw = await _get_text(
        f"{_HSIM_API}/fund/tdandte?trustNo={rec['trustNo']}&fundCode={to_hk_symbol(code)}",
        _HSIM_REF,
    )
    f = (json.loads(raw) or {}).get("Funds", {})
    # Note the source's misspelling of "Return".
    td = (f.get("Total_Ruturn_Tracking_Difference") or {}).get("TD_1_Year")
    return [
        {
            "label": str(code),
            "tracking_difference_mtd": None,
            "tracking_difference_1y": parse_num((td or "").rstrip("%")) if td else None,
            "tracking_error_1y": parse_num(
                (f.get("Total_Ruturn_Tracking_Error") or "").rstrip("%")
            ),
            "as_of": f.get("ReportDate"),
        }
    ]


async def hsim_nav_history(code: str) -> list[dict]:
    """HSIM publishes no open daily NAV series — return the current NAV snapshot."""
    rec = await _hsim_record(code)
    if not rec or not rec.get("trustNo"):
        return []
    raw = await _get_text(
        f"{_HSIM_API}/etffunddetail?trustNo={rec['trustNo']}", _HSIM_REF
    )
    info = (json.loads(raw) or {}).get("Fund", {}).get("ETF_info", {})
    prev = str(info.get("PrevDate") or "")
    if not (len(prev) == 8 and prev.isdigit()):
        return []
    return [
        {
            "date": f"{prev[:4]}-{prev[4:6]}-{prev[6:8]}",
            "nav": parse_num(info.get("Nav")),
            "currency": None,
        }
    ]


# --------------------------------------------------------------------------- #
# Date helpers
# --------------------------------------------------------------------------- #


def _parse_loose_date(s: str) -> str | None:
    s = (s or "").strip().replace(",", "")
    for fmt in (
        "%d %b %Y",
        "%Y/%m/%d",
        "%d %B %Y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d-%b-%Y",
    ):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_ddmmyyyy(s: str) -> str | None:
    try:
        return datetime.strptime(str(s).strip(), "%d%m%Y").date().isoformat()
    except ValueError:
        return None


def _unescape(s: str) -> str:
    import html as _html

    return _html.unescape(s)


# --------------------------------------------------------------------------- #
# Issuer routing
# --------------------------------------------------------------------------- #

# Substring (lower-cased) of the HKEX quote ``issuer_name`` -> adapter key.
_ISSUER_SIGNATURES: list[tuple[str, str]] = [
    ("csop", "csop"),
    ("blackrock", "ishares"),
    ("ishares", "ishares"),
    ("global x", "globalx"),
    ("mirae", "globalx"),
    ("china asset management", "chinaamc"),
    ("chinaamc", "chinaamc"),
    ("hang seng investment", "hsim"),
]


def detect_issuer(issuer_name: str | None) -> str | None:
    """Return the adapter key for an HKEX ``issuer_name``, or None if unsupported."""
    name = (issuer_name or "").lower()
    for sig, key in _ISSUER_SIGNATURES:
        if sig in name:
            return key
    return None


async def _csop_name_or_raise(code: str, issuer_name: str | None) -> str:
    if detect_issuer(issuer_name) == "csop":
        name = await csop_product_name(code)
        if name:
            return name
    raise UnsupportedIssuerError(issuer_name)


async def fetch_holdings(code: str, issuer_name: str | None) -> list[dict]:
    """Resolve the issuer for ``code`` and return its normalized holdings basket.

    Raises ``UnsupportedIssuerError`` when no adapter covers the fund's issuer.
    """
    key = detect_issuer(issuer_name)
    code = to_hk_symbol(code)
    if key == "csop":
        name = await csop_product_name(code)
        if name:
            return await csop_holdings(name)
    elif key == "ishares":
        pid = (await _ishares_index()).get(code)
        if pid:
            return await ishares_holdings(pid)
    elif key == "globalx":
        slug = (await _globalx_index()).get(code)
        if slug:
            return await globalx_holdings(slug)
    elif key == "chinaamc":
        ss = await _chinaamc_ssid(code)
        if ss:
            return await chinaamc_holdings(ss)
    elif key == "hsim":
        # TraHK (2800) publishes a full daily basket; other HSIM funds only
        # disclose a fresh top-10 (HKEX has no central holdings feed).
        return (
            await trahk_holdings()
            if code == "2800"
            else await hsim_top10_holdings(code)
        )
    raise UnsupportedIssuerError(issuer_name)


async def fetch_nav_history(
    code: str, issuer_name: str | None, start: date | None, end: date | None
) -> list[dict]:
    """Resolve the issuer and return its daily NAV history (snapshot for some)."""
    key = detect_issuer(issuer_name)
    code = to_hk_symbol(code)
    if key == "csop":
        return await csop_nav_history(
            await _csop_name_or_raise(code, issuer_name), start, end
        )
    if key == "ishares":
        pid = (await _ishares_index()).get(code)
        if pid:
            return await ishares_nav_history(pid)
    elif key == "globalx":
        slug = (await _globalx_index()).get(code)
        if slug:
            return await globalx_nav_history(slug)
    elif key == "chinaamc":
        ss = await _chinaamc_ssid(code)
        if ss:
            return await chinaamc_nav_history(ss)
    elif key == "hsim":
        return await hsim_nav_history(code)
    raise UnsupportedIssuerError(issuer_name)


async def fetch_performance(code: str, issuer_name: str | None) -> list[dict]:
    """Resolve the issuer and return fund (+ benchmark) trailing returns."""
    key = detect_issuer(issuer_name)
    code = to_hk_symbol(code)
    if key == "csop":
        return await csop_performance(await _csop_name_or_raise(code, issuer_name))
    if key == "ishares":
        pid = (await _ishares_index()).get(code)
        if pid:
            return await ishares_performance(pid)
    elif key == "globalx":
        slug = (await _globalx_index()).get(code)
        if slug:
            return await globalx_performance(slug)
    elif key == "chinaamc":
        ss = await _chinaamc_ssid(code)
        if ss:
            return await chinaamc_performance(ss)
    elif key == "hsim":
        return await hsim_performance(code)
    raise UnsupportedIssuerError(issuer_name)


async def fetch_tracking(code: str, issuer_name: str | None) -> list[dict]:
    """Resolve the issuer and return tracking difference & error."""
    key = detect_issuer(issuer_name)
    code = to_hk_symbol(code)
    if key == "csop":
        return await csop_tracking(await _csop_name_or_raise(code, issuer_name))
    if key == "ishares":
        pid = (await _ishares_index()).get(code)
        if pid:
            return await ishares_tracking(pid)
    elif key == "globalx":
        slug = (await _globalx_index()).get(code)
        if slug:
            return await globalx_tracking(slug)
    elif key == "chinaamc":
        ss = await _chinaamc_ssid(code)
        if ss:
            return await chinaamc_tracking(ss)
    elif key == "hsim":
        return await hsim_tracking(code)
    raise UnsupportedIssuerError(issuer_name)


class UnsupportedIssuerError(Exception):
    """Raised when an ETF's issuer has no holdings adapter yet."""

    def __init__(self, issuer_name: str | None) -> None:
        super().__init__(
            f"No holdings source is wired for issuer '{issuer_name or 'unknown'}' yet."
        )
