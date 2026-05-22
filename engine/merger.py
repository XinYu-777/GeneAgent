"""多方行动合并与冲突仲裁。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from engine.schemas import (
    Action,
    AdvanceFrontAction,
    FactionId,
    PacificStrikeAction,
    SovietInvasionAction,
)
from engine.combat import attack_power, defense_power
from engine.state import GameState
from engine.verifier import verify_actions

CONTEST_TYPES = frozenset({"advance_front", "pacific_strike", "soviet_invasion"})


@dataclass(frozen=True)
class ResolvedAction:
    action: Action
    accepted: bool
    message: str | None = None


def _contest_target(action: Action) -> str | None:
    if isinstance(action, AdvanceFrontAction):
        return action.to_region
    if isinstance(action, (PacificStrikeAction, SovietInvasionAction)):
        return action.target_region
    return None


def _pick_attacker(
    state: GameState, contenders: list[Action]
) -> tuple[Action, float]:
    best = contenders[0]
    best_p = -1.0
    for a in contenders:
        fr: str | None = None
        if isinstance(a, AdvanceFrontAction):
            fr = a.from_region
        p = attack_power(state, a.faction, fr)
        if p > best_p:
            best_p = p
            best = a
    return best, best_p


def merge_actions(state: GameState, actions: list[Action]) -> list[ResolvedAction]:
    """校验后合并；同一目标区的进攻行动只保留优势最大一方。"""
    verified = verify_actions(state, actions)
    rejected = [
        ResolvedAction(v.action, False, v.message) for v in verified if not v.accepted
    ]
    accepted_actions = [v.action for v in verified if v.accepted]

    by_target: dict[str, list[Action]] = defaultdict(list)
    non_contest: list[Action] = []

    for action in accepted_actions:
        if action.type in CONTEST_TYPES:
            target = _contest_target(action)
            if target:
                by_target[target].append(action)
            else:
                non_contest.append(action)
        else:
            non_contest.append(action)

    merged: list[ResolvedAction] = list(rejected)
    losers_messages: list[ResolvedAction] = []

    for target, contenders in by_target.items():
        if len(contenders) == 1:
            merged.append(ResolvedAction(contenders[0], True))
            continue
        winner, win_power = _pick_attacker(state, contenders)
        defense = defense_power(state, target)
        for a in contenders:
            if a is winner:
                if win_power >= defense * 0.85:
                    merged.append(ResolvedAction(a, True))
                else:
                    merged.append(
                        ResolvedAction(
                            a,
                            True,
                            f"进攻 {target} 僵持（攻势 {win_power:.1f} vs 守势 {defense:.1f}）",
                        )
                    )
            else:
                losers_messages.append(
                    ResolvedAction(
                        a,
                        False,
                        f"与 {winner.faction.value} 争夺 {target} 失败，行动被合并否决",
                    )
                )

    for action in non_contest:
        merged.append(ResolvedAction(action, True))

    return merged + losers_messages
