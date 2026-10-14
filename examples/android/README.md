# Android USB prototype

This developer example runs the existing FireRed/LeafGreen Python host on Android through
Chaquopy and a native USB CDC stream. A OnePlus CPH2621 running Android 16 powered a XIAO
ESP32C6 over USB-C, completed a smooth retail FireRed trade and saved a PKHeX-legal received
Pokemon. The console left the room and wireless session cleanly.

The frontend is a diagnostic Activity. Full mobile GUI, on-phone PKHeX, background services,
firmware installation and retail Android trades for other games remain unimplemented or
unmeasured. [Android setup requirements](../../docs/gui.md#android-setup-requirements) defines
the guided USB/OTG flow required for the mobile GUI.

## Build

Run from the repository root with JDK 21, Android SDK 36 / build tools 36.1.0, Python 3.13
and Gradle 8.13 installed. The Gradle build pins AGP 8.13.0 and Chaquopy 17.0.0.

```sh
python3.13 -m pip wheel --no-deps --wheel-dir examples/android/wheels python-netlink==0.0.15
python3.13 examples/android/stage.py
gradle -p examples/android --no-daemon --console=plain assembleDebug
adb -s PHONE_IP:PORT install -r examples/android/build/outputs/apk/debug/PokeLDNPythonProbe-debug.apk
```

`stage.py` copies tracked Python sources and package data into the ignored `staged/` directory.
Keys, Pokemon records, captures, APKs, Gradle caches and signing keys remain local. Android wheels
use PyCryptodome 3.21.0 and Zstandard 0.23.0; other trade dependencies retain the tested pins.
`POKELDN_ANDROID_BUILD_PYTHON` selects the build interpreter when `python3.13` is not on PATH.

The debug build uses Android's local debug signing key. `assembleRelease` produces a release
APK signed with that same key for local testing. `POKELDN_ANDROID_KEYSTORE` selects an existing
compatible Android debug keystore when updating an earlier installation. Preserve the signing
key to retain access to the existing app's private files during updates. These debug signatures
are for development distribution.

## Private inputs and trade

Start the installed diagnostic once and grant USB access. On phones with a separate USB host
or OTG toggle, enable it in Settings. Use a data-capable cable and the C6's native USB port.
The tested OnePlus enumerated the board immediately after enabling OTG connection.

Provision the user's own Switch keys and a PK3 while the debuggable APK is installed. The desktop
Python environment needs the repository's PKHeX service available. This command validates the
offer, copies the inputs directly to private app storage and enables the tested crypto option:

```sh
python examples/android/provision.py --device PHONE_IP:PORT --keys /path/to/prod.keys --offer /path/to/offer.pk3
adb -s PHONE_IP:PORT shell am start -f 0x20000000 -n org.pokeldn.usbprobe/.MainActivity --es mode trade
```

On the Switch, open the FireRed/LeafGreen wireless Trade Center and join POKELDN. The host uses
channel 11 and six participant slots, matching the desktop launcher. The Activity's Stop trade
button requests cooperative cleanup. The native USB bridge retains released DTR/RTS lines and
the existing Python Radio's framing, checksums, request handling and flow control.

The offer's SHA-256 must match its desktop validation manifest before hosting. Received records
and diagnostic outputs go into separate timestamped private `files/trade/run-*` directories.
The APK contains no user keys or Pokemon records. ADB is developer tooling for this example;
the mobile GUI requires its own input import and USB setup flow.

## Scheduling and validation

The protocol coroutine runs on the same Trio thread as LDN. Before creating radio and network
threads, the worker selects the allowed CPU with highest sysfs `cpu_capacity` and restricts its
CPU affinity to that core. The worker restores its original affinity during cleanup. On the
SM6375 test phone this selected core 6. The tested configuration uses synchronous USB writes,
a 1 ms Python thread-switch interval and `ctypes.PyDLL` for the tiny native crypto calls.

The initial host ran about 10 parent slots/s with slow movement and an extended animation wait.
The shared Trio loop alone improved scheduling but remained slow. With affinity, the player
reported smooth movement and a completed trade; the capture measured 51.1 unique parent UNI
slots/s. Every console block fragment was echoed, and the received PK3 passed desktop PKHeX.
These observations cover this phone and board; other devices need measurement.

```sh
python examples/android/check_shared_loop.py
```

This desktop check verifies protocol ticks run on the network's Trio thread, room-close grace
continues after departure and cleanup stops the worker. The Activity's Test Python button runs
imports, AES known-answer and Trio checks, existing simulated fragmented LDN and two-trade loss/
duplicate/reordering tests, 100 real HELLOs, receive BENCH and a 5000-command output count check.

## Diagnostics

Logs use `PokeLDNPython`, `python.stderr` and `AndroidRuntime`. The host aggregates numeric call
counts, elapsed time and calling-thread CPU time every five seconds into `timing.jsonl` and
`HOST_TIMING`. `async_wait.cpu_ms` includes LDN tasks running on the same thread while the
protocol coroutine waits.

Activity intent modes `profile`, `uplink` and `replay` select developer diagnostics. Profile
measures packet processing with idle or receiving USB traffic. Uplink compares original and
performance-core CPU placement, with optional Java write batching, while the radio is idle;
each case checks board command counts and wire checksums. Replay runs the most recent private
host capture through the full peer/session with a virtual protocol clock. All diagnostics
require a connected board; replay requires an existing capture and private keys.

While a trade worker is active, `--es experiment stop` requests cleanup, `memory_trace` retains
trace records in memory until cleanup, and `switch_us_N` changes the thread-switch interval.
Use these with `am start -f 0x20000000` as above. Force-stopping a memory-trace run loses that
portion of its capture. Java queued writes remain disabled in the validated live configuration.

A private `files/trade/enable_profile` marker enables a short connected cProfile recording.
Live cProfile results in this embedded runtime interleaved threads and produced unreliable
caller relationships. A cross-thread `sys._current_frames` sampler triggered a JNI reference
error and was removed. Debug APKs enable CheckJNI; release APKs omit that extra checking.
`run-as` requires a debuggable APK, so stop the release worker before temporarily updating to
debug to retrieve private outputs, then restore the tested release. Wi-Fi APK installation can
progress silently for several minutes.
