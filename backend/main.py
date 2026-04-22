"""Industrial digital twin core: pick fusion + modular engine pipeline (layout, geometry, collision, web payload)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Tuple

import cv2

from backend.api import load_equipment_from_excel
from backend.engines import collision_engine, web_ui
from backend.engines.scene import build_scene_document
from backend.pickpoint import PICKPOINT_TAGS, pick_points_on_plan

PLAN_MM = 17500.0


def _default_plan_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "plan_hd.png"


def _plan_image_size(path: Path) -> Tuple[int, int]:
    """Return (image_width, image_height) in pixels."""
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Cannot read image (missing or unsupported format): {path}")
    h, w = img.shape[:2]
    return w, h


def build_final_data(
    pixels: Mapping[str, Tuple[int, int]],
    equipment: Mapping[str, Mapping[str, Any]],
    image_width: int,
    image_height: int,
) -> List[Dict[str, Any]]:
    """Merge pixels and Excel rows in PICKPOINT_TAGS order; convert pixels to mm using plan scale."""
    if image_width <= 0:
        raise ValueError(f"image_width must be positive, got {image_width}")
    scale = PLAN_MM / float(image_width)

    final_data: List[Dict[str, Any]] = []
    for tag in PICKPOINT_TAGS:
        if tag not in pixels:
            raise ValueError(f"Missing pick point for tag {tag!r}")
        if tag not in equipment:
            raise ValueError(f"Missing Excel row for tag {tag!r}")

        x_px, y_px = pixels[tag]
        row = equipment[tag]
        x_mm = float(x_px) * scale
        y_mm = float(image_height - y_px) * scale

        entry: MutableMapping[str, Any] = {
            "tag": tag,
            "service": row["service"],
            "position": row["position"],
            "pixel": {"x": int(x_px), "y": int(y_px)},
            "mm": {"x": x_mm, "y": y_mm},
            "diameter": row["diameter"],
            "length": row["length"],
            "height": row["height"],
        }
        final_data.append(dict(entry))
    return final_data


def run_engine_pipeline(equipment: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    """
    Unified chain (no UI, no frontend):

    equipements -> layout_engine + geometry_engine (via build_scene_document) ->
    collision_engine -> web_ui
    """
    scene = build_scene_document(equipment)
    scene["collisions"] = collision_engine(scene)
    return web_ui(scene)


def run_pick_fusion(plan_path: Path | None = None, excel_path: Path | None = None) -> List[Dict[str, Any]]:
    """Interactive pick points + Excel merge (legacy fusion path)."""
    plan = plan_path if plan_path is not None else _default_plan_path()
    image_width, image_height = _plan_image_size(plan)

    pixels = pick_points_on_plan(plan)
    equipment = load_equipment_from_excel(excel_path)
    return build_final_data(pixels, equipment, image_width, image_height)


def main(
    excel_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run core engine pipeline on equipment loaded from Excel (headless)."""
    equipment = load_equipment_from_excel(excel_path)
    return run_engine_pipeline(equipment)


if __name__ == "__main__":
    out = main()
    print(json.dumps(out, ensure_ascii=False, indent=2))
