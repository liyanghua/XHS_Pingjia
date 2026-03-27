# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""SQLite 原始/归一化存储：写入、按条件读、幂等。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from review_intel.schemas.examples import example_normalized_review, example_raw_review_event
from review_intel.storage.sqlite_support import open_review_intel_stores


@pytest.fixture
def stores(tmp_path):
    db = tmp_path / "ri.db"
    return open_review_intel_stores(db)


def test_raw_save_idempotent_list_by_job(stores) -> None:
    raw, _ = stores
    ev = example_raw_review_event()
    assert raw.save(ev) is True
    assert raw.save(ev) is False
    rows = raw.list_by_job(ev.job_id)
    assert len(rows) == 1
    assert rows[0].event_id == ev.event_id


def test_normalized_save_idempotent_query(stores) -> None:
    _, norm = stores
    r = example_normalized_review()
    assert norm.save(r) is True
    assert norm.save(r) is False
    out = norm.query(platform=r.platform.value, category=r.category)
    assert len(out) == 1
    assert out[0].review_id == r.review_id


def test_normalized_time_range(stores) -> None:
    _, norm = stores
    t0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    r = example_normalized_review()
    r = r.model_copy(
        update={
            "review_id": "time-range-1",
            "publish_time": t0,
            "crawl_time": t0,
        }
    )
    assert norm.save(r) is True
    lo = t0 - timedelta(days=1)
    hi = t0 + timedelta(days=1)
    q = norm.query(time_start=lo, time_end=hi)
    assert any(x.review_id == "time-range-1" for x in q)
    q2 = norm.query(time_start=t0 + timedelta(days=10))
    assert not any(x.review_id == "time-range-1" for x in q2)
