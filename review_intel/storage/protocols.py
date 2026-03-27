# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""review_intel 存储与任务执行协议。

`ReviewIntelTaskRunner` 与任务强相关，后续若拆分可迁至 `jobs/protocols.py`，
当前与存储协议同文件以减少碎片。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from review_intel.jobs.task_models import ReviewIntelTask, TaskResult
from review_intel.schemas import ReviewIntelBatch


@runtime_checkable
class ReviewIntelStore(Protocol):
    """持久化一批评价情报记录的存储抽象。"""

    async def append_batch(self, batch: ReviewIntelBatch) -> None:
        """追加写入一个批次。"""
        ...


@runtime_checkable
class ReviewIntelTaskRunner(Protocol):
    """执行单条 review_intel 任务的运行器抽象。"""

    async def run(self, task: ReviewIntelTask) -> TaskResult:
        """根据任务定义执行并返回结果摘要。"""
        ...
