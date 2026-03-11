from abc import ABC, abstractmethod
from typing import Dict, Any, List


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