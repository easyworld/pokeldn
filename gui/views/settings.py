import copy
import os
import threading

import flet as ft

from gui import theme as t
from gui.app import keys_found
from pokeldn import __version__
from pokeldn.app.paths import SESSION
from pokeldn.app.sprites import CACHE
from pokeldn.app.settings import LANGUAGES, switch_ids_valid
from pokeldn.app import storage
from gui.views.widgets import PathField, open_folder

LINKS = (('文档', "https://decryptu.github.io/pokeldn/"),
         ("GitHub", "https://github.com/Decryptu/pokeldn"),
         ("Discord", "https://discord.gg/PyvaVYnpXC"))


class SettingsView:
    def __init__(self, app):
        self.app = app
        self.keys_state = ft.Container()
        self.sprite_state = t.text("", 12, t.MUTED)
        self.update_state = t.text("", 12, t.MUTED)
        self.storage_state = t.text('正在检查本地文件…', 12, t.MUTED)
        self.storage_result = t.text("", 12, t.MUTED, visible=False)
        self.storage_inventory = storage.Inventory()
        self.storage_work = False
        self.clear_button = t.button('清理本地文件', self._clear_local, "folder", filled=False,
                                     disabled=True)
        self.shown = self.asked = False
        app.update_listeners.append(self._update_shown)
        self._update_text()
        self.show_advanced = False
        self.column = ft.Column(spacing=t.GAP, width=760)
        self.scroll = ft.ListView([ft.Row([self.column], alignment=ft.MainAxisAlignment.CENTER)],
                                  padding=ft.Padding(4, 8, 4, 24), expand=True)
        self.control = t.fade(self.scroll)
        self.render()

    def enter(self, **_) -> None:
        self.shown = True
        self._storage_refresh()

    def leave(self) -> None:
        self.shown = False

    def save(self, name: str, value) -> None:
        setattr(self.app.settings, name, value)
        self.app.settings.save()

    def render(self) -> None:
        s = self.app.settings
        home = lambda: os.path.expanduser("~")   # noqa: E731
        keys = PathField(self.app.picker, home, s.keys, "file", ("keys",), self._keys)
        received = PathField(self.app.picker, home, s.received, "dir", on_change=lambda v: self.save("received", v))
        self._keys(s.keys, update=False)
        speed = t.dropdown([("921600", '921600（默认）'), ("1500000", '1500000（更快，需要优质数据线）')],
                           str(s.baud), on_select=lambda e: self.save("baud", int(e.control.value)))

        def number(name, label, valid, size):
            def store(e):
                try:
                    value = int(e.control.value)
                except ValueError:
                    return
                if valid(value):
                    self.save(name, value)
            return ft.Column([t.text(label, 11, t.MUTED),
                              t.field(value=str(getattr(s, name)), mono=True, digits=True, limit=size,
                                      on_change=store)],
                             spacing=4, expand=True)

        gba = lambda v: 0 <= v <= 65535   # noqa: E731
        trainer = ft.Column([
            ft.Row([
                ft.Column([t.text('姓名', 11, t.MUTED),
                           t.field(value=s.ot, limit=12, on_change=lambda e: self.save("ot", e.control.value[:12]))],
                          spacing=4, expand=True),
                ft.Column([t.text('语言', 11, t.MUTED),
                           t.dropdown(list(LANGUAGES), str(s.language),
                                      on_select=lambda e: self.save("language", int(e.control.value)))],
                          spacing=4, expand=True),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.START),
            ft.Row([
                number("tid", "ID（火红／叶绿）", gba, 5),
                number("sid", '里 ID', gba, 5),
                number("switch_tid", "ID（Switch 游戏）", lambda v: switch_ids_valid(v, s.switch_sid), 6),
                number("switch_sid", '里 ID', lambda v: switch_ids_valid(s.switch_tid, v), 4),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.START),
        ], spacing=10)

        def switch(name, label, help_):
            return t.card(label, None, help_,
                          trailing=t.switch(getattr(s, name), lambda e: self.save(name, e.control.value)))

        def link(label, url):
            return t.link_button(label, lambda e: self.app.page.run_task(self.app.open_url, url))

        def section(label):
            return ft.Container(t.text(label, 12, t.MUTED, weight=ft.FontWeight.W_600),
                                padding=ft.Padding(4, 8, 0, 0))

        advanced = [
            t.card('串口波特率', speed, '电脑与开发板的通信速率。除非指南另有要求，请保留默认值。'),
            switch("board_trace", '记录开发板串口通信',
                   '在会话记录中加入开发板计数器和每条串口消息。仅在排查无线通信问题时按要求启用。'),
            t.card('宝可梦图像', ft.Row([t.button('清除缓存', self._clear_sprites, "refresh",
                                                        filled=False), self.sprite_state], spacing=10),
                   '像素图像来自 PokeAPI，首次下载后缓存在此电脑上。没有图像也能使用应用。',
                   trailing=t.switch(s.sprites, lambda e: self.save("sprites", e.control.value))),
        ]
        self.column.controls = [
            ft.Container(ft.Row([t.pixel_icon("gear", size=24, color=t.RED),
                                 t.text('设置', 22, weight=ft.FontWeight.W_600)], spacing=10),
                         padding=ft.Padding(4, 12, 0, 0)),
            section('基础设置'),
            t.card('Switch 密钥', ft.Column([keys.control, self.keys_state], spacing=8),
                   '从自己的游戏机导出的 prod.keys，用于与游戏通信，仅保存在此电脑上。'),
            t.card('原始训练家', trainer,
                   "生成宝可梦时使用的原始训练家。填写自己的姓名和 ID 即可将其设为自己的宝可梦。火红／叶绿显示五位 ID，Switch 游戏显示六位 ID。首次启动时随机生成 ID。"),
            t.card('已接收的宝可梦', ft.Row([ft.Container(received.control, expand=True),
                                               t.icon_button("external-link",
                                                             lambda e: open_folder(os.path.expanduser(s.received)),
                                                             '打开文件夹')]),
                   '保存游戏机发送过来的宝可梦的位置。'),
            section('存储'),
            t.card('本地文件', ft.Column([
                self.storage_state,
                ft.Row([self.clear_button], spacing=10),
                self.storage_result,
            ], spacing=8),
                   '清理会话记录、日志、临时交换文件及未使用的已生成宝可梦。保留已接收的宝可梦、已选择的交换文件、密钥、固件和设置。'),
            section('问题报告'),
            t.card('记录每次会话', ft.Row([t.button('打开记录文件夹', lambda e: open_folder(
                str(SESSION / "captures")), "folder", filled=False)]),
                   '为每次会话保存简要记录。发生错误时，请将最新记录附在问题报告中。',
                   trailing=t.switch(s.capture, lambda e: self.save("capture", e.control.value))),
            ft.Row([t.link_button('隐藏高级设置' if self.show_advanced else '显示高级设置',
                                  self._toggle_advanced)]),
            *(advanced if self.show_advanced else []),
            t.card('更新', ft.Row([t.button('立即检查', self._check_update, "refresh", filled=False),
                                      self.update_state], spacing=10),
                   '应用启动时向 GitHub 查询 pokeldn 新版本，不发送个人或游戏信息。',
                   trailing=t.switch(s.check_updates, lambda e: self.save("check_updates", e.control.value))),
            t.card(f'关于 pokeldn {__version__}', ft.Row([link(label, url) for label, url in LINKS], spacing=4),
                   'pokeldn 使用 AGPLv3 许可，宝可梦由 PKHeX.Core（GPLv3）检查。'),
        ]

    def _toggle_advanced(self, e) -> None:
        self.show_advanced = not self.show_advanced
        self.render()
        self.control.update()

    def _check_update(self, e) -> None:
        self.asked = True
        self.app.check_update()
        self._update_text()
        self.update_state.update()

    def _update_text(self) -> None:
        release, state = self.app.update, self.app.update_state
        self.update_state.value = {
            "checking": '正在检查…',
            "current": f'当前已是最新版本（{__version__}）。',
            "offline": 'GitHub 未响应，请检查网络连接。',
            "available": f'pokeldn {release.version} 已发布。' if release else "",
        }.get(state, "")
        self.update_state.color = t.GREEN if state == "available" else t.MUTED

    def _update_shown(self) -> None:
        self._update_text()
        if self.shown:
            self.update_state.update()
            if self.asked and self.app.update:
                self.app.navigate("update")
        self.asked = False

    def _clear_sprites(self, e) -> None:
        self.sprite_state.value = f'{CACHE.clear()} 个文件已删除'
        self.sprite_state.update()

    def _storage_refresh(self, inventory=None) -> None:
        if self.storage_work:
            return
        self.storage_work = True
        self.clear_button.disabled = True
        self.storage_state.value = '正在清理本地文件…' if inventory is not None else '正在检查本地文件…'
        if self.shown:
            self.app.ui(self.control.update)
        settings = copy.deepcopy(self.app.settings)

        def work():
            try:
                result = storage.clear(inventory, settings) if inventory is not None else None
                found = storage.scan(settings)
                self.app.ui(lambda: self._storage_done(found, result))
            except OSError as error:
                self.app.ui(lambda message=str(error): self._storage_done(storage.Inventory(errors=1),
                                                                          error=message))
            finally:
                if inventory is not None:
                    self.app.storage_busy = False

        threading.Thread(target=work, daemon=True).start()

    def _storage_done(self, inventory, result=None, error="") -> None:
        self.storage_work = False
        self.storage_inventory = inventory
        count = len(inventory.files)
        self.clear_button.disabled = not count
        self.storage_state.value = (f'{storage.size_text(inventory.size)} 可释放 · {count} 个文件'
                                    if count else '没有可清理的本地文件。')
        if inventory.errors:
            self.storage_state.value += '部分文件夹无法读取。'
        if result is not None:
            self.storage_result.value = f'已释放 {storage.size_text(result.size)} · {result.files} 个文件已删除。'
            if result.errors:
                self.storage_result.value += f' {result.errors} 个文件无法删除，请重试。'
            if result.skipped:
                self.storage_result.value += '正在使用或检查后已修改的文件予以保留。'
        if error:
            self.storage_result.value = f'无法清理本地文件：{error}'
        self.storage_result.visible = bool(self.storage_result.value)
        if self.shown:
            self.control.update()

    def _clear_local(self, e) -> None:
        if self.storage_work:
            return
        if self.app.busy:
            self.storage_result.value = '请先完成当前运行或开发板检查，再清理本地文件。'
            self.storage_result.visible = True
            self.storage_result.update()
            return
        inventory = self.storage_inventory
        if not inventory.files:
            self._storage_refresh()
            return

        def close(e):
            self.app.page.pop_dialog()

        def clear(e):
            close(e)
            if self.app.busy or self.storage_work:
                self.storage_result.value = '请先完成当前运行或开发板检查，再清理本地文件。'
                self.storage_result.visible = True
                self.storage_result.update()
                return
            self.app.storage_busy = True
            self._storage_refresh(inventory)

        self.app.page.show_dialog(t.dialog(
            title=t.text('清理本地文件？', 17, weight=ft.FontWeight.W_600),
            content=ft.Container(t.text(
                f'删除 {len(inventory.files)} 个文件，约可释放 {storage.size_text(inventory.size)}。将删除已保存的会话记录、日志、临时交换文件和未使用的已生成宝可梦。请先保存问题报告需要的记录。保留已接收的宝可梦、已选择的交换文件、密钥、固件和设置。', 13, t.MUTED), width=460),
            actions=[t.secondary_button('取消', close), t.button('清理文件', clear)],
        ))

    def _keys(self, value: str, update: bool = True) -> None:
        self.save("keys", value)
        ok = keys_found(value)
        self.keys_state.content = ft.Row([
            t.pixel_icon("checkbox-on" if ok else "warning-diamond",
                    color=t.GREEN if ok else t.RED),
            t.text('已找到' if ok else '此路径下没有文件', 12, t.GREEN if ok else t.RED)], spacing=6)
        if update:
            self.keys_state.update()
