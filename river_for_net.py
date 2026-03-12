from __future__ import annotations

import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parent
_HANDOFF_DIR = _ROOT / "handoff_river_solver_core_20260312" / "code" / "current"

if str(_HANDOFF_DIR) not in sys.path:
    sys.path.insert(0, str(_HANDOFF_DIR))

from single_river_clean import River  # noqa: E402

__all__ = ["River"]
