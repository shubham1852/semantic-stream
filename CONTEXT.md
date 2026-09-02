# SEMANTICSTREAM — MASTER CONTEXT DOCUMENT
<!-- AI AGENT: Read this file at the start of EVERY session before touching any code. -->
<!-- Last updated: 2026-08-30 -->

---

## 0. YOUR PERMANENT ROLE

You are the Senior Full-Stack Engineer, AI/ML Engineer, Multimedia Systems Architect,
and Technical Lead for this project. Responsibilities:
- Design and protect the overall system architecture
- Write production-quality, modular, documented code
- Maintain complete consistency across every file
- Never contradict a previous architectural decision
- Follow SOLID, DRY, KISS principles at all times
- Always plan modules and interfaces BEFORE implementing

Before writing any code, mentally execute:
1. Understand the module and its role in the system
2. Check what already exists (read PROGRESS.md first)
3. Define the module interface (inputs, outputs, dependencies)
4. Choose the simplest correct implementation
5. Validate: scalable, testable, replaceable?
6. Then write the code

---

## 1. PROJECT IDENTITY

| Field | Value |
|-------|-------|
| **Project Name** | SemanticStream |
| **Full Title** | SemanticStream: Semantic-Aware Adaptive Video Streaming Framework with Bandwidth-Aware Region Priority Encoding |
| **Version** | 1.0.0 |
| **Institution** | Vellore Institute of Technology (VIT), Vellore |
| **Course** | BITE314L — Multimedia Systems, Fall Semester 2026-27 |
| **Team** | Mayukh Banerjee (23BIT0061), Shubham Kumar (23BIT0079), Yashwant Sahoo (23BIT0115) |
| **Guide** | Dr. Balasubramani M, Dept. of Information Technology |
| **License** | MIT |
| **GitHub** | semanticstream (suggested repo name) |

---

## 2. PROBLEM & SOLUTION

**Problem:** Conventional ABR streaming (HLS, MPEG-DASH, WebRTC) reduces quality
UNIFORMLY across the entire frame when bandwidth degrades. This is spatially blind —
a face gets the same compression as an empty background, destroying perceptual quality
exactly where the human visual system is focused.

**Solution:** SemanticStream introduces a semantic priority layer between the YOLO
object detection pipeline and the video encoder. Each frame is classified into a
5-tier priority hierarchy; QP values are applied spatially non-uniformly (low QP =
high quality for faces, high QP = aggressive compression for background). Under
bandwidth pressure, perceptually important content is protected.

**Novel Contributions (NEVER REMOVE):**
1. **5-Tier Dynamic Priority Hierarchy** — changes per frame based on class + confidence + motion + temporal persistence
2. **SPQI (Semantic Perceptual Quality Index)** — first semantically-weighted full-reference video quality metric
3. **Closed-Loop Semantic Rate Controller** — P1 SPQI shortfall triggers reallocation from P5 budget
4. **Confidence-Weighted Graceful Degradation** — falls back to optical flow when detection confidence drops
5. **SEES (Semantic Energy Efficiency Score)** — measures compute saved by temporal propagation

---

## 3. TECHNOLOGY STACK

### Backend
| Tool | Purpose |
|------|---------|
| Python 3.11+ | Language |
| FastAPI (async) | REST API framework, OpenAPI auto-docs |
| YOLOv8n (Ultralytics → ONNX) | Object detection |
| OpenCV DNN | ONNX inference (no PyTorch at runtime) |
| OpenCV 4.9+ + PyAV | Video frame extraction, container manipulation |
| FFmpeg + ffmpeg-python | Per-macroblock QP matrix injection, libx264 encoding |
| scikit-image | SSIM/PSNR computation |
| ReportLab | PDF report generation |
| SQLAlchemy ORM | Database abstraction |
| SQLite (dev) / PostgreSQL (prod) | Database engine |
| Pydantic v2 | Request/response validation schemas |
| FastAPI BackgroundTasks | Parallel experiment jobs |
| FastAPI WebSocket | Live camera feed |
| structlog | Structured JSON logging (NEVER use print()) |

### Frontend
| Tool | Purpose |
|------|---------|
| React 18 + Vite | Framework + build tool |
| Tailwind CSS v3 | Styling (NO component library — custom only) |
| Zustand | Global state management |
| React Router v6 | Client-side routing |
| Recharts | Charts (primary) |
| D3.js | Custom heatmap visualization |
| HLS.js | Adaptive stream playback |
| Axios + interceptors | HTTP client |
| Lucide React | Icons |
| KaTeX | Math formula rendering (SPQI/SEES on ResearchPage) |
| Native WebSocket API | Live camera hook |

### DevOps
- Docker + Docker Compose (single `docker-compose up` startup)
- Environment variables via `.env` (NEVER hardcode config)
- Hot reload for both frontend and backend in development

---

## 4. COMPLETE FOLDER STRUCTURE

```
semanticstream/
├── README.md
├── CONTEXT.md                    ← THIS FILE (AI master reference)
├── PROGRESS.md                   ← Completion tracker
├── docker-compose.yml
├── .env.example
├── .gitignore
│
├── backend/
│   ├── main.py                   # FastAPI entry point — ZERO business logic
│   ├── requirements.txt
│   ├── Dockerfile
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── upload.py         # POST /api/v1/upload
│   │   │   ├── analyze.py        # POST /api/v1/analyze/{video_id}
│   │   │   ├── results.py        # GET  /api/v1/results/{job_id}
│   │   │   ├── stream.py         # GET  /api/v1/stream/{video_id}
│   │   │   ├── experiment.py     # POST /api/v1/experiment
│   │   │   ├── history.py        # GET  /api/v1/history
│   │   │   ├── bandwidth.py      # GET  /api/v1/bandwidth-profiles
│   │   │   └── report.py         # GET  /api/v1/report/{session_id}
│   │   └── websocket.py          # WebSocket /ws/live
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── detection_service.py  # Priority map pipeline (Section 4.1)
│   │   ├── compression_service.py# QP map + FFmpeg encoding (Section 4.2)
│   │   ├── bandwidth_service.py  # 5 bandwidth profiles (Section 4.6)
│   │   ├── analytics_service.py  # SPQI, SSIM, SEES computation
│   │   ├── scene_service.py      # Scene cut detection + classification (Section 4.5)
│   │   └── report_service.py     # ReportLab PDF generator
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── yolo_engine.py        # YOLOv8n ONNX loader + inference
│   │   └── model_cache.py        # Singleton model instance manager [MISSING]
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py             # ALL configuration — env-based via pydantic-settings
│   │   ├── logging_config.py     # structlog setup
│   │   └── exceptions.py        # All custom exception classes
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── database.py           # SQLAlchemy engine + async session
│   │   ├── models.py             # ORM table definitions (6 tables)
│   │   └── crud.py               # All DB read/write operations
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── video.py              # Video/upload Pydantic models
│   │   ├── analysis.py           # Results/metrics Pydantic models
│   │   └── experiment.py         # Experiment Pydantic models
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── frame_utils.py        # Frame extraction, resize, normalize
│   │   ├── qp_utils.py           # QP calculation from priority scores
│   │   ├── metric_utils.py       # SSIM, PSNR, SPQI, SEES formulas
│   │   └── file_utils.py         # File handling, path management [MISSING]
│   │
│   ├── storage/
│   │   ├── uploads/
│   │   ├── processed/
│   │   ├── frames/
│   │   └── reports/
│   │
│   └── tests/
│       ├── __init__.py
│       ├── test_analytics_service.py [MISSING]
│       ├── test_detection_service.py [MISSING]
│       └── test_metric_utils.py [MISSING]
│
└── frontend/
    ├── package.json
    ├── vite.config.js            # Proxy: /api → :8000, /ws → :8000 (ws)
    ├── tailwind.config.js        # Design system tokens
    ├── Dockerfile
    ├── index.html                # Google Fonts: Space Grotesk, Inter, JetBrains Mono
    │
    └── src/
        ├── main.jsx
        ├── App.jsx               # Router — 12 routes total [NEEDS UPDATE]
        │
        ├── pages/
        │   ├── LandingPage.jsx   # / — standalone full-width, no sidebar [MISSING]
        │   ├── DashboardPage.jsx # /dashboard ✅
        │   ├── UploadPage.jsx    # /upload ✅
        │   ├── ResultsPage.jsx   # /results/:jobId ✅
        │   ├── LivePage.jsx      # /live ✅
        │   ├── StreamingPage.jsx # /streaming [MISSING]
        │   ├── AnalyticsPage.jsx # /analytics [MISSING]
        │   ├── BandwidthPage.jsx # /bandwidth [MISSING]
        │   ├── ExperimentPage.jsx# /experiments ✅
        │   ├── ReportsPage.jsx   # /reports [MISSING]
        │   ├── HistoryPage.jsx   # /history ✅
        │   ├── SettingsPage.jsx  # /settings [MISSING]
        │   ├── ResearchPage.jsx  # /research [MISSING]
        │   └── NotFoundPage.jsx  # /* ✅
        │
        ├── components/
        │   ├── layout/
        │   │   ├── PageShell.jsx ✅
        │   │   ├── Sidebar.jsx   ✅ [NEEDS more nav items]
        │   │   └── Topbar.jsx    ✅
        │   │
        │   ├── ui/
        │   │   ├── Button.jsx    ✅
        │   │   ├── Card.jsx      ✅
        │   │   ├── Badge.jsx     ✅
        │   │   ├── Spinner.jsx   ✅
        │   │   ├── Toast.jsx     ✅
        │   │   ├── Modal.jsx     ✅
        │   │   ├── ProgressBar.jsx ✅
        │   │   ├── Tooltip.jsx   ✅
        │   │   ├── Slider.jsx    [MISSING]
        │   │   └── Toggle.jsx    [MISSING]
        │   │
        │   ├── video/
        │   │   ├── VideoUploader.jsx  ✅
        │   │   ├── VideoPlayer.jsx    ✅
        │   │   ├── LiveCameraView.jsx ✅
        │   │   ├── DetectionOverlay.jsx ✅
        │   │   ├── HeatmapOverlay.jsx [MISSING]
        │   │   ├── FrameScrubber.jsx  [MISSING]
        │   │   └── PriorityLegend.jsx [MISSING]
        │   │
        │   └── charts/
        │       ├── MetricsLineChart.jsx    ✅
        │       ├── BitrateBarChart.jsx     ✅
        │       ├── StrategyRadarChart.jsx  ✅
        │       ├── QpHeatmapGrid.jsx       ✅
        │       ├── BandwidthChart.jsx      ✅
        │       ├── SpqiChart.jsx           [MISSING]
        │       ├── ConfidenceChart.jsx     [MISSING]
        │       └── TierAllocationChart.jsx [MISSING]
        │
        ├── hooks/
        │   ├── useJobPoller.js        ✅
        │   ├── useExperimentPoller.js ✅
        │   └── useWebSocket.js        ✅
        │
        ├── store/
        │   └── useAppStore.js  ✅ (upload, analysis, experiment, ui slices)
        │
        ├── api/
        │   ├── client.js       ✅ (Axios, baseURL=/api/v1, envelope unwrapper)
        │   ├── videos.js       ✅ (uploadVideo, getHistory)
        │   ├── analysis.js     ✅ (startAnalysis, getResults)
        │   ├── experiments.js  ✅ (startExperiment, getExperimentResults)
        │   ├── bandwidth.js    ✅ (getBandwidthProfiles)
        │   ├── reports.js      [MISSING]
        │   └── stream.js       [MISSING]
        │
        └── styles/
            └── index.css  ✅
```

---

## 5. DESIGN SYSTEM (LOCKED — NEVER CHANGE)

### Colors
```
bg-primary:    #0A0E1A   (deep navy)
bg-secondary:  #0F1426
bg-card:       #151C34
accent:        #4F46E5   (indigo)
accent-light:  #818CF8
data-green:    #00FF87   (phosphor — success, live, SemanticStream color)
data-amber:    #F59E0B   (warning, Static ROI color)
data-red:      #EF4444   (error, Uniform ABR color)
data-blue:     #60A5FA   (info)
text-primary:  #F0F0FF
text-muted:    #8892A4
border:        rgba(79,70,229,0.18)
```

### Priority Tier Colors
```
P1 (Face):       #00FF87  — bright green
P2 (Text):       #4ADE80  — mid green
P3 (Motion):     #F59E0B  — amber
P4 (Objects):    #818CF8  — indigo-light
P5 (Background): #EF4444  — red
```

### Typography
```
Display/headings: Space Grotesk (Google Fonts)
Body/UI:          Inter (Google Fonts)
Code/metrics:     JetBrains Mono (Google Fonts)
```

### Component Rules
- Cards: border-radius 12px, 1px border, `glass-card` class (backdrop-filter blur)
- Buttons: 8px radius, Space Grotesk font, glow on hover for primary
- All charts: dark background, indigo/green palette
- Loading states: Spinner component
- Empty states: icon + heading + action button
- Error states: red border + message + retry button

### Strategy Colors (charts)
```
Uniform ABR:    #EF4444  (red)
Static ROI:     #F59E0B  (amber)
SemanticStream: #00FF87  (green)
```

---

## 6. DATABASE SCHEMA (6 tables)

```sql
TABLE videos
  id UUID PK, filename, filepath, duration_seconds, fps,
  width, height, size_mb, uploaded_at

TABLE analysis_jobs
  id UUID PK, video_id FK, status (queued/running/done/failed),
  bandwidth_profile, frame_sample_rate, confidence_threshold,
  progress_percent, started_at, completed_at, error_message

TABLE frame_metrics
  id UUID PK, job_id FK, frame_number, timestamp_ms,
  spqi_score, ssim_score, psnr_score, bitrate_kbps,
  detection_confidence, scene_type, sees_contribution_ms,
  p1_ssim, p2_ssim, p3_ssim, p4_ssim, p5_ssim

TABLE experiments
  id UUID PK, video_id FK, bandwidth_profile, created_at

TABLE experiment_results
  id UUID PK, experiment_id FK, strategy_name,
  avg_spqi, avg_ssim, avg_bitrate_mbps, face_ssim,
  bg_ssim, encode_time_ms, sees_score, bitrate_reduction_pct

TABLE scene_events
  id UUID PK, job_id FK, frame_number, timestamp_ms,
  previous_scene_type, new_scene_type, histogram_score
```

---

## 7. COMPLETE API CONTRACT

**Base prefix:** `/api/v1/`
**Response envelope:** `{ "status": "success"|"error", "data": {}, "message": "" }`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/upload` | Upload video (multipart), returns video_id |
| POST | `/analyze/{video_id}` | Queue analysis job, returns job_id |
| GET | `/results/{job_id}` | Poll job status + metrics |
| GET | `/frame/{video_id}/{frame_number}` | Single frame with overlay |
| POST | `/experiment` | Start multi-strategy experiment |
| GET | `/experiment/{id}/results` | Experiment results + winner |
| GET | `/history` | Paginated session list |
| GET | `/report/{session_id}` | Download PDF report |
| GET | `/bandwidth-profiles` | List of 5 profiles |
| WS | `/ws/live` | Live camera frame analysis |

### Request/Response Key Fields

**POST /analyze/{video_id}** body:
```json
{ "frame_sample_rate": 5, "confidence_threshold": 0.45,
  "bandwidth_profile": "strong_wifi", "run_comparison": false }
```

**GET /results/{job_id}** response data:
```json
{
  "job_id": "...", "status": "done", "progress_percent": 100,
  "metrics": {
    "per_frame_metrics": [{ "frame_index": 0, "psnr": 38.2, "ssim": 0.94,
      "spqi": 0.91, "dominant_tier": "P1", "assigned_qp": 18 }],
    "summary": {
      "avg_psnr": 37.8, "avg_ssim": 0.93, "avg_spqi": 0.89,
      "avg_bitrate_mbps": 2.1, "bitrate_reduction_pct": 42.3,
      "sees_score": 0.67, "face_ssim": 0.97, "bg_ssim": 0.81,
      "encode_time_ms": 4230
    },
    "scene_events": [{ "timestamp": 12.4, "scene_type": "DIALOGUE" }]
  }
}
```

**WS /ws/live** protocol:
- Client sends: `{ "frame_base64": "<JPEG base64>" }`
- Server sends: `{ "priority_map_base64": "...", "detections": [...],
    "spqi": 0.87, "confidence": 0.92, "scene_type": "DIALOGUE",
    "current_qp_assignments": {"P1": 18, "P5": 40}, "processing_time_ms": 34 }`

---

## 8. CORE ALGORITHMS

### 8.1 Semantic Priority Engine (detection_service.py)
```
INPUT:  raw video frame (numpy BGR array)
OUTPUT: priority_map (HxW float32, values 0.0–1.0)

Step 1 — Preprocessing:
  Resize to 640×480, Normalize ImageNet stats, BGR→RGB

Step 2 — YOLO Inference (YOLOv8n ONNX via OpenCV DNN):
  Filter detections below confidence_threshold (default 0.45)

Step 3 — Priority Map (5-tier hierarchy):
  P1 (1.0): Face/Person bounding boxes
  P2 (0.8): Text overlay regions
  P3 (0.6): High optical flow magnitude (LK flow > 2.0px)
  P4 (0.4): All other detected objects
  P5 (0.1): Remaining background pixels
  Overlap rule: take MAX priority score

Step 4 — Confidence Weighting (NOVEL — Graceful Degradation):
  effective_priority = tier_score × detection_confidence
  If P1 confidence < 0.5: downgrade to P3 treatment
  Log as "degraded_mode" in analytics

Step 5 — Temporal Smoothing (NOVEL — source of SEES):
  priority_map_final = 0.3 × current_map + 0.7 × previous_map  (α=0.3)
  P5-only background regions: propagate from previous frame (skip inference)
```

### 8.2 Compression Decision Engine (compression_service.py)
```
INPUT:  priority_map, bandwidth_estimate_mbps
OUTPUT: qp_matrix (per-macroblock QP integers)

Step 1 — BW Estimation: harmonic mean of last 5 segments × 0.85 safety margin
Step 2 — Target Bitrate (BOLA-inspired):
  buffer > 8s → 80% usable_bw | buffer < 4s → emergency 40%
Step 3 — Per-Tier Budget:
  Normal:    P1=40%, P2=15%, P3=20%, P4=15%, P5=10%
  Emergency: P1=40%, P2=15%, P3=25%, P4=10%, P5=5%
Step 4 — QP Lookup (720p/30fps): QP18→4Mbps, QP24→2Mbps, QP28→1.2Mbps,
                                   QP34→0.6Mbps, QP40→0.3Mbps
Step 5 — Closed-Loop (NOVEL): If P1 SPQI < 0.75 → reallocate 5% P5→P1
```

### 8.3 SPQI Formula
```
SPQI = Σᵢ [wᵢ × SSIM(regionᵢ, compressed_regionᵢ)] / Σᵢ [wᵢ]
  wᵢ: P1=1.0, P2=0.8, P3=0.6, P4=0.4, P5=0.1
  SSIM: scikit-image per bounding box
```

### 8.4 SEES Formula
```
SEES = (T_baseline - T_semantic) / T_baseline × 100%
  T_baseline: full inference on all regions, all frames
  T_semantic: skip inference on P5-only regions (propagate instead)
  Measured with time.perf_counter()
```

### 8.5 Scene Detection (scene_service.py)
```
HSV histogram correlation (32 bins/ch) < 0.65 → cut
Classification: >60% face area=DIALOGUE | flow>5px=ACTION | text>20%=TITLE CARD | else=GENERAL
On cut: flush temporal buffer, fresh inference for 3 frames
```

### 8.6 Bandwidth Profiles
```
strong_wifi:  8 Mbps constant ± 0.3 Mbps noise
weak_wifi:    2 Mbps mean ± 0.6 Mbps jitter
4g_degrading: 5→1.5 Mbps over 60s, recovers to 3.5 Mbps
burst_loss:   6 Mbps + 3 drops to 0.3 Mbps at t=20,50,90s (3s each)
stress_test:  4↔0.5 Mbps alternating every 8 seconds
```

---

## 9. THREE BASELINE STRATEGIES

| ID | Label | Color | Description |
|----|-------|-------|-------------|
| `uniform_abr` | Uniform ABR | #EF4444 | QP=28 everywhere, no AI |
| `static_roi` | Static ROI | #F59E0B | Center 40% = QP 20, rest QP 35 |
| `semanticstream` | SemanticStream | #00FF87 | Full YOLO + 5-tier + closed-loop |

---

## 10. FRONTEND — 12 PAGES SPEC

| # | Page | Route | Layout | Key Content |
|---|------|-------|---------|-------------|
| 1 | LandingPage | `/` | **Standalone (NO sidebar)** | Full-screen hero, animated CSS heatmap demo, CTA |
| 2 | DashboardPage | `/dashboard` | PageShell | Stat cards, SPQI trend, bitrate bar, recent sessions |
| 3 | UploadPage | `/upload` | PageShell | 4-step: upload→config→analyse→redirect |
| 4 | LivePage | `/live` | PageShell | Webcam → WS → heatmap side-by-side |
| 5 | StreamingPage | `/streaming` | PageShell | HLS VideoPlayer + live metrics sidebar |
| 6 | AnalyticsPage | `/analytics` | PageShell | 3-strategy comparison + all 6 chart types + scene markers |
| 7 | BandwidthPage | `/bandwidth` | PageShell | 5 profile cards + area chart + run simulation |
| 8 | ExperimentPage | `/experiments` | PageShell | 3-column workbench, parallel run, radar chart |
| 9 | ReportsPage | `/reports` | PageShell | Reports list, PDF preview, download |
| 10 | HistoryPage | `/history` | PageShell | Sortable, paginated table |
| 11 | SettingsPage | `/settings` | PageShell | QP override table, sliders, toggles, localStorage persist |
| 12 | ResearchPage | `/research` | PageShell | KaTeX SPQI/SEES, architecture SVG, contributions |

**IMPORTANT:** LandingPage is at route `/` and uses a STANDALONE layout (no Sidebar, no Topbar).
The current DashboardPage should move to `/dashboard` and the root `/` redirect goes to Landing.

---

## 11. PDF REPORT STRUCTURE

```
Page 1: Title, session metadata (video, profile, date, team)
Page 2: Results Table — Metric | Uniform ABR | Static ROI | SemanticStream | winner in green
Page 3: Auto-generated conclusion (template with actual numbers)
Page 4: Charts (SPQI timeline, Bitrate chart, Tier allocation bar)
Page 5: SPQI and SEES formula definitions
Page 6: References (17 papers from literature survey)
```

---

## 12. CODING STANDARDS

### Python
- Type hints on ALL parameters and return values
- Google-style docstrings on all modules and functions
- Max 50 lines per function — split into helpers
- All config in `core/config.py` — no magic numbers
- All paths via `pathlib.Path`
- All errors raise custom exceptions from `core/exceptions.py`
- Logging via `structlog` — NEVER `print()`

### React
- Functional components only
- One component per file, PascalCase
- No inline styles — Tailwind ONLY
- No hardcoded API URLs — through `api/` clients
- Loading + empty + error states in EVERY data-fetching component
- async/await with proper error handling

### Architecture
- Routes call services ONLY — zero business logic in routes
- Components call `api/` functions — never direct Axios
- State in Zustand or local component state

---

## 13. WHAT NEVER TO DO

- Business logic in route files
- Hardcoded QP values, thresholds, paths
- print() — use structlog
- Global variables
- Components that fetch + render + manage state all in one
- Missing loading/error/empty states in data components
- Inline styles in React
- API keys in code
- Direct Axios in components
- Paid/proprietary APIs or models

---

## 14. SESSION STARTUP CHECKLIST

At the start of EVERY new session:
1. Read CONTEXT.md (this file)
2. Read PROGRESS.md to see current completion state
3. Identify next incomplete item in build order
4. Check existing relevant files before writing new ones
5. Build without breaking anything existing
