# XHS_Pingjia（评价情报）

基于开源项目 [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) 扩展：**评价情报子系统 `review_intel`**，并针对 **小红书（XHS）** 的登录检测、`xhs_demo` 验收流程与浏览器数据目录等做了工程化优化。

| 文档 | [中文 README](README.md) · [English](README_en.md) · [Español](README_es.md) |
|------|-----------------------------------------------------------------------------|

[![License](https://img.shields.io/github/license/liyanghua/XHS_Pingjia)](LICENSE)
[![GitHub](https://img.shields.io/badge/GitHub-liyanghua%2FXHS__Pingjia-181717?logo=github)](https://github.com/liyanghua/XHS_Pingjia)

---

## 本仓库在做什么

- **`review_intel/`**：评论/评价的采集、归一化、清洗、SQLite 存储、FastAPI 调试接口与 **Vite + React** 关键词检索前端（与主爬虫并行，不替换 `main.py`）。
- **小红书适配**：`review_intel/adapters/xiaohongshu.py`、`xhs_mapping.py`；真实环境验收用 **`python -m review_intel.adapters.xhs_demo`**。
- **上游能力保留**：仍可通过 `uv run main.py --platform xhs ...` 使用原版多平台爬虫（见 `config/`）。

## 相对上游的主要优化（XHS / 会话）

| 方向 | 说明 |
|------|------|
| **`pong()` 登录判定** | `media_platform/xhs/client.py`：兼容 `selfinfo` 多种 JSON 结构；在响应非「明确未登录」时，可用 `web_session` Cookie 辅助判断，减少「已登录却判未登录」。 |
| **`xhs_demo` 会话流程** | 单次软同步、扫码后 **稳定会话并重试 `pong()`**；必要时以 **浏览器探测已登录** 兜底后继续搜索/评论，避免扫码成功仍退出。 |
| **浏览器数据目录** | `config.browser_persistent_data_dirname()`：标准 Playwright 与 CDP 共用 `browser_data/cdp_<平台>_user_data_dir`，避免两套目录分裂。 |
| **CDP 默认关闭** | `ENABLE_CDP_MODE` 默认 `False`，减少本机 `/json/version` 502 导致反复回退；需要时再在 `config/base_config.py` 开启。 |
| **调试** | 环境变量 `XHS_DEBUG_SELFINFO=1` 时打印 `selfinfo` 响应截断内容，便于排查。 |

详细排障与运行说明见 **[review_intel/adapters/README_XHS.md](review_intel/adapters/README_XHS.md)**。

## 快速开始

### 依赖

- Python 3.11+（见 `pyproject.toml` / `requirements.txt`）
- [uv](https://docs.astral.sh/uv/) 或 `pip` + `venv`
- Node.js ≥ 16（前端 / 部分工具）

```bash
cd /path/to/XHS_Pingjia   # 或本仓库根目录
uv sync                   # 或: pip install -r requirements.txt
uv run playwright install
```

### 评价情报子系统

```bash
make review-intel-test           # 子系统单测
make review-intel-api            # FastAPI，默认 http://127.0.0.1:8090
make review-intel-xhs-demo       # 小红书真实验收（需可登录环境）
```

更多命令与模块说明见 **[README_review_intel.md](README_review_intel.md)**。

### 原版爬虫入口（可选）

```bash
uv run main.py --platform xhs --lt qrcode --type search
# 配置见 config/base_config.py、config/xhs_config.py
```

## 文档索引

| 文档 | 内容 |
|------|------|
| [README_review_intel.md](README_review_intel.md) | 子系统目标、Makefile、测试分层、模块职责 |
| [review_intel/adapters/README_XHS.md](review_intel/adapters/README_XHS.md) | 小红书适配、`xhs_demo`、CDP/目录/登录排障 |
| [docs/first_round_design.md](docs/first_round_design.md) | 第一轮设计与边界 |
| [LICENSE](LICENSE) | 许可证（继承上游 NON-COMMERCIAL LEARNING LICENSE 等，请一并阅读） |

## 致谢与上游

- 核心爬虫框架来自 **[NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler)**。
- 使用本仓库请遵守目标平台服务条款与当地法律法规，**仅供学习与研究**，禁止用于未授权的大规模爬取或商业滥用。

## 免责声明（摘要）

本仓库代码仅供技术研究与学习；使用者自行承担合规与数据使用责任。完整条款见仓库内许可文件及上游文档；继续使用即表示知悉相关风险。

---

<div id="disclaimer"></div>
