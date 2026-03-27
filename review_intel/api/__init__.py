# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""HTTP 边界：最小 FastAPI 调试服务见 ``app`` / ``create_app``。"""

from review_intel.api.app import app, create_app
from review_intel.api.placeholder import get_review_intel_router_prefix

__all__ = [
    "app",
    "create_app",
    "get_review_intel_router_prefix",
]
