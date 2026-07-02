"""Index constituent sources for Hang Seng Indexes Company indices.

HKEX does not publish index weightings (the indices are compiled by Hang Seng
Indexes Company). The authoritative open sources are:

* ``constituents.do`` — full constituent list (code, name, share class), no weight
* the index factsheet PDF — the only open weighting source, published for the
  **top 50** constituents only.

This module fetches both and merges them: every constituent from the list, with
the factsheet weight attached where published (``weight=None`` for the tail
beyond the top 50).
"""

from __future__ import annotations

import io
import re

from async_lru import alru_cache
from openbb_core.provider.utils.helpers import amake_request

from openbb_hkex.utils.client import (
    _bytes_callback,
    _common_headers,
    _text_callback,
    parse_num,
    to_hk_symbol,
)

HSI_BASE = "https://www.hsi.com.hk"
_HSI_REFERER = f"{HSI_BASE}/eng/indexes/all-indexes/hsi"

# Index RIC -> (constituents.do slug, factsheet PDF basename)
CONSTITUENT_INDEXES: dict[str, tuple[str, str]] = {
    ".HSI": ("hsi", "hsie"),
    ".HSCE": ("hscei", "hsceie"),
    ".HSTECH": ("hstech", "hsteche"),
    ".HSCI": ("hsci", "hscie"),
    ".HSHDYI": ("hshdyi", "hshdyie"),
    ".HSBIO": ("hsbio", "hsbioe"),
    ".HSIII": ("hsiii", "hsiiie"),
    ".HSIESG": ("hsiesg", "hsiesge"),
    ".HSSCHK": ("hsschk", "hsschke"),
}

# RIC -> human label for Workspace dropdowns.
INDEX_LABELS: dict[str, str] = {
    ".HSI": "Hang Seng Index (HSI)",
    ".HSCE": "Hang Seng China Enterprises (HSCEI)",
    ".HSTECH": "Hang Seng TECH (HSTECH)",
    ".HSCI": "Hang Seng Composite (HSCI)",
    ".HSHDYI": "Hang Seng High Dividend Yield (HSHDYI)",
    ".HSBIO": "Hang Seng Biotech (HSBIO)",
    ".HSIII": "Hang Seng Internet & IT (HSIII)",
    ".HSIESG": "HSI ESG Index (HSIESG)",
    ".HSSCHK": "Hang Seng Stock Connect HK (HSSCHK)",
}

# Hang Seng Industry Classification System — the 12 industries, longest first so
# multi-word names match before their prefixes.
_INDUSTRIES = [
    "Consumer Discretionary",
    "Consumer Staples",
    "Information Technology",
    "Properties & Construction",
    "Telecommunications",
    "Conglomerates",
    "Financials",
    "Healthcare",
    "Materials",
    "Energy",
    "Utilities",
    "Industrials",
]
_SHARE_TYPES = [
    "Other HK-listed Mainland Co.",
    "HK Ordinary",
    "H Share",
    "Red Chip",
    "A Share",
    "B Share",
    "P Chip",
    "Foreign Company",
]
_ROW_RE = re.compile(r"^(\d{4,5})\s+([A-Z0-9]{12})\s+(.*?)\s+([\d.]+)$")


def normalize_ric(symbol: str) -> str:
    """Normalize a user index symbol to a leading-dot RIC, e.g. ``HSI`` -> ``.HSI``."""
    s = str(symbol).strip().upper()
    return s if s.startswith(".") else f".{s}"


def _hsi_headers(accept: str = "*/*") -> dict[str, str]:
    h = _common_headers(_HSI_REFERER)
    h["Accept"] = accept
    return h


async def fetch_constituent_list(slug: str) -> list[dict]:
    """Full constituent list for an index slug from ``constituents.do``."""
    import json

    raw = await amake_request(
        f"{HSI_BASE}/data/eng/rt/index-series/{slug}/constituents.do",
        headers=_hsi_headers("application/json"),
        response_callback=_text_callback,
    )
    payload = json.loads(raw)
    out: list[dict] = []
    seen: set[str] = set()
    for series in payload.get("indexSeriesList") or []:
        for idx in series.get("indexList") or []:
            for c in idx.get("constituentContent") or []:
                code = to_hk_symbol(str(c.get("code") or ""))
                if not code or code in seen:
                    continue
                seen.add(code)
                out.append(
                    {
                        "symbol": code,
                        "name": c.get("constituentName"),
                        "share_class": c.get("type") or None,
                    }
                )
    return out


async def fetch_sector_membership(slug: str) -> list[dict]:
    """Tag each constituent of an index *series* with its sector.

    ``constituents.do`` for the Hang Seng Composite Industry series returns one
    ``indexList`` entry per sub-index, each carrying an ``indexName`` like
    ``"Hang Seng Composite Industry Index - Energy"``. The 12 groups are the
    top level of the HSIC and are exposed here as *sectors* (the finer industry
    level is only on the per-symbol quote and is not crawled). We match the
    index name against the 12 groups and tag every constituent. Returns
    ``[{symbol, sector, name}, ...]`` (empty if the series has no such
    sub-indexes).
    """
    import json

    raw = await amake_request(
        f"{HSI_BASE}/data/eng/rt/index-series/{slug}/constituents.do",
        headers=_hsi_headers("application/json"),
        response_callback=_text_callback,
    )
    payload = json.loads(raw)
    out: list[dict] = []
    for series in payload.get("indexSeriesList") or []:
        for idx in series.get("indexList") or []:
            name = (idx.get("indexName") or "").strip()
            low = name.lower()
            sector = next((i for i in _INDUSTRIES if i.lower() in low), None)
            if not sector:
                continue
            for c in idx.get("constituentContent") or []:
                code = to_hk_symbol(str(c.get("code") or ""))
                if code:
                    out.append(
                        {
                            "symbol": code,
                            "sector": sector,
                            "name": c.get("constituentName"),
                        }
                    )
    return out


_DL_BASE = "/static/uploads/contents/en/dl_centre"

# Download-centre manifests: kind -> (manifest path, display label). The per-index
# PDF field (``factsheetFile`` / ``methodologyFile`` / ``brochureFile``) is
# auto-detected, so every uniform ``indexSeriesList`` manifest works the same way.
_DOC_MANIFESTS: dict[str, tuple[str, str]] = {
    "factsheet": ("/data/eng/download/factsheets.json", "Factsheet"),
    "methodology": ("/data/eng/download/index-methodologies.json", "Methodology"),
    "brochure": ("/data/eng/download/brochures.json", "Brochure"),
}


def _doc_file(entry: dict) -> str | None:
    """Return the first ``*File`` PDF path on a manifest entry."""
    for key, value in entry.items():
        if key.endswith("File") and isinstance(value, str) and value.endswith(".pdf"):
            return value
    return None


@alru_cache(maxsize=8)
async def fetch_document_manifest(kind: str) -> list[dict]:
    """Flatten an HSI download-centre manifest into ``[{code, name, series, file}]``.

    Covers every index (recursing into sub-indexes), deduplicated by document URL.
    """
    import json

    path, _ = _DOC_MANIFESTS[kind]
    raw = await amake_request(
        f"{HSI_BASE}{path}",
        headers=_hsi_headers("application/json"),
        response_callback=_text_callback,
    )
    payload = json.loads(raw)
    out: list[dict] = []
    seen: set[str] = set()

    def _walk(series: str, items: list) -> None:
        for it in items or []:
            code = (it.get("indexShortName") or "").strip()
            doc = _doc_file(it)
            if doc and doc not in seen:
                seen.add(doc)
                out.append(
                    {
                        "kind": kind,
                        "code": code or None,
                        "name": it.get("indexName"),
                        "series": series,
                        "category": it.get("categoryName"),
                        "file": doc,
                    }
                )
            _walk(series, it.get("subIndexList"))

    for s in payload.get("indexSeriesList") or []:
        _walk(s.get("seriesName") or "", s.get("indexList"))
    return out


async def fetch_document_catalog() -> list[dict]:
    """Aggregate every published HSI PDF (factsheets, methodologies, brochures)."""
    out: list[dict] = []
    for kind, (_, label) in _DOC_MANIFESTS.items():
        try:
            for entry in await fetch_document_manifest(kind):
                out.append({**entry, "label": label})
        except Exception:  # noqa: BLE001,S112 — one bad manifest shouldn't sink the rest
            continue
    return out


@alru_cache(maxsize=16)
async def _factsheet_text(path: str) -> str:
    """Download and extract the text of a factsheet PDF (cached by path)."""
    import pypdf

    data = await amake_request(
        f"{HSI_BASE}{path}",
        headers=_hsi_headers("application/pdf"),
        response_callback=_bytes_callback,
    )
    reader = pypdf.PdfReader(io.BytesIO(data))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def _parse_weights(text: str) -> dict[str, dict]:
    """Parse the top-50 constituent rows of a factsheet into ``{code: {...}}``."""
    weights: dict[str, dict] = {}
    for line in text.splitlines():
        m = _ROW_RE.match(line.strip())
        if not m:
            continue
        code, isin, mid, w = m.groups()
        stype = next((s for s in _SHARE_TYPES if mid.endswith(s)), None)
        mid2 = mid[: -len(stype)].strip() if stype else mid
        industry = next((i for i in _INDUSTRIES if mid2.endswith(i)), None)
        name = mid2[: -len(industry)].strip() if industry else mid2
        weights[to_hk_symbol(code)] = {
            "weight": parse_num(w),
            "isin": isin,
            "sector": industry,
            "share_type": stype,
            "name": name or None,
        }
    return weights


async def fetch_factsheet_weights(basename: str) -> dict[str, dict]:
    """Parse the index factsheet PDF (top-50) into ``{code: {weight, isin, ...}}``."""
    return _parse_weights(
        await _factsheet_text(f"{_DL_BASE}/factsheets/{basename}.pdf")
    )


# Dated index-report manifests (per index family, by date).
_REPORT_MANIFESTS: dict[str, str] = {
    "daily-bulletin": "/data/eng/download/daily-bulletin.json",
    "daily-bulletin-month-end": "/data/eng/download/daily-bulletin-month-end.json",
}


@alru_cache(maxsize=4)
async def fetch_report_manifest(name: str) -> list[dict]:
    """Return the ``indexSeriesList`` of a dated-report manifest."""
    import json

    raw = await amake_request(
        f"{HSI_BASE}{_REPORT_MANIFESTS[name]}",
        headers=_hsi_headers("application/json"),
        response_callback=_text_callback,
    )
    return json.loads(raw).get("indexSeriesList") or []


async def report_series_choices() -> list[dict]:
    """Index-family options for the dated-report viewer (value = series code)."""
    return [
        {"label": s.get("seriesName"), "value": s.get("seriesCode")}
        for s in await fetch_report_manifest("daily-bulletin")
        if s.get("seriesCode")
    ]


def _fmt_report_date(value: str) -> str:
    """Format ``2026-06-01 00:00:00`` as ``01 Jun 2026``."""
    from datetime import datetime

    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%d %b %Y")
    except (ValueError, TypeError):
        return value or ""


async def report_date_choices(series: str, report_type: str) -> list[dict]:
    """Dated PDF options for a series + report type (``<manifest>:<reportType>``).

    Newest first; value is the absolute PDF URL.
    """
    manifest, _, rtype = report_type.partition(":")
    if manifest not in _REPORT_MANIFESTS:
        return []
    series_list = await fetch_report_manifest(manifest)
    entry = next((s for s in series_list if s.get("seriesCode") == series), None)
    if not entry:
        return []
    dated: list[tuple[str, str]] = []
    for rep in entry.get("reportList") or []:
        if rep.get("reportType") != rtype:
            continue
        for d in rep.get("reportDate") or []:
            url = d.get("url")
            if url:
                dated.append((d.get("date") or "", url))
    dated.sort(key=lambda x: x[0], reverse=True)
    return [
        {"label": _fmt_report_date(date), "value": f"{HSI_BASE}{url}"}
        for date, url in dated
    ]


_BULLETIN_FIELDS: tuple[tuple[str, bool], ...] = (
    ("trade_date", False),
    ("index", False),
    ("currency", False),
    ("high", True),
    ("low", True),
    ("close", True),
    ("change", True),
    ("change_pct", True),
    ("dividend_yield", True),
    ("pe_ratio", True),
    ("index_turnover_m", True),
    ("market_turnover_m", True),
    ("fx_rate", True),
)


async def fetch_index_bulletin(series: str, url: str | None = None) -> list[dict]:
    """Parse a Hang Seng Index Daily Bulletin (per-index performance) into rows.

    The bulletin is a UTF-16, tab-separated CSV with bilingual headers. Defaults
    to the latest available date for the family when ``url`` is omitted.
    """
    import re as _re

    if not url:
        series_list = await fetch_report_manifest("daily-bulletin")
        entry = next((s for s in series_list if s.get("seriesCode") == series), None)
        rep = next(
            (
                r
                for r in (entry or {}).get("reportList") or []
                if r.get("reportType") == "idx"
            ),
            None,
        )
        dated = sorted(
            (rep or {}).get("reportDate") or [],
            key=lambda d: d.get("date") or "",
            reverse=True,
        )
        if not dated:
            return []
        url = dated[0]["url"]
    path = url[len(HSI_BASE) :] if url.startswith(HSI_BASE) else url
    data = await amake_request(
        f"{HSI_BASE}{path}",
        headers=_hsi_headers("text/csv"),
        response_callback=_bytes_callback,
    )
    text = data.decode("utf-16", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    start = next((i for i, ln in enumerate(lines) if "Trade Date" in ln), 0)
    out: list[dict] = []
    for ln in lines[start + 1 :]:
        cells = [c.strip().strip('"') for c in ln.split("\t")]
        if len(cells) < len(_BULLETIN_FIELDS):
            continue
        row: dict = {}
        for (key, numeric), raw in zip(_BULLETIN_FIELDS, cells):
            if numeric:
                row[key] = parse_num(raw)
            elif key == "index":
                row[key] = _re.split(r"[一-鿿]", raw)[0].strip() or raw
            else:
                row[key] = raw or None
        out.append(row)
    return out


async def fetch_index_constituents(ric: str) -> list[dict]:
    """Merge the full constituent list with factsheet weights for an index RIC.

    Raises ``UnsupportedIndexError`` for indices with no Hang Seng constituent
    source wired.
    """
    slug_file = CONSTITUENT_INDEXES.get(ric)
    if not slug_file:
        raise UnsupportedIndexError(ric)
    slug, basename = slug_file

    listing = await fetch_constituent_list(slug)
    try:
        weights = await fetch_factsheet_weights(basename)
    except Exception:  # noqa: BLE001 — list is still useful without weights
        weights = {}

    for row in listing:
        w = weights.get(row["symbol"])
        if w:
            row.update(w)
    return listing


class UnsupportedIndexError(Exception):
    """Raised when an index has no Hang Seng source wired."""

    def __init__(self, index: str) -> None:
        super().__init__(f"No Hang Seng source is wired for index '{index}'.")
