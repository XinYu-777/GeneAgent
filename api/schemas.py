"""API 请求/响应模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NewGameRequest(BaseModel):
    resolve_all_decisions: bool = False
    use_llm_agents: bool = False
    use_multi_agent: bool = True


class NewGameResponse(BaseModel):
    game_id: str
    snapshot: dict[str, Any]


class AdvanceRequest(BaseModel):
    game_id: str
    use_multi_agent: bool = True
    use_stub_ai: bool = False


class DecisionRequest(BaseModel):
    game_id: str
    intent_id: str | None = None
    text: str | None = None
    use_llm: bool = False


class DecisionResponse(BaseModel):
    directive: dict[str, Any]
    summary: str
    snapshot: dict[str, Any]


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None
    pending_decision: dict[str, Any] | None = None


class AdvanceResponse(BaseModel):
    snapshot: dict[str, Any]


class StateResponse(BaseModel):
    game_id: str
    snapshot: dict[str, Any]
