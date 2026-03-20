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

try:
    mp_pose = mp.solutions.pose
    USE_LEGACY = True
    logger.info("Using legacy MediaPipe pose detection")
except AttributeError:
    USE_LEGACY = False
    logger.info("Using new MediaPipe pose detection")


def convert_video(input_path: str) -> str:
    """
    Converts and compresses video for compatibility and memory efficiency.
    Shrinks to 640px wide, 15fps, max 30 seconds.
    Uses imageio_ffmpeg bundled ffmpeg - no system install needed.
    """
    try:
        import imageio_ffmpeg
        output_path = os.path.splitext(input_path)[0] + '_conv.mp4'
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

        cmd = [
            ffmpeg_path,
            '-i', input_path,
            '-vcodec', 'libx264',
            '-acodec', 'aac',
            '-preset', 'ultrafast',
            '-crf', '35',
            '-vf', 'scale=640:-2',
            '-r', '15',
            '-t', '30',
            '-movflags', '+faststart',
            '-max_muxing_queue_size', '1024',
            '-y',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=60)

        if result.returncode == 0 and os.path.exists(output_path):
            out_size = os.path.getsize(output_path)
            if out_size > 1000:
                in_size = os.path.getsize(input_path)
                logger.info(
                    f"Video compressed: {in_size} -> {out_size} bytes "
                    f"({100 - int(out_size/in_size*100)}% reduction)"
                )
                try:
                    os.remove(input_path)
                except Exception:
                    pass
                return output_path
            else:
                logger.warning("Converted file too small - using original")
                return input_path
        else:
            stderr = result.stderr.decode('utf-8', errors='ignore')
            logger.warning(f"FFmpeg failed (code {result.returncode}): {stderr[-300:]}")
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
    Extracts pose landmarks from every other frame of a video.
    Handles format conversion automatically.
    """
    frames_landmarks = []

    if not os.path.exists(video_path):
        logger.error(f"Video file not found: {video_path}")
        return frames_landmarks

    file_size = os.path.getsize(video_path)
    logger.info(f"Processing video: {video_path} ({file_size} bytes)")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.warning("OpenCV could not open video directly - trying conversion")
        cap.release()
        video_path = convert_video(video_path)
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"Could not open video after conversion: {video_path}")
            return frames_landmarks

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    logger.info(f"Video opened: {total_frames} frames at {fps:.1f} FPS")

    if USE_LEGACY:
        frames_landmarks = _extract_legacy(
            cap, min_detection_confidence, min_tracking_confidence
        )
    else:
        frames_landmarks = _extract_new(cap)

    cap.release()

    if '_conv' in video_path:
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
        frame_count = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1
            if frame_count % 2 != 0:
                continue

            h, w = frame.shape[:2]
            if w > 640:
                scale = 640 / w
                frame = cv2.resize(frame, (640, int(h * scale)))

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
            output_segmentation_masks=False,
        )

        frame_count = 0
        with vision.PoseLandmarker.create_from_options(options) as landmarker:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                frame_count += 1
                if frame_count % 2 != 0:
                    continue

                h, w = frame.shape[:2]
                if w > 640:
                    scale = 640 / w
                    frame = cv2.resize(frame, (640, int(h * scale)))

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=rgb_frame,
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
    min_visibility: float = 0.5,
) -> Optional[tuple]:
    data = frame.get(name)
    if data is None:
        return None
    x, y, z, visibility = data
    if visibility < min_visibility:
        return None
    return (x, y, z)