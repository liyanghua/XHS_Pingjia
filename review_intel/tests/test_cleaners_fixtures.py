# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""cleaners 与 fixtures 联动：用 sample_comments.json 做可维护边界用例。"""

from __future__ import annotations

import json
from pathlib import Path

from review_intel.cleaners.filters import should_keep_review_text
from review_intel.cleaners.quality_score import compute_quality_score

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample_comments.json"


def _snippets() -> list[dict]:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return list(data["snippets"])


def test_fixture_snippets_filter_expectations() -> None:
    by_id = {s["id"]: s for s in _snippets()}
    assert should_keep_review_text(by_id["snip_empty"]["review_text"]) is False
    assert should_keep_review_text(by_id["snip_ok"]["review_text"], min_len=4) is True
    assert should_keep_review_text(by_id["snip_ad"]["review_text"]) is False


def test_fixture_ok_snippet_quality_score_range() -> None:
    by_id = {s["id"]: s for s in _snippets()}
    text = by_id["snip_ok"]["review_text"]
    q = compute_quality_score(text)
    assert 0.0 <= q <= 1.0
    assert q > 0.3
