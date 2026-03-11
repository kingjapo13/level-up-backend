import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


def count_reps(
    angle_list: List[Optional[float]],
    down_threshold: float = 70.0,
    up_threshold: float = 160.0,
) -> int:
    reps = 0
    stage = "up"

    valid_angles = [a for a in angle_list if a is not None]

    if not valid_angles:
        logger.warning("count_reps received no valid angles.")
        return 0

    for angle in valid_angles:
        if angle < down_threshold:
            stage = "down"
        elif angle > up_threshold and stage == "down":
            stage = "up"
            reps += 1

    return reps