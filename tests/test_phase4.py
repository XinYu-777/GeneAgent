"""阶段 4 API 验收。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.store import SNAPSHOTS_ROOT, store

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def client():
    store._games.clear()
    return TestClient(app)


class TestGameAPI:
    def test_health(self, client: TestClient):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_new_and_state(self, client: TestClient):
        r = client.post("/game/new", json={"resolve_all_decisions": False})
        assert r.status_code == 200
        data = r.json()
        gid = data["game_id"]
        assert data["snapshot"]["turn"] == 0
        assert data["snapshot"]["pending_decision"] is not None

        r2 = client.get("/game/state", params={"game_id": gid})
        assert r2.status_code == 200
        assert r2.json()["snapshot"]["turn"] == 0

        path = SNAPSHOTS_ROOT / gid / "turn_0.json"
        assert path.exists()

    def test_advance_blocked_without_decision(self, client: TestClient):
        r = client.post("/game/new", json={})
        gid = r.json()["game_id"]
        r2 = client.post(
            "/game/advance",
            json={"game_id": gid, "use_stub_ai": True, "use_multi_agent": True},
        )
        assert r2.status_code == 409
        detail = r2.json()["detail"]
        if isinstance(detail, str):
            assert "决断" in detail
        else:
            assert detail.get("code") == "pending_decision"

    def test_full_flow_five_turns(self, client: TestClient):
        r = client.post("/game/new", json={})
        gid = r.json()["game_id"]

        client.post(
            "/game/decision",
            json={
                "game_id": gid,
                "intent_id": "guerrilla_expand",
                "text": "扩大游击",
            },
        )

        for _ in range(5):
            ar = client.post(
                "/game/advance",
                json={
                    "game_id": gid,
                    "use_stub_ai": True,
                    "use_multi_agent": True,
                },
            )
            assert ar.status_code == 200, ar.text
            if ar.json()["snapshot"].get("pending_decision"):
                client.post(
                    "/game/decision",
                    json={"game_id": gid, "intent_id": "hold_core"},
                )

        r_state = client.get("/game/state", params={"game_id": gid})
        assert r_state.json()["snapshot"]["turn"] == 5

        r_replay = client.get(f"/game/replay/3", params={"game_id": gid})
        assert r_replay.status_code == 200
        assert r_replay.json()["turn"] == 3

        snap_dir = SNAPSHOTS_ROOT / gid
        files = list(snap_dir.glob("turn_*.json"))
        assert len(files) >= 6

    def test_decision_rejected(self, client: TestClient):
        r = client.post("/game/new", json={})
        gid = r.json()["game_id"]
        r2 = client.post(
            "/game/decision",
            json={"game_id": gid, "text": "明天占领东京"},
        )
        assert r2.status_code == 422

    def test_replay_missing_turn(self, client: TestClient):
        r = client.post("/game/new", json={"resolve_all_decisions": True})
        gid = r.json()["game_id"]
        r2 = client.get("/game/replay/99", params={"game_id": gid})
        assert r2.status_code == 404
