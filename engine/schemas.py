"""阶段 0 核心数据契约：势力、行动、玩家诏令、回合快照。"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class FactionId(str, Enum):
    CHINA = "china"
    JAPAN = "japan"
    SOVIET = "soviet"
    CPC = "cpc"
    ALLIED = "allied"
    NEUTRAL = "neutral"


class DiplomacyTone(str, Enum):
    URGENT = "urgent"
    MODERATE = "moderate"
    CAUTIOUS = "cautious"


class RouteStatus(str, Enum):
    OPEN = "open"
    CUT = "cut"
    CONTESTED = "contested"


# --- Actions (阶段 1+ 引擎消费；阶段 0 定义契约) ---


class ActionBase(BaseModel):
    faction: FactionId


class AdvanceFrontAction(ActionBase):
    type: Literal["advance_front"] = "advance_front"
    from_region: str
    to_region: str


class HoldGarrisonAction(ActionBase):
    type: Literal["hold_garrison"] = "hold_garrison"
    region: str


class GuerrillaOperationAction(ActionBase):
    type: Literal["guerrilla_operation"] = "guerrilla_operation"
    region: str


class RaidSupplyAction(ActionBase):
    type: Literal["raid_supply"] = "raid_supply"
    route_id: str


class SeekAlliedAidAction(ActionBase):
    type: Literal["seek_allied_aid"] = "seek_allied_aid"


class PacificStrikeAction(ActionBase):
    type: Literal["pacific_strike"] = "pacific_strike"
    target_region: str


class SovietInvasionAction(ActionBase):
    type: Literal["soviet_invasion"] = "soviet_invasion"
    target_region: str


Action = Annotated[
    AdvanceFrontAction
    | HoldGarrisonAction
    | GuerrillaOperationAction
    | RaidSupplyAction
    | SeekAlliedAidAction
    | PacificStrikeAction
    | SovietInvasionAction,
    Field(discriminator="type"),
]


class ActionPlayed(BaseModel):
    """写入快照的行动记录（含结算结果占位）。"""

    faction: FactionId
    action: Action
    accepted: bool = True
    message: str | None = None


# --- 玩家战略诏令 ---


class StrategicDirective(BaseModel):
    """玩家决断解析结果，仅注入 China Agent。"""

    priority: str = Field(description="对应 suggested_intents.id 或组合策略名")
    resource_bias: dict[str, float] = Field(default_factory=dict)
    diplomacy_tone: DiplomacyTone = DiplomacyTone.MODERATE
    duration_turns: int = Field(ge=1, le=20)
    raw_quote: str = ""
    source_decision_id: str | None = None


class ActiveDirective(BaseModel):
    """生效中的诏令（带剩余回合）。"""

    directive: StrategicDirective
    turns_left: int


# --- 快照子结构 ---


class RegionSnapshot(BaseModel):
    id: str
    name: str
    owner: FactionId
    garrison: float = Field(ge=0.0, le=1.0, description="驻军强度 0-1")
    unrest: float = Field(default=0.0, ge=0.0, le=1.0)


class RouteSnapshot(BaseModel):
    id: str
    name: str
    status: RouteStatus


class FactionSnapshot(BaseModel):
    manpower: int = Field(ge=0)
    supply: float = Field(ge=0.0, le=1.0)
    morale: float = Field(default=0.5, ge=0.0, le=1.0)
    industrial_capacity: float = Field(default=0.5, ge=0.0, le=1.0)


class PendingDecisionSnapshot(BaseModel):
    """前端决断弹窗所需字段。"""

    id: str
    title: str
    prompt: str
    suggested_intents: list[dict[str, str]]


class GameSnapshot(BaseModel):
    """单回合完整 UI/回放状态（前后端契约）。"""

    scenario_id: str
    title: str
    turn: int
    regions: list[RegionSnapshot]
    routes: list[RouteSnapshot]
    factions: dict[str, FactionSnapshot]
    actions_played: list[ActionPlayed] = Field(default_factory=list)
    active_directives: list[ActiveDirective] = Field(default_factory=list)
    pending_decision: PendingDecisionSnapshot | None = None
    fired_events: list[str] = Field(default_factory=list)

    def model_dump_json_ready(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
