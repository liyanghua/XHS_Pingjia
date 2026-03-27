# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""库内命中与实时抓取结果合并 + 去重。

去重策略与 ``cleaners.dedup`` 一致：先按 ``(job_id, review_id)``，再按
``normalize_for_dedup(review_text)``；保留先出现的一条。
"""

from __future__ import annotations

from review_intel.api.schemas import SearchHit
from review_intel.cleaners.dedup import normalize_for_dedup


def merge_cached_and_live(
    cached: list[SearchHit],
    live: list[SearchHit],
) -> tuple[list[SearchHit], int]:
    """先 ``cache``（按 ``publish_time`` 降序），再 ``live``，然后去重。

    Returns:
        ``(merged_hits, dedupe_dropped_count)``
    """
    cached_sorted = sorted(
        cached,
        key=lambda h: h.review.publish_time,
        reverse=True,
    )
    ordered = cached_sorted + live
    seen_rid: set[tuple[str, str]] = set()
    seen_text: set[str] = set()
    out: list[SearchHit] = []
    dropped = 0
    for h in ordered:
        rid_key = (h.job_id, h.review.review_id)
        if rid_key in seen_rid:
            dropped += 1
            continue
        seen_rid.add(rid_key)
        tk = normalize_for_dedup(h.review.review_text or "")
        if tk:
            if tk in seen_text:
                dropped += 1
                continue
            seen_text.add(tk)
        out.append(h)
    return out, dropped


def dedupe_hits(hits: list[SearchHit]) -> tuple[list[SearchHit], int]:
    """单列表去重（用于仅库内检索）。"""
    return merge_cached_and_live(hits, [])
