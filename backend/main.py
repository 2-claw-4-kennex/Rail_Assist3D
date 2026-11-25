import asyncio
import json
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from services.llm import gemini_agent
from services.railradar import railradar

BOARD_FILE = Path(__file__).parent / "data" / "lucknow_board.json"


def load_board() -> dict:
    if not BOARD_FILE.exists():
        return {"station": "Lucknow Station", "arrivals": [], "departures": []}
    return json.loads(BOARD_FILE.read_text(encoding="utf-8"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await railradar.close()
    await gemini_agent.close()


app = FastAPI(title="RailAssist 3D", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    text: str
    session_id: str = "http-default"


async def process_query(session_id: str, user_text: str) -> dict:
    t0 = time.perf_counter()
    cleaned = user_text.strip()
    if not cleaned:
        return {
            "transcript": "",
            "reply": "I could not hear you. Ask me about any train by name or number.",
            "animation": "talk",
            "liveTrain": None,
            "latencyMs": int((time.perf_counter() - t0) * 1000),
        }

    result = await gemini_agent.chat(session_id, cleaned, load_board())
    return {
        "transcript": cleaned,
        "reply": result["reply"],
        "animation": result["animation"],
        "liveTrain": result["liveTrain"],
        "latencyMs": int((time.perf_counter() - t0) * 1000),
    }


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/board")
async def get_board():
    return load_board()


@app.get("/api/train/{train_no}/live")
async def get_live_train(train_no: str, authoritative: bool = False):
    res = await railradar.get_live_train(train_no, authoritative=authoritative)
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=res.get("error", "UPSTREAM_FAILURE"))
    return res["data"]


@app.post("/api/query")
async def query_text(req: QueryRequest):
    try:
        return await asyncio.wait_for(process_query(req.session_id, req.text), timeout=25.0)
    except asyncio.TimeoutError:
        return {
            "transcript": req.text,
            "reply": "Request timed out. Please try again.",
            "animation": "talk",
            "liveTrain": None,
            "latencyMs": 25000,
        }
    except Exception as exc:
        print(f"[HTTP ERROR] {exc}")
        return {
            "transcript": req.text,
            "reply": f"Backend error: {exc}",
            "animation": "talk",
            "liveTrain": None,
            "latencyMs": 0,
        }


@app.websocket("/ws/chat")
async def ws_chat(ws: WebSocket):
    await ws.accept()
    session_id = str(uuid.uuid4())
    try:
        while True:
            raw = await ws.receive_text()
            payload = json.loads(raw)
            text = payload.get("text", "")
            await ws.send_json({"type": "state", "state": "processing"})
            try:
                result = await asyncio.wait_for(process_query(session_id, text), timeout=25.0)
            except asyncio.TimeoutError:
                result = {
                    "transcript": text,
                    "reply": "Request timed out. Please try again.",
                    "animation": "talk",
                    "liveTrain": None,
                    "latencyMs": 25000,
                }
            except Exception as exc:
                print(f"[WS ERROR] {exc}")
                result = {
                    "transcript": text,
                    "reply": f"Backend error: {exc}",
                    "animation": "talk",
                    "liveTrain": None,
                    "latencyMs": 0,
                }
            await ws.send_json({"type": "response", **result})
    except WebSocketDisconnect:
        gemini_agent.clear_session(session_id)