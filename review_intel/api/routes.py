# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""review_intel 作业相关 HTTP 路由。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from review_intel.adapters.dummy import DummyAdapter
from review_intel.api.registry import JobRegistry, assert_safe_job_id
from review_intel.api.schemas import (
    CreateJobRequest,
    JobCreateResponse,
    JobDetailResponse,
    JobReviewsResponse,
    JobSummaryResponse,
)
from review_intel.jobs.runner import ReviewCollectionRunner
from review_intel.schemas.enums import JobStatus
from review_intel.storage.sqlite_support import open_review_intel_stores


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_registry(request: Request) -> JobRegistry:
    return request.app.state.registry


def build_router() -> APIRouter:
    router = APIRouter(tags=["review_intel_jobs"])

    @router.post("/jobs", response_model=JobCreateResponse)
    async def create_job(
        body: CreateJobRequest,
        registry: JobRegistry = Depends(get_registry),
    ) -> JobCreateResponse:
        job = body.to_collection_job()
        registry.put_job(job)

        if not body.execute:
            return JobCreateResponse(
                job=job,
                executed=False,
                summary=None,
                error=None,
            )

        job = job.model_copy(update={"status": JobStatus.RUNNING, "updated_at": _utc_now()})
        registry.put_job(job)

        db_path = registry.store_path(job.job_id)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        raw_store, norm_store = open_review_intel_stores(db_path)

        try:
            summary = await ReviewCollectionRunner().run(
                job,
                DummyAdapter(),
                raw_store,
                norm_store,
            )
        except Exception as e:  # noqa: BLE001 — 调试 API 返回 repr
            failed = job.model_copy(update={"status": JobStatus.FAILED, "updated_at": _utc_now()})
            registry.put_job(failed)
            return JobCreateResponse(
                job=failed,
                executed=True,
                summary=None,
                error=repr(e),
            )

        done = job.model_copy(update={"status": JobStatus.SUCCEEDED, "updated_at": _utc_now()})
        registry.put_job(done)
        registry.set_summary(job.job_id, summary)
        return JobCreateResponse(
            job=done,
            executed=True,
            summary=summary,
            error=None,
        )

    @router.get("/jobs/{job_id}", response_model=JobDetailResponse)
    def get_job(
        job_id: str,
        registry: JobRegistry = Depends(get_registry),
    ) -> JobDetailResponse:
        try:
            assert_safe_job_id(job_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        job = registry.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job_not_found")
        summary = registry.get_summary(job_id)
        return JobDetailResponse(job=job, summary=summary)

    @router.get("/jobs/{job_id}/reviews", response_model=JobReviewsResponse)
    def list_job_reviews(
        job_id: str,
        registry: JobRegistry = Depends(get_registry),
    ) -> JobReviewsResponse:
        try:
            assert_safe_job_id(job_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if registry.get_job(job_id) is None:
            raise HTTPException(status_code=404, detail="job_not_found")

        db_path = registry.store_path(job_id)
        if not db_path.is_file():
            return JobReviewsResponse(job_id=job_id, total=0, items=[])

        _raw, norm_store = open_review_intel_stores(db_path)
        items = norm_store.query()
        return JobReviewsResponse(job_id=job_id, total=len(items), items=items)

    @router.get("/jobs/{job_id}/summary", response_model=JobSummaryResponse)
    def get_job_summary(
        job_id: str,
        registry: JobRegistry = Depends(get_registry),
    ) -> JobSummaryResponse:
        try:
            assert_safe_job_id(job_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if registry.get_job(job_id) is None:
            raise HTTPException(status_code=404, detail="job_not_found")
        summary = registry.get_summary(job_id)
        if summary is None:
            raise HTTPException(status_code=404, detail="summary_not_found")
        return JobSummaryResponse(job_id=job_id, summary=summary)

    return router
