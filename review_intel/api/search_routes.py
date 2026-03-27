# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""关键词检索与「库内 + 实时 Dummy 抓取」合并 API。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from review_intel.adapters.dummy import DummyAdapter
from review_intel.api.merge import merge_cached_and_live
from review_intel.api.registry import JobRegistry, assert_safe_job_id
from review_intel.api.schemas import (
    KeywordSearchResponse,
    KeywordSearchRunRequest,
    KeywordSearchRunResponse,
    SearchHit,
)
from review_intel.api.search_service import load_normalized_for_job, scan_storage_for_keyword
from review_intel.jobs.models import CollectionJob, FreshnessLevel, QueryIntent, QuerySpec
from review_intel.jobs.runner import ReviewCollectionRunner
from review_intel.schemas.enums import JobStatus, PlatformType
from review_intel.storage.sqlite_support import open_review_intel_stores


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _collection_job_for_keyword(keyword: str, job_id: str) -> CollectionJob:
    terms = [t for t in keyword.replace(",", " ").split() if t.strip()]
    if not terms:
        terms = ["demo"]
    spec = QuerySpec(
        industry="web",
        category="search",
        brand=None,
        intent=QueryIntent.PAINPOINT_SEARCH,
        terms=terms,
        negative_terms=[],
        time_window=None,
        platforms=[PlatformType.XHS],
    )
    return CollectionJob(
        job_id=job_id,
        industry=spec.industry,
        category=spec.category,
        brand=None,
        query_spec=spec,
        target_types=["post", "comment"],
        priority=0,
        freshness_level=FreshnessLevel.NORMAL,
        status=JobStatus.PENDING,
        owner="keyword-search-ui",
    )


def get_registry(request: Request) -> JobRegistry:
    return request.app.state.registry


def build_search_router() -> APIRouter:
    router = APIRouter(prefix="/api", tags=["review_intel_search"])

    @router.get("/search", response_model=KeywordSearchResponse)
    def search_keyword(
        q: str,
        registry: JobRegistry = Depends(get_registry),
    ) -> KeywordSearchResponse:
        """仅扫描已有 ``store.db``，按关键词过滤并去重。"""
        kw = (q or "").strip()
        if not kw:
            raise HTTPException(status_code=400, detail="query_param_q_required")
        root = registry.storage_root
        pairs = scan_storage_for_keyword(root, kw)
        hits = [SearchHit(provenance="cache", job_id=jid, review=r) for jid, r in pairs]
        merged, dropped = merge_cached_and_live(hits, [])
        return KeywordSearchResponse(
            keyword=kw,
            total=len(merged),
            dedupe_dropped=dropped,
            items=merged,
        )

    @router.post("/search/run", response_model=KeywordSearchRunResponse)
    async def search_and_run(
        body: KeywordSearchRunRequest,
        registry: JobRegistry = Depends(get_registry),
    ) -> KeywordSearchRunResponse:
        """先扫库，再创建作业并同步执行 Dummy 采集，合并去重后返回。"""
        kw = body.keyword.strip()
        if not kw:
            raise HTTPException(status_code=400, detail="keyword_required")

        jid = body.job_id
        if jid is not None:
            try:
                assert_safe_job_id(jid)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from e
        else:
            jid = f"job-{uuid.uuid4().hex[:12]}"

        root = registry.storage_root
        cache_pairs = scan_storage_for_keyword(root, kw)
        cache_hits = [SearchHit(provenance="cache", job_id=j, review=r) for j, r in cache_pairs]

        job = _collection_job_for_keyword(kw, jid)
        registry.put_job(job)
        job_running = job.model_copy(update={"status": JobStatus.RUNNING, "updated_at": _utc_now()})
        registry.put_job(job_running)

        db_path = registry.store_path(jid)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        raw_store, norm_store = open_review_intel_stores(db_path)

        try:
            summary = await ReviewCollectionRunner().run(
                job,
                DummyAdapter(),
                raw_store,
                norm_store,
            )
        except Exception as e:  # noqa: BLE001
            failed = job.model_copy(update={"status": JobStatus.FAILED, "updated_at": _utc_now()})
            registry.put_job(failed)
            return KeywordSearchRunResponse(
                keyword=kw,
                job_id=jid,
                summary=None,
                error=repr(e),
                cache_hits=len(cache_hits),
                live_hits=0,
                total=0,
                dedupe_dropped=0,
                items=[],
            )

        done = job.model_copy(update={"status": JobStatus.SUCCEEDED, "updated_at": _utc_now()})
        registry.put_job(done)
        registry.set_summary(jid, summary)

        live_reviews = load_normalized_for_job(db_path)
        live_hits = [SearchHit(provenance="live", job_id=jid, review=r) for r in live_reviews]

        merged, dropped = merge_cached_and_live(cache_hits, live_hits)
        return KeywordSearchRunResponse(
            keyword=kw,
            job_id=jid,
            summary=summary,
            error=None,
            cache_hits=len(cache_hits),
            live_hits=len(live_hits),
            total=len(merged),
            dedupe_dropped=dropped,
            items=merged,
        )

    return router
