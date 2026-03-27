# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""清洗管线占位：对 `ReviewIntelRecord` 做去噪、标准化等可扩展步骤。"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from review_intel.schemas import ReviewIntelRecord


@runtime_checkable
class ReviewIntelCleaner(Protocol):
    """单条记录在入库或导出前的清洗步骤。"""

    def clean(self, record: ReviewIntelRecord) -> ReviewIntelRecord:
        """返回清洗后的记录（可实现为不可变拷贝）。"""
        ...
