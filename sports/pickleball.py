from typing import Dict, Any, List
from sports.base import SportAnalyzer


class PickleballAnalyzer(SportAnalyzer):
    name = "pickleball"

    IDEAL_ELBOW_MIN = 110
    IDEAL_ELBOW_MAX = 155
    IDEAL_SHOULDER_MIN = 30
    IDEAL_SHOULDER_MAX = 70
    IDEAL_KNEE_MIN = 140
    IDEAL_KNEE_MAX = 168

    def analyze(self, angle_data: Dict[str, Any]) -> Dict[str, Any]:
        elbow_angles = angle_data.get("elbow", [])
        shoulder_angles = angle_data.get("shoulder", [])
        knee_angles = angle_data.get("knee", [])
        hip_angles = angle_data.get("hip", [])

        if not elbow_angles:
            return {"error": "No arm angle data — ensure your paddle arm is fully visible"}

        avg_elbow = self._safe_avg(elbow_angles)
        avg_shoulder = self._safe_avg(shoulder_angles) if shoulder_angles else None
        avg_knee = self._safe_avg(knee_angles) if knee_angles else None
        avg_hip = self._safe_avg(hip_angles) if hip_angles else None

        elbow_consistency = self._consistency_pct(
            elbow_angles, self.IDEAL_ELBOW_MIN, self.IDEAL_ELBOW_MAX
        )
        elbow_std = self._std_dev(elbow_angles)

        return {
            "avg_elbow_angle": round(avg_elbow, 1),
            "avg_shoulder_angle": round(avg_shoulder, 1) if avg_shoulder else None,
            "avg_knee_angle": round(avg_knee, 1) if avg_knee else None,
            "avg_hip_angle": round(avg_hip, 1) if avg_hip else None,
            "elbow_consistency_pct": elbow_consistency,
            "elbow_std_dev": round(elbow_std, 1),
        }

    def score(self, metrics: Dict[str, Any]) -> int:
        if "error" in metrics:
            return 30

        elbow = metrics.get("avg_elbow_angle", 0)
        shoulder = metrics.get("avg_shoulder_angle")
        knee = metrics.get("avg_knee_angle")
        consistency = metrics.get("elbow_consistency_pct", 0)
        std_dev = metrics.get("elbow_std_dev", 999)

        # Factor 1: Paddle arm position (30%)
        if self.IDEAL_ELBOW_MIN <= elbow <= self.IDEAL_ELBOW_MAX:
            elbow_score = 88
        elif 90 <= elbow < self.IDEAL_ELBOW_MIN:
            elbow_score = 65
        elif self.IDEAL_ELBOW_MAX < elbow <= 170:
            elbow_score = 60
        else:
            elbow_score = 35

        # Factor 2: Consistency (25%)
        if consistency >= 65:
            consistency_score = 88
        elif consistency >= 45:
            consistency_score = 68
        elif consistency >= 25:
            consistency_score = 48
        else:
            consistency_score = 28

        # Factor 3: Stability (20%)
        if std_dev < 12:
            stability_score = 88
        elif std_dev < 22:
            stability_score = 68
        elif std_dev < 32:
            stability_score = 48
        else:
            stability_score = 28

        # Factor 4: Shoulder preparation (15%)
        if shoulder and self.IDEAL_SHOULDER_MIN <= shoulder <= self.IDEAL_SHOULDER_MAX:
            shoulder_score = 85
        elif shoulder and 20 <= shoulder < self.IDEAL_SHOULDER_MIN:
            shoulder_score = 60
        elif shoulder:
            shoulder_score = 40
        else:
            shoulder_score = 50

        # Factor 5: Athletic stance (10%)
        if knee and self.IDEAL_KNEE_MIN <= knee <= self.IDEAL_KNEE_MAX:
            knee_score = 85
        elif knee and 120 <= knee < self.IDEAL_KNEE_MIN:
            knee_score = 65
        elif knee:
            knee_score = 45
        else:
            knee_score = 55

        return self._score_from_factors([
            {"score": elbow_score,       "weight": 0.30},
            {"score": consistency_score, "weight": 0.25},
            {"score": stability_score,   "weight": 0.20},
            {"score": shoulder_score,    "weight": 0.15},
            {"score": knee_score,        "weight": 0.10},
        ])

    def feedback(self, metrics: Dict[str, Any]) -> List[str]:
        if "error" in metrics:
            return [{"tip": "Could not detect paddle motion. Ensure your full arm and paddle are visible.", "priority": "high"}]

        tips = []
        elbow = metrics.get("avg_elbow_angle")
        consistency = metrics.get("elbow_consistency_pct", 100)
        std_dev = metrics.get("elbow_std_dev", 0)
        knee = metrics.get("avg_knee_angle")

        if elbow is not None:
            if elbow < 95:
                tips.append({"tip": f"Arm too bent ({elbow:.0f}°) — extend your arm more through contact for better control.", "priority": "high"})
            elif elbow > 165:
                tips.append({"tip": f"Arm fully locked out ({elbow:.0f}°) — keep a slight bend to absorb the ball and reduce errors.", "priority": "medium"})

        if consistency < 40:
            tips.append({"tip": f"Very inconsistent paddle position ({consistency:.0f}% ideal) — focus on getting your paddle ready early.", "priority": "high"})
        elif consistency < 60:
            tips.append({"tip": f"Work on paddle preparation — get it up and ready before the ball arrives every time.", "priority": "medium"})

        if std_dev > 28:
            tips.append({"tip": "High shot variability — slow down your swing and focus on a compact consistent motion.", "priority": "medium"})

        if knee and knee < 128:
            tips.append({"tip": f"Stance too low ({knee:.0f}°) — stay athletic but don't over-crouch between shots.", "priority": "low"})

        if not tips:
            tips.append({"tip": "Solid pickleball mechanics! Focus on your third shot drop and kitchen domination.", "priority": "low"})

        return tips