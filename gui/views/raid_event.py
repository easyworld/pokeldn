"""The Tera Raid host's Raid event card: the app's copy of the EventsGallery's raid events
(pokeldn.app.events_gallery), downloaded, checked and updated; the event the raid comes from,
searchable by its name or its bosses'; and the override for a boss a save catches once."""

import threading
import time

import flet as ft

from gui import theme as t
from gui.localization import raid_label, translate
from gui.views.widgets import Check, PixelActivity
from pokeldn.app import events_gallery as gallery
from pokeldn.sv import raid_event

NONE = "-"
NO_EVENT = "不使用活动，主持普通团体战 · 输入活动或宝可梦名称搜索"
ORDER = "#raid-event-order"       # "newest" (the default) or "oldest", kept with the tool's values
FOLDED = "#raid-event-folded"     # the chosen event while the card is folded, set aside until unfolded
CATCH = "--raid-catch-normal"


def day(date: str) -> str:
    when = gallery.date_of(date)
    return f"{when.year} 年 {when.month} 月 {when.day} 日" if when else "未知日期"


class RaidEventPicker:
    """`view` is the GamesView: it keeps the card open across redraws, holds the values and
    narrows the raid card to the chosen event."""

    def __init__(self, view, field):
        self.view, self.app, self.field = view, view.app, field
        self.stop = threading.Event()
        self.events = None          # the gallery's index, once listed
        self.chevron = t.pixel_icon("chevron-down" if view.raid_event_open else "chevron-right", color=t.FAINT)
        key = view.values.get(field.key) or ""
        folded = "" if key else view.values.get(FOLDED) or ""
        # An event the gallery lacks (never downloaded, or updated without it) stays chosen, for the
        # gallery to come back; the run refuses it (pokeldn.app.command.code_error).
        missing = bool(key) and not gallery.holds(key)
        if missing:
            summary, tip = (f"缺失：{raid_label(gallery.title(key))}",
                            "活动库中没有此活动，请下载或更新活动库，或选择其他活动")
        elif key:
            summary, tip = raid_label(gallery.title(key)), "折叠后暂停使用此活动，改为主持普通团体战"
        elif folded:
            summary, tip = f"已关闭：{raid_label(gallery.title(folded))}", "展开后恢复使用此活动"
        else:
            summary, tip = "未选择，主持普通团体战", "显示或隐藏活动团体战"
        self.summary = t.text(summary, 12, t.RED if missing else t.BLUE if key else t.MUTED, max_lines=1,
                              overflow=ft.TextOverflow.ELLIPSIS)
        header = ft.Container(ft.Row([
            self.chevron, t.text(field.label, 13, weight=ft.FontWeight.W_600),
            ft.Container(self.summary, expand=True, alignment=ft.Alignment.CENTER_RIGHT),
        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER), on_click=self._toggle, tooltip=tip)
        self.busy = ft.Container(PixelActivity("正在处理"), visible=False)
        self.status = t.text("", 12, t.MUTED, expand=True)
        self.actions = ft.Row([], spacing=8, tight=True)
        self.bar = ft.ProgressBar(value=None, color=t.BLUE, bgcolor=t.FIELD, height=4, border_radius=2,
                                  visible=False)
        self.dropdown = t.dropdown([], None, on_select=self._picked, enable_filter=True, editable=True,
                                   menu_height=360, hint_text="正在查找活动库…", disabled=True)
        self.order = t.icon_button(self._order_icon(), self._turn, self._order_tip())
        self.catch = ft.Column([], spacing=4, visible=False)
        self.body = ft.Column([
            t.text(field.help, 12, t.MUTED),
            ft.Row([self.busy, self.status, self.actions], spacing=8,
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self.bar,
            ft.Row([self.dropdown, self.order], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self.catch,
        ], spacing=10, visible=view.raid_event_open)
        self.control = t.surface(ft.Container(ft.Column([header, self.body], spacing=10, tight=True), padding=16))
        self._show_catch()
        if view.raid_event_open:
            self._refresh(update=False)

    # Opening

    def _toggle(self, _e) -> None:
        self.view.show_raid_event(not self.view.raid_event_open)

    def _working(self, text: str, bar: bool = False) -> None:
        self.status.value, self.status.color = text, t.MUTED
        self.busy.visible, self.bar.visible, self.bar.value = True, bar, None
        self.actions.controls = []

    def _background(self, work, then) -> None:
        """Runs work() on a thread, then then(result, error) on the page, error "" or why it failed."""
        def run():
            try:
                result, error = work(), ""
            except Exception as exc:
                result, error = None, str(exc)
            self.app.ui(lambda: then(result, error))
        threading.Thread(target=run, daemon=True).start()

    def _refresh(self, update: bool = True) -> None:
        """Looks for the gallery, then lists its events."""
        self._working("正在查找活动库…")
        if update:
            self.control.update()
        self._background(gallery.state, self._show_state)

    def _show_state(self, found, error: str) -> None:
        self.busy.visible = self.bar.visible = False
        if error:
            self._failed(error, self._refresh)
            return
        if not found.present:
            self.status.value = "尚未下载活动库。"
            self.actions.controls = [t.button("下载", self._download, "download")]
            self.dropdown.hint_text, self.dropdown.disabled = "请先下载活动库", True
            self.dropdown.options, self.dropdown.value = [], None
            self.control.update()
            return
        self.status.value = f"活动库更新于 {day(found.date)}"
        self.actions.controls = [t.secondary_button("检查更新", self._check, "refresh")]
        self.control.update()
        self._background(gallery.index, self._fill)

    # The events

    def _fill(self, events, error: str) -> None:
        if error:
            self.dropdown.hint_text = f"无法读取活动：{translate(error)}"
            self.dropdown.update()
            return
        self.events = events
        newest = self.view.values.get(ORDER, "newest") != "oldest"
        options = [ft.DropdownOption(key=NONE, text="不使用活动，主持普通团体战")]
        for entry in (reversed(events) if newest else events):
            species = "、".join(translate(name) for name in entry.species)
            options.append(ft.DropdownOption(key=entry.key, text=f"{raid_label(entry.title)} · {species}", content=ft.Column([
                t.text(raid_label(entry.title), 13, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                t.text(species, 11, t.MUTED, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=0, tight=True)))
        key = self.view.values.get(self.field.key) or ""
        known = {e.key for e in events}
        self.dropdown.options = options
        # No event leaves the field empty under its hint, so a search is typed straight in.
        self.dropdown.value = key if key in known else None
        self.dropdown.hint_text = NO_EVENT
        self.dropdown.disabled = False
        if key and key not in known:
            self.status.value, self.status.color = "活动库中没有所选活动。", t.RED
        self.control.update()

    def _picked(self, e) -> None:
        key = "" if e.control.value in (None, NONE) else e.control.value
        if key == (self.view.values.get(self.field.key) or ""):
            if e.control.value == NONE:         # back to the empty field under its hint
                self.dropdown.value = None
                self.dropdown.update()
            return
        self.view.values.pop(CATCH, None)       # another event: the catch-once override starts unchecked
        self.view.set_value(self.field, key, rebuild=True)

    def _order_icon(self) -> str:
        return "arrow-up" if self.view.values.get(ORDER) == "oldest" else "arrow-down"

    def _order_tip(self) -> str:
        return ("当前按时间升序排列；点击改为降序" if self.view.values.get(ORDER) == "oldest"
                else "当前按时间降序排列；点击改为升序")

    def _turn(self, _e) -> None:
        self.view.values[ORDER] = "newest" if self.view.values.get(ORDER) == "oldest" else "oldest"
        self.app.settings.save()
        self.order.icon.src = f"icons/{self._order_icon()}.svg"
        self.order.tooltip = self._order_tip()
        if self.events is not None:
            self._fill(self.events, "")
        self.order.update()

    def _show_catch(self) -> None:
        """The override under the event, for an event whose bosses a save catches once."""
        event = self.view.raid_event()
        names = raid_event.catch_once(event) if event is not None else []
        self.catch.visible = bool(names)
        if not names:
            return
        field = next(f for f in self.view.tool.fields if f.key == CATCH)
        box = Check("允许再次捕获", value=bool(self.view.values.get(CATCH)), size=13,
                    on_change=lambda on: self.view.set_value(field, on, rebuild=True))
        who = "、".join(translate(name) for name in names)
        self.catch.controls = [box.control, t.text(
            f"每个存档只能捕获一次{who}。勾选后，已捕获过的存档也可再次捕获，"
            "捕获的宝可梦与首次捕获的一样合法。", 12, t.MUTED)]

    # Download, check, update

    def _download(self, _e) -> None:
        self._run(lambda progress: gallery.download(progress=progress, cancelled=self.stop.is_set),
                  "正在下载活动库…")

    def _update(self, _e) -> None:
        self._run(lambda progress: gallery.download(progress=progress, cancelled=self.stop.is_set),
                  "正在更新活动库…")

    def _run(self, job, text: str) -> None:
        self.stop.clear()
        self._working(text, bar=True)
        self.actions.controls = [t.secondary_button("取消", lambda _e: self.stop.set())]
        self.control.update()
        shown = [0.0]

        def progress(what: str, done: int, total: int) -> None:
            now = time.monotonic()
            if now - shown[0] < 0.2 and done != total:
                return
            shown[0] = now
            mb = 1 << 20

            def show():
                self.status.value = (f"{translate(what)} {done / mb:.0f} / {total / mb:.0f} MB" if total else
                                     f"{translate(what)} {done / mb:.0f} MB" if done else translate(what))
                self.bar.value = done / total if total else None
                self.status.update()
                self.bar.update()
            self.app.ui(show)

        def work():
            try:
                job(progress)
                error = ""
            except Exception as exc:
                error = "Cancelled." if self.stop.is_set() else (str(exc) or type(exc).__name__)

            def done():
                if error:
                    self._failed(error, self._refresh)
                else:
                    self.view.gallery_changed()
            self.app.ui(done)
        threading.Thread(target=work, daemon=True).start()

    def _check(self, _e) -> None:
        self._working("正在检查更新…")
        self.control.update()
        self._background(gallery.check, self._checked)

    def _checked(self, found, error: str) -> None:
        self.busy.visible = False
        if error:
            self._failed(error, lambda: self._check(None))
            return
        if found.available:
            self.status.value = f"发现 {day(found.date)} 的更新。"
            self.actions.controls = [t.button("更新", self._update, "download")]
        else:
            self.status.value = f"已是最新版本：团体战活动最后更新于 {day(found.date)}。"
            self.actions.controls = [t.secondary_button("再次检查", self._check, "refresh")]
        self.control.update()

    def _failed(self, error: str, retry) -> None:
        self.busy.visible = self.bar.visible = False
        self.status.value, self.status.color = translate(error), t.RED
        self.actions.controls = [t.secondary_button("重试", lambda _e: retry())]
        self.control.update()
