"""Battle client slots and positions: which slot a party position maps to in each battle mode, and the
side class of each position."""

from pokeldn.sv.battle.engine.calls import M32, _need, _s32, _tail
from pokeldn.sv.battle.machine import UnliftedCall, lifted

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


@lifted(0x1151988)
def slot_free(m, o, i, *_):
    i &= 0xFFFFFFFF
    if i >= 0x80000000:
        i -= 1 << 32
    return int(i < 6 and m.u8(o + i + 0x86) == 0)


@lifted(0x173F034)
def client_for_0xae(m, o, ctx, action, b, client, *_):
    """`client`, unless the action is 0xae: then (u8 +0xa: 7) the battler's own client slot, or (0) the
    result of 0x10e21c0 when the slots differ in a way 0x163f398 accepts."""
    client &= 0xFFFFFFFF
    pokecon = m.u64(o + 0x10)
    own = m.call(m.main + 0xFE161C, m.u64(pokecon + 0x290), m.vcall(b, 0x98) & 0xFFFFFFFF) & 0xFFFFFFFF
    if m.u16(action) != 0xAE:
        return client
    kind = m.u8(action + 0xA)
    if kind == 7:
        return own
    if kind != 0:
        return client
    if client & 0xFF != 10 and own & 0xFF != client & 0xFF \
            and m.call(m.main + 0x163F398, m.u64(m.u64(o + 0x10) + 0x290), own, client) & 1 == 0:
        return client
    x = m.call(m.main + 0x11440E8, m.u64(o + 0x10))
    return m.call(m.main + 0x10E21C0, ctx, m.u64(o + 0x10), b, 0xAE, x) & 0xFFFFFFFF


# Position -> client slot rows read by 0xc9c750: mode 0 (0x3c6a348), mode 1 by rule 1..5 (0x44fccb8 ->
# 0x3c6a3a0 x3, 0x3c6a3cc, 0x3c6a3f8) or any other rule (0x3c6a374), mode 2 (0x3c6a424).
_C9_MODE0 = (0, 1)
_C9_MODE1 = {1: (0, 1, 2, 3), 2: (0, 1, 2, 3), 3: (0, 1, 2, 3), 4: (0, 1, 0, 3), 5: (0, 1, 2)}
_C9_MODE1_OTHER = (0, 1, 0, 1)
_C9_MODE2 = (0, 2, 3, 4, 1, 1, 1, 1, 1, 1, 5)
_C9_MODE2_EMPTY = {0: 0x40E, 1: 0x40C}


@lifted(0xC9C750)
def side_of_position(m, mode, rule, pos, *_):
    """The side class (0x3c6a450 tables) of the client at battle position `pos`; 2 when none."""
    mode &= 0xFFFFFFFF; rule &= 0xFF; pos &= 0xFF
    if mode == 0:
        return SIDE[0][_C9_MODE0[pos]] if pos < 2 else 2
    if mode == 1:
        if pos > 10:
            return 2
        row = _C9_MODE1.get(rule, _C9_MODE1_OTHER)
        slot = row[pos] if pos < len(row) else 5
        return SIDE[1][slot] if slot <= 4 else 2
    if mode != 2 or pos > 10:
        return 2
    if rule in _C9_MODE2_EMPTY:
        if _C9_MODE2_EMPTY[rule] >> pos & 1:
            return 2
    elif pos == 10 or (rule == 2 and pos == 3):
        return 2
    return SIDE[2][_C9_MODE2[pos]]


SIDE = {0: (0, 1, 2, 2, 2), 1: (0, 1, 0, 1, 2), 2: (0, 1, 0, 0, 0)}   # 0x3c6a450, 0x3c6a455, 0x3c6a45a


@lifted(0x283D6A0)
def entry_mode_class(m, o, i, *_):
    """Tail call of 0x144e790 with the id of entry i (below 0x86) of [[o+0x38]+0x78], 0 when none."""
    i &= 0xFFFF
    ident = 0
    if i <= 0x85:
        e = m.u64(m.u64(m.u64(o + 0x38) + 0x78) + 8 + 8 * i)
        if e:
            ident = m.u32(e + 0xC)
    return m.call(m.main + 0x144E790, m.u64(m.u64(o + 8) + 0x290), ident)


@lifted(0x17D31E0)
def slot_in_f0(m, o, ident, *_):
    """Tail call of 0x1381420 on [[o+0x10]+0xf0]."""
    return m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), ident)


@lifted(0xE7E28C)
def client_in_battle(m, o, slot, *_):
    """Tail call of 0xe7e2a0 with the setup's mode and rule."""
    s = m.u64(o + 8)
    return m.call(m.main + 0xE7E2A0, m.u32(s + 0x36C), m.u8(s + 0x370), slot & 0xFF)


def _flag_2fd(m, e):
    """The byte table at 0x3c6a2fd, indexed as the game does (uxtw of a value at most 4)."""
    return int(m.u8(m.main + 0x3C6A2FD + (e & 0xFFFFFFFF)) != 0)


@lifted(0x15C04A4)
def same_side_ids(m, o, a, b, *_):
    """Tail call of 0x118ab58 on [[o+0x10]+0x290]."""
    return m.call(m.main + 0x118AB58, m.u64(m.u64(o + 0x10) + 0x290), a, b)


# Position -> client slot rows (5 = none): 0x3c6a348, 0x3c6a374, 0x3c6a3a0, 0x3c6a3cc, 0x3c6a3f8, 0x3c6a424.
_ROW_348 = (0, 1) + (5,) * 9
_ROW_374 = (0, 1, 0, 1) + (5,) * 7
_ROW_3A0 = (0, 1, 2, 3) + (5,) * 7
_ROW_3CC = (0, 1, 0, 3) + (5,) * 7
_ROW_3F8 = (0, 1, 2) + (5,) * 8
_ROW_424 = (0, 2, 3, 4, 1, 1, 1, 1, 1, 1, 5)


@lifted(0x127E444)
def position_used(m, o, pos, *_):
    """Whether battle position `pos` belongs to a client in the setup's mode and rule."""
    s = m.u64(o + 8)
    mode, rule, pos = m.u32(s + 0x36C), m.u8(s + 0x370), pos & 0xFF
    if mode > 2 or pos > 10:
        return 0
    if mode == 0:
        slot = _ROW_348[pos]
    elif mode == 1:
        if rule == 5:
            row = _ROW_3F8
        elif 1 <= rule <= 3:
            row = _ROW_3A0
        elif rule == 4:
            row = _ROW_3CC
        else:
            row = _ROW_374
        slot = row[pos]
    else:
        empty = (rule == 0 and 1 <= pos <= 3) or (rule == 1 and pos & 0xFE == 2) or (rule == 2 and pos == 3)
        slot = 5 if empty else _ROW_424[pos]
    return int(slot != 5)


@lifted(0x127E2B8)
def build_slot_table(m, out, s, *_):
    """Fill the 11 slot entries of `out` (8 bytes from +8, initialised 0x0000_0500_0000_0000) for the
    battle's 2, 4 or 10 slots (u32 [s+0x36c], table 0x3c69db8): a slot 0x127e444 accepts takes kind
    0xe1eea8 (+5) when that is not 5; then each slot's member (0x1153868 kind and index, the member list
    [s+0x30]) unless vf 0x200 says otherwise stores its id (vf 0x98) at +0 and in the map at +0x60
    (0xf785a8), or 0."""
    from pokeldn.sv.battle.machine import FUNCTIONS, UnliftedCall
    if 0xF785A8 not in FUNCTIONS:           # reached after the first writes
        raise UnliftedCall("main+0xf785a8")
    for k in range(11):
        m.put(out + 8 + 8 * k, 8, 0x50000000000)
    mode = m.u32(s + 0x36C)
    last = (1, 3, 9)[mode] if mode <= 2 else 3       # 0x3c69db8
    for i in range(last + 1):
        e = out + 8 + 8 * i
        if m.call(m.main + 0x127E444, m.u64(s + 0x290), i) & 1 and m.u8(e + 4) == 0:
            kind = m.call(m.main + 0xE1EEA8, m.u64(s + 0x290), i)
            if kind & 0xFF != 5:
                m.put(e + 4, 1, 1)
                m.put(e + 5, 1, kind)
                m.put(e, 4, 0)
    x0 = 0
    with m.frame(0x10) as f:
        for i in range(last + 1):
            e = out + 8 + 8 * i
            x0 = m.call(m.main + 0x1153868, m.u64(s + 0x290), i, f, f + 4)
            kind = m.u8(f)
            if kind == 5:
                continue
            idx = m.u8(f + 4)
            lst = m.u64(s + 0x30) + 0x38 * kind
            b = m.u64(lst + 0x28 + 8 * idx) if m.u8(lst + 0x58) > idx else 0
            if b == 0:
                m.put(e, 4, 0)
                continue
            x0 = m.vcall(b, 0x200)
            if x0 & 1:
                m.put(e, 4, 0)
                continue
            ident = m.vcall(b, 0x98) & 0xFFFFFFFF
            m.put(f + 8, 4, ident)
            m.put(e, 4, ident)
            x0 = m.call(m.main + 0xF785A8, out + 0x60, f + 8)
            m.put(x0, 1, i)
    return x0


@lifted(0x13DF9D4)
def side_slot(m, o, side, i, *_):
    side &= 0xFF; i &= 0xFFFFFFFF
    si = i if i < 0x80000000 else i - (1 << 32)
    if si > 0x12 or side > 1:
        return 0
    return (m.u64(o + 0x90) + side * 0x2F8 + i * 0x28 + 8) & 0xFFFFFFFFFFFFFFFF


# Battle mode 0, 1, 2 -> five-entry tables (0x3c6a450, 0x3c6a455, 0x3c6a45a).
_MODE_TABLES = {0: (0, 1, 2, 2, 2), 1: (0, 1, 0, 1, 2), 2: (0, 1, 0, 0, 0)}


@lifted(0x1142ECC)
def same_mode_class(m, o, a, b, *_):
    """Whether keys a and b fall in the same class under the setup's battle mode (+0x36c)."""
    a &= 0xFF; b &= 0xFF
    t = _MODE_TABLES.get(m.u32(m.u64(o + 8) + 0x36C))
    ca = t[a] if t and a < 5 else 2
    cb = t[b] if t and b < 5 else 2
    return int(ca == cb)


@lifted(0x2823478)
def side_flags(m, o, flags, count, code, *_):
    """Falls into 0x2823490 (the mode word [[o+8]+0x36c] is passed and unused): codes 0/1 set
    flags[0] = code, 4 sets 1, 5 sets 0, 3 also sets flags[count+1]; count ends as the entries set."""
    code &= 0xFF
    m.put(count, 1, 0)
    if code <= 1:
        m.put(flags, 1, code); n = 1
    elif code == 5:
        m.put(flags, 1, 0); n = m.u8(count) + 1
    elif code == 4:
        m.put(flags, 1, 1); n = m.u8(count) + 1
    elif code == 3:
        m.put(flags, 1, 0)
        k = (m.u8(count) + 1) & 0xFF
        m.put(count, 1, k)
        m.put(flags + k, 1, 1)
        n = m.u8(count) + 1
    else:
        n = 0
    m.put(count, 1, n)


@lifted(0x113AF40)
def position_of_side_index(m, mode, rule, side, index, *_):
    """The battle position (0..9) of the index-th position whose client is of side class `side`; 10 if none."""
    mode &= 0xFFFFFFFF; rule &= 0xFF; side &= 0xFF; index &= 0xFF
    if side > 1 or index > 5:
        return 10
    n = 0
    for pos in range(10):
        slot = slot_of_position(mode, rule, pos)
        cls = SIDE_CLASS[mode][slot] if mode in SIDE_CLASS and slot < 5 else 2
        if cls == side:
            if n == index:
                return pos
            n += 1
    return 10


_CLASS_TABLES = {0: 0x3C6A450, 1: 0x3C6A455, 2: 0x3C6A45A}


@lifted(0x142A758)
def allies_present(m, mode, rule, slot, *_):
    """How many other client slots (0..4) are present (0xe7e2a0) and of the same side class as `slot`."""
    mode &= 0xFFFFFFFF; slot &= 0xFFFFFFFF
    if mode in SIDE_CLASS:
        if slot < 5:
            mine = SIDE_CLASS[mode][slot]
        elif slot >= 0x80000000:   # signed compare: a negative slot indexes the table
            mine = m.u8(m.main + _CLASS_TABLES[mode] + slot)
        else:
            mine = 2
    else:
        mine = 2
    n = 0
    for s in range(5):
        if s == slot:
            continue
        if m.call(m.main + 0xE7E2A0, mode, rule, s) & 1:
            theirs = SIDE_CLASS[mode][s] if mode in SIDE_CLASS else 2
            if theirs == mine:
                n += 1
    return n & 0xFF


@lifted(0x1149478)
def allies_plus_1(m, setup, *_):
    return (m.call(m.main + 0x142A758, m.u32(setup + 0x36C), m.u8(setup + 0x370), 0) & 0xFF) + 1


@lifted(0xFA29D0)
def side_slot_0x95(m, o, side, *_):
    """Unless [[o+0x10]+0x38]+0x49b bit 0: find the last slot k > 0 of side's list (o + side*0x38: count
    u8 +0x58, objects from +0x28) whose vtable +0x208 says yes; then for each i < k, look up the key of
    (side, i) in the list at [[[[o+0x18]+0x290]+8]+0x50]+0x38 in the map at o+0x140; an entry whose +0x28
    list holds the static 0x46d3f08 and whose vtable +0xf8 is 0x95 gets vtable +0x1e8(slot k's +0x98)."""
    from pokeldn.sv.battle.engine.containers import find
    if m.u8(m.u64(m.u64(o + 0x10) + 0x38) + 0x49B) & 1:
        return
    side &= 0xFF
    row = o + side * 0x38
    c = m.u8(row + 0x58)
    if c == 0:
        return
    while True:
        k = (c - 1) & 0xFF
        if k == 0:
            return
        slot = row + k * 8 + 0x28
        if m.vcall(m.u64(slot), 0x208) & 1:
            break
        c -= 1
    guard, static = m.u64(m.main + 0x46D3F00), m.u64(m.main + 0x46D3F08)
    with m.frame(0x10) as kp:
        for i in range(k):
            node = m.u64(m.u64(m.u64(m.u64(m.u64(o + 0x18) + 0x290) + 8) + 0x50) + 0x38)
            key = 0
            while node:
                if m.u32(node + 0x14) == side and m.u8(node + 0x18) == i & 0xFF:
                    key = m.u32(node + 0x10)
                    break
                node = m.u64(node)
            m.put(kp, 4, key)
            if not find(m, o + 0x140, key, 4):
                continue
            if m.u64(m.call(m.main + 0xFA1B68, o + 0x140, kp)) == 0:
                continue
            obj = m.u64(m.call(m.main + 0xFA1B68, o + 0x140, kp))
            x = m.vcall(obj + 0x28, 0)
            if m.u8(guard) & 1 == 0:
                raise UnliftedCall("static 0x46d3f08 not built")
            while x:
                if x == static:
                    if m.vcall(obj, 0xF8) & 0xFFFF == 0x95:
                        v = m.vcall(m.u64(slot), 0x98)
                        m.vcall_void(m.u64(m.call(m.main + 0xFA1B68, o + 0x140, kp)), 0x1E8, v & 0xFFFFFFFF)
                    break
                x = m.u64(x)


# 11 u32 each, by mode [[o+8]+0x36c] and sub-mode [[o+8]+0x370] (0x3c6a348 .. 0x3c6a424).
_T_3C6A348 = (0, 1, 5, 5, 5, 5, 5, 5, 5, 5, 5)
_T_3C6A374 = (0, 1, 0, 1, 5, 5, 5, 5, 5, 5, 5)
_T_3C6A3A0 = (0, 1, 2, 3, 5, 5, 5, 5, 5, 5, 5)
_T_3C6A3CC = (0, 1, 0, 3, 5, 5, 5, 5, 5, 5, 5)
_T_3C6A3F8 = (0, 1, 2, 5, 5, 5, 5, 5, 5, 5, 5)
_T_3C6A424 = (0, 2, 3, 4, 1, 1, 1, 1, 1, 1, 5)


@lifted(0xE1EEA8)
def slot_class(m, o, i, *_):
    """Class of position i (0..10) under the battle's mode; 5 out of range or excluded."""
    p = m.u64(o + 8)
    mode, sub = m.u32(p + 0x36C), m.u8(p + 0x370)
    i &= 0xFF
    if i > 0xA or mode > 2:
        return 5
    if mode == 0:
        return _T_3C6A348[i]
    if mode == 1:
        if sub == 5:
            return _T_3C6A3F8[i]
        if 1 <= sub <= 3:
            return _T_3C6A3A0[i]
        return (_T_3C6A3CC if sub == 4 else _T_3C6A374)[i]
    if (sub == 0 and 1 <= i <= 3) or (sub == 1 and i & 0xFE == 2) or (sub == 2 and i == 3):
        return 5
    return _T_3C6A424[i]


@lifted(0x1365E90)
def clients_off_side(m, mode, rule, pos, *_):
    """How many of the clients 0..4 present in this mode (0xe7e2a0) map to a class other than the one
    of `pos` (tables 0x3c6a450 / 455 / 45a, 2 outside them)."""
    from pokeldn.sv.battle.engine.getters import _MODE_TABLES
    raw = (mode, rule)
    mode &= 0xFFFFFFFF; rule &= 0xFFFFFFFF; pos &= 0xFFFFFFFF
    n = 0
    for c in range(5):
        if m.call(m.main + 0xE7E2A0, *(raw if c == 0 else (mode, rule)), c) & 1 == 0:
            continue
        if mode not in _MODE_TABLES or 4 < (pos ^ 0x80000000) - 0x80000000:
            side = 2
        elif pos < 5:
            side = _MODE_TABLES[mode][pos]
        else:
            side = m.u8(m.main + 0x3C6A450 + 5 * mode + pos)
        n += side != (_MODE_TABLES[mode][c] if mode in _MODE_TABLES else 2)
    return n & 0xFF


def _class_of(m, mode, i):
    """Entry i of the mode's five-entry class table (0x3c6a450 + 5 * mode), indexed as a u32."""
    from pokeldn.sv.battle.engine.getters import _MODE_TABLES
    i &= 0xFFFFFFFF
    return _MODE_TABLES[mode][i] if i < 5 else m.u8(m.main + 0x3C6A450 + 5 * mode + i)


@lifted(0x1365B00)
def nth_client_off_side(m, mode, rule, pos, nth, *_):
    """Walking the clients after `pos` ((pos + k) % 5), the (nth % count)-th present one whose class
    differs from pos's, counting with 0x1365e90; 5 when there is none."""
    n = m.call(m.main + 0x1365E90, mode, rule, pos, nth) & 0xFF
    nth &= 0xFF
    target = nth % n if n else nth
    mode &= 0xFFFFFFFF; rule &= 0xFFFFFFFF
    p = _s32(pos)
    count = 0
    for k in range(5):
        s = _s32(p + k)
        c = (s - int(s / 5) * 5) & 0xFFFFFFFF
        if c == pos & 0xFFFFFFFF or m.call(m.main + 0xE7E2A0, mode, rule, c) & 1 == 0 or mode > 2:
            continue
        mine = _class_of(m, mode, p) if p <= 4 else 2
        if mine == _class_of(m, mode, c):
            continue
        if count == target:
            return c
        count = (count + 1) & 0xFFFFFFFF
    return 5


@lifted(0x283D690)
def mode_class_of(m, o, key, *_):
    return _tail(m, m.main + 0x144E790, m.u64(m.u64(o + 8) + 0x290), key)


@lifted(0x17D5D98)
def same_side_pair(m, o, a, b, *_):
    ia = m.vcall(a, 0x98) & 0xFFFFFFFF
    ib = m.vcall(b, 0x98) & 0xFFFFFFFF
    return _tail(m, m.main + 0x118AB58, m.u64(m.u64(o + 0x10) + 0x290), ia, ib)


@lifted(0x113AECC)
def side_of_c9c750(m, a, b, c, d, *_):
    """0x113a588 of (a, b, 0x113af40(a, b, k, 0), d), where k is 1, 0 or 2 for 0xc9c750's 0, 1 or
    anything else (table 0x3b72710)."""
    r = m.call(m.main + 0xC9C750, a, b, c, d) & 0xFF
    k = (1, 0)[r] if r <= 1 else 2
    s = m.call(m.main + 0x113AF40, a & 0xFFFFFFFF, b & 0xFFFFFFFF, k, 0)
    return _tail(m, m.main + 0x113A588, a & 0xFFFFFFFF, b & 0xFFFFFFFF, s & 0xFFFFFFFF, d & 0xFFFFFFFF)


@lifted(0xFA0028)
def side_slot_typed(m, o, side, k, *_):
    """Entry k of side's list (o + side*0x38: objects +0x28, count u8 +0x58) when the type list from its
    +0x28 interface (vf 0) holds the static 0x46d3f08; else 0."""
    side &= 0xFF; k &= 0xFF
    if side > 4 or m.u8(o + side * 0x38 + 0x58) <= k:
        return 0
    obj = m.u64(o + side * 0x38 + 8 * k + 0x28)
    if obj == 0:
        return 0
    node = m.vcall(obj + 0x28, 0)
    if m.u8(m.u64(m.main + 0x46D3F00)) & 1 == 0:
        raise UnliftedCall("static 0x46d3f08 not built")
    static = m.u64(m.main + 0x46D3F08)
    while node:
        if node == static:
            return obj
        node = m.u64(node)
    return 0


@lifted(0x283D6F0)
def same_side_of(m, o, a, b, *_):
    return _tail(m, m.main + 0x118AB58, m.u64(m.u64(o + 8) + 0x290), a, b)


# Position class by side for each battle mode (rodata 0x3c6a450, 0x3c6a455, 0x3c6a45a).
_SIDE_CLASS = {0: (0, 1, 2, 2, 2), 1: (0, 1, 0, 1, 2), 2: (0, 1, 0, 0, 0)}


@lifted(0x282329C)
def slot_in_play(m, o, pos, *_):
    """Whether position `pos` (<= 10) is on a side and its slot is below the side's position count."""
    if pos & 0xFF > 0xA:
        return 0
    with m.frame(0x10) as f:
        m.call_void(m.main + 0x1153868, o, pos, f + 4, f)
        side = m.u8(f + 4)
        if side == 5:
            return 0
        rule = m.u64(o + 8)
        mode = m.u32(rule + 0x36C)
        cls = _SIDE_CLASS[mode][side] if mode in _SIDE_CLASS and side <= 4 else 2
        n = m.call(m.main + 0x113AA70, mode, m.u8(rule + 0x370), cls) & M32
        return int(n > m.u8(f))


@lifted(0x2843AA0)
def position_in_play(m, o, ident, *_):
    """The position of `ident`, or 10 when it is not in play."""
    pos = m.call(m.main + 0x1381420, m.call(m.main + 0x13813E4, m.u64(o + 8)), ident) & M32
    if m.call(m.main + 0x282329C, m.u64(m.u64(o + 8) + 0x290), pos) & 1:
        return pos
    return 0xA


@lifted(0x113A588)
def nth_position_on_side(m, mode, rule, pos, i, *_):
    """Scanning positions from `pos` (mod 11), the (i mod count)-th one whose client is on the side class
    0xc9c750 names; `pos` when the side has no positions."""
    side = m.call(m.main + 0xC9C750, mode, rule, pos, i) & 0xFF
    n = m.call(m.main + 0x113AA70, mode, rule, side) & M32
    mode &= M32
    if n == 0 or mode not in SIDE_CLASS:
        return pos & M32
    k = (i & 0xFF) % n
    j = 0
    for step in range(11):
        p = ((pos & 0xFF) + step) % 11
        slot = slot_of_position(mode, rule & 0xFF, p)
        if slot == 5 or SIDE_CLASS[mode][slot] != side:
            continue
        if j == k:
            return p
        j += 1
    return pos & M32


def _in_play(m, o, ident):
    """The battler `ident` when its id is in play, else 0."""
    v = m.call(m.main + 0x13813E4, m.call(m.main + 0x1482534, o))
    if m.call(m.main + 0x1381400, v, ident) & 1 == 0:
        return 0
    return m.call(m.main + 0x13813F4, o, ident)


@lifted(0x1723914)
def side_slot_value(m, t, side, pos, *_):
    """The u64 at +0x30 of entry (side, pos): 0x28 bytes per side 0..3, 8 per position 0..4; 0 outside."""
    side &= 0xFF
    pos = pos & M32
    if side > 3 or (pos if pos < 0x80000000 else pos - (1 << 32)) > 4:
        return 0
    return m.u64(t + side * 0x28 + 8 * pos + 0x30)


@lifted(0x11480F8)
def bump_side_slot(m, c, side, pos, *_):
    """Raise entry (side, pos) of [[c+0x20]+0x10]+0x210 by one, up to the side's cap ([0x46e2f38]); then
    command 0x2e (side, pos)."""
    pos = pos & M32
    side &= 0xFF
    bad = side > 3 or (pos if pos < 0x80000000 else pos - (1 << 32)) > 4
    if not bad:
        e = m.u64(m.u64(m.u64(c + 0x20) + 0x10) + 0x210) + side * 0x28 + 8 * pos + 0x30
        cap = m.u64(m.u64(m.main + 0x46E2F38) + 8 * side)
        if cap > m.u64(e):
            m.put(e, 8, m.u64(e) + 1)
    return _tail(m, m.main + 0x119AFF0, m.u64(c + 0x18), 0x2E, side, pos & 0xFF)


# Kind of r+4 -> (0x28870ec kind, text, check, its text): 0x1153068's three branches.
_SIDE_KIND = {1: (0x417, 0x2887104, 0x35E), 2: (0x418, 0x171A4EC, 0x35F), 3: (0x419, 0x28871B4, 0x360)}


@lifted(0x1153068)
def side_event(m, o, _x1, r, *_):
    """For battler id [r] with side count 0x11531d4 at most 2: by kind byte r+4 (1..3) the command
    0x28870ec, its text and, when the kind's counter is positive, a second text (kind 3 then 0x28872dc);
    then 0x11480f8 bumps the side's slot."""
    ident = m.u32(r)
    k = m.u8(r + 4)
    if k in _SIDE_KIND:
        _need(m, m.main + _SIDE_KIND[k][1])
        if k == 3:
            _need(m, m.main + 0x28872DC)
    c = m.call(m.main + 0x1589A40, o, ident) & M32
    if m.call(m.main + 0x11531D4, o, 1, c) <= 2 and k in _SIDE_KIND:
        text, counter, more = _SIDE_KIND[k]
        m.call_void(m.main + 0x28870EC, m.call(m.main + 0x1143584, o), ident, k)
        m.call_void(m.main + 0x287EE68, m.call(m.main + 0x1143584, o), ident, text)
        n = m.call(m.main + counter, o) & M32
        if n and n < 0x80000000:
            m.call_void(m.main + 0x287EE68, m.call(m.main + 0x1143584, o), ident, more)
        if k == 3:
            m.call_void(m.main + 0x28872DC, o, ident)
    return _tail(m, m.main + 0x11480F8, m.call(m.main + 0x1143584, o), 1, c)


@lifted(0x11410E0)
def side_event_of(m, o, p, *_):
    """0x1153068 on [o+0x78]'s object with {u32 [p], byte [p+0x25]}."""
    with m.frame(0x10) as sp:
        r = sp + 8
        m.put(r, 4, m.u32(p)); m.put(r + 4, 1, m.u8(p + 0x25))
        x = m.call(m.main + 0x114111C, m.u64(o + 0x78))
        return _tail(m, m.main + 0x1153068, x, sp, r)


@lifted(0xC9C090)
def position_of_entry(m, o, client, idx, *_):
    """Battle position (0..10) of entry idx of client slot `client` under the setup's mode +0x36c and rule
    +0x370: the slots own positions 0, 1, 2, 3 and 4..8 in turn (slot per position by mode; mode 1 uses
    tables 0x3c69d34 / 0x3c69d48); 9 or 10 when it falls past them."""
    s = m.u64(o + 8)
    mode, rule = m.u32(s + 0x36C), m.u8(s + 0x370)
    c = client & 0xFF
    idx &= M32

    def take(owner, result):
        nonlocal idx
        if owner == c:
            if idx & 0xFF == 0:
                return result
            idx = (idx - 1) & M32
        return None

    r = take(0 if mode < 3 else 5, 0)
    if r is not None:
        return r
    w = (5 if rule == 0 else 2) if mode == 2 else (1 if mode in (0, 1) else 5)
    r = take(w, 1)
    if r is not None:
        return r
    if mode == 2:
        w = 5 if rule < 2 else 3
    elif mode == 1:
        w = (2, 2, 2, 0, 2)[rule - 1] if 0 <= rule - 1 < 5 else 0      # 0x3c69d34
    else:
        w = 5
    r = take(w, 2)
    if r is not None:
        return r
    if mode == 2:
        w = 5 if rule < 3 else 4
    elif mode == 1:
        w = (3, 3, 3, 3, 5)[rule - 1] if 0 <= rule - 1 < 5 else 1      # 0x3c69d48
    else:
        w = 5
    r = take(w, 3)
    if r is not None:
        return r
    w = 1 if mode == 2 else 5
    if w == c:
        v = idx & 0xFF
        if v < 4:
            return (idx + 4) & M32
        if v == 4:
            return 8
        idx = (idx - 5) & M32
        return 9 if idx & 0xFF == 0 else 10
    return 10


@lifted(0x1148430)
def party_member(m, parties, client, i, *_):
    """Member i of client slot `client` (0..4) in the parties table (0x38 bytes a slot, count +0x58), or 0."""
    client &= 0xFF; i &= 0xFF
    if client > 4 or m.u8(parties + 0x38 * client + 0x58) <= i:
        return 0
    return m.u64(parties + 0x38 * client + 0x28 + 8 * i)


@lifted(0x1148380)
def party_member_of(m, o, client, i, *_):
    return _tail(m, m.main + 0x1148430, m.u64(m.u64(o + 0x10) + 0x30), client, i)


@lifted(0x11483F4)
def send_out_id(m, o, a, b, c, *_):
    """0x114e268 on [[o+0x78]+0x13e0] with bytes {a, b, c}: the id it answers."""
    with m.frame(0x20) as sp:
        m.put(sp + 8, 1, a); m.put(sp + 9, 1, b); m.put(sp + 0xA, 1, c)
        x = m.call(m.main + 0x114E21C, m.call(m.main + 0x1361214, o))
        m.call_void(m.main + 0x114E268, x, sp, sp + 8)
        return m.u32(sp)


@lifted(0x11483CC)
def queue_98(m, c, a, b, d, e, *_):
    return _tail(m, m.main + 0x119AFF0, m.u64(c + 0x18), 0x98, a & 0xFF, b & 0xFF, d & 0xFF, e & 1)


@lifted(0x114838C)
def fire_trigger_of(m, o, kind, v, *_):
    """Trigger 0x121bdb0 on [0x1361214(o)+0x1d40] with the event {u32 kind, u32 v, zeros}."""
    with m.frame(0x30) as sp:
        ev = sp + 0x10
        m.put(ev + 8, 2, 0); m.put(ev + 0xA, 1, 0); m.put(ev + 0xC, 2, 0)
        m.put(ev, 4, kind); m.put(ev + 4, 4, v)
        m.put(sp + 8, 1, 0)
        x = m.call(m.main + 0x114E520, m.call(m.main + 0x1361214, o))
        return _tail(m, m.main + 0x121BDB0, x, sp + 8, ev)


@lifted(0x11482A0)
def send_in(m, o, out, args, *_):
    """Send in entry args[1] of client slot args[0] at place args[2] (0x11483f4; *out = the id), command
    0x98 with args[0..3], triggers 0xc, 0x16 and 0x20 for the id; when flag 0 of 0x113df30's object is
    set and the member exists, 0x1148470 with it and 0x12."""
    a0, a1, a2 = m.u8(args), m.u8(args + 1), m.u8(args + 2)
    ident = m.call(m.main + 0x11483F4, o, a0, a1, a2) & 0xFF
    m.put(out, 4, ident)
    m.call_void(m.main + 0x11483CC, m.call(m.main + 0x1143584, o), m.u8(args), m.u8(args + 1),
                m.u8(args + 2), m.u8(args + 3))
    for kind in (0xC, 0x16, 0x20):
        m.call_void(m.main + 0x114838C, o, kind, m.u32(out))
    x = m.call(m.main + 0x113DF30, m.call(m.main + 0x1482534, o))
    if not m.call(m.main + 0x147992C, x, 0) & 1:
        return
    b = m.call(m.main + 0x1148380, o, m.u8(args), m.u8(args + 1))
    if not b:
        return
    return _tail(m, m.main + 0x1148470, m.call(m.main + 0x1143584, o), b, 0x12)
