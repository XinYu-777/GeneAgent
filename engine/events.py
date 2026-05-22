"""剧本事件：按回合触发并施加效果。"""

from __future__ import annotations

from engine.schemas import FactionId
from engine.state import GameState
from engine.world import events_for_turn


def fire_turn_events(state: GameState) -> list[str]:
    """在当前 state.turn 触发尚未记录的事件，返回本回合新触发 id。"""
    new_events: list[str] = []
    for eid in events_for_turn(state.scenario, state.turn):
        if eid in state.fired_events:
            continue
        state.fired_events.add(eid)
        new_events.append(eid)
        _apply_event_effect(state, eid)
    return new_events


def _apply_event_effect(state: GameState, event_id: str) -> None:
    if event_id == "evt_pearl_harbor":
        jp = state.factions[FactionId.JAPAN]
        state.factions[FactionId.JAPAN] = jp.model_copy(
            update={"supply": min(1.0, jp.supply + 0.06), "morale": min(1.0, jp.morale + 0.04)}
        )
        cn = state.factions[FactionId.CHINA]
        state.factions[FactionId.CHINA] = cn.model_copy(
            update={"morale": max(0.0, cn.morale - 0.03)}
        )
    elif event_id == "evt_china_1944_pressure":
        cn = state.factions[FactionId.CHINA]
        state.factions[FactionId.CHINA] = cn.model_copy(
            update={
                "manpower": max(0, cn.manpower - 25),
                "morale": max(0.0, cn.morale - 0.08),
                "supply": max(0.0, cn.supply - 0.05),
            }
        )
    elif event_id == "evt_soviet_invasion":
        su = state.factions[FactionId.SOVIET]
        state.factions[FactionId.SOVIET] = su.model_copy(
            update={"manpower": su.manpower + 40, "morale": min(1.0, su.morale + 0.1)}
        )
