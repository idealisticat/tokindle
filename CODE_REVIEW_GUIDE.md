# TOKINDLE — 第三方 AI 单文件代码审查建议

本仓库将使用**每次只审查一个文件**的第三方 AI 进行代码审查。请按下面列出的**顺序**依次打开并审查每个文件；每份「审查焦点」用于引导 AI 在该文件中重点看什么，以便在单文件视角下仍能覆盖架构、安全与可维护性。

---

## 使用说明

- **顺序**：务必按 1 → 2 → 3 → … 的顺序审查，以便先理解核心逻辑再看扩展与测试。
- **单文件**：每次只向 AI 提供本列表中「文件路径」所指的**一个文件**的完整内容，并附上对应的「审查焦点」。
- **输出**：请 AI 针对该文件给出：逻辑/正确性、边界与错误处理、安全、可读性与可维护性、性能（如适用）方面的意见，以及具体修改建议（若无需修改也请说明）。

---

## 审查顺序与焦点

### 1. `main.py`

**文件路径**：`main.py`（项目根目录）

**审查焦点**：

- **任务跟踪**：`_tasks`、`_tasks_lock`、`_new_task`、`_task_step`、`_task_done` 的线程安全与竞态；任务数量上限 `_MAX_TASKS` 的清理策略是否会导致遗漏或重复。
- **API 契约**：`POST /parse-url`、`POST /parse-html` 的请求/响应格式；错误时是否仍正确调用 `_task_done` 并返回合适 HTTP 状态码。
- **EPUB 与 Kindle**：`save_epub` 的时间戳命名是否可能冲突；`build_epub` 与图片下载（含 `_download_with_retry`）在异常路径下是否会导致资源未释放或任务状态不一致。
- **安全**：是否从用户输入（URL、html_content）直接进入请求或文件系统；路径遍历、注入风险。
- **依赖**：对 `.env` 的读取时机；是否在请求中依赖全局可变状态（除任务字典外）。

---

### 2. `admin_ui.py`

**文件路径**：`admin_ui.py`（项目根目录）

**审查焦点**：

- **进程管理**：基于 PID 文件的启停逻辑；`_read_pid`、`_kill_pid` 在进程已退出、权限不足、跨平台（如 Windows）时的行为。
- **配置与敏感信息**：`.env` 的读取与写回；在 UI 中展示或日志中是否可能泄露密码；`validate_env` 与保存前的校验是否充分。
- **后端地址**：`BACKEND_URL` 写死为 `http://127.0.0.1:8000` 对跨机/多环境部署的影响；是否应改为环境变量可配置。
- **任务展示**：对 `GET /tasks` 的轮询与解析；在 FastAPI 未启动或返回异常时的降级与错误提示。
- **RSS 与 feeds.json**：对 `feeds.json` 的读写与校验；`validate_feed_url` 在超时或恶意 URL 下的行为。
- **Streamlit 使用**：`st.fragment(run_every=...)` 的刷新频率是否合理；表单与按钮是否存在重复提交或状态不一致。

---

### 3. `rss_worker.py`

**文件路径**：`rss_worker.py`（项目根目录）

**审查焦点**：

- **优雅退出**：SIGTERM/SIGINT 处理与 `_shutdown` 标志；是否在收尾（如当前周期完成、PID 文件删除）后再退出。
- **PID 文件**：写入与删除的时机；进程崩溃时是否会产生陈旧 PID 文件及对后续启动的影响。
- **feeds.json**：解析失败、格式错误时的降级与日志；`interval_minutes` 与循环间隔的边界（如 0 或极大值）。
- **网络与重试**：`_post_with_retry` 的重试次数与退避；对 backend 不可用、超时的处理是否会导致 worker 卡死或重复发送。
- **已处理 URL**：`config/rss_seen.txt` 的并发写入（若与其它进程共享）；文件无限增长与清理策略。

---

### 4. `tests/test_main.py`

**文件路径**：`tests/test_main.py`

**审查焦点**：

- **覆盖范围**：是否覆盖 `main.py` 中新增的任务跟踪（如任务 ID 在响应中、失败时任务状态为 failed）；是否覆盖 `GET /tasks`、`GET /tasks/{task_id}`。
- **Mock 与隔离**：网络请求、文件系统、`.env` 的 mock 是否充分；是否有测试依赖真实环境或泄漏状态。
- **边界与错误**：502/422/500 等路径；空输入、超长 URL、非法 HTML 等边界情况。

---

### 5. `tests/conftest.py`

**文件路径**：`tests/conftest.py`

**审查焦点**：

- **Fixture**：与 `test_main.py` 的配合；`MINIMAL_JPEG` 等共享数据是否仍满足当前 EPUB/图片逻辑。
- **作用域与清理**：是否有全局或 session 级 fixture 影响并行或顺序执行；临时目录/文件的清理。

---

### 6. `scripts/rss_job.py`

**文件路径**：`scripts/rss_job.py`

**审查焦点**：

- **与 rss_worker 的关系**：本脚本为「单次执行」版本，与 `rss_worker.py`（长驻）共用 `config/rss_seen.txt` 等时的并发与一致性。
- **配置与参数**：`config/rss_feeds.txt` 与命令行参数；缺失文件、空列表时的退出码与提示。
- **错误处理**：单条 URL 失败是否影响后续；日志是否足够定位问题。

---

### 7. `extension/popup.js` 与 `extension/options.js`

**文件路径**：`extension/popup.js`、`extension/options.js`（可拆成两次审查，每次一个文件）

**审查焦点**：

- **popup.js**：对后端 URL 的拼接与请求；响应解析与错误展示；是否存在 XSS（如将未转义的后端返回内容写入 DOM）。
- **options.js**：后端 URL 的保存与读取；是否校验 URL 格式或协议。

---

### 8. `extension/manifest.json`

**文件路径**：`extension/manifest.json`

**审查焦点**：

- **权限**：声明的权限是否与 popup/options 实际行为一致；是否有多余权限。
- **Manifest 版本**：V3 的合规性；content_scripts、host_permissions 等是否与文档一致。

---

### 9. `requirements.txt`

**文件路径**：`requirements.txt`

**审查焦点**：

- **版本范围**：上下限是否与当前代码兼容；是否存在已知漏洞的版本范围（可结合 CVE 或安全公告）。
- **依赖数量**：是否有可合并或可选的包；是否缺少运行或测试必需的包（如 pytest）。

---

### 10. `.gitignore`

**文件路径**：`.gitignore`

**审查焦点**：

- **敏感与产出**：是否忽略 `.env`、`output/`、`logs/`、`feeds.json`、`*.epub`、PID 文件等；是否可能误提交密钥或大文件。

---

## 审查完成后的汇总建议

当所有单文件审查完成后，建议第三方 AI 或人工再做一次**跨文件**汇总，重点包括：

- **main.py ↔ admin_ui.py**：任务 API 与 Dashboard 的契约是否一致；健康检查与 PID 管理是否与 uvicorn 实际行为一致。
- **main.py ↔ rss_worker.py**：`/parse-url` 的调用方式与重试策略；backend 不可用时的整体行为。
- **配置与安全**：`.env`、`feeds.json` 在 main、admin_ui、rss_worker 中的使用是否统一；是否存在未授权访问或敏感信息泄露风险。
- **部署**：与 `DEPLOYMENT.md`、`DEPLOYABILITY_REVIEW.md` 的结论是否一致；是否还有未文档化的假设（如工作目录、端口）。

将上述汇总整理成简短报告，便于后续按优先级修改代码或文档。
