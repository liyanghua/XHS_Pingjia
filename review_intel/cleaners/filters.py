# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""基于规则的评论文本过滤：空、过短、纯符号/表情、明显广告；可选高价值短词豁免。"""

from __future__ import annotations

import re
from typing import FrozenSet

_DEFAULT_AD_SUBSTRINGS: tuple[str, ...] = (
    "加微信",
    "加我微信",
    "加vx",
    "私我",
    "私聊",
    "优惠券",
    "点击链接",
    "代购",
    "详情看主页",
    "广告推广",
    "关注公众号",
    "扫码",
    "免费领取",
)


def default_ad_keywords() -> FrozenSet[str]:
    """返回默认广告词集合（不可变，便于缓存比较）。"""
    return frozenset(_DEFAULT_AD_SUBSTRINGS)


def is_empty_text(text: str) -> bool:
    """空白或仅空白字符视为空。"""
    return len(text.strip()) == 0


def is_too_short(text: str, *, min_len: int = 4) -> bool:
    """按字符数判断过短（中英文均按字符计）。"""
    return len(text.strip()) < min_len


def is_pure_emoji_or_symbols(text: str) -> bool:
    """无汉字、拉丁字母与数字，仅表情/标点等，视为低信息量。"""
    s = text.strip()
    if not s:
        return True
    return re.search(r"[\u4e00-\u9fffA-Za-z0-9]", s) is None


def contains_ad_keywords(text: str, keywords: FrozenSet[str] | set[str] | None = None) -> bool:
    """子串匹配广告词（大小写不敏感仅影响英文部分）。"""
    kws = keywords if keywords is not None else default_ad_keywords()
    lower = text.lower()
    return any(k.lower() in lower for k in kws)


def hits_high_value_short_term(text: str, terms: FrozenSet[str]) -> bool:
    """正文是否命中任一高价值短词（子串匹配，与广告词风格一致）。"""
    if not terms:
        return False
    s = text.strip()
    if not s:
        return False
    lower = s.lower()
    return any(t.lower() in lower for t in terms)


def should_keep_review_text(
    text: str,
    *,
    min_len: int = 4,
    ad_keywords: FrozenSet[str] | set[str] | None = None,
    high_value_short_terms: FrozenSet[str] | None = None,
) -> bool:
    """综合过滤：保留返回 True。

    顺序：空 → 纯表情/符号 → 广告 → 过短（若提供 ``high_value_short_terms`` 且命中则豁免长度）。

    ``high_value_short_terms`` 为 ``None`` 或空集时不做短评豁免（与旧行为兼容）。
    """
    if is_empty_text(text):
        return False
    if is_pure_emoji_or_symbols(text):
        return False
    if contains_ad_keywords(text, keywords=ad_keywords):
        return False
    hv = high_value_short_terms if high_value_short_terms is not None else frozenset()
    if is_too_short(text, min_len=min_len):
        if hv and hits_high_value_short_term(text, hv):
            return True
        return False
    return True
