from typing import Dict
from sports.base import SportAnalyzer
from sports.basketball import BasketballAnalyzer
from sports.golf import GolfAnalyzer
from sports.pickleball import PickleballAnalyzer
from sports.soccer import SoccerAnalyzer
from sports.tennis import TennisAnalyzer
from sports.baseball import BaseballAnalyzer

SPORT_REGISTRY: Dict[str, SportAnalyzer] = {
    "basketball": BasketballAnalyzer(),
    "golf": GolfAnalyzer(),
    "pickleball": PickleballAnalyzer(),
    "soccer": SoccerAnalyzer(),
    "tennis": TennisAnalyzer(),
    "baseball": BaseballAnalyzer(),
}


def get_sport_analyzer(name: str) -> SportAnalyzer:
    key = name.lower().strip()
    if key not in SPORT_REGISTRY:
        supported = ", ".join(SPORT_REGISTRY.keys())
        raise ValueError(f"Sport '{name}' not supported. Supported: {supported}")
    return SPORT_REGISTRY[key]


def get_supported_sports():
    return list(SPORT_REGISTRY.keys())