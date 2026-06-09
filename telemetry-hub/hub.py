import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import List, Dict, Optional
import json
import time as _time

app = FastAPI(title="Antigravity Buddy v2 Hub")

class HubState:
    def __init__(self):
        self.mascot_state = "idle"
        self.pending_prompts: List[dict] = []  # queue of active blocking prompts
        self.tokens_in = 0
        self.tokens_out = 0
        self.active_connections: List[WebSocket] = []
        self.resolved_prompts: Dict[str, dict] = {}
        self.history: List[dict] = []

state = HubState()

class EventPayload(BaseModel):
    session_id: str
    event: str
    timestamp: float
    data: Optional[dict] = None
    prompt: Optional[dict] = None

class ResolutionPayload(BaseModel):
    decision: str
    reason: Optional[str] = ""

async def broadcast(message: dict):
    payload = json.dumps(message)
    disconnected = []
    for ws in state.active_connections:
        try:
            await ws.send_text(payload)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        if ws in state.active_connections:
            state.active_connections.remove(ws)

def _oldest_prompt():
    return state.pending_prompts[0] if state.pending_prompts else None

def _remove_prompt(prompt_id):
    for i, p in enumerate(state.pending_prompts):
        if p.get("id") == prompt_id:
            state.pending_prompts.pop(i)
            return True
    return False

def _build_state_sync(new_event=None):
    return {
        "type": "state_sync",
        "mascot_state": state.mascot_state,
        "pending_prompts": list(state.pending_prompts),
        "new_event": new_event
    }

@app.get("/debug/history")
async def get_history():
    return {
        "mascot_state": state.mascot_state,
        "pending_prompts": state.pending_prompts,
        "connection_count": len(state.active_connections),
        "history_count": len(state.history),
        "history": state.history
    }

@app.get("/debug/state")
async def get_state():
    return {
        "mascot_state": state.mascot_state,
        "pending_count": len(state.pending_prompts),
        "oldest_prompt_id": _oldest_prompt().get("id") if _oldest_prompt() else None,
        "connections": len(state.active_connections),
        "resolved_count": len(state.resolved_prompts)
    }

@app.post("/event")
async def receive_event(payload: EventPayload):
    event = payload.event

    if event == "SessionStart":
        state.mascot_state = "celebrate"
        state.pending_prompts.clear()
    elif event == "BeforeAgent":
        state.mascot_state = "idle"
    elif event == "BeforeModel" or event == "State Thinking":
        state.mascot_state = "thinking"
    elif event == "AfterModel" or event == "State Thinking Done":
        state.mascot_state = "busy"
    elif event == "AfterAgent" or event == "State Concluded":
        state.mascot_state = "sleep"
    elif event == "PostToolUse":
        state.mascot_state = "idle"
    elif (event == "BeforeTool" or event == "PreToolUse") and payload.prompt:
        state.mascot_state = "attention"
        # Append to queue — never overwrite existing prompts
        state.pending_prompts.append(payload.prompt)

    log_item = {
        "event": event,
        "timestamp": payload.timestamp,
        "session_id": payload.session_id,
        "data": payload.data,
        "prompt": payload.prompt
    }
    state.history.append(log_item)
    if len(state.history) > 50:
        state.history.pop(0)

    await broadcast(_build_state_sync(new_event=log_item))
    return {"ok": True, "mascot_state": state.mascot_state}

@app.get("/prompt/{prompt_id}")
async def get_prompt_status(prompt_id: str):
    if prompt_id in state.resolved_prompts:
        res = state.resolved_prompts[prompt_id]
        return {"resolved": True, "decision": res["decision"], "reason": res["reason"]}
    return {"resolved": False}

@app.post("/prompt/{prompt_id}/resolve")
async def resolve_prompt(prompt_id: str, resolution: ResolutionPayload):
    state.resolved_prompts[prompt_id] = {
        "decision": resolution.decision,
        "reason": resolution.reason
    }

    removed = _remove_prompt(prompt_id)
    if removed:
        if not state.pending_prompts:
            state.mascot_state = "dizzy" if resolution.decision == "deny" else "celebrate"
        # else: still more prompts pending, keep attention state

    resolve_item = {
        "event": "PromptResolved",
        "timestamp": _time.time(),
        "session_id": "default_session",
        "data": {"prompt_id": prompt_id, "decision": resolution.decision, "reason": resolution.reason},
        "prompt": None
    }
    state.history.append(resolve_item)
    if len(state.history) > 50:
        state.history.pop(0)

    await broadcast(_build_state_sync(new_event=resolve_item))
    return {"ok": True}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    state.active_connections.append(websocket)
    try:
        await websocket.send_json({
            "type": "state_sync",
            "mascot_state": state.mascot_state,
            "pending_prompts": list(state.pending_prompts),
            "history": state.history
        })
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("event") == "resolve":
                # Resolve specific prompt_id if provided, otherwise oldest pending
                p_id = msg.get("prompt_id")
                if not p_id:
                    oldest = _oldest_prompt()
                    if not oldest:
                        continue
                    p_id = oldest.get("id")
                decision = msg.get("decision", "deny")
                reason = msg.get("reason", "WebSocket resolution")
                state.resolved_prompts[p_id] = {"decision": decision, "reason": reason}
                _remove_prompt(p_id)

                if not state.pending_prompts:
                    state.mascot_state = "dizzy" if decision == "deny" else "celebrate"

                resolve_item = {
                    "event": "PromptResolved",
                    "timestamp": _time.time(),
                    "session_id": "default_session",
                    "data": {"prompt_id": p_id, "decision": decision, "reason": reason},
                    "prompt": None
                }
                state.history.append(resolve_item)
                if len(state.history) > 50:
                    state.history.pop(0)

                await broadcast(_build_state_sync(new_event=resolve_item))
    except WebSocketDisconnect:
        if websocket in state.active_connections:
            state.active_connections.remove(websocket)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=38900)
