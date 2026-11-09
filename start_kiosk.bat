@echo off
REM ============================================================================
REM RailAssist 3D — Single-Click Kiosk Launcher (Epic 4 Hardening Sprint)
REM Document Owner: Aryan Sanskar Ahuja (Bennett University, SCSET)
REM Target Environment: Windows PC (Intel Core i5-13450HX, NVIDIA RTX 4060 8GB)
REM ============================================================================

title RailAssist 3D — Conversational Railway Enquiry Kiosk Launcher
color 0B

echo ============================================================================
echo   RailAssist 3D: Conversational Railway Enquiry Kiosk (Lucknow LKO)
echo   Hardware Profile: Intel Core i5-13450HX + NVIDIA RTX 4060 (8GB VRAM)
echo ============================================================================
echo.

REM 1. Ensure .env exists
if not exist ".env" (
    echo [1/4] Creating .env from .env.example...
    copy /Y ".env.example" ".env" >nul
) else (
    echo [1/4] Found .env configuration.
)

REM 2. Check / Warm Ollama Qwen 2.5 3B Q4_K_M on RTX 4060 GPU
where ollama >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [2/4] Verifying Ollama service and Qwen 2.5 3B Q4_K_M model...
    start /B "" ollama serve >nul 2>nul
) else (
    echo [2/4] Ollama CLI not detected in PATH; backend will run in Deterministic Hinglish Fallback mode.
)

REM 3. Start Python FastAPI Orchestrator (Backend)
echo [3/4] Starting FastAPI Backend Orchestrator on http://127.0.0.1:8000 ...
if not exist "backend\.venv" (
    echo       Creating Python virtual environment in backend\.venv...
    python -m venv backend\.venv
    call backend\.venv\Scripts\activate.bat
    pip install --upgrade pip
    pip install -r backend\requirements.txt
) else (
    call backend\.venv\Scripts\activate.bat
)

start "RailAssist-3D-Backend" cmd /k "cd /d %~dp0backend && call .venv\Scripts\activate.bat && uvicorn main:app --host 0.0.0.0 --port 8000"

REM 4. Start React + Vite + React Three Fiber Kiosk Frontend
echo [4/4] Starting React Three Fiber 3D Kiosk UI on http://localhost:5173 ...
if not exist "frontend\node_modules" (
    echo       Installing frontend npm packages...
    cd /d "%~dp0frontend"
    call npm install
    cd /d "%~dp0"
)

start "RailAssist-3D-Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

REM Wait 4 seconds and open browser in Kiosk/App mode
timeout /t 4 /nobreak >nul
start "" "http://localhost:5173"

echo.
echo ============================================================================
echo   RailAssist 3D Kiosk is now running!
echo   - Frontend Kiosk UI : http://localhost:5173
echo   - FastAPI Swagger   : http://127.0.0.1:8000/docs
echo   - WebSocket Stream  : ws://127.0.0.1:8000/ws/chat
echo ============================================================================
pause
