"""Checks one by one what a plugin tool relies on and prints PASS or FAIL for each."""
import argparse
import os
import sys
import tempfile

import testkit_common as kit


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--word", default="")
    parser.add_argument("--number", type=int, default=0)
    parser.add_argument("--color", choices=("red", "blue", "green"), default="red")
    parser.add_argument("--loud", action="store_true")
    parser.add_argument("--trainer", default="")
    return parser


def radio_check():
    import trio
    from ldn import wlan
    saved = os.environ.get("POKELDN_RADIO")
    os.environ["POKELDN_RADIO"] = "testkit:selftest"
    wlan.set_factory(None)

    async def open_factory():
        async with wlan.create_factory() as factory:
            return type(factory).__name__
    try:
        return trio.run(open_factory)
    finally:
        wlan.set_factory(None)
        if saved is None:
            os.environ.pop("POKELDN_RADIO", None)
        else:
            os.environ["POKELDN_RADIO"] = saved


def main():
    args = build_parser().parse_args()
    results = []

    def check(label, ok, detail=""):
        results.append(ok)
        kit.say(f"{'PASS' if ok else 'FAIL'}  {label}" + (f": {detail}" if detail else ""))

    kit.say(f"Python {sys.version.split()[0]}, working folder {os.getcwd()}")
    managed = os.environ.get("POKELDN_MANAGED_RUN") == "1"
    kit.say(("Started by the app" if managed else "Started from the command line") +
            f", radio {os.environ.get('POKELDN_RADIO') or 'none'}")

    from pokeldn import plugins
    state, message = plugins.compatibility((1, 1))
    check("the plugin API serves 1.1", state == "ok", message or f"pokeldn runs {plugins.API_VERSION}.{plugins.API_LEVEL}")
    state = {p.id: p for p in plugins.load()}.get("test-kit")
    check("this plugin loaded in the run", bool(state and state.loaded and not state.error),
          state.error if state else "not enabled here")
    tools = {t.key for g in plugins.games() for t in g.tools}
    check("the catalog lists the kit's tools", {"test-kit-selftest", "test-kit-hello"} <= tools)
    check("its own module imports", kit.__name__ == "testkit_common")
    check("arguments arrive", args.word != "" and isinstance(args.number, int),
          f"word={args.word!r} number={args.number} color={args.color} switch={'on' if args.loud else 'off'}")
    check("the trainer name arrives", bool(args.trainer), args.trainer)
    try:
        with tempfile.NamedTemporaryFile(dir=os.getcwd(), prefix="test-kit-"):
            pass
        check("the working folder is writable", True)
    except OSError as error:
        check("the working folder is writable", False, str(error))
    try:
        data = plugins.data_folder("test-kit")
        data.mkdir(parents=True, exist_ok=True)
        runs = data / "runs.txt"
        count = (int(runs.read_text()) if runs.is_file() else 0) + 1
        runs.write_text(str(count))
        check("its data folder keeps what it writes", True, f"self-test run {count}, kept across updates")
    except (OSError, ValueError) as error:
        check("its data folder keeps what it writes", False, str(error))
    try:
        name = radio_check()
        check("the kit's radio installs", name == "KitFactory", name)
    except Exception as error:
        check("the kit's radio installs", False, f"{type(error).__name__}: {error}")

    passed = sum(results)
    kit.say(f"{passed} of {len(results)} checks passed" + ("." if passed == len(results) else ", see FAIL above."))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
