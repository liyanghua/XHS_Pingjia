# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""review_intel 对外 API 边界占位。

与仓库顶层 `api/`（FastAPI 爬虫服务）区分：本模块仅预留子系统专用路由或 CLI
的挂载点，默认不向主应用注册，避免改变现有 HTTP 行为。
"""

from __future__ import annotations


def get_review_intel_router_prefix() -> str:
    """返回未来挂载到主应用时的 URL 前缀（占位）。"""
    return "/review-intel"
