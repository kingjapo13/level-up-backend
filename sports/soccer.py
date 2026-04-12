from typing import Dict, Any, List
from sports.base import SportAnalyzer


class SoccerAnalyzer(SportAnalyzer):
    name = "soccer"

    IDEAL_KNEE_SWING_MIN = 60
    IDEAL_KNEE_SWING_MAX = 110
    IDEAL_HIP_MIN = 55
    IDEAL_HIP_MAX = 90
    IDEAL_ANKLE_MIN = 80
    IDEAL_ANKLE_MAX = 115

    def analyze(self, angle_data: Dict[str, Any]) -> Dict[str, Any]:
        knee_angles = angle_data.get("knee", [])
        hip_angles = angle_data.get("hip", [])
        ankle_angles = angle_data.get("ankle", [])
        shoulder_angles = angle_data.get("shoulder", [])

        if not knee_angles:
            return {"error": "No leg angle data — ensure full body is visible"}

        avg_knee = self._safe_avg(knee_angles)
        avg_hip = self._safe_avg(hip_angles) if hip_angles else None
        avg_ankle = self._safe_avg(ankle_angles) if ankle_angles else None
        avg_shoulder = self._safe_avg(shoulder_angles) if shoulder_angles else None

        knee_range = max(knee_angles) - min(knee_angles) if len(knee_angles) > 1 else 0
        hip_range = max(hip_angles) - min(hip_angles) if hip_angles and len(hip_angles) > 1 else 0

        return {
            "avg_knee_angle": round(avg_knee, 1),
            "avg_hip_angle": round(avg_hip, 1) if avg_hip else None,
            "avg_ankle_angle": round(avg_ankle, 1) if avg_ankle else None,
            "avg_shoulder_angle": round(avg_shoulder, 1) if avg_shoulder else None,
            "knee_range": round(knee_range, 1),
            "hip_range": round(hip_range, 1),
        }

    def score(self, metrics: Dict[str, Any]) -> int:
        if "error" in metrics:
            return 30

        knee = metrics.get("avg_knee_angle", 0)
        hip = metrics.get("avg_hip_angle")
        ankle = metrics.get("avg_ankle_angle")
        knee_range = metrics.get("knee_range", 0)
        hip_range = metrics.get("hip_range", 0)

        # Factor 1: Kicking knee swing (25%)
        if self.IDEAL_KNEE_SWING_MIN <= knee <= self.IDEAL_KNEE_SWING_MAX:
            knee_score = 88
        elif 45 <= knee < self.IDEAL_KNEE_SWING_MIN:
            knee_score = 65
        elif self.IDEAL_KNEE_SWING_MAX < knee <= 135:
            knee_score = 60
        else:
            knee_score = 35

        # Factor 2: Hip drive through ball (25%)
        if hip and self.IDEAL_HIP_MIN <= hip <= self.IDEAL_HIP_MAX:
            hip_score = 88
        elif hip and 40 <= hip < self.IDEAL_HIP_MIN:
            hip_score = 62
        elif hip:
            hip_score = 42
        else:
            hip_score = 50

        # Factor 3: Ankle lock at contact (20%)
        if ankle and self.IDEAL_ANKLE_MIN <= ankle <= self.IDEAL_ANKLE_MAX:
            ankle_score = 88
        elif ankle and 65 <= ankle < self.IDEAL_ANKLE_MIN:
            ankle_score = 55
        elif ankle:
            ankle_score = 40
        else:
            ankle_score = 50

        # Factor 4: Knee range of motion / full swing (15%)
        if knee_range >= 60:
            knee_range_score = 90
        elif knee_range >= 40:
            knee_range_score = 70
        elif knee_range >= 20:
            knee_range_score = 50
        else:
            knee_range_score = 30

        # Factor 5: Hip mobility range (15%)
        if hip_range >= 35:
            hip_range_score = 88
        elif hip_range >= 20:
            hip_range_score = 65
        else:
            hip_range_score = 40

        return self._score_from_factors([
            {"score": knee_score,       "weight": 0.25},
            {"score": hip_score,        "weight": 0.25},
            {"score": ankle_score,      "weight": 0.20},
            {"score": knee_range_score, "weight": 0.15},
            {"score": hip_range_score,  "weight": 0.15},
        ])

    def feedback(self, metrics: Dict[str, Any]) -> List[str]:
        if "error" in metrics:
            return [{"tip": "Could not detect kicking motion. Ensure full body is visible from the side.", "priority": "high"}]

        tips = []
        knee = metrics.get("avg_knee_angle")
        hip = metrics.get("avg_hip_angle")
        ankle = metrics.get("avg_ankle_angle")
        knee_range = metrics.get("knee_range", 0)

        if knee is not None:
            if knee < 50:
                tips.append({"tip": f"Knee not swinging through fully ({knee:.0f}°) — drive your knee forward and follow through completely.", "priority": "high"})
            elif knee > 130:
                tips.append({"tip": f"Planting leg too bent ({knee:.0f}°) — keep your plant leg more stable for better power transfer.", "priority": "medium"})

        if hip is not None and hip < 45:
            tips.append({"tip": f"Limited hip drive ({hip:.0f}°) — rotate your hips through the ball, not just your leg.", "priority": "high"})

        if ankle is not None and ankle < 70:
            tips.append({"tip": f"Ankle not locked at contact ({ankle:.0f}°) — point your toes down and lock your ankle for accuracy and power.", "priority": "high"})

        if knee_range < 25:
            tips.append({"tip": "Short kicking motion detected — take a fuller backswing with your kicking leg.", "priority": "medium"})

        if not tips:
            tips.append({"tip": "Good kicking mechanics! Focus on your follow-through direction to improve accuracy.", "priority": "low"})

        return tips