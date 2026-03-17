from typing import Dict, Any, List
from sports.base import SportAnalyzer


class BaseballAnalyzer(SportAnalyzer):
    name = "baseball"

    def analyze(self, angle_data: Dict[str, Any]) -> Dict[str, Any]:
        shoulder_angles = angle_data.get("shoulder", [])
        elbow_angles = angle_data.get("elbow", [])
        hip_angles = angle_data.get("hip", [])

        if not shoulder_angles and not elbow_angles:
            return {"error": "Insufficient angle data for baseball analysis"}

        avg_shoulder = sum(shoulder_angles) / len(shoulder_angles) if shoulder_angles else None
        avg_elbow = sum(elbow_angles) / len(elbow_angles) if elbow_angles else None
        avg_hip = sum(hip_angles) / len(hip_angles) if hip_angles else None

        # Throwing power proxy: shoulder rotation range
        throw_power = None
        if shoulder_angles:
            shoulder_range = max(shoulder_angles) - min(shoulder_angles)
            throw_power = min(100, int(shoulder_range * 1.3))

        # Hip rotation
        hip_rotation = None
        if hip_angles:
            hip_range = max(hip_angles) - min(hip_angles)
            hip_rotation = min(100, int(hip_range * 1.2))

        return {
            "throw_power": throw_power or 70,
            "hip_rotation": hip_rotation or 70,
            "avg_shoulder_angle": round(avg_shoulder, 1) if avg_shoulder else None,
            "avg_elbow_angle": round(avg_elbow, 1) if avg_elbow else None,
            "avg_hip_angle": round(avg_hip, 1) if avg_hip else None,
        }

    def score(self, metrics: Dict[str, Any]) -> int:
        if "error" in metrics:
            return 0
        score = 60
        if metrics.get("throw_power", 0) >= 80:
            score += 20
        elif metrics.get("throw_power", 0) >= 60:
            score += 10
        if metrics.get("hip_rotation", 0) >= 80:
            score += 20
        elif metrics.get("hip_rotation", 0) >= 60:
            score += 10
        return max(0, min(100, score))

    def feedback(self, metrics: Dict[str, Any]) -> List[str]:
        tips = []
        if "error" in metrics:
            return ["Could not analyze baseball motion. Ensure full body is visible."]
        if metrics.get("throw_power", 100) < 65:
            tips.append("Low throwing power — rotate your shoulder fully and follow through.")
        if metrics.get("hip_rotation", 100) < 65:
            tips.append("Increase hip rotation to generate more throwing velocity.")
        if not tips:
            tips.append("Great throwing mechanics! Focus on accuracy and release point.")
        return tips