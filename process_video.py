#!/usr/bin/env python3
"""
Full process_video implementation.

- Runs MediaPipe Pose over input video
- Computes per-frame metrics (wrist speed, elbow angle, trunk twist, knee angle, hip shift)
- Detects swing events (wrist speed threshold)
- Optionally uses classifier (StrokeClassifier from classifier.py) if model_dir is provided
- Produces an annotated MP4 and an analysis JSON with per-swing metrics and feedback

Usage (called by main.py):
    analyze_video(input_path, output_dir="results/jobid", model_dir=None, dominant_hand="right")
"""
import os
import json
import math
import time
from typing import Dict, Any, List, Optional

import cv2
import numpy as np
import mediapipe as mp

mp_pose = mp.solutions.pose

# helper math functions
def angle_between(a, b, c):
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)
    c = np.array(c, dtype=float)
    ba = a - b
    bc = c - b
    if np.linalg.norm(ba) == 0 or np.linalg.norm(bc) == 0:
        return 0.0
    cosang = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
    cosang = np.clip(cosang, -1.0, 1.0)
    ang = math.degrees(math.acos(cosang))
    return ang

def euclidean(a, b):
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)
    return float(np.linalg.norm(a - b))

def normalized_to_px(nx, ny, w, h):
    return int(nx * w), int(ny * h)

def get_flat_landmarks_dict(norm_landmarks: Dict[str, tuple]) -> Optional[np.ndarray]:
    """
    Return flattened normalized landmarks vector using MediaPipe PoseLandmark ordering.
    Vector shape = (num_landmarks * 4,)
    """
    if not norm_landmarks:
        return None
    flat = []
    for lm_enum in mp_pose.PoseLandmark:
        key = lm_enum.name
        if key in norm_landmarks and norm_landmarks[key] is not None:
            x, y, z, vis = norm_landmarks[key]
            flat.extend([float(x), float(y), float(z), float(vis)])
        else:
            flat.extend([0.0, 0.0, 0.0, 0.0])
    return np.array(flat, dtype=np.float32)

def landmarks_from_results(results) -> Optional[Dict[str, tuple]]:
    """
    Convert mediapipe results.pose_landmarks to a dict name -> (x,y,z,visibility) normalized
    """
    if not results or not results.pose_landmarks:
        return None
    lm_dict = {}
    for idx, lm in enumerate(results.pose_landmarks.landmark):
        name = mp_pose.PoseLandmark(idx).name
        lm_dict[name] = (lm.x, lm.y, lm.z, lm.visibility)
    return lm_dict

def draw_landmarks_on_frame(frame, norm_landmarks):
    if not norm_landmarks:
        return
    h, w = frame.shape[:2]
    mp_draw = mp.solutions.drawing_utils
    # Build normalized list for mp drawing
    lm_list = []
    from mediapipe.framework.formats import landmark_pb2
    for i in range(len(mp_pose.PoseLandmark)):
        name = mp_pose.PoseLandmark(i).name
        if norm_landmarks and name in norm_landmarks:
            x, y, z, vis = norm_landmarks[name]
        else:
            x, y, z, vis = 0.0, 0.0, 0.0, 0.0
        lm = landmark_pb2.NormalizedLandmark(x=float(x), y=float(y), z=float(z), visibility=float(vis))
        lm_list.append(lm)
    mp_draw.draw_landmarks(
        frame,
        landmark_pb2.NormalizedLandmarkList(landmark=lm_list),
        mp_pose.POSE_CONNECTIONS,
        mp_draw.DrawingSpec(color=(0,255,0), thickness=2, circle_radius=2),
        mp_draw.DrawingSpec(color=(200,200,0), thickness=2)
    )

def simple_coach_feedback(metrics: Dict[str, Any]) -> List[str]:
    """
    Rule-based feedback based on per-swing metrics.
    """
    texts = []
    el = metrics.get("elbow_angle_deg")
    twist = metrics.get("trunk_twist_deg")
    knee = metrics.get("knee_angle_deg")
    hip_dx = metrics.get("hip_vs_ankle_dx")
    if el is not None:
        if el > 160:
            texts.append("Good: strong elbow extension")
        elif el > 120:
            texts.append("OK: partial extension — extend more at impact")
        else:
            texts.append("Fix: elbow too bent at impact")
    if twist is not None:
        if twist > 15:
            texts.append("Good: torso rotation present")
        else:
            texts.append("Fix: increase torso rotation")
    if knee is not None:
        if knee < 150:
            texts.append("Good: knee bend observed")
        else:
            texts.append("Fix: more knee bend for lower COG")
    if hip_dx is not None:
        if abs(hip_dx) > 20:
            texts.append("Good: weight transfer detected")
        else:
            texts.append("Fix: transfer weight onto front foot")
    return texts or ["No strong feedback available"]

def analyze_video(input_path: str, output_dir: str, model_dir: Optional[str] = None, dominant_hand: str = "right", swing_speed_thresh: Optional[float] = None) -> Dict[str, Any]:
    """
    Main analysis function.
    Returns a dict with annotated_video and analysis_json (local paths).
    """
    os.makedirs(output_dir, exist_ok=True)
    annotated_path = os.path.join(output_dir, "annotated.mp4")
    analysis_json_path = os.path.join(output_dir, "analysis.json")

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise RuntimeError("Cannot open video: " + input_path)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    # default threshold heuristics: scale with image size if not provided
    if swing_speed_thresh is None:
        swing_speed_thresh = max(40.0, w * 0.06)  # px/frame heuristic

    # optional classifier
    clf = None
    try:
        if model_dir:
            from classifier import StrokeClassifier
            clf = StrokeClassifier(model_dir)
    except Exception:
        clf = None

    pose = mp_pose.Pose(static_image_mode=False, model_complexity=1, min_detection_confidence=0.5, min_tracking_confidence=0.5)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(annotated_path, fourcc, fps, (w, h))

    seq_len = 24
    seq_buffer = []
    last_wrist_px = None
    last_swing_frame = -9999
    min_gap_frames = int(fps * 0.4)  # require gap between swings (0.4s)
    frame_idx = 0

    swings = []
    start_time = time.time()
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(img_rgb)
        norm_lms = landmarks_from_results(results)
        flat = get_flat_landmarks_dict(norm_lms)
        seq_buffer.append(flat)
        if len(seq_buffer) > seq_len:
            seq_buffer.pop(0)

        # compute pixel-based landmarks (for wrist speed)
        wrist_name = "RIGHT_WRIST" if dominant_hand == "right" else "LEFT_WRIST"
        wrist_px = None
        if norm_lms and wrist_name in norm_lms:
            nx, ny, nz, vis = norm_lms[wrist_name]
            wrist_px = (int(nx * w), int(ny * h)) if nx is not None else None

        # wrist speed
        wrist_speed = 0.0
        if last_wrist_px is not None and wrist_px is not None:
            wrist_speed = euclidean(last_wrist_px, wrist_px)
        last_wrist_px = wrist_px

        # compute per-frame quick metrics (pixel-level)
        metrics = {}
        # elbow angle
        elbow_name = "RIGHT_ELBOW" if dominant_hand == "right" else "LEFT_ELBOW"
        shoulder_name = "RIGHT_SHOULDER" if dominant_hand == "right" else "LEFT_SHOULDER"
        hip_name = "RIGHT_HIP" if dominant_hand == "right" else "LEFT_HIP"
        knee_name = "RIGHT_KNEE" if dominant_hand == "right" else "LEFT_KNEE"
        ankle_name = "RIGHT_ANKLE" if dominant_hand == "right" else "LEFT_ANKLE"

        def get_px(name):
            if not norm_lms or name not in norm_lms:
                return None
            nx, ny, nz, vis = norm_lms[name]
            return (int(nx * w), int(ny * h))

        a = get_px(shoulder_name); b = get_px(elbow_name); c = get_px(wrist_name)
        if a and b and c:
            metrics["elbow_angle_deg"] = angle_between(a, b, c)
        # trunk twist: difference between shoulders vector angle and hips vector angle
        if norm_lms and "LEFT_SHOULDER" in norm_lms and "RIGHT_SHOULDER" in norm_lms and "LEFT_HIP" in norm_lms and "RIGHT_HIP" in norm_lms:
            sL = np.array(get_px("LEFT_SHOULDER")); sR = np.array(get_px("RIGHT_SHOULDER"))
            hL = np.array(get_px("LEFT_HIP")); hR = np.array(get_px("RIGHT_HIP"))
            shoulders_vec = sR - sL
            hips_vec = hR - hL
            shoulders_angle = math.degrees(math.atan2(shoulders_vec[1], shoulders_vec[0]))
            hips_angle = math.degrees(math.atan2(hips_vec[1], hips_vec[0]))
            metrics["trunk_twist_deg"] = abs(shoulders_angle - hips_angle)
        # knee angle
        hip_pt = get_px(hip_name); knee_pt = get_px(knee_name); ankle_pt = get_px(ankle_name)
        if hip_pt and knee_pt and ankle_pt:
            metrics["knee_angle_deg"] = angle_between(hip_pt, knee_pt, ankle_pt)
        # hip vs ankle dx
        if norm_lms and "LEFT_HIP" in norm_lms and "RIGHT_HIP" in norm_lms and "LEFT_ANKLE" in norm_lms and "RIGHT_ANKLE" in norm_lms:
            hip_center = (np.array(get_px("LEFT_HIP")) + np.array(get_px("RIGHT_HIP"))) / 2.0
            ankle_center = (np.array(get_px("LEFT_ANKLE")) + np.array(get_px("RIGHT_ANKLE"))) / 2.0
            metrics["hip_vs_ankle_dx"] = float(hip_center[0] - ankle_center[0])

        metrics["wrist_speed_px"] = wrist_speed

        # Swing detection
        swing_detected = wrist_speed > swing_speed_thresh
        # require a gap to avoid multiple detections
        if swing_detected and (frame_idx - last_swing_frame) > min_gap_frames:
            # require buffer full and no missing frames for classification
            seq_np = None
            if len(seq_buffer) == seq_len and all(x is not None for x in seq_buffer):
                seq_np = np.stack(seq_buffer, axis=0)  # (T, feat)
            stroke_label = None
            stroke_prob = None
            if seq_np is not None and clf is not None:
                try:
                    stroke_label, stroke_prob = clf.classify(seq_np)
                except Exception:
                    stroke_label, stroke_prob = None, None

            # compute per-swing feedback & record entry
            feedback_texts = simple_coach_feedback(metrics)
            swing_entry = {
                "frame_idx": frame_idx,
                "wrist_speed_px": wrist_speed,
                "metrics": metrics,
                "feedback": feedback_texts,
                "stroke_label": stroke_label,
                "stroke_prob": stroke_prob
            }
            swings.append(swing_entry)
            last_swing_frame = frame_idx

            # annotate frame with immediate feedback text
            # show top-left coach feedback
            y0 = 30
            for i, t in enumerate(feedback_texts[:6]):
                cv2.putText(frame, t, (10, y0 + i*22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2, cv2.LINE_AA)
            if stroke_label is not None:
                cv2.putText(frame, f"Stroke: {stroke_label} ({stroke_prob:.2f})", (10, h-30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (20,220,20), 2, cv2.LINE_AA)
        else:
            # small hint while preparing
            if wrist_speed > (swing_speed_thresh * 0.4):
                cv2.putText(frame, "Preparing swing...", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200,200,200), 2, cv2.LINE_AA)

        # draw landmarks and simple overlays
        draw_landmarks_on_frame(frame, norm_lms)
        # write wrist speed overlay
        cv2.putText(frame, f"Wrist speed: {wrist_speed:.1f}px", (10, h-60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (240,240,0), 2, cv2.LINE_AA)
        # write annotated frame
        out.write(frame)

        frame_idx += 1

    cap.release()
    out.release()
    pose.close()

    elapsed = time.time() - start_time
    # Simple summary (you may compute a better scoring algorithm)
    overall_score = int(60 + min(40, len(swings)*5))  # naive: more swings -> higher score (placeholder)
    analysis = {
        "sport": "tennis",
        "overall_score": overall_score,
        "swings_detected": len(swings),
        "swings": swings,
        "swing_speed_thresh": float(swing_speed_thresh),
        "analyzed_at": time.strftime("%Y-%m-%dT%H:%M:%S")
    }

    with open(analysis_json_path, "w") as f:
        json.dump(analysis, f, indent=2)

    return {"annotated_video": annotated_path, "analysis_json": analysis_json_path}
