# TOKINDLE Chrome Extension (Manifest V3)

把当前标签页的 HTML 发给 TOKINDLE 后端，在服务器上生成 EPUB 并保存到 `output/`。

## 安装（开发者模式）

1. Chrome 打开 `chrome://extensions/`
2. 开启「开发者模式」
3. 「加载已解压的扩展程序」→ 选择本 **extension** 文件夹（含 `manifest.json` 的目录）

## 使用

1. 确保后端已启动（默认 `http://127.0.0.1:8000`）
2. 打开要转换的页面（如微信公众号文章）
3. 点击扩展图标 → **Convert to EPUB**
4. 若需修改后端地址：点击 **Set backend URL** 打开选项页

## 文件说明

- `manifest.json` — 扩展配置（Manifest V3）
- `popup.html` / `popup.js` — 弹窗 UI 与调用 `/parse-html` 逻辑
- `options.html` / `options.js` — 后端 URL 设置
- `icons/128.png` — 扩展图标
