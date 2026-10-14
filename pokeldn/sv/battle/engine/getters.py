"""Pointer and field getters of the server's objects, named by offset until their meaning is known."""

from pokeldn.sv.battle.machine import UnliftedCall, lifted


def _q(off):
    def get(m, o, *_): return m.u64(o + off)
    return get


for _addr, _off in ((0x1482534, 0x10), (0x1143584, 0x20), (0x1146E90, 0x38), (0x11409B4, 0x310),
                    (0x1361214, 0x78), (0x13813EC, 0x290), (0x11427FC, 0x68), (0x148253C, 0x70),
                    (0x114E480, 0x08), (0x11440E8, 0x10)):
    lifted(_addr)(_q(_off))


@lifted(0x1149348)
def get_2420(m, o, *_): return m.u8(o + 0x2420)


@lifted(0x1482544)
def slot_a8_nonzero(m, o, i, *_):
    i &= 0xFFFFFFFF
    if i >= 0x80000000 or i >= 0xE:   # signed compare: negative indices are below 0xe
        if i >= 0x80000000:
            return int(m.u32(o + (i & 0xFFFFFFFF) * 4 + 0xA8) != 0)
        return 0
    return int(m.u32(o + i * 4 + 0xA8) != 0)


@lifted(0x179372C)
def clear_pair(m, p, *_):
    m.put(p + 8, 8, 0); m.put(p, 4, 0)


@lifted(0x1381420)
def slot_of_id(m, o, ident, *_):
    """Index 0..9 of the active entry (u32 id at +8 + 8i, flag byte at +0xc + 8i) holding `ident`; 10 if none."""
    ident &= 0xFFFFFFFF
    for i in range(10):
        if m.u8(o + 0xC + 8 * i) and m.u32(o + 8 + 8 * i) == ident:
            return i
    return 10


@lifted(0x2D1FD38)
def static_46d3f08(m, *_):
    """A function-local static, built on first use; the engine only reads one already built."""
    if m.u8(m.u64(m.main + 0x46D3F00)) & 1 == 0:
        raise UnliftedCall("static 0x46d3f08 not built")
    return m.u64(m.main + 0x46D3F08)


@lifted(0x1149340)
def get_48(m, o, *_): return m.u64(o + 0x48)


@lifted(0x1146154)
def clear_0x24(m, p, *_):
    m.put(p + 0x20, 4, 0); m.put(p + 0x10, 8, 0); m.put(p + 0x18, 8, 0); m.put(p, 8, 0); m.put(p + 8, 8, 0)


@lifted(0x10E2DA8)
def rule_value(m, o, key, *_):
    """The u32 value for `key` in the setup's map ([[o+8]+0x50]); 0 when absent or above 4."""
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(o + 8) + 0x50), key)
    if p == 0:
        return 0
    v = m.s(p, 4)
    return v & 0xFFFFFFFF if v < 5 else 0


# Battle mode 0, 1, 2 -> five-entry tables (0x3c6a450, 0x3c6a455, 0x3c6a45a).
_MODE_TABLES = {0: (0, 1, 2, 2, 2), 1: (0, 1, 0, 1, 2), 2: (0, 1, 0, 0, 0)}


@lifted(0x144E790)
def mode_class(m, o, key, *_):
    setup = m.u64(o + 8)
    mode = m.u32(setup + 0x36C)
    p = m.call(m.main + 0x10E2DD4, m.u64(setup + 0x50), key)
    v = 0 if p == 0 or m.s(p, 4) > 4 else m.u32(p) & 0xFF
    if mode not in _MODE_TABLES or v > 4:
        return 2
    return _MODE_TABLES[mode][v]


@lifted(0x1149354)
def action_entry(m, o, i, *_):
    """Entry i (0x8c bytes from +8) of the list whose count is the byte at +0x2420; 0 past the end."""
    i &= 0xFF
    return o + 8 + 0x8C * i if i < m.u8(o + 0x2420) else 0


@lifted(0x1146164)
def append_action(m, o, entry, *_):
    n = m.u8(o + 0x2420)
    if n < 0x42 and m.u32(entry + 4) != 0:
        m.write(o + 8 + 0x8C * n, m.read(entry, 0x8C))
        m.put(o + 0x2420, 1, n + 1)


@lifted(0x114E624)
def in_byte_list(m, o, v, *_):
    """Whether `v` is one of the 30 bytes at +8."""
    v &= 0xFFFFFFFF
    return int(any(m.u8(o + 8 + i) == v for i in range(30)))


@lifted(0x2844360)
def entry_c(m, o, i, *_):
    i &= 0xFFFF
    if i < 0x86:
        e = m.u64(m.u64(m.u64(o + 0x38) + 0x78) + 8 + 8 * i)
        if e:
            return m.u32(e + 0xC)
    return 0


@lifted(0x2D17F20)
def kind_3(m, out, *_):
    m.put(out, 4, 3)
    return m.main + 0x44F9D90


@lifted(0x127399C)
def init_0x48(m, p, *_):
    m.put(p, 4, 0xA0A0000); m.put(p + 4, 8, 0xFFFF000000000000)
    m.put(p + 0x15, 8, 0x7000007000007); m.put(p + 0xD, 8, 0x70000070000)
    m.put(p + 0x25, 8, 0x70000070000); m.put(p + 0xC, 1, 0); m.put(p + 0x40, 8, 0)
    m.put(p + 0x1D, 8, 0x700000700000700); m.put(p + 0x2D, 1, 7)
    m.put(p + 0x30, 8, 0); m.put(p + 0x38, 8, 0)


def _cached_battler_id(m, o):
    if m.u32(o + 0x18) == 0:
        lst = m.call(m.main + 0x14B5634, m.u64(m.u64(o + 0x10) + 0x30), 1)
        b = m.call(m.main + 0x114C614, lst, 0)
        if b:
            m.put(o + 0x18, 4, m.vcall(b, 0x98))
    return m.u32(o + 0x18)


@lifted(0xF6FC68)
def raid_battler(m, o, *_):
    """The battler whose id the object caches at +0x18 (looked up once), when it carries the static
    marker at 0x46d3f08 in its list and the setup's flag bit 0x4d2 is set; else 0."""
    from pokeldn.sv.battle.engine.containers import battler
    if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x499) >> 2 & 1 == 0:
        return 0
    b = battler(m, m.u64(m.u64(o + 0x10) + 0x30), _cached_battler_id(m, o))
    if b == 0:
        return 0
    node, target = m.vcall(b + 0x28, 0), static_46d3f08(m)
    while node:
        if node == target:
            return b
        node = m.u64(node)
    return 0


@lifted(0x11493A0)
def is_raid_battler(m, o, ident, *_):
    p = m.u64(o + 0x310)
    if m.u8(m.u64(m.u64(p + 8) + 0x38) + 0x499) >> 2 & 1:
        _cached_battler_id(m, p)
    return int(m.u32(p + 0x18) == ident & 0xFFFFFFFF)


@lifted(0x1142E68)
def same_side_class(m, o, pokecon, b, *_):
    """Whether battler b's client and the client at o+0x95 fall in the same class of the mode's table."""
    setup = m.u64(m.u64(pokecon + 0x290) + 8)
    p = m.call(m.main + 0x10E2DD4, m.u64(setup + 0x50), m.vcall(b, 0x98))
    v = 0 if p == 0 or m.s(p, 4) > 4 else m.u32(p)
    table = _MODE_TABLES.get(m.u32(setup + 0x36C))
    if table is None:
        return 1
    a = table[v & 0xFF] if v & 0xFF < 5 else 2
    c = m.u8(o + 0x95)
    return int(a == (table[c] if c < 5 else 2))


@lifted(0x114D824)
def entry_7c(m, o, i, *_):
    i &= 0xFF
    return m.u16(o + 0x7C + 2 * i) if i < 5 else 0


@lifted(0x114D34C)
def raid_flag(m, o, *_):
    return m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x499) >> 2 & 1


@lifted(0x1578AB4)
def init_target(m, out, user, info, ids, *_):
    flag = m.u8(info + 0xA7)
    m.put(out + 3, 1, 10)
    m.put(out + 2, 1, slot_of_id(m, ids, m.vcall(user, 0x98)))
    m.put(out + 0x15, 8, 0x7000007000007); m.put(out + 0xD, 8, 0x70000070000)
    m.put(out + 0x25, 8, 0x70000070000); m.put(out + 7, 2, 0); m.put(out + 9, 1, 0)
    m.put(out + 0xC, 1, 0); m.put(out + 0x40, 8, 0); m.put(out + 0x1D, 8, 0x700000700000700)
    m.put(out + 0x2D, 1, 7); m.put(out + 0x30, 8, 0); m.put(out + 0x38, 8, 0)
    if flag == 1 and m.u8(info + 0xA6) and m.u64(info):
        m.put(out + 3, 1, slot_of_id(m, ids, m.vcall(m.u64(info), 0x98)))


@lifted(0xF6DE7C)
def boss_hp_threshold(m, o, arg, *_):
    """With no argument and the latch at +0x8c clear: when the raid boss's HP share (vf 0x108 / vf 0x110,
    in percent) is at or below +0x54, queue event (5, 0) in the four-entry list at +0x5c; 1 then."""
    if arg != 0:
        return 0
    holder = m.u64(m.u64(o + 8) + 0x310)
    if m.u8(holder + 0x8C) or raid_battler(m, holder) == 0:
        return 0
    hp = m.vcall(raid_battler(m, holder), 0x108) & 0xFFFF
    top = m.vcall(raid_battler(m, holder), 0x110) & 0xFFFF
    share = hp * 100 // top if top else 0
    if m.u16(o + 0x54) < share:
        return 0
    n = m.u32(o + 0x7C)
    if n < 4:
        m.put(o + 0x5C + 8 * n, 1, 5); m.put(o + 0x60 + 8 * n, 4, 0); m.put(o + 0x7C, 4, n + 1)
    return 1


def _side_class_of(m, setup, ident):
    from pokeldn.sv.battle.engine.slots import SIDE_CLASS
    p = m.call(m.main + 0x10E2DD4, m.u64(setup + 0x50), ident)
    v = 0 if p == 0 or m.s(p, 4) > 4 else m.u32(p) & 0xFF
    table = SIDE_CLASS.get(m.u32(setup + 0x36C))
    return table[v] if table is not None and v < 5 else 2


@lifted(0x118AB58)
def same_side(m, o, a, b, *_):
    """Whether two battlers (by id; 0 never) stand on the same side."""
    a &= 0xFFFFFFFF; b &= 0xFFFFFFFF
    if a == 0 or b == 0:
        return 0
    setup = m.u64(o + 8)
    return int(_side_class_of(m, setup, a) == _side_class_of(m, setup, b))


@lifted(0x113F5B8)
def raid_flag_38(m, o, *_):
    return m.u8(m.u64(o + 0x38) + 0x499) >> 2 & 1


@lifted(0x114E528)
def setup_entry(m, o, i, *_):
    i &= 0xFF
    return m.u64(m.u64(m.u64(o + 0x10) + 0x210) + 8 + 8 * i) if i < 5 else 0


@lifted(0x1399E68)
def setup_4a4(m, o, *_):
    setup = m.u64(o + 0x38)
    return 0 if m.u32(setup + 0x30) else m.u8(setup + 0x4A4)


@lifted(0x1399E20)
def within_setup_limit(m, o, *_):
    limit = setup_4a4(m, m.u64(o + 8))
    return int(limit != 0 and limit <= (setup_entry(m, o, 0) + 1) & 0xFFFFFFFF)


@lifted(0x158003C)
def next_listed(m, lst, *_):
    i = m.u8(lst + 0xA8)
    if i < m.u8(lst + 0xA6):
        m.put(lst + 0xA8, 1, i + 1)
        return m.u64(lst + 8 * i)
    return 0
