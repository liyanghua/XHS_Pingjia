# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""作业断点：可序列化状态 + JSON 持久化，便于单机恢复与排障。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)


class CheckpointStage(str, Enum):
    """采集管线阶段（用于定位与恢复）。"""

    SEARCH = "search"
    FETCH_COMMENTS = "fetch_comments"
    NORMALIZE = "normalize"
    CLEAN = "clean"
    STORE = "store"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JobCheckpoint(BaseModel):
    """单次作业在某一时刻的可恢复快照。"""

    job_id: str = Field(..., description="作业 ID")
    platform: str = Field(..., description="适配器名或平台键，如 dummy / xhs")
    stage: CheckpointStage = Field(..., description="当前阶段")
    cursor: str | None = Field(
        default=None,
        description="搜索分页下一页游标（仅 stage=search 时有效）；评论分页请用 comment_cursor",
    )
    comment_cursor: str | None = Field(
        default=None,
        description="评论分页下一页游标；与 pending_post_id 联用表示同帖续拉",
    )
    pending_post_id: str | None = Field(
        default=None,
        description="尚未拉完评论的帖子 ID；存在时 Runner 从该帖继续 fetch_comments",
    )
    last_post_id: str | None = Field(
        default=None,
        description="已完整处理完的帖子 ID；无 pending 时恢复会跳过该帖（旧语义保留）",
    )
    processed_count: int = Field(default=0, ge=0, description="已处理评论事件条数（累计）")
    failed_count: int = Field(default=0, ge=0, description="平台调用失败次数（累计）")
    updated_at: datetime = Field(default_factory=_utc_now, description="UTC 更新时间")
    last_error: str | None = Field(default=None, description="最近一次错误摘要")

    @model_validator(mode="after")
    def _migrate_legacy_fetch_comments_cursor(self) -> JobCheckpoint:
        """旧版将评论下一页游标写在 ``cursor``；迁移到 ``comment_cursor`` + ``pending_post_id``。"""
        if self.pending_post_id is not None or self.comment_cursor is not None:
            return self
        if self.stage != CheckpointStage.FETCH_COMMENTS:
            return self
        if self.cursor and self.last_post_id:
            return self.model_copy(
                update={
                    "comment_cursor": self.cursor,
                    "pending_post_id": self.last_post_id,
                    "cursor": None,
                }
            )
        return self


@runtime_checkable
class CheckpointStore(Protocol):
    """断点存储抽象，可替换为 SQLite / Redis 等。"""

    def load(self, job_id: str) -> JobCheckpoint | None:
        """读取作业断点；不存在则 ``None``。"""

    def save(self, checkpoint: JobCheckpoint) -> None:
        """覆盖写入断点。"""

    def delete(self, job_id: str) -> None:
        """删除断点（成功结束后可选调用）。"""


class JsonCheckpointStore:
    """每作业一个 JSON 文件，便于人工查看与拷贝。"""

    def __init__(self, base_dir: str | Path) -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    def _path(self, job_id: str) -> Path:
        safe = job_id.replace("/", "_").replace("..", "_")
        return self._base / f"{safe}.json"

    def load(self, job_id: str) -> JobCheckpoint | None:
        p = self._path(job_id)
        if not p.is_file():
            return None
        text = p.read_text(encoding="utf-8")
        return JobCheckpoint.model_validate_json(text)

    def save(self, checkpoint: JobCheckpoint) -> None:
        p = self._path(checkpoint.job_id)
        tmp = p.with_suffix(".json.tmp")
        cp = checkpoint.model_copy(update={"updated_at": _utc_now()})
        data = cp.model_dump_json(indent=2)
        tmp.write_text(data, encoding="utf-8")
        tmp.replace(p)
        logger.debug("checkpoint saved job_id=%s stage=%s", cp.job_id, cp.stage.value)

    def delete(self, job_id: str) -> None:
        p = self._path(job_id)
        if p.is_file():
            p.unlink()


class SqliteCheckpointStore:
    """与 review_intel 其它 SQLite 存储一致，单表 `job_checkpoints`。"""

    def __init__(self, conn: object) -> None:
        import sqlite3

        if not isinstance(conn, sqlite3.Connection):
            raise TypeError("conn must be sqlite3.Connection")
        conn.row_factory = sqlite3.Row
        self._conn = conn
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_checkpoints (
                job_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def load(self, job_id: str) -> JobCheckpoint | None:
        row = self._conn.execute(
            "SELECT payload_json FROM job_checkpoints WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            return None
        return JobCheckpoint.model_validate_json(row["payload_json"])

    def save(self, checkpoint: JobCheckpoint) -> None:
        cp = checkpoint.model_copy(update={"updated_at": _utc_now()})
        payload = cp.model_dump_json()
        self._conn.execute(
            """
            INSERT INTO job_checkpoints (job_id, payload_json)
            VALUES (?, ?)
            ON CONFLICT(job_id) DO UPDATE SET payload_json = excluded.payload_json
            """,
            (cp.job_id, payload),
        )
        self._conn.commit()
        logger.debug("checkpoint saved job_id=%s stage=%s", cp.job_id, cp.stage.value)

    def delete(self, job_id: str) -> None:
        self._conn.execute("DELETE FROM job_checkpoints WHERE job_id = ?", (job_id,))
        self._conn.commit()
