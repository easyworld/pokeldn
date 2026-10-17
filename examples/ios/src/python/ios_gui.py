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


def _tuned_runs():
    """The run tuning the FireRed host measured on Android (examples/android/README.md, Scheduling),
    less the CPU affinity iOS does not offer: a 1 ms thread switch interval, crypto calls that keep the
    GIL, the protocol on LDN's Trio thread, and the radio closed after each in-process run."""
    import ctypes
    from Crypto.Util import _raw_api
    if _raw_api.backend == "ctypes":
        _raw_api.CDLL = ctypes.PyDLL
    import android_host_loop
    from pokeldn.app import runner
    from pokeldn.frlg.link.host_app import HostApplication
    HostApplication._timing = {}
    HostApplication.run = android_host_loop.run
    state = {}

    def before():
        state["interval"] = sys.getswitchinterval()
        sys.setswitchinterval(0.001)

    def after():
        from ldn import wlan
        from pokeldn.ldn import esp32_wlan
        radio, esp32_wlan._radio = esp32_wlan._radio, None   # a second process would have closed it
        if radio is not None:
            radio.close()
        wlan.set_factory(None)
        sys.setswitchinterval(state.get("interval", 0.005))

    runner.before_run(before)
    runner.after_run(after)


def selftest():
    """`simctl launch booted io.pokeldn.app --selftest` (or devicectl): each native piece a run needs,
    one PASS or FAIL line each in pokeldn.log."""
    import traceback

    def check(name, fn):
        try:
            print(f"selftest PASS {name}: {fn()}", flush=True)
        except Exception:
            print(f"selftest FAIL {name}: {traceback.format_exc()}", flush=True)

    def aes():
        from Crypto.Cipher import AES
        return AES.new(bytes(16), AES.MODE_ECB).encrypt(bytes(16)).hex() == "66e94bd4ef8a2c3b884cfa59ca342b2e"

    def zstd():
        from pokeldn.ldn import crypto
        return crypto.HAVE_ZSTD and len(crypto._zstd.ZstdCompressor().compress(b"pokeldn" * 50)) < 350

    def pkhex():
        from pokeldn import pokemon
        return len(pokemon.SERVICE.species("frlg"))

    def radio():
        """With a board ready over Bluetooth: HELLO round trips through main.m's bridge, against a Mac's
        32 ms on the same board (docs/hardware_esp32.md, Bluetooth)."""
        import time
        from pokeldn.app import ios
        from pokeldn.ldn import esp32
        for _ in range(100):   # the bridge connects in the first seconds
            if ios.radio_state() == "ready":
                break
            time.sleep(0.1)
        else:
            return "no board ready; module imports"
        r = esp32.Radio.open_serial(ios.port())
        try:
            n, start = 200, time.monotonic()
            for _ in range(n):
                r.request(esp32.CMD_HELLO, b"", esp32.MSG_INFO, timeout=3)
            rtt = (time.monotonic() - start) / n * 1000
            status = r.request(esp32.CMD_STATUS, b"", esp32.MSG_STATUS, timeout=3).decode(errors="replace")
            interval = next((w for w in status.split() if w.startswith("ble_itvl_us=")), "")
            return f"{r.info.text}; HELLO round trip {rtt:.1f} ms; {interval}"
        finally:
            r.close()

    for name, fn in (("aes", aes), ("zstd", zstd), ("pkhex", pkhex), ("radio module", radio)):
        check(name, fn)


def profile():
    """`--profile` at launch: pokeldn.app.sampler writing Documents/profile.txt."""
    from pokeldn.app import sampler
    sampler.start(os.path.join(os.environ["POKELDN_IOS_DOCUMENTS"], "profile.txt"))


def clean():
    """`--clean` at launch: what --selftest, --host-test and --profile left in Documents, a prod.keys copied
    in over the cable, the session captures and offers, and Python's log; the keys the app picked stay."""
    import glob
    import shutil
    documents = os.environ["POKELDN_IOS_DOCUMENTS"]
    for name in ("offer.pk3", "prod.keys", "profile.txt", "host-test.log", "host-test.jsonl",
                 "host-test_received.pk3", "pokeldn.log"):
        try:
            os.remove(os.path.join(documents, name))
        except OSError:
            pass
    for folder in glob.glob(os.path.join(documents, "data", "session", "*")):
        shutil.rmtree(folder, ignore_errors=True)


def host_test():
    """`--host-test` at launch: the FireRed Trade (Host) launcher alone, with the app's run tuning and no
    interface, so its link rate can be set against a run from the interface. Inputs and outputs are
    in Documents: prod.keys, offer.pk3; host-test.log, host-test.jsonl, host-test_received.pk3."""
    from pokeldn.app import runner
    documents = os.environ["POKELDN_IOS_DOCUMENTS"]
    argv = ["--run", "bin/frlg_trade_host.py", "--live", "--phy", "auto", "--keys", f"{documents}/prod.keys",
            f"{documents}/offer.pk3", "--slot", "0", "-o", f"{documents}/host-test_received.pk3",
            "--capture", f"{documents}/host-test.jsonl"]
    done = threading.Event()
    log = open(f"{documents}/host-test.log", "w", buffering=1)
    os.environ["POKELDN_RADIO"] = "esp32:" + os.environ["POKELDN_IOS_RADIO"]
    runner.InProcess(argv, os.getcwd(), dict(os.environ), lambda line: log.write(line + "\n"),
                     lambda code: (log.write(f"exit {code}\n"), done.set()))
    done.wait()


def main():
    signal.signal = _signal_on_main_thread_only
    import webbrowser   # Flet's web view opens a browser; on iOS that is Safari, over the app
    webbrowser.open = lambda *args, **kwargs: True
    documents = Path(os.environ["POKELDN_IOS_DOCUMENTS"])
    os.environ.update(HOME=str(documents), POKELDN_DATA=str(documents / "data"), POKELDN_PLATFORM="ios",
                      POKELDN_RADIO="esp32:" + os.environ["POKELDN_IOS_RADIO"])
    app = Path(__file__).resolve().parent
    os.environ["POKELDN_IOS_BUNDLE"] = str(app.parent)
    os.environ["POKELDN_PKHEX"] = str(app.parent / "Frameworks" / "pokeldn_pkhex.framework" / "pokeldn_pkhex")
    os.chdir(app)
    from pokeldn.app import ios
    ios.install()
    try:
        _crypto_libraries()
    except ImportError:
        pass
    _tuned_runs()
    if os.environ.get("POKELDN_IOS_SELFTEST"):
        selftest()
    if os.environ.get("POKELDN_IOS_CLEAN"):
        clean()
    if os.environ.get("POKELDN_IOS_PROFILE"):
        profile()
    if os.environ.get("POKELDN_IOS_HOSTTEST"):
        host_test()
    from gui import main as gui_main
    gui_main.run()


if __name__ == "__main__":
    main()
