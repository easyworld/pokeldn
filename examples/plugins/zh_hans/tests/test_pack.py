"""Run against upstream, not the Chinese fork; README.md gives the exact command."""
from collections import Counter
from dataclasses import fields, is_dataclass
import json
import os
from pathlib import Path
import string
import subprocess
import sys
from types import SimpleNamespace
import tomllib

import pytest

from pokeldn import plugins
from pokeldn.app import i18n, paths, plugin_store

PACK = Path(__file__).resolve().parents[1]
ID = "easyworld-zh-hans"


@pytest.fixture(autouse=True)
def selected(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "DATA", tmp_path / "data")
    monkeypatch.setenv("POKELDN_PLUGINS", str(PACK))
    plugins._reset()
    i18n.select(ID)
    assert i18n.locale() == "zh-Hans"
    yield
    plugins._reset()
    i18n.select()


def texts(control):
    import flet as ft
    if isinstance(control, ft.Text):
        yield control.value
    if is_dataclass(control):
        for field in fields(control):
            if field.name.startswith("_"):
                continue
            value = getattr(control, field.name)
            if isinstance(value, ft.Control):
                yield from texts(value)
            elif isinstance(value, (list, tuple)):
                for child in value:
                    if isinstance(child, ft.Control):
                        yield from texts(child)


def test_every_upstream_key_preserves_format_fields():
    english = tomllib.loads(Path("pokeldn/app/data/strings.en.toml").read_text(encoding="utf-8"))
    chinese = tomllib.loads((PACK / "strings.toml").read_text(encoding="utf-8"))
    def placeholders(text):
        return Counter((name, spec, conversion) for _, name, spec, conversion
                       in string.Formatter().parse(text) if name is not None)
    for key, default in english.items():
        assert key in chinese, key
        assert placeholders(chinese[key]) == placeholders(default), key


@pytest.mark.parametrize("source,expected", [
    ("Your save", "我的存档"),
    ("The ferry to Navel Rock, where Ho-Oh and Lugia wait.", "可搭乘渡轮前往肚脐岩，凤王和洛奇亚在那里等待。"),
    ("Puts the Pikachu uniform in the wardrobe", "将皮卡丘队服放入衣柜"),
    ("Violet · Paldea", "紫 · 帕底亚"),
    ("Steel", "钢"), ("Calm", "温和"),
    ("Magma Armor", "熔岩铠甲"), ("Flame Wheel", "火焰轮"),
    ("Water Pulse", "水之波动"), ("Swift Swim", "悠游自如"),
])
def test_reported_literal_and_dynamic_text(source, expected):
    from gui.localization import translate
    assert translate(source) == expected


def test_every_official_item_card_uses_record_item_ids():
    from gui.localization import translate
    from pokeldn.swsh import events
    expected = json.loads((PACK / "event_messages.json").read_text(encoding="utf-8"))
    cards = [card for card in events.load() if card["group"] == "Items"]
    assert len(cards) >= 60
    for card in cards:
        assert translate(card["label"]) == expected[card["label"]], card["label"]
        assert translate(card["summary"]) == "放入背包"
    assert any("沉重球" in v and "诱饵球" in v for v in expected.values())


def test_all_partner_pools_translate_names_types_abilities_and_moves():
    from gui.localization import translate
    from pokeldn.sv.raid_partners import pool
    for stage in range(5):
        for partner in pool(stage):
            for value in (partner.trainer, partner.name, partner.tera, partner.ability, *partner.moves):
                assert translate(value) != value, (stage, value)
    assert translate("Psychic") == "超能力"
    assert i18n.t("pokemon.move.Psychic", "Psychic") == "精神强念"


def test_actual_partner_card_displays_chinese_and_keeps_selection_key():
    from gui.views.raid_partners import RaidPartnersPicker
    from pokeldn.sv.raid_partners import pool
    picker = SimpleNamespace(picks=[], free=2, level=40,
                             app=SimpleNamespace(settings=SimpleNamespace(sprites=False)))
    for stage in range(5):
        for partner in pool(stage):
            before = partner.trainer
            card = RaidPartnersPicker._card(picker, partner)
            displayed = list(texts(card))
            assert before not in displayed
            assert partner.trainer == before
            for move in partner.moves:
                assert move not in displayed
            if "Psychic" in partner.moves:
                assert "精神强念" in displayed and "超能力" not in displayed


def test_legendary_dropdown_and_rental_names_translate_but_keys_do_not():
    from gui.views.games import GamesView
    from gui.views.lair_seed import LairSeedPicker
    from pokeldn.app.catalog import GAMES
    tool = next(t for g in GAMES for t in g.tools if t.key == "swsh-lair-raid-host")
    field = next(f for f in tool.fields if f.flag == "--lair-legendary")
    stub = SimpleNamespace(values={}, raid_choices=lambda _: None, set_value=lambda *a, **kw: None)
    dropdown = GamesView.input(stub, field)
    mewtwo = next(option for option in dropdown.options if option.key == "150")
    assert mewtwo.text == "超梦"
    assert LairSeedPicker._name(SimpleNamespace(names={"150": "Mewtwo"}), 150) == "超梦"


def test_real_package_install_and_english_fallback(tmp_path, monkeypatch):
    package = plugin_store.pack(str(PACK), str(tmp_path / "language.pokeplugin"))
    assert package.version == tomllib.loads((PACK / "plugin.toml").read_text(encoding="utf-8"))["version"]
    assert package.findings == []
    assert not any(name.endswith(".py") for name in package.members)
    installed = plugin_store.install(package)
    monkeypatch.setenv("POKELDN_PLUGINS", "")
    (paths.DATA / "settings.json").write_text(json.dumps({"plugins": [ID]}), encoding="utf-8")
    plugins._reset()
    i18n.select(ID)
    assert i18n.message("Your save") == "我的存档"
    assert i18n.document("guide", "english.md") == installed / "docs/guide.md"
    assert i18n.document("missing.md", "english.md") == Path("english.md")
    assert i18n.message("Unknown error: C:/玩家/save.sav") == "Unknown error: C:/玩家/save.sav"
    i18n.select()
    assert i18n.message("Your save") == "Your save"


def test_gift_egg_category_is_not_the_sandwich_ingredient():
    from gui.localization import translate
    from pokeldn.swsh.gift_builder import KINDS
    label = next(label for key, label, _ in KINDS if key == "egg")
    assert translate(label) == "宝可梦的蛋"
    # The name by item ID still describes the actual sandwich ingredient.
    item_terms = json.loads((PACK / "pkhex_terms.json").read_text(encoding="utf-8"))["terms"]
    assert item_terms["Egg"] == "水煮蛋片"
    assert translate("水煮蛋片") == "水煮蛋片"


def test_localized_document_titles_and_english_body_fallback():
    from gui.views import docs
    def flatten(items):
        for item in items:
            yield item
            yield from flatten(item.children)
    tree = docs.pages()
    pages = {page.file: page for page in flatten(tree)}
    for page in pages.values():
        assert docs.page_title(page) != page.title, page.file
    assert docs.page_title(pages["hardware.md"]) == "硬件与设置"
    assert docs.page_title(pages["frlg_rom_map.md"]) == "ROM 映射"
    assert pages["frlg_rom_map.md"] in pages["frlg.md"].children
    assert pages["frlg_rom_map.md"].parent == "FireRed and LeafGreen"
    assert docs.page_title(pages["sv_union_circle.md"]) == "集友圈"
    assert docs.document_path("sv_union_circle.md") == Path(docs.DOCS) / "sv_union_circle.md"
    sections = docs.index(tree, "入门指南")
    assert any(section.page == "硬件与设置" for section in sections)
    assert any(section.page == "集友圈" for section in sections)
    localized = docs.document_path("frlg_rom_map.md")
    assert localized == PACK / "docs/frlg_rom_map.md"
    i18n.select()
    assert docs.page_title(pages["hardware.md"]) == "Hardware and setup"
    assert docs.page_title(pages["sv_union_circle.md"]) == "Union Circle"


def test_catalog_protocol_values_unchanged_in_fresh_processes(tmp_path):
    code = '''import json, os
from pokeldn.app import i18n
i18n.select(os.environ['LANGUAGE_PACK'])
from pokeldn.app.catalog import GAMES
print(json.dumps([(g.key, [(t.key, t.script, t.fixed,
 [(f.key, f.flag, f.default, [c[0] for c in f.choices]) for f in t.fields]) for t in g.tools]) for g in GAMES]))
'''
    results = []
    for language in ("", ID):
        env = {**os.environ, "LANGUAGE_PACK": language, "POKELDN_PLUGINS": str(PACK),
               "POKELDN_DATA": str(tmp_path), "PYTHONIOENCODING": "utf-8"}
        results.append(subprocess.check_output([sys.executable, "-c", code], env=env, text=True))
    assert results[0] == results[1]
