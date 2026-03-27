# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""CollectionJob / QuerySpec 序列化与工厂测试。"""

from __future__ import annotations

import json

from review_intel.jobs.models import (
    CollectionJob,
    QueryIntent,
    QuerySpec,
    create_job_from_dict,
    example_job_beauty_dupes_competitor,
    example_job_home_storage_need,
    example_job_womens_sun_protection_painpoint,
)
from review_intel.schemas.enums import JobStatus, PlatformType


def test_query_spec_json_roundtrip() -> None:
    spec = QuerySpec(
        intent=QueryIntent.TREND_SEARCH,
        terms=["a"],
        platforms=[PlatformType.UNKNOWN],
    )
    data = spec.model_dump(mode="json")
    back = QuerySpec.model_validate(data)
    assert back.intent == QueryIntent.TREND_SEARCH


def test_collection_job_json_roundtrip() -> None:
    job = example_job_womens_sun_protection_painpoint()
    data = job.model_dump(mode="json")
    back = CollectionJob.model_validate(data)
    assert back.job_id == job.job_id
    assert back.query_spec.intent == QueryIntent.PAINPOINT_SEARCH
    json.dumps(data)


def test_create_job_from_dict() -> None:
    job = example_job_home_storage_need()
    d = job.model_dump(mode="json")
    restored = create_job_from_dict(d)
    assert restored.job_id == job.job_id
    assert restored.query_spec.terms == job.query_spec.terms


def test_three_examples() -> None:
    a = example_job_womens_sun_protection_painpoint()
    b = example_job_home_storage_need()
    c = example_job_beauty_dupes_competitor()
    assert a.query_spec.intent == QueryIntent.PAINPOINT_SEARCH
    assert b.query_spec.intent == QueryIntent.NEED_SEARCH
    assert c.query_spec.intent == QueryIntent.COMPETITOR_SEARCH
    assert a.status == JobStatus.PENDING
