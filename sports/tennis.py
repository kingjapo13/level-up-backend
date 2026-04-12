from typing import Dict, Any, List
from sports.base import SportAnalyzer


class TennisAnalyzer(SportAnalyzer):
    name = "tennis"

    IDEAL_ELBOW_MIN = 100
    IDEAL_ELBOW_MAX = 145
    IDEAL_SHOULDER_MIN = 45
    IDEAL_SHOULDER_MAX = 90
    IDEAL_HIP_MIN = 50
    IDEAL_HIP_MAX = 85

    def analyze(self, angle_data: Dict[str, Any]) -> Dict[str, Any]:
        elbow_angles = angle_data.get("elbow", [])
        shoulder_angles = angle_data.get("shoulder", [])
        hip_angles = angle_data.get("hip", [])
        knee_angles = angle_data.get("knee", [])

        if not elbow_angles and not shoulder_angles:
            return {"error": "No arm angle data — ensure full upper body is visible"}

        avg_elbow = self._safe_avg(elbow_angles) if elbow_angles else None
        avg_shoulder = self._safe_avg(shoulder_angles) if shoulder_angles else None
        avg_hip = self._safe_avg(hip_angles) if hip_angles else None
        avg_knee = self._safe_avg(knee_angles) if knee_angles else None

        elbow_consistency = self._consistency_pct(
            elbow_angles, self.IDEAL_ELBOW_MIN, self.IDEAL_ELBOW_MAX
        ) if elbow_angles else 0

        elbow_range = (max(elbow_angles) - min(elbow_angles)) if elbow_angles and len(elbow_angles) > 1 else 0

        return {
            "avg_elbow_angle": round(avg_elbow, 1) if avg_elbow else None,
            "avg_shoulder_angle": round(avg_shoulder, 1) if avg_shoulder else None,
            "avg_hip_angle": round(avg_hip, 1) if avg_hip else None,
            "avg_knee_angle": round(avg_knee, 1) if avg_knee else None,
            "elbow_consistency_pct": elbow_consistency,
            "elbow_range": round(elbow_range, 1),
        }

    def score(self, metrics: Dict[str, Any]) -> int:
        if "error" in metrics:
            return 30

        elbow = metrics.get("avg_elbow_angle")
        shoulder = metrics.get("avg_shoulder_angle")
        hip = metrics.get("avg_hip_angle")
        knee = metrics.get("avg_knee_angle")
        consistency = metrics.get("elbow_consistency_pct", 0)
        elbow_range = metrics.get("elbow_range", 0)

        # Factor 1: Elbow position at contact (25%)
        if elbow and self.IDEAL_ELBOW_MIN <= elbow <= self.IDEAL_ELBOW_MAX:
            elbow_score = 88
        elif elbow and 80 <= elbow < self.IDEAL_ELBOW_MIN:
            elbow_score = 65
        elif elbow and self.IDEAL_ELBOW_MAX < elbow <= 165:
            elbow_score = 60
        elif elbow:
            elbow_score = 35
        else:
            elbow_score = 50

        # Factor 2: Shoulder rotation (25%)
        if shoulder and self.IDEAL_SHOULDER_MIN <= shoulder <= self.IDEAL_SHOULDER_MAX:
            shoulder_score = 88
        elif shoulder and 30 <= shoulder < self.IDEAL_SHOULDER_MIN:
            shoulder_score = 60
        elif shoulder:
            shoulder_score = 45
        else:
            shoulder_score = 50

        # Factor 3: Hip rotation (20%)
        if hip and self.IDEAL_HIP_MIN <= hip <= self.IDEAL_HIP_MAX:
            hip_score = 85
        elif hip and 35 <= hip < self.IDEAL_HIP_MIN:
            hip_score = 60
        elif hip:
            hip_score = 40
        else:
            hip_score = 50

        # Factor 4: Swing arc range of motion (15%)
        if elbow_range >= 50:
            arc_score = 88
        elif elbow_range >= 30:
            arc_score = 68
        elif elbow_range >= 15:
            arc_score = 48
        else:
            arc_score = 30

        # Factor 5: Knee bend / ready position (15%)
        if knee and 130 <= knee <= 165:
            knee_score = 85
        elif knee and 115 <= knee < 130:
            knee_score = 65
        elif knee:
            knee_score = 45
        else:
            knee_score = 50

        return self._score_from_factors([
            {"score": elbow_score,    "weight": 0.25},
            {"score": shoulder_score, "weight": 0.25},
            {"score": hip_score,      "weight": 0.20},
            {"score": arc_score,      "weight": 0.15},
            {"score": knee_score,     "weight": 0.15},
        ])

    def feedback(self, metrics: Dict[str, Any]) -> List[str]:
        if "error" in metrics:
            return [{"tip": "Could not detect tennis stroke. Ensure full body is visible from the side.", "priority": "high"}]

        tips = []
        elbow = metrics.get("avg_elbow_angle")
        shoulder = metrics.get("avg_shoulder_angle")
        hip = metrics.get("avg_hip_angle")
        elbow_range = metrics.get("elbow_range", 0)

        if elbow is not None:
            if elbow < 85:
                tips.append({"tip": f"Arm too bent at contact ({elbow:.0f}°) — extend toward the ball for more power and control.", "priority": "high"})
            elif elbow > 160:
                tips.append({"tip": f"Arm too straight ({elbow:.0f}°) — keep a slight bend to absorb pace and generate topspin.", "priority": "medium"})

        if shoulder is not None and shoulder < 35:
            tips.append({"tip": f"Limited shoulder rotation ({shoulder:.0f}°) — turn your shoulders fully on the takeback for more power.", "priority": "high"})

        if hip is not None and hip < 40:
            tips.append({"tip": f"Hips not rotating through the shot ({hip:.0f}°) — drive your hips toward the target at contact.", "priority": "high"})

        if elbow_range < 20:
            tips.append({"tip": "Very short swing arc detected — take a fuller backswing to generate pace.", "priority": "medium"})

        if not tips:
            tips.append({"tip": "Good stroke mechanics! Focus on consistent contact point and finishing high over your shoulder.", "priority": "low"})

        return tips