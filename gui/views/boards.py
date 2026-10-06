import os
import re
import sys
import threading
import time

import flet as ft

from gui import board
from gui.app import BoardStatus
from pokeldn.app import runner
from pokeldn.app.paths import SESSION
from gui import drop, theme as t
from gui.views.widgets import CodeBlock, Log, PixelActivity

PERCENT = re.compile(r"(\d{1,3}(?:\.\d)?)\s?%")
CHIP = re.compile(r"Firmware for (ESP32(?:-S3|-C3|-C6)?):")

FLASH_STEPS = [
    'ESP32-S3、C3 或 C6 若有两个 USB 接口，请连接标有 USB 的接口，避开 COM 或 UART 接口。',
    '点击“刷写”。应用会选择适合芯片的固件，并在完成后检查开发板。',
    '卡在“连接中”？按住开发板的 BOOT 按钮，直到开始写入后松开。',
]

STATE_LOOK = {   # state -> icon, color
    "ready": ("checkbox-on", t.GREEN),
    "checking": ("refresh", t.BLUE),
    "missing": ("usb", t.MUTED),
    "choose": ("cpu", t.BLUE),
}


class BoardView:
    def __init__(self, app):
        self.app = app
        self.ports: list[board.Port] = []
        self.selected: str = ""
        self.visible = False
        self.downloading = False
        self.list = ft.ListView(spacing=4, padding=8, expand=True)
        self.detail = ft.Column(spacing=t.GAP)
        self.log = Log(app.page, '检查和刷写的输出显示在此处。')
        self.progress = ft.ProgressBar(value=0, color=t.BLUE, bgcolor=t.FIELD, height=4, border_radius=0, visible=False)
        self.progress_text = t.text("", 12, t.MUTED)
        self.control = ft.Row([
            t.panel(ft.Column([
                t.panel_header('开发板', t.icon_button("refresh", lambda e: self.scan(), '重新扫描')),
                t.fade(self.list),
            ], spacing=0, expand=True), width=t.SIDEBAR_WIDTH),
            t.fade(ft.ListView([self.detail], padding=ft.Padding(0, 0, 0, 24), expand=True)),
            t.panel(ft.Column([t.panel_header('活动'),
                               ft.Container(self.log.control, padding=16, expand=True)],
                              spacing=0, expand=True), width=t.SESSION_WIDTH),
        ], spacing=t.GAP, expand=True, vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        app.board_listeners.append(self._checked)

    # Port list, polled while the page is open so a board shows up when it is plugged in

    def enter(self, **_) -> None:
        self.scan(update=False)
        if not self.visible:
            self.visible = True
            threading.Thread(target=self._poll, daemon=True).start()

    def leave(self) -> None:
        self.visible = False

    def _poll(self) -> None:
        while self.visible:
            time.sleep(2)
            present = board.ports()
            if sys.platform == "win32":
                hidden = [] if present else board.bridges_without_driver()
                if hidden != self.app.hidden_bridges:
                    self.app.hidden_bridges = hidden
                    self.app.ui(self.scan)
                    continue
            if self.visible and [p.device for p in present] != [p.device for p in self.ports]:
                self.app.ui(self.scan)

    def scan(self, update: bool = True) -> None:
        self.ports = board.ports()
        devices = [p.device for p in self.ports]
        if self.selected not in devices:
            self.selected = self.app.radio_port(self.ports) or (devices[0] if devices else "")
        self._check_selected()
        self.render()
        if update:
            self.control.update()

    def _check_selected(self) -> None:
        if self.selected and self.selected not in self.app.identities and not self.app.busy:
            self.log.add(f"[app] Checking {self.selected}; the board may restart.")
            self.app.check_board(self.selected, log=self.log.add)

    def _checked(self) -> None:
        if self.visible:
            self.render()
            self.control.update()

    def port(self) -> board.Port | None:
        return next((p for p in self.ports if p.device == self.selected), None)

    def name_of(self, device: str) -> str:
        ident = self.app.identities.get(device)
        if isinstance(ident, board.Identity):
            return self.app.settings.board_names.get(ident.sta_mac, "")
        return ""

    def status(self) -> BoardStatus:
        if self.app.board_busy and self.selected not in self.app.identities:
            return BoardStatus("checking", '正在检查开发板', '正在查询开发板固件。', self.selected)
        return self.app.board_status(self.ports, self.selected)

    def render(self) -> None:
        rows = []
        several = len(self.ports) > 1
        session_port = self.app.radio_port(self.ports)
        for p in self.ports:
            active = p.device == self.selected
            state = self.app.board_status(self.ports, p.device)
            dot = t.GREEN if state.ready else t.RED if state.state in ("flash", "wrong-port", "busy", "denied") else t.FAINT
            rows.append(ft.Container(ft.Row([
                t.pixel_icon("cpu", color=t.BLUE if active else t.FAINT),
                ft.Column([
                    t.text(self.name_of(p.device) or os.path.basename(p.device), 13,
                           t.TEXT if active else t.SOFT, weight=ft.FontWeight.W_600),
                    t.text(state.title, 11, t.MUTED),
                ], spacing=1, expand=True),
                t.badge('使用中', t.BLUE, "checkbox-on") if several and p.device == session_port else
                ft.Container(width=8, height=8, border_radius=4, bgcolor=dot),
            ], spacing=10), padding=ft.Padding(10, 8, 10, 8), border_radius=12,
                bgcolor=t.SELECTED if active else None,
                on_click=lambda e, d=p.device: self._select(d)))
        if not rows:
            rows.append(ft.Container(ft.Column([
                t.pixel_icon("usb", color=t.FAINT),
                t.text('未找到开发板', 13, t.MUTED, weight=ft.FontWeight.W_600),
                t.text('使用数据线连接后，开发板会自动显示在此处。', 12, t.FAINT,
                       text_align=ft.TextAlign.CENTER),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6), padding=24))
        self.list.controls = rows
        cards = [self.status_card()]
        if self.port():
            cards += [self.flash_card(), self.details_card()]
        cards.append(self.help_card())
        self.detail.controls = cards

    def _select(self, device: str) -> None:
        self.selected = device
        self._check_selected()
        self.render()
        self.control.update()

    # The selected board, in one line

    def status_card(self) -> ft.Control:
        status = self.status()
        icon, color = STATE_LOOK.get(status.state, ("warning-diamond", t.RED))
        lead = PixelActivity('检查中') if status.state == "checking" else t.pixel_icon(icon, size=24, color=color)
        actions: list[ft.Control] = []
        several = len(self.ports) > 1
        if self.port() and several and self.selected != self.app.radio_port(self.ports):
            actions.append(t.button('使用此开发板', self._use, "check"))
        if status.ready:
            actions.append(t.button('前往游戏页', lambda e: self.app.navigate("games"), "gamepad",
                                    filled=not actions))
        if status.state in ("flash", "wrong-port", "busy", "denied"):
            actions.append(t.secondary_button('重新检查', self._identify, "refresh", disabled=self.app.busy))
        detail = status.detail
        if status.ready and several:
            detail += ('会话使用此开发板。' if self.selected == self.app.radio_port(self.ports)
                       else '会话正在使用另一个开发板，点击“使用此开发板”切换。')
        return t.surface(ft.Container(ft.Column([
            ft.Row([
                ft.Container(lead, width=24, height=24, alignment=ft.Alignment.CENTER),
                ft.Column([t.text(status.title, 17, weight=ft.FontWeight.W_600),
                           t.text(detail, 13, t.MUTED)], spacing=2, expand=True),
            ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START),
            *([ft.Row(actions, spacing=8)] if actions else []),
        ], spacing=14, tight=True), padding=ft.Padding(18, 16, 18, 18)))

    def details_card(self) -> ft.Control:
        p = self.port()
        ident = self.app.identities.get(p.device)
        if isinstance(ident, board.Identity):
            firmware = f"pokeldn v{ident.firmware_version}" if ident.firmware_version else "pokeldn"
            mac = ident.sta_mac
        else:
            firmware, mac = ident or '尚未检查', "unknown"

        def info(label, value):
            return ft.Row([t.text(label, 12, t.MUTED, width=110),
                           value if isinstance(value, ft.Control) else t.text(value, 13, font_family=t.MONO)])

        name = t.field(value=self.name_of(p.device), hint='客厅、备用…', width=220,
                       disabled=not isinstance(ident, board.Identity), on_submit=self._rename)
        body = ft.Column([
            info('端口', p.device),
            info('USB 芯片', p.bridge),
            info('固件', firmware),
            info('Wi-Fi MAC 地址', mac),
            info('昵称', ft.Row([name, t.icon_button("check", lambda e: self._rename(e, name),
                                                         '保存昵称')], spacing=4,
                                               vertical_alignment=ft.CrossAxisAlignment.CENTER)),
            ft.Row([t.secondary_button('闪烁 LED', self._blink, "lightbulb",
                                       disabled=self.app.busy or not isinstance(ident, board.Identity))]),
        ], spacing=10)
        return t.card('详情', body, '点击“闪烁 LED”可识别开发板：经典 ESP32 的蓝色 LED 会闪烁五秒。连接多个开发板时，可使用昵称区分。')

    def _rename(self, e, field=None) -> None:
        field = field or e.control
        ident = self.app.identities.get(self.selected)
        if isinstance(ident, board.Identity):
            names = self.app.settings.board_names
            if field.value.strip():
                names[ident.sta_mac] = field.value.strip()
            else:
                names.pop(ident.sta_mac, None)
            self.app.settings.save()
            self.render()
            self.control.update()

    def _use(self, e) -> None:
        self.app.settings.radio_port = self.selected
        self.app.settings.save()
        self.log.add(f"[app] Sessions now use {self.selected}.")
        self.render()
        self.control.update()

    def _identify(self, e, blink: bool = False) -> None:
        if self.app.busy:
            return
        self.app.identities.pop(self.selected, None)
        self.log.add(f"[app] Checking {self.selected}; the board may restart.")
        self.app.check_board(self.selected, blink=blink, log=self.log.add)
        self.render()
        self.control.update()

    def _blink(self, e) -> None:
        self._identify(e, blink=True)

    # Flashing

    def firmware(self) -> str:
        chosen = self.app.settings.firmware
        if chosen and os.path.exists(chosen):
            return chosen
        return ""

    def flash_button(self) -> ft.Control:
        image = self.firmware()
        available = image or any(os.path.isfile(f) for f in (board.FIRMWARE, board.FIRMWARE_S3, board.FIRMWARE_C3, board.FIRMWARE_C6))
        flashing = bool(self.app.process and self.app.process.running and self.app.process_label == "flash")
        return t.button('正在刷写…' if flashing else '刷写', self._flash, "zap", filled=not self.status().ready,
                        disabled=self.app.busy or not available or not self.port())

    def flash_card(self) -> ft.Control:
        image = self.firmware()
        available = image or any(os.path.isfile(f) for f in (board.FIRMWARE, board.FIRMWARE_S3, board.FIRMWARE_C3, board.FIRMWARE_C6))
        source = ft.Row([
            t.pixel_icon("package", color=t.MUTED),
            t.text(f'自定义镜像：{image}' if image else
                   '应用附带 ESP32、ESP32-S3、ESP32-C3、ESP32-C6 固件，会根据芯片自动选择。' if available
                   else '当前没有固件镜像（从源码运行）。请下载发布版固件，无需安装 ESP-IDF。',
                   12, t.MUTED if available else t.RED, expand=True),
            *([t.secondary_button('附带固件', self._clear_file, "refresh")] if image else
              [t.icon_button("file", self._choose_file, '使用自己的固件文件'
                                                         + ('，或将 .bin 拖放到此卡片' if drop.AVAILABLE else ""))] + ([] if available else [
                  t.button('正在下载…' if self.downloading else '下载固件', self._download,
                           "download", disabled=self.downloading)])),
        ], spacing=6)
        return drop.target(t.card('刷写固件', ft.Column([
            t.step_list(FLASH_STEPS),
            source,
            ft.Column([self.progress, self.progress_text], spacing=6, visible=self.progress.visible),
            ft.Row([self.flash_button()]),
        ], spacing=14), '每个开发板首次使用时需要刷写一次；应用更新提示需要时再次刷写。约需三十秒。'), self._dropped)

    def _dropped(self, paths: list[str]) -> None:
        """A firmware image dropped on the card becomes the custom image."""
        path = next((p for p in paths if drop.suffix(p) == "bin"), "")
        if path and not self.app.busy:
            self._set_firmware(path)

    def _download(self, e) -> None:
        self.downloading = True
        self.render()
        self.control.update()

        def work():
            try:
                tag = board.download_firmware(self.log.add)
                self.log.add(f'[app] {tag} 的固件已就绪，请点击“刷写”。')
            except Exception as error:
                self.log.add(f'[app] 无法下载固件：{error}')
            finally:
                self.downloading = False
                self.app.ui(lambda: (self.render(), self.control.update()))

        threading.Thread(target=work, daemon=True).start()

    async def _choose_file(self, e) -> None:
        files = await self.app.picker.pick_files(allowed_extensions=["bin"],
                                                 file_type=ft.FilePickerFileType.CUSTOM)
        if files and files[0].path:
            self._set_firmware(files[0].path)

    def _clear_file(self, e) -> None:
        self._set_firmware("")

    def _set_firmware(self, path: str) -> None:
        self.app.settings.firmware = path
        self.app.settings.save()
        self.render()
        self.control.update()

    def _flash(self, e) -> None:
        if self.app.busy:
            return
        args = ["--module", "gui.board", "--port", self.selected]
        if image := self.firmware():
            args += ["--firmware", image]
        self.log.clear()
        self.log.add(f"[app] Flashing {self.selected}.")
        self.progress.visible, self.progress.value = True, None
        self.progress_text.value = '正在连接…'
        self.progress_text.color = t.MUTED
        env = dict(os.environ, NO_COLOR="1", PYTHONUNBUFFERED="1")
        env.pop("POKELDN_RADIO", None)
        self.app.process_label = "flash"
        self.app.process = runner.Process(args, str(SESSION), env, self._flash_line,
                                          self._flashed)
        self.render()
        self.control.update()

    def _flash_line(self, line: str) -> None:
        self.log.add(line)
        if chip := CHIP.search(line):
            self.app.chips[self.selected] = chip[1]
        found = PERCENT.findall(line)
        if found and "Writing" in line:
            value = min(float(found[-1]), 100.0) / 100

            def show():
                self.progress.value = value
                self.progress_text.value = f'正在写入 {value:.0%}'
                self.progress.update()
                self.progress_text.update()
            self.app.ui(show)

    def _flashed(self, code: int) -> None:
        device = self.selected

        def done():
            self.progress.value = 1 if code == 0 else 0
            self.progress_text.value = ('写入完成，正在检查开发板…' if code == 0 else
                                        '刷写失败。请按住 BOOT 按钮并再次点击“刷写”。详情见活动日志。')
            self.progress_text.color = t.GREEN if code == 0 else t.RED
            self.app.identities.pop(device, None)
            self.render()
            self.control.update()
            if code == 0:
                threading.Timer(2.0, lambda: self.app.ui(self._after_flash)).start()
        self.app.ui(done)

    def _after_flash(self) -> None:
        self.scan(update=False)   # a native-USB board can come back under a new port name
        self.render()
        self.control.update()

    def help_card(self) -> ft.Control:
        def link(label, url):
            return t.secondary_button(label, lambda e: self.app.page.run_task(self.app.open_url, url),
                                      "external-link")

        lines = [t.text('请尝试其他数据线或 USB 接口。许多线缆仅支持充电。', 13)]
        if sys.platform == "win32":
            lines += [
                t.text('Windows 需要安装开发板 USB 芯片的驱动，芯片型号印在 USB 接口旁的芯片上（CP2102 或 CH340）：', 13),
                ft.Row([link("CP210x 驱动", board.DRIVERS["Silicon Labs CP210x"]),
                        link("CH340 驱动", board.DRIVERS["WCH CH340"])], spacing=6, wrap=True),
                t.text(f"CP210x: {board.DRIVER_STEPS['Silicon Labs CP210x']}", 13, t.MUTED),
                t.text(f"CH340: {board.DRIVER_STEPS['WCH CH340']}", 13, t.MUTED)]
        elif sys.platform.startswith("linux"):
            lines += [
                t.text('授予串口权限，然后注销并重新登录：', 13),
                CodeBlock(self.app, "sudo usermod -aG dialout $USER").control,
                t.text('Arch 及其衍生发行版使用 uucp 用户组，而不是 dialout。', 13, t.MUTED)]
        lines.append(t.text('请使用经典 ESP32（ESP32-D0WD、WROOM-32E），或通过原生 USB 接口连接 ESP32-S3、C3、C6。不支持 S2 开发板。',
                            13, t.MUTED))
        return t.card('没有看到开发板？', ft.Column(lines, spacing=8))
