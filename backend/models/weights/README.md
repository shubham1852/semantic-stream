# Model Weights

This directory stores the YOLOv8n ONNX weights used by the SemanticStream
inference engine.

## What goes here

| File | Size | Purpose |
|------|------|---------|
| `yolov8n.onnx` | ~12 MB | YOLOv8 Nano ONNX model for CPU inference |
| `.gitkeep` | 0 B | Keeps directory tracked by git |

> **Note:** `*.onnx` files are excluded from git (see `.gitignore`).
> Each developer must export the model locally.

## How to generate `yolov8n.onnx`

Run the export script from the **project root**:

```bash
# 1 — Install the export dependency (one-time)
pip install ultralytics

# 2 — Run the script
python backend/models/export_onnx.py
```

The script will:
1. Load `backend/yolov8n.pt` (the PyTorch checkpoint)
2. Export it to `backend/models/weights/yolov8n.onnx`
3. Verify the export with onnxruntime
4. Print the output tensor shape

After this, restart the FastAPI server. The startup log will show:

```
yolo_model_loaded  path=...yolov8n.onnx  mode=REAL_ONNX
```

## If you skip this step

The backend starts in `MOCK_FALLBACK` mode — it returns **simulated**
random detections instead of running real inference. All metrics will still
be computed (using the mock bounding boxes), so the pipeline stays exercisable
without the model. The Live Camera page will show an amber warning banner.

## Model details

- Architecture: YOLOv8 Nano (YOLOv8n)
- Task: Object detection (COCO 80-class)
- Input: `(1, 3, 640, 640)` float32, normalised to [0, 1]
- Output: `(1, 84, 8400)` — 4 bbox coords + 80 class scores per anchor
- Inference provider: `CPUExecutionProvider` (CUDA auto-detected if available)
- Licence: [AGPL-3.0](https://ultralytics.com/license) (Ultralytics)
