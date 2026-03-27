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
from review_intel.cleaners.quality_score import QUALITY_FLOOR_SHORT_HIT, compute_quality_score
from review_intel.cleaners.term_lists import default_high_value_short_terms

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


def test_fixture_high_value_short_with_terms() -> None:
    by_id = {s["id"]: s for s in _snippets()}
    text = by_id["snip_high_value_short"]["review_text"]
    hv = default_high_value_short_terms()
    assert should_keep_review_text(text, min_len=4, high_value_short_terms=hv) is True
    q = compute_quality_score(text, high_value_short_terms=hv)
    assert q >= QUALITY_FLOOR_SHORT_HIT
