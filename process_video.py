# process_video.py
import argparse
from pose_tracker import PoseTracker
from analyzer import Analyzer
from classifier import StrokeClassifier  # optional
from coach import Coach
from utils import draw_landmarks, draw_feedback
import cv2
import numpy as np
import json
import os

def analyze_video(input_path, output_dir="results", model_dir=None, dominant_hand="right"):
    os.makedirs(output_dir, exist_ok=True)
    cap = cv2.VideoCapture(input_path)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0

    tracker = PoseTracker(static_image_mode=False, model_complexity=1,
                          min_detection_confidence=0.5, min_tracking_confidence=0.5)
    analyzer = Analyzer(w, h, dominant_hand=dominant_hand)
    coach = Coach()
    clf = None
    if model_dir:
        from classifier import StrokeClassifier
        clf = StrokeClassifier(model_dir)

    # prepare video writer for annotated output
    out_path = os.path.join(output_dir, "annotated.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(out_path, fourcc, fps, (w, h))

    results_summary = {"swings": []}
    frame_idx = 0
    seq_buffer = []
    seq_len = 24

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        results = tracker.process(frame)
        lms = tracker.get_landmarks_dict(results)
        metrics = analyzer.update(frame_idx, lms)
        feedback = coach.update(frame_idx, lms, metrics)

        # classification on swing detection (as earlier app.py)
        if clf and metrics.get("swing_detected"):
            # build sequence of flattened landmarks and call clf.classify(...)
            pass

        # draw overlays and write
        draw_landmarks(frame, lms)
        draw_feedback(frame, feedback)
        out.write(frame)
        frame_idx += 1

    cap.release()
    out.release()
    # write JSON summary
    json_path = os.path.join(output_dir, "analysis.json")
    with open(json_path, "w") as f:
        json.dump(results_summary, f, indent=2)
    return {"annotated_video": out_path, "analysis_json": json_path}
