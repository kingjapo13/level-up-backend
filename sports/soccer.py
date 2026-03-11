from typing import Dict, Any, List
from sports.base import SportAnalyzer


class SoccerAnalyzer(SportAnalyzer):
    name = "soccer"

    def analyze(self, angle_data: Dict[str, Any]) -> Dict[str, Any]:
        knee_angles = angle_data.get("knee", [])
        hip_angles = angle_data.get("hip", [])

        if not knee_angles:
            return {"error": "No knee angle data available"}

        min_knee = min(knee_angles)
        max_knee = max(knee_angles)
        avg_knee = sum(knee_angles) / len(knee_angles)
        avg_hip = sum(hip_angles) / len(hip_angles) if hip_angles else None

        return {
            "kick_detected": min_knee < 70,
            "full_followthrough": max_knee >= 155,
            "min_knee_angle": round(min_knee, 1),
            "max_knee_angle": round(max_knee, 1),
            "avg_knee_angle": round(avg_knee, 1),
            "avg_hip_angle": round(avg_hip, 1) if avg_hip else None,
        }

    def score(self, metrics: Dict[str, Any]) -> int:
        if "error" in metrics:
            return 0
        score = 60
        if metrics.get("kick_detected"):
            score += 20
        if metrics.get("full_followthrough"):
            score += 20
        hip = metrics.get("avg_hip_angle")
        if hip and hip < 60:
            score -= 10
        return max(0, min(100, score))

    def feedback(self, metrics: Dict[str, Any]) -> List[str]:
        tips = []
        if "error" in metrics:
            return ["Could not detect kicking motion. Ensure full leg is visible."]
        if not metrics.get("kick_detected"):
            tips.append("Kick not clearly detected — bend your knee further on the backswing.")
        if not metrics.get("full_followthrough"):
            tips.append("Incomplete follow-through — drive through the ball fully for more power.")
        if not tips:
            tips.append("Strong kicking mechanics! Work on placement accuracy.")
        return tips