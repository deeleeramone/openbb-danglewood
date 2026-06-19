"""Yahoo Finance sector and industry choice catalogs for Workspace dropdowns.

Sourced from yfinance's bundled ``SECTOR_INDUSTY_MAPPING_LC`` so the dropdowns
carry the real Yahoo sector/industry keys — no guessing, no network call.
"""

from openbb_core.app.service.system_service import SystemService

from yfinance.const import SECTOR_INDUSTY_MAPPING_LC

_API_PREFIX = SystemService().system_settings.api_settings.prefix

INDUSTRY_CHOICES_ENDPOINT = f"{_API_PREFIX}/yfinance/industry_choices"

SECTOR_KEYS: list[str] = list(SECTOR_INDUSTY_MAPPING_LC)

INDUSTRY_BY_SECTOR: dict[str, list[str]] = {
    sector: list(industries) for sector, industries in SECTOR_INDUSTY_MAPPING_LC.items()
}


def label_from_slug(slug: str) -> str:
    """Turn a Yahoo slug ('financial-services') into a label ('Financial Services')."""
    return slug.replace("—", " — ").replace("-", " ").title()


SECTOR_OPTIONS: list[dict] = [
    {"label": label_from_slug(s), "value": s} for s in SECTOR_KEYS
]

MARKET_OPTION: dict = {"label": "Market (All Sectors)", "value": ""}

SECTOR_OPTIONS_WITH_MARKET: list[dict] = [MARKET_OPTION, *SECTOR_OPTIONS]


def sector_keys(sector: str | None) -> list[str]:
    """Resolve a sector query to a list of keys; empty/None means every sector."""
    keys: list[str] = [
        s.strip().lower() for s in (sector or "").split(",") if s.strip()
    ]
    if not keys:
        return list(SECTOR_KEYS)
    return keys


def industry_keys(sector: str | None) -> list[str]:
    """Industry keys for the given sector(s); every industry when none is given."""
    seen: set[str] = set()
    result: list[str] = []
    for key in sector_keys(sector):
        for industry in INDUSTRY_BY_SECTOR.get(key, []):
            if industry not in seen:
                seen.add(industry)
                result.append(industry)
    return result


def industry_options(sector: str | None = None) -> list[dict]:
    """Return ``[{label, value}]`` industry choices for a sector (all when empty)."""
    return [{"label": label_from_slug(i), "value": i} for i in industry_keys(sector)]
