"""可变对局状态与快照互转。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from engine.decision_points import ScenarioConfig
from engine.schemas import (
    ActiveDirective,
    FactionId,
    FactionSnapshot,
    GameSnapshot,
    RegionSnapshot,
    RouteSnapshot,
    RouteStatus,
)
from engine.world import WorldMap, decision_to_pending_snapshot


class RegionState(BaseModel):
    id: str
    name: str
    owner: FactionId
    garrison: float = Field(ge=0.0, le=1.0)
    unrest: float = Field(default=0.0, ge=0.0, le=1.0)


class GameState(BaseModel):
    scenario: ScenarioConfig
    world_map: WorldMap
    turn: int
    regions: dict[str, RegionState]
    routes: dict[str, RouteStatus]
    factions: dict[FactionId, FactionSnapshot]
    fired_events: set[str] = Field(default_factory=set)
    resolved_decision_ids: set[str] = Field(default_factory=set)
    active_directives: list[ActiveDirective] = Field(default_factory=list)

    def region_neighbors(self, region_id: str) -> list[str]:
        return self.world_map.neighbors_of(region_id)

    def get_region(self, region_id: str) -> RegionState:
        if region_id not in self.regions:
            raise KeyError(region_id)
        return self.regions[region_id]

    def owns(self, faction: FactionId, region_id: str) -> bool:
        return self.get_region(region_id).owner == faction

    def route_status(self, route_id: str) -> RouteStatus | None:
        return self.routes.get(route_id)


def game_state_from_world(
    scenario: ScenarioConfig,
    world_map: WorldMap,
    factions: dict[FactionId, FactionSnapshot],
    turn: int | None = None,
) -> GameState:
    t = scenario.start_turn if turn is None else turn
    return GameState(
        scenario=scenario,
        world_map=world_map,
        turn=t,
        regions={
            r.id: RegionState(
                id=r.id,
                name=r.name,
                owner=r.owner,
                garrison=r.garrison,
                unrest=r.unrest,
            )
            for r in world_map.regions
        },
        routes={r.id: r.status for r in world_map.routes},
        factions=factions,
    )


def snapshot_from_state(state: GameState, actions_played: list | None = None) -> GameSnapshot:
    from engine.schemas import ActionPlayed

    pending = state.scenario.pending_decision(
        state.turn,
        state.fired_events,
        state.resolved_decision_ids,
    )
    return GameSnapshot(
        scenario_id=state.scenario.scenario_id,
        title=state.scenario.title,
        turn=state.turn,
        regions=[
            RegionSnapshot(
                id=r.id,
                name=r.name,
                owner=r.owner,
                garrison=r.garrison,
                unrest=r.unrest,
            )
            for r in sorted(state.regions.values(), key=lambda x: x.id)
        ],
        routes=[
            RouteSnapshot(id=rid, name=_route_name(state, rid), status=st)
            for rid, st in state.routes.items()
        ],
        factions={k.value: v for k, v in state.factions.items()},
        actions_played=actions_played or [],
        active_directives=list(state.active_directives),
        pending_decision=(
            decision_to_pending_snapshot(pending) if pending else None
        ),
        fired_events=sorted(state.fired_events),
    )


def _route_name(state: GameState, route_id: str) -> str:
    for r in state.world_map.routes:
        if r.id == route_id:
            return r.name
    return route_id
