"""The GTS: banked Pokemon listed against a wanted species on public relays, other players' listings,
and offers on them [pokeldn.app.gts, docs/online.md, The GTS]."""
import re
import threading
import time

import flet as ft

from gui import theme as t
from gui.localization import SERVICE, translate, summary_text, game_terms
from gui.views.bank import NAMES, game_icon
from gui.views.sprites import MINI, SIZE, Sprite
from pokeldn import __version__, pokemon
from pokeldn.app import bank
from pokeldn.app.gts import GtsError, Service
from pokeldn.app.paths import GTS
from pokeldn.online import gts

ANY = "-"
STATUS = {"active": ("已挂牌", t.BLUE, "globe"), "traded": ("已交换", t.GREEN, "checkbox-on"),
          "withdrawn": ("已撤下", t.MUTED, "close"), "ended": ("已结束", t.MUTED, "clock"),
          "waiting": ("等待挂牌方", t.BLUE, "clock"), "returned": ("已返还银行", t.AMBER, "repeat")}


def service(app) -> Service:
    """The app's one GTS client, started on first use; it answers offers while the app is open."""
    if getattr(app, "gts", None) is None:
        app.gts = Service(trainer=app.settings.ot, app=__version__)
        app.gts.start()
    return app.gts


def resume(app) -> None:
    """Start the client when an earlier session left a listing or an offer to settle."""
    if GTS.is_dir() and any(GTS.glob("*/state.json")):
        service(app)


def level_of(entry: bank.Entry) -> int:
    found = re.search(r"(?:level |等级 )(\d+)", entry.summary)
    return int(found.group(1)) if found else 0


def _when(seconds: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(seconds))


def wanted_text(wants: gts.Wants) -> str:
    name = translate(wants.name)
    if (wants.min_level, wants.max_level) == (1, 100):
        return name
    return f"{name}，等级 {wants.min_level} 到 {wants.max_level}"


class GtsView:
    def __init__(self, app):
        self.app = app
        self.visible = False
        self.species: list[tuple[str, str]] = []      # (id, name), every game's
        self.search = "has"
        self.chosen = ANY
        self.selected: tuple | str = ""                 # a listing's (key, d), or one of ours by id
        self.working = False
        self.pending = False
        self.status = t.text("", 12, t.MUTED)
        self.mine = ft.Column(spacing=2)
        self.grid = ft.Row(spacing=8, run_spacing=8, wrap=True)
        self.heading = t.text("", 12, t.MUTED)
        self.detail = ft.Column(spacing=24, scroll=ft.ScrollMode.AUTO, expand=True)
        self.note = t.text("", 12, t.MUTED)
        self.picker = t.dropdown([(ANY, "任意宝可梦")], ANY, self._pick, enable_filter=True, editable=True,
                                 menu_height=320)
        self.control = ft.Row([
            t.panel(ft.Column([
                t.panel_header("GTS", t.icon_button("refresh", lambda e: self._browse(), "刷新")),
                ft.Container(ft.Column([
                    self.status,
                    t.segmented([("has", "提供的宝可梦", "package"), ("wants", "想要的宝可梦", "search")], self.search,
                                self._mode),
                    self.picker,
                    t.button("存入宝可梦", lambda e: self._deposit_dialog(), "upload"),
                    t.section("我的挂牌与报价", self.mine),
                ], spacing=12, scroll=ft.ScrollMode.AUTO, expand=True), padding=ft.Padding(14, 4, 14, 14),
                    expand=True),
            ], spacing=0, expand=True), width=t.SIDEBAR_WIDTH),
            t.fade(ft.ListView([ft.Container(self.heading, padding=ft.Padding(4, 14, 4, 0)), self.grid],
                               spacing=12, padding=ft.Padding(0, 0, 0, 24), expand=True)),
            t.panel(ft.Column([
                t.panel_header("挂牌详情"),
                ft.Container(ft.Column([self.detail, self.note], spacing=8, expand=True),
                             padding=ft.Padding(18, 8, 18, 18), expand=True),
            ], spacing=0, expand=True), width=t.SESSION_WIDTH),
        ], spacing=t.GAP, expand=True, vertical_alignment=ft.CrossAxisAlignment.STRETCH)

    @property
    def client(self) -> Service:
        return service(self.app)

    def enter(self, **_) -> None:
        self.visible = True
        if self._changed not in self.client.listeners:
            self.client.listeners.append(self._changed)
        if not self.species:
            threading.Thread(target=self._load_species, daemon=True).start()
        self._browse(update=False)
        self.render()

    def leave(self) -> None:
        self.visible = False

    def _load_species(self) -> None:
        names: dict[int, str] = {}
        for game in NAMES:
            try:
                names.update((s["id"], s["name"]) for s in SERVICE.species(game))
            except (OSError, pokemon.BuilderError):
                continue

        def done():
            self.species = sorted(((str(k), v) for k, v in names.items()), key=lambda s: s[1])
            self.picker.options = [ft.DropdownOption(key=ANY, text="任意宝可梦")] + [
                ft.DropdownOption(key=k, text=v) for k, v in self.species]
            if self.visible:
                self.picker.update()
        self.app.ui(done)

    def _changed(self) -> None:
        """From a relay thread: draw again once, however many events arrive together."""
        if self.pending or not self.visible:
            return
        self.pending = True

        def draw():
            self.pending = False
            if self.visible:
                self.render()
                self.control.update()
        self.app.ui(draw)

    # Searching

    def _filters(self) -> dict:
        species = int(self.chosen) if self.chosen not in (None, ANY) else None
        return {"has": species} if self.search == "has" else {"wants": species}

    def _browse(self, update=True) -> None:
        self.client.browse(**self._filters())
        if update:
            self.render()
            self.control.update()

    def _mode(self, key: str) -> None:
        self.search = key
        self._browse()

    def _pick(self, e) -> None:
        self.chosen = e.control.value or ANY
        self._browse()

    # Drawing

    def render(self) -> None:
        client = self.client
        relays = client.connected()
        listings = client.open_listings(**self._filters())
        self.status.value = (f"已连接 {relays} / {len(gts.relay_urls())} 个中继服务器" if relays
                             else "正在连接中继服务器…")
        if listings:
            self.heading.value = f"{len(listings)} 条有效挂牌"
        elif client.loaded():
            self.heading.value = "没有匹配的有效挂牌。可从左侧存入一只宝可梦。"
        else:
            self.heading.value = "正在从中继服务器读取挂牌…"
        self.grid.controls = [self._tile(x) for x in listings]
        self.mine.controls = [self._mine_row(s) for s in client.mine()] or [
            t.text("尚未挂牌或提出交换。", 12, t.FAINT)]
        self.render_detail(listings)

    def _tile(self, listing: gts.Listing) -> ft.Control:
        active = self.selected == (listing.key, listing.d)
        shown = listing.pokemon
        return ft.Container(ft.Row([
            ft.Stack([Sprite(self.app, int(shown.get("species_id") or 0), bool(shown.get("shiny")), size=MINI).control,
                      ft.Container(game_icon(listing.game, 16), right=0, bottom=0)]),
            t.pixel_icon("arrows-horizontal", size=12, color=t.FAINT),
            Sprite(self.app, listing.wants.species, size=MINI).control,
        ], spacing=4, tight=True), padding=4, border_radius=14,
            tooltip=f"{translate(shown.get('species') or '')}，等级 {shown.get('level')}，想换 {wanted_text(listing.wants)}",
            border=ft.Border.all(2, t.BLUE if active else ft.Colors.TRANSPARENT),
            on_click=lambda e, k=(listing.key, listing.d): self._select(k))

    def _mine_row(self, state: dict) -> ft.Control:
        label, color, icon = STATUS[state["status"]]
        title = translate(state["info"].get("species", ""))
        if state["role"] == "listing":
            title += f" → {translate(gts.Wants(**state['wants']).name)}"
        else:
            title += f" → {translate(state['listing'] and gts.parse_listing(state['listing']).pokemon.get('species') or '')}"
        active = self.selected == state["id"]
        return ft.Container(ft.Row([
            Sprite(self.app, int(state["info"].get("species_id") or 0), bool(state["info"].get("shiny")),
                   size=MINI).control,
            ft.Column([t.text(title, 12, t.TEXT, weight=ft.FontWeight.W_600, max_lines=1,
                              overflow=ft.TextOverflow.ELLIPSIS),
                       t.badge(label, color, icon)], spacing=2, expand=True),
        ], spacing=8), padding=ft.Padding(4, 4, 6, 4), border_radius=12,
            bgcolor=t.SELECTED if active else None, on_click=lambda e, i=state["id"]: self._select(i))

    def _select(self, key) -> None:
        self.selected = key
        self.note.value = ""
        self.render()
        self.control.update()

    def render_detail(self, listings: list[gts.Listing]) -> None:
        if isinstance(self.selected, str) and self.selected:
            state = next((s for s in self.client.mine() if s["id"] == self.selected), None)
            if state:
                self.detail.controls = self._mine_detail(state)
                return
        listing = next((x for x in listings if (x.key, x.d) == self.selected), None)
        if listing is None:
            self.detail.controls = [t.text(
                "选择一条挂牌，查看宝可梦和挂牌方的需求。挂牌方下次打开应用时完成交换；等待期间，我方宝可梦暂时移出银行。", 13, t.MUTED)]
            return
        self.detail.controls = [self._about(listing.pokemon, listing.game),
                                t.section("想要", ft.Row([Sprite(self.app, listing.wants.species, size=MINI).control,
                                                              t.text(wanted_text(listing.wants), 13)], spacing=10)),
                                t.text(f"挂牌方：{listing.trainer or '一位训练家'}，有效期至 {_when(listing.expires)}",
                                       12, t.FAINT),
                                t.section("符合需求的我方宝可梦", self._answers(listing))]

    def _about(self, shown: dict, game: str) -> ft.Control:
        terms = game_terms(game)
        def named(value):
            return terms.get(value, translate(value)) if value else ""
        facts = [named(shown.get("nature")), named(shown.get("ability")), named(shown.get("ball"))]
        if shown.get("held_item"):
            facts.append(f"携带 {named(shown['held_item'])}")
        return ft.Row([
            Sprite(self.app, int(shown.get("species_id") or 0), bool(shown.get("shiny")), size=SIZE).control,
            ft.Column([
                t.text(f"{translate(shown.get('species') or '')} · 等级 {shown.get('level')}" + (" · 异色" if shown.get("shiny") else ""),
                       15, weight=ft.FontWeight.W_600),
                t.text(" · ".join(translate(str(f)) for f in facts if f), 12, t.MUTED),
                t.text("，".join(named(m) for m in shown.get("moves") or []), 12, t.MUTED),
                ft.Row([game_icon(game), t.text(f"当前游戏：{NAMES.get(game, game)}，原始训练家：{shown.get('ot')}", 12, t.SOFT)],
                       spacing=6),
            ], spacing=4, expand=True),
        ], spacing=14, vertical_alignment=ft.CrossAxisAlignment.START)

    def _answers(self, listing: gts.Listing) -> ft.Control:
        held = [e for e in bank.entries() if e.species_id == listing.wants.species and e.legal
                and not listing.wants.refusal(e.species_id, level_of(e))
                and not bank.queued(self.app.settings, e.id)]
        if not held:
            return t.text(f"银行中没有符合 {wanted_text(listing.wants)} 需求且未加入交换队列的合法宝可梦。",
                          12, t.FAINT)
        return ft.Column([ft.Row([
            Sprite(self.app, e.species_id, e.shiny, size=MINI).control,
            ft.Column([t.text(summary_text(e.summary), 12, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                       ft.Row([game_icon(e.game, 16), t.text(NAMES[e.game], 11, t.MUTED)], spacing=4)],
                      spacing=2, expand=True),
            t.button("提出交换", lambda ev, x=e: self._confirm_offer(listing, x), "arrows-horizontal",
                     disabled=self.working),
        ], spacing=8) for e in held], spacing=8)

    def _mine_detail(self, state: dict) -> list[ft.Control]:
        label, color, icon = STATUS[state["status"]]
        controls = [self._about(state["info"], state["game"]), t.badge(label, color, icon)]
        if state["role"] == "listing":
            wants = gts.Wants(**state["wants"])
            controls.append(t.text(f"想要 {wanted_text(wants)}。有效期至 {_when(state['expires'])}；已回应 {len(state['answers'])} 个交换请求。",
                                   12, t.MUTED))
            if state["status"] == "traded":
                controls.append(t.text(f"已与 {state['partner'] or '一位训练家'} 交换，收到的宝可梦已放入银行。",
                                       12, t.SOFT))
            if state["status"] == "active":
                controls.append(t.secondary_button("撤下挂牌", lambda e: self._withdraw(state), "close"))
        else:
            listing = gts.parse_listing(state["listing"])
            if listing:
                controls.append(t.text(f"已提出交换：{translate(listing.pokemon.get('species') or '')}，等级 {listing.pokemon.get('level')}，挂牌方：{listing.trainer or '一位训练家'}。", 12, t.MUTED))
            if state["status"] == "waiting":
                controls.append(t.text("挂牌方下次打开应用时完成交换。若挂牌结束仍未回应，我方宝可梦将返还银行。", 12, t.FAINT))
            if state["why"]:
                controls.append(t.text(translate(state["why"]), 12,
                                       t.AMBER if state["status"] == "returned" else t.SOFT))
        if state["status"] not in ("active", "waiting"):
            controls.append(t.secondary_button("从列表清除", lambda e: self._forget(state), "trash"))
        return controls

    # Actions

    def _work(self, label: str, action, done_text: str) -> None:
        self.working = True
        self._say(label, t.BLUE)

        def work():
            try:
                action()
                problem = ""
            except (OSError, GtsError, pokemon.BuilderError) as error:
                problem = str(error)

            def done():
                self.working = False
                self.render()
                self.control.update()
                self._say(translate(problem) if problem else done_text, t.RED if problem else t.MUTED)
            self.app.ui(done)
        threading.Thread(target=work, daemon=True).start()

    def _confirm_offer(self, listing: gts.Listing, entry: bank.Entry) -> None:
        def go(e):
            self.app.page.pop_dialog()
            self._work("PKHeX 正在检查…", lambda: self.client.offer(listing, entry),
                       "已提出交换。挂牌方应用回应后，可在“我的挂牌与报价”中查看结果。")

        self.app.page.show_dialog(t.dialog(
            title=t.text(f"用 {summary_text(entry.summary).split(' · ')[0]} 提出交换？", 18),
            content=t.text(f"我方宝可梦将暂时移出银行，等待挂牌方应用处理。若这是首个符合需求的交换请求，将收到 {translate(listing.pokemon.get('species') or '')}；否则宝可梦将返还。中继服务器无法强制挂牌方送出宝可梦，交换依赖对方运行真实应用。", 13, t.MUTED, width=400),
            actions=[t.button("取消", lambda e: self.app.page.pop_dialog(), filled=False),
                     t.button("提出交换", go, "arrows-horizontal")]))

    def _withdraw(self, state: dict) -> None:
        self._work("正在撤下挂牌…", lambda: self.client.withdraw(state["id"]),
                   "已撤下挂牌，宝可梦已返还银行。")

    def _forget(self, state: dict) -> None:
        self.client.forget(state["id"])
        self.selected = ""
        self.render()
        self.control.update()

    def _deposit_dialog(self) -> None:
        held = [e for e in bank.entries() if e.legal and not bank.queued(self.app.settings, e.id)]
        if not held:
            self._say("银行中没有未加入交换队列的合法宝可梦。", t.AMBER)
            return
        if not self.species:
            self._say("PKHeX 仍在读取宝可梦种类列表，请稍后再试。", t.AMBER)
            return
        choice = t.dropdown([(e.id, f"{summary_text(e.summary).split(' · ')[0]}, {summary_text(e.summary).split(' · ')[1]} "
                                    f"({NAMES[e.game]})") for e in held], held[0].id, enable_filter=True,
                            editable=True, menu_height=320)
        wanted = t.dropdown(self.species, None, enable_filter=True, editable=True, menu_height=320)
        low = t.field(value="1", mono=True, width=80, digits=True, limit=3)
        high = t.field(value="100", mono=True, width=80, digits=True, limit=3)
        message = t.text("", 12, t.RED)

        def go(e):
            entry = next((x for x in held if x.id == choice.value), None)
            name = dict(self.species).get(wanted.value or "")
            levels = (low.value or "").strip(), (high.value or "").strip()
            if entry is None or not name:
                message.value = "请选择我方宝可梦和想要的宝可梦。"
            elif not all(v.isdigit() for v in levels) or not 1 <= int(levels[0]) <= int(levels[1]) <= 100:
                message.value = "等级范围为 1 到 100，最低等级不能高于最高等级。"
            else:
                self.app.page.pop_dialog()
                wants = gts.Wants(int(wanted.value), name, int(levels[0]), int(levels[1]))
                self._work("PKHeX 正在检查…", lambda: self.client.deposit(entry, wants),
                           "已挂牌，有效期 30 天。应用打开时收到符合需求的请求便会完成交换。")
                return
            message.update()

        self.app.page.show_dialog(t.dialog(
            title=t.text("存入宝可梦", 18),
            content=ft.Column([
                t.labeled_control("我方宝可梦", choice),
                t.labeled_control("想要", wanted),
                ft.Row([t.labeled_control("最低等级", low), t.labeled_control("最高等级", high)], spacing=10),
                t.text("挂牌期间宝可梦暂时移出银行。应用下次打开时将处理首个符合需求的请求并完成交换。可在“我的挂牌与报价”中撤下挂牌，取回宝可梦。", 12, t.FAINT),
                message,
            ], spacing=14, tight=True, width=420),
            actions=[t.button("取消", lambda e: self.app.page.pop_dialog(), filled=False),
                     t.button("存入", go, "upload")]))

    def _say(self, text: str, color: str) -> None:
        self.note.value, self.note.color = text, color
        try:
            self.note.update()
        except RuntimeError:
            pass
