# TOKINDLE — 开发上下文摘要

供后续开发或新会话快速恢复上下文用。与 `project_plan.md` 配合阅读。

---

## 1. 项目是什么

- **目标**：把微信公众号文章转成 EPUB，保存到本地 `output/`，并可选通过 Gmail SMTP 直接发往 Kindle（Send to Kindle 邮箱）。
- **流程**：抓/解析 → 生成 EPUB（Kindle 兼容）→ 落盘（带时间戳文件名，不覆盖）→ 发邮件到 Kindle（若配置 .env）→ 返回路径与 `email_sent`/`email_error`，并写入任务进度供 Admin UI 展示。
- **客户端**：Chrome 扩展（当前页 HTML → `/parse-html`）、iOS 快捷指令（剪贴板链接 → `/parse-url`）、RSS Worker（定时读 `feeds.json` 调 `/parse-url`）、Streamlit Admin UI（进程管理、配置、任务看板）。

---

## 2. 整体思路、依赖环境与基本逻辑

**思路**：后端提供若干接口（见 §4）；Chrome 扩展和 iOS 快捷指令把「链接」或「当前页 HTML」发给后端，后端统一做抓取/解析、图片防盗链、EPUB 生成（含 Kindle 兼容处理）、写入 `output/`，再按 .env 配置通过 Gmail SMTP 发往 Kindle，返回路径与邮件结果。

**依赖环境**：

| 组件 | 依赖 |
|------|------|
| 后端 | Python 3.9+、`requirements.txt`（FastAPI / Uvicorn / requests / BeautifulSoup4 / EbookLib / Pillow / python-dotenv / python-multipart 等）。**Send to Kindle 为可选**：需配置 `.env`（见 `.env.example`）；未配置时仅保存 EPUB，响应中 `email_sent: false`。 |
| Admin UI | Streamlit、psutil、requests、python-dotenv、feedparser；需后端已启动才能看到任务进度与健康状态。运行：`streamlit run admin_ui.py`（或 `./start.sh` 一键启动）。后端地址通过 `TOKINDLE_BACKEND_URL` 环境变量覆盖，默认 `http://127.0.0.1:8000`。 |
| Chrome 扩展 | 后端已启动；扩展选项里可配置 Backend URL（默认 `http://127.0.0.1:8000`）。 |
| iOS 快捷指令 | 后端已启动且 **`--host 0.0.0.0`**；iPhone 与运行后端的机器 **同一 Wi‑Fi**，快捷指令里 URL 填 `http://<主机IP>:8000/parse-url`。若需外网访问可选用 ngrok 等内网穿透。 |
| RSS Worker | 读项目根目录 `feeds.json`（格式见 docs/RSS_SETUP.md），已处理 URL 写入 `config/rss_seen.txt`（自动截断至 2000 条）；可由 Admin UI 或 launchd/systemd 启停。 |

**基本逻辑**：

- **POST /parse-url**：请求体 `{"url": "微信文章链接"}` → 创建任务并更新步骤（fetching_url → parsing_html → generating_epub → saving_file → sending_email → completed）→ 抓 URL → 解析 → `build_epub` → `save_epub`（文件名带时间戳）→ `send_to_kindle` → 返回 `{success, path, title, email_sent, email_error, task_id}`。
- **POST /parse-html**：请求体 `{"title": "...", "html_content": "<html>..."}` → 同上任务步骤（无 fetching_url）→ 同上流程，返回同上。
- **GET /tasks**：返回最近任务列表（含进度、状态、错误），供 Admin UI Dashboard 轮询。
- **GET /tasks/{task_id}**：返回单条任务详情。
- **POST /test-send-epub**：上传已知可用的 .epub，用同一 SMTP 发 Kindle；响应 `{success, filename, email_sent, email_error}`。
- Chrome 扩展：当前标签页取 title + outerHTML，POST 到 `/parse-html`，popup 中展示 path 与 Sent to Kindle 状态；任务进度可在 Admin UI 的 Dashboard 中查看。
- iOS 快捷指令：剪贴板或输入得到链接 → POST 到 `/parse-url`，同上；进度同样在 Admin UI 看。
- **RSS Worker**：长驻进程，读 `feeds.json`，定时拉 RSS，对每条新链接 POST `/parse-url`，已处理 URL 记入 `config/rss_seen.txt`。
- **Admin UI**：`streamlit run admin_ui.py`。侧边栏启停 FastAPI / RSS Worker（PID 文件），主区域：Dashboard（任务进度条）、Configuration（.env 编辑）、RSS Feeds（feeds.json）、Testing（Gmail 连接检查、发测试邮件、日志）。

---

## 3. 技术栈与入口

| 项目     | 说明 |
|----------|------|
| 语言     | Python 3 |
| 框架     | FastAPI + Uvicorn |
| 解析     | BeautifulSoup4 |
| 电子书   | EbookLib，**仅输出 .epub**，不生成 .mobi |
| 图片     | Pillow：所有图片转 JPEG（避免 Kindle E999 / WebP 拒绝） |
| 邮件     | smtplib + Gmail SMTP（STARTTLS），可选，依赖 .env |
| 依赖     | `requirements.txt`（含 python-dotenv、Pillow、python-multipart） |
| 启动     | `uvicorn main:app --reload`，默认 http://127.0.0.1:8000 |
| 调试     | http://127.0.0.1:8000/docs |

---

## 4. API 一览

| 方法/路径           | 作用 | 请求体 | 响应 |
|---------------------|------|--------|------|
| GET /ping           | 健康检查 | - | `{"ping":"pong"}` |
| POST /parse-url     | 链接抓微信文章 → EPUB → output/ → 可选发 Kindle；会写入任务进度 | `{"url": "https://mp.weixin.qq.com/s/..."}` | `{success, path, title, email_sent, email_error, task_id}` |
| POST /parse-html    | 已有 HTML → EPUB → output/ → 可选发 Kindle；会写入任务进度 | `{"title": "...", "html_content": "<html>..."}` | 同上 |
| GET /tasks          | 最近任务列表（供 Admin UI 轮询进度） | 可选 query `limit` | `{tasks: [{id, source, status, current_step, ...}]}` |
| GET /tasks/{task_id} | 单条任务详情 | - | 任务对象 |
| POST /test-send-epub | 上传已知可用的 .epub，用同一 SMTP 发 Kindle（排查 E999 用） | multipart/form-data，字段 `file` | `{success, filename, email_sent, email_error}` |

- 所有生成的 EPUB 写入 **`output/`**，文件名为「标题安全化（去特殊字符、截断 50 字）_YYYYMMDD_HHMMSS.epub」，避免覆盖。
- `output/`、`logs/`、`feeds.json`、`.env` 已在 `.gitignore`，不提交。

---

## 5. 必须遵守的约束（来自 project_plan）

1. **微信图片防盗链**  
   正文里的图真实地址在 `data-src`，请求图片时必须带 **`Referer: https://mp.weixin.qq.com/`**，否则可能 403。下载后嵌入 EPUB，并把 `<img>` 的 `src` 改为 EPUB 内路径。
2. **EPUB 格式与 Kindle 兼容（E999 修复）**  
   只生成 `.epub`（EbookLib）。为通过 Kindle 转换（避免 E999），已做：  
   - 图片：全部下载后经 Pillow 转 JPEG，EPUB 内仅 `.jpg`；`data:` 内联图从 DOM 中移除（`img.decompose()`）。  
   - DOM：移除 `script`、`style`、`iframe`、`video`、`audio`、`noscript`、`svg` 及所有 `mp-*` 自定义标签。  
   - 链接/样式：`href="javascript:;"` 改为 `href="#"`；style 中去掉 `background-image: url("http...)`。  
   - XHTML：正文序列化为严格自闭合 `<img ... />`、`<br/>`（`_to_xhtml_string`）。  
   - Spine：仅 `[chapter]`，不引用不存在的 `nav`（否则 manifest 缺 nav 会 E999）。  
3. **内容定位**  
   - 从 URL 抓的页面：用 `div#js_content` 或 class 含 `rich_media_content` 定位正文；若无则 422。
   - 从 `/parse-html` 来的 HTML：先按上面找，找不到则用 `<body>` 或整份文档。

---

## 6. main.py 结构（便于改代码时定位）

```
# 常量
OUTPUT_DIR, WECHAT_REFERER, FETCH_HEADERS, FETCH_TIMEOUT, IMAGE_TIMEOUT

# 请求模型
ParseUrlRequest(url), ParseHtmlRequest(title, html_content)

# 任务跟踪（内存，线程安全）
_tasks, _tasks_lock, _MAX_TASKS, STEPS_PARSE_URL, STEPS_PARSE_HTML
_new_task(source, detail, steps) → task_id
_task_step(task_id, step_name), _task_done(task_id, error=?, result=?)

# 输出
_safe_filename(title) → 安全文件名
save_epub(epub_bytes, title) → 写 output/，文件名带时间戳，返回绝对路径
send_to_kindle(epub_path, title) → (email_sent: bool, email_error: str|None)，读 .env 发 Gmail SMTP

# HTTP
fetch_wechat_article(url)
download_image(url)
_download_with_retry(url) → 带重试的图片下载

# 图片
_image_to_jpeg(raw_bytes) → JPEG bytes | None  # Pillow，WebP 等统一转 JPEG

# HTML 解析与 Kindle 兼容清洗
_strip_hidden_styles(root)             # 去掉 visibility/opacity/display 隐藏
_deep_clean_dom(root)                 # 移除 script/style/iframe/video/audio/noscript/svg/mp-*
_sanitize_links_and_styles(root)      # javascript: → #，去掉 style 里 url("http...)
_to_xhtml_string(tag)                 # 序列化为 XHTML，img/br 自闭合
_find_wechat_content_div(soup)
parse_wechat_html(raw_html)           # 全页 → (title, content_div)
parse_raw_html(html_content)          # 任意 HTML → content Tag

# EPUB 生成（/parse-url、/parse-html 共用）
build_epub(title, content) → bytes   # _deep_clean_dom → _sanitize_links_and_styles → 图转 JPEG、data: 图 decompose → 单章 spine=[chapter]

# 上层流程
create_epub_from_url(url) → (title, epub_bytes)
create_epub_from_html(title, html_content) → (title, epub_bytes)

# 路由
GET /ping
POST /parse-url       → 创建任务 → 逐步 _task_step → fetch → parse → build_epub → save_epub → send_to_kindle → _task_done → JSON(..., task_id)
POST /parse-html      → 同上（无 fetching_url 步骤）
GET /tasks            → 返回最近任务列表
GET /tasks/{task_id}  → 返回单任务
POST /test-send-epub  → 上传 file → 临时文件 → send_to_kindle → JSON(filename, email_sent, email_error)
```

- 错误：502 抓 URL 失败，422 无正文/参数问题，500 其它异常（detail 里带 traceback）。

---

## 7. 测试

- 位置：`tests/`（`conftest.py` 里是 fixture 和 `MINIMAL_JPEG`，`test_main.py` 是全部用例）。
- 运行：`pytest tests/ -v`（HTTP mock、SMTP mock、output 重定向到 tmp_path，**无真实网络、无真实邮件、不污染 output/ 目录**）。
- 共 **24 个用例**，覆盖：ping、parse-url 成功/网络错误/无正文、parse-html 成功/纯 body、**GET /tasks 列表、GET /tasks/{id}、任务 404、失败任务状态**、parse_wechat_html、parse_raw_html、_find_wechat_content_div 多种情况、_strip_hidden_styles、EPUB 内容与无隐藏样式。

---

## 8. 易踩坑（实现细节）

- **EbookLib 与 XML 声明**：往 `EpubHtml` 里塞的 HTML 字符串**不要**带 `<?xml version="1.0" ...?>`，否则 lxml 解析会报错，章节会变成空。
- **正文可见性**：微信页面常给正文容器加 `visibility: hidden; opacity: 0`，必须用 `_strip_hidden_styles` 去掉，否则 EPUB 里看起来是空的。
- **同名文件**：已改为「标题_YYYYMMDD_HHMMSS.epub」，不再覆盖；历史行为见 git 历史。

---

## 9. Phase 2 / 3 / 4 / 5 与 Admin UI（已实现）

- **Phase 2 — Chrome 扩展**：目录 `extension/`，Manifest V3。从当前标签页取 `document.title` + `document.documentElement.outerHTML`，POST 到后端 `/parse-html`。选项页可设 Backend URL。见 `extension/README.md`。
- **Phase 3 — iOS 快捷指令**：剪贴板或询问输入得到链接，POST `{"url": "<链接>"}` 到 `http://<主机IP>:8000/parse-url`（同 Wi‑Fi），Method=POST，Content-Type=application/json。详细步骤见 `docs/SHORTCUT_IOS.md`、`docs/iOS_SHORTCUT_SETUP.md`。
- **Phase 4 — Send to Kindle**：配置 `.env` 后，`/parse-url` 与 `/parse-html` 在保存 EPUB 后自动通过 Gmail SMTP 发往 Kindle；响应含 `email_sent`、`email_error`。EPUB 已按 Kindle 要求清洗，E999 已修复。可选：`POST /test-send-epub` 验证 SMTP。
- **Phase 5 — RSS 自动化**：`rss_worker.py` 长驻进程读 `feeds.json`，定时拉 RSS 并 POST `/parse-url`；或使用 `scripts/rss_job.py` + cron。见 `docs/RSS_SETUP.md`。
- **Admin UI**：`streamlit run admin_ui.py`（或 `./start.sh` 一键启动）。后端地址通过 `TOKINDLE_BACKEND_URL` 环境变量覆盖。侧边栏启停 FastAPI / RSS Worker（PID 文件），主区域：**Dashboard**（任务进度条，轮询 `/tasks`）、**Configuration**（邮箱提供商下拉 Gmail/Outlook/Custom + .env 编辑与保存并重启 FastAPI）、**RSS Feeds**（feeds.json 增删与校验）、**Testing & Logs**（Gmail/Outlook 连接检查、发测试邮件、日志查看）。首次使用缺 .env 或 feeds 时会显示引导说明。

---

## 10. 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 方式一：仅启动后端（适合只用扩展/快捷指令）
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 方式二：启动 Admin UI（推荐，可在此启停后端与 RSS Worker）
streamlit run admin_ui.py
# 然后在浏览器中点击侧边栏 Start 启动 FastAPI；可选 Start 启动 RSS Worker。

# RSS Worker 单独运行（若不用 Admin UI 管理）
python rss_worker.py

# 测试
pytest tests/ -v
```

- 需要手机通过同一 Wi‑Fi 访问时，后端须 `--host 0.0.0.0`，快捷指令 URL 填 `http://<主机IP>:8000/parse-url`。
- 若需外网访问，可选用 ngrok 等内网穿透，见 `docs/SHORTCUT_IOS.md`。部署与安全注意见 **DEPLOYMENT.md** 与 **DEPLOYABILITY_REVIEW.md**。

---

---

## 11. Kindle E999 修复与对比样本

- **结论**：通过对比「能正常发 Kindle 的 EPUB」（`samples/good.epub`）与「本工具生成曾报 E999 的 EPUB」（`samples/bad.epub`），定位并修复：spine 引用不存在的 `nav`、DOM 中保留 `svg`/`mp-*`、`href="javascript:;"`、style 内 `url("http...)` 等。修复后已验证可正常发至 Kindle。
- **测试接口**：`POST /test-send-epub` 可上传已知没问题的 .epub，用同一 SMTP 发 Kindle，用于区分是「生成内容问题」还是「SMTP/亚马逊问题」。

*若架构或接口有变，请同步更新本文和 `project_plan.md`。*
