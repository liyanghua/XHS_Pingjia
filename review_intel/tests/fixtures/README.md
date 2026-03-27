# 测试用样例数据

供 `review_intel/tests/` 中测试与后续 AI 工具引用，**非**生产数据。

| 文件 | 说明 |
|------|------|
| `sample_comments.json` | 归一化评论正文片段、用途标签；用于 cleaners / schema 边界用例 |

扩展约定：JSON 顶层 `version` 字段；新增字段时保持向后兼容或递增 `version`。
