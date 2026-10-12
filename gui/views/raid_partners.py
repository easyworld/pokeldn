"""The Tera Raid host's Raid NPC partners card: the progress the partners come from and one of that
pool's trainers for each slot the consoles joining leave empty, in slot order (pokeldn.sv.raid_partners);
the host draws a partner seed that seats them when it starts, and draws a partner left unpicked as the
game does. Folding only hides the card: the choice goes to the raid."""

import flet as ft

from gui import theme as t
from gui.localization import translate, game_terms
from gui.views.sprites import MINI, Sprite
from pokeldn.app import command
from pokeldn.sv import raid_partners

COLUMNS = 3
# A card narrower than this cuts the trainer's, the Pokemon's and the moves' names, so a narrow window
# shows two to a row.
CARD_WIDTH = 150
GAP = 8
REASON_HEIGHT = 48                          # two 11 px lines at the theme's 1.4 line height, padded
RANKS = {1: (t.AMBER, '推荐搭档'), 2: (t.SILVER, '次选搭档')}


def columns(width: float) -> int:
    """-> the cards to a row in `width` px: COLUMNS while each is CARD_WIDTH wide, else two; COLUMNS
    before the width is known."""
    return COLUMNS if not width or (width - GAP * (COLUMNS - 1)) / COLUMNS >= CARD_WIDTH else 2


class RaidPartnersPicker:
    """`view` is the GamesView: it keeps the card open across redraws, holds the values and gives the
    raid's context, whose progress and crystal set the partners' progress unless one is chosen. Its
    Consoles joining sets how many partners there are to pick."""

    def __init__(self, view, field):
        self.view, self.app, self.field = view, view.app, field
        self.open = view.raid_partners_open
        stored = view.values.get(field.key)
        self.value = dict(stored) if isinstance(stored, dict) else {"progress": "", "picks": []}
        context = view.raid_context()
        self.default = raid_partners.stage_of(context["progress"], context.get("content", "standard"))
        chosen = self.value.get("progress")
        self.stage = raid_partners.STAGES.index(chosen) if chosen in raid_partners.STAGES else self.default
        self.pool = raid_partners.pool(self.stage)
        self.consoles = command.raid_consoles(view.tool, view.values)
        self.free = raid_partners.slots(self.consoles)
        # Partners take four fifths of the level of Our Pokemon, the host's; 0 until it is built.
        self.host = command.raid_pokemon_level(view.values)
        self.level = raid_partners.level_for(self.host)
        # A trainer this progress's pool lacks (Dylan and Luke below four stars) leaves the choice, and
        # a console joining takes the last pick's slot.
        names = {p.trainer for p in self.pool}
        picks = [name for name in self.value.get("picks", ()) if name in names][:self.free]
        if isinstance(stored, dict) and picks != list(self.value.get("picks", ())):
            self.value["picks"] = picks
            view.values[field.key] = self.value
            self.app.settings.save()
        self.picks = picks
        self.chevron = t.pixel_icon("chevron-down" if self.open else "chevron-right", color=t.FAINT)
        summary = self._summary()
        header = ft.Container(ft.Row([
            self.chevron, t.text(field.label, 13, weight=ft.FontWeight.W_600),
            ft.Container(t.text(summary, 12, t.BLUE if picks or chosen else t.MUTED, max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS), expand=True,
                         alignment=ft.Alignment.CENTER_RIGHT),
        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER), on_click=self._toggle,
            tooltip='显示或隐藏团体战搭档')
        self.body = ft.Column([], spacing=10, visible=self.open)
        if self.open:
            self.body.controls = self._body()
        self.control = t.surface(ft.Container(ft.Column([header, self.body], spacing=10, tight=True),
                                              padding=16))

    def _summary(self) -> str:
        labels = dict(next(f for f in self.view.tool.fields if f.key == "--raid-progress").choices)
        stage = f" · {labels.get(self.value['progress'], '')}" if self.value.get("progress") else ""
        if not self.free:
            return f"无 NPC 搭档，{self.consoles} 台游戏机占满空位"
        if not self.picks:
            return f"由游戏随机安排{stage}"
        names = ", ".join(self.picks)
        return (names if len(self.picks) == self.free else f"{names}，另 1 名随机安排") + stage

    def _body(self) -> list[ft.Control]:
        labels = dict(next(f for f in self.view.tool.fields if f.key == "--raid-progress").choices)
        options = [(key, labels.get(key, key) + ('（剧情进度）' if n == self.default else ""))
                   for n, key in enumerate(raid_partners.STAGES)]
        progress = t.dropdown(options, raid_partners.STAGES[self.stage], on_select=self._progress)
        lead = (f"搭档等级为 {self.level}，即我方宝可梦等级 {self.host} 的五分之四。"
                if self.level else '搭档等级为我方宝可梦等级的五分之四。')
        if not self.free:
            note = (f"{lead} {self.consoles} 台游戏机加入后没有空位；未有游戏机加入的席位才由搭档占用。")
        elif self.free == 1:
            note = (f"{lead} 可为游戏机留下的空位选择 1 名搭档，或在主持开始时随机安排。")
        else:
            note = (f"{lead} 最多选择 2 名，依次填补空位；未选择的搭档在主持开始时随机安排。")
        # The cards' width sets how many stand to a row.
        cards = ft.Container(ft.Column(self._rows(), spacing=GAP), size_change_interval=100,
                             on_size_change=self._spread)
        return [t.text(self.field.help, 12, t.MUTED),
                t.labeled_control('搭档进度', progress),
                t.text(note, 12, t.MUTED),
                cards]

    def _rows(self) -> list[ft.Control]:
        count = columns(self.view.raid_partners_width)
        rows = []
        for i in range(0, len(self.pool), count):
            partners = self.pool[i:i + count]
            # A row with a favoured partner gives every card the reason's room, so they stand level.
            footer = any(p.why for p in partners)
            row = [self._card(p, footer) for p in partners]
            row += [ft.Container(expand=True) for _ in range(count - len(row))]
            rows.append(ft.Row(row, spacing=GAP, vertical_alignment=ft.CrossAxisAlignment.START))
        return rows

    def _card(self, partner, footer=False) -> ft.Control:
        picked = partner.trainer in self.picks
        full = len(self.picks) >= self.free
        order = ft.Container(t.text(str(self.picks.index(partner.trainer) + 1), 11, t.BG,
                                    weight=ft.FontWeight.W_700),
                             width=20, height=20, border_radius=10, bgcolor=t.BLUE,
                             alignment=ft.Alignment.CENTER) if picked else ft.Container()
        title = ft.Row([
            Sprite(self.app, partner.species, size=MINI).control,
            ft.Column([t.text(partner.trainer, 13, weight=ft.FontWeight.W_600, max_lines=1,
                              overflow=ft.TextOverflow.ELLIPSIS),
                       t.text(translate(partner.name), 12, t.MUTED, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)],
                      spacing=0, expand=True),
            order,
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        facts = ft.Row([t.chip(f"等级 {self.level}" if self.level else '等级 —'),
                        t.chip(translate(partner.tera), "diamond-gem", t.FAINT)], spacing=6, tight=True)
        # Every partner has three moves, one to a line, so every card of a pool stands as tall.
        moves = ft.Column([t.text(game_terms("sv").get(partner.ability, translate(partner.ability)), 12, t.SOFT, weight=ft.FontWeight.W_500, max_lines=1,
                                  overflow=ft.TextOverflow.ELLIPSIS)]
                          + [t.text(game_terms("sv").get(move, translate(move)), 12, t.MUTED, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
                             for move in partner.moves], spacing=1)
        column = [title, facts, moves]
        if footer:
            # Wanted by raiders: a strip tinted gold for the favoured, silver for the next tier; its
            # tooltip says why at more length. A card without one keeps the strip's room.
            strip = ft.Container(height=REASON_HEIGHT)
            if partner.why:
                ink, tier = RANKS[partner.rank]
                strip = ft.Container(ft.Row([
                    t.pixel_icon("star", 12, color=ink),
                    ft.Container(t.text(translate(partner.why), 11, ink, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                 expand=True),
                ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.START),
                    height=REASON_HEIGHT, padding=ft.Padding(8, 6, 8, 6), border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.10, ink), tooltip=f"{tier}：{translate(partner.detail)}。")
            column.append(strip)
        return ft.Container(
            ft.Column(column, spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH), expand=True,
            padding=12, border_radius=12,
            bgcolor=t.SELECTED if picked else t.FIELD,
            border=ft.Border.all(1, t.BLUE if picked else t.OUTLINE),
            opacity=0.45 if full and not picked else 1.0,
            on_click=None if full and not picked else (lambda _e, name=partner.trainer: self._pick(name)),
            tooltip=None if full and not picked else ('改为随机安排' if picked else '选择此搭档'))

    # Changes

    def _toggle(self, _e) -> None:
        self.view.show_raid_partners(not self.open)

    def _spread(self, e) -> None:
        before = columns(self.view.raid_partners_width)
        self.view.raid_partners_width = e.width
        if columns(e.width) != before:
            e.control.content.controls = self._rows()
            e.control.content.update()

    def follow_host(self) -> None:
        """Our Pokemon changed, which the view saves without a redraw: the partners' level follows."""
        host = command.raid_pokemon_level(self.view.values)
        if host != self.host:
            self.host, self.level = host, raid_partners.level_for(host)
            if self.open:
                self.body.controls = self._body()
                self.body.update()

    def _progress(self, e) -> None:
        # The story progress's own stage follows the story progress, rather than holding it.
        chosen = e.control.value
        self.value["progress"] = "" if raid_partners.STAGES.index(chosen) == self.default else chosen
        self.view.set_value(self.field, self.value, rebuild=True)

    def _pick(self, name: str) -> None:
        picks = [p for p in self.picks if p != name]
        if name not in self.picks:
            picks.append(name)
        self.value["picks"] = picks[:self.free]
        self.view.set_value(self.field, self.value, rebuild=True)
