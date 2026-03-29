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
    logger.info("MediaPipe pose loaded successfully")
except Exception as e:
    mp_pose = None
    logger.error(f"MediaPipe failed to load: {e}")


def fix_rotation(frame):
    """Fix iPhone video rotation."""
    h, w = frame.shape[:2]
    if h > w:
        frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    return frame


def convert_video(input_path: str) -> str:
    """
    Converts and compresses video for compatibility.
    Uses imageio_ffmpeg bundled ffmpeg.
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
                    f"({100 - int(out_size / in_size * 100)}% reduction)"
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
    Always uses legacy MediaPipe API.
    """
    frames_landmarks = []

    if mp_pose is None:
        logger.error("MediaPipe not available")
        return frames_landmarks

    if not os.path.exists(video_path):
        logger.error(f"Video file not found: {video_path}")
        return frames_landmarks

    file_size = os.path.getsize(video_path)
    logger.info(f"Processing video: {video_path} ({file_size} bytes)")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.warning("OpenCV could not open video - trying conversion")
        cap.release()
        video_path = convert_video(video_path)
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"Could not open video after conversion: {video_path}")
            return frames_landmarks

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    logger.info(f"Video opened: {total_frames} frames at {fps:.1f} FPS")

    frames_landmarks = _extract_legacy(
        cap, min_detection_confidence, min_tracking_confidence
    )

    cap.release()

    # DON'T delete the video here — we need it for annotated frames
    # Cleanup happens in process_video.py after annotation is complete

    logger.info(f"Extracted landmarks from {len(frames_landmarks)} frames.")
    return frames_landmarks


def _extract_legacy(cap, min_detection_confidence, min_tracking_confidence):
    """MediaPipe legacy API."""
    frames_landmarks = []

    try:
        with mp_pose.Pose(
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            model_complexity=1,
        ) as pose:
            frame_count = 0
            detected_count = 0

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                frame_count += 1
                if frame_count % 2 != 0:
                    continue

                frame = fix_rotation(frame)

                h, w = frame.shape[:2]
                if w > 640:
                    scale = 640 / w
                    frame = cv2.resize(frame, (640, int(h * scale)))

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                rgb_frame.flags.writeable = False
                results = pose.process(rgb_frame)
                rgb_frame.flags.writeable = True

                if results.pose_landmarks:
                    detected_count += 1
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

            logger.info(
                f"Processed {frame_count} frames, "
                f"detected pose in {detected_count} frames"
            )

    except Exception as e:
        logger.error(f"Legacy MediaPipe extraction failed: {e}", exc_info=True)

    return frames_landmarks


def get_landmark_point(
    frame: Dict[str, tuple],
    name: str,
    min_visibility: float = 0.5,
) -> Optional[tuple]:
    """Returns (x, y, z) for a named landmark if visible enough."""
    data = frame.get(name)
    if data is None:
        return None
    x, y, z, visibility = data
    if visibility < min_visibility:
        return None
    return (x, y, z)

def extract_annotated_frames(
    video_path: str,
    landmarks_per_frame: List[Dict[str, tuple]],
    form_issues: List[str],
    num_frames: int = 3,
) -> List[str]:
    logger.info(f"Starting annotation: video={video_path}, landmarks={len(landmarks_per_frame)}, issues={form_issues}")
    import base64
    ...

    if not landmarks_per_frame:
        logger.warning("No landmarks available for annotation")
        return []

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.warning(f"Cannot open video for annotation: {video_path}")
        return []

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames < 1:
        cap.release()
        return []

    num_frames = min(num_frames, total_frames)

    # Pick evenly spaced frames
    frame_indices = [
        int(total_frames * i / (num_frames + 1))
        for i in range(1, num_frames + 1)
    ]

    issue_joints = _get_issue_joints(form_issues)
    annotated = []

    for frame_idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            continue

        frame = fix_rotation(frame)

        h, w = frame.shape[:2]
        if w > 640:
            scale = 640 / w
            frame = cv2.resize(frame, (640, int(h * scale)))
        h, w = frame.shape[:2]

        # Get nearest landmark frame
        lm_idx = min(
            int(frame_idx / max(total_frames, 1) * len(landmarks_per_frame)),
            len(landmarks_per_frame) - 1
        )
        landmarks = landmarks_per_frame[lm_idx] if landmarks_per_frame else {}

        if landmarks:
            frame = _draw_skeleton(frame, landmarks, issue_joints, w, h)

        label = _get_frame_label(frame_idx, total_frames, form_issues)
        frame = _add_text_overlay(frame, label)

        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        annotated.append(img_base64)

    cap.release()
    logger.info(f"Generated {len(annotated)} annotated frames")
    return annotated


def _get_issue_joints(form_issues: List[str]) -> set:
    """Maps form issue text to joint names."""
    issue_map = {
        'knee': {'left_knee', 'right_knee'},
        'hip': {'left_hip', 'right_hip'},
        'shoulder': {'left_shoulder', 'right_shoulder'},
        'elbow': {'left_elbow', 'right_elbow'},
        'wrist': {'left_wrist', 'right_wrist'},
        'ankle': {'left_ankle', 'right_ankle'},
        'back': {'left_hip', 'right_hip', 'left_shoulder', 'right_shoulder'},
        'spine': {'left_hip', 'right_hip', 'left_shoulder', 'right_shoulder'},
        'posture': {'left_shoulder', 'right_shoulder', 'left_hip', 'right_hip'},
        'balance': {'left_ankle', 'right_ankle', 'left_knee', 'right_knee'},
        'arm': {'left_elbow', 'right_elbow', 'left_wrist', 'right_wrist'},
        'leg': {'left_knee', 'right_knee', 'left_ankle', 'right_ankle'},
        'foot': {'left_ankle', 'right_ankle'},
        'core': {'left_hip', 'right_hip', 'left_shoulder', 'right_shoulder'},
        'chest': {'left_shoulder', 'right_shoulder'},
        'head': {'nose'},
        'neck': {'nose', 'left_shoulder', 'right_shoulder'},
    }
    issue_joints = set()
    for issue in form_issues:
        issue_lower = issue.lower()
        for keyword, joints in issue_map.items():
            if keyword in issue_lower:
                issue_joints.update(joints)
    return issue_joints


def _draw_skeleton(frame, landmarks, issue_joints, w, h):
    """Draws color-coded skeleton on frame."""
    GREEN = (0, 255, 136)
    RED = (0, 80, 255)
    WHITE = (255, 255, 255)
    DARK = (20, 20, 20)

    connections = [
        ('left_shoulder', 'right_shoulder'),
        ('left_shoulder', 'left_elbow'),
        ('left_elbow', 'left_wrist'),
        ('right_shoulder', 'right_elbow'),
        ('right_elbow', 'right_wrist'),
        ('left_shoulder', 'left_hip'),
        ('right_shoulder', 'right_hip'),
        ('left_hip', 'right_hip'),
        ('left_hip', 'left_knee'),
        ('left_knee', 'left_ankle'),
        ('right_hip', 'right_knee'),
        ('right_knee', 'right_ankle'),
    ]

    def get_pixel(name):
        lm = landmarks.get(name)
        if lm and lm[3] > 0.3:
            return (int(lm[0] * w), int(lm[1] * h))
        return None

    def joint_color(name):
        return RED if name in issue_joints else GREEN

    # Draw connections
    for start, end in connections:
        p1 = get_pixel(start)
        p2 = get_pixel(end)
        if p1 and p2:
            is_issue = start in issue_joints or end in issue_joints
            color = RED if is_issue else GREEN
            cv2.line(frame, p1, p2, DARK, 5, cv2.LINE_AA)
            cv2.line(frame, p1, p2, color, 2, cv2.LINE_AA)

    # Draw joint dots
    for name in LANDMARK.keys():
        pt = get_pixel(name)
        if pt:
            color = joint_color(name)
            cv2.circle(frame, pt, 7, DARK, -1, cv2.LINE_AA)
            cv2.circle(frame, pt, 6, color, -1, cv2.LINE_AA)
            cv2.circle(frame, pt, 7, WHITE, 1, cv2.LINE_AA)

    return frame


def _add_text_overlay(frame, text: str):
    """Adds a text label at the bottom of the frame."""
    if not text:
        return frame

    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, h - 52), (w, h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)

    font = cv2.FONT_HERSHEY_SIMPLEX
    max_chars = int(w / 10)
    display_text = text[:max_chars] + '...' if len(text) > max_chars else text
    cv2.putText(
        frame, display_text, (8, h - 18),
        font, 0.48, (255, 255, 255), 1, cv2.LINE_AA
    )

    return frame


def _get_frame_label(frame_idx, total_frames, form_issues) -> str:
    """Returns a contextual label for each frame position."""
    position = frame_idx / max(total_frames, 1)
    if position < 0.35:
        position_label = "Start"
    elif position < 0.65:
        position_label = "Mid movement"
    else:
        position_label = "End"

    if form_issues:
        issue_short = form_issues[0][:35]
        return f"{position_label} — Fix: {issue_short}"
    return f"{position_label} — Good form!"