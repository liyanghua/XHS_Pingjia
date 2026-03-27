# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""ReviewCollectionRunner 闭环与幂等行为。"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from review_intel.adapters.dummy import DummyAdapter
from review_intel.jobs.models import example_job_womens_sun_protection_painpoint
from review_intel.jobs.runner import ReviewCollectionRunner
from review_intel.storage.sqlite_support import open_review_intel_stores


@pytest.mark.asyncio
async def test_run_summary_counts_with_dummy_adapter() -> None:
    """搜索 2 帖 × 每帖 1 条评论；Dummy 复用同一 event_id / 同正文 → 存储与去重计数可解释。"""
    job = example_job_womens_sun_protection_painpoint()
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "ri.db"
        raw_store, norm_store = open_review_intel_stores(db_path)
        runner = ReviewCollectionRunner()
        summary = await runner.run(job, DummyAdapter(), raw_store, norm_store)

    assert summary.job_id == job.job_id
    assert summary.fetched_count == 2
    assert summary.normalized_count == 2
    assert summary.cleaned_count == 1
    assert summary.stored_raw_count == 1
    assert summary.stored_normalized_count == 1


@pytest.mark.asyncio
async def test_normalized_reviews_get_job_id_and_crawl_query() -> None:
    """归一化落库行含 job_id 与 Runner 注入的 crawl_query。"""
    job = example_job_womens_sun_protection_painpoint()
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "ri.db"
        raw_store, norm_store = open_review_intel_stores(db_path)
        await ReviewCollectionRunner().run(job, DummyAdapter(), raw_store, norm_store)
        rows = norm_store.query()

    assert len(rows) >= 1
    expected_q = " ".join(job.query_spec.terms)
    for rev in rows:
        assert rev.job_id == job.job_id
        assert rev.extra_meta.get("crawl_query") == expected_q


@pytest.mark.asyncio
async def test_raw_events_get_job_id() -> None:
    job = example_job_womens_sun_protection_painpoint()
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "ri.db"
        raw_store, norm_store = open_review_intel_stores(db_path)
        await ReviewCollectionRunner().run(job, DummyAdapter(), raw_store, norm_store)
        rows = raw_store.list_by_job(job.job_id)

    assert len(rows) >= 1
    for ev in rows:
        assert ev.job_id == job.job_id


@pytest.mark.asyncio
async def test_second_run_does_not_increase_stored_counts() -> None:
    job = example_job_womens_sun_protection_painpoint()
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "ri.db"
        raw_store, norm_store = open_review_intel_stores(db_path)
        runner = ReviewCollectionRunner()
        first = await runner.run(job, DummyAdapter(), raw_store, norm_store)
        second = await runner.run(job, DummyAdapter(), raw_store, norm_store)

    assert first.stored_raw_count == 1
    assert first.stored_normalized_count == 1
    assert second.fetched_count == 2
    assert second.stored_raw_count == 0
    assert second.stored_normalized_count == 0
