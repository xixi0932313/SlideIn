# Vercel Serverless 入口：用 Mangum 把 FastAPI 转为 serverless handler
from __future__ import annotations

import sys
from pathlib import Path

# 确保项目根目录在 path 中（Vercel 运行时可能从 api/ 目录执行）
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from mangum import Mangum
from web import app

handler = Mangum(app, lifespan="off")
