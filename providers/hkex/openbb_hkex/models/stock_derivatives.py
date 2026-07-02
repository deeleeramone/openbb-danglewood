"""HKEX Stock Derivatives roster fetcher (custom model).

Lists every stock with listed single-stock options or single-stock futures,
along with its 3-letter ATS ticker (use that as `symbol` when calling
`options.chains` or `derivatives.futures.curve` with this provider).
"""

from __future__ import annotations

from typing import Any, Literal

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field

from openbb_hkex.utils.client import call_widget, parse_int


class HkexStockDerivativesQueryParams(QueryParams):
    """HKEX Stock Derivatives query."""

    kind: Literal["options", "futures", "all"] = Field(
        default="options",
        description="'options' = stocks with SSOs (~139), 'futures' = SSFs (~92), "
        "'all' = combined list.",
        json_schema_extra={"choices": ["options", "futures", "all"]},
    )


class HkexStockDerivativesData(Data):
    """HKEX Stock Derivatives row."""

    ats_code: str = Field(description="3-letter ATS ticker (e.g. TCH for Tencent).")
    stock_code: str = Field(description="HKEX 5-digit stock code (zero-padded).")
    name: str = Field(description="Underlying short name.")
    option_activity: int | None = Field(
        default=None, description="Current option OI/volume on the underlying."
    )
    future_activity: int | None = Field(
        default=None, description="Current futures OI/volume on the underlying."
    )


class HkexStockDerivativesFetcher(
    Fetcher[HkexStockDerivativesQueryParams, list[HkexStockDerivativesData]]
):
    """HKEX Stock Derivatives fetcher."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> HkexStockDerivativesQueryParams:
        """Transform the query parameters."""
        return HkexStockDerivativesQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: HkexStockDerivativesQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the data from the HKEX endpoints."""
        type_map = {"all": 0, "futures": 1, "options": 2}
        data = await call_widget("getstockderivativeslist", type=type_map[query.kind])
        return data.get("stocklist", [])

    @staticmethod
    def transform_data(
        query: HkexStockDerivativesQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[HkexStockDerivativesData]:
        """Transform the raw data into the model."""
        out: list[HkexStockDerivativesData] = []
        for r in data:
            out.append(
                HkexStockDerivativesData(
                    ats_code=r.get("cd", ""),
                    stock_code=str(r.get("sym") or "").zfill(5),
                    name=r.get("nm", ""),
                    option_activity=parse_int(r.get("opt")),
                    future_activity=parse_int(r.get("fut")),
                )
            )
        return out
