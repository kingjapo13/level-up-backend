from typing import Dict, Any, List
from sports.base import SportAnalyzer


class VolleyballAnalyzer(SportAnalyzer):
    name = "volleyball"

    def analyze(self, angle_data: Dict[str, Any]) -> Dict[str, Any]:
        shoulder_angles = angle_data.get("shoulder", [])
        elbow_angles = angle_data.get("elbow", [])
        knee_angles = angle_data.get("knee", [])

        if not shoulder_angles:
            return {"error": "Insufficient data for volleyball analysis"}

        avg_shoulder = sum(shoulder_angles) / len(shoulder_angles)
        max_shoulder = max(shoulder_angles)
        avg_elbow = sum(elbow_angles) / len(elbow_angles) if elbow_angles else None
        avg_knee = sum(knee_angles) / len(knee_angles) if knee_angles else None

        arm_swing = max_shoulder - min(shoulder_angles) if shoulder_angles else 0
        spike_power = min(100, int(arm_swing * 1.3))

        return {
            "spike_power": spike_power,
            "avg_shoulder_angle": round(avg_shoulder, 1),
            "max_shoulder_rotation": round(max_shoulder, 1),
            "avg_elbow_angle": round(avg_elbow, 1) if avg_elbow else None,
            "avg_knee_angle": round(avg_knee, 1) if avg_knee else None,
        }

    def score(self, metrics: Dict[str, Any]) -> int:
        if "error" in metrics:
            return 0
        score = 60
        spike = metrics.get("spike_power", 0)
        if spike >= 80:
            score += 30
        elif spike >= 60:
            score += 15
        knee = metrics.get("avg_knee_angle")
        if knee and knee < 150:
            score += 10
        return max(0, min(100, score))

    def feedback(self, metrics: Dict[str, Any]) -> List[str]:
        tips = []
        if "error" in metrics:
            return ["Could not analyze volleyball motion. Ensure full body is visible."]
        if metrics.get("spike_power", 100) < 65:
            tips.append("Increase arm swing speed for more spike power.")
        knee = metrics.get("avg_knee_angle")
        if knee and knee > 160:
            tips.append("Bend your knees more in ready position for better reaction time.")
        if not tips:
            tips.append("Good mechanics! Focus on placement and court coverage.")
        return tips