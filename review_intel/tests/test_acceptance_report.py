# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

from __future__ import annotations

from review_intel.jobs.acceptance_report import AcceptanceChecklist, FieldCoverageEntry, XhsAcceptanceReport
from review_intel.jobs.models import example_job_xhs_acceptance_womens_sun_painpoint
from review_intel.jobs.run_xhs_acceptance import _build_checklist


def test_xhs_acceptance_report_serializes() -> None:
    job = example_job_xhs_acceptance_womens_sun_painpoint()
    summary_dict = {
        "posts_selected": 2,
        "fetched_count": 5,
        "normalized_count": 5,
        "cleaned_count": 4,
        "stored_raw_count": 5,
        "stored_normalized_count": 4,
        "failed_count": 0,
        "retry_count": 1,
    }
    r = XhsAcceptanceReport.from_job_and_summary(
        job=job,
        platform="xhs",
        query_summary="test",
        summary_dict=summary_dict,
        field_coverage=[
            FieldCoverageEntry(field="review_id", present_ratio=1.0, non_empty_count=1, total=1)
        ],
        sample_reviews=[],
        checklist=AcceptanceChecklist(schema_ok=True, runner_ok=True, cleaner_ok=True, store_ok=True),
        db_path="/tmp/x.db",
        output_dir="/tmp/out",
        db_raw_row_count=5,
        db_normalized_row_count=4,
    )
    js = r.model_dump_json()
    assert "job-xhs-acceptance" in js
    assert "retry_count" in js


def test_checklist_idempotent_rerun_not_store_failure() -> None:
    """重复 run：stored_* 为 0 但库内已有行，不应判 store 失败。"""
    summary = {
        "posts_selected": 3,
        "fetched_count": 21,
        "normalized_count": 21,
        "cleaned_count": 21,
        "stored_raw_count": 0,
        "stored_normalized_count": 0,
    }
    cl = _build_checklist(
        summary_dict=summary,
        coverage=[
            FieldCoverageEntry(field="review_id", present_ratio=1.0, non_empty_count=21, total=21)
        ],
        db_raw_row_count=21,
        db_normalized_row_count=21,
    )
    assert cl.store_ok is True
    assert any("幂等" in n or "info:" in n for n in cl.notes)
