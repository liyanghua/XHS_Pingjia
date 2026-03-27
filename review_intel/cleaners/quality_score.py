# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""可解释的简单质量分（0~1），不依赖 embedding / LLM。"""

from __future__ import annotations

import re
from typing import Sequence

_DEFAULT_ATTRIBUTE_WORDS: tuple[str, ...] = (
    "颜色",
    "味道",
    "肤质",
    "尺码",
    "效果",
    "持久",
    "性价比",
    "显白",
    "脱妆",
    "遮瑕",
    "保湿",
    "质地",
    "肤感",
)


def compute_quality_score(
    text: str,
    *,
    attribute_words: Sequence[str] | None = None,
) -> float:
    """综合长度、具体性（数字/量纲）、属性词命中，输出 0~1。

    权重：长度 35%，具体描述 35%，属性词 30%。
    """
    t = text.strip()
    if not t:
        return 0.0

    attrs = tuple(attribute_words) if attribute_words is not None else _DEFAULT_ATTRIBUTE_WORDS

    length_component = min(1.0, len(t) / 100.0)

    has_concrete = bool(re.search(r"\d", t)) or bool(
        re.search(r"(第|共|用了|大概|左右|毫升|ml|g|克|天|周|月)", t, re.I)
    )
    concrete_component = 1.0 if has_concrete else 0.35

    attr_hits = sum(1 for w in attrs if w in t)
    attr_component = min(1.0, attr_hits / 3.0)

    score = 0.35 * length_component + 0.35 * concrete_component + 0.30 * attr_component
    return round(max(0.0, min(1.0, score)), 4)
