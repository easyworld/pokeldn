"""The battler object (one per Pokemon in battle): field getters and flag bits."""

from pokeldn.sv.battle.engine.calls import M32, _tail, _vtail
from pokeldn.sv.battle.engine.containers import battler
from pokeldn.sv.battle.machine import UnliftedCall, lifted


@lifted(0x2D3B6F8)
def get_50(m, b, *_): return m.u32(b + 0x50)


@lifted(0x2D3BC58)
def hp(m, b, *_): return m.u16(b + 0x5A)


@lifted(0x2D3BC60)
def max_hp(m, b, *_): return m.u16(b + 0x58)


@lifted(0x2D3BB04)
def get_408(m, b, *_): return m.u16(b + 0x408)


@lifted(0x2D3B7D0)
def get_487(m, b, *_): return m.u8(b + 0x487)


@lifted(0x2D3EADC)
def get_6c(m, b, *_): return m.u8(b + 0x6C)


@lifted(0x2D3E63C)
def get_5a0(m, b, i, *_): return m.u8(b + (i & 0xFFFFFFFF) + 0x5A0)


def _bit(m, b, base, i):
    i &= 0xFFFFFFFF
    return m.u8(b + ((i >> 3) & 0xFF) + base) >> (i & 7) & 1


@lifted(0x2D3D14C)
def flag_49e(m, b, i, *_): return _bit(m, b, 0x49E, i)


@lifted(0x2D3D130)
def flag_49a(m, b, i, *_): return _bit(m, b, 0x49A, i)


@lifted(0x2D3D114)
def flag_496(m, b, i, *_): return _bit(m, b, 0x496, i)


@lifted(0x2D3D7F4)
def set_flag_496(m, b, i, *_):
    i &= 0xFFFFFFFF
    a = b + ((i >> 3) & 0xFF) + 0x496
    m.put(a, 1, m.u8(a) | (1 << (i & 7)))


@lifted(0x2D3C0B8)
def slot_88_active(m, b, i, *_):
    return int(m.u8(b + (i & 0xFFFF) * 0x10 + 0x88) & 7 != 0)


@lifted(0x2D3ECFC)
def clear_6f8(m, b, *_):
    if m.u32(b + 0x6F8) != 0:
        m.put(b + 0x6F8, 4, 0); m.put(b + 0x6F4, 2, 0)


@lifted(0x2D3EE2C)
def call_520_3(m, b, *_):
    return m.vcall(b, 0x520, 3)


# Stat stages -6..+6 as (numerator, denominator), 0x3c69d73.
STAGE_RATIO = ((2, 8), (2, 7), (2, 6), (2, 5), (2, 4), (2, 3), (2, 2),
               (3, 2), (4, 2), (5, 2), (6, 2), (7, 2), (8, 2))


@lifted(0x2D3BFC0)
def vf108_is_zero(m, b, *_):
    return int(m.vcall(b, 0x108) & 0xFFFF == 0)


@lifted(0x2D3C1B8)
def first_active_98(m, b, *_):
    for i, off in enumerate((0x98, 0xA8, 0xB8, 0xC8), 1):
        if m.u8(b + off) & 7:
            return i
    return 5 if m.u8(b + 0xD8) & 7 else 0


@lifted(0x2D3BEB0)
def staged_value(m, b, *_):
    """vf 0xe0 scaled by the stage in byte +0x418 (b[0x83] as u64 index)."""
    v = m.vcall(b, 0xE0)
    stage = m.u8(b + 0x418)
    if stage >= 13:
        return v
    num, den = STAGE_RATIO[stage]
    return ((v * num) & 0xFFFF) // den & 0xFFFFFFFF


def vf2a8_unless(m, b, other, *_):
    if m.u32(other + 0xBC) == 0 and m.vcall(b, 0x220, 0x13) & 1 == 0:
        return m.vcall(b, 0x2A8)
    return 0


@lifted(0x2D3DBE8)
def turn_start(m, b, *_):
    m.put(b + 0x496, 4, 0)
    if m.u16(b + 0x488) < 9999:
        m.put(b + 0x488, 2, m.u16(b + 0x488) + 1)
    n = (m.u8(b + 0x6EF) + 1) & 0xFF
    n = n if n < 3 else 0
    m.put(b + 0x6EF, 1, n)
    m.put(b + n + 0x6EC, 1, 0)
    m.put(b + 0x487, 1, 1)


@lifted(0x2D3CBF4)
def move_index(m, b, move, *_):
    """Which of the four move slots (u16 at +0x430 + 0x16 * i) holds `move`; 4 for none or move 0."""
    move &= 0xFFFF
    if move == 0:
        return 4
    for i in range(4):
        if m.u16(b + 0x430 + 0x16 * i) == move:
            return i
    return 4


@lifted(0x2D3E660)
def add_counter_5a8(m, b, i, n, *_):
    i &= 0xFF
    if i < 9:
        a = b + 0x5A8 + 4 * i
        v = (m.u32(a) + n) & 0xFFFFFFFF
        m.put(a, 4, 0xFFFF if v > 0xFFFE else v)


@lifted(0x2D3D938)
def step_condition(m, b, cond, out_pair, out_ended, *_):
    """Count one turn of condition `cond` (16-byte entries at +0x80, turns at +0x390); 1 when set."""
    cond &= 0xFFFF
    if cond & 0xFFFB == 2:
        return 0
    entry = b + 0x80 + 0x10 * cond
    word = m.u64(entry + 8)
    if word & 7 == 0:
        return 0
    kind = word & 7
    limit = (word >> 3) & 0x3F if kind in (2, 4) else 0
    first, second = m.u64(entry), m.u64(entry + 8)
    if out_pair:
        m.put(out_pair, 8, first); m.put(out_pair + 8, 8, second)
    if out_ended:
        m.put(out_ended, 1, 0)
    if cond == 0x1C:
        raise UnliftedCall("condition 0x1c (vf 0x668)")
    turns = b + 0x390 + cond
    if limit == 0:
        word = m.u64(entry + 8)
        if word & 7 == 1 and word & 0x1F8:
            if m.u8(turns) < (word >> 3) & 0x3F:
                m.put(turns, 1, m.u8(turns) + 1)
    else:
        t = (m.u8(turns) + 1) & 0xFF
        m.put(turns, 1, t)
        if limit <= t:
            m.put(entry, 8, 0); m.put(entry + 8, 8, 0); m.put(turns, 1, 0)
            if out_ended:
                m.put(out_ended, 1, 1)
    return 1


@lifted(0x2D3BB6C)
def get_47e(m, b, *_): return m.u16(b + 0x47E)


@lifted(0x2D3B7D8)
def set_487(m, b, v, *_): m.put(b + 0x487, 1, v)


@lifted(0x2D3D18C)
def major_status(m, b, *_):
    """The first condition of 3, 5, 4, 6, 0x1a the battler holds (vf 0x4d0), else 0x20."""
    for cond in (3, 5, 4, 6, 0x1A):
        if m.vcall(b, 0x4D0, cond) & 1:
            return cond
    return 0x20


NO_TYPE = 0x12


@lifted(0x2D1F300)
def types(m, b, out1, out2, *_):
    """The battler's two types: its Tera type twice once terastallized (+0x714, type +0x715; 0x63
    and 0x12 read the base types, any other value past 0x11 gives none), else +0x40a and +0x40b, where
    condition 0x19 turns a Flying (2) type into none and condition 0x17 keeps a lone none."""
    tera = m.u8(b + 0x715)
    if m.u8(b + 0x714) and tera != 0x12 and tera != 0x63:
        t = tera if tera < 0x12 else NO_TYPE
        m.put(out1, 1, t); m.put(out2, 1, t)
        return
    roost = m.vcall(b, 0x220, 0x19) & 1
    t1, t2 = m.u8(b + 0x40A), m.u8(b + 0x40B)
    if roost:
        t1 = NO_TYPE if t1 == 2 else t1
        t2 = NO_TYPE if t2 == 2 else t2
    m.put(out1, 1, t1); m.put(out2, 1, t2)
    if m.vcall(b, 0x4D0, 0x17) & 1 == 0:
        if t1 == NO_TYPE:
            if t2 == NO_TYPE:
                t2 = 0
                m.put(out2, 1, 0)
            m.put(out1, 1, t2)
            return
    elif t1 == NO_TYPE:
        if t2 != NO_TYPE:
            m.put(out1, 1, t2)
        return
    if t2 == NO_TYPE:
        m.put(out2, 1, t1)


@lifted(0x2D3BFE4)
def can_act(m, b, *_):
    if m.vcall(m.u64(b + 0x48), 0x158, 2) & 1:
        return 0
    if m.vcall(b, 0x200) & 1 or m.vcall(b, 0x7B8) & 1:
        return 0
    return (m.vcall(b, 0x520, 7) ^ 1) & 1


@lifted(0x2D3CDA0)
def has_type(m, b, t, *_):
    """Whether the battler is of type `t` (its two types, or the added type at +0x40c); none never matches."""
    t &= 0xFF
    if t == NO_TYPE:
        return 0
    with m.frame(8) as out:
        m.vcall_void(b, 0x808, out, out + 4)
        return int(m.u8(out) == t or m.u8(out + 4) == t or m.u8(b + 0x40C) == t)


@lifted(0x2D3CD30)
def packed_types(m, b, *_):
    with m.frame(8) as out:
        m.vcall_void(b, 0x808, out, out + 4)
        return (m.u8(out) & 0x1F) | (m.u8(out + 4) & 0x1F) << 5 | (m.u8(b + 0x40C) & 0x1F) << 10


@lifted(0x2D3D8CC)
def clear_4a0(m, b, i, *_): m.put(b + (i & 0xFFFFFFFF) * 8 + 0x4A0, 8, 0)


@lifted(0x2D3E6BC)
def counter_5a8(m, b, i, *_):
    i &= 0xFF
    return m.u32(b + 0x5A8 + 4 * i) if i < 9 else 0


@lifted(0x2D3C8F0)
def move_byte_432(m, b, i, *_):
    """Byte +2 of move slot i (the slots are 0x16 bytes from +0x430), for i below the count at +0x482."""
    i &= 0xFF
    return m.u8(b + 0x432 + 0x16 * i) if i < m.u8(b + 0x482) else 0


@lifted(0x2D3D0F4)
def bump_72(m, b, *_): m.put(b + 0x72, 2, m.u16(b + 0x72) + 1)


@lifted(0x2D3D818)
def set_flag_49a(m, b, i, *_):
    """Set flag i of the +0x49a set unless the battler holds condition i (vf 0x4d0), then tell vf 0x500."""
    i &= 0xFFFFFFFF
    if m.vcall(b, 0x4D0, i) & 1:
        return
    a = b + ((i >> 3) & 0xFF) + 0x49A
    m.put(a, 1, m.u8(a) | (1 << (i & 7)))
    m.vcall_void(b, 0x500, i)


@lifted(0x2D3E434)
def set_last_490(m, b, p2, p3, p4, p5, p6, *_):
    """Record the battler's last action: +0x490 (p5), +0x492, +0x48e, +0x486, and the repeat count at
    +0x48c (reset unless p4's bit 0, kept counting while p5 repeats)."""
    previous = m.u16(b + 0x490)
    m.put(b + 0x490, 2, p5); m.put(b + 0x492, 2, p6); m.put(b + 0x48E, 1, p2); m.put(b + 0x486, 1, p3)
    if previous == p5 & 0xFFFF:
        if p4 & 1 == 0:
            m.put(b + 0x48C, 2, 0)
            return
        m.put(b + 0x48C, 2, m.u16(b + 0x48C) + 1)
    else:
        m.put(b + 0x48C, 2, p4 & 1)


@lifted(0x2D3EB00)
def has_6f2(m, b, *_): return int(m.u16(b + 0x6F2) != 0)


MOVE_SLOT, MOVE_SLOTS_COUNT = 0x16, 0x482      # four 0x16-byte move slots from +0x430; count at +0x482


@lifted(0x2D3C720)
def move_byte_437(m, b, i, *_):
    i &= 0xFF
    return m.u8(b + 0x437 + MOVE_SLOT * i) if i < m.u8(b + MOVE_SLOTS_COUNT) else 0


@lifted(0x2D3C748)
def set_move_byte_437(m, b, i, v, *_):
    i &= 0xFF
    if i < m.u8(b + MOVE_SLOTS_COUNT):
        s = b + MOVE_SLOT * i
        m.put(s + 0x437, 1, v)
        if m.u8(s + 0x43A):
            m.put(s + 0x42D, 1, v)


HP, MAX_HP = 0x5A, 0x58


@lifted(0x2D3D7AC)
def lose_hp(m, b, n, *_):
    """Take n HP; at or past zero, vf 0x2f0 (0x2d3d7ec) sets HP to 0."""
    n &= 0xFFFF
    if n < m.u16(b + HP):
        m.put(b + HP, 2, m.u16(b + HP) - n)
        return
    m.vcall_void(b, 0x2F0, n)


@lifted(0x2D3D7D0)
def gain_hp(m, b, n, *_):
    m.put(b + HP, 2, min(m.u16(b + MAX_HP), (m.u16(b + HP) + n) & 0xFFFF))


@lifted(0x2D3D7EC)
def zero_hp(m, b, *_):
    m.put(b + HP, 2, 0)


@lifted(0x2D3CB5C)
def mark_move_used(m, b, i, *_):
    s = b + MOVE_SLOT * (i & 0xFF)
    if m.u8(s + 0x436) == 0:
        m.put(s + 0x436, 1, 1)
        m.put(b + 0x485, 1, m.u8(b + 0x485) + 1)
    m.put(s + 0x435, 1, 1)
    if m.u8(s + 0x43A):
        m.put(s + 0x42B, 2, 0x101)


@lifted(0x2D3D6C0)
def critical_stage(m, b, *_):
    """The battler's critical-hit stage: vf 0x298's, +2 under condition 9, +3 under condition 0x29, at most 3."""
    stage = m.vcall(b, 0x298) & 0xFFFFFFFF
    if m.vcall(b, 0x4D0, 9) & 1:
        stage += 2
    if m.vcall(b, 0x220, 0x29) & 1:
        stage += 3
    return 3 if stage & 0xFF > 2 else stage & 0xFFFFFFFF


@lifted(0x2D3E4BC)
def remember_action(m, b, record, *_):
    """Append a 13-byte record to the battler's current turn history (six 0x10-byte rows per turn at
    +0x5cc + 0x60 * turn, count at +0x6ec + turn); a full history drops its oldest row."""
    turn = m.u8(b + 0x6EF)
    count_at = b + 0x6EC + turn
    n = m.u8(count_at)
    rows = b + 0x5CC + 0x60 * turn
    if n == 6:
        for i in range(5):
            m.put(rows + 0x10 * i, 8, m.u64(rows + 0x10 * (i + 1)))
            m.put(rows + 0x10 * i + 5, 8, m.u64(rows + 0x10 * (i + 1) + 5))
        n = 5
    row = rows + 0x10 * n
    first = m.u64(record)
    m.put(row + 5, 8, m.u64(record + 5)); m.put(row, 8, first)
    if m.u8(count_at) < 6:
        m.put(count_at, 1, m.u8(count_at) + 1)


@lifted(0x2D3B720)
def set_out_reason(m, b, a, c, *_):
    """For a battler out of the battle (vf 0x200): +0x7c and the u32 at +0x78."""
    if m.vcall(b, 0x200) & 1:
        m.put(b + 0x7C, 1, a); m.put(b + 0x78, 4, c)


@lifted(0x2D3BAB4)
def value_402_406(m, o, *_):
    p = m.u64(o + 0x700)
    return m.u16(o + 0x406) if p and m.u32(p + 0xB8) else m.u16(o + 0x402)


@lifted(0x2D3D8D8)
def set_slot_pair(m, b, i, pair, *_):
    """Store a 16-byte pair at +0x80 + 16i and clear byte +0x390 + i; slots below 6 run vf 0x608 first."""
    k = i & 0xFFFF
    if k <= 5:
        m.vcall_void(b, 0x608, i, pair)
    m.write(b + 0x80 + 16 * k, m.read(pair, 16))
    m.put(b + 0x390 + k, 1, 0)


@lifted(0x11484E4)
def battler_508(m, o, ident, arg, *_):
    """Tail call of vf 0x508 on battler `ident` with `arg`."""
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), ident)
    m.vcall_void(b, 0x508, arg & 0xFFFFFFFF)


@lifted(0x16EEB98)
def unruled_460(m, o, pokecon, b, *_):
    """vf 0x460 of the battler when flag bit 2 of +0x499 is clear, +0x30 is below 2 and the battler's
    rule value (setup map) is absent, 0 or above 4 (signed: a negative value gives 0); else 0."""
    s = m.u64(o + 0x38)
    if m.u8(s + 0x499) >> 2 & 1 or m.u32(s + 0x30) > 1:
        return 0
    setup = m.u64(pokecon + 0x290)
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(setup + 8) + 0x50), m.vcall(b, 0x98) & 0xFFFFFFFF)
    if p:
        v = m.s(p, 4)
        if v <= 4 and v != 0:  # cmp #4; ccmp #0, le at 0x16eebec: signed
            return 0
    return m.vcall(b, 0x460)


@lifted(0x1360524)
def battler_618(m, o, ident, arg, *_):
    """Tail call of vf 0x618 on battler `ident` with `arg`."""
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), ident)
    m.vcall_void(b, 0x618, arg & 0xFFFFFFFF)


@lifted(0x2D1F884)
def has_type_715(m, b, *_):
    """Whether the type byte at +0x715 (when +0x714 is set) is one of the battler's two types (+0x40a,
    +0x40b), after vf 0x220 (0x19) and vf 0x4d0 (0x17) mask them; 0x12 is no type (0x3c630a0 maps 0..0x12
    to itself)."""
    if m.u8(b + 0x714) == 0:
        return 0
    c = m.vcall(b, 0x220, 0x19) & 1
    t1, t2 = m.u8(b + 0x40A), m.u8(b + 0x40B)
    r = m.vcall(b, 0x4D0, 0x17) & 1
    a = t1 == 0x12 or (c and t1 == 2)
    z = t2 == 0x12 or (c and t2 == 2)
    if r:
        if a and z:
            t1 = t2 = 0x12
        elif a:
            t1 = t2
        elif z:
            t2 = t1
    elif a:
        t2 = 0 if z else t2
        t1 = t2
    elif z:
        t2 = t1
    k = m.u8(b + 0x715)
    t = k if k <= 0x12 else 0x12
    return int(t == t1 or t == t2)


@lifted(0x288D134)
def battler_1c8(m, o, ident, a, b, *_):
    """Tail call of vf 0x1c8 (a, b) on battler `ident`, nothing when there is none."""
    t = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), ident)
    if t == 0:
        return 0
    return _tail(m, m.u64(m.u64(t) + 0x1C8), t, a & 0xFFFFFFFF, b & 0xFFFFFFFF)


@lifted(0x14807D0)
def reset_32_flags(m, b, *_):
    """Clear the u32 at +0x49a and run vf 0x500 for 0..31."""
    m.put(b + 0x49A, 4, 0)
    for i in range(32):
        m.vcall_void(b, 0x500, i)


@lifted(0x15C04B0)
def has_battler(m, o, ident, *_):
    """Whether the u32-keyed battler map at o+0x140 holds a nonzero battler for `ident`."""
    from pokeldn.sv.battle.engine.containers import find
    node = find(m, o + 0x140, ident & 0xFFFFFFFF, 4)
    return int(node != 0 and m.u64(node + 0x18) != 0)


@lifted(0x283D610)
def battler_by_id(m, o, ident, *_):
    """Tail call of 0xf21c94 on [[o+8]+0x30]."""
    return m.call(m.main + 0xF21C94, m.u64(m.u64(o + 8) + 0x30), ident)


@lifted(0x1373610)
def refresh_716(m, o, a, b, *_):
    """0x13736d8, then when the type chain of [o+0x48]+0x28 (vf 0) holds the static 0x46dcd58: +0x716 =
    0xbf44f4 of [[o+0x48]+0x48]+0x70."""
    m.call_void(m.main + 0x13736D8, o, a & 1, b & 1)
    p = m.u64(o + 0x48)
    t = m.vcall(p + 0x28, 0)
    guard = m.u64(m.main + 0x46DCD50)
    if m.u8(guard) & 1 == 0 and m.call(m.main + 0x343CF10, guard) & 0xFFFFFFFF:
        m.put(m.u64(m.main + 0x46DCD58), 8, m.call(m.main + 0x19F5520))
        m.call_void(m.main + 0x343CF20, guard)
    want = m.u64(m.main + 0x46DCD58)
    while t:
        if t == want:
            v = m.call(m.main + 0xBF44F4, m.u64(m.u64(p + 0x48) + 0x70))
            m.put(o + 0x716, 2, v)
            return v
        t = m.u64(t)
    return 0


@lifted(0x14A08A4)
def bump_counter(m, o, ident, key, *_):
    """vf 0x780(key, vf 0x778(key) + 1) on the battler `ident`; a count of 0xff wraps to -1."""
    from pokeldn.sv.battle.engine.containers import battler
    b = battler(m, m.u64(m.u64(o + 0x10) + 0x30), ident)
    v = m.vcall(b, 0x778, key & 0xFFFFFFFF) & 0xFF
    return _vtail(m, b, 0x780, key & 0xFFFFFFFF, 0xFFFFFFFF if v == 0xFF else v + 1)


@lifted(0x136075C)
def battler_to_1360c00(m, o, ident, *_):
    from pokeldn.sv.battle.engine.containers import battler
    b = battler(m, m.u64(m.u64(o + 0x10) + 0x30), ident)
    return _tail(m, m.main + 0x1360C00, m.u64(o + 0x18), b)


def _main_battler(m, o, ident):
    return battler(m, m.u64(m.u64(o + 0x10) + 0x30), ident)


@lifted(0x1143AB8)
def battler_set_5a0(m, o, ident, i, v, *_):
    b = _main_battler(m, o, ident)
    return _vtail(m, b, 0x530, i & 0xFFFFFFFF, v & 0xFFFFFFFF)


@lifted(0x183F194)
def battler_4f8(m, o, ident, a, b2, *_):
    b = _main_battler(m, o, ident)
    return _vtail(m, b, 0x4F8, a & 0xFFFFFFFF, b2)


@lifted(0x288CE48)
def battler_398(m, o, ident, *_):
    return _vtail(m, _main_battler(m, o, ident), 0x398)


@lifted(0x14375B4)
def battler_4a0(m, o, ident, *_):
    b = _main_battler(m, o, ident)
    if b == 0:
        return
    return _vtail(m, b, 0x4A0)


@lifted(0x1381400)
def has_id(m, o, ident, *_): return int(m.call(m.main + 0x1381420, o, ident) & 0xFF != 10)


@lifted(0x113F4F8)
def settle_state(m, o, *_):
    r = m.call(m.main + 0x113F5B8, m.call(m.main + 0x114E480, o))
    if r & 1:
        return r
    if m.call(m.main + 0x113F630, m.call(m.main + 0x113F5B0, m.call(m.main + 0x1482534, o))) & 1 == 0:
        e = m.call(m.main + 0x113F5B0, m.call(m.main + 0x1482534, o))
        r = m.call(m.main + 0x113F5C8, e, 0)
        if r & 0xFF == 0:
            return r
    a = m.call(m.main + 0x114E480, o)
    flag = m.call(m.main + 0x114E550, a, m.call(m.main + 0x1482534, o)) & 1
    x = m.call(m.main + 0x1143584, o)
    m.call_void(m.main + (0x1148C58 if flag else 0x114C994), x)
    m.call_void(m.main + 0x113F5F0, o)
    p = m.call(m.main + 0x113DE70, m.call(m.main + 0x113DE68, o))
    m.put(p, 1, 2)   # tail call to 0x113fa5c, a byte store returning its pointer
    return p


@lifted(0x2D1F784)
def has_type_2d1f784(m, b, t, *_):
    t &= 0xFF
    if t == 0x12:
        return 0
    r = m.vcall(b, 0x220, 0x19) & 1
    c1, c2 = m.u8(b + 0x40A), m.u8(b + 0x40B)
    a = c1 == 0x12 or (r and c1 == 2)
    z = c2 == 0x12 or (r and c2 == 2)
    if m.vcall(b, 0x4D0, 0x17) & 1:
        if not a:
            if z:
                c2 = c1
        elif not z:
            c1 = c2
        else:
            c1 = c2 = 0x12
    elif a:
        c1 = c2 = 0 if z else c2
    elif z:
        c2 = c1
    return int(c1 == t or c2 == t)


@lifted(0x2D3B780)
def bump_490(m, b, *_):
    """Raise the byte counter behind slots 0x490 (get) and 0x498 (set) by one, unless it is 0xff."""
    v = m.vcall(b, 0x490)
    if ~v & 0xFF == 0:
        return
    return _vtail(m, b, 0x498, (v + 1) & 0xFFFFFFFF)


@lifted(0x171A850)
def battler_1c0(m, o, ident, a, b, *_):
    bt = _main_battler(m, o, ident)
    if bt == 0:
        return
    return _vtail(m, bt, 0x1C0, a & 0xFFFFFFFF, b & 0xFFFFFFFF)


@lifted(0x13736D8)
def refresh_battle_stats(m, b, reset, scale, *_):
    """reset: +0x40a/+0x40b from vf 0x350/0x358, +0x410 = 0, +0x40c = 0x12. Always +0x40d from the
    core's vf 0x130. scale: the u16 stats +0x400..+0x408 = core vf 0x70(1..5) * byte +0x3f6.. / 10."""
    if reset & 1:
        m.put(b + 0x40A, 1, m.vcall(b, 0x350))
        m.put(b + 0x40B, 1, m.vcall(b, 0x358))
        m.put(b + 0x410, 4, 0)
        m.put(b + 0x40C, 1, 0x12)
    m.put(b + 0x40D, 1, m.vcall(m.u64(b + 0x48), 0x130))
    if scale & 1:
        for i in range(5):
            v = m.vcall(m.u64(b + 0x48), 0x70, i + 1) & 0xFFFF
            m.put(b + 0x400 + 2 * i, 2, (v * m.u8(b + 0x3F6 + i) & 0xFFFFFFFF) // 10)


@lifted(0x14806D0)
def apply_five_flags(m, b, flags, *_):
    """For each non-zero byte k of flags +4..+8, vf 0x370(k - 3, byte)."""
    vals = [m.u8(flags + 4 + k) for k in range(5)]
    if not any(vals):
        return b
    r = b
    for k, v in enumerate(vals):
        if v:
            r = _vtail(m, b, 0x370, k + 1, v)
    return r


@lifted(0xF79790)
def battler_checked(m, o, ident, *_):
    """The battler with id `ident` (map o+0x140) when present (count, then at), else 0."""
    return battler(m, o, ident)


@lifted(0x2842E80)
def battler_308(m, o, ident, *_):
    """vf 0x308 of the battler with id `ident` (0xf79790 on [[o+8]+0x30])."""
    b = m.call(m.main + 0xF79790, m.u64(m.u64(o + 8) + 0x30), ident)
    return _vtail(m, b, 0x308)


@lifted(0x114EB70)
def note_718_in_side(m, o, b, *_):
    """For a battler whose type list (+0x28 interface, vf 0) holds the static 0x46d3f08: store its u16
    +0x718 at +6 of the entry holding its id among the six 0x10-byte entries from +0x10 of its side's
    0x60-byte row ([[o+0x10]+0x250]; side from the setup map, 0..4)."""
    node = m.vcall(b + 0x28, 0)
    if m.u8(m.u64(m.main + 0x46D3F00)) & 1 == 0:
        raise UnliftedCall("static 0x46d3f08 not built")
    static = m.u64(m.main + 0x46D3F08)
    while node != static:
        if node == 0:
            return
        node = m.u64(node)
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    v = m.u16(b + 0x718)
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50), ident)
    side = 0
    if p:
        side = m.s(p, 4)
        if side >= 5:
            side = 0
        if side & 0xFF > 4:
            return
        side &= 0xFF
    row = m.u64(m.u64(o + 0x10) + 0x250) + side * 0x60
    for k in range(1, 7):
        if m.u32(row + 0x10 * k) == ident:
            m.put(row + 0x10 * k + 6, 2, v)
            return


@lifted(0x2844800)
def not_flagged_and_not_308(m, o, ident, *_):
    """1 unless 0x28422f0 holds for {0x283d610(o), 1} or battler `ident`'s vf 0x308 (0x2842e80) does."""
    with m.frame(0x10) as p:
        m.put(p, 8, m.call(m.main + 0x283D610, o, ident))
        m.put(p + 8, 1, 1)
        if m.call(m.main + 0x28422F0, o, p) & 1:
            return 0
    return (m.call(m.main + 0x2842E80, o, ident & 0xFFFFFFFF) ^ 1) & 1


def _battler_of(m, o, ident):
    return m.call(m.main + 0xF21C94, m.u64(m.u64(o + 8) + 0x30), ident)


@lifted(0x1142484)
def battler_vf_4e0(m, o, ident, v, *_):
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), ident)
    return _tail(m, m.u64(m.u64(b) + 0x4E0), b, v)


@lifted(0x1360558)
def is_type_7f(m, o, b, *_):
    """Whether b's vf 0xf8 is 0x7f or event 0xec lists 0x7f among its (count 0x7c) u16 values."""
    if m.vcall(b, 0xF8) & 0xFFFF == 0x7F:
        return 1
    with m.frame(0x10) as f:
        out = f + 0xC
        n = m.call(m.main + 0x114F6FC, m.call(m.main + 0x1146E90, o), m.vcall(b, 0x98) & M32, out) & 0xFF
        for i in range(n):
            if m.u16(out + 2 * i) == 0x7F:
                return 1
    return 0


@lifted(0x2D3B81C)
def add_byte(m, b, v, *_):
    """Add v to the byte set at b+0x3c2 (count +0x3c1, at most 30) once."""
    n = m.u8(b + 0x3C1)
    if any(m.u8(b + 0x3C2 + i) == v & M32 for i in range(n)):
        return b
    if n and n - 1 > 0x1C:
        return b
    m.put(b + 0x3C2 + n, 1, v); m.put(b + 0x3C1, 1, n + 1)
    return b


@lifted(0x2D3DBC4)
def reset_turn_record(m, b, v, *_):
    """u16 +0x48a = v, +0x488 = 0, byte +0x6e = 1, the 0x125 bytes from +0x5cc zeroed."""
    m.put(b + 0x48A, 2, v); m.put(b + 0x488, 2, 0); m.put(b + 0x6E, 1, 1)
    m.write(b + 0x5CC, bytes(0x125))
    return b + 0x5CC


@lifted(0x114E550)
def first_turn_flag(m, o, b, *_):
    """0 under rule 0x49b bit 0, else whether u32 [[b+0x70]+0xcc] is 0."""
    if m.u8(m.u64(o + 0x38) + 0x49B) & 1:
        return 0
    return int(m.u32(m.u64(b + 0x70) + 0xCC) == 0)
