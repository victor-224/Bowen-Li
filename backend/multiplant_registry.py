"""Phase C: multi-plant version registry."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping


def _registry_path(runtime_dir: Path) -> Path:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir / "plants_registry.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_registry(runtime_dir: Path) -> Dict[str, Any]:
    path = _registry_path(runtime_dir)
    if not path.is_file():
        return {"plants": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"plants": {}}


def write_registry(runtime_dir: Path, data: Mapping[str, Any]) -> Path:
    path = _registry_path(runtime_dir)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def register_snapshot(
    runtime_dir: Path,
    *,
    plant_id: str,
    payload: Mapping[str, Any],
    source_files: Mapping[str, Any],
) -> Dict[str, Any]:
    db = read_registry(runtime_dir)
    plants = db.setdefault("plants", {})
    record = plants.setdefault(plant_id, {"versions": []})
    versions: List[Dict[str, Any]] = record.setdefault("versions", [])
    version_id = f"v{len(versions) + 1}"
    item = {
        "version_id": version_id,
        "created_at": _utc_now(),
        "summary": {
            "scene_count": len(payload.get("scene", [])) if isinstance(payload.get("scene"), list) else 0,
            "edge_count": len(payload.get("layout_graph", {}).get("edges", []))
            if isinstance(payload.get("layout_graph"), dict)
            else 0,
            "zone_count": len(payload.get("layout_graph", {}).get("zones", []))
            if isinstance(payload.get("layout_graph"), dict)
            else 0,
        },
        "source_files": dict(source_files),
    }
    versions.append(item)
    write_registry(runtime_dir, db)
    return item


def list_plants(runtime_dir: Path) -> Dict[str, Any]:
    db = read_registry(runtime_dir)
    out: Dict[str, Any] = {"plants": []}
    for pid, rec in db.get("plants", {}).items():
        versions = rec.get("versions", [])
        out["plants"].append(
            {
                "plant_id": pid,
                "version_count": len(versions),
                "latest_version": versions[-1] if versions else None,
            }
        )
    out["plants"] = sorted(out["plants"], key=lambda x: x["plant_id"])
    return out

