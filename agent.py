# SlideIn Agent - 主逻辑
from __future__ import annotations

import json
import re
from typing import Any, Optional

from openai import OpenAI

try:
    from .config import AgentConfig, load_config
    from .state import AgentState, SLOT_SPEC, Slots
    from .tools import invoke_tool, get_tools_for_agent
except ImportError:
    from config import AgentConfig, load_config
    from state import AgentState, SLOT_SPEC, Slots
    from tools import invoke_tool, get_tools_for_agent


def _open_file(path: str) -> None:
    try:
        import subprocess
        import sys
        if sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
        elif sys.platform == "win32":
            subprocess.run(["start", "", path], shell=True, check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)
    except Exception:
        pass


class SlideInAgent:
    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or load_config()
        self.client = None
        if OpenAI and self.config.openai_api_key:
            self.client = OpenAI(
                base_url=f"{self.config.openai_api_base}/v1",
                api_key=self.config.openai_api_key,
            )
        self.state = AgentState.INIT
        self.slots = Slots()
        self.messages: list[dict[str, str]] = []
        self.outline: Any = None
        self.slide_deck: Any = None
        self.last_export_paths: list[dict[str, str]] = []
        self._tools = get_tools_for_agent()

    def _extract_slots_from_user(self, user_text: str) -> None:
        if self.client:
            self._extract_slots_via_llm(user_text)
        else:
            self._extract_slots_simple(user_text)

    def _extract_slots_simple(self, user_text: str) -> None:
        t = user_text.strip()
        if not t:
            return
        for pattern in [r"关于[「\s]*([^」\s]+)", r"做一个[「\s]*([^」\s，。]+)", r"做一份[「\s]*([^」\s，。]+)", r"主题[是为：]\s*([^，。]+)"]:
            m = re.search(pattern, t)
            if m and not self.slots.topic:
                self.slots.topic = m.group(1).strip()
                break
        if "课程" in t or "汇报" in t:
            self.slots.purpose = self.slots.purpose or "课程汇报"
        if "老师" in t or "同学" in t:
            self.slots.audience = self.slots.audience or "老师+同学"
        if re.search(r"\d+页", t):
            self.slots.length = re.search(r"(\d+页)", t).group(1)
        if "中文" in t:
            self.slots.language = "中文"
        if "概念" in t or "案例" in t:
            self.slots.focus = self.slots.focus or "概念+案例"

    def _extract_slots_via_llm(self, user_text: str) -> None:
        if not self.client:
            return
        slot_list = "\n".join(f"- {k}: {v['meaning']}, 默认: {v['default']}" for k, v in SLOT_SPEC.items())
        prompt = f"""从下面用户输入中抽取 PPT 需求槽位。只输出 JSON 对象，键为槽位名，值为用户表达的内容；未提及的不要写。
槽位说明：
{slot_list}

用户输入：{user_text}

当前已填槽位：{self.slots.model_dump()}

输出 JSON："""
        try:
            r = self.client.chat.completions.create(
                model=self.config.model_chat,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
            )
            text = (r.choices[0].message.content or "").strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text)
            for k, v in data.items():
                if k in SLOT_SPEC and v is not None and str(v).strip():
                    setattr(self.slots, k, v)
        except Exception:
            pass

    def _is_skip_or_default(self, text: str) -> bool:
        return text.strip() in self.config.skip_keywords or "跳过" in text or "默认" in text

    def _ask_for_missing_slots(self, max_n: int = 2) -> list[str]:
        missing = self.slots.missing_any()
        return missing[:max_n]

    def _run_outline(self) -> None:
        topic = self.slots.topic or "未命名"
        self.outline = [
            {"title": f"{topic} - 封面", "points": ["副标题", "基本信息"]},
            {"title": "目录", "points": ["第一章", "第二章", "第三章"]},
            {"title": "核心内容", "points": ["要点一", "要点二", "总结"]},
        ]

    def _format_outline_reply(self) -> str:
        if not self.outline:
            return "大纲生成完成。"
        lines = ["大纲预览："]
        for s in self.outline:
            lines.append(f"- {s.get('title', '')}: {', '.join(s.get('points', []))}")
        return "\n".join(lines) + "\n\n请确认大纲后回复「确认」或「生成」开始生成正文。"

    def _run_content(self) -> None:
        self.slide_deck = {"slides": self.outline or []}

    def _format_content_summary(self) -> str:
        n = len(self.slide_deck.get("slides", [])) if self.slide_deck else 0
        return f"{n} 页"

    def turn(self, user_input: str) -> str:
        user_input = (user_input or "").strip()
        self.messages.append({"role": "user", "content": user_input})

        if self._is_skip_or_default(user_input):
            self.slots.apply_defaults()
            self.state = AgentState.REQUIREMENT_GATHERING
            if not self.slots.missing_required():
                self.state = AgentState.OUTLINE_PREVIEW
                self._run_outline()
                reply = self._format_outline_reply()
                self.messages.append({"role": "assistant", "content": reply})
                return reply

        self._extract_slots_from_user(user_input)

        if self.state == AgentState.INIT:
            self.state = AgentState.REQUIREMENT_GATHERING

        if self.state == AgentState.REQUIREMENT_GATHERING:
            missing_required = self.slots.missing_required()
            if not missing_required:
                self.slots.apply_defaults()
                self.state = AgentState.OUTLINE_PREVIEW
                self._run_outline()
                reply = self._format_outline_reply()
            else:
                missing = missing_required[: self.config.max_questions_per_turn]
                qs = [f"- {SLOT_SPEC[m]['meaning']}（槽位：{m}）" for m in missing]
                reply = "为了更好为您生成 PPT，请补充：\n" + "\n".join(qs)
            self.messages.append({"role": "assistant", "content": reply})
            return reply

        if self.state == AgentState.OUTLINE_PREVIEW:
            if "确认" in user_input or "生成" in user_input or "好的" in user_input or "可以" in user_input:
                self.state = AgentState.CONTENT_GENERATING
                self._run_content()
                styles = invoke_tool("recommend_style", topic=self.slots.topic or "", purpose=self.slots.purpose or "", audience=self.slots.audience or "")
                reply = "内容已生成（" + self._format_content_summary() + "）。推荐风格：\n" + "\n".join(f"- {s['name']}: {s['preview']}" for s in styles[:3])
                reply += "\n\n如需导出 PPT，请回复「导出」或「导出为 pptx」。"
                self.state = AgentState.REVIEW_EDIT
                self.messages.append({"role": "assistant", "content": reply})
                return reply
            reply = "请确认大纲后回复「确认」或「生成」开始生成正文；如需修改请直接说明。"
            self.messages.append({"role": "assistant", "content": reply})
            return reply

        if self.state == AgentState.REVIEW_EDIT:
            if "导出" in user_input or "pptx" in user_input or "下载" in user_input:
                self.state = AgentState.EXPORT
                if not self.slide_deck:
                    reply = "当前无内容可导出，请先完成内容生成。"
                else:
                    parts = []
                    want_pptx = "word" not in user_input and "docx" not in user_input
                    want_docx = "word" in user_input or "docx" in user_input
                    if not want_docx and not want_pptx:
                        want_pptx = True
                    if want_pptx:
                        out = invoke_tool("render_pptx", slide_deck=self.slide_deck, theme=None)
                        if out.get("success"):
                            url = out.get("file_url", "")
                            parts.append(f"PPT：{url}")
                            self.last_export_paths.append({"url": url, "label": "PPT"})
                            if self.config.open_file_after_export and url:
                                _open_file(url)
                        else:
                            parts.append(f"PPT：{out.get('message', '导出失败')}")
                    if want_docx:
                        out_docx = invoke_tool("render_docx", slide_deck=self.slide_deck)
                        if out_docx.get("success"):
                            url = out_docx.get("file_url", "")
                            parts.append(f"Word：{url}")
                            self.last_export_paths.append({"url": url, "label": "Word"})
                            if self.config.open_file_after_export and url:
                                _open_file(url)
                        else:
                            parts.append(f"Word：{out_docx.get('message', '导出失败')}")
                    reply = "导出完成。\n" + "\n".join(parts)
                self.state = AgentState.END
            else:
                reply = "您可以继续修改内容；回复「导出」生成 .pptx，或「导出 word」生成 .docx。"
            self.messages.append({"role": "assistant", "content": reply})
            return reply

        self.messages.append({"role": "assistant", "content": "当前会话已结束。如需新 PPT，请新建对话。"})
        return "当前会话已结束。如需新 PPT，请新建对话。"
