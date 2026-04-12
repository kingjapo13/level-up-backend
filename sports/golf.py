from typing import Dict, Any, List
from sports.base import SportAnalyzer


class GolfAnalyzer(SportAnalyzer):
    name = "golf"

    IDEAL_SHOULDER_TURN_MIN = 35
    IDEAL_SHOULDER_TURN_MAX = 65
    IDEAL_HIP_MIN = 40
    IDEAL_HIP_MAX = 75
    IDEAL_ELBOW_MIN = 150
    IDEAL_ELBOW_MAX = 175

    def analyze(self, angle_data: Dict[str, Any]) -> Dict[str, Any]:
        shoulder_angles = angle_data.get("shoulder", [])
        hip_angles = angle_data.get("hip", [])
        elbow_angles = angle_data.get("elbow", [])
        knee_angles = angle_data.get("knee", [])

        if not shoulder_angles:
            return {"error": "No shoulder angle data — ensure full upper body is visible"}

        avg_shoulder = self._safe_avg(shoulder_angles)
        avg_hip = self._safe_avg(hip_angles) if hip_angles else None
        avg_elbow = self._safe_avg(elbow_angles) if elbow_angles else None
        avg_knee = self._safe_avg(knee_angles) if knee_angles else None

        shoulder_range = max(shoulder_angles) - min(shoulder_angles) if len(shoulder_angles) > 1 else 0
        hip_range = max(hip_angles) - min(hip_angles) if hip_angles and len(hip_angles) > 1 else 0

        return {
            "avg_shoulder_angle": round(avg_shoulder, 1),
            "avg_hip_angle": round(avg_hip, 1) if avg_hip else None,
            "avg_elbow_angle": round(avg_elbow, 1) if avg_elbow else None,
            "avg_knee_angle": round(avg_knee, 1) if avg_knee else None,
            "shoulder_range": round(shoulder_range, 1),
            "hip_range": round(hip_range, 1),
        }

    def score(self, metrics: Dict[str, Any]) -> int:
        if "error" in metrics:
            return 30

        shoulder = metrics.get("avg_shoulder_angle", 0)
        hip = metrics.get("avg_hip_angle")
        elbow = metrics.get("avg_elbow_angle")
        shoulder_range = metrics.get("shoulder_range", 0)
        hip_range = metrics.get("hip_range", 0)

        # Factor 1: Shoulder turn rotation (25%)
        if self.IDEAL_SHOULDER_TURN_MIN <= shoulder <= self.IDEAL_SHOULDER_TURN_MAX:
            shoulder_score = 88
        elif 25 <= shoulder < self.IDEAL_SHOULDER_TURN_MIN:
            shoulder_score = 65
        elif self.IDEAL_SHOULDER_TURN_MAX < shoulder <= 80:
            shoulder_score = 70
        else:
            shoulder_score = 40

        # Factor 2: Hip rotation (25%)
        if hip and self.IDEAL_HIP_MIN <= hip <= self.IDEAL_HIP_MAX:
            hip_score = 88
        elif hip and 30 <= hip < self.IDEAL_HIP_MIN:
            hip_score = 60
        elif hip:
            hip_score = 45
        else:
            hip_score = 50

        # Factor 3: Lead arm extension (20%)
        if elbow and self.IDEAL_ELBOW_MIN <= elbow <= self.IDEAL_ELBOW_MAX:
            elbow_score = 88
        elif elbow and 130 <= elbow < self.IDEAL_ELBOW_MIN:
            elbow_score = 60
        elif elbow:
            elbow_score = 40
        else:
            elbow_score = 50

        # Factor 4: Shoulder turn range of motion (15%)
        if shoulder_range >= 40:
            range_score = 90
        elif shoulder_range >= 25:
            range_score = 70
        elif shoulder_range >= 15:
            range_score = 50
        else:
            range_score = 30

        # Factor 5: Hip sequencing range (15%)
        if hip_range >= 30:
            hip_range_score = 88
        elif hip_range >= 15:
            hip_range_score = 65
        else:
            hip_range_score = 40

        return self._score_from_factors([
            {"score": shoulder_score,    "weight": 0.25},
            {"score": hip_score,         "weight": 0.25},
            {"score": elbow_score,       "weight": 0.20},
            {"score": range_score,       "weight": 0.15},
            {"score": hip_range_score,   "weight": 0.15},
        ])

    def feedback(self, metrics: Dict[str, Any]) -> List[str]:
        if "error" in metrics:
            return [{"tip": "Could not detect golf swing. Ensure full body is visible from the side.", "priority": "high"}]

        tips = []
        shoulder = metrics.get("avg_shoulder_angle")
        hip = metrics.get("avg_hip_angle")
        elbow = metrics.get("avg_elbow_angle")
        shoulder_range = metrics.get("shoulder_range", 0)

        if shoulder is not None:
            if shoulder < 30:
                tips.append({"tip": f"Shoulder turn too restricted ({shoulder:.0f}°) — rotate fully until your back faces the target.", "priority": "high"})
            elif shoulder > 75:
                tips.append({"tip": f"Over-rotating shoulders ({shoulder:.0f}°) — keep your spine angle consistent through the backswing.", "priority": "medium"})

        if hip is not None and hip < 35:
            tips.append({"tip": f"Hips not clearing through impact ({hip:.0f}°) — drive your lead hip toward the target on the downswing.", "priority": "high"})

        if elbow is not None and elbow < 140:
            tips.append({"tip": f"Lead arm bending too much ({elbow:.0f}°) — keep your lead arm straighter through the backswing for a wider arc.", "priority": "medium"})

        if shoulder_range < 20:
            tips.append({"tip": "Very limited swing rotation detected — film from directly behind to check your full turn.", "priority": "high"})

        if not tips:
            tips.append({"tip": "Good swing mechanics! Focus on tempo — count 1-2-3 on backswing, accelerate through impact.", "priority": "low"})

        return tips