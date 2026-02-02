#!/usr/bin/env python3
"""
Process video pipeline with ffmpeg normalization and inline classifier loading.

- Normalizes input video using ffmpeg to a consistent MP4 (H.264/AAC) file.
- Runs MediaPipe pose detection over normalized video frames.
- Computes per-frame metrics, detects swings based on wrist speed.
- Optionally loads a trained LSTM stroke classifier from model_dir (if present).
- Produces an annotated MP4 and an analysis JSON in output_dir.

Usage:
    analyze_video(input_path, output_dir="results/jobid", model_dir="models/quick_run", dominant_hand="right")
"""
import os
import json
import math
import time
import subprocess
from typing import Dict, Any, List, Optional

import cv2
import numpy as np

# Try optional imports for classifier
try:
    import joblib
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except Exception:
    TORCH_AVAILABLE = False

import mediapipe as mp
mp_pose = mp.solutions.pose

# ---------------------------
# Inline LSTM model & loader
# ---------------------------
if TORCH_AVAILABLE:
    class LSTMClassifier(nn.Module):
        def __init__(self, input_dim, hidden_dim=128, num_layers=2, num_classes=3, dropout=0.2, bidirectional=True):
            super().__init__()
            self.hidden_dim = hidden_dim
            self.num_layers = num_layers
            self.bidirectional = bidirectional
            num_directions = 2 if bidirectional else 1
            self.lstm = nn.LSTM(input_dim, hidden_dim, num_layers=num_layers,
                                batch_first=True, dropout=dropout, bidirectional=bidirectional)
            self.fc = nn.Sequential(
                nn.Linear(hidden_dim * num_directions, 64),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(64, num_classes)
            )

        def forward(self, x):
            out, (hn, cn) = self.lstm(x)
            last = out[:, -1, :]
            logits = self.fc(last)
            return logits

    class StrokeClassifierInline:
        """
        Loads model artifacts from a model_dir if available.
        Expects:
          - label_encoder.joblib
          - either model_best.pt (state_dict) and model_metadata.pt OR model_metadata.pt that contains state_dict
        """
        def __init__(self, model_dir: str):
            self.model_dir = model_dir
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.le = None
            self.model = None
            self.seq_len = None
            self.input_dim = None
            self.classes = None

            # load label encoder (optional)
            le_path = os.path.join(model_dir, "label_encoder.joblib")
            if os.path.exists(le_path):
                try:
                    self.le = joblib.load(le_path)
                except Exception:
                    self.le = None

            # load metadata (model_metadata.pt preferred)
            metadata_path = os.path.join(model_dir, "model_metadata.pt")
            model_best_path = os.path.join(model_dir, "model_best.pt")
            loaded_state = None
            meta = None
            if os.path.exists(metadata_path):
                try:
                    meta = torch.load(metadata_path, map_location="cpu")
                    # meta may contain "state_dict" key
                    if isinstance(meta, dict) and "state_dict" in meta:
                        loaded_state = meta["state_dict"]
                except Exception:
                    meta = None

            # if metadata didn't include state, try model_best.pt
            if loaded_state is None and os.path.exists(model_best_path):
                try:
                    loaded_state = torch.load(model_best_path, map_location="cpu")
                except Exception:
                    loaded_state = None

            # load class list / seq_len / input_dim from metadata if present
            if meta:
                self.input_dim = meta.get("input_dim")
                self.seq_len = meta.get("seq_len")
                self.classes = meta.get("classes")
            # fallback: try reading model_best.pt filename / not available -> keep None

            if loaded_state is None:
                # cannot load model
                raise RuntimeError("Model state not found in model_dir")

            if self.input_dim is None:
                # try infer from state shapes (best-effort). We need input_dim to instantiate LSTM
                # Without input_dim we cannot reliably create the model - bail
                raise RuntimeError("Model metadata missing input_dim; please include model_metadata.pt")

            num_classes = len(self.classes) if self.classes else (loaded_state.get("fc.3.weight").shape[0] if "fc.3.weight" in loaded_state else 3)
            # instantiate model with default hyperparams used during training (may need tuning)
            self.model = LSTMClassifier(input_dim=self.input_dim, hidden_dim=128, num_layers=2, num_classes=num_classes, bidirectional=True)
            # load state (state may be a state_dict)
            try:
                self.model.load_state_dict(loaded_state)
            except Exception as e:
                # maybe state is already a full checkpoint with "state_dict"
                if isinstance(loaded_state, dict) and "state_dict" in loaded_state:
                    self.model.load_state_dict(loaded_state["state_dict"])
                else:
                    raise e
            self.model.to(self.device)
            self.model.eval()

        def _prepare(self, seq: np.ndarray):
            # seq: (T, feat)
            if self.seq_len is None:
                # try infer from model metadata, else fallback to seq length provided
                self.seq_len = seq.shape[0]
            if seq.shape[0] != self.seq_len:
                if seq.shape[0] > self.seq_len:
                    start = (seq.shape[0] - self.seq_len)//2
                    seq = seq[start:start+self.seq_len]
                else:
                    pad = np.repeat(seq[-1:,:], self.seq_len - seq.shape[0], axis=0)
                    seq = np.concatenate([seq, pad], axis=0)
            x = torch.from_numpy(seq).unsqueeze(0).to(self.device)
            return x

        def classify(self, seq: np.ndarray):
            x = self._prepare(seq)
            with torch.no_grad():
                logits = self.model(x)
                probs = F.softmax(logits, dim=1).cpu().numpy()[0]
                idx = int(np.argmax(probs))
                label = self.classes[idx] if self.classes else (self.le.inverse_transform([idx])[0] if self.le is not None else str(idx))
                return label, float(probs[idx])
else:
    StrokeClassifierInline = None

# ---------------------------
# Math & Mediapipe helpers
# ---------------------------
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

def landmarks_from_results(results) -> Optional[Dict[str, tuple]]:
    if not results or not results.pose_landmarks:
        return None
    lm_dict = {}
    for idx, lm in enumerate(results.pose_landmarks.landmark):
        name = mp_pose.PoseLandmark(idx).name
        lm_dict[name] = (lm.x, lm.y, lm.z, lm.visibility)
    return lm_dict

def get_flat_landmarks_dict(norm_landmarks: Dict[str, tuple]) -> Optional[np.ndarray]:
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

def draw_landmarks_on_frame(frame, norm_landmarks):
    if not norm_landmarks:
        return
    h, w = frame.shape[:2]
    mp_draw = mp.solutions.drawing_utils
    from mediapipe.framework.formats import landmark_pb2
    lm_list = []
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

# ---------------------------
# ffmpeg normalization
# ---------------------------
def normalize_with_ffmpeg(input_path: str, output_path: str) -> None:
    """
    Normalize video to H.264/AAC MP4 at same resolution (re-encode).
    Requires ffmpeg on PATH.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        output_path
    ]
    # Run and let ffmpeg print progress to console; raise on error
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        # include stderr for debugging
        raise RuntimeError(f"ffmpeg normalization failed: {proc.stderr.decode('utf-8', errors='ignore')}")

# ---------------------------
# Main analyze function
# ---------------------------
def analyze_video(input_path: str, output_dir: str, model_dir: Optional[str] = None,
                  dominant_hand: str = "right", swing_speed_thresh: Optional[float] = None,
                  normalize: bool = True) -> Dict[str, Any]:
    """
    Analyze video and write annotated output + analysis.json.

    - input_path: original uploaded file
    - output_dir: place to write annotated.mp4 and analysis.json
    - model_dir: optional path to trained classifier artifacts
    - dominant_hand: 'right' or 'left'
    - swing_speed_thresh: override detection threshold (pixels/frame). If None, heuristic derived from width.
    - normalize: run ffmpeg normalization before processing
    """
    os.makedirs(output_dir, exist_ok=True)
    annotated_path = os.path.join(output_dir, "annotated.mp4")
    analysis_json_path = os.path.join(output_dir, "analysis.json")

    # Step 1: normalize input (if requested)
    tmp_normalized = os.path.join(output_dir, "normalized_input.mp4")
    source_for_capture = input_path
    if normalize:
        try:
            normalize_with_ffmpeg(input_path, tmp_normalized)
            source_for_capture = tmp_normalized
        except Exception as e:
            # if normalization fails, fall back to original and continue with a warning in analysis
            source_for_capture = input_path
            normalization_error = str(e)
        else:
            normalization_error = None
    else:
        normalization_error = None

    cap = cv2.VideoCapture(source_for_capture)
    if not cap.isOpened():
        raise RuntimeError("Cannot open video for processing: " + source_for_capture)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    if swing_speed_thresh is None:
        swing_speed_thresh = max(40.0, w * 0.06)  # heuristic px/frame

    # attempt to load classifier inline if provided and torch available
    clf = None
    if model_dir and TORCH_AVAILABLE:
        try:
            clf = StrokeClassifierInline(model_dir)
        except Exception:
            clf = None

    pose = mp_pose.Pose(static_image_mode=False, model_complexity=1,
                        min_detection_confidence=0.5, min_tracking_confidence=0.5)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(annotated_path, fourcc, fps, (w, h))

    seq_len = 24
    seq_buffer = []
    last_wrist_px = None
    last_swing_frame = -9999
    min_gap_frames = int(fps * 0.4)
    frame_idx = 0

    swings = []
    start_time = time.time()
    try:
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

            wrist_name = "RIGHT_WRIST" if dominant_hand == "right" else "LEFT_WRIST"
            wrist_px = None
            if norm_lms and wrist_name in norm_lms:
                nx, ny, nz, vis = norm_lms[wrist_name]
                if nx is not None:
                    wrist_px = (int(nx * w), int(ny * h))

            wrist_speed = 0.0
            if last_wrist_px is not None and wrist_px is not None:
                wrist_speed = euclidean(last_wrist_px, wrist_px)
            last_wrist_px = wrist_px

            # quick metrics
            metrics = {}
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

            if norm_lms and "LEFT_SHOULDER" in norm_lms and "RIGHT_SHOULDER" in norm_lms and "LEFT_HIP" in norm_lms and "RIGHT_HIP" in norm_lms:
                try:
                    sL = np.array(get_px("LEFT_SHOULDER")); sR = np.array(get_px("RIGHT_SHOULDER"))
                    hL = np.array(get_px("LEFT_HIP")); hR = np.array(get_px("RIGHT_HIP"))
                    shoulders_vec = sR - sL
                    hips_vec = hR - hL
                    shoulders_angle = math.degrees(math.atan2(shoulders_vec[1], shoulders_vec[0]))
                    hips_angle = math.degrees(math.atan2(hips_vec[1], hips_vec[0]))
                    metrics["trunk_twist_deg"] = abs(shoulders_angle - hips_angle)
                except Exception:
                    pass

            hip_pt = get_px(hip_name); knee_pt = get_px(knee_name); ankle_pt = get_px(ankle_name)
            if hip_pt and knee_pt and ankle_pt:
                metrics["knee_angle_deg"] = angle_between(hip_pt, knee_pt, ankle_pt)

            if norm_lms and "LEFT_HIP" in norm_lms and "RIGHT_HIP" in norm_lms and "LEFT_ANKLE" in norm_lms and "RIGHT_ANKLE" in norm_lms:
                hip_center = (np.array(get_px("LEFT_HIP")) + np.array(get_px("RIGHT_HIP"))) / 2.0
                ankle_center = (np.array(get_px("LEFT_ANKLE")) + np.array(get_px("RIGHT_ANKLE"))) / 2.0
                metrics["hip_vs_ankle_dx"] = float(hip_center[0] - ankle_center[0])

            metrics["wrist_speed_px"] = wrist_speed

            # Swing detection & classification
            swing_detected = wrist_speed > swing_speed_thresh
            if swing_detected and (frame_idx - last_swing_frame) > min_gap_frames:
                seq_np = None
                if len(seq_buffer) == seq_len and all(x is not None for x in seq_buffer):
                    seq_np = np.stack(seq_buffer, axis=0)
                stroke_label = None
                stroke_prob = None
                if seq_np is not None and clf is not None:
                    try:
                        stroke_label, stroke_prob = clf.classify(seq_np)
                    except Exception:
                        stroke_label, stroke_prob = None, None

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

                # overlay quick feedback on frame
                y0 = 30
                for i, t in enumerate(feedback_texts[:6]):
                    cv2.putText(frame, t, (10, y0 + i*22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2, cv2.LINE_AA)
                if stroke_label is not None:
                    cv2.putText(frame, f"Stroke: {stroke_label} ({stroke_prob:.2f})", (10, h-30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (20,220,20), 2, cv2.LINE_AA)
            else:
                if wrist_speed > (swing_speed_thresh * 0.4):
                    cv2.putText(frame, "Preparing swing...", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200,200,200), 2, cv2.LINE_AA)

            draw_landmarks_on_frame(frame, norm_lms)
            cv2.putText(frame, f"Wrist speed: {wrist_speed:.1f}px", (10, h-60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (240,240,0), 2, cv2.LINE_AA)
            out.write(frame)
            frame_idx += 1
    finally:
        cap.release()
        out.release()
        pose.close()

    elapsed = time.time() - start_time
    overall_score = int(60 + min(40, len(swings)*5))
    analysis = {
        "sport": "tennis",
        "overall_score": overall_score,
        "swings_detected": len(swings),
        "swings": swings,
        "swing_speed_thresh": float(swing_speed_thresh),
        "normalization_error": normalization_error,
        "analyzed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "processing_seconds": elapsed
    }

    with open(analysis_json_path, "w") as f:
        json.dump(analysis, f, indent=2)

    return {"annotated_video": annotated_path, "analysis_json": analysis_json_path}
