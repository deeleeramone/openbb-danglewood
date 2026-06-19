"""Yahoo Finance News Model."""

from datetime import datetime
from typing import Any

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field, model_validator


class YFinanceNewsQueryParams(QueryParams):
    """YFinance News Query.

    Source: https://finance.yahoo.com/news/
    """

    query: str | None = Field(default=None, description="Free-text news search query.")
    symbol: str | None = Field(
        default=None, description="A ticker symbol to fetch news for."
    )
    limit: int = Field(
        default=20, description="The maximum number of results to return."
    )
    fetch_body: bool = Field(
        default=True,
        description="Fetch the full article body for each result. Disable for a"
        + " faster response with only the headline and excerpt.",
    )

    @model_validator(mode="after")
    def _require_query_or_symbol(self):
        """Require at least one of query or symbol."""
        if not self.query and not self.symbol:
            raise ValueError("Either 'query' or 'symbol' must be provided.")
        return self


class YFinanceNewsData(Data):
    """YFinance News Data."""

    title: str = Field(description="The title of the article.")
    date: datetime | None = Field(
        default=None, description="The date the article was published."
    )
    author: str | None = Field(
        default=None, description="The publisher/author of the article."
    )
    excerpt: str | None = Field(
        default=None, description="A short preview of the article."
    )
    body: str | None = Field(
        default=None, description="The full article body, as markdown text."
    )
    url: str | None = Field(default=None, description="The URL to the article.")
    symbols: str | None = Field(
        default=None, description="Comma-separated symbols related to the article."
    )


class YFinanceNewsFetcher(Fetcher[YFinanceNewsQueryParams, list[YFinanceNewsData]]):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> YFinanceNewsQueryParams:
        """Transform query params."""
        return YFinanceNewsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceNewsQueryParams,
        credentials: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the raw data from Yahoo Finance."""
        import asyncio

        from openbb_core.provider.utils.errors import EmptyDataError

        from openbb_yfinance.utils.news_helpers import get_article_body
        from yfinance import Search, Ticker

        def _normalize(item: dict) -> dict | None:
            """Flatten a Yahoo news item to a flat record."""
            if not isinstance(item, dict):
                return None
            content = item.get("content")
            content = content if isinstance(content, dict) else item
            title = content.get("title") or content.get("summary")
            if not title:
                return None
            url = None
            for key in ("clickThroughUrl", "canonicalUrl"):
                node = content.get(key)
                if isinstance(node, dict) and node.get("url"):
                    url = node["url"]
                    break
            url = url or content.get("previewUrl") or content.get("link")
            provider = content.get("provider")
            author = (
                provider.get("displayName")
                if isinstance(provider, dict)
                else content.get("publisher")
            )
            return {
                "uuid": item.get("id") or content.get("id"),
                "date": content.get("pubDate") or content.get("displayTime"),
                "title": title,
                "author": author,
                "excerpt": content.get("summary") or content.get("description"),
                "url": url,
                "symbols": query.symbol,
            }

        def _fetch() -> list[dict]:
            """Fetch the news list in a worker thread."""
            if query.symbol:
                raw = Ticker(query.symbol).get_news(count=query.limit) or []
            else:
                raw = Search(query.query, news_count=query.limit).news or []
            out: list[dict] = []
            for item in raw:
                norm = _normalize(item)
                if norm:
                    out.append(norm)
            return out[: query.limit]

        results = await asyncio.to_thread(_fetch)

        if not results:
            raise EmptyDataError("No news was returned for the given query.")

        if query.fetch_body:
            bodies = await asyncio.gather(
                *(asyncio.to_thread(get_article_body, r.get("uuid")) for r in results)
            )
            for record, body in zip(results, bodies, strict=False):
                record["body"] = body or record.get("excerpt")
        else:
            for record in results:
                record["body"] = record.get("excerpt")

        for record in results:
            record.pop("uuid", None)

        return results

    @staticmethod
    def transform_data(
        query: YFinanceNewsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceNewsData]:
        """Transform the data."""
        return [YFinanceNewsData.model_validate(d) for d in data]
