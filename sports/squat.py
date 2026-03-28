from typing import Dict, Any, List
from sports.base import SportAnalyzer


class SquatAnalyzer(SportAnalyzer):
    name = "squat"

    def analyze(self, angle_data: Dict[str, Any]) -> Dict[str, Any]:
        knee_angles = angle_data.get("knee", [])
        hip_angles = angle_data.get("hip", [])

        if not knee_angles:
            return {"error": "Insufficient data for squat analysis"}

        avg_knee = sum(knee_angles) / len(knee_angles)
        min_knee = min(knee_angles)
        max_knee = max(knee_angles)
        knee_range = max_knee - min_knee

        avg_hip = sum(hip_angles) / len(hip_angles) if hip_angles else None

        depth_score = min(100, max(0, int((180 - min_knee) * 1.2)))

        return {
            "avg_knee_angle": round(avg_knee, 1),
            "min_knee_angle": round(min_knee, 1),
            "max_knee_angle": round(max_knee, 1),
            "knee_range": round(knee_range, 1),
            "avg_hip_angle": round(avg_hip, 1) if avg_hip else None,
            "depth_score": depth_score,
        }

    def score(self, metrics: Dict[str, Any]) -> int:
        if "error" in metrics:
            return 0
        score = 50
        depth = metrics.get("depth_score", 0)
        if depth >= 80:
            score += 30
        elif depth >= 60:
            score += 15
        knee_range = metrics.get("knee_range", 0)
        if knee_range >= 60:
            score += 20
        elif knee_range >= 40:
            score += 10
        return max(0, min(100, score))

    def feedback(self, metrics: Dict[str, Any]) -> List[str]:
        tips = []
        if "error" in metrics:
            return ["Could not analyze squat. Ensure full body is visible."]
        min_knee = metrics.get("min_knee_angle", 180)
        if min_knee > 110:
            tips.append("Squat deeper — aim to get thighs parallel to the floor.")
        if min_knee > 130:
            tips.append("Increase range of motion — you are only doing a partial squat.")
        knee_range = metrics.get("knee_range", 0)
        if knee_range < 40:
            tips.append("Increase your range of motion for more effective squats.")
        if not tips:
            tips.append("Great squat depth! Focus on keeping chest up and knees over toes.")
        return tips