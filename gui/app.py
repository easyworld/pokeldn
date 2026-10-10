import errno
import os
import sys
import threading
from dataclasses import dataclass

import flet as ft
import serial

from gui import board
from pokeldn.app import settings, update
from pokeldn.app.paths import SESSION
from gui.views.widgets import on_ui

NO_FIRMWARE = '未检测到 pokeldn 固件'
PORT_BUSY = '端口被占用或无权限'
PORT_DENIED = '无端口访问权限'


@dataclass(frozen=True)
class BoardStatus:
    state: str     # missing, choose, checking, ready, flash, wrong-port, busy, denied, controller
    title: str
    detail: str
    port: str = ""

    @property
    def ready(self) -> bool:
        return self.state == "ready"


class App:
    """State shared by the pages: settings, the one child process a board allows, and services."""

    storage_busy = False
    controllers = 0    # S3 controller boards on USB, polled

    def __init__(self, page: ft.Page):
        self.page = page
        SESSION.mkdir(parents=True, exist_ok=True)
        self.settings = settings.load()
        self.picker = ft.FilePicker()
        self.clipboard = ft.Clipboard()
        self.launcher = ft.UrlLauncher()
        self.process = None        # the running session or flash
        self.process_label = ""
        self.board_busy = False    # a check holds the port
        self.navigate = None       # set by the shell: navigate(page_key, **kwargs)
        self.identities: dict[str, board.Identity | str] = {}   # device -> identity, or why none answered
        self.chips: dict[str, str] = {}                         # device -> chip the last flash detected
        self.board_listeners: list = []                         # called on the UI loop after a check
        self.hidden_bridges: list[str] = []                     # Windows: bridges with no driver, polled
        self.update: update.Release | None = None               # a newer release GitHub offered
        self.update_state = ""                                  # checking, current, available, offline
        self.update_listeners: list = []                        # called on the UI loop after a check
        self.gts = None                                         # gui.views.gts.service, once used
        threading.Thread(target=self._watch_controllers, daemon=True).start()

    def ui(self, fn) -> None:
        on_ui(self.page, fn)

    def _watch_controllers(self) -> None:
        """A controller board has no serial port, so the port list never shows it; USB does."""
        import time
        while True:
            found = board.controllers()
            if found != self.controllers:
                self.controllers = found
                self.ui(lambda: [listener() for listener in list(self.board_listeners)])
            time.sleep(6 if sys.platform == "win32" else 2)

    @property
    def busy(self) -> bool:
        return self.storage_busy or self.board_busy or bool(self.process and self.process.running)

    def radio_port(self, present: list[board.Port] | None = None) -> str:
        """The chosen board if it is plugged in, else the only board present."""
        devices = [p.device for p in (board.ports() if present is None else present)]
        if self.settings.radio_port in devices:
            return self.settings.radio_port
        return devices[0] if len(devices) == 1 else ""

    def board_status(self, present: list[board.Port] | None = None, device: str = "") -> BoardStatus:
        """One line a player can act on: is the board plugged in, does pokeldn's firmware answer.
        Without a device, the board sessions use."""
        present = board.ports() if present is None else present
        for device in set(self.identities) - {p.device for p in present}:
            self.identities.pop(device)   # unplugged: check again when it returns
        if not present:
            hidden = board.bridges_without_port() if sys.platform.startswith("linux") else []
            if hidden:
                fix = ("Ubuntu 22.04 的盲文服务占用了 CH340 开发板：执行 sudo apt remove brltty，然后拔出并重新连接。"
                       if "WCH CH340" in hidden else "请拔出并重新连接；内核日志（sudo dmesg）可查看原因。")
                return BoardStatus("missing", '已找到开发板，但没有串口',
                                   f"Linux 未给 {hidden[0]} 分配串口。{fix}")
            if sys.platform == "win32" and self.hidden_bridges:
                name = self.hidden_bridges[0]
                steps = board.DRIVER_STEPS.get(name, '请安装对应驱动；开发板页面提供驱动链接。')
                return BoardStatus("missing", '已找到开发板，但未安装驱动',
                                   f"Windows 未安装 {name} 的驱动，因此没有 COM 端口。{steps}")
            if self.controllers:
                return BoardStatus("controller", '开发板正在运行手柄固件',
                                   '交换需要无线固件，请在“开发板”页安装。')
            return BoardStatus("missing", '未连接开发板',
                               '请使用 USB 数据线连接 ESP32。仅支持充电的线缆无法识别开发板。')
        port = device or self.radio_port(present)
        if not port:
            return BoardStatus("choose", '连接了多个开发板',
                               '打开“开发板”页，选择要使用的开发板。')
        found = next((p for p in present if p.device == port), None)
        if found is None:
            return BoardStatus("missing", '开发板已断开', '请重新连接。', port)
        ident = self.identities.get(port)
        if isinstance(ident, board.Identity):
            if ident.current:
                version = f" v{ident.firmware_version}" if ident.firmware_version else ""
                return BoardStatus("ready", '开发板已就绪', f"pokeldn 固件{version} 已响应。", port)
            return BoardStatus("flash", '固件版本过旧',
                               '请在“开发板”页更新固件。', port)
        if isinstance(ident, board.PadIdentity):
            return BoardStatus("controller", '开发板正在运行手柄固件',
                               '交换需要无线固件，请在“开发板”页安装。', port)
        if ident == PORT_DENIED:
            group = "uucp" if os.path.exists("/etc/arch-release") else "dialout"
            fix = (f"将自己加入 {group} 用户组（sudo usermod -aG {group} $USER），然后注销并重新登录。"
                   if sys.platform.startswith("linux") else '请拔出并重新连接开发板。')
            return BoardStatus("denied", '无权访问开发板', fix, port)
        if ident == PORT_BUSY:
            return BoardStatus("busy", '开发板端口被占用',
                               '其他程序占用了端口。请关闭该程序，或拔出并重新连接开发板。',
                               port)
        if ident == NO_FIRMWARE:
            if board.wrong_port(found, self.chips.get(port, "")):
                return BoardStatus("wrong-port", '请使用开发板的另一个 USB 接口',
                                   f"{self.chips[port]} 固件通过原生 USB 接口通信。请将"
                                   '线缆连接到标有 USB 的接口，避开 COM 或 UART。', port)
            return BoardStatus("flash", '开发板未安装 pokeldn 固件',
                               '请在“开发板”页安装无线固件。如果刚刚安装完成，请按开发板的 '
                               'RESET（RST）按钮。',
                               port)
        return BoardStatus("checking", '正在检查开发板', '正在查询开发板固件。', port)

    def check_board(self, device: str, blink: bool = False, log=None) -> None:
        """Ask the board's firmware for its identity in the background; opening the port can restart it."""
        if self.busy or not device:
            return
        self.board_busy = True
        say = log or (lambda line: None)

        def work():
            try:
                ident = board.identify(device, blink=blink)
                self.identities[device] = ident
                say(f"[app] {ident.firmware}, protocol {ident.protocol}, chip revision "
                    f"{ident.chip_revision}, MAC {ident.sta_mac}")
                if not ident.current:
                    say("[app] This firmware uses a different radio protocol. Update it on the Board page.")
            except serial.SerialException as error:
                # pyserial keeps the open's errno: EACCES is a missing group on Linux, not a busy port.
                self.identities[device] = PORT_DENIED if error.errno == errno.EACCES else PORT_BUSY
                say(f"[app] Could not open {device}: {error}")
            except Exception as error:
                try:
                    self.identities[device] = board.identify_pad(device)
                    say(f"[app] {device} runs the controller firmware.")
                except Exception:
                    self.identities[device] = NO_FIRMWARE
                    say(f"[app] No pokeldn firmware answered on {device} ({error}).")
                    self._probe_chip(device, say)
            finally:
                self.board_busy = False
                self.ui(lambda: [listener() for listener in list(self.board_listeners)])

        threading.Thread(target=work, daemon=True).start()

    def _probe_chip(self, device: str, say) -> None:
        """Through a USB-to-serial bridge, the ROM bootloader still names the chip: an S3, C3 or C6 there
        is on its UART socket, where the radio firmware never answers."""
        port = next((p for p in board.ports() if p.device == device), None)
        if port is None or port.native:
            return
        try:
            self.chips[device] = board.detect_chip(device)
            say(f"[app] The chip on {device} is an {self.chips[device]}.")
        except Exception as error:
            say(f"[app] Could not read the chip type on {device} ({error}).")

    def check_if_unknown(self, present: list[board.Port] | None = None) -> None:
        port = self.radio_port(present)
        if port and port not in self.identities and not self.busy:
            self.check_board(port)

    def check_update(self) -> None:
        """Ask GitHub for a newer release in the background; listeners run when it answers."""
        if self.update_state == "checking":
            return
        self.update_state = "checking"

        def work():
            try:
                found, state = update.check(), "current"
            except OSError:
                found, state = None, "offline"
            self.ui(lambda: self._update_done(found, state))

        threading.Thread(target=work, daemon=True).start()

    def _update_done(self, found, state: str) -> None:
        if state != "offline":   # a failed check keeps a release an earlier one found
            self.update = found
        self.update_state = "available" if self.update else state
        for listener in list(self.update_listeners):
            listener()

    async def open_url(self, url: str) -> None:
        await self.launcher.launch_url(url)

    async def copy(self, value: str) -> None:
        await self.clipboard.set(value)
        self.page.show_dialog(ft.SnackBar(ft.Text('已复制'), duration=1500))


def keys_found(path: str) -> bool:
    return os.path.isfile(os.path.expanduser(path))
