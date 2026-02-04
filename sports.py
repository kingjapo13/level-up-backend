import numpy as np

def angle(a, b, c):
    a, b, c = np.array(a), np.array(b), np.array(c)
    ba, bc = a - b, c - b
    cos_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    return float(np.degrees(np.arccos(np.clip(cos_angle, -1, 1))))

def basketball_shot(elbow, shoulder, wrist):
    elbow_angle = angle(shoulder, elbow, wrist)
    good = 85 <= elbow_angle <= 110
    return elbow_angle, good

def golf_swing_phase(wrist_y, prev):
    if prev is None:
        return "setup"
    if wrist_y < prev - 0.02:
        return "backswing"
    if wrist_y > prev + 0.02:
        return "downswing"
    return "follow_through"

