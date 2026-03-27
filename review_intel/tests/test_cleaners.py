# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""cleaners：过滤、去重、质量分与 pipeline。"""

from __future__ import annotations

from review_intel.cleaners.dedup import ExactTextDeduper, normalize_for_dedup
from review_intel.cleaners.filters import (
    contains_ad_keywords,
    is_pure_emoji_or_symbols,
    should_keep_review_text,
)
from review_intel.cleaners.pipeline import clean_and_score_reviews
from review_intel.cleaners.quality_score import compute_quality_score
from review_intel.schemas.examples import example_normalized_review


def _rev(text: str, rid: str = "r1"):
    r = example_normalized_review()
    return r.model_copy(update={"review_id": rid, "review_text": text})


def test_filter_empty_and_short() -> None:
    assert should_keep_review_text("") is False
    assert should_keep_review_text("   ") is False
    assert should_keep_review_text("好短", min_len=4) is False


def test_filter_pure_emoji_or_symbols() -> None:
    assert is_pure_emoji_or_symbols("😀😀😀") is True
    assert is_pure_emoji_or_symbols("！！！") is True
    assert is_pure_emoji_or_symbols("这件防晒衣质地不错") is False


def test_filter_ad_keywords() -> None:
    assert contains_ad_keywords("加我微信了解详情") is True
    assert should_keep_review_text("防晒衣很舒服质地上乘推荐") is True


def test_normalize_dedup_case_and_whitespace() -> None:
    assert normalize_for_dedup("  Hello   World ") == normalize_for_dedup("hello world")
    d = ExactTextDeduper()
    assert d.try_add("Aa Bb") is True
    assert d.try_add("  aa  bb  ") is False


def test_exact_deduper_distinct_texts() -> None:
    d = ExactTextDeduper()
    assert d.try_add("第一条评价内容足够长") is True
    assert d.try_add("第二条评价内容足够长") is True
    assert len(d) == 2


def test_quality_score_range_and_concrete() -> None:
    s = compute_quality_score("还行")
    assert 0.0 <= s <= 1.0
    s2 = compute_quality_score("用了14天感觉保湿效果不错质地轻薄性价比可以")
    assert s2 >= s


def test_clean_and_score_filters_and_dedup() -> None:
    a = _rev("太短", "id1")
    b = _rev("这是一条足够长的真实评价内容", "id2")
    c = _rev("这是一条足够长的真实评价内容", "id3")
    out = clean_and_score_reviews([a, b, c])
    assert len(out) == 1
    assert out[0].review_id == "id2"
    assert out[0].quality_score is not None


def test_clean_and_score_ad_removed() -> None:
    bad = _rev("这是一条足够长的评价加微信私聊", "x1")
    good = _rev("这是一条足够长的正常评价内容没有广告", "x2")
    out = clean_and_score_reviews([bad, good])
    assert len(out) == 1
    assert out[0].review_id == "x2"


def test_min_len_override() -> None:
    r = _rev("abc", "m1")
    assert clean_and_score_reviews([r], min_len=4) == []
    assert len(clean_and_score_reviews([r], min_len=2)) == 1


def test_noop_near_duplicate_resolver() -> None:
    from review_intel.cleaners.dedup import NoopNearDuplicateResolver

    r = NoopNearDuplicateResolver()
    assert r.is_near_duplicate("a", "a") is False
