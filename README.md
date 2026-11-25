# RailAssist 3D

A lightweight, voice-enabled 3D railway enquiry kiosk built with React, Three.js and FastAPI.

### Features
- **3D Avatar:** Interactive avatar-based kiosk interface.
- **Voice Interaction:** Browser Web Speech API with English/Hinglish support.
- **AI Assistance:** Gemini-powered railway enquiries.
- **Station Board:** Lucknow arrivals and departures from local JSON data.
- **Live Train Status:** On-demand train tracking through RailRadar API.
- **Lightweight:** No Ollama or Whisper model downloads.

### Tech Stack
React · Vite · Three.js · React Three Fiber · Python · FastAPI · Gemini API · RailRadar API · WebSockets

### Run Locally

**1. Configure `backend/.env`:**

```env
RAILRADAR_API_KEY=your_api_key
```

**2. Install dependencies:**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

cd ..\frontend
npm install
```

**3. Launch:**

```powershell
cd ..
.\start_kiosk.ps1
```

Open http://localhost:3000 in Chrome or Edge.

### Deployment
**Frontend:** [GitHub Pages]

**Backend:** Local deployment currently; public hosting pending.

]
