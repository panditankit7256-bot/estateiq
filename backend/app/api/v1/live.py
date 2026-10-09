import asyncio, json
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from ...core.security import decode_token, require_roles
from ...services import live as L
from ..deps import facility_id

router = APIRouter(tags=["live"])
subscribers: set[asyncio.Queue] = set()


class Spike(BaseModel):
    kind: str = Field(pattern="^(leak|pollution|energy|bins|outage|advance)$")


@router.post("/simulate/spike")
async def spike(body: Spike, fid: str = Depends(facility_id), user: dict = Depends(require_roles("administrator", "operations"))):
    """Demo helper: append 3 simulated hours, optionally with an injected incident, and notify live clients."""
    res = await asyncio.to_thread(L.append_hours, fid, None if body.kind == "advance" else body.kind)
    event = {"type": "data_update", "facility": fid, **res}
    for q in list(subscribers):
        q.put_nowait(event)
    return res


@router.websocket("/ws/live")
async def live(ws: WebSocket, token: str = Query(...)):
    try:
        decode_token(token)
    except Exception:
        await ws.close(code=4401); return
    await ws.accept()
    q: asyncio.Queue = asyncio.Queue()
    subscribers.add(q)
    try:
        await ws.send_text(json.dumps({"type": "hello"}))
        while True:
            try:
                await ws.send_text(json.dumps(await asyncio.wait_for(q.get(), 20)))
            except asyncio.TimeoutError:
                await ws.send_text(json.dumps({"type": "ping"}))
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        subscribers.discard(q)
