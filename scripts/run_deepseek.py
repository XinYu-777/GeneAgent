#!/usr/bin/env python3
"""DeepSeek 多 Agent 试跑（在项目根目录执行）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import GameSession
from engine.llm_client import get_model, is_llm_configured


def main() -> None:
    turns = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    print("LLM:", is_llm_configured(), "| 模型:", get_model())

    session = GameSession.new(
        resolve_all_decisions=True,
        use_llm_agents=True,
        trace_dir=ROOT / "traces",
    )
    for _ in range(turns):
        snap = session.advance_turn(use_multi_agent=True)
        print(f"回合 {snap.turn} | 行动 {len(snap.actions_played)} 条")
    print("完成，trace:", ROOT / "traces")


if __name__ == "__main__":
    main()
