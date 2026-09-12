# SemanticStream — Runbook
<!-- Last updated: 2026-09-11 -->

> **Quick reference**: all commands, environment setup, and troubleshooting notes for running SemanticStream locally.

---

## Prerequisites

| Requirement   | Min Version | Check command              |
|--------------|-------------|---------------------------|
| Python        | 3.11+       | python --version         |
| Node.js       | 18+         | 
ode --version           |
| npm           | 9+          | 
pm --version            |
| FFmpeg        | 4.x+        | fmpeg -version          |
| Git           | any         | git --version            |

> **FFmpeg must be on PATH.** The backend compression service calls `ffmpeg` and `ffprobe` directly.

---

## Environment Setup (First Time)

### 1. Clone and navigate
```powershell
git clone https://github.com/shubham1852/semantic-stream.git
cd semantic-stream
```

### 2. Backend — Python virtual environment
```powershell
# From project root
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1

pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Frontend — Node dependencies
```powershell
cd frontend
npm install
```

### 4. Environment variables
The .env file is already present at project root — no action needed.
To reset: `Copy-Item .env.example .env`

---

## Running Locally (Development)

### Terminal 1 — Backend (FastAPI + Uvicorn)
```powershell
# From project root
$env:PYTHONPATH = 'd:\vit\projects\semanticstream'
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

URLs:
- API base:      http://localhost:8000/api/v1
- Swagger docs:  http://localhost:8000/api/docs
- Health check:  http://localhost:8000/health

### Terminal 2 — Frontend (Vite dev server)
```powershell
# From: d:\vit\projects\semanticstream\frontend
npm run dev
```

App URL: http://localhost:5173

> Vite proxies /api/* to localhost:8000 and /ws/* to ws://localhost:8000

---

## Running with Docker

```powershell
docker-compose up --build
# Background: docker-compose up --build -d
# Stop:       docker-compose down
```

---

## Build Frontend (Production)

```powershell
# From: d:\vit\projects\semanticstream\frontend
npm run build
npm run preview   # preview built output
```

---

## Running Tests

### Backend (pytest)
```powershell
$env:PYTHONPATH = 'd:\vit\projects\semanticstream'
python -m pytest backend/tests/ -v
```
Expected: 59 tests, all passing.

### Frontend lint
```powershell
# From: d:\vit\projects\semanticstream\frontend
npm run lint
```
Expected: Exit code 0, no output (zero errors, zero warnings).

---

## Test Videos

Located in test_videos/:

| File                     | Size    | Notes                              |
|--------------------------|---------|------------------------------------|
| sample-5s.mp4            | 2.7 MB  | Short 5-second clip                |
| sample_960x540.mp4       | 1.3 MB  | 960x540 resolution sample          |
| test_clip.mp4            | 0.8 MB  | Minimal test clip                  |
| trailer.mp4              | 4.2 MB  | Trailer sample                     |
| BigBuckBunny_237mb.mp4   | 237 MB  | Full-length Big Buck Bunny (W3C)   |

Download 237MB Big Buck Bunny:
```powershell
python -c "import urllib.request; urllib.request.urlretrieve('https://media.w3.org/2010/05/bunny/movie.mp4', 'test_videos/BigBuckBunny_237mb.mp4'); print('Done')"
```

---

## Key API Endpoints

```powershell
# Health check
curl http://localhost:8000/health

# Upload video
curl -X POST http://localhost:8000/api/v1/upload -F "file=@test_videos/sample-5s.mp4"

# Start analysis (replace VIDEO_ID)
curl -X POST http://localhost:8000/api/v1/analyze/VIDEO_ID -H "Content-Type: application/json" -d '{"frame_sample_rate": 5, "confidence_threshold": 0.45}'

# Poll results (replace JOB_ID)
curl http://localhost:8000/api/v1/results/JOB_ID

# List bandwidth profiles
curl http://localhost:8000/api/v1/bandwidth-profiles

# Run 3-strategy experiment
curl -X POST http://localhost:8000/api/v1/experiment -H "Content-Type: application/json" -d '{"video_id": "VIDEO_ID", "bandwidth_profile": "strong_wifi"}'
```

---

## Database

- Type: SQLite (dev), PostgreSQL-ready for production
- File: semanticstream.db (project root)

```powershell
# Reset database
Remove-Item semanticstream.db -Force
# App recreates tables on next start

# Inspect tables
python -c "import sqlite3; conn = sqlite3.connect('semanticstream.db'); print([t[0] for t in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]); conn.close()"
```

---

## Known Issues

| Issue | Location | Severity | Notes |
|-------|----------|----------|-------|
| Chunk size >500KB on build | Frontend build | LOW | Cosmetic; no runtime impact |
| Dynamic import warning for useAppStore | client.js | LOW | Intentional circular dep break |
| VideoPlayer not wired to ResultsPage | ResultsPage.jsx | LOW | PDF/metrics shown; playback optional |
| HLS encoding not auto-triggered | Backend | LOW | Raw video fallback works |

---

## Common Errors and Fixes

### ModuleNotFoundError: No module named 'backend'
```powershell
$env:PYTHONPATH = 'd:\vit\projects\semanticstream'
python -m uvicorn backend.main:app --reload --port 8000
```

### Port 5173 already in use
```powershell
netstat -ano | findstr :5173
taskkill /PID <PID_NUMBER> /F
```

### Port 8000 already in use
```powershell
netstat -ano | findstr :8000
taskkill /PID <PID_NUMBER> /F
```

### FFmpeg not found
Install FFmpeg and add to PATH: https://ffmpeg.org/download.html

### YOLO model not found
Backend uses graceful mock fallback automatically.
For real inference: place yolov8n.onnx at backend/models/weights/yolov8n.onnx
(Note: the yolov8n.pt file in backend/ is NOT the ONNX version)

### SQLite database locked
```powershell
Get-Process python | Stop-Process -Force
# Then restart backend
```

---

## Bugs Fixed (2026-09-11)

| File | Issue | Fix |
|------|-------|-----|
| AnalyticsPage.jsx | useAppStore called conditionally (React Hooks violation) | Moved hook call unconditionally before ternary |
| AnalyticsPage.jsx | Unused StatusBadge import | Removed |
| AnalyticsPage.jsx | Unused 
ame prop in StrategyCard | Removed from destructuring |
| ResearchPage.jsx | Unescaped apostrophes in JSX (') | Replaced with &apos; |
| ResearchPage.jsx | Unused Link and FileText imports | Removed |
| ConfidenceChart.jsx | Unused LineChart, Line imports | Removed (file uses AreaChart) |
| TierAllocationChart.jsx | Unused Cell import | Removed |
| LandingPage.jsx | Unused ChevronDown import | Removed |
| SettingsPage.jsx | Unused useEffect import | Removed |
| BandwidthPage.jsx | profiles state assigned but never read in JSX | Prefixed with _ |
| StreamingPage.jsx | Dead ufferLevel/currentBitrate state with unused setters | Replaced with simple const = 0 |

---

## Project Structure

```
semanticstream/
├── backend/
│   ├── api/routes/     8 REST route files
│   ├── services/       7 domain services
│   ├── models/         YOLOv8 ONNX engine + model cache
│   ├── database/       6-table ORM schema + CRUD
│   ├── utils/          metric, QP, frame, file utilities
│   ├── tests/          59 pytest unit tests
│   ├── main.py         FastAPI app factory + lifespan
│   └── requirements.txt
├── frontend/
│   ├── src/pages/      14 React pages
│   ├── src/components/ 30+ UI/chart/video components
│   ├── src/api/        Axios client + 7 API modules
│   ├── src/store/      Zustand store (4 slices)
│   ├── src/hooks/      3 custom hooks
│   ├── vite.config.js  Vite + proxy config
│   └── package.json
├── test_videos/        MP4 test files
├── .env                Environment variables (local only, do not commit)
├── .env.example        Template
├── docker-compose.yml  Docker setup
├── RUNBOOK.md          This file
├── PROGRESS.md         Feature completion tracker
└── README.md           Project overview
```
