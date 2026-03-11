from typing import Dict, Any, List
from sports.base import SportAnalyzer


class PickleballAnalyzer(SportAnalyzer):
    name = "pickleball"

    def analyze(self, angle_data: Dict[str, Any]) -> Dict[str, Any]:
        shoulder_angles = angle_data.get("shoulder", [])
        elbow_angles = angle_data.get("elbow", [])
        knee_angles = angle_data.get("knee", [])

        if not shoulder_angles and not elbow_angles:
            return {"error": "Insufficient angle data for pickleball analysis"}

        serve_power = None
        if shoulder_angles:
            shoulder_range = max(shoulder_angles) - min(shoulder_angles)
            serve_power = min(100, int(shoulder_range * 1.2))

        footwork_score = None
        if knee_angles:
            knee_range = max(knee_angles) - min(knee_angles)
            footwork_score = min(100, int(knee_range * 1.4))

        avg_elbow = sum(elbow_angles) / len(elbow_angles) if elbow_angles else None

        return {
            "serve_power": serve_power or 70,
            "footwork_score": footwork_score or 75,
            "avg_elbow_angle": round(avg_elbow, 1) if avg_elbow else None,
        }

    def score(self, metrics: Dict[str, Any]) -> int:
        if "error" in metrics:
            return 0
        return int((metrics.get("serve_power", 0) + metrics.get("footwork_score", 0)) / 2)

    def feedback(self, metrics: Dict[str, Any]) -> List[str]:
        tips = []
        if "error" in metrics:
            return ["Could not analyze pickleball motion. Ensure full body visibility."]
        if metrics.get("serve_power", 100) < 70:
            tips.append("Increase hip rotation during serve for more power.")
        if metrics.get("footwork_score", 100) < 65:
            tips.append("Work on lateral movement drills to improve court coverage.")
        if not tips:
            tips.append("Good overall mechanics! Focus on placement and third-shot drops.")
        return tips