"""The gift builder shared by the Mystery Gift tools: a preset, a gift built in a form, or an opened
file, then a summary of what the console gets. Each game's form lives in its builder module."""

import asyncio
import copy
import os
import threading

import flet as ft

from gui import drop, theme as t
from gui.localization import SERVICE, translate, gift_description, event_text
from gui.views.pokemon import NamePicker
from gui.views.widgets import PathField
from pokeldn import gifts, pokemon
from pokeldn.app import command, gift_builder, gift_files
from pokeldn.frlg.gift import builder as frlg
from pokeldn.frlg.rom import custom_code
from pokeldn.swsh import gift_builder as swsh

def species_frlg():
    """Use the cartridge's internal IDs with PKHeX Chinese names."""
    return SERVICE.names("frlg", "species3")


def _number(value, default=0):
    try:
        return int(str(value).strip() or default, 0)
    except ValueError:
        return default


def _chips(choices, value, on_change) -> ft.Row:
    """A row of pickable capsules, one per (value, label)."""
    row = ft.Row(spacing=6, wrap=True, run_spacing=6)

    def render(selected):
        row.controls = [ft.Container(
            t.text(translate(label), 12, t.TEXT if key == selected else t.MUTED, weight=ft.FontWeight.W_600),
            padding=ft.Padding(12, 6, 12, 6), border_radius=15,
            border=ft.Border.all(1, t.BLUE if key == selected else t.BORDER),
            bgcolor=t.SELECTED if key == selected else None, on_click=lambda e, k=key: pick(k))
            for key, label in choices]

    def pick(key):
        render(key)
        row.update()
        on_change(key)

    render(value)
    return row


class GiftBuilder:
    def __init__(self, games, field):
        self.games, self.field = games, field
        self.app, self.tool = games.app, games.tool
        self.game = gift_builder.GAMES[self.tool.key]
        self.module = gift_builder.module(self.game)
        self.value = gift_builder.normalized(self.game, command.value_of(field, games.values))
        self.when = t.text("", 12, t.MUTED)
        self.effects = ft.Column(spacing=4)
        self.status = t.text("", 12, t.MUTED)
        self.save_button = t.secondary_button('保存礼物文件', self._save, "download")

    # State

    @property
    def state(self) -> dict:
        return self.value["build"]

    def commit(self, rebuild=False) -> None:
        self.games.set_value(self.field, self.value, rebuild=rebuild)
        if not rebuild:
            self.show_summary(update=True)

    def edit(self, key, value, rebuild=False, target=None) -> None:
        (self.state if target is None else target)[key] = value
        self.commit(rebuild)

    # Cards

    def cards(self) -> list[ft.Control]:
        mode = self.value["mode"]
        modes = t.segmented(gift_builder.modes(self.game), mode, self._mode)
        body = {"preset": self.presets, "event": self.events, "build": self.editor, "file": self.file}[mode]()
        self.show_summary()
        actions = [self.save_button]
        if mode == "preset" and self.module.PRESET[self.value["preset"]].state is not None:
            actions.insert(0, t.secondary_button('自定义', self._customize, "sliders-horizontal"))
        summary = ft.Column([self.when, self.effects, self.status,
                             ft.Row(actions, alignment=ft.MainAxisAlignment.END)], spacing=10)
        gift = drop.target(t.card('礼物', ft.Column([modes, body], spacing=14)), self._dropped)
        return [gift, t.card('发送前', summary)]

    def exts(self) -> tuple[str, ...]:
        return ("pokegift", "wc8") if self.game == "swsh" else ("pokegift", "wc3")

    def _dropped(self, paths: list[str]) -> None:
        """A gift file dropped anywhere on the card opens it."""
        path = next((p for p in paths if drop.suffix(p) in self.exts()), "")
        if path:
            self.value["mode"], self.value["file"] = "file", path
            self.commit(rebuild=True)

    def _mode(self, key) -> None:
        self.value["mode"] = key
        self.commit(rebuild=True)

    def presets(self) -> ft.Control:
        groups: dict[str, list] = {}
        for preset in self.module.PRESETS:
            groups.setdefault(preset.group, []).append(preset)
        selected = self.module.PRESET[self.value["preset"]]
        sections = []
        for group, items in groups.items():
            tiles, body = [], []
            for preset in items:
                if not hasattr(preset, "members"):
                    tiles.append(self._tile(preset.label, preset.summary, preset is selected,
                                            lambda e, k=preset.key: self._pick(k)))
                    continue
                on = preset.settings(self.value["options"].get(preset.key))["on"] if preset is selected else []
                tiles += [self._tile(b.label, b.summary, b.key in on, lambda e, p=preset, k=b.key: self._toggle(p, k),
                                     settings=bool(b.options)) for b in preset.members]
                if on:
                    body.append(self.boost_settings(preset))
            body.insert(0, ft.ResponsiveRow(tiles, spacing=6, run_spacing=6))
            intro = getattr(self.module, "GROUP_INTROS", {}).get(group, "")
            if intro:
                body.insert(0, t.text(translate(intro), 12, t.MUTED))
            sections.append(t.section(translate(group), ft.Column(body, spacing=10)))
        return ft.Column(sections, spacing=14)

    def _tile(self, label, summary, active, on_click, settings=False) -> ft.Control:
        """The preset's name and full description, including any steps needed to use it."""
        head = [t.text(translate(label), 13, weight=ft.FontWeight.W_600, expand=True)]
        if settings:
            head.append(t.pixel_icon("sliders-horizontal", color=t.BLUE if active else t.FAINT,
                                     tooltip='可设置'))
        return ft.Container(ft.Row([
            t.pixel_icon("checkbox-on" if active else "checkbox", color=t.BLUE if active else t.FAINT),
            ft.Column([ft.Row(head, spacing=6),
                       t.text(event_text(summary), 12, t.MUTED)],
                      spacing=1, expand=True),
        ], spacing=10), padding=ft.Padding(10, 8, 10, 8), border_radius=10, col={"xs": 12, "md": 6},
            tooltip=translate(summary), border=ft.Border.all(1, t.BLUE if active else t.BORDER),
            bgcolor=t.SELECTED if active else None, on_click=on_click)

    def _toggle(self, preset, key) -> None:
        """Tick or untick a boost; the first tick from another gift starts the set with that one."""
        chosen = preset.settings(self.value["options"].get(preset.key))
        if self.value["preset"] != preset.key:
            chosen["on"] = [key]
        elif key in chosen["on"]:
            chosen["on"].remove(key)
        else:
            chosen["on"].append(key)
        self.value["preset"], self.value["options"][preset.key] = preset.key, chosen
        self.commit(rebuild=True)

    def boost_settings(self, preset) -> ft.Control:
        """A panel per ticked boost with settings, then the save switch and the room they take."""
        chosen = preset.settings(self.value["options"].get(preset.key))
        self.value["options"][preset.key] = chosen
        panels = []
        for boost in preset.members:
            if boost.key not in chosen["on"] or not boost.options:
                continue
            mine = chosen[boost.key]
            rows = []
            for option in boost.options:
                if not option.choices:
                    rows.append(self.switch_row(option.label, option.key, option.help, mine))
                elif all(len(label) <= 24 for _, label in option.choices):
                    rows.append(t.labeled_control(translate(option.label), _chips(
                        option.choices, mine[option.key], lambda v, k=option.key, m=mine: self.edit(k, v, target=m))))
                else:
                    rows.append(t.labeled_control(translate(option.label), t.dropdown(
                        [(key, translate(label)) for key, label in option.choices], mine[option.key],
                        on_select=lambda e, k=option.key, m=mine: self.edit(k, e.control.value, target=m))))
            panels.append(ft.Container(ft.Column([t.text(translate(boost.label), 13, weight=ft.FontWeight.W_600), *rows],
                                                 spacing=12),
                                       padding=14, border_radius=10, border=ft.Border.all(1, t.BORDER)))
        used, room = preset.size(chosen), frlg.RESIDENT_AREA
        try:
            too_large = preset.built(chosen)[2]
        except ValueError:
            too_large = False
        keep = (t.text(translate('这些增强功能始终保存在游戏存档中。' + frlg.MOM_STEPS), 12, t.MUTED)
                if too_large or "hook-follower" in chosen["on"]
                else self.switch_row(frlg.KEEP.label, "keep", frlg.KEEP.help, chosen))
        meter = ft.Column([
            ft.Row([t.text('游戏机可用空间', 12, t.MUTED, expand=True),
                    t.text(f'{used} / {room} 字节', 12, t.RED if used > room else t.MUTED)]),
            ft.ProgressBar(value=min(used / room, 1), color=t.RED if used > room else t.BLUE,
                           bgcolor=t.BORDER, bar_height=4, border_radius=2)], spacing=4)
        common = ft.Container(ft.Column([keep, meter, t.text(
            '所选增强功能同时运行。发送新的组合会替换正在运行的增强功能。',
            12, t.MUTED)],
            spacing=12), padding=14, border_radius=10, border=ft.Border.all(1, t.BORDER))
        return ft.Column([*panels, common], spacing=10)

    def _pick(self, key) -> None:
        self.value["preset"] = key
        self.commit(rebuild=True)

    # Official events

    def events(self) -> ft.Control:
        """Every official card the game's builder ships, filtered by a search and a group."""
        cards = self.module.OFFICIAL.load()
        tiles = ft.ResponsiveRow(spacing=6, run_spacing=6)
        search = t.field(hint='搜索：皮卡丘、大师球、异色…', value=self.value.get("event_search", ""))
        group = {"value": self.value.get("event_group", "")}

        def render(update=True):
            words = search.value.casefold().split()
            shown = [c for c in cards if (not group["value"] or c["group"] == group["value"])
                     and all(w in f"{c['label']} {c['group']} {c['summary']} {event_text(c['label'])} {event_text(c['summary'])}".casefold() for w in words)]
            tiles.controls = [self._tile(event_text(c["label"]), c["summary"], c["key"] == self.value["event"],
                                         lambda e, k=c["key"]: self._event(k)) for c in shown]
            count.value = f'{len(shown)} / {len(cards)} 张卡片'
            if update:
                tiles.update()
                count.update()

        def filtered(key, value):
            self.value[key] = value
            if key == "event_group":
                group["value"] = value
            render()

        search.on_change = lambda e: filtered("event_search", search.value)
        count = t.text("", 12, t.MUTED)
        render(update=False)
        groups = _chips([("", '全部')] + [(g, g) for g in self.module.OFFICIAL.GROUPS], group["value"],
                        lambda k: filtered("event_group", k))
        intro = t.text('来自 projectpokemon EventsGallery 存档的真实活动卡片，均已通过游戏自身的卡片检查。', 12, t.MUTED)
        listing = ft.Container(ft.Column([tiles], scroll=ft.ScrollMode.AUTO), height=440)
        return ft.Column([intro, search, groups, count, listing], spacing=10)

    def _event(self, key) -> None:
        self.value["event"] = key
        self.commit(rebuild=True)

    def _customize(self, e) -> None:
        self.value["build"] = copy.deepcopy(self.module.PRESET[self.value["preset"]].state)
        self.value["mode"] = "build"
        self.commit(rebuild=True)

    def file(self) -> ft.Control:
        path = PathField(self.app.picker, lambda: os.path.expanduser("~"), self.value["file"], "file",
                         self.exts(), self._file, single_line=True, droppable=False)
        controls = [t.text('他人分享的 .pokegift，或一个 ' + ('剑／盾 .wc8' if self.game == "swsh"
                                                                  else ".wc3") + ' 神奇卡片。', 12, t.MUTED),
                    path.control]
        if self.game == "frlg":
            icon = NamePicker(self.app, self.game, "species", str(self.value.get("icon") or ""),
                              self._icon, optional=True, names=species_frlg)
            controls.append(t.labeled_control('卡片图标', icon.control))
            controls.append(t.text('留空保留文件的原有图标。', 12, t.MUTED))
        return ft.Column(controls, spacing=8)

    def _icon(self, value) -> None:
        number = _number(value)
        self.value["icon"] = number if number else None
        self.commit()

    def _file(self, path) -> None:
        self.value["file"] = path
        self.commit()

    # Build your own

    def editor(self) -> ft.Control:
        kind = self.state.get("kind")
        kinds = t.segmented([(k, translate(label), icon) for k, label, icon in self.module.KINDS], kind, lambda k: self.edit("kind", k, rebuild=True))
        form = getattr(self, f"{self.game}_{kind}")()
        return ft.Column([kinds, form], spacing=14)

    def text_field(self, label, key, target=None, width=None, **kwargs) -> ft.Control:
        target = self.state if target is None else target
        box = t.field(value=str(target.get(key, "")), on_change=lambda e: self.edit(key, e.control.value,
                                                                                     target=target),
                      expand=width is None, width=width, **kwargs)
        return t.labeled_control(translate(label), box, expand=width is None)

    def number_field(self, label, key, target=None, width=96) -> ft.Control:
        target = self.state if target is None else target
        box = t.field(value=str(target.get(key, "")), mono=True, width=width,
                      on_change=lambda e: self.edit(key, _number(e.control.value), target=target))
        return t.labeled_control(translate(label), box)

    def name_field(self, label, kind, key, target=None, optional=True) -> ft.Control:
        target = self.state if target is None else target
        names = species_frlg if self.game == "frlg" and kind == "species" else None
        picker = NamePicker(self.app, self.game, kind, str(target.get(key) or ""),
                            lambda v: self.edit(key, _number(v), target=target), optional=optional, names=names)
        return t.labeled_control(translate(label), picker.control, expand=True)

    def switch_row(self, label, key, help_, target=None) -> ft.Control:
        target = self.state if target is None else target
        return ft.Row([ft.Column([t.text(translate(label), 13), t.text(translate(help_), 12, t.MUTED)], spacing=1, expand=True),
                       t.switch(bool(target.get(key)), lambda e: self.edit(key, e.control.value, target=target))])

    def moves(self, target) -> ft.Control:
        target.setdefault("moves", [0, 0, 0, 0])

        def picker(n):
            def changed(v):
                target["moves"][n] = _number(v)
                self.commit()
            return t.labeled_control(f'招式 {n + 1}', NamePicker(
                self.app, self.game, "move", str(target["moves"][n] or ""), changed).control, expand=True)
        return ft.Column([ft.Row([picker(0), picker(1)], spacing=10), ft.Row([picker(2), picker(3)], spacing=10)],
                         spacing=10)

    # FireRed / LeafGreen

    def frlg_card(self) -> ft.Control:
        card = self.state["card"]
        body = card.setdefault("body", ["", "", "", ""])

        def line(n):
            def changed(e):
                body[n] = e.control.value
                self.commit()
            return t.field(value=body[n], hint=f'行 {n + 1}', on_change=changed)
        giver = t.dropdown([(key, f"{translate(who)}, {translate(where)}") for key, who, where, *_ in frlg.GIVERS],
                           self.state.get("giver", "deliveryman"),
                           on_select=lambda e: self.edit("giver", e.control.value, rebuild=True))
        card_form = ft.Column([
            ft.Row([self.text_field('标题', "title", card), self.text_field('副标题', "subtitle", card)],
                   spacing=10),
            t.labeled_control('卡片文字', ft.Column([line(n) for n in range(4)], spacing=6,
                                                            horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                              horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            ft.Row([self.name_field('图标', "species", "icon", card, optional=False),
                    self.number_field('卡片 ID', "flag_id", card)], spacing=10),
            self.switch_row('允许重复领取', "repeatable", '否则每个存档只能领取一次。', card),
            self.switch_row('允许玩家分享', "shareable", '神秘礼物 → 神奇卡片 → 发送。', card),
        ], spacing=10)
        return ft.Column([
            t.section('卡片', card_form),
            t.section('赠送者', giver),
            t.section('效果', self.frlg_steps()),
        ], spacing=18)

    def frlg_steps(self) -> ft.Control:
        steps = self.state["steps"]
        rows = [self.frlg_step(n, step) for n, step in enumerate(steps)]
        adders = ft.Row([t.secondary_button(translate(label), lambda e, k=key: self._add_step(k), "plus")
                         for key, label in frlg.STEPS], spacing=6, wrap=True, run_spacing=6)
        return ft.Column([*rows, adders], spacing=10)

    def frlg_step(self, n, step) -> ft.Control:
        kind = step["type"]
        label = translate(dict(frlg.STEPS)[kind])
        if kind in ("pokemon", "battle"):
            fields = [ft.Row([self.name_field('种类', "species", "species", step, optional=False),
                              self.number_field('等级', "level", step, 72),
                              self.name_field('携带道具', "item", "item", step)], spacing=10)]
            if kind == "pokemon":
                fields.append(self.moves(step))
        elif kind == "egg":
            fields = [self.name_field('种类', "species", "species", step, optional=False)]
        elif kind == "item":
            fields = [ft.Row([self.name_field('道具', "item", "item", step, optional=False),
                              self.number_field('数量', "quantity", step, 72)], spacing=10)]
        else:
            fields = [self.text_field('消息', "text", step, multiline=True, min_lines=2, max_lines=4,
                                      hint='{PLAYER} 代表玩家姓名。每个文本框可容纳两行。')]
        tools = ft.Row([t.icon_button("chevron-up", lambda e: self._move_step(n, -1), '前移', disabled=n == 0),
                        t.icon_button("chevron-down", lambda e: self._move_step(n, 1), '后移',
                                      disabled=n == len(self.state["steps"]) - 1),
                        t.icon_button("close", lambda e: self._remove_step(n), '移除')], spacing=0)
        head = ft.Row([t.text(f"{n + 1}. {label}", 12, t.SOFT, weight=ft.FontWeight.W_600, expand=True), tools],
                      vertical_alignment=ft.CrossAxisAlignment.CENTER)
        return ft.Container(ft.Column([head, *fields], spacing=8), padding=12, border_radius=10,
                            border=ft.Border.all(1, t.BORDER))

    def _add_step(self, kind) -> None:
        defaults = {"pokemon": {"species": 25, "level": 5, "item": 0, "moves": [0, 0, 0, 0]},
                    "battle": {"species": 25, "level": 5, "item": 0}, "egg": {"species": 25},
                    "item": {"item": 1, "quantity": 1}, "message": {"text": "Here you go!"}}
        self.state["steps"].append({"type": kind, **defaults[kind]})
        self.commit(rebuild=True)

    def _move_step(self, n, delta) -> None:
        steps = self.state["steps"]
        steps[n], steps[n + delta] = steps[n + delta], steps[n]
        self.commit(rebuild=True)

    def _remove_step(self, n) -> None:
        del self.state["steps"][n]
        self.commit(rebuild=True)

    def frlg_news(self) -> ft.Control:
        news = self.state["news"]

        def lines(e):
            news["lines"] = e.control.value.split("\n")[:10]
            self.commit()
        return ft.Column([
            ft.Row([self.text_field('标题', "title", news), self.number_field('新闻 ID', "id", news)], spacing=10),
            t.labeled_control('文字（最多十行）', t.field(value="\n".join(news.get("lines", ())),
                                                               multiline=True, min_lines=4, max_lines=10,
                                                               on_change=lines)),
            t.text('游戏机仅保存与现有内容不同的神奇新闻。若要再次发送相同文字，请更改 ID。', 12, t.MUTED),
        ], spacing=10)

    def frlg_code(self) -> ft.Control:
        code = self.state["code"]
        self.check_line = t.text("", 12, t.MUTED)
        self.hex_view = t.text("", 11, t.SOFT, font_family=t.MONO, selectable=True)
        source = t.field(value=code.get("source", ""), mono=True, multiline=True, min_lines=10, max_lines=24,
                         on_change=lambda e: code.__setitem__("source", e.control.value),
                         on_blur=lambda e: self.commit())
        binary = PathField(self.app.picker, lambda: os.path.expanduser("~"), code.get("binary", ""), "file",
                           ("bin",), lambda v: self.edit("binary", v, target=code), single_line=True)
        return ft.Column([
            t.text('接收时，游戏机会逐帧运行 ARM 代码，直到返回 1。错误或死循环会使神秘礼物菜单卡住，因此发送前需要离线检查。', 12, t.MUTED),
            t.labeled_control('汇编代码', source, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            self._toolchain_status(),
            t.labeled_control('或使用已编译的 .bin（替代汇编代码）', binary.control),
            ft.Row([t.labeled_control('目标版本', t.dropdown(
                        [("any", '任意卡带')] + [(code, translate(label)) for code, label in frlg.CARTRIDGES.items()], code.get("build") or "any",
                        on_select=lambda e: self.edit("build", "" if e.control.value == "any" else e.control.value,
                                                      target=code)), expand=True),
                    self.text_field('预期结果', "expect", code, width=140, hint="any"),
                    self.text_field('返回字节', "dump_size", code, width=140, hint="4")], spacing=10),
            ft.Row([t.secondary_button('离线检查', self._check, "play"), ft.Container(self.check_line,
                                                                                            expand=True)]),
            self.hex_view,
        ], spacing=10)

    def _toolchain_status(self) -> ft.Control:
        if custom_code.toolchain():
            return t.text('使用此电脑上的 GNU Arm 工具链编译。', 12, t.MUTED)
        command, page = custom_code.install_hint()
        run = self.app.page.run_task
        if command:
            how = ft.Row([ft.Container(t.text(command, 12, t.TEXT, font_family=t.MONO, selectable=True),
                                       expand=True),
                          t.icon_button("copy", lambda e: run(self.app.copy, command), '复制')],
                         vertical_alignment=ft.CrossAxisAlignment.CENTER)
            steps = '将此命令粘贴到终端执行，然后重新检查'
        else:
            how, steps = None, '从 Arm 官网下载，然后重新检查'
        actions = ft.Row([t.secondary_button('重新检查', lambda e: self.commit(rebuild=True), "refresh"),
                          t.link_button('自制程序' if page == "https://brew.sh" else 'Arm 下载页面',
                                        lambda e: run(self.app.open_url, page))], spacing=8)
        return t.surface(ft.Column([
            t.text(f'输入汇编代码需要免费的 GNU Arm 汇编器。安装一次即可：{steps}。使用已编译的 .bin 无需安装。', 12, t.AMBER),
            *([how] if how else []), actions], spacing=8), padding=12)

    def _check(self, e) -> None:
        self.check_line.value, self.check_line.color = '正在检查…', t.MUTED
        self.check_line.update()
        code_state = dict(self.state["code"])

        def run():
            try:
                code = frlg.code_bytes(code_state)
                result, color = translate(frlg.checked(code).describe()), t.GREEN
                dump = "\n".join(code[i:i + 16].hex(" ") for i in range(0, min(len(code), 256), 16))
            except (OSError, ValueError) as exc:
                result, color, dump = translate(str(exc)), t.RED, ""

            def show():
                self.check_line.value, self.check_line.color, self.hex_view.value = result, color, dump
                self.check_line.update()
                self.hex_view.update()
            self.app.ui(show)
        threading.Thread(target=run, daemon=True).start()

    # Sword / Shield

    def swsh_pokemon(self, egg=False) -> ft.Control:
        rows = [ft.Row([self.name_field('种类', "species", "species", optional=False),
                        *([] if egg else [self.number_field('等级', "level", width=72)])], spacing=10)]
        if not egg:
            rows += [ft.Row([self.name_field('携带道具', "item", "item"), self.name_field('精灵球', "ball", "ball")],
                            spacing=10),
                     ft.Row([self.text_field('昵称', "nickname"), self.text_field("OT", "ot")], spacing=10),
                     self.switch_row('异色', "shiny", '收到的宝可梦为异色。'),
                     self.switch_row('超极巨化', "gigantamax",
                                     '允许超极巨化；仅适用于具有超极巨化形态的种类。')]
        rows += [self.moves(self.state), self.number_field('卡片 ID', "card_id")]
        return ft.Column(rows, spacing=10)

    def swsh_egg(self) -> ft.Control:
        return self.swsh_pokemon(egg=True)

    def swsh_items(self) -> ft.Control:
        items = self.state.setdefault("items", [[1, 1]])

        def row(n):
            def item(v):
                items[n][0] = _number(v)
                self.commit()

            def quantity(e):
                items[n][1] = _number(e.control.value)
                self.commit()

            def remove(e):
                del items[n]
                self.commit(rebuild=True)
            return ft.Row([t.labeled_control('道具', NamePicker(self.app, "swsh", "item", str(items[n][0] or ""),
                                                                item, optional=False).control, expand=True),
                           t.labeled_control('数量', t.field(value=str(items[n][1]), mono=True, width=72,
                                                                 on_change=quantity)),
                           ft.Container(t.icon_button("close", remove, '移除'), height=t.CONTROL_HEIGHT,
                                        alignment=ft.Alignment.CENTER)],
                          spacing=10, vertical_alignment=ft.CrossAxisAlignment.END)

        def add(e):
            items.append([1, 1])
            self.commit(rebuild=True)
        adder = [t.secondary_button('添加道具', add, "plus")] if len(items) < 6 else []
        return ft.Column([*(row(n) for n in range(len(items))), *adder, self.number_field('卡片 ID', "card_id")],
                         spacing=10)

    def swsh_clothing(self) -> ft.Control:
        chosen = self.state.setdefault("outfits", [])

        def toggle(key, on):
            if on and key not in chosen:
                chosen.append(key)
            elif not on and key in chosen:
                chosen.remove(key)
            self.commit()
        rows = [ft.Row([t.text(translate(o.label), 13, expand=True),
                        t.switch(o.key in chosen, lambda e, k=o.key: toggle(k, e.control.value))])
                for o in swsh.OUTFITS]
        return ft.Column([t.text('官方服装。每张卡片可为每种性别包含六件服装，玩家收到与自身角色对应的版本。', 12, t.MUTED), *rows,
                          self.number_field('卡片 ID', "card_id")], spacing=8)

    def swsh_money(self) -> ft.Control:
        return ft.Row([self.number_field("Money", "money", width=120), self.number_field('卡片 ID', "card_id")],
                      spacing=10)

    def swsh_bp(self) -> ft.Control:
        return ft.Row([self.number_field('对战点数', "bp"), self.number_field('卡片 ID', "card_id")],
                      spacing=10)

    # Summary

    def name(self, kind, n) -> str:
        """The name PKHeX gives an id; the first miss loads the list and redraws the summary."""
        if self.game == "frlg" and kind == "species":
            names = "species3"
        else:
            names = "items" if kind == "item" else kind
        cached = SERVICE.species_cache.get(f"{self.game}:{names}")
        if cached is None:
            def load():
                try:
                    SERVICE.names(self.game, names)
                except Exception:
                    return
                if self.games.tool is self.tool:
                    self.app.ui(lambda: self.show_summary(update=True))
            threading.Thread(target=load, daemon=True).start()
        return next((entry["name"] for entry in cached or () if entry["id"] == _number(n)), f"{kind} #{n}")

    def show_summary(self, update=False) -> None:
        mode = self.value["mode"]
        self.status.value, self.status.color = "", t.MUTED
        if mode == "build":
            when, lines = gift_description(self.game, self.state, self.name)
        elif mode == "preset":
            preset = self.module.PRESET[self.value["preset"]]
            when, lines = getattr(preset, "when", ""), [preset.summary]
            if hasattr(preset, "members"):
                when = '游戏机接收后立即生效。'
                lines = preset.effects(self.value["options"].get(preset.key))
            elif preset.state is not None:
                when, lines = gift_description(self.game, preset.state, self.name)
        elif mode == "event":
            when, lines = self.module.OFFICIAL.describe(self.module.OFFICIAL.by_key()[self.value["event"]]["record"],
                                                      self.name)
        else:
            when, lines = "", []
        problem = gift_builder.problem(self.tool, self.value)
        if problem:
            self.status.value, self.status.color = translate(problem), t.RED
        elif mode != "preset" or self.module.PRESET[self.value["preset"]].args == ():
            gift = gift_builder.compile(self.tool, self.value)
            targets = [translate(frlg.CARTRIDGES.get(code, '剑／盾')) for code in gift.variants]
            self.status.value = '适用于 ' + ", ".join(targets) + "."
            if mode == "file":
                lines = [gift.name]
        self.when.value = translate(when)
        self.when.visible = bool(when)
        self.effects.controls = [ft.Row([t.pixel_icon("check", color=t.GREEN), t.text(translate(line), 13, expand=True)],
                                        spacing=8) for line in lines]
        if update:
            for control in (self.when, self.effects, self.status):
                control.update()

    async def _save(self, e) -> None:
        self.save_button.disabled = True
        self.status.value, self.status.color = '正在准备礼物文件…', t.MUTED
        self.save_button.update()
        self.status.update()
        tool, extra = self.tool, dict(self.games.extra)
        values = {**self.games.values, self.field.key: copy.deepcopy(self.value)}
        try:
            gift = await asyncio.to_thread(gift_files.build, tool, values, extra, self.app.settings)
            native = "wc8" if self.game == "swsh" else "wc3"
            path = await self.app.picker.save_file(
                dialog_title='保存神秘礼物', file_name=f"{tool.key}.pokegift",
                file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=[gifts.EXTENSION, native])
            if path:
                path += "" if path.lower().endswith((".pokegift", f".{native}")) else ".pokegift"
                gifts.save(path, gift)
                self.status.value = f'已保存 {path}'
            else:
                self.show_summary()
        except (OSError, ValueError, pokemon.BuilderError) as exc:
            self.status.value, self.status.color = translate(str(exc)), t.RED
        finally:
            self.save_button.disabled = False
            if self.games.tool is tool:
                self.save_button.update()
                self.status.update()
