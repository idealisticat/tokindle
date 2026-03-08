# TOKINDLE — 待办 / 后续可做

---

## 服务上云（让别人也能用）

先不做了，以后要做时按下面步骤来。

### 1. 选云

- **VPS**：阿里云 ECS、腾讯云 CVM、DigitalOcean、Linode、Vultr 等，买一台 Linux（如 Ubuntu），有公网 IP。
- **PaaS**：Railway、Render、Fly.io 等，代码连 Git 自动部署；需确认是否支持多进程（FastAPI + Streamlit + RSS Worker）。

推荐先用 **一台 VPS** 跑全栈。

### 2. 服务器上要做的事

1. 装 Python 3.9+、Git（如 Ubuntu：`apt install python3 python3-venv git`）。
2. 从 GitHub 克隆仓库到服务器。
3. 项目目录下：建 venv、`pip install -r requirements.txt`（或 `./start.sh` 只做到装依赖为止）。
4. 在服务器上**新建** `.env`，填 SMTP、Kindle 邮箱等（不要从本地上传）。
5. 用 **systemd** 把 FastAPI（uvicorn）和 RSS Worker 做成两个 service，开机自启、崩溃重启；Admin UI（Streamlit）可选常驻或需要时再开。
6. 防火墙开放 8000（FastAPI），若对外提供 Admin UI 再开 8501；或只开 80/443，用 Nginx 反代。

### 3. 让别人能访问

- **域名**：买域名，A 记录指到服务器公网 IP。
- **Nginx**：装 Nginx（或 Caddy），监听 80/443，把请求转发到本机 `127.0.0.1:8000`（及可选的 8501）。
- **HTTPS**：用 Let’s Encrypt（如 certbot）为域名申请证书。
- 别人在 Chrome 扩展 / iOS 快捷指令里把 **Backend URL** 改成 `https://你的域名` 即可使用。

### 4. 安全（必做）

- Admin UI 和 FastAPI 目前都**没有登录**，谁拿到地址谁就能用。
- 要么：**不对外暴露 Admin UI**，只暴露 8000（API）；要么用 **Nginx Basic Auth**（或 Caddy basicauth）给 Admin UI 和/或 API 加账号密码；或 Nginx 限制只允许指定 IP 访问。

### 5. 别人怎么用

- 你提供 API 地址（如 `https://tokindle.你的域名.com`）。
- 对方在扩展 / 快捷指令里填这个地址即可；转文章、发 Kindle 会走你服务器上的 .env 配置（你的 SMTP、你的 Kindle 邮箱）。若要做「每人自己的 Kindle 邮箱」需要再做多用户/配置隔离。

### 6. 顺序小结

1. 代码 push 到 GitHub。
2. 买/选云服务器（VPS 或支持多进程的 PaaS）。
3. 服务器：装环境 → 克隆仓库 → 配 .env → systemd 跑 uvicorn + rss_worker（+ 可选 Streamlit）。
4. 配域名 + Nginx 反代 + HTTPS。
5. 做访问控制（Basic Auth 或只暴露 API）。
6. 把 API 地址发给别人，让他们在扩展/快捷指令里填写。

详细可参考项目里的 **DEPLOYMENT.md**（含 systemd 示例）、**DEPLOYABILITY_REVIEW.md**（跨服务器部署注意点）。
