"""Flask JSON API: equipment data from Excel (server-side only)."""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Any, Dict, Mapping, MutableMapping, Optional, Tuple

import openpyxl
from flask import Flask, jsonify

SHEET_NAME = "Equipment_list"
HEADER_ROW = 6
DATA_START_ROW = 7

# Canonical JSON keys -> possible header labels (row 6), normalized match
_COLUMN_ALIASES: Mapping[str, Tuple[str, ...]] = {
    "tag": ("tag",),
    "service": ("service",),
    "position": ("position", "positionnement"),
    "diameter": ("diameter", "diamètre", "diametre"),
    "length": ("length", "longueur"),
    "height": ("height", "hauteur"),
}

_EXCEL_REL = Path("data") / "Annexe 2_Equipment_liste_et_taille.xlsx"


def _excel_path() -> Path:
    return Path(__file__).resolve().parent.parent / _EXCEL_REL


def _normalize_header(value: object) -> str:
    if value is None:
        return ""
    s = str(value).strip().lower()
    # Strip accents for robust matching (e.g. diamètre -> diametre)
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def _build_header_map(header_row: Tuple[object, ...]) -> Dict[str, int]:
    """Map canonical key -> 0-based column index."""
    norm_to_idx: Dict[str, int] = {}
    for idx, cell in enumerate(header_row):
        n = _normalize_header(cell)
        if n:
            norm_to_idx[n] = idx

    out: Dict[str, int] = {}
    for key, aliases in _COLUMN_ALIASES.items():
        col_idx: Optional[int] = None
        for alias in aliases:
            a = _normalize_header(alias)
            if a in norm_to_idx:
                col_idx = norm_to_idx[a]
                break
        if col_idx is None:
            raise ValueError(
                f"Missing column for {key!r}; expected one of {aliases!r} in row {HEADER_ROW}"
            )
        out[key] = col_idx
    return out


def _json_scalar(value: object) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return value
    # openpyxl may return datetime for date cells; stringify for JSON safety
    return str(value)


def load_equipment_from_excel(path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """Load Equipment_list from Excel: header at HEADER_ROW, data from DATA_START_ROW."""
    p = path if path is not None else _excel_path()
    if not p.is_file():
        raise FileNotFoundError(f"Excel not found: {p}")

    out: Dict[str, Dict[str, Any]] = {}
    wb = openpyxl.load_workbook(p, data_only=True, read_only=True)
    try:
        if SHEET_NAME not in wb.sheetnames:
            raise ValueError(f"Sheet {SHEET_NAME!r} not found; have {wb.sheetnames!r}")
        ws = wb[SHEET_NAME]
        rows = ws.iter_rows(min_row=HEADER_ROW, values_only=True)
        header = next(rows, None)
        if header is None:
            raise ValueError(f"Empty sheet {SHEET_NAME!r}")
        col_map = _build_header_map(tuple(header))
        tag_i = col_map["tag"]

        for row in ws.iter_rows(min_row=DATA_START_ROW, values_only=True):
            if row is None:
                continue
            tag_val = row[tag_i] if tag_i < len(row) else None
            if tag_val is None or (isinstance(tag_val, str) and not tag_val.strip()):
                continue
            tag = str(tag_val).strip()
            entry: MutableMapping[str, Any] = {}
            for key in ("service", "position", "diameter", "length", "height"):
                ci = col_map[key]
                cell = row[ci] if ci < len(row) else None
                entry[key] = _json_scalar(cell)
            out[tag] = dict(entry)
    finally:
        wb.close()
    return out


app = Flask(__name__)


@app.get("/api/equipment")
def get_equipment() -> Any:
    try:
        data = load_equipment_from_excel()
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
