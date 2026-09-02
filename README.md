<div align="center">

# SemanticStream

**Smarter video compression, powered by what the eye actually cares about.**

*A final-year research project @ VIT Vellore — BITE314L Multimedia Systems*

[![Python](https://img.shields.io/badge/Python-3.11-blue?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-teal?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react)](https://reactjs.org)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-ONNX-purple?style=flat-square)](https://ultralytics.com)
[![License](https://img.shields.io/badge/License-All%20Rights%20Reserved-red?style=flat-square)](#)

</div>

---

## The problem with streaming today

When your internet drops, Netflix doesn't decide *which parts of the video deserve to stay sharp*. It compresses everything equally — your face gets pixelated the same way the background does. That's perceptually wrong.

SemanticStream fixes this. It uses object detection to understand what's **semantically important** in each frame, then applies aggressive compression only to things that don't matter visually — like sky, walls, and empty floors.

The result: a **42% bitrate reduction** with barely any perceptual quality loss on faces and text.

---

## How it works

```
Video Frame
    │
    ▼
YOLOv8n Detection ──► 5-Tier Priority Map
    │                       │
    │                  P1 Face/Person  → QP 18 (sharpest)
    │                  P2 Text/UI      → QP 22
    │                  P3 Motion       → QP 26
    │                  P4 Objects      → QP 32
    │                  P5 Background   → QP 40 (most compressed)
    │                       │
    ▼                       ▼
Optical Flow           QP Matrix
    │                       │
    └───────────────────────┘
                │
                ▼
        FFmpeg Encoder
                │
                ▼
     Compressed Output + SPQI Score
```

Every frame gets its own spatially non-uniform quantization map. The more important the region, the less it gets compressed.

---

## Running it locally

You need Python 3.11+, Node 18+, and FFmpeg.

```bash
# Clone
git clone https://github.com/shubham1852/semantic-stream.git
cd semantic-stream

# Backend
cd backend
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install && npm run dev
```

App runs at `http://localhost:5173`, API at `http://localhost:8000/api/docs`.

**Or with Docker:**
```bash
docker-compose up --build
```

---

## What you can do with it

- **Upload any MP4/MOV** and run the semantic analysis pipeline on it
- **Compare 3 strategies** side-by-side: Uniform ABR vs Static ROI vs SemanticStream
- **Live webcam mode** — point your camera at anything and see the priority heatmap in real-time via WebSocket
- **Download a PDF report** with per-session metrics, charts, and the SEES breakdown
- **Adjust QP values** in Settings and re-run to see how they affect quality/bitrate tradeoffs

---

## API overview

All responses follow `{ status, data, message }`.

| Endpoint | What it does |
|----------|-------------|
| `POST /api/v1/upload` | Upload a video (up to 2 GB) |
| `POST /api/v1/analyze/{video_id}` | Start analysis job |
| `GET /api/v1/results/{job_id}` | Poll job progress + metrics |
| `POST /api/v1/experiment` | Run strategy comparison |
| `GET /api/v1/frame/{id}/{n}` | Get annotated frame with heatmap |
| `GET /api/v1/report/{session_id}` | Download PDF report |
| `WS /ws/live` | Real-time webcam analysis |

Full OpenAPI spec at `/api/docs` when the server is running.

---

## Tech stack

**Backend** — FastAPI, SQLAlchemy async (SQLite/Postgres), YOLOv8n via OpenCV ONNX runtime, ReportLab for PDFs, structlog for logging.

**Frontend** — React 18 + Vite, Zustand for state, Recharts + D3 for charts, HLS.js for streaming, KaTeX for formula rendering.

**Why ONNX instead of PyTorch?** Inference is ~3× faster and the runtime doesn't require a GPU or CUDA driver. The model runs fine on a CPU for real-time webcam analysis.

---

## Results

We tested on 4 video types: talking-head interview, action sequence, UI screencast, and nature footage.

| Metric | Uniform ABR | SemanticStream | Improvement |
|--------|-------------|----------------|-------------|
| Avg SPQI | 0.72 | 0.91 | +26% |
| Face SSIM | 0.79 | 0.97 | +23% |
| Bitrate | 2.80 Mbps | 1.62 Mbps | −42% |
| SEES Score | — | 0.67 | — |

Background SSIM drops slightly (0.83 → 0.81) — which is the whole point.

---

## Project structure

```
semantic-stream/
├── backend/
│   ├── api/routes/         # 8 REST endpoints
│   ├── services/           # detection, compression, analytics, streaming, report
│   ├── models/             # YOLOv8 ONNX engine + singleton cache
│   ├── database/           # SQLAlchemy ORM + CRUD
│   ├── utils/              # metrics, frame ops, file helpers, QP math
│   └── tests/              # 59 unit tests
└── frontend/
    ├── src/pages/          # 14 pages
    ├── src/components/     # 30+ UI + video + chart components
    ├── src/store/          # Zustand slices
    └── src/api/            # Axios client + 7 API modules
```

---

## Team

Built by three third-year Information Technology students at VIT Vellore as part of the BITE314L Multimedia Systems course.

- **Mayukh Banerjee** — 23BIT0061
- **Shubham Kumar** — 23BIT0079  
- **Yashwant Sahoo** — 23BIT0115

Guide: Dr. Balasubramani M, Department of IT, VIT Vellore.

---

<div align="center">

© 2026 Mayukh Banerjee, Shubham Kumar, Yashwant Sahoo · VIT Vellore · All Rights Reserved

</div>
