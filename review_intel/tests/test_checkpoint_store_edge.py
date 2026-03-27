# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""checkpoint：存储边界行为。"""

from __future__ import annotations

import tempfile
from pathlib import Path

from review_intel.jobs.checkpoint import CheckpointStage, JobCheckpoint, JsonCheckpointStore


def test_json_checkpoint_store_load_missing_returns_none() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = JsonCheckpointStore(tmp)
        assert store.load("no-such-job") is None


def test_json_checkpoint_roundtrip_preserves_stage() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = JsonCheckpointStore(tmp)
        cp = JobCheckpoint(
            job_id="j-edge",
            platform="dummy",
            stage=CheckpointStage.NORMALIZE,
            cursor=None,
            last_post_id=None,
            processed_count=0,
            failed_count=0,
        )
        store.save(cp)
        loaded = store.load("j-edge")
        assert loaded is not None
        assert loaded.stage == CheckpointStage.NORMALIZE
