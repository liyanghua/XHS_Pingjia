# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""评价情报 Pydantic 模型、枚举与样例工厂导出。"""

from review_intel.schemas.enums import ContentType, JobStatus, PlatformType
from review_intel.schemas.examples import (
    example_comment_page,
    example_normalized_review,
    example_raw_review_event,
    example_search_page,
)
from review_intel.schemas.models import (
    ReviewIntelBatch,
    ReviewIntelRecord,
    ReviewPlatformKey,
)
from review_intel.schemas.normalized import NormalizedReview
from review_intel.schemas.pages import CommentPage, SearchPage
from review_intel.schemas.raw_event import RawReviewEvent

__all__ = [
    "CommentPage",
    "ContentType",
    "JobStatus",
    "NormalizedReview",
    "PlatformType",
    "RawReviewEvent",
    "ReviewIntelBatch",
    "ReviewIntelRecord",
    "ReviewPlatformKey",
    "SearchPage",
    "example_comment_page",
    "example_normalized_review",
    "example_raw_review_event",
    "example_search_page",
]
