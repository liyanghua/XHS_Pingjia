# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""子包与顶层符号可导入性冒烟测试。"""

from __future__ import annotations


def test_import_subpackages() -> None:
    """各子目录包应可独立导入。"""
    import review_intel.adapters  # noqa: F401
    import review_intel.api  # noqa: F401
    import review_intel.cleaners  # noqa: F401
    import review_intel.jobs  # noqa: F401
    import review_intel.outputs  # noqa: F401
    import review_intel.schemas  # noqa: F401
    import review_intel.storage  # noqa: F401


def test_public_api_symbols() -> None:
    """根 `review_intel` 聚合导出保持不变。"""
    import review_intel as ri

    assert ri.ReviewIntelRecord is not None
    assert ri.ReviewIntelTask is not None
    assert ri.ReviewIntelStore is not None
    assert ri.TaskStatus is not None
