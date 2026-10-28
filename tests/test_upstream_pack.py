"""Run against a compatible upstream checkout named by POKELDN_SOURCE."""
import json
import os
from pathlib import Path
import re
import string
import subprocess
import sys
import tomllib
import zipfile

import pytest

PACK = Path(__file__).resolve().parents[1]
APP = Path(os.environ["POKELDN_SOURCE"]).resolve()
sys.path.insert(0, str(APP))

from pokeldn import plugins, pokemon
from pokeldn.app import i18n, paths, plugin_store, settings
from scripts.check_language_pack import check, help_keys

HAN = re.compile(r"[\u3400-\u9fff]")
ENGLISH = tomllib.loads((APP / "pokeldn/app/data/strings.en.toml").read_text(encoding="utf-8"))


@pytest.fixture
def installed(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "DATA", tmp_path / "app-data")
    monkeypatch.setattr(settings, "PATH", paths.DATA / "settings.json")
    monkeypatch.setenv("POKELDN_PLUGINS", "")
    monkeypatch.setattr(plugins.metadata, "entry_points", lambda **kw: [])
    package = plugin_store.pack(str(PACK), str(tmp_path / "language.pokeplugin"))
    plugin_store.install(package)
    selected = settings.Settings(plugins=[package.id], app_language=package.id)
    selected.save()
    plugins._reset()
    i18n.select(package.id)
    assert i18n.locale() == "zh-Hans"
    yield package
    i18n.select()
    plugins._reset()


def test_current_upstream_catalog_has_no_missing_or_stale_resources():
    assert plugins.compatibility((1, 9))[0] == "ok"
    assert check(PACK) == {"missing strings": [], "unknown strings": [], "placeholders differ": [],
                           "missing help": [], "unknown help": []}


def test_english_source_contract_catches_changed_help_as_well_as_new_keys():
    snapshot = json.loads((PACK / "tests/upstream_sources.json").read_text(encoding="utf-8"))
    assert snapshot["strings"] == ENGLISH
    assert snapshot["help"] == help_keys()


def test_installable_archive_is_data_only_in_the_19_format(installed):
    assert not installed.findings
    with zipfile.ZipFile(installed.source) as archive:
        names = set(archive.namelist())
        assert {"plugin.toml", "strings.toml", "messages.toml", "templates.toml", "terms.toml", "help.toml"} <= names
        assert not any(name.startswith(("tests/", "locales/")) or name.endswith((".py", ".pyc")) for name in names)
        manifest = tomllib.loads(archive.read("plugin.toml").decode())
        assert manifest["api"] == "1.9" and "localization_format" not in manifest
    assert i18n.t("main.games_d9dae7", "Games") == "游戏"
    i18n.select()
    assert i18n.t("main.games_d9dae7", "Games") == "Games"


@pytest.mark.parametrize("language", ["community-zh-hans", ""])
def test_every_interface_template_formats_in_chinese_and_english(installed, language):
    targets = tomllib.loads((PACK / "strings.toml").read_text(encoding="utf-8"))
    i18n.select(language)
    for key, english in ENGLISH.items():
        fields = list(string.Formatter().parse(english))
        params = {name: 1234 if spec and spec[-1:] != "s" else "PLAYER {braces} C:/Save/00123456"
                  for _, name, spec, _ in fields if name is not None}
        if key == "plugins.source_count":
            params = {"value0": 2, "value1": "s"}
        elif key == "plugins.source_added":
            params = {"value0": "Source", "value1": 2, "value2": "s"}
        elif key == "plugins.tool_d0d814":
            params = {"value0": "demo", "value1": 2, "value2": "s"}
        shown = i18n.t(key, english, **params)
        if language:
            assert shown == targets[key].format(**params), key
        else:
            assert shown == english.format(**params) and not HAN.search(shown), (key, shown)


def test_english_plural_suffix_does_not_leak_into_chinese(installed):
    for count, suffix in ((1, ""), (2, "s")):
        assert i18n.t("plugins.source_count", ENGLISH["plugins.source_count"], value0=count, value1=suffix) == f"{count} 个插件"
        shown = i18n.t("gts.open_until_offer_answered_3c9d1f", ENGLISH["gts.open_until_offer_answered_3c9d1f"],
                       value0="2026-10-26", value1=count, value2=suffix)
        assert shown == f"开放至 2026-10-26；已回应 {count} 份交换提议。"


def test_dynamic_templates_do_not_shadow_other_templates_or_translate_literal_fields(installed):
    templates = tomllib.loads((PACK / "templates.toml").read_text(encoding="utf-8"))
    for source, target in templates.items():
        params = {name: "SENTINEL_" + name + "_{braces}_C:/Save/00123456"
                  for _, name, _, _ in string.Formatter().parse(source) if name is not None}
        assert i18n.message(source.format(**params)) == target.format(**params), source


def test_advanced_help_is_tool_specific_and_complete(installed):
    resources = tomllib.loads((PACK / "help.toml").read_text(encoding="utf-8"))
    for key, source in help_keys().items():
        tool, option = key.split(":", 1)
        assert i18n.help_text(tool, option, source) == resources[key]
    assert "训练家" in i18n.help_text("frlg-trade-host", "--language", "missing")


def test_gift_and_event_metadata_and_cjk_tooltips(installed):
    from gui.localization import translate
    from pokeldn.app.gift_builder import module
    from pokeldn.swsh import events
    for game in ("frlg", "rse", "swsh"):
        for preset in module(game).PRESETS:
            for attr in ("label", "group", "summary", "when"):
                value = getattr(preset, attr, "")
                if value and re.search("[A-Za-z]", value):
                    assert HAN.search(translate(value)), (game, preset.key, attr, value)
            for boost in getattr(preset, "members", ()):
                for attr in ("label", "summary"):
                    value = getattr(boost, attr, "")
                    if value and re.search("[A-Za-z]", value):
                        assert HAN.search(translate(value)), (game, boost.key, attr, value)
                        assert "Turns off any game boost" not in translate(value), (boost.key, value)
    for card in events.load():
        assert HAN.search(translate(card["label"])), card["key"]
    assert translate("Item") == "道具" and translate("Egg") == "蛋"
    text = "Turns off any game boost that is on."
    assert HAN.search(translate(text)) and "Turns off" not in translate(text)
    from gui import theme
    style = theme.app_theme().tooltip_theme.text_style
    assert style.font_family == "Noto Sans CJK SC" and theme.CJK_FONT in style.font_family_fallback


def test_real_pkhex_names_follow_display_language_without_changing_ids(installed):
    from gui.localization import SERVICE, summary_text, summary_lines
    checks = {"national": (25, "皮卡丘"), "moves": (94, "精神强念"), "abilities": (1, "恶臭"),
              "types": (0, "一般"), "natures": (0, "勤奋"), "balls": (4, "精灵球")}
    for kind, (identity, expected) in checks.items():
        table = {entry["id"]: entry["name"] for entry in SERVICE.names("sv", kind)}
        assert table[identity] == expected, (kind, table.get(identity))
    assert {entry["id"]: entry["name"] for entry in pokemon.SERVICE.names("sv", "moves")}[94] == "Psychic"
    literal = "'旅人 {species} C:/Save/00012345'"
    shown = summary_text("Pikachu · Lv. 5 · shiny · " + literal)
    assert "皮卡丘" in shown and "异色" in shown and literal in shown
    head, rest = summary_lines("Pikachu · Lv. 5 · shiny · alpha · " + literal)
    assert "头目" in head and literal in rest
    assert i18n.message("Gives an Egg containing Pikachu.") == "赠送皮卡丘的蛋。"


def test_custom_firered_giver_and_location_summaries_translate_nested_module_values(installed):
    from gui.localization import gift_description
    from pokeldn.frlg.gift import builder
    for giver, _, _, *_ in builder.GIVERS:
        state = builder.blank()
        state["giver"] = giver
        when, lines = gift_description("frlg", state, lambda kind, number: "皮卡丘" if kind == "species" else "大师球")
        assert HAN.search(when) and not re.search("[A-Za-z]", when.replace("NPC", "")), when
        assert not any("the delivery man" in line or "talks to mom" in line or "pallet town" in line for line in lines), lines


def test_localized_document_titles_anchors_search_and_missing_page_fallback(installed):
    from gui.views import docs
    from gui.views.widgets import heading_sections
    for path in (PACK / "docs").glob("*.md"):
        name = "guide" if path.name == "guide.md" else path.name
        assert docs.document_path(name) == plugins.folder() / installed.id / "docs" / path.name
        body, reference = docs.document_body(name)
        assert reference is not None
        sections = [(key, title) for key, title, _ in heading_sections(body, reference=reference) if title]
        assert len({key for key, _ in sections}) == len(sections), path.name
        assert all(re.fullmatch("[a-z0-9-]+", key) for key, _ in sections), path.name
    page = docs.Page("frlg.md", "FireRed and LeafGreen", 1)
    assert HAN.search(docs.page_title(page))
    assert docs.document_path("plugins.md") == Path(docs.DOCS) / "plugins.md"
    for file in ("frlg_rom.md", "pia.md", "sv_raid.md", "rse_switch_build.md"):
        assert docs.document_path(file) == Path(docs.DOCS) / file
        assert docs.document_body(file)[1] is None
    assert docs.search(docs.index([page], "指南"), "宝可梦")


def test_split_emerald_docs_keep_current_english_section_links(installed):
    from gui.views import docs
    from gui.views.widgets import heading_sections
    for name in ("rse.md", "rse_gift.md", "rse_link.md"):
        body, reference = docs.document_body(name)
        english = {key for key, title, _ in heading_sections(reference) if title}
        translated = {key for key, title, _ in heading_sections(body, reference=reference) if title}
        assert english <= translated, (name, english - translated)
    assert "五轮" in docs.document_body("rse_link.md")[0]


def test_new_legendary_boost_options_and_countdown_are_chinese(installed):
    from gui.localization import translate
    from pokeldn.frlg.gift import builder
    boost = builder.BOOST["hook-shiny-press"]
    assert translate(boost.label) == "异色传说宝可梦"
    for identity, label in builder.LEGENDARIES:
        assert HAN.search(translate(label)), label
        _, lines = boost.compose({"legendary": identity})
        assert all(HAN.search(translate(line)) for line in lines)
        assert not any(word in translate(lines[0]) for word in ("Mewtwo", "Articuno", "Zapdos", "Moltres"))
        instructions = translate(lines[1])
        if identity == "mewtwo":
            assert "自行按 A" in instructions and "不要按任何按钮" in instructions
            assert "按住 B" not in instructions
        else:
            assert "上方向键" in instructions and "按住 B" in instructions
        i18n.select()
        assert translate(lines[1]) == lines[1]
        i18n.select(installed.id)


def test_new_help_covers_rom_probe_and_emerald_five_rounds(installed):
    for tool in ("frlg-gift", "rse-gift"):
        assert "软重置" in i18n.help_text(tool, "--buffer-script", "missing")
        assert "--write-unsafe" in i18n.help_text(tool, "--rom-fold-n", "missing")
        assert "EMER" in i18n.help_text(tool, "--rom-fill-base", "missing")
    for tool in ("frlg-trade-host", "frlg-trade-online", "rse-trade-host", "rse-trade-online"):
        assert "--version emerald 时为 5 轮" in i18n.help_text(tool, "--save-rounds", "missing")


def test_activity_labels_translate_but_tool_variants_and_protocol_values_stay_identical(tmp_path):
    code = '''
import json, os
from pokeldn.app import i18n
i18n.select(os.environ["TEST_PACK"])
from pokeldn.app.catalog import GAMES, activities
labels, identities = [], []
for game in GAMES:
    labels.append(game.name)
    for activity in activities(game):
        labels.append(activity.name)
        for tool in activity.tools:
            identities.append([game.key, activity.key, tool.key, list(tool.variant), list(tool.fixed)])
            for _, axis, options in activity.axes(tool):
                labels.append(axis.label)
                labels.extend(option[1] for option in options)
print(json.dumps({"labels":labels,"identities":identities}, ensure_ascii=False))
'''
    outputs = []
    for pack in ("", "community-zh-hans"):
        environment = dict(os.environ, PYTHONPATH=str(APP), PYTHONIOENCODING="utf-8", TEST_PACK=pack,
                           POKELDN_PLUGINS=str(PACK), POKELDN_DATA=str(tmp_path / (pack or "english")))
        result = subprocess.run([sys.executable, "-c", code], cwd=APP, env=environment,
                                capture_output=True, text=True, encoding="utf-8", timeout=60)
        assert result.returncode == 0, result.stderr
        outputs.append(json.loads(result.stdout))
    assert outputs[0]["identities"] == outputs[1]["identities"]
    assert not any(HAN.search(value) for value in outputs[0]["labels"])
    assert {"交换", "极巨大冒险", "极巨团体战", "太晶团体战", "连接方式", "你的游戏机"} <= set(outputs[1]["labels"])


def test_selected_pack_loads_without_babel(tmp_path):
    code = '''
import importlib.abc, os, sys
class NoBabel(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "babel" or fullname.startswith("babel."):
            raise ImportError("Babel is unavailable on mobile")
sys.meta_path.insert(0, NoBabel())
from pokeldn.app import i18n
i18n.select("community-zh-hans")
assert i18n.locale() == "zh-Hans"
assert i18n.t("main.games_d9dae7", "Games") == "游戏"
from gui.localization import translate
assert translate("Item") == "道具"
'''
    environment = dict(os.environ, PYTHONPATH=str(APP), PYTHONIOENCODING="utf-8",
                       POKELDN_PLUGINS=str(PACK), POKELDN_DATA=str(tmp_path / "data"))
    result = subprocess.run([sys.executable, "-c", code], env=environment, cwd=APP,
                            capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
