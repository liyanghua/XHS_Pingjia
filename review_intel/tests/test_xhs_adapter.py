# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""XHSAdapter：Mock Client，不发起真实请求。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from review_intel.adapters.xiaohongshu import XHSAdapter


@pytest.mark.asyncio
async def test_search_posts_maps_and_caches_tokens() -> None:
    client = MagicMock()
    client.get_note_by_keyword = AsyncMock(
        return_value={
            "items": [
                {
                    "id": "nid1",
                    "xsec_token": "tok1",
                    "xsec_source": "pc_search",
                    "title": "t",
                }
            ],
            "has_more": False,
        }
    )
    ad = XHSAdapter(client, job_id="j1")
    sp = await ad.search_posts("keyword", None)
    assert len(sp.items) == 1
    assert sp.items[0]["id"] == "nid1"
    assert ad._note_sec["nid1"] == ("tok1", "pc_search")


@pytest.mark.asyncio
async def test_fetch_comments_uses_cached_token() -> None:
    client = MagicMock()
    client.get_note_by_keyword = AsyncMock(
        return_value={
            "items": [{"id": "n1", "xsec_token": "xt", "xsec_source": "pc_search"}],
            "has_more": False,
        }
    )
    client.get_note_comments = AsyncMock(
        return_value={"comments": [], "has_more": False, "cursor": ""}
    )
    ad = XHSAdapter(client, job_id="j1")
    await ad.search_posts("k", None)
    await ad.fetch_comments("n1", None)
    client.get_note_comments.assert_awaited_once()
    call_kw = client.get_note_comments.await_args
    assert call_kw.kwargs["xsec_token"] == "xt"


@pytest.mark.asyncio
async def test_fetch_replies_not_implemented() -> None:
    client = MagicMock()
    ad = XHSAdapter(client, job_id="j1")
    with pytest.raises(NotImplementedError):
        await ad.fetch_replies("c1", None)
