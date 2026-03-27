# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""采集作业执行器：搜索 → 评论 → 归一化 → 清洗 → 双写存储（单机、顺序、首页分页）。"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, Field

from review_intel.adapters.base import PlatformAdapter
from review_intel.adapters.dummy import DummyAdapter
from review_intel.cleaners.pipeline import clean_and_score_reviews
from review_intel.jobs.checkpoint import CheckpointStage, CheckpointStore, JobCheckpoint
from review_intel.jobs.models import CollectionJob, example_job_womens_sun_protection_painpoint
from review_intel.schemas.normalized import NormalizedReview
from review_intel.storage.repository_protocols import NormalizedReviewRepository, RawReviewRepository
from review_intel.storage.sqlite_support import open_review_intel_stores

logger = logging.getLogger(__name__)

T = TypeVar("T")

#: 单次平台调用失败后额外重试次数（共 ``1 + PLATFORM_MAX_RETRIES`` 次尝试）
PLATFORM_MAX_RETRIES = 2


async def _retry_async(
    factory: Callable[[], Awaitable[T]],
    *,
    label: str,
    max_retries: int = PLATFORM_MAX_RETRIES,
) -> T:
    """异步调用失败时最多重试 ``max_retries`` 次（不含首次）。"""
    last_err: BaseException | None = None
    for attempt in range(max_retries + 1):
        try:
            return await factory()
        except BaseException as e:
            last_err = e
            logger.warning(
                "platform call failed %s attempt %s/%s: %s",
                label,
                attempt + 1,
                max_retries + 1,
                e,
            )
            if attempt >= max_retries:
                break
    assert last_err is not None
    raise last_err


class CollectionRunSummary(BaseModel):
    """单次 ``ReviewCollectionRunner.run`` 的可对账摘要。"""

    job_id: str = Field(..., description="采集作业 ID")
    fetched_count: int = Field(
        ge=0,
        description="从适配器拉取的原始评论事件条数（不含跳过的帖子）",
    )
    normalized_count: int = Field(ge=0, description="归一化产出条数")
    cleaned_count: int = Field(ge=0, description="清洗去重后保留条数")
    stored_raw_count: int = Field(ge=0, description="raw_store.save 为 True 的次数")
    stored_normalized_count: int = Field(
        ge=0,
        description="normalized_store.save 为 True 的次数",
    )
    last_error: str | None = Field(default=None, description="保留字段；失败时以抛异常为准")


def _query_from_job(job: CollectionJob) -> str:
    q = " ".join(job.query_spec.terms).strip()
    return q if q else "*"


def _post_id_from_search_item(item: object) -> str | None:
    if not isinstance(item, dict):
        logger.warning("search item is not dict, skip: %r", item)
        return None
    pid = item.get("id")
    if pid is None:
        pid = item.get("post_id")
    if pid is None:
        return None
    s = str(pid).strip()
    return s if s else None


def _apply_job_context(
    job: CollectionJob,
    review: NormalizedReview,
    crawl_query: str,
) -> NormalizedReview:
    """写入行业/品类/品牌标签、``job_id``，并合并 ``crawl_query`` 到 ``extra_meta``（不覆盖适配器已写键）。"""
    updates: dict[str, object] = {}
    if job.industry is not None:
        updates["industry"] = job.industry
    if job.category is not None:
        updates["category"] = job.category
    if job.brand is not None:
        updates["brand"] = job.brand
    updates["job_id"] = job.job_id
    em = dict(review.extra_meta)
    if "crawl_query" not in em:
        em["crawl_query"] = crawl_query
    updates["extra_meta"] = em
    return review.model_copy(update=updates)


def _persist_checkpoint(store: CheckpointStore, checkpoint: JobCheckpoint) -> None:
    store.save(checkpoint)


def _failed_count_inc(cp_loaded: JobCheckpoint | None) -> int:
    if cp_loaded is None:
        return 1
    return cp_loaded.failed_count + 1


class ReviewCollectionRunner:
    """基于 ``PlatformAdapter`` 与双仓库的最小顺序采集闭环。"""

    async def run(
        self,
        job: CollectionJob,
        adapter: PlatformAdapter,
        raw_store: RawReviewRepository,
        normalized_store: NormalizedReviewRepository,
        *,
        checkpoint_store: CheckpointStore | None = None,
    ) -> CollectionRunSummary:
        query = _query_from_job(job)
        platform = adapter.adapter_name()
        logger.info(
            "collection run start job_id=%s adapter=%s query=%r",
            job.job_id,
            platform,
            query,
        )

        cp_loaded: JobCheckpoint | None = None
        if checkpoint_store is not None:
            cp_loaded = checkpoint_store.load(job.job_id)

        resume_after: str | None = None
        processed_total = cp_loaded.processed_count if cp_loaded else 0
        if cp_loaded is not None and (
            cp_loaded.stage == CheckpointStage.FETCH_COMMENTS
            and cp_loaded.last_post_id
        ):
            resume_after = cp_loaded.last_post_id

        try:
            search_page = await _retry_async(
                lambda: adapter.search_posts(query, None),
                label=f"search_posts({job.job_id})",
            )
        except BaseException as e:
            if checkpoint_store is not None:
                _persist_checkpoint(
                    checkpoint_store,
                    JobCheckpoint(
                        job_id=job.job_id,
                        platform=platform,
                        stage=CheckpointStage.SEARCH,
                        cursor=None,
                        last_post_id=None,
                        processed_count=processed_total,
                        failed_count=_failed_count_inc(cp_loaded),
                        last_error=repr(e),
                    ),
                )
            raise

        if checkpoint_store is not None:
            _persist_checkpoint(
                checkpoint_store,
                JobCheckpoint(
                    job_id=job.job_id,
                    platform=platform,
                    stage=CheckpointStage.SEARCH,
                    cursor=search_page.next_cursor,
                    last_post_id=None,
                    processed_count=processed_total,
                    failed_count=cp_loaded.failed_count if cp_loaded else 0,
                    last_error=None,
                ),
            )

        normalized_batch: list[NormalizedReview] = []
        fetched = 0
        normalized_n = 0
        stored_raw = 0
        skipped_posts = 0

        skip_until_after = resume_after

        for item in search_page.items:
            post_id = _post_id_from_search_item(item)
            if post_id is None:
                skipped_posts += 1
                logger.warning(
                    "search item missing id/post_id, skip job_id=%s item=%r",
                    job.job_id,
                    item,
                )
                continue

            if skip_until_after is not None:
                if post_id == skip_until_after:
                    skip_until_after = None
                continue

            logger.debug("fetch comments post_id=%s job_id=%s", post_id, job.job_id)
            try:
                comment_page = await _retry_async(
                    lambda pid=post_id: adapter.fetch_comments(pid, None),
                    label=f"fetch_comments({post_id})",
                )
            except BaseException as e:
                if checkpoint_store is not None:
                    _persist_checkpoint(
                        checkpoint_store,
                        JobCheckpoint(
                            job_id=job.job_id,
                            platform=platform,
                            stage=CheckpointStage.FETCH_COMMENTS,
                            cursor=None,
                            last_post_id=post_id,
                            processed_count=processed_total,
                            failed_count=_failed_count_inc(cp_loaded),
                            last_error=repr(e),
                        ),
                    )
                raise

            for event in comment_page.items:
                fetched += 1
                event_job = event.model_copy(update={"job_id": job.job_id})
                if raw_store.save(event_job):
                    stored_raw += 1

                raw_dict = event.model_dump(mode="json")
                norm = adapter.normalize_comment(raw_dict)
                norm = _apply_job_context(job, norm, query)
                normalized_batch.append(norm)
                normalized_n += 1
                processed_total += 1

            if checkpoint_store is not None:
                _persist_checkpoint(
                    checkpoint_store,
                    JobCheckpoint(
                        job_id=job.job_id,
                        platform=platform,
                        stage=CheckpointStage.FETCH_COMMENTS,
                        cursor=comment_page.next_cursor,
                        last_post_id=post_id,
                        processed_count=processed_total,
                        failed_count=cp_loaded.failed_count if cp_loaded else 0,
                        last_error=None,
                    ),
                )

        if checkpoint_store is not None:
            _persist_checkpoint(
                checkpoint_store,
                JobCheckpoint(
                    job_id=job.job_id,
                    platform=platform,
                    stage=CheckpointStage.NORMALIZE,
                    cursor=None,
                    last_post_id=None,
                    processed_count=processed_total,
                    failed_count=cp_loaded.failed_count if cp_loaded else 0,
                    last_error=None,
                ),
            )

        cleaned = clean_and_score_reviews(normalized_batch)
        cleaned_n = len(cleaned)

        if checkpoint_store is not None:
            _persist_checkpoint(
                checkpoint_store,
                JobCheckpoint(
                    job_id=job.job_id,
                    platform=platform,
                    stage=CheckpointStage.CLEAN,
                    cursor=None,
                    last_post_id=None,
                    processed_count=processed_total,
                    failed_count=cp_loaded.failed_count if cp_loaded else 0,
                    last_error=None,
                ),
            )

        stored_norm = 0
        for rev in cleaned:
            if normalized_store.save(rev):
                stored_norm += 1

        if checkpoint_store is not None:
            _persist_checkpoint(
                checkpoint_store,
                JobCheckpoint(
                    job_id=job.job_id,
                    platform=platform,
                    stage=CheckpointStage.STORE,
                    cursor=None,
                    last_post_id=None,
                    processed_count=processed_total,
                    failed_count=cp_loaded.failed_count if cp_loaded else 0,
                    last_error=None,
                ),
            )
            checkpoint_store.delete(job.job_id)

        if skipped_posts:
            logger.warning(
                "collection run skipped search items without post id: count=%s job_id=%s",
                skipped_posts,
                job.job_id,
            )

        logger.info(
            "collection run done job_id=%s fetched=%s normalized=%s cleaned=%s "
            "stored_raw=%s stored_norm=%s",
            job.job_id,
            fetched,
            normalized_n,
            cleaned_n,
            stored_raw,
            stored_norm,
        )

        return CollectionRunSummary(
            job_id=job.job_id,
            fetched_count=fetched,
            normalized_count=normalized_n,
            cleaned_count=cleaned_n,
            stored_raw_count=stored_raw,
            stored_normalized_count=stored_norm,
            last_error=None,
        )


async def _main_demo_async() -> CollectionRunSummary:
    job = example_job_womens_sun_protection_painpoint()
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "review_intel_demo.db"
        raw_store, norm_store = open_review_intel_stores(db_path)
        summary = await ReviewCollectionRunner().run(job, DummyAdapter(), raw_store, norm_store)
    return summary


def main_demo() -> None:
    """示例：示例作业 + DummyAdapter + 临时 SQLite；打印摘要。"""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    summary = asyncio.run(_main_demo_async())
    print(summary.model_dump())


if __name__ == "__main__":
    main_demo()
