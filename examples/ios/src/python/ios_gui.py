"""Runs the desktop app's interface (gui/main.py) as the local web server the app's WKWebView shows,
with the radio board reached over Bluetooth through main.m's socket (examples/ios/README.md)."""
import os
import signal
import sys
import threading
from pathlib import Path

_signal = signal.signal


def _signal_on_main_thread_only(signum, handler):
    # main.m runs Python on its own thread; Flet and the launchers install SIGINT handlers.
    # Trio asks signal.signal whether it is on the main thread: it gets the real refusal.
    caller = sys._getframe(1).f_globals.get("__name__", "")
    if threading.current_thread() is threading.main_thread() or caller.startswith("trio"):
        return _signal(signum, handler)
    return signal.getsignal(signum)


def _crypto_libraries():
    # PyCryptodome loads its C code with ctypes from beside each module; on iOS a library lives in
    # the bundle's Frameworks as Name.framework/Name (build.py), and a .fwork file says where.
    from Crypto.Util import _file_system, _raw_api
    original = _raw_api.load_pycryptodome_raw_lib

    def load(name, cdecl):
        *package, base = name.split(".")
        for suffix in _raw_api.extension_suffixes:
            fwork = Path(_file_system.pycryptodome_filename(package, base + suffix.removesuffix(".so") + ".fwork"))
            if fwork.is_file():
                return _raw_api.load_lib(str(Path(os.environ["POKELDN_IOS_BUNDLE"]) / fwork.read_text().strip()), cdecl)
        return original(name, cdecl)

    _raw_api.load_pycryptodome_raw_lib = load


def main():
    signal.signal = _signal_on_main_thread_only
    import webbrowser   # Flet's web view opens a browser; on iOS that is Safari, over the app
    webbrowser.open = lambda *args, **kwargs: True
    documents = Path(os.environ["POKELDN_IOS_DOCUMENTS"])
    os.environ.update(HOME=str(documents), POKELDN_DATA=str(documents / "data"), POKELDN_PLATFORM="ios",
                      POKELDN_RADIO="esp32:" + os.environ["POKELDN_IOS_RADIO"])
    app = Path(__file__).resolve().parent
    os.environ["POKELDN_IOS_BUNDLE"] = str(app.parent)
    os.chdir(app)
    from pokeldn.app import ios
    ios.install()
    try:
        _crypto_libraries()
    except ImportError:
        pass
    from gui import main as gui_main
    gui_main.run()


if __name__ == "__main__":
    main()
