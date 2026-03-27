# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""小红书第一轮真实平台验收：Runner + 双写 SQLite + ``acceptance_report.json`` / Markdown 摘要。

**前置条件**（与 ``runner_acceptance_demo`` / ``xhs_demo`` 相同）：

- 仓库根目录、已安装依赖与 Playwright 浏览器（``playwright install``）。
- 已能打开 ``https://www.xiaohongshu.com/`` 且 **Web 端已登录**（扫码 Cookie 持久化见 ``config`` 与 ``README_XHS``）。
- 网络可达；若首页 ``goto`` 超时，加大 ``--goto-timeout-ms``（默认 120000）。

运行示例::

    python -m review_intel.jobs.run_xhs_acceptance \\
      --output-dir review_intel_data/xhs_acceptance/run-001

产出（默认在 ``output-dir`` 下）：

- ``acceptance_report.json``：结构化验收报告（人工 review / CI 归档）。
- ``acceptance_summary.md``：通过项与暴露问题简述。

"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from review_intel.jobs.acceptance_report import (
    AcceptanceChecklist,
    FieldCoverageEntry,
    SampleReviewSnippet,
    XhsAcceptanceReport,
)
from review_intel.jobs.models import CollectionJob, CollectionRunLimits
from review_intel.jobs.xhs_acceptance_bootstrap import (
    _DEFAULT_GOTO_TIMEOUT_MS,
    build_acceptance_job,
    run_xhs_collection_with_browser,
)
from review_intel.schemas.normalized import NormalizedReview
from review_intel.storage.sqlite_support import connect, open_review_intel_stores


def _query_summary(job: CollectionJob) -> str:
    qs = job.query_spec
    bits = [
        f"industry={qs.industry!r}",
        f"category={qs.category!r}",
        f"intent={qs.intent.value}",
        f"terms={qs.terms!r}",
    ]
    return "; ".join(bits)


def _count_raw_events_for_job(db_path: Path, job_id: str) -> int:
    """``raw_review_events`` 中该 ``job_id`` 的行数（与是否本次 INSERT 成功无关）。"""
    conn = connect(db_path)
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM raw_review_events WHERE job_id = ?",
        (job_id,),
    ).fetchone()
    return int(row["c"]) if row else 0


def _list_normalized_for_job(db_path: Path, job_id: str) -> list[NormalizedReview]:
    """按 ``payload_json.job_id`` 过滤（验收库通常很小，全表扫描可接受）。"""
    raw_store, norm_store = open_review_intel_stores(db_path)
    _ = raw_store
    all_rows = norm_store.query()
    return [r for r in all_rows if r.job_id == job_id]


def _field_coverage(reviews: list[NormalizedReview]) -> list[FieldCoverageEntry]:
    if not reviews:
        return []
    total = len(reviews)
    checks: list[tuple[str, object]] = [
        ("review_id", lambda r: bool(r.review_id)),
        ("platform", lambda r: r.platform is not None),
        ("review_text", lambda r: bool((r.review_text or "").strip())),
        ("publish_time", lambda r: r.publish_time is not None),
        ("source_post_id", lambda r: bool(r.source_post_id)),
        ("source_comment_id", lambda r: bool(r.source_comment_id)),
        ("quality_score", lambda r: r.quality_score is not None),
        ("job_id", lambda r: bool(r.job_id)),
        ("industry", lambda r: r.industry is not None and str(r.industry).strip() != ""),
        ("category", lambda r: r.category is not None and str(r.category).strip() != ""),
        ("evidence_url", lambda r: bool(r.evidence_url)),
        ("extra_meta.crawl_query", lambda r: bool(r.extra_meta.get("crawl_query"))),
    ]
    out: list[FieldCoverageEntry] = []
    for name, pred in checks:
        n = sum(1 for r in reviews if pred(r))
        out.append(
            FieldCoverageEntry(
                field=name,
                present_ratio=n / total,
                non_empty_count=n,
                total=total,
            )
        )
    return out


def _sample_reviews(reviews: list[NormalizedReview], *, max_n: int = 5) -> list[SampleReviewSnippet]:
    out: list[SampleReviewSnippet] = []
    for r in reviews[:max_n]:
        text = (r.review_text or "").strip()
        if len(text) > 200:
            text = text[:200] + "…"
        out.append(
            SampleReviewSnippet(
                review_id=r.review_id,
                review_text=text,
                quality_score=r.quality_score,
                source_post_id=r.source_post_id,
                source_comment_id=r.source_comment_id,
            )
        )
    return out


def _build_checklist(
    *,
    summary_dict: dict[str, object],
    coverage: list[FieldCoverageEntry],
    db_raw_row_count: int,
    db_normalized_row_count: int,
) -> AcceptanceChecklist:
    """Runner 的 ``stored_*_count`` 仅统计**本次** ``INSERT`` 成功次数；同一批 ``event_id`` / ``review_id``
    再次运行会因 ``INSERT OR IGNORE`` 为 0，但库内仍应有行。用 ``db_*`` 与库内行数对账。
    """
    notes: list[str] = []
    posts = int(summary_dict.get("posts_selected", 0) or 0)
    fetched = int(summary_dict.get("fetched_count", 0) or 0)
    norm_n = int(summary_dict.get("normalized_count", 0) or 0)
    cleaned = int(summary_dict.get("cleaned_count", 0) or 0)
    stored_raw = int(summary_dict.get("stored_raw_count", 0) or 0)
    stored_norm = int(summary_dict.get("stored_normalized_count", 0) or 0)

    schema_ok = True
    for e in coverage:
        if e.field in ("review_id", "platform", "publish_time") and e.present_ratio < 0.9:
            schema_ok = False
            notes.append(f"schema: 核心字段 {e.field!r} 覆盖率 {e.present_ratio:.2f} 偏低")

    runner_ok = posts > 0 and fetched > 0
    if not runner_ok:
        notes.append("runner: 未选中帖子或未拉到评论，检查登录/搜索词/限流")

    cleaner_ok = True
    if norm_n > 0 and cleaned == 0:
        cleaner_ok = False
        notes.append("cleaner: 归一化有条但清洗后为空，检查 filters / min_len")

    store_ok = True
    if cleaned > 0:
        if stored_norm > 0:
            store_ok = True
        elif db_normalized_row_count >= cleaned:
            store_ok = True
            if stored_norm == 0:
                notes.append(
                    "info: normalized 本次 INSERT 为 0（主键重复，INSERT OR IGNORE），"
                    f"库内该 job 已有 {db_normalized_row_count} 行，属幂等重跑"
                )
        else:
            store_ok = False
            notes.append(
                "store: 清洗有条但库中仍无足够 normalized 行（或 job_id 未写入），检查 SQLite / 写入路径"
            )

    if norm_n > 0:
        if stored_raw == norm_n:
            pass
        elif db_raw_row_count >= norm_n:
            if stored_raw < norm_n:
                notes.append(
                    "info: raw 本次新增行数为 0（event_id 重复），"
                    f"库内该 job 已有 {db_raw_row_count} 条 raw 事件，属幂等重跑"
                )
        else:
            store_ok = False
            notes.append(
                f"store: 期望至少 {norm_n} 条 raw 事件，库内仅 {db_raw_row_count}，检查写入或去重键"
            )

    return AcceptanceChecklist(
        schema_ok=schema_ok,
        runner_ok=runner_ok,
        cleaner_ok=cleaner_ok,
        store_ok=store_ok,
        notes=notes,
    )


def _write_markdown(path: Path, report: XhsAcceptanceReport) -> None:
    lines = [
        "# 小红书第一轮架构验收摘要",
        "",
        f"- **job_id**: `{report.job_id}`",
        f"- **platform**: `{report.platform}`",
        f"- **query**: {report.query_summary}",
        "",
        "## 计数",
        "",
        f"| 指标 | 值 |",
        f"|------|-----|",
        f"| fetched_post_count | {report.fetched_post_count} |",
        f"| fetched_comment_count | {report.fetched_comment_count} |",
        f"| normalized_count | {report.normalized_count} |",
        f"| cleaned_count | {report.cleaned_count} |",
        f"| stored_raw_count | {report.stored_raw_count} |",
        f"| stored_normalized_count | {report.stored_normalized_count} |",
        f"| failed_count | {report.failed_count} |",
        f"| retry_count | {report.retry_count} |",
        f"| db_raw_row_count (SQLite) | {report.db_raw_row_count} |",
        f"| db_normalized_row_count (SQLite) | {report.db_normalized_row_count} |",
        "",
        "## 检查清单（第一轮架构是否成立）",
        "",
        f"- **schema / 归一化**: {'通过' if report.checklist.schema_ok else '待查'}",
        f"- **runner / 适配器**: {'通过' if report.checklist.runner_ok else '待查'}",
        f"- **cleaner**: {'通过' if report.checklist.cleaner_ok else '待查'}",
        f"- **store**: {'通过' if report.checklist.store_ok else '待查'}",
        "",
    ]
    if report.checklist.notes:
        lines.extend(["### 暴露的问题 / 线索", ""])
        for n in report.checklist.notes:
            lines.append(f"- {n}")
        lines.append("")
    lines.extend(
        [
            "## 核心字段覆盖率（归一化样本）",
            "",
            "| 字段 | 比例 | 非空/总数 |",
            "|------|------|-----------|",
        ]
    )
    for e in report.field_coverage:
        lines.append(f"| {e.field} | {e.present_ratio:.2f} | {e.non_empty_count}/{e.total} |")
    lines.extend(["", "## 样例评论（3~5 条）", ""])
    for s in report.sample_reviews:
        lines.append(f"- `{s.review_id}` score={s.quality_score} post={s.source_post_id}")
        lines.append(f"  > {s.review_text}")
    lines.extend(
        [
            "",
            "## 产出文件",
            "",
            f"- JSON: `{report.output_dir}/acceptance_report.json`",
            f"- DB: `{report.db_path}`",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


async def _run_async(
    *,
    job_id: str,
    db_path: Path,
    output_dir: Path,
    keyword: str | None,
    goto_timeout_ms: int,
    max_search_pages: int,
    max_posts: int,
    max_comments_per_post: int,
    max_comment_pages_per_post: int,
) -> None:
    job = build_acceptance_job(job_id=job_id, keyword=keyword)
    limits = CollectionRunLimits(
        max_search_pages=max_search_pages,
        max_posts=max_posts,
        max_comments_per_post=max_comments_per_post,
        max_comment_pages_per_post=max_comment_pages_per_post,
        enable_replies=False,
    )

    summary = await run_xhs_collection_with_browser(
        job=job,
        db_path=db_path,
        limits=limits,
        goto_timeout_ms=goto_timeout_ms,
    )
    summary_dict = summary.model_dump(mode="json")

    output_dir.mkdir(parents=True, exist_ok=True)
    reviews = _list_normalized_for_job(db_path, job.job_id)
    db_raw_n = _count_raw_events_for_job(db_path, job.job_id)
    db_norm_n = len(reviews)
    coverage = _field_coverage(reviews)
    checklist = _build_checklist(
        summary_dict=summary_dict,
        coverage=coverage,
        db_raw_row_count=db_raw_n,
        db_normalized_row_count=db_norm_n,
    )
    samples = _sample_reviews(reviews, max_n=5)

    report = XhsAcceptanceReport.from_job_and_summary(
        job=job,
        platform="xhs",
        query_summary=_query_summary(job),
        summary_dict=summary_dict,
        field_coverage=coverage,
        sample_reviews=samples,
        checklist=checklist,
        db_path=str(db_path.resolve()),
        output_dir=str(output_dir.resolve()),
        db_raw_row_count=db_raw_n,
        db_normalized_row_count=db_norm_n,
    )

    json_path = output_dir / "acceptance_report.json"
    json_path.write_text(
        report.model_dump_json(indent=2, exclude_none=True),
        encoding="utf-8",
    )
    md_path = output_dir / "acceptance_summary.md"
    _write_markdown(md_path, report)

    print(json.dumps(summary_dict, ensure_ascii=False, indent=2))
    print("", file=sys.stderr)
    print(
        f"[run_xhs_acceptance] 报告已写入: {json_path} 与 {md_path}",
        file=sys.stderr,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    p = argparse.ArgumentParser(
        description="小红书第一轮真实平台验收：CollectionJob + XHSAdapter + Runner + 报告 JSON/Markdown",
    )
    p.add_argument(
        "--job-id",
        default="job-xhs-acceptance-womens-sun-painpoint",
        help="作业 ID（与示例 CollectionJob 一致时可复现）",
    )
    p.add_argument(
        "--db-path",
        type=Path,
        default=Path("review_intel_data") / "xhs_acceptance" / "store.db",
        help="SQLite 路径",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path("review_intel_data") / "xhs_acceptance" / "last_run",
        help="acceptance_report.json / acceptance_summary.md 输出目录",
    )
    p.add_argument("--keyword", default=None, help="覆盖 QuerySpec.terms（空格分词）")
    p.add_argument(
        "--goto-timeout-ms",
        type=int,
        default=_DEFAULT_GOTO_TIMEOUT_MS,
        help="首页 Page.goto 超时（毫秒）",
    )
    p.add_argument("--max-search-pages", type=int, default=1)
    p.add_argument("--max-posts", type=int, default=3)
    p.add_argument("--max-comments-per-post", type=int, default=20)
    p.add_argument("--max-comment-pages-per-post", type=int, default=20)
    args = p.parse_args()

    asyncio.run(
        _run_async(
            job_id=args.job_id,
            db_path=args.db_path,
            output_dir=args.output_dir,
            keyword=args.keyword,
            goto_timeout_ms=args.goto_timeout_ms,
            max_search_pages=args.max_search_pages,
            max_posts=args.max_posts,
            max_comments_per_post=args.max_comments_per_post,
            max_comment_pages_per_post=args.max_comment_pages_per_post,
        )
    )


if __name__ == "__main__":
    main()
