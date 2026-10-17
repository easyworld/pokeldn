"""Every name docs/plugins.md promises in "The program surface" resolves, with the parameters it names.

Programs outside the repository import these; a rename here breaks them silently.
"""
import importlib
import inspect
import re
from pathlib import Path

import pytest

DOC = Path(__file__).resolve().parents[1] / "docs" / "plugins.md"


def _names(heading="## The program surface", root=""):
    """The names a table under `heading` promises: `a.b.f(x, y=)`, then `.g(z)` or a bare `C` beside it (a
    sibling of `f`). A bare name opening a row is `root`'s when given; `api.*` names the object register()
    receives and is left out. -> (dotted path, [parameters])."""
    level = heading.split(" ")[0]
    section = DOC.read_text(encoding="utf-8").split(heading, 1)[1].split(f"\n{level} ", 1)[0]
    names, base = [], root
    for line in section.splitlines():
        if not line.startswith("| `"):
            continue
        opening = True
        for token in re.findall(r"`([^`]+)`", line.split(" | ")[0]):
            if token.startswith(("python ", "api.")):
                continue
            path, _, params = token.partition("(")
            if path.startswith("."):
                path = base + path
            elif not path.startswith(("pokeldn.", "gui.")):
                path = (root if opening and root else base) + "." + path
            opening = False
            base = path.rsplit(".", 1)[0]
            params = [p.split("=")[0].strip().lstrip("*") for p in params.rstrip(")").split(",")]
            names.append((path, [p for p in params if p]))
    return names


NAMES = (_names() + _names("## The API, version 1", "pokeldn.plugins")
         + _names("### LDN networks (1.7)", "pokeldn.ldn.network"))


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
            "pokeldn.frlg.gift.builder.CARTRIDGES", "gui.board.flash", "pokeldn.popup.choose",
            "pokeldn.ldn.network.join", "pokeldn.ldn.network.Network.send_ip", "pokeldn.ldn.radio_lost"} <= paths


@pytest.mark.parametrize("path,params", NAMES, ids=[p for p, _ in NAMES])
def test_a_promised_name_resolves_with_its_parameters(path, params):
    obj = _resolve(path)
    if params:
        accepted = inspect.signature(obj).parameters
        assert [p for p in params if p not in accepted] == []
