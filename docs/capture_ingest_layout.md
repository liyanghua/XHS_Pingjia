# 抓取与落库分离：目录结构与设计约定

本文档描述 **两阶段** 流水线，与「Runner 内联写 SQLite」解耦：

1. **Capture（抓取）**：只负责浏览器会话、平台 API、将**原始可回放数据**写入约定目录（不依赖最终库表细节）。
2. **Ingest（入库）**：读取目录中的文件，映射为 `RawReviewEvent` / `NormalizedReview`，再写入 SQLite（或后续其他存储），**可重复执行、可换库表实现**。

## 设计动机

- **解耦**：网络抖动、登录、风控与 DB 事务分离；抓取失败不污染库。
- **可审计**：保留平台原始 JSON，便于对照 schema 与接口变更。
- **可重放**：同一目录可多次跑 ingest（例如清洗规则升级后重算 normalized）。
- **与现有代码对齐**：`RawReviewEvent` / `NormalizedReview` 仍是领域边界；ingest 即当前 `adapter.normalize_*` + `clean_and_score_reviews` 的逻辑，只是输入从「内存」改为「目录中的文件」。

## 推荐根目录与环境变量

- 根目录：由环境变量 **`REVIEW_INTEL_CAPTURE_ROOT`**（或配置项）指定，例如 `~/review_intel_data/capture`。**未设置**时，实现上默认为仓库工作目录下的 `review_intel_capture/`（见 `review_intel/jobs/capture_io.default_capture_root`）。
- 与 API 用 **`REVIEW_INTEL_API_DATA`** 下的 `{job_id}/store.db` **并列**：capture 管「原始文件」，ingest 产出「最终库」。**未设置**时默认同目录约定为工作目录下的 `review_intel_data/`（见 `default_api_data_root`）。
- 上述默认目录已列入仓库根 `.gitignore`，避免误提交含 token 的原始 JSON。

```text
{REVIEW_INTEL_CAPTURE_ROOT}/
  {job_id}/                      # 与 CollectionJob.job_id 一致，便于关联
    manifest.json               # 作业元数据（见下）
    raw/                        # 原始抓取物（机器可读，非最终业务库）
      search/                   # 搜索相关
        page_001.json           # get_note_by_keyword 单页完整响应（或分页序列）
      notes/                    # 按笔记维度
        {note_id}/
          detail.json           # 可选：详情 /feed 或 HTML 回退摘要
          comments/             # 评论分页
            cursor_000.json     # get_note_comments 当页完整响应
            cursor_001.json
      events.jsonl              # 可选：已解析的 RawReviewEvent 一行一个 JSON（便于快速 ingest）
    ingest_state.json           # 可选：ingest 进度、checksum，支持断点
```

## manifest.json（建议字段）

| 字段 | 说明 |
|------|------|
| `job_id` | 与目录名一致 |
| `platform` | 如 `xhs` |
| `query_spec` / `crawl_query` | 与 `CollectionJob` 一致或可序列化子集 |
| `adapter_version` / `schema_version` | 便于 ingest 迁移 |
| `capture_started_at` / `capture_finished_at` | ISO8601 UTC |
| `status` | `running` / `succeeded` / `failed` |
| `error` | 最后一次失败信息（可选） |

## 文件内容约定

- **`*.json`**：平台 API **原样**（或脱敏后的）响应体，便于 diff 与回归。
- **`events.jsonl`**：每行一个 **`RawReviewEvent.model_dump(mode="json")`**，与 [`review_intel/schemas/raw_event.py`](../review_intel/schemas/raw_event.py) 一致；ingest 首选读此文件，若无则自 `comments/*.json` 再解析（成本更高）。

## Ingest 阶段（第二阶段）

- **输入**：`{job_id}/` 下 `manifest.json` + `raw/events.jsonl`（及/或 `raw/notes/**`）。
- **处理**：逐行 → `RawReviewEvent` → `normalize_comment` / 上下文补全 → `clean_and_score_reviews` → `SqliteNormalizedReviewStore` / raw 表（与现 [`runner`](../review_intel/jobs/runner.py) 对齐）。
- **输出**：与现有一致：`{REVIEW_INTEL_API_DATA}/{job_id}/store.db`，或 ingest 专用 `ingest_output/{job_id}/store.db`（由产品决定，建议在文档中固定一种）。

## 与现有脚本的关系

| 组件 | 角色 |
|------|------|
| `python -m review_intel.jobs.xhs_capture` | 仅写 `{REVIEW_INTEL_CAPTURE_ROOT}/{job_id}/...`，不写 `store.db` |
| `python -m review_intel.jobs.ingest_capture` | 读目录 → SQLite（`{REVIEW_INTEL_API_DATA}/{job_id}/store.db`） |
| `review_intel.adapters.xhs_demo` | 验收脚本：内存闭环打印，可选与 capture 对照 |
| `ReviewCollectionRunner` | 可保留为「内存一站式」；ingest 复用其归一化 + `clean_and_score_reviews` 链 |

## 实现顺序建议

1. 定义 **manifest + events.jsonl** 最小集，在 `xhs_demo` 或新 CLI 中先写出目录。
2. 实现 **ingest 命令**：读 `events.jsonl` → 现有清洗与 `open_review_intel_stores`。
3. 再视需要把「仅 JSON 快照、无 events.jsonl」的解析补进 ingest。

## 注意事项

- **隐私与体积**：原始 JSON 可能含 token；`.gitignore` 应对 `{REVIEW_INTEL_CAPTURE_ROOT}` 默认忽略或提供 `sanitize` 选项。
- **幂等**：ingest 使用 `INSERT OR IGNORE`（与现 raw/norm 一致）时，重复跑可能跳过；需在 manifest 或 `ingest_state` 中记录已处理偏移。
