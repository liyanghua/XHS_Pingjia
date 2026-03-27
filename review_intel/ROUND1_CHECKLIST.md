# review_intel 第一轮完成情况清单

用于发布前自检与交接；与 `docs/first_round_design.md` 配合使用。

## 契约与模型

- [x] `schemas`：`RawReviewEvent`、`NormalizedReview`（含 `job_id` / `extra_meta`）、分页模型与枚举可 JSON 往返
- [x] `jobs`：`CollectionJob` / `QuerySpec` / 示例作业；`create_job_from_dict`
- [x] `jobs/runner`：`ReviewCollectionRunner` + `CollectionRunSummary`

## 存储与清洗

- [x] `storage`：SQLite raw + normalized；`event_id` / `review_id` 幂等
- [x] `cleaners`：过滤、精确去重、质量分、`clean_and_score_reviews`

## 编排与断点

- [x] `checkpoint`：`JobCheckpoint`、`CheckpointStage`；JSON / SQLite 两种 Store
- [x] `runner`：平台调用重试；断点按帖恢复（最小语义）
- [x] `scheduler`：`run_collection_job` / `MinimalScheduler` 薄封装

## API 与调试

- [x] `api`：POST/GET `/jobs`、GET `/jobs/{id}/reviews`、`/summary`；`app.py` 可 `uvicorn` 启动

## 测试与样例

- [x] `review_intel/tests/` 覆盖 schemas / cleaners / storage / runner / checkpoint / api（含 fixtures 联动）
- [x] `review_intel/tests/fixtures/sample_comments.json` + README

## 文档与命令

- [x] `docs/first_round_design.md`
- [x] 根目录 `Makefile`：`review-intel-test` / `review-intel-api` / `review-intel-demo`
- [x] `README_review_intel.md` 指向设计与清单

## 验证命令

```bash
make review-intel-test
```
