"""战斗力量估算（合并与结算共用）。"""

from __future__ import annotations

from engine.schemas import FactionId
from engine.state import GameState


def attack_power(state: GameState, faction: FactionId, from_region: str | None) -> float:
    f = state.factions[faction]
    g = 0.35
    if from_region and from_region in state.regions and state.owns(faction, from_region):
        g = state.get_region(from_region).garrison
    return f.manpower * 0.02 + g * 80.0 + f.morale * 20.0


def defense_power(state: GameState, region_id: str) -> float:
    r = state.get_region(region_id)
    bonus = 15.0 if r.owner == FactionId.NEUTRAL else 25.0
    return r.garrison * 90.0 * (1.0 + r.unrest * 0.5) + bonus
