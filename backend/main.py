"""
RailAssist 3D: Conversational Railway Enquiry Kiosk — FastAPI Orchestrator
Document Owner: Aryan Sanskar Ahuja (Bennett University, SCSET)
Target Hardware: Intel Core i5-13450HX + NVIDIA RTX 4060 (8GB VRAM)

Pipeline:
Audio/Text In -> Faster-Whisper STT (CPU) -> Qwen 2.5 3B Intent Engine (GPU)
-> Hybrid Lucknow Edge Cache / RapidAPI Router -> Piper / Browser Neural TTS -> Speech + Telemetry Out
"""

import asyncio
import base64
import contextlib
import json
import logging
import time
from typing import Any, Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import settings
from services.llm_service import llm_service
from services.metrics import metrics_tracker
from services.railway_router import railway_router, RailwayAPIError
from services.stt_service import stt_service
from services.tts_service import tts_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("railassist.main")

CONVERSATIONAL_NON_TRAIN_INTENTS = {
    "GENERAL_GREETING",
    "SMALL_TALK",
    "STATION_FACILITY",
}


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    stt_service.warm_up_background()
    await railway_router.start_background_worker()
    yield
    await railway_router.stop_background_worker()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Full-duplex multimodal railway enquiry kiosk backend for Lucknow Charbagh (LKO). "
        "Combines Faster-Whisper CPU STT, Qwen 2.5 3B Q4_K_M GPU intent extraction, "
        "Hybrid 5-minute edge cache + RapidAPI routing, and clear Hindi/English TTS."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TextEnquiryRequest(BaseModel):
    query: str
    simulate_http_status: Optional[int] = None


async def execute_kiosk_pipeline(
    *,
    audio_bytes: bytes = b"",
    text_override: Optional[str] = None,
    simulate_http_status: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Executes the headless orchestration pipeline:
    Audio/Text -> STT -> Qwen 2.5 Intent -> Hybrid Cache/RapidAPI -> Neural/Piper TTS -> Payload
    """
    pipeline_t0 = time.perf_counter()

    try:
        # 1. Speech-to-Text in worker thread with strict 2.2s timeout
        try:
            stt_result = await asyncio.wait_for(
                asyncio.to_thread(
                    stt_service.transcribe_audio_bytes,
                    audio_bytes,
                    text_override,
                ),
                timeout=2.2,
            )
        except asyncio.TimeoutError:
            stt_result = {
                "text": (text_override or "").strip(),
                "language": "hi",
                "latency_ms": 2200.0,
                "is_confident": bool(text_override and text_override.strip()),
                "engine": "faster-whisper-timeout-fallback",
            }

        transcript = stt_result["text"]
        stt_ms = stt_result["latency_ms"]

        # Requirement N3: Unintelligible or empty audio failsafe
        if not stt_result["is_confident"] or not transcript.strip():
            metrics_tracker.record_error()
            tts_payload = await asyncio.to_thread(
                tts_service.synthesize_speech_payload, settings.MSG_UNINTELLIGIBLE_HI
            )
            wav_b64 = (
                base64.b64encode(tts_payload["wav_bytes"]).decode("ascii")
                if tts_payload["wav_bytes"]
                else None
            )
            total_rtt_ms = round((time.perf_counter() - pipeline_t0) * 1000.0, 1)
            return {
                "type": "kiosk_response",
                "state": "ERROR",
                "error_code": "UNINTELLIGIBLE_AUDIO",
                "transcript": transcript or "(आवाज़ स्पष्ट नहीं हुई — कृपया फिर से बोलें या नीचे टाइप करें)",
                "intent": {"intent": "UNKNOWN", "train_number": None, "train_name": None},
                "train": None,
                "spoken_text": "मैं आपकी बात सुन नहीं पाया, कृपया माइक बटन दबाकर दोबारा बोलें या नीचे टाइप करें।",
                "display_en": "Could not hear clearly. Hold the mic button and speak again, tap a quick query chip, or type below.",
                "audio_wav_base64": wav_b64,
                "use_browser_tts": bool(tts_payload["use_browser_tts"]),
                "tts_engine": tts_payload["tts_engine"],
                "latency": {
                    "stt_ms": stt_ms,
                    "llm_ms": 0.0,
                    "router_ms": 0.0,
                    "tts_ms": tts_payload["latency_ms"],
                    "total_rtt_ms": total_rtt_ms,
                    "cache_hit": False,
                },
                "kpis": metrics_tracker.snapshot(),
            }

        # 2. LLM Intent & Entity Extraction (Supports English, Hinglish, and Devanagari)
        intent_data = await llm_service.extract_intent_and_entity(transcript)
        llm_ms = intent_data.get("latency_ms", 0.0)

        # 3. Hybrid Data Routing (5-minute Lucknow JSON Cache vs. On-Demand RapidAPI)
        router_t0 = time.perf_counter()
        train_info: Optional[Dict[str, Any]] = None
        is_cache_hit = True

        try:
            if (
                intent_data["intent"] not in CONVERSATIONAL_NON_TRAIN_INTENTS
                or simulate_http_status is not None
            ):
                train_info, is_cache_hit = await railway_router.resolve_train_telemetry(
                    train_number=intent_data.get("train_number"),
                    train_name=intent_data.get("train_name"),
                    raw_query=transcript,
                    simulate_http_status=simulate_http_status,
                )
        except RailwayAPIError as api_err:
            metrics_tracker.record_error()
            router_ms = round((time.perf_counter() - router_t0) * 1000.0, 1)
            tts_payload = await asyncio.to_thread(
                tts_service.synthesize_speech_payload, api_err.spoken_hi
            )
            wav_b64 = (
                base64.b64encode(tts_payload["wav_bytes"]).decode("ascii")
                if tts_payload["wav_bytes"]
                else None
            )
            total_rtt_ms = round((time.perf_counter() - pipeline_t0) * 1000.0, 1)
            return {
                "type": "kiosk_response",
                "state": "ERROR",
                "error_code": f"HTTP_{api_err.status_code}",
                "transcript": transcript,
                "intent": intent_data,
                "train": None,
                "spoken_text": api_err.spoken_hi,
                "display_en": str(api_err),
                "audio_wav_base64": wav_b64,
                "use_browser_tts": bool(tts_payload["use_browser_tts"]),
                "tts_engine": tts_payload["tts_engine"],
                "latency": {
                    "stt_ms": stt_ms,
                    "llm_ms": llm_ms,
                    "router_ms": router_ms,
                    "tts_ms": tts_payload["latency_ms"],
                    "total_rtt_ms": total_rtt_ms,
                    "cache_hit": False,
                },
                "kpis": metrics_tracker.snapshot(),
            }

        router_ms = round((time.perf_counter() - router_t0) * 1000.0, 1)

        # 4. Compose Grounded Spoken & Display Response
        composed = llm_service.compose_grounded_response(
            intent_data,
            train_info,
            all_board_trains=railway_router.get_board_trains(),
        )

        # 5. Synthesize Speech Payload (Piper ONNX or Browser Neural TTS)
        tts_payload = await asyncio.to_thread(
            tts_service.synthesize_speech_payload, composed["spoken_text"]
        )
        wav_b64 = (
            base64.b64encode(tts_payload["wav_bytes"]).decode("ascii")
            if tts_payload["wav_bytes"]
            else None
        )
        tts_ms = float(tts_payload["latency_ms"])
        total_rtt_ms = round((time.perf_counter() - pipeline_t0) * 1000.0, 1)

        metrics_tracker.record_query(
            is_cache_hit=is_cache_hit,
            stt_ms=stt_ms,
            llm_ms=llm_ms,
            tts_ms=tts_ms,
            total_rtt_ms=total_rtt_ms,
        )

        is_conversational_success = (
            train_info is not None
            or intent_data["intent"] in CONVERSATIONAL_NON_TRAIN_INTENTS
        )
        final_state = "SPEAKING" if is_conversational_success else "ERROR"

        return {
            "type": "kiosk_response",
            "state": final_state,
            "error_code": None if final_state == "SPEAKING" else "TRAIN_NOT_FOUND",
            "transcript": transcript,
            "intent": intent_data,
            "train": train_info,
            "spoken_text": composed["spoken_text"],
            "display_en": composed["display_en"],
            "audio_wav_base64": wav_b64,
            "use_browser_tts": bool(tts_payload["use_browser_tts"]),
            "tts_engine": tts_payload["tts_engine"],
            "latency": {
                "stt_ms": stt_ms,
                "llm_ms": llm_ms,
                "router_ms": router_ms,
                "tts_ms": tts_ms,
                "total_rtt_ms": total_rtt_ms,
                "cache_hit": is_cache_hit,
            },
            "kpis": metrics_tracker.snapshot(),
        }

    except Exception as unexpected_exc:
        logger.exception("Unexpected error in execute_kiosk_pipeline: %s", unexpected_exc)
        return {
            "type": "kiosk_response",
            "state": "ERROR",
            "error_code": "INTERNAL_RECOVERY",
            "transcript": text_override or "(Voice Query)",
            "intent": {"intent": "UNKNOWN", "train_number": None, "train_name": None},
            "train": None,
            "spoken_text": "माफ़ कीजिये, अभी तकनीकी समस्या आई है। कृपया दोबारा पूछें।",
            "display_en": f"Recovered from error: {unexpected_exc}",
            "audio_wav_base64": None,
            "use_browser_tts": True,
            "tts_engine": "browser-neural-hi_IN",
            "latency": {
                "stt_ms": 0.0,
                "llm_ms": 0.0,
                "router_ms": 0.0,
                "tts_ms": 10.0,
                "total_rtt_ms": round((time.perf_counter() - pipeline_t0) * 1000.0, 1),
                "cache_hit": False,
            },
            "kpis": metrics_tracker.snapshot(),
        }


@app.get("/api/health")
async def get_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "project": settings.PROJECT_NAME,
        "owner": settings.OWNER,
        "station": settings.STATION_NAME,
        "models": {
            "stt": f"faster-whisper ({settings.WHISPER_MODEL_SIZE}, {settings.WHISPER_DEVICE}, {settings.WHISPER_COMPUTE_TYPE})",
            "llm": settings.OLLAMA_MODEL,
            "tts": "Piper TTS / Browser Neural hi-IN",
        },
        "kpis": metrics_tracker.snapshot(),
    }


@app.get("/api/board")
async def get_station_board() -> Dict[str, Any]:
    return railway_router.cache_data


@app.post("/api/board/refresh")
async def trigger_board_refresh() -> Dict[str, Any]:
    updated = await railway_router.refresh_station_board_once()
    return {"status": "refreshed", "board": updated}


@app.get("/api/metrics")
async def get_kpi_metrics() -> Dict[str, Any]:
    return metrics_tracker.snapshot()


@app.post("/api/query")
async def post_text_enquiry(req: TextEnquiryRequest) -> Dict[str, Any]:
    return await execute_kiosk_pipeline(
        text_override=req.query,
        simulate_http_status=req.simulate_http_status,
    )


@app.websocket("/ws/chat")
async def websocket_chat_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    audio_buffer = bytearray()

    await websocket.send_json(
        {
            "type": "session_ready",
            "state": "IDLE",
            "station": settings.STATION_NAME,
            "kpis": metrics_tracker.snapshot(),
            "board": railway_router.cache_data,
        }
    )

    try:
        while True:
            message = await websocket.receive()

            if message.get("type") == "websocket.disconnect":
                break

            if "bytes" in message and message["bytes"] is not None:
                audio_buffer.extend(message["bytes"])
                continue

            if "text" in message and message["text"] is not None:
                try:
                    payload = json.loads(message["text"])
                except json.JSONDecodeError:
                    payload = {"action": "text_query", "query": message["text"]}

                action = payload.get("action")

                if action == "start_listening":
                    audio_buffer.clear()
                    await websocket.send_json(
                        {"type": "state_change", "state": "LISTENING"}
                    )

                elif action == "audio_chunk":
                    b64 = payload.get("data_base64", "")
                    if b64:
                        audio_buffer.extend(base64.b64decode(b64))

                elif action == "stop_listening":
                    await websocket.send_json(
                        {"type": "state_change", "state": "PROCESSING"}
                    )
                    hint_text = payload.get("hint_text")
                    sim_status = payload.get("simulate_http_status")
                    captured = bytes(audio_buffer)
                    audio_buffer.clear()
                    result = await execute_kiosk_pipeline(
                        audio_bytes=captured,
                        text_override=hint_text,
                        simulate_http_status=sim_status,
                    )
                    await websocket.send_json(result)

                elif action == "text_query":
                    await websocket.send_json(
                        {"type": "state_change", "state": "PROCESSING"}
                    )
                    query_str = payload.get("query", "")
                    sim_status = payload.get("simulate_http_status")
                    result = await execute_kiosk_pipeline(
                        text_override=query_str,
                        simulate_http_status=sim_status,
                    )
                    await websocket.send_json(result)

                elif action == "ping":
                    await websocket.send_json(
                        {"type": "pong", "kpis": metrics_tracker.snapshot()}
                    )

    except WebSocketDisconnect:
        logger.info("Kiosk WebSocket client disconnected.")
    except Exception as exc:
        logger.error("WebSocket session error: %s", exc)
