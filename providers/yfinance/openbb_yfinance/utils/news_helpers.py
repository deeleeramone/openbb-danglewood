"""Yahoo Finance news helpers — full article body retrieval."""

import html
import re

_CAAS_URL = "https://finance.yahoo.com/caas/content/article/"
_DROP_BLOCKS = re.compile(
    r"<(script|style|figure|aside|table|form)[^>]*>.*?</\1>", re.S | re.I
)
_BLOCK = re.compile(r"<(h[1-6]|p|li)[^>]*>(.*?)</\1>", re.S | re.I)
_TAGS = re.compile(r"<[^>]+>")


def markup_to_markdown(markup: str) -> str:
    """Convert a Yahoo CAAS article markup blob into readable markdown text."""
    if not markup:
        return ""
    cleaned = _DROP_BLOCKS.sub(" ", markup)
    blocks: list[str] = []
    for match in _BLOCK.finditer(cleaned):
        tag = match.group(1).lower()
        text = html.unescape(_TAGS.sub("", match.group(2))).strip()
        text = re.sub(r"\s+", " ", text)
        if len(text) < 2:
            continue
        if tag.startswith("h"):
            blocks.append(f"## {text}")
        elif tag == "li":
            blocks.append(f"- {text}")
        else:
            blocks.append(text)
    return "\n\n".join(blocks)


def get_article_body(uuid: str | None) -> str | None:
    """Fetch the full article body for a Yahoo news ``uuid`` as markdown text.

    The yfinance library exposes only the article summary, so the full body is
    read from Yahoo's CAAS content endpoint.
    """
    from yfinance.data import YfData

    if not uuid:
        return None
    try:
        response = YfData().get(url=_CAAS_URL, params={"uuid": uuid}, timeout=15)
        items = response.json().get("items") or []
        markup = items[0].get("markup", "") if items else ""
        return markup_to_markdown(markup) or None
    except Exception:
        return None
