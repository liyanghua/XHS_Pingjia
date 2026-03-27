# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""从 capture 目录读取 ``manifest.json`` + ``raw/events.jsonl``，归一化、清洗后写入 SQLite。

输出路径与 FastAPI 一致：``{REVIEW_INTEL_API_DATA}/{job_id}/store.db``（未设置环境变量时见
``capture_io.default_api_data_root``）。

运行示例::

    export REVIEW_INTEL_CAPTURE_ROOT=~/review_intel_capture
    python -m review_intel.jobs.ingest_capture --job-id job-xhs-001

打印抓取到的原始事件（与 ``events.jsonl`` 解析结果一致，入库前）::

    python -m review_intel.jobs.ingest_capture --job-id job-xhs-001 --print-captured
    python -m review_intel.jobs.ingest_capture --job-id job-xhs-001 --print-captured --print-captured-json --print-captured-limit 0

"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

from review_intel.adapters.xiaohongshu import XHSAdapter
from review_intel.cleaners.pipeline import clean_and_score_reviews
from review_intel.jobs.capture_io import default_api_data_root, default_capture_root, job_capture_dir
from review_intel.jobs.models import CollectionJob, QueryIntent, QuerySpec
from review_intel.jobs.runner import _apply_job_context, _query_from_job
from review_intel.schemas.raw_event import RawReviewEvent
from review_intel.storage.sqlite_support import open_review_intel_stores


logger = logging.getLogger(__name__)

# 单条事件控制台预览时正文最大长度
_PRINT_TEXT_MAX = 240


def _print_captured_event(index: int, ev: RawReviewEvent, *, as_json: bool) -> None:
    """将单条抓取事件打到 stdout（与入库读取一致）。"""
    if as_json:
        print(ev.model_dump_json(indent=2))
        print("---")
        return
    text = (ev.raw_text or "").replace("\n", " ").strip()
    if len(text) > _PRINT_TEXT_MAX:
        text = text[: _PRINT_TEXT_MAX] + "…"
    print(
        f"[ingest_capture] raw #{index} event_id={ev.event_id!r} "
        f"source_id={ev.source_id!r} parent_id={ev.parent_id!r} "
        f"platform={ev.platform.value} text={text!r}",
    )


def _collection_job_from_manifest(m: dict[str, object]) -> CollectionJob:
    job_id = str(m["job_id"])
    qs = m.get("query_spec")
    if not isinstance(qs, dict):
        qs = {}
    terms_raw = qs.get("terms")
    terms: list[str] = []
    if isinstance(terms_raw, list):
        terms = [str(t).strip() for t in terms_raw if str(t).strip()]
    if not terms:
        cq = str(m.get("crawl_query") or "").strip()
        terms = [t for t in cq.replace(",", " ").split() if t.strip()] or ["*"]

    spec = QuerySpec(
        industry=qs.get("industry") if isinstance(qs.get("industry"), str) else None,
        category=qs.get("category") if isinstance(qs.get("category"), str) else None,
        brand=None,
        intent=QueryIntent.TREND_SEARCH,
        terms=terms,
    )
    return CollectionJob(
        job_id=job_id,
        industry=spec.industry,
        category=spec.category,
        brand=None,
        query_spec=spec,
        target_types=["comment"],
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    p = argparse.ArgumentParser(description="从 capture 目录 ingest 到 SQLite（与 Runner 清洗链一致）")
    p.add_argument("--job-id", required=True, help="与 capture 目录名一致")
    p.add_argument(
        "--capture-root",
        type=Path,
        default=None,
        help="覆盖 REVIEW_INTEL_CAPTURE_ROOT",
    )
    p.add_argument(
        "--api-data-root",
        type=Path,
        default=None,
        help="覆盖 REVIEW_INTEL_API_DATA（store.db 父目录的根）",
    )
    p.add_argument(
        "--print-captured",
        action="store_true",
        help="将 events.jsonl 中解析到的每条 RawReviewEvent 打印到 stdout（入库前）",
    )
    p.add_argument(
        "--print-captured-json",
        action="store_true",
        help="与 --print-captured 联用：每条打印完整 JSON（多行），默认为一行摘要",
    )
    p.add_argument(
        "--print-captured-limit",
        type=int,
        default=50,
        metavar="N",
        help="仅打印前 N 条；0 表示不限制（与 --print-captured 联用，默认 50）",
    )
    args = p.parse_args()

    cap_root = Path(args.capture_root) if args.capture_root else default_capture_root()
    api_root = Path(args.api_data_root) if args.api_data_root else default_api_data_root()
    job_dir = job_capture_dir(cap_root, args.job_id)
    manifest_path = job_dir / "manifest.json"
    events_path = job_dir / "raw" / "events.jsonl"

    if not manifest_path.is_file():
        print(f"[ingest_capture] missing manifest: {manifest_path}", file=sys.stderr)
        raise SystemExit(2)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    job = _collection_job_from_manifest(manifest)

    if args.print_captured:
        print("[ingest_capture] manifest (摘要):", file=sys.stderr)
        print(
            json.dumps(
                {k: manifest.get(k) for k in ("job_id", "platform", "crawl_query", "status", "capture_finished_at")},
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        print(f"[ingest_capture] events.jsonl: {events_path}", file=sys.stderr)

    # normalize 仅需 industry/category；无需真实 HTTP 客户端
    qs = manifest.get("query_spec")
    ind = None
    cat = None
    if isinstance(qs, dict):
        ind = qs.get("industry") if isinstance(qs.get("industry"), str) else None
        cat = qs.get("category") if isinstance(qs.get("category"), str) else None
    adapter = XHSAdapter(
        MagicMock(),
        job_id=job.job_id,
        industry=ind,
        category=cat,
    )

    out_dir = api_root / args.job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    db_path = out_dir / "store.db"
    raw_store, norm_store = open_review_intel_stores(db_path)

    fetched = 0
    normalized_n = 0
    stored_raw = 0
    normalized_batch: list = []
    query = _query_from_job(job)

    if events_path.is_file():
        with events_path.open(encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = RawReviewEvent.model_validate_json(line)
                except Exception as e:  # noqa: BLE001
                    logger.warning("skip line %s: %s", line_no, e)
                    continue
                ev = ev.model_copy(update={"job_id": job.job_id})
                fetched += 1
                if args.print_captured:
                    lim = args.print_captured_limit
                    if lim == 0 or fetched <= lim:
                        _print_captured_event(
                            fetched,
                            ev,
                            as_json=args.print_captured_json,
                        )
                    elif fetched == lim + 1:
                        print(
                            f"[ingest_capture] … 已达 --print-captured-limit={lim}，后续不再打印",
                            file=sys.stderr,
                        )
                if raw_store.save(ev):
                    stored_raw += 1
                raw_dict = ev.model_dump(mode="json")
                norm = adapter.normalize_comment(raw_dict)
                norm = _apply_job_context(job, norm, query)
                normalized_n += 1
                normalized_batch.append(norm)
    else:
        logger.warning("no events.jsonl at %s", events_path)

    cleaned = clean_and_score_reviews(normalized_batch)
    cleaned_n = len(cleaned)
    stored_norm = 0
    for rev in cleaned:
        if norm_store.save(rev):
            stored_norm += 1

    logger.info(
        "ingest_capture done job_id=%s db=%s fetched=%s normalized=%s cleaned=%s "
        "stored_raw=%s stored_norm=%s",
        args.job_id,
        db_path,
        fetched,
        normalized_n,
        cleaned_n,
        stored_raw,
        stored_norm,
    )
    print(
        f"[ingest_capture] job_id={args.job_id} db={db_path} "
        f"fetched={fetched} normalized={normalized_n} cleaned={cleaned_n} "
        f"stored_raw={stored_raw} stored_norm={stored_norm}"
    )


if __name__ == "__main__":
    main()
