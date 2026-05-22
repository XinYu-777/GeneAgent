"""决断点配置：从 scenario YAML 加载，便于日后追加。"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class DecisionTrigger(BaseModel):
    type: Literal["turn", "event"]
    value: int | str


class SuggestedIntent(BaseModel):
    id: str
    label: str


class DecisionPoint(BaseModel):
    id: str
    order: int
    title: str
    prompt: str
    trigger: DecisionTrigger
    suggested_intents: list[SuggestedIntent] = Field(min_length=1)
    directive_duration_turns: int = Field(ge=1, le=20)


class ScenarioConfig(BaseModel):
    scenario_id: str
    title: str
    start_turn: int = 0
    max_turns: int
    player_faction: Literal["china"] = "china"
    decision_points: list[DecisionPoint]
    events: list[dict] = Field(default_factory=list)

    def decision_points_sorted(self) -> list[DecisionPoint]:
        return sorted(self.decision_points, key=lambda dp: dp.order)

    def pending_decision(
        self,
        turn: int,
        fired_events: set[str],
        resolved_ids: set[str],
    ) -> DecisionPoint | None:
        """返回当前应触发的下一个未处理决断（按 order）。"""
        for dp in self.decision_points_sorted():
            if dp.id in resolved_ids:
                continue
            t = dp.trigger
            if t.type == "turn" and turn == t.value:
                return dp
            if t.type == "event" and t.value in fired_events:
                return dp
        return None


def load_scenario(path: str | Path) -> ScenarioConfig:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return ScenarioConfig.model_validate(data)
