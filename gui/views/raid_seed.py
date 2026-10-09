"""The raid seed field: the boss and rewards the seed gives in the chosen context, and a finder that
searches seeds by what the boss is (pokeldn.sv.raid_search)."""

import re
import threading

import flet as ft

from gui import theme as t
from gui.views.pokemon import NamePicker
from gui.views.sprites import MINI, SIZE, Sprite
from gui.views.widgets import PixelActivity
from gui.localization import SERVICE, translate
from pokeldn.sv import raid_encounter, raid_search

TERA_TYPES = ("一般", "格斗", "飞行", "毒", "地面", "岩石", "虫", "幽灵", "钢",
              "火", "水", "草", "电", "超能力", "冰", "龙", "恶", "妖精")
NATURES = ("勤奋", "怕寂寞", "勇敢", "固执", "顽皮", "大胆", "坦率", "悠闲", "淘气",
           "乐天", "胆小", "急躁", "认真", "爽朗", "天真", "内敛", "慢吞吞", "冷静", "害羞",
           "马虎", "温和", "温顺", "自大", "慎重", "浮躁")
GENDERS = ("雄性", "雌性", "无性别")
STATS = ("HP", "攻击", "防御", "速度", "特攻", "特防")
VERSIONS = {"scarlet": "朱", "violet": "紫"}
REGIONS = {"paldea": "帕底亚", "kitakami": "北上乡", "blueberry": "蓝莓学园"}
PROGRESS = (("beginning", "游戏初期"), ("tera", "已解锁太晶团体战"), ("3star", "3 星团体战"),
            ("4star", "4 星团体战"), ("5star", "5 星团体战"), ("6star", "6 星团体战"))


def seed_of(text: str) -> int | None:
    return int(text, 16) if re.fullmatch(r"[0-9A-Fa-f]{8}", text or "") else None


def iv_range(text: str) -> tuple[int, int]:
    """'' any, '31' exactly, '20-31' a range."""
    text = (text or "").strip()
    if not text:
        return 0, 31
    match = re.fullmatch(r"(\d{1,2})(?:\s*-\s*(\d{1,2}))?", text)
    low, high = (int(match.group(1)), int(match.group(2) or match.group(1))) if match else (1, 0)
    if not 0 <= low <= high <= 31:
        raise ValueError("个体值可留空、填写 0 到 31 的数值，或填写范围（如 20-31）。")
    return low, high


def crystal_colors(context) -> tuple[str, str]:
    return t.BRAND_RED if context["content"] == "black" else t.BRAND_BLUE


def stars_row(count: int, context) -> ft.ShaderMask:
    """The raid's stars as pixel stars in the crystal's brand gradient: blue standard, red black."""
    return t.tinted(ft.Row([t.pixel_icon("star", color="#FFFFFF") for _ in range(count)], spacing=1,
                           tight=True), crystal_colors(context))


def framed_sprite(app, species: int, shiny: bool, size: int, context) -> ft.Container:
    """The sprite inside a ring of the crystal's gradient."""
    sprite = Sprite(app, species, shiny, size=size)
    sprite.frame.border = None
    radius = 12 if size >= SIZE else 10
    return ft.Container(sprite.control, padding=1.5, border_radius=radius + 1.5,
                        gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                                                   colors=list(crystal_colors(context))),
                        shadow=ft.BoxShadow(blur_radius=18, spread_radius=-6,
                                            color=ft.Colors.with_opacity(0.45, crystal_colors(context)[1])))


def iv_tile(label: str, iv: int, stat: int, compact: bool) -> ft.Container:
    """One stat: its IV large (blue at 31, red at 0), a bar of IV out of 31, the stat at the boss's level."""
    color = t.BLUE if iv == 31 else t.RED if iv == 0 else t.TEXT
    bar = ft.ProgressBar(value=iv / 31, color=t.BLUE, bgcolor=ft.Colors.with_opacity(0.08, "#FFFFFF"),
                         bar_height=3, border_radius=2)
    rows = [t.text(label, 10, t.MUTED, weight=ft.FontWeight.W_600),
            t.text(str(iv), 13 if compact else 17, color, weight=ft.FontWeight.W_700), bar]
    if not compact:
        rows.append(t.text(f"{stat}", 10, t.FAINT, tooltip="首领当前等级对应的能力值"))
    return ft.Container(ft.Column(rows, spacing=3 if compact else 4, tight=True,
                                  horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        width=46 if compact else 62, padding=ft.Padding(6, 6, 6, 8), border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.04, "#FFFFFF"))


def reward_chips(names: dict[int, str] | None, rewards) -> ft.Control:
    """The rewards as item chips, one per item with the quantities summed, in the raid's order."""
    if names is None:
        return ft.Row([PixelActivity("正在加载奖励名称"), t.text("正在加载奖励名称…", 12, t.MUTED)],
                      spacing=8)
    totals: dict[int, int] = {}
    for item, quantity in rewards:
        totals[item] = totals.get(item, 0) + quantity
    return ft.Row([ft.Container(ft.Row([
        t.text(names.get(item, f"道具 {item}"), 12, t.SOFT),
        t.text(f"×{quantity}", 12, t.BLUE, weight=ft.FontWeight.W_700)], spacing=6, tight=True),
        padding=ft.Padding(10, 4, 10, 4), border_radius=999, bgcolor=ft.Colors.with_opacity(0.06, "#FFFFFF"))
        for item, quantity in totals.items()], spacing=6, run_spacing=6, wrap=True)


def boss_card(app, seed, stars, boss, context, *, compact=False, rewards=None, on_use=None):
    """The boss a seed gives: sprite, stars, level, Tera type, IVs over stats, nature, context."""
    shiny = (boss["trainer_id"] ^ boss["secret_id"] ^ (boss["pid"] >> 16) ^ (boss["pid"] & 0xFFFF)) < 16
    name = translate(raid_encounter.tables()["species_names"][str(boss["species"])])
    title = [t.text(name, 14 if compact else 17, weight=ft.FontWeight.W_700)]
    if shiny:
        title.append(t.tinted(t.pixel_icon("sparkles", color="#FFFFFF", tooltip="异色"), crystal_colors(context)))
    title.append(stars_row(stars, context))
    accent = t.RED if context["content"] == "black" else t.BLUE
    facts = ft.Row([
        t.chip(f"等级 {boss['level']}", "sword", accent),
        t.chip(f"太晶属性：{TERA_TYPES[boss['tera_type_original']]}", "diamond-gem", accent),
        t.chip(NATURES[boss["nature"]]), t.chip(GENDERS[boss["gender"]]),
        *([t.chip("异色", "sparkles", accent)] if shiny and not compact else []),
    ], spacing=6, run_spacing=6, wrap=True)
    where = (f"{VERSIONS[context['version']]} · {REGIONS[context['map_name']]} · "
             f"{dict(PROGRESS)[context['progress']]} · "
             f"{'黑色' if context['content'] == 'black' else '普通'}结晶")
    ivs = ft.Row([iv_tile(label, iv, stat, compact)
                  for label, iv, stat in zip(STATS, boss["ivs"], boss["stats"])], spacing=6, wrap=True)
    column = [ft.Row(title, spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER), facts, ivs]
    if compact:
        column.append(ft.Row([t.text(f"{seed:08X}", 11, t.SOFT, font_family=t.MONO, selectable=True),
                              t.text(where, 11, t.FAINT)], spacing=10, wrap=True))
    else:
        column.append(ft.Row([t.pixel_icon("map-pin", size=12, color=t.FAINT), t.text(where, 12, t.MUTED)],
                             spacing=6))
    row = [framed_sprite(app, boss["species"], shiny, MINI if compact else SIZE, context),
           ft.Column(column, spacing=8 if compact else 10, expand=True)]
    if on_use:
        row.append(t.secondary_button("使用", lambda _e: on_use(seed, context), "check"))
    body = ft.Row(row, spacing=14 if compact else 18, vertical_alignment=ft.CrossAxisAlignment.START)
    if rewards is not None:
        body = ft.Column([body, ft.Container(height=1, bgcolor=t.DIVIDER),
                          ft.Row([t.pixel_icon("gift", size=12, color=t.MUTED),
                                  t.text("团体战默认奖励", 12, t.MUTED, weight=ft.FontWeight.W_600)], spacing=6),
                          rewards], spacing=10, tight=True)
    return ft.Container(body, padding=12 if compact else 16, border_radius=14,
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, "#FFFFFF")),
                        gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                                                   colors=[ft.Colors.with_opacity(0.08, accent), t.FIELD],
                                                   stops=[0, 0.55]))


class RaidSeedPicker:
    """The seed, what it gives in the tool's raid context, and Find a raid."""

    def __init__(self, app, value: str, on_change, context, on_context_change):
        self.app, self.on_change = app, on_change
        self.context, self.on_context_change = context, on_context_change
        self.seed = t.field(value=str(value or ""), mono=True, expand=True, on_change=self._typed)
        self.preview = ft.Container()
        self.control = ft.Column([
            ft.Row([self.seed, t.secondary_button("查找团体战", self._open, "search")], spacing=8),
            self.preview], spacing=8, tight=True)
        self._show(str(value or ""), update=False)

    def _show(self, text: str, update: bool = True) -> None:
        seed = seed_of(text)
        self.seed.error = None if seed is not None else "请输入八位十六进制数字。"
        self.preview.content = None
        if seed is not None:
            raid = raid_encounter.generate(seed, **self.context())
            rewards = ft.Container(reward_chips(None, raid.rewards))
            self.preview.content = boss_card(self.app, seed, raid.stars, raid.boss, raid.context,
                                             rewards=rewards)
            threading.Thread(target=self._name_rewards, args=(rewards, raid.rewards), daemon=True).start()
        if update:
            self.control.update()

    def _name_rewards(self, holder, rewards) -> None:
        try:
            names = {n["id"]: n["name"] for n in SERVICE.names("sv", "bag")}
        except Exception:
            names = {}
        holder.content = reward_chips(names, rewards)
        self.app.ui(lambda: self._update(holder))

    @staticmethod
    def _update(control) -> None:
        try:
            control.update()
        except RuntimeError:        # the card was redrawn while the names loaded
            pass

    def _typed(self, event) -> None:
        event.control.value = event.control.value.upper()
        self.on_change(event.control.value)
        self._show(event.control.value)

    def _use(self, seed: int, context: dict) -> None:
        self.app.page.pop_dialog()
        self.seed.value = f"{seed:08X}"
        self.on_change(self.seed.value)
        self.on_context_change(context)

    def _open(self, _event) -> None:
        current = self.context()
        choose = lambda options, value: t.dropdown(options, value)
        version = choose([("any", "任意游戏"), ("scarlet", "朱"), ("violet", "紫")], current["version"])
        region = choose([("any", "任意地区"), ("paldea", "帕底亚"), ("kitakami", "北上乡"),
                         ("blueberry", "蓝莓学园")], current["map_name"])
        story = choose([("any", "任意进度"), *PROGRESS], current["progress"])
        crystal = choose([("any", "任意结晶"), ("standard", "普通"), ("black", "黑色")], "any")
        species = NamePicker(self.app, "sv", "species", "", lambda _v: None,
                             names=[{"id": s, "name": translate(n)} for s, n in raid_search.species()]).control
        stars = choose([("any", "任意星级"), *((str(n), f"{n} 星") for n in range(1, 7))], "any")
        tera = choose([("any", "任意太晶属性"), *((str(i), n) for i, n in enumerate(TERA_TYPES))], "any")
        nature = choose([("any", "任意性格"), *((str(i), n) for i, n in enumerate(NATURES))], "any")
        gender = choose([("any", "任意性别"), *((str(i), n) for i, n in enumerate(GENDERS))], "any")
        shiny = choose([("any", "不限异色"), ("yes", "仅异色"), ("no", "非异色")], "any")
        rank = choose([(key, translate(label)) for key, (label, _, _) in raid_search.OBJECTIVES.items()], "overall")
        ivs = [t.field(hint="任意", mono=True, expand=True, text_align=ft.TextAlign.CENTER,
                       content_padding=ft.Padding(4, 8, 4, 8)) for _ in STATS]
        start = t.field(value=self.seed.value if seed_of(self.seed.value) is not None else "00000000",
                        mono=True)
        count = t.field(value="100000", mono=True, keyboard_type=ft.KeyboardType.NUMBER)
        results = ft.ListView(spacing=8, expand=True)
        results.controls = [empty_results()]
        status = t.text("选择团体战条件，然后点击“搜索”。", 12, t.MUTED)
        busy = ft.Container(PixelActivity("正在搜索"), visible=False)
        run = t.button("搜索", None, "search")
        stop = t.secondary_button("停止", None)
        stop.disabled = True
        cancel, closed = threading.Event(), threading.Event()
        pick = lambda control: None if control.value in (None, "any", "-", "") else control.value

        def close(_=None):
            cancel.set()
            closed.set()
            self.app.page.pop_dialog()

        def done(found, stopped):
            if closed.is_set():
                return
            results.controls = [boss_card(self.app, f.seed, f.stars, f.boss, f.context, compact=True,
                                          on_use=self._use) for f in found] or [empty_results(True)]
            status.value = (f"找到 {len(found)} 场团体战" + ("（搜索已停止）。" if stopped else "。")
                            if found else "没有符合条件的团体战。")
            run.disabled, stop.disabled, busy.visible = False, True, False
            for control in (results, status, run, stop, busy):
                control.update()

        def submit(_):
            try:
                if not (count.value or "").strip().isdigit():
                    raise ValueError("搜索种子数量必须为整数。")
                first, amount = seed_of(start.value), int(count.value)
                scope = raid_search.contexts(version.value, region.value, story.value, crystal.value)
                if first is None or not 1 <= amount * len(scope) <= raid_search.MAX_WORK:
                    raise ValueError(f"请输入八位十六进制起始种子，当前范围最多搜索 "
                                     f"{raid_search.MAX_WORK // len(scope):,} 个种子。")
                ranges = tuple(iv_range(field.value) for field in ivs)
                filters = dict(stars=pick(stars) and int(stars.value),
                               species_id=pick(species) and int(species.value),
                               tera_type=pick(tera) and int(tera.value),
                               nature=pick(nature) and int(nature.value),
                               gender=pick(gender) and int(gender.value),
                               shiny=None if pick(shiny) is None else shiny.value == "yes",
                               ivs=None if ranges == ((0, 31),) * 6 else ranges)
            except ValueError as exc:
                status.value, status.color = str(exc), t.RED
                status.update()
                return
            cancel.clear()
            status.value, status.color = "正在搜索…", t.MUTED
            results.controls, run.disabled, stop.disabled, busy.visible = [], True, False, True
            for control in (status, results, run, stop, busy):
                control.update()

            def progress(done_count, total):
                status.value = f"正在搜索种子：{done_count:,} / {total:,}…"
                self.app.ui(lambda: self._update(status))

            def work():
                try:
                    found = raid_search.search(first, amount, scope, rank.value,
                                               one_per_species=filters["species_id"] is None, limit=30,
                                               progress=progress, cancelled=cancel.is_set, **filters)
                    self.app.ui(lambda: done(found, cancel.is_set()))
                except Exception as exc:
                    message = str(exc)

                    def failed():
                        if not closed.is_set():
                            status.value, status.color, run.disabled = message, t.RED, False
                            stop.disabled, busy.visible = True, False
                            for control in (status, run, stop, busy):
                                control.update()
                    self.app.ui(failed)
            threading.Thread(target=work, daemon=True).start()

        run.on_click = submit
        stop.on_click = lambda _e: cancel.set()
        pair = lambda *controls: ft.Row(list(controls), spacing=8)
        filters = ft.Column([
            heading("map-pin", "团体战地点"),
            pair(t.labeled_control("游戏", version, expand=True), t.labeled_control("地区", region, expand=True)),
            pair(t.labeled_control("剧情进度", story, expand=True),
                 t.labeled_control("结晶", crystal, expand=True)),
            heading("sword", "首领"),
            pair(t.labeled_control("种类", species, expand=True), t.labeled_control("星级", stars, expand=True)),
            pair(t.labeled_control("太晶属性", tera, expand=True), t.labeled_control("性格", nature, expand=True)),
            pair(t.labeled_control("性别", gender, expand=True), t.labeled_control("异色", shiny, expand=True)),
            heading("sliders-horizontal", "个体值"),
            pair(*(t.labeled_control(label, field, expand=True) for label, field in zip(STATS, ivs))),
            t.text("留空表示不限，也可填写数值或范围（如 20-31）。", 11, t.FAINT),
            heading("search", "搜索"),
            t.labeled_control("排序依据", rank),
            t.text("耐久和攻击评分只依据首领的能力值估算难度。", 11, t.FAINT),
            pair(t.labeled_control("起始种子", start, expand=True),
                 t.labeled_control("搜索种子数量", count, expand=True)),
        ], spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
        found = ft.Column([
            ft.Row([busy, status], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            t.fade(results)], spacing=10, expand=True)
        self.app.page.show_dialog(t.dialog(
            title=t.text("查找太晶团体战", 17, weight=ft.FontWeight.W_600),
            content=ft.Container(ft.Row([
                ft.Container(t.fade(filters), width=360, padding=ft.Padding(0, 0, 12, 0)),
                ft.Container(width=1, bgcolor=t.DIVIDER),
                ft.Container(found, expand=True, padding=ft.Padding(8, 0, 0, 0)),
            ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.STRETCH), width=1000, height=600),
            actions=[t.secondary_button("关闭", close), stop, run]))


def heading(icon: str, title: str) -> ft.Container:
    return ft.Container(ft.Row([t.pixel_icon(icon, size=12, color=t.BLUE),
                                t.text(title, 12, t.SOFT, weight=ft.FontWeight.W_600)], spacing=8),
                        padding=ft.Padding(0, 6, 0, 0))


def empty_results(searched: bool = False) -> ft.Container:
    return ft.Container(ft.Column([
        t.tinted(t.pixel_icon("diamond-gem", size=48, color="#FFFFFF"), t.BRAND_BLUE),
        t.text("没有符合条件的团体战，请放宽条件或扩大搜索范围。" if searched else
               "搜索到的团体战会显示在这里。", 13, t.MUTED, text_align=ft.TextAlign.CENTER),
    ], spacing=12, tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        alignment=ft.Alignment.CENTER, padding=ft.Padding(0, 120, 0, 0))
