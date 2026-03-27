# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""持久化与协议：存储抽象及任务运行器接口。"""

from review_intel.storage.normalized_store import SqliteNormalizedReviewStore, open_normalized_store
from review_intel.storage.protocols import ReviewIntelStore, ReviewIntelTaskRunner
from review_intel.storage.raw_store import SqliteRawReviewStore, open_raw_store
from review_intel.storage.repository_protocols import NormalizedReviewRepository, RawReviewRepository
from review_intel.storage.sqlite_support import connect, dumps_model, open_review_intel_stores

__all__ = [
    "NormalizedReviewRepository",
    "RawReviewRepository",
    "ReviewIntelStore",
    "ReviewIntelTaskRunner",
    "SqliteNormalizedReviewStore",
    "SqliteRawReviewStore",
    "connect",
    "dumps_model",
    "open_normalized_store",
    "open_raw_store",
    "open_review_intel_stores",
]
