import logging
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLDS = {
    "min_bend_angle": 90.0,
    "full_extension_angle": 150.0,
    "min_range_of_motion": 40.0,
}


def detect_bad_form(
    angle_list: List[Optional[float]],
    thresholds: Optional[Dict[str, float]] = None,
) -> List[str]:
    issues = []

    valid_angles = [a for a in angle_list if a is not None]
    if not valid_angles:
        return issues

    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    min_angle = min(valid_angles)
    max_angle = max(valid_angles)
    range_of_motion = max_angle - min_angle

    if min_angle > t["min_bend_angle"]:
        issues.append(
            f"Not bending deep enough — lowest angle was {min_angle:.1f}° "
            f"(target: below {t['min_bend_angle']}°)"
        )

    if max_angle < t["full_extension_angle"]:
        issues.append(
            f"Not fully extending — highest angle was {max_angle:.1f}° "
            f"(target: above {t['full_extension_angle']}°)"
        )

    if range_of_motion < t["min_range_of_motion"]:
        issues.append(
            f"Limited range of motion — only {range_of_motion:.1f}° of movement detected "
            f"(target: at least {t['min_range_of_motion']}°)"
        )

    return issues