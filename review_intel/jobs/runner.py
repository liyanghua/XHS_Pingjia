# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""采集作业执行器：搜索 → 评论 → 归一化 → 清洗 → 双写存储（单机、顺序、分页可配）。"""

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
from review_intel.jobs.models import (
    CollectionJob,
    CollectionRunLimits,
    example_job_womens_sun_protection_painpoint,
)
from review_intel.schemas.normalized import NormalizedReview
from review_intel.schemas.pages import CommentPage
from review_intel.schemas.raw_event import RawReviewEvent
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
    metrics: dict[str, int] | None = None,
) -> T:
    """异步调用失败时最多重试 ``max_retries`` 次（不含首次）。

    若传入 ``metrics``，每次进入下一轮重试前递增 ``metrics[\"retry\"]``，供验收对账。
    """
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
            if metrics is not None:
                metrics["retry"] = metrics.get("retry", 0) + 1
    assert last_err is not None
    raise last_err


class RunErrorContext(BaseModel):
    """平台调用失败时的可序列化定位信息（日志 / 排障）。"""

    stage: str = Field(..., description="CheckpointStage 或 search/comments 子阶段")
    post_id: str | None = None
    search_cursor: str | None = None
    comment_cursor: str | None = None
    message: str = ""


class CollectionRunSummary(BaseModel):
    """单次 ``ReviewCollectionRunner.run`` 的可对账摘要。"""

    job_id: str = Field(..., description="采集作业 ID")
    fetched_count: int = Field(
        ge=0,
        description="从适配器拉取的原始评论事件条数（含回复链，若开启 enable_replies）",
    )
    normalized_count: int = Field(ge=0, description="归一化产出条数")
    cleaned_count: int = Field(ge=0, description="清洗去重后保留条数")
    stored_raw_count: int = Field(ge=0, description="raw_store.save 为 True 的次数")
    stored_normalized_count: int = Field(
        ge=0,
        description="normalized_store.save 为 True 的次数",
    )
    last_error: str | None = Field(default=None, description="保留字段；失败时以抛异常为准")
    limits: CollectionRunLimits = Field(
        default_factory=CollectionRunLimits,
        description="本次运行使用的调度边界（回显）",
    )
    search_pages_fetched: int = Field(default=0, ge=0, description="实际拉取的搜索分页页数")
    posts_selected: int = Field(default=0, ge=0, description="应用 max_posts 后参与评论抓取的帖子数")
    comment_pages_fetched: int = Field(default=0, ge=0, description="累计评论分页请求次数")
    reply_pages_fetched: int = Field(default=0, ge=0, description="fetch_replies 分页次数")
    retry_count: int = Field(
        default=0,
        ge=0,
        description="平台调用在 _retry_async 内的累计重试次数（不含首次尝试）",
    )
    failed_count: int = Field(
        default=0,
        ge=0,
        description="成功完成时为 0；断点中累计失败次数可在未来与 checkpoint 对齐",
    )
    last_error_context: RunErrorContext | None = Field(
        default=None,
        description="成功时为 None；若未来支持部分失败返回可填充",
    )


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


def _comment_next_cursor(page: CommentPage) -> str | None:
    return page.next_cursor or page.page_token


def _comment_has_more(page: CommentPage) -> bool:
    nc = _comment_next_cursor(page)
    if nc:
        return True
    return bool(page.has_more)


def _append_normalized_event(
    job: CollectionJob,
    query: str,
    adapter: PlatformAdapter,
    raw_store: RawReviewRepository,
    normalized_batch: list[NormalizedReview],
    event_job: RawReviewEvent,
) -> tuple[int, int, int]:
    """处理一条 ``RawReviewEvent``：raw 落库 + 归一化追加。返回 (stored_raw_delta, normalized_n_delta, processed_delta)。"""
    stored_raw = 0
    if raw_store.save(event_job):
        stored_raw = 1
    raw_dict = event_job.model_dump(mode="json")
    norm = adapter.normalize_comment(raw_dict)
    norm = _apply_job_context(job, norm, query)
    normalized_batch.append(norm)
    return stored_raw, 1, 1


async def _drain_replies_for_comment(
    *,
    adapter: PlatformAdapter,
    job: CollectionJob,
    query: str,
    raw_store: RawReviewRepository,
    normalized_batch: list[NormalizedReview],
    comment_id: str,
    limits: CollectionRunLimits,
    remaining_quota: int | None,
    reply_pages_fetched: list[int],
    metrics: dict[str, int] | None = None,
) -> tuple[int, int, int]:
    """拉取一条评论的回复链；与顶层共用 ``max_comments_per_post`` 剩余配额。返回 (fetched, norm_delta, raw_saved)。"""
    fetched = 0
    norm_d = 0
    raw_saved = 0
    rc: str | None = None
    rpages = 0
    while True:
        if limits.max_comment_pages_per_post is not None and rpages >= limits.max_comment_pages_per_post:
            break
        if remaining_quota is not None and remaining_quota <= 0:
            break
        try:
            cur = rc
            rpage = await _retry_async(
                lambda: adapter.fetch_replies(comment_id, cur),
                label=f"fetch_replies({comment_id})",
                metrics=metrics,
            )
        except BaseException:
            raise
        rpages += 1
        reply_pages_fetched[0] += 1

        for event in rpage.items:
            if remaining_quota is not None:
                if remaining_quota <= 0:
                    return fetched, norm_d, raw_saved
                remaining_quota -= 1
            ev = event.model_copy(update={"job_id": job.job_id})
            sr, nd, _pd = _append_normalized_event(
                job, query, adapter, raw_store, normalized_batch, ev
            )
            raw_saved += sr
            norm_d += nd
            fetched += 1

        nxt = _comment_next_cursor(rpage)
        if not _comment_has_more(rpage) or not nxt:
            break
        rc = nxt

    return fetched, norm_d, raw_saved


class ReviewCollectionRunner:
    """基于 ``PlatformAdapter`` 与双仓库的顺序采集闭环（分页与上限由 ``CollectionRunLimits`` 控制）。"""

    async def run(
        self,
        job: CollectionJob,
        adapter: PlatformAdapter,
        raw_store: RawReviewRepository,
        normalized_store: NormalizedReviewRepository,
        *,
        checkpoint_store: CheckpointStore | None = None,
        limits: CollectionRunLimits | None = None,
    ) -> CollectionRunSummary:
        limits = limits or CollectionRunLimits()
        query = _query_from_job(job)
        platform = adapter.adapter_name()
        logger.info(
            "collection run start job_id=%s adapter=%s query=%r limits=%s",
            job.job_id,
            platform,
            query,
            limits.model_dump(),
        )

        cp_loaded: JobCheckpoint | None = None
        if checkpoint_store is not None:
            cp_loaded = checkpoint_store.load(job.job_id)

        processed_total = cp_loaded.processed_count if cp_loaded else 0

        skip_until_after: str | None = None
        resume_post_id: str | None = None
        resume_comment_cursor: str | None = None
        if cp_loaded is not None:
            if cp_loaded.pending_post_id:
                resume_post_id = cp_loaded.pending_post_id
                resume_comment_cursor = cp_loaded.comment_cursor
            elif (
                cp_loaded.stage == CheckpointStage.FETCH_COMMENTS
                and cp_loaded.last_post_id
            ):
                skip_until_after = cp_loaded.last_post_id

        last_completed_post_id: str | None = None

        normalized_batch: list[NormalizedReview] = []
        fetched = 0
        normalized_n = 0
        stored_raw = 0
        skipped_posts = 0
        search_pages_fetched = 0
        comment_pages_fetched = 0
        reply_pages_fetched_box = [0]

        search_cursor: str | None = None
        retry_metrics: dict[str, int] = {"retry": 0}

        try:
            merged_items: list[dict] = []
            for _ in range(limits.max_search_pages):
                cur_sc = search_cursor
                sp = await _retry_async(
                    lambda: adapter.search_posts(query, cur_sc),
                    label=f"search_posts({job.job_id})",
                    metrics=retry_metrics,
                )
                search_pages_fetched += 1
                merged_items.extend(sp.items)
                next_sc = sp.next_cursor or sp.page_token
                if not next_sc and not sp.has_more:
                    break
                if not next_sc:
                    break
                search_cursor = next_sc
        except BaseException as e:
            logger.error(
                "collection failed job_id=%s stage=search search_cursor=%r err=%s",
                job.job_id,
                search_cursor,
                e,
            )
            if checkpoint_store is not None:
                _persist_checkpoint(
                    checkpoint_store,
                    JobCheckpoint(
                        job_id=job.job_id,
                        platform=platform,
                        stage=CheckpointStage.SEARCH,
                        cursor=search_cursor,
                        comment_cursor=None,
                        pending_post_id=None,
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
                    cursor=search_cursor,
                    comment_cursor=None,
                    pending_post_id=None,
                    last_post_id=None,
                    processed_count=processed_total,
                    failed_count=cp_loaded.failed_count if cp_loaded else 0,
                    last_error=None,
                ),
            )

        posts_items: list[tuple[str, dict]] = []
        for item in merged_items:
            pid = _post_id_from_search_item(item)
            if pid is None:
                skipped_posts += 1
                logger.warning(
                    "search item missing id/post_id, skip job_id=%s item=%r",
                    job.job_id,
                    item,
                )
                continue
            posts_items.append((pid, item))

        if limits.max_posts is not None:
            posts_items = posts_items[: limits.max_posts]

        posts_selected = len(posts_items)

        for post_id, _item in posts_items:
            if skip_until_after is not None:
                if post_id == skip_until_after:
                    skip_until_after = None
                continue

            if resume_post_id is not None and post_id != resume_post_id:
                continue

            start_cc: str | None = None
            if resume_post_id == post_id:
                start_cc = resume_comment_cursor
                resume_post_id = None
                resume_comment_cursor = None

            cc_loop: str | None = start_cc
            pages_this_post = 0
            events_this_post = 0
            stop_post = False

            while not stop_post:
                if (
                    limits.max_comment_pages_per_post is not None
                    and pages_this_post >= limits.max_comment_pages_per_post
                ):
                    break

                cur_cc = cc_loop
                try:
                    cpage = await _retry_async(
                        lambda: adapter.fetch_comments(post_id, cur_cc),
                        label=f"fetch_comments({post_id})",
                        metrics=retry_metrics,
                    )
                except BaseException as e:
                    logger.error(
                        "collection failed job_id=%s stage=fetch_comments post_id=%s "
                        "search_cursor=%r comment_cursor=%r err=%s",
                        job.job_id,
                        post_id,
                        search_cursor,
                        cc_loop,
                        e,
                    )
                    if checkpoint_store is not None:
                        _persist_checkpoint(
                            checkpoint_store,
                            JobCheckpoint(
                                job_id=job.job_id,
                                platform=platform,
                                stage=CheckpointStage.FETCH_COMMENTS,
                                cursor=None,
                                comment_cursor=cc_loop,
                                pending_post_id=post_id,
                                last_post_id=last_completed_post_id,
                                processed_count=processed_total,
                                failed_count=_failed_count_inc(cp_loaded),
                                last_error=repr(e),
                            ),
                        )
                    raise

                pages_this_post += 1
                comment_pages_fetched += 1

                for event in cpage.items:
                    if limits.max_comments_per_post is not None:
                        if events_this_post >= limits.max_comments_per_post:
                            stop_post = True
                            break
                    events_this_post += 1
                    ev = event.model_copy(update={"job_id": job.job_id})
                    sr, nd, pd = _append_normalized_event(
                        job, query, adapter, raw_store, normalized_batch, ev
                    )
                    stored_raw += sr
                    normalized_n += nd
                    processed_total += pd
                    fetched += 1

                    if limits.enable_replies:
                        rem: int | None
                        if limits.max_comments_per_post is None:
                            rem = None
                        else:
                            rem = max(0, limits.max_comments_per_post - events_this_post)
                        if rem is None or rem > 0:
                            rf, rnd, rs = await _drain_replies_for_comment(
                                adapter=adapter,
                                job=job,
                                query=query,
                                raw_store=raw_store,
                                normalized_batch=normalized_batch,
                                comment_id=str(event.source_id),
                                limits=limits,
                                remaining_quota=rem,
                                reply_pages_fetched=reply_pages_fetched_box,
                                metrics=retry_metrics,
                            )
                            stored_raw += rs
                            normalized_n += rnd
                            processed_total += rnd
                            fetched += rf
                            events_this_post += rf

                if stop_post:
                    break

                next_cc = _comment_next_cursor(cpage)
                if not _comment_has_more(cpage) or not next_cc:
                    break

                cc_loop = next_cc

                if checkpoint_store is not None:
                    _persist_checkpoint(
                        checkpoint_store,
                        JobCheckpoint(
                            job_id=job.job_id,
                            platform=platform,
                            stage=CheckpointStage.FETCH_COMMENTS,
                            cursor=None,
                            comment_cursor=next_cc,
                            pending_post_id=post_id,
                            last_post_id=last_completed_post_id,
                            processed_count=processed_total,
                            failed_count=cp_loaded.failed_count if cp_loaded else 0,
                            last_error=None,
                        ),
                    )

            last_completed_post_id = post_id
            if checkpoint_store is not None:
                _persist_checkpoint(
                    checkpoint_store,
                    JobCheckpoint(
                        job_id=job.job_id,
                        platform=platform,
                        stage=CheckpointStage.FETCH_COMMENTS,
                        cursor=None,
                        comment_cursor=None,
                        pending_post_id=None,
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
                    comment_cursor=None,
                    pending_post_id=None,
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
                    comment_cursor=None,
                    pending_post_id=None,
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
                    comment_cursor=None,
                    pending_post_id=None,
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

        reply_pages_fetched = reply_pages_fetched_box[0]

        logger.info(
            "collection run done job_id=%s fetched=%s normalized=%s cleaned=%s "
            "stored_raw=%s stored_norm=%s limits=%s search_pages=%s posts=%s "
            "comment_pages=%s reply_pages=%s",
            job.job_id,
            fetched,
            normalized_n,
            cleaned_n,
            stored_raw,
            stored_norm,
            limits.model_dump(),
            search_pages_fetched,
            posts_selected,
            comment_pages_fetched,
            reply_pages_fetched,
        )

        return CollectionRunSummary(
            job_id=job.job_id,
            fetched_count=fetched,
            normalized_count=normalized_n,
            cleaned_count=cleaned_n,
            stored_raw_count=stored_raw,
            stored_normalized_count=stored_norm,
            last_error=None,
            limits=limits,
            search_pages_fetched=search_pages_fetched,
            posts_selected=posts_selected,
            comment_pages_fetched=comment_pages_fetched,
            reply_pages_fetched=reply_pages_fetched,
            retry_count=retry_metrics.get("retry", 0),
            failed_count=0,
            last_error_context=None,
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
