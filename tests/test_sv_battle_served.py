"""A raid battle served by the engine (pokeldn.sv.battle.engine.server.Server) from a Scarlet 4.0.0 host's
own bootstrap and the stations' messages its server received, against the frames that server sent the guest
between two emulated consoles (docs/sv_raid.md, The server's flow). The session needs Scarlet 4.0.0's image
and tables, read from the user's dump (game_files)."""
import base64
import json
import os
import re
import zlib
from pathlib import Path

import pytest

from pokeldn import gen9

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((Path(__file__).parent / "data" / "sv_raid_served.json").read_text())
EMULATOR_NAMES = {"Player", "POKELDN", "VMJOINER"}
HEADER = 18 + 0x20                 # the frame's address and length, then the message header
PADDING = set(range(4, 8)) | set(range(0x1A, 0x20))       # header bytes the game copies from its stack


def events():
    blob = zlib.decompress(base64.b64decode(DATA["blob"]))
    return [(kind, t, slot, blob[at:at + n]) for kind, t, slot, at, n in DATA["events"]]


def test_the_recorded_battle_names_only_an_emulated_player():
    boot = bytes.fromhex(DATA["bootstrap"])
    data = boot + b"".join(e[3] for e in events())
    assert {m.decode("utf-16-le") for m in re.findall(rb"(?:[\x20-\x7e]\x00){4,}", data)} <= EMULATOR_NAMES
    assert not re.search(rb"u-[0-9a-z]{20}", data)
    owners = {gen9.read(gen9.decrypt(boot[o:o + 0x158]))["ot_name"] for o in (0, 0x158, 0x560)}
    assert owners <= EMULATOR_NAMES | {""}


def game_files():
    """Scarlet 4.0.0's image and tables (pokeldn.sv.battle.game) from the cache in POKELDN_SV_GAME_CACHE
    (default scratchpad/sv/game), prepared there first from the dump when POKELDN_SV_UPDATE,
    POKELDN_SV_BASE and POKELDN_KEYS name it."""
    from pokeldn.sv.battle import game
    cache = Path(os.environ.get("POKELDN_SV_GAME_CACHE", ROOT / "scratchpad" / "sv" / "game"))
    if game.ready(cache):
        return game.load(cache)
    dump = [os.environ.get(v) for v in ("POKELDN_SV_UPDATE", "POKELDN_SV_BASE", "POKELDN_KEYS")]
    if not all(dump):
        pytest.skip("needs Scarlet 4.0.0's image and tables: POKELDN_SV_GAME_CACHE, or the dump "
                    "in POKELDN_SV_UPDATE, POKELDN_SV_BASE and POKELDN_KEYS")
    cache.mkdir(parents=True, exist_ok=True)
    return game.prepare(*dump, cache)


@pytest.fixture(scope="module")
def session():
    from pokeldn.sv.battle import standalone
    return standalone.battle(game_files(), bytes.fromhex(DATA["bootstrap"]), slot=0)   # the host's slot 0


def serve(m, n):
    from pokeldn.sv.battle.engine import server
    srv = server.Server(m, n)
    ev = events()
    srv.clock(ev[0][1])
    srv.setup()
    srv.run()
    ours = []
    for kind, t, slot, data in ev:
        ours += srv.handle([(slot, data)] if kind == "in" else [], t)[2]
    return ours, [e[3] for e in ev if e[0] == "out"]


def unwritten(frame):
    """The offsets the game never writes: header padding, and a round's or capture's request block bytes."""
    from pokeldn.sv.battle.engine import requests
    out = {HEADER - 0x20 + i for i in PADDING}
    if frame[HEADER - 0x20] in (0x15, 0x23, 0x25):
        out |= {HEADER + i for i in requests.UNWRITTEN}
    return out


def test_the_served_battle_sends_the_guest_the_servers_frames(session):
    m, n = session
    ours, wire = serve(m, n)
    assert len(ours) == len(wire) == 24
    for i, (a, b) in enumerate(zip(ours, wire)):
        skip = unwritten(b)
        assert len(a) == len(b) and [o for o in range(len(a)) if a[o] != b[o] and o not in skip] == [], i
    assert [f[HEADER - 0x20] for f in wire[-3:]] == [0x25, 0x29, 0x49]


POSITION = {0: 0, 2: 1, 3: 2, 4: 3}        # a player slot's battle position; the boss is at 4
BATTLER = {0: 1, 2: 3, 3: 4, 4: 5}          # a player slot's battler id; the boss is 2


def command(req, slot, player_move, boss_move):
    """A station's type-6 command for request `req` (docs/sv_raid.md, Actions): the slot's battler uses
    `player_move` on the boss, and the boss answers with `boss_move` on the slot's position."""
    body = bytearray(0xC8)
    body[0] = 2
    words = [(1 | 4 << 4 | player_move << 8, BATTLER[slot]), (1 | POSITION[slot] << 4 | boss_move << 8, 2)]
    for i, (w, a) in enumerate(words):
        body[8 + 16 * i:16 + 16 * i] = w.to_bytes(8, "little")
        body[16 + 16 * i:24 + 16 * i] = a.to_bytes(8, "little")
    return bytes([6]) + bytes(7) + req[8:0x18] + bytes([5, slot]) + bytes(6) + bytes(body)


def answering_stations(srv, case):
    """The recorded station messages up to the case's cut, then stations answering every odd message sent
    from answer_from on (type + 1, its step and round, 5 and the slot) after `answer` seconds, except the
    unanswered types, requests (5) with a command of the case's two moves when it has them, and the clock
    in `tick` steps to `end`; returns (slot, message) the server sent from the cut on, in order."""
    import heapq
    cut, unanswered = case["cut"], set(case["unanswered"])
    q = [(t, i, slot, data) for i, (kind, t, slot, data) in enumerate(events()) if kind == "in" and t <= cut]
    k = len(q)
    t = cut
    while t < case["end"]:
        t += case["tick"]
        q.append((t, k, None, None)); k += 1
    heapq.heapify(q)
    out = []
    while q:
        t, _, slot, data = heapq.heappop(q)
        srv.handle([(slot, data)] if slot is not None else [], t, stations=())
        for s in range(5):
            for msg in srv.sent(s):
                if t >= cut:
                    out.append((s, msg))
                if t < case["answer_from"]:
                    continue
                if msg[0] == 5 and case["commands"] and s in POSITION:
                    reply = command(msg, s, *case["commands"])
                elif msg[0] & 1 and msg[0] not in unanswered:
                    reply = bytes([msg[0] + 1]) + bytes(7) + msg[8:0x18] + bytes([5, s]) + bytes(6)
                else:
                    continue
                heapq.heappush(q, (t + case["answer"], k, s, reply)); k += 1
    return out


def game_case(name):
    """Scarlet's own server code on the same session (scratchpad/battle/timeup/make_timeup_data.py): the case
    and every message it sent each slot from the cut on."""
    case = json.loads((Path(__file__).parent / "data" / f"{name}.json").read_text())
    blob = zlib.decompress(base64.b64decode(case["blob"]))
    return case, [(slot, blob[at:at + size]) for slot, at, size in case["messages"]]


def served_case(name):
    from pokeldn.sv.battle import standalone
    from pokeldn.sv.battle.engine import server
    case, games = game_case(name)
    m, n = standalone.battle(game_files(), bytes.fromhex(DATA["bootstrap"]), slot=0)
    srv = server.Server(m, n)
    srv.clock(events()[0][1])
    srv.run()
    ours = answering_stations(srv, case)
    for s in range(5):
        a = [msg for slot, msg in ours if slot == s]
        b = [msg for slot, msg in games if slot == s]
        assert [x[0] for x in a] == [x[0] for x in b], s
        for i, (x, y) in enumerate(zip(a, b)):
            skip = {o - 18 for o in unwritten(bytes(18) + y)}
            assert len(x) == len(y) and [o for o in range(len(x)) if x[o] != y[o] and o not in skip] == [], (s, i)
    return games


def test_the_battle_timer_running_out_ends_the_raid_as_the_games_server_does():
    """Past the battle timer the game's server sent each slot the boss's last timed round, then 0x2b (slot 0,
    outcome 0, decided by 2), 0x35 and 0x37."""
    games = served_case("sv_raid_timeup")
    assert [msg[0] for slot, msg in games if slot == 2] == [0x15, 0x2B, 0x35, 0x37]
    assert games[5][1][0x20:] == bytes.fromhex("000000000200")


def test_a_raid_the_boss_wins_by_fainting_the_players_ends_as_the_games_server_does():
    """Stations whose Pokemon use Growl on the boss while the boss answers with move 0x1cc on them: the game's
    server sent each fainted slot 0x21, every slot the revival rounds 0x23, and, once the faints had run the
    battle timer out, 0x2b (outcome 0, decided by 2), 0x35 and 0x37."""
    games = served_case("sv_raid_boss_wins")
    kinds = [msg[0] for slot, msg in games if slot == 2]
    assert 0x21 in kinds and 0x23 in kinds and kinds[-3:] == [0x2B, 0x35, 0x37]
    assert [msg for slot, msg in games if slot == 2 and msg[0] == 0x2B][0][0x20:] == bytes.fromhex("000000000200")
