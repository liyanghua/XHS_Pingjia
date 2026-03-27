# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""归一化评论列表：规则过滤、精确去重、写入质量分。"""

from __future__ import annotations

from typing import FrozenSet

from review_intel.cleaners.dedup import ExactTextDeduper
from review_intel.cleaners.filters import should_keep_review_text
from review_intel.cleaners.quality_score import compute_quality_score
from review_intel.cleaners.term_lists import default_high_value_short_terms
from review_intel.schemas.normalized import NormalizedReview


def clean_and_score_reviews(
    reviews: list[NormalizedReview],
    *,
    min_len: int = 4,
    ad_keywords: FrozenSet[str] | set[str] | None = None,
    high_value_short_terms: FrozenSet[str] | None = None,
) -> list[NormalizedReview]:
    """过滤低质文本，按标准化正文精确去重，并为保留项写入 ``quality_score``。

    不改变 ``review_id``；重复文本仅保留首次出现的一条。

    ``high_value_short_terms``：

    - ``None``（默认）：使用内置 :func:`~review_intel.cleaners.term_lists.default_high_value_short_terms`，
      对命中痛点词的短评放宽长度过滤并抬高质量分下限（适合小红书等真实评论）。
    - 空 ``frozenset()``：关闭高价值短词机制，行为接近早期仅 ``min_len`` + 广告过滤。
    - 其它：自定义词表（子串匹配）。
    """
    hv_terms = default_high_value_short_terms() if high_value_short_terms is None else high_value_short_terms

    deduper = ExactTextDeduper()
    out: list[NormalizedReview] = []
    for r in reviews:
        text = r.review_text
        if not should_keep_review_text(
            text,
            min_len=min_len,
            ad_keywords=ad_keywords,
            high_value_short_terms=hv_terms,
        ):
            continue
        if not deduper.try_add(text):
            continue
        q = compute_quality_score(text, high_value_short_terms=hv_terms)
        out.append(r.model_copy(update={"quality_score": q}))
    return out
