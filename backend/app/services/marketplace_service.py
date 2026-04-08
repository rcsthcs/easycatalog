from __future__ import annotations

import asyncio
import logging
import time
from uuid import uuid4

from app.adapters.base import MarketplaceAdapter
from app.adapters.kaspi import KaspiAdapter
from app.adapters.ozon import OzonAdapter
from app.adapters.wildberries import WildberriesAdapter
from app.core.config import settings
from app.core.http_client import RequestClient
from app.core.proxy_manager import ProxyManager
from app.schemas.models import ProductDetail, SearchResponse, SourceName, SourceResult

logger = logging.getLogger(__name__)


class MarketplaceService:
    def __init__(self, proxy_manager: ProxyManager):
        client = RequestClient(proxy_manager)
        self.adapters: dict[SourceName, MarketplaceAdapter] = {
            SourceName.kaspi: KaspiAdapter(client),
            SourceName.wildberries: WildberriesAdapter(client),
            SourceName.ozon: OzonAdapter(client),
        }
        per_source_limit = max(1, settings.source_concurrency_limit)
        self._source_semaphores: dict[SourceName, asyncio.Semaphore] = {
            source: asyncio.Semaphore(per_source_limit) for source in self.adapters
        }

    async def _run_with_source_limit(self, source: SourceName, operation):
        semaphore = self._source_semaphores[source]
        async with semaphore:
            return await operation

    async def search(self, query: str, request_id: str | None = None) -> SearchResponse:
        request_id = request_id or str(uuid4())

        async def run_source(source: SourceName, adapter: MarketplaceAdapter) -> SourceResult:
            started_at = time.perf_counter()
            try:
                items = await self._run_with_source_limit(
                    source,
                    adapter.search(query, limit=settings.max_items_per_source),
                )
                logger.info(
                    "search_source_done request_id=%s source=%s items=%s latency_ms=%s",
                    request_id,
                    source.value,
                    len(items),
                    int((time.perf_counter() - started_at) * 1000),
                )
                return SourceResult(source=source, items=items)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "search_source_failed request_id=%s source=%s latency_ms=%s err=%s",
                    request_id,
                    source.value,
                    int((time.perf_counter() - started_at) * 1000),
                    exc,
                )
                return SourceResult(source=source, items=[], error=str(exc))

        tasks = [run_source(source, adapter) for source, adapter in self.adapters.items()]
        results = await asyncio.gather(*tasks)
        logger.info(
            "search_request_done request_id=%s query_len=%s sources=%s",
            request_id,
            len(query),
            len(results),
        )
        return SearchResponse(query=query, results=results)

    async def get_product_details(self, source: SourceName, product_url: str, request_id: str | None = None) -> ProductDetail:
        request_id = request_id or str(uuid4())
        started_at = time.perf_counter()
        adapter = self.adapters[source]
        detail = await self._run_with_source_limit(source, adapter.get_product_details(product_url))
        logger.info(
            "detail_request_done request_id=%s source=%s latency_ms=%s",
            request_id,
            source.value,
            int((time.perf_counter() - started_at) * 1000),
        )
        return detail
