"""Asset Contract Layer for runtime-generated pipeline artifacts.

Formalizes:
  - who produces each runtime asset (pipeline stage)
  - who is allowed to consume it
  - when it is valid for consumption
  - structured failure when violated

Scope: does NOT modify pipeline architecture or task state machine.
Only adds a validation/ownership gate between stages and the filesystem.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2


logger = logging.getLogger("industrial_digital_twin.asset_contract")


@dataclass
class AssetContract:
    name: str
    path: str
    produced_by: str
    consumed_by: List[str]
    valid_after: List[str] = field(default_factory=list)
    required: bool = True
    lifecycle: str = "ephemeral"  # "ephemeral" or "persistent"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "produced_by": self.produced_by,
            "consumed_by": list(self.consumed_by),
            "valid_after": list(self.valid_after),
            "required": self.required,
            "lifecycle": self.lifecycle,
        }


class AssetContractViolation(Exception):
    """Base class for asset contract violations (not pipeline failures)."""

    code: str = "ASSET_VIOLATION"

    def __init__(
        self,
        contract: AssetContract,
        *,
        stage: str = "",
        message: str = "",
    ) -> None:
        self.contract = contract
        self.stage = stage or (contract.consumed_by[0] if contract.consumed_by else "")
        self.message = message or f"Asset contract violated: {contract.name}"
        super().__init__(self.message)

    def to_error_payload(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "asset": self.contract.name,
            "produced_by": self.contract.produced_by,
            "consumed_by": (
                self.stage if self.stage in self.contract.consumed_by else (
                    self.contract.consumed_by[0] if self.contract.consumed_by else ""
                )
            ),
            "stage": self.stage,
            "message": self.message,
        }


class AssetMissingError(AssetContractViolation):
    code = "ASSET_MISSING"

    def __init__(self, contract: AssetContract, *, stage: str = "") -> None:
        super().__init__(
            contract,
            stage=stage,
            message=(
                f"Asset '{contract.name}' missing. Expected producer stage: "
                f"{contract.produced_by}."
            ),
        )


class AssetCorruptedError(AssetContractViolation):
    code = "ASSET_CORRUPTED"

    def __init__(self, contract: AssetContract, *, stage: str = "") -> None:
        super().__init__(
            contract,
            stage=stage,
            message=(
                f"Asset '{contract.name}' is corrupted or unreadable. "
                f"Produced by stage: {contract.produced_by}."
            ),
        )


# -----------------------------------------------------------------------------
# Contract registry + validation
# -----------------------------------------------------------------------------


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _absolute(path_str: str) -> Path:
    p = Path(path_str)
    if not p.is_absolute():
        p = _repo_root() / p
    return p


PLAN_IMAGE_CONTRACT = AssetContract(
    name="plan.png",
    path="data/runtime/plan.png",
    produced_by="layout_parse",
    consumed_by=["scene_render"],
    valid_after=["layout_parse"],
    required=True,
    lifecycle="ephemeral",
)


_REGISTRY: Dict[str, AssetContract] = {
    PLAN_IMAGE_CONTRACT.name: PLAN_IMAGE_CONTRACT,
}


def get_contract(name: str) -> AssetContract:
    c = _REGISTRY.get(name)
    if c is None:
        raise KeyError(f"Unknown asset contract: {name}")
    return c


def resolve_asset_path(contract: AssetContract, override_path: Optional[Path] = None) -> Path:
    if override_path is not None:
        return Path(override_path)
    return _absolute(contract.path)


def log_asset_status(contract: AssetContract, status: str) -> None:
    """Debug visibility of the asset graph."""
    logger.info(
        "[ASSET] %s produced_by=%s consumed_by=%s status=%s",
        contract.name,
        contract.produced_by,
        ",".join(contract.consumed_by) or "-",
        status,
    )


def validate_asset(
    contract: AssetContract,
    *,
    stage: str = "",
    override_path: Optional[Path] = None,
) -> Path:
    """Validate a contracted asset before consumption.

    Returns resolved filesystem path on success. Raises AssetMissingError or
    AssetCorruptedError on violations. These errors are explicitly distinct
    from pipeline failures so upper layers can map them to ASSET_* error codes
    rather than raw FileNotFoundError / ValueError.
    """
    path = resolve_asset_path(contract, override_path=override_path)
    if not os.path.exists(path):
        log_asset_status(contract, "MISSING")
        raise AssetMissingError(contract, stage=stage or (contract.consumed_by[0] if contract.consumed_by else ""))
    log_asset_status(contract, "PRESENT")
    return path


def load_asset(
    contract: AssetContract,
    *,
    stage: str = "",
    override_path: Optional[Path] = None,
    reader: str = "cv2",
) -> Any:
    """Load a contracted asset with corruption validation and structured error surface."""
    path = validate_asset(contract, stage=stage, override_path=override_path)
    if reader == "cv2":
        img = cv2.imread(str(path))
        if img is None:
            log_asset_status(contract, "CORRUPTED")
            raise AssetCorruptedError(contract, stage=stage or (contract.consumed_by[0] if contract.consumed_by else ""))
        log_asset_status(contract, "VALID")
        return path  # callers use path; image pre-check is enough
    if reader == "path":
        return path
    if reader == "bytes":
        with open(path, "rb") as f:
            return f.read()
    raise ValueError(f"Unsupported asset reader: {reader}")
