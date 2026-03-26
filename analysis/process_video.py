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
from analysis.scoring import calculate_score
from analysis.feedback import generate_feedback
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
    """
    Full video analysis pipeline:
    1. Extract pose landmarks
    2. Count reps
    3. Calculate joint angles
    4. Score performance
    5. Generate feedback
    6. Create annotated frames
    """
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

    # 2. Get joint config for this sport
    joint_config = SPORT_JOINT_CONFIG.get(sport.lower(), SPORT_JOINT_CONFIG["squat"])

    # 3. Extract angles for rep counting
    angles = []
    for frame in frames_landmarks:
        joint = get_landmark_point(frame, joint_config["joint"])
        proximal = get_landmark_point(frame, joint_config["proximal"])
        distal = get_landmark_point(frame, joint_config["distal"])

        if joint and proximal and distal:
            angle = calculate_angle(proximal, joint, distal)
            angles.append(angle)

    # 4. Count reps
    reps = count_reps(
        angles,
        down_threshold=joint_config["down_threshold"],
        up_threshold=joint_config["up_threshold"],
    ) if angles else 0

    # 5. Run sport-specific analysis
    try:
        analyzer = get_sport_analyzer(sport)
        angle_data = _extract_angle_data(frames_landmarks)
        metrics = analyzer.analyze(angle_data)
        score = analyzer.score(metrics)
        raw_tips = analyzer.feedback(metrics)
    except Exception as e:
        logger.warning(f"Sport analyzer failed: {e}")
        score = _calculate_fallback_score(angles, reps)
        metrics = {}
        raw_tips = []

    # 6. Format coaching tips
    coaching_tips = []
    for tip in raw_tips:
        if isinstance(tip, str):
            coaching_tips.append({"tip": tip, "priority": "medium"})
        elif isinstance(tip, dict):
            coaching_tips.append(tip)

    # 7. Detect form issues
    form_issues = _detect_form_issues(frames_landmarks, sport, angles)

    # 8. Calculate final score
    final_score = min(100, max(0, score))

    # 9. Calculate improvement
    improvement = None
    if previous_score is not None:
        diff = final_score - previous_score
        if diff > 0:
            improvement = f"+{diff:.0f} points better than last session! 🔥"
        elif diff < 0:
            improvement = f"{diff:.0f} points from last session — keep practicing!"
        else:
            improvement = "Same score as last session — consistency is key!"

    # 10. Build summary
    summary = _build_summary(sport, final_score, reps, form_issues)

    result = {
        "sport": sport,
        "score": final_score,
        "reps_completed": reps,
        "form_issues": form_issues,
        "coaching_tips": coaching_tips,
        "summary": summary,
        "improvement": improvement,
        "metrics": metrics,
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
        logger.info(f"Added {len(annotated)} annotated frames to result")
    except Exception as e:
        logger.warning(f"Annotated frames failed: {e}")
        result["annotated_frames"] = []

    return result


def _extract_angle_data(frames_landmarks: List[Dict]) -> Dict[str, List[float]]:
    """Extracts angle data for all major joints across all frames."""
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
    """Detects common form issues based on landmarks."""
    issues = []

    if not frames_landmarks:
        return issues

    # Check knee cave (knees caving inward)
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
                if ankle_width > 0 and knee_width < ankle_width * 0.7:
                    knee_caves += 1
        if knee_caves > len(frames_landmarks) * 0.3:
            issues.append("Knee cave detected — keep knees aligned over toes")

    # Check forward lean
    forward_leans = 0
    for frame in frames_landmarks:
        shoulder = get_landmark_point(frame, "right_shoulder")
        hip = get_landmark_point(frame, "right_hip")
        if shoulder and hip:
            lean = shoulder[0] - hip[0]
            if abs(lean) > 0.08:
                forward_leans += 1
    if forward_leans > len(frames_landmarks) * 0.4:
        issues.append("Excessive forward lean — keep chest up and back straight")

    # Check shoulder symmetry
    shoulder_issues = 0
    for frame in frames_landmarks:
        left_sh = get_landmark_point(frame, "left_shoulder")
        right_sh = get_landmark_point(frame, "right_shoulder")
        if left_sh and right_sh:
            height_diff = abs(left_sh[1] - right_sh[1])
            if height_diff > 0.06:
                shoulder_issues += 1
    if shoulder_issues > len(frames_landmarks) * 0.4:
        issues.append("Uneven shoulders — keep shoulders level and square")

    # Check depth for squats
    if sport == "squat" and angles:
        min_angle = min(angles)
        if min_angle > 100:
            issues.append("Squat depth too shallow — try to reach parallel or below")

    # Check elbow position for curls
    if sport == "curl" and angles:
        max_angle = max(angles)
        if max_angle < 140:
            issues.append("Not fully extending arm — extend fully at bottom of curl")

    return issues[:4]


def _calculate_fallback_score(angles: List[float], reps: int) -> float:
    """Simple fallback score when sport analyzer fails."""
    if not angles:
        return 50.0
    base = 60.0
    if reps > 0:
        base += min(reps * 3, 20)
    angle_range = max(angles) - min(angles) if angles else 0
    if angle_range > 60:
        base += 10
    elif angle_range > 30:
        base += 5
    return min(base, 85.0)


def _build_summary(
    sport: str,
    score: float,
    reps: int,
    form_issues: List[str],
) -> str:
    """Builds a human-readable summary of the analysis."""
    sport_name = sport.charAt(0).upper() + sport[1:] if hasattr(sport, 'charAt') else sport.capitalize()

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
        summary += f". One area to improve: {form_issues[0].lower()}"
    else:
        summary += f". {len(form_issues)} form areas to work on."

    return summary