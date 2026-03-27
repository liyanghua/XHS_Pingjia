# review_intel：评价情报子系统

在 **MediaCrawler** 仓库内并行扩展的「评价情报」底座：在**不替换**现有 `media_platform`、`store` 与 `main.py` 主流程的前提下，提供评论/评价的采集抽象、归一化、存储与调试 API；本 fork 额外强化了 **小红书会话与验收路径**（见下文「小红书优化」）。

## 目标

- 将多平台评论映射为统一领域模型（`RawReviewEvent`、`NormalizedReview` 等），便于检索与后续加工。
- 通过 **适配器** 与 `media_platform` 松耦合；核心以 **schema、任务模型、Protocol** 为主。

## 小红书优化（本仓库增量）

| 位置 | 说明 |
|------|------|
| `media_platform/xhs/client.py` | `pong()`：`selfinfo` 多形态 JSON 解析；非明确登出时可用 `web_session` 辅助，减少误判。 |
| `review_intel/adapters/xhs_demo.py` | 单次软同步；扫码后 **稳定会话 + 重试 `pong()`**；必要时 **浏览器探测已登录** 后继续抓取。 |
| `config/base_config.py` | `browser_persistent_data_dirname()`、`DEBUG_XHS_SELFINFO`（或环境变量 `XHS_DEBUG_SELFINFO=1`）、默认 `ENABLE_CDP_MODE=False` 等。 |
| `review_intel/adapters/README_XHS.md` | **排障与运行说明**（必读本目录下该文件）。 |

## 第一轮设计文档

| 文档 | 说明 |
|------|------|
| [docs/first_round_design.md](docs/first_round_design.md) | 目标、范围、模块、限制 |
| [review_intel/ROUND1_CHECKLIST.md](review_intel/ROUND1_CHECKLIST.md) | 第一轮清单 |
| [docs/capture_ingest_layout.md](docs/capture_ingest_layout.md) | **抓取与落库解耦**：`REVIEW_INTEL_CAPTURE_ROOT` 目录约定、`manifest` + `events.jsonl`、与 `ingest` 两阶段流水线 |

## 常用命令（Makefile）

在**仓库根目录**（需已安装依赖与虚拟环境）：

```bash
make review-intel-test               # 子系统全部测试
make review-intel-api                # FastAPI，默认 http://127.0.0.1:8090
make review-intel-demo               # Dummy 采集闭环摘要
make review-intel-keyword-pipeline   # 关键词 → Runner → SQLite（Dummy）
make review-intel-xhs-demo           # 小红书真实验收（需登录，见 adapters/README_XHS.md）
make review-intel-xhs-capture        # 小红书：仅落盘 capture（manifest + raw/events.jsonl），不写库
make review-intel-ingest-capture JOB_ID=<job_id>   # 从 capture 目录 ingest → REVIEW_INTEL_API_DATA/<job_id>/store.db
```

环境变量（可选，未设置时使用仓库工作目录下的默认路径，见 [`review_intel/jobs/capture_io.py`](review_intel/jobs/capture_io.py)）：

- **`REVIEW_INTEL_CAPTURE_ROOT`**：抓取输出根目录（默认 `./review_intel_capture/`）。
- **`REVIEW_INTEL_API_DATA`**：API / ingest 使用的数据根目录（默认 `./review_intel_data/`，与 FastAPI 一致）。

本地抓取目录通常含 Cookie/原始 JSON，已在根目录 [`.gitignore`](.gitignore) 中忽略 `review_intel_capture/` 与 `review_intel_data/`。

等价命令示例：

```bash
python -m pytest review_intel/tests/ -q
python -m uvicorn review_intel.api.app:app --reload --host 127.0.0.1 --port 8090
python -m review_intel.jobs.keyword_pipeline_demo --keyword "防晒 搓泥"
python -m review_intel.adapters.xhs_demo --keyword 防晒 --max-notes 2 --max-comments 3
python -m review_intel.jobs.xhs_capture --keyword 防晒 --job-id job-xhs-001
python -m review_intel.jobs.ingest_capture --job-id job-xhs-001
```

## 测试与「该跑哪个」

| 目的 | 位置 |
|------|------|
| 自动化断言（Dummy 闭环） | `review_intel/tests/test_runner.py` |
| 人工看入库 JSON / 关键词管线 | `python -m review_intel.jobs.keyword_pipeline_demo` |
| 仅摘要 | `python review_intel/jobs/runner.py` |
| **真实小红书**（内存归一化打印） | `python -m review_intel.adapters.xhs_demo` |

## 领域模型与模块（概要）

- **schemas/**：`RawReviewEvent`、`NormalizedReview`、`SearchPage`、`CommentPage`、枚举与 `examples.py`。
- **jobs/**：`ReviewCollectionRunner`、`CollectionJob`、`runner` / `checkpoint` / `scheduler`。
- **storage/**：SQLite 实现 `SqliteRawReviewStore`、`SqliteNormalizedReviewStore`。
- **adapters/**：`DummyAdapter`、`XHSAdapter`（依赖 `media_platform.xhs`）。
- **cleaners/**：过滤、去重、质量分。
- **api/**：FastAPI 调试服务，见 [review_intel/api/README.md](review_intel/api/README.md)。
- **frontend/**：Vite + React + TS，见 [review_intel/frontend/README.md](review_intel/frontend/README.md)。

## 前端联调（关键词检索 UI）

1. 启动 API：`make review-intel-api`。
2. `cd review_intel/frontend && npm install && npm run dev`（默认通过代理连 `8090`，见 `vite.config.ts` / `.env.development`）。

## 与现有代码的边界

- 顶层 `api/`：原爬虫管理；`review_intel/api/` 为独立应用，可按需合并路由。
- `media_platform/*`：保持可增量对接；XHS 会话逻辑在 `client.py` / `xhs_demo` 的改动仅影响调用方行为，不改变平台包对外职责划分。

## 验证

```bash
make review-intel-test
# 或
python -m pytest review_intel/tests/ -q
```

## 已知限制

- 仍以 [docs/first_round_design.md](docs/first_round_design.md) 与测试为准；`XHSAdapter.fetch_replies` 等可能未实现，见适配器代码与 `ROUND1_CHECKLIST.md`。
