# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""统一平台适配器抽象：搜索、详情、评论/回复抓取与归一化。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from review_intel.adapters.types import JsonObject, RateLimitPolicy
from review_intel.schemas.normalized import NormalizedReview
from review_intel.schemas.pages import CommentPage, SearchPage


class PlatformAdapter(ABC):
    """各内容平台接入评价情报管线的统一入口。

    **调用约定**

    - 所有 ``post_id`` / ``comment_id`` 均为**平台原生字符串 ID**，编码方式由实现解释。
    - ``cursor`` 与分页：首次请求传 ``None``；后续使用上一页 ``SearchPage`` / ``CommentPage``
      返回的 ``next_cursor`` 或 ``page_token``（实现可选用其一或两者，调用方应透传返回的游标）。
    - **幂等与线程安全**：网络抓取方法由实现自行处理重试；若适配器持有会话状态，并发行为
      以 ``rate_limit_policy().max_concurrency`` 为契约上限，多线程共享实例时需实现方保证安全。
    - **异步方法**在事件循环中执行；**同步方法**应为纯变换或只读元数据，避免阻塞过久。

    本类型不依赖 MediaCrawler 具体 ``media_platform`` 实现，仅约束输入输出 schema。
    """

    @abstractmethod
    async def search_posts(self, query: str, cursor: str | None = None) -> SearchPage:
        """按关键词搜索帖子/内容一页结果。

        Args:
            query: 搜索词或平台支持的查询表达式（由实现定义）。
            cursor: 上一页返回的游标；首页为 ``None``。

        Returns:
            ``SearchPage``，其中 ``items`` 为平台相关的 ``dict`` 列表。
        """

    @abstractmethod
    async def fetch_post_detail(self, post_id: str) -> JsonObject:
        """拉取单帖/单条内容的详情（原始结构化 dict，尚未归一化）。"""

    @abstractmethod
    async def fetch_comments(self, post_id: str, cursor: str | None = None) -> CommentPage:
        """拉取某帖子下评论一页；``items`` 为 ``RawReviewEvent`` 列表。"""

    @abstractmethod
    async def fetch_replies(self, comment_id: str, cursor: str | None = None) -> CommentPage:
        """拉取某条评论下的回复一页（结构与 ``fetch_comments`` 相同）。"""

    @abstractmethod
    def normalize_post(self, raw: JsonObject) -> JsonObject:
        """将平台帖子详情 dict 转为统一形状（当前为 dict，后续可替换为专用 schema）。"""

    @abstractmethod
    def normalize_comment(self, raw: JsonObject) -> NormalizedReview:
        """将平台评论原始 dict 转为 ``NormalizedReview``。"""

    @abstractmethod
    def rate_limit_policy(self) -> RateLimitPolicy:
        """返回本适配器建议的限流参数。"""

    @abstractmethod
    def adapter_name(self) -> str:
        """唯一可读名称，用于日志与注册表（如 ``xhs``、``dummy``）。"""
