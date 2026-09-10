"""Bounded public camera projections shared by envd and model transports."""

from __future__ import annotations

import base64
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from fle.commons.directions import (
    CARDINAL_RENDER_DIRECTIONS,
    normalize_render_direction,
)

__all__ = [
    "CARDINAL_RENDER_DIRECTIONS",
    "CameraSettings",
    "compact_terrain",
    "normalize_render_direction",
    "persist_camera_snapshot",
    "render_coarse_map",
]


class CameraSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    radius: int = Field(default=32, ge=8, le=192)
    entity_limit: int = Field(default=32, ge=1, le=128)


def persist_camera_snapshot(directory: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Publish one atomic latest view and deduplicate its immutable PNG asset."""
    result = dict(payload)
    directory.mkdir(parents=True, exist_ok=True)
    encoded = result.get("image_base64")
    if isinstance(encoded, str):
        png = base64.b64decode(encoded, validate=True)
        digest = hashlib.sha256(png).hexdigest()
        renders = directory / "renders"
        renders.mkdir(exist_ok=True)
        path = renders / f"camera-{digest}.png"
        if not path.exists():
            path.write_bytes(png)
        result["artifact"] = {"id": f"camera-{digest}", "sha256": digest}
    metadata = {key: value for key, value in result.items() if key != "image_base64"}
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=directory, delete=False
    ) as stream:
        json.dump(metadata, stream, separators=(",", ":"))
        temporary = Path(stream.name)
    temporary.replace(directory / "camera-latest.json")
    return result


def compact_terrain(view: dict[str, Any]) -> dict[str, Any]:
    """Encode overlapping coarse layers without hundreds of verbose cell objects."""
    if not view.get("available"):
        return dict(view)
    width, height = int(view["width"]), int(view["height"])
    layers: dict[str, list[list[str]]] = {}

    def mark(layer: str, row: int, column: int, value: str = "1") -> None:
        grid = layers.setdefault(
            layer, [["." for _ in range(width)] for _ in range(height)]
        )
        grid[row][column] = value

    for cell in view.get("cells", []):
        row, column = int(cell["row"]), int(cell["column"])
        if cell.get("unknown"):
            mark("unknown", row, column)
            continue
        for key in (
            "water",
            "blocked_tiles",
            "trees",
            "cliffs",
            "occupied",
            "obstacles",
        ):
            if cell.get(key):
                mark(key, row, column)
        for resource, count in (cell.get("resources") or {}).items():
            if count:
                mark(resource, row, column)
    result = {key: value for key, value in view.items() if key != "cells"}
    result["terrain_layers"] = {
        key: ["".join(row) for row in grid] for key, grid in sorted(layers.items())
    }
    result["terrain_legend"] = (
        "1=present somewhere in cell; .=absent; unknown layer overrides absence"
    )
    return result


def render_coarse_map(view: dict[str, Any]) -> bytes:
    """Render large-radius public map facts without materializing tile sprites."""
    from io import BytesIO

    from PIL import Image, ImageDraw

    size = 768
    image = Image.new("RGB", (size, size), "#17211b")
    draw = ImageDraw.Draw(image)
    width, height = int(view["width"]), int(view["height"])
    scale = size / max(width, height)
    colors = {
        "iron-ore": "#8aa5b5",
        "copper-ore": "#d98449",
        "coal": "#24282b",
        "stone": "#d4c797",
        "uranium-ore": "#85bd35",
        "crude-oil": "#d16cd5",
    }
    for cell in view.get("cells", []):
        x, y = int(cell["column"]) * scale, int(cell["row"]) * scale
        color = "#080c10" if cell.get("unknown") else "#516345"
        if cell.get("water"):
            color = "#285b80"
        draw.rectangle((x, y, x + scale, y + scale), fill=color, outline="#344238")
        if cell.get("trees"):
            draw.ellipse(
                (x + scale * 0.2, y + scale * 0.2, x + scale * 0.8, y + scale * 0.8),
                fill="#253f25",
            )
        if cell.get("cliffs"):
            draw.line(
                (x, y + scale * 0.5, x + scale, y + scale * 0.5),
                fill="#c7bba1",
                width=3,
            )
        for index, resource in enumerate(sorted(cell.get("resources") or {})):
            offset = 3 + index * 5
            draw.rectangle(
                (x + offset, y + 3, x + offset + 4, y + scale - 3),
                fill=colors.get(resource, "white"),
            )
        if cell.get("occupied"):
            draw.rectangle(
                (x + scale * 0.4, y + scale * 0.4, x + scale * 0.6, y + scale * 0.6),
                fill="#edbd66",
            )
    origin, center = view["origin"], view["center"]
    unit = scale / int(view["cell_size"])
    x, y = (center["x"] - origin["x"]) * unit, (center["y"] - origin["y"]) * unit
    draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill="#ff7a24", outline="white", width=2)
    draw.text(
        (8, 8),
        f"Coarse map | {view['cell_size']} tiles/cell | N up",
        fill="white",
        stroke_width=1,
        stroke_fill="black",
    )
    draw.rectangle((0, size - 48, size, size), fill="#17211b")
    for index, (name, color) in enumerate(colors.items()):
        x = 8 + index * 126
        draw.rectangle((x, size - 42, x + 8, size - 34), fill=color)
        draw.text((x + 12, size - 44), name, fill="white")
    draw.text(
        (8, size - 22),
        "Blue: water | Circle: trees | Yellow: owned entities | Markers indicate presence within a cell",
        fill="white",
    )
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
