"""The app on iOS (examples/ios): the radio board over Bluetooth, which the app's own code (main.m)
carries on a local socket, listed as the one serial port so the Board page and the launchers reach
it unchanged."""
import os
import sys

VID, PID = 0x303A, 0x1001   # listed as native USB: the board's firmware speaks the same wire


def active() -> bool:
    return os.environ.get("POKELDN_PLATFORM") == "ios"


def port() -> str:
    return os.environ.get("POKELDN_IOS_RADIO", "")


CONTAINER = "/var/mobile/Containers/Data/Application/"


def rebase(value):
    """A path saved under an earlier install's data container, moved to this one: iOS gives the app a
    new container path on every install and update, and refuses the old one (Errno 1)."""
    home = os.environ.get("POKELDN_IOS_DOCUMENTS", "")
    for prefix in (CONTAINER, "/private" + CONTAINER):
        if isinstance(value, str) and value.startswith(prefix) and home:
            current = os.path.dirname(home)   # the container: Documents' parent
            rest = value[len(prefix):].split("/", 1)
            return os.path.join(current, rest[1]) if len(rest) == 2 else current
    return value


def radio_state() -> str:
    """off, scanning or ready: what main.m last wrote to Documents/.radio."""
    try:
        with open(os.path.join(os.environ["POKELDN_IOS_DOCUMENTS"], ".radio")) as f:
            return f.read().strip() or "off"
    except (KeyError, OSError):
        return "off"


class _Port:
    """A ListPortInfo for the board, the fields gui.board and esp32_wlan read."""

    def __init__(self):
        self.device, self.vid, self.pid = port(), VID, PID
        self.serial_number = self.description = self.product = "Bluetooth radio"
        self.manufacturer, self.hwid, self.location, self.interface = "Espressif", "BLE", "", ""

    def __getitem__(self, index):
        return (self.device, self.description, self.hwid)[index]


def comports(include_links=False):
    return [_Port()] if radio_state() == "ready" else []


def install() -> None:
    """Before anything imports serial.tools.list_ports: pyserial has no port list for iOS."""
    import types
    posix = types.ModuleType("serial.tools.list_ports_posix")
    posix.comports = comports
    sys.modules["serial.tools.list_ports_posix"] = posix


CONTROL = ("127.0.0.1", 47812)   # main.m FileBridge


def _ask(request: str) -> list[str]:
    import socket
    with socket.create_connection(CONTROL) as s:
        s.sendall(request.encode() + b"\n")
        reply = b""
        while not reply.endswith(b"\n"):
            chunk = s.recv(4096)
            if not chunk:
                break
            reply += chunk
    return [line for line in reply.decode().strip().split("\n") if line]


class PickedFile:
    def __init__(self, path: str):
        self.path, self.name, self.size = path, os.path.basename(path), os.path.getsize(path)


class Picker:
    """flet.FilePicker's three calls on iOS's document picker: in a web view Flet's picker returns no paths."""

    async def pick_files(self, allow_multiple: bool = False, allowed_extensions=None, **_):
        import asyncio
        paths = await asyncio.to_thread(_ask, f"pick {int(bool(allow_multiple))}")
        files = [PickedFile(_keep(p)) for p in paths]
        if allowed_extensions:
            wanted = {e.lower().lstrip(".") for e in allowed_extensions}
            files = [f for f in files if f.name.rsplit(".", 1)[-1].lower() in wanted] or files
        return files

    async def save_file(self, file_name: str = "", **_):
        """A path in the app's outbox; once the caller has written it and it stops changing, the export
        sheet asks where it goes."""
        import tempfile
        import threading
        outbox = os.path.join(os.environ.get("HOME", tempfile.gettempdir()), "outbox")
        os.makedirs(outbox, exist_ok=True)
        path = os.path.join(tempfile.mkdtemp(dir=outbox), file_name or "file")
        threading.Thread(target=_export_when_written, args=(path,), daemon=True).start()
        return path

    async def get_directory_path(self, initial_directory: str = "", **_):
        return initial_directory or None


def _keep(path: str) -> str:
    """The picker's copy sits in tmp, which iOS empties; a setting such as prod.keys must outlive it."""
    import shutil
    import tempfile
    from pokeldn.app.paths import DATA
    os.makedirs(DATA / "picked", exist_ok=True)
    folder = tempfile.mkdtemp(dir=DATA / "picked")
    kept = os.path.join(folder, os.path.basename(path))
    shutil.move(path, kept)
    return kept


def _export_when_written(path: str, settle: float = 1.0, limit: float = 600.0) -> None:
    import time
    deadline, seen, since = time.monotonic() + limit, None, time.monotonic()
    while time.monotonic() < deadline:
        try:
            now = os.stat(path).st_size, os.stat(path).st_mtime
        except OSError:
            now = None
        if now != seen:
            seen, since = now, time.monotonic()
        elif now is not None and time.monotonic() - since >= settle:
            _ask("save " + path)
            return
        time.sleep(0.2)
