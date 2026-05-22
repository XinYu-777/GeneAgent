"""回合推进：合并、结算、事件、决断门禁。"""

from __future__ import annotations

from pathlib import Path

from engine.apply import apply_all
from engine.decision_points import load_scenario
from engine.events import fire_turn_events
from engine.merger import merge_actions
from engine.schemas import Action, ActionPlayed, FactionId, GameSnapshot, RouteStatus
from engine.state import GameState, game_state_from_world, snapshot_from_state
from engine.stub_ai import generate_stub_actions
from engine.world import (
    DEFAULT_MAP_PATH,
    DEFAULT_SCENARIO_PATH,
    _default_faction_snapshots,
    load_world_map,
)

DEFAULT_SCENARIO = DEFAULT_SCENARIO_PATH
DEFAULT_MAP = DEFAULT_MAP_PATH


class PendingDecisionError(Exception):
    """存在未处理的玩家决断，不能推进回合。"""


class GameSession:
    def __init__(
        self,
        state: GameState,
        *,
        skip_decision_gate: bool = False,
    ):
        self.state = state
        self.skip_decision_gate = skip_decision_gate

    @classmethod
    def new(
        cls,
        scenario_path: str | Path = DEFAULT_SCENARIO,
        map_path: str | Path = DEFAULT_MAP,
        *,
        skip_decision_gate: bool = False,
        resolve_all_decisions: bool = False,
    ) -> GameSession:
        scenario = load_scenario(scenario_path)
        world = load_world_map(map_path)
        factions = {
            FactionId(k): v
            for k, v in _default_faction_snapshots().items()
        }
        state = game_state_from_world(scenario, world, factions)
        if resolve_all_decisions:
            state.resolved_decision_ids = {dp.id for dp in scenario.decision_points}
        fire_turn_events(state)
        return cls(state, skip_decision_gate=skip_decision_gate)

    def has_pending_decision(self) -> bool:
        return (
            self.state.scenario.pending_decision(
                self.state.turn,
                self.state.fired_events,
                self.state.resolved_decision_ids,
            )
            is not None
        )

    def resolve_decision(self, decision_id: str) -> None:
        self.state.resolved_decision_ids.add(decision_id)

    def get_snapshot(self, actions_played: list[ActionPlayed] | None = None) -> GameSnapshot:
        return snapshot_from_state(self.state, actions_played)

    def advance_turn(
        self,
        actions: list[Action] | None = None,
        *,
        use_stub_ai: bool = False,
    ) -> GameSnapshot:
        if self.state.turn >= self.state.scenario.max_turns:
            raise ValueError("已达剧本最大回合数")

        if self.has_pending_decision() and not self.skip_decision_gate:
            raise PendingDecisionError(
                "当前回合有待处理决断，请先 resolve_decision 或设置 skip_decision_gate"
            )

        if actions is None:
            actions = generate_stub_actions(self.state) if use_stub_ai else []

        resolved = merge_actions(self.state, actions)
        played = [
            ActionPlayed(
                faction=r.action.faction,
                action=r.action,
                accepted=r.accepted,
                message=r.message,
            )
            for r in resolved
        ]

        apply_all(self.state, [r for r in resolved if r.accepted])

        self._tick_directives()
        self._upkeep()

        self.state.turn += 1
        fire_turn_events(self.state)

        return snapshot_from_state(self.state, played)

    def _tick_directives(self) -> None:
        remaining = []
        for ad in self.state.active_directives:
            left = ad.turns_left - 1
            if left > 0:
                remaining.append(ad.model_copy(update={"turns_left": left}))
        self.state.active_directives = remaining

    def _upkeep(self) -> None:
        for fid, f in list(self.state.factions.items()):
            supply = f.supply
            if fid == FactionId.JAPAN:
                open_count = sum(
                    1 for st in self.state.routes.values() if st == RouteStatus.OPEN
                )
                if open_count < len(self.state.routes):
                    supply = max(0.0, supply - 0.02)
            elif fid == FactionId.CHINA:
                if self.state.routes.get("burma_road") == RouteStatus.CUT:
                    supply = max(0.0, supply - 0.03)
                else:
                    supply = min(1.0, supply + 0.01)
            self.state.factions[fid] = f.model_copy(update={"supply": supply})


def advance_turn(
    session: GameSession,
    actions: list[Action] | None = None,
    *,
    use_stub_ai: bool = False,
) -> GameSnapshot:
    return session.advance_turn(actions, use_stub_ai=use_stub_ai)
