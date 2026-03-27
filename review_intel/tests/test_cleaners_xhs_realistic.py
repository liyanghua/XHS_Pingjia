# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""贴近小红书真实评论的表驱动用例（高价值短词、灌水、广告）。"""

from __future__ import annotations

import pytest

from review_intel.cleaners.filters import should_keep_review_text
from review_intel.cleaners.pipeline import clean_and_score_reviews
from review_intel.cleaners.quality_score import QUALITY_FLOOR_SHORT_HIT, compute_quality_score
from review_intel.cleaners.term_lists import default_high_value_short_terms
from review_intel.schemas.examples import example_normalized_review


def _rev(text: str, rid: str) -> object:
    r = example_normalized_review()
    return r.model_copy(update={"review_id": rid, "review_text": text})


_HV = default_high_value_short_terms()


@pytest.mark.parametrize(
    ("text", "expect_keep", "category"),
    [
        ("加我微信了解详情", False, "广告"),
        ("私我", False, "短广告"),
        ("👍👍👍", False, "纯表情"),
        ("！！！", False, "纯符号"),
        ("dd", False, "灌水极短"),
        ("蹲", False, "无信息单字"),
        ("来了", False, "灌水短"),
        ("好穿", True, "极短高价值"),
        ("闷", True, "极短高价值"),
        ("起球", True, "极短高价值"),
        ("求链接", True, "极短高价值"),
        ("不推荐", True, "极短高价值"),
        ("平替真香", True, "短评含高价值词"),
        ("这件防晒衣闷热搓泥但显瘦", True, "正常有效长评"),
        ("颜色还行就是有点透", True, "含透/痛点"),
        ("模板好评返现刷单专用文案很长很长很长很长", True, "长文本未命中广告子串时仍保留"),
        ("详情看主页私聊", False, "广告组合"),
    ],
)
def test_should_keep_xhs_style(text: str, expect_keep: bool, category: str) -> None:
    _ = category
    got = should_keep_review_text(text, min_len=4, high_value_short_terms=_HV)
    assert got is expect_keep, (text, category, got, expect_keep)


def test_short_high_value_gets_quality_floor() -> None:
    q = compute_quality_score("好穿", high_value_short_terms=_HV)
    assert q >= QUALITY_FLOOR_SHORT_HIT


def test_pipeline_keeps_high_value_short_and_dedup() -> None:
    a = _rev("好穿", "r1")
    b = _rev("好穿", "r2")
    c = _rev("这件防晒衣质地轻薄穿着不闷很显瘦推荐入手", "r3")
    out = clean_and_score_reviews([a, b, c])
    assert len(out) == 2
    texts = {x.review_text for x in out}
    assert "好穿" in texts
    by_text = {x.review_text: x for x in out}
    assert by_text["好穿"].quality_score is not None
    assert by_text["好穿"].quality_score >= QUALITY_FLOOR_SHORT_HIT


def test_pipeline_disable_high_value_strict_short() -> None:
    """显式空词表时，短评仍按 min_len 丢弃（接近旧行为）。"""
    r = _rev("好穿", "only")
    out = clean_and_score_reviews([r], high_value_short_terms=frozenset())
    assert out == []
