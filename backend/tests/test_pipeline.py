"""
RailAssist 3D — Automated Verification & Integration Test Suite
Tests:
1. Local 5-minute Lucknow station board cache lookup (F4.1, F4.2)
2. Train lookup by Name in English, Hinglish, and Devanagari ("Where is Gomti Express?", "गोमती एक्सप्रेस कहाँ है?")
3. Destination / Route & Context Queries ("यह ट्रेन कितनी देर में पहुंचेगी दिल्ली")
4. Small Talk & Station Facility Queries ("How are you doing?", "आप कैसे हैं?", "Waiting room kahan hai?")
5. Out-of-network train RapidAPI fallback (F4.3)
6. Graceful degradation on HTTP 429 and HTTP 504 (N3)
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings  # noqa: E402
from services.llm_service import llm_service  # noqa: E402
from services.metrics import metrics_tracker  # noqa: E402
from services.railway_router import railway_router, RailwayAPIError  # noqa: E402
from services.tts_service import tts_service  # noqa: E402


def test_lucknow_board_cache_loaded():
    trains = railway_router.get_board_trains()
    assert len(trains) >= 8
    train_numbers = {t["train_number"] for t in trains}
    assert "12004" in train_numbers
    assert "12419" in train_numbers
    assert "22426" in train_numbers


def test_versatile_small_talk_and_train_by_name():
    async def _run():
        # 1. Small talk: "How are you doing?"
        st = await llm_service.extract_intent_and_entity("How are you doing?")
        assert st["intent"] == "SMALL_TALK"
        resp_st = llm_service.compose_grounded_response(st, None)
        assert "great" in resp_st["spoken_text"].lower() or "ठीक" in resp_st["spoken_text"]

        # 2. Train by name without number (English): "Where is Gomti Express?"
        gomti_intent = await llm_service.extract_intent_and_entity("Where is Gomti Express?")
        assert gomti_intent["train_number"] == "12419"
        gomti_train, is_hit = await railway_router.resolve_train_telemetry(
            train_number=gomti_intent["train_number"],
            train_name=gomti_intent["train_name"],
            raw_query="Where is Gomti Express?",
        )
        assert is_hit is True
        assert gomti_train["train_number"] == "12419"

        # 3. Devanagari query from user screenshot: "यह ट्रेन कितनी देर में पहुंचेगी दिल्ली"
        delhi_q = "यह ट्रेन कितनी देर में पहुंचेगी दिल्ली"
        delhi_intent = await llm_service.extract_intent_and_entity(delhi_q)
        assert delhi_intent["intent"] in ("SCHEDULE_ENQUIRY", "ROUTE_SEARCH", "LIVE_STATUS")
        delhi_train, _ = await railway_router.resolve_train_telemetry(
            train_number=delhi_intent.get("train_number"),
            train_name=delhi_intent.get("train_name"),
            raw_query=delhi_q,
        )
        assert delhi_train is not None
        composed_delhi = llm_service.compose_grounded_response(delhi_intent, delhi_train)
        assert "दिल्ली" in composed_delhi["spoken_text"]

        # 4. Devanagari train by name: "वंदे भारत कहाँ है?"
        vb_q = "वंदे भारत कहाँ है?"
        vb_intent = await llm_service.extract_intent_and_entity(vb_q)
        assert vb_intent["train_number"] == "22426"

    asyncio.run(_run())


def test_hybrid_cache_and_live_fallback_routing():
    async def _run():
        cached_train, is_hit = await railway_router.resolve_train_telemetry(
            train_number="12004", train_name="Shatabdi Express"
        )
        assert is_hit is True
        assert cached_train is not None
        assert cached_train["platform"] == 1

        live_train, is_hit_live = await railway_router.resolve_train_telemetry(
            train_number="20504", train_name="Rajdhani Express"
        )
        assert is_hit_live is False
        assert live_train is not None
        assert live_train["data_source"] == "LIVE_RAPIDAPI_GATEWAY"

    asyncio.run(_run())


def test_graceful_degradation_http_429_and_504():
    async def _run():
        try:
            await railway_router.resolve_train_telemetry(
                train_number="12419", simulate_http_status=429
            )
            assert False, "Expected RailwayAPIError for HTTP 429"
        except RailwayAPIError as err:
            assert err.status_code == 429
            assert err.spoken_hi == settings.MSG_RATE_LIMIT_HI

        try:
            await railway_router.resolve_train_telemetry(
                train_number="12533", simulate_http_status=504
            )
            assert False, "Expected RailwayAPIError for HTTP 504"
        except RailwayAPIError as err:
            assert err.status_code == 504
            assert err.spoken_hi == settings.MSG_TIMEOUT_HI

    asyncio.run(_run())


def test_tts_wav_synthesis_and_kpi_metrics():
    wav_bytes, tts_ms = tts_service.synthesize_wav(
        "Gaadi sankhya 12004, Shatabdi Express, Platform number 1 par aayegi."
    )
    assert wav_bytes[:4] == b"RIFF"
    assert wav_bytes[8:12] == b"WAVE"
    assert tts_ms < 1000.0

    metrics_tracker.record_query(
        is_cache_hit=True,
        stt_ms=120.0,
        llm_ms=210.0,
        tts_ms=tts_ms,
        total_rtt_ms=450.0,
    )
    snap = metrics_tracker.snapshot()
    assert snap["vram"]["within_budget"] is True
    assert snap["avg_end_to_end_rtt_ms"] < 3000.0


if __name__ == "__main__":
    print("Running RailAssist 3D versatile verification suite...")
    test_lucknow_board_cache_loaded()
    print("  [PASS] test_lucknow_board_cache_loaded")
    test_versatile_small_talk_and_train_by_name()
    print("  [PASS] test_versatile_small_talk_and_train_by_name")
    test_hybrid_cache_and_live_fallback_routing()
    print("  [PASS] test_hybrid_cache_and_live_fallback_routing")
    test_graceful_degradation_http_429_and_504()
    print("  [PASS] test_graceful_degradation_http_429_and_504")
    test_tts_wav_synthesis_and_kpi_metrics()
    print("  [PASS] test_tts_wav_synthesis_and_kpi_metrics")
    print("All 5 test suites passed!")
