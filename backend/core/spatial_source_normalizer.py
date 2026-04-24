"""Layer 1: normalize heterogeneous spatial sources into a common record shape."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, MutableMapping, Tuple

# pickpoint > OCR > CAD > fallback
_SOURCE_RANK: Dict[str, int] = {
    "pickpoint": 0,
    "ocr": 1,
    "cad": 2,
    "fallback": 3,
}


def _normalize_source_key(raw: str) -> str:
    s = (raw or "").strip().lower()
    if s == "pickpoint":
        return "pickpoint"
    if s in {"ocr", "pdf_text", "ocr_vote", "cache"}:
        return "ocr"
    if s in {"cad", "dxf", "dwg"}:
        return "cad"
    return "fallback"


def _rank(src: str) -> int:
    return _SOURCE_RANK.get(src, 99)


def _as_pixel(row: Mapping[str, Any]) -> Tuple[float, float] | None:
    if "pixel" in row and isinstance(row["pixel"], (list, tuple)) and len(row["pixel"]) >= 2:
        return float(row["pixel"][0]), float(row["pixel"][1])
    if "pos" in row and isinstance(row["pos"], (list, tuple)) and len(row["pos"]) >= 2:
        return float(row["pos"][0]), float(row["pos"][1])
    return None


def normalize_spatial_sources(raw_points: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merge samples per tag using source priority: pickpoint > OCR > CAD > fallback.

    Output dict keys: tag, source (pickpoint|ocr|cad|fallback), pixel (x, y),
    confidence, is_valid_spatial

    Rules:
    - ``cluster_estimate`` → unified source ``fallback``, confidence < 0.4,
      ``is_valid_spatial`` False when any trusted (pickpoint/ocr/cad) point
      exists in the batch; if no trusted points exist, cluster rows stay True.
    - Other invalid low-confidence fallbacks flagged False but still returned.
    """
    best: Dict[str, MutableMapping[str, Any]] = {}
    for row in raw_points:
        if not isinstance(row, Mapping):
            continue
        tag = str(row.get("tag") or "").strip()
        if not tag:
            continue
        pix = _as_pixel(row)
        if pix is None:
            continue
        raw_src = str(row.get("source") or "")
        src = _normalize_source_key(raw_src)
        conf = max(0.0, min(1.0, float(row.get("confidence", 0.0) or 0.0)))
        cand: MutableMapping[str, Any] = {
            "tag": tag,
            "source": src,
            "pixel": (pix[0], pix[1]),
            "confidence": conf,
            "_raw_source": raw_src,
        }
        prev = best.get(tag)
        if prev is None or _rank(src) < _rank(str(prev["source"])):
            best[tag] = cand
        elif prev is not None and _rank(src) == _rank(str(prev["source"])) and conf > float(prev["confidence"]):
            best[tag] = cand

    trusted_any = any(
        str(v["source"]) in {"pickpoint", "ocr", "cad"} for v in best.values()
    )

    out: List[Dict[str, Any]] = []
    for tag in sorted(best.keys()):
        row = best[tag]
        src = str(row["source"])
        raw_src = str(row.get("_raw_source", ""))
        pix = (float(row["pixel"][0]), float(row["pixel"][1]))
        conf = float(row["confidence"])
        is_valid = True

        if raw_src == "cluster_estimate":
            conf = min(conf, 0.39)
            if trusted_any:
                is_valid = False
            else:
                is_valid = True
        elif src == "fallback":
            is_valid = conf >= 0.25
        else:
            is_valid = True

        out.append(
            {
                "tag": tag,
                "source": src,
                "pixel": pix,
                "confidence": conf,
                "is_valid_spatial": bool(is_valid),
            }
        )

    return out


__all__ = ["normalize_spatial_sources"]
