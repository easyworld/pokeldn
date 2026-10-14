"""Every name docs/plugins.md promises in "The program surface" resolves, with the parameters it names.

Programs outside the repository import these; a rename here breaks them silently.
"""
import importlib
import inspect
import re
from pathlib import Path

import pytest

DOC = Path(__file__).resolve().parents[1] / "docs" / "plugins.md"


def _names():
    """`a.b.f(x, y=)`, then `.g(z)` or a bare `C` beside it (a sibling of `f`) -> (dotted path, [parameters])."""
    section = DOC.read_text(encoding="utf-8").split("## The program surface", 1)[1].split("\n## ", 1)[0]
    names, base = [], ""
    for line in section.splitlines():
        if not line.startswith("| `"):
            continue
        for token in re.findall(r"`([^`]+)`", line.split(" | ")[0]):
            if token.startswith("python "):
                continue
            path, _, params = token.partition("(")
            if not path.startswith(("pokeldn.", "gui.")):
                path = base + "." + path.lstrip(".")
            base = path.rsplit(".", 1)[0]
            params = [p.strip().rstrip("=").lstrip("*") for p in params.rstrip(")").split(",") if p.strip()]
            names.append((path, params))
    return names


NAMES = _names()


def _resolve(path):
    parts = path.split(".")
    for cut in range(len(parts), 0, -1):
        try:
            obj = importlib.import_module(".".join(parts[:cut]))
        except ImportError:
            continue
        for attr in parts[cut:]:
            obj = getattr(obj, attr)
        return obj
    raise ImportError(path)


def test_the_section_names_every_kind_of_entry():
    paths = {p for p, _ in NAMES}
    assert {"pokeldn.pokemon.SERVICE.make", "pokeldn.swsh.gift_builder.compile",
            "pokeldn.frlg.gift.builder.CARTRIDGES", "gui.board.flash"} <= paths


@pytest.mark.parametrize("path,params", NAMES, ids=[p for p, _ in NAMES])
def test_a_promised_name_resolves_with_its_parameters(path, params):
    obj = _resolve(path)
    if params:
        accepted = inspect.signature(obj).parameters
        assert [p for p in params if p not in accepted] == []
