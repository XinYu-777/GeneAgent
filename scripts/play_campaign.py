#!/usr/bin/env python3
"""东亚风云 · 统帅部战役（玩家决断影响战局）"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import GameSession
from engine.llm_client import is_llm_configured
from engine.player_intent import DirectiveRejectError
from engine.turn import PendingDecisionError

BANNER = """
╔══════════════════════════════════════╗
║   东亚风云 · 1941                     ║
║   是英雄还是虫子 —— 在此一搏          ║
╚══════════════════════════════════════╝
"""


def _prompt_decision(session: GameSession, use_llm: bool) -> None:
    dp = session.get_pending_decision_point()
    if not dp:
        return
    print("\n" + "═" * 44)
    print(f"【{dp.title}】")
    print(dp.prompt)
    print("─" * 44)
    for i, intent in enumerate(dp.suggested_intents, 1):
        print(f"  {i}. [{intent.id}] {intent.label}")
    print("  或直接输入你的战略诏令（自然语言）")
    print("═" * 44)

    while True:
        raw = input("\n统帅部决断 > ").strip()
        if not raw:
            continue
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(dp.suggested_intents):
                intent = dp.suggested_intents[idx]
                try:
                    d, summary = session.submit_player_decision(
                        intent_id=intent.id,
                        text=intent.label,
                        use_llm=use_llm,
                    )
                    print(f"\n✓ 诏令生效：{d.priority}")
                    print(f"  {summary}")
                    if d.raw_quote:
                        print(f"  「{d.raw_quote}」")
                    return
                except DirectiveRejectError as e:
                    print(f"\n✗ {e}")
                    continue
        try:
            d, summary = session.submit_player_decision(
                text=raw, use_llm=use_llm
            )
            print(f"\n✓ 诏令生效：{d.priority}")
            print(f"  {summary}")
            print(f"  「{d.raw_quote}」")
            return
        except DirectiveRejectError as e:
            print(f"\n✗ {e}")
            print("  请调整措辞，或输入数字选择建议意图。")


def main() -> None:
    use_llm = "--llm" in sys.argv
    max_turns = 15
    for arg in sys.argv[1:]:
        if arg.isdigit():
            max_turns = int(arg)

    print(BANNER)
    print("DeepSeek 解析决断:", use_llm and is_llm_configured())
    print("多方 Agent:", "开启" if use_llm else "规则+诏令（加 --llm 启用 AI）")

    session = GameSession.new(
        trace_dir=ROOT / "traces",
        use_llm_agents=use_llm,
    )

    while session.state.turn < min(max_turns, session.state.scenario.max_turns):
        if session.has_pending_decision():
            _prompt_decision(session, use_llm)
        try:
            snap = session.advance_turn(use_multi_agent=True)
        except PendingDecisionError:
            _prompt_decision(session, use_llm)
            snap = session.advance_turn(use_multi_agent=True)

        china = session.state.factions[__import__("engine.schemas", fromlist=["FactionId"]).FactionId.CHINA]
        print(
            f"\n── 回合 {snap.turn} 终局 ── 人力 {china.manpower} "
            f"补给 {china.supply:.2f} 士气 {china.morale:.2f}"
        )
        if session.state.active_directives:
            ad = session.state.active_directives[0]
            print(
                f"   诏令 [{ad.directive.priority}] 剩余 {ad.turns_left} 回合"
            )
        n = len(snap.actions_played)
        print(f"   本回合行动 {n} 条")

    print("\n战役阶段结束。轨迹见 traces/")


if __name__ == "__main__":
    main()
