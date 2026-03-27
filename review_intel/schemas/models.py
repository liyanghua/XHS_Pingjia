# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""review_intel 领域 schema：统一描述跨平台的评价/评论情报记录。"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


def _utc_now() -> datetime:
    """返回当前 UTC 时间（用于默认时间戳）。"""
    return datetime.now(timezone.utc)


class ReviewPlatformKey(str, Enum):
    """与爬虫平台标识对齐的键；可扩展，不强制与 api.schemas 一一导入以避免循环依赖。"""

    XHS = "xhs"
    DOUYIN = "dy"
    KUAISHOU = "ks"
    BILIBILI = "bili"
    WEIBO = "wb"
    TIEBA = "tieba"
    ZHIHU = "zhihu"
    UNKNOWN = "unknown"


class ReviewIntelRecord(BaseModel):
    """单条评价情报记录（规范化后的最小公共字段）。"""

    record_id: str = Field(..., description="业务侧稳定主键，建议含平台前缀")
    platform: ReviewPlatformKey = Field(
        default=ReviewPlatformKey.UNKNOWN,
        description="来源平台键",
    )
    source_uri: Optional[str] = Field(
        default=None,
        description="可选：原文或详情页 URI",
    )
    collected_at: datetime = Field(
        default_factory=_utc_now,
        description="采集/入库时间（UTC）",
    )
    body_text: str = Field(default="", description="评价正文")
    rating: Optional[float] = Field(
        default=None,
        description="可选：归一化评分（具体量纲由上游约定）",
    )
    author_ref: Optional[str] = Field(
        default=None,
        description="可选：作者/账号的稳定引用（非明文 PII 场景可自行哈希）",
    )
    raw_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="平台特有字段，保持可序列化",
    )

    @field_validator("body_text", mode="before")
    @classmethod
    def _strip_body(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()


class ReviewIntelBatch(BaseModel):
    """一批评价记录，用于批量写入或任务输出。"""

    batch_id: str = Field(..., description="批次标识")
    records: list[ReviewIntelRecord] = Field(default_factory=list)
    notes: Optional[str] = Field(default=None, description="可选：批次说明")
