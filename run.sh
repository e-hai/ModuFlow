#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo "          ⚡ 启动 ModuFlow AI 产品研发工作流平台            "
echo "=========================================================="

# 1. 确保环境与数据库
mkdir -p data/snapshots

# 2. 捕获中断信号退出子进程
trap 'echo "正在停止服务..."; kill 0' SIGINT SIGTERM EXIT

# 3. 启动 FastAPI 后端
echo "▶ 正在启动后端 API 服务 (http://127.0.0.1:8000)..."
PYTHONPATH=. backend/.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!

# 等待后端就绪
sleep 1.5

# 4. 启动 Vite 前端
echo "▶ 正在启动前端 Web 界面 (http://localhost:5173)..."
cd frontend
npm run dev -- --host &
FRONTEND_PID=$!

echo ""
echo "=========================================================="
echo "  🚀 ModuFlow 平台已就绪："
echo "  • 前端工作台: http://localhost:5173"
echo "  • 后端接口文档: http://127.0.0.1:8000/docs"
echo "  按 Ctrl+C 退出所有服务"
echo "=========================================================="

wait
