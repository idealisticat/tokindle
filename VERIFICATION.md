# TOKINDLE — 手动验证步骤

按下面顺序做一遍即可确认 Chrome 扩展、iOS 快捷指令与 Send to Kindle 工作正常。

---

## 1. 启动后端（二选一）

**方式 A（推荐）**  
```bash
./start.sh
```  
浏览器会打开 Admin UI。在**侧边栏**点击 **Start** 启动 FastAPI，看到 🟢 Running 即表示后端已就绪。

**方式 B**  
```bash
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

本机访问 http://127.0.0.1:8000/ping 应返回 `{"ping":"pong"}`。  
手机验证前：确认 Mac 与手机**同一 Wi‑Fi**，手机浏览器访问 `http://Mac的IP:8000/ping` 也返回 pong（Mac IP 可用 `ipconfig getifaddr en0` 查看）。

---

## 2. Chrome 扩展

1. Chrome 打开 `chrome://extensions/` → 开启「开发者模式」→「加载已解压的扩展程序」→ 选项目里的 **`extension`** 目录。
2. 扩展选项里 **Backend URL** 填 `http://127.0.0.1:8000`（本机默认即可）。
3. 打开**任意一篇微信公众号文章**（浏览器打开链接），点击扩展图标 → **Convert to EPUB**。
4. **通过条件**：popup 显示成功、带保存路径；项目下 **`output/`** 里出现新的 `.epub` 文件（文件名含时间戳）。用阅读器打开 EPUB 检查标题、正文、图片正常。

---

## 3. iOS 快捷指令

1. 按 **docs/SHORTCUT_IOS.md** 或 **docs/iOS_SHORTCUT_SETUP.md** 新建快捷指令；**URL** 填 `http://Mac的IP:8000/parse-url`（端口 8000，不要漏掉 `/parse-url`），方法 **POST**，Body **JSON**：`{"url": "剪贴板或输入的链接"}`。
2. 在微信里复制一篇公众号文章链接，运行该快捷指令。
3. **通过条件**：返回内容里含 `"success": true` 和 `"path": "..."`；在 Mac 的 **`output/`** 里能看到新生成的 `.epub`。

---

## 4. Send to Kindle（可选）

若已配置 **`.env`**（可复制 `.env.example` 再填 SMTP 与 `KINDLE_EMAIL`）：  
用扩展或快捷指令转一篇后，响应里 `email_sent` 应为 `true`，`email_error` 为 `null`；稍后在 Kindle 设备/App 中能看到该文档且无 E999。  
未配置时 EPUB 仍会生成并写入 `output/`，仅不发邮件。

---

## 5. 验收清单

| 项 | 通过标准 |
|----|----------|
| 后端 | `/ping` 返回 `{"ping":"pong"}` |
| Chrome 扩展 | 微信文章页点 Convert，popup 成功，`output/` 有对应 epub |
| iOS 快捷指令 | 同 Wi‑Fi 下运行快捷指令，返回 success，`output/` 有 epub |
| Send to Kindle | 已配置 .env 时，`email_sent: true`，Kindle 收到且无 E999 |

---

## 6. 常见问题

- **扩展连不上**：确认后端已启动，Backend URL 为 `http://127.0.0.1:8000`（或当前机器 IP）。
- **手机访问不了**：同一 Wi‑Fi、后端用 `--host 0.0.0.0`（Admin UI 里 Start 即为此配置）。
- **422**：链接非微信文章或页面无正文容器，换一篇标准公众号文章。
- **发 Kindle 失败**：看响应里 `email_error`；检查 .env、Gmail 应用专用密码、`KINDLE_EMAIL` 是否在亚马逊里已批准。

以上全部通过即表示 Phase 2（Chrome 扩展）与 Phase 3（iOS 快捷指令）验证完成。
