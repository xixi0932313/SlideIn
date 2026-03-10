# SlideIn Agent - 配置
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass


@dataclass
class AgentConfig:
    openai_api_base: str = ""
    openai_api_key: str = ""
    model_chat: str = "deepseek-chat"
    model_reasoner: str = "deepseek-reasoner"
    model_vision: str = "deepseek-v3"
    max_questions_per_turn: int = 2
    skip_keywords: tuple = ("跳过", "使用默认值", "默认值", "默认")
    enable_web_search: bool = True
    enable_document_parse: bool = True
    enable_parse_image: bool = True
    enable_generate_image: bool = True
    enable_parse_video: bool = True
    enable_asr: bool = True
    tavily_api_key: str = ""
    fal_api_key: str = ""
    whisper_mode: str = "local"
    open_file_after_export: bool = True


def load_config() -> AgentConfig:
    api_base = os.getenv("DEEPSEEK_API_BASE") or os.getenv("OPENAI_API_BASE", "https://api.deepseek.com")
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    return AgentConfig(
        openai_api_base=api_base.rstrip("/"),
        openai_api_key=api_key,
        model_chat=os.getenv("MODEL_CHAT", "deepseek-chat"),
        model_reasoner=os.getenv("MODEL_REASONER", "deepseek-reasoner"),
        model_vision=os.getenv("MODEL_VISION", "deepseek-v3"),
        max_questions_per_turn=int(os.getenv("MAX_QUESTIONS_PER_TURN", "2")),
        enable_web_search=os.getenv("ENABLE_WEB_SEARCH", "true").lower() == "true",
        enable_document_parse=os.getenv("ENABLE_DOCUMENT_PARSE", "true").lower() == "true",
        enable_parse_image=os.getenv("ENABLE_PARSE_IMAGE", "true").lower() == "true",
        enable_generate_image=os.getenv("ENABLE_GENERATE_IMAGE", "true").lower() == "true",
        enable_parse_video=os.getenv("ENABLE_PARSE_VIDEO", "true").lower() == "true",
        enable_asr=os.getenv("ENABLE_ASR", "true").lower() == "true",
        tavily_api_key=os.getenv("TAVILY_API_KEY", ""),
        fal_api_key=os.getenv("FAL_API_KEY", ""),
        whisper_mode=os.getenv("WHISPER_MODE", "local").lower(),
        open_file_after_export=os.getenv("OPEN_FILE_AFTER_EXPORT", "true").lower() == "true",
    )
