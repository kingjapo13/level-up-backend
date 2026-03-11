from typing import Dict, Any, List
from sports.base import SportAnalyzer


class GolfAnalyzer(SportAnalyzer):
    name = "golf"

    PHASES = [
        (30, "Address"),
        (90, "Backswing"),
        (130, "Downswing"),
        (float("inf"), "Follow-through"),
    ]

    def analyze(self, angle_data: Dict[str, Any]) -> Dict[str, Any]:
        shoulder_angles = angle_data.get("shoulder", [])
        hip_angles = angle_data.get("hip", [])
        elbow_angles = angle_data.get("elbow", [])

        if not shoulder_angles:
            return {"error": "No shoulder angle data available"}

        avg_shoulder = sum(shoulder_angles) / len(shoulder_angles)
        max_shoulder = max(shoulder_angles)
        avg_hip = sum(hip_angles) / len(hip_angles) if hip_angles else None
        avg_elbow = sum(elbow_angles) / len(elbow_angles) if elbow_angles else None

        xfactor = None
        if hip_angles and shoulder_angles:
            separations = [abs(s - h) for s, h in zip(shoulder_angles, hip_angles)]
            xfactor = round(max(separations), 1)

        return {
            "avg_shoulder_angle": round(avg_shoulder, 1),
            "max_shoulder_rotation": round(max_shoulder, 1),
            "avg_hip_angle": round(avg_hip, 1) if avg_hip else None,
            "avg_elbow_angle": round(avg_elbow, 1) if avg_elbow else None,
            "xfactor_separation": xfactor,
            "swing_phase": self._detect_phase(avg_shoulder),
        }

    def score(self, metrics: Dict[str, Any]) -> int:
        if "error" in metrics:
            return 0
        score = 70
        xfactor = metrics.get("xfactor_separation")
        if xfactor is not None:
            if xfactor >= 40:
                score += 20
            elif xfactor >= 25:
                score += 10
            else:
                score -= 15
        max_rotation = metrics.get("max_shoulder_rotation", 0)
        if max_rotation >= 90:
            score += 10
        elif max_rotation < 60:
            score -= 10
        return max(0, min(100, score))

    def feedback(self, metrics: Dict[str, Any]) -> List[str]:
        tips = []
        if "error" in metrics:
            return ["Could not detect swing. Ensure your full body is visible."]
        xfactor = metrics.get("xfactor_separation")
        if xfactor is not None and xfactor < 25:
            tips.append(f"Low hip-shoulder separation ({xfactor:.0f}°) — rotate hips earlier for more power.")
        max_rotation = metrics.get("max_shoulder_rotation", 0)
        if max_rotation < 80:
            tips.append(f"Shoulder rotation is limited ({max_rotation:.0f}°) — work on a fuller backswing.")
        if not tips:
            tips.append("Solid swing mechanics! Focus on tempo and consistent ball position.")
        return tips

    def _detect_phase(self, avg_shoulder: float) -> str:
        for threshold, phase in self.PHASES:
            if avg_shoulder < threshold:
                return phase
        return "Follow-through"