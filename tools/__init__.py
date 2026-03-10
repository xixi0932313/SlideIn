# SlideIn Agent - 工具
from __future__ import annotations

import os
from pathlib import Path


def get_tools_for_agent() -> list:
    return []


def invoke_tool(name: str, **kwargs: object) -> dict:
    if name == "recommend_style":
        return [
            {"name": "简约蓝", "preview": "蓝色主调，适合汇报"},
            {"name": "学术风", "preview": "白底深灰，适合答辩"},
            {"name": "商务", "preview": "深色标题栏，适合路演"},
        ]
    if name == "render_pptx":
        slide_deck = kwargs.get("slide_deck")
        out_dir = Path(os.getenv("SLIDEIN_OUTPUT_DIR", ".")).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "SlideIn_export.pptx"
        try:
            with open(path, "wb") as f:
                f.write(b"")
            return {"success": True, "file_url": str(path)}
        except Exception as e:
            return {"success": False, "message": str(e)}
    if name == "render_docx":
        out_dir = Path(os.getenv("SLIDEIN_OUTPUT_DIR", ".")).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "SlideIn_export.docx"
        try:
            with open(path, "wb") as f:
                f.write(b"")
            return {"success": True, "file_url": str(path)}
        except Exception as e:
            return {"success": False, "message": str(e)}
    return {}
