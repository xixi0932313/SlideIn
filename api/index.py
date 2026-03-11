# Vercel Serverless 入口：直接导出 FastAPI app（Vercel 原生支持 ASGI）
from __future__ import annotations

import sys
from pathlib import Path

# 确保项目根目录在 path 中（Vercel 运行时可能从 api/ 目录执行）
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from web import app

# Vercel Python 运行时支持直接导出 ASGI app，无需 Mangum
