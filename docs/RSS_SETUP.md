# TOKINDLE — RSS 自动化配置

RSS 脚本会定时拉取配置的 RSS 源，把每篇文章的链接发给后端 `POST /parse-url`，自动转 EPUB 并可选发到 Kindle。与 Chrome 扩展、iOS 快捷指令解耦，仅依赖同一套 API。

---

## 1. 前提

- 后端已启动（如 `uvicorn main:app --host 0.0.0.0 --port 8000`）
- 已安装依赖：`pip install -r requirements.txt`（含 `feedparser`）

---

## 2. 配置 RSS 源

1. 复制示例配置并编辑：

   ```bash
   cp config/rss_feeds.txt.example config/rss_feeds.txt
   # 编辑 config/rss_feeds.txt，每行一个 RSS 地址，# 开头为注释
   ```

2. 微信公众号本身不提供 RSS，需使用第三方聚合或自建桥接，例如：
   - 瓦斯阅读、RSSHub、WeRSS 等提供的公众号 RSS 链接
   - 任何输出标准 RSS/Atom、且每条包含文章 URL 的 feed 均可

---

## 3. 运行方式

**手动跑一次：**

```bash
# 使用默认 config/rss_feeds.txt、config/rss_seen.txt
python scripts/rss_job.py

# 指定后端地址（默认 http://127.0.0.1:8000）
TOKINDLE_BACKEND_URL=http://192.168.1.100:8000 python scripts/rss_job.py

# 自定义配置与状态文件、每源最多处理条数
python scripts/rss_job.py --config config/rss_feeds.txt --state config/rss_seen.txt --max-per-feed 10
```

**每次运行会：**

- 读取 `config/rss_feeds.txt` 中的 feed 列表
- 拉取每个 feed，取每条条目的链接（每条条目只用第一个 link）
- 若链接不在 `config/rss_seen.txt` 中，则 `POST /parse-url` 发给后端，成功后把该 URL 追加进 `rss_seen.txt`，避免重复发送
- 每个 feed 每次最多处理 `--max-per-feed` 条（默认 10），避免首次运行一次性处理过多

---

## 4. 定时执行（Mac）

**cron（每小时）：**

```bash
crontab -e
# 添加（请把 /path/to/tokindle 换成实际路径）：
0 * * * * cd /path/to/tokindle && /path/to/tokindle/venv/bin/python scripts/rss_job.py >> /path/to/tokindle/logs/rss_job.log 2>&1
```

**launchd（推荐，每小时）：**

1. 创建 `~/Library/LaunchAgents/com.tokindle.rss.plist`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.tokindle.rss</string>
  <key>ProgramArguments</key>
  <array>
    <string>/path/to/tokindle/venv/bin/python</string>
    <string>/path/to/tokindle/scripts/rss_job.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/path/to/tokindle</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>0</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>/path/to/tokindle/logs/rss_job.out.log</string>
  <key>StandardErrorPath</key>
  <string>/path/to/tokindle/logs/rss_job.err.log</string>
</dict>
</plist>
```

2. 加载：

```bash
mkdir -p /path/to/tokindle/logs
launchctl load ~/Library/LaunchAgents/com.tokindle.rss.plist
```

`StartCalendarInterval` 的 `Hour`/`Minute` 可改，例如每小时整点可设多个间隔或改用 `StartInterval`（秒）。

---

## 5. 参数与环境变量

| 选项 / 环境变量 | 说明 |
|----------------|------|
| `--config` |  feed 列表文件路径，默认 `config/rss_feeds.txt` |
| `--state` | 已处理 URL 状态文件，默认 `config/rss_seen.txt` |
| `--max-per-feed` | 每个 feed 每次运行最多处理几条，默认 10 |
| `TOKINDLE_BACKEND_URL` | 后端地址，默认 `http://127.0.0.1:8000` |

---

## 6. 清空已处理记录（重新发送）

若希望某批 URL 重新走一遍流程，可编辑或清空状态文件：

```bash
# 清空全部
echo -n "" > config/rss_seen.txt

# 或手动删除其中若干行
```

下次运行时会重新向这些 URL 发送 `POST /parse-url`。
