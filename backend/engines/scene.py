"""Assemble scene document from equipment + detected plan positions (canonical shape in scene_spec).

Scene stage MUST NOT access the filesystem directly. All runtime-asset
dependencies are governed by `backend/asset_contract.py`.
"""

from __future__ import annotations

import logging
import cv2
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from backend.api import equipment_dict_to_list
from backend.asset_contract import (
    PLAN_IMAGE_CONTRACT,
    AssetContractViolation,
    load_asset,
)
from backend.core.execution_policy import resolve_execution_policy
from backend.core.input_contract import evaluate_input_contract
from backend.core.spatial_contract import SpatialMode, make_spatial_contract
from backend.core.spatial_truth_ledger import log_spatial_event, validate_contract_usage
from backend.engines.geometry import geometry_engine
from backend.locator import pixel_to_mm, resolve_spatial_positions_with_contract
from backend.scene_spec import build_equipment_list, empty_scene
from backend.walls import parse_walls_and_rooms


logger = logging.getLogger("industrial_digital_twin.scene")

SCENE_STAGE = "scene_render"


def safe_load_image(path: str) -> Optional[Any]:
    """Safe image read used by degraded mode guard."""
    img = cv2.imread(path)
    if img is None:
        return None
    return img


def _degraded_empty_layout(
    equipment: Mapping[str, Mapping[str, Any]],
    warning: str = "missing_demo_asset",
    input_contract: Optional[Dict[str, Any]] = None,
    spatial_contract: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return a safe empty-layout scene that keeps downstream contracts stable."""
    rows = equipment_dict_to_list(equipment)
    items = build_equipment_list(rows, positions_mm={})
    contract = input_contract or {}
    scene: Dict[str, Any] = empty_scene(
        {
            "layout": "empty",
            "warning": warning,
            "input_state": contract.get("state", "degraded_layout"),
            "input_contract": contract,
            "execution_policy": contract.get("execution_policy"),
            "spatial_contract": spatial_contract
            if isinstance(spatial_contract, dict)
            else make_spatial_contract(
                spatial_valid=False,
                spatial_mode=SpatialMode.DEGRADED,
                source="none",
                scene_allowed=False,
                visual_allowed=True,
                reason="layout_unavailable",
            ),
        }
    )
    scene["equipment"] = items
    scene["walls"] = []
    scene["rooms"] = []
    scene["center"] = [0.0, 0.0]
    return geometry_engine(scene)


def _extract_spatial_source(detected: Mapping[str, Any]) -> str:
    counts: Dict[str, int] = {}
    for value in detected.values():
        if isinstance(value, dict):
            src = str(value.get("source") or "unknown")
            counts[src] = counts.get(src, 0) + 1
    if not counts:
        return "none"
    return max(counts.items(), key=lambda kv: kv[1])[0]


def build_scene_document(
    equipment: Mapping[str, Mapping[str, Any]],
    plan_path: Optional[Path] = None,
    detected_positions: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """equipment (tag -> row) -> scene dict following backend/scene_spec.py.

    Position source priority: plan OCR/pickpoint -> mm conversion.
    The plan image asset is a contracted artifact; this stage only consumes
    it through the contract layer.
    """
    # Contract-governed input. Any violation surfaces as AssetContractViolation
    # which the API layer translates into a structured ASSET_* error.

    try:
        safe_plan = load_asset(PLAN_IMAGE_CONTRACT, stage=SCENE_STAGE, override_path=plan_path)
    except AssetContractViolation:
        logger.warning(
            "Layout image unavailable (demo or upload corrupted). Pipeline continues in degraded mode."
        )
        logger.warning(
            "Demo plan.png missing or corrupted, switching to empty layout mode"
        )
        contract = evaluate_input_contract(
            excel=equipment,
            layout_image=None,
            plan_path=None,
        )
        policy = resolve_execution_policy(contract)
        spatial_contract = make_spatial_contract(
            spatial_valid=False,
            spatial_mode=SpatialMode.DEGRADED,
            source="none",
            scene_allowed=False,
            visual_allowed=True,
            reason="layout_missing_or_corrupted",
        )
        return _degraded_empty_layout(
            equipment,
            warning="missing_demo_asset",
            input_contract={**contract, "execution_policy": policy},
            spatial_contract=spatial_contract,
        )
    if safe_load_image(str(safe_plan)) is None:
        logger.warning(
            "Layout image unavailable (demo or upload corrupted). Pipeline continues in degraded mode."
        )
        logger.warning(
            "Demo plan.png missing or corrupted, switching to empty layout mode"
        )
        contract = evaluate_input_contract(
            excel=equipment,
            layout_image=str(safe_plan),
            plan_path=str(safe_plan),
        )
        policy = resolve_execution_policy(contract)
        spatial_contract = make_spatial_contract(
            spatial_valid=False,
            spatial_mode=SpatialMode.DEGRADED,
            source="none",
            scene_allowed=False,
            visual_allowed=True,
            reason="layout_unreadable",
        )
        return _degraded_empty_layout(
            equipment,
            warning="missing_demo_asset",
            input_contract={**contract, "execution_policy": policy},
            spatial_contract=spatial_contract,
        )

    # Evaluate contract with resolved plan path so state is explicit and accurate.
    contract = evaluate_input_contract(
        excel=equipment,
        layout_image=str(safe_plan),
        plan_path=str(safe_plan),
    )
    policy = resolve_execution_policy(contract)

    allowed_tags = set(str(t) for t in equipment.keys())
    if detected_positions is not None:
        detected = dict(detected_positions)
        spatial_contract = make_spatial_contract(
            spatial_valid=True,
            spatial_mode=SpatialMode.REAL,
            source="external",
            scene_allowed=True,
            visual_allowed=True,
            reason="external_positions_provided",
        )
    else:
        resolved = resolve_spatial_positions_with_contract(
            plan_path=safe_plan, allowed_tags=allowed_tags
        )
        detected = dict(resolved.get("positions", {}))
        spatial_contract = dict(resolved.get("spatial_contract", {}))

    # CRITICAL GATE: synthetic / degraded modes must not feed scene geometry.
    source = _extract_spatial_source(detected)
    usage_check = validate_contract_usage(contract=spatial_contract, scene_input_source=source)
    log_spatial_event(
        {
            "stage": "scene",
            "source": source,
            "contract_mode": spatial_contract.get("spatial_mode", SpatialMode.DEGRADED),
            "scene_allowed": bool(spatial_contract.get("scene_allowed")),
            "used_in_scene": False,
            "bypass_detected": bool(usage_check.get("bypass_detected")),
            "reason": usage_check.get("violation_type", "NONE"),
        }
    )
    if not bool(spatial_contract.get("scene_allowed")):
        return _degraded_empty_layout(
            equipment,
            warning="missing_demo_asset",
            input_contract={**contract, "execution_policy": policy},
            spatial_contract=spatial_contract,
        )
    pixel_positions: Dict[str, tuple[int, int]] = {}
    conf_map: Dict[str, float] = {}
    for tag, v in detected.items():
        if isinstance(v, dict):
            p = v.get("pos", [0, 0])
            pixel_positions[tag] = (int(p[0]), int(p[1]))
            conf_map[tag] = float(v.get("confidence", 0.0))
        else:
            pixel_positions[tag] = (int(v[0]), int(v[1]))
            conf_map[tag] = 0.7
    positions = pixel_to_mm(pixel_positions, safe_plan)
    rows = equipment_dict_to_list(equipment)
    items = build_equipment_list(rows, positions)
    wall_info = parse_walls_and_rooms(safe_plan)
    scene: Dict[str, Any] = empty_scene()
    for item in items:
        item["confidence"] = conf_map.get(str(item.get("tag", "")), 0.0)
    scene["equipment"] = items
    scene["walls"] = wall_info.get("walls", [])
    scene["rooms"] = wall_info.get("rooms", [])
    scene["center"] = wall_info.get("center", [0.0, 0.0])
    scene.setdefault("meta", {})
    scene["meta"]["input_state"] = contract.get("state", "valid")
    scene["meta"]["input_contract"] = contract
    scene["meta"]["execution_policy"] = policy
    scene["meta"]["spatial_contract"] = spatial_contract
    usage_check = validate_contract_usage(
        contract=spatial_contract,
        scene_input_source=_extract_spatial_source(detected),
    )
    log_spatial_event(
        {
            "stage": "scene",
            "source": _extract_spatial_source(detected),
            "contract_mode": spatial_contract.get("spatial_mode", SpatialMode.DEGRADED),
            "scene_allowed": bool(spatial_contract.get("scene_allowed")),
            "used_in_scene": True,
            "bypass_detected": bool(usage_check.get("bypass_detected")),
            "reason": usage_check.get("violation_type", "NONE"),
        }
    )
    scene["meta"]["spatial_truth_status"] = (
        "VIOLATION" if usage_check.get("bypass_detected") else "CLEAN"
    )
    return geometry_engine(scene)


__all__ = ["build_scene_document", "AssetContractViolation", "SCENE_STAGE"]
