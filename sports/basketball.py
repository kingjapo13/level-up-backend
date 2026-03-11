from typing import Dict, Any, List
from sports.base import SportAnalyzer


class BasketballAnalyzer(SportAnalyzer):
    name = "basketball"

    IDEAL_ELBOW_MIN = 85
    IDEAL_ELBOW_MAX = 100
    ACCEPTABLE_ELBOW_MIN = 70
    ACCEPTABLE_ELBOW_MAX = 115

    def analyze(self, angle_data: Dict[str, Any]) -> Dict[str, Any]:
        elbow_angles = angle_data.get("elbow", [])
        shoulder_angles = angle_data.get("shoulder", [])
        knee_angles = angle_data.get("knee", [])

        if not elbow_angles:
            return {"error": "No elbow angle data available"}

        avg_elbow = sum(elbow_angles) / len(elbow_angles)
        avg_shoulder = sum(shoulder_angles) / len(shoulder_angles) if shoulder_angles else None
        avg_knee = sum(knee_angles) / len(knee_angles) if knee_angles else None

        ideal_frames = [a for a in elbow_angles if self.IDEAL_ELBOW_MIN <= a <= self.IDEAL_ELBOW_MAX]
        consistency = round(len(ideal_frames) / len(elbow_angles) * 100, 1)

        shot_grade, shot_note = self._grade_shot(avg_elbow)

        return {
            "avg_elbow_angle": round(avg_elbow, 1),
            "avg_shoulder_angle": round(avg_shoulder, 1) if avg_shoulder else None,
            "avg_knee_angle": round(avg_knee, 1) if avg_knee else None,
            "elbow_consistency_pct": consistency,
            "shot_grade": shot_grade,
            "shot_note": shot_note,
        }

    def score(self, metrics: Dict[str, Any]) -> int:
        if "error" in metrics:
            return 0
        base = metrics.get("shot_grade", 60)
        consistency_bonus = int(metrics.get("elbow_consistency_pct", 0) * 0.2)
        return min(100, base + consistency_bonus)

    def feedback(self, metrics: Dict[str, Any]) -> List[str]:
        tips = []
        if "error" in metrics:
            return ["Could not detect shooting motion. Ensure your full arm is visible."]

        elbow = metrics.get("avg_elbow_angle")
        consistency = metrics.get("elbow_consistency_pct", 100)

        if elbow is not None:
            if elbow < self.ACCEPTABLE_ELBOW_MIN:
                tips.append(f"Elbow angle too low ({elbow:.0f}°) — tuck your elbow in closer to your body.")
            elif elbow > self.ACCEPTABLE_ELBOW_MAX:
                tips.append(f"Elbow flaring out ({elbow:.0f}°) — keep elbow under the ball at release.")

        if consistency < 60:
            tips.append(f"Shooting form is inconsistent ({consistency:.0f}% ideal frames) — work on a repeatable release.")

        if not tips:
            tips.append("Great shooting mechanics! Focus on follow-through and arch consistency.")

        return tips

    def _grade_shot(self, avg_elbow: float):
        if self.IDEAL_ELBOW_MIN <= avg_elbow <= self.IDEAL_ELBOW_MAX:
            return 95, "Excellent elbow alignment at release"
        elif self.ACCEPTABLE_ELBOW_MIN <= avg_elbow <= self.ACCEPTABLE_ELBOW_MAX:
            return 78, "Solid form — minor elbow adjustment needed"
        else:
            return 55, "Elbow alignment needs significant work"