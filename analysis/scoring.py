import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

REP_SCORE_VALUE = 5
REP_SCORE_CAP = 70
FORM_PENALTY = 10
CONSISTENCY_BONUS = 10
CONSISTENCY_THRESHOLD = 15.0


def calculate_score(
    reps: int,
    bad_form_issues: List[str],
    angle_list: Optional[List[float]] = None,
) -> int:
    base_score = min(reps * REP_SCORE_VALUE, REP_SCORE_CAP)
    penalty = len(bad_form_issues) * FORM_PENALTY
    bonus = 0

    if angle_list:
        valid_angles = [a for a in angle_list if a is not None]
        if len(valid_angles) > 1:
            import numpy as np
            std_dev = float(np.std(valid_angles))
            if std_dev < CONSISTENCY_THRESHOLD:
                bonus = CONSISTENCY_BONUS

    final_score = base_score - penalty + bonus
    return max(min(final_score, 100), 0)