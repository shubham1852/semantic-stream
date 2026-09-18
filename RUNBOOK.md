# SemanticStream — Runbook
<!-- Last updated: 2026-09-17 -->

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

## Phase 10 Demo & Feature Verification Playbook

### 1. Live Camera Dual-Canvas & Real-Time Heatmap
1. Open frontend at `http://localhost:5173/live`.
2. Click **Start Camera** and grant browser webcam permissions.
3. Observe the **Dual-Canvas layout**:
   - **Left Canvas**: Live webcam feed with priority-colored bounding boxes (Green P1 for face/person with pulsing dot, Cyan P2 for pets/animals, Orange P3 for vehicles, Red-Orange P4 for items) and HUD status bar.
   - **Right Canvas**: True JET colormap heatmap with Gaussian-bloomed energy peaks concentrated on detected semantic regions.
4. Drag the **Bandwidth Slider**:
   - Slide to `< 0.35` (e.g., 0.20): Observe the red warning banner `"Bandwidth severely constrained"` and intensified background dimming.
   - Slide to `1.00`: Full bandwidth mode.
5. Check the **Latency History Chart**:
   - Roundtrip latency benchmark is **~80–110ms** (well below the 150ms CPU target line).

### 2. Upload Analysis & Split-View Video Player
1. Navigate to `http://localhost:5173/upload`.
2. Select a video from `test_videos/` (e.g., `sample-5s.mp4` or `sample_960x540.mp4`).
3. Set frame sampling rate (e.g., 5 frames) and start analysis.
4. Once completed, you are redirected to `http://localhost:5173/results/{job_id}`.
5. In the **Video Player**, test the 3-way toggle button:
   - **Split View** (default): Canvas divider with `ORIGINAL` badge on the left and `PROCESSED (MACROBLOCK)` badge on the right. Notice pristine face detail vs blocky, blurred background.
   - **Processed**: Full-frame processed video showing selective macroblock compression and ROI overlays.
   - **Original**: Full-frame uncompressed source video.
6. Review the **Compression Visibility Metric Card**:
   - Background Compression level (16x16 macroblocks, Q=4–15)
   - ROI Preservation (100% P1 humans, 90% P2 animals)
   - Bandwidth Saved % (40%–65% reduction)
   - Visual Diff Score ($\Delta\text{SSIM}$)

---

## Known Issues

| Issue | Location | Severity | Notes |
|-------|----------|----------|-------|
| Chunk size >500KB on build | Frontend build | LOW | Cosmetic warning from bundle size; no runtime impact |
| Dynamic import warning for useAppStore | client.js | LOW | Intentional design to prevent circular dependency |

*(Note: VideoPlayer wiring, HLS fallback streaming, and live camera latency bottlenecks are fully resolved in Phase 9 & 10).*

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
For real inference: place `yolov8n.onnx` at `backend/models/weights/yolov8n.onnx`

### SQLite database locked
```powershell
Get-Process python | Stop-Process -Force
# Then restart backend
```

---

## Bugs & Optimizations Fixed (2026-09-17)

| File | Issue | Fix |
|------|-------|-----|
| `backend/models/yolo_engine.py` | 530ms loop over 8,400 YOLO candidate anchors | Vectorized NumPy matrix slicing and OpenCV NMS (cut to 3.9ms) |
| `backend/models/yolo_engine.py` | 380ms unscaled Haar cascade face search on large ROIs | Downscaled head ROI to max 160px with inverse coordinate projection (cut to 14.8ms) |
| `frontend/src/components/video/LiveCameraView.jsx` | Frame queue backlog over WebSocket causing 500ms+ lag | In-flight backpressure guard (`isWaitingForResponseRef`) dropping roundtrip latency to ~89ms |
| `backend/services/render_service.py` | Background compression too subtle in output video | 16x16 macroblock downscale + Gaussian blur + HSV desaturation + JPEG Q=4–15 quantization |
| `frontend/src/pages/ResultsPage.jsx` | Missing direct visual comparison between raw and processed video | Interactive Split-View video player with canvas divider and directional pill badges |
| `frontend/src/pages/LivePage.jsx` | Single canvas cramped detection view | Dual-canvas layout (annotated live camera + JET semantic heatmap) with priority swatch legend |
| `backend/services/analytics_service.py` | Processed video not ready before job status set to completed | Reordered runner so `render_annotated_video` commits before setting job status |
| `backend/api/routes/stream.py` | Video seek failure on partial downloads | Implemented HTTP 206 Partial Content byte-range seeking with CORS headers |

---

## Bugs Fixed (2026-09-11)

| File | Issue | Fix |
|------|-------|-----|
| AnalyticsPage.jsx | useAppStore called conditionally (React Hooks violation) | Moved hook call unconditionally before ternary |
| AnalyticsPage.jsx | Unused StatusBadge import | Removed |
| AnalyticsPage.jsx | Unused name prop in StrategyCard | Removed from destructuring |
| ResearchPage.jsx | Unescaped apostrophes in JSX (') | Replaced with &apos; |
| ResearchPage.jsx | Unused Link and FileText imports | Removed |
| ConfidenceChart.jsx | Unused LineChart, Line imports | Removed (file uses AreaChart) |
| TierAllocationChart.jsx | Unused Cell import | Removed |
| LandingPage.jsx | Unused ChevronDown import | Removed |
| SettingsPage.jsx | Unused useEffect import | Removed |
| BandwidthPage.jsx | profiles state assigned but never read in JSX | Prefixed with _ |
| StreamingPage.jsx | Dead bufferLevel/currentBitrate state with unused setters | Replaced with simple const = 0 |

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
