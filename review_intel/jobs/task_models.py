# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""review_intel 任务模型：描述异步/离线处理单元的状态与结果。"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from review_intel.schemas.enums import JobStatus

# 与 schemas.JobStatus 同一枚举，保持任务状态单一事实来源
TaskStatus = JobStatus


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TaskKind(str, Enum):
    """任务类型（增量扩展；当前仅定义占位）。"""

    INGEST = "ingest"
    NORMALIZE = "normalize"
    EXPORT = "export"


class ReviewIntelTask(BaseModel):
    """评价情报流水线中的可调度任务。"""

    task_id: str = Field(..., description="全局唯一任务 ID")
    kind: TaskKind = Field(..., description="任务种类")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="当前状态")
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="不透明负载：输入参数、游标、平台句柄等",
    )
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: Optional[datetime] = Field(default=None)
    error: Optional[str] = Field(default=None, description="失败时的错误信息")


class TaskResult(BaseModel):
    """任务执行结果摘要（与具体业务输出解耦）。"""

    task_id: str
    status: TaskStatus
    message: Optional[str] = None
    output_ref: dict[str, Any] = Field(
        default_factory=dict,
        description="可选：输出引用（路径、对象键、条数统计等）",
    )
