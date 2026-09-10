"""Direction normalization shared by public camera views and sprite renderers."""

from __future__ import annotations

from typing import Any

CARDINAL_RENDER_DIRECTIONS = (0, 4, 8, 12)


def normalize_render_direction(value: Any, *, index_direction: bool = False) -> int:
    """Map a Factorio direction value to a cardinal sprite-renderer key.

    Sprite renderers ship four cardinal sprites keyed by Factorio 2.0 values
    (0/4/8/12). Inputs may be 16-direction values (0-15, diagonals on even
    values), legacy 8-direction indices (0-7, only when ``index_direction``),
    floats, or missing. Non-cardinal values snap to the nearest cardinal.
    """

    try:
        direction = int(round(float(value)))
    except (TypeError, ValueError):
        return 0
    if direction in CARDINAL_RENDER_DIRECTIONS:
        return direction
    if index_direction and 0 <= direction <= 7:
        direction = (direction * 2) % 16
    direction %= 16
    return ((direction + 2) // 4 * 4) % 16
