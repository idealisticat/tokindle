#!/usr/bin/env bash
# 允许局域网访问（同一 Wi‑Fi 下手机可访问）。用于 iOS 快捷指令等。
# 使用：./run_lan.sh  或  bash run_lan.sh
cd "$(dirname "$0")"
echo "TOKINDLE: 启动后端（监听 0.0.0.0:8000，手机可通过 Mac 的局域网 IP 访问）"
echo "本机: http://127.0.0.1:8000/docs  手机: http://$(ipconfig getifaddr en0 2>/dev/null || echo 'Mac的IP'):8000/ping"
exec uvicorn main:app --reload --host 0.0.0.0 --port 8000
