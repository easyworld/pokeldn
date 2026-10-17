# iOS app

The iOS app runs the desktop app's own interface on an iPhone or iPad, with the radio board reached
over Bluetooth: an iPhone app cannot open a USB serial device without Apple's MFi program. The board
runs the Bluetooth radio firmware ([Bluetooth](../../docs/hardware_esp32.md#bluetooth)) and needs USB
only for power. Every page, game and tool is the code in `gui/` and `pokeldn/`; only the shell in this
folder is iOS's.

On an iPhone 13 Pro with a XIAO ESP32C6 running the Bluetooth firmware, the app completes retail
FireRed host trades: 34.6 unique link slots per second from the interface, 41.0 with `--host-test`
(a Mac over the same Bluetooth link: 41.7; Android over USB: 51). The interface shares the run's
interpreter: with a 1500-line session log redrawn four times a second, Flet's diffing held the main
thread 75% of the time and the run fell to 12.2; a phone keeps 300 lines and redraws once a second
(`gui/views/widgets.py` Log). Each auto-scroll of that log also made Flet re-diff the whole page, which
`theme.fade` now prevents (examples/android/README.md). With a 30 ms connection interval and no run tuning the same trade
crawled at 4.4. A Legends Z-A joiner trade from the same phone completed in 27 s. The run takes Android's tuning (`ios_gui._tuned_runs`, the shared Trio
loop from `examples/android/src/python/android_host_loop.py`) less its CPU affinity. In the iOS Simulator the
interface and the self-test run; the simulator has no Bluetooth, so no run reaches a board there.

## How it works

| piece | what it does |
|---|---|
| `src/main.m` | starts BeeWare's embedded CPython on its own thread, which serves `gui/main.py` as Flet's web app on 127.0.0.1:8550, and shows it in a WKWebView inside the safe area |
| `RadioBridge` in `main.m` | CoreBluetooth: finds the board by its service, subscribes to its TX characteristic and carries the byte stream on 127.0.0.1:47811, one connection at a time; writes without response are paced by `canSendWriteWithoutResponse` |
| `src/python/ios_gui.py` | sets the environment (`POKELDN_PLATFORM=ios`, data in the app's Documents, `POKELDN_RADIO=esp32:socket://127.0.0.1:47811`), installs the port list and the pycryptodome loader, keeps Flet from opening Safari |
| `pokeldn/app/ios.py` | lists the Bluetooth radio as the one serial port while `main.m` reports it ready (`Documents/.radio`); `Picker` stands in for Flet's web picker, which gives no paths |
| `FileBridge` in `main.m` | the document picker and the export sheet, asked over 127.0.0.1:47812 (`pick 0`, `pick 1`, `save PATH`); a picked file is copied into the app |
| `pokeldn/app/runner.py` `InProcess` | runs a launcher on the app's own interpreter, as on Android: iOS starts no second process |
| `services/pkhex/Library.cs` | PKHeX compiled ahead of time as `Frameworks/pokeldn_pkhex.framework`; `pokeldn.pokemon._Library` runs its request loop on a thread over two pipes, since iOS starts no second process |
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

```sh
./.venv/bin/python examples/ios/build.py --run-on DEVICE --team TEAM
```

signs with the Mac's Apple Development identity and installs on a paired iPhone (`xcrun devicectl
list devices` names it; the team ID is in Xcode, Settings, Accounts). Xcode issues a development
profile only for a project it builds, so `build.py` has it build a one-file stub app with the same
bundle identifier and reuses that profile. A free personal team's profile lasts seven days. On the
phone, Settings, General, VPN and Device Management trusts the developer once.

Launch flags, for `xcrun devicectl device process launch --device DEVICE io.pokeldn.app FLAG`:

| flag | what it does |
|---|---|
| `--selftest` | one `selftest PASS` or `FAIL` line per native piece in `pokeldn.log`; with a board ready, 200 HELLO round trips and the granted interval |
| `--host-test` | FireRed Trade (Host) with no interface, from `Documents/offer.pk3` and `Documents/prod.keys` (`devicectl device copy to`), into `host-test.log` and `host-test.jsonl` |
| `--profile` | samples every thread's Python frame every 10 ms into `Documents/profile.txt` |
| `--clean` | deletes what the flags above, the session captures and offers left in Documents; picked keys stay |

`devicectl` copies files but deletes none, hence `--clean`.

`--selftest` at launch (`xcrun simctl launch booted io.pokeldn.app --selftest`, or `xcrun devicectl
device process launch --device DEVICE io.pokeldn.app --selftest`) writes one `selftest PASS` or
`selftest FAIL` line per native piece to `pokeldn.log`: AES, zstd, PKHeX, the radio module.

iOS 27 on a device stops at launch an app with no scene lifecycle (UIKit's
`NoSceneLifecycleAdoption` trap); the simulator does not. `main.m` has a `SceneDelegate` for it.

`build.py` installs the pure-Python packages from PyPI (pinned as `examples/android/build.gradle`
pins them, msgpack built without its C extension, `examples/android/src/python/fastapi` in place of
FastAPI) and compiles the two C libraries a run needs that have no iOS wheel: pycryptodome's ctypes
libraries and zstandard's extension. Every `.so` becomes `Frameworks/<module>.framework` with a
`.fwork` file in its place, as BeeWare's `build/utils.sh` does; `ios_gui.py` points pycryptodome's
ctypes loader at them. PKHeX is published with `--artifacts-path build/pkhex/artifacts`: a publish into
`services/pkhex/bin` would replace the desktop helper there.

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
| Unicorn | iOS allows no JIT for a sideloaded app without a debugger; payloads are not executed offline before they are sent |
| firmware install | the board flashes over USB from a computer: the desktop app's Board page installs Bluetooth wireless |
| the Control page | the controller board's link is bleak on a desktop |
