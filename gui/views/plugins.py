"""The Plugins page: add a .pokeplugin, turn plugins on and off, update and remove them, pick a radio.
Every install shows the risks and waits for the user's acceptance (docs/plugins.md)."""
import os
import shutil
import threading
from pathlib import Path

import flet as ft

from gui.localization import translate
from gui import drop
from gui import theme as t
from gui.views.widgets import open_folder
from pokeldn import plugins
from pokeldn.app import plugin_store as store
from pokeldn.app.paths import SESSION

ACTIONS = {"install": '安装', "update": '更新', "reinstall": '重新安装', "downgrade": '安装旧版'}
RISKS = (
    '插件会在此电脑上运行程序，具有你账户对所有文件的访问权限，包括 prod.keys。',
    '插件可以访问网络、开发板以及你启动的会话。',
    'pokeldn 会阻止插件删除或覆盖你的文件及执行擦除命令，但恶意编写的插件可能绕过这些限制。',
    'pokeldn 不审核插件或提供插件支持，也无法撤销插件执行的操作。',
)


def plugin_icon(source: str | bytes = "", size: int = 48) -> ft.Control:
    """The plugin's own image, or the blocks mark on the brand gradient."""
    if isinstance(source, str) and source:
        try:
            source = Path(source).read_bytes()
        except OSError:
            source = b""
    if source:
        image = ft.Image(src=source, width=size, height=size, fit=ft.BoxFit.CONTAIN,
                         filter_quality=ft.FilterQuality.NONE)
        return ft.Container(image, width=size, height=size, border_radius=size * 0.22,
                            clip_behavior=ft.ClipBehavior.ANTI_ALIAS)
    return ft.Container(t.tinted(t.pixel_icon("blocks", size=24 if size < 48 else 48), t.BRAND_BLUE),
                        width=size, height=size, border_radius=size * 0.22, alignment=ft.Alignment.CENTER,
                        bgcolor=ft.Colors.with_opacity(0.08, "#FFFFFF"))


def checkbox(label: str, value: bool, on_change) -> ft.Container:
    """A whole-row tick box in the app's pixel style."""
    state = {"on": value}
    mark = t.pixel_icon("checkbox-on" if value else "checkbox", color=t.BLUE if value else t.MUTED)

    def toggle(e):
        state["on"] = not state["on"]
        mark.src = f"icons/{'checkbox-on' if state['on'] else 'checkbox'}.svg"
        mark.color = t.BLUE if state["on"] else t.MUTED
        mark.update()
        on_change(state["on"])

    return ft.Container(ft.Row([mark, t.text(label, 13, expand=True)], spacing=10,
                               vertical_alignment=ft.CrossAxisAlignment.START),
                        padding=ft.Padding(10, 10, 10, 10), border_radius=10, on_click=toggle,
                        bgcolor=ft.Colors.with_opacity(0.04, "#FFFFFF"))


class PluginsView:
    def __init__(self, app):
        self.app = app
        self.notice = ft.Container()
        self.column = ft.Column(spacing=t.GAP, width=760)
        self.zone = ft.Container()
        self.scroll = ft.ListView([ft.Row([self.column], alignment=ft.MainAxisAlignment.CENTER)],
                                  padding=ft.Padding(4, 8, 4, 24), expand=True)
        self.control = drop.target(ft.Container(t.fade(self.scroll), expand=True), self._dropped,
                                   glow=lambda: self.zone)
        self.downloading = ""      # the plugin whose update is downloading
        app.plugin_update_listeners.append(lambda: self.render(update=self.column.page is not None))
        self.render()

    def enter(self, **_) -> None:
        self.render()

    def leave(self) -> None:
        self.notice.content = None

    # Rendering

    def render(self, update: bool = False) -> None:
        found = plugins.discover()
        loaded = {p.id: p for p in plugins.load()}
        rows = [self._row(p, loaded.get(p.id)) for p in found]
        header = ft.Container(ft.Row([
            t.pixel_icon("plug", size=24, color=t.RED),
            t.text('插件', 22, weight=ft.FontWeight.W_600, expand=True),
            t.secondary_button('如何制作插件', lambda e: self.app.navigate("docs", doc="plugins.md"),
                               "book-open"),
            t.button('添加插件', self._pick, "plus"),
        ], spacing=10), padding=ft.Padding(4, 12, 0, 0))
        self.zone = self._zone(compact=bool(rows))
        installed = t.section(
            f"已安装 · {len(rows)}" if rows else '已安装',
            ft.Column([*rows, t.text(f"此 pokeldn 使用插件 API {plugins.API_VERSION}.{plugins.API_LEVEL}。",
                                     12, t.FAINT)], spacing=8) if rows else None,
            trailing=ft.Row([
                t.icon_button("refresh", self._refresh, '检查变化和更新'),
                t.icon_button("folder", self._open_folder, '打开插件文件夹'),
            ], spacing=0))
        self.column.controls = [header, self.notice, self.zone, *([installed] if rows else []),
                                *self._radio_card()]
        if update:
            self.column.update()

    def _zone(self, compact: bool) -> ft.Container:
        title = ('将 .pokeplugin 文件拖到这里' if drop.AVAILABLE else '添加 .pokeplugin 文件')
        lead = t.tinted(t.pixel_icon("archive", size=24 if compact else 48), t.BRAND_BLUE)
        body = [t.text(title, 15 if not compact else 13, weight=ft.FontWeight.W_600),
                t.text('插件可添加第三方制作的工具和无线通信后端。安装前会展示插件内容，需确认接受其风险。', 12, t.MUTED,
                       text_align=None if compact else ft.TextAlign.CENTER)]
        choose = t.secondary_button('选择文件', self._pick, "folder")
        if compact:
            content = ft.Row([lead, ft.Column(body, spacing=2, expand=True), choose], spacing=14)
            padding = ft.Padding(18, 14, 14, 14)
        else:
            content = ft.Column([lead, *body, ft.Container(height=4), choose], spacing=8,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            padding = ft.Padding(32, 36, 32, 32)
        return ft.Container(content, padding=padding, border_radius=16, bgcolor=t.CARD,
                            border=ft.Border.all(1.5, ft.Colors.with_opacity(0.12, "#FFFFFF")),
                            on_click=self._pick if not compact else None)

    def _row(self, plugin: plugins.Plugin, state: plugins.Plugin | None) -> ft.Control:
        s = self.app.settings
        local = plugin.folder is not None and plugin.folder.parent == plugins.folder()
        forced = plugins.named(plugin)
        on = state is not None
        meta = " · ".join(x for x in (f"版本 {plugin.version}" if plugin.version else "",
                                      f"作者：{plugin.author}" if plugin.author else "",
                                      f"插件 API {plugins.api_text(plugin.api)}") if x)
        lines: list[ft.Control] = [
            ft.Row([t.text(plugin.name, 14, weight=ft.FontWeight.W_600), self._status(plugin, state)],
                   spacing=10, wrap=True),
        ]
        if meta:
            lines.append(t.text(meta, 12, t.FAINT))
        if plugin.description:
            lines.append(t.text(plugin.description, 12, t.MUTED))
        if state is not None and state.error:
            lines.append(ft.Container(t.text(translate(state.error), 12, t.SOFT, selectable=True, font_family=t.MONO),
                                      padding=10, border_radius=8,
                                      bgcolor=ft.Colors.with_opacity(0.08, t.RED)))
        elif on:
            chips = self._adds(state)
            if chips:
                lines.append(ft.Row(chips, spacing=6, run_spacing=6, wrap=True))
        elif plugin.error:
            lines.append(t.badge(translate(plugin.error), t.RED, "warning-diamond"))
        level, message = plugins.compatibility(plugin.api)
        if level == "deprecated":
            lines.append(t.badge(translate(message), t.AMBER, "warning-diamond"))
        available = self.app.plugin_updates.get(plugin.id)
        if available is not None and local:
            busy = self.downloading == plugin.id
            lines.append(ft.Row([
                t.chip(f"版本 {available.version} 已发布", "upload", t.GREEN),
                t.button('正在下载' if busy else f"更新到 {available.version}",
                         lambda e, a=available, p=plugin: self._download(a, p), "download", color=t.GREEN,
                         disabled=bool(self.downloading)),
            ], spacing=8, wrap=True))
        if forced:
            lines.append(t.badge('通过 POKELDN_PLUGINS 加载；环境变量包含此插件时，它将保持启用。', t.FAINT))
        elif plugin.entry_point is not None:
            lines.append(t.badge('作为 Python 包安装。', t.FAINT))

        def item(label, icon, action, color=t.MUTED):
            return ft.PopupMenuItem(ft.Row([t.pixel_icon(icon, color=color), t.text(label, 13)], spacing=10),
                                    on_click=action, height=40)
        menu_items = []
        if on and state.loaded and (first := self._first_tool(state)):
            menu_items.append(item('打开插件工具', "gamepad", lambda e, k=first: self._open_tool(*k)))
        if local:
            menu_items += [item('从文件更新', "upload", lambda e, p=plugin: self.app.page.run_task(
                self._pick_update, p)),
                           item('在文件夹中显示', "folder", lambda e, p=plugin: open_folder(str(p.folder)))]
        if plugin.homepage:
            menu_items.append(item('访问插件页面', "external-link",
                                   lambda e, u=plugin.homepage: self.app.page.run_task(self.app.open_url, u)))
        if local:
            menu_items.append(item('移除', "trash", lambda e, p=plugin: self._confirm_remove(p), t.RED))
        menu = ft.PopupMenuButton(
            content=ft.Container(t.pixel_icon("more-vertical", color=t.MUTED), width=32, height=32,
                                 alignment=ft.Alignment.CENTER),
            tooltip='更多', bgcolor=t.PANEL, menu_position=ft.PopupMenuPosition.UNDER,
            items=menu_items) if menu_items else ft.Container(width=32)
        toggle = t.switch(plugin.id in s.plugins or forced, lambda e, p=plugin: self._toggle(p, e.control.value))
        toggle.disabled = forced or bool(plugin.error) or \
            plugins.compatibility(plugin.api)[0] in ("newer", "older")
        toggle.tooltip = '启用' if not on else '停用'
        return t.surface(ft.Container(ft.Row([
            plugin_icon(plugin.icon),
            ft.Column(lines, spacing=4, expand=True),
            ft.Row([toggle, menu], spacing=2),
        ], spacing=14, vertical_alignment=ft.CrossAxisAlignment.START), padding=ft.Padding(16, 14, 8, 14)))

    def _status(self, plugin: plugins.Plugin, state: plugins.Plugin | None) -> ft.Control:
        if plugins.compatibility(plugin.api)[0] in ("newer", "older"):
            return t.chip('不兼容', "warning-diamond", t.RED)
        if plugin.error or (state is not None and state.error):
            return t.chip('加载失败', "warning-diamond", t.RED)
        if state is not None:
            return t.chip('已启用', "check", t.GREEN)
        if plugin.folder is not None and plugin.folder.parent == plugins.folder() and not store.consented(plugin):
            return t.chip('手动添加', "warning-diamond", t.AMBER)
        return t.chip('已停用', None, t.FAINT)

    def _adds(self, state: plugins.Plugin) -> list[ft.Control]:
        names = {g.key: g.name for g in plugins.games()}
        chips = [t.chip(f"{g.name} · {len(g.tools)} 个工具", "gamepad", t.BLUE)
                 for g in state.games]
        chips += [t.chip(f"{names.get(game, game)}：{tool.name}", "arrows-horizontal", t.BLUE)
                  for game, tool in state.tools]
        chips += [t.chip(f"无线通信后端：{plugins.radio(r).label}", "cpu", t.AMBER) for r in state.radios]
        return chips

    def _radio_card(self) -> list[ft.Control]:
        s = self.app.settings
        choices = [("", '开发板（默认）')] + [(r.scheme, r.label) for r in plugins.radios()]
        if s.radio and s.radio not in {c[0] for c in choices}:
            choices.append((s.radio, f"{s.radio}（插件已停用）"))
        if len(choices) == 1:
            return []
        return [t.section('无线通信后端', t.card(
            '传输无线消息的后端',
            t.dropdown(choices, s.radio, on_select=lambda e: self._set_radio(e.control.value or "")),
            '除非插件说明另有要求，否则请使用开发板。“游戏”页面会在开始前显示当前使用的无线通信后端。'))]

    def _first_tool(self, state: plugins.Plugin):
        for game in state.games:
            if game.tools:
                return game.key, game.tools[0].key
        return (state.tools[0][0], state.tools[0][1].key) if state.tools else None

    # Actions

    def say(self, text: str, color: str = t.GREEN, icon: str = "check", action: tuple | None = None) -> None:
        row = [t.pixel_icon(icon, color=color), t.text(text, 13, expand=True)]
        if action:
            row.append(t.link_button(*action))
        row.append(t.icon_button("close", self._clear_notice, '关闭提示'))
        self.notice.content = ft.Container(ft.Row(row, spacing=10), padding=ft.Padding(14, 6, 6, 6),
                                           border_radius=12, bgcolor=ft.Colors.with_opacity(0.1, color))

    def _clear_notice(self, e=None) -> None:
        self.notice.content = None
        self.notice.update()

    def _reload(self, message: str = "") -> None:
        plugins.reload()
        s = self.app.settings
        if s.radio and plugins.radio(s.radio) is None:
            s.radio = ""
            s.save()
            message = (message + " " if message else "") + '无线通信后端已恢复为开发板。'
        if message:
            self.say(message, t.MUTED, "refresh")
        self.render(update=True)

    def _refresh(self, e=None) -> None:
        self._reload('已重新加载插件，正在检查更新。')
        self.app.check_plugin_updates()

    def _download(self, available, plugin: plugins.Plugin) -> None:
        from pokeldn.app import plugin_updates
        self.downloading = plugin.id
        self.render(update=True)

        def work():
            try:
                path, error = plugin_updates.download(available, SESSION / "plugin-download"), ""
            except OSError as failure:
                path, error = None, str(failure)
            self.app.ui(lambda: done(path, error))

        def done(path, error):
            self.downloading = ""
            self.render(update=True)
            if path is None:
                self.error_dialog(f"{plugin.name} {available.version} 下载失败", error)
            else:
                self.open_file(str(path), expected=plugin)

        threading.Thread(target=work, daemon=True).start()

    def _open_folder(self, e) -> None:
        plugins.folder().mkdir(parents=True, exist_ok=True)
        open_folder(str(plugins.folder()))

    def _open_tool(self, game: str, tool: str) -> None:
        self.app.navigate("games", game=game, tool=tool)

    def _set_radio(self, scheme: str) -> None:
        self.app.settings.radio = scheme
        self.app.settings.save()
        radio = plugins.radio(scheme)
        self.say(f"会话现使用 {radio.label}。" if radio else '会话现使用开发板。', t.BLUE, "cpu")
        self.render(update=True)

    def _toggle(self, plugin: plugins.Plugin, value: bool) -> None:
        if value and plugin.folder is not None and not store.consented(plugin):
            try:
                package = store.describe(plugin)
            except (OSError, store.PackageError) as error:
                self.error_dialog(f"无法启用 {plugin.name}", str(error))
                self.render(update=True)
                return
            self.consent(package, "enable", plugin)
            self.render(update=True)     # the switch stays off until the user accepts
            return
        self._set_enabled(plugin.id, value)
        state = {p.id: p for p in plugins.load()}.get(plugin.id)
        if value and state is not None and state.error:
            self.say(f"{plugin.name} 加载失败，请查看插件卡片上的错误。", t.RED, "warning-diamond")
        elif value:
            self.say(f"{plugin.name} 已启用。", action=self._tools_action(plugin.id))
        else:
            self.say(f"{plugin.name} 已停用，其工具会隐藏，直到再次启用。", t.MUTED, "check")
        self.render(update=True)

    def _set_enabled(self, plugin_id: str, value: bool) -> None:
        s = self.app.settings
        s.plugins = [i for i in s.plugins if i != plugin_id] + ([plugin_id] if value else [])
        s.save()
        plugins.reload()
        if s.radio and plugins.radio(s.radio) is None:
            s.radio = ""
            s.save()

    def _tools_action(self, plugin_id: str):
        state = {p.id: p for p in plugins.load()}.get(plugin_id)
        first = self._first_tool(state) if state is not None and state.loaded else None
        return ('打开插件工具', lambda e, k=first: self._open_tool(*k)) if first else None

    # Adding a package

    def _dropped(self, paths: list[str]) -> None:
        wanted = [p for p in paths if drop.suffix(p) == store.EXTENSION]
        if not wanted:
            self.error_dialog('不是插件文件', '请拖入扩展名为 .pokeplugin 的文件。')
            return
        self.open_file(wanted[0])

    async def _pick(self, e=None) -> None:
        files = await self.app.picker.pick_files(dialog_title='选择插件', allowed_extensions=[store.EXTENSION],
                                                 file_type=ft.FilePickerFileType.CUSTOM)
        if files and files[0].path:
            self.open_file(files[0].path)

    async def _pick_update(self, plugin: plugins.Plugin) -> None:
        files = await self.app.picker.pick_files(dialog_title=f"更新 {plugin.name}",
                                                 allowed_extensions=[store.EXTENSION],
                                                 file_type=ft.FilePickerFileType.CUSTOM)
        if files and files[0].path:
            self.open_file(files[0].path, expected=plugin)

    def open_file(self, path: str, expected: plugins.Plugin | None = None) -> None:
        """Reads a package and shows what it is with its risks; nothing is installed before the user accepts."""
        try:
            package = store.read(path)
        except store.PackageError as error:
            self.error_dialog(f"无法安装 {os.path.basename(path)}", str(error))
            return
        if expected is not None and package.id != expected.id:
            self.error_dialog('插件不一致', f"{os.path.basename(path)} 属于 {package.name}，并非 {expected.name} 的更新。")
            return
        self.consent(package, store.compare(package, store.installed(package.id)), store.installed(package.id))

    def error_dialog(self, title: str, message: str) -> None:
        self.app.page.show_dialog(t.dialog(
            title=ft.Row([t.pixel_icon("warning-diamond", size=24, color=t.RED), t.text(title, 18, expand=True)],
                         spacing=10),
            content=t.text(translate(message), 13, t.MUTED, width=420, selectable=True),
            actions=[t.button('确定', lambda e: self.app.page.pop_dialog())]))

    def consent(self, package: store.Package, action: str, current: plugins.Plugin | None) -> None:
        """The risk screen every install, update and first turn-on goes through."""
        trust = store.trust(package)
        stranger = trust in ("changed", "dropped")     # not the author of the copy seen before
        state = {"accepted": False, "enable": True, "stranger": not stranger}
        go = t.button('启用' if action == "enable" else ACTIONS[action], None,
                      "check", disabled=True, color=t.RED if stranger else t.BLUE)

        def ready() -> None:
            go.disabled = not (state["accepted"] and state["stranger"])
            go.update()

        def accepted(value: bool) -> None:
            state["accepted"] = value
            ready()

        def stranger_ok(value: bool) -> None:
            state["stranger"] = value
            ready()

        def enable(e) -> None:
            state["enable"] = bool(e.control.value)

        def close(e=None) -> None:
            self.app.page.pop_dialog()

        def confirm(e) -> None:
            if not (state["accepted"] and state["stranger"]):
                return
            close()
            self._accepted(package, action, current, state["enable"])

        go.on_click = confirm
        meta = " · ".join(x for x in (f"版本 {package.version}" if package.version else "",
                                      f"作者：{package.author}" if package.author else '作者未署名') if x)
        lines: list[ft.Control] = [
            ft.Row([
                plugin_icon(package.icon or (current.icon if current else ""), 56),
                ft.Column([t.text(package.name, 20, weight=ft.FontWeight.W_600),
                           t.text(meta, 12, t.MUTED)], spacing=2, expand=True),
                t.icon_button("close", close, '取消'),
            ], spacing=14, vertical_alignment=ft.CrossAxisAlignment.START),
        ]
        if package.description:
            lines.append(t.text(package.description, 13, t.SOFT))
        version_note = {
            "update": (f"将 {current.name if current else ''} 从 {current.version if current else '?'} 更新到 {package.version}，保留已保存的数据。", t.BLUE, "upload"),
            "reinstall": (f"版本 {package.version} 已安装；此操作会替换其文件。", t.MUTED,
                          "refresh"),
            "downgrade": (f"将旧版 {package.version} 安装到较新版 {current.version if current else '?'} 上。",
                          t.AMBER, "warning-diamond"),
            "enable": ('此插件由手动复制到插件文件夹，尚未经应用检查。',
                       t.AMBER, "warning-diamond"),
        }.get(action)
        if version_note:
            lines.append(t.badge(*version_note))
        level, message = plugins.compatibility(package.api)
        if level == "deprecated":
            lines.append(t.badge(translate(message), t.AMBER, "warning-diamond"))
        if package.source:
            lines.append(t.badge(f"{os.path.basename(package.source)} · {package.files} 个文件 · {store.size_text(package.size)}", t.FAINT, "archive"))
        lines.append(self._signature(package, trust))
        lines.append(self._findings(package.findings))
        lines.append(ft.Container(ft.Row([
            t.pixel_icon("warning-diamond", size=24, color=t.RED),
            ft.Column([t.text('插件具有完整访问权限', 14, weight=ft.FontWeight.W_600),
                       *[ft.Row([t.text("·", 13, t.RED), t.text(r, 12, t.SOFT, expand=True)], spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.START) for r in RISKS]],
                      spacing=6, expand=True),
        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START),
            padding=16, border_radius=14, bgcolor=ft.Colors.with_opacity(0.08, t.RED),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, t.RED))))
        if stranger:
            lines.append(checkbox('我知道此文件并非来自已安装版本的作者，仍要安装。', False, stranger_ok))
        lines.append(checkbox('我理解这些风险，并信任此插件的作者。', False, accepted))
        if action != "enable":
            lines.append(ft.Row([t.text('安装后启用', 13, expand=True),
                                 t.switch(True, enable)]))
        self.app.page.show_dialog(t.dialog(
            modal=True, content_padding=0, actions_padding=0, inset_padding=32, scrollable=True,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS, semantics_label=f"安装 {package.name}",
            content=ft.Container(ft.Column([
                ft.Container(ft.Column(lines, spacing=12, tight=True), padding=ft.Padding(26, 22, 18, 6)),
                ft.Container(ft.Row([ft.Container(expand=True), t.secondary_button('取消', close), go],
                                    spacing=8), padding=ft.Padding(26, 12, 22, 22)),
            ], spacing=0, tight=True), width=540, border_radius=20)))

    @staticmethod
    def _signature(package: store.Package, trust: str) -> ft.Control:
        """Who signed the file, against the author of the copy this app saw before."""
        key = f"密钥 {store.fingerprint(package.key)}" if package.key else ""
        title, text, color, icon = {
            "same": ('由同一作者签名', f"与此前安装版本签名的密钥一致：{key}。",
                     t.GREEN, "shield"),
            "new": ('由作者签名', f"签名使用 {key}。若作者公开了密钥，请进行比对。后续更新必须使用相同密钥。", t.BLUE, "key"),
            "unsigned": ('未签名', '无法证明此文件的作者身份，也无法证明文件未经修改。',
                         t.AMBER, "warning-diamond"),
            "changed": ('由其他人签名', f"签名使用 {key}，与此前安装版本的作者密钥不同。此文件可能由其他人制作。", t.RED, "warning-diamond"),
            "dropped": ('不再带有签名', '此前安装的版本有作者签名，此文件没有，可能由其他人制作。', t.RED, "warning-diamond"),
        }[trust]
        return ft.Container(ft.Row([t.pixel_icon(icon, size=24, color=color), ft.Column([
            t.text(title, 14, weight=ft.FontWeight.W_600), t.text(text, 12, t.SOFT, selectable=True)],
            spacing=4, expand=True)], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START),
            padding=16, border_radius=14, bgcolor=ft.Colors.with_opacity(0.06, color),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, color)))

    @staticmethod
    def _findings(findings: list[str]) -> ft.Control:
        """What a reading of its code found; it informs, it cannot clear a plugin."""
        if findings:
            body = [t.text('代码会执行的操作', 14, weight=ft.FontWeight.W_600),
                    *[ft.Row([t.text("·", 13, t.AMBER), t.text(translate(f), 12, t.SOFT, expand=True)], spacing=8,
                             vertical_alignment=ft.CrossAxisAlignment.START) for f in findings]]
            color, icon = t.AMBER, "search"
        else:
            body = [t.text('代码会执行的操作', 14, weight=ft.FontWeight.W_600),
                    t.text('未在文件中发现网络访问、外部程序调用、删除操作或隐藏代码。代码扫描无法证明插件安全。', 12, t.SOFT)]
            color, icon = t.BLUE, "search"
        return ft.Container(ft.Row([t.pixel_icon(icon, size=24, color=color), ft.Column(body, spacing=6, expand=True)],
                                   spacing=12, vertical_alignment=ft.CrossAxisAlignment.START),
                            padding=16, border_radius=14, bgcolor=ft.Colors.with_opacity(0.06, color),
                            border=ft.Border.all(1, ft.Colors.with_opacity(0.25, color)))

    def _accepted(self, package: store.Package, action: str, current, enable: bool) -> None:
        if action == "enable":
            store.accept(current, package.key)
            self._toggle(current, True)
            return
        try:
            store.install(package)
        except (OSError, store.PackageError) as error:
            self.error_dialog(f"{package.name} 未安装成功", str(error))
            return
        if package.source.startswith(str(SESSION / "plugin-download")):
            shutil.rmtree(SESSION / "plugin-download", ignore_errors=True)
        if self.app.plugin_updates.pop(package.id, None) is not None:
            self.app._plugin_updates_done(self.app.plugin_updates)
        if enable:
            self._set_enabled(package.id, True)
        else:
            plugins.reload()
        state = {p.id: p for p in plugins.load()}.get(package.id)
        done = {"install": '已安装', "update": f"已更新到 {package.version}",
                "reinstall": '已重新安装', "downgrade": f"已切换到 {package.version}"}[action]
        if state is not None and state.error:
            self.say(f"{package.name} {done}，但加载失败。请查看插件卡片上的错误。", t.RED,
                     "warning-diamond")
        elif enable:
            self.say(f"{package.name} {done}并已启用。", action=self._tools_action(package.id))
        else:
            self.say(f"{package.name} {done}。需要使用其工具时可启用。", t.MUTED)
        self.render(update=True)

    # Removing

    def _confirm_remove(self, plugin: plugins.Plugin) -> None:
        kept = plugins.data_folder(plugin.id).is_dir()
        state = {"data": False}

        def done(e):
            self.app.page.pop_dialog()
            try:
                store.remove(plugin.id, data=state["data"])
            except (OSError, store.PackageError) as error:
                self.error_dialog(f"{plugin.name} 未移除成功", str(error))
                return
            self._set_enabled(plugin.id, False)
            self.say(f"{plugin.name} 已移除。", t.MUTED, "trash")
            self.render(update=True)

        self.app.page.show_dialog(t.dialog(
            title=ft.Row([plugin_icon(plugin.icon, 32), t.text(f"移除 {plugin.name}？", 18, expand=True)],
                         spacing=12),
            content=ft.Column([
                t.text('此电脑上的插件文件将被删除，其工具会从“游戏”页面移除。正在运行的会话会继续，直到会话结束。', 13, t.MUTED),
                *([checkbox(f"同时删除已保存的数据（{store.size_text(store.kept_data(plugin.id))}）；若保留，重新安装后仍可使用。", False,
                            lambda value: state.update(data=value))] if kept else []),
            ], spacing=12, tight=True, width=420),
            actions=[t.secondary_button('取消', lambda e: self.app.page.pop_dialog()),
                     t.button('移除', done, "trash", color=t.RED)]))
