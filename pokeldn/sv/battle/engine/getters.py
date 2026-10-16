"""Pointer and field getters of the server's objects, named by offset until their meaning is known."""

from pokeldn.sv.battle.engine.calls import M32, _tail, _vtail, m_s32
from pokeldn.sv.battle.engine.statics import static_46d3f08
from pokeldn.sv.battle.machine import Pair, lifted


def _q(off):
    def get(m, o, *_): return m.u64(o + off)
    return get


for _addr, _off in ((0x1482534, 0x10), (0x1143584, 0x20), (0x1146E90, 0x38), (0x11409B4, 0x310),
                    (0x1361214, 0x78), (0x13813EC, 0x290), (0x11427FC, 0x68), (0x148253C, 0x70),
                    (0x114E480, 0x08), (0x11440E8, 0x10), (0x1148260, 0x13C0), (0x2885CD4, 0xF00),
                    (0x288D768, 0x1D80)):
    lifted(_addr)(_q(_off))


@lifted(0x147992C)
def flag_byte(m, o, i, *_): return m.u8(o + 8 + (i & 0xFFFF))


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


@lifted(0x114B1E4)
def bits_0_7(m, o, *_): return m.u16(o + 2) & 0x7F


@lifted(0x114B1F0)
def bits_7_14(m, o, *_): return m.u16(o + 2) >> 7 & 0x7F


@lifted(0x114B1FC)
def bit_30(m, o, *_): return m.u8(o + 3) >> 6 & 1


@lifted(0x114AB84)
def bit_31(m, o, *_): return int(m.s(o + 2, 2) < 0)


@lifted(0x2D171C0)
def kind_2_2d171c0(m, out, *_):
    m.put(out, 4, 2)
    return m.main + 0x44F9F20


@lifted(0x1380C48)
def nop(m, *_): return


@lifted(0x1820F40)
def copy_0x24(m, dst, src, *_):
    m.write(dst, m.read(src, 0x24))
    return dst


@lifted(0x16962F0)
def entry_b8_c(m, o, *_):
    e = m.u64(m.u64(m.u64(o + 0x38) + 0x78) + 0xB8)
    return m.u32(e + 0xC) if e else 0


@lifted(0x114DC38)
def zero_0x70(m, o, *_): return int(m.u32(o + 0x70) == 0)


@lifted(0x288D980)
def below_2(m, v, *_): return int(v & 0xFF < 2)


@lifted(0x1143354)
def plus_8(m, o, *_): return (o + 8) & 0xFFFFFFFFFFFFFFFF


@lifted(0x113E080)
def with_one(m, v, *_): return Pair(v & 0xFFFFFFFF, 1)


@lifted(0x288DA88)
def count_0x1c(m, o, *_):
    m.put(o + 0x1C, 4, m.u32(o + 0x1C) + 1)


@lifted(0x283D5E0)
def entry_18(m, o, i, *_):
    """Tail call of 0x283c90c on [o+0x38]: the u64 at +0x18 of entry i (below 0x86), or 0."""
    i &= 0xFFFF
    if i < 0x86:
        e = m.u64(m.u64(m.u64(o + 0x38) + 0x78) + 8 + 8 * i)
        if e:
            return m.u64(e + 0x18)
    return 0


@lifted(0x2D1FE78)
def hash_aa4611a0(m, *_): return 0xAA4611A011782F5A


@lifted(0xFA9128)
def set_30_from(m, o, src, *_):
    m.put(o + 0x30, 8, m.u64(src))


@lifted(0xFB00D0)
def get_10(m, o, *_): return m.u64(o + 0x10)


@lifted(0xFB00B8)
def get_190(m, o, *_): return m.u64(o + 0x190)


@lifted(0x2A1D994)
def is_entry_58(m, o, v, *_):
    """0 when byte +0x710 of [o+0x50] is set, else whether the u32 at +0x58 equals v."""
    if m.u8(m.u64(o + 0x50) + 0x710):
        return 0
    return int(m.u32(o + 0x58) == v & 0xFFFFFFFF)


@lifted(0xFA91A0)
def draw_five(m, o, *_):
    """Five u16 values of 0xfa91f8 on [o+0x30] stored at +0x98..+0xa0."""
    r = 0
    for k in range(5):
        r = m.call(m.main + 0xFA91F8, m.u64(o + 0x30))
        m.put(o + 0x98 + 2 * k, 2, r)
    return r


@lifted(0xFA47B4)
def set_40_x2(m, o, src, *_):
    m.put(o + 0x40, 8, m.u64(src))
    m.put(o + 0x48, 8, m.u64(src + 8))
    return o


@lifted(0xFA47E4)
def set_40_x3(m, o, src, *_):
    m.put(o + 0x40, 8, m.u64(src))
    m.put(o + 0x48, 8, m.u64(src + 8))
    m.put(o + 0x50, 8, m.u64(src + 0x10))
    return o


@lifted(0x10E244C)
def set_id_byte(m, p, ident, b, *_):
    m.put(p, 4, ident); m.put(p + 4, 1, b)


@lifted(0x11438A4)
def byte_equals(m, p, v, *_):
    return int(m.u8(p) == v & 0xFF)


@lifted(0x114B1DC)
def plus_4(m, p, *_):
    return (p + 4) & 0xFFFFFFFFFFFFFFFF


# Index permutation at 0x3c69ef0 (s64 x 14) into the 16-byte entries at 0x44f11c8.
_ORDER_3C69EF0 = (0, 1, 2, 3, 4, 5, 7, 6, 8, 9, 10, 11, 12, 13)


@lifted(0x114C070)
def entry_44f11d0(m, i, *_):
    i &= 0xFFFFFFFF
    if i > 0xD:
        return 0
    return m.u64(m.main + 0x44F11D0 + _ORDER_3C69EF0[i] * 0x10)


@lifted(0x1150ED0)
def state_is_1(m, o, *_):
    return int(m.u32(o + 0x70) == 1)


@lifted(0x11531D4)
def grid_entry(m, o, row, col, *_):
    """Tail call into 0x1723914 on [[o+0x10]+0x210]: entry (row < 4, signed col <= 4) of a 4x5 grid at +0x30."""
    base = m.u64(m.u64(o + 0x10) + 0x210)
    row &= 0xFF; col &= 0xFFFFFFFF
    if row > 3 or (col if col < 0x80000000 else col - (1 << 32)) > 4:
        return 0
    return m.u64((base + row * 0x28 + col * 8 + 0x30) & 0xFFFFFFFFFFFFFFFF)


@lifted(0x1794040)
def pack_kind_1(m, a, b, c, *_):
    return Pair(a & 0xFFFFFFFF, ((c & 0xFFFF) << 9) | ((b << 3) & 0x1F8) | 1)


@lifted(0x1794970)
def pack_kind_4(m, a, b, c, *_):
    return Pair(a & 0xFFFFFFFF, ((b & 0xFFFFFFFF) << 26) | ((c & 0x3F) << 3) | 4)


@lifted(0x28616B0)
def pack_kind_2(m, a, b, *_):
    return Pair(a & 0xFFFFFFFF, ((b << 3) & 0x1F8) | 2)


@lifted(0x171A7EC)
def tenth(m, v, *_):
    return (v & 0xFFFF) // 10


@lifted(0x2A10D80)
def nothing(m, *_):
    return


@lifted(0x2D174A0)
def kind_1_44fa3c0(m, out, *_):
    m.put(out, 4, 1)
    return m.main + 0x44FA3C0


@lifted(0x2D10C60)
def kind_1_44f40d0(m, out, *_):
    m.put(out, 4, 1)
    return m.main + 0x44F40D0


@lifted(0x2888AB8)
def count_reached(m, o, *_):
    return int((m.u32(o + 0x10) >> 3 & 0x3F) <= m.u32(o + 0x1C))


@lifted(0x284D154)
def set_word_48(m, o, i, v, *_):
    m.put(o + (i & 0xFF) * 4 + 0x48, 4, v)


def _copy_0x24(m, dst, src, *_):
    m.write(dst, m.read(src, 0x24))
    return dst


lifted(0x287ECA8)(_copy_0x24)
lifted(0x28800B8)(_copy_0x24)


@lifted(0x2888170)
def set_word_4(m, o, i, v, *_):
    """Word i from +4 when i is below the count in bits 7..13 of the u16 at +2."""
    i &= 0xFF
    if i < (m.u16(o + 2) >> 7 & 0x7F):
        m.put(o + i * 4 + 4, 4, v)


@lifted(0x284DCD0)
def entry_44f3f98(m, i, *_):
    i &= 0xFFFFFFFF
    return m.u64(m.main + 0x44F3F98 + i * 0x10) if i < 0x13 else 0


@lifted(0x1769890)
def max_s32(m, a, b, *_):
    sa = m_s32(a); sb = m_s32(b)
    return (b if sa < sb else a) & 0xFFFFFFFF


@lifted(0xE7E3C8)
def entry_0x38(m, o, i, *_):
    i &= 0xFFFFFFFF
    return (o + i * 0x38 + 0x28) & 0xFFFFFFFFFFFFFFFF if i < 5 else 0


@lifted(0x17286D0)
def div_or_1(m, a, b, *_):
    a &= 0xFFFFFFFF; b &= 0xFFFFFFFF
    return a // (b or 1)


@lifted(0x184A110)
def packed_index(m, o, *_):
    """The index packed in the u64 at +8: bits 3..8 for kind 3, bits 26..57 (low 32) for kind 4, else 0."""
    v = m.u64(o + 8)
    kind = v & 7
    if kind == 3:
        return v >> 3 & 0x3F
    if kind == 4:
        return v >> 26 & 0xFFFFFFFF
    return 0


@lifted(0x2D0E080)
def kind_of_index(m, out, i, *_):
    """(kind, descriptor) for i in 1..4 from 0x3baa850 and the pointers at 0x44f14b0; else (1, 0x44f1448)."""
    j = (i - 1) & 0xFF
    if j > 3:
        m.put(out, 4, 1)
        return m.main + 0x44F1448
    m.put(out, 4, (2, 3, 3, 2)[j])   # 0x3baa850
    return m.u64(m.main + 0x44F14B0 + 8 * j)


@lifted(0x288D990)
def start_or_count(m, o, src, *_):
    n = m.u32(o + 0x20)
    if n == 0:
        m.put(o + 0x1C, 8, 0x100000000)
        m.write(o + 8, m.read(src, 0x10))
        return 1
    limit = m.call(m.main + 0x288FCD8, m.u32(o + 0x18)) & 0xFFFFFFFF
    if n >= limit:
        return 0
    m.put(o + 0x20, 4, m.u32(o + 0x20) + 1)
    return 1


@lifted(0x2888224)
def all_clear_then_25(m, p, *_):
    """1 if any of the 37 bytes from p is set, else the byte at +0x25."""
    if any(m.read(p, 0x25)):
        return 1
    return m.u8(p + 0x25)


@lifted(0x2853340)
def is_last_kind_1(m, o, obj, *_):
    """Whether the u64 at o+8 is kind 1 with index (bits 3..8) one below vf 0x68(obj, [0x46e2700])."""
    n = m.vcall(obj, 0x68, m.u64(m.main + 0x46E2700))
    v = m.u64(o + 8)
    return int(v & 7 == 1 and (v >> 3 & 0x3F) == (n - 1) & 0xFFFFFFFF)


@lifted(0x1381540)
def has_10d3f10(m, a, b=0, *_):
    return int(m.call(m.main + 0x10D3F10, a, b) != 0)


@lifted(0x92E438)
def field_1f0(m, o, *_):
    return m.u64(o + 0x1F0)


@lifted(0xFA91F8)
def u16_8c(m, o, *_):
    return m.u16(o + 0x8C)


@lifted(0xFA01F8)
def set_u16_slot(m, o, i, v, *_):
    i &= 0xFF
    if i <= 4:
        m.put(o + 0xA + 2 * i, 2, v)


@lifted(0xFA0330)
def nothing_fa0330(m, *_):
    return


@lifted(0xE7E284)
def field_30_e7e284(m, o, *_):
    return m.u64(o + 0x30)


@lifted(0xFB00C8)
def field_30_fb00c8(m, o, *_):
    return m.u64(o + 0x30)


@lifted(0x126B014)
def byte_e2(m, o, *_):
    return m.u8(o + 0xE2)


@lifted(0x13F5EF8)
def field_150(m, o, *_):
    return m.u64(o + 0x150)


@lifted(0x18B7DB4)
def register_by_byte(m, o, p, *_):
    """The entry for p's byte +0xe2 in the map at o+0x1a0 (0x18b7e00) takes p at +0x30."""
    with m.frame(0x10) as k:
        m.put(k, 4, m.call(m.main + 0x126B014, p) & 0xFF)
        r = m.call(m.main + 0x18B7E00, o + 0x1A0, k)
    if r:
        m.put(r + 0x30, 8, p)
    return r


@lifted(0x14C7890)
def is_1_or_6(m, v, *_): return int(v & 0xFF in (1, 6))


@lifted(0x114B1D4)
def u16_at_0(m, p, *_): return m.u16(p)


@lifted(0x17CE3AC)
def low7_of_2(m, p, *_): return int(m.u8(p + 2) & 0x7F != 0)


@lifted(0x1149380)
def entry_of_five(m, o, i, *_):
    i &= 0xFF
    return m.u64(o + 8 + 8 * i) if i < 5 else 0


@lifted(0x139B698)
def current_c4_entry(m, o, *_):
    base = m.u64(m.u64(o + 0x40) + 8)
    return base + m.u8(base + 0x938) * 0xC4 + 8


@lifted(0x114A934)
def first_byte_of_2a0(m, o, *_):
    with m.frame(0x10) as p:
        m.call_void(m.main + 0x113FA64, m.call(m.main + 0x114A964, m.u64(o + 0x78)), p, p + 8)
        return m.u8(p)


@lifted(0x114E498)
def entry_38(m, o, i, *_):
    i &= 0xFF
    return 0 if i > 4 else m.u64(m.u64(o + 0x10) + 0x30) + i * 0x38 + 0x28


@lifted(0x10E2474)
def copy_5(m, dst, src, *_):
    m.put(dst, 4, m.u32(src)); m.put(dst + 4, 1, m.u8(src + 4))


@lifted(0x1380DB8)
def count_sign(m, o, e, n, *_):
    """Signal the sign of `n` (0x15 positive, 0x16 negative) to [e+8] through slot 0x508, unless the
    byte at e+0x10 is 8."""
    if m.u8(e + 0x10) == 8:
        return
    n &= 0xFFFFFFFF
    if n == 0:
        return
    return _vtail(m, m.u64(e + 8), 0x508, 0x16 if n & 0x80000000 else 0x15)


@lifted(0x2D19610)
def advance_2d0(m, o, ident, *_):
    s = m.u64(m.u64(o + 0x38) + 0x78)
    p = m.u64(s + 0x20)
    if (m.u32(p + 0xC) if p else 0) != ident & 0xFFFFFFFF:
        return
    q = m.u64(s + 0x2D0)
    if q == 0 or m.u8(q + 0xA) > 1:
        return
    m.put(q + 0xC, 4, 1)
    if m.u8(q + 0xA) == 1:
        m.put(q + 0xA, 1, 2)


@lifted(0x1360CDC)
def set_41(m, e, v, *_): m.put(e + 0x41, 1, v & 1)


@lifted(0x287B2D4)
def count_outcome(m, counters, pokecon, attacker, target, kind, *_):
    """Count one outcome in the u16 counters (at most 9999): +8 / +0xc / +0xa by `kind` (0, below 8,
    8 and up; 7 is not counted) on one side, +0xe / +0x12 / +0x10 on the other, picked by the two
    battlers' classes in the setup's map; nothing when 0x118ab58 holds or both classes are set."""
    a = m.vcall(attacker, 0x98) & 0xFFFFFFFF
    t = m.vcall(target, 0x98) & 0xFFFFFFFF

    def cls(ident):
        p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(pokecon + 0x290) + 8) + 0x50), ident)
        return 0 if p == 0 or m.s(p, 4) >= 5 else m.u32(p) & 0xFF
    ca, ct = cls(a), cls(t)
    r = m.call(m.main + 0x118AB58, m.u64(pokecon + 0x290), a, t)
    kind &= 0xFF
    if r & 1 or (ca and ct):
        return
    offs = (8, 0xC, 0xA) if ca == 0 else (0xE, 0x12, 0x10)
    if kind == 7:
        return
    at = counters + (offs[0] if kind == 0 else offs[1] if kind < 8 else offs[2])
    v = m.u16(at)
    if v <= 0x270E:
        m.put(at, 2, v + 1)


@lifted(0x287A68C)
def core_b80208(m, b, *_):
    return _tail(m, m.main + 0xB80208, m.u64(m.u64(b + 0x48) + 0x70))


@lifted(0x2A1C178)
def is_zero_u16(m, _o, v, *_): return int(v & 0xFFFF == 0)


@lifted(0xFA6268)
def set_30(m, p, v, *_): m.put(p + 0x30, 8, v)


@lifted(0xFB00C0)
def field_170(m, p, *_): return m.u64(p + 0x170)


@lifted(0xFB00D8)
def field_1d0(m, p, *_): return m.u64(p + 0x1D0)


@lifted(0xFA58C0)
def byte_e3(m, p, *_): return m.u8(p + 0xE3)


@lifted(0x16F814C)
def byte_712_of_38(m, p, *_): return m.u8(m.u64(p + 0x38) + 0x712)


@lifted(0xFA38C8)
def kind_2_in_37(m, a, b, *_):
    """1 when a is 2 and b - 1 (0..5) is a set bit of 0x37."""
    k = (b - 1) & 0xFFFFFFFF
    if a & 0xFFFFFFFF == 2 and k & 0xFF <= 5:
        return 0x37 >> (k & 0x1F) & 1
    return 0


@lifted(0xFA47C8)
def copy_24_to_40(m, p, src, *_):
    m.put(p + 0x40, 8, m.u64(src)); m.put(p + 0x50, 8, m.u64(src + 0x10)); m.put(p + 0x48, 8, m.u64(src + 8))


@lifted(0xFA0154)
def spread_8c(m, o, dst, *_):
    """0xfa01f8(0xfa01f0(dst), i, u16 o+0x8c) for i in 0..4."""
    for i in range(4):
        m.call_void(m.main + 0xFA01F8, m.call(m.main + 0xFA01F0, dst), i, m.u16(o + 0x8C))
    return _tail(m, m.main + 0xFA01F8, m.call(m.main + 0xFA01F0, dst), 4, m.u16(o + 0x8C))


@lifted(0xF7C230)
def f_f7c230(m, rec, *_): return m.u8(rec + 0x43)


@lifted(0xF7BB80)
def f_f7bb80(m, v, *_):
    return _tail(m, m.main + 0x20FAA24, v)


@lifted(0xF803C8)
def f_f803c8(m, o, *_): return m.u32(o + 0x38)


@lifted(0x1752268)
def f_1752268(m, o, *_): return m.u64(o + 0x11C0)


@lifted(0x1752184)
def f_1752184(m, o, *_): return m.u64(o + 0x11E0)


@lifted(0x28363E0)
def descriptor_shift(m, d, n, *_):
    """A descriptor of kind 2 or 4 (low bits & 0x1c7) moves its index (bits 3..8) by n."""
    for kind in (2, 4):
        v = m.u64(d + 8)
        if v & 0x1C7 == kind:
            i = (((v + (n << 3)) & M32) >> 3) & 0x3F
            m.put(d + 8, 8, v & ~(0x3F << 3) | i << 3)


@lifted(0x2836430)
def descriptor_set_count(m, d, n, *_):
    """A descriptor of kind 1..4 (low 3 bits) takes n as its u16 at bits 9..24."""
    v = m.u64(d + 8)
    if 1 <= v & 7 <= 4:
        m.put(d + 8, 8, v & ~(0xFFFF << 9) | (n & 0xFFFF) << 9)


@lifted(0x13603FC)
def true_13603fc(m, *_): return 1


@lifted(0x283E2A8)
def f_283e2a8(m, o, *_): return m.u64(o + 0xE20)


@lifted(0x18675D8)
def f_18675d8(m, o, *_): return m.u64(o + 0x1580)


@lifted(0x113EE04)
def f_113ee04(m, o, *_):
    return _tail(m, m.main + 0x144B6C8, m.u64(o + 8))


@lifted(0x287F1DC)
def field_1380(m, o, *_):
    return m.u64(o + 0x1380)


@lifted(0x1580E18)
def get_1860(m, o, *_): return m.u64(o + 0x1860)


@lifted(0x288A9C8)
def run_1580e20(m, o, b, *_):
    with m.frame(0x10) as f:
        m.put(f + 8, 8, b)
        x = m.call(m.main + 0x1580E18, m.call(m.main + 0x1361214, o, b), b)
        return _tail(m, m.main + 0x1580E20, x, f, f + 8)


@lifted(0x184A028)
def drop_entries_of(m, o, key, *_):
    """Clear every tagged 16-byte entry (+0x80, +0x90, +0xa0, then 46 from +0xb0) whose 0x184a110 value is
    `key`; clearing +0xa0 also clears +0x110 and byte +0x399."""
    key &= M32
    if not key:
        return
    for off in (0x80, 0x90, 0xA0):
        e = o + off
        if m.u8(e + 8) & 7 and m.call(m.main + 0x184A110, e) & M32 == key:
            m.write(e, bytes(16))
            if off == 0xA0:
                m.put(o + 0x399, 1, 0)
                m.write(o + 0x110, bytes(16))
    for i in range(0, 0x2E0, 0x10):
        e = o + 0xB0 + i
        if m.u8(e + 8) & 7 and m.call(m.main + 0x184A110, e) & M32 == key:
            m.write(e, bytes(16))


@lifted(0x1360F04)
def get_1320(m, o, *_): return m.u64(o + 0x1320)


@lifted(0x134ED30)
def field_14(m, o, *_):
    return m.u32(o + 0x14)


@lifted(0x113FA5C)
def store_byte(m, p, v, *_):
    m.put(p, 1, v)


@lifted(0x2888998)
def field_1f60(m, o, *_):
    return m.u64(o + 0x1F60)


@lifted(0x2882BDC)
def field_840(m, o, *_):
    return m.u64(o + 0x840)


@lifted(0x2882C58)
def field_860(m, o, *_):
    return m.u64(o + 0x860)


@lifted(0x288AFA0)
def field_6c0(m, o, *_):
    return m.u64(o + 0x6C0)


@lifted(0x288B040)
def field_700(m, o, *_):
    return m.u64(o + 0x700)


@lifted(0x1579A90)
def field_1bc0(m, o, *_):
    return m.u64(o + 0x1BC0)


@lifted(0x2880F5C)
def field_1ca0(m, o, *_):
    return m.u64(o + 0x1CA0)


def _copy(m, dst, src, n):
    m.write(dst, m.read(src, n))


@lifted(0x113E06C)
def setup_3c(m, o, *_):
    return m.u64(o + 0x38) + 0x3C


@lifted(0x113E058)
def setup_byte_41(m, o, *_):
    return m.u8(m.u64(o + 0x38) + 0x41)


@lifted(0x1145AA0)
def byte_at(m, p, *_):
    return m.u8(p)


@lifted(0x113DE78)
def byte_set(m, p, *_):
    return int(m.u8(p) != 0)


@lifted(0x114E488)
def zero_114e488(m, *_):
    return 0


@lifted(0x2A10D7C)
def identity_2a10d7c(m, x, *_):
    return x


@lifted(0x2D14970)
def kind_2(m, p, *_):
    m.put(p, 4, 2)
    return m.main + 0x44F5F10
