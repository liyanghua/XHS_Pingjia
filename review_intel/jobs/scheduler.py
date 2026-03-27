# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""最小调度入口：将 CollectionJob、CheckpointStore 与 ReviewCollectionRunner 串成单进程可调用单元。

后续可替换为队列/分布式调度，接口保持 ``run`` 异步方法即可。
"""

from __future__ import annotations

from review_intel.adapters.base import PlatformAdapter
from review_intel.jobs.checkpoint import CheckpointStore
from review_intel.jobs.models import CollectionJob
from review_intel.jobs.runner import CollectionRunSummary, ReviewCollectionRunner
from review_intel.storage.repository_protocols import NormalizedReviewRepository, RawReviewRepository


async def run_collection_job(
    job: CollectionJob,
    adapter: PlatformAdapter,
    raw_store: RawReviewRepository,
    normalized_store: NormalizedReviewRepository,
    *,
    checkpoint_store: CheckpointStore | None = None,
) -> CollectionRunSummary:
    """执行一次采集作业（与直接调用 ``ReviewCollectionRunner.run`` 等价，便于注入调度层）。"""
    return await ReviewCollectionRunner().run(
        job,
        adapter,
        raw_store,
        normalized_store,
        checkpoint_store=checkpoint_store,
    )


class MinimalScheduler:
    """持有可选 ``CheckpointStore`` 的薄封装；无队列、无并发。"""

    def __init__(self, checkpoint_store: CheckpointStore | None = None) -> None:
        self._checkpoint_store = checkpoint_store

    async def run(
        self,
        job: CollectionJob,
        adapter: PlatformAdapter,
        raw_store: RawReviewRepository,
        normalized_store: NormalizedReviewRepository,
    ) -> CollectionRunSummary:
        return await ReviewCollectionRunner().run(
            job,
            adapter,
            raw_store,
            normalized_store,
            checkpoint_store=self._checkpoint_store,
        )
