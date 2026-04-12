from abc import ABC, abstractmethod
from typing import Dict, Any, List
import math


class SportAnalyzer(ABC):
    name: str

    @abstractmethod
    def analyze(self, angle_data: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def score(self, metrics: Dict[str, Any]) -> int:
        pass

    @abstractmethod
    def feedback(self, metrics: Dict[str, Any]) -> List[str]:
        pass

    def full_analysis(self, angle_data: Dict[str, Any]) -> Dict[str, Any]:
        metrics = self.analyze(angle_data)
        performance_score = self.score(metrics)
        coaching_tips = self.feedback(metrics)
        return {
            "sport": self.name,
            "score": performance_score,
            "metrics": metrics,
            "feedback": coaching_tips,
        }

    # ── Shared helpers ────────────────────────────────────────────────────

    def _safe_avg(self, values: List[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    def _consistency_pct(self, values: List[float], low: float, high: float) -> float:
        if not values:
            return 0.0
        ideal = [v for v in values if low <= v <= high]
        return round(len(ideal) / len(values) * 100, 1)

    def _std_dev(self, values: List[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return math.sqrt(variance)

    def _clamp(self, value: int, low: int = 20, high: int = 96) -> int:
        return max(low, min(high, value))

    def _score_from_factors(self, factors: List[Dict]) -> int:
        """
        factors = [
            {"score": 0-100, "weight": 0.0-1.0},
            ...
        ]
        weights should sum to 1.0
        Returns weighted score clamped to 20-96
        """
        total = sum(f["score"] * f["weight"] for f in factors)
        return self._clamp(round(total))