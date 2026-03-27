# 小红书 XHSAdapter

## 依赖

- 与主项目相同：Playwright、已配置的 `config`（登录、CDP/标准浏览器等）。
- 网络与签名由 `media_platform.xhs.client.XiaoHongShuClient` 完成，适配器只做参数与 `review_intel` 模型映射（见 `xhs_mapping.py`）。

## 模块

| 文件 | 说明 |
|------|------|
| `xhs_mapping.py` | API `dict` ↔ `SearchPage` / `CommentPage` / `RawReviewEvent` / 窄表 `normalize_post` |
| `xiaohongshu.py` | `XHSAdapter`：注入 `XiaoHongShuClient`，缓存 `note_id → (xsec_token, xsec_source)` |
| `xhs_demo.py` | 真实环境验收脚本（浏览器 + 登录 + 搜索 + 评论） |

## 运行 Demo（真实请求）

在**仓库根目录**执行：

```bash
python -m review_intel.adapters.xhs_demo --keyword 防晒 --max-notes 2 --max-comments 3
```

首次需完成小红书 Web 登录（与运行主爬虫一致）。

## CDP 与浏览器数据目录

- **`ENABLE_CDP_MODE`**（[`config/base_config.py`](../../config/base_config.py)）默认 **False**：避免本机访问 `http://localhost:<CDP_DEBUG_PORT>/json/version` 时出现 **HTTP 502**（端口被占用、系统代理/VPN、DevTools 未就绪等）导致 CDP 连接失败。
- 若需 CDP：关闭占用端口的进程、暂时关闭代理后重试；或将 `ENABLE_CDP_MODE` 设为 `True`。
- **标准 Playwright 持久化目录与 CDP 使用同一目录名**：`browser_data/cdp_<平台>_user_data_dir`（小红书示例：`browser_data/cdp_xhs_user_data_dir`），避免「CDP 一套、回退后又一套」导致登录态分裂。旧版仅使用 `browser_data/xhs_user_data_dir` 的用户如需保留会话，可在**退出所有浏览器后**自行合并或重命名目录（谨慎操作）。

## 调试 `pong=False`（API 自检失败）

- `pong()` 调用 edith 的 `GET .../user/selfinfo`，与页面是否显示「我」、是否有 `web_session` Cookie **可能不一致**。
- 设置环境变量 **`XHS_DEBUG_SELFINFO=1`** 后，[`XiaoHongShuClient.query_self`](../../media_platform/xhs/client.py) 会在日志中打印 HTTP 状态码与**截断后的响应体**（便于区分 401/结构变化/风控；请勿在公开场合粘贴完整日志）。

## 已登录仍提示要登录 / 优先 Cookie

`xhs_demo` 会先 **`update_cookies` 再 `pong()`**：

- **`pong()==True`**：视为 API 会话有效，**不再**打开登录流程。
- **`pong()==False`**：只做**一次**软同步（单次 reload + `pong`），再尝试 `/login`，然后照常执行 **`LOGIN_TYPE`**（扫码/手机/Cookie）。扫码成功后会对 Cookie 做**多轮同步 + 回首页等待**并重试 `pong()`；若 `selfinfo` 仍异常但浏览器已显示登录态，**仍会进入搜索/评论**（避免「扫码成功却退出」）。
- **推荐**：在能正常打开小红书的浏览器中导出 Cookie，在 config 中设置 **`LOGIN_TYPE=cookie`** 与 **`COOKIES`**，使 httpx 与浏览器一致。
- 若坚持扫码：在浏览器中**退出账号**后再运行，使页面回到**未登录**（与 `login_by_qrcode` 的顶栏按钮假设一致）；或清空 `browser_data/cdp_xhs_user_data_dir` 后重试（先关闭浏览器）。

搜索阶段若仍报「登录已过期」等，会退出码 `3` 并提示重新登录或清理用户数据目录。

## 限制（第一版）

- `fetch_replies` 未实现，显式 `NotImplementedError`（二级评论需 `get_note_sub_comments` 与更多上下文）。
- `fetch_post_detail` / `fetch_comments` 依赖 `search_posts` 对同一 `note_id` 写入的 `xsec_token` 缓存；否则可能失败。
- `/feed` 接口偶发 ``{"code":-1,"success":false}``（tenacity 抛 ``RetryError``）时，适配器会**自动回退** ``get_note_by_id_from_html``，与主爬虫 ``get_note_detail_async_task`` 一致；若仍失败请检查登录态与风控。
