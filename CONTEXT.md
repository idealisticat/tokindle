# TOKINDLE — 开发上下文摘要

供后续开发或新会话快速恢复上下文用。与 `project_plan.md` 配合阅读。

---

## 1. 项目是什么

- **目标**：把微信公众号文章转成 EPUB，保存到本地 `output/`，由外部 RPA（如 OpenClaw）负责上传到 Kindle。
- **不做**：不发邮件、不调 Kindle API，后端只负责「抓/解析 → 生成 EPUB → 落盘 → 返回路径」。
- **客户端**：Chrome 扩展（当前页 HTML → `/parse-html`）、iOS 快捷指令（剪贴板链接 → `/parse-url`）。

---

## 2. 整体思路、依赖环境与基本逻辑

**思路**：后端提供两个接口（见 §4）；Chrome 扩展和 iOS 快捷指令只负责把「链接」或「当前页 HTML」发给后端，后端统一做抓取/解析、图片防盗链、EPUB 生成并写入 `output/`，返回保存路径。上传到 Kindle 由 RPA 等外部工具从 `output/` 处理。

**依赖环境**：

| 组件 | 依赖 |
|------|------|
| 后端 | Python 3、`requirements.txt`（FastAPI / Uvicorn / requests / BeautifulSoup4 / EbookLib 等），无 .env 必填项 |
| Chrome 扩展 | 后端已启动；扩展选项里可配置 Backend URL（默认 `http://127.0.0.1:8000`） |
| iOS 快捷指令 | 后端已启动且 **`--host 0.0.0.0`**；iPhone 与运行后端的 Mac **同一 Wi‑Fi**，快捷指令里 URL 填 `http://Mac的IP:8000/parse-url`。若需外网访问可选用 ngrok 等内网穿透 |

**基本逻辑**：

- **POST /parse-url**：请求体 `{"url": "微信文章链接"}` → 后端用 requests 抓该 URL → 解析正文与图片（data-src + Referer）→ `build_epub` → `save_epub` 写 `output/` → 返回 `{success, path, title}`。
- **POST /parse-html**：请求体 `{"title": "...", "html_content": "<html>..."}` → 后端不抓 URL，直接解析 `html_content`（同一套正文/图片逻辑）→ `build_epub` → `save_epub` → 返回同上。
- Chrome 扩展：当前标签页用 `scripting.executeScript` 取 `document.title` 和 `document.documentElement.outerHTML`，POST 到 `/parse-html`。
- iOS 快捷指令：剪贴板或询问输入得到链接 → POST 到 `/parse-url`，body 为 `{"url": "<链接变量>"}`，需确保变量正确绑定且 Content-Type 为 `application/json`。

---

## 3. 技术栈与入口

| 项目     | 说明 |
|----------|------|
| 语言     | Python 3 |
| 框架     | FastAPI + Uvicorn |
| 解析     | BeautifulSoup4 |
| 电子书   | EbookLib，**仅输出 .epub**，不生成 .mobi |
| 依赖     | `requirements.txt`（无 python-dotenv，无 SMTP） |
| 启动     | `uvicorn main:app --reload`，默认 http://127.0.0.1:8000 |
| 调试     | http://127.0.0.1:8000/docs |

---

## 4. API 一览

| 方法/路径        | 作用 | 请求体 | 响应 |
|------------------|------|--------|------|
| GET /ping        | 健康检查 | - | `{"ping":"pong"}` |
| POST /parse-url  | 根据链接抓微信文章 → EPUB → 写入 output/ | `{"url": "https://mp.weixin.qq.com/s/..."}` | `{"success": true, "path": "/abs/path/to/output/标题.epub", "title": "..."}` |
| POST /parse-html | 根据已有 HTML 生成 EPUB（不请求 URL）→ 写入 output/ | `{"title": "...", "html_content": "<html>..."}` | 同上 |

- 所有 EPUB 写入 **`output/`**（项目根下），文件名由标题做安全化（去特殊字符、截断 50 字）+ `.epub`。
- `output/` 已在 `.gitignore`，不提交。

---

## 5. 必须遵守的约束（来自 project_plan）

1. **微信图片防盗链**  
   正文里的图真实地址在 `data-src`，请求图片时必须带 **`Referer: https://mp.weixin.qq.com/`**，否则可能 403。下载后嵌入 EPUB，并把 `<img>` 的 `src` 改为 EPUB 内路径。
2. **EPUB 格式**  
   只生成 `.epub`（EbookLib），不生成 `.mobi`。
3. **内容定位**  
   - 从 URL 抓的页面：用 `div#js_content` 或 class 含 `rich_media_content` 定位正文；若无则 422。
   - 从 `/parse-html` 来的 HTML：先按上面找，找不到则用 `<body>` 或整份文档。

---

## 6. main.py 结构（便于改代码时定位）

```
# 常量
OUTPUT_DIR, WECHAT_REFERER, FETCH_HEADERS, FETCH_TIMEOUT, IMAGE_TIMEOUT, _EXT_BY_HINT

# 请求模型
ParseUrlRequest(url), ParseHtmlRequest(title, html_content)

# 输出
_safe_filename(title) → 安全文件名
save_epub(epub_bytes, title) → 写 output/，返回绝对路径

# HTTP
fetch_wechat_article(url)   # 抓整页 HTML
download_image(url)         # 带 Referer 抓图

# HTML 解析（WeChat 专用 + 通用）
_strip_hidden_styles(root)           # 去掉 visibility/opacity/display 隐藏
_find_wechat_content_div(soup)      # 找正文 div，多种选择器兜底
parse_wechat_html(raw_html)          # 全页 → (title, content_div)，无 div 则 ValueError
parse_raw_html(html_content)         # 任意 HTML → content Tag（含 fallback body/整文档）

# EPUB 生成（/parse-url 和 /parse-html 共用）
_guess_ext(url)       # 按 URL 猜图片后缀
build_epub(title, content: Tag) → bytes   # 处理 img data-src、下载、写 EPUB

# 上层流程
create_epub_from_url(url) → (title, epub_bytes)
create_epub_from_html(title, html_content) → (title, epub_bytes)

# 路由
GET /ping
POST /parse-url  → 调 create_epub_from_url → save_epub → JSON
POST /parse-html → 调 create_epub_from_html → save_epub → JSON
```

- 错误：502 抓 URL 失败，422 无正文/参数问题，500 其它异常（detail 里带 traceback）。

---

## 7. 测试

- 位置：`tests/`（`conftest.py` 里是 fixture 和 `MINIMAL_JPEG`，`test_main.py` 是全部用例）。
- 运行：`pytest tests/ -v`（已 mock 所有 requests，无真实网络）。
- Phase 1 收尾时共 **20 个用例**，覆盖：ping、parse-url 成功/网络错误/无正文、parse-html 成功/纯 body、parse_wechat_html、parse_raw_html、_find_wechat_content_div 多种情况、_strip_hidden_styles、EPUB 内容与无隐藏样式。

---

## 8. 易踩坑（实现细节）

- **EbookLib 与 XML 声明**：往 `EpubHtml` 里塞的 HTML 字符串**不要**带 `<?xml version="1.0" ...?>`，否则 lxml 解析会报错，章节会变成空。
- **正文可见性**：微信页面常给正文容器加 `visibility: hidden; opacity: 0`，必须用 `_strip_hidden_styles` 去掉，否则 EPUB 里看起来是空的。
- **同名文件**：同一标题会覆盖 `output/` 下同名 .epub；如需不覆盖可在此文档或代码里注明「后续可加时间戳/UUID」。

---

## 9. Phase 2 & 3（已实现）

- **Phase 2 — Chrome 扩展**：目录 `extension/`，Manifest V3。从当前标签页取 `document.title` + `document.documentElement.outerHTML`，POST 到后端 `/parse-html`。选项页可设 Backend URL。见 `extension/README.md`。
- **Phase 3 — iOS 快捷指令**：剪贴板或询问输入得到链接，POST `{"url": "<链接>"}` 到 `http://Mac的IP:8000/parse-url`（同 Wi‑Fi），Method=POST，Content-Type=application/json，Request Body 的 `url` 必须绑定到链接变量。详细步骤见 `docs/SHORTCUT_IOS.md`、`docs/iOS_SHORTCUT_SETUP.md`。
- **Phase 4**：OpenClaw（或其它 RPA）监听/轮询 `output/`，上传到 Kindle，未实现。

---

## 10. 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务（仅本机访问，如 Chrome 扩展）
uvicorn main:app --reload

# 启动服务（允许局域网访问，如 iOS 快捷指令同 Wi‑Fi）
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 测试
pytest tests/ -v
```

- 需要手机通过同一 Wi‑Fi 访问时，必须加 `--host 0.0.0.0`，快捷指令 URL 填 `http://Mac的IP:8000/parse-url`。
- 若需外网访问，可选用 ngrok 等内网穿透，见 `docs/SHORTCUT_IOS.md`。

---

*若架构或接口有变，请同步更新本文和 `project_plan.md`。*
