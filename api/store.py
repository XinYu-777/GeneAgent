"""对局存储与快照持久化。"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from engine.schemas import GameSnapshot
from engine.turn import GameSession

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOTS_ROOT = ROOT / "snapshots"


@dataclass
class GameRecord:
    game_id: str
    session: GameSession
    snapshot_dir: Path
    history_turns: list[int] = field(default_factory=list)


class GameStore:
    def __init__(self, snapshots_root: Path | None = None) -> None:
        self._games: dict[str, GameRecord] = {}
        self.snapshots_root = snapshots_root or SNAPSHOTS_ROOT
        self.snapshots_root.mkdir(parents=True, exist_ok=True)

    def create_game(
        self,
        *,
        resolve_all_decisions: bool = False,
        use_llm_agents: bool = False,
    ) -> GameRecord:
        game_id = uuid.uuid4().hex[:12]
        snap_dir = self.snapshots_root / game_id
        snap_dir.mkdir(parents=True, exist_ok=True)
        session = GameSession.new(
            resolve_all_decisions=resolve_all_decisions,
            use_llm_agents=use_llm_agents,
            trace_dir=ROOT / "traces" / game_id,
        )
        record = GameRecord(
            game_id=game_id,
            session=session,
            snapshot_dir=snap_dir,
        )
        self._games[game_id] = record
        snap = session.get_snapshot()
        self._persist(record, snap)
        return record

    def get(self, game_id: str) -> GameRecord:
        if game_id not in self._games:
            raise KeyError(game_id)
        return self._games[game_id]

    def _persist(self, record: GameRecord, snapshot: GameSnapshot) -> Path:
        path = record.snapshot_dir / f"turn_{snapshot.turn}.json"
        path.write_text(
            json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if snapshot.turn not in record.history_turns:
            record.history_turns.append(snapshot.turn)
            record.history_turns.sort()
        return path

    def save_snapshot(self, game_id: str, snapshot: GameSnapshot) -> None:
        record = self.get(game_id)
        self._persist(record, snapshot)

    def load_replay(self, game_id: str, turn: int) -> dict:
        record = self.get(game_id)
        path = record.snapshot_dir / f"turn_{turn}.json"
        if not path.exists():
            raise FileNotFoundError(f"回合 {turn} 无快照")
        return json.loads(path.read_text(encoding="utf-8"))


store = GameStore()
