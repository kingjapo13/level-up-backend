import logging
import cv2
import mediapipe as mp
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)

LANDMARK = {
    "nose": 0,
    "left_shoulder": 11, "right_shoulder": 12,
    "left_elbow": 13,    "right_elbow": 14,
    "left_wrist": 15,    "right_wrist": 16,
    "left_hip": 23,      "right_hip": 24,
    "left_knee": 25,     "right_knee": 26,
    "left_ankle": 27,    "right_ankle": 28,
}

# Support both old and new mediapipe versions
try:
    mp_pose = mp.solutions.pose
    PoseLandmarker = None
    USE_LEGACY = True
    logger.info("Using legacy MediaPipe pose detection")
except AttributeError:
    USE_LEGACY = False
    logger.info("Using new MediaPipe pose detection")


def extract_landmarks_from_video(
    video_path: str,
    min_detection_confidence: float = 0.5,
    min_tracking_confidence: float = 0.5,
) -> List[Dict[str, tuple]]:
    frames_landmarks = []

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error(f"Could not open video: {video_path}")
        return frames_landmarks

    if USE_LEGACY:
        frames_landmarks = _extract_legacy(cap, min_detection_confidence, min_tracking_confidence)
    else:
        frames_landmarks = _extract_new(cap)

    cap.release()
    logger.info(f"Extracted landmarks from {len(frames_landmarks)} frames.")
    return frames_landmarks


def _extract_legacy(cap, min_detection_confidence, min_tracking_confidence):
    frames_landmarks = []
    with mp_pose.Pose(
        min_detection_confidence=min_detection_confidence,
        min_tracking_confidence=min_tracking_confidence,
    ) as pose:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb_frame)
            if results.pose_landmarks:
                frame_data = {}
                lm = results.pose_landmarks.landmark
                for name, idx in LANDMARK.items():
                    frame_data[name] = (
                        lm[idx].x,
                        lm[idx].y,
                        lm[idx].z,
                        lm[idx].visibility,
                    )
                frames_landmarks.append(frame_data)
    return frames_landmarks


def _extract_new(cap):
    frames_landmarks = []
    try:
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        base_options = mp_python.BaseOptions(
            model_asset_path='pose_landmarker.task'
        )
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            output_segmentation_masks=False
        )

        with vision.PoseLandmarker.create_from_options(options) as landmarker:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                result = landmarker.detect(mp_image)

                if result.pose_landmarks:
                    frame_data = {}
                    lm = result.pose_landmarks[0]
                    for name, idx in LANDMARK.items():
                        if idx < len(lm):
                            frame_data[name] = (
                                lm[idx].x,
                                lm[idx].y,
                                lm[idx].z,
                                getattr(lm[idx], 'visibility', 1.0),
                            )
                    frames_landmarks.append(frame_data)
    except Exception as e:
        logger.error(f"New MediaPipe extraction failed: {e}")

    return frames_landmarks


def get_landmark_point(
    frame: Dict[str, tuple],
    name: str,
    min_visibility: float = 0.5
) -> Optional[tuple]:
    data = frame.get(name)
    if data is None:
        return None
    x, y, z, visibility = data
    if visibility < min_visibility:
        return None
    return (x, y, z)