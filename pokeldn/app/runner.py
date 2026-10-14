import _thread
import os
import runpy
import subprocess
import sys
import threading
import time
from typing import Callable

from pokeldn.app.paths import ROOT

# Session and flash runs are child processes of the app itself (`--run` / `--module`), which
# also works inside a packaged app where no separate python executable exists.


_closing: list[Callable[[], None]] = []


def at_app_close(hook: Callable[[], None]) -> None:
    """Runs `hook` in the child when the app closes its stdin, before the KeyboardInterrupt: for a child whose
    main thread the interrupt does not leave (pokeldn.pad.service)."""
    _closing.append(hook)


def _read_the_app() -> None:
    # The app answers the child's pop-ups on its stdin (pokeldn.popup) and stops a managed run by closing it; the
    # close raises the same KeyboardInterrupt as Ctrl-C, which a windowless child on Windows cannot receive as a
    # signal.
    from pokeldn import popup
    for line in sys.stdin:
        popup.receive(line)
    for hook in list(_closing):
        hook()
    if os.environ.get("POKELDN_MANAGED_RUN"):
        _thread.interrupt_main()


def utf8_output() -> None:
    """Use the same UTF-8 output for CLI commands and managed runs, including pipes."""
    for stream in (sys.stdout, sys.stderr):
        if stream and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", line_buffering=True)


def child(argv: list[str]) -> None:
    """Runs in the child: an entry point script or a module, as `python -u` would."""
    utf8_output()
    if sys.stdin and (os.environ.get("POKELDN_MANAGED_RUN") or os.environ.get("POKELDN_POPUPS")):
        threading.Thread(target=_read_the_app, daemon=True).start()
    mode, target, *args = argv
    if mode == "--run":
        path = os.path.join(ROOT, target)
        if os.path.isabs(target):     # a plugin's script: loading the plugins puts it under their guardrails
            from pokeldn import plugins
            plugins.load()
        sys.argv = [path, *args]
        sys.path.insert(0, os.path.dirname(path))
        runpy.run_path(path, run_name="__main__")
    else:
        sys.argv = [target, *args]
        runpy.run_module(target, run_name="__main__", alter_sys=True)


# macOS 26 delivers no Bluetooth LE discoveries to a background process signed as an app's main
# executable; this bare-signed copy of it gets an active scan (scripts/pack_app.py, docs/gui.md).
BLUETOOTH_HELPER = os.path.join(os.path.dirname(os.path.dirname(sys.executable)), "Helpers", "pokeldn-bluetooth")


def command(*argv: str, bluetooth: bool = False) -> list[str]:
    if getattr(sys, "frozen", False):
        if bluetooth and sys.platform == "darwin" and os.path.isfile(BLUETOOTH_HELPER):
            return [BLUETOOTH_HELPER, *argv]
        return [sys.executable, *argv]
    return [sys.executable, "-u", os.path.join(ROOT, "pokeldn", "app", "entry.py"), *argv]


class Process:
    """A child of the app. With `popups` (pokeldn.app.popups.Manager), the child's `[popup]` lines open pop-ups
    under `label`, never reaching `on_line`, and their answers go back on its stdin (pokeldn.popup)."""

    def __init__(self, argv: list[str], cwd: str, env: dict, on_line: Callable[[str], None],
                 on_exit: Callable[[int], None], bluetooth: bool = False, popups=None, label: str = ""):
        self.on_line, self.on_exit = on_line, on_exit
        self.stdin_lock = threading.Lock()
        if popups is not None:
            env = dict(env, POKELDN_POPUPS="1")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.proc = subprocess.Popen(command(*argv, bluetooth=bluetooth), cwd=cwd, env=env, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                     encoding="utf-8", errors="replace", bufsize=1,
                                     creationflags=flags)
        self.started = time.monotonic()
        self.popups = popups.program(label, self.send) if popups is not None else None
        threading.Thread(target=self._pump, daemon=True).start()

    @property
    def running(self) -> bool:
        return self.proc.poll() is None

    def _pump(self) -> None:
        from pokeldn import popup
        for line in self.proc.stdout:
            line = line.rstrip("\n")
            before, message = popup.read(line) if self.popups is not None else (line, None)
            if message is None:
                self.on_line(line)
                continue
            if before.strip():
                self.on_line(before)
            self.popups.take(message)
        self.proc.stdout.close()
        with self.stdin_lock:
            if not self.proc.stdin.closed:
                self.proc.stdin.close()
        if self.popups is not None:
            self.popups.ended()
        self.on_exit(self.proc.wait())

    def send(self, message: dict) -> None:
        """Answers one of the child's pop-ups on its stdin; a child that has stopped reading gets nothing."""
        from pokeldn import popup
        with self.stdin_lock:
            try:
                self.proc.stdin.write(popup.line(message) + "\n")
                self.proc.stdin.flush()
            except (OSError, ValueError):
                pass

    def stop(self) -> None:
        # An interrupt lets the entry point leave the network and close the board; a launcher
        # that ignores it for 15 s is terminated.
        if not self.running:
            return
        with self.stdin_lock:
            try:
                self.proc.stdin.close()
            except OSError:
                pass
        threading.Thread(target=self._escalate, daemon=True).start()

    def _escalate(self) -> None:
        for action, wait in ((None, 15), (self.proc.terminate, 5), (self.proc.kill, 0)):
            if action:
                action()
            try:
                self.proc.wait(wait or None)
                return
            except subprocess.TimeoutExpired:
                continue


def base_env(settings, port: str, trace: str | None = None) -> dict:
    env = dict(os.environ, PYTHONUNBUFFERED="1", POKELDN_ESP32_BAUD=str(settings.baud),
               POKELDN_MANAGED_RUN="1", POKELDN_HOME_TRACKER=settings.home_tracker)
    env["POKELDN_RADIO"] = f"{settings.radio}:" if settings.radio else f"esp32:{port or 'auto'}"
    if trace:
        env["POKELDN_ESP32_TRACE"] = trace
    return env
