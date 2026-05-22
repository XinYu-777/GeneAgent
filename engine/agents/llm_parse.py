"""解析 DeepSeek 返回的 actions JSON。"""

from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter

from engine.schemas import Action, FactionId
from engine.state import GameState
from engine.verifier import verify_action

_action_adapter = TypeAdapter(Action)


def parse_llm_response(
    payload: dict[str, Any],
    faction: FactionId,
    state: GameState,
    *,
    max_actions: int = 3,
) -> tuple[str, list[Action]]:
    reasoning = str(payload.get("reasoning", "")).strip() or "（无说明）"
    raw_actions = payload.get("actions") or []
    if not isinstance(raw_actions, list):
        raw_actions = []

    valid: list[Action] = []
    for item in raw_actions[:max_actions]:
        if not isinstance(item, dict):
            continue
        item = dict(item)
        item["faction"] = faction.value
        try:
            action = _action_adapter.validate_python(item)
        except Exception:
            continue
        if verify_action(state, action).accepted:
            valid.append(action)

    return reasoning, valid
