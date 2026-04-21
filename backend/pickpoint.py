"""Interactive pick points on plan image using OpenCV (ordered tags, no Excel/3D)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Tuple

import cv2
import numpy as np

PICKPOINT_TAGS = [
    "B200",
    "E300",
    "X100",
    "X200A",
    "P001A",
    "B301",
    "B1000",
    "P202A",
]

WINDOW_NAME = "Pick points — plan_hd"
_BAR_H = 52


def _default_plan_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "plan_hd.png"


def _load_bgr(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Cannot read image (missing or unsupported format): {path}")
    return img


@dataclass
class _PickState:
    plan: np.ndarray
    idx: int = 0
    results: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    done: bool = False

    def _compose_display(self) -> np.ndarray:
        h, w = self.plan.shape[:2]
        header = np.zeros((_BAR_H, w, 3), dtype=np.uint8)
        header[:] = (48, 48, 48)
        layer = self.plan.copy()
        if self.idx < len(PICKPOINT_TAGS):
            msg = (
                f"Next: {PICKPOINT_TAGS[self.idx]} "
                f"({self.idx + 1}/{len(PICKPOINT_TAGS)}) — click on plan | q cancel"
            )
        else:
            msg = "All points placed — closing"
        cv2.putText(
            header,
            msg,
            (10, 34),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        for tag, (px, py) in self.results.items():
            cv2.circle(layer, (px, py), 10, (0, 255, 0), 2)
            cv2.putText(
                layer,
                tag,
                (px + 12, py - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )
        return np.vstack([header, layer])

    def redraw(self) -> None:
        cv2.imshow(WINDOW_NAME, self._compose_display())


def pick_points_on_plan(image_path: Path | str | None = None) -> Dict[str, Tuple[int, int]]:
    """Open a window on the plan image; left-click in order to bind each tag. Returns {tag: (x, y)}."""
    path = Path(image_path) if image_path is not None else _default_plan_path()
    if not path.is_file():
        raise FileNotFoundError(f"Image not found: {path}")

    plan = _load_bgr(path)
    state = _PickState(plan=plan)

    def on_mouse(event: int, x: int, y: int, _flags: int, _param: object) -> None:
        if state.done or event != cv2.EVENT_LBUTTONDOWN:
            return
        if y < _BAR_H:
            return
        if state.idx >= len(PICKPOINT_TAGS):
            return
        ix, iy = x, y - _BAR_H
        tag = PICKPOINT_TAGS[state.idx]
        state.results[tag] = (ix, iy)
        state.idx += 1
        state.redraw()
        if state.idx >= len(PICKPOINT_TAGS):
            state.done = True

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(WINDOW_NAME, on_mouse)
    state.redraw()

    while not state.done:
        key = cv2.waitKey(30) & 0xFF
        if key in (ord("q"), 27):
            cv2.destroyAllWindows()
            raise RuntimeError("Pick cancelled by user")
        try:
            if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                cv2.destroyAllWindows()
                raise RuntimeError("Window closed before completing picks")
        except cv2.error:
            cv2.destroyAllWindows()
            raise RuntimeError("Window closed before completing picks") from None

    cv2.waitKey(200)
    cv2.destroyAllWindows()
    return dict(state.results)


if __name__ == "__main__":
    out = pick_points_on_plan()
    print(out)
