"""The Mystery Gift - Simulated card: every Pokemon gift the game gave, from PKHeX's event database
(pokeldn.pokemon.Service.gift_events), searched by anything a tile shows. Up to the field's queue limit are
picked in order, each made fresh and legal for the app's trainer, then offered by the trade host
(docs/gift_simulated.md)."""

import threading
from datetime import date

import flet as ft

from gui import theme as t
from gui.localization import SERVICE, translate, summary_text
from gui.views.sprites import MINI, Sprite
from gui.views.widgets import PixelActivity
from pokeldn import pokemon as builder
from pokeldn.app.command import offers

PAGE = 24   # tiles shown at once, and how many Show more adds: each tile loads a sprite
BOX = 440   # the height of the list's scroll box, for more tiles than FIT
FIT = 10    # tiles that show whole without one: Legends Z-A has 8 gifts
LANGUAGES = {1: "日语", 2: "英语", 3: "法语", 4: "意大利语", 5: "德语", 7: "西班牙语", 8: "韩语",
             9: "简体中文", 10: "繁体中文"}
UNMADE = "不合法：PKHeX 无法生成合法副本"


def day(iso: str) -> str:
    try:
        d = date.fromisoformat(iso)
        return f"{d.year} 年 {d.month} 月 {d.day} 日"
    except ValueError:
        return ""


def species(event: dict) -> str:
    return translate(f"{event['species']}-{event['form']}" if event.get("form") else event["species"])


def facts(event: dict) -> str:
    """The Pokemon: species, level, Tera type, shininess and held item."""
    parts = [species(event), f"等级 {event['level']}", f"太晶属性：{translate(event['tera'])}" if event.get("tera") else "",
             {"always": "异色", "random": "可能为异色"}.get(event["shiny"], ""), translate(event.get("held_item", ""))]
    return " · ".join(p for p in parts if p)


def origin(event: dict) -> str:
    """Whose it is, the language the card fixes, and when it was given."""
    parts = [f"OT {event['ot']}" if event.get("ot") else "你的初训家", LANGUAGES.get(event.get("language"), ""),
             day(event.get("date", ""))]
    return " · ".join(p for p in parts if p)


def problem(event: dict) -> str:
    """Why a gift's copy is illegal, or "" for a legal one: PKHeX makes none, or no save in the trainer's
    language received the card (pokeldn.pokemon.Service.gift_event)."""
    if event.get("legal", True):
        return ""
    return f"不合法：{translate(event['refused'])}" if event.get("refused") else UNMADE


def warning(event: dict) -> str:
    """What the HOME tracker setting gave a gift HOME gave (docs/gui.md, The HOME tracker setting), or ""."""
    return translate(builder.HOME_TRACKER_WARNINGS.get(event.get("home_tracker", ""), ""))


def haystack(event: dict) -> str:
    return " ".join([event["title"], facts(event), origin(event), translate(event.get("ball", "")), *(translate(m) for m in event.get("moves", ())),
                     str(event.get("card_id", "")), problem(event), warning(event)]).casefold()


class EventGiftPicker:
    """An ordered queue of built Pokemon entries, each with its event's key and title."""

    def __init__(self, app, game: str, value: dict | list[dict] | None, on_change, limit: int = 1):
        self.app, self.game, self.on_change = app, game, on_change
        self.limit = max(1, int(limit))
        self.values = [dict(v) for v in offers(value)[:self.limit] if v.get("file")]
        self.events: list[dict] | None = None
        self.shown = PAGE
        self.busy = False
        self.search = t.field(hint="搜索：梦幻、Gavin、火、异色、韩语、2024…", expand=True,
                              on_change=self._searched)
        self.count = t.text("", 12, t.MUTED)
        self.tiles = ft.Column(spacing=6, tight=True)
        self.more = t.secondary_button('显示更多', self._more, "chevron-down", visible=False)
        self.status = ft.Container()
        self.result = ft.Container()
        self.scroller = ft.Column([self.tiles, ft.Row([self.more], alignment=ft.MainAxisAlignment.CENTER)],
                                  spacing=10)
        self.box = ft.Container(self.scroller)
        self.control = ft.Column([self.result, self.status, ft.Row([self.search]), self.count, self.box], spacing=10)
        self.tiles.controls = [ft.Row([PixelActivity('正在读取活动'),
                                       t.text('正在读取 PKHeX 活动数据库…', 12, t.MUTED)], spacing=8)]
        self._show_result()
        threading.Thread(target=self._load, daemon=True).start()

    # The events

    def _load(self) -> None:
        try:
            events, error = SERVICE.gift_events(self.game, self.app.settings.trainer(self.game)), ""
        except Exception as exc:
            events, error = [], str(exc) or type(exc).__name__

        def show():
            if error:
                self.tiles.controls = [t.text(f"无法读取活动：{translate(error)}", 12, t.RED, selectable=True)]
            else:
                self.events = events
                self._render()
            self._refresh()
        self.app.ui(show)

    def _render(self) -> None:
        if self.events is None:
            return
        words = self.search.value.casefold().split()
        matches = [e for e in self.events if all(w in haystack(e) for w in words)]
        self.tiles.controls = t.grid_rows([self._tile(e) for e in matches[:self.shown]])
        if not matches:
            self.tiles.controls = [t.text("没有符合条件的活动宝可梦。", 12, t.MUTED)]
        self.count.value = f"{len(matches)} / {len(self.events)} 只活动宝可梦，按时间从新到旧排序"
        self.more.visible = len(matches) > self.shown
        few = len(matches) <= FIT
        self.box.height, self.scroller.scroll = (None, None) if few else (BOX, ft.ScrollMode.AUTO)

    def _tile(self, event: dict) -> ft.Control:
        """An illegal copy's tile has a red outline, chosen or not, and says why; one with a HOME tracker
        warning, an amber one."""
        chosen = sum(event["key"] == value.get("event") for value in self.values)
        disabled = self.busy or (self.limit > 1 and len(self.values) >= self.limit)
        shiny = event["shiny"] == "always"
        why, warned = problem(event), warning(event)
        head = [t.text(event["title"], 13, weight=ft.FontWeight.W_600, max_lines=1,
                       overflow=ft.TextOverflow.ELLIPSIS, expand=True)]
        if shiny:
            head.append(t.pixel_icon("sparkles", size=12, color=t.AMBER, tooltip='异色'))
        if chosen and self.limit > 1:
            head.append(t.text(f"已加入队列 {chosen} 份", 11, t.BLUE))
        lines = [ft.Row(head, spacing=6),
                 t.text(facts(event), 12, t.SOFT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                 t.text(origin(event), 12, t.MUTED, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)]
        for note, color in ((why, t.RED), (warned, t.AMBER)):
            if note:
                lines.append(ft.Row([t.pixel_icon("warning-diamond", size=12, color=color),
                                     t.text(note, 12, color, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                                            expand=True)], spacing=6))
        return ft.Container(ft.Row([
            Sprite(self.app, event["species_id"], shiny, size=MINI, form=event.get("form_id", 0)).control,
            ft.Column(lines, spacing=0, expand=True),
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding(10, 8, 10, 8), border_radius=10, tooltip="、".join(translate(m) for m in event.get("moves", ())) or None,
            border=ft.Border.all(1, t.RED if why else t.AMBER if warned else t.BLUE if chosen else t.BORDER),
            bgcolor=t.SELECTED if chosen else None, disabled=disabled, opacity=0.5 if disabled else 1.0,
            on_click=lambda e, key=event["key"]: self._pick(key))

    async def _searched(self, _e) -> None:
        self.shown = PAGE
        self._render()
        self._refresh()
        await self.scroller.scroll_to(offset=0)     # the matches start at the top

    def _more(self, _e) -> None:
        self.shown += PAGE
        self._render()
        self._refresh()

    def _refresh(self) -> None:
        try:
            self.control.update()
        except RuntimeError:    # the card was redrawn away
            pass

    # The gifts picked

    def _pick(self, key: str) -> None:
        """Makes a fresh copy and adds it to the queue. A one-slot picker keeps the old single-value shape."""
        if self.busy:
            return
        if self.limit > 1 and len(self.values) >= self.limit:
            self.status.content = t.text(f"队列已满：每场会话最多交换 {self.limit} 份礼物。",
                                         12, t.AMBER)
            self._refresh()
            return
        self.busy = True
        trainer = self.app.settings.trainer(self.game)
        self.status.content = ft.Row([PixelActivity('正在生成宝可梦'),
                                      t.text('正在生成新的副本…', 12, t.MUTED)], spacing=8)
        self._render()
        self._refresh()

        def work():
            try:
                info = SERVICE.gift_event(self.game, key, trainer)
                if info["refused"]:
                    raise ValueError(f"设置中的训练家无法接收此礼物：{translate(info['refused'])}。")
                value, error = {"file": info["file"], "event": key, "title": info["title"],
                                "species": info["species_id"], "shiny": info["shiny"],
                                "form_id": info.get("form_id", 0),
                                "summary": builder.summary(info), "legal": info["legal"],
                                "home_tracker": info.get("home_tracker", ""),
                                "encounter": info["encounter"], "moves": info["moves"], "ot": info["ot"],
                                "your_ot": info["your_ot"], "handled": info.get("handled", False)}, ""
            except Exception as exc:
                value, error = None, str(exc) or type(exc).__name__

            def done():
                self.busy = False
                if value is None:
                    self.status.content = t.text(translate(error), 12, t.RED, selectable=True)
                else:
                    self.status.content = None
                    if self.limit == 1:
                        self.values = [value]
                        self.on_change(dict(value))
                    else:
                        self.values.append(value)
                        self.on_change([dict(v) for v in self.values])
                    self._show_result()
                self._render()
                self._refresh()
            self.app.ui(done)
        threading.Thread(target=work, daemon=True).start()

    def _remove(self, index: int) -> None:
        """Removes one queued gift without rebuilding the others."""
        if not 0 <= index < len(self.values):
            return
        self.values.pop(index)
        if not self.busy:
            self.status.content = None
        self.on_change([dict(v) for v in self.values] if self.limit > 1 else
                       (dict(self.values[0]) if self.values else {}))
        self._render()
        self._show_result()
        self._refresh()

    def _result_card(self, value: dict, number: int | None = None) -> ft.Control:
        legal = value.get("legal", False)
        title = value.get("title", "")
        if number is not None:
            title = f"{number}. {title}"
        detail = " · ".join(p for p in ("、".join(translate(m) for m in value.get("moves", ())), f"OT {value.get('ot', '')}") if p)
        lines = [ft.Row([t.text(title, 13, weight=ft.FontWeight.W_600, expand=True),
                         t.badge('合法' if legal else '不合法', t.GREEN if legal else t.RED,
                                 "check" if legal else "warning-diamond")], spacing=8),
                 t.text(summary_text(value.get("summary", "")), 12, t.SOFT),
                 t.text(detail, 12, t.MUTED)]
        if warned := builder.HOME_TRACKER_WARNINGS.get(value.get("home_tracker", "")):
            lines.append(ft.Row([t.badge(translate(warned), t.AMBER, "warning-diamond")]))
        trailing = ([t.icon_button("close", lambda e, n=number - 1: self._remove(n), '移除此礼物')]
                    if number is not None else [])
        return ft.Container(ft.Row([
            Sprite(self.app, int(value.get("species") or 0), bool(value.get("shiny")), size=MINI,
                   form=value.get("form_id", 0)).control,
            ft.Column(lines, spacing=2, expand=True),
            *trailing,
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding(10, 8, 10, 8), border_radius=10, bgcolor=ft.Colors.with_opacity(0.04, "#FFFFFF"),
            border=None if legal else ft.Border.all(1, t.RED))

    def _show_result(self) -> None:
        if not self.values:
            self.result.content = (t.text(f"选择最多 {self.limit} 份礼物，将按此顺序交换。", 12, t.MUTED)
                                   if self.limit > 1 else None)
            return
        if self.limit == 1:
            self.result.content = self._result_card(self.values[0])
            return
        full = len(self.values) >= self.limit
        note = (f"已加入队列 {len(self.values)} / {self.limit} 份礼物，按此顺序交换"
                + (" · 队列已满" if full else ""))
        self.result.content = ft.Column([
            t.text(note, 12, t.MUTED),
            *[self._result_card(value, n) for n, value in enumerate(self.values, start=1)],
        ], spacing=6)
