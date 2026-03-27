# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""fixtures 与 schemas 契约：样例 JSON 可被解析并用于边界断言。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from review_intel.schemas.examples import example_raw_review_event
from review_intel.schemas.raw_event import RawReviewEvent

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def sample_comments() -> dict:
    path = _FIXTURE_DIR / "sample_comments.json"
    assert path.is_file(), f"missing fixture: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def test_fixture_sample_comments_json_version(sample_comments: dict) -> None:
    assert sample_comments.get("version") == "1"
    assert isinstance(sample_comments.get("snippets"), list)
    assert len(sample_comments["snippets"]) >= 3


def test_fixture_snippet_ids_unique(sample_comments: dict) -> None:
    ids = [s["id"] for s in sample_comments["snippets"]]
    assert len(ids) == len(set(ids))


def test_raw_event_merge_with_fixture_overrides(sample_comments: dict) -> None:
    base = example_raw_review_event()
    ov = sample_comments["raw_event_overrides"]
    merged = base.model_copy(
        update={
            "source_id": ov["comment_id"],
            "parent_id": ov["parent_id"],
            "raw_text": sample_comments["snippets"][2]["review_text"],
        }
    )
    assert isinstance(merged, RawReviewEvent)
    assert merged.source_id == "fixture-comment-001"
    assert "闷热" in merged.raw_text
