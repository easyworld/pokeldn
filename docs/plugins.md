---
title: Plugins
---
# Plugins

A plugin adds tools, games and radios to pokeldn without changing it. It is a folder of Python files
with a `plugin.toml`, shipped as one `.pokeplugin` file that players add on the app's Plugins page.
The project does not distribute, review or support third-party plugins.

Code: `pokeldn/plugins.py` (the loader and the API), `pokeldn/app/plugin_store.py` (packages),
`pokeldn/ldn/radios.py` (the radio lookup), `gui/views/plugins.py` (the page).

Two examples are a base to start from: `examples/plugins/hello` is the smallest plugin, one tool in
two files; `examples/plugins/test_kit` uses every part of the API.

## Installing a plugin

1. Open **Plugins** at the bottom of the side menu.
2. Drop the `.pokeplugin` file on the page, or press **Add a plugin** and choose it.
3. Read what the plugin is and the risks, tick the acknowledgement, and press **Install**.

The plugin's tools appear on the Games page at once, marked with a plug and "From the plugin ...".
Each plugin's card has a switch to turn it off and on, and a menu to open its tools, update it from a
newer file, show its folder, visit its page and remove it. Every install and update shows the risk
screen again. A plugin copied into the plugins folder by hand shows "Added by hand" and asks for the
same acceptance the first time it is turned on.

A plugin that closes or freezes the app while it starts is turned off at the next start, and the app
names it. Removing a plugin asks whether to delete what it saved as well.

A plugin runs as Python inside pokeldn, with the same access to files, keys, the network and the
board. Nothing in a package runs before it is installed and turned on.

### Guardrails

Two checks stop the obvious harm. Neither is a sandbox: a plugin written to get around them can.

The install screen reads the package's Python files and lists what they do: use the network, start
other programs, delete files, call native code (`ctypes`, `cffi`), run code built at run time
(`exec`, `eval`, `compile`, `marshal`), name `prod.keys`, or ship compiled files the reading cannot
see into. An empty list means none was found, not that the plugin is safe.

While a plugin's code is on the call stack, in the app and in every run, an audit hook
(`pokeldn/plugin_guard.py`) refuses with `PermissionError`:

| refused | allowed |
|---|---|
| deleting, emptying, moving or overwriting a file outside the plugin's folders | the same inside its folder, its data folder, the session folder, the logs folder and the temporary folder |
| starting `rm`, `del`, `rd`, `Remove-Item`, `shred`, `dd`, `format`, `mkfs`, `diskutil`, `diskpart`, `sudo`, `su` and similar, directly or inside a shell command, or any command with `-delete` or `--no-preserve-root` | starting any other program |
| | creating a new file anywhere |

Code with no plugin on its call stack, pokeldn's own included, is never refused; pokeldn code a
plugin calls is. A plugin that needs a refused action asks the player to do it.

## Making a plugin

### The folder

    my-plugin/
        plugin.toml        what the plugin is
        plugin.py          register(api): what it adds
        hello.py           a tool's script
        icon.png           optional, shown on the Plugins page and the Games page
        mylib_common.py    optional, any module the scripts share

### plugin.toml

```toml
id = "my-plugin"            # required: lowercase letters, digits, dots, dashes, underscores
name = "My plugin"          # shown in the app
version = "1.0.0"           # compared on update: 1.2.0 updates 1.0.0
author = "Your name"
description = "One or two sentences shown on the install screen and the plugin's card."
homepage = "https://example.org/my-plugin"   # optional, opened from the plugin's menu
updates = "https://github.com/you/my-plugin" # optional, where newer versions are published (Updates)
api = "1.1"                 # required: the plugin API it needs (see Versions); 1 means 1.0
icon = "icon.png"           # optional; a square PNG, 96 x 96 looks sharp
module = "plugin"           # optional; the module holding register()
```

### plugin.py

`register(api)` runs when the plugin is turned on, in the app and in every run the app starts.

```python
from pokeldn.plugins import Field, Game, Tool


def register(api):
    api.add_tool("frlg", Tool(
        "my-hello",                                   # a key no other tool uses
        "Hello",                                      # the name on the Games page
        "hello.py",                                   # the script, relative to the plugin folder
        "Says hello.",                                # the line under the tool's name
        ("Nothing to do on the console.", "Press Start."),   # the console steps the app lists
        fields=(Field("--name", "Your name", default="Red"),),
        fixed=("--trainer", "{ot}"),                  # always passed; {ot} is the trainer name in Settings
    ))
```

### A tool's script

The app imports the script to read its options for the Advanced tab, then runs it as its own child
process in the session folder. The script defines `build_parser()` and does its work under
`if __name__ == "__main__"`; work at the top level runs on import and breaks the Games page.

```python
import argparse


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name")
    parser.add_argument("--trainer")
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    print(f"Hello {args.name}, from {args.trainer}'s pokeldn.")
```

| the script | the app |
|---|---|
| prints a line | shows it in the session's output |
| prints `[done] trade N complete` (`pokeldn.ldn.show_done()`) | ticks one queued trade off |
| exits with code 0 | ends the session as done |
| exits with another code or raises | shows the session as failed, with the traceback in the output |
| receives `KeyboardInterrupt` | the player pressed Stop; leave cleanly within 15 s or the process is ended |

Give shared modules a name no other package uses (`mylib_common`, not `utils`): the plugin's folder
is added to Python's search path.

### What a plugin can import

The released app carries its own Python 3.13 and no `pip`. A plugin can import:

| what | where it comes from |
|---|---|
| the standard library | bundled, except `multiprocessing`, `tkinter`, `curses`, `venv`, `ensurepip`, `profile`, `cProfile`, `pstats`, `trace`, `compileall`, `modulefinder`, `pyclbr`, `tabnanny` and the modules of another platform (`scripts/pack_app.py`, `PLUGIN_STDLIB`) |
| `trio`, `pycryptodome` (`Crypto`), `zstandard`, `pyserial` (`serial`), `websockets`, `certifi`, `bleak`, `unicorn`, `flet` | pokeldn's own dependencies, at the versions in `requirements.txt` |
| `ldn` and `pokeldn` | pokeldn itself; only the API table below is stable |
| any pure-Python module | shipped in the plugin's folder |

A package with compiled code (`numpy`, `Pillow`) works only from source runs where it is installed.
Test a plugin in a released app before publishing it: the Plugin Test Kit's self-test runs the same
way there.

### Fields

A `Field` is one input on the tool's Basic tab; the app passes its value after its flag.

| `kind` | the input | passed as |
|---|---|---|
| `text` (default) | a text box | `--flag VALUE` |
| `number` | a number box | `--flag VALUE` |
| `choice` | a dropdown of `choices=((value, label), ...)` | `--flag VALUE` |
| `switch` | an on/off switch | `--flag` when on |
| `file` | a file chooser, `exts=("bin",)` | `--flag PATH` |

### What a plugin keeps

An update replaces the plugin's folder. Settings, caches and anything else meant to last go in
`api.data` from `register`, or `pokeldn.plugins.data_folder("my-plugin")` from a tool's script: the
data folder's `plugin-data/<id>`, kept across updates and deleted on removal only if the player
asks.

`help=` puts a line under the input, `default=` fills it, and `hidden=True` moves it to the
Advanced tab. The fields the built-in tools use, and the
rest of `Field`, are in `pokeldn/app/catalog.py`. A tool's `fixed` arguments may carry `{ot}`,
`{tid}`, `{sid}` and `{language}` (the trainer in Settings), `{received}` (the Received folder) and
`{stamp}` (the run's start time).

### A game of its own

```python
api.add_game(Game("my-game", "My game", "Mine", "", (tool_one, tool_two)), icon="icon.png")
```

`Game(key, name, short, doc, tools)`; the game's section lists its tools in order, under the built-in
games. `api.add_tool("my-game", tool)` adds more to it.

### A radio

A radio carries the wireless messages in place of the ESP32 board. `api.add_radio(scheme, install,
label)` lists it on the Plugins page under **Radio**; a run started with that radio calls
`install(argument, log)` before its first wireless call.

```python
import contextlib
from ldn import wlan


def install(argument, log):
    @contextlib.asynccontextmanager
    async def factory():
        yield MyFactory()           # the interface of ldn.wlan.Factory
    wlan.set_factory(factory)


def register(api):
    api.add_radio("myradio", install, "My radio")
```

`pokeldn/ldn/esp32_wlan.py` is the board's factory and the reference for one with no kernel
interface. The app runs a plugin radio as `POKELDN_RADIO=myradio:` with an empty argument; from the
command line the argument is what follows the colon.

### Packing and testing

```bash
python scripts/pack_plugin.py my-plugin --key ~/my-plugin-signing.pem
```

writes `my-plugin-1.0.0.pokeplugin`, signed, and checks it the way the app does before installing. Any zip
works if `plugin.toml` sits at its top or inside one top folder, with no path leaving that folder
and no symbolic link.

While writing, skip the package: name the folder in `POKELDN_PLUGINS` and the plugin is on in that
process and the runs it starts, whatever the Plugins page says.

```bash
POKELDN_PLUGINS=~/my-plugin python -m pokeldn --plugins
POKELDN_PLUGINS=~/my-plugin python -m pokeldn my-hello -- --name Blue
POKELDN_PLUGINS=~/my-plugin python gui/main.py
```

`--plugins` lists every plugin found and why one failed to load. A plugin that raises in
`register`, targets another API version or takes a key in use adds nothing; its card shows the
error and the other plugins still load. A plugin can also ship as a Python package with an entry
point in the `pokeldn.plugins` group naming the module that holds `register`.

### Signing

`--key FILE` signs the package with the author's Ed25519 key, made in `FILE` the first time, and
prints the key's fingerprint (`ABCD-EFGH-IJKL-MNOP`). The package carries `plugin.sig`: the public
key and a signature over the plugin's id, its version and the SHA-256 of every other file.

| the app sees | it shows |
|---|---|
| a signature that does not match the files | refuses the file: it was changed after its author signed it |
| a signed plugin it has not seen before | the fingerprint, and remembers the key for that plugin id |
| an update signed with the remembered key | "Signed by the same author" |
| an update signed with another key, or unsigned where the earlier copy was signed | a red warning and a second acknowledgement before Install works |
| an unsigned plugin never seen signed | "Not signed" |

Keep the key file private and backed up: a lost key makes every later version look like someone
else's, and anyone holding it can sign as the author. Publish the fingerprint on the plugin's page,
so players can compare it with the one the install screen shows. The first install cannot prove who
the author is; signing proves that later versions come from the same one.

### Updates

`updates` in `plugin.toml` names where newer versions are published:

| `updates` | the app reads |
|---|---|
| `https://github.com/OWNER/REPO` | the latest release: its tag (`v1.3.0` or `1.3.0`) and its first `.pokeplugin` asset |
| any other HTTPS address | a JSON file `{"version": "1.3.0", "url": "https://.../my-plugin-1.3.0.pokeplugin", "page": "..."}` |

With Settings, Updates on, the app asks each installed plugin's address at start and when the
Plugins page's refresh is pressed. A newer version turns the Plugins menu entry green and puts
**Update to 1.3.0** on the plugin's card; pressing it downloads the file and opens the install
screen with its signature check. Nothing installs without the player's acceptance. HTTP is accepted
for `127.0.0.1` and `localhost` only, to test a release locally.

## The Plugin Test Kit

`examples/plugins/test_kit`, packed with `scripts/pack_plugin.py`, adds:

| where | tool | what it does |
|---|---|---|
| Plugin Test Kit | Self-test | checks the API version, its own loading, its imports, every field kind, the trainer token, the session folder, its data folder (a run counter that survives updates) and its radio; prints PASS or FAIL for each |
| Plugin Test Kit | Simulated session | prints a trade's steps and a `[done]` line per trade; Stop ends it cleanly |
| Plugin Test Kit | Fail on purpose | raises, or exits with code 3 |
| FireRed & LeafGreen | Hello from a plugin | a plugin tool among the built-in ones |
| Radio | Test Kit radio | installs and carries nothing; a session started with it says so |

## Versions

The plugin API has a major and a level, written `1.1`. A plugin's `api` names the lowest version it
needs; the app shows its own on the Plugins page and in `python -m pokeldn --plugins`.

| change to the API | the app |
|---|---|
| an addition | raises the level; a plugin needing a higher level is refused with "Update pokeldn" |
| a removal or a change of meaning | raises the major |
| an old major still served | `DEPRECATED` in `pokeldn/plugins.py` names the release that drops it; the plugin loads, and its card and install screen say so |
| an old major dropped | `API_OLDEST` passes it; the plugin is refused with "Ask its author for a newer version" |

A plugin's own `version` is only compared with its installed copy, to show an update, a reinstall
or a downgrade.

| API | added |
|---|---|
| 1.0 | `add_tool`, `add_game`, `add_radio`, `folder`, `version` |
| 1.1 | `api.data`, `api.level`, `pokeldn.plugins.data_folder(id)` |

## The API, version 1

| name | what it is |
|---|---|
| `api.add_tool(game, tool)` | adds a `Tool` under the game whose key is `game`: `frlg`, `lgpe`, `swsh`, `bdsp`, `pla`, `sv`, `za`, or one the plugin added |
| `api.add_game(game, icon="")` | adds a game section with its tools |
| `api.add_radio(scheme, install, label="")` | adds a radio |
| `api.folder` | the plugin's folder (a `Path`), or None for a Python package |
| `api.version`, `api.level` | the major and level the app runs, `1` and `1` |
| `api.data` | a folder kept across updates, created on first use (1.1) |
| `pokeldn.plugins.data_folder(id)` | the same folder from a tool's script (1.1) |
| `Tool`, `Field`, `Game` | the app's catalog types, imported from `pokeldn.plugins` |
| `pokeldn.ldn.show_done()` | prints the line that ticks a trade off |

This table is the supported surface. Anything else a plugin imports from pokeldn can change in any
release.
