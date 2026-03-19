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
    Converts video to MP4 H.264 format for compatibility.
    Uses imageio/ffmpeg for conversion without system dependencies.
    """
    try:
        import imageio
        output_path = os.path.splitext(input_path)[0] + '_conv.mp4'

        # Read with imageio and write as standard mp4
        reader = imageio.get_reader(input_path)
        fps = reader.get_meta_data().get('fps', 30)
        writer = imageio.get_writer(
            output_path,
            fps=fps,
            codec='libx264',
            quality=5,
        )

        for frame in reader:
            writer.append_data(frame)

        reader.close()
        writer.close()

        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            logger.info(f"Video converted via imageio: {output_path}")
            try:
                os.remove(input_path)
            except Exception:
                pass
            return output_path
        else:
            logger.warning("imageio conversion produced invalid file")
            return input_path

    except Exception as e:
        logger.warning(f"imageio conversion failed: {e}")

        # Fall back to subprocess ffmpeg if available
        try:
            output_path = os.path.splitext(input_path)[0] + '_conv2.mp4'
            result = subprocess.run([
                'ffmpeg', '-i', input_path,
                '-vcodec', 'libx264',
                '-acodec', 'aac',
                '-movflags', '+faststart',
                '-y', output_path
            ], capture_output=True, timeout=120)

            if result.returncode == 0 and os.path.exists(output_path):
                logger.info(f"Video converted via ffmpeg subprocess")
                try:
                    os.remove(input_path)
                except Exception:
                    pass
                return output_path
        except Exception as e2:
            logger.warning(f"Subprocess ffmpeg also failed: {e2}")

        return input_path

    except FileNotFoundError:
        logger.warning("FFmpeg not found — skipping conversion")
        return input_path
    except subprocess.TimeoutExpired:
        logger.warning("FFmpeg timed out — using original")
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
    Extracts pose landmarks from every frame of a video.
    Automatically handles video format conversion.
    """
    frames_landmarks = []

    # Verify file exists and is readable
    if not os.path.exists(video_path):
        logger.error(f"Video file not found: {video_path}")
        return frames_landmarks

    file_size = os.path.getsize(video_path)
    logger.info(f"Processing video: {video_path} ({file_size} bytes)")

    # Try to open with OpenCV first
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.warning(f"OpenCV could not open video directly — trying conversion")
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

    # Clean up converted file
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

            # Skip frames for performance (process every 2nd frame)
            if frame_count % 2 != 0:
                continue

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
    """
    Returns (x, y, z) for a named