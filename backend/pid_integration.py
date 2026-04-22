"""Phase C: lightweight P&ID linkage engine."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Mapping

from backend.file_classifier import classify_files


_TAG_PATTERN = re.compile(r"\b[A-Z]\d{2,4}[A-Z]?\b")


def _extract_pdf_text(path: Path) -> str:
    try:
        import fitz  # pymupdf

        with fitz.open(path) as doc:
            parts: List[str] = []
            for i in range(min(3, len(doc))):
                parts.append(doc[i].get_text() or "")
            return "\n".join(parts)
    except Exception:
        return ""


def _pick_pid_sources(data_dir: Path) -> List[Path]:
    cls = classify_files(data_dir)
    out: List[Path] = []
    for key in ("reference", "gad"):
        raw = cls.get(key)
        if isinstance(raw, list):
            out.extend(Path(p) for p in raw)
        elif isinstance(raw, str) and raw:
            out.append(Path(raw))
    return [p for p in out if p.is_file() and p.suffix.lower() == ".pdf"]


def build_pid_links(layout_graph: Mapping[str, Any], data_dir: Path) -> Dict[str, Any]:
    """
    Build a minimal P&ID bridge:
    - detect tag mentions in reference/gad PDFs
    - infer process links from existing layout_graph edges
    """
    nodes = layout_graph.get("nodes", [])
    tags = {str(n.get("tag")) for n in nodes if isinstance(n, dict) and n.get("tag")}
    docs = _pick_pid_sources(data_dir)

    mentions: Dict[str, List[str]] = {t: [] for t in tags}
    docs_summary: List[Dict[str, Any]] = []
    for doc in docs:
        text = _extract_pdf_text(doc)
        found_tags = sorted({m.group(0) for m in _TAG_PATTERN.finditer(text) if m.group(0) in tags})
        for t in found_tags:
            mentions[t].append(doc.name)
        docs_summary.append({"file": doc.name, "detected_tags": found_tags})

    inferred: List[Dict[str, Any]] = []
    for e in layout_graph.get("edges", []):
        if not isinstance(e, dict):
            continue
        if e.get("type") in {"upstream", "connected_process"}:
            inferred.append(
                {
                    "from": e.get("source"),
                    "to": e.get("target"),
                    "type": "pid_link",
                    "confidence": float(e.get("confidence", 0.5)),
                }
            )

    return {
        "documents": docs_summary,
        "tag_mentions": {k: v for k, v in mentions.items() if v},
        "inferred_process_links": inferred,
    }
