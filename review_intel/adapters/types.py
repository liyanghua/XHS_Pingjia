# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""适配器层共用类型：限流策略与 JSON 载荷别名。"""

from __future__ import annotations

from typing import Any, TypeAlias

from pydantic import BaseModel, Field

#: 平台返回的半结构化 JSON 对象（帖子详情、原始 dict 等），避免绑定具体平台类。
JsonObject: TypeAlias = dict[str, Any]


class RateLimitPolicy(BaseModel):
    """适配器声明的抓取限流策略，供调度器/客户端合并为实际等待间隔。

    实现方可根据平台 robots/账号等级调整；调用方应尊重 ``min_interval_seconds``
    与 ``max_concurrency``，避免触发封禁。
    """

    min_interval_seconds: float = Field(
        default=1.0,
        ge=0.0,
        description="两次请求之间的最小间隔（秒）",
    )
    max_concurrency: int = Field(
        default=1,
        ge=1,
        description="同一适配器实例允许的最大并发请求数",
    )
    burst: int = Field(
        default=1,
        ge=1,
        description="短时突发允许的请求次数上限（与令牌桶语义对齐时可使用）",
    )
