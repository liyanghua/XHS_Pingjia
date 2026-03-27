# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""原始层：单次抓取解析后的评价/评论事件（平台中立字段 + 原始载荷）。

``extra_meta`` 存放已解析、需在 Raw→Norm 间传递的窄字段；完整结构仍见 ``raw_payload``。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from review_intel.schemas.enums import ContentType, PlatformType


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RawReviewEvent(BaseModel):
    """原始评价事件：适配器从各平台结构映射到此模型后再入清洗/归一化管线。"""

    event_id: str = Field(..., description="事件唯一 ID（建议含平台与业务前缀）")
    platform: PlatformType = Field(..., description="来源平台")
    content_type: ContentType = Field(..., description="内容形态")
    source_id: str = Field(..., description="平台侧内容/评论主键")
    parent_id: Optional[str] = Field(
        default=None,
        description="父级 ID；顶层内容可为空",
    )
    author_id: str = Field(default="", description="作者平台 ID；匿名可用空串")
    publish_time: datetime = Field(..., description="内容发布时间 UTC")
    crawl_time: datetime = Field(
        default_factory=_utc_now,
        description="爬虫采集时间 UTC",
    )
    raw_text: str = Field(default="", description="原始正文")
    raw_media: list[dict[str, Any]] = Field(
        default_factory=list,
        description="原始媒体引用列表（URL、类型等）",
    )
    raw_metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="平台侧互动指标快照，如赞数",
    )
    url: Optional[str] = Field(default=None, description="可访问的原文或落地页 URL")
    job_id: str = Field(..., description="所属采集作业 ID")
    extra_meta: dict[str, Any] = Field(
        default_factory=dict,
        description="解析后的扩展键值（如笔记标题快照），供归一化合并；非全量原始数据",
    )
    raw_payload: dict[str, Any] = Field(
        default_factory=dict,
        description="平台完整原始 JSON/结构，便于排错与重放",
    )

    @field_validator("raw_text", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()
