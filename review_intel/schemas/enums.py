# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""评价情报领域枚举：平台、内容形态、作业状态。

`PlatformType` 取值与 `ReviewPlatformKey` 对齐，便于并存与后续映射。
`JobStatus` 与 `jobs.task_models` 中的任务状态语义一致，作为单一事实来源。
"""

from __future__ import annotations

from enum import Enum


class PlatformType(str, Enum):
    """内容来源平台（短码，适合 DB / API）。"""

    XHS = "xhs"
    DOUYIN = "dy"
    KUAISHOU = "ks"
    BILIBILI = "bili"
    WEIBO = "wb"
    TIEBA = "tieba"
    ZHIHU = "zhihu"
    UNKNOWN = "unknown"


class ContentType(str, Enum):
    """内容形态（非穷举，可按业务扩展）。"""

    POST = "post"
    COMMENT = "comment"
    REPLY = "reply"
    VIDEO = "video"
    SEARCH_HIT = "search_hit"
    UNKNOWN = "unknown"


class JobStatus(str, Enum):
    """采集/归一化等作业生命周期状态（与任务编排层对齐）。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
