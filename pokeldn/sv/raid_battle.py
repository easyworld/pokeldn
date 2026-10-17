"""A Scarlet / Violet Tera Raid battle served from the host's station (docs/sv_raid.md, Serving the
battle): a plugin's battle server (docs/plugins.md, A battle server) and the stations the host keeps for
itself: our Pokemon (slot 0), the boss (slot 1) and the NPC partners. A console's battle messages go in
with `receive`; `poll` returns the battle-start frames for each console, the server's own and the
relayed messages of every station.

    battle = RaidBattle(factory, bootstrap, consoles={2})
    battle.start(now)
    battle.receive(2, message, now)
    for slot, frame in battle.poll(now): ...
"""

import heapq
import struct

from pokeldn import gen9
from pokeldn.sv import raid_partners

KEY = 0x007B
ADDRESS = 0x2713                        # setup +0x2c, the battle's port address
SERVER, RELAY = 1, 3                    # a frame's second address word: the server's step, a station's
EVERY = 5                               # the destination of a relayed station message
HEADER = 0x20
FRAME = struct.Struct("<HIIII")         # key, address, x, y, length
PARTY_RECORD = 0x158
BOSS, OURS = 1, 0
PLAYER_SLOTS = (0, 2, 3, 4)
POSITION = {0: 0, 2: 1, 3: 2, 4: 3}     # a player slot's battle position; the boss is at 4
BATTLER = {0: 1, 2: 3, 3: 4, 4: 5}      # a player slot's battler id; the boss is 2
BOSS_POSITION, BOSS_BATTLER = 4, 2
COMMAND = 0xC8                          # a type-6 command's body (docs/sv_raid.md, Actions)
REQUEST, NOTICE = 0x05, 0x46
FADE_END = 0x37                         # the fade-out's last message; answering it re-runs the time-up
ROUTE = (1, 2, 3, 4, 0)                 # a retail host's stations answered message 1 in this order
ANSWER_DELAY = 0.05                     # a local station answers this long after a message reaches it
END_WAIT = 5.0                          # after 0x37, how long the consoles' answers are waited for


def frame(x, y, message):
    """-> a battle-start frame on key 0x7b addressed (0x2713, x, y)."""
    return FRAME.pack(KEY, ADDRESS, x, y, len(message)) + bytes(message)


def unframe(raw):
    """-> (x, y, message) of a battle-start frame, or None."""
    raw = bytes(raw)
    if len(raw) < FRAME.size + HEADER:
        return None
    key, address, x, y, n = FRAME.unpack_from(raw)
    if key != KEY or address != ADDRESS or len(raw) != FRAME.size + n:
        return None
    return x, y, raw[FRAME.size:]


def answer(message, slot):
    """-> a station's answer to a server step: type + 1, the step's two counters, 5 and the slot."""
    return bytes([message[0] + 1]) + bytes(7) + message[8:0x18] + bytes([EVERY, slot]) + bytes(6)


def command(request, slot, move, boss_move):
    """-> a station's type-6 command for `request`: the slot's battler uses `move` on the boss, and the
    boss answers with `boss_move` on the slot's position (docs/sv_raid.md, Actions)."""
    body = bytearray(COMMAND)
    words = [(1 | BOSS_POSITION << 4 | move << 8, BATTLER[slot]),
             (1 | POSITION[slot] << 4 | boss_move << 8, BOSS_BATTLER)]
    body[0] = len(words)
    for i, (word, actor) in enumerate(words):
        struct.pack_into("<QQ", body, 8 + 16 * i, word, actor)
    return bytes([6]) + bytes(7) + request[8:0x18] + bytes([EVERY, slot]) + bytes(6) + bytes(body)


def first_move(record):
    """-> the first move a 0x158-byte encrypted party record knows."""
    moves = gen9.read(gen9.decrypt(bytes(record)))["moves"]
    return next((m for m in moves if m), 0)


def generated_partners(bootstrap, count=raid_partners.HOSTED):
    """-> the NPC partners' records from the bootstrap alone: the RaidPoint's randSeed and unlock stage
    draw the trainers (raid_partners.draw) and seed their records (raid_partners.record), at four
    fifths of the level of the Pokemon in slot 0."""
    seed, stage = struct.unpack_from("<QI", bootstrap, 5 * PARTY_RECORD + 0x3D8)
    level = int(0.8 * gen9.read(gen9.decrypt(bytes(bootstrap[:PARTY_RECORD])))["level"])
    return [raid_partners.record(seed, stage, i, level) for i in raid_partners.draw(seed, stage, count)]


class RaidBattle:
    """The battle server `factory(bootstrap, partners)` builds and the host's own stations for one
    bootstrap. `consoles` are the player slots a console holds (one console, at slot 2); every other slot, the boss
    included, is answered here: each odd step with its answer, a request (5) with a command in which
    the slot's Pokemon uses its first move on the boss and the boss its first move on that Pokemon.
    Every message the server reads, the consoles' own included, is relayed to each console (x 3, as
    a console host relays them), and each server frame that moved the battle sends, after that frame's
    messages, a notice 0x46 from slot 0. `over` is set once every console answered 0x37 or END_WAIT passed after it."""

    def __init__(self, factory, bootstrap, consoles=(2,), partners=None, moves=None):
        if set(consoles) != {2}:
            raise ValueError("a served battle seats one console, at slot 2")
        self.consoles = tuple(consoles)
        if partners is None:
            partners = generated_partners(bootstrap)
        self.server = factory(bytes(bootstrap), list(partners))
        records = {0: bootstrap[:PARTY_RECORD], 3: partners[0], 4: partners[1]}
        boss = first_move(bootstrap[4 * PARTY_RECORD:5 * PARTY_RECORD])
        self.moves = {s: (first_move(r), boss) for s, r in records.items()}
        self.moves.update(moves or {})
        self.local = [s for s in range(5) if s not in self.consoles]
        self.queue = []                 # (time, order, slot, message) the local stations will send
        self.order = 0
        self.out = []                   # (console slot, frame)
        self.ended_at = None
        self.answered_end = set()
        self.sent_types = []            # (slot, type) of every server message, in order
        self.over = False

    # --- in and out --------------------------------------------------------------------------------

    def start(self, now):
        """The server's first frame: the battle timer and Wild::Setup, then message 1."""
        self._serve(lambda: self.server.start(now))

    def receive(self, slot, message, now):
        """A console's battle message (32-byte header and body) from the console at `slot`."""
        message = bytes(message)
        if self.ended_at is not None:
            if message[0] == FADE_END + 1:
                self.answered_end.add(slot)
            return
        self._advance(now)
        self._read(slot, message)

    def poll(self, now):
        """-> [(console slot, frame)] due by `now`: the server's frames up to `now`, the local stations'
        answers that fell due on the way, and what each produced."""
        if self.ended_at is None:
            self._advance(now)
        elif now >= self.ended_at + END_WAIT or self.answered_end >= set(self.consoles):
            self.over = True
        out, self.out = self.out, []
        return out

    # --- the stations ------------------------------------------------------------------------------

    def _advance(self, now):
        """Server frames up to `now`, with each local answer read at its own time."""
        while self.queue and self.queue[0][0] <= now and self.ended_at is None:
            t, _, slot, message = heapq.heappop(self.queue)
            if t > self.server.t:
                self._serve(lambda: self.server.run(t))
            self._read(slot, message)
        if self.ended_at is None and now > self.server.t:
            self._serve(lambda: self.server.run(now))

    def _read(self, slot, message):
        """A station's message into the server, relayed to every console, and one frame after it."""
        for console in self.consoles:
            self.out.append((console, frame(RELAY, EVERY, message)))
        self.server.receive(slot, message)
        self._serve(lambda: self.server.run(self.server.t + 1 / 30))

    def _serve(self, run):
        """Run server frames, a notice for each that moved, then route what the server queued."""
        moved = run()
        t = self.server.t
        for slot in ROUTE:
            for message in self.server.sent(slot):
                self.sent_types.append((slot, message[0]))
                if slot in self.consoles:
                    self.out.append((slot, frame(SERVER, slot, message)))
                    continue
                reply = self._reply(slot, message)
                if reply is not None:
                    heapq.heappush(self.queue, (t + ANSWER_DELAY * (1 + len(self.queue)), self.order,
                                                slot, reply))
                    self.order += 1
        notice = bytes([NOTICE]) + bytes(0x17) + bytes([EVERY, OURS]) + bytes(6) + bytes(4)
        for console in self.consoles:
            self.out += [(console, frame(RELAY, EVERY, notice))] * moved
        if self.ended_at is None and all((s, FADE_END) in self.sent_types for s in range(5)):
            self.ended_at = t
            self.queue.clear()

    def _reply(self, slot, message):
        kind = message[0]
        if kind == REQUEST and slot in self.moves:
            return command(message, slot, *self.moves[slot])
        if kind & 1 and kind not in (REQUEST, FADE_END):
            return answer(message, slot)
        return None
