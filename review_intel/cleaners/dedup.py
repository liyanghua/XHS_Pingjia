# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""文本标准化与精确去重；近重复接口预留。"""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable


def normalize_for_dedup(text: str) -> str:
    """标准化用于精确去重：去首尾空白、折叠空白、小写拉丁部分。"""
    t = text.strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


@runtime_checkable
class NearDuplicateResolver(Protocol):
    """近重复判定（第一版不实现，仅作扩展点）。"""

    def is_near_duplicate(self, a_normalized: str, b_normalized: str) -> bool:
        """若 ``a`` 与 ``b`` 在语义上近似重复则返回 True。"""
        ...


class NoopNearDuplicateResolver:
    """占位：永不判定为近重复。"""

    def is_near_duplicate(self, a_normalized: str, b_normalized: str) -> bool:
        _ = (a_normalized, b_normalized)
        return False


class ExactTextDeduper:
    """基于 ``normalize_for_dedup`` 的精确去重集合。"""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def try_add(self, text: str) -> bool:
        """若标准化键未出现过则登记并返回 True，否则 False。"""
        key = normalize_for_dedup(text)
        if not key:
            return False
        if key in self._seen:
            return False
        self._seen.add(key)
        return True

    def __len__(self) -> int:
        return len(self._seen)
