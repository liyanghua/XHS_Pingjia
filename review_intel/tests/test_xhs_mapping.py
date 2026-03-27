# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""xhs_mapping 纯函数单测（无网络）。"""

from __future__ import annotations

from review_intel.adapters.xhs_mapping import (
    build_search_page_from_api,
    normalize_xhs_comment_dict,
    normalize_xhs_post_dict,
    search_items_to_hit_dicts,
    xhs_comment_dict_to_raw_event,
    xhs_timestamp_to_utc,
)


def test_search_items_skips_hot_query() -> None:
    items = [
        {"model_type": "hot_query", "id": "x"},
        {"id": "n1", "xsec_token": "t1", "xsec_source": "pc_search", "title": "a"},
    ]
    out = search_items_to_hit_dicts(items)
    assert len(out) == 1
    assert out[0]["id"] == "n1"
    assert out[0]["xsec_token"] == "t1"


def test_build_search_page_next_cursor_when_has_more() -> None:
    sp = build_search_page_from_api(
        api_data={"items": [{"id": "a", "xsec_token": "", "xsec_source": "pc_search"}], "has_more": True},
        search_id="sid",
        page=1,
        job_id="j1",
    )
    assert sp.has_more is True
    assert sp.next_cursor is not None
    assert "page" in sp.next_cursor


def test_normalize_post_shape() -> None:
    d = normalize_xhs_post_dict(
        {"note_id": "nid", "title": "t", "user": {"user_id": "u"}, "interact_info": {"liked_count": 1}}
    )
    assert d["platform"] == "xhs"
    assert d["note_id"] == "nid"


def test_xhs_comment_to_raw_event() -> None:
    ev = xhs_comment_dict_to_raw_event(
        note_id="note1",
        comment={
            "id": "c1",
            "content": "hello",
            "create_time": 1700000000000,
            "user_info": {"user_id": "u1"},
        },
        job_id="job1",
    )
    assert ev.job_id == "job1"
    assert ev.parent_id == "note1"
    assert "hello" in ev.raw_text
    assert ev.extra_meta.get("note_id") == "note1"


def test_xhs_comment_to_raw_event_note_context() -> None:
    ev = xhs_comment_dict_to_raw_event(
        note_id="n1",
        comment={"id": "c1", "content": "x", "create_time": 1700000000000, "user_info": {}},
        job_id="j1",
        note_context={"note_title": "T", "note_type": "normal", "note_publish_time": "2025-01-01T00:00:00+00:00"},
    )
    assert ev.extra_meta["note_title"] == "T"
    assert ev.extra_meta["note_type"] == "normal"


def test_normalize_xhs_comment_dict_extra_meta() -> None:
    n = normalize_xhs_comment_dict(
        {
            "note_id": "note1",
            "id": "c1",
            "content": "hi",
            "create_time": 1700000000000,
            "user_info": {"nickname": "小红"},
            "like_count": 5,
            "sub_comment_count": 2,
        },
        raw_extra_meta={"note_title": "标题", "note_id": "note1"},
    )
    assert n.extra_meta.get("note_title") == "标题"
    assert n.extra_meta.get("user_name") == "小红"
    assert n.extra_meta.get("like_count") == 5
    assert n.extra_meta.get("reply_count") == 2
    assert n.extra_meta.get("comment_level") == 1


def test_iso_timestamp() -> None:
    dt = xhs_timestamp_to_utc("2025-01-01T00:00:00+00:00")
    assert dt.year == 2025
