# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""review_intel FastAPI 最小接口测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("REVIEW_INTEL_API_DATA", str(tmp_path))
    from review_intel.api.app import create_app

    with TestClient(create_app()) as client:
        yield client


def test_post_job_without_execute(api_client: TestClient) -> None:
    r = api_client.post(
        "/jobs",
        json={
            "query_spec": {
                "intent": "painpoint_search",
                "terms": ["闷热"],
                "platforms": ["xhs"],
            },
            "execute": False,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "1"
    assert body["executed"] is False
    assert body["job"]["job_id"]
    assert body["summary"] is None
    jid = body["job"]["job_id"]

    g = api_client.get(f"/jobs/{jid}")
    assert g.status_code == 200
    assert g.json()["job"]["job_id"] == jid

    s = api_client.get(f"/jobs/{jid}/summary")
    assert s.status_code == 404

    rev = api_client.get(f"/jobs/{jid}/reviews")
    assert rev.status_code == 200
    assert rev.json()["total"] == 0


def test_post_job_execute_and_fetch_reviews(api_client: TestClient) -> None:
    r = api_client.post(
        "/jobs",
        json={
            "job_id": "api-test-job-001",
            "query_spec": {
                "intent": "painpoint_search",
                "terms": ["闷热"],
                "platforms": ["xhs"],
            },
            "execute": True,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["executed"] is True
    assert body["error"] is None
    assert body["summary"]["fetched_count"] == 2
    jid = body["job"]["job_id"]

    s = api_client.get(f"/jobs/{jid}/summary")
    assert s.status_code == 200
    assert s.json()["summary"]["cleaned_count"] == 1

    rev = api_client.get(f"/jobs/{jid}/reviews")
    assert rev.status_code == 200
    rj = rev.json()
    assert rj["total"] == 1
    assert len(rj["items"]) == 1


def test_get_unknown_job(api_client: TestClient) -> None:
    r = api_client.get("/jobs/does-not-exist")
    assert r.status_code == 404


def test_get_api_search_requires_q(api_client: TestClient) -> None:
    r = api_client.get("/api/search", params={"q": ""})
    assert r.status_code == 400


def test_get_api_search_hits_normalized_text(api_client: TestClient) -> None:
    """先有入库数据，再按正文子串检索。"""
    api_client.post(
        "/jobs",
        json={
            "job_id": "search-cache-001",
            "query_spec": {
                "intent": "painpoint_search",
                "terms": ["闷热"],
                "platforms": ["xhs"],
            },
            "execute": True,
        },
    )
    r = api_client.get("/api/search", params={"q": "示例归一化"})
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "1"
    assert body["total"] >= 1
    assert body["items"][0]["provenance"] == "cache"
    assert body["items"][0]["job_id"] == "search-cache-001"


def test_post_api_search_run_merge(api_client: TestClient) -> None:
    """库内 + 本次 Runner 合并（Dummy）。"""
    api_client.post(
        "/jobs",
        json={
            "job_id": "pre-existing-job",
            "query_spec": {
                "intent": "painpoint_search",
                "terms": ["闷热"],
                "platforms": ["xhs"],
            },
            "execute": True,
        },
    )
    r = api_client.post("/api/search/run", json={"keyword": "闷热"})
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "1"
    assert body["error"] is None
    assert body["job_id"]
    assert body["summary"] is not None
    assert body["cache_hits"] >= 1
    assert body["live_hits"] >= 1
    assert body["total"] >= 1
    prov = {it["provenance"] for it in body["items"]}
    assert "cache" in prov or "live" in prov
