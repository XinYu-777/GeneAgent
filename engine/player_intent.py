"""玩家自然语言 / 意图卡 → StrategicDirective。"""

from __future__ import annotations

import json
import re

from engine.decision_points import DecisionPoint
from engine.directives import (
    ALLOWED_PRIORITIES,
    build_directive_from_intent,
)
from engine.llm_client import chat_json_sync, is_llm_configured
from engine.schemas import DiplomacyTone, StrategicDirective
from engine.state import GameState

# 不可能在 1941-1945 战略层实现的幻想指令
ILLEGAL_PATTERNS: list[tuple[str, str]] = [
    (r"占领\s*东京|攻占\s*日本|灭日|消灭日本", "1940 年代中国军队不具备直接攻占日本本土的战略条件"),
    (r"立刻统一|马上胜利|一年灭日", "时间表不符合史实与当前国力"),
    (r"核爆|原子弹", "此时期尚无可用核武器决策"),
    (r"投降|投敌", "当前剧本为国民政府抗战路线"),
]

# 关键词 → 意图 id（规则解析，无 LLM 时）
KEYWORD_TO_INTENT: dict[str, list[str]] = {
    "guerrilla_expand": ["游击", "敌后", "持久", "牵制"],
    "hold_core": ["大后方", "西南", "巩固", "收缩", "待机"],
    "seek_allied_aid": ["同盟", "援助", "国际", "求援", "驼峰", "美英"],
    "hold_burma": ["滇缅", "缅甸", "公路", "交通线", "缅甸路"],
    "counteroffensive_huabei": ["反击", "反攻", "华北", "进攻", "有限反击"],
}


class DirectiveRejectError(ValueError):
    """非法或不可执行的玩家决断。"""


def _check_illegal(text: str) -> None:
    for pattern, reason in ILLEGAL_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            raise DirectiveRejectError(reason)


def _allowed_intent_ids(decision_point: DecisionPoint) -> set[str]:
    return {i.id for i in decision_point.suggested_intents}


def parse_nl_rule_based(
    text: str, decision_point: DecisionPoint
) -> StrategicDirective:
    _check_illegal(text)
    allowed = _allowed_intent_ids(decision_point)
    text_l = text.lower()

    best_id: str | None = None
    best_score = 0
    for intent_id, keywords in KEYWORD_TO_INTENT.items():
        if intent_id not in allowed:
            continue
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_id = intent_id

    if best_id is None:
        # 无法匹配时取本决断第一个建议（保守默认）
        best_id = decision_point.suggested_intents[0].id

    return build_directive_from_intent(best_id, decision_point, raw_quote=text.strip())


def parse_nl_with_llm(
    text: str, decision_point: DecisionPoint
) -> StrategicDirective:
    _check_illegal(text)
    allowed = _allowed_intent_ids(decision_point)
    intents_desc = "\n".join(
        f"- {i.id}: {i.label}" for i in decision_point.suggested_intents
    )
    system = """你是抗战战略顾问，将统帅自然语言决断解析为 JSON。
只能输出一个合法 JSON 对象，priority 必须是下列 id 之一，不可幻想行动。"""
    user = (
        f"决断场景：{decision_point.title}\n"
        f"问题：{decision_point.prompt}\n"
        f"玩家原话：{text}\n"
        f"可选 priority（必须其一）：\n{intents_desc}\n"
        "输出格式："
        '{"priority":"...", "diplomacy_tone":"urgent|moderate|cautious", '
        '"resource_bias": {"region_id": 0.0-1.0}, "reasoning":"一句话"}'
    )
    payload = chat_json_sync(system, user)
    priority = str(payload.get("priority", "")).strip()
    if priority not in allowed:
        raise DirectiveRejectError(
            f"无法将决断映射到合法战略：{priority!r}；请从建议意图中选择"
        )
    tone_raw = str(payload.get("diplomacy_tone", "moderate")).lower()
    try:
        tone = DiplomacyTone(tone_raw)
    except ValueError:
        tone = DiplomacyTone.MODERATE

    bias = payload.get("resource_bias") or {}
    if not isinstance(bias, dict):
        bias = {}

    meta_priority = priority
    d = build_directive_from_intent(
        meta_priority,
        decision_point,
        raw_quote=text.strip(),
    )
    # 合并 LLM 给出的 bias（限制在 0-1）
    merged_bias = dict(d.resource_bias)
    for k, v in bias.items():
        try:
            merged_bias[str(k)] = max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            continue
    return d.model_copy(
        update={
            "resource_bias": merged_bias,
            "diplomacy_tone": tone,
        }
    )


def parse_player_input(
    decision_point: DecisionPoint,
    *,
    intent_id: str | None = None,
    text: str | None = None,
    use_llm: bool = False,
) -> StrategicDirective:
    """意图卡优先；否则解析自然语言。"""
    if intent_id:
        allowed = _allowed_intent_ids(decision_point)
        if intent_id not in allowed:
            raise DirectiveRejectError(f"无效意图：{intent_id}")
        quote = (text or "").strip()
        return build_directive_from_intent(
            intent_id, decision_point, raw_quote=quote or intent_id
        )

    if not text or not text.strip():
        raise DirectiveRejectError("请输入战略决断或选择建议意图")

    if use_llm and is_llm_configured():
        return parse_nl_with_llm(text.strip(), decision_point)
    return parse_nl_rule_based(text.strip(), decision_point)


def verify_directive(
    directive: StrategicDirective,
    state: GameState,
    decision_point: DecisionPoint,
) -> None:
    """二次校验诏令合法性。"""
    if directive.priority not in ALLOWED_PRIORITIES:
        raise DirectiveRejectError(f"未知战略 priority：{directive.priority}")

    allowed = _allowed_intent_ids(decision_point)
    if directive.priority not in allowed:
        raise DirectiveRejectError(
            f"该决断点不支持战略「{directive.priority}」，可选：{sorted(allowed)}"
        )

    if directive.raw_quote:
        _check_illegal(directive.raw_quote)

    # 资源倾向中的区域 id 须存在
    for rid in directive.resource_bias:
        if rid not in state.regions and rid != "allied_hub":
            raise DirectiveRejectError(f"未知区域权重：{rid}")
