"""Official card presentation keeps the original records and uses PKHeX reward IDs."""
import re

import pytest

ft = pytest.importorskip("flet")
from gui.localization import SERVICE, event_label, event_text
from gui.views.gifts import GiftBuilder
from pokeldn.swsh import events


def walk(control):
    yield control
    for child in [*(getattr(control, "controls", None) or []), getattr(control, "content", None)]:
        if isinstance(child, ft.Control):
            yield from walk(child)


def test_official_swsh_item_labels_use_record_ids_and_keep_original_cards():
    items = {item["id"]: item["name"] for item in SERVICE.names("swsh", "items")}
    for card in events.load():
        if card["group"] != "Items":
            continue
        original = dict(card)
        pairs = events.item_pairs(card["record"])
        expected = "，".join(f"{items[ident]} ×{quantity}" for ident, quantity in pairs)
        assert event_label("swsh", card) == expected
        # The archive title may be stale; the actual reward IDs are authoritative.
        assert event_label("swsh", {**card, "label": "outdated English title"}) == expected
        assert card == original


def test_all_official_swsh_cards_localize_summaries_and_non_pokemon_labels():
    for card in events.load():
        assert not re.search(r"[A-Za-z]{3,}", event_text(card["summary"])), card["key"]
        label = event_label("swsh", card)
        assert re.search(r"[\u4e00-\u9fff]", label), card["key"]
        if card["group"] != "Pokemon":
            assert not re.search(r"[A-Za-z]{3,}", label), card["key"]
    assert event_text("Wolfe Coalossal (Gmax)") == "Wolfe 巨炭山（超极巨化）"
    assert event_text("Ash Pikachu (Partner Cap)") == "Ash 皮卡丘 （就决定是你了之帽子）"
    assert event_text("WCS22 Sinistea (Antique)") == "WCS22 来悲茶 （真品）"
    assert event_text("Eric Gastrodon (East)") == "Eric 海兔兽 （东海）"


@pytest.mark.parametrize("source, expected", [
    ("20 Battle Points", "20 对战点数"),
    ("600 Battle Points", "600 对战点数"),
    ("Added to the player's Battle Points", "增加玩家的对战点数"),
    ("Into the bag", "放入背包"),
    ("Coalossal, level 50, can Gigantamax", "巨炭山, 等级 50, 可超极巨化"),
    ("2 pieces of clothing", "2 件服装"),
])
def test_card_tooltip_matches_its_localized_visible_summary(source, expected):
    view = GiftBuilder.__new__(GiftBuilder)
    tile = view._tile("测试卡片", source, False, lambda e: None)
    assert tile.tooltip == expected
    assert expected in [c.value for c in walk(tile) if isinstance(c, ft.Text)]


def test_official_event_search_finds_rewards_by_the_chinese_item_name():
    from pokeldn.swsh import gift_builder

    view = GiftBuilder.__new__(GiftBuilder)
    view.game, view.module = "swsh", gift_builder
    view.value = {"event": "", "event_search": "特性胶囊"}
    control = view.events()
    texts = [c.value for c in walk(control) if isinstance(c, ft.Text)]
    expected = [event_label("swsh", c) for c in events.load()
                if c["group"] == "Items" and "特性胶囊" in event_label("swsh", c)]
    assert expected and all(label in texts for label in expected)
    assert f"{len(expected)} / {len(events.load())} 张卡片" in texts
