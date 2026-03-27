# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""导出占位：将批次写入文件、消息队列或外部系统。"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from review_intel.schemas import ReviewIntelBatch


@runtime_checkable
class ReviewIntelBatchSink(Protocol):
    """消费一批规范化记录（如导出 JSONL、推送到 Kafka）。"""

    def write_batch(self, batch: ReviewIntelBatch) -> None:
        """写出或发送一个批次。"""
        ...
