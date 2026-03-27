# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""标准层：归一化后的评价情报，便于检索、打分与下游分析。

``job_id`` 使单条记录可脱离「按库文件隔离」仍能对账来源任务；``extra_meta`` 承载易变平台字段，
避免顶层字段随各平台 API 频繁膨胀。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from review_intel.schemas.enums import PlatformType


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NormalizedReview(BaseModel):
    """跨平台统一语义的评价记录（可与 OLTP/搜索索引行对应）。"""

    job_id: Optional[str] = Field(
        default=None,
        description="采集作业 ID；导出/合并多源时与 Raw 层对齐，旧数据可为空",
    )
    review_id: str = Field(..., description="归一化后主键")
    platform: PlatformType = Field(..., description="来源平台")
    industry: Optional[str] = Field(default=None, description="行业标签")
    category: Optional[str] = Field(default=None, description="品类/话题分类")
    brand: Optional[str] = Field(default=None, description="提及品牌")
    query_hit_terms: list[str] = Field(
        default_factory=list,
        description="检索或规则命中的词项",
    )
    review_text: str = Field(default="", description="清洗后正文")
    publish_time: datetime = Field(..., description="发布时间 UTC")
    crawl_time: datetime = Field(
        default_factory=_utc_now,
        description="入库/归一化时间 UTC",
    )
    engagement_score: Optional[float] = Field(
        default=None,
        description="互动综合分（量纲由上游约定）",
    )
    freshness_score: Optional[float] = Field(default=None, description="时效分")
    quality_score: Optional[float] = Field(default=None, description="质量分")
    spam_score: Optional[float] = Field(default=None, description="垃圾/水军可疑度")
    author_type: str = Field(
        default="unknown",
        description="作者类型：如 verified_user, bot, unknown",
    )
    evidence_url: Optional[str] = Field(default=None, description="证据链或原文链接")
    source_post_id: Optional[str] = Field(default=None, description="所属帖子/视频 ID")
    source_comment_id: Optional[str] = Field(default=None, description="平台评论 ID")
    extra_meta: dict[str, Any] = Field(
        default_factory=dict,
        description="平台/任务扩展键值（JSON 可序列化）；强通用语义仍放顶层字段",
    )

    @field_validator("review_text", mode="before")
    @classmethod
    def _strip_review(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()
