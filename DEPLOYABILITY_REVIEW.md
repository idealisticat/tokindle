# TOKINDLE — 其他服务器部署易用性审查报告

本文档对项目在「非本机、其他服务器」上部署的易用性与可移植性进行审查，**仅作报告，不修改代码**。

---

## 1. 审查范围与结论概览

| 维度 | 结论 | 说明 |
|------|------|------|
| 路径与工作目录 | 良好 | 使用 `Path(__file__).resolve().parent`，无硬编码绝对路径 |
| 操作系统假设 | 部分依赖 Mac | 文档与 launchd 以 Mac 为主；Linux 需自配 systemd/cron |
| Python 版本 | 需明确 | 未在代码中写死；建议文档统一写 Python 3.9+ |
| 端口与地址 | 可改进 | admin_ui 中 `BACKEND_URL` 写死 `127.0.0.1:8000`，跨机部署需改 |
| 环境变量 | 良好 | 敏感配置走 `.env`，有 `.env.example`，易复现 |
| 多用户/多实例 | 未考虑 | 单机单实例设计；多实例需不同端口与数据目录 |
| Linux 兼容性 | 可行 | 核心逻辑无 Mac 专有 API；进程管理需改用 systemd/supervisor |
| Windows | 未验证 | 路径与 venv 可用；launchd/psutil 子进程在 Windows 上需验证 |
| 安全与访问控制 | 需加固 | Admin UI 与 API 无认证；公网部署需反向代理 + 认证 |

---

## 2. 路径与工作目录

- **结论：良好。**
- 所有关键路径均基于 `Path(__file__).resolve().parent`（main.py 用 `Path("output")` 相对当前工作目录，通常与项目根一致）。
- **注意**：启动方式必须保证「当前工作目录 = 项目根目录」，否则 `output/`、`.env`、`feeds.json`、`logs/` 会错位。文档中已强调 `cwd=str(BASE_DIR)` 与 `WorkingDirectory`，部署时需同样保证。

---

## 3. 操作系统与进程管理

- **现状**：DEPLOYMENT.md 以 **macOS + launchd** 为主；admin_ui.py 通过 **PID 文件 + psutil** 启停进程，与 OS 无关。
- **Linux**：
  - 无 launchd；需自行提供 **systemd** 或 **supervisor** 配置，或只用 cron 跑 `scripts/rss_job.py`（若不用 rss_worker）。
  - `venv` 路径为 `venv/bin/python3`，Linux 通用。
- **建议**：在 DEPLOYMENT.md 中增加「Linux 部署」小节（systemd 示例 + 工作目录约定），便于其他服务器直接复用。

---

## 4. 端口与后端地址

- **admin_ui.py** 中 `BACKEND_URL = "http://127.0.0.1:8000"` 写死。
  - 本机部署：Streamlit 与 FastAPI 同机，无问题。
  - **跨机部署**：若 Streamlit 与 FastAPI 不在同一台机器，需通过环境变量或配置覆盖 `BACKEND_URL`，当前代码未提供入口。
- **main.py** 中 uvicorn 端口由启动参数决定，无硬编码。
- **建议**：在 admin_ui 中优先读取环境变量（如 `TOKINDLE_BACKEND_URL`），缺省再使用 `http://127.0.0.1:8000`，可提升多机/多环境易用性。

---

## 5. Python 版本

- 代码未强制 Python 版本；使用的语法与标准库在 **Python 3.9+** 下均可用。
- DEPLOYMENT.md 写的是「Python 3.10+」，与 requirements 的包兼容性略有不一致（如部分包仍支持 3.9）。
- **建议**：在 README 或 DEPLOYMENT 中统一写「Python 3.9+」，并与 CI/本地测试版本对齐。

---

## 6. 环境变量与配置

- **良好**：`.env` 管理 SMTP 与 Kindle 邮箱；`.env.example` 提供模板；`.gitignore` 排除 `.env`。
- **feeds.json**：路径固定为项目根下的 `feeds.json`；未支持通过环境变量指定路径，单实例足够，多实例需不同项目目录或符号链接。

---

## 7. 多用户 / 多实例

- 未设计多租户或多实例：
  - 任务列表、PID 文件、`output/`、`config/rss_seen.txt`、`feeds.json` 均为单份。
- 若在同一台机器跑多实例，需：
  - 不同端口（如 8000 / 8001）；
  - 不同项目目录（或通过环境变量区分 `output/`、`logs/`、`feeds.json`），当前代码未支持，需改配置或代码。

---

## 8. Linux 部署易用性

- **核心逻辑**：无 macOS 专有调用，Linux 可直接运行。
- **缺口**：
  - 官方文档未提供 systemd unit 示例，部署者需自行编写。
  - `scripts/rss_job.py` 用 cron 即可；`rss_worker.py` 需常驻进程，建议提供 systemd 或 supervisor 示例。
- **建议**：在 DEPLOYMENT.md 中增加「Linux (systemd)」小节，给出 FastAPI、RSS Worker、可选 Streamlit 的 unit 示例，便于其他服务器一键部署。

---

## 9. Windows 部署

- **未验证**：
  - `Path`、venv、相对路径在 Windows 上可用。
  - psutil 终止进程树、subprocess 启动方式在 Windows 上可能与 Unix 有差异。
  - 无 launchd；需用 NSSM、Task Scheduler 或手动启动。
- **建议**：若需支持 Windows，需在 Windows 上做一次启停与 RSS 流程的冒烟测试，并在文档中注明「仅验证过 macOS/Linux」。

---

## 10. 安全与访问控制

- **Admin UI (Streamlit)**：无登录与权限控制；谁都能访问则可能修改 `.env`、feeds、启停服务。
- **FastAPI**：无 API Key 或认证；`/parse-url`、`/parse-html` 对网络内可达者开放。
- **建议**：
  - 公网或不可信网络部署时，将 Admin UI 与 API 置于反向代理（nginx/Caddy）之后，并配置认证（如 Basic Auth、OAuth）。
  - 在 DEPLOYMENT 中增加「安全注意事项」：仅内网可访问时的风险说明，以及推荐「仅本地或 VPN 访问」的用法。

---

## 11. 总结与建议优先级

| 优先级 | 建议 | 说明 |
|--------|------|------|
| 高 | 文档补充 Linux systemd 部署示例 | 显著提升其他服务器部署易用性 |
| 高 | Admin UI 的 BACKEND_URL 支持环境变量 | 便于跨机、多环境部署 |
| 中 | 文档统一 Python 版本说明（如 3.9+） | 避免环境不一致 |
| 中 | DEPLOYMENT 增加安全与访问控制说明 | 避免公网误用 |
| 低 | 多实例/多目录支持（环境变量或配置） | 仅在多实例需求出现时再做 |

**总体**：项目在「单机、本机或内网」部署下易用性良好；路径与配置设计清晰。在其他服务器（尤其 Linux）上部署的主要缺口是**文档与进程管理示例**，以及 Admin UI 后端地址的可配置性；按上表优先级逐步完善即可进一步提升跨服务器部署易用性。
