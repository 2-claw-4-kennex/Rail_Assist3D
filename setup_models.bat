@echo off
REM ============================================================================
REM RailAssist 3D — Local AI Model Provisioning Script (Epic 1)
REM Pulls Qwen 2.5 (3B Q4_K_M) via Ollama (~2.2GB VRAM on RTX 4060)
REM Pre-warms Faster-Whisper (Small int8 CPU) & Piper TTS Hindi voice model
REM ============================================================================

title RailAssist 3D — Model Setup (Qwen 2.5 + Faster-Whisper + Piper TTS)
color 0A

echo ============================================================================
echo   RailAssist 3D: Provisioning Local AI Stack for RTX 4060 (8GB VRAM)
echo ============================================================================
echo.

REM 1. Pull Qwen 2.5 3B Q4_K_M in Ollama
where ollama >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [1/3] Pulling Qwen 2.5 3B Q4_K_M (~2.2GB VRAM footprint)...
    ollama pull qwen2.5:3b-instruct-q4_K_M
    ollama create railassist-qwen -f Modelfile.qwen-railassist
) else (
    echo [WARNING] Ollama not installed yet. Download from https://ollama.com/download/windows
)

REM 2. Pre-download Faster-Whisper Small (CPU CTranslate2 int8)
echo.
echo [2/3] Pre-caching Faster-Whisper (small, CPU int8) weights...
if exist "backend\.venv\Scripts\python.exe" (
    backend\.venv\Scripts\python.exe -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8'); print('Faster-Whisper small int8 cached successfully.')"
) else (
    python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8'); print('Faster-Whisper small int8 cached successfully.')"
)

REM 3. Create Piper TTS directory for hi_IN voice model
echo.
echo [3/3] Preparing Piper TTS (hi_IN) model directory...
if not exist "backend\models\piper" mkdir "backend\models\piper"
echo Place hi_IN-rohan-medium.onnx and hi_IN-rohan-medium.onnx.json in backend\models\piper\
echo (Note: Built-in syllabic WAV synthesizer runs automatically if ONNX files are absent.)

echo.
echo ============================================================================
echo   Setup complete! Run start_kiosk.bat to launch the kiosk.
echo ============================================================================
pause
