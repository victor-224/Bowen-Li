"""PDF to image runtime loader for industrial plan parsing."""

from __future__ import annotations

from pathlib import Path
from typing import List

import fitz  # PyMuPDF


def pdf_to_images(pdf_path: Path, output_dir: Path, prefix: str) -> List[Path]:
    """
    Convert all pages of a PDF into PNG files under output_dir.
    Returns list of generated image paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    out: List[Path] = []
    try:
        for i in range(len(doc)):
            page = doc[i]
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            p = output_dir / f"{prefix}_p{i + 1}.png"
            pix.save(str(p))
            out.append(p)
    finally:
        doc.close()
    return out


def first_page_to_layout_png(pdf_path: Path, layout_png_path: Path) -> Path:
    """Render page 1 of pdf_path to layout_png_path."""
    layout_png_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    try:
        if len(doc) == 0:
            raise ValueError(f"PDF has no pages: {pdf_path}")
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
        pix.save(str(layout_png_path))
    finally:
        doc.close()
    return layout_png_path
