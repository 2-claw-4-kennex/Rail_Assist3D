# RailAssist 3D (Zero-Ollama Edition)

Self-contained kiosk with zero C: drive model downloads:
- **No Ollama / No Whisper downloads** — runs in <25 MB Python packages + browser Web Speech API (`en-IN` English/Hinglish).
- **Lucknow Board (`/api/board`)**: Served directly from `backend/data/lucknow_board.json`.
- **Live Train Status**: Calls RailRadar (`GET /v1/trains/{number}/live`) strictly when a specific train is requested.

## Run in 3 Steps (Windows PowerShell)

1. Put your RailRadar key in `backend/.env`:
   ```env
   RAILRADAR_API_KEY=rg_your_key_here
   ```
2. Drop your rigged avatar at `frontend/public/models/avatar.glb`.
3. Install & launch:
   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt

   cd ..rontend
   npm install

   cd ..
   .\start_kiosk.ps1
   ```
   Open `http://localhost:3000` in Chrome or Edge.
