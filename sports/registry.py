import logging
from typing import Dict
from sports.base import SportAnalyzer

logger = logging.getLogger(__name__)

# ── Import all sport analyzers ────────────────────────────────────────────────

try:
    from sports.basketball import BasketballAnalyzer
    _basketball = BasketballAnalyzer()
except Exception as e:
    logger.warning(f"BasketballAnalyzer failed to load: {e}")
    _basketball = None

try:
    from sports.golf import GolfAnalyzer
    _golf = GolfAnalyzer()
except Exception as e:
    logger.warning(f"GolfAnalyzer failed to load: {e}")
    _golf = None

try:
    from sports.pickleball import PickleballAnalyzer
    _pickleball = PickleballAnalyzer()
except Exception as e:
    logger.warning(f"PickleballAnalyzer failed to load: {e}")
    _pickleball = None

try:
    from sports.soccer import SoccerAnalyzer
    _soccer = SoccerAnalyzer()
except Exception as e:
    logger.warning(f"SoccerAnalyzer failed to load: {e}")
    _soccer = None

try:
    from sports.tennis import TennisAnalyzer
    _tennis = TennisAnalyzer()
except Exception as e:
    logger.warning(f"TennisAnalyzer failed to load: {e}")
    _tennis = None

try:
    from sports.baseball import BaseballAnalyzer
    _baseball = BaseballAnalyzer()
except Exception as e:
    logger.warning(f"BaseballAnalyzer failed to load: {e}")
    _baseball = None

try:
    from sports.volleyball import VolleyballAnalyzer
    _volleyball = VolleyballAnalyzer()
except Exception as e:
    logger.warning(f"VolleyballAnalyzer failed to load: {e}")
    _volleyball = None

try:
    from sports.boxing import BoxingAnalyzer
    _boxing = BoxingAnalyzer()
except Exception as e:
    logger.warning(f"BoxingAnalyzer failed to load: {e}")
    _boxing = None

try:
    from sports.squat import SquatAnalyzer
    _squat = SquatAnalyzer()
except Exception as e:
    logger.warning(f"SquatAnalyzer failed to load: {e}")
    _squat = None

try:
    from sports.curl import CurlAnalyzer
    _curl = CurlAnalyzer()
except Exception as e:
    logger.warning(f"CurlAnalyzer failed to load: {e}")
    _curl = None


# ── Build registry ─────────────────────────────────────────────────────────────

def _build_registry() -> Dict[str, SportAnalyzer]:
    registry = {}

    # Core sports
    if _basketball:
        registry["basketball"] = _basketball
    if _golf:
        registry["golf"] = _golf
    if _soccer:
        registry["soccer"] = _soccer
    if _tennis:
        registry["tennis"] = _tennis
    if _baseball:
        registry["baseball"] = _baseball
    if _volleyball:
        registry["volleyball"] = _volleyball
    if _boxing:
        registry["boxing"] = _boxing
    if _pickleball:
        registry["pickleball"] = _pickleball

    # New sports — use closest analyzer as fallback
    # Swimming uses shoulder/hip movement similar to volleyball
    if _volleyball:
        registry["swimming"] = _volleyball
    elif _basketball:
        registry["swimming"] = _basketball

    # Water polo uses arm/throwing motion similar to basketball
    if _basketball:
        registry["waterpolo"] = _basketball
    elif _volleyball:
        registry["waterpolo"] = _volleyball

    # Badminton uses racket swing similar to tennis
    if _tennis:
        registry["badminton"] = _tennis
    elif _basketball:
        registry["badminton"] = _basketball

    # Legacy sports (keep for existing users)
    if _squat:
        registry["squat"] = _squat
    if _curl:
        registry["curl"] = _curl

    logger.info(f"Sport registry loaded: {list(registry.keys())}")
    return registry


SPORT_REGISTRY = _build_registry()


def get_sport_analyzer(name: str) -> SportAnalyzer:
    """Returns the analyzer for the given sport name."""
    key = name.lower().strip()

    if key in SPORT_REGISTRY:
        return SPORT_REGISTRY[key]

    # Fuzzy match — try partial name matching
    for registered_name, analyzer in SPORT_REGISTRY.items():
        if key in registered_name or registered_name in key:
            logger.info(f"Fuzzy matched sport '{key}' to '{registered_name}'")
            return analyzer

    # Final fallback — use basketball analyzer
    if _basketball:
        logger.warning(f"Sport '{key}' not found, using basketball analyzer as fallback")
        return _basketball

    supported = ", ".join(SPORT_REGISTRY.keys())
    raise ValueError(f"Sport '{name}' not supported. Supported: {supported}")


def get_supported_sports():
    """Returns list of all supported sport names."""
    return list(SPORT_REGISTRY.keys())


def is_sport_supported(name: str) -> bool:
    """Check if a sport is supported."""
    return name.lower().strip() in SPORT_REGISTRY