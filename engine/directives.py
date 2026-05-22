"""玩家战略诏令：生效、时效、对战局数值与中方 AI 的影响。"""

from __future__ import annotations

from engine.decision_points import DecisionPoint
from engine.schemas import (
    ActiveDirective,
    DiplomacyTone,
    FactionId,
    RouteStatus,
    StrategicDirective,
)
from engine.state import GameState

# 各战略重心：资源倾向、外交语气、立即生效的国力修正
PRIORITY_META: dict[str, dict] = {
    "guerrilla_expand": {
        "resource_bias": {"north_china": 0.85, "cpc_shaanxi": 0.7},
        "diplomacy_tone": DiplomacyTone.MODERATE,
        "morale_delta": 0.06,
        "supply_delta": 0.02,
        "unrest_on_japan_regions": 0.06,
    },
    "hold_core": {
        "resource_bias": {"southwest_china": 1.0, "central_china": 0.75},
        "diplomacy_tone": DiplomacyTone.CAUTIOUS,
        "morale_delta": 0.04,
        "supply_delta": 0.05,
    },
    "seek_allied_aid": {
        "resource_bias": {"allied_hub": 0.9, "southwest_china": 0.6},
        "diplomacy_tone": DiplomacyTone.URGENT,
        "morale_delta": 0.03,
        "supply_delta": 0.08,
        "manpower_delta": 12,
    },
    "hold_burma": {
        "resource_bias": {"burma": 0.95, "yunnan": 0.9, "southwest_china": 0.7},
        "diplomacy_tone": DiplomacyTone.URGENT,
        "morale_delta": 0.05,
        "supply_delta": 0.06,
        "protect_burma_road": True,
    },
    "counteroffensive_huabei": {
        "resource_bias": {"north_china": 0.9, "jiangxi": 0.8, "central_china": 0.85},
        "diplomacy_tone": DiplomacyTone.URGENT,
        "morale_delta": 0.08,
        "supply_delta": -0.02,
        "manpower_delta": -10,
    },
}

ALLOWED_PRIORITIES = set(PRIORITY_META.keys())


def build_directive_from_intent(
    intent_id: str,
    decision_point: DecisionPoint,
    *,
    raw_quote: str = "",
) -> StrategicDirective:
    meta = PRIORITY_META.get(intent_id, {})
    return StrategicDirective(
        priority=intent_id,
        resource_bias=dict(meta.get("resource_bias", {})),
        diplomacy_tone=meta.get("diplomacy_tone", DiplomacyTone.MODERATE),
        duration_turns=decision_point.directive_duration_turns,
        raw_quote=raw_quote,
        source_decision_id=decision_point.id,
    )


def activate_directive(state: GameState, directive: StrategicDirective) -> ActiveDirective:
    """诏令进入生效列表；新诏令覆盖旧诏令（仅一条主战略生效）。"""
    active = ActiveDirective(
        directive=directive,
        turns_left=directive.duration_turns,
    )
    state.active_directives = [active]
    return active


def apply_directive_immediate_effects(
    state: GameState, directive: StrategicDirective
) -> str:
    """决断提交瞬间的国力修正（可验证的战局影响）。"""
    meta = PRIORITY_META.get(directive.priority, {})
    parts: list[str] = []

    china = state.factions[FactionId.CHINA]
    updates: dict = {}
    if "morale_delta" in meta:
        updates["morale"] = min(1.0, china.morale + meta["morale_delta"])
    if "supply_delta" in meta:
        updates["supply"] = max(0.0, min(1.0, china.supply + meta["supply_delta"]))
    if "manpower_delta" in meta:
        updates["manpower"] = max(0, china.manpower + meta["manpower_delta"])
    if updates:
        state.factions[FactionId.CHINA] = china.model_copy(update=updates)
        parts.append(f"中国国力调整：{updates}")

    if meta.get("protect_burma_road") and state.routes.get("burma_road") == RouteStatus.CUT:
        state.routes["burma_road"] = RouteStatus.CONTESTED
        parts.append("滇缅公路由切断转为争夺中")

    unrest_delta = meta.get("unrest_on_japan_regions", 0.0)
    if unrest_delta > 0:
        n = 0
        for rid, reg in state.regions.items():
            if reg.owner == FactionId.JAPAN:
                reg.unrest = min(1.0, reg.unrest + unrest_delta)
                n += 1
        if n:
            parts.append(f"日占区动荡上升（{n} 区）")

    if directive.diplomacy_tone == DiplomacyTone.URGENT:
        allied = state.factions.get(FactionId.ALLIED)
        if allied:
            state.factions[FactionId.ALLIED] = allied.model_copy(
                update={"supply": min(1.0, allied.supply + 0.03)}
            )
            parts.append("同盟援华关注度上升")

    return "；".join(parts) if parts else "诏令已传达统帅部"


def primary_directive(state: GameState) -> StrategicDirective | None:
    if not state.active_directives:
        return None
    return state.active_directives[0].directive
