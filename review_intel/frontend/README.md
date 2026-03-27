# review_intel 前端（Vite + React + TS）

调用本仓库 FastAPI 的 `/api/search` 与 `/api/search/run`。

## 开发

```bash
# 终端 1：后端（项目根目录）
export REVIEW_INTEL_API_DATA=/tmp/review_intel_data   # 可选，持久化作业库
python -m uvicorn review_intel.api.app:app --reload --host 127.0.0.1 --port 8090

# 终端 2：前端（本目录）
npm install
npm run dev
```

浏览器打开 Vite 提示的地址（默认 `http://127.0.0.1:5173`）。

**联调建议（避免「查询并抓取」跨域失败）**

1. 先启动后端：`uvicorn review_intel.api.app:app --reload --host 127.0.0.1 --port 8090`。
2. `.env.development` 中 **`VITE_API_BASE` 留空**（默认）：前端请求走 **Vite 代理**（`vite.config.ts` 里 `/api` → `8090`），与页面同源，无 CORS 问题。
3. 若把 `VITE_API_BASE` 设为 `http://127.0.0.1:8090` 直连后端，需保证后端 CORS 允许你的前端 origin（已用 `localhost` / `127.0.0.1` 任意端口正则）。
4. 若出现 `Failed to fetch`：检查 8090 是否已监听、防火墙、以及是否用 `https` 页面去请求 `http` API（混合内容会被拦截）。

## 构建

```bash
npm run build
```

产物在 `dist/`，可由任意静态服务器托管；部署时需将 `VITE_API_BASE` 指到实际 API  origin。
