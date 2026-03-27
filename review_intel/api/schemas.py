# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""review_intel HTTP API 的请求/响应模型（与领域模型解耦，便于前端契约稳定）。"""

from __future__ import annotations

import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict

from review_intel.api.registry import assert_safe_job_id
from review_intel.jobs.models import (
    CollectionJob,
    FreshnessLevel,
    QuerySpec,
)
from review_intel.jobs.runner import CollectionRunSummary
from review_intel.schemas.enums import JobStatus
from review_intel.schemas.normalized import NormalizedReview


class CreateJobRequest(BaseModel):
    """创建采集作业；``job_id`` 缺省则自动生成。"""

    job_id: str | None = Field(default=None, description="作业 ID；缺省为随机生成")
    industry: Optional[str] = Field(default=None, description="行业")
    category: Optional[str] = Field(default=None, description="品类")
    brand: Optional[str] = Field(default=None, description="品牌")
    query_spec: QuerySpec = Field(..., description="查询规格")
    target_types: list[str] = Field(
        default_factory=list,
        description="抓取目标类型，如 post, comment",
    )
    priority: int = Field(default=0, description="优先级")
    freshness_level: FreshnessLevel = Field(
        default=FreshnessLevel.NORMAL,
        description="新鲜度档位",
    )
    owner: str = Field(default="", description="创建者/租户标识")
    execute: bool = Field(
        default=True,
        description="是否在创建后立即同步执行一次采集（DummyAdapter + 本地 SQLite）",
    )

    @field_validator("job_id", mode="before")
    @classmethod
    def _validate_job_id(cls, value: object) -> str | None:
        if value is None or value == "":
            return None
        s = str(value).strip()
        if not s:
            return None
        assert_safe_job_id(s)
        return s

    def to_collection_job(self) -> CollectionJob:
        jid = self.job_id or f"job-{uuid.uuid4().hex[:12]}"
        return CollectionJob(
            job_id=jid,
            industry=self.industry,
            category=self.category,
            brand=self.brand,
            query_spec=self.query_spec,
            target_types=list(self.target_types),
            priority=self.priority,
            freshness_level=self.freshness_level,
            status=JobStatus.PENDING,
            owner=self.owner,
        )


class JobCreateResponse(BaseModel):
    """POST /jobs 统一响应。"""

    version: Literal["1"] = Field(default="1", description="响应契约版本")
    job: CollectionJob = Field(..., description="持久化后的作业（含生成后的 job_id）")
    executed: bool = Field(..., description="是否已尝试执行采集")
    summary: CollectionRunSummary | None = Field(
        default=None,
        description="执行成功时的运行摘要；未执行或失败时可能为空",
    )
    error: str | None = Field(
        default=None,
        description="执行失败时的错误信息；仅调试用，非完整错误栈",
    )


class JobDetailResponse(BaseModel):
    """GET /jobs/{job_id} 统一响应。"""

    version: Literal["1"] = Field(default="1")
    job: CollectionJob
    summary: CollectionRunSummary | None = Field(
        default=None,
        description="若已执行过采集则有摘要",
    )


class JobReviewsResponse(BaseModel):
    """GET /jobs/{job_id}/reviews 统一响应。"""

    version: Literal["1"] = Field(default="1")
    job_id: str
    total: int = Field(ge=0, description="本作业库中归一化评价条数")
    items: list[NormalizedReview] = Field(default_factory=list)


class JobSummaryResponse(BaseModel):
    """GET /jobs/{job_id}/summary 统一响应。"""

    version: Literal["1"] = Field(default="1")
    job_id: str
    summary: CollectionRunSummary


class SearchHit(BaseModel):
    """单条检索结果：来源（库内 / 本次抓取）+ 作业维度 + 归一化记录。"""

    model_config = ConfigDict(extra="forbid")

    provenance: Literal["cache", "live"] = Field(
        ...,
        description="cache=历史库命中；live=本次 Runner 写入",
    )
    job_id: str = Field(..., description="数据所在作业目录名")
    review: NormalizedReview = Field(..., description="归一化评价")


class KeywordSearchResponse(BaseModel):
    """GET /api/search 仅查库。"""

    version: Literal["1"] = Field(default="1")
    keyword: str
    total: int = Field(ge=0)
    dedupe_dropped: int = Field(default=0, ge=0)
    items: list[SearchHit] = Field(default_factory=list)


class KeywordSearchRunRequest(BaseModel):
    """POST /api/search/run：关键词 + 可选作业 ID。"""

    keyword: str = Field(..., min_length=1, description="检索词；写入 QuerySpec.terms 并触发 Runner")
    job_id: str | None = Field(default=None, description="缺省则自动生成")


class KeywordSearchRunResponse(BaseModel):
    """POST /api/search/run：库内命中 + 本次 Dummy 抓取合并后结果。"""

    version: Literal["1"] = Field(default="1")
    keyword: str
    job_id: str
    summary: CollectionRunSummary | None = Field(
        default=None,
        description="本次采集摘要；失败时为空",
    )
    error: str | None = Field(default=None, description="执行失败时的错误信息")
    cache_hits: int = Field(ge=0, description="合并前库内命中条数")
    live_hits: int = Field(ge=0, description="本次作业归一化条数（清洗前可多于 merged）")
    total: int = Field(ge=0, description="合并去重后条数")
    dedupe_dropped: int = Field(default=0, ge=0)
    items: list[SearchHit] = Field(default_factory=list)
