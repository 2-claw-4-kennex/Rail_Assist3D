"""
RailAssist 3D — Backend Configuration Module
Hardware Target: Intel Core i5-13450HX (CPU STT/TTS) + NVIDIA RTX 4060 8GB VRAM (GPU LLM)
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

load_dotenv(ROOT_DIR / ".env")
load_dotenv(BASE_DIR / ".env")


class Settings:
    PROJECT_NAME: str = "RailAssist 3D: Conversational Railway Enquiry Kiosk"
    OWNER: str = "Aryan Sanskar Ahuja (Bennett University - SCSET)"
    VERSION: str = "1.0.0"

    # Server & Station
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    STATION_CODE: str = os.getenv("STATION_CODE", "LKO")
    STATION_NAME: str = os.getenv("STATION_NAME", "Lucknow Charbagh (LKO)")
    CACHE_REFRESH_SECONDS: int = int(os.getenv("CACHE_REFRESH_SECONDS", "300"))
    BOARD_CACHE_FILE: Path = BASE_DIR / "data" / "lucknow_board.json"

    # Ollama Qwen 2.5 3B Q4_K_M (GPU)
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:3b-instruct-q4_K_M")
    OLLAMA_TIMEOUT_SECONDS: float = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "2.2"))
    OLLAMA_KEEP_ALIVE: str = os.getenv("OLLAMA_KEEP_ALIVE", "-1")

    # Faster-Whisper Small (CPU CTranslate2 int8)
    WHISPER_MODEL_SIZE: str = os.getenv("WHISPER_MODEL_SIZE", "small")
    WHISPER_DEVICE: str = os.getenv("WHISPER_DEVICE", "cpu")
    WHISPER_COMPUTE_TYPE: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    WHISPER_CPU_THREADS: int = int(os.getenv("WHISPER_CPU_THREADS", "6"))

    # Piper TTS (CPU VITS)
    PIPER_EXECUTABLE: str = os.getenv("PIPER_EXECUTABLE", "piper")
    PIPER_MODEL_PATH: str = os.getenv(
        "PIPER_MODEL_PATH", str(BASE_DIR / "models" / "piper" / "hi_IN-rohan-medium.onnx")
    )
    PIPER_CONFIG_PATH: str = os.getenv(
        "PIPER_CONFIG_PATH",
        str(BASE_DIR / "models" / "piper" / "hi_IN-rohan-medium.onnx.json"),
    )
    PIPER_SPEAKER_ID: int = int(os.getenv("PIPER_SPEAKER_ID", "0"))

    # RapidAPI Indian Railways
    RAPIDAPI_KEY: str = os.getenv("RAPIDAPI_KEY", "")
    RAPIDAPI_HOST: str = os.getenv("RAPIDAPI_HOST", "irctc1.p.rapidapi.com")
    RAPIDAPI_TIMEOUT_SECONDS: float = float(os.getenv("RAPIDAPI_TIMEOUT_SECONDS", "2.5"))

    # Failsafe / Graceful Degradation Messages (Requirement N3)
    ENABLE_GRACEFUL_FALLBACK: bool = (
        os.getenv("ENABLE_GRACEFUL_FALLBACK", "true").lower() == "true"
    )
    MSG_UNINTELLIGIBLE_HI: str = (
        "Main sun nahi paya, kripya button daba kar dobara bolein."
    )
    MSG_TIMEOUT_HI: str = (
        "Server se sampark karne mein samay lag raha hai. Kripya kuch kshan baad prayaas karein."
    )
    MSG_RATE_LIMIT_HI: str = (
        "Abhi seva vyast hai. Kripya thodi der baad dobara poochein."
    )
    MSG_TRAIN_NOT_FOUND_HI: str = (
        "Kshama karein, is gaadi ki jaankari abhi uplabdh nahi hai. Kripya gaadi sankhya ya naam dobara batayein."
    )


settings = Settings()
