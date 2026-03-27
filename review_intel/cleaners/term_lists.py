# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""集中维护清洗用词表（高价值短评、可按品类迭代扩展）。

不在其它模块内硬编码同义词表；调整默认行为时只改本文件或调用方传入的 ``frozenset``。
"""

from __future__ import annotations

from typing import FrozenSet

# 第一版：偏电商 / 服饰防晒场景 + 小红书常见短评痛点词（子串匹配）
_HIGH_VALUE_SHORT_TERMS: tuple[str, ...] = (
    # 用户明确列举
    "显瘦",
    "显胖",
    "透",
    "闷",
    "起球",
    "掉色",
    "不值",
    "小个子慎入",
    "好穿",
    "不推荐",
    "平替",
    "求链接",
    # 同类扩展（防晒 / 服装痛点）
    "搓泥",
    "假滑",
    "扎人",
    "透不过气",
    "不透气",
    "显黑",
    "收腰",
    "踩雷",
    "回购",
    "避雷",
    "种草",
    "拔草",
    "色差",
    "码正",
    "偏大",
    "偏小",
)

_DEFAULT_HIGH_VALUE_FROZEN: FrozenSet[str] = frozenset(_HIGH_VALUE_SHORT_TERMS)


def default_high_value_short_terms() -> FrozenSet[str]:
    """默认「高价值短词」集合（不可变，便于与 checkpoint / 配置比较）。"""
    return _DEFAULT_HIGH_VALUE_FROZEN
