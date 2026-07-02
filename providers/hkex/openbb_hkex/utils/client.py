"""Async client for the HKEX `hkexwidget` JSONP endpoints and hkexnews.hk."""

from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import unquote

from openbb_core.app.model.abstract.error import OpenBBError
from openbb_core.provider.utils.helpers import amake_request

WIDGET_BASE = "https://www1.hkex.com.hk/hkexwidget/data"
HKEXNEWS_BASE = "https://www1.hkexnews.hk"
SECLIST_XLSX = (
    "https://www.hkex.com.hk/eng/services/trading/securities/"
    "securitieslists/ListOfSecurities.xlsx"
)
TOKEN_PAGE = (
    "https://www.hkex.com.hk/Market-Data/Securities-Prices/"  # noqa: S105 — public page URL, not a credential
    "Equities/Equities-Quote?sym=5&sc_lang=en"
)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
REFERER = "https://www.hkex.com.hk/"
_TOKEN_RE = re.compile(r'^\s*return\s+"([^"]+)"\s*;', re.MULTILINE)

_token_cache: dict[str, Any] = {"value": None, "fetched": 0.0}


def _common_headers(referer: str = REFERER) -> dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "Referer": referer,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }


async def _text_callback(response, _: Any) -> str:
    return await response.text()


async def _bytes_callback(response, _: Any) -> bytes:
    return await response.read()


async def get_token(refresh: bool = False) -> str:
    """Scrape the rotating widget token from a live HKEX page (cached 1h)."""
    age = time.time() - _token_cache["fetched"]
    if not refresh and _token_cache["value"] and age < 3600:
        return _token_cache["value"]
    headers = _common_headers()
    headers["Accept"] = "text/html"
    html = await amake_request(
        TOKEN_PAGE, headers=headers, response_callback=_text_callback
    )
    token = next(
        (
            m.group(1)
            for m in _TOKEN_RE.finditer(html)
            if m.group(1) != "Base64-AES-Encrypted-Token"
        ),
        None,
    )
    if not token:
        raise OpenBBError("Could not extract the HKEX widget token.")
    _token_cache["value"] = unquote(token)
    _token_cache["fetched"] = time.time()
    return _token_cache["value"]


async def call_widget(api: str, **params: Any) -> dict:
    """Call a `hkexwidget` JSONP endpoint and return the inner `data` payload."""
    import json
    from urllib.parse import urlencode

    qs = {
        "lang": params.pop("lang", "eng"),
        "token": await get_token(),
        "qid": str(int(time.time() * 1000)),
        "callback": "cb",
    }
    qs.update({k: v for k, v in params.items() if v is not None})
    url = f"{WIDGET_BASE}/{api}?{urlencode(qs)}"
    raw = await amake_request(
        url, headers=_common_headers(), response_callback=_text_callback, timeout=20
    )
    body = raw.strip()
    if body.startswith("cb("):
        body = body[3:]
    if body.endswith(");"):
        body = body[:-2]
    elif body.endswith(")"):
        body = body[:-1]
    payload = json.loads(body)
    data = payload.get("data") or {}
    rc = data.get("responsecode")
    if rc and rc not in ("000", "0"):
        raise OpenBBError(f"HKEX {api} error {rc}: {data.get('responsemsg')}")
    return data


async def fetch_seclist_xlsx() -> bytes:
    """Download the daily `ListOfSecurities.xlsx` security-master file."""
    return await amake_request(
        SECLIST_XLSX,
        headers=_common_headers(),
        response_callback=_bytes_callback,
    )


async def fetch_disclosure_taxonomy() -> tuple[list, list]:
    """Return (tier1, tier2) JSON arrays from the hkexnews title-search page."""
    import json

    base = HKEXNEWS_BASE
    t1_raw = await amake_request(
        f"{base}/ncms/script/eds/tierone_e.json",
        headers={"User-Agent": USER_AGENT},
        response_callback=_text_callback,
    )
    t2_raw = await amake_request(
        f"{base}/ncms/script/eds/tiertwo_e.json",
        headers={"User-Agent": USER_AGENT},
        response_callback=_text_callback,
    )
    return json.loads(t1_raw), json.loads(t2_raw)


async def find_stock_id(name_or_code: str, kind: str = "active") -> list[dict]:
    """Resolve a name/code to the hkexnews `stockId` used by the disclosure search."""
    import json
    from urllib.parse import urlencode

    type_code = "A" if kind == "active" else "I"
    url = f"{HKEXNEWS_BASE}/search/prefix.do?" + urlencode(
        {
            "callback": "callback",
            "lang": "EN",
            "type": type_code,
            "name": name_or_code,
            "market": "SEHK",
        }
    )
    body = await amake_request(
        url,
        headers={"User-Agent": USER_AGENT},
        response_callback=_text_callback,
    )
    body = body.strip().rstrip(";").rstrip()
    if body.startswith("callback(") and body.endswith(")"):
        body = body[len("callback(") : -1]
    return json.loads(body).get("stockInfo", [])


def disclosure_search_sync(
    stock_id: str | int | None,
    t1_code: str | None,
    t2_code: str | None,
    date_from: str,
    date_to: str,
    title: str = "",
    market: str = "SEHK",
) -> list[dict]:
    """Search hkexnews for disclosure documents via titleSearchServlet.do."""
    import json as _json
    import urllib.parse
    import urllib.request

    params = {
        "sortDir": "0",
        "sortByOptions": "DateTime",
        "category": "0",
        "market": market,
        "stockId": str(stock_id) if stock_id is not None else "",
        "documentType": "-1",
        "fromDate": date_from,
        "toDate": date_to,
        "title": title or "",
        "searchType": "1",
        "t1code": t1_code or "-2",
        "t2Gcode": "-2",
        "t2code": t2_code or "-2",
        "rowRange": "50000",
        "lang": "EN",
    }
    url = f"{HKEXNEWS_BASE}/search/titleSearchServlet.do?" + urllib.parse.urlencode(
        params
    )
    raw = (
        urllib.request.urlopen(  # noqa: S310 — fixed https hkexnews endpoint
            urllib.request.Request(url, headers={"User-Agent": USER_AGENT}),  # noqa: S310
            timeout=60,
        )
        .read()
        .decode("utf-8", "replace")
    )

    payload = _json.loads(raw)
    result = payload.get("result")
    items = _json.loads(result) if isinstance(result, str) else (result or [])

    def _clean(s: str | None) -> str:
        return re.sub(r"\s*<br\s*/?>\s*", " / ", s or "").strip(" /").strip()

    rows: list[dict] = []
    for it in items:
        link = it.get("FILE_LINK") or ""
        rows.append(
            {
                "release_time": (it.get("DATE_TIME") or "").strip(),
                "stock_code": _clean(it.get("STOCK_CODE")),
                "stock_short_name": _clean(it.get("STOCK_NAME")),
                "category": (it.get("LONG_TEXT") or it.get("SHORT_TEXT") or "")
                .replace("<br/>", "")
                .strip(),
                "title": (it.get("TITLE") or "").strip(),
                "url": f"{HKEXNEWS_BASE}{link}" if link.startswith("/") else link,
                "size": (it.get("FILE_INFO") or "").strip(),
            }
        )
    return rows


DERIVATIVE_PRODUCTS: dict[str, dict[str, str]] = {
    "HSI": {"category": "Equity-Index", "name": "Hang Seng Index Futures and Options"},
    "MHI": {
        "category": "Equity-Index",
        "name": "Mini Hang Seng Index Futures and Options",
    },
    "PHS": {"category": "Equity-Index", "name": "HSI Futures Options (weekly/serial)"},
    "XHS": {"category": "Equity-Index", "name": "Flexible Hang Seng Index Options"},
    "HHI": {"category": "Equity-Index", "name": "HSCEI Futures and Options"},
    "MCH": {"category": "Equity-Index", "name": "Mini-HSCEI Futures and Options"},
    "PHH": {
        "category": "Equity-Index",
        "name": "HSCEI Futures Options (weekly/serial)",
    },
    "XHH": {"category": "Equity-Index", "name": "Flexible HSCEI Options"},
    "HTI": {
        "category": "Equity-Index",
        "name": "Hang Seng TECH Index Futures and Options",
    },
    "PTE": {"category": "Equity-Index", "name": "Hang Seng TECH Index Futures Options"},
    "HBI": {"category": "Equity-Index", "name": "Hang Seng Biotech Index Futures"},
    "HGT": {"category": "Equity-Index", "name": "Hang Seng Total Return Index Futures"},
    "HNT": {
        "category": "Equity-Index",
        "name": "Hang Seng Total Return Index Futures (HNT)",
    },
    "HHT": {"category": "Equity-Index", "name": "HSCEI Total Return Index"},
    "HHN": {"category": "Equity-Index", "name": "HSCEI Total Return Index (HHN)"},
    "MBI": {
        "category": "Equity-Index",
        "name": "Hang Seng Mainland Banks Index Futures",
    },
    "VHS": {"category": "Equity-Index", "name": "HSI Volatility Index Futures"},
    "DHS": {"category": "Equity-Index", "name": "HSI Dividend Futures"},
    "DHH": {"category": "Equity-Index", "name": "HSCEI Dividend Futures"},
    "CHH": {"category": "Equity-Index", "name": "CES China 120 Index Futures"},
    "GTI": {"category": "Equity-Index", "name": "CES Gaming Top 10 Index Futures"},
    "MCA": {
        "category": "Equity-Index",
        "name": "MSCI China A 50 Connect (USD) Index Futures",
    },
    "CHI": {"category": "Equity-Index", "name": "MSCI China (USD) Index Futures"},
    "CHN": {"category": "Equity-Index", "name": "MSCI China NTR (USD) Index Futures"},
    "MEI": {
        "category": "Equity-Index",
        "name": "MSCI Emerging Markets (USD) Index Futures",
    },
    "EMN": {
        "category": "Equity-Index",
        "name": "MSCI Emerging Markets NTR (USD) Index Futures",
    },
    "MXC": {
        "category": "Equity-Index",
        "name": "MSCI EM ex-China NTR (USD) Index Futures",
    },
    "MXK": {
        "category": "Equity-Index",
        "name": "MSCI EM ex-Korea NTR (USD) Index Futures",
    },
    "EAN": {"category": "Equity-Index", "name": "MSCI EM Asia NTR (USD) Index Futures"},
    "MAC": {
        "category": "Equity-Index",
        "name": "MSCI EM Asia ex-China NTR (USD) Index Futures",
    },
    "MAK": {
        "category": "Equity-Index",
        "name": "MSCI EM Asia ex-Korea NTR (USD) Index Futures",
    },
    "MEE": {"category": "Equity-Index", "name": "MSCI EM EMEA NTR (USD) Index Futures"},
    "MEL": {
        "category": "Equity-Index",
        "name": "MSCI EM LatAm NTR (USD) Index Futures",
    },
    "MXJ": {"category": "Equity-Index", "name": "MSCI Asia ex-Japan Index Futures"},
    "MJU": {"category": "Equity-Index", "name": "MSCI Japan NTR (USD) Index Futures"},
    "MPC": {"category": "Equity-Index", "name": "MSCI Pacific NTR (USD) Index Futures"},
    "MPJ": {
        "category": "Equity-Index",
        "name": "MSCI Pacific ex-Japan NTR (USD) Index Futures",
    },
    "MAN": {
        "category": "Equity-Index",
        "name": "MSCI Australia NTR (USD) Index Futures",
    },
    "MNZ": {
        "category": "Equity-Index",
        "name": "MSCI New Zealand NTR (USD) Index Futures",
    },
    "MHK": {
        "category": "Equity-Index",
        "name": "MSCI Hong Kong NTR (USD) Index Futures",
    },
    "MND": {"category": "Equity-Index", "name": "MSCI India (USD) Index Futures"},
    "MIN": {"category": "Equity-Index", "name": "MSCI India NTR (USD) Index Futures"},
    "MIA": {"category": "Equity-Index", "name": "MSCI Indonesia (USD) Index Futures"},
    "MDN": {
        "category": "Equity-Index",
        "name": "MSCI Indonesia NTR (USD) Index Futures",
    },
    "MMA": {"category": "Equity-Index", "name": "MSCI Malaysia (USD) Index Futures"},
    "MMN": {
        "category": "Equity-Index",
        "name": "MSCI Malaysia NTR (USD) Index Futures",
    },
    "MPS": {"category": "Equity-Index", "name": "MSCI Philippines (USD) Index Futures"},
    "MPN": {
        "category": "Equity-Index",
        "name": "MSCI Philippines NTR (USD) Index Futures",
    },
    "MSG": {
        "category": "Equity-Index",
        "name": "MSCI Singapore Free (SGD) Index Futures",
    },
    "MSN": {
        "category": "Equity-Index",
        "name": "MSCI Singapore NTR (USD) Index Futures",
    },
    "MGN": {
        "category": "Equity-Index",
        "name": "MSCI Singapore Free NTR (USD) Index Futures",
    },
    "MTW": {"category": "Equity-Index", "name": "MSCI Taiwan (USD) Index Futures"},
    "MWN": {"category": "Equity-Index", "name": "MSCI Taiwan NTR (USD) Index Futures"},
    "TWP": {
        "category": "Equity-Index",
        "name": "MSCI Taiwan 25/50 (USD) Index Futures",
    },
    "TWN": {
        "category": "Equity-Index",
        "name": "MSCI Taiwan 25/50 NTR (USD) Index Futures",
    },
    "MTD": {"category": "Equity-Index", "name": "MSCI Thailand (USD) Index Futures"},
    "MTN": {
        "category": "Equity-Index",
        "name": "MSCI Thailand NTR (USD) Index Futures",
    },
    "MVI": {"category": "Equity-Index", "name": "MSCI Vietnam (USD) Index Futures"},
    "MVN": {"category": "Equity-Index", "name": "MSCI Vietnam NTR (USD) Index Futures"},
    "CUS": {"category": "Foreign-Exchange", "name": "USD/CNH Futures and Options"},
    "MCS": {"category": "Foreign-Exchange", "name": "Mini USD/CNH Futures"},
    "UCN": {"category": "Foreign-Exchange", "name": "CNH/USD Futures"},
    "CAU": {"category": "Foreign-Exchange", "name": "AUD/CNH Futures"},
    "CEU": {"category": "Foreign-Exchange", "name": "EUR/CNH Futures"},
    "CJP": {"category": "Foreign-Exchange", "name": "JPY/CNH Futures"},
    "HB1": {"category": "Interest-Rate", "name": "One-Month HIBOR Futures"},
    "HB3": {"category": "Interest-Rate", "name": "Three-Month HIBOR Futures"},
    "GDU": {"category": "Commodities", "name": "USD Gold Futures"},
    "GDR": {"category": "Commodities", "name": "CNH Gold Futures"},
    "SIU": {"category": "Commodities", "name": "USD Silver Futures"},
    "SIR": {"category": "Commodities", "name": "CNH Silver Futures"},
    "LUA": {"category": "Commodities", "name": "USD London Aluminium Mini Futures"},
    "LUC": {"category": "Commodities", "name": "USD London Copper Mini Futures"},
    "LUN": {"category": "Commodities", "name": "USD London Nickel Mini Futures"},
    "LUP": {"category": "Commodities", "name": "USD London Lead Mini Futures"},
    "LUS": {"category": "Commodities", "name": "USD London Tin Mini Futures"},
    "LUZ": {"category": "Commodities", "name": "USD London Zinc Mini Futures"},
    "LRA": {"category": "Commodities", "name": "CNH London Aluminium Mini Futures"},
    "LRC": {"category": "Commodities", "name": "CNH London Copper Mini Futures"},
    "LRN": {"category": "Commodities", "name": "CNH London Nickel Mini Futures"},
    "LRP": {"category": "Commodities", "name": "CNH London Lead Mini Futures"},
    "LRS": {"category": "Commodities", "name": "CNH London Tin Mini Futures"},
    "LRZ": {"category": "Commodities", "name": "CNH London Zinc Mini Futures"},
}


def to_hk_symbol(symbol: str) -> str:
    """Normalize a user-provided symbol to a bare HKEX stock code.

    Accepts ``'700'``, ``'00700'``, ``'00700.HK'``, ``'0700.HK'`` —
    returns ``'700'`` (leading zeros stripped, for the widget API).
    """
    s = str(symbol).upper().split(".")[0]
    return s.lstrip("0") or "0"


def to_padded_code(symbol: str) -> str:
    """Zero-pad a stock code to the canonical 5-digit string used by the master."""
    return to_hk_symbol(symbol).zfill(5)


def parse_num(s: Any) -> float | None:
    """Parse an HKEX-formatted number string ('143.900', '17,936', '') into float."""
    if s is None or s in {"", "-", "—"}:
        return None
    try:
        return float(str(s).replace(",", ""))
    except (TypeError, ValueError):
        return None


def parse_int(s: Any) -> int | None:
    """Parse an HKEX integer string ('17,936', '', '—') into int."""
    v = parse_num(s)
    return int(v) if v is not None else None


def _hkex_api_base() -> str:
    """Mounted base path of the HKEX router widget routes ({api_prefix}/hkex)."""
    from openbb_core.app.service.system_service import SystemService

    return f"{SystemService().system_settings.api_settings.prefix or ''}/hkex"


SYMBOL_CHOICES_ENDPOINT = f"{_hkex_api_base()}/security_choices"
OPTION_UNDERLYINGS_ENDPOINT = f"{_hkex_api_base()}/option_underlyings"


def symbol_widget_config(multi: bool = False) -> dict:
    """Workspace endpoint-dropdown config for a ``symbol`` field."""
    cfg: dict[str, Any] = {
        "type": "endpoint",
        "optionsEndpoint": SYMBOL_CHOICES_ENDPOINT,
        "description": (
            "HKEX security code. Pick from the list or type a code / name."
        ),
        "style": {"popupWidth": 600},
    }
    if multi:
        cfg["multiSelect"] = True
    return {"hkex": {"x-widget_config": cfg}}
