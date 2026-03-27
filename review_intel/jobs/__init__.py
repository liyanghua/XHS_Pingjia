# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""作业与任务模型：调度单元、状态与结果类型。"""

from review_intel.jobs.checkpoint import (
    CheckpointStage,
    CheckpointStore,
    JobCheckpoint,
    JsonCheckpointStore,
    SqliteCheckpointStore,
)
from review_intel.jobs.models import (
    CollectionJob,
    FreshnessLevel,
    QueryIntent,
    QuerySpec,
    TimeWindow,
    create_job_from_dict,
    example_job_beauty_dupes_competitor,
    example_job_home_storage_need,
    example_job_womens_sun_protection_painpoint,
)
from review_intel.jobs.runner import CollectionRunSummary, ReviewCollectionRunner, main_demo
from review_intel.jobs.scheduler import MinimalScheduler, run_collection_job
from review_intel.jobs.task_models import (
    ReviewIntelTask,
    TaskKind,
    TaskResult,
    TaskStatus,
)

__all__ = [
    "CheckpointStage",
    "CheckpointStore",
    "CollectionJob",
    "CollectionRunSummary",
    "FreshnessLevel",
    "JobCheckpoint",
    "JsonCheckpointStore",
    "MinimalScheduler",
    "QueryIntent",
    "QuerySpec",
    "ReviewCollectionRunner",
    "ReviewIntelTask",
    "SqliteCheckpointStore",
    "TaskKind",
    "TaskResult",
    "TaskStatus",
    "TimeWindow",
    "create_job_from_dict",
    "example_job_beauty_dupes_competitor",
    "example_job_home_storage_need",
    "example_job_womens_sun_protection_painpoint",
    "main_demo",
    "run_collection_job",
]
