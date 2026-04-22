"""Flask JSON API: equipment data from Excel (server-side only)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, MutableMapping, Optional

import openpyxl
from flask import Flask, jsonify, request
from flask_cors import CORS
from backend.relations import build_relations

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
_RUNTIME_DIR_REL = Path("data") / "runtime"
_RUNTIME_PLAN_REL = _RUNTIME_DIR_REL / "plan.png"
_RUNTIME_EXCEL_REL = _RUNTIME_DIR_REL / "equipment.xlsx"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def runtime_dir_path() -> Path:
    return _repo_root() / _RUNTIME_DIR_REL


def runtime_plan_path() -> Path:
    return _repo_root() / _RUNTIME_PLAN_REL


def runtime_excel_path() -> Path:
    return _repo_root() / _RUNTIME_EXCEL_REL


def _excel_path() -> Path:
    runtime_excel = runtime_excel_path()
    if runtime_excel.is_file():
        return runtime_excel
    return _repo_root() / _EXCEL_REL


def plan_image_path() -> Path:
    runtime_plan = runtime_plan_path()
    if runtime_plan.is_file():
        return runtime_plan
    return _repo_root() / Path("data") / "plan_hd.png"


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


def build_scene(equipment: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Unified scene document via core engines (layout + geometry)."""
    from backend.engines.scene import build_scene_document

    if equipment is None:
        equipment = load_equipment_from_excel()
    return build_scene_document(equipment)


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
    try:
        return jsonify(build_scene(equipment))
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/relations")
def get_relations() -> Any:
    try:
        equipment = load_equipment_from_excel()
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    try:
        scene = build_scene(equipment)
        return jsonify(build_relations(scene))
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/upload")
def upload_project_files() -> Any:
    plan_file = request.files.get("plan_file")
    excel_file = request.files.get("excel_file")

    if plan_file is None or excel_file is None:
        return jsonify({"success": False, "error": "plan_file and excel_file are required"}), 400

    plan_name = (plan_file.filename or "").lower()
    excel_name = (excel_file.filename or "").lower()
    if not plan_name.endswith((".png", ".jpg", ".jpeg")):
        return jsonify({"success": False, "error": "plan_file must be png/jpg/jpeg"}), 400
    if not excel_name.endswith(".xlsx"):
        return jsonify({"success": False, "error": "excel_file must be .xlsx"}), 400

    runtime_dir = runtime_dir_path()
    runtime_dir.mkdir(parents=True, exist_ok=True)

    plan_target = runtime_plan_path()
    excel_target = runtime_excel_path()
    plan_file.save(plan_target)
    excel_file.save(excel_target)

    print(f"[upload] plan_file: {plan_file.filename} -> {plan_target}")
    print(f"[upload] excel_file: {excel_file.filename} -> {excel_target}")
    return jsonify({"success": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
