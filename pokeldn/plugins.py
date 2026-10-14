"""Third-party extensions: a plugin adds tools to the app and radios to the wireless layer.

A plugin is a folder holding `plugin.toml` and a Python module with `register(api)`, found in the
data folder's `plugins/` (enabled in Settings) or named in POKELDN_PLUGINS (os.pathsep-separated
folders, always loaded), or an installed package under the `pokeldn.plugins` entry point group.
Plugins run with the program's full access; none is loaded unless enabled. docs/plugins.md.
"""
import importlib.util
import json
import os
import re
import sys
import tomllib
from dataclasses import dataclass, field, replace
from importlib import metadata
from pathlib import Path
from typing import Callable

from pokeldn.app.catalog import Field, Game, Tool   # noqa: F401  (re-exported for plugins)

# docs/plugins.md, Versions: a removal or a change of meaning raises the major, an addition the level.
API_VERSION = 1                    # the major this pokeldn serves
API_LEVEL = 3                      # 1.1 api.data and api.level, 1.2 pokeldn.popup, 1.3 the program surface
API_OLDEST = 1                     # an older major is refused
DEPRECATED: dict[int, str] = {}    # a served major due for removal -> the release that drops it
ENTRY_POINT_GROUP = "pokeldn.plugins"


@dataclass
class Plugin:
    id: str
    name: str
    folder: Path | None = None
    description: str = ""
    version: str = ""
    author: str = ""
    homepage: str = ""
    updates: str = ""                     # where newer versions are published (plugin_updates)
    icon: str = ""                        # an image file in the folder
    api: tuple | None = (API_VERSION, 0)   # (major, level) from plugin.toml; None when unreadable
    module: str = "plugin"
    entry_point: object = None
    error: str = ""                       # why it did not load; empty once registered
    loaded: bool = False
    tools: list = field(default_factory=list)    # (game key, Tool)
    games: list = field(default_factory=list)
    radios: list = field(default_factory=list)   # scheme names


@dataclass(frozen=True)
class Radio:
    scheme: str
    label: str
    install: Callable[[str, Callable], object]   # (the text after "scheme:", log) -> None
    plugin: str = ""


class API:
    """What `register(api)` receives. Only this surface is kept stable across API versions."""

    version = API_VERSION
    level = API_LEVEL

    def __init__(self, plugin: Plugin):
        self.plugin = plugin
        self.folder = plugin.folder

    @property
    def data(self) -> Path:
        """A folder for what the plugin keeps; an update replaces the plugin's folder, never this one."""
        path = data_folder(self.plugin.id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _script(self, script: str) -> str:
        if self.folder is None or os.path.isabs(script):
            return script
        return str(self.folder / script)

    def _tool(self, tool: Tool) -> Tool:
        if tool.key in _builtin_tool_keys() or any(t.key == tool.key for t in tools_added()):
            raise ValueError(f"tool key {tool.key!r} is already taken")
        return replace(tool, script=self._script(tool.script))

    def add_tool(self, game: str, tool: Tool) -> None:
        """Adds `tool` under the game whose catalog key is `game` (frlg, swsh, sv...), or under a
        game this plugin added. A relative `tool.script` is relative to the plugin's folder."""
        keys = {g.key for g in _builtin_games()} | {g.key for p in _loaded.values() for g in p.games}
        if game not in keys:
            raise ValueError(f"no game {game!r}")
        self.plugin.tools.append((game, self._tool(tool)))

    def add_game(self, game: Game, icon: str = "") -> None:
        """Adds a new game section with its own tools. `icon` is an image file in the plugin."""
        if game.key in {g.key for g in _builtin_games()} | {g.key for p in _loaded.values() for g in p.games}:
            raise ValueError(f"game key {game.key!r} is already taken")
        tools = tuple(self._tool(t) for t in game.tools)
        self.plugin.games.append(replace(game, tools=tools, icon=self._script(icon) if icon else ""))

    def add_radio(self, scheme: str, install: Callable, label: str = "") -> None:
        """Makes POKELDN_RADIO=`scheme`:ARG call `install(ARG, log)` before the first LDN call;
        `install` routes ldn.scan, ldn.connect and ldn.create_network, normally through
        `ldn.wlan.set_factory`."""
        from pokeldn.ldn import radios
        if not scheme.isidentifier() or scheme in radios.BUILTIN or scheme in _radios:
            raise ValueError(f"radio {scheme!r} is already taken or not a plain name")
        _radios[scheme] = Radio(scheme, label or scheme, install, self.plugin.id)
        self.plugin.radios.append(scheme)


def parse_api(value) -> tuple | None:
    """plugin.toml's api: 1 is (1, 0), "1.1" is (1, 1)."""
    if isinstance(value, int) and not isinstance(value, bool):
        return (value, 0)
    if isinstance(value, str) and re.fullmatch(r"\d+(\.\d+)?", value.strip()):
        major, _, level = value.strip().partition(".")
        return (int(major), int(level or 0))
    return None


def api_text(api: tuple | None) -> str:
    return f"{api[0]}.{api[1]}" if api else "none"


def compatibility(api: tuple | None) -> tuple[str, str]:
    """ok, deprecated (loads, with the message), newer or older (refused, with the message)."""
    here = f"this pokeldn runs plugin API {API_VERSION}.{API_LEVEL}"
    if api is None or api[0] < 1:
        return "older", "plugin.toml names no plugin API version (api = 1)."
    if api > (API_VERSION, API_LEVEL):
        return "newer", f"It needs plugin API {api_text(api)} and {here}. Update pokeldn to use it."
    if api[0] < API_OLDEST:
        return "older", (f"It was written for plugin API {api[0]}, which {here} no longer supports. "
                         "Ask its author for a newer version.")
    if api[0] in DEPRECATED:
        return "deprecated", (f"It uses plugin API {api[0]}, which {DEPRECATED[api[0]]} stops supporting. "
                              "Ask its author for a newer version.")
    return "ok", ""


_loaded: dict[str, Plugin] = {}
_radios: dict[str, Radio] = {}
_done = False
generation = 0          # counts reloads, so a view knows its catalog is stale


def _builtin_games() -> tuple[Game, ...]:
    from pokeldn.app import catalog
    return catalog.GAMES


def _builtin_tool_keys() -> set[str]:
    return {t.key for g in _builtin_games() for t in g.tools}


def folder() -> Path:
    from pokeldn.app.paths import DATA
    return DATA / "plugins"


def data_folder(plugin_id: str) -> Path:
    from pokeldn.app.paths import DATA
    return DATA / "plugin-data" / plugin_id


def enabled() -> list[str]:
    """The plugin ids Settings turned on; read without creating a settings file."""
    from pokeldn.app.paths import DATA
    try:
        data = json.loads((DATA / "settings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    ids = data.get("plugins", []) if isinstance(data, dict) else []
    return [i for i in ids if isinstance(i, str)]


def _read_folder(path: Path) -> Plugin:
    plugin = Plugin(id=path.name, name=path.name, folder=path)
    try:
        meta = tomllib.loads((path / "plugin.toml").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        plugin.error = f"plugin.toml: {error}"
        return plugin
    plugin.id = str(meta.get("id", path.name))
    plugin.name = str(meta.get("name", plugin.id))
    plugin.description = str(meta.get("description", ""))
    plugin.version = str(meta.get("version", ""))
    plugin.author = str(meta.get("author", ""))
    plugin.homepage = str(meta.get("homepage", ""))
    plugin.updates = str(meta.get("updates", ""))
    icon = str(meta.get("icon", "icon.png"))
    plugin.icon = str(path / icon) if icon and (path / icon).is_file() and "/" not in icon else ""
    plugin.module = str(meta.get("module", "plugin"))
    plugin.api = parse_api(meta.get("api"))
    return plugin


def _named() -> set[Path]:
    return {Path(p).expanduser().resolve() for p in os.environ.get("POKELDN_PLUGINS", "").split(os.pathsep) if p}


def named(plugin: Plugin) -> bool:
    """True for a plugin POKELDN_PLUGINS names, which loads whatever Settings says."""
    return plugin.folder in _named()


def discover() -> list[Plugin]:
    """Every plugin present, loaded or not: the data folder's, POKELDN_PLUGINS' and installed ones."""
    found, seen = [], set()
    local = sorted(p for p in folder().iterdir() if not p.name.startswith(".") and (p / "plugin.toml").is_file()) \
        if folder().is_dir() else []
    for path in [*sorted(_named()), *local]:
        plugin = _read_folder(path)
        if plugin.id not in seen:
            seen.add(plugin.id)
            found.append(plugin)
    for entry in metadata.entry_points(group=ENTRY_POINT_GROUP):
        if entry.name not in seen:
            seen.add(entry.name)
            found.append(Plugin(id=entry.name, name=entry.name, entry_point=entry))
    return found


def _register(plugin: Plugin) -> None:
    state, message = compatibility(plugin.api)
    if state in ("newer", "older"):
        raise RuntimeError(message)
    if plugin.entry_point is not None:
        module = plugin.entry_point.load()
    else:
        source = plugin.folder / f"{plugin.module}.py"
        spec = importlib.util.spec_from_file_location(f"pokeldn_plugin_{plugin.id}", source)
        if spec is None:
            raise RuntimeError(f"no {source.name}")
        module = importlib.util.module_from_spec(spec)
        if str(plugin.folder) not in sys.path:
            sys.path.append(str(plugin.folder))     # the plugin's own bundled modules
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    module.register(API(plugin))


def load() -> list[Plugin]:
    """Loads the plugins named in POKELDN_PLUGINS and those enabled in Settings, once per process.
    A plugin that fails keeps its error and adds nothing."""
    global _done
    if _done:
        return list(_loaded.values())
    _done = True
    on = set(enabled())
    wanted = [p for p in discover() if named(p) or p.id in on]
    if wanted:
        _guard(wanted)
    for plugin in wanted:
        _loaded[plugin.id] = plugin
        if plugin.error:          # plugin.toml did not parse
            continue
        radios_before = dict(_radios)
        if watch:
            _marker().write_text(plugin.id, encoding="utf-8")
        try:
            _register(plugin)
            plugin.loaded = True
        except (Exception, SystemExit) as error:   # a broken plugin never takes the program down
            plugin.error = f"{type(error).__name__}: {error}"
            plugin.tools.clear()
            plugin.games.clear()
            plugin.radios.clear()
            _radios.clear()
            _radios.update(radios_before)
        finally:
            if watch:
                _marker().unlink(missing_ok=True)
    return list(_loaded.values())


def _guard(wanted: list[Plugin]) -> None:
    """Puts every plugin's code under pokeldn.plugin_guard before any of it runs."""
    import tempfile
    from pokeldn import plugin_guard
    from pokeldn.app.paths import DATA, LOGS, SESSION
    code = [folder(), *_named()]
    for plugin in wanted:
        if plugin.entry_point is not None:
            try:
                spec = importlib.util.find_spec(plugin.entry_point.value.split(":")[0].split(".")[0])
            except (ImportError, ValueError):
                spec = None
            if spec is not None and spec.origin:     # a package's folder, or a lone module's own file
                code += list(spec.submodule_search_locations or [spec.origin])
    plugin_guard.install(code, [folder(), DATA / "plugin-data", SESSION, LOGS, tempfile.gettempdir(), *_named()])


watch = False     # the app sets it: a plugin that ends the app while registering is named at its next start


def _marker() -> Path:
    folder().mkdir(parents=True, exist_ok=True)
    return folder() / ".starting"


def turn_off_the_one_that_stopped(settings) -> str:
    """Turns off, in `settings`, a plugin that froze or closed the app while it started, and names it;
    then watches this start."""
    global watch
    stopped = stopped_the_app()
    watch = True
    if stopped not in settings.plugins:
        return ""
    settings.plugins = [i for i in settings.plugins if i != stopped]
    settings.save()
    return stopped


def stopped_the_app() -> str:
    """The id of a plugin the app was registering when it last ended, or "": it froze or crashed it."""
    try:
        plugin_id = (folder() / ".starting").read_text(encoding="utf-8").strip()
        (folder() / ".starting").unlink()
    except OSError:
        return ""
    return plugin_id


def tools_added() -> list[Tool]:
    return [t for p in _loaded.values() for _, t in p.tools] + \
           [t for p in _loaded.values() for g in p.games for t in g.tools]


def games() -> tuple[Game, ...]:
    """The catalog with the loaded plugins' tools and games."""
    load()
    extra: dict[str, list[Tool]] = {}
    for plugin in _loaded.values():
        for game, tool in plugin.tools:
            extra.setdefault(game, []).append(tool)
    added = [g for p in _loaded.values() for g in p.games]
    out = []
    for game in (*_builtin_games(), *added):
        more = tuple(extra.get(game.key, ()))
        out.append(replace(game, tools=game.tools + more) if more else game)
    return tuple(out)


def radio(scheme: str) -> Radio | None:
    load()
    return _radios.get(scheme)


def radios() -> list[Radio]:
    load()
    return list(_radios.values())


def _reset() -> None:
    """Forgets every loaded plugin; for tests."""
    global _done
    from pokeldn import plugin_guard
    _done = False
    _loaded.clear()
    _radios.clear()
    plugin_guard.clear()


def reload() -> list[Plugin]:
    """Loads the plugins again after Settings or the plugins folder changed. A module a plugin
    dropped stays imported; its tools and radios are gone."""
    global generation
    _reset()
    generation += 1
    return load()


def owner(tool_key: str) -> Plugin | None:
    """The loaded plugin that added the tool `tool_key`, or None for a built-in tool."""
    for plugin in _loaded.values():
        if any(t.key == tool_key for _, t in plugin.tools) or \
                any(t.key == tool_key for g in plugin.games for t in g.tools):
            return plugin
    return None
