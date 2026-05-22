# 东亚风云 · East Asia WWII Multi-Agent Sim

> **Human-in-the-loop multi-agent** 东亚二战战略模拟：多个独立 LLM Agent 在共享结构化世界上博弈；玩家固定扮演 **中国统帅**，在关键决断点用自然语言左右本国战略；前端以 **图形化战略地图** 回放各方意图与结算结果。

本项目不是 RAG 问答，也不是纯文字战报——核心是 **可验证的世界状态 + 多 Agent 并行决策 + 优美可交互演示**。

---

## 特性概览

| 维度 | 设计 |
|------|------|
| **地理范围** | 中国、日本、朝鲜半岛（日占期）、东南亚、苏联远东 |
| **剧本 MVP** | `1941`（太平洋战争爆发前后） |
| **Multi-Agent** | 日本 / 中国 / 中共(可选) / 苏联远东 等 **独立** LLM Agent，每回合并行出招，由 Merger + Verifier 合并 |
| **玩家** | **固定绑定中国**；不扮演轴心或苏联 |
| **Human-in-the-loop** | **3 个关键决断点**（可扩展）：自然语言 → `StrategicDirective` → 仅约束 `ChinaSupreme` Agent |
| **世界模型** | 结构化区域图、资源、补给线、外交关系、不对称情报（非向量 RAG） |
| **前端** | React + SVG 战略地图、意图箭头动画、决断弹窗、Agent Trace 抽屉、回合回放时间轴 |

---

## 架构示意

```text
玩家（中国统帅）── NL 决断 ──► StrategicDirective
                                    │
                                    ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ JapanHQ     │  │ ChinaSupreme│  │ CPCBase*    │  │ SovietFarEast│
│ Agent       │  │ Agent       │  │ Agent       │  │ Agent        │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬───────┘
       │                │                │                │
       └────────────────┴────────────────┴────────────────┘
                                │
                         Merger + Verifier
                                │
                         World State S_t
                                │
                    FastAPI / WebSocket
                                │
                         React 战略地图 UI
```

\* MVP 阶段中共可用规则 Bot，二期升级为独立 LLM Agent。

---

## 三个决断点（1941 剧本）

配置见 [`scenarios/1941.yaml`](scenarios/1941.yaml)，新增决断点只需在 YAML 中追加条目。

| 顺序 | ID | 触发 | 主题 |
|------|-----|------|------|
| 1 | `dp_opening_strategy` | 回合 0 | 抗战初期总体战略 |
| 2 | `dp_post_pearl_harbor` | 事件 `evt_pearl_harbor` | 珍珠港后援华线与同盟国沟通 |
| 3 | `dp_1944_crisis` | 事件 `evt_china_1944_pressure` | 战线危机：反击 / 求援 / 收缩 |

---

## 仓库结构

```text
GeneAgent/
├── README.md
├── plan.md                 # 实施计划与里程碑
├── requirements.txt
├── scenarios/
│   └── 1941.yaml           # 剧本、事件、决断点
├── data/
│   └── regions_1941.yaml   # 32 战略区 + 补给线
├── schemas/
│   └── snapshot-schema.json
├── engine/
│   ├── decision_points.py
│   ├── schemas.py          # Action / GameSnapshot / StrategicDirective
│   ├── state.py            # GameState
│   ├── world.py            # 地图加载与初始快照
│   ├── verifier.py / merger.py / apply.py / events.py / turn.py
│   ├── observation.py / turn_runner.py
│   ├── agents/             # 日/中/CPC/苏 独立 Agent
│   └── stub_ai.py
├── tests/
│   ├── test_phase0.py
│   ├── test_phase1.py
│   └── test_phase2.py      # Multi-Agent 验收
├── api/                    # [待建] FastAPI
├── web/                    # [待建] React 前端
└── snapshots/              # [待建] 回合回放 JSON
```

详细开发阶段见 **[plan.md](plan.md)**。

---

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 20+（前端阶段）

### 安装依赖

```bash
cd GeneAgent
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 验证场景配置与阶段 0 验收

```bash
pytest tests/ -v
```

或手动检查：

```bash
python -c "from engine import load_scenario, build_initial_snapshot; s=load_scenario('scenarios/1941.yaml'); print(s.title, len(s.decision_points)); snap=build_initial_snapshot(); print(snap.turn, snap.pending_decision.id, len(snap.regions))"
```

预期：3 个决断点；回合 0 待决断为 `dp_opening_strategy`；地图 30 区。

### DeepSeek（各国 Agent LLM）

**请勿在聊天或代码仓库中提交 API Key。** 在项目根目录创建 `.env`：

```bash
cp .env.example .env
# 编辑 .env，填入：
# DEEPSEEK_API_KEY=sk-...
```

### 统帅部决断（阶段 3）

```bash
python scripts/play_campaign.py       # 三处决断点，自然语言/数字选意图
python scripts/play_campaign.py --llm  # 用 DeepSeek 理解你的战略诏令
```

`submit_player_decision(text="不惜代价保住滇缅公路")` → 诏令注入中国 Agent + 立即修正国力。

---

启用 LLM 推进回合：

```python
from pathlib import Path
from engine import GameSession

session = GameSession.new(
    resolve_all_decisions=True,
    use_llm_agents=True,
    trace_dir=Path("traces"),
)
session.advance_turn(use_multi_agent=True)
```

- **API**：`https://api.deepseek.com`（OpenAI 兼容）
- **默认模型**：`deepseek-chat`（可用环境变量 `DEEPSEEK_MODEL` 覆盖，如 `deepseek-reasoner`）
- **未配置 Key**：自动回退规则 Bot，trace 中 reasoning 含 `[deepseek-fallback]`

---

## 设计原则

1. **数值与胜负由规则引擎决定**，LLM 只产出结构化 `Action`，经 Verifier 校验。
2. **一国一 Agent 一次调用**，避免单 prompt 模拟多国（伪 Multi-Agent）。
3. **玩家自然语言不直接改地图**，只生成有时效的 `StrategicDirective` 注入中国 Agent。
4. **史官/战报为附属**，主界面是地图动画与 HUD；纪事需可追溯到 `event_id`。
5. **Alternate history 模拟器**，非史学科普；敏感事件不做游戏化机制，详见 plan.md 伦理节。

---

## 技术栈（目标）

| 层 | 技术 |
|----|------|
| 引擎 | Python, Pydantic, asyncio |
| Agent | 可插拔 LLM 接口（OpenAI / 兼容 API） |
| API | FastAPI, WebSocket |
| 前端 | React, TypeScript, Tailwind, Framer Motion, SVG 地图 |

---

## 许可证与声明

- 代码许可证：MIT（见 [LICENSE](LICENSE)）
- 内容声明：本项目为 **架空战略仿真**；日占朝鲜、东南亚殖民等使用历史语境表述，**不美化侵略、不将惨案机制化为玩法**。

---

## 相关文档

- [plan.md](plan.md) — 分阶段实施计划、API 契约草案、评测与伦理清单

---

## 发布到 GitHub

本地仓库已初始化并完成首次提交。若远程尚未创建，在终端执行（需已安装 [GitHub CLI](https://cli.github.com/) 并登录）：

```bash
cd GeneAgent
gh auth login
gh repo create GeneAgent --public \
  --description "East Asia WWII multi-agent strategic sim (东亚风云)" \
  --source=. --remote=origin --push
```

若仓库已在网页端创建（例如 `https://github.com/<你的用户名>/GeneAgent`），则：

```bash
git remote add origin git@github.com:<你的用户名>/GeneAgent.git
git push -u origin main
```

---

## 贡献

欢迎 Issue / PR。扩展决断点请只修改 `scenarios/*.yaml` 并补充 `events` 与引擎效果实现。
