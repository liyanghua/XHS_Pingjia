# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""评价情报采集任务模型：查询意图、QuerySpec 与 CollectionJob。

供调度器、API 与存储层序列化使用；与 ``ReviewIntelTask``（流水线单步任务）互补。
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from review_intel.schemas.enums import JobStatus, PlatformType


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class QueryIntent(str, Enum):
    """用户检索/监控意图分类（用于路由策略与报告模板）。"""

    TREND_SEARCH = "trend_search"
    PAINPOINT_SEARCH = "painpoint_search"
    NEED_SEARCH = "need_search"
    COMPETITOR_SEARCH = "competitor_search"
    SCENARIO_SEARCH = "scenario_search"


class FreshnessLevel(str, Enum):
    """数据新鲜度要求（调度侧可映射为更短抓取间隔）。"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    REALTIME = "realtime"


class TimeWindow(BaseModel):
    """时间范围；均可选，由调度解释（如仅 ``end`` 表示截至某日）。"""

    start: Optional[datetime] = Field(default=None, description="起始时间 UTC")
    end: Optional[datetime] = Field(default=None, description="结束时间 UTC")
    label: Optional[str] = Field(
        default=None,
        description="可读标签，如 last_7d（与起止二选一或并存）",
    )


class QuerySpec(BaseModel):
    """一次评价情报采集的查询规格（可独立序列化为 JSON/DB 列）。"""

    industry: Optional[str] = Field(default=None, description="行业")
    category: Optional[str] = Field(default=None, description="品类")
    brand: Optional[str] = Field(default=None, description="品牌（可选）")
    intent: QueryIntent = Field(..., description="查询意图")
    terms: list[str] = Field(default_factory=list, description="主检索词/短语")
    negative_terms: list[str] = Field(
        default_factory=list,
        description="排除词，降低噪声命中",
    )
    time_window: Optional[TimeWindow] = Field(
        default=None,
        description="时间窗；不限则为空",
    )
    platforms: list[PlatformType] = Field(
        default_factory=list,
        description="目标平台列表；空表示使用默认策略",
    )

    @field_validator("terms", "negative_terms", mode="before")
    @classmethod
    def _ensure_str_list(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value else []
        return [str(x).strip() for x in value if str(x).strip()]


class CollectionJob(BaseModel):
    """可持久化的评价情报采集作业（从「关键词抓取」升级为结构化情报任务）。"""

    job_id: str = Field(..., description="全局唯一作业 ID")
    industry: Optional[str] = Field(default=None, description="冗余：行业（便于列表筛选）")
    category: Optional[str] = Field(default=None, description="冗余：品类")
    brand: Optional[str] = Field(default=None, description="冗余：品牌")
    query_spec: QuerySpec = Field(..., description="查询规格（主配置）")
    target_types: list[str] = Field(
        default_factory=list,
        description="抓取目标类型，如 post, comment（字符串与 ContentType 取值对齐即可）",
    )
    priority: int = Field(default=0, description="优先级，越大越优先")
    freshness_level: FreshnessLevel = Field(
        default=FreshnessLevel.NORMAL,
        description="新鲜度档位",
    )
    status: JobStatus = Field(default=JobStatus.PENDING, description="作业状态")
    checkpoint: dict[str, Any] = Field(
        default_factory=dict,
        description="断点：游标、已处理 ID、分页状态等，调度器读写",
    )
    retry_count: int = Field(default=0, ge=0, description="已重试次数")
    owner: str = Field(default="", description="创建者/租户标识")
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: Optional[datetime] = Field(default=None, description="最后更新时间 UTC")


def create_job_from_dict(data: dict[str, Any]) -> CollectionJob:
    """从 dict 校验并构造 ``CollectionJob``（API/队列 payload 入口）。

    Args:
        data: 与 ``CollectionJob`` 兼容的键值；嵌套 ``query_spec``、``time_window`` 可嵌套 dict。

    Returns:
        校验后的 ``CollectionJob`` 实例。

    Raises:
        pydantic.ValidationError: 字段不合法时。
    """
    return CollectionJob.model_validate(data)


def example_job_womens_sun_protection_painpoint() -> CollectionJob:
    """示例：女装防晒衣痛点搜索。"""
    tw = TimeWindow(label="last_30d")
    spec = QuerySpec(
        industry="女装",
        category="防晒衣",
        brand=None,
        intent=QueryIntent.PAINPOINT_SEARCH,
        terms=["闷热", "假滑", "搓泥", "不透气"],
        negative_terms=["广告", "抽奖"],
        time_window=tw,
        platforms=[PlatformType.XHS, PlatformType.DOUYIN],
    )
    return CollectionJob(
        job_id="job-demo-sun-protection-painpoint",
        industry="女装",
        category="防晒衣",
        brand=None,
        query_spec=spec,
        target_types=["post", "comment"],
        priority=5,
        freshness_level=FreshnessLevel.NORMAL,
        status=JobStatus.PENDING,
        owner="demo",
    )


def example_job_home_storage_need() -> CollectionJob:
    """示例：家居收纳需求搜索。"""
    spec = QuerySpec(
        industry="家居",
        category="收纳",
        brand=None,
        intent=QueryIntent.NEED_SEARCH,
        terms=["小户型收纳", "衣柜扩容", "换季整理"],
        negative_terms=[],
        time_window=TimeWindow(label="last_14d"),
        platforms=[PlatformType.XHS, PlatformType.BILIBILI],
    )
    return CollectionJob(
        job_id="job-demo-home-storage-need",
        industry="家居",
        category="收纳",
        brand=None,
        query_spec=spec,
        target_types=["post", "comment", "search_hit"],
        priority=3,
        freshness_level=FreshnessLevel.LOW,
        status=JobStatus.PENDING,
        owner="demo",
    )


def example_job_beauty_dupes_competitor() -> CollectionJob:
    """示例：美妆平替竞品搜索。"""
    spec = QuerySpec(
        industry="美妆",
        category="护肤",
        brand="DemoBrand",
        intent=QueryIntent.COMPETITOR_SEARCH,
        terms=["平替", "国货替代", "同成分"],
        negative_terms=["假货"],
        time_window=None,
        platforms=[PlatformType.XHS, PlatformType.WEIBO, PlatformType.ZHIHU],
    )
    return CollectionJob(
        job_id="job-demo-beauty-dupes-competitor",
        industry="美妆",
        category="护肤",
        brand="DemoBrand",
        query_spec=spec,
        target_types=["post", "comment"],
        priority=8,
        freshness_level=FreshnessLevel.HIGH,
        status=JobStatus.PENDING,
        owner="demo",
    )
