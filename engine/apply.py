"""将已合并的行动应用到 GameState。"""

from __future__ import annotations

from engine.merger import ResolvedAction
from engine.schemas import (
    Action,
    AdvanceFrontAction,
    FactionId,
    GuerrillaOperationAction,
    HoldGarrisonAction,
    PacificStrikeAction,
    RaidSupplyAction,
    RouteStatus,
    SeekAlliedAidAction,
    SovietInvasionAction,
)
from engine.state import GameState
from engine.verifier import MANPOWER_COST


def _spend_manpower(state: GameState, faction: FactionId, action_type: str) -> None:
    cost = MANPOWER_COST.get(action_type, 0)
    f = state.factions[faction]
    state.factions[faction] = f.model_copy(
        update={"manpower": max(0, f.manpower - cost)}
    )


def _resolve_battle(
    state: GameState,
    attacker: FactionId,
    from_region: str | None,
    target: str,
    label: str,
) -> str:
    from engine.combat import attack_power, defense_power

    atk = attack_power(state, attacker, from_region)
    defense = defense_power(state, target)
    region = state.get_region(target)

    if atk < defense * 0.85:
        region.garrison = max(0.1, region.garrison - 0.12)
        return f"{label}：进攻 {target} 受挫，守军 garrison 降至 {region.garrison:.2f}"

    region.garrison = max(0.15, region.garrison - 0.35)
    if region.garrison < 0.35:
        old = region.owner
        region.owner = attacker
        region.garrison = 0.52
        region.unrest = max(0.0, region.unrest - 0.1)
        return f"{label}：占领 {target}（{old.value} → {attacker.value}）"

    return f"{label}：削弱 {target} 守军至 {region.garrison:.2f}"


def apply_resolved_action(state: GameState, resolved: ResolvedAction) -> str | None:
    if not resolved.accepted:
        return resolved.message
    action = resolved.action
    _spend_manpower(state, action.faction, action.type)

    if isinstance(action, AdvanceFrontAction):
        msg = _resolve_battle(
            state,
            action.faction,
            action.from_region,
            action.to_region,
            "前线推进",
        )
        return resolved.message or msg

    if isinstance(action, HoldGarrisonAction):
        r = state.get_region(action.region)
        r.garrison = min(1.0, r.garrison + 0.12)
        return f"加强 {action.region} 守备至 {r.garrison:.2f}"

    if isinstance(action, GuerrillaOperationAction):
        r = state.get_region(action.region)
        r.unrest = min(1.0, r.unrest + 0.18)
        jp = state.factions.get(FactionId.JAPAN)
        if jp:
            state.factions[FactionId.JAPAN] = jp.model_copy(
                update={"supply": max(0.0, jp.supply - 0.03)}
            )
        return f"{action.region} 动荡升至 {r.unrest:.2f}"

    if isinstance(action, RaidSupplyAction):
        state.routes[action.route_id] = RouteStatus.CUT
        china = state.factions.get(FactionId.CHINA)
        if china and action.faction == FactionId.JAPAN:
            state.factions[FactionId.CHINA] = china.model_copy(
                update={"supply": max(0.0, china.supply - 0.08)}
            )
        return f"补给线 {action.route_id} 被切断"

    if isinstance(action, SeekAlliedAidAction):
        china = state.factions[FactionId.CHINA]
        state.factions[FactionId.CHINA] = china.model_copy(
            update={
                "supply": min(1.0, china.supply + 0.07),
                "manpower": china.manpower + 8,
            }
        )
        return "获得同盟援助，补给与人力上升"

    if isinstance(action, PacificStrikeAction):
        fr = _nearest_owned(state, action.faction, action.target_region)
        return _resolve_battle(
            state, action.faction, fr, action.target_region, "南进打击"
        )

    if isinstance(action, SovietInvasionAction):
        fr = _nearest_owned(state, FactionId.SOVIET, action.target_region)
        return _resolve_battle(
            state, action.faction, fr, action.target_region, "苏军入关"
        )

    return None


def _nearest_owned(
    state: GameState, faction: FactionId, target: str
) -> str | None:
    for rid, r in state.regions.items():
        if r.owner == faction and target in state.region_neighbors(rid):
            return rid
    for rid, r in state.regions.items():
        if r.owner == faction:
            return rid
    return None


def apply_all(state: GameState, resolved_list: list[ResolvedAction]) -> None:
    for res in resolved_list:
        if res.accepted:
            apply_resolved_action(state, res)
