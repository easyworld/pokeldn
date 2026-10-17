"""Cards and library notes a run leaves on its tool's page (docs/plugins.md, Status cards): `show` prints
`[panel] {json}`, which the Games page draws as a card above the tool's Start button and keeps after the run;
`annotate` marks one file of the plugin's library. A run outside the app prints the line and nothing else.
`read` is the app's side: the line checked against the limits below, or None.
"""
import json
import re

PREFIX = "[panel] "
TONES = ("info", "ok", "warning", "error")
STATES = ("ok", "bad", "checking")
CARDS = 8                     # cards one plugin keeps; a new id past it is refused by the app
LINES, CHIPS = 12, 6
TITLE, TEXT, CHIP = 80, 200, 40
IMAGE_BYTES = 2 << 20
ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")


def _short(value, limit: int, what: str) -> str:
    value = " ".join(str(value).split())
    if len(value) > limit:
        raise ValueError(f"{what} is at most {limit} characters")
    return value


def _image(image) -> str | None:
    if image is None:
        return None
    image = str(image)
    if not image.lower().endswith((".png", ".jpg", ".jpeg")):
        raise ValueError("a panel image is a .png, .jpg or .jpeg file")
    return image


def _card(id, title, lines=(), image=None, chips=(), tone="info") -> dict:
    if not isinstance(id, str) or not ID.fullmatch(id):
        raise ValueError("a card id is 1 to 32 lower-case letters, digits, - and _")
    if tone not in TONES:
        raise ValueError(f"a card's tone is one of {', '.join(TONES)}")
    lines, chips = [str(x) for x in lines], [tuple(c) for c in chips]
    if len(lines) > LINES or len(chips) > CHIPS:
        raise ValueError(f"a card holds at most {LINES} lines and {CHIPS} chips")
    title = _short(title, TITLE, "a card's title")
    if not title:
        raise ValueError("a card has a title")
    return {"id": id, "title": title, "tone": tone, "image": _image(image),
            "lines": [_label(x) for x in lines],
            "chips": [[_short(k, CHIP, "a chip's label"), _short(v, CHIP, "a chip's value")]
                      for k, v in chips]}


def _label(line: str):
    """"Label: value" lines are drawn as two columns, as the app's own cards do."""
    label, sep, value = line.partition("\t")
    return [_short(label, CHIP, "a line's label"), _short(value, TEXT, "a line")] if sep else _short(line, TEXT, "a line")


def _note(name, state="ok", text="", image=None) -> dict:
    name = str(name)
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise ValueError("a note names one file of the library, by its file name")
    if state not in STATES:
        raise ValueError(f"a note's state is one of {', '.join(STATES)}")
    return {"file": name, "state": state, "text": _short(text, TEXT, "a note"), "image": _image(image)}


def _print(message: dict) -> None:
    print(PREFIX + json.dumps(message, ensure_ascii=False, separators=(",", ":")), flush=True)


def show(id: str, title: str, lines=(), *, image=None, chips=(), tone: str = "info") -> None:
    """Shows the card `id`, replacing the last one shown under it. `lines` are plain text, or
    "label<TAB>value" for a two-column row; `chips` are (label, value) pairs; `image` is a PNG or JPEG
    in the plugin's data folder or library, at most IMAGE_BYTES; `tone` is info, ok, warning or error."""
    _print(_card(id, title, lines, image, chips, tone))


def clear(id: str) -> None:
    if not isinstance(id, str) or not ID.fullmatch(id):
        raise ValueError("a card id is 1 to 32 lower-case letters, digits, - and _")
    _print({"id": id, "clear": True})


def annotate(name: str, *, state: str = "ok", text: str = "", image=None) -> None:
    """Marks the library file `name`: ok, bad or checking, with a short `text` and an icon `image`.
    The note is the file name's: renaming or deleting the file drops it."""
    _print(_note(name, state, text, image))


def unannotate(name: str) -> None:
    _print({"file": str(name), "clear": True})


def read(line: str) -> dict | None:
    """The card, note or clear a `[panel]` line carries, checked; None for any other line or a bad one."""
    if not line.startswith(PREFIX):
        return None
    try:
        data = json.loads(line[len(PREFIX):])
        if not isinstance(data, dict):
            return None
        if data.get("clear") is True:
            key = "id" if "id" in data else "file"
            value = data.get(key)
            ok = isinstance(value, str) and (ID.fullmatch(value) if key == "id" else _note(value))
            return {key: value, "clear": True} if ok else None
        if "file" in data:
            return _note(data["file"], data.get("state", "ok"), data.get("text", ""), data.get("image"))
        lines = [x if isinstance(x, str) else "\t".join(map(str, x)) for x in data.get("lines", [])]
        return _card(data.get("id"), data.get("title", ""), lines, data.get("image"),
                     data.get("chips", []), data.get("tone", "info"))
    except (ValueError, TypeError):
        return None
