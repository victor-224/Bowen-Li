"""Flask JSON API: equipment data from Excel (server-side only)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, MutableMapping, Optional

import openpyxl
from flask import Flask, jsonify
from flask_cors import CORS

SHEET_NAME = "Equipment_list"
# Real annex: column B = TAG, C = SERVICE, D = POSITION (or TEMA), E/F/G = dimensions (mm)
DATA_START_ROW = 9
COL_TAG = 2
COL_SERVICE = 3
COL_POSITION = 4
COL_DIAMETER = 5
COL_LENGTH = 6
COL_HEIGHT = 7

_EXCEL_REL = Path("data") / "Copy of Annexe 2_Equipment_liste_et_taille.xlsx"


def _excel_path() -> Path:
    return Path(__file__).resolve().parent.parent / _EXCEL_REL


def _normalize_tag(value: object) -> str:
    """Collapse whitespace so e.g. 'P202 A' matches pickpoint tag 'P202A'."""
    if value is None:
        return ""
    return "".join(str(value).split())


def _json_scalar(value: object) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return value
    return str(value)


def load_equipment_from_excel(path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """Load Equipment_list: fixed columns, data from DATA_START_ROW; keys are normalized tags."""
    p = path if path is not None else _excel_path()
    if not p.is_file():
        raise FileNotFoundError(f"Excel not found: {p}")

    out: Dict[str, Dict[str, Any]] = {}
    wb = openpyxl.load_workbook(p, data_only=True, read_only=True)
    try:
        if SHEET_NAME not in wb.sheetnames:
            raise ValueError(f"Sheet {SHEET_NAME!r} not found; have {wb.sheetnames!r}")
        ws = wb[SHEET_NAME]
        for row in ws.iter_rows(
            min_row=DATA_START_ROW,
            min_col=COL_TAG,
            max_col=COL_HEIGHT,
            values_only=True,
        ):
            tag_raw = row[0]
            tag = _normalize_tag(tag_raw)
            if not tag:
                continue
            entry: MutableMapping[str, Any] = {
                "service": _json_scalar(row[1]),
                "position": _json_scalar(row[2]),
                "diameter": _json_scalar(row[3]),
                "length": _json_scalar(row[4]),
                "height": _json_scalar(row[5]),
            }
            out[tag] = dict(entry)
    finally:
        wb.close()
    return out


def equipment_dict_to_list(equipment: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Stable list form: one object per row with explicit tag field."""
    return [{"tag": tag, **row} for tag, row in equipment.items()]


def _infer_geometry_type(service: Any) -> str:
    """Map service name to Phase-4 placeholder types: Tank | Compressor | Exchanger."""
    s = (str(service) if service is not None else "").lower()
    if "compressor" in s:
        return "Compressor"
    if any(k in s for k in ("exchanger", "cooler", "heater", "coalescer")):
        return "Exchanger"
    return "Tank"


def _grid_position_mm(index: int, cols: int = 5, spacing_mm: float = 12000.0) -> Dict[str, float]:
    """Deterministic floor positions in mm (Three.js: x, elevation y, plan z)."""
    col = index % cols
    row = index // cols
    return {
        "x": float(col * spacing_mm),
        "y": 0.0,
        "z": float(row * spacing_mm),
    }


def enrich_equipment_for_scene(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Add position_mm and geometry_type for 3D consumers (no layout solver)."""
    sorted_rows = sorted(rows, key=lambda r: str(r.get("tag", "")))
    out: List[Dict[str, Any]] = []
    for i, row in enumerate(sorted_rows):
        item = dict(row)
        item["geometry_type"] = _infer_geometry_type(row.get("service"))
        item["position_mm"] = _grid_position_mm(i)
        out.append(item)
    return out


def build_scene(equipment: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Unified scene document (2D/3D consumer); walls reserved for future use."""
    if equipment is None:
        equipment = load_equipment_from_excel()
    base_list = equipment_dict_to_list(equipment)
    return {
        "equipment": enrich_equipment_for_scene(base_list),
        "walls": [],
        "meta": {"project": "Industrial Digital Twin"},
    }


app = Flask(__name__)
CORS(
    app,
    resources={r"/api/*": {"origins": ["http://localhost:3000", "http://127.0.0.1:3000"]}},
    supports_credentials=True,
)


@app.get("/api/equipment")
def get_equipment() -> Any:
    try:
        data = load_equipment_from_excel()
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(data)


@app.get("/api/scene")
def get_scene() -> Any:
    try:
        equipment = load_equipment_from_excel()
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(build_scene(equipment))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
