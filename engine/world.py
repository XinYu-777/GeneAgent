"""战略世界地图：区域邻接、补给线、开局快照构建。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

from engine.decision_points import DecisionPoint, ScenarioConfig, load_scenario
from engine.schemas import (
    FactionId,
    FactionSnapshot,
    GameSnapshot,
    PendingDecisionSnapshot,
    RegionSnapshot,
    RouteSnapshot,
    RouteStatus,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_SCENARIO_PATH = Path(__file__).resolve().parent.parent / "scenarios" / "1941.yaml"
DEFAULT_MAP_PATH = DATA_DIR / "regions_1941.yaml"


class RegionDef(BaseModel):
    id: str
    name: str
    owner: FactionId
    neighbors: list[str] = Field(min_length=1)
    garrison: float = Field(default=0.5, ge=0.0, le=1.0)
    unrest: float = Field(default=0.0, ge=0.0, le=1.0)


class RouteDef(BaseModel):
    id: str
    name: str
    status: RouteStatus = RouteStatus.OPEN
    connects: list[str] = Field(min_length=2)


class WorldMap(BaseModel):
    regions: list[RegionDef]
    routes: list[RouteDef] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_neighbor_symmetry(self) -> WorldMap:
        ids = {r.id for r in self.regions}
        if len(ids) != len(self.regions):
            raise ValueError("region id 重复")

        index = {r.id: r for r in self.regions}
        for region in self.regions:
            for nb in region.neighbors:
                if nb not in ids:
                    raise ValueError(f"{region.id} 的邻接 {nb} 不存在")
                if region.id not in index[nb].neighbors:
                    raise ValueError(f"邻接不对称: {region.id} <-> {nb}")
        return self

    @property
    def region_count(self) -> int:
        return len(self.regions)

    def get_region(self, region_id: str) -> RegionDef:
        for r in self.regions:
            if r.id == region_id:
                return r
        raise KeyError(region_id)

    def neighbors_of(self, region_id: str) -> list[str]:
        return list(self.get_region(region_id).neighbors)


def load_world_map(path: str | Path = DEFAULT_MAP_PATH) -> WorldMap:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return WorldMap.model_validate(raw)


def _default_faction_snapshots() -> dict[str, FactionSnapshot]:
    return {
        FactionId.CHINA.value: FactionSnapshot(
            manpower=420, supply=0.52, morale=0.58, industrial_capacity=0.35
        ),
        FactionId.JAPAN.value: FactionSnapshot(
            manpower=280, supply=0.68, morale=0.72, industrial_capacity=0.62
        ),
        FactionId.SOVIET.value: FactionSnapshot(
            manpower=120, supply=0.45, morale=0.5, industrial_capacity=0.4
        ),
        FactionId.CPC.value: FactionSnapshot(
            manpower=45, supply=0.3, morale=0.65, industrial_capacity=0.15
        ),
        FactionId.ALLIED.value: FactionSnapshot(
            manpower=0, supply=0.8, morale=0.7, industrial_capacity=0.9
        ),
    }


def decision_to_pending_snapshot(dp: DecisionPoint) -> PendingDecisionSnapshot:
    return PendingDecisionSnapshot(
        id=dp.id,
        title=dp.title,
        prompt=dp.prompt,
        suggested_intents=[{"id": i.id, "label": i.label} for i in dp.suggested_intents],
    )


def build_initial_snapshot(
    scenario_path: str | Path = DEFAULT_SCENARIO_PATH,
    map_path: str | Path = DEFAULT_MAP_PATH,
) -> GameSnapshot:
    """根据剧本与地图数据构建回合 0 快照。"""
    from engine.turn import GameSession

    return GameSession.new(scenario_path, map_path).get_snapshot()


def events_for_turn(scenario: ScenarioConfig, turn: int) -> list[str]:
    """返回该回合应触发的剧本事件 id 列表。"""
    fired: list[str] = []
    for ev in scenario.events:
        if ev.get("turn") == turn:
            fired.append(str(ev["id"]))
    return fired


def scenario_events_by_turn(scenario: ScenarioConfig) -> dict[int, list[str]]:
    table: dict[int, list[str]] = {}
    for ev in scenario.events:
        t = ev.get("turn")
        if t is not None:
            table.setdefault(int(t), []).append(str(ev["id"]))
    return table
