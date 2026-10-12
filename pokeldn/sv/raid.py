"""A Tera Raid on 0x80 port 0, both roles, as pure state machines: the lobby, the battle bootstrap
and the start of the battle (docs/sv_raid.md). A raid message is a game message (`pokeldn.sv.trade`)
whose body is the game's serializer header and a payload. `RaidHost.actions` and
`RaidGuest.tick` return what to send; the launcher owns Pia, sequences and retransmits.
"""

import struct

from pokeldn import gen9
from pokeldn.ldn import channel_table as tables, reliable5
from pokeldn.sv import lz4, raid_encounter, raid_partners, streams, trade

KEY_LOBBY = 0x3380
KEY_BATTLE = 0x3480
KEY_LOAD = 0x0132
# The handler keys a raid host announces on 0x7C port 1: a Link Trade's four, then the raid's two.
CHANNEL_KEYS = (0x007B, 0x0132, 0x0232, 0x0332, KEY_LOBBY, KEY_BATTLE)
KIND_DESCRIPTOR, KIND_STATE, KIND_POKEMON, KIND_BOOTSTRAP, KIND_COUNTDOWN = 0x2C, 0x2D, 0x2E, 0x2F, 0x30
COMPRESSION_NONE, COMPRESSION_LZ4 = 0, 2
SERIALIZER_HEADER = struct.Struct("<HII4s")      # counter, compression, plain size, four unread bytes

# Lua chunk be21e654, proto 0.30822: 0 not ready, 1 ready, 12 start, 13 its answer, 24 entering the
# lobby, 30 refused (docs/sv_raid.md, The lobby).
STATE_NOT_READY, STATE_IDLE, STATE_READY, STATE_START, STATE_STARTED = 0x00, 0x18, 0x01, 0x0C, 0x0D

# What a retail host and a retail guest sent, by the prefix the game dispatches on.
CONSOLE_POKEMON = trade.build(KEY_LOBBY, KIND_POKEMON, 1)
CONSOLE_STATE = trade.build(KEY_LOBBY, KIND_STATE, 1)
CONSOLE_LOADING = trade.build(KEY_LOAD, 0x6E)
CONSOLE_LOADED = trade.build(KEY_LOAD, 0x73)
BATTLE = trade.build(KEY_BATTLE, 0x93, 1)
# The host's two loading transitions and its six battle-start messages, as a retail host sent them.
# The handoff's `07265a` and `ceaf29` and LOADED's `6f74` are unwritten padding (docs/sv_raid.md, The lobby).
LOADED = bytes.fromhex("320173000400000000000800000000006f740100000001000000")
BATTLE_READY = bytes.fromhex("803493010400000000000400000000000000ed030000")
HANDOFF = tuple(bytes.fromhex(h) for h in (
    "7b0013270000010000000200000020000000010000000000000001000000000000000000000000000000050507265a000000",
    "7b00132700000300000005000000240000004600000000000000000000000000000000000000000000000500ceaf2900000000000000",
    "7b00132700000300000005000000200000000200000000000000010000000000000000000000000000000501000000000000",
    "7b00132700000300000005000000200000000200000000000000010000000000000000000000000000000503000000000000",
    "7b00132700000300000005000000200000000200000000000000010000000000000000000000000000000504000000000000",
    "7b00132700000300000005000000200000000200000000000000010000000000000000000000000000000500000000000000"))

COMPLETE = reliable5.FLAG_APPLICATION_DATA | reliable5.FLAG_MESSAGE_START | reliable5.FLAG_MESSAGE_END
COMPLETE_ZLIB = COMPLETE | reliable5.FLAG_ZLIB
FIRST = COMPLETE_ZLIB | reliable5.FLAG_IS_INITIALIZED
FRAGMENT_START = reliable5.FLAG_APPLICATION_DATA | reliable5.FLAG_MESSAGE_START
FRAGMENT_END_ZLIB = reliable5.FLAG_APPLICATION_DATA | reliable5.FLAG_MESSAGE_END | reliable5.FLAG_ZLIB
BOOTSTRAP_FRAGMENT = 1395         # where a retail host split its 0x012f message

# The battle bootstrap: four participants, the boss, the RaidPoint [0xe327fc].
PARTICIPANTS = 4
BOOTSTRAP_SIZE = 5 * gen9.SIZE_PARTY + 0x3E8
RAIDPOINT = 5 * gen9.SIZE_PARTY
POINT_SIZE = 0x3E8
POINT_NAME = "RaidPoint_POKELDN_0"
POINT_REWARDS = 0x0E4             # rows of item, quantity, rare, subject
POINT_SUMMARY = 0x3B8
REWARD_ROWS = (POINT_SUMMARY - POINT_REWARDS) // 16           # 45
SUBJECT_ALL = 0                   # the table's SubjectType: 0 everyone, 1 host, 2 guests, 3 once
POINT_PARTNERS = 0x3D8            # the partner seed, u64, then the host's unlock stage, u32
POINT_TIME = 0x30                 # the record's raidTimeData; zero leaves the console's own limits
# The crystal word: the save's raid content, 0 standard, 1 black (retail), 2 an event, 3 a seven-star
# event (Tera-Finder RaidContent); no retail event RaidPoint has been seen (docs/sv_raid.md).
CRYSTALS = {"standard": 0, "black": 1, "event": 2, "might": 3}
TERA_EMPTY = raid_encounter.TERA_NONE
FIRST_COUNTER = 0x0105            # the host's lobby counters run on from here, one per message
CONSOLES = PARTICIPANTS - 1       # station indices 1 to 3; our player is station 0

# Seconds after the port-2 answer for the lobby's first nine messages and the start, as a retail
# host's raid ran: the descriptor, state 0x18, our Pokemon, three timer steps, our state 0x01, two
# steps; then a step each time the timer, LOBBY_SECONDS at the first console's answer, ticks.
LOBBY = (("descriptor", 0.0), ("idle", 0.0), ("pokemon", 0.0), ("timer", 0.726), ("timer", 1.758),
         ("timer", 2.748), ("ready", 3.192), ("timer", 3.757), ("timer", 4.787))
START_AT = 5.393
LOBBY_SECONDS = 180               # a retail host's lobby; the timer is the seconds left
# After the first battle-start message: when the six leave, and each one's lowest pending.
HANDOFF_AT = (0.0, 0.0, 0.101, 0.121, 0.161, 0.181)
HANDOFF_LOWEST = (None, 0, 0, 2, 3, None)
GATE_MARGIN = 0.05                # a gated message leaves this long after its milestone
RETRY = 0.5                       # the raid Net 0x50 and Session update repeat until answered
LINGER = 5.0                      # the handover starts this long after the twentieth message
HANDOVER_WAIT = 20.0              # at most this long after the first console's, for the others
# A leaving host's Session type 7, Net 0x11 is-migrating and NetStartHostMigration: repeat and give-up
# times (`0x6df050`, `0x6defb8`, `0x6ac68c`, `0x6aca98`, `0x6ac984`; docs/sv.md, Leaving).
MIGRATION_REPEAT, MIGRATION_WAIT = 1.0, 5.0
STATUS_REPEAT, STATUS_WAIT = 0.5, 4.0
HANDOVER_REPEAT, HANDOVER_SPAN, HANDOVER_SPAN_UNANSWERED = 0.3, 4.0, 2.0
STATION_LIST_RETRY = 2.0          # a retail raid host resends its Session station list this often


def channel_table():
    return tables.build([(struct.pack("<II", key & 0xFF, key >> 8), True) for key in CHANNEL_KEYS])


def message(key, kind, step, counter, payload, *, compression=COMPRESSION_NONE, size=None,
            unread=bytes(4)):
    """-> a serialized raid message: the game message header, then the serializer header."""
    payload = bytes(payload)
    return (trade.build(key, kind, step)
            + SERIALIZER_HEADER.pack(counter, compression, len(payload) if size is None else size,
                                     bytes(unread)) + payload)


def payload_of(raw):
    """-> the payload of a serialized raid message, decompressed when it says LZ4."""
    _, compression, size, _ = SERIALIZER_HEADER.unpack_from(raw, 4)
    body = raw[4 + SERIALIZER_HEADER.size:]
    return lz4.decompress(body, size) if compression == COMPRESSION_LZ4 else body


def state(counter, value, *, initial=False):
    body = (bytes.fromhex("080000000400040004000000") if initial else
            bytes.fromhex("0c000000000006000c00040006000000") + struct.pack("<II", value, 0))
    return message(KEY_LOBBY, KIND_STATE, 1, counter, body)


def state_of(raw):
    """-> the lobby state a 42-byte state message carries, or None."""
    if len(raw) != 42 or raw[:4] != CONSOLE_STATE:
        return None
    return struct.unpack_from("<I", raw, 34)[0]


def pokemon(counter, party_pk9):
    """-> the lobby message presenting a participant's 344-byte party record."""
    return message(KEY_LOBBY, KIND_POKEMON, 1, counter, gen9.encrypt(gen9.load(party_pk9)))


def pokemon_of(raw):
    """-> the plain party record a lobby Pokemon message carries, or None."""
    if raw[:4] != CONSOLE_POKEMON or len(raw) != 18 + gen9.SIZE_PARTY:
        return None
    try:
        return gen9.load(raw[18:])
    except ValueError:
        return None


def countdown(counter, value):
    body = bytes.fromhex("0c000000000006000800040006000000") + struct.pack("<I", value)
    return message(KEY_LOBBY, KIND_COUNTDOWN, 1, counter, body)


def descriptor(counter, raid):
    """-> what the lobby shows of the raid before the battle: species, form, stars, Tera, gender."""
    boss = raid.boss
    body = struct.pack("<11I", 0, gen9.internal_index(raid.species), boss["form"], 0, raid.stars,
                       raid.tera_type, boss["gender"], raid.row["identifier"], 0, 0x33, 0)
    return message(KEY_LOBBY, KIND_DESCRIPTOR, 1, counter, body)


def empty_participant():
    """-> the record a retail bootstrap holds in an empty participant slot: species 0, level 1,
    named Egg. An all-zero record crashed a console when its battle began."""
    return gen9.encrypt(gen9.write(
        bytes(gen9.SIZE_PARTY), nickname="Egg", current_hp=11, tera_type_original=TERA_EMPTY,
        tera_type_override=TERA_EMPTY, language=2, level=1, stats=(11, 5, 5, 5, 5, 5)))


def boss_record(raid):
    """-> the boss's encrypted party record."""
    return gen9.encrypt(gen9.write(bytes(gen9.SIZE_PARTY), **raid.boss))


def raid_point(raid, rewards=None, name=POINT_NAME, partner_seed=0, stage=None):
    """-> the 0x3e8-byte RaidPoint: identity, stars, crystal and catch level, the boss's HP
    coefficient and its 37-word action profile, the reward rows, the summary, the partner seed and
    the unlock stage that pick the NPC partners (the raid's own by default). The seed's rows keep
    retail's subjects and bonus rows; chosen `rewards` go to every player. Unknown words stay zero."""
    if rewards is not None:
        rows = tuple((item, quantity, 0, SUBJECT_ALL) for item, quantity in rewards)
    else:
        rows = raid.rows or tuple((item, quantity, 0, SUBJECT_ALL) for item, quantity in raid.rewards)
    if len(rows) > REWARD_ROWS:
        raise ValueError(f"a RaidPoint holds at most {REWARD_ROWS} reward rows")
    out = bytearray(POINT_SIZE)
    encoded = name.encode("ascii")
    if not encoded.startswith(b"RaidPoint_") or len(encoded) > 23:
        raise ValueError(f"a RaidPoint name is RaidPoint_ and at most 13 more characters, not {name!r}")
    out[:len(encoded)] = encoded
    out[0x18] = 0x40
    struct.pack_into("<IIII", out, 0x20, raid.stars, CRYSTALS[raid.content],
                     raid.row.get("capture_rate", 1), raid.row["capture_level"])
    struct.pack_into("<7I", out, POINT_TIME, *(raid.row.get("time") or (0,) * 7))
    struct.pack_into("<37I", out, 0x4C, *raid.row["boss_desc"])
    for index, row in enumerate(rows):
        struct.pack_into("<IIII", out, POINT_REWARDS + index * 16, *row)
    struct.pack_into("<7I", out, POINT_SUMMARY, raid.stars, gen9.internal_index(raid.species),
                     raid.boss["form"], raid.boss["gender"], raid.boss["level"], 0, raid.tera_type)
    if stage is None:
        stage = raid_partners.stage_of(raid.progress, raid.content)
    if not 0 <= stage <= raid_partners.SIX_STARS:
        raise ValueError(f"an unlock stage is 0 to {raid_partners.SIX_STARS}, not {stage}")
    struct.pack_into("<QI", out, POINT_PARTNERS, partner_seed, stage)
    return bytes(out)


def bootstrap(raid, participants, rewards=None, name=POINT_NAME, partner_seed=0, stage=None):
    """-> the 0xaa0 plaintext: up to four party records (None an empty slot), the boss, the
    RaidPoint."""
    if len(participants) > PARTICIPANTS:
        raise ValueError(f"a raid has at most {PARTICIPANTS} participants")
    records = [empty_participant() if p is None else gen9.encrypt(gen9.load(p)) for p in participants]
    records += [empty_participant()] * (PARTICIPANTS - len(records))
    return (b"".join(records) + boss_record(raid)
            + raid_point(raid, rewards, name, partner_seed, stage))


def bootstrap_message(plain, counter=FIRST_COUNTER + 10):
    if len(plain) != BOOTSTRAP_SIZE:
        raise ValueError(f"a bootstrap is {BOOTSTRAP_SIZE} bytes, not {len(plain)}")
    return message(KEY_LOBBY, KIND_BOOTSTRAP, 1, counter, lz4.compress(plain),
                   compression=COMPRESSION_LZ4, size=len(plain))


class RaidGroup:
    """The lobby a raid host shares with up to three consoles, one per station index: who is seated
    and ready, the timer, the start, the one bootstrap they all receive and the handover. The start
    waits until `players` consoles are seated and every one has sent state 0x01, or until the timer
    runs out. The bootstrap's partner seed and unlock stage pick the NPCs for the seats no console
    holds. `left` is set once the host may go."""

    def __init__(self, raid, pokemon_record, rewards=None, players=1, partner_seed=0, stage=None):
        if not 1 <= players <= CONSOLES:
            raise ValueError(f"a raid seats 1 to {CONSOLES} consoles, not {players}")
        self.raid = raid
        self.pokemon = gen9.load(pokemon_record)
        self.rewards = None if rewards is None else tuple(rewards)
        self.partners = partner_seed, stage
        # A list or a stage that does not fit raises before the radio.
        raid_point(raid, self.rewards, partner_seed=partner_seed, stage=stage)
        self.players = players
        self.members = {}                       # station index -> RaidHost
        self.opened_at = None
        self.started_at = None
        self.handover_at = None
        self.plain = None

    def seat(self, index, now):
        """-> the RaidHost for the console at station `index`, or None once the raid has started."""
        if self.started_at is not None or not 1 <= index <= CONSOLES:
            return None
        if self.opened_at is None:
            self.opened_at = now
        self.members[index] = RaidHost(self, index)
        self.members[index].accepted(now)
        return self.members[index]

    def leave(self, index):
        """The console at `index` left the network; before the start its seat is freed."""
        member = self.members.get(index)
        if member is not None and self.started_at is None:
            del self.members[index]
            if not self.members:
                self.opened_at = None           # the next console starts a fresh timer

    def present(self):
        return [m for _, m in sorted(self.members.items()) if not m.gone_at]

    def timer(self, now):
        return max(0, LOBBY_SECONDS - int(max(0.0, now - self.opened_at - LOBBY[3][1])))

    def started(self, now):
        if self.started_at is None and self.opened_at is not None:
            here = self.present()
            ready = len(here) >= self.players and all(m.ready for m in here)
            if (here and ready) or self.timer(now) == 0:
                self.started_at = now
        return self.started_at is not None

    def bootstrap(self):
        """-> the bootstrap plaintext: our record in slot 0, each console's in its station index."""
        if self.plain is None:
            slots = [self.pokemon] + [self.members[i].guest if i in self.members else None
                                      for i in range(1, CONSOLES + 1)]
            self.plain = bootstrap(self.raid, slots, self.rewards, POINT_NAME, *self.partners)
        return self.plain

    def next_host(self):
        """-> the station index the network goes to: the lowest still on it with its battle."""
        here = [m for m in self.present() if m.done_at is not None] or self.present()
        return here[0].index if here else None

    def due(self, now):
        """-> whether the handover begins: every console on the network has its battle."""
        if self.handover_at is None:
            here = self.present()
            done = [m.done_at for m in here if m.done_at is not None]
            if here and len(done) == len(here):
                self.handover_at = max(done)
            elif done and now >= min(done) + HANDOVER_WAIT:
                self.handover_at = now          # a console stuck loading holds no one back
        return self.handover_at is not None and now >= self.handover_at

    @property
    def left(self):
        return bool(self.members) and all(m.left for m in self.members.values())


class RaidHost:
    """The host's side of one console's raid, on 0x80 port 0: the lobby, then the bootstrap, the
    loading steps and six battle-start messages, each released by the console's previous step, then
    the network handed over as a leaving retail host hands it (to the lowest station index; the
    others draw the is-migrating status and NetStartHostMigration). `actions` -> [("app", seq,
    flags, lowest, payload) | ("net",) | ("session",) | ("migration",) | ("migrating",) |
    ("handover",)]; the launcher reports the console's messages, its acks, and its leaving."""

    def __init__(self, group, index):
        self.group = group
        self.index = index
        self.raid = group.raid
        self.pokemon = group.pokemon
        self.guest = None
        self.ready = False
        self.seen = {}                          # milestone -> when the console reached it
        self.sent = {}                          # our sequence -> when it left
        self.steps = {}                         # step name -> our sequence
        self.counter = FIRST_COUNTER
        self.accepted_at = None
        self.timer_sent = None
        self.net_at = self.session_at = None
        self.done_at = None
        self.gone_at = None
        self.departure = None                   # [phase, since, next send, span]
        self.left = False
        self.whole = None

    def accepted(self, now):
        """The console's port-2 join was answered: its lobby clock starts."""
        if self.accepted_at is None:
            self.accepted_at = now

    def on_message(self, payload, now):
        """A message the console sent on 0x80 port 0, inflated."""
        payload = bytes(payload)
        record, state_value = pokemon_of(payload), state_of(payload)
        if "start" not in self.steps:
            # A ready console resends its Pokemon to each newcomer; only a state withdraws Ready.
            if state_value == STATE_READY:
                self.ready = True
            elif state_value in (STATE_NOT_READY, STATE_IDLE):
                self.ready = False
        if record is not None and "start" not in self.steps:
            self.guest = record
            self._reach("guest_lobby", now)
        if state_value == STATE_STARTED and "start" in self.steps:
            self._reach("guest_start", now)
        if payload[:4] == CONSOLE_LOADING and "boot2" in self.steps:
            self._reach("loading", now)
        if payload[:4] == CONSOLE_LOADED and "boot2" in self.steps:
            self._reach("loaded", now)
        if payload[:4] == BATTLE and "loaded" in self.steps:
            self._reach("battle", now)

    def net_acked(self, now):
        if self.net_at is not None:
            self._reach("net_ack", now)

    def session_acked(self, now):
        if self.session_at is not None:
            self._reach("session_ack", now)

    def migration_acked(self, now):
        """The console's Session type 8 naming itself: our status goes next."""
        if self.departure and self.departure[0] == "migration":
            self._depart("status", now)

    def status_acked(self, now):
        """The console's Net 0x12 to the is-migrating status."""
        if self.departure and self.departure[0] == "status":
            self._depart("handover", now, HANDOVER_SPAN)

    def gone(self, now):
        """The console left the network: a client of a migrating host leaves to host its own."""
        if self.gone_at is None:
            self.gone_at = now
        if self.departure or self.group.started_at is not None:
            self.left = True

    def _depart(self, phase, now, span=None):
        self.departure = [phase, now, now, span]

    def _leaving(self, now):
        phase, since, _, span = self.departure
        if phase == "migration" and now - since >= MIGRATION_WAIT:
            self._depart("status", now)
        elif phase == "status" and now - since >= STATUS_WAIT:
            self._depart("handover", now, HANDOVER_SPAN_UNANSWERED)
        elif phase == "handover" and now - since >= span:
            self.left = True
            return []
        phase, _, due, _ = self.departure
        if now < due:
            return []
        repeat = {"migration": MIGRATION_REPEAT, "status": STATUS_REPEAT}.get(phase, HANDOVER_REPEAT)
        self.departure[2] = max(due + repeat, now)
        return [({"status": "migrating"}.get(phase, phase),)]

    def _reach(self, milestone, now):
        self.seen.setdefault(milestone, now)

    def _passed(self, *milestones, now):
        times = [self.seen[m] for m in milestones if m in self.seen]
        return bool(times) and now >= min(times) + GATE_MARGIN

    def _count(self):
        self.counter += 1
        return self.counter - 1

    def _lobby(self, now):
        """-> the next lobby step that may leave now, or None."""
        if not self._passed("guest_lobby", now=now):
            return None
        position = len(self.sent)
        if position < len(LOBBY):
            name, at = LOBBY[position]
            if now < self.accepted_at + at:
                return None
            return name
        if self.group.timer(now) != self.timer_sent:
            return "timer"
        if self.group.started(now) and now >= self.accepted_at + START_AT:
            return "start"
        return None

    def _build(self, name, now):
        """-> (flags, payload, lowest) of a lobby step."""
        if name == "descriptor":
            return FIRST, streams.compress(descriptor(self._count(), self.raid)), 1
        if name == "idle":
            return COMPLETE, state(self._count(), STATE_IDLE, initial=True), 1
        if name == "pokemon":
            return COMPLETE, pokemon(self._count(), self.pokemon), 1
        if name == "timer":
            self.timer_sent = self.group.timer(now)
            return COMPLETE, countdown(self._count(), self.timer_sent), None
        if name == "ready":
            return COMPLETE_ZLIB, streams.compress(state(self._count(), STATE_READY)), None
        return COMPLETE_ZLIB, streams.compress(state(self._count(), STATE_START)), None

    def _next(self, now):
        """-> (name, flags, payload, lowest) of the message that may leave now, or None."""
        if "start" not in self.steps:
            name = self._lobby(now)
            if name is None:
                return None
            return (name,) + self._build(name, now)
        if "boot1" not in self.steps:
            # A retail host sends the bootstrap once every member has answered the start (0.27140).
            if (self.guest is None or not self._passed("session_ack", now=now)
                    or not all("guest_start" in m.seen for m in self.group.present())):
                return None
            self.whole = bootstrap_message(self.group.bootstrap(), self._count())
            cut = min(BOOTSTRAP_FRAGMENT, len(self.whole) - 1)
            return "boot1", FRAGMENT_START, self.whole[:cut], None
        if "boot2" not in self.steps:
            cut = min(BOOTSTRAP_FRAGMENT, len(self.whole) - 1)
            return "boot2", FRAGMENT_END_ZLIB, streams.compress(self.whole[cut:]), self.steps["boot1"]
        if "loaded" not in self.steps:
            if not self._passed("loading", "loaded", now=now):
                return None
            return "loaded", COMPLETE, LOADED, None
        if "battle" not in self.steps:
            if not self._passed("loaded", now=now):
                return None
            return "battle", COMPLETE, BATTLE_READY, None
        first = self.steps.get("handoff0")
        n = sum(1 for name in self.steps if name.startswith("handoff"))
        if n == len(HANDOFF):
            return None
        if n == 0 and not self._passed("battle", now=now):
            return None
        if n and now < self.sent[first] + HANDOFF_AT[n]:
            return None
        lowest = None if HANDOFF_LOWEST[n] is None else (first or len(self.sent) + 1) + HANDOFF_LOWEST[n]
        return f"handoff{n}", COMPLETE_ZLIB, streams.compress(HANDOFF[n]), lowest

    def actions(self, now):
        if self.accepted_at is None or self.left:
            return []
        if self.departure:
            return self._leaving(now)
        if self.gone_at is not None:
            return []
        if "start" in self.steps and self.group.due(now):
            self._depart("migration" if self.group.next_host() == self.index else "status", now)
            return self._leaving(now)
        if self.done_at is not None:
            return []
        out = []
        while True:
            step = self._next(now)
            if step is None:
                break
            name, flags, payload, lowest = step
            seq = len(self.sent) + 1
            out.append(("app", seq, flags, seq if lowest is None else lowest, payload))
            self.sent[seq] = now
            self.steps[name] = seq
        if f"handoff{len(HANDOFF) - 1}" in self.steps and self.done_at is None:
            self.done_at = now + LINGER
        if ("net_ack" not in self.seen and self._passed("guest_start", now=now)
                and (self.net_at is None or now >= self.net_at + RETRY)):
            self.net_at = now
            out.append(("net",))
        if ("session_ack" not in self.seen and self._passed("net_ack", now=now)
                and (self.session_at is None or now >= self.session_at + RETRY)):
            self.session_at = now
            out.append(("session",))
        return out


class RaidGuest:
    """The guest's side: its lobby state and Pokemon, Ready after `ready_delay`, and the answer to
    the host's start. `on_message` takes the host's messages on 0x80 port 0, inflated; `tick`
    -> [(flags, payload)] to send there in order."""

    def __init__(self, pokemon_record, ready_delay=2.0):
        self.pokemon = gen9.load(pokemon_record)
        self.ready_delay = ready_delay
        self.lobby_at = None
        self.counter = 0
        self.ready_sent = self.started = False
        self.start_seen = False

    def _next(self):
        self.counter += 1
        return self.counter

    def lobby(self, now):
        """-> the two messages that make the guest a lobby participant."""
        self.lobby_at = now
        return [(FIRST, streams.compress(state(self._next(), STATE_IDLE))),
                (COMPLETE, pokemon(self._next(), self.pokemon))]

    def on_message(self, payload):
        if state_of(bytes(payload)) == STATE_START:
            self.start_seen = True

    def tick(self, now):
        out = []
        if self.lobby_at is not None and not self.ready_sent and now >= self.lobby_at + self.ready_delay:
            self.ready_sent = True
            out.append((COMPLETE_ZLIB, streams.compress(state(self._next(), STATE_READY))))
        if self.ready_sent and self.start_seen and not self.started:
            self.started = True
            out.append((COMPLETE_ZLIB, streams.compress(state(self._next(), STATE_STARTED))))
        return out
