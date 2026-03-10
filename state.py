# SlideIn Agent - 状态与槽位
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel


class AgentState(str, Enum):
    INIT = "INIT"
    REQUIREMENT_GATHERING = "REQUIREMENT_GATHERING"
    OUTLINE_PREVIEW = "OUTLINE_PREVIEW"
    CONTENT_GENERATING = "CONTENT_GENERATING"
    REVIEW_EDIT = "REVIEW_EDIT"
    EXPORT = "EXPORT"
    END = "END"


SLOT_SPEC = {
    "topic": {"meaning": "PPT 主题", "default": ""},
    "purpose": {"meaning": "用途（课程/竞赛/答辩/其他）", "default": "课程汇报"},
    "audience": {"meaning": "受众", "default": "老师+同学"},
    "length": {"meaning": "页数", "default": "10-15页"},
    "language": {"meaning": "语言", "default": "中文"},
    "focus": {"meaning": "侧重（概念/案例/数据等）", "default": "概念+案例"},
    "need_web_search": {"meaning": "是否需要联网查资料", "default": False},
}


class Slots(BaseModel):
    topic: str = ""
    purpose: str = ""
    audience: str = ""
    length: str = ""
    language: str = "中文"
    focus: str = ""
    need_web_search: Any = False

    def missing_any(self) -> list[str]:
        required = ["topic", "purpose"]
        return [k for k in required if not getattr(self, k, None)]

    def missing_required(self) -> list[str]:
        return self.missing_any()

    def apply_defaults(self) -> None:
        for k, v in SLOT_SPEC.items():
            if not getattr(self, k, None):
                setattr(self, k, v["default"])
