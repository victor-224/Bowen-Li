"""Canonical vision scene schema and normalization of ``run_vision_model`` output.

Isolated: not used by the pipeline, API, or OCR. Never raises outward.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Dict, List, Optional, TypedDict

logger = logging.getLogger("industrial_digital_twin.vision.schema")

_ALLOWED_OBJECT_TYPES = frozenset({"equipment", "structure", "text", "unknown"})
_UNNAMED = "Unnamed"
_DEFAULT_REL = "unknown"
_DEFAULT_REL_TYPE = "related_to"

# TypedDict: relation keys "from" / "to" / "type" (as per canonical schema).
VisionRelationSchema = TypedDict(
    "VisionRelationSchema",
    {"from": str, "to": str, "type": str},
    total=True,
)


class VisionObjectSchema(TypedDict, total=True):
    id: str
    type: str
    name: str
    bbox: List[float]


class VisionMetadataSchema(TypedDict, total=True):
    model: str
    confidence: float


class VisionSceneSchema(TypedDict, total=True):
    objects: List[VisionObjectSchema]
    relations: List[VisionRelationSchema]
    metadata: VisionMetadataSchema


__all__ = [
    "VisionObjectSchema",
    "VisionMetadataSchema",
    "VisionSceneSchema",
    "VisionRelationSchema",
    "empty_schema",
    "normalize_vision_output",
]


def _as_float(n: Any) -> Optional[float]:
    if n is None:
        return None
    if isinstance(n, bool):
        return None
    if isinstance(n, (int, float)) and not isinstance(n, bool):
        return float(n)
    if isinstance(n, str):
        t = n.strip()
        if not t:
            return None
        try:
            return float(t)
        except ValueError:
            return None
    return None


def _id_for_object(item: dict, list_index: int) -> str:
    for key in ("id", "Id", "ID", "object_id", "ObjectId"):
        v = item.get(key)
        if v is not None and not isinstance(v, (dict, list, bool)):
            s = str(v).strip()
            if s:
                return s
    return f"obj_{list_index + 1}"


def _name_for_object(item: dict) -> str:
    for key in ("name", "Name", "label", "Label", "text", "Text"):
        v = item.get(key)
        if v is not None and not isinstance(v, (dict, list, bool)):
            s = str(v).strip()
            if s:
                return s
    return _UNNAMED


def _normalize_object_type(t: Any) -> str:
    if t is None or isinstance(t, (dict, list, bool)):
        return "unknown"
    s = str(t).strip().lower().replace(" ", "_")
    if s in _ALLOWED_OBJECT_TYPES:
        return s
    logger.warning("vision schema: unknown object type %r, using 'unknown'", t)
    return "unknown"


def _bbox(item: dict) -> List[float]:
    b: Any
    b = item.get("bbox", item.get("Bbox", item.get("box", item.get("BBOX"))))
    if b is None:
        logger.warning("vision schema: missing bbox, using [0,0,0,0]")
        return [0.0, 0.0, 0.0, 0.0]
    if not isinstance(b, (list, tuple)) or len(b) != 4:
        logger.warning("vision schema: bbox malformed, using [0,0,0,0]")
        return [0.0, 0.0, 0.0, 0.0]
    out: List[float] = []
    for i, v in enumerate(b):
        f = _as_float(v)
        if f is None:
            logger.warning(
                "vision schema: bbox item %d not numeric, using [0,0,0,0]", i
            )
            return [0.0, 0.0, 0.0, 0.0]
        out.append(f)
    return out


def _rel_end(x: Any) -> str:
    if x is None or (isinstance(x, str) and not str(x).strip()):
        return _DEFAULT_REL
    if isinstance(x, (dict, list, bool)):
        return _DEFAULT_REL
    s = str(x).strip()
    return s if s else _DEFAULT_REL


def _rel_type(v: Any) -> str:
    if v is None or isinstance(v, (dict, list, bool)):
        return _DEFAULT_REL_TYPE
    s = str(v).strip()
    return s if s else _DEFAULT_REL_TYPE


def empty_schema(model: str) -> dict:
    m = (model or "").strip() if isinstance(model, str) else ""
    return {
        "objects": [],
        "relations": [],
        "metadata": {"model": m, "confidence": 0.0},
    }


def _metadata_model(param_model: str, raw: Dict[str, Any]) -> str:
    p = (param_model or "").strip() if isinstance(param_model, str) else ""
    meta = raw.get("metadata")
    if not isinstance(meta, dict):
        return p
    rm = meta.get("model")
    if isinstance(rm, str) and rm.strip():
        return rm.strip()
    return p


def _metadata_confidence(raw: Dict[str, Any]) -> float:
    c: Any = None
    meta = raw.get("metadata")
    if isinstance(meta, dict) and "confidence" in meta:
        c = meta.get("confidence")
    if c is None and "confidence" in raw:
        c = raw.get("confidence")
    f = _as_float(c) if c is not None else None
    if f is None:
        return 0.0
    if f < 0.0:
        return 0.0
    if f > 1.0:
        return 1.0
    return f


def _normalize_one_relation(
    rel: Any, index: int
) -> Optional[Dict[str, str]]:
    if rel is None:
        logger.warning("vision schema: skipped null relation at index %d", index)
        return None
    if not isinstance(rel, dict):
        logger.warning("vision schema: skip non-dict relation at index %d", index)
        return None
    a = _rel_end(
        rel.get("from", rel.get("From", rel.get("source", rel.get("src"))))
    )
    b = _rel_end(rel.get("to", rel.get("To", rel.get("target", rel.get("dst")))))
    t = _rel_type(rel.get("type", rel.get("Type", rel.get("name"))))
    return {"from": a, "to": b, "type": t}


def _normalize_relations_list(raw: Dict[str, Any]) -> List[Dict[str, str]]:
    r = raw.get("relations")
    if r is None:
        return []
    if not isinstance(r, list):
        logger.warning("vision schema: relations not a list, using []")
        return []
    out: List[Dict[str, str]] = []
    for i, rel in enumerate(r):
        d = _normalize_one_relation(rel, i)
        if d is not None:
            out.append(d)
    return out


def _normalize_objects_list(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    o = raw.get("objects")
    if o is None:
        return []
    if not isinstance(o, list):
        logger.warning("vision schema: objects not a list, using []")
        return []
    out: List[Dict[str, Any]] = []
    for i, item in enumerate(o):
        if not isinstance(item, dict):
            logger.warning("vision schema: skip non-dict object at index %d", i)
            continue
        kind = item.get("type", item.get("Type", item.get("kind", item.get("Kind"))))
        out.append(
            {
                "id": _id_for_object(item, i),
                "type": _normalize_object_type(kind),
                "name": _name_for_object(item),
                "bbox": _bbox(item),
            }
        )
    return out


def normalize_vision_output(raw: dict, model: str) -> dict:
    """
    Map ``raw`` (typically from ``run_vision_model``) to a canonical
    :class:`VisionSceneSchema` dict. Never raises.
    """
    try:
        if not isinstance(raw, dict):
            logger.warning("vision schema: raw is not a dict")
            return empty_schema(str(model) if model is not None else "")

        r = raw  # type: Dict[str, Any]
        objects = _normalize_objects_list(r)
        relations = _normalize_relations_list(r)
        m = _metadata_model(str(model) if model is not None else "", r)
        conf = _metadata_confidence(r)

        return {
            "objects": objects,
            "relations": relations,
            "metadata": {"model": m, "confidence": conf},
        }
    except Exception as e:  # noqa: BLE001
        logger.warning("vision schema: unexpected error: %r", e)
        return empty_schema(str(model) if model is not None else "")


if __name__ == "__main__":
    import importlib

    m = importlib.import_module("backend.models.vision.vision_schema")
    n = m.normalize_vision_output
    es = m.empty_schema
    fails = 0

    # CASE A: perfect JSON
    a_in = {
        "success": True,
        "objects": [
            {
                "id": "obj_1",
                "type": "equipment",
                "name": "Pump A",
                "bbox": [0, 0, 100, 100],
            }
        ],
        "relations": [
            {"from": "obj_1", "to": "obj_2", "type": "connected_to"},
        ],
        "metadata": {"model": "qwen2.5-vl-7b-instruct", "confidence": 0.5},
    }
    a = n(a_in, "m-param")
    if a["metadata"]["model"] != "qwen2.5-vl-7b-instruct" or a["objects"][0]["id"] != "obj_1":
        print("FAIL A", a)
        fails += 1
    else:
        print("OK A")

    # CASE B: missing bbox
    b = n(
        {
            "objects": [{"id": "x1", "type": "text", "name": "L"}],
            "relations": [],
            "metadata": {},
        },
        "m",
    )
    if b["objects"][0]["bbox"] != [0.0, 0.0, 0.0, 0.0]:
        print("FAIL B", b)
        fails += 1
    else:
        print("OK B")

    # CASE C: machineX
    c = n(
        {"objects": [{"type": "machineX", "name": "P"}]},
        "m",
    )
    if c["objects"][0]["type"] != "unknown" or c["objects"][0]["id"] != "obj_1":
        print("FAIL C", c)
        fails += 1
    else:
        print("OK C")

    # CASE D: empty dict
    d = n({}, "m2")
    if d != es("m2"):
        print("FAIL D", d, es("m2"))
        fails += 1
    else:
        print("OK D")

    # CASE E: objects string
    e = n({"objects": "hello"}, "m3")
    if e["objects"]:
        print("FAIL E", e)
        fails += 1
    else:
        print("OK E")

    # CASE F: confidence 9.3
    f = n({"metadata": {"confidence": 9.3}}, "m4")
    if f["metadata"]["confidence"] != 1.0:
        print("FAIL F", f)
        fails += 1
    else:
        print("OK F")

    # CASE G: null and bad relation entries
    g = n(
        {
            "relations": [None, {"from": "a", "to": "b", "type": "x"}, "x"],
        },
        "m5",
    )
    if len(g["relations"]) != 1 or g["relations"][0]["type"] != "x":
        print("FAIL G", g)
        fails += 1
    else:
        print("OK G")

    sys.exit(1 if fails else 0)
