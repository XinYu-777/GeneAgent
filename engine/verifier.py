"""行动合法性校验（阶段 1）。"""

from __future__ import annotations

from dataclasses import dataclass

from engine.schemas import (
    Action,
    AdvanceFrontAction,
    FactionId,
    GuerrillaOperationAction,
    HoldGarrisonAction,
    PacificStrikeAction,
    RaidSupplyAction,
    SeekAlliedAidAction,
    SovietInvasionAction,
)
from engine.state import GameState

# 1945 前苏联进攻门槛（无专用事件时用回合近似）
SOVIET_INVASION_MIN_TURN = 38

MANPOWER_COST: dict[str, int] = {
    "advance_front": 15,
    "hold_garrison": 5,
    "guerrilla_operation": 8,
    "raid_supply": 10,
    "seek_allied_aid": 5,
    "pacific_strike": 20,
    "soviet_invasion": 25,
}


@dataclass(frozen=True)
class VerifyResult:
    action: Action
    accepted: bool
    message: str | None = None


def _has_manpower(state: GameState, faction: FactionId, cost: int) -> bool:
    snap = state.factions.get(faction)
    if snap is None:
        return False
    return snap.manpower >= cost


def verify_action(state: GameState, action: Action) -> VerifyResult:
    cost = MANPOWER_COST.get(action.type, 0)
    if not _has_manpower(state, action.faction, cost):
        return VerifyResult(
            action,
            False,
            f"{action.faction.value} 人力不足（需要 {cost}）",
        )

    if isinstance(action, AdvanceFrontAction):
        return _verify_advance(state, action, cost)
    if isinstance(action, HoldGarrisonAction):
        return _verify_hold(state, action)
    if isinstance(action, GuerrillaOperationAction):
        return _verify_guerrilla(state, action)
    if isinstance(action, RaidSupplyAction):
        return _verify_raid(state, action)
    if isinstance(action, SeekAlliedAidAction):
        return _verify_seek_aid(state, action)
    if isinstance(action, PacificStrikeAction):
        return _verify_pacific(state, action)
    if isinstance(action, SovietInvasionAction):
        return _verify_soviet(state, action)

    return VerifyResult(action, False, "未知行动类型")


def _verify_advance(state: GameState, action: AdvanceFrontAction, cost: int) -> VerifyResult:
    if action.from_region not in state.regions or action.to_region not in state.regions:
        return VerifyResult(action, False, "区域不存在")
    if not state.owns(action.faction, action.from_region):
        return VerifyResult(action, False, f"未控制出发区 {action.from_region}")
    if action.to_region not in state.region_neighbors(action.from_region):
        return VerifyResult(action, False, "目标区与出发区不相邻")
    if state.owns(action.faction, action.to_region):
        return VerifyResult(action, False, "已占领目标区")
    return VerifyResult(action, True)


def _verify_hold(state: GameState, action: HoldGarrisonAction) -> VerifyResult:
    if action.region not in state.regions:
        return VerifyResult(action, False, "区域不存在")
    if not state.owns(action.faction, action.region):
        return VerifyResult(action, False, "只能守备己方控制区")
    r = state.get_region(action.region)
    if r.garrison >= 0.98:
        return VerifyResult(action, False, "驻军已满")
    return VerifyResult(action, True)


def _verify_guerrilla(state: GameState, action: GuerrillaOperationAction) -> VerifyResult:
    if action.region not in state.regions:
        return VerifyResult(action, False, "区域不存在")
    if state.owns(action.faction, action.region):
        return VerifyResult(action, False, "游击目标须为敌方控制区")
    if action.faction not in (FactionId.CHINA, FactionId.CPC):
        return VerifyResult(action, False, "仅中国/CPC 可发动游击")
    return VerifyResult(action, True)


def _verify_raid(state: GameState, action: RaidSupplyAction) -> VerifyResult:
    if action.route_id not in state.routes:
        return VerifyResult(action, False, "补给线不存在")
    return VerifyResult(action, True)


def _verify_seek_aid(state: GameState, action: SeekAlliedAidAction) -> VerifyResult:
    if action.faction != FactionId.CHINA:
        return VerifyResult(action, False, "仅中国可寻求同盟援助")
    return VerifyResult(action, True)


def _verify_pacific(state: GameState, action: PacificStrikeAction) -> VerifyResult:
    if action.faction != FactionId.JAPAN:
        return VerifyResult(action, False, "仅日本可发动南进打击")
    if action.target_region not in state.regions:
        return VerifyResult(action, False, "目标区域不存在")
    target = state.get_region(action.target_region)
    if target.owner in (FactionId.JAPAN, FactionId.SOVIET):
        return VerifyResult(action, False, "南进目标须非日苏直接领土")
    return VerifyResult(action, True)


def _verify_soviet(state: GameState, action: SovietInvasionAction) -> VerifyResult:
    if action.faction != FactionId.SOVIET:
        return VerifyResult(action, False, "仅苏联可发动入关进攻")
    if state.turn < SOVIET_INVASION_MIN_TURN and "evt_soviet_invasion" not in state.fired_events:
        return VerifyResult(
            action,
            False,
            f"1945 前苏军未参战（回合须 ≥ {SOVIET_INVASION_MIN_TURN} 或触发 evt_soviet_invasion）",
        )
    if action.target_region not in state.regions:
        return VerifyResult(action, False, "目标区域不存在")
    if not state.owns(FactionId.JAPAN, action.target_region):
        return VerifyResult(action, False, "苏军进攻目标须为日占区")
    return VerifyResult(action, True)


def verify_actions(state: GameState, actions: list[Action]) -> list[VerifyResult]:
    return [verify_action(state, a) for a in actions]
