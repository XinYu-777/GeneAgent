"""阶段 0 验收测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from engine import build_initial_snapshot, load_scenario, load_world_map
from engine.schemas import AdvanceFrontAction, FactionId, GameSnapshot, StrategicDirective

ROOT = Path(__file__).resolve().parent.parent
SCENARIO = ROOT / "scenarios" / "1941.yaml"
MAP = ROOT / "data" / "regions_1941.yaml"
SNAPSHOT_SCHEMA = ROOT / "schemas" / "snapshot-schema.json"


class TestLoadScenario:
    def test_load_scenario_no_error(self):
        s = load_scenario(SCENARIO)
        assert s.scenario_id == "east_asia_1941"
        assert s.player_faction == "china"
        assert len(s.decision_points) == 3

    def test_pending_decision_turn_0(self):
        s = load_scenario(SCENARIO)
        dp = s.pending_decision(turn=0, fired_events=set(), resolved_ids=set())
        assert dp is not None
        assert dp.id == "dp_opening_strategy"

    def test_pending_decision_pearl_harbor(self):
        s = load_scenario(SCENARIO)
        dp = s.pending_decision(
            turn=6,
            fired_events={"evt_pearl_harbor"},
            resolved_ids={"dp_opening_strategy"},
        )
        assert dp is not None
        assert dp.id == "dp_post_pearl_harbor"

    def test_pending_decision_1944_crisis(self):
        s = load_scenario(SCENARIO)
        dp = s.pending_decision(
            turn=28,
            fired_events={"evt_china_1944_pressure"},
            resolved_ids={"dp_opening_strategy", "dp_post_pearl_harbor"},
        )
        assert dp is not None
        assert dp.id == "dp_1944_crisis"

    def test_pending_decision_none_when_all_resolved(self):
        s = load_scenario(SCENARIO)
        dp = s.pending_decision(
            turn=99,
            fired_events={"evt_pearl_harbor", "evt_china_1944_pressure"},
            resolved_ids={
                "dp_opening_strategy",
                "dp_post_pearl_harbor",
                "dp_1944_crisis",
            },
        )
        assert dp is None

    def test_opening_not_repeated_after_resolved(self):
        s = load_scenario(SCENARIO)
        dp = s.pending_decision(
            turn=0, fired_events=set(), resolved_ids={"dp_opening_strategy"}
        )
        assert dp is None


class TestWorldMap:
    def test_load_world_map_region_count(self):
        world = load_world_map(MAP)
        assert 30 <= world.region_count <= 40

    def test_neighbor_symmetry_enforced(self):
        world = load_world_map(MAP)
        for r in world.regions:
            for nb in r.neighbors:
                assert r.id in world.get_region(nb).neighbors


class TestSchemasAndSnapshot:
    def test_strategic_directive_roundtrip(self):
        d = StrategicDirective(
            priority="hold_burma",
            resource_bias={"burma": 0.9, "southwest_china": 0.5},
            duration_turns=4,
            raw_quote="不惜代价保住滇缅公路",
            source_decision_id="dp_post_pearl_harbor",
        )
        restored = StrategicDirective.model_validate_json(d.model_dump_json())
        assert restored.priority == "hold_burma"

    def test_action_discriminator(self):
        a = AdvanceFrontAction(
            faction=FactionId.JAPAN,
            from_region="east_china",
            to_region="central_china",
        )
        assert a.type == "advance_front"

    def test_initial_snapshot_matches_schema(self):
        snap = build_initial_snapshot(SCENARIO, MAP)
        assert isinstance(snap, GameSnapshot)
        assert snap.turn == 0
        assert snap.pending_decision is not None
        assert snap.pending_decision.id == "dp_opening_strategy"
        assert len(snap.regions) >= 30

        schema = json.loads(SNAPSHOT_SCHEMA.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        payload = snap.model_dump(mode="json")
        errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
        assert not errors, f"schema errors: {[e.message for e in errors]}"

    def test_snapshot_json_export(self, tmp_path: Path):
        snap = build_initial_snapshot(SCENARIO, MAP)
        out = tmp_path / "turn0.json"
        out.write_text(
            json.dumps(snap.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["scenario_id"] == "east_asia_1941"
