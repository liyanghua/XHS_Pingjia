# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""storage：同一 SQLite 文件上 raw + normalized 共存。"""

from __future__ import annotations

from review_intel.schemas.examples import example_normalized_review, example_raw_review_event
from review_intel.storage.sqlite_support import open_review_intel_stores


def test_open_review_intel_stores_single_file_both_tables(tmp_path) -> None:
    db = tmp_path / "shared.db"
    raw, norm = open_review_intel_stores(db)
    ev = example_raw_review_event()
    nr = example_normalized_review()
    assert raw.save(ev) is True
    assert norm.save(nr) is True
    assert raw.list_by_job(ev.job_id)
    assert norm.query()
