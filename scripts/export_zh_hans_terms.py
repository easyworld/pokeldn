"""Freeze PKHeX's Chinese names and official item-card display messages into pack sources.

Run from this Chinese fork after building services/pkhex; the fork's helper supports
the natures and abilities name lists. The language pack itself needs no Python code.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pokeldn.pokemon import Service  # noqa: E402
from pokeldn.swsh import events  # noqa: E402

PACK = ROOT / "examples/plugins/zh_hans"


def export():
    english, chinese = Service(), Service(display_language="zh-Hans")
    terms, counts, messages = {}, {}, {}
    try:
        for game in ("frlg", "swsh", "sv", "za"):
            for kind in ("moves", "items", "balls", "natures", "abilities"):
                localized = {v["id"]: v["name"] for v in chinese.names(game, kind)}
                names = english.names(game, kind)
                for value in names:
                    if value["id"] in localized and value["name"] != localized[value["id"]]:
                        source, target = value["name"], localized[value["id"]]
                        terms[source] = target
                        # Archives and module tables use both ASCII and typographic apostrophes.
                        terms[source.replace("’", "'")] = target
                        terms[source.replace("'", "’")] = target
                counts[f"{game}:{kind}"] = len(names)
        items = {v["id"]: v["name"] for v in chinese.names("swsh", "items")}
        # A legacy archive can call Heavy Ball 'Heavy Poke Ball'; item IDs remain authoritative.
        for card in events.load():
            if card["group"] == "Items":
                messages[card["label"]] = "、".join(f"{items[ident]} ×{quantity}"
                                                         for ident, quantity in events.item_pairs(card["record"]))
        for source, target in list(terms.items()):
            if "Poké" in source:
                terms.setdefault(source.replace("Poké", "Poke"), target)
        # Names spellings in historical tables (PKHeX uses a space in current generations).
        for source in ("Dragon Breath", "Feather Dance"):
            if source in terms:
                terms[source.replace(" ", "")] = terms[source]
        source = "PKHeX.Core 26.8.26, paired by game and numeric ID"
        (PACK / "pkhex_terms.json").write_text(json.dumps({"source": source, "terms": terms, "counts": counts},
                                                  ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (PACK / "event_messages.json").write_text(json.dumps(messages, ensure_ascii=False, indent=2) + "\n",
                                                  encoding="utf-8")
        print(f"Exported {len(terms)} terms and {len(messages)} official item-card labels")
    finally:
        english.close()
        chinese.close()


if __name__ == "__main__":
    export()
