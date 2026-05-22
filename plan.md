# 东亚风云 — 实施计划 (plan.md)

本文档与 [README.md](README.md) 配套，记录分阶段交付目标、模块划分与验收标准。  
**当前进度**：阶段 3 已完成；阶段 4 待开始。

---

## 项目目标（复述）

构建一款 **东亚二战多 Agent 战略模拟器**：

- **Multi-agent**：日本、中国、苏联等独立 Agent 并行决策；共享环境；Merger 解决冲突。
- **结构化世界**：区域控制、资源、补给线、事件脚本；非 RAG 主链路。
- **玩家固定中国**：3 个关键决断点（可 YAML 扩展）用自然语言注入 `StrategicDirective`。
- **图形化演示**：React 战略地图为主，文字纪事为辅。

---

## 阶段总览

| 阶段 | 名称 | 状态 | 交付物 |
|------|------|------|--------|
| 0 | 配置与契约 | ✅ 完成 | scenario YAML、决断加载、schemas、world、snapshot-schema |
| 1 | 世界引擎核心 | ✅ 完成 | Verifier、Merger、apply、events、GameSession.advance_turn |
| 2 | Multi-Agent 层 | ✅ 完成 | observation、四国 Agent、turn_runner、trace |
| 3 | 玩家决断链路 | ✅ 完成 | NL/意图卡→诏令、国力修正、中方 AI 服从 |
| 4 | API 层 | ⬜ 待开始 | FastAPI、snapshot JSON、WebSocket |
| 5 | 前端 MVP | ⬜ 待开始 | SVG 地图、HUD、决断 Modal、回合动画 |
| 6 | 集成与演示 | ⬜ 待开始 | 1941 端到端可录屏 demo |
| 7 | 评测与打磨 | ⬜ 待开始 | 固定 seed 回归、Trace 导出、伦理文案 |

---

## 阶段 0：配置与契约（当前）

### 已完成

- [x] `scenarios/1941.yaml` — 3 决断点 + 2 剧本事件
- [x] `engine/decision_points.py` — `ScenarioConfig`、`pending_decision()`
- [x] `engine/schemas.py` — `Action`, `StrategicDirective`, `GameSnapshot`, `FactionId`
- [x] `engine/world.py` — 32 区邻接表 + `build_initial_snapshot()`
- [x] `data/regions_1941.yaml` — 地图与补给线数据
- [x] `schemas/snapshot-schema.json` — 前后端回合 JSON 契约
- [x] `tests/test_phase0.py` — 验收测试
- [x] `README.md`、`plan.md`

### 验收（已通过 `pytest tests/test_phase0.py`）

- [x] `load_scenario('scenarios/1941.yaml')` 无报错
- [x] `pending_decision()` 在 turn=0 / 事件集合下返回预期决断
- [x] 初始 `GameSnapshot` 符合 `schemas/snapshot-schema.json`

---

## 阶段 1：世界引擎核心

### 已完成模块

```
engine/
  state.py       # GameState、快照互转
  world.py       # 地图加载、build_initial_snapshot
  verifier.py    # 合法性检查
  merger.py      # 多 Action 冲突仲裁
  apply.py       # 行动结算
  combat.py      # 攻势/守势计算
  events.py      # 回合事件触发（珍珠港、1944 危机等）
  turn.py        # GameSession.advance_turn()
  stub_ai.py     # 规则 Bot（集成测试用）
```

### 验收（已通过 `pytest tests/test_phase1.py`）

- [x] 纯 Python：`advance_turn(use_stub_ai=True)` 连续 10 回合无异常
- [x] Merger：中日同时进攻 `central_china` 时一方被合并否决
- [x] Verifier：非邻接进攻、过早苏军入关被拒
- [x] 未决决断时 `advance_turn` 抛出 `PendingDecisionError`

### 区域划分（MVP 约 35 区）

- **中国**：东北、华北、华东、华中、华南、西南 等（可合并细度）
- **日本**：本土、台湾、朝鲜（日占）
- **东南亚**：越南、泰国、马来、缅甸、菲律宾 等块
- **苏联**：远东 2–3 块

### Action 类型（初版）

| Action | 说明 |
|--------|------|
| `advance_front` | 前线推进/争夺 |
| `hold_garrison` | 守备占领区 |
| `guerrilla_operation` | 敌后（降稳定、牵制日军） |
| `raid_supply` | 切断援华/南洋航线 |
| `seek_allied_aid` | 提升同盟援助变量 |
| `pacific_strike` | 日军南进（东南亚区） |
| `soviet_invasion` | 仅 1945 事件后可用 |

### 验收

- 纯 Python 无 LLM：`advance_turn()` 10 回合无异常
- 单元测试：Merger 双方向争夺同一区域、非法 Action 被拒

---

## 阶段 2：Multi-Agent 层

### 已完成模块

```
engine/
  observation.py      # project(state, faction) 不对称情报
  agents/
    base.py           # BaseAgent, MockAgent, LLMAgent（无 Key 回退）
    japan.py / china.py / cpc.py / soviet.py
  turn_runner.py      # asyncio.gather 并行 + traces/
```

### 验收（已通过 `pytest tests/test_phase2.py`）

- [x] 日、中、CPC、苏 **独立** `decide()`，单回合 ≥3 方有行动
- [x] 日本对中国区 `garrison` 仅为 `estimate`，非确认真值
- [x] 中国 `observation.active_directives` 携带诏令；日本不可见
- [x] `traces/{turn}_{faction}.json` 含 reasoning、actions、observation
- [x] `advance_turn(use_multi_agent=True)` 连续 10 回合；`MockAgent` 无 LLM 可跑通

### 用法

```python
session = GameSession.new(resolve_all_decisions=True, trace_dir=Path("traces"))
snap = session.advance_turn(use_multi_agent=True)
```

### LLM：DeepSeek（可选）

- **客户端**：`engine/llm_client.py`（`https://api.deepseek.com`，OpenAI 兼容）
- **默认模型**：`deepseek-chat`（环境变量 `DEEPSEEK_MODEL` 可改为 `deepseek-reasoner` 等）
- **密钥**：本地 `.env` 中 `DEEPSEEK_API_KEY`（勿提交仓库；见 `.env.example`）
- **启用**：`GameSession.new(use_llm_agents=True)` + `advance_turn(use_multi_agent=True)`
- **回退**：未配置 Key、API 失败或 LLM 输出无合法行动时 → 规则 Bot（trace 含 `[deepseek-fallback]` / `[deepseek-error]`）
- **测试**：`pytest tests/test_deepseek.py`（mock，不消耗 API）

---

## 阶段 3：玩家决断链路

### 已完成模块

```
engine/
  player_intent.py   # NL/意图卡解析、非法决断拒绝、可选 DeepSeek
  directives.py      # 诏令生效、立即国力修正、priority 元数据
  turn.py            # GameSession.submit_player_decision()
scripts/
  play_campaign.py   # 交互战役「是英雄还是虫子」
```

### 验收（`pytest tests/test_phase3.py`）

- [x] 3 个决断点各可 `submit_player_decision` 一次
- [x] 非法 NL（占领东京）→ `DirectiveRejectError`
- [x] `hold_core` 中方不出击；`counteroffensive` 可进攻；`guerrilla_expand` 强化中共游击
- [x] 未决断时 `advance_turn` → `PendingDecisionError`

### 交互试玩

```bash
python scripts/play_campaign.py      # 规则+关键词解析
python scripts/play_campaign.py --llm  # DeepSeek 解析自然语言
```

---

## 阶段 4：API 层

### 端点（草案）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/game/new` | 加载 scenario，返回初始 snapshot |
| POST | `/game/advance` | 推进一回合（若待决断则 409） |
| POST | `/game/decision` | 提交玩家决断 |
| GET | `/game/state` | 当前 snapshot |
| GET | `/game/replay/{turn}` | 历史 snapshot |
| WS | `/game/stream` | 自动播放推送 `turn_complete` |

### Snapshot 核心字段

```json
{
  "turn": 7,
  "regions": [{"id": "south_china", "owner": "china", "garrison": 0.6}],
  "routes": [{"id": "burma_road", "status": "open"}],
  "factions": {"china": {"manpower": 400, "supply": 0.5}},
  "actions_played": [{"faction": "japan", "type": "advance", "from": "...", "to": "..."}],
  "active_directives": [{"priority": "hold_burma", "turns_left": 2}],
  "pending_decision": null
}
```

### 验收

- Postman/curl 可完整跑完 5 回合（Mock Agent）
- `snapshots/` 自动持久化每回合 JSON

---

## 阶段 5：前端 MVP

### 技术

- React 18 + TypeScript + Vite
- Tailwind CSS + Framer Motion
- SVG 战略区（`web/src/assets/regions.json`）

### 页面/组件

| 组件 | 职责 |
|------|------|
| `StrategicMap` | 区域着色、点击选中、意图/结算箭头动画 |
| `FactionHUD` | 中国资源、诏令 chip、援华/缅甸路状态 |
| `AgentRadar` | 各方思考中/本回合行动图标 |
| `DecisionModal` | 决断全屏弹窗、NL 输入、建议卡 |
| `Timeline` | 回合回放拖动 |
| `TraceDrawer` | 可折叠 Agent trace（面试用） |

### 视觉

- 暗色战略台、势力色：日/中/苏/盟/中立
- 决断时毛玻璃遮罩 + 地图热点高亮

### 验收

- 浏览器内：新开局 → 决断 1 次 → 自动播 3 回合 → 时间轴回放
- 无需阅读长文本即可理解战局变化

---

## 阶段 6：集成与演示

### 1941 演示脚本（录屏用）

1. 开局决断：选择「扩大游击」或输入 NL
2. 自动播放至回合 6 → 珍珠港事件 → 决断 2
3. 展示日本意图箭头 vs 中国守缅动画
4. 打开 Trace 展示日本 Agent 推理摘要
5. 跳转回合 28 前展示 1944 危机决断（可 cheat `POST /game/advance?to=28` 调试）

### 验收

- 3 分钟录屏可上传作品集
- README 附演示 GIF（可选）

---

## 阶段 7：评测与伦理

### 评测

- `eval/scenarios_1941.json` — 固定 seed、期望事件链、非法 Action 率
- 指标：决断解析成功率、Merger 冲突次数、中国存续回合分布

### 伦理清单（发布前必查）

- [ ] README 标明 alternate history，非史学科普
- [ ] 不出现现代「韩国」国名指代 1940 年代实体
- [ ] 惨案类仅 `Event` 标记 + 固定简短史实备注，无玩法奖励
- [ ] Agent 人格为国家军事决策体，非法西斯宣传口吻

---

## 里程碑时间表（建议）

| 周 | 目标 |
|----|------|
| W1 | 阶段 1 完成 + 单元测试 |
| W2 | 阶段 2–3（Mock LLM 跑通决断） |
| W3 | 阶段 4–5 前端可演示 |
| W4 | 阶段 6–7 接真实 LLM + 录屏 + GitHub Release v0.1 |

---

## 扩展 backlog（非 MVP）

- [ ] 第四决断点：苏军入关前夕（`dp_soviet_entry`）
- [ ] CPC 升级为独立 LLM Agent
- [ ] Agent 间 `DiplomaticMessage` 连线动画
- [ ] Counterfactual 双地图对比（fork 状态）
- [ ] 1937 / 1945-only 短剧本

---

## 变更日志

| 日期 | 内容 |
|------|------|
| 2026-05-22 | 初版 plan；锁定玩家中国、3 决断点、1941 剧本 |
