"""东亚风云 FastAPI 应用。"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from api.schemas import (
    AdvanceRequest,
    AdvanceResponse,
    DecisionRequest,
    DecisionResponse,
    ErrorResponse,
    NewGameRequest,
    NewGameResponse,
    StateResponse,
)
from api.store import store
from engine.player_intent import DirectiveRejectError
from engine.turn import PendingDecisionError

app = FastAPI(
    title="东亚风云 API",
    description="East Asia WWII multi-agent strategic simulation",
    version="0.4.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _snap_dict(snap) -> dict[str, Any]:
    return snap.model_dump(mode="json")


def _pending_payload(session) -> dict | None:
    dp = session.get_pending_decision_point()
    if not dp:
        return None
    from engine.world import decision_to_pending_snapshot

    return decision_to_pending_snapshot(dp).model_dump(mode="json")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "dongya-fengyun"}


@app.post("/game/new", response_model=NewGameResponse)
def game_new(body: NewGameRequest) -> NewGameResponse:
    record = store.create_game(
        resolve_all_decisions=body.resolve_all_decisions,
        use_llm_agents=body.use_llm_agents,
    )
    snap = record.session.get_snapshot()
    return NewGameResponse(game_id=record.game_id, snapshot=_snap_dict(snap))


@app.get("/game/state", response_model=StateResponse)
def game_state(game_id: str) -> StateResponse:
    try:
        record = store.get(game_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="对局不存在") from None
    snap = record.session.get_snapshot()
    return StateResponse(game_id=game_id, snapshot=_snap_dict(snap))


@app.get("/game/replay/{turn}")
def game_replay(turn: int, game_id: str) -> dict[str, Any]:
    try:
        return store.load_replay(game_id, turn)
    except KeyError:
        raise HTTPException(status_code=404, detail="对局不存在") from None
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None


@app.post("/game/decision", response_model=DecisionResponse)
def game_decision(body: DecisionRequest) -> DecisionResponse:
    try:
        record = store.get(body.game_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="对局不存在") from None

    try:
        directive, summary = record.session.submit_player_decision(
            intent_id=body.intent_id,
            text=body.text,
            use_llm=body.use_llm,
        )
    except DirectiveRejectError as e:
        raise HTTPException(
            status_code=422,
            detail=ErrorResponse(detail=str(e), code="directive_rejected").model_dump(
                mode="json"
            ),
        ) from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    snap = record.session.get_snapshot()
    store.save_snapshot(body.game_id, snap)
    return DecisionResponse(
        directive=directive.model_dump(mode="json"),
        summary=summary,
        snapshot=_snap_dict(snap),
    )


@app.post("/game/advance", response_model=AdvanceResponse)
def game_advance(body: AdvanceRequest) -> AdvanceResponse:
    try:
        record = store.get(body.game_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="对局不存在") from None

    session = record.session
    try:
        snap = session.advance_turn(
            use_stub_ai=body.use_stub_ai,
            use_multi_agent=body.use_multi_agent,
        )
    except PendingDecisionError as e:
        raise HTTPException(
            status_code=409,
            detail=ErrorResponse(
                detail=str(e),
                code="pending_decision",
                pending_decision=_pending_payload(session),
            ).model_dump(mode="json"),
        ) from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    store.save_snapshot(body.game_id, snap)
    return AdvanceResponse(snapshot=_snap_dict(snap))


@app.websocket("/game/stream")
async def game_stream(
    websocket: WebSocket,
    game_id: str,
    interval_ms: int = 800,
    max_steps: int = 10,
    use_stub_ai: bool = True,
) -> None:
    """推送回合推进事件；需已处理所有决断。"""
    await websocket.accept()
    try:
        record = store.get(game_id)
    except KeyError:
        await websocket.send_json({"event": "error", "detail": "对局不存在"})
        await websocket.close()
        return

    session = record.session
    try:
        for step in range(max_steps):
            if session.has_pending_decision():
                await websocket.send_json(
                    {
                        "event": "decision_required",
                        "pending_decision": _pending_payload(session),
                        "turn": session.state.turn,
                    }
                )
                break

            snap = session.advance_turn(
                use_stub_ai=use_stub_ai,
                use_multi_agent=True,
            )
            store.save_snapshot(game_id, snap)
            await websocket.send_json(
                {
                    "event": "turn_complete",
                    "step": step + 1,
                    "snapshot": _snap_dict(snap),
                }
            )
            if session.state.turn >= session.state.scenario.max_turns:
                await websocket.send_json({"event": "game_over", "turn": snap.turn})
                break
            await asyncio.sleep(interval_ms / 1000.0)
    except WebSocketDisconnect:
        return
    except PendingDecisionError:
        await websocket.send_json(
            {
                "event": "decision_required",
                "pending_decision": _pending_payload(session),
            }
        )
    except Exception as e:
        await websocket.send_json({"event": "error", "detail": str(e)})
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
