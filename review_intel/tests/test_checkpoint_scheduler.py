# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""CheckpointStore、重试与 Runner 恢复路径。"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from review_intel.adapters.dummy import DummyAdapter
from review_intel.jobs.checkpoint import (
    CheckpointStage,
    JobCheckpoint,
    JsonCheckpointStore,
    SqliteCheckpointStore,
)
from review_intel.jobs.models import example_job_womens_sun_protection_painpoint
from review_intel.jobs.runner import ReviewCollectionRunner
from review_intel.jobs.scheduler import MinimalScheduler, run_collection_job
from review_intel.storage.sqlite_support import connect, open_review_intel_stores


def test_json_checkpoint_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = JsonCheckpointStore(tmp)
        cp = JobCheckpoint(
            job_id="j1",
            platform="dummy",
            stage=CheckpointStage.FETCH_COMMENTS,
            cursor="c1",
            last_post_id="p9",
            processed_count=3,
            failed_count=0,
            updated_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        )
        store.save(cp)
        loaded = store.load("j1")
        assert loaded is not None
        assert loaded.job_id == "j1"
        assert loaded.stage == CheckpointStage.FETCH_COMMENTS
        assert loaded.last_post_id == "p9"
        assert loaded.processed_count == 3
        store.delete("j1")
        assert store.load("j1") is None


def test_sqlite_checkpoint_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "c.db"
        conn = connect(db)
        store = SqliteCheckpointStore(conn)
        cp = JobCheckpoint(
            job_id="j1",
            platform="xhs",
            stage=CheckpointStage.SEARCH,
            cursor=None,
            last_post_id=None,
            processed_count=0,
            failed_count=1,
        )
        store.save(cp)
        loaded = store.load("j1")
        assert loaded is not None
        assert loaded.failed_count == 1
        store.delete("j1")
        assert store.load("j1") is None


class FlakySearchAdapter(DummyAdapter):
    """前 ``n`` 次 ``search_posts`` 抛错，之后成功。"""

    def __init__(self, fail_times: int) -> None:
        super().__init__()
        self._fail_times = fail_times
        self._calls = 0

    async def search_posts(self, query: str, cursor: str | None = None):  # type: ignore[override]
        self._calls += 1
        if self._calls <= self._fail_times:
            raise RuntimeError("transient")
        return await super().search_posts(query, cursor)


@pytest.mark.asyncio
async def test_search_retries_then_succeeds() -> None:
    job = example_job_womens_sun_protection_painpoint()
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "ri.db"
        raw_store, norm_store = open_review_intel_stores(db_path)
        adapter = FlakySearchAdapter(fail_times=2)
        summary = await ReviewCollectionRunner().run(job, adapter, raw_store, norm_store)
    assert adapter._calls == 3
    assert summary.fetched_count == 2


@pytest.mark.asyncio
async def test_search_fails_after_all_retries_checkpoint_persisted() -> None:
    job = example_job_womens_sun_protection_painpoint()
    with tempfile.TemporaryDirectory() as tmp:
        cp_dir = Path(tmp) / "cp"
        store = JsonCheckpointStore(cp_dir)
        db_path = Path(tmp) / "ri.db"
        raw_store, norm_store = open_review_intel_stores(db_path)

        class AlwaysFailSearch(DummyAdapter):
            async def search_posts(self, query: str, cursor: str | None = None):  # type: ignore[override]
                raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            await ReviewCollectionRunner().run(
                job,
                AlwaysFailSearch(),
                raw_store,
                norm_store,
                checkpoint_store=store,
            )
        loaded = store.load(job.job_id)
        assert loaded is not None
        assert loaded.stage == CheckpointStage.SEARCH
        assert loaded.last_error is not None
        assert "boom" in loaded.last_error
        assert loaded.failed_count >= 1


@pytest.mark.asyncio
async def test_resume_skips_post_after_last_post_id() -> None:
    """断点 last_post_id=n1: 仅处理第二帖。"""

    job = example_job_womens_sun_protection_painpoint()
    with tempfile.TemporaryDirectory() as tmp:
        cp_dir = Path(tmp) / "cp"
        store = JsonCheckpointStore(cp_dir)
        store.save(
            JobCheckpoint(
                job_id=job.job_id,
                platform="dummy",
                stage=CheckpointStage.FETCH_COMMENTS,
                cursor=None,
                last_post_id="n1",
                processed_count=1,
                failed_count=0,
            )
        )
        db_path = Path(tmp) / "ri.db"
        raw_store, norm_store = open_review_intel_stores(db_path)
        summary = await ReviewCollectionRunner().run(
            job,
            DummyAdapter(),
            raw_store,
            norm_store,
            checkpoint_store=store,
        )

    assert summary.fetched_count == 1
    assert summary.normalized_count == 1


@pytest.mark.asyncio
async def test_run_collection_job_delegates_to_runner() -> None:
    job = example_job_womens_sun_protection_painpoint()
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "ri.db"
        raw_store, norm_store = open_review_intel_stores(db_path)
        s = await run_collection_job(job, DummyAdapter(), raw_store, norm_store)
        assert s.fetched_count == 2


@pytest.mark.asyncio
async def test_minimal_scheduler() -> None:
    job = example_job_womens_sun_protection_painpoint()
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "ri.db"
        raw_store, norm_store = open_review_intel_stores(db_path)
        sch = MinimalScheduler()
        s = await sch.run(job, DummyAdapter(), raw_store, norm_store)
        assert s.fetched_count == 2
