# XHS_Pingjia (Review Intelligence)

This repository extends **[MediaCrawler](https://github.com/NanmiCoder/MediaCrawler)** with the **`review_intel`** subsystem and **Xiaohongshu (XHS)**-focused improvements: login detection (`pong()` / `selfinfo`), `xhs_demo` session flow, and unified browser profile paths.

| README | [中文](README.md) · **English** · [Español](README_es.md) |

[![License](https://img.shields.io/github/license/liyanghua/XHS_Pingjia)](LICENSE)
[![GitHub](https://img.shields.io/badge/GitHub-liyanghua%2FXHS__Pingjia-181717?logo=github)](https://github.com/liyanghua/XHS_Pingjia)

## Highlights

- **`review_intel/`** — Normalize reviews, cleaners, SQLite stores, FastAPI, Vite/React search UI.
- **XHS** — `XHSAdapter`, `xhs_mapping.py`, real-network smoke: `python -m review_intel.adapters.xhs_demo`.
- **Upstream** — Original multi-platform crawler still available via `uv run main.py ...`.

## Quick start

```bash
uv sync
uv run playwright install
make review-intel-test
make review-intel-api      # http://127.0.0.1:8090
make review-intel-xhs-demo # real XHS; login required
```

See **[README_review_intel.md](README_review_intel.md)** and **[review_intel/adapters/README_XHS.md](review_intel/adapters/README_XHS.md)** for details, env vars (`XHS_DEBUG_SELFINFO`), and troubleshooting.

## Legal

For learning and research only. Respect platform ToS and local laws. License terms in [LICENSE](LICENSE); upstream: [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler).
