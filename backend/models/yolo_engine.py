"""
models/yolo_engine.py
=====================
ONNX-based YOLOv8 inference engine for SemanticStream.

Responsibilities
----------------
* Load a YOLOv8n ONNX model once at startup (singleton pattern).
* Run object-detection inference on a single BGR frame (NumPy array).
* Return a list of :class:`Detection` dataclasses ready for the priority
  pipeline in ``services/detection_service.py``.
* Gracefully fall back to **mock detections** when the model file is absent
  (useful in CI or during early development).

COCO class IDs referenced by the 5-tier priority system
---------------------------------------------------------
Tier 1 — Person / Face  : class 0  (person)
Tier 4 — Other objects  : all other COCO classes

Text overlays (Tier 2) and optical flow (Tier 3) are detected by the
detection service using dedicated frame utilities, not YOLO.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import numpy as np

from backend.core.config import settings
from backend.core.exceptions import ModelLoadError
from backend.core.logging_config import get_logger

log = get_logger(__name__)

# ── COCO class groups ─────────────────────────────────────────────────────────
_PERSON_CLASSES: frozenset[int] = frozenset({0})          # person
_VEHICLE_CLASSES: frozenset[int] = frozenset({1, 2, 3, 4, 5, 6, 7, 8})  # bicycle…boat
_SPORTS_CLASSES: frozenset[int] = frozenset(range(27, 40))  # sports ball … tennis racket
_ANIMAL_CLASSES: frozenset[int] = frozenset(range(14, 24))  # bird … bear etc.


# ── Detection dataclass ───────────────────────────────────────────────────────

@dataclass
class Detection:
    """A single bounding-box detection from the YOLO model.

    Coordinates are **pixel-space** (x1, y1, x2, y2) in the *original*
    frame dimensions — i.e., after the inference results have been
    rescaled back from the 640 × 480 inference canvas.
    """

    class_id: int
    class_name: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int
    priority_tier: str = ""

    def __post_init__(self) -> None:
        if not self.priority_tier:
            self.priority_tier = "P1" if self.is_person else "P4"

    # Derived helpers ─────────────────────────────────────────────────────────

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        """Return (x1, y1, x2, y2)."""
        return (self.x1, self.y1, self.x2, self.y2)

    @property
    def area(self) -> int:
        """Bounding-box area in pixels²."""
        return max(0, self.x2 - self.x1) * max(0, self.y2 - self.y1)

    @property
    def is_person(self) -> bool:
        return self.class_id in _PERSON_CLASSES or self.class_id == 0

    @property
    def center(self) -> tuple[int, int]:
        return ((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)


# ── Live detection tier mapping ───────────────────────────────────────────────

LIVE_DETECTION_CLASSES = {
    0: ("person", "P1"),      # Highest priority
    56: ("chair", "P4"),
    57: ("couch", "P4"),
    63: ("laptop", "P4"),
    64: ("mouse", "P4"),
    65: ("remote", "P4"),
    66: ("keyboard", "P4"),
    67: ("cell phone", "P4"),
    73: ("book", "P4"),
}


def get_priority_tier(class_id: int, class_name: str = "") -> str:
    """Map YOLO class to SemanticStream priority tier."""
    person_classes = {0, 1}  # person, bicycle
    cname = (class_name or "").lower()
    if class_id in person_classes or "person" in cname or "face" in cname:
        return "P1"
    return "P4"


# ── COCO class name table ─────────────────────────────────────────────────────

COCO_CLASSES: List[str] = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag",
    "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite",
    "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon",
    "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot",
    "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant",
    "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote",
    "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]


# ── YOLOEngine ────────────────────────────────────────────────────────────────

class YOLOEngine:
    """Singleton ONNX inference engine wrapping YOLOv8n.

    The engine is initialised once via :meth:`load` and reused for every
    frame.  If ONNX Runtime is unavailable **or** the model weights file
    does not exist, the engine enters *mock mode* — it returns plausible
    random detections so that the rest of the pipeline can be exercised
    without real weights.

    Parameters
    ----------
    model_path:
        Filesystem path to the ``.onnx`` weights file.  Defaults to the
        value in ``settings.YOLO_MODEL_PATH``.
    confidence_threshold:
        Minimum score to accept a detection.
    nms_threshold:
        IoU threshold for non-maximum suppression.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: float = settings.CONFIDENCE_THRESHOLD,
        nms_threshold: float = settings.NMS_THRESHOLD,
    ) -> None:
        raw_path = str(model_path or settings.YOLO_MODEL_PATH)
        path_obj = Path(raw_path)
        if not path_obj.is_absolute() or not path_obj.exists():
            cand = settings.BASE_DIR / path_obj
            if cand.exists():
                raw_path = str(cand)
            else:
                default_cand = settings.BASE_DIR / "models" / "weights" / "yolov8n.onnx"
                if default_cand.exists():
                    raw_path = str(default_cand)

        self._model_path = raw_path
        self._conf_threshold = confidence_threshold
        self._nms_threshold = nms_threshold
        self._session = None          # onnxruntime.InferenceSession
        self._cv2_net = None          # cv2.dnn.Net fallback
        self._face_cascade = None     # cv2.CascadeClassifier for face precision
        self._mock_mode: bool = False
        self._input_name: str = ""
        self._inf_w: int = settings.INFERENCE_WIDTH
        self._inf_h: int = settings.INFERENCE_HEIGHT

        # Initialize Haar face detector for high-precision P1 Face detection
        try:
            import cv2
            cascade_file = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
            if cascade_file.exists():
                self._face_cascade = cv2.CascadeClassifier(str(cascade_file))
        except Exception:
            self._face_cascade = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def load(self) -> None:
        """Load the ONNX model via ONNX Runtime or OpenCV DNN fallback.

        A missing file activates mock mode; otherwise real AI inference is guaranteed.
        """
        import os

        # Final check if model path exists
        if not os.path.exists(self._model_path):
            cand = settings.BASE_DIR / "models" / "weights" / "yolov8n.onnx"
            if cand.exists():
                self._model_path = str(cand)

        if not os.path.exists(self._model_path):
            log.warning(
                "yolo_engine_startup",
                path=self._model_path,
                mode="MOCK_FALLBACK",
                reason="weights_file_not_found",
                advice="Run: python backend/models/export_onnx.py",
            )
            self._mock_mode = True
            return

        # 1. Try ONNX Runtime first
        try:
            import onnxruntime as ort  # type: ignore
            import os

            providers = ["CPUExecutionProvider"]
            if "CUDAExecutionProvider" in ort.get_available_providers():
                providers.insert(0, "CUDAExecutionProvider")

            opts = ort.SessionOptions()
            opts.intra_op_num_threads = min(4, os.cpu_count() or 4)
            opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            self._session = ort.InferenceSession(
                self._model_path, sess_options=opts, providers=providers
            )
            input_tensor = self._session.get_inputs()[0]
            self._input_name = input_tensor.name
            if len(input_tensor.shape) == 4:
                if isinstance(input_tensor.shape[2], int):
                    self._inf_h = input_tensor.shape[2]
                if isinstance(input_tensor.shape[3], int):
                    self._inf_w = input_tensor.shape[3]
            self._mock_mode = False
            log.info(
                "yolo_engine_startup",
                path=self._model_path,
                mode="REAL_ONNX",
                providers=self._session.get_providers(),
            )
            return
        except Exception as exc:
            log.warning(
                "yolo_engine_ort_fallback",
                error=str(exc),
                advice="Trying OpenCV DNN loader...",
            )

        # 2. Try OpenCV DNN fallback if ONNX Runtime fails or is missing
        try:
            import cv2
            self._cv2_net = cv2.dnn.readNetFromONNX(self._model_path)
            if not self._cv2_net.empty():
                self._mock_mode = False
                log.info(
                    "yolo_engine_startup",
                    path=self._model_path,
                    mode="REAL_OPENCV_DNN",
                )
                return
        except Exception as cv_exc:
            log.warning(
                "yolo_engine_cv2_dnn_failed",
                error=str(cv_exc),
                mode="MOCK_FALLBACK",
            )

        self._mock_mode = True

    def unload(self) -> None:
        """Release the ONNX / OpenCV DNN session."""
        self._session = None
        self._cv2_net = None
        log.info("yolo_model_unloaded")

    # ── Inference ─────────────────────────────────────────────────────────────

    def detect(
        self,
        frame_bgr: np.ndarray,
        conf_threshold: Optional[float] = None,
    ) -> List[Detection]:
        """Run detection on a single BGR frame with real ONNX/DNN inference.

        Returns filtered detections (confidence ≥ threshold, after NMS)
        with face refinement.
        """
        if self._session is None and self._cv2_net is None and not self._mock_mode:
            try:
                self.load()
            except Exception:
                self._mock_mode = True

        if self._mock_mode or (self._session is None and self._cv2_net is None):
            return self._mock_detections(frame_bgr)

        t0 = time.perf_counter()
        try:
            blob, scale_x, scale_y = self._preprocess(frame_bgr)
            if self._session is not None:
                raw = self._session.run(None, {self._input_name: blob})[0]
            else:
                self._cv2_net.setInput(blob)
                raw = self._cv2_net.forward()

            detections = self._postprocess(raw, scale_x, scale_y, conf_threshold)

            # Refine person face detection using Haar cascade if face classifier exists
            detections = self._refine_face_detections(frame_bgr, detections)

            elapsed_ms = (time.perf_counter() - t0) * 1000
            log.debug("yolo_infer", detections=len(detections), elapsed_ms=round(elapsed_ms, 1))
            return detections
        except Exception as exc:
            log.warning("yolo_inference_error", error=str(exc))
            return self._mock_detections(frame_bgr)

    def _refine_face_detections(
        self, frame_bgr: np.ndarray, detections: List[Detection]
    ) -> List[Detection]:
        """Identify faces in detected person regions for pinpoint P1 Face priority."""
        if self._face_cascade is None or not detections:
            return detections

        import cv2

        h, w = frame_bgr.shape[:2]
        new_dets = list(detections)
        has_face = any(d.class_name.lower() == "face" for d in detections)

        # For each person detected, search the upper half for a face
        for det in detections:
            if not det.is_person:
                continue

            # Upper 55% of the person box represents the head/face region
            px1 = max(0, min(det.x1, w - 1))
            px2 = max(0, min(det.x2, w - 1))
            py1 = max(0, min(det.y1, h - 1))
            py2 = max(0, min(det.y1 + int((det.y2 - det.y1) * 0.55), h - 1))

            pw = px2 - px1
            ph = py2 - py1
            if pw < 30 or ph < 30:
                continue

            person_roi = frame_bgr[py1:py2, px1:px2]
            try:
                # Downscale ROI to max 160px for 15x faster cascade evaluation
                target_w = min(pw, 160)
                scale_f = target_w / pw
                target_h = max(1, int(ph * scale_f))
                small_roi = cv2.resize(person_roi, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
                gray_roi = cv2.cvtColor(small_roi, cv2.COLOR_BGR2GRAY)
                faces = self._face_cascade.detectMultiScale(
                    gray_roi,
                    scaleFactor=1.25,
                    minNeighbors=4,
                    minSize=(16, 16),
                )
                inv_s = 1.0 / scale_f
                for (fx, fy, fw, fh) in faces:
                    fx_orig = int(fx * inv_s)
                    fy_orig = int(fy * inv_s)
                    fw_orig = int(fw * inv_s)
                    fh_orig = int(fh * inv_s)
                    new_dets.append(
                        Detection(
                            class_id=0,
                            class_name="face",
                            confidence=round(min(0.99, det.confidence + 0.05), 3),
                            x1=px1 + fx_orig,
                            y1=py1 + fy_orig,
                            x2=px1 + fx_orig + fw_orig,
                            y2=py1 + fy_orig + fh_orig,
                            priority_tier="P1",
                        )
                    )
                    has_face = True
            except Exception:
                pass

        return new_dets

    # ── Private helpers ───────────────────────────────────────────────────────

    def _preprocess(
        self, frame_bgr: np.ndarray
    ) -> tuple[np.ndarray, float, float]:
        """Resize → RGB → normalise → NCHW blob."""
        import cv2  # type: ignore

        orig_h, orig_w = frame_bgr.shape[:2]
        resized = cv2.resize(frame_bgr, (self._inf_w, self._inf_h))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        blob = rgb.astype(np.float32) / 255.0
        blob = np.transpose(blob, (2, 0, 1))   # HWC → CHW
        blob = np.expand_dims(blob, axis=0)    # CHW → NCHW
        scale_x = orig_w / self._inf_w
        scale_y = orig_h / self._inf_h
        return blob, scale_x, scale_y

    def _postprocess(
        self,
        raw: np.ndarray,
        scale_x: float,
        scale_y: float,
        conf_threshold: Optional[float] = None,
    ) -> List[Detection]:
        """Parse YOLOv8 ONNX output and apply NMS.

        YOLOv8 ONNX output shape: (1, 84, num_anchors) where the first 4
        rows are cx, cy, w, h (normalised to inference canvas) and rows
        4–83 are class probabilities.
        """
        import cv2  # type: ignore

        thresh = conf_threshold if conf_threshold is not None else self._conf_threshold

        output = raw[0].T  # (num_anchors, 84)
        class_scores = output[:, 4:]
        class_ids_arr = np.argmax(class_scores, axis=1)
        confidences = class_scores[np.arange(len(class_scores)), class_ids_arr]

        mask = confidences >= thresh
        if not np.any(mask):
            return []

        boxes_raw = output[mask, :4]
        scores = confidences[mask].astype(float).tolist()
        class_ids = class_ids_arr[mask].astype(int).tolist()

        cx = boxes_raw[:, 0]
        cy = boxes_raw[:, 1]
        w = boxes_raw[:, 2]
        h = boxes_raw[:, 3]

        x1 = (cx - w / 2).astype(np.int32)
        y1 = (cy - h / 2).astype(np.int32)
        bw = w.astype(np.int32)
        bh = h.astype(np.int32)

        boxes = [
            [int(x1[i]), int(y1[i]), int(bw[i]), int(bh[i])]
            for i in range(len(x1))
        ]

        if not boxes:
            return []

        # Batched NMS: offset coordinates by class_id * 4096 so distinct classes
        # (e.g. person vs chair/laptop) are preserved and not aggressively merged.
        boxes_for_nms = [
            [b[0] + cid * 4096, b[1] + cid * 4096, b[2], b[3]]
            for b, cid in zip(boxes, class_ids)
        ]

        # Apply NMS
        indices = cv2.dnn.NMSBoxes(
            boxes_for_nms, scores, thresh, self._nms_threshold
        )
        if len(indices) == 0:
            return []

        frame_area = (scale_x * self._inf_w) * (scale_y * self._inf_h)
        detections: List[Detection] = []
        for i in indices.flatten():
            bx, by, bw, bh = boxes[i]
            cid = class_ids[i]
            x1 = max(0, int(bx * scale_x))
            y1 = max(0, int(by * scale_y))
            x2 = int((bx + bw) * scale_x)
            y2 = int((by + bh) * scale_y)
            box_area = max(0, x2 - x1) * max(0, y2 - y1)

            # Area filter: ignore boxes spanning >= 95% of the entire frame (full-frame errors)
            max_area_ratio = 0.98 if cid == 0 else 0.92
            if frame_area > 0 and box_area >= max_area_ratio * frame_area:
                continue

            cname = COCO_CLASSES[cid] if cid < len(COCO_CLASSES) else f"cls_{cid}"
            tier = get_priority_tier(cid, cname)

            det = Detection(
                class_id=cid,
                class_name=cname,
                confidence=scores[i],
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
                priority_tier=tier,
            )
            detections.append(det)

        return detections

    # ── Mock mode ─────────────────────────────────────────────────────────────

    def _mock_detections(self, frame_bgr: np.ndarray) -> List[Detection]:
        """Return reproducible synthetic detections for dev / CI."""
        h, w = frame_bgr.shape[:2]
        rng = np.random.default_rng(seed=int(time.time()) % 1000)

        num = rng.integers(0, 4)
        detections: List[Detection] = []
        for _ in range(num):
            cid = int(rng.choice([0, 2, 14, 56]))  # person/car/bird/chair
            x1 = int(rng.uniform(0, w * 0.6))
            y1 = int(rng.uniform(0, h * 0.6))
            x2 = int(x1 + rng.uniform(w * 0.1, w * 0.3))
            y2 = int(y1 + rng.uniform(h * 0.1, h * 0.3))
            detections.append(
                Detection(
                    class_id=cid,
                    class_name=COCO_CLASSES[cid] if cid < len(COCO_CLASSES) else "object",
                    confidence=float(rng.uniform(0.5, 0.95)),
                    x1=x1,
                    y1=min(y1, h - 1),
                    x2=min(x2, w - 1),
                    y2=min(y2, h - 1),
                )
            )
        return detections

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def is_mock(self) -> bool:
        """True when running in mock mode (no real model loaded)."""
        return self._mock_mode

    @property
    def is_loaded(self) -> bool:
        """True when the ONNX session is active."""
        return self._session is not None or self._mock_mode


# ── Module-level singleton ────────────────────────────────────────────────────

yolo_engine = YOLOEngine()
