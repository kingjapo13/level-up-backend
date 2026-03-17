import logging
from typing import Optional

from analysis.pose_detection import extract_landmarks_from_video, get_landmark_point
from analysis.angles import calculate_angle
from analysis.rep_counter import count_reps
from analysis.bad_form import detect_bad_form
from analysis.scoring import calculate_score
from analysis.feedback import generate_feedback

logger = logging.getLogger(__name__)

SPORT_JOINT_CONFIG = {
    "basketball": {
        "joint": "right_elbow",
        "proximal": "right_shoulder",
        "distal": "right_wrist",
        "down_threshold": 70,
        "up_threshold": 155,
    },
    "golf": {
        "joint": "left_elbow",
        "proximal": "left_shoulder",
        "distal": "left_wrist",
        "down_threshold": 80,
        "up_threshold": 160,
    },
    "squat": {
        "joint": "left_knee",
        "proximal": "left_hip",
        "distal": "left_ankle",
        "down_threshold": 90,
        "up_threshold": 160,
    },
    "curl": {
        "joint": "right_elbow",
        "proximal": "right_shoulder",
        "distal": "right_wrist",
        "down_threshold": 50,
        "up_threshold": 150,
    },
    "soccer": {
        "joint": "left_knee",
        "proximal": "left_hip",
        "distal": "left_ankle",
        "down_threshold": 70,
        "up_threshold": 160,
    },
    "pickleball": {
        "joint": "right_elbow",
        "proximal": "right_shoulder",
        "distal": "right_wrist",
        "down_threshold": 70,
        "up_threshold": 155,
    },
    "tennis": {
        "joint": "right_elbow",
        "proximal": "right_shoulder",
        "distal": "right_wrist",
        "down_threshold": 60,
        "up_threshold": 155,
    },
    "baseball": {
        "joint": "right_elbow",
        "proximal": "right_shoulder",
        "distal": "right_wrist",
        "down_threshold": 60,
        "up_threshold": 155,
    },
}

DEFAULT_SPORT = "squat"


def analyze_video(
    video_path: str,
    sport: Optional[str] = None,
    previous_score: Optional[int] = None,
) -> dict:
    sport_key = (sport or DEFAULT_SPORT).lower()
    config = SPORT_JOINT_CONFIG.get(sport_key, SPORT_JOINT_CONFIG[DEFAULT_SPORT])

    logger.info(f"Starting analysis: sport={sport_key}, video={video_path}")

    frames = extract_landmarks_from_video(video_path)
    if not frames:
        return {
            "error": "Could not detect a person in the video. "
                     "Ensure the full body is visible and well-lit."
        }

    angles = []
    for frame in frames:
        proximal = get_landmark_point(frame, config["proximal"])
        joint = get_landmark_point(frame, config["joint"])
        distal = get_landmark_point(frame, config["distal"])

        if proximal and joint and distal:
            angle = calculate_angle(proximal, joint, distal)
            angles.append(angle)
        else:
            angles.append(None)

    valid_angles = [a for a in angles if a is not None]

    if not valid_angles:
        return {
            "error": "Could not measure joint angles. "
                     "Make sure the relevant joints are visible throughout the video."
        }

    reps = count_reps(
        valid_angles,
        down_threshold=config["down_threshold"],
        up_threshold=config["up_threshold"],
    )

    bad_form_issues = detect_bad_form(valid_angles)
    score = calculate_score(reps, bad_form_issues, angle_list=valid_angles)
    feedback = generate_feedback(
        reps=reps,
        score=score,
        bad_form_issues=bad_form_issues,
        sport=sport_key,
        previous_score=previous_score,
    )

    return feedback