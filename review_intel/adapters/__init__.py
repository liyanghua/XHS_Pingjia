# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""适配器层：连接各平台爬虫与 review_intel 领域模型。"""

from review_intel.adapters.base import PlatformAdapter
from review_intel.adapters.dummy import DummyAdapter
from review_intel.adapters.types import JsonObject, RateLimitPolicy
from review_intel.adapters.xiaohongshu import XHSAdapter

__all__ = [
    "DummyAdapter",
    "JsonObject",
    "PlatformAdapter",
    "RateLimitPolicy",
    "XHSAdapter",
]
