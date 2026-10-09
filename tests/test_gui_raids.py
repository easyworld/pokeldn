"""Raid presentation must keep the seed's protocol IDs and the finder's stored choices."""
from types import SimpleNamespace

import pytest

ft = pytest.importorskip("flet")
from gui.localization import translate
from gui.views import raid_seed
from gui.views.games import tool_icon
from pokeldn.app.catalog import GAMES
from pokeldn.sv import raid_encounter


def walk(control):
    yield control
    for child in [*(getattr(control, "controls", None) or []), getattr(control, "content", None)]:
        if isinstance(child, ft.Control):
            yield from walk(child)


def test_raid_card_names_the_original_boss_in_chinese(monkeypatch):
    monkeypatch.setattr(raid_seed, "Sprite", lambda *a, **kw:
                        SimpleNamespace(frame=ft.Container(), control=ft.Container()))
    raid = raid_encounter.generate(0x000F34C3, version="violet", map_name="paldea",
                                   progress="4star", content="standard")
    card = raid_seed.boss_card(None, raid.seed, raid.stars, raid.boss, raid.context)
    texts = [c.value for c in walk(card) if isinstance(c, ft.Text)]
    expected = translate(raid_encounter.tables()["species_names"][str(raid.boss["species"])])
    assert expected in texts and any("\u4e00" <= c <= "\u9fff" for c in expected)
    assert "紫 · 帕底亚 · 4 星团体战 · 普通结晶" in texts
    assert f"等级 {raid.boss['level']}" in texts
    assert any(text.startswith("太晶属性：") for text in texts)
    assert all(label in texts for label in ("HP", "攻击", "防御", "速度", "特攻", "特防"))


def test_raid_finder_translates_choices_without_changing_the_context_keys(monkeypatch):
    monkeypatch.setattr(raid_seed, "NamePicker", lambda *a, **kw: SimpleNamespace(control=ft.Dropdown()))
    dialogs = []
    app = SimpleNamespace(page=SimpleNamespace(show_dialog=dialogs.append))
    context = dict(version="scarlet", map_name="kitakami", progress="5star", content="standard")
    picker = raid_seed.RaidSeedPicker(app, "", lambda value: None,
                                     lambda: context, lambda value: None)
    picker._open(None)
    dropdowns = [c for c in walk(dialogs[0].content) if isinstance(c, ft.Dropdown)]
    version = next(c for c in dropdowns if any(o.key == "scarlet" for o in c.options))
    region = next(c for c in dropdowns if any(o.key == "kitakami" for o in c.options))
    assert version.value == "scarlet" and region.value == "kitakami"
    assert {o.key: o.text for o in version.options} == {"any": "任意游戏", "scarlet": "朱", "violet": "紫"}
    assert {o.key: o.text for o in region.options}["kitakami"] == "北上乡"
    tools = next(g for g in GAMES if g.key == "sv").tools
    assert [t.key for t in tools] == ["sv-host", "sv-join", "sv-online", "sv-raid-host", "sv-raid-join"]
    assert all(tool_icon(t) == "diamond-gem" for t in tools if "-raid-" in t.key)
