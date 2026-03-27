# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""原始/归一化存储的 Repository 协议，便于单元测试与替换后端。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

from review_intel.schemas.normalized import NormalizedReview
from review_intel.schemas.raw_event import RawReviewEvent


@runtime_checkable
class RawReviewRepository(Protocol):
    """原始事件存储抽象。"""

    def save(self, event: RawReviewEvent) -> bool:
        """写入一条事件；若 ``event_id`` 已存在则跳过，返回 ``False``，否则 ``True``。"""

    def list_by_job(self, job_id: str) -> list[RawReviewEvent]:
        """按作业 ID 列出全部事件（顺序不保证与写入一致）。"""


@runtime_checkable
class NormalizedReviewRepository(Protocol):
    """归一化评价存储抽象。"""

    def save(self, review: NormalizedReview) -> bool:
        """写入一条；若 ``review_id`` 已存在则跳过，返回 ``False``。"""

    def query(
        self,
        *,
        platform: Optional[str] = None,
        category: Optional[str] = None,
        time_start: Optional[datetime] = None,
        time_end: Optional[datetime] = None,
    ) -> list[NormalizedReview]:
        """按条件过滤 ``publish_time``（含边界）；未传的条件不参与过滤。"""
