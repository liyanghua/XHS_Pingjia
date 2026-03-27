# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""review_intel 最小 FastAPI 应用，供本地调试与后续挂载主服务。

启动::

    uvicorn review_intel.api.app:app --reload --port 8090

环境变量 ``REVIEW_INTEL_API_DATA``：作业与 SQLite 数据根目录；未设置则使用临时目录。
"""

from __future__ import annotations

import logging
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from review_intel.api.registry import JobRegistry
from review_intel.api.routes import build_router
from review_intel.api.search_routes import build_search_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    raw = os.environ.get("REVIEW_INTEL_API_DATA")
    if raw:
        root = Path(raw)
    else:
        root = Path(tempfile.mkdtemp(prefix="review_intel_api_"))
    root.mkdir(parents=True, exist_ok=True)
    app.state.registry = JobRegistry(root)
    logger.info("review_intel API data root: %s", root)
    yield


def create_app() -> FastAPI:
    """构造 FastAPI 实例（测试可注入独立数据目录）。"""
    app = FastAPI(
        title="review_intel API",
        description="评价情报子系统调试接口（同步执行 Dummy 采集闭环）",
        version="0.1.0",
        lifespan=_lifespan,
    )
    # 开发时 Vite 端口可能不是 5173；生产可收紧为具体域名
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(build_router())
    app.include_router(build_search_router())
    return app


app = create_app()
