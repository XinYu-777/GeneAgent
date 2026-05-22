"""DeepSeek API（OpenAI 兼容）。"""

from __future__ import annotations

import json
import os
from typing import Any

# 可选：从项目根目录 .env 加载（勿提交 .env）
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"


def get_deepseek_api_key() -> str | None:
    return os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")


def is_llm_configured() -> bool:
    return bool(get_deepseek_api_key())


def get_model() -> str:
    return os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL)


async def chat_json(system: str, user: str) -> dict[str, Any]:
    """调用 DeepSeek，要求返回 JSON 对象。"""
    api_key = get_deepseek_api_key()
    if not api_key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY")

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)
    response = await client.chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.4,
    )
    content = response.choices[0].message.content or "{}"
    return json.loads(content)
