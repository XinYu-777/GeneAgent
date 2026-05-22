"""规则 Bot：无 LLM 时供阶段 1 集成测试生成行动。"""

from __future__ import annotations

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
)
from engine.state import GameState
from engine.verifier import verify_action


def generate_stub_actions(state: GameState) -> list[Action]:
    """各方简单启发式行动，用于 advance_turn 集成测试。"""
    actions: list[Action] = []

    if state.owns(FactionId.JAPAN, "east_china") and not state.owns(
        FactionId.JAPAN, "central_china"
    ):
        actions.append(
            AdvanceFrontAction(
                faction=FactionId.JAPAN,
                from_region="east_china",
                to_region="central_china",
            )
        )

    if state.owns(FactionId.CHINA, "south_china") and state.get_region(
        "central_china"
    ).owner == FactionId.JAPAN:
        actions.append(
            AdvanceFrontAction(
                faction=FactionId.CHINA,
                from_region="south_china",
                to_region="central_china",
            )
        )

    actions.append(
        HoldGarrisonAction(faction=FactionId.CHINA, region="southwest_china")
    )

    if state.owns(FactionId.JAPAN, "north_china"):
        actions.append(
            GuerrillaOperationAction(
                faction=FactionId.CPC, region="north_china"
            )
        )

    if state.turn >= 6 and state.routes.get("burma_road") == RouteStatus.OPEN:
        actions.append(
            RaidSupplyAction(faction=FactionId.JAPAN, route_id="burma_road")
        )

    if state.turn >= 4 and state.turn % 3 == 0:
        actions.append(SeekAlliedAidAction(faction=FactionId.CHINA))

    if state.turn >= 7 and not state.owns(FactionId.JAPAN, "philippines"):
        actions.append(
            PacificStrikeAction(
                faction=FactionId.JAPAN, target_region="philippines"
            )
        )

    valid: list[Action] = []
    for a in actions:
        if verify_action(state, a).accepted:
            valid.append(a)
    return valid
