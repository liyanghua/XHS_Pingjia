# ReviewCollectionRunner 调度边界（CollectionRunLimits）

`ReviewCollectionRunner`（[`review_intel/jobs/runner.py`](../review_intel/jobs/runner.py)）在**不依赖具体平台**的前提下，通过 `CollectionRunLimits` 控制搜索分页、帖子数量、评论分页与条数、是否拉取二级回复链。

## 字段说明

| 字段 | 默认值 | 含义 |
|------|--------|------|
| `max_search_pages` | `1` | 搜索分页最多拉取页数（与旧版「只搜一页」一致） |
| `max_posts` | `None` | 合并多页搜索结果后最多处理多少个帖子；`None` 不截断 |
| `max_comment_pages_per_post` | `1` | 每帖评论分页最多拉取页数；`None` 表示直到无下一页 |
| `max_comments_per_post` | `None` | 每帖评论+回复事件累计上限（`enable_replies=True` 时与回复共用同一配额）；`None` 不截断 |
| `enable_replies` | `False` | 是否在每条顶层评论上继续调用 `fetch_replies`（由适配器实现；小红书当前可能未实现） |

`run(..., limits=None)` 时等价于 `CollectionRunLimits()`，即与旧 Runner 行为一致（单页搜索、每帖单页评论、不截断帖子数与评论条数）。

## 与旧行为的对照

- 旧版：一次 `search_posts`，对每个帖子一次 `fetch_comments(None)`。  
- 现版默认：`max_search_pages=1`、`max_comment_pages_per_post=1`，其余不截断 → **等价**。

## 断点 JobCheckpoint

见 [`review_intel/jobs/checkpoint.py`](../review_intel/jobs/checkpoint.py)：`cursor` 为**搜索**下一页游标；`comment_cursor` + `pending_post_id` 表示**同帖评论**续拉；`last_post_id` 为**已完整处理**的帖子，用于 skip 恢复。

## 真实验收入口

```bash
python -m review_intel.jobs.runner_acceptance_demo --db-path /tmp/xhs_accept.db
```

可选：`--job-id`、`--keyword`（覆盖 `QuerySpec.terms`）、`--goto-timeout-ms`（首页加载超时毫秒，默认 120000；跨境或慢网可设 180000）。默认 limits：**3 帖 × 每帖最多 20 条评论事件（最多 20 页评论分页）**。

若出现 ``Page.goto: Timeout exceeded``：多为访问 `xiaohongshu.com` 过慢或被拦截，请检查本机网络、系统代理、VPN，或增大 `--goto-timeout-ms`。

## CollectionRunSummary 样例（虚构）

成功时 `model_dump(mode="json")` 大致如下（数值随平台与清洗结果变化）：

```json
{
  "job_id": "job-xhs-acceptance-womens-sun-painpoint",
  "fetched_count": 12,
  "normalized_count": 12,
  "cleaned_count": 6,
  "stored_raw_count": 10,
  "stored_normalized_count": 5,
  "last_error": null,
  "limits": {
    "max_search_pages": 1,
    "max_posts": 3,
    "max_comment_pages_per_post": 20,
    "max_comments_per_post": 20,
    "enable_replies": false
  },
  "search_pages_fetched": 1,
  "posts_selected": 3,
  "comment_pages_fetched": 4,
  "reply_pages_fetched": 0,
  "last_error_context": null
}
```

失败时仍以抛异常为主；日志中会带 `stage`、`post_id`、`search_cursor`、`comment_cursor`（若适用），断点 JSON 中写入 `last_error`。
