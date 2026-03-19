import os
import logging
import subprocess
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
    USE_LEGACY = True
    logger.info("Using legacy MediaPipe pose detection")
except AttributeError:
    USE_LEGACY = False
    logger.info("Using new MediaPipe pose detection")


def convert_video(input_path: str) -> str:
    """
    Converts video to MP4 H.264 format for compatibility with OpenCV on Linux.
    iPhone videos are often HEVC/H.265 which OpenCV can't read on Render.
    Returns the converted file path, or original path if conversion fails.
    """
    try:
        output_path = input_path.rsplit('.', 1)[0] + '_converted.mp4'
        result = subprocess.run([
            'ffmpeg',
            '-i', input_path,
            '-vcodec', 'libx264',
            '-acodec', 'aac',
            '-preset', 'fast',
            '-crf', '23',
            '-y',
            output_path
        ], capture_output=True, timeout=120)

        if result.returncode == 0 and os.path.exists(output_path):
            logger.info(f"Video converted successfully: {output_path}")
            try:
                os.remove(input_path)
            except Exception:
                pass
            return output_path
        else:
            logger.warning(f"FFmpeg conversion failed: {result.stderr.decode()}")
            return input_path

    except FileNotFoundError:
        logger.warning("FFmpeg not found — skipping conversion")
        return input_path
    except subprocess.TimeoutExpired:
        logger.warning("FFmpeg conversion timed out")
        return input_path
    except Exception as e:
        logger.warning(f"Video conversion error: {e}")
        return input_path


def extract_landmarks_from_video(
    video_path: str,
    min_detection_confidence: float = 0.5,
    min_tracking_confidence: float = 0.5,
) -> List[Dict[str, tuple]]:
    """
    Extracts pose landmarks from every frame of a video using MediaPipe.
    Automatically converts video format for compatibility before processing.

    Returns:
        List of frames, each a dict mapping landmark name -> (x, y, z, visibility).
        Returns empty list if video cannot be processed.
    """
    # Convert video format first for iPhone/HEVC compatibility
    video_path = convert_video(video_path)

    frames_landmarks = []

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error(f"Could not open video: {video_path}")
        return frames_landmarks

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    logger.info(f"Video: {total_frames} frames at {fps:.1f} FPS")

    if USE_LEGACY:
        frames_landmarks = _extract_legacy(
            cap, min_detection_confidence, min_tracking_confidence
        )
    else:
        frames_landmarks = _extract_new(cap)

    cap.release()

    # Clean up converted file
    if '_converted' in video_path:
        try:
            os.remove(video_path)
        except Exception:
            pass

    logger.info(f"Extracted landmarks from {len(frames_landmarks)} frames.")
    return frames_landmarks


def _extract_legacy(cap, min_detection_confidence, min_tracking_confidence):
    """MediaPipe legacy API (0.10.x)"""
    frames_landmarks = []

    with mp_pose.Pose(
        min_detection_confidence=min_detection_confidence,
        min_tracking_confidence=min_tracking_confidence,
        model_complexity=1,
    ) as pose:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # Resize large frames for faster processing
            h, w = frame.shape[:2]
            if w > 1280:
                scale = 1280 / w
                frame = cv2.resize(frame, (1280, int(h * scale)))

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb_frame.flags.writeable = False
            results = pose.process(rgb_frame)
            rgb_frame.flags.writeable = True

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
    """MediaPipe new Tasks API"""
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
                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=rgb_frame
                )
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
    """
    Returns (x, y, z) for a named landmark if visible enough, else None.
    """
    data = frame.get(name)
    if data is None:
        return None
    x, y, z, visibility = data
    if visibility < min_visibility:
        return None
    return (x, y, z)