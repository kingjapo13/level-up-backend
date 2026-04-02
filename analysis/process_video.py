import os
import logging
import math
from typing import Dict, List, Optional, Any

from analysis.pose_detection import (
    extract_landmarks_from_video,
    get_landmark_point,
    extract_annotated_frames,
)
from analysis.angles import calculate_angle
from analysis.rep_counter import count_reps
from sports.registry import get_sport_analyzer

logger = logging.getLogger(__name__)

SPORT_JOINT_CONFIG = {
    "squat": {
        "joint": "right_knee",
        "proximal": "right_hip",
        "distal": "right_ankle",
        "down_threshold": 100,
        "up_threshold": 160,
    },
    "curl": {
        "joint": "right_elbow",
        "proximal": "right_shoulder",
        "distal": "right_wrist",
        "down_threshold": 60,
        "up_threshold": 150,
    },
    "basketball": {
        "joint": "right_elbow",
        "proximal": "right_shoulder",
        "distal": "right_wrist",
        "down_threshold": 70,
        "up_threshold": 160,
    },
    "golf": {
        "joint": "right_shoulder",
        "proximal": "right_hip",
        "distal": "right_elbow",
        "down_threshold": 60,
        "up_threshold": 160,
    },
    "tennis": {
        "joint": "right_elbow",
        "proximal": "right_shoulder",
        "distal": "right_wrist",
        "down_threshold": 60,
        "up_threshold": 160,
    },
    "pickleball": {
        "joint": "right_elbow",
        "proximal": "right_shoulder",
        "distal": "right_wrist",
        "down_threshold": 60,
        "up_threshold": 160,
    },
    "soccer": {
        "joint": "right_knee",
        "proximal": "right_hip",
        "distal": "right_ankle",
        "down_threshold": 80,
        "up_threshold": 160,
    },
    "baseball": {
        "joint": "right_elbow",
        "proximal": "right_shoulder",
        "distal": "right_wrist",
        "down_threshold": 50,
        "up_threshold": 155,
    },
    "volleyball": {
        "joint": "right_elbow",
        "proximal": "right_shoulder",
        "distal": "right_wrist",
        "down_threshold": 60,
        "up_threshold": 155,
    },
    "boxing": {
        "joint": "right_elbow",
        "proximal": "right_shoulder",
        "distal": "right_wrist",
        "down_threshold": 50,
        "up_threshold": 155,
    },
}


def analyze_video(
    video_path: str,
    sport: str = "squat",
    previous_score: Optional[int] = None,
) -> Dict[str, Any]:
    """Full video analysis pipeline."""
    logger.info(f"Starting analysis: sport={sport}, video={video_path}")

    # 1. Extract landmarks
    frames_landmarks = extract_landmarks_from_video(video_path)

    if not frames_landmarks:
        return {
            "error": (
                "Could not detect a person in the video. "
                "Ensure your full body is visible and well lit."
            )
        }

    logger.info(f"Got landmarks from {len(frames_landmarks)} frames")

    # 2. Get joint config
    joint_config = SPORT_JOINT_CONFIG.get(
        sport.lower(), SPORT_JOINT_CONFIG["squat"]
    )

    # 3. Extract angles
    angles = []
    for frame in frames_landmarks:
        joint = get_landmark_point(frame, joint_config["joint"])
        proximal = get_landmark_point(frame, joint_config["proximal"])
        distal = get_landmark_point(frame, joint_config["distal"])
        if joint and proximal and distal:
            angle = calculate_angle(proximal, joint, distal)
            angles.append(angle)

    # 4. Count reps
    reps = 0
    if angles:
        reps = count_reps(
            angles,
            down_threshold=joint_config["down_threshold"],
            up_threshold=joint_config["up_threshold"],
        )

    # 5. Run sport analyzer
    score = 0
    metrics = {}
    raw_tips = []

    try:
        analyzer = get_sport_analyzer(sport)
        angle_data = _extract_angle_data(frames_landmarks)
        metrics = analyzer.analyze(angle_data)
        score = analyzer.score(metrics)
        raw_tips = analyzer.feedback(metrics)
        logger.info(f"Sport analyzer returned score: {score}")
    except Exception as e:
        logger.warning(f"Sport analyzer failed: {e}")
        score = _calculate_fallback_score(angles, reps, frames_landmarks)
        logger.info(f"Fallback score: {score}")

    # 6. Format coaching tips
    coaching_tips = []
    for tip in raw_tips:
        if isinstance(tip, str):
            coaching_tips.append({"tip": tip, "priority": "medium"})
        elif isinstance(tip, dict):
            coaching_tips.append(tip)

    # 7. Detect form issues
    form_issues = _detect_form_issues(frames_landmarks, sport, angles)

    # 8. Penalize score for form issues
    issue_penalty = len(form_issues) * 8
    score = max(20, min(95, score - issue_penalty))

    # 9. Calculate improvement
    improvement = None
    if previous_score is not None:
        diff = score - previous_score
        if diff > 0:
            improvement = f"+{diff:.0f} points better than last session! 🔥"
        elif diff < 0:
            improvement = f"{abs(diff):.0f} points from last session — keep practicing!"
        else:
            improvement = "Same score as last session — consistency is key!"

    # 10. Build summary
    summary = _build_summary(sport, score, reps, form_issues)

    result = {
        "sport": sport,
        "score": round(score),
        "reps_completed": reps,
        "form_issues": form_issues,
        "coaching_tips": coaching_tips,
        "summary": summary,
        "improvement": improvement,
        "metrics": metrics,
        "annotated_frames": [],
    }

    # 11. Generate annotated frames
    try:
        annotated = extract_annotated_frames(
            video_path=video_path,
            landmarks_per_frame=frames_landmarks,
            form_issues=form_issues,
            num_frames=3,
        )
        result["annotated_frames"] = annotated
        logger.info(f"Added {len(annotated)} annotated frames")
    except Exception as e:
        logger.warning(f"Annotated frames failed: {e}", exc_info=True)

    # 12. Clean up video
    try:
        if os.path.exists(video_path):
            os.remove(video_path)
            logger.info(f"Cleaned up: {video_path}")
    except Exception as e:
        logger.warning(f"Could not clean up video: {e}")

    return result


def _extract_angle_data(frames_landmarks: List[Dict]) -> Dict[str, List[float]]:
    """Extracts angle data for all major joints."""
    angle_data = {
        "knee": [], "hip": [], "shoulder": [],
        "elbow": [], "ankle": [],
    }

    joint_configs = {
        "knee": ("right_hip", "right_knee", "right_ankle"),
        "hip": ("right_shoulder", "right_hip", "right_knee"),
        "shoulder": ("right_hip", "right_shoulder", "right_elbow"),
        "elbow": ("right_shoulder", "right_elbow", "right_wrist"),
        "ankle": ("right_knee", "right_ankle", "right_hip"),
    }

    for frame in frames_landmarks:
        for joint_name, (p1, p2, p3) in joint_configs.items():
            pt1 = get_landmark_point(frame, p1)
            pt2 = get_landmark_point(frame, p2)
            pt3 = get_landmark_point(frame, p3)
            if pt1 and pt2 and pt3:
                angle = calculate_angle(pt1, pt2, pt3)
                angle_data[joint_name].append(angle)

    return angle_data


def _detect_form_issues(
    frames_landmarks: List[Dict],
    sport: str,
    angles: List[float],
) -> List[str]:
    """Detects common form issues from landmarks."""
    issues = []
    if not frames_landmarks:
        return issues

    # Check knee cave
    if sport in ("squat", "basketball", "soccer"):
        knee_caves = 0
        for frame in frames_landmarks:
            left_knee = get_landmark_point(frame, "left_knee")
            right_knee = get_landmark_point(frame, "right_knee")
            left_ankle = get_landmark_point(frame, "left_ankle")
            right_ankle = get_landmark_point(frame, "right_ankle")
            if left_knee and right_knee and left_ankle and right_ankle:
                knee_width = abs(left_knee[0] - right_knee[0])
                ankle_width = abs(left_ankle[0] - right_ankle[0])
                if ankle_width > 0 and knee_width < ankle_width * 0.75:
                    knee_caves += 1
        if knee_caves > len(frames_landmarks) * 0.3:
            issues.append("Knee cave detected — keep knees aligned over toes")

    # Check forward lean
    forward_leans = 0
    for frame in frames_landmarks:
        shoulder = get_landmark_point(frame, "right_shoulder")
        hip = get_landmark_point(frame, "right_hip")
        if shoulder and hip:
            lean = abs(shoulder[0] - hip[0])
            if lean > 0.1:
                forward_leans += 1
    if forward_leans > len(frames_landmarks) * 0.45:
        issues.append("Excessive forward lean — keep chest up and back straight")

    # Check shoulder symmetry
    shoulder_issues = 0
    for frame in frames_landmarks:
        left_sh = get_landmark_point(frame, "left_shoulder")
        right_sh = get_landmark_point(frame, "right_shoulder")
        if left_sh and right_sh:
            height_diff = abs(left_sh[1] - right_sh[1])
            if height_diff > 0.07:
                shoulder_issues += 1
    if shoulder_issues > len(frames_landmarks) * 0.4:
        issues.append("Uneven shoulders — keep shoulders level and square")

    # Sport specific
    if sport == "squat" and angles:
        min_angle = min(angles)
        if min_angle > 110:
            issues.append("Squat depth too shallow — try to reach parallel or below")

    if sport in ("curl",) and angles:
        max_angle = max(angles)
        if max_angle < 140:
            issues.append("Not fully extending arm — extend fully at bottom of curl")

    # Check head/neck position
    head_issues = 0
    for frame in frames_landmarks:
        nose = get_landmark_point(frame, "nose")
        left_sh = get_landmark_point(frame, "left_shoulder")
        right_sh = get_landmark_point(frame, "right_shoulder")
        if nose and left_sh and right_sh:
            mid_shoulder_x = (left_sh[0] + right_sh[0]) / 2
            if abs(nose[0] - mid_shoulder_x) > 0.12:
                head_issues += 1
    if head_issues > len(frames_landmarks) * 0.4:
        issues.append("Head position off — keep head neutral and aligned with spine")

    return issues[:4]


def _calculate_fallback_score(
    angles: List[float],
    reps: int,
    frames_landmarks: List[Dict],
) -> float:
    """Improved fallback score when sport analyzer fails."""
    if not angles or not frames_landmarks:
        return 45.0

    base = 45.0

    # Reps detected
    if reps >= 5:
        base += 15
    elif reps >= 3:
        base += 10
    elif reps >= 1:
        base += 5

    # Range of motion
    angle_range = max(angles) - min(angles)
    if angle_range >= 80:
        base += 15
    elif angle_range >= 60:
        base += 10
    elif angle_range >= 40:
        base += 5

    # Consistency — standard deviation of angles
    if len(angles) > 5:
        mean = sum(angles) / len(angles)
        variance = sum((a - mean) ** 2 for a in angles) / len(angles)
        std_dev = math.sqrt(variance)
        if std_dev < 15:
            base += 10
        elif std_dev < 25:
            base += 5

    # Pose detection quality — more detected frames = better
    detection_rate = len(frames_landmarks) / max(len(frames_landmarks), 1)
    if detection_rate > 0.8:
        base += 5

    return min(base, 78.0)  # Cap fallback at 78 — perfect scores need real analysis


def _build_summary(
    sport: str,
    score: float,
    reps: int,
    form_issues: List[str],
) -> str:
    """Builds a human-readable summary."""
    sport_name = sport.capitalize()

    if score >= 85:
        quality = "excellent"
    elif score >= 70:
        quality = "good"
    elif score >= 55:
        quality = "decent"
    else:
        quality = "developing"

    summary = f"{quality.capitalize()} {sport_name} performance"

    if reps > 0:
        summary += f" with {reps} rep{'s' if reps != 1 else ''} detected"

    if not form_issues:
        summary += ". Great form overall — keep it up!"
    elif len(form_issues) == 1:
        summary += f". One area to improve: {form_issues[0].lower()[:50]}"
    else:
        summary += f". {len(form_issues)} form areas to work on."

    return summary