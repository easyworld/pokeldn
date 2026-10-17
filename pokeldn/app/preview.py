"""Titles prepared ahead of their Switch release: shown when the app runs from a source checkout,
hidden in a packaged release until the flag is lifted ([Unreleased titles](docs/gui.md#unreleased-titles))."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def enabled(environ=os.environ, frozen: bool | None = None, root: Path = ROOT) -> bool:
    """POKELDN_PREVIEW=1 shows them anywhere and 0 hides them anywhere; otherwise a git checkout run
    unfrozen shows them. A packaged app carries no .git, so a release never does."""
    flag = environ.get("POKELDN_PREVIEW", "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return True
    if flag in ("0", "false", "no", "off"):
        return False
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    return not frozen and (root / ".git").exists()
