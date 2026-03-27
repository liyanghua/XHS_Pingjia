# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""清洗与规范化：文本与结构化字段处理。"""

from review_intel.cleaners.base import ReviewIntelCleaner
from review_intel.cleaners.dedup import (
    ExactTextDeduper,
    NearDuplicateResolver,
    NoopNearDuplicateResolver,
    normalize_for_dedup,
)
from review_intel.cleaners.filters import (
    contains_ad_keywords,
    default_ad_keywords,
    is_empty_text,
    is_pure_emoji_or_symbols,
    is_too_short,
    should_keep_review_text,
)
from review_intel.cleaners.pipeline import clean_and_score_reviews
from review_intel.cleaners.quality_score import compute_quality_score

__all__ = [
    "ExactTextDeduper",
    "NearDuplicateResolver",
    "NoopNearDuplicateResolver",
    "ReviewIntelCleaner",
    "clean_and_score_reviews",
    "compute_quality_score",
    "contains_ad_keywords",
    "default_ad_keywords",
    "is_empty_text",
    "is_pure_emoji_or_symbols",
    "is_too_short",
    "normalize_for_dedup",
    "should_keep_review_text",
]
