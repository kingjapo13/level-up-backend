from typing import Dict, Any, List
from sports.base import SportAnalyzer


class BasketballAnalyzer(SportAnalyzer):
    name = "basketball"

    # Ideal shooting elbow angle at release (L-shape under ball)
    IDEAL_ELBOW_MIN = 80
    IDEAL_ELBOW_MAX = 105
    # Ideal knee bend for athletic stance
    IDEAL_KNEE_MIN = 140
    IDEAL_KNEE_MAX = 170
    # Ideal shoulder angle
    IDEAL_SHOULDER_MIN = 40
    IDEAL_SHOULDER_MAX = 80

    def analyze(self, angle_data: Dict[str, Any]) -> Dict[str, Any]:
        elbow_angles = angle_data.get("elbow", [])
        shoulder_angles = angle_data.get("shoulder", [])
        knee_angles = angle_data.get("knee", [])

        if not elbow_angles:
            return {"error": "No elbow angle data — make sure your full arm is visible"}

        avg_elbow = self._safe_avg(elbow_angles)
        avg_shoulder = self._safe_avg(shoulder_angles) if shoulder_angles else None
        avg_knee = self._safe_avg(knee_angles) if knee_angles else None
        elbow_consistency = self._consistency_pct(
            elbow_angles, self.IDEAL_ELBOW_MIN, self.IDEAL_ELBOW_MAX
        )
        elbow_std = self._std_dev(elbow_angles)

        return {
            "avg_elbow_angle": round(avg_elbow, 1),
            "avg_shoulder_angle": round(avg_shoulder, 1) if avg_shoulder else None,
            "avg_knee_angle": round(avg_knee, 1) if avg_knee else None,
            "elbow_consistency_pct": elbow_consistency,
            "elbow_std_dev": round(elbow_std, 1),
        }

    def score(self, metrics: Dict[str, Any]) -> int:
        if "error" in metrics:
            return 30

        elbow = metrics.get("avg_elbow_angle", 0)
        consistency = metrics.get("elbow_consistency_pct", 0)
        std_dev = metrics.get("elbow_std_dev", 999)
        knee = metrics.get("avg_knee_angle")
        shoulder = metrics.get("avg_shoulder_angle")

        # Factor 1: Elbow alignment (30% weight)
        if self.IDEAL_ELBOW_MIN <= elbow <= self.IDEAL_ELBOW_MAX:
            elbow_score = 90
        elif 70 <= elbow < self.IDEAL_ELBOW_MIN or self.IDEAL_ELBOW_MAX < elbow <= 120:
            elbow_score = 65
        elif 55 <= elbow < 70 or 120 < elbow <= 135:
            elbow_score = 45
        else:
            elbow_score = 25

        # Factor 2: Consistency across reps (25% weight)
        if consistency >= 70:
            consistency_score = 90
        elif consistency >= 50:
            consistency_score = 70
        elif consistency >= 30:
            consistency_score = 50
        else:
            consistency_score = 30

        # Factor 3: Stability / low std dev (20% weight)
        if std_dev < 10:
            stability_score = 90
        elif std_dev < 20:
            stability_score = 70
        elif std_dev < 30:
            stability_score = 50
        else:
            stability_score = 30

        # Factor 4: Knee bend / athletic stance (15% weight)
        if knee and self.IDEAL_KNEE_MIN <= knee <= self.IDEAL_KNEE_MAX:
            knee_score = 85
        elif knee and 125 <= knee < self.IDEAL_KNEE_MIN:
            knee_score = 65
        elif knee:
            knee_score = 45
        else:
            knee_score = 55  # no data — neutral

        # Factor 5: Shoulder position (10% weight)
        if shoulder and self.IDEAL_SHOULDER_MIN <= shoulder <= self.IDEAL_SHOULDER_MAX:
            shoulder_score = 85
        elif shoulder:
            shoulder_score = 55
        else:
            shoulder_score = 55

        return self._score_from_factors([
            {"score": elbow_score,       "weight": 0.30},
            {"score": consistency_score, "weight": 0.25},
            {"score": stability_score,   "weight": 0.20},
            {"score": knee_score,        "weight": 0.15},
            {"score": shoulder_score,    "weight": 0.10},
        ])

    def feedback(self, metrics: Dict[str, Any]) -> List[str]:
        if "error" in metrics:
            return ["Could not detect shooting motion. Make sure your full arm is visible."]

        tips = []
        elbow = metrics.get("avg_elbow_angle")
        consistency = metrics.get("elbow_consistency_pct", 100)
        std_dev = metrics.get("elbow_std_dev", 0)
        knee = metrics.get("avg_knee_angle")

        if elbow is not None:
            if elbow < 70:
                tips.append({
                    "tip": f"Elbow angle too closed ({elbow:.0f}°) — keep elbow under the ball forming an L-shape at release.",
                    "priority": "high"
                })
            elif elbow > 120:
                tips.append({
                    "tip": f"Elbow flaring out ({elbow:.0f}°) — tuck your elbow in, it should point at the basket.",
                    "priority": "high"
                })
            elif self.IDEAL_ELBOW_MIN <= elbow <= self.IDEAL_ELBOW_MAX:
                tips.append({
                    "tip": f"Good elbow alignment at {elbow:.0f}° — keep it consistent every shot.",
                    "priority": "low"
                })

        if consistency < 40:
            tips.append({
                "tip": f"Your form is very inconsistent ({consistency:.0f}% ideal frames) — slow down and focus on repeating the same motion.",
                "priority": "high"
            })
        elif consistency < 65:
            tips.append({
                "tip": f"Form consistency at {consistency:.0f}% — practice form shooting from 3 feet to groove your mechanics.",
                "priority": "medium"
            })

        if std_dev > 25:
            tips.append({
                "tip": "High variability in your release point — record yourself to identify what changes between shots.",
                "priority": "medium"
            })

        if knee and knee < 130:
            tips.append({
                "tip": f"Knees too bent ({knee:.0f}°) — use a natural athletic stance, not a deep squat.",
                "priority": "medium"
            })

        if not tips:
            tips.append({
                "tip": "Solid shooting mechanics! Work on arc consistency and follow-through hold time.",
                "priority": "low"
            })

        return tips