import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pokeldn.app import paths  # noqa: E402,F401  (puts the repository and vendor/LDN on sys.path)

if len(sys.argv) > 2 and sys.argv[1] in ("--run", "--module"):
    from pokeldn.app.runner import child
    child(sys.argv[1:])
    sys.exit(0)

# The app's own process never drives a board: an inherited POKELDN_RADIO would open the port as
# soon as pokeldn.ldn is imported.
os.environ.pop("POKELDN_RADIO", None)

import flet as ft  # noqa: E402

from gui import drop, flet_client, screen, theme as t  # noqa: E402
from gui.app import App  # noqa: E402
from gui.views.widgets import page_key  # noqa: E402
from pokeldn import __version__  # noqa: E402
from pokeldn.app.paths import ROOT  # noqa: E402

PAGES = (
    ("games", '游戏', "gamepad"),
    ("board", '开发板', "cpu"),
    ("docs", '文档', "book-open"),
)
SETTINGS = ("settings", '设置', "gear")
UPDATE = ("update", '更新', "download")


def main(page: ft.Page) -> None:
    page.title = "pokeldn"
    page.theme_mode = ft.ThemeMode.DARK
    # CanvasKit web previews cannot use the desktop host's installed fonts.
    page.theme = page.dark_theme = t.app_theme(system_fonts=not page.web)
    chinese = ft.Locale("zh", "CN", "Hans")
    page.locale_configuration = ft.LocaleConfiguration(supported_locales=[chinese], current_locale=chinese)
    page.bgcolor = t.BG
    page.padding = 0
    # 1440 x 900 overflows a 13-inch MacBook Air (1440 x 932 points less the menu bar): fit, then center.
    (width, height), (min_width, min_height) = screen.fit((1440, 900), (1180, 720), screen.size())
    page.window.min_width, page.window.min_height = min_width, min_height
    page.window.width, page.window.height = width, height
    page.window.bgcolor = t.BG

    app = App(page)
    views: dict[str, object] = {}
    content = ft.Container(expand=True)
    rail = ft.Column(spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    bottom = ft.Column(spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    current = {"key": "games"}

    def build(key: str):
        if key == "games":
            from gui.views.games import GamesView
            return GamesView(app)
        if key == "board":
            from gui.views.boards import BoardView
            return BoardView(app)
        if key == "docs":
            from gui.views.docs import DocsView
            return DocsView(app)
        from gui.views.settings import SettingsView
        return SettingsView(app)

    def item(entry) -> ft.Control:
        key, label, icon = entry
        active = key == current["key"]
        color = t.GREEN if key == "update" else t.RED if active else t.MUTED
        return ft.Semantics(selected=active, button=True, label=label, exclude_semantics=True,
                            on_tap=lambda e, k=key: navigate(k), content=ft.Container(ft.Column([
            t.pixel_icon(icon, size=24, color=color),
            t.text(label, 11, color, weight=ft.FontWeight.W_500),
        ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            width=56, padding=ft.Padding(0, 8, 0, 7), border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.12, t.RED) if active else None,
            on_click=lambda e, k=key: navigate(k), tooltip=label))

    def render_rail() -> None:
        rail.controls = [item(p) for p in PAGES]
        bottom.controls = [item(UPDATE)] * bool(app.update) + [item(SETTINGS)]

    def navigate(key: str, **kwargs) -> None:
        if key == "update":
            offer_update(app)
            return
        previous = views.get(current["key"])
        if previous is not None and hasattr(previous, "leave"):
            previous.leave()
        current["key"] = key
        if key not in views:
            views[key] = build(key)
        view = views[key]
        if hasattr(view, "enter"):
            view.enter(**kwargs)
        content.content = view.control
        render_rail()
        page.update()

    app.navigate = navigate
    page.on_keyboard_event = page_key     # set once, before a code box takes the focus
    side = t.panel(ft.Column([
        ft.Container(ft.Image(src="logo.svg", width=28, height=32), padding=ft.Padding(0, 16, 0, 18)),
        rail,
        ft.Container(expand=True),
        bottom,
        ft.Container(height=8),
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0), width=72)
    page.add(t.backdrop(ft.Row([side, content], spacing=t.GAP, expand=True,
                               vertical_alignment=ft.CrossAxisAlignment.STRETCH)))
    navigate("games")
    if not page.web:
        page.run_task(page.window.center)
    if not os.path.isfile(os.path.expanduser(app.settings.keys)):
        welcome(app)

    def updated() -> None:
        render_rail()
        page.update()
    app.update_listeners.append(updated)
    if getattr(sys, "frozen", False):
        threading.Thread(target=prune_viewers, daemon=True).start()
    if app.settings.check_updates:
        app.check_update()


def prune_viewers() -> None:
    try:
        flet_client.prune_cache()
    except Exception:   # housekeeping: a locked or vanished folder waits for the next launch
        pass


def offer_update(app: App) -> None:
    """A newer release on GitHub: its file for this computer, and its notes."""
    release = app.update

    def close(e):
        app.page.pop_dialog()

    def open_(url):
        def go(e):
            app.page.pop_dialog()
            app.page.run_task(app.open_url, url)
        return go

    direct = release.download != release.page
    app.page.show_dialog(t.dialog(
        semantics_label='有可用更新',
        title=t.text(f'pokeldn {release.version} 已发布', 17, weight=ft.FontWeight.W_600),
        content=ft.Container(t.text(
            f'当前版本：{__version__}. '
            + ('下载新版本，然后替换当前应用。' if direct else
               '从发布页面下载适用于此电脑的新版本，然后替换当前应用。')
            + '设置、密钥和已接收的宝可梦将保留在原位置。', 13, t.MUTED), width=460),
        actions=[t.link_button('更新内容', open_(release.page)),
                 t.secondary_button('稍后', close),
                 t.button('下载', open_(release.download), "download")],
    ))
    app.page.update()   # also shown from a background check, where Flet does not flush on its own


def welcome(app: App) -> None:
    """The one file the app cannot ship: the user's own Switch keys."""
    def close(e):
        app.page.pop_dialog()

    def use(path: str) -> None:
        app.settings.keys = path
        app.settings.save()
        app.page.pop_dialog()
        app.navigate("games")

    async def choose(e):
        files = await app.picker.pick_files(allowed_extensions=["keys"], file_type=ft.FilePickerFileType.CUSTOM)
        if files and files[0].path:
            use(files[0].path)

    def dropped(paths: list[str]) -> None:
        if path := next((p for p in paths if drop.suffix(p) == "keys"), ""):
            use(path)

    def instructions(e):
        app.page.pop_dialog()
        app.navigate("docs", doc="guide")

    body = ft.Column([
        ft.Row([ft.Image(src="logo.svg", width=28, height=32), ft.Container(expand=True),
                t.icon_button("close", close, '关闭欢迎页面')],
               vertical_alignment=ft.CrossAxisAlignment.START),
        t.text('欢迎使用 pokeldn', 22, weight=ft.FontWeight.W_600),
        t.text('直接通过电脑，以本地无线通信交换宝可梦和发送礼物。', 13, t.MUTED),
        ft.Container(height=6),
        t.step_list([
            '选择从自己的游戏机导出的 prod.keys。密钥用于解密本地无线通信消息，并保存在此电脑上。',
            '使用 USB 数据线连接 ESP32。',
            '选择游戏和功能，然后按照游戏机操作步骤进行。',
        ]),
        ft.Row([t.link_button('阅读设置指南', instructions)]),
    ], spacing=8, tight=True)
    app.page.show_dialog(t.dialog(
        modal=True, content_padding=0, actions_padding=0, inset_padding=32,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        semantics_label='欢迎使用 pokeldn',
        content=drop.target(ft.Container(ft.Column([
            ft.Container(body, padding=ft.Padding(28, 22, 18, 8)),
            ft.Container(ft.Row([
                t.text('将 prod.keys 拖放到此处，或稍后在设置中添加密钥。' if drop.AVAILABLE else
                       '稍后可在设置中添加密钥。', 12, t.FAINT, expand=True),
                t.secondary_button('稍后', close),
                t.button('选择 prod.keys', choose, "key"),
            ], spacing=8), padding=ft.Padding(28, 12, 24, 24)),
        ], spacing=0, tight=True), width=500, border_radius=20), dropped),
    ))


def run() -> None:
    assets = os.path.join(ROOT, "gui", "assets")
    drop.use_client()
    if os.environ.get("POKELDN_GUI_WEB"):   # a browser preview, for screenshots
        ft.run(main, assets_dir=assets, view=ft.AppView.WEB_BROWSER, no_cdn=True,
               port=int(os.environ["POKELDN_GUI_WEB"]))
    else:
        ft.run(main, assets_dir=assets)


if __name__ == "__main__":
    run()
