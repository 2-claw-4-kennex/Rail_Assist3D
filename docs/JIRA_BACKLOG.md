# RailAssist 3D — Jira Sprint Backlog & Epic Traceability Matrix

**Document Owner:** Aryan Sanskar Ahuja  
**Institution:** Bennett University, School of Computer Science Engineering and Technology  
**Target Hardware:** Intel Core i5-13450HX + NVIDIA RTX 4060 (8GB VRAM)  

| Epic ID | Story ID | Summary | Implementation File(s) | Acceptance Criteria / Target KPI |
| :--- | :--- | :--- | :--- | :--- |
| **EPIC-1** | **RA-101** | Quantized Qwen 2.5 (3B Q4_K_M) deployment via Ollama | `Modelfile.qwen-railassist`, `setup_models.bat`, `backend/services/llm_service.py` | VRAM footprint stays `< 2.5GB` (Total VRAM `< 4.5GB`); JSON intent extraction `< 800ms`. |
| **EPIC-1** | **RA-102** | Headless FastAPI pipeline (`Audio In -> STT -> LLM -> API -> TTS -> Audio Out`) | `backend/main.py`, `backend/services/stt_service.py`, `backend/services/tts_service.py` | Faster-Whisper (`small`, `int8`) runs strictly on CPU via CTranslate2; Piper TTS synthesizes 22050Hz WAV audio on CPU. |
| **EPIC-1** | **RA-103** | Background 5-minute Lucknow station board worker & `lucknow_board.json` cache | `backend/services/railway_router.py`, `backend/data/lucknow_board.json` | Polls Lucknow (`LKO` / `LJN`) arrival/departure telemetry every 300s; achieves `> 75%` Cache Hit Ratio. |
| **EPIC-2** | **RA-201** | Vite + React Kiosk UI scaffold & high-contrast responsive CSS grid | `frontend/src/App.jsx`, `frontend/src/styles/kiosk.css` | Accessible touchscreen layout operable without a physical keyboard (Requirement N4). |
| **EPIC-2** | **RA-202** | Ready Player Me `.glb` 3D avatar integration with `jawOpen` morph target | `frontend/public/models/avatar.glb`, `frontend/src/components/AvatarCanvas.jsx` | Loads `.glb` mesh and binds `jawOpen`, `mouthSmile`, `eyeBlinkLeft`, and `eyeBlinkRight` morphTargetDictionary indices. |
| **EPIC-2** | **RA-203** | React Three Fiber lighting, camera framing, and 60 FPS render loop | `frontend/src/components/AvatarCanvas.jsx` | Studio 3-point lighting + state-reactive holographic torus ring synced to kiosk state machine. |
| **EPIC-3** | **RA-301** | Full-duplex WebSocket (`/ws/chat`) streaming protocol | `backend/main.py`, `frontend/src/hooks/useKioskStateMachine.js` | Persistent connection eliminating HTTP handshake overhead; streams binary audio chunks and JSON state transitions. |
| **EPIC-3** | **RA-302** | `MediaRecorder` API "Hold to Speak" voice capture | `frontend/src/hooks/useKioskStateMachine.js`, `frontend/src/components/KioskHUD.jsx` | Captures 16kHz mono Opus/WebM chunks every 150ms while held and triggers pipeline immediately upon release. |
| **EPIC-3** | **RA-303** | Web Audio API `AnalyserNode` procedural `jawOpen` lip-sync | `frontend/src/hooks/useAudioLipSync.js`, `frontend/src/components/AvatarCanvas.jsx` | Computes real-time vocal band energy (`fftSize=256`) and interpolates `jawOpen` blendshape (`0.0` to `1.0`). |
| **EPIC-4** | **RA-401** | Finite State Machine (`IDLE`, `LISTENING`, `PROCESSING`, `SPEAKING`, `ERROR`) | `frontend/src/hooks/useKioskStateMachine.js`, `frontend/src/components/KioskHUD.jsx` | Visual & spoken cues indicate current kiosk state clearly for elderly and non-technical passengers. |
| **EPIC-4** | **RA-402** | Failsafe routing for HTTP 429, HTTP 504, unintelligible audio & LLM hallucinations | `backend/services/railway_router.py`, `backend/services/llm_service.py`, `backend/tests/test_pipeline.py` | Plays pre-warmed Hindi TTS failsafe prompts (`"Main sun nahi paya, kripya dobara bolein"`) and blocks hallucinated train numbers. |
| **EPIC-4** | **RA-403** | Single-click Windows `.bat` deployment launcher | `start_kiosk.bat`, `setup_models.bat` | Launches Ollama, FastAPI backend, Vite frontend, and browser window with one double-click on Windows. |
