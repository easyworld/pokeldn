"""Emerald gifts in the shared .pokegift file (docs/gifts.md): one variant, "emerald", serving
every Emerald cartridge, since nothing in it names a ROM address."""

from pokeldn import gifts
from pokeldn.frlg.gift import mg_server, wonder_card
from pokeldn.frlg.gift.stamp_rally import MysteryGiftDistribution
from pokeldn.rse.constants import EMERALD_RULES

TARGET = "emerald"


def validate(gift):
    if set(gift.variants) != {TARGET}:
        raise ValueError('An Emerald gift has one variant, "emerald".')
    distribution(gift.variants[TARGET])


def distribution(variant):
    if set(variant.data) != {"card", "ram_script"} or variant.options:
        raise ValueError("An Emerald gift is a Wonder Card and its delivery script.")
    card, script = variant.data["card"], variant.data["ram_script"]
    if len(card) != wonder_card.WONDER_CARD_SIZE:
        raise ValueError(f"An Emerald Wonder Card is {wonder_card.WONDER_CARD_SIZE} bytes.")
    EMERALD_RULES.flag_for_flag_id(int.from_bytes(card[:2], "little"))
    if not 0 < len(script) <= mg_server.MysteryGiftServer.MAX_RAM_SCRIPT_SIZE:
        raise ValueError("The delivery script must contain 1 to 995 bytes.")
    return MysteryGiftDistribution(bytes(card), bytes(script), game=TARGET)


def from_distribution(chosen, *, name):
    return gifts.Gift("rse", name, {TARGET: gifts.Variant({"card": bytes(chosen.card),
                                                          "ram_script": bytes(chosen.ram_script)})})
