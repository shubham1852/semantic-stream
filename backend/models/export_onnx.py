"""
models/export_onnx.py
=====================
One-shot script to export the YOLOv8n PyTorch weights to ONNX format
for use with the SemanticStream inference engine.

Usage
-----
    python backend/models/export_onnx.py

Requirements
------------
    pip install ultralytics          # only needed for this export step
    pip install onnxruntime          # already in requirements.txt

What it does
------------
1. Loads the YOLOv8n .pt checkpoint (backend/yolov8n.pt by default)
2. Exports to ONNX at backend/models/weights/yolov8n.onnx
3. Verifies the resulting ONNX file with onnxruntime
4. Prints the output shape so you can sanity-check the model

After running this script, the backend will start in REAL_ONNX mode
instead of MOCK_FALLBACK mode.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

# ── Resolve project root and source/dest paths ────────────────────────────────
HERE = Path(__file__).parent                        # backend/models/
BACKEND_ROOT = HERE.parent                          # backend/
WEIGHTS_DIR = HERE / "weights"
DEST_PATH = WEIGHTS_DIR / "yolov8n.onnx"

# Look for the .pt file next to backend/ first, then inside backend/
PT_CANDIDATES = [
    BACKEND_ROOT / "yolov8n.pt",
    BACKEND_ROOT.parent / "yolov8n.pt",
]

SOURCE_PT: Path | None = next((p for p in PT_CANDIDATES if p.exists()), None)


def main() -> None:
    print("=" * 60)
    print("SemanticStream — ONNX Export Script")
    print("=" * 60)

    # ── Locate source weights ─────────────────────────────────────────────────
    if SOURCE_PT is None:
        print("\n[ERROR] Could not find yolov8n.pt in any of:")
        for p in PT_CANDIDATES:
            print(f"        {p}")
        print("\nDownload it with:")
        print("  from ultralytics import YOLO; YOLO('yolov8n.pt')")
        sys.exit(1)

    print(f"\n[OK] Source weights:  {SOURCE_PT}")
    print(f"[OK] Output path:     {DEST_PATH}")

    # ── Check ultralytics is available ────────────────────────────────────────
    try:
        from ultralytics import YOLO  # type: ignore
    except ImportError:
        print("\n[ERROR] ultralytics is not installed.")
        print("Install it with:  pip install ultralytics")
        print("(It is only required for this export step, not for inference.)")
        sys.exit(1)

    # ── Export ────────────────────────────────────────────────────────────────
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    print("\n[...] Loading YOLOv8n model…")
    model = YOLO(str(SOURCE_PT))

    print("[...] Exporting to ONNX (opset 12, no dynamic axes)…")
    model.export(
        format="onnx",
        imgsz=640,
        opset=12,
        simplify=True,
        dynamic=False,
    )

    # ultralytics exports to the same dir as the .pt file by default
    generated = SOURCE_PT.with_suffix(".onnx")
    if not generated.exists():
        print(f"\n[ERROR] Expected ONNX at {generated} but it was not found.")
        sys.exit(1)

    # Move to the canonical weights directory
    import shutil
    shutil.move(str(generated), str(DEST_PATH))
    print(f"\n[OK] Exported to: {DEST_PATH}")

    # ── Verify with onnxruntime ───────────────────────────────────────────────
    print("[...] Verifying with onnxruntime…")
    try:
        import onnxruntime as ort  # type: ignore
        import numpy as np

        session = ort.InferenceSession(
            str(DEST_PATH), providers=["CPUExecutionProvider"]
        )
        inp = session.get_inputs()[0]
        print(f"[OK] Input  — name: {inp.name}, shape: {inp.shape}")
        out = session.get_outputs()[0]
        print(f"[OK] Output — name: {out.name}, shape: {out.shape}")

        # Run a dummy forward pass
        dummy = np.zeros((1, 3, 640, 640), dtype=np.float32)
        result = session.run(None, {inp.name: dummy})
        print(f"[OK] Forward pass — output shape: {result[0].shape}")

    except ImportError:
        print("[WARN] onnxruntime not installed — skipping verification.")
        print("       Install with: pip install onnxruntime")

    # ── File size check ───────────────────────────────────────────────────────
    size_mb = DEST_PATH.stat().st_size / (1024 * 1024)
    print(f"\n[OK] File size: {size_mb:.1f} MB")
    if size_mb < 5:
        print("[WARN] File seems small — the export may be incomplete.")
    else:
        print("[OK] File size looks correct (expected ~12 MB for YOLOv8n).")

    print("\n" + "=" * 60)
    print("Export complete.")
    print("The backend will now start in REAL_ONNX mode.")
    print("Restart the FastAPI server to pick up the new weights.")
    print("=" * 60)


if __name__ == "__main__":
    main()
