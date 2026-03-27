# review_intel 调试 API

最小 FastAPI 服务，用于本地联调「创建作业 → 同步跑 Dummy 采集 → 查摘要与归一化评价」。不面向公网，无鉴权。

## 依赖

与主项目一致，需已安装 `fastapi`、`uvicorn`（见仓库根目录 `pyproject.toml`）。

## 启动

```bash
cd /path/to/MediaCrawler-main
uvicorn review_intel.api.app:app --reload --port 8090
```

可选环境变量：

| 变量 | 含义 |
|------|------|
| `REVIEW_INTEL_API_DATA` | 作业与 SQLite 文件根目录；未设置则使用系统临时目录 |

## 接口一览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/jobs` | 创建作业；`execute: true`（默认）时同步执行一次采集 |
| GET | `/jobs/{job_id}` | 作业详情 + 可选运行摘要 |
| GET | `/jobs/{job_id}/reviews` | 该作业 SQLite 中的归一化评价列表 |
| GET | `/jobs/{job_id}/summary` | 运行摘要（需已成功执行过采集） |
| GET | `/api/search?q=` | 跨作业扫描 `REVIEW_INTEL_API_DATA/*/store.db`，按关键词子串过滤并去重 |
| POST | `/api/search/run` | body：`{"keyword":"…","job_id":null}` — 先扫库再同步跑 Dummy `ReviewCollectionRunner`，合并返回 |

开发环境下为 `http://127.0.0.1:5173` / `http://localhost:5173` 启用了 CORS，便于 [`review_intel/frontend`](../frontend/README.md) 联调。

响应 JSON 均带 `version: "1"`，便于前端契约演进。

## 测试

```bash
pytest review_intel/tests/test_api.py -q
```

## 示例

```bash
# 仅创建不执行
curl -s -X POST http://127.0.0.1:8090/jobs \
  -H 'Content-Type: application/json' \
  -d '{"query_spec":{"intent":"painpoint_search","terms":["闷热"],"platforms":["xhs"]},"execute":false}' | jq .

# 创建并同步执行（DummyAdapter）
curl -s -X POST http://127.0.0.1:8090/jobs \
  -H 'Content-Type: application/json' \
  -d '{"query_spec":{"intent":"painpoint_search","terms":["闷热"],"platforms":["xhs"]},"execute":true}' | jq .

# 将上一步返回的 job_id 填入
curl -s http://127.0.0.1:8090/jobs/<job_id>/summary | jq .
```
