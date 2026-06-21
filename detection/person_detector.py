"""
Person Detection Module (SDD C5)
=================================
Detects persons in camera frames using YOLOv8 (primary) or
MobileNet-SSD via OpenCV DNN (fallback).

Per SysRS FR-3.1 / FR-3.2:
    - Detect persons with bounding boxes and confidence scores
    - Run at >= 15 FPS on lobby video stream
    - Configurable confidence threshold and NMS IoU

The heavy `ultralytics` dependency is OPTIONAL. If unavailable,
the module falls back to OpenCV DNN MobileNet-SSD; if that is
also unavailable, detection returns an empty list and logs a
warning so the rest of the pipeline keeps working.

Usage:
    from detection import person_detector, person_tracker
    detections = person_detector.detect(frame)
    tracked   = person_tracker.update(detections)
"""
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional

try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:
    np = None
    _NUMPY_AVAILABLE = False

from config.settings import settings
from config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class PersonDetection:
    """A detected person in a frame."""
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    confidence: float
    track_id: Optional[int] = None

    @property
    def centroid(self) -> Tuple[int, int]:
        x, y, w, h = self.bbox
        return (x + w // 2, y + h // 2)


class PersonDetector:
    """
    Detects persons in BGR frames.

    Backends (auto-selected, in order of preference):
        - 'yolov8'   : ultralytics YOLOv8 (best accuracy)
        - 'mobilenet': OpenCV DNN MobileNet-SSD
        - 'none'     : no-op (returns []), logs a warning
    """

    PERSON_CLASS_ID_COCO = 0  # YOLO/COCO 'person' class

    def __init__(self):
        self._conf_threshold = settings.detection.confidence_threshold
        self._iou_threshold = settings.detection.nms_iou_threshold
        self._model_name = settings.detection.model
        self._device = self._resolve_device(settings.detection.device)
        self._imgsz = int(getattr(settings.detection, "inference_width", 0) or 640)
        self._backend = "none"
        self._model = None
        self._init_backend()
        logger.info(
            f"PersonDetector initialized backend='{self._backend}' "
            f"model='{self._model_name}' conf={self._conf_threshold} "
            f"device='{self._device}' imgsz={self._imgsz}"
        )

    @staticmethod
    def _resolve_device(device: str):
        """Resolve the configured device string to a concrete YOLO device.

        "auto" -> CUDA GPU 0 when a CUDA-capable torch is present, else CPU.
        Any explicit value (e.g. "cpu", "cuda:0", 0) is passed through.
        """
        if device and device != "auto":
            return device
        try:
            import torch
            if torch.cuda.is_available():
                return 0  # first CUDA device
        except Exception:
            pass
        return "cpu"

    # ------------------------------------------------------------
    # Backend initialization
    # ------------------------------------------------------------
    def _init_backend(self) -> None:
        if self._try_init_yolo():
            self._backend = "yolov8"
            return
        if self._try_init_mobilenet():
            self._backend = "mobilenet"
            return
        self._backend = "none"
        logger.warning(
            "No person-detection backend available. Install 'ultralytics' "
            "(YOLOv8) or 'opencv-python' with a MobileNet-SSD weights file."
        )

    def _try_init_yolo(self) -> bool:
        try:
            from ultralytics import YOLO  # type: ignore
        except ImportError:
            return False
        try:
            # ultralytics auto-downloads e.g. 'yolov8n.pt' on first call
            weights = self._model_name if self._model_name.endswith(".pt") else f"{self._model_name}.pt"
            self._model = YOLO(weights)
            return True
        except Exception as e:
            logger.warning(f"YOLOv8 init failed: {e}")
            return False

    def _try_init_mobilenet(self) -> bool:
        try:
            import cv2
        except ImportError:
            return False
        # MobileNet-SSD weights are not bundled; expect them under data/models/.
        # If missing, skip silently and let the no-op backend take over.
        from pathlib import Path
        proto = Path(settings.project_root) / "data" / "models" / "MobileNetSSD_deploy.prototxt"
        weights = Path(settings.project_root) / "data" / "models" / "MobileNetSSD_deploy.caffemodel"
        if not (proto.exists() and weights.exists()):
            return False
        try:
            self._model = cv2.dnn.readNetFromCaffe(str(proto), str(weights))
            return True
        except Exception as e:
            logger.warning(f"MobileNet-SSD init failed: {e}")
            return False

    # ------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------
    def detect(self, frame) -> List[PersonDetection]:
        """
        Detect persons in a BGR frame.

        Args:
            frame: BGR numpy array (HxWx3)

        Returns:
            List of PersonDetection (track_id is left None; assign via tracker)
        """
        if not _NUMPY_AVAILABLE or frame is None or self._backend == "none":
            return []
        try:
            if self._backend == "yolov8":
                return self._detect_yolo(frame)
            if self._backend == "mobilenet":
                return self._detect_mobilenet(frame)
        except Exception as e:
            logger.error(f"Person detection failed: {e}", exc_info=True)
        return []

    def _detect_yolo(self, frame) -> List[PersonDetection]:
        results = self._model(
            frame,
            conf=self._conf_threshold,
            iou=self._iou_threshold,
            classes=[self.PERSON_CLASS_ID_COCO],
            device=self._device,
            imgsz=self._imgsz,
            half=(self._device != "cpu"),   # FP16 on GPU: ~2x throughput
            verbose=False,
        )
        detections: List[PersonDetection] = []
        for r in results:
            boxes = getattr(r, "boxes", None)
            if boxes is None:
                continue
            for b in boxes:
                xyxy = b.xyxy[0].cpu().numpy().astype(int)
                conf = float(b.conf[0].cpu().numpy())
                x1, y1, x2, y2 = xyxy
                detections.append(
                    PersonDetection(bbox=(int(x1), int(y1), int(x2 - x1), int(y2 - y1)), confidence=conf)
                )
        return detections

    def _detect_mobilenet(self, frame) -> List[PersonDetection]:
        import cv2
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(
            cv2.resize(frame, (300, 300)), 0.007843, (300, 300), 127.5
        )
        self._model.setInput(blob)
        outputs = self._model.forward()
        detections: List[PersonDetection] = []
        # MobileNet-SSD person class index = 15
        PERSON_CLASS_SSD = 15
        for i in range(outputs.shape[2]):
            confidence = float(outputs[0, 0, i, 2])
            class_id = int(outputs[0, 0, i, 1])
            if class_id != PERSON_CLASS_SSD or confidence < self._conf_threshold:
                continue
            box = outputs[0, 0, i, 3:7] * np.array([w, h, w, h])
            x1, y1, x2, y2 = box.astype(int)
            detections.append(
                PersonDetection(bbox=(int(x1), int(y1), int(x2 - x1), int(y2 - y1)), confidence=confidence)
            )
        return detections

    @property
    def backend(self) -> str:
        return self._backend


# ============================================================
# Centroid-IoU Tracker — produces stable track IDs across frames
# ============================================================

class CentroidTracker:
    """
    Lightweight tracker that assigns persistent track IDs to detections
    by matching centroids between consecutive frames.

    This is intentionally simple (no Kalman filter / deep features) so
    it has zero extra dependencies. It is sufficient for dwell-time
    computation in a low-traffic lobby.
    """

    def __init__(self, max_disappeared: int = 8, max_distance: float = 250.0,
                 bbox_smoothing: Optional[float] = None,
                 bbox_deadband_px: Optional[float] = None):
        self._next_id = 1
        self._objects: Dict[int, Tuple[int, int]] = {}      # id -> centroid (raw)
        self._disappeared: Dict[int, int] = {}              # id -> frames missing
        self._max_disappeared = max_disappeared
        self._max_distance = max_distance
        # Anti-jitter bbox smoothing state: id -> smoothed (x, y, w, h) as floats.
        self._bboxes: Dict[int, Tuple[float, float, float, float]] = {}
        # EMA weight on the newest frame (1.0 = no smoothing); read from config
        # but overridable for tests.
        smoothing = (bbox_smoothing if bbox_smoothing is not None
                     else getattr(settings.detection, "bbox_smoothing", 0.4))
        self._smoothing = min(1.0, max(0.0, float(smoothing)))
        deadband = (bbox_deadband_px if bbox_deadband_px is not None
                    else getattr(settings.detection, "bbox_deadband_px", 2.0))
        self._deadband = max(0.0, float(deadband))

    def update(self, detections: List[PersonDetection]) -> List[PersonDetection]:
        """
        Assign track IDs to the supplied detections (mutates them in-place
        and returns the same list).
        """
        if not detections:
            for tid in list(self._disappeared.keys()):
                self._disappeared[tid] += 1
                if self._disappeared[tid] > self._max_disappeared:
                    self._objects.pop(tid, None)
                    self._disappeared.pop(tid, None)
                    self._bboxes.pop(tid, None)
            return detections

        if not self._objects:
            for det in detections:
                det.track_id = self._register(det.centroid)
                det.bbox = self._smooth_bbox(det.track_id, det.bbox)
            return detections

        existing_ids = list(self._objects.keys())
        existing_centroids = list(self._objects.values())
        used_existing: set = set()
        used_new: set = set()

        # Greedy nearest-centroid assignment
        for ei, ec in enumerate(existing_centroids):
            best_di = -1
            best_dist = float("inf")
            for di, det in enumerate(detections):
                if di in used_new:
                    continue
                dist = ((det.centroid[0] - ec[0]) ** 2 + (det.centroid[1] - ec[1]) ** 2) ** 0.5
                if dist < best_dist and dist <= self._max_distance:
                    best_dist = dist
                    best_di = di
            if best_di >= 0:
                tid = existing_ids[ei]
                det = detections[best_di]
                det.track_id = tid
                # Store the RAW centroid for next-frame matching (must happen
                # before we replace the bbox with its smoothed version).
                self._objects[tid] = det.centroid
                self._disappeared[tid] = 0
                det.bbox = self._smooth_bbox(tid, det.bbox)
                used_existing.add(tid)
                used_new.add(best_di)

        # Register unmatched detections as new tracks
        for di, det in enumerate(detections):
            if di in used_new:
                continue
            det.track_id = self._register(det.centroid)
            det.bbox = self._smooth_bbox(det.track_id, det.bbox)

        # Increment disappeared for unmatched existing tracks
        for tid in existing_ids:
            if tid in used_existing:
                continue
            self._disappeared[tid] = self._disappeared.get(tid, 0) + 1
            if self._disappeared[tid] > self._max_disappeared:
                self._objects.pop(tid, None)
                self._disappeared.pop(tid, None)
                self._bboxes.pop(tid, None)

        return detections

    def _register(self, centroid: Tuple[int, int]) -> int:
        tid = self._next_id
        self._next_id += 1
        self._objects[tid] = centroid
        self._disappeared[tid] = 0
        return tid

    def _smooth_bbox(self, tid: int, raw_bbox: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
        """Exponential-moving-average a track's bbox to kill per-frame jitter.

        A new track is seeded with its raw box. For subsequent frames, if every
        corner moved less than the deadband the previous box is held verbatim
        (a stationary person shows zero shimmer); otherwise the box eases toward
        the new detection at the configured smoothing weight.
        """
        raw = tuple(float(v) for v in raw_bbox)
        prev = self._bboxes.get(tid)
        if prev is None or self._smoothing >= 1.0:
            self._bboxes[tid] = raw
            return tuple(int(round(v)) for v in raw)
        # Deadband — hold steady for sub-threshold movement.
        if self._deadband > 0 and max(abs(n - p) for n, p in zip(raw, prev)) < self._deadband:
            return tuple(int(round(v)) for v in prev)
        a = self._smoothing
        smoothed = tuple(a * n + (1.0 - a) * p for n, p in zip(raw, prev))
        self._bboxes[tid] = smoothed
        return tuple(int(round(v)) for v in smoothed)

    def reset(self) -> None:
        self._objects.clear()
        self._disappeared.clear()
        self._bboxes.clear()
        self._next_id = 1

    @property
    def active_count(self) -> int:
        return len(self._objects)


# Global singletons
person_detector = PersonDetector()
person_tracker = CentroidTracker()
