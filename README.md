# RailAssist 3D: Conversational Railway Enquiry Kiosk

**Document Owner:** Aryan Sanskar Ahuja  
**Institution:** Bennett University, School of Computer Science Engineering and Technology  
**Target Hardware:** Local Windows PC (Intel Core i5-13450HX, NVIDIA RTX 4060 8GB VRAM)  
**Target Station:** Lucknow Charbagh / Lucknow Junction (`LKO` / `LJN`)  

---

## 1. Architecture Overview

RailAssist 3D is a full-duplex, multimodal conversational railway enquiry kiosk designed to eliminate GUI friction for elderly and hurried railway passengers. Users press and hold the **"Hold to Speak (बोलने के लिए दबाए रखें)"** button and ask naturally in Hindi, English, or Hinglish (e.g., *"12004 Shatabdi Express kab aayegi?"* or *"Gomti Express ka platform number kya hai?"*).

| Layer | Technology | Execution Device | Purpose |
| :--- | :--- | :--- | :--- |
| **Frontend Renderer** | React 18 (Vite), React Three Fiber (`@react-three/fiber`, `@react-three/drei`) | Browser / WebGL | Declarative 3D scene rendering, state-reactive lighting, and zero-keyboard touch HUD. |
| **3D Avatar & Lip-Sync** | Ready Player Me `.glb` (`public/models/avatar.glb`) + Web Audio API `AnalyserNode` | Browser | Maps real-time TTS vocal frequency energy (`fftSize=256`) to the avatar's `jawOpen` morph target at 60 FPS. |
| **Backend Orchestrator** | Python FastAPI + Full-Duplex WebSockets (`/ws/chat`) | CPU | Asynchronous audio chunk streaming, state broadcasts, and hybrid cache/API routing. |
| **Speech-to-Text (STT)** | Faster-Whisper (`small`, `int8` via CTranslate2) | CPU (i5-13450HX) | Offloads acoustic transcription from GPU to preserve RTX 4060 VRAM; conditioned for Hinglish train names. |
| **LLM / Intent Engine** | Qwen 2.5 (`3B Q4_K_M`) via Ollama | GPU (RTX 4060 8GB) | Uses ~2.2GB VRAM; extracts structured JSON intent & train entity in `<800ms` with anti-hallucination guardrails. |
| **Hybrid Data Router** | 5-Min Edge Cache (`lucknow_board.json`) + RapidAPI Indian Railways | CPU / Network | Instant `<5ms` resolution for Lucknow trains (`>75%` cache hit ratio) with synchronous RapidAPI fallback for out-of-network trains. |
| **Text-to-Speech (TTS)** | Piper TTS (`hi_IN` VITS ONNX) + Syllabic Formant WAV Fallback | CPU | Generates low-latency 22050Hz 16-bit mono WAV PCM audio for immediate playback and procedural lip-sync. |

---

## 2. Project Directory Structure

```text
RailAssist-3D/
├── start_kiosk.bat                  # Single-click Windows presentation launcher (Epic 4)
├── setup_models.bat                 # Pulls Qwen 2.5 3B Q4_K_M & caches Faster-Whisper Small
├── Modelfile.qwen-railassist        # Ollama Modelfile tuned for Lucknow Hinglish NLU
├── .env.example                     # Environment template (ports, Ollama, Whisper, Piper, RapidAPI)
├── docs/
│   └── JIRA_BACKLOG.md              # Traceability matrix across Epics 1, 2, 3, and 4
├── backend/
│   ├── main.py                      # FastAPI server, /ws/chat full-duplex WebSocket, REST endpoints
│   ├── config.py                    # Hardware & failsafe settings
│   ├── requirements.txt             # Python dependencies
│   ├── data/
│   │   └── lucknow_board.json       # Pre-seeded 5-minute Lucknow (LKO/LJN) arrival/departure cache
│   ├── services/
│   │   ├── stt_service.py           # Faster-Whisper (Small, CPU, int8) with Hinglish conditioning
│   │   ├── llm_service.py           # Qwen 2.5 3B Q4_K_M intent engine + hallucination guardrails
│   │   ├── railway_router.py        # 5-min background cache worker + RapidAPI HTTP 429/504 failsafes
│   │   ├── tts_service.py           # Piper TTS (hi_IN) + built-in syllabic WAV fallback
│   │   └── metrics.py               # KPI tracker (Cache Hit %, LLM ms, Total RTT ms, RTX 4060 VRAM)
│   └── tests/
│       └── test_pipeline.py         # Pytest suite covering cache hits, live fallback, HTTP 429/504, & WS
└── frontend/
    ├── package.json                 # React 18, Vite, Three.js, @react-three/fiber, @react-three/drei
    ├── vite.config.js               # Proxy setup for /api and /ws/chat
    ├── index.html                   # Kiosk HTML shell with Devanagari & Inter typography
    ├── public/
    │   └── models/
    │       └── avatar.glb           # Pre-bundled 3D Kiosk Avatar (.glb) with jawOpen morph target
    └── src/
        ├── main.jsx                 # React entry point
        ├── App.jsx                  # 2-column kiosk layout
        ├── components/
        │   ├── AvatarCanvas.jsx     # 3D canvas, lighting, and 60 FPS jawOpen morph target loop
        │   ├── KioskHUD.jsx         # State banner, Hold-to-Speak button, and Hinglish quick chips
        │   ├── LiveStationBoard.jsx # Interactive Lucknow arrival/departure table
        │   └── TelemetryPanel.jsx   # Real-time KPI scorecard & Epic 4 failsafe simulation buttons
        ├── hooks/
        │   ├── useAudioLipSync.js   # Web Audio API AnalyserNode -> jawOpen blendshape driver
        │   └── useKioskStateMachine.js # Finite state machine (IDLE/LISTENING/PROCESSING/SPEAKING/ERROR)
        └── styles/
            └── kiosk.css            # High-contrast touchscreen kiosk stylesheet
```

---

## 3. Quick Start Guide (Windows PC — i5-13450HX + RTX 4060)

### Option A: Single-Click Launch (Recommended for Presentations)
1. Extract `RailAssist-3D.zip` to a folder on your Windows PC.
2. *(Optional)* Run `setup_models.bat` once to pull `qwen2.5:3b-instruct-q4_K_M` into Ollama and pre-cache `faster-whisper` (`small`).
3. Double-click **`start_kiosk.bat`**.
   - It automatically sets up `backend\.venv`, starts the FastAPI server on `http://127.0.0.1:8000`, starts the Vite 3D frontend on `http://localhost:5173`, and opens the kiosk in your browser.
   - **Zero-Config Resilience:** Even before Ollama, Piper ONNX binaries, or a RapidAPI key are configured, `ENABLE_GRACEFUL_FALLBACK=true` ensures the kiosk works out-of-the-box with deterministic Hinglish NLU, the Lucknow station cache, and syllabic WAV synthesis so the 3D avatar speaks and animates its jaw immediately.

### Option B: Manual Terminal Launch
**1. Start Backend:**
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**2. Start Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**3. Run Automated Verification Tests:**
```bash
cd backend
pytest -v
```

---

## 4. Customizing the Ready Player Me 3D Avatar
The project ships with a valid binary glTF 2.0 3D avatar at `frontend/public/models/avatar.glb` containing `jawOpen`, `mouthSmile`, `eyeBlinkLeft`, and `eyeBlinkRight` morph targets so it renders and lip-syncs immediately out of the box.
To swap in your own custom Ready Player Me `.glb` character:
1. Export your avatar from Ready Player Me with morph targets enabled (`?morphTargets=ARKit,Oculus Visemes`).
2. Save the file as `frontend/public/models/avatar.glb` (overwriting the default file).
3. `AvatarCanvas.jsx` automatically traverses all meshes in the `.glb` and binds `jawOpen` / `viseme_aa` / `mouthOpen` to the Web Audio API `AnalyserNode`.
