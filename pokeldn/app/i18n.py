"""Community language packs and English fallback; docs/plugins.md, Language packs."""
import os
import re
import string
import tomllib
from pathlib import Path

_strings: dict[str, str] = {}
_selected = ""
BUILTIN_CHINESE = "zh-Hans"


def read_pack(meta: dict, read) -> dict[str, str]:
    locale = meta.get("locale")
    if not isinstance(locale, str) or not re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", locale):
        raise ValueError("Language pack needs a locale such as zh-Hans.")
    name = meta.get("strings")
    if not isinstance(name, str) or Path(name).name != name or name in ("", ".", ".."):
        raise ValueError("Language pack strings must name a TOML file beside plugin.toml.")
    try:
        values = tomllib.loads(read(name).decode("utf-8"))
    except (OSError, KeyError, UnicodeError, ValueError) as error:
        raise ValueError(f"Language pack {name} does not parse: {error}") from None
    if any(not isinstance(value, str) for value in values.values()):
        raise ValueError("Language pack strings must be quoted keys and text values.")
    for value in values.values():
        try:
            for _, field, spec, _ in string.Formatter().parse(value):
                if field is not None and (not field.isidentifier() or '{' in spec):
                    raise ValueError("Use named placeholders without attribute or index access.")
        except ValueError as error:
            raise ValueError(f"Language pack has an invalid format string: {error}") from None
    return values


def select(plugin_id: str = "") -> None:
    """Select an enabled language plugin by id; an absent or broken pack selects English."""
    global _strings, _selected
    _selected = plugin_id
    _strings = {}
    if plugin_id == BUILTIN_CHINESE:
        _strings = tomllib.loads((Path(__file__).parent / "data/strings.zh-Hans.toml").read_text(encoding="utf-8"))
        return
    from pokeldn import plugins
    if plugin_id:
        on = plugins.enabled()
        candidate = next((p for p in plugins.discover() if p.id == plugin_id and p.locale and not p.error
                          and (plugins.named(p) or p.id in on)
                          and plugins.compatibility(p.api)[0] in ("ok", "deprecated")), None)
        if candidate is not None:
            _strings = candidate.translations


# The English strings name the device the app runs on; on Android it is a phone (examples/android).
_PHONE = re.compile(r"\b(this|your|the) computer\b")


def _device(text: str) -> str:
    return _PHONE.sub(r"\1 phone", text) if os.environ.get("POKELDN_PLATFORM") == "android" else text


def t(key: str, default: str, **fmt) -> str:
    """Look up a string and format named values; malformed translations fall back to English."""
    default = _device(default)
    value = _strings.get(key, default)
    try:
        return value.format(**fmt)
    except (ValueError, KeyError, IndexError, AttributeError, TypeError):
        return default.format(**fmt)


# This fork starts in Chinese; an explicit English selection still uses upstream defaults.
select(BUILTIN_CHINESE)
