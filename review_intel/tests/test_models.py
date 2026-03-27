# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""领域模型与协议行为测试。"""

from __future__ import annotations

import pytest

from review_intel import (
    ReviewIntelBatch,
    ReviewIntelRecord,
    ReviewIntelStore,
    ReviewIntelTask,
    ReviewIntelTaskRunner,
    ReviewPlatformKey,
    TaskKind,
    TaskResult,
    TaskStatus,
)


def test_review_intel_record_defaults_and_strip() -> None:
    """正文应去首尾空白；默认可用。"""
    rec = ReviewIntelRecord(
        record_id="xhs:cmt:1",
        platform=ReviewPlatformKey.XHS,
        body_text="  hello  ",
    )
    assert rec.body_text == "hello"
    assert rec.platform == ReviewPlatformKey.XHS


def test_review_intel_batch_roundtrip() -> None:
    """批次可序列化并保留记录。"""
    batch = ReviewIntelBatch(
        batch_id="b1",
        records=[
            ReviewIntelRecord(record_id="a", body_text="x"),
            ReviewIntelRecord(record_id="b", body_text="y"),
        ],
    )
    data = batch.model_dump(mode="json")
    restored = ReviewIntelBatch.model_validate(data)
    assert len(restored.records) == 2
    assert restored.records[0].record_id == "a"


def test_review_intel_task_and_result() -> None:
    """任务与结果模型字段一致。"""
    task = ReviewIntelTask(task_id="t1", kind=TaskKind.INGEST, payload={"k": 1})
    assert task.status == TaskStatus.PENDING
    res = TaskResult(task_id=task.task_id, status=TaskStatus.SUCCEEDED, output_ref={"n": 2})
    assert res.output_ref["n"] == 2


@pytest.mark.asyncio
async def test_protocols_runtime_check() -> None:
    """实现类应满足 Protocol 结构子类型。"""

    class _MemStore:
        def __init__(self) -> None:
            self.batches: list[ReviewIntelBatch] = []

        async def append_batch(self, batch: ReviewIntelBatch) -> None:
            self.batches.append(batch)

    class _NoopRunner:
        async def run(self, task: ReviewIntelTask) -> TaskResult:
            return TaskResult(task_id=task.task_id, status=TaskStatus.SUCCEEDED)

    store: ReviewIntelStore = _MemStore()
    runner: ReviewIntelTaskRunner = _NoopRunner()
    assert isinstance(store, ReviewIntelStore)
    assert isinstance(runner, ReviewIntelTaskRunner)

    b = ReviewIntelBatch(batch_id="z", records=[])
    await store.append_batch(b)
    assert isinstance(store, _MemStore)
    assert getattr(store, "batches")[0].batch_id == "z"

    out = await runner.run(ReviewIntelTask(task_id="x", kind=TaskKind.EXPORT))
    assert out.status == TaskStatus.SUCCEEDED
