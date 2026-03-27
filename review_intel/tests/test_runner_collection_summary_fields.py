# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""runner：摘要模型字段与 Dummy 闭环一致。"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from review_intel.adapters.dummy import DummyAdapter
from review_intel.jobs.models import example_job_womens_sun_protection_painpoint
from review_intel.jobs.runner import CollectionRunSummary, ReviewCollectionRunner
from review_intel.storage.sqlite_support import open_review_intel_stores


@pytest.mark.asyncio
async def test_collection_run_summary_has_stable_counts() -> None:
    job = example_job_womens_sun_protection_painpoint()
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "ri.db"
        raw_store, norm_store = open_review_intel_stores(db_path)
        summary = await ReviewCollectionRunner().run(
            job,
            DummyAdapter(),
            raw_store,
            norm_store,
        )

    assert isinstance(summary, CollectionRunSummary)
    d = summary.model_dump()
    for key in (
        "job_id",
        "fetched_count",
        "normalized_count",
        "cleaned_count",
        "stored_raw_count",
        "stored_normalized_count",
        "retry_count",
        "failed_count",
    ):
        assert key in d
    assert summary.last_error is None
