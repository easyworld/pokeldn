import os
import shlex
import threading
import time

import flet as ft

from gui import board
from gui.app import keys_found
from pokeldn.app import bank, command, gift_builder, online, received, runner
from gui import theme as t
from gui.localization import SERVICE, translate, summary as pokemon_summary, summary_text
from gui.advanced_zh_hans import description as advanced_description
from pokeldn.app.catalog import GAMES, Field, Game, Tool
from pokeldn.app.introspect import flags_of
from pokeldn.app.paths import SESSION
from gui.views.pokemon import NAME_LISTS, LinkCodePicker, NamePicker, OfferQueue, PokemonPicker
from gui.views.raid_seed import RaidSeedPicker
from gui.views.rewards import RewardPicker
from gui.views.gifts import GiftBuilder
from gui.views.sprites import MINI, Sprite
from gui.views.widgets import CodeBlock, DigitCode, Log, PathField, open_folder

TOOL_ICONS = {'交换': "arrows-horizontal", '神秘礼物': "gift", '太晶团体战': "diamond-gem"}
EMPTY = "-"   # a dropdown option cannot carry an empty key
ADVANCED_NOTE = ('经过测试的默认值适用于大多数玩家。请仅按指南或问题排查要求修改。此处的设置将覆盖“基本”页的值。')


def tool_icon(tool: Tool):
    if "-raid-" in tool.key:
        return "diamond-gem"
    if tool.key.endswith("-online"):
        return "globe"
    return TOOL_ICONS.get(tool.name.split(" (")[0], "arrows-horizontal")


def tool_role(tool: Tool) -> str:
    """Who looks for whom, said from the console's side."""
    if tool.key.endswith("-host"):
        return '游戏机加入 pokeldn'
    if tool.key.endswith("-join"):
        return "pokeldn 加入游戏机"
    if tool.key.endswith("-online"):
        return "游戏机加入 pokeldn，再由 pokeldn 在线连接交换伙伴"
    return ""


class GamesView:
    def __init__(self, app):
        self.app = app
        self.game: Game = GAMES[0]
        self.tool: Tool = self.game.tools[0]
        self.tab = "basic"
        self.search = ""
        self.sprites: dict[str, Sprite] = {}   # a species field's key -> the sprite on its card
        self.visible = False
        self.tree = ft.ListView(spacing=2, padding=ft.Padding(8, 8, 8, 8), expand=True)
        self.summary = t.text("", 12, t.MUTED, text_align=ft.TextAlign.CENTER)
        self.cards = ft.Column(spacing=t.GAP)
        # The cards start below the toolbar and scroll under its glass.
        self.body = ft.ListView([ft.Container(self.summary, alignment=ft.Alignment.CENTER,
                                              padding=ft.Padding(12, 0, 12, 4)), self.cards],
                                spacing=t.GAP, padding=ft.Padding(0, 62, 0, 24), expand=True)
        self.tabs = ft.Container()
        self.session = SessionPanel(app, self)
        center = ft.Stack([
            t.fade(self.body, 48),
            ft.Container(t.notch(self.tabs,
                                 t.icon_button("book-open", self._open_doc, '阅读此游戏的文档')),
                         top=0, left=0, right=0),
        ], expand=True)
        self.control = ft.Row([
            t.panel(ft.Column([t.panel_header('游戏'), t.fade(self.tree)], spacing=0, expand=True), width=t.SIDEBAR_WIDTH),
            center,
            self.session.control,
        ], spacing=t.GAP, expand=True, vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        self.select(self.game, self.tool, update=False)

    def enter(self, game: str = "", tool: str = "", **_) -> None:
        """`game` and `tool` are catalog keys: the bank opens the trade it queued a Pokemon for."""
        self.visible = True
        chosen = next(((g, x) for g in GAMES for x in g.tools if g.key == game and x.key == tool), None)
        if chosen:   # once the view is back on the page: a list rebuilt off it shows empty
            self.app.ui(lambda: self.select(*chosen))
        self.session.refresh(update=False)
        self.app.check_if_unknown()

    def leave(self) -> None:
        self.visible = False

    # State

    def stored(self) -> dict:
        return self.app.settings.tool_values.setdefault(self.tool.key, {"values": {}, "extra": {}})

    @property
    def values(self) -> dict:
        return self.stored()["values"]

    @property
    def extra(self) -> dict:
        return self.stored()["extra"]

    def set_value(self, field: Field, value, rebuild: bool = False) -> None:
        self.values[field.key] = value
        self.app.settings.save()
        if rebuild:
            self.render_body()
            self.cards.update()
        self.session.refresh()

    def set_raid_context(self, context: dict[str, str]) -> None:
        """The raid finder's choice brings its version, region, progress and crystal with it."""
        self.values.update({
            "--raid-version": context["version"],
            "--raid-map": context["map_name"],
            "--raid-progress": context["progress"],
            "--raid-content": context["content"],
        })
        self.app.settings.save()
        self.render_body()
        self.cards.update()
        self.session.refresh()

    # Rendering

    def select(self, game: Game, tool: Tool, update: bool = True) -> None:
        if tool is not self.tool:
            self.tab, self.search = "basic", ""
        self.game, self.tool = game, tool
        self.summary.value = tool.summary
        self.tabs.content = t.segmented([("basic", '基本', "sliders-horizontal"),
                                          ("all", '高级', "bulletlist")], self.tab, self._tab)
        self.render_tree()
        self.render_body()
        self.session.show(tool)
        if update:
            self.control.update()

    def render_tree(self) -> None:
        rows = []
        for game in GAMES:
            open_ = game is self.game
            rows.append(ft.Container(ft.Row([
                ft.Container(ft.Image(src=f"games/{game.key}.png", width=36, height=36,
                                      fit=ft.BoxFit.CONTAIN, filter_quality=ft.FilterQuality.NONE,
                                      semantics_label=game.name),
                             width=40, height=36, alignment=ft.Alignment.CENTER),
                t.text(game.name, 13, t.TEXT if open_ else t.SOFT, weight=ft.FontWeight.W_600, expand=True),
            ], spacing=10), padding=ft.Padding(8, 6, 8, 6), border_radius=12,
                on_click=lambda e, g=game: self.select(g, g.tools[0])))
            if open_:
                for tool in game.tools:
                    active = tool is self.tool
                    name = t.text(tool.name, 13, t.TEXT if active else (t.FAINT if tool.unavailable else t.MUTED))
                    role = tool_role(tool)
                    rows.append(ft.Container(ft.Row([
                        t.pixel_icon(tool_icon(tool), color=t.BLUE if active else t.FAINT),
                        ft.Column([name, t.text(role, 11, t.FAINT)], spacing=0, expand=True) if role else
                        ft.Container(name, expand=True),
                        t.badge('即将推出', t.FAINT) if tool.unavailable else ft.Container(),
                    ], spacing=10), padding=ft.Padding(24, 7, 8, 7), border_radius=12, tooltip=tool.summary,
                        bgcolor=t.SELECTED if active else None,
                        on_click=lambda e, g=game, x=tool: self.select(g, x)))
                rows.append(ft.Container(height=6))
        self.tree.controls = rows

    def render_body(self) -> None:
        if self.tool.unavailable:
            self.tabs.visible = False
            self.cards.controls = [t.card('暂不可用', None, self.tool.unavailable)]
            return
        self.tabs.visible = True
        self.cards.controls = self.basic_cards() if self.tab == "basic" else self.all_rows()

    def _tab(self, key: str) -> None:
        self.tab = key
        self.render_body()
        self.cards.update()

    def _open_doc(self, e) -> None:
        self.app.navigate("docs", doc=self.tool.doc or self.game.doc)

    # Basic tab

    def basic_cards(self) -> list[ft.Control]:
        cards, groups = [], {}
        for field in self.tool.fields:
            if field.hidden or not command.applies(field, self.tool, self.values):
                continue
            if field.group:
                if field.group not in groups:
                    groups[field.group] = []
                    cards.append(("group", field.group))
                groups[field.group].append(field)
            else:
                cards.append(("field", field))
        out = []
        self.sprites = {}
        for kind, item in cards:
            if kind == "field" and item.kind == "builder":
                out.extend(GiftBuilder(self, item).cards())
            elif kind == "field" and item.kind == "switch":
                out.append(t.card(item.label, None, item.help, trailing=self.input(item)))
            elif kind == "field" and item.kind == "pokemon" and item.queue > 1:
                # "Add a trade" sits under the card, outside it.
                queue = self.offer_queue(item)
                queue.card = t.card(item.label, queue.control, self.description(item))
                out.append(queue.card)
                out.append(queue.footer)
            elif kind == "field":
                out.append(t.card(item.label, self.input(item), self.description(item),
                                  trailing=self.species_sprite([item])))
            else:
                fields = groups[item]
                per_row = 2 if len(fields) > 3 else len(fields)
                sprite = self.species_sprite(fields)
                rows = [ft.Row([
                    t.labeled_control(f.label, self.input(f, grouped=True), expand=True)
                    for f in fields[i:i + per_row]], spacing=10, vertical_alignment=ft.CrossAxisAlignment.START)
                    for i in range(0, len(fields), per_row)]
                if item == "Console" and self.tool.key == "frlg-gift":
                    rows.append(ft.Column([
                        t.text("Game language", 12, t.MUTED),
                        t.text("Detected automatically", 13, t.TEXT),
                        t.text("English · French · German · Italian · Spanish · Japanese", 12, t.MUTED),
                        t.text("After you choose pokeldn in the Friend list, your game reports its language.",
                               12, t.MUTED),
                    ], spacing=4))
                out.append(t.card(item, ft.Column(rows, spacing=10),
                                  " ".join(f.help for f in fields if f.help), trailing=sprite))
        if not self.tool.fields:
            out.append(t.text('无需填写。', 13, t.MUTED))
        return out

    def shiny(self) -> bool:
        return any(bool(command.value_of(f, self.values)) for f in self.tool.fields
                   if f.shiny and command.applies(f, self.tool, self.values))

    def species_sprite(self, fields: list[Field]) -> ft.Control | None:
        field = next((f for f in fields if f.kind == "species"), None)
        if field is None:
            return None
        value = str(command.value_of(field, self.values) or "")
        sprite = Sprite(self.app, int(value) if value.isdigit() else 0, self.shiny(), size=MINI)
        self.sprites[field.key] = sprite
        return sprite.control

    def description(self, field: Field) -> str:
        selected = command.value_of(field, self.values)
        detail = dict(field.choice_help).get(selected, "") if field.kind == "choice" else ""
        return " ".join(part for part in (field.help, detail) if part)

    def offer_queue(self, field: Field) -> OfferQueue:
        return OfferQueue(self.app, self.game.key, command.value_of(field, self.values), field.queue,
                          lambda v: self.set_value(field, v), version=str(self.values.get("--version", "")))

    def input(self, field: Field, grouped: bool = False) -> ft.Control:
        value = command.value_of(field, self.values)
        if field.kind == "switch":
            return t.switch(bool(value), lambda e: self.set_value(field, e.control.value, rebuild=True))
        if field.kind == "choice":
            return t.dropdown([(k or EMPTY, label) for k, label in field.choices], value or EMPTY,
                              on_select=lambda e: self.set_value(
                                  field, "" if e.control.value == EMPTY else e.control.value, rebuild=True))
        if field.kind in NAME_LISTS:
            def picked(v):
                self.set_value(field, v)
                if field.key in self.sprites:
                    self.sprites[field.key].show(int(v) if str(v).isdigit() else 0, self.shiny())
            return NamePicker(self.app, self.game.key, field.kind, value, picked,
                              optional=not field.default).control
        if field.kind == "pokemon" and field.queue > 1:
            return self.offer_queue(field).control
        if field.kind == "pokemon":
            first = command.offers(value)
            return PokemonPicker(self.app, self.game.key, first[0] if first else {},
                                 lambda v: self.set_value(field, v),
                                 version=str(self.values.get("--version", ""))).control
        if field.kind == "rewards":
            return RewardPicker(self.app, self.game.key, value,
                                lambda v: self.set_value(field, v)).control
        if field.kind == "raidseed":
            return RaidSeedPicker(self.app, value,
                                  lambda v: self.set_value(field, v),
                                  context=lambda: {
                                      "version": str(self.values.get("--raid-version", "violet")),
                                      "map_name": str(self.values.get("--raid-map", "paldea")),
                                      "progress": str(self.values.get("--raid-progress", "4star")),
                                      "content": str(self.values.get("--raid-content", "standard")),
                                  }, on_context_change=self.set_raid_context).control
        if field.kind == "linkcode":
            return LinkCodePicker(self.app, value, lambda v: self.set_value(field, v)).control
        if field.kind == "code":
            return DigitCode(value, lambda v: self.set_value(field, v)).control
        if field.kind == "file":
            return PathField(self.app.picker, lambda: os.path.expanduser("~"), value or "", "file", field.exts,
                             lambda v: self.set_value(field, v)).control
        def changed(e):
            if field.limits:
                e.control.error = command.limit_error(field, e.control.value) or None
                e.control.update()
            self.set_value(field, e.control.value)

        box = t.field(value=str(value), mono=field.kind == "number", error_max_lines=2,
                      digits=field.kind == "number",
                      width=180 if field.kind == "number" and not grouped else None,
                      error=command.limit_error(field, value) or None, on_change=changed,
                      expand=field.kind != "number" or grouped)
        return box if grouped or field.kind == "number" else ft.Row([box])

    # All tab

    def all_rows(self) -> list[ft.Control]:
        search = t.field(value=self.search, hint='搜索选项', autofocus=False,
                         prefix_icon=ft.Container(t.pixel_icon("search", color=t.FAINT),
                                                  width=40, alignment=ft.Alignment.CENTER),
                         on_change=self._search)
        self.flag_list = ft.Column(spacing=0)
        self._fill_flags()
        return [t.card('高级选项', ft.Column([search, self.flag_list], spacing=10,
                                                     horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                       ADVANCED_NOTE)]

    def _search(self, e) -> None:
        self.search = e.control.value
        self._fill_flags()
        self.flag_list.update()

    def _fill_flags(self) -> None:
        try:
            flags = flags_of(self.tool.script)
        except Exception as error:
            self.flag_list.controls = [t.text(f'无法读取选项：{error}', 12, t.RED)]
            return
        query = self.search.lower().strip()
        hidden = {f.key: f for f in self.tool.fields if f.hidden}
        if any(f.kind == "builder" for f in self.tool.fields):   # the Gift card sets these
            owned = gift_builder.owned_flags(self.tool)
            flags = [f for f in flags if f.option not in owned]
        rows = []
        # The settings kept off the Basic tab come first.
        for flag in sorted(flags, key=lambda f: f.option not in hidden):
            field = hidden.get(flag.option)
            localized = advanced_description(flag.help, flag.option)
            text = " ".join((flag.option, flag.help, localized, field.label, field.help) if field else
                            (flag.option, flag.help, localized))
            if query and query not in text.lower():
                continue
            rows.append(self.flag_row(flag))
        empty = '没有匹配的选项。' if flags else '此功能没有额外的高级选项。'
        self.flag_list.controls = rows[:200] or [t.text(empty, 12, t.MUTED)]

    def flag_row(self, flag) -> ft.Control:
        # A field kept off the Basic tab is set here, on its own value, default included.
        bound = next((f for f in self.tool.fields if f.hidden and f.key == flag.option), None)
        value = command.value_of(bound, self.values) if bound else self.extra.get(flag.option)

        def store(v):
            if bound:
                self.set_value(bound, v if v not in (None, "") else bound.default)
                return
            if v in (None, "", False):
                self.extra.pop(flag.option, None)
            else:
                self.extra[flag.option] = v
            self.app.settings.save()
            self.session.refresh()
            if flag.kind == "choice":
                self._fill_flags()
                self.flag_list.update()

        if flag.kind == "switch":
            control = t.switch(bool(value), lambda e: store(e.control.value))
        elif flag.kind == "choice":
            control = ft.Container(t.dropdown([(EMPTY, "默认")] + [(c, translate(c)) for c in flag.choices],
                                              value or EMPTY,
                                              on_select=lambda e: store("" if e.control.value == EMPTY else e.control.value)),
                                   width=220)
        else:
            default = "" if flag.default in (None, [], "") else str(flag.default)
            control = ft.Container(t.field(value=value or "", hint=default, mono=True,
                                           on_change=lambda e: store(e.control.value)), width=220)
        detail = ""
        for field in self.tool.fields:
            if field.flag == flag.option and field.choice_help:
                detail = dict(field.choice_help).get(value or flag.default, "")
                break
        lines = ([bound.help] if bound and bound.help else
                 [advanced_description(flag.help, flag.option)])
        if detail:
            lines.append(detail)
        help_ = t.text("\n".join(l for l in lines if l) or '暂无说明。', 12, t.MUTED, max_lines=4,
                       overflow=ft.TextOverflow.ELLIPSIS)

        def toggle(e):
            help_.max_lines = None if help_.max_lines else 4
            help_.update()

        return ft.Container(ft.Row([
            ft.Column([ft.Row([t.text(bound.label, 13, weight=ft.FontWeight.W_600),
                               t.text(flag.option, 12, t.BLUE if value != bound.default else t.MUTED,
                                      font_family=t.MONO)], spacing=8) if bound else
                       t.text(flag.option, 13, t.BLUE if value else t.TEXT, font_family=t.MONO),
                       ft.Container(help_, on_click=toggle, tooltip='显示全部' if len(lines) > 4 else None)],
                      spacing=3, expand=True),
            control,
        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START),
            border=ft.Border(top=ft.BorderSide(1, t.DIVIDER)), padding=ft.Padding(0, 12, 0, 12))


def pokemon_row(app, species: int, shiny: bool, summary: str, tip: str = "") -> ft.Control:
    """A small sprite, then pokeldn.pokemon.summary on two lines: species, level and shininess, then the rest."""
    parts = summary.split(" · ")
    head = 3 if len(parts) > 2 and parts[2] in ("shiny", "异色") else 2
    lines = [t.text(" · ".join(parts[:head]), 13, weight=ft.FontWeight.W_600, max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS)]
    if parts[head:]:
        lines.append(t.text(" · ".join(parts[head:]), 12, t.MUTED, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS))
    return ft.Container(ft.Row([Sprite(app, species, shiny, size=MINI).control,
                                ft.Column(lines, spacing=0, expand=True)],
                               spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        tooltip=tip or None)


class SessionPanel:
    def __init__(self, app, games: GamesView):
        self.app, self.games = app, games
        self.tool: Tool | None = None
        self.stopping = False
        self.pulsing = False
        self.status_dot = ft.Container(width=10, height=10, border_radius=5, bgcolor=t.MUTED,
                                       animate_opacity=ft.Animation(800, ft.AnimationCurve.EASE_IN_OUT),
                                       on_animation_end=self._pulse)
        self.status_label = ft.Semantics(content=self.status_dot, label='空闲')
        self.status = ft.Container(self.status_label, width=24, height=24,
                                   alignment=ft.Alignment.CENTER, tooltip='空闲')
        self.board_line = ft.Container()   # the checklist before Start, or one line once all is set
        self.offering = ft.Container(visible=False)
        self.transfer = ft.Container(visible=False)   # a save backup or restore's progress
        self.partner = ft.Container(visible=False)    # an online trade's partner
        self.partner_state = None                     # pokeldn.app.online.Partner
        self.offered = None                # what the offering card shows, to rebuild it only on a change
        self.traded = 0                    # the run's completed trades, from its `[done] trade N` lines
        self.banked: list[str] = []        # the bank id of each offer the run trades, "" for a built one
        self.running_tool: Tool | None = None
        self.restart = False               # Start on another tool: stop this run, then start that one
        self.received = ft.Container(visible=False)
        self.run = None                    # (process, stamp, game) of the last run started
        self.seen: dict[str, tuple] = {}   # a received file -> (size, mtime, what PKHeX read, or None)
        self.steps = ft.Container()
        self.action = ft.Container()
        command_block = CodeBlock(app)
        self.command_text = command_block.text
        self.command_box = command_block.control
        self.command_box.visible = False
        self.log = Log(app.page, '会话输出显示在此处。')
        tools = ft.Row([
            t.icon_button("code", self._toggle_command, '显示命令'),
            t.icon_button("copy", self._copy_log, '复制日志'),
            t.icon_button("folder", self._open_received, '打开接收文件夹'),
        ], spacing=0)
        self.control = t.panel(ft.Column([
            t.panel_header('会话', self.status),
            # The checklist and the steps scroll; Start stays in view below them.
            ft.Container(t.fade(ft.Column([self.board_line, self.partner, self.offering, self.transfer, self.received,
                                                     self.steps],
                                          spacing=24,
                                          scroll=ft.ScrollMode.AUTO)),
                         padding=ft.Padding(18, 8, 18, 0), expand=3),
            ft.Container(ft.Column([
                self.action,
                ft.Row([t.text('输出', 12, t.MUTED, weight=ft.FontWeight.W_600, expand=True), tools]),
                self.command_box,
            ], spacing=12), padding=ft.Padding(18, 14, 18, 8)),
            ft.Container(self.log.control, padding=ft.Padding(12, 0, 12, 12), expand=2),
        ], spacing=0, expand=True), width=t.SESSION_WIDTH)
        self.set_status('就绪', t.MUTED)
        app.board_listeners.append(lambda: self.refresh() if games.visible else None)

    def set_status(self, label: str, color: str) -> None:
        description = '空闲' if label == '就绪' else label
        running = label.startswith('运行中')
        self.status_dot.bgcolor = color
        self.status.tooltip = description
        self.status_label.label = description
        if running and not self.pulsing:
            self.status_dot.opacity = 0.35
        elif not running:
            self.status_dot.opacity = 1
        self.pulsing = running

    def _pulse(self, e) -> None:
        if self.pulsing:
            self.status_dot.opacity = 1 if self.status_dot.opacity < 1 else 0.35
            self.status_dot.update()

    def show(self, tool: Tool) -> None:
        if tool is not self.tool and not (self.app.process and self.app.process.running):
            self.log.clear()
            self.set_status('就绪', t.MUTED)
            self.seen, self.received.content, self.received.visible = {}, None, False
            self.transfer.content, self.transfer.visible = None, False
            self.partner.content, self.partner.visible, self.partner_state = None, False, None
            self.traded = 0
        self.tool = tool
        self.steps.content = t.section('在游戏机上操作', t.step_list(list(tool.steps)))
        self.refresh(update=False)

    def checklist(self) -> list[tuple[str, str, str, str]]:
        """(state, what, how to fix it, the page that fixes it) for each thing Start needs.
        state is ok, wait, warn (Start still allowed) or block."""
        status = self.app.board_status()
        board_state = ("ok" if status.ready else "wait" if status.state == "checking" else
                       "block" if status.state in ("missing", "choose", "controller") else "warn")
        items = [
            ("ok", '已添加 Switch 密钥', "", "") if keys_found(self.app.settings.keys) else
            ("block", '添加 Switch 密钥', '请在设置中选择 prod.keys。', "settings"),
            (board_state, status.title, "" if status.ready else status.detail, "board"),
        ]
        if missing := command.missing_offer(self.tool, self.games.values):
            missing = translate(missing)
            hint = '选择种类，然后点击“生成”。' if missing.startswith('请先生成') else ""
            items.append(("block", '用于交换的宝可梦', missing + hint, ""))
        items += [("block", '检查选项', translate(problem), "") for problem in
                  command.problems(self.tool, self.games.values)]
        return items

    def render_checklist(self, items) -> ft.Control:
        if all(state == "ok" for state, *_ in items):
            return ft.Row([t.pixel_icon("checkbox-on", color=t.GREEN),
                           t.text('准备就绪', 13, t.TEXT, expand=True),
                           t.secondary_button('开发板', lambda e: self.app.navigate("board"), "cpu")], spacing=8)
        looks = {"ok": ("checkbox-on", t.GREEN), "wait": ("refresh", t.BLUE),
                 "warn": ("warning-diamond", t.AMBER), "block": ("warning-diamond", t.RED)}
        labels = {"settings": '设置', "board": '开发板'}
        rows = []
        for state, what, how, page in items:
            icon, color = looks[state]
            rows.append(ft.Row([
                ft.Container(t.pixel_icon(icon, color=color), padding=ft.Padding(0, 1, 0, 0)),
                ft.Column([t.text(what, 13, weight=ft.FontWeight.W_600)] +
                          ([t.text(how, 12, t.MUTED)] if how else []), spacing=1, expand=True),
                t.secondary_button(labels[page], lambda e, k=page: self.app.navigate(k))
                if page and state != "ok" else ft.Container(),
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.START))
        return t.section('开始前', ft.Column(rows, spacing=10))

    def refresh(self, update: bool = True) -> None:
        tool, s = self.tool, self.app.settings
        running = bool(self.app.process and self.app.process.running)
        session = running and self.run is not None and self.run[0] is self.app.process
        here = session and self.running_tool is tool
        items = self.checklist()
        self.board_line.content = None if here else self.render_checklist(items)
        blocked = any(state == "block" for state, *_ in items)
        if here:
            action = t.button('停止', self._stop, "stop", t.RED, expand=True)
        elif session:
            action = t.button(f'停止 {self.running_tool.name} 并开始', self._start, "play", expand=True,
                              disabled=self.restart or blocked or bool(tool.unavailable))
        else:
            action = t.button('开始', self._start, "play", expand=True,
                              disabled=self.app.busy or blocked or bool(tool.unavailable))
        self.action.content = ft.Row([action])
        self.render_offering()
        try:
            self.command_text.value = shlex.join([tool.script, *command.build(
                tool, self.games.values, self.games.extra, s, stamp="STAMP")])
        except OSError as error:
            self.command_text.value = f"{error}"
        if update:
            self.control.update()

    def offered_entries(self) -> list[dict]:
        """The queued offers in the order the launcher trades them."""
        return [entry for field in self.tool.fields
                if field.kind == "pokemon" and command.applies(field, self.tool, self.games.values)
                for entry in command.offers(command.value_of(field, self.games.values))[:field.queue]
                if entry.get("file")]

    def render_offering(self) -> None:
        entries = self.offered_entries()
        shown = [(int(e.get("species") or 0), bool(e.get("shiny")), e.get("summary", "")) for e in entries]
        if (shown, self.traded) == self.offered:
            return
        self.offered = (shown, self.traded)
        self.offering.visible = bool(shown)
        done = t.text(f'{self.traded} 次交换已完成', 12, t.GREEN) if self.traded else None
        if not shown:
            self.offering.content = None
        elif len(shown) == 1:
            species, shiny, summary = shown[0]
            self.offering.content = t.section('正在提供', pokemon_row(self.app, species, shiny, summary_text(summary)),
                                              trailing=done)
        else:
            tiles = []
            for n, (species, shiny, summary) in enumerate(shown, start=1):
                sprite = Sprite(self.app, species, shiny, size=MINI)
                traded = n <= self.traded
                sprite.frame.tooltip = f"交换 {n}{('（已完成）' if traded else '')}: {summary}"
                tiles.append(ft.Stack([sprite.control, ft.Container(
                    t.pixel_icon("checkbox-on", color=t.GREEN), right=0, bottom=0, visible=traded)]))
            progress = (f'{min(self.traded, len(shown))} / {len(shown)} 次交换已完成' if self.traded
                        else f'{len(shown)} 次交换，按顺序进行')
            self.offering.content = t.section('正在提供', ft.Row(tiles, spacing=6, run_spacing=6, wrap=True),
                                              trailing=t.text(progress, 12, t.GREEN if self.traded else t.MUTED))

    def show_transfer(self, what: str, done: int, total: int) -> None:
        unit = "KB" if what == "backup" else "parts"
        title = "Backing up the save" if what == "backup" else "Putting the save on the console"
        self.transfer.visible = True
        self.transfer.content = t.section(title, ft.Column([
            ft.ProgressBar(value=done / total if total else 0, color=t.BLUE, bgcolor=t.BORDER,
                           bar_height=6, border_radius=3),
            t.text(f"{done} of {total} {unit}. Keep the Switch near the board.", 12, t.MUTED)], spacing=6))
        self.transfer.update()

    def show_partner(self, partner) -> None:
        """Who the online trade meets, what they offer and whether they confirmed."""
        self.partner_state = partner
        looks = {"looking": ("refresh", t.BLUE, "正在连接中继"),
                 "waiting": ("refresh", t.BLUE, "正在寻找交换伙伴"),
                 "paired": ("user", t.GREEN, f"正在与 {partner.name} 交换"),
                 "lost": ("warning-diamond", t.RED, f"{partner.name or '交换伙伴'} 已离开")}
        icon, color, title = looks[partner.state]
        if partner.state in ("looking", "waiting"):
            code = partner.code.removeprefix("code ")
            detail = ("可与此游戏中未设置密码的在线玩家匹配。"
                      if partner.code == "no code" else f"交换伙伴需要输入相同密码：{code}。")
        elif partner.state == "lost":
            detail = "请在游戏机上退出交换，然后重新启动以寻找交换伙伴。"
        elif partner.offer:
            detail = "对方已确认。请在游戏机上确认以开始交换。" if partner.confirmed else \
                "正在等待对方确认。"
        else:
            detail = "请在游戏机上提出要交换的宝可梦；对方选择后，其宝可梦将显示在此处。"
        rows = [ft.Row([t.pixel_icon(icon, color=color),
                        ft.Column([t.text(title, 13, weight=ft.FontWeight.W_600),
                                   t.text(detail, 12, t.MUTED)], spacing=1, expand=True)],
                       spacing=8, vertical_alignment=ft.CrossAxisAlignment.START)]
        if partner.offer and partner.state == "paired":
            species, shiny, summary = partner.offer
            rows.append(pokemon_row(self.app, species, shiny, summary_text(summary)))
            if partner.flag:
                rows.append(t.text(f"PKHeX 检查结果：{translate(partner.flag)}", 12, t.AMBER))
        if partner.note:
            rows.append(t.text(translate(partner.note), 12, t.AMBER))
        trailing = t.text(f"已交换 {partner.trades} 次", 12, t.GREEN) if partner.trades else None
        self.partner.content = t.section("交换伙伴", ft.Column(rows, spacing=10), trailing=trailing)
        self.partner.visible = True
        self.partner.update()

    def scan_received(self, run: tuple) -> None:
        """Read each Pokemon file the run has saved so far; a file still growing is read again."""
        process, stamp, game = run
        changed = False
        for path in received.session_files(self.app.settings.received, stamp):
            try:
                size, mtime = os.path.getsize(path), os.path.getmtime(path)
            except OSError:
                continue
            if path in self.seen and self.seen[path][:2] == (size, mtime):
                continue
            try:
                info = SERVICE.check(game, path)
            except Exception:
                info = None
            if self.run is not run:
                return
            self.seen[path] = (size, mtime, info)
            changed = True
            if info is not None:
                try:
                    bank.deposit(game, path, info)
                except OSError as error:
                    self.app.ui(lambda m=f"[app] Not banked: {error}": self.log.add(m))
        if changed:
            self.app.ui(lambda: self.render_received(process))

    def render_received(self, process) -> None:
        if self.run is None or self.run[0] is not process:
            return
        rows = []
        for path, (_, _, info) in list(self.seen.items()):
            name = os.path.basename(path)
            if info is None:
                rows.append(pokemon_row(self.app, 0, False, f'PKHeX 无法读取 · {name}', path))
            else:
                rows.append(pokemon_row(self.app, int(info.get("species_id") or 0), bool(info.get("shiny")),
                                        pokemon_summary(info), path))
        self.received.visible = True
        self.received.content = t.section('已接收', ft.Column(rows, spacing=8),
                                       trailing=t.icon_button("folder", self._open_received,
                                                              '打开接收文件夹'))
        self.received.update()

    def _toggle_command(self, e) -> None:
        self.command_box.visible = not self.command_box.visible
        self.command_box.update()

    async def _copy_log(self, e) -> None:
        await self.app.copy(self.log.text())

    def _open_received(self, e) -> None:
        open_folder(os.path.expanduser(self.app.settings.received))

    def _start(self, e) -> None:
        tool, s = self.tool, self.app.settings
        process = self.app.process
        if (process and process.running and self.run is not None and self.run[0] is process
                and self.running_tool is not tool):
            # one board, one session: the running one leaves the network first
            self.restart = True
            self._stop(e)
            self.refresh()
            return
        if self.app.busy:
            return
        port = self.app.radio_port()
        problems = [p for p in (
            "" if port else '未找到开发板。请连接开发板，或在“开发板”页选择一个。',
            "" if os.path.isfile(os.path.expanduser(s.keys)) else '请在设置中选择自己的 prod.keys。',
            command.missing_offer(tool, self.games.values), *command.problems(tool, self.games.values)) if p]
        self.log.clear()
        if problems:
            for p in problems:
                self.log.add(f"[app] {translate(p)}")
            self.set_status('尚未开始', t.RED)
            self.refresh()
            return
        try:
            command.prepare(tool, self.games.values)
        except (OSError, ValueError) as error:
            self.log.add(f"[app] {error}")
            self.set_status('尚未开始', t.RED)
            self.refresh()
            return
        stamp = time.strftime("%Y%m%d-%H%M%S")
        args = command.build(tool, self.games.values, self.games.extra, s, stamp)
        for folder in (SESSION / "captures", os.path.expanduser(s.received)):
            os.makedirs(folder, exist_ok=True)
        trace = f"captures/{tool.key}-{stamp}_esp32.trace" if s.board_trace else None
        self.log.add(f"[app] {tool.name} · {self.games.game.name} · radio {port}")
        self.seen, self.received.content, self.received.visible = {}, None, False
        self.transfer.content, self.transfer.visible = None, False
        self.partner.content, self.partner.visible, self.partner_state = None, False, None
        self.traded = 0
        self.banked = [entry.get("bank", "") for entry in self.offered_entries()]
        self.stopping = False
        self.app.process_label = tool.name
        self.running_tool = tool
        self.app.process = runner.Process(["--run", tool.script, *args], str(SESSION),
                                          runner.base_env(s, port, trace), self._line, self._exited)
        self.run = (self.app.process, stamp, self.games.game.key)
        threading.Thread(target=self._tick, daemon=True).start()
        self.refresh()

    def _line(self, line: str) -> None:
        self.log.add(line)
        if progress := received.save_progress(line):
            self.app.ui(lambda: self.show_transfer(*progress))
        partner = online.update(self.partner_state, line)
        if partner is not self.partner_state:
            self.partner_state = partner
            self.app.ui(lambda p=partner: self.show_partner(p) if self.partner_state is p else None)
        n = received.trades_done(line)
        if n is not None and n > self.traded:
            def mark():
                # A banked Pokemon leaves the bank once its trade completes.
                for gone in self.banked[self.traded:n]:
                    if gone:
                        bank.remove(gone)
                self.traded = n
                self.render_offering()
                self.offering.update()
            self.app.ui(mark)

    def _tick(self) -> None:
        run = self.run
        process = run[0]
        while process.running:
            elapsed = int(time.monotonic() - process.started)
            self.app.ui(lambda e=elapsed: (self.set_status(f'正在运行 {e // 60:02d}:{e % 60:02d}', t.BLUE),
                                           self.status.update())
                        if self.app.process is process and process.running else None)
            self.scan_received(run)
            time.sleep(1)
        self.scan_received(run)   # a launcher may write its last file as it closes

    def _stop(self, e) -> None:
        self.stopping = True
        self.log.add("[app] Stopping: the entry point leaves the network and closes the board.")
        self.app.process.stop()

    def _exited(self, code: int) -> None:
        def done():
            if self.stopping:
                self.set_status('已停止', t.MUTED)
            elif code == 0:
                self.set_status('已完成', t.GREEN)
            else:
                self.set_status(f'失败（{code})', t.RED)
            self.log.add(f"[app] Exited with code {code}.")
            bank.prune(self.app.settings)     # the traded ones leave the queue too
            if self.games.visible and self.games.tool is self.running_tool:
                self.games.render_body()      # a backup has joined the save library
                self.games.cards.update()
            if self.restart:
                self.restart = False
                self._start(None)
                return
            self.refresh()
        self.app.ui(done)
