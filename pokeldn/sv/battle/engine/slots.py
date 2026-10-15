"""Battle client slots: which slot a party position maps to in each battle mode."""

from pokeldn.sv.battle.machine import lifted

_MODE1_A = (2, 2, 2, 0, 2)      # 0x3c6a304
_MODE1_B = (3, 3, 3, 3, 5)      # 0x3c6a318


@lifted(0xE7E2A0)
def slot_matches(m, mode, rule, slot, *_):
    mode &= 0xFFFFFFFF; rule &= 0xFF; slot = slot & 0xFFFFFFFF
    slot = slot - (1 << 32) if slot & 0x80000000 else slot
    if slot > 4:
        return 0
    if (5 if mode > 2 else 0) == slot:
        return 1
    if mode == 2:
        v = 2 if rule else 5
    elif mode in (0, 1):
        v = 1
    else:
        v = 5
    if v == slot:
        return 1
    if mode == 2:
        v = 3 if rule > 1 else 5
    elif mode == 1:
        v = _MODE1_A[rule - 1] if 0 <= rule - 1 < 5 else 0
    else:
        v = 5
    if v == slot:
        return 1
    if mode == 2:
        w = 5 if rule < 3 else 4
    elif mode == 1:
        w = _MODE1_B[rule - 1] if 0 <= rule - 1 < 5 else 1
    else:
        w = 5
    if w == slot:
        return 1
    return int((1 if mode == 2 else 5) == slot)


def _slot_counts(mode, rule):
    if mode == 0:
        return (1, 1, 0, 0, 0, 9)
    if mode == 1:
        if 1 <= rule <= 3:
            return (1, 1, 1, 1, 0, 7)
        return {4: (2, 1, 0, 1, 0, 7), 5: (1, 1, 1, 0, 0, 8)}.get(rule, (2, 2, 0, 0, 0, 7))
    if mode == 2:
        return ((1, 6, 0, 0, 0, 4), (1, 6, 1, 0, 0, 3), (1, 6, 1, 1, 0, 2))[rule] if rule < 3 \
            else (1, 6, 1, 1, 1, 1)
    return (0, 0, 0, 0, 0, 11)


@lifted(0xFF9128)
def positions_of_slot(m, mode, rule, slot, *_):
    """How many of the battle's ten positions belong to client slot `slot` (5 = none)."""
    slot &= 0xFFFFFFFF
    return _slot_counts(mode & 0xFFFFFFFF, rule & 0xFF)[slot] if slot <= 5 else 0


# Position -> client slot (5 = none), positions 0..10 (0x3c6a348 .. 0x3c6a424, 0x44ee590).
_POS_MODE0 = (0, 1) + (5,) * 9
_POS_MODE1 = {1: (0, 1, 2, 3), 2: (0, 1, 2, 3), 3: (0, 1, 2, 3), 4: (0, 1, 0, 3), 5: (0, 1, 2)}
_POS_MODE1_OTHER = (0, 1, 0, 1)
_POS_MODE2 = (0, 2, 3, 4, 1, 1, 1, 1, 1, 1, 5)


def slot_of_position(mode, rule, pos):
    if pos > 10:
        return 5
    if mode == 0:
        return _POS_MODE0[pos]
    if mode == 1:
        row = _POS_MODE1.get(rule, _POS_MODE1_OTHER)
        return row[pos] if pos < len(row) else 5
    if mode == 2:
        empty = {0: (1, 2, 3), 1: (2, 3), 2: (3,)}.get(rule, ())
        return 5 if pos in empty else _POS_MODE2[pos]
    return 5


@lifted(0x1153868)
def client_of_position(m, o, pos, out_slot, out_index, *_):
    """The client slot holding battle position `pos`, and how many earlier positions it holds."""
    setup = m.u64(o + 8)
    mode, rule, pos = m.u32(setup + 0x36C), m.u8(setup + 0x370), pos & 0xFF
    slot = slot_of_position(mode, rule, pos)
    m.put(out_slot, 1, slot)
    count = 0 if slot == 5 else sum(slot_of_position(mode, rule, p) == slot for p in range(pos))
    m.put(out_index, 1, count)
    # x0 is left at the table 0x3c6a374 once the loop from 0x1153a54 runs, else it is still o.
    return m.main + 0x3C6A374 if pos >= 3 and slot != 5 else o


# Client slot -> side class per battle mode (0x3c6a450, 0x3c6a455, 0x3c6a45a); slot 5 or past: 2.
SIDE_CLASS = {0: (0, 1, 2, 2, 2), 1: (0, 1, 0, 1, 2), 2: (0, 1, 0, 0, 0)}


@lifted(0x113AA70)
def positions_on_side(m, mode, rule, side, *_):
    """How many battle positions belong to clients of side class `side`."""
    mode &= 0xFFFFFFFF; rule &= 0xFF; side &= 0xFF
    if mode == 0:
        return int(side in (0, 1))
    if mode == 1:
        n = 0
        for pos in range(10):
            client = slot_of_position(1, rule, pos)
            if client != 5 and SIDE_CLASS[1][client] == side:
                n += 1
        return n
    if mode == 2:
        return _mode2_side_count(rule, side)
    return 0


def _mode2_side_count(rule, side):
    a = int(side == 0); b = int(side == 1)
    if rule == 0:
        return a | b << 1 | b << 2
    if rule == 1:
        return (a << 1 | b) + (b | b << 2)
    if rule == 2:
        return (a << 1 | a) + (6 if b else 0)
    return (a | b << 1 | b << 2) + (a << 1 | a)


@lifted(0x157C76C)
def within_side(m, ids, pokecon, ident, *_):
    """Whether the battler `ident` stands at an index its side has room for."""
    from pokeldn.sv.battle.engine.getters import slot_of_id
    pos = slot_of_id(m, ids, ident) & 0xFF
    if pos >= 10:
        return 0
    owner = m.u64(pokecon + 0x290)
    with m.frame(8) as out:
        client_of_position(m, owner, pos, out, out + 4)
        client, idx = m.u8(out), m.u8(out + 4)
    if client == 5:
        return 0
    setup = m.u64(owner + 8)
    mode = m.u32(setup + 0x36C)
    side = SIDE_CLASS[mode][client] if mode in SIDE_CLASS and client <= 4 else 2
    return int(idx < positions_on_side(m, mode, m.u8(setup + 0x370), side))


def _position_slots(mode, rule):
    """Client slot of positions 0..9 as 0xfe161c walks them (5 = none)."""
    s0 = 5 if mode > 2 else 0
    s1 = (2 if rule else 5) if mode == 2 else (1 if mode in (0, 1) else 5)
    if mode == 2:
        s2, s3 = (3 if rule > 1 else 5), (5 if rule < 3 else 4)
    elif mode == 1:
        s2 = _MODE1_A[rule - 1] if 0 <= rule - 1 < 5 else 0
        s3 = _MODE1_B[rule - 1] if 0 <= rule - 1 < 5 else 1
    else:
        s2 = s3 = 5
    return (s0, s1, s2, s3) + (1 if mode == 2 else 5,) * 6


@lifted(0xFE161C)
def position_of(m, o, ident, *_):
    """The battle position (0..9) of the party member with id `ident`, or 10."""
    setup = m.u64(o + 8)
    p = m.call(m.main + 0x10E2DD4, m.u64(setup + 0x50), ident)
    client = 0
    if p:
        client = m.s(p, 4)
        client = 0 if client > 4 else client
        if client & 0xFF > 4:
            return 10
    client &= 0xFF
    base = m.u64(setup + 0x30) + 0x38 * client
    n = m.u8(base + 0x58)
    for i in range(n):
        member = m.u64(base + 0x28 + 8 * i) if i < m.u8(base + 0x58) else 0
        if member and m.vcall(member, 0x98) & 0xFFFFFFFF == ident & 0xFFFFFFFF:
            break
    else:
        return 10
    for pos, slot in enumerate(_position_slots(m.u32(setup + 0x36C), m.u8(setup + 0x370))):
        if slot == client:
            if i == 0:
                return pos
            i -= 1
    return 10
