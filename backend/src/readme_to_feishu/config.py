"""Load settings from environment (.env and env vars)."""

from __future__ import annotations

import os
from pathlib import Path

# Load .env from backend root if present
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path)


def _str(key: str, default: str = "") -> str:
    return (os.environ.get(key) or "").strip() or default


# Feishu
FEISHU_APP_ID = _str("FEISHU_APP_ID")
FEISHU_APP_SECRET = _str("FEISHU_APP_SECRET")
FEISHU_FOLDER_TOKEN = _str("FEISHU_FOLDER_TOKEN") or None
FEISHU_DOC_BASE_URL = _str("FEISHU_DOC_BASE_URL")

# LLM (OpenAI)
OPENAI_API_KEY = _str("OPENAI_API_KEY")
LLM_MODEL = _str("LLM_MODEL") or "gpt-4o-mini"

# Data dir
README_TO_FEISHU_DATA_DIR = _str("README_TO_FEISHU_DATA_DIR")
