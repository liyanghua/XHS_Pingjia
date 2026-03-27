# review_intel：评价情报子系统

本目录与文档描述在 **MediaCrawler** 仓库内 **并行扩展** 的「评价情报」底座：在**不替换**现有 `media_platform`、`store` 与 `main.py` 爬虫主流程的前提下，逐步接入评论/评价的采集、归一化、存储与调试 API。

## 目标

- 将多平台评论与评价数据映射为统一的领域模型（`RawReviewEvent`、`NormalizedReview` 等），便于检索、分析与后续情报加工。
- 通过 **适配器（adapters）** 与现有爬虫实现松耦合集成；核心逻辑以 **schema、任务模型、协议（Protocol）** 为主，避免过早绑定具体存储或 HTTP 框架。

## 第一轮文档（接手必读）

| 文档 | 说明 |
|------|------|
| [docs/first_round_design.md](docs/first_round_design.md) | 系统目标、范围、模块职责、已知限制、下一轮建议 |
| [review_intel/ROUND1_CHECKLIST.md](review_intel/ROUND1_CHECKLIST.md) | 第一轮完成清单与自检项 |
| [review_intel/api/README.md](review_intel/api/README.md) | 调试 API 启动与 curl 示例 |

## 常用命令（Makefile）

在项目根目录执行（需已安装依赖，建议使用虚拟环境）：

```bash
make review-intel-test    # 运行子系统全部测试
make review-intel-api     # 启动 FastAPI（默认 http://127.0.0.1:8090）
make review-intel-demo    # 同步跑 Dummy 采集闭环并打印摘要
make review-intel-keyword-pipeline  # 关键词→Runner→清洗→SQLite→打印入库 JSON（Dummy）
make review-intel-xhs-demo  # 小红书真实验收（需登录，见 adapters/README_XHS.md）
```

等价命令：

```bash
python -m pytest review_intel/tests/ -q
python -m uvicorn review_intel.api.app:app --reload --host 127.0.0.1 --port 8090
python review_intel/jobs/runner.py
python -m review_intel.jobs.keyword_pipeline_demo --keyword "防晒 搓泥"
```

## 测试与样例数据

- 测试目录：`review_intel/tests/`
- 可维护样例：`review_intel/tests/fixtures/`（如 `sample_comments.json`，供 cleaners / schema 边界用例）

### 想「看完整链路」时该用哪个？

| 目的 | 位置 |
|------|------|
| **自动化断言**（同一套 Dummy 闭环，不打印明细） | `review_intel/tests/test_runner.py`（`ReviewCollectionRunner` + `DummyAdapter` + 临时 DB） |
| **人工核对入库 JSON**（关键词、`crawl_query`、`extra_meta`、质量分等） | `python -m review_intel.jobs.keyword_pipeline_demo` 或 `make review-intel-keyword-pipeline` |
| **仅打印「摘要」**（无逐条入库内容） | `python review_intel/jobs/runner.py` / `make review-intel-demo` |
| **真实小红书网络**（不经过 Runner/SQLite，只打印内存里归一化结果） | `python -m review_intel.adapters.xhs_demo --keyword …`（见 `adapters/README_XHS.md`） |

若需要「真实抓取 + 同一套 Runner 落库」，可在本地用 `XHSAdapter` 注入 `ReviewCollectionRunner` 自建脚本；仓库内默认以 **Dummy** 保证 CI 可重复、**xhs_demo** 保证可连网验收。

## 领域分层模型（`schemas/`）

- **枚举**：`PlatformType`、`ContentType`、`JobStatus`（[`review_intel/schemas/enums.py`](review_intel/schemas/enums.py)）。`JobStatus` 与 `jobs` 中的 `TaskStatus` 为同一枚举，避免两套状态漂移。
- **原始层**：`RawReviewEvent` — 单次抓取解析后的平台中立事件（[`raw_event.py`](review_intel/schemas/raw_event.py)）。
- **标准层**：`NormalizedReview` — 归一化后可供检索/打分的记录（[`normalized.py`](review_intel/schemas/normalized.py)）。
- **分页**：`SearchPage`（条目为 `dict` 占位）、`CommentPage`（条目为 `RawReviewEvent`）（[`pages.py`](review_intel/schemas/pages.py)）。
- **遗留最小模型**：`ReviewIntelRecord` / `ReviewIntelBatch` / `ReviewIntelKey`（[`models.py`](review_intel/schemas/models.py)），与新模型并行，后续可映射或收敛。
- **样例工厂**：[`examples.py`](review_intel/schemas/examples.py) 中 `example_*()`，测试与文档示例请统一从这里引用。

## 模块职责

| 路径 | 职责 |
|------|------|
| `review_intel/schemas/` | Pydantic 模型与枚举：分层领域模型、遗留 `ReviewIntel*`、样例工厂等。 |
| `review_intel/jobs/` | 流水线任务（`ReviewIntelTask`）与 **评价情报采集作业**（`CollectionJob`、`QuerySpec`、`QueryIntent`）；`runner` / `checkpoint` / `scheduler`。 |
| `review_intel/storage/` | 协议与 SQLite 实现：`SqliteRawReviewStore`、`SqliteNormalizedReviewStore`、`open_review_intel_stores`。 |
| `review_intel/adapters/` | 各平台原始数据 → 领域模型的适配；`DummyAdapter` 联调；`XHSAdapter` 复用 `media_platform.xhs`（见 `adapters/README_XHS.md`）。 |
| `review_intel/cleaners/` | 规则过滤、精确去重、质量分与 `clean_and_score_reviews`。 |
| `review_intel/api/` | 子系统 **FastAPI 调试服务**（见 `api/README.md`）；默认不自动挂到顶层 `api/`。 |
| `review_intel/frontend/` | 独立 **Vite + React + TS** 前端：关键词「仅查库 / 查库并抓取」调用 `/api/search*`（见 [`frontend/README.md`](review_intel/frontend/README.md)）。 |
| `review_intel/tests/` | 子系统单元测试；`tests/fixtures/` 为样例 JSON。 |

## 前端联调（关键词检索 UI）

1. 启动 API：`make review-intel-api` 或 `python -m uvicorn review_intel.api.app:app --reload --host 127.0.0.1 --port 8090`。
2. 可选：设置 `REVIEW_INTEL_API_DATA` 指向固定目录，便于多次启动仍能看到历史入库数据。
3. 进入 [`review_intel/frontend`](review_intel/frontend/) 执行 `npm install` 与 `npm run dev`（默认连接 `http://127.0.0.1:8090`，见 `.env.development` 中 `VITE_API_BASE`）。

## 与现有代码的边界

- **顶层 `api/`**：现有 FastAPI 爬虫管理服务；`review_intel/api/` 为独立应用，可按需 `include_router` 集成。
- **`media_platform/*`**：保持现有爬虫实现；新功能通过 **adapters** 增量对接。
- **根 `test/` 与 `tests/`**：历史测试布局保留；review_intel 以 **`review_intel/tests/`** 为主。

## 验证

```bash
make review-intel-test
```

或：

```bash
python -c "import review_intel; from review_intel.schemas.models import ReviewIntelRecord, ReviewPlatformKey"
python -m pytest review_intel/tests/ -q
```

## 已知限制

- 详见 [docs/first_round_design.md](docs/first_round_design.md) 第四节；子系统仍在迭代，以测试与 `first_round_design.md` 为准。
