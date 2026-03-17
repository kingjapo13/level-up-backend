from typing import Dict, Any, List
from sports.base import SportAnalyzer


class TennisAnalyzer(SportAnalyzer):
    name = "tennis"

    def analyze(self, angle_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyzes tennis serve/stroke using shoulder, elbow, and knee angles.

        Expected angle_data keys:
            - shoulder: List[float]
            - elbow: List[float]
            - knee: List[float]
        """
        shoulder_angles = angle_data.get("shoulder", [])
        elbow_angles = angle_data.get("elbow", [])
        knee_angles = angle_data.get("knee", [])

        if not shoulder_angles and not elbow_angles:
            return {"error": "Insufficient angle data for tennis analysis"}

        # Serve power proxy: shoulder rotation range
        serve_power = None
        if shoulder_angles:
            shoulder_range = max(shoulder_angles) - min(shoulder_angles)
            serve_power = min(100, int(shoulder_range * 1.3))

        # Knee bend for ready position
        avg_knee = sum(knee_angles) / len(knee_angles) if knee_angles else None

        # Elbow extension for follow through
        avg_elbow = sum(elbow_angles) / len(elbow_angles) if elbow_angles else None
        max_elbow = max(elbow_angles) if elbow_angles else None

        # Consistency of shoulder rotation
        consistency = None
        if shoulder_angles:
            ideal_frames = [a for a in shoulder_angles if 60 <= a <= 120]
            consistency = round(len(ideal_frames) / len(shoulder_angles) * 100, 1)

        return {
            "serve_power": serve_power or 70,
            "avg_knee_angle": round(avg_knee, 1) if avg_knee else None,
            "avg_elbow_angle": round(avg_elbow, 1) if avg_elbow else None,
            "max_elbow_extension": round(max_elbow, 1) if max_elbow else None,
            "stroke_consistency": consistency or 70,
        }

    def score(self, metrics: Dict[str, Any]) -> int:
        if "error" in metrics:
            return 0

        score = 60
        serve_power = metrics.get("serve_power", 0)
        consistency = metrics.get("stroke_consistency", 0)

        if serve_power >= 80:
            score += 20
        elif serve_power >= 60:
            score += 10
        else:
            score -= 10

        if consistency >= 70:
            score += 20
        elif consistency >= 50:
            score += 10
        else:
            score -= 10

        return max(0, min(100, score))

    def feedback(self, metrics: Dict[str, Any]) -> List[str]:
        tips = []
        if "error" in metrics:
            return ["Could not analyze tennis motion. Ensure full body is visible."]

        serve_power = metrics.get("serve_power", 100)
        consistency = metrics.get("stroke_consistency", 100)
        avg_knee = metrics.get("avg_knee_angle")
        max_elbow = metrics.get("max_elbow_extension")

        if serve_power < 65:
            tips.append(
                "Low serve power detected — rotate your shoulder fully and drive through the ball."
            )

        if consistency < 60:
            tips.append(
                f"Stroke consistency is low ({consistency:.0f}%) — focus on a repeatable swing path."
            )

        if avg_knee and avg_knee > 160:
            tips.append(
                "Bend your knees more in your ready position for better court coverage and reaction time."
            )

        if max_elbow and max_elbow < 150:
            tips.append(
                "Extend your arm more fully on follow-through for better power and control."
            )

        if not tips:
            tips.append(
                "Solid tennis mechanics! Focus on placement, spin variation, and footwork to the ball."
            )

        return tips