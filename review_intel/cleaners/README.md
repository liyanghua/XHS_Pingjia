# review_intel.cleaners：第一轮规则式清洗

面向「小红书等真实评论」的可解释管线：**过滤** → **精确去重** → **质量分**，不引入 embedding / LLM。

## 动机（为何加「高价值短词」）

- 真实评论区存在大量 **2～4 字的有效反馈**（如「好穿」「闷」「起球」），仅按 `min_len` 截断会 **误杀高信息密度短评**。
- 原 `quality_score` 长度项权重高，短评总分易 **被压得过低**，不利于后续排序与展示。

## 规则结构（透明、易调）

| 模块 | 职责 |
|------|------|
| [`term_lists.py`](term_lists.py) | **集中配置**默认高价值短词（子串匹配）；可按品类迭代或运行时传入自定义 `frozenset` |
| [`filters.py`](filters.py) | 空 → 纯表情/符号 → **广告** → **过短**（命中高价值词则豁免长度） |
| [`dedup.py`](dedup.py) | 标准化正文精确去重（未改） |
| [`quality_score.py`](quality_score.py) | 长度 / 具体性 / 属性词；短文本且命中高价值词时 **不低于** `QUALITY_FLOOR_SHORT_HIT` |
| [`pipeline.py`](pipeline.py) | `clean_and_score_reviews` 统一传入词表 |

### `clean_and_score_reviews` 与词表

- **`high_value_short_terms=None`（默认）**：使用 [`default_high_value_short_terms()`](term_lists.py)，启用短评豁免与质量分下限。
- **`high_value_short_terms=frozenset()`**：关闭高价值机制，行为接近早期「仅 `min_len` + 广告」。
- **自定义 `frozenset`**：自建词表（如垂直品类）。

单独调用 [`should_keep_review_text`](filters.py) 时，`high_value_short_terms=None` 表示 **不豁免**（兼容旧调用）；管线内会传入解析后的 `frozenset`。

## 适应真实评论的规则小结

1. **广告优先于长度**：短文本若含「私我」「加微信」等，仍丢弃，避免高价值词表误放行营销话术。
2. **高价值子串**：命中则短亦可留、且质量分有下限，减轻「短=差」的偏差。
3. **仍规则化**：全部可用人眼审查与单元测试固定。

## 可能的副作用

| 风险 | 说明 |
|------|------|
| 子串误命中 | 如「透」可能匹配无关上下文；需靠词表精简或改为整词/分类目表（后续轮次） |
| 词表膨胀 | 词过多会放过低质短评；建议定期复盘命中率与人工抽检 |
| 与广告词表极少数重叠 | 若业务词与广告子串冲突，应优先调整广告词或高价值词，并加测试锁定 |

## 测试

见 [`review_intel/tests/test_cleaners_xhs_realistic.py`](../tests/test_cleaners_xhs_realistic.py) 与 [`fixtures/sample_comments.json`](../tests/fixtures/sample_comments.json)。
