"""Chinese GTS and bank presentation keeps species, move and item IDs usable."""
from types import SimpleNamespace

import pytest

ft = pytest.importorskip("flet")
from gui.views import gts as view_gts
from gui.views.bank import EditDialog, NONE
from pokeldn.online.gts import Wants


def walk(control):
    yield control
    for child in [*(getattr(control, "controls", None) or []), getattr(control, "content", None)]:
        if isinstance(child, ft.Control):
            yield from walk(child)


def test_gts_chinese_species_selection_and_bank_levels_keep_matching_ids():
    view = SimpleNamespace(chosen="25", search="has")
    assert view_gts.GtsView._filters(view) == {"has": 25}
    view.search = "wants"
    assert view_gts.GtsView._filters(view) == {"wants": 25}
    for summary in ("Pikachu · level 50 · Hardy", "皮卡丘 · 等级 50 · 勤奋"):
        assert view_gts.level_of(SimpleNamespace(summary=summary)) == 50
    wants = Wants(25, "Pikachu", 20, 50)
    assert view_gts.wanted_text(wants) == "皮卡丘，等级 20 到 50"
    assert wants.name == "Pikachu" and wants.species == 25


def test_remote_gts_facts_use_pkhex_chinese_names_and_leave_trainer_names(monkeypatch):
    monkeypatch.setattr(view_gts, "Sprite", lambda *a, **kw: SimpleNamespace(control=ft.Container()))
    shown = dict(species="Pikachu", species_id=25, level=50, nature="Timid", ability="Static",
                 ball="Poké Ball", held_item="Light Ball", moves=["Thunderbolt"], ot="East", shiny=True)
    view = SimpleNamespace(app=None)
    card = view_gts.GtsView._about(view, shown, "swsh")
    text = "\n".join(c.value for c in walk(card) if isinstance(c, ft.Text))
    for term in ("皮卡丘", "胆小", "静电", "精灵球", "电气球", "十万伏特", "原始训练家：East"):
        assert term in text
    assert shown["held_item"] == "Light Ball" and shown["ot"] == "East"


def test_bank_editor_chinese_choices_save_ids_and_reject_duplicate_moves():
    info = dict(nickname="My Pikachu", species="皮卡丘", level=50, move_ids=[85, 98], held_item_id=236)
    view = SimpleNamespace(app=SimpleNamespace(page=SimpleNamespace(pop_dialog=lambda: None)))
    entry = SimpleNamespace(game="swsh")
    editor = EditDialog(view, entry, info, [{"id": 85, "name": "十万伏特"}, {"id": 98, "name": "电光一闪"}],
                        [{"id": 236, "name": "电气球"}])
    assert editor._changes() == {}
    assert next(o for o in editor.moves[0].options if o.key == "85").text == "十万伏特"
    editor.level.value = "51"
    editor.item.value = NONE
    assert editor._changes() == {"level": 51, "held_item": 0}
    editor.moves[1].value = "85"
    assert editor._changes() == "招式不能重复。"


def test_pkhex_plain_chinese_report_folds_move_errors_and_preserves_detailed_report(tmp_path, monkeypatch):
    import base64
    from gui.localization import SERVICE
    from pokeldn import pokemon

    monkeypatch.setattr(pokemon, "POKEMON", tmp_path)
    service = pokemon.Service()
    trainer = dict(ot="POKELDN", tid=12345, sid=54321, language=2, gender=0)
    try:
        data = base64.b64decode(service.make("swsh", 25, trainer)["data"])
        fields = {"moves": [620, 621]}
        english = service.check_bytes("swsh", data, fields=fields)
        chinese = SERVICE.check_bytes("swsh", data, fields=fields)
    finally:
        service.close()
    assert not english["legal"] and not chinese["legal"]
    assert "moves are not legal" in english["problems"]
    assert "招式不合法" in chinese["problems"]
    assert "Invalid Move" not in chinese["problems"]
    assert chinese["report"] != english["report"]
    assert chinese["move_ids"] == english["move_ids"] == [620, 621]
