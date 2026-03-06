# TOKINDLE — 手动验证方案（Phase 2 & Phase 3）

请按下列步骤**亲自**验证 Chrome 扩展与 iOS 快捷指令是否工作正常。

---

## 一、前置条件（必做）

1. **后端已启动**
   - 仅本机调试（如 Chrome 扩展）：`uvicorn main:app --reload`
   - **需要手机访问时（iOS 快捷指令）**：`uvicorn main:app --reload --host 0.0.0.0 --port 8000`，或直接执行项目根目录下的 **`./run_lan.sh`**（会打印本机 IP 供手机访问）。
   ```bash
   cd /Users/idealisticatte/cursor_app/tokindle
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   # 或：./run_lan.sh
   ```
   浏览器打开 http://127.0.0.1:8000/docs 能看到 Swagger 即表示正常。

2. **确认 /ping 正常**
   - 本机：http://127.0.0.1:8000/ping  
   - 手机（与 Mac 同 Wi‑Fi 时）：http://你的Mac的IP:8000/ping  
   - 应返回：`{"ping":"pong"}`

---

## 二、Phase 2：Chrome 扩展验证

### 2.1 安装扩展

1. Chrome 地址栏输入：`chrome://extensions/`
2. 右上角打开 **「开发者模式」**
3. 点击 **「加载已解压的扩展程序」**
4. 选择本项目的 **`extension`** 文件夹（路径应包含 `manifest.json`）
5. 确认扩展列表中出现 **TOKINDLE**，无报错。

### 2.2 设置后端地址（可选）

1. 点击 TOKINDLE 扩展的 **「详细信息」**
2. 在扩展详情页找到 **「扩展程序选项」** 并打开（若无此入口，可点击扩展图标后通过 popup 里的「Set backend URL」打开）
3. **Backend URL** 填写：`http://127.0.0.1:8000`（若后端在本机且端口为 8000）
4. 保存

### 2.3 验证「当前页转 EPUB」

1. 在 Chrome 中打开**一篇微信公众号文章**（例如从微信复制链接到浏览器打开，或用 `https://mp.weixin.qq.com/s/...` 任意一篇）
2. 点击浏览器工具栏的 **TOKINDLE 扩展图标**，弹出 popup
3. 点击 **「Convert to EPUB」**
4. **预期**：
   - 几秒内 popup 中显示绿色成功信息
   - 文案中包含 `Saved:` 和一条**绝对路径**（例如 `/Users/.../tokindle/output/xxx.epub`）
   - 打开该路径对应目录，应能看到新生成的 `.epub` 文件
5. 用 Mac 自带的「图书」或其它阅读器打开该 EPUB，确认**标题与正文、图片**正常

### 2.4 异常情况自测（可选）

- 后端未启动时点击「Convert to EPUB」→ 应显示网络/连接错误（红色）。
- 在 `chrome://extensions/` 等禁止脚本的页面点击 → 应提示无法读取页面。

---

## 三、Phase 3：iOS 快捷指令验证（局域网方案）

### 3.1 让手机能访问到后端（同一 Wi‑Fi）

1. 在 Mac 上以后台可被局域网访问的方式启动：
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
2. 查看 Mac 的局域网 IP（任选一种）：
   - 系统设置 → 网络 → Wi‑Fi → 详情 → IP 地址
   - 终端执行：`ipconfig getifaddr en0`（多为 `192.168.x.x`）
3. 手机连接**与 Mac 相同的 Wi‑Fi**，在手机浏览器打开：`http://Mac的IP:8000/ping`  
   应返回 `{"ping":"pong"}`。

**若需在外网或非同一 Wi‑Fi 下使用**：可选用 ngrok 等内网穿透，见 `docs/SHORTCUT_IOS.md` 末尾「可选：内网穿透」。

### 3.2 按文档配置快捷指令

1. 打开 **docs/SHORTCUT_IOS.md**（中文）或 **docs/iOS_SHORTCUT_SETUP.md**（英文详细步骤），按其中步骤新建快捷指令。
2. **URL** 填：`http://你的Mac局域网IP:8000/parse-url`（例如 `http://192.168.1.10:8000/parse-url`，不要漏掉 `/parse-url`）
3. 方法 **POST**，请求头 **Content-Type: application/json**，请求体 **JSON**：`{"url": "这里用剪贴板或输入的链接变量"}`

### 3.3 验证「链接转 EPUB」

1. 在微信中打开任意一篇公众号文章 → 右上角 **「…」** → **「复制链接」**
2. 运行刚建的快捷指令（若配置为「询问输入」则粘贴链接后确定）
3. **预期**：
   - 快捷指令返回内容为 JSON，其中包含 `"success": true` 和 `"path": "..."`、`"title": "..."`
   - 在**运行后端的 Mac** 上打开 `output/` 目录，应能看到新生成的 `.epub` 文件（文件名与标题对应）
4. 将生成的 EPUB 拷到手机或用其它方式打开，确认内容、图片正常

### 3.4 异常情况自测（可选）

- URL 填错或未带 `/parse-url` → 应得到 404 或连接失败。
- 请求体不是合法 JSON 或缺少 `url` → 后端可能返回 422，快捷指令中会看到对应错误信息。
- 手机与 Mac 不在同一 Wi‑Fi 或 Mac 未用 `--host 0.0.0.0` → 手机无法访问，可改用内网穿透（见文档）。

---

## 四、验收清单（可打勾）

| 项目 | 说明 | 结果 |
|------|------|------|
| 后端 /ping | 浏览器访问 /ping 返回 pong | ☐ |
| 后端 /parse-url | 在 /docs 里用 POST /parse-url 发链接，返回 success 且 output/ 有 epub | ☐ |
| 后端 /parse-html | 在 /docs 里用 POST /parse-html 发 title+html_content，返回 success 且 output/ 有 epub | ☐ |
| Chrome 扩展安装 | 加载 extension 文件夹无报错 | ☐ |
| Chrome 扩展转换 | 在微信文章页点击扩展并 Convert，popup 显示成功且 output/ 有对应 epub | ☐ |
| Chrome 扩展选项 | 可打开选项页并保存 Backend URL | ☐ |
| iOS 快捷指令配置 | 按 SHORTCUT_IOS.md 建好快捷指令（URL 为 Mac 局域网 IP） | ☐ |
| iOS 快捷指令运行 | 手机与 Mac 同 Wi‑Fi，复制微信链接后运行快捷指令，返回 success 且 Mac 上 output/ 有 epub | ☐ |

---

## 五、问题排查

- **扩展提示无法连接**：检查 Backend URL 是否为 `http://127.0.0.1:8000`（本机）且后端已启动；若后端在别机，填该机 IP 或域名。
- **扩展在部分页面无反应**：Chrome 限制在 `chrome://`、`edge://` 等页面注入脚本，请用普通网页（如微信文章在浏览器打开的页面）测试。
- **iOS 无法访问**：确认手机与 Mac **同一 Wi‑Fi**，且后端启动时加了 **`--host 0.0.0.0`**；快捷指令 URL 为 `http://Mac的IP:8000/parse-url`。若需在外网使用，见 `docs/SHORTCUT_IOS.md` 的「可选：内网穿透」。
- **返回 422**：多为链接不是微信文章或 HTML 中无正文容器，换一篇标准公众号文章再试。

完成上述验证后，Phase 2 与 Phase 3 即可视为通过。
