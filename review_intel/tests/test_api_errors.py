# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""api：错误码与边界。"""

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


def test_get_job_with_invalid_job_id_returns_400(api_client: TestClient) -> None:
    r = api_client.get("/jobs/bad@id")
    assert r.status_code == 400
