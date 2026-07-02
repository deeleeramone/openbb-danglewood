"""HKEX Derivative Products fetcher (custom model — static catalog)."""

from __future__ import annotations

from typing import Any, Literal

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field

from openbb_hkex.utils.client import DERIVATIVE_PRODUCTS

DerivativeCategory = Literal[
    "Equity-Index", "Foreign-Exchange", "Interest-Rate", "Commodities"
]
DERIVATIVE_CATEGORY_CHOICES: list[str] = list(
    DerivativeCategory.__args__  # type: ignore[attr-defined]
)


class HkexDerivativeProductsQueryParams(QueryParams):
    """HKEX Derivative Products query."""

    category: DerivativeCategory | None = Field(
        default=None,
        description="Filter by product category.",
        json_schema_extra={"choices": DERIVATIVE_CATEGORY_CHOICES},
    )


class HkexDerivativeProductsData(Data):
    """HKEX Derivative Products row."""

    code: str = Field(description="HKEX ATS contract code, e.g. HSI / HHI / GDU / CUS.")
    name: str = Field(description="Full product name.")
    category: str = Field(
        description="Equity-Index / Foreign-Exchange / Interest-Rate / Commodities."
    )


class HkexDerivativeProductsFetcher(
    Fetcher[HkexDerivativeProductsQueryParams, list[HkexDerivativeProductsData]]
):
    """HKEX Derivative Products fetcher (no network call — static catalog)."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> HkexDerivativeProductsQueryParams:
        """Transform the query parameters."""
        return HkexDerivativeProductsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: HkexDerivativeProductsQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the data from the HKEX endpoints."""
        return [
            {"code": code, **info}
            for code, info in DERIVATIVE_PRODUCTS.items()
            if not query.category or info["category"] == query.category
        ]

    @staticmethod
    def transform_data(
        query: HkexDerivativeProductsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[HkexDerivativeProductsData]:
        """Transform the raw data into the model."""
        return [HkexDerivativeProductsData(**r) for r in data]
