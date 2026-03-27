# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""进程内作业注册表 + 每作业独立 SQLite 路径，便于替换为远程 DB。"""

from __future__ import annotations

import re
from pathlib import Path

from review_intel.jobs.models import CollectionJob
from review_intel.jobs.runner import CollectionRunSummary

_JOB_ID_SAFE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def assert_safe_job_id(job_id: str) -> None:
    if not _JOB_ID_SAFE.match(job_id) or ".." in job_id or "/" in job_id or "\\" in job_id:
        raise ValueError("invalid job_id")


class JobRegistry:
    """最小内存索引；持久化由每作业目录下 SQLite 承担。"""

    def __init__(self, storage_root: Path) -> None:
        self._root = Path(storage_root)
        self._jobs: dict[str, CollectionJob] = {}
        self._summaries: dict[str, CollectionRunSummary] = {}

    @property
    def storage_root(self) -> Path:
        return self._root

    def store_path(self, job_id: str) -> Path:
        assert_safe_job_id(job_id)
        return self._root / job_id / "store.db"

    def put_job(self, job: CollectionJob) -> None:
        assert_safe_job_id(job.job_id)
        self._jobs[job.job_id] = job

    def get_job(self, job_id: str) -> CollectionJob | None:
        assert_safe_job_id(job_id)
        return self._jobs.get(job_id)

    def set_summary(self, job_id: str, summary: CollectionRunSummary) -> None:
        assert_safe_job_id(job_id)
        self._summaries[job_id] = summary

    def get_summary(self, job_id: str) -> CollectionRunSummary | None:
        assert_safe_job_id(job_id)
        return self._summaries.get(job_id)
