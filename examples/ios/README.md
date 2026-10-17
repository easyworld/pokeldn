# iOS app

The iOS app runs the desktop app's own interface on an iPhone or iPad, with the radio board reached
over Bluetooth: an iPhone app cannot open a USB serial device without Apple's MFi program. The board
runs the Bluetooth radio firmware ([Bluetooth](../../docs/hardware_esp32.md#bluetooth)) and needs USB
only for power. Every page, game and tool is the code in `gui/` and `pokeldn/`; only the shell in this
folder is iOS's.

It runs in the iOS Simulator: the interface starts and shows the phone layout. The simulator has no
Bluetooth, so no run reaches a board there. It has not yet run on an iPhone.

## How it works

| piece | what it does |
|---|---|
| `src/main.m` | starts BeeWare's embedded CPython on its own thread, which serves `gui/main.py` as Flet's web app on 127.0.0.1:8550, and shows it in a WKWebView inside the safe area |
| `RadioBridge` in `main.m` | CoreBluetooth: finds the board by its service, subscribes to its TX characteristic and carries the byte stream on 127.0.0.1:47811, one connection at a time; writes without response are paced by `canSendWriteWithoutResponse` |
| `src/python/ios_gui.py` | sets the environment (`POKELDN_PLATFORM=ios`, data in the app's Documents, `POKELDN_RADIO=esp32:socket://127.0.0.1:47811`), installs the port list and the pycryptodome loader, keeps Flet from opening Safari |
| `pokeldn/app/ios.py` | lists the Bluetooth radio as the one serial port while `main.m` reports it ready (`Documents/.radio`); `Picker` stands in for Flet's web picker, which gives no paths |
| `FileBridge` in `main.m` | the document picker and the export sheet, asked over 127.0.0.1:47812 (`pick 0`, `pick 1`, `save PATH`); a picked file is copied into the app |
| `pokeldn/app/runner.py` `InProcess` | runs a launcher on the app's own interpreter, as on Android: iOS starts no second process |
| `build.py` | the bundle, with no Xcode project |

`pokeldn.ldn.esp32` opens a `socket://` port with pyserial's `serial_for_url`; the wire is the same COBS
stream as over USB, with no line rate.

## Build

Needs Xcode, `gh` (to fetch BeeWare's Python-Apple-support `3.13-b16` into `support/` once) and the
repository's `.venv` (Python 3.13).

```sh
./.venv/bin/python examples/ios/build.py --install
```

builds for the simulator and launches it on the booted one;

```sh
./.venv/bin/python examples/ios/build.py --device
```

writes `build/pokeldn-ios.ipa`, unsigned. AltStore or SideStore signs it on the phone with the
player's own Apple ID.

`build.py` installs the pure-Python packages from PyPI (pinned as `examples/android/build.gradle`
pins them, msgpack built without its C extension, `examples/android/src/python/fastapi` in place of
FastAPI) and compiles the two C libraries a run needs that have no iOS wheel: pycryptodome's ctypes
libraries and zstandard's extension. Every `.so` becomes `Frameworks/<module>.framework` with a
`.fwork` file in its place, as BeeWare's `build/utils.sh` does; `ios_gui.py` points pycryptodome's
ctypes loader at them.

Python's output goes to `pokeldn.log` in the app's Documents folder (Files, On My iPhone, pokeldn).
CPython on iOS otherwise sends `print` to the system log.

## Release

The release workflow's `ios` job builds `pokeldn-ios.ipa` on macOS and attaches it to the release; the
`firmware` job adds `pokeldn-radio-ble-c6.bin` and `pokeldn-radio-ble.bin`. After a release,
`scripts/altstore_source.py` rebuilds `.github/altstore/source.json` from the published releases;
commit it. Players add the feed in AltStore or SideStore:

    https://raw.githubusercontent.com/Decryptu/pokeldn/main/.github/altstore/source.json

## Not in the iOS app

| missing | why |
|---|---|
| PKHeX | the .NET helper has no iOS build here; PKHeX-backed preparation, the Bank's conversions and save editing fail |
| Unicorn | iOS allows no JIT for a sideloaded app without a debugger; payloads are not executed offline before they are sent |
| firmware install | the board flashes over USB from a computer (the desktop app's Board page) |
| the Control page | the controller board's link is bleak on a desktop |
