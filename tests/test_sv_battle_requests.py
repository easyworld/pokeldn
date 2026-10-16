"""A round's request block built from a station's type-6 command message (pokeldn.sv.battle.engine.requests),
against the action blocks of the type-0x15 records a Scarlet 4.0.0 server sent between two emulated
consoles (docs/sv_raid.md, Actions)."""
import json
from pathlib import Path

import pytest

from pokeldn.sv.battle.engine import requests

PAIRS = json.loads((Path(__file__).parent / "data" / "sv_raid_commands.json").read_text())


@pytest.mark.parametrize("index", range(len(PAIRS)))
def test_block_from_command_matches_the_servers_record(index):
    command, record = bytes.fromhex(PAIRS[index]["command"]), bytes.fromhex(PAIRS[index]["block"])
    built = requests.posted(0x15, [(command[0x19], command)])[:requests.BLOCK]
    differ = {i for i in range(requests.BLOCK) if built[i] != record[i]}
    assert differ <= set(requests.UNWRITTEN)


def test_a_command_rebuilt_from_its_actions_gives_the_same_block():
    command = bytes.fromhex(PAIRS[0]["command"])
    actions = [(int.from_bytes(command[0x28 + 16 * i:0x30 + 16 * i], "little"),
                int.from_bytes(command[0x30 + 16 * i:0x34 + 16 * i], "little")) for i in range(command[0x20])]
    assert actions[0][0] == requests.move(871, 4)
    slot = command[0x19]
    assert requests.posted(0x15, [(slot, requests.command(actions))]) == requests.posted(0x15, [(slot, command)])
