"""不对称情报：各方仅见其观测投影。"""

from __future__ import annotations

import hashlib
import random
from typing import Any

from pydantic import BaseModel, Field

from engine.schemas import (
    ActiveDirective,
    FactionId,
    FactionSnapshot,
    RouteSnapshot,
    RouteStatus,
)
from engine.state import GameState


class RegionIntel(BaseModel):
    id: str
    name: str
    owner: FactionId
    garrison_estimate: float = Field(ge=0.0, le=1.0)
    unrest_estimate: float = Field(ge=0.0, le=1.0)
    intel_quality: str = Field(description="confirmed | estimate | poor")


class FactionObservation(BaseModel):
    faction: FactionId
    turn: int
    own_stats: FactionSnapshot
    regions: list[RegionIntel]
    routes: list[RouteSnapshot]
    fired_events: list[str]
    active_directives: list[ActiveDirective] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    def model_dump_for_trace(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def _rng_for(state: GameState, faction: FactionId, region_id: str) -> random.Random:
    key = f"{state.turn}:{faction.value}:{region_id}"
    seed = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)
    return random.Random(seed)


def _estimate_garrison(
    true_garrison: float,
    rng: random.Random,
    *,
    bias: float = 0.0,
) -> float:
    noise = rng.uniform(-0.18, 0.18) + bias
    return max(0.05, min(1.0, true_garrison + noise))


def _region_visible(faction: FactionId, owner: FactionId, region_id: str) -> bool:
    """该势力是否将此区域纳入观测网。"""
    if faction == FactionId.SOVIET:
        return region_id.startswith("soviet") or region_id in (
            "sakhalin",
            "manchuria",
            "korea",
            "japan_home",
        )
    if faction == FactionId.CPC:
        return owner in (FactionId.CPC, FactionId.CHINA, FactionId.JAPAN) or region_id in (
            "cpc_shaanxi",
            "north_china",
            "central_china",
            "northwest_china",
        )
    if faction == FactionId.ALLIED:
        return False
    return True


def project(state: GameState, faction: FactionId) -> FactionObservation:
    """从全局状态生成势力局部观测（日本对中国兵力仅为估计）。"""
    own_stats = state.factions[faction]
    regions: list[RegionIntel] = []
    notes: list[str] = []

    for rid in sorted(state.regions.keys()):
        r = state.get_region(rid)
        if not _region_visible(faction, r.owner, rid):
            continue

        rng = _rng_for(state, faction, rid)
        if r.owner == faction or r.owner == FactionId.CHINA and faction == FactionId.CPC:
            g_est = r.garrison
            u_est = r.unrest
            quality = "confirmed"
        elif faction == FactionId.JAPAN and r.owner == FactionId.CHINA:
            g_est = _estimate_garrison(r.garrison, rng, bias=-0.12)
            u_est = _estimate_garrison(r.unrest, rng)
            quality = "estimate"
            notes.append(f"对华情报：{rid} 守备估计 {g_est:.2f}")
        elif faction == FactionId.CHINA and r.owner == FactionId.JAPAN:
            g_est = _estimate_garrison(r.garrison, rng, bias=0.08)
            u_est = r.unrest
            quality = "estimate"
        else:
            g_est = _estimate_garrison(r.garrison, rng)
            u_est = _estimate_garrison(r.unrest, rng)
            quality = "poor" if faction != FactionId.JAPAN else "estimate"

        if faction == FactionId.SOVIET and rid == "manchuria":
            quality = "estimate"

        regions.append(
            RegionIntel(
                id=rid,
                name=r.name,
                owner=r.owner,
                garrison_estimate=g_est,
                unrest_estimate=u_est,
                intel_quality=quality,
            )
        )

    routes = _visible_routes(state, faction)
    directives = (
        list(state.active_directives)
        if faction == FactionId.CHINA
        else []
    )

    if faction == FactionId.JAPAN and "evt_pearl_harbor" in state.fired_events:
        notes.append("太平洋战争已爆发，南进压力上升")
    if faction == FactionId.CHINA and state.routes.get("burma_road") == RouteStatus.CUT:
        notes.append("滇缅公路可能被切断")

    return FactionObservation(
        faction=faction,
        turn=state.turn,
        own_stats=own_stats,
        regions=regions,
        routes=routes,
        fired_events=sorted(state.fired_events),
        active_directives=directives,
        notes=notes,
    )


def _visible_routes(state: GameState, faction: FactionId) -> list[RouteSnapshot]:
    from engine.state import _route_name

    out: list[RouteSnapshot] = []
    for rid, st in state.routes.items():
        if faction == FactionId.JAPAN:
            out.append(RouteSnapshot(id=rid, name=_route_name(state, rid), status=st))
        elif faction == FactionId.CHINA and rid in ("burma_road", "hump_airlift"):
            out.append(RouteSnapshot(id=rid, name=_route_name(state, rid), status=st))
        elif faction == FactionId.SOVIET and rid == "pacific_shipping":
            out.append(RouteSnapshot(id=rid, name=_route_name(state, rid), status=st))
    return out


def japan_cannot_see_china_true_garrison(
    state: GameState, region_id: str
) -> bool:
    """供测试：日方可观测的中国区 garrison_estimate 应与真值有偏差。"""
    r = state.get_region(region_id)
    if r.owner != FactionId.CHINA:
        return False
    obs = project(state, FactionId.JAPAN)
    intel = next((x for x in obs.regions if x.id == region_id), None)
    if intel is None:
        return False
    return abs(intel.garrison_estimate - r.garrison) > 1e-6 or intel.intel_quality == "estimate"
