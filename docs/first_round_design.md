# review_intel 第一轮设计说明

面向后续开发者与 AI 工具：说明本子系统在 MediaCrawler 仓库内的**目标、边界、模块分工与已知限制**，便于接力演进与代码评审。

## 1. 系统目标

- 在**不替换**现有爬虫主流程的前提下，为「评论 / 评价」情报建立**可扩展**子系统：统一领域模型、采集编排、清洗、存储与调试 API。
- 优先保证**契约清晰**（Pydantic / Protocol）、**单机可跑通**（DummyAdapter + SQLite）、**可测试**，而非一上来做完整分布式或全平台接入。

## 2. 当前范围（第一轮）

| 已具备 | 未纳入 |
|--------|--------|
| 领域模型：`RawReviewEvent`、`NormalizedReview`、`SearchPage`/`CommentPage` | 真实平台 OAuth、反爬对抗 |
| 作业模型：`CollectionJob`、`QuerySpec`、`QueryIntent` | 生产级任务队列 / 多租户权限 |
| 适配器抽象 + `DummyAdapter` + 小红书 `XHSAdapter`（复用 `media_platform.xhs`） | 各平台真实 `PlatformAdapter` 全覆盖 |
| SQLite 存储（raw / normalized）+ 幂等写入 | PostgreSQL / 分库分表 |
| cleaners：规则过滤、精确去重、简单质量分 | Embedding / LLM 清洗 |
| `ReviewCollectionRunner` 顺序闭环 + checkpoint + 重试 | 并发抓取、分页拉全量 |
| FastAPI 调试接口（创建作业、查摘要、查评价） | 与顶层 `api/` 自动挂载、网关鉴权 |

## 3. 模块职责

| 路径 | 职责 |
|------|------|
| `review_intel/schemas/` | 枚举与分层模型；`examples.py` 为测试/文档统一样例入口。 |
| `review_intel/jobs/` | `CollectionJob` 等作业模型；`runner` 编排采集；`checkpoint` 断点；`scheduler` 薄封装。 |
| `review_intel/adapters/` | `PlatformAdapter` 契约与 `DummyAdapter`。 |
| `review_intel/storage/` | `RawReviewRepository` / `NormalizedReviewRepository` 协议与 SQLite 实现。 |
| `review_intel/cleaners/` | `filters` / `dedup` / `quality_score` / `pipeline.clean_and_score_reviews`。 |
| `review_intel/api/` | 最小 FastAPI 应用，同步执行 Dummy 闭环，便于本地调试。 |
| `review_intel/tests/` | 子系统测试；`tests/fixtures/` 存放可版本化的样例 JSON。 |

## 4. 已知限制

- **数据**：`NormalizedReview` 含可选 `job_id` 与 `extra_meta`（Runner 写入 `job_id`、检索词 `crawl_query`；平台特有字段先入 `extra_meta`）。API 仍按「每作业独立 SQLite 文件」隔离列表；单条记录自带 `job_id` 便于导出合并与对账。
- **Runner**：默认仅搜索首页 + 每帖评论首页；完整分页与断点恢复的组合策略仍偏薄。
- **API**：无鉴权；进程内 `JobRegistry`，重启后作业元数据丢失（磁盘上 SQLite 仍在 `REVIEW_INTEL_API_DATA` 下，但注册表需重建或后续持久化）。
- **文档**：`README_review_intel.md` 为子系统总览；本文件为第一轮设计快照。

### 4.1 `job_id` 与 `extra_meta`（为何这样设计）

- **`job_id` 写在 `NormalizedReview` 上**：归一化行常被导出、合并或脱离「按库路径推断作业」的环境使用；与 `RawReviewEvent.job_id`、`CollectionRunSummary.job_id` 对齐后，可按任务直接回溯，而不依赖外部存储约定。
- **`extra_meta` 而非一次性扩很多顶层字段**：首轮各平台字段仍在演变，顶层保留跨平台稳定语义（主键、时间、正文、来源 ID、链接等）；易变或平台特有的键（如小红书笔记标题、点赞数快照）放入 `extra_meta`，减少 schema 频繁改版与大量可空顶层列，同时仍保证 JSON 存储与 API 可序列化。

**SQLite**：`normalized_reviews` / `raw_review_events` 仍以 `payload_json` 存全模型；新增字段由 Pydantic 默认值兼容旧行，无需 `ALTER TABLE`（若未来需按 `job_id` SQL 索引再考虑加列与版本迁移）。

## 5. 下一轮建议（优先级从高到低）

1. 实现至少一个真实平台 `PlatformAdapter`（可先接现有爬虫回调或中间存储）。
2. Runner：可配置分页深度、与 `CollectionJob.checkpoint` 字段对齐持久化。
3. 单库多作业：若需 SQL 级按 `job_id` 过滤，可为 `normalized_reviews` 增加索引列并 bump `schema_version`。
4. API：作业列表、异步任务队列、或将路由挂到顶层 `api/` 并加简单 Token。
5. cleaners：近重复去重接口实现、可配置词表与语言范围。

## 6. 相关文件

- 命令与 Makefile：仓库根目录 [`Makefile`](Makefile)（`review-intel-*` 目标）。
- 第一轮完成清单：[`review_intel/ROUND1_CHECKLIST.md`](../review_intel/ROUND1_CHECKLIST.md)。
- 子系统 README：[`README_review_intel.md`](../README_review_intel.md)。
