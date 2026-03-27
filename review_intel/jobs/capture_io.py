# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""抓取落盘路径与 manifest 辅助（见 docs/capture_ingest_layout.md）。"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from review_intel.storage.sqlite_support import SCHEMA_VERSION


def default_capture_root() -> Path:
    """环境变量 ``REVIEW_INTEL_CAPTURE_ROOT``；未设置则为仓库下 ``review_intel_capture/``。"""
    raw = os.environ.get("REVIEW_INTEL_CAPTURE_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path.cwd() / "review_intel_capture"


def default_api_data_root() -> Path:
    """与 FastAPI ``REVIEW_INTEL_API_DATA`` 对齐，供 ingest 写 ``store.db``。"""
    raw = os.environ.get("REVIEW_INTEL_API_DATA", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path.cwd() / "review_intel_data"


def job_capture_dir(root: Path, job_id: str) -> Path:
    return root / job_id


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def manifest_template(
    *,
    job_id: str,
    crawl_query: str,
    industry: str | None,
    category: str | None,
    query_terms: list[str],
    status: str,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "platform": "xhs",
        "schema_version": SCHEMA_VERSION,
        "adapter_version": "xhs_capture_v1",
        "crawl_query": crawl_query,
        "query_spec": {
            "industry": industry,
            "category": category,
            "terms": query_terms,
        },
        "capture_started_at": utc_now_iso(),
        "capture_finished_at": None,
        "status": status,
        "error": error,
    }
