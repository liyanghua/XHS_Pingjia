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
from review_intel.schemas.normalized import NormalizedReview


def clean_and_score_reviews(
    reviews: list[NormalizedReview],
    *,
    min_len: int = 4,
    ad_keywords: FrozenSet[str] | set[str] | None = None,
) -> list[NormalizedReview]:
    """过滤低质文本，按标准化正文精确去重，并为保留项写入 ``quality_score``。

    不改变 ``review_id``；重复文本仅保留首次出现的一条。
    """
    deduper = ExactTextDeduper()
    out: list[NormalizedReview] = []
    for r in reviews:
        text = r.review_text
        if not should_keep_review_text(text, min_len=min_len, ad_keywords=ad_keywords):
            continue
        if not deduper.try_add(text):
            continue
        q = compute_quality_score(text)
        out.append(r.model_copy(update={"quality_score": q}))
    return out
