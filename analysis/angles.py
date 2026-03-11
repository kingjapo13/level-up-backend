import logging
import numpy as np
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


def calculate_angle(
    a: Tuple[float, float, float],
    b: Tuple[float, float, float],
    c: Tuple[float, float, float],
    use_3d: bool = False
) -> Optional[float]:
    try:
        if use_3d:
            a_arr = np.array(a[:3], dtype=float)
            b_arr = np.array(b[:3], dtype=float)
            c_arr = np.array(c[:3], dtype=float)
        else:
            a_arr = np.array(a[:2], dtype=float)
            b_arr = np.array(b[:2], dtype=float)
            c_arr = np.array(c[:2], dtype=float)

        ba = a_arr - b_arr
        bc = c_arr - b_arr

        magnitude_ba = np.linalg.norm(ba)
        magnitude_bc = np.linalg.norm(bc)

        if magnitude_ba == 0 or magnitude_bc == 0:
            return None

        cos_angle = np.dot(ba, bc) / (magnitude_ba * magnitude_bc)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        angle = np.degrees(np.arccos(cos_angle))
        return round(float(angle), 2)

    except Exception as e:
        logger.warning(f"calculate_angle failed: {e}")
        return None