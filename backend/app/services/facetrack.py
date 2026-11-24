"""Subject-aware framing.

Uses OpenCV's Haar cascade face detector to sample frames inside the selected
range and compute a stable crop anchor around the dominant face. This is a
static smart crop for the clip (not frame-by-frame re-tracking), and users can
override the anchor manually. If OpenCV is unavailable the endpoint reports
that clearly instead of guessing.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("fireclip.facetrack")


class FaceTrackingUnavailable(RuntimeError):
    pass


@dataclass
class FocusResult:
    focus_x: float
    focus_y: float
    faces_detected: int
    samples: int
    method: str
    camera_x: float = 0.6
    camera_y: float = 0.5
    camera_w: float = 0.4
    camera_h: float = 0.5


def available() -> bool:
    try:
        import cv2  # noqa: F401

        return True
    except Exception:
        return False


def detect_focus(
    video_path: Path,
    *,
    clip_start_ms: int,
    clip_end_ms: int,
    target_width: int,
    target_height: int,
    samples: int = 9,
) -> FocusResult:
    try:
        import cv2
    except Exception as exc:  # pragma: no cover - optional dependency
        raise FaceTrackingUnavailable(
            "Face detection requires opencv-python-headless. It is included in the Docker image."
        ) from exc

    cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    cascade = cv2.CascadeClassifier(str(cascade_path))
    if cascade.empty():
        raise FaceTrackingUnavailable("OpenCV face model could not be loaded")

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise FaceTrackingUnavailable("Could not open the video for face detection")

    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration_ms = (frame_count / fps * 1000) if frame_count else max(clip_end_ms, 1)
    start = max(0, clip_start_ms)
    end = min(clip_end_ms, duration_ms) if duration_ms else clip_end_ms
    span = max(1000, end - start)

    detections: list[tuple[float, float, float, float, float]] = []  # cx, cy, area, w, h (normalized)
    frame_width = capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0
    frame_height = capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0
    try:
        for index in range(samples):
            timestamp = start + span * (index + 0.5) / samples
            capture.set(cv2.CAP_PROP_POS_MSEC, timestamp)
            ok, frame = capture.read()
            if not ok or frame is None:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, scaleFactor=1.12, minNeighbors=6, minSize=(48, 48))
            if len(faces) == 0:
                continue
            x, y, w, h = max(faces, key=lambda box: int(box[2]) * int(box[3]))
            frame_width = frame.shape[1]
            frame_height = frame.shape[0]
            detections.append(
                (
                    (x + w / 2) / frame_width,
                    (y + h * 0.45) / frame_height,
                    (w * h) / (frame_width * frame_height),
                    w / frame_width,
                    h / frame_height,
                )
            )
    finally:
        capture.release()

    if not detections or not frame_width or not frame_height:
        raise FaceTrackingUnavailable(
            "No face was detected in this range. Pick the framing manually with the focus controls."
        )

    # Median resists one-off false positives; area weighting prefers the closest subject.
    weights = [max(0.01, item[2]) for item in detections]
    total = sum(weights)
    cx = sum(item[0] * weight for item, weight in zip(detections, weights)) / total
    cy = sum(item[1] * weight for item, weight in zip(detections, weights)) / total
    face_w = sum(item[3] * weight for item, weight in zip(detections, weights)) / total
    face_h = sum(item[4] * weight for item, weight in zip(detections, weights)) / total
    camera_w = min(0.9, max(0.24, face_w * 2.8))
    camera_h = min(0.9, max(0.3, face_h * 3.2))
    camera_x = min(1.0 - camera_w, max(0.0, cx - camera_w / 2))
    camera_y = min(1.0 - camera_h, max(0.0, cy - camera_h * 0.35))

    source_ratio = frame_width / frame_height
    target_ratio = target_width / target_height
    if source_ratio > target_ratio:
        crop_width = frame_height * target_ratio
        crop_height = frame_height
    else:
        crop_width = frame_width
        crop_height = frame_width / target_ratio
    max_offset_x = max(1.0, frame_width - crop_width)
    max_offset_y = max(1.0, frame_height - crop_height)
    desired_x = cx * frame_width - crop_width / 2
    desired_y = cy * frame_height - crop_height / 2
    focus_x = min(1.0, max(0.0, desired_x / max_offset_x))
    focus_y = min(1.0, max(0.0, desired_y / max_offset_y))

    return FocusResult(
        focus_x=round(focus_x, 4),
        focus_y=round(focus_y, 4),
        faces_detected=len(detections),
        samples=samples,
        method="haar_cascade_dominant_face",
        camera_x=round(camera_x, 4),
        camera_y=round(camera_y, 4),
        camera_w=round(camera_w, 4),
        camera_h=round(camera_h, 4),
    )
