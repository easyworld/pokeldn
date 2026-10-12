"""Run the same tool presets as the desktop app."""
import argparse
import os

from pokeldn import plugins
from pokeldn.app import command, runner, settings
from pokeldn.pokemon import BuilderError


def main(argv=None):
    runner.utf8_output()
    games = plugins.games()
    tools = {tool.key: tool for game in games for tool in game.tools}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="list available tools")
    parser.add_argument("--radio", help="radio backend, e.g. esp32:auto, or SCHEME:ARG a plugin adds")
    parser.add_argument("--plugins", action="store_true", help="list plugins and whether they loaded")
    parser.add_argument("tool", nargs="?", choices=tuple(tools))
    parser.add_argument("args", nargs=argparse.REMAINDER, help="arguments passed to the tool")
    args = parser.parse_args(argv)
    if args.plugins:
        loaded = {p.id: p for p in plugins.load()}
        print(f"plugin API {plugins.API_VERSION}.{plugins.API_LEVEL}")
        for plugin in plugins.discover():
            state = loaded.get(plugin.id)
            status = "off" if state is None else (f"failed: {state.error}" if state.error else "loaded")
            level, message = plugins.compatibility(plugin.api)
            note = f" ({message})" if level == "deprecated" else ""
            print(f"{plugin.id:20} {plugin.name}, API {plugins.api_text(plugin.api)}: {status}{note}")
        return 0
    if args.list:
        for game in games:
            for tool in game.tools:
                print(f"{tool.key:20} {game.name}: {tool.name}")
        return 0
    if not args.tool:
        parser.print_help()
        return 0
    profile = settings.load()
    if args.radio:
        os.environ["POKELDN_RADIO"] = args.radio
    tool = tools[args.tool]
    overrides = args.args[1:] if args.args[:1] == ["--"] else args.args
    try:
        runner.child(["--run", tool.script, *command.build(tool, {}, {}, profile), *overrides])
    except BuilderError as exc:
        parser.exit(1, f"{exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
