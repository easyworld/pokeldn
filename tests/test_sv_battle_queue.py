"""The server command queue codec against rounds a Scarlet 4.0.0 server produced (docs/sv_raid.md)."""
import json
import struct
from pathlib import Path

import pytest

from pokeldn.sv.battle import queue

ROUNDS = json.loads((Path(__file__).parent / "data" / "sv_raid_rounds.json").read_text())


@pytest.mark.parametrize("index", range(len(ROUNDS)))
def test_recorded_queue_round_trips(index):
    body = bytes.fromhex(ROUNDS[index]["body"])
    length = struct.unpack_from("<I", body, 0x238)[0]
    raw = body[0x23C:0x23C + length]
    commands = queue.decode(raw)
    assert commands[0] == (0xB5, (0,))
    assert b"".join(queue.encode(c, a) for c, a in commands) == raw


def test_truncated_queue_is_refused():
    raw = queue.encode(0x5A, (3, 506, 212))
    with pytest.raises(ValueError):
        queue.decode(raw[:-1])


def test_argument_is_truncated_to_its_field():
    assert queue.encode(0x51, (2, 0x103)) == queue.encode(0x51, (2, 3))
