from typing import Dict, Any, List
from sports.base import SportAnalyzer


class BoxingAnalyzer(SportAnalyzer):
    name = "boxing"

    def analyze(self, angle_data: Dict[str, Any]) -> Dict[str, Any]:
        elbow_angles = angle_data.get("elbow", [])
        shoulder_angles = angle_data.get("shoulder", [])
        hip_angles = angle_data.get("hip", [])

        if not elbow_angles:
            return {"error": "Insufficient data for boxing analysis"}

        avg_elbow = sum(elbow_angles) / len(elbow_angles)
        min_elbow = min(elbow_angles)
        max_elbow = max(elbow_angles)
        punch_extension = max_elbow - min_elbow

        avg_shoulder = sum(shoulder_angles) / len(shoulder_angles) if shoulder_angles else None
        avg_hip = sum(hip_angles) / len(hip_angles) if hip_angles else None

        punch_power = min(100, int(punch_extension * 1.1))
        hip_rotation = None
        if hip_angles:
            hip_range = max(hip_angles) - min(hip_angles)
            hip_rotation = min(100, int(hip_range * 1.2))

        return {
            "punch_power": punch_power,
            "punch_extension": round(punch_extension, 1),
            "hip_rotation": hip_rotation or 60,
            "avg_elbow_angle": round(avg_elbow, 1),
            "avg_shoulder_angle": round(avg_shoulder, 1) if avg_shoulder else None,
        }

    def score(self, metrics: Dict[str, Any]) -> int:
        if "error" in metrics:
            return 0
        score = 55
        if metrics.get("punch_power", 0) >= 75:
            score += 25
        elif metrics.get("punch_power", 0) >= 55:
            score += 12
        if metrics.get("hip_rotation", 0) >= 70:
            score += 20
        elif metrics.get("hip_rotation", 0) >= 50:
            score += 10
        return max(0, min(100, score))

    def feedback(self, metrics: Dict[str, Any]) -> List[str]:
        tips = []
        if "error" in metrics:
            return ["Could not analyze boxing motion. Ensure full body is visible."]
        if metrics.get("punch_power", 100) < 60:
            tips.append("Extend your arm fully on punches for maximum reach and power.")
        if metrics.get("hip_rotation", 100) < 55:
            tips.append("Rotate your hips into punches to generate more power from your core.")
        if not tips:
            tips.append("Strong punching mechanics! Focus on combination speed and head movement.")
        return tips