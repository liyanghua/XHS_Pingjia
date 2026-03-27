# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""小红书第一轮真实平台验收：``acceptance_report.json`` 的可序列化模型。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from review_intel.jobs.models import CollectionJob, QuerySpec


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FieldCoverageEntry(BaseModel):
    """单字段在样本中的非空比例。"""

    field: str = Field(..., description="NormalizedReview 字段名或 extra_meta 键")
    present_ratio: float = Field(..., ge=0.0, le=1.0, description="非空比例 0~1")
    non_empty_count: int = Field(default=0, ge=0, description="非空条数")
    total: int = Field(default=0, ge=0, description="参与统计条数")


class AcceptanceChecklist(BaseModel):
    """人工扫一眼即可判断：哪些环节通过、哪些暴露问题。"""

    schema_ok: bool = Field(
        default=False,
        description="归一化字段与预期类型基本一致（无大面积缺失/空）",
    )
    runner_ok: bool = Field(default=False, description="搜索/评论分页有产出且未异常中断")
    cleaner_ok: bool = Field(
        default=False,
        description="清洗后仍有合理条数，且 quality_score 非大面积为 0",
    )
    store_ok: bool = Field(
        default=False,
        description="raw / normalized 写入条数与 Runner 摘要一致或可对账",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="暴露的问题（schema/runner/cleaner/store）",
    )


class SampleReviewSnippet(BaseModel):
    """抽样展示用，便于人工核对。"""

    review_id: str
    review_text: str = Field(default="", description="正文（截断前）")
    quality_score: Optional[float] = None
    source_post_id: Optional[str] = None
    source_comment_id: Optional[str] = None


class XhsAcceptanceReport(BaseModel):
    """一次真实平台验收的完整报告（写入 JSON）。"""

    generated_at: datetime = Field(default_factory=_utc_now)
    job_id: str
    platform: str = Field(..., description="适配器名，如 xhs")
    query_summary: str = Field(..., description="可读查询摘要")
    query_spec: dict[str, Any] = Field(
        default_factory=dict,
        description="QuerySpec 序列化（便于对账）",
    )

    fetched_post_count: int = Field(ge=0, description="参与评论抓取的帖子数（Runner.posts_selected）")
    fetched_comment_count: int = Field(ge=0, description="拉取的评论事件条数（含回复链若开启）")
    normalized_count: int = Field(ge=0)
    cleaned_count: int = Field(ge=0)
    stored_raw_count: int = Field(ge=0, description="raw_store.save 为 True 的次数")
    stored_normalized_count: int = Field(ge=0, description="normalized_store.save 为 True 的次数")
    failed_count: int = Field(default=0, ge=0, description="与 Runner 摘要对齐；成功路径为 0")
    retry_count: int = Field(default=0, ge=0, description="平台调用内部重试次数")
    db_raw_row_count: int = Field(
        default=0,
        ge=0,
        description="SQLite 中该 job_id 的 raw_review_events 行数（验收时查询，含历史重复 run）",
    )
    db_normalized_row_count: int = Field(
        default=0,
        ge=0,
        description="SQLite 中 payload_json.job_id 匹配的 normalized_reviews 行数",
    )

    field_coverage: list[FieldCoverageEntry] = Field(
        default_factory=list,
        description="核心字段覆盖率（基于归一化样本）",
    )
    sample_reviews: list[SampleReviewSnippet] = Field(
        default_factory=list,
        description="3~5 条抽样",
    )

    checklist: AcceptanceChecklist = Field(default_factory=AcceptanceChecklist)
    db_path: str = Field(default="", description="本次 run 使用的 SQLite 路径")
    output_dir: str = Field(default="", description="报告 JSON/Markdown 输出目录")

    @field_validator("query_spec", mode="before")
    @classmethod
    def _spec_to_dict(cls, v: object) -> dict[str, Any]:
        if isinstance(v, QuerySpec):
            return v.model_dump(mode="json")
        if isinstance(v, dict):
            return v
        raise TypeError("query_spec must be QuerySpec or dict")

    @classmethod
    def from_job_and_summary(
        cls,
        *,
        job: CollectionJob,
        platform: str,
        query_summary: str,
        summary_dict: dict[str, Any],
        field_coverage: list[FieldCoverageEntry],
        sample_reviews: list[SampleReviewSnippet],
        checklist: AcceptanceChecklist,
        db_path: str,
        output_dir: str,
        db_raw_row_count: int = 0,
        db_normalized_row_count: int = 0,
    ) -> XhsAcceptanceReport:
        """从 ``CollectionRunSummary.model_dump()`` 与作业构造报告。"""
        return cls(
            job_id=job.job_id,
            platform=platform,
            query_summary=query_summary,
            query_spec=job.query_spec,
            fetched_post_count=int(summary_dict.get("posts_selected", 0)),
            fetched_comment_count=int(summary_dict.get("fetched_count", 0)),
            normalized_count=int(summary_dict.get("normalized_count", 0)),
            cleaned_count=int(summary_dict.get("cleaned_count", 0)),
            stored_raw_count=int(summary_dict.get("stored_raw_count", 0)),
            stored_normalized_count=int(summary_dict.get("stored_normalized_count", 0)),
            failed_count=int(summary_dict.get("failed_count", 0)),
            retry_count=int(summary_dict.get("retry_count", 0)),
            db_raw_row_count=db_raw_row_count,
            db_normalized_row_count=db_normalized_row_count,
            field_coverage=field_coverage,
            sample_reviews=sample_reviews,
            checklist=checklist,
            db_path=db_path,
            output_dir=output_dir,
        )
