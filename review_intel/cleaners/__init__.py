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
    hits_high_value_short_term,
    is_empty_text,
    is_pure_emoji_or_symbols,
    is_too_short,
    should_keep_review_text,
)
from review_intel.cleaners.pipeline import clean_and_score_reviews
from review_intel.cleaners.quality_score import QUALITY_FLOOR_SHORT_HIT, compute_quality_score
from review_intel.cleaners.term_lists import default_high_value_short_terms

__all__ = [
    "ExactTextDeduper",
    "NearDuplicateResolver",
    "NoopNearDuplicateResolver",
    "ReviewIntelCleaner",
    "QUALITY_FLOOR_SHORT_HIT",
    "clean_and_score_reviews",
    "compute_quality_score",
    "contains_ad_keywords",
    "default_ad_keywords",
    "default_high_value_short_terms",
    "is_empty_text",
    "is_pure_emoji_or_symbols",
    "is_too_short",
    "normalize_for_dedup",
    "hits_high_value_short_term",
    "should_keep_review_text",
]
