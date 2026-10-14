"""Lifted battle server functions, batch 1 (moved to their topic module once reviewed)."""

from pokeldn.sv.battle.engine import flatbuffer as fb  # noqa: F401
from pokeldn.sv.battle.engine.containers import data_record
from pokeldn.sv.battle.engine.data import static_table
from pokeldn.sv.battle.machine import Pair, UnliftedCall, lifted  # noqa: F401


@lifted(0x10E244C)
def set_id_byte(m, p, ident, b, *_):
    m.put(p, 4, ident); m.put(p + 4, 1, b)


@lifted(0x10E2464)
def clear_id_byte(m, p, *_):
    m.put(p, 4, 0); m.put(p + 4, 1, 10)


@lifted(0x11438A4)
def byte_equals(m, p, v, *_):
    return int(m.u8(p) == v & 0xFF)


@lifted(0x1149604)
def init_0x4b(m, p, *_):
    m.put(p, 8, 0xE00000000); m.put(p + 8, 2, 0); m.put(p + 0x18, 8, 0); m.put(p + 0x10, 4, 0)
    m.put(p + 0x20, 2, 0x9C)
    for o in (0x24, 0x2C, 0x34, 0x3C, 0x43):
        m.put(p + o, 8, 0)


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


@lifted(0x1380C4C)
def clear_0x19(m, p, *_):
    m.put(p + 0x18, 1, 0); m.put(p, 8, 0); m.put(p + 8, 8, 0); m.put(p + 0x10, 8, 0)


@lifted(0x13DF9D4)
def side_slot(m, o, side, i, *_):
    side &= 0xFF; i &= 0xFFFFFFFF
    si = i if i < 0x80000000 else i - (1 << 32)
    if si > 0x12 or side > 1:
        return 0
    return (m.u64(o + 0x90) + side * 0x2F8 + i * 0x28 + 8) & 0xFFFFFFFFFFFFFFFF


@lifted(0x1533CA0)
def percent_round(m, a, b, *_):
    """a * b / 100 (32-bit), rounded half up."""
    v = (a * b) & 0xFFFFFFFF
    q, r = divmod(v, 100)
    return q + 1 if r > 0x31 else q


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


@lifted(0x1380EA4)
def record_field18_byte(m, o, i, *_):
    """Byte i of the 3-byte entry in field 18 of the data record for the u16 id at o+8; 0 when i > 2."""
    i &= 0xFF
    if i > 2:
        return 0
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    rec = data_record(m, table, m.u16(o + 8))
    off = m.u16(rec - m.s(rec, 4) + 0x28)   # read without the vtable size check, as the game does
    return m.u8(rec + off + 3 * i)


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


def m_s32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v & 0x80000000 else v


@lifted(0xE7E3C8)
def entry_0x38(m, o, i, *_):
    i &= 0xFFFFFFFF
    return (o + i * 0x38 + 0x28) & 0xFFFFFFFFFFFFFFFF if i < 5 else 0


def _owner_id(m, o, slot):
    """The u32 id (+0xc) of the object at [[o+0x38]+0x78]+slot, 0 when there is none."""
    p = m.u64(m.u64(m.u64(o + 0x38) + 0x78) + slot)
    return m.u32(p + 0xC) if p else 0


def _mark_pending(m, rec):
    """A record whose state byte (+0xa) is 0 or 1 gets +0xc = 1, and state 1 moves to 2."""
    if not rec or m.u8(rec + 0xA) > 1:
        return 0
    m.put(rec + 0xC, 4, 1)
    if m.u8(rec + 0xA) == 1:
        m.put(rec + 0xA, 1, 2)
    return 1


@lifted(0x2844C10)
def mark_pending_248(m, o, ident, key, *_):
    root = m.u64(m.u64(o + 0x38) + 0x78)
    if _owner_id(m, o, 0x28) != ident & 0xFFFFFFFF:
        return 0
    p = m.u64(root + 0xF8)
    if (m.u32(p + 0xC) if p else 0) & 0xFFFF != key & 0xFFFF:
        return 0
    return _mark_pending(m, m.u64(root + 0x248))


@lifted(0x2D1A5F0)
def mark_pending_298(m, o, ident, *_):
    if _owner_id(m, o, 0x18) == ident & 0xFFFFFFFF:
        _mark_pending(m, m.u64(m.u64(m.u64(o + 0x38) + 0x78) + 0x298))


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


@lifted(0x288C730)
def clear_slot(m, o, i, *_):
    """Falls into 0x288c73c on [[o+0x10]+0x70]: clears slot i (signed i <= 13, flag at +0xa8 + 4i)."""
    base = m.u64(m.u64(o + 0x10) + 0x70)
    i &= 0xFFFFFFFF
    if m_s32(i) > 0xD:
        return 0
    flag = (base + i * 4 + 0xA8) & 0xFFFFFFFFFFFFFFFF
    if m.u32(flag) == 0:
        return 0
    a = base + 8 + i * 0x10; b = base + 8 + i * 4; c = base + i * 0x2C
    m.put(a + 0x348, 8, 0); m.put(a + 0x340, 8, 0)
    m.put(b + 0x30, 4, 0); m.put(b + 0x68, 4, 0); m.put(flag, 4, 0)
    m.put(c + 0x108, 4, 0)
    m.put(c + 0xF8, 8, 0); m.put(c + 0x100, 8, 0)
    m.put(c + 0xE8, 8, 0); m.put(c + 0xF0, 8, 0)
    m.put(c + 0xE0, 8, 0)
    return 1


# Stage kinds 1..7 -> the stage bytes at +0x414..+0x41a.
def _stage_byte(kind):
    kind &= 0xFFFFFFFF
    return 0x413 + kind if 1 <= kind <= 7 else None


@lifted(0x2D3D2D0)
def stage_can_move(m, o, kind, up, *_):
    """Whether the signed stage byte can still rise (up > 0: below 12) or fall (above 0)."""
    off = _stage_byte(kind)
    v = m.s(o + off, 1) if off else 0
    return int(v < 0xC) if m_s32(up) > 0 else int(v > 0)


@lifted(0x2D3D48C)
def stage_raise(m, o, kind, n, *_):
    """Raise a stage byte by n (u8), capped at 12; returns the amount added."""
    off = _stage_byte(kind)
    if not off:
        return 0
    v = m.s(o + off, 1)
    if v > 0xB:
        return 0
    r = (0xC - v) if v + (n & 0xFF) > 0xC else n
    r &= 0xFFFFFFFF
    m.put(o + off, 1, r + v)
    return r


def _boost_if_kind(m, o, ident, kind):
    """0x2853510: when the owner id matches and the action kind (0x16962f0) is `kind` with a nonzero
    [[o+0x48]+0x48], tail-calls 0x1353738([o+0x38], 0x34, 0x1333)."""
    if _owner_id(m, o, 0x20) != ident & 0xFFFFFFFF:
        return
    if m.call(m.main + 0x16962F0, o) & 0xFF != kind & 0xFF:
        return
    if m.u32(m.u64(o + 0x48) + 0x48) == 0:
        return
    m.call_void(m.main + 0x1353738, m.u64(o + 0x38), 0x34, 0x1333)


@lifted(0x285A750)
def boost_if_kind_11(m, o, ident, *_):
    _boost_if_kind(m, o, ident, 0x11)


def _tail(m, address, *args):
    """A tail call: the callee's result as it is (None from a void callee)."""
    from pokeldn.sv.battle.machine import FUNCTIONS
    fn = FUNCTIONS.get(address - m.main)
    if fn is None:
        raise UnliftedCall(f"main+0x{address - m.main:x}")
    return fn(m, *args)


def _vtail(m, obj, slot, *args):
    return _tail(m, m.u64(m.u64(obj) + slot), obj, *args)


@lifted(0x15808E4)
def any_1_or_3(m, p, *_):
    """0 if one of the first n (+0x14) words is 1, else 1 if one is 3, else 2; 2 when the flag at
    +0x18 is clear or n is 0."""
    n = m.u32(p + 0x14)
    if m.u8(p + 0x18) == 0 or n == 0:
        return 2
    words = [m.u32(p + 4 * i) for i in range(n)]
    if 1 in words:
        return 0
    return 1 if 3 in words else 2


@lifted(0x1589B18)
def rank_after_others(m, o, i, *_):
    """A byte at +8+i still at 5 (unset) becomes one more than the highest set byte of +8..+0xc."""
    i &= 0xFF
    if i > 4 or m.u8(o + 8 + i) != 5:
        return
    first = m.u8(o + 8)
    cur = 0xFF if first == 5 else first
    for k in range(1, 5):
        b = m.u8(o + 8 + k)
        sc = cur - 0x100 if cur & 0x80 else cur
        if b != 5 and not (sc > b):
            cur = b
    m.put(o + 8 + i, 1, cur + 1)


@lifted(0x1589A40)
def rule_value_290(m, o, key, *_):
    """The setup map's value for `key` ([[o+0x10]+0x290] owner), 0 when absent or above 4."""
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50), key)
    if p == 0:
        return 0
    v = m.s(p, 4)
    return v & 0xFFFFFFFF if v < 5 else 0


@lifted(0x1579420)
def fill_entry(m, o, a, entry, src, *_):
    v = m.u16(src + 2)
    if v == 0xFFFF:
        v = m.call(m.main + 0x1579490, m.u64(o + 8))
    m.put(entry + 0xA, 2, v)
    m.call_void(m.main + 0x1579498, m.u64(o + 0x10), a, entry, src)
    m.put(entry + 4, 1, 0); m.put(entry + 9, 1, 1)


@lifted(0xF74860)
def data_record_f74860(m, table, key, *_):
    return data_record(m, table, key)


@lifted(0x1382AE8)
def record_flag_34(m, o, *_):
    """Field 34 of the data record for the u16 id at o+8, as a bool."""
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    return int(fb.u8(m, data_record(m, table, m.u16(o + 8)), 34) != 0)


@lifted(0x20FB1E0)
def record_field16_pos(m, o, *_):
    """Field 16 (s8) of the data record for the u16 id at o+8, negatives as 0."""
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    rec = data_record(m, table, m.u16(o + 8))
    off = fb.field(m, rec, 16)
    return max(m.s(rec + off, 1), 0) if off else 0


@lifted(0x11416C0)
def mark_all_standing(m, o, *_):
    """Unless the setup flag bit 0x4d2 is set: for every party member still in the battle, vf 0x4b0(1)
    on its battler and command 0x51 (id, 1) on the queue."""
    from pokeldn.sv.battle.engine.containers import battler
    from pokeldn.sv.battle.engine.flow import first_standing, next_standing
    if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x499) >> 2 & 1:
        return
    with m.frame(0x20) as it:
        m.put(it, 8, m.u64(m.main + 0x46E2580) + 0x10)
        m.put(it + 8, 8, m.u64(o + 8)); m.put(it + 0x10, 8, m.u64(o + 0x10))
        m.put(it + 0x18, 2, 0); m.put(it + 0x1A, 1, 1)
        first_standing(m, it)
        with m.frame(8) as out:
            while next_standing(m, it, out):
                b = m.u64(out)
                owner = m.u64(o + 0x20)
                b2 = battler(m, m.u64(m.u64(m.u64(owner + 0x20) + 0x10) + 0x30), m.vcall(b, 0x98))
                m.vcall_void(b2, 0x4B0, 1)
                q = m.u64(owner + 0x18)
                m.call_void(m.main + 0x119AFF0, q, 0x51, m.vcall(b, 0x98) & 0xFFFFFFFF, 1)


@lifted(0x113AF40)
def position_of_side_index(m, mode, rule, side, index, *_):
    """The battle position (0..9) of the index-th position whose client is of side class `side`; 10 if none."""
    from pokeldn.sv.battle.engine.slots import SIDE_CLASS, slot_of_position
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


@lifted(0x1143D84)
def clear_member_list(m, lst, *_):
    m.write(lst, bytes(0x8F))
    m.put(lst + 0x90, 8, 0); m.put(lst + 0x98, 8, 0); m.put(lst + 0xA0, 8, 0); m.put(lst + 0xA8, 2, 0)


@lifted(0x288D228)
def add_u16_8(m, o, n, *_):
    p = m.call(m.main + 0xFA01F0, m.u64(o + 0x10))
    m.put(p + 8, 2, m.u16(p + 8) + n)


@lifted(0x2853340)
def is_last_kind_1(m, o, obj, *_):
    """Whether the u64 at o+8 is kind 1 with index (bits 3..8) one below vf 0x68(obj, [0x46e2700])."""
    n = m.vcall(obj, 0x68, m.u64(m.main + 0x46E2700))
    v = m.u64(o + 8)
    return int(v & 7 == 1 and (v >> 3 & 0x3F) == (n - 1) & 0xFFFFFFFF)


@lifted(0x114D360)
def check_114da8c(m, o, a, *_):
    return m.call(m.main + 0x114DA8C, m.call(m.main + 0x11440E8, m.u64(o + 0x10)), a) & 1


@lifted(0x14A08A4)
def bump_counter(m, o, ident, key, *_):
    """vf 0x780(key, vf 0x778(key) + 1) on the battler `ident`; a count of 0xff wraps to -1."""
    from pokeldn.sv.battle.engine.containers import battler
    b = battler(m, m.u64(m.u64(o + 0x10) + 0x30), ident)
    v = m.vcall(b, 0x778, key & 0xFFFFFFFF) & 0xFF
    return _vtail(m, b, 0x780, key & 0xFFFFFFFF, 0xFFFFFFFF if v == 0xFF else v + 1)


@lifted(0x1360318)
def apply_kind_4(m, o, _a, p, *_):
    """When vf 0x540(4) of the battler at [p] names an entry (0x13813f4), run 0x1361d0c on it, then
    tail-call 0x1361b20(o, [p], byte p+8)."""
    v = m.vcall(m.u64(p), 0x540, 4) & 0xFF
    if v == 0:
        return
    e = m.call(m.main + 0x13813F4, o, v)
    if e == 0:
        return
    m.call_void(m.main + 0x1361D0C, o, e, m.u8(p + 9))
    return _tail(m, m.main + 0x1361B20, o, m.u64(p), m.u8(p + 8))


@lifted(0x12708F4)
def init_action_list(m, o, *_):
    """Constructor of the action list (vtable 0x44ee488): bytes +0x60..+0x84 of each of the 66 entries
    (0x8c bytes from +8) and the count at +0x2420 are zeroed."""
    m.put(o, 8, m.main + 0x44EE488)
    for k in range(0x42):
        m.write(o + 0x68 + 0x8C * k, bytes(0x24))
    m.put(o + 0x2420, 1, 0)


@lifted(0x114358C)
def count_turn_limit(m, o, i, *_):
    """For a live slot i (signed i <= 13, flag at +0xa8 + 4i of [[[o+0x20]+0x10]+0x70]) with a limit
    (0x19375b0 on its +0x348 + 16i entry): count +0x38 + 4i up, 1 when it reaches the limit. Always
    queues command 0x44 (i)."""
    i &= 0xFFFFFFFF
    r = 0
    if m_s32(i) <= 0xD:
        base = m.u64(m.u64(m.u64(o + 0x20) + 0x10) + 0x70)
        if m.u32(base + i * 4 + 0xA8):
            limit = m.call(m.main + 0x19375B0, base + i * 0x10 + 0x348) & 0xFF
            if limit:
                n = (m.u32(base + i * 4 + 0x38) + 1) & 0xFFFFFFFF
                m.put(base + i * 4 + 0x38, 4, n)
                if n >= limit:
                    r = 1
    m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0x44, i)
    return r


@lifted(0x15323D4)
def note_targets(m, o, p, *_):
    """For each of the p[0] + p[1] entries (12 bytes from p+8: id, then byte +4, flags +6): mark the
    id's slot (0x1381420) in row [[[o+0x40]+8]+0x938] of the 0xc4-byte table: +0x25 = 1, +0x26 = 2
    (flag bit 1) or 1 (bit 0) from the first entry of that id with either, +0x27 = the first entry's
    byte (7 when none)."""
    def count():
        return m.u8(p) + m.u8(p + 1)
    if count() == 0:
        return
    t = m.u64(m.u64(o + 0x40) + 8)
    row = t + m.u8(t + 0x938) * 0xC4
    k = 0
    while True:
        ident = m.u32(p + 8 + 0xC * k)
        s = m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), ident) & 0xFF
        m.put(row + 3 * s + 0x25, 1, 1)
        v = 0
        for j in range(max(count(), 1) if count() else 0):
            if m.u32(p + 8 + 0xC * j) == ident:
                f = m.u8(p + 0xE + 0xC * j)
                if f & 2:
                    v = 2; break
                if f & 1:
                    v = 1; break
        m.put(row + 3 * s + 0x26, 1, v)
        v = 7
        for j in range(max(count(), 1) if count() else 0):
            if m.u32(p + 8 + 0xC * j) == ident:
                v = m.u8(p + 0xC + 0xC * j); break
        m.put(row + 3 * s + 0x27, 1, v)
        k += 1
        if k >= count():
            return


@lifted(0x1794478)
def record_field11_byte3(m, o, *_):
    """Byte 3 of field 11 of the data record for the u16 id at o+8 (read without the vtable size check)."""
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    rec = data_record(m, table, m.u16(o + 8))
    return m.u8(rec + m.u16(rec - m.s(rec, 4) + 0x1A) + 3)


@lifted(0x157BD30)
def drop_unmarked_members(m, o, _a, ctx, *_):
    """Walk the member list [ctx+0x18] with its cursor at +0xa8. A member whose id (vf 0x98) is in the
    ten (id, flag) pairs at [ctx+0x10] with the flag clear is removed (0x157bf08) and handed to
    0x287ef48 (when one member was listed or [ctx+8]+0x13 is clear) and 0x158137c. When [ctx+0x20] is
    set and the list was emptied with +0xa7 or +0xa9 set, tail-calls 0x157bf90(0x1143584(o), id, 3)."""
    lst = m.u64(ctx + 0x18)
    if m.u8(lst + 0xA6) == 0:
        return
    m.put(lst + 0xA8, 1, 0)
    while True:
        lst = m.u64(ctx + 0x18)
        i = m.u8(lst + 0xA8)
        if i >= m.u8(lst + 0xA6):
            break
        m.put(lst + 0xA8, 1, i + 1)
        b = m.u64(lst + 8 * i)
        if b == 0:
            break
        ident = m.vcall(b, 0x98) & 0xFFFFFFFF
        pairs = m.u64(ctx + 0x10)
        hit = next((pairs + 8 * k for k in range(10) if m.u32(pairs + 8 * k) == ident), None)
        if hit is None or m.u8(hit + 4):
            continue
        lst = m.u64(ctx + 0x18)
        n = m.u8(lst + 0xA6)
        flag = m.u8(m.u64(ctx + 8) + 0x13)
        m.call_void(m.main + 0x157BF08, lst, b)
        if n < 2 or flag == 0:
            m.call_void(m.main + 0x287EF48, o, m.u64(ctx), b, m.u64(ctx + 0x10))
        m.call_void(m.main + 0x158137C, o, m.u64(ctx), b)
    if m.u64(ctx + 0x20) == 0:
        return
    lst = m.u64(ctx + 0x18)
    if m.u8(lst + 0xA7) == 0 and m.u8(lst + 0xA9) == 0:
        return
    if m.u8(lst + 0xA6):
        return
    x = m.call(m.main + 0x1143584, o)
    return _tail(m, m.main + 0x157BF90, x, m.vcall(m.u64(ctx), 0x98) & 0xFFFFFFFF, 3)


def _filter_members(m, src, pokecon, b, dst, n, ident, keep):
    from pokeldn.sv.battle.engine.flow import add_member
    for i in range(n):
        x = m.u64(src + 8 * i)
        r = m.call(m.main + 0x118AB58, m.u64(pokecon + 0x290), ident, m.vcall(x, 0x98) & 0xFF)
        if x and r & 1 == keep:
            add_member(m, dst, x)


@lifted(0x1532554)
def members_related(m, src, pokecon, b, dst, *_):
    """Fill member list `dst` with the members of `src` that 0x118ab58 relates to battler b; their count."""
    n = m.u8(src + 0xA6)
    ident = m.vcall(b, 0x98) & 0xFF
    clear_member_list(m, dst)
    if n == 0:
        return 0
    _filter_members(m, src, pokecon, b, dst, n, ident, 1)
    return m.u8(dst + 0xA6)


@lifted(0x153268C)
def members_unrelated(m, src, pokecon, b, dst, *_):
    """Fill member list `dst` with the members of `src` that 0x118ab58 does not relate to battler b."""
    clear_member_list(m, dst)
    ident = m.vcall(b, 0x98) & 0xFF
    _filter_members(m, src, pokecon, b, dst, m.u8(src + 0xA6), ident, 0)
    return m.u8(dst + 0xA6)


def _rule_or_0(m, o, key):
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50), key)
    if p == 0:
        return None
    v = m.s(p, 4)
    return v & 0xFFFFFFFF if v < 5 else 0


@lifted(0x114D390)
def drop_raid_actions(m, o, lst, *_):
    """For each kind-1 action of the raid battler (0xf6fc68) in the action list, look up its class
    (setup map, key +0xc; class 5 redirects through 0x1138c38(o, byte +8)); when 0x114d824 gives a
    negative count for it, the battler's actions are removed (0x1148894) and 0x156616c(6, class) runs."""
    raid = m.call(m.main + 0xF6FC68, m.u64(m.u64(o + 0x10) + 0x310))
    if raid == 0 or m.u8(lst + 0x2420) == 0:
        return
    k = 0
    while True:
        e = lst + 8 + 0x8C * k
        if k & 0xFF < m.u8(lst + 0x2420):
            ident = m.u32(e)
            if ident == m.vcall(raid, 0x98) & 0xFFFFFFFF and m.u32(e + 4) == 1:
                v = _rule_or_0(m, o, m.u32(e + 0xC))
                if v is None:
                    cls = 0; v = 0
                else:
                    if v & 0xFF == 5:
                        b = m.call(m.main + 0x1138C38, o, m.u8(e + 8))
                        if b:
                            v = _rule_or_0(m, o, m.vcall(b, 0x98) & 0xFFFFFFFF) or 0
                    cls = v & 0xFF
                if cls != 5:
                    n = m.call(m.main + 0x114D824, m.u64(m.u64(o + 0x10) + 0x310), v)
                    if n & 0x8000:
                        m.call_void(m.main + 0x1148894, lst, m.vcall(raid, 0x98) & 0xFFFFFFFF)
                        m.call_void(m.main + 0x156616C, m.call(m.main + 0x1143584, o), 6, cls)
        k += 1
        if k >= m.u8(lst + 0x2420):
            return


@lifted(0x1143A30)
def set_and_queue_35(m, o, b, a, c, *_):
    """0x1143ab8([o+0x20], id, a, c), then command 0x35 (id, a & 0xff, c & 0xff)."""
    m.call_void(m.main + 0x1143AB8, m.u64(o + 0x20), m.vcall(b, 0x98) & 0xFFFFFFFF, a & 0xFFFFFFFF, c & 0xFFFFFFFF)
    q = m.u64(o + 0x18)
    return _tail(m, m.main + 0x119AFF0, q, 0x35, m.vcall(b, 0x98) & 0xFFFFFFFF, a & 0xFF, c & 0xFF)


@lifted(0x1360480)
def set_and_queue_41(m, o, a, b, *_):
    """0x1360524([o+0x20], id a, id b), then command 0x41 (id a, id b)."""
    x = m.u64(o + 0x20)
    ia = m.vcall(a, 0x98) & 0xFFFFFFFF
    m.call_void(m.main + 0x1360524, x, ia, m.vcall(b, 0x98) & 0xFFFFFFFF)
    q = m.u64(o + 0x18)
    ia = m.vcall(a, 0x98) & 0xFFFFFFFF
    return _tail(m, m.main + 0x119AFF0, q, 0x41, ia, m.vcall(b, 0x98) & 0xFFFFFFFF)


@lifted(0x1148470)
def set_and_queue_20(m, o, b, c, *_):
    """0x11484e4([o+0x20], id, c), then command 0x20 (id, c)."""
    m.call_void(m.main + 0x11484E4, m.u64(o + 0x20), m.vcall(b, 0x98) & 0xFFFFFFFF, c & 0xFFFFFFFF)
    q = m.u64(o + 0x18)
    return _tail(m, m.main + 0x119AFF0, q, 0x20, m.vcall(b, 0x98) & 0xFFFFFFFF, c & 0xFFFFFFFF)


@lifted(0x136078C)
def set_and_queue_6c(m, o, ident, *_):
    m.call_void(m.main + 0x13607C0, m.u64(o + 0x20), ident & 0xFFFFFFFF)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x6C, ident & 0xFFFFFFFF)


@lifted(0x136075C)
def battler_to_1360c00(m, o, ident, *_):
    from pokeldn.sv.battle.engine.containers import battler
    b = battler(m, m.u64(m.u64(o + 0x10) + 0x30), ident)
    return _tail(m, m.main + 0x1360C00, m.u64(o + 0x18), b)


@lifted(0x1360F0C)
def drop_handlers_of(m, o, ident, *_):
    """Remove every kind-0 handler of battler `ident` from the handler table [[[o+0x18]+8]+0xd0]: live
    ones (+0x44) through 0x13608e0, or 0x1360cdc(1) when +0x3f is set; repeats until none is found."""
    from pokeldn.sv.battle.engine.containers import battler, find_handler
    b = battler(m, m.u64(m.u64(o + 0x10) + 0x30), ident)
    owner = m.u64(o + 0x18)
    bid = m.vcall(b, 0x98) & 0xFFFFFFFF
    table = m.u64(m.u64(owner + 8) + 0xD0)
    h = find_handler(m, table, 0, bid)
    while h:
        if m.u8(h + 0x44):
            if m.u8(h + 0x3F) == 0:
                m.call_void(m.main + 0x13608E0, m.u64(m.u64(owner + 8) + 0xD0), h)
            else:
                m.call_void(m.main + 0x1360CDC, h, 1)
        h = find_handler(m, table, 0, bid)


@lifted(0x1381540)
def has_10d3f10(m, a, b=0, *_):
    return int(m.call(m.main + 0x10D3F10, a, b) != 0)


@lifted(0x1793E60)
def run_17942d0_with(m, v, *rest):
    """0x17942d0's result for a stack object (vtable [0x46ddad8] + 0x10, u16 v at +8)."""
    with m.frame(0x10) as f:
        m.put(f, 8, m.u64(m.main + 0x46DDAD8) + 0x10)
        m.put(f + 8, 2, v)
        return m.call(m.main + 0x17942D0, f, *rest[:6])


@lifted(0x288D9F0)
def queue_4a(m, q, a, b, src, *_):
    """Command 0x4a (a & 0xff, b, then the three values 0x174ae90 reads out of `src`)."""
    with m.frame(0x10) as f:
        m.put(f, 8, 0); m.put(f + 8, 4, 0)
        m.call_void(m.main + 0x174AE90, src, f + 4, f, f + 8)
        m.call_void(m.main + 0x119AFF0, q, 0x4A, a & 0xFF, b & 0xFFFFFFFF, m.u32(f + 4), m.u32(f), m.u32(f + 8))


@lifted(0x162B830)
def class_matches_95(m, o, ident, *_):
    """Whether battler `ident`'s class in the setup map equals the byte at [o+8]+0x95."""
    from pokeldn.sv.battle.engine.containers import battler
    b = battler(m, m.u64(m.u64(o + 0x10) + 0x30), ident)
    want = m.u64(o + 8)
    v = _rule_or_0(m, o, m.vcall(b, 0x98) & 0xFFFFFFFF)
    return int((v or 0) == m.u8(want + 0x95))


@lifted(0x1793EFC)
def build_target(m, x0, code, b, out, ctx, *_):
    """Pack a target descriptor for battler b from `code` (kind in bits 0..3, fields at bits 4 and 10)
    into the 16 bytes at `out`."""
    code &= 0xFFFFFFFF
    kind = code & 0xF
    f4, f10 = (code & 0xFFFF) >> 4 & 0x3F, code >> 10 & 0x3F

    def ident():
        return m.vcall(b, 0x98) & 0xFFFFFFFF
    if kind == 2:
        v = m.call(m.main + 0x179405C, ctx, f4, f10)
        r = (ident(), (v & 0x3F) << 3 | 2)
    elif kind == 1:
        r = m.call(m.main + 0x1794040, ident(), f10, f4)
    elif kind == 4:
        a = ident(); c = ident()
        r = m.call(m.main + 0x1794970, a, c, m.call(m.main + 0x179405C, ctx, f4, f10))
    elif kind == 3:
        a = ident()
        r = (a, (ident() & 0x3F) << 3 | 3)
    else:
        r = m.call(m.main + 0x1794120, x0, code, b, out, ctx)
    m.put(out, 8, r[0]); m.put(out + 8, 8, r[1])


@lifted(0x28680A0)
def boost_if_flag_4(m, o, ident, *_):
    """When the owner id matches and the battler named at +0x28 has vf 0x4d0(4), tail-calls
    0x1353738([o+0x38], 0x38, 0x2000)."""
    from pokeldn.sv.battle.engine.containers import battler
    if _owner_id(m, o, 0x20) != ident & 0xFFFFFFFF:
        return
    b = battler(m, m.u64(m.u64(o + 8) + 0x30), _owner_id(m, o, 0x28))
    if m.vcall(b, 0x4D0, 4) & 1:
        return _tail(m, m.main + 0x1353738, m.u64(o + 0x38), 0x38, 0x2000)


@lifted(0x17CE294)
def take_pending_code(m, _o, b, p, *_):
    """Consume the code at p (set to 0, or 6 for code 0x32 while vf 0x230 is nonzero); the result
    depends on the code: 0x31 gives vf 0x230, 0x32 vf 0x230 or 6 when vf 0x220(6), 0x33 0x17ce3c0
    (p kept when nonzero), anything else the code itself when vf 0x220(code)."""
    v = m.vcall(b, 0x230)
    code = m.u32(p)
    if code == 0x32:
        if v & 0xFFFF:
            m.put(p, 4, 6)
            return v
        r = 6 if m.vcall(b, 0x220, 6) & 1 else 0
    elif code == 0x31:
        r = v
    elif code == 0x33:
        r = m.call(m.main + 0x17CE3C0, b)
        if r & 0xFFFF:
            return r
        r = 0
    else:
        r = m.u32(p) if m.vcall(b, 0x220, code) & 1 else 0
    m.put(p, 4, 0)
    return r


_CODES_3C69DC4 = (0x7, 0xC, 0xD, 0xF, 0x17, 0xB)   # u16 x 6 at 0x3c69dc4


@lifted(0x2823BE0)
def code_at(m, i, *_):
    i &= 0xFFFFFFFF
    return _CODES_3C69DC4[i] if i <= 5 else 0


@lifted(0x17CE3C0)
def first_code_held(m, b, *_):
    """The first code of 0x2823be0's list for which vf 0x220 holds; 0 at the end of the list."""
    i = 0
    while True:
        v = m.call(m.main + 0x2823BE0, i) & 0xFFFFFFFF
        i += 1
        if v & 0xFFFF == 0 or m.vcall(b, 0x220, v) & 1:
            return v


@lifted(0x17CE354)
def maybe_114b0ac(m, o, a, p, *_):
    """When 0x17ce3ac(p) holds (bits 0..6 of the byte at p+2), tail-calls 0x114b0ac(0x1143584(o), a, p)."""
    if m.call(m.main + 0x17CE3AC, p) & 1 == 0:
        return
    return _tail(m, m.main + 0x114B0AC, m.call(m.main + 0x1143584, o), a & 0xFFFFFFFF, p)


@lifted(0x2872E70)
def kind_3_2872d60(m, o, a, *_):
    return _tail(m, m.main + 0x2872D60, o, a, 3)


@lifted(0x288DBD0)
def queue_49(m, o, b, src, *_):
    """Command 0x49 (id of b, then id of [src] and the u16 at src+8, or 0, 0 without src)."""
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    other = val = 0
    if src:
        other = m.vcall(m.u64(src), 0x98) & 0xFFFFFFFF
        val = m.u16(src + 8)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x49, ident, other, val)


@lifted(0x1437580)
def set_and_queue_38(m, o, a, *_):
    m.call_void(m.main + 0x14375B4, m.u64(o + 0x20), a & 0xFFFFFFFF)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x38, a & 0xFFFFFFFF)


# Event parameter frames, as the handlers inline them: a pool of 0x60 parameter records (pointers at
# pool + 8 + 32i, u16 kind at +8, used count at pool+0xc08) and a stack of 31 frames (stack+0x408).

def ev_push(m, ctx):
    """Open a frame: claim the next free record as a frame marker (kind 1), make the next frame current."""
    pool = m.u64(ctx + 0x38)
    c = m.u32(pool + 0xC08)
    while c <= 0x5F:
        e = m.u64(pool + 32 * c + 8)
        if m.u16(e + 8) == 0:
            if c <= 0x5E:
                m.put(e + 8, 2, 1)
                m.put(pool + 0xC08, 4, m.u32(pool + 0xC08) + 1)
            break
        c += 1
        m.put(pool + 0xC08, 4, c)
    stk = m.u64(ctx + 0x58)
    n = m.u32(stk + 0x408)
    if n <= 0x1E:
        m.put(stk + 0x408, 4, n + 1)
        stk = m.u64(ctx + 0x58)
        n = m.u32(stk + 0x408)
    m.put(ctx + 0x78, 8, m.u64(stk + 32 * n + 8))


def ev_param(m, ctx, kind, value, typ, slot):
    """Set parameter `kind` of the current frame (reusing a record of that kind above the used count,
    else the first free one) and note it in the frame at `slot`."""
    pool = m.u64(ctx + 0x38)
    i = m.u32(pool + 0xC08)
    while i < 0x60:
        k = m.u16(m.u64(pool + 32 * i + 8) + 8)
        if k == 0 or k == kind:
            break
        i += 1
    else:
        return
    e = m.u64(pool + 32 * i + 8)
    if e == 0:
        return
    m.put(e + 8, 2, kind); m.put(e + 0xC, 4, value); m.put(e + 0xA, 1, typ)
    m.put(e + 0x10, 8, 0); m.put(e + 0x18, 8, 0)
    m.put(m.u64(ctx + 0x78) + slot, 8, e)


def ev_pop(m, ctx):
    """Close the current frame: clear it, release its records back to the frame marker below."""
    stk = m.u64(ctx + 0x58)
    n = m.u32(stk + 0x408)
    if n:
        m.write(m.u64(stk + 32 * n + 8) + 8, bytes(0x430))
        m.put(stk + 0x408, 4, m.u32(stk + 0x408) - 1)
        stk = m.u64(ctx + 0x58)
        n = m.u32(stk + 0x408)
    m.put(ctx + 0x78, 8, m.u64(stk + 32 * n + 8))
    pool = m.u64(ctx + 0x38)
    c = m.u32(pool + 0xC08)
    if c == 0:
        return
    if c & 0xFFFF <= 0x5F:
        j = c & 0xFFFF
        while True:
            e = m.u64(pool + 32 * j + 8)
            if m.u16(e + 8) == 0:
                break
            m.put(e + 8, 2, 0)
            j += 1
            if j & 0xFFFF == 0x60:
                break
        c = m.u32(pool + 0xC08)
    c = (c - 1) & 0xFFFFFFFF
    m.put(pool + 0xC08, 4, c)
    m.put(m.u64(pool + 32 * c + 8) + 8, 2, 0)
    c = m.u32(pool + 0xC08)
    while c:
        c -= 1
        m.put(pool + 0xC08, 4, c)
        if m.u16(m.u64(pool + 32 * c + 8) + 8) == 1:
            m.put(pool + 0xC08, 4, c + 1)
            return


@lifted(0x157E064)
def event_c5(m, o, a, b, _x3, out, *_):
    """Unless vf 0x4e8 of b is 0x20: event 0xc5 with parameters 3 (id a), 4 (id b), 0x24 (that value),
    0x49 (1) and 0x56 ([out]); returns whether parameter 0x49 came back nonzero, [out] gets 0x56's."""
    m.put(out, 1, 1)
    v = m.vcall(b, 0x4E8) & 0xFFFFFFFF
    if v == 0x20:
        return 0
    ev_push(m, m.u64(o + 0x10))
    ctx = m.u64(o + 0x10)
    ev_param(m, ctx, 3, m.vcall(a, 0x98), 4, 0x20)
    ctx = m.u64(o + 0x10)
    ev_param(m, ctx, 4, m.vcall(b, 0x98), 4, 0x28)
    ev_param(m, m.u64(o + 0x10), 0x24, v, 4, 0x128)
    ev_param(m, m.u64(o + 0x10), 0x49, 1, 1, 0x250)
    ev_param(m, m.u64(o + 0x10), 0x56, m.u8(out), 1, 0x2B8)
    m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), 0xC5, 8, 1)
    frame = m.u64(m.u64(o + 0x10) + 0x78)
    p = m.u64(frame + 0x250)
    r = int(p != 0 and m.u32(p + 0xC) != 0)
    p = m.u64(frame + 0x2B8)
    m.put(out, 1, int(p != 0 and m.u32(p + 0xC) != 0))
    ev_pop(m, m.u64(o + 0x10))
    return r


@lifted(0x17776D8)
def event_bc_if_2a8(m, o, _a, p, *_):
    """When vf 0x2a8 of battler [p] is nonzero, tail-calls 0x1777748(0x1146e90(o), battler, byte p+4)."""
    from pokeldn.sv.battle.engine.containers import battler
    b = battler(m, m.u64(m.u64(o + 0x10) + 0x30), m.u32(p))
    if m.vcall(b, 0x2A8) & 0xFFFF == 0:
        return
    return _tail(m, m.main + 0x1777748, m.call(m.main + 0x1146E90, o), b, m.u8(p + 4))


@lifted(0x156616C)
def add_and_queue_85(m, o, kind, n, *_):
    m.call_void(m.main + 0x15661B0, m.u64(o + 0x20), kind & 0xFFFFFFFF, n & 0xFFFFFFFF)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x85, kind & 0xFF, n & 0xFFFFFFFF)


@lifted(0x15660D0)
def first_member_11493a0(m, o, lst, n, *_):
    """Walk the member list; at the first member 0x11493a0 accepts, tail-calls 0x156616c([o+0x20], 7, n)."""
    m.put(lst + 0xA8, 1, 0)
    if m.u8(lst + 0xA6) == 0:
        return
    i = 0
    while True:
        m.put(lst + 0xA8, 1, i + 1)
        b = m.u64(lst + 8 * i)
        if b == 0:
            return
        if m.call(m.main + 0x11493A0, m.u64(o + 0x10), m.vcall(b, 0x98) & 0xFFFFFFFF) & 1:
            return _tail(m, m.main + 0x156616C, m.u64(o + 0x20), 7, n & 0xFFFFFFFF)
        i = m.u8(lst + 0xA8)
        if i >= m.u8(lst + 0xA6):
            return


_CLASS_TABLES = {0: 0x3C6A450, 1: 0x3C6A455, 2: 0x3C6A45A}


@lifted(0x142A758)
def allies_present(m, mode, rule, slot, *_):
    """How many other client slots (0..4) are present (0xe7e2a0) and of the same side class as `slot`."""
    from pokeldn.sv.battle.engine.slots import SIDE_CLASS
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


def _pokemon_getters():
    from pokeldn.sv.battle.engine.pokemon import _getter
    lifted(0xBF41A8)(_getter(0, 0x1C, 2, 0, 0x4742290, False))     # block A +0x1c (u16)


_pokemon_getters()


@lifted(0x114DC24)
def queue_c1(m, o, a, b, *_):
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xC1, a & 0xFF, b & 0xFFFFFFFF)


@lifted(0x1149478)
def allies_plus_1(m, setup, *_):
    return (m.call(m.main + 0x142A758, m.u32(setup + 0x36C), m.u8(setup + 0x370), 0) & 0xFF) + 1


@lifted(0x171A804)
def set_and_queue_73(m, o, ident, a, b, *_):
    m.call_void(m.main + 0x171A850, m.u64(o + 0x20), ident & 0xFFFFFFFF, a & 0xFFFFFFFF, b & 0xFFFFFFFF)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x73, ident & 0xFFFFFFFF, a & 0xFF, b & 0xFFFF)


@lifted(0x2887F9C)
def count_and_queue_4a(m, o, side, i, src, *_):
    """When 0x288d980(side) holds and slot (side, i) of [o+0x10] accepts the count (0x288d990), queue
    command 0x4a for it; 1 when queued."""
    if m.call(m.main + 0x288D980, side & 0xFFFFFFFF) & 1 == 0:
        return 0
    e = m.call(m.main + 0x13DF9D4, m.u64(o + 0x10), side & 0xFFFFFFFF, i & 0xFFFFFFFF)
    if e == 0:
        return 0
    if m.call(m.main + 0x288D990, e, src) & 1 == 0:
        return 0
    m.call_void(m.main + 0x288D9F0, m.u64(o + 0x18), side & 0xFFFFFFFF, i & 0xFFFFFFFF, src)
    return 1


def _raid_id(m, rec):
    """The raid battler id the record caches at +0x18, looked up once while setup flag 0x4d2 is set."""
    if m.u8(m.u64(m.u64(rec + 8) + 0x38) + 0x499) >> 2 & 1 and m.u32(rec + 0x18) == 0:
        lst = m.call(m.main + 0x14B5634, m.u64(m.u64(rec + 0x10) + 0x30), 1)
        b = m.call(m.main + 0x114C614, lst, 0)
        if b:
            m.put(rec + 0x18, 4, m.vcall(b, 0x98))
    return m.u32(rec + 0x18)


def _class_of(m, o, ident):
    v = _rule_or_0(m, o, ident)
    return 0 if v is None else v


def _next_action_serial(m, o):
    c = m.u64(m.u64(o + 0x10) + 0x190)
    v = m.u32(c + 8)
    if v == 0:
        v = 1
        m.put(c + 8, 4, 1)
    m.put(c + 8, 4, m.u32(c + 8) + 1)
    return v


@lifted(0x114D528)
def raid_extra_actions(m, o, lst, *_):
    """For each side class (0..4) holding a non-raid battler with an action in the list, when 0x114d824
    gives the raid record a positive count for it, append a raid action (kind 0xc, that count as move)
    aimed at that battler and run 0x156616c(6, class)."""
    with m.frame(0x20 + 0x90) as f:
        ids, act = f, f + 0x20
        m.write(ids, bytes(0x14))
        n = m.u8(lst + 0x2420)
        k = 0
        while k < n:
            if k & 0xFF < n:
                e = lst + 8 + 0x8C * k
                ident = m.u32(e)
                rec = m.u64(m.u64(o + 0x10) + 0x310)
                if _raid_id(m, rec) != ident:
                    cls = _class_of(m, o, m.u32(e))
                    m.put(ids + 4 * cls, 4, m.u32(e))
            n = m.u8(lst + 0x2420)
            k += 1
        for cls in range(5):
            target = m.u32(ids + 4 * cls)
            if target == 0:
                continue
            cnt = m.call(m.main + 0x114D824, m.u64(m.u64(o + 0x10) + 0x310), cls) & 0xFFFF
            cnt = cnt - 0x10000 if cnt & 0x8000 else cnt
            if cnt < 1:
                continue
            m.write(act, bytes(0x8C))
            m.put(act + 0x88, 1, 5); m.put(act + 0x84, 4, 0x5400000); m.put(act + 4, 4, 0xC)
            m.put(act + 0x10, 2, cnt)
            m.put(act + 8, 1, m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), target))
            m.put(act + 0xC, 4, target)
            m.put(act + 0x28, 1, 8); m.put(act + 0x2C, 4, 0)
            m.put(act, 4, _raid_id(m, m.u64(m.u64(o + 0x10) + 0x310)))
            raid = _raid_id(m, m.u64(m.u64(o + 0x10) + 0x310))
            m.put(act + 0x88, 1, _class_of(m, o, raid)); m.put(act + 0x89, 2, 0)
            m.put(act + 0x84, 4, m.call(m.main + 0x11514B8, o, act, lst))
            m.put(act + 0x54, 4, _next_action_serial(m, o))
            m.call_void(m.main + 0x1820EB8, lst, act)
            m.call_void(m.main + 0x156616C, m.call(m.main + 0x1143584, o), 6, cls)


@lifted(0x114CE2C)
def raid_actions(m, o, _a, p, *_):
    """The raid battler's turn additions to the action list [p]: drop what 0x114d390 drops; when the raid
    record (+0x8c set, move +0x64 accepted by 0x114d360) has a pending kind-1 action (+0x89 clear) of its
    own, add one more action with one of its moves (vf 0x730) aimed at a battler of the second action
    list [o+0x48]; then the per-class extras (0x114d528)."""
    from pokeldn.sv.battle.engine.containers import battler
    if m.call(m.main + 0x114D34C, m.u64(m.u64(o + 0x10) + 0x310)) & 1 == 0:
        return
    lst = m.u64(p)
    m.call_void(m.main + 0x114D390, o, lst)
    rec = m.u64(m.u64(o + 0x10) + 0x310)
    if m.u8(rec + 0x8C):
        raid = m.call(m.main + 0xF6FC68, rec)
        move = m.u16(m.u64(m.u64(o + 0x10) + 0x310) + 0x64) if raid else 0
        if raid and move and m.call(m.main + 0x114D360, o, move) & 0xFFFFFFFF and m.u8(lst + 0x2420):
            k = 0
            while True:
                e = lst + 8 + 0x8C * k
                if k & 0xFF < m.u8(lst + 0x2420):
                    ident = m.u32(e)
                    if ident == m.vcall(raid, 0x98) & 0xFFFFFFFF and m.u32(e + 4) == 1 \
                            and m.u8(e + 0x89) == 0:
                        _raid_extra_move(m, o, lst, e)
                        break
                k += 1
                if k >= m.u8(lst + 0x2420):
                    break
    return _tail(m, m.main + 0x114D528, o, lst)


def _raid_extra_move(m, o, lst, entry):
    from pokeldn.sv.battle.engine.containers import battler
    with m.frame(0xC0) as f:
        moves, out, req, act = f, f + 0x10, f + 0x18, f + 0x20
        m.write(f + 0x20, bytes(0x24))
        raid = m.call(m.main + 0xF6FC68, m.u64(m.u64(o + 0x10) + 0x310))
        if raid == 0:
            return
        m.put(moves, 2, 0)
        n = 0
        for i in range(4):
            if i:
                m.put(moves + 2 * i, 2, 0)
            if m.vcall(raid, 0x730, i) & 0xFFFF:
                m.put(moves + 2 * n, 2, m.vcall(raid, 0x730, i))
                n += 1
        other = m.u64(o + 0x48)
        if m.u8(other + 0x2420) == 0:
            return
        j = 0
        while True:
            if j & 0xFF < m.u8(other + 0x2420):
                ident = m.u32(other + 8 + 0x8C * j)
                if ident:
                    rec = m.u64(m.u64(o + 0x10) + 0x310)
                    if _raid_id(m, rec) != ident:
                        break
                    other = m.u64(o + 0x48)
            j += 1
            if j >= m.u8(other + 0x2420):
                return
        b = battler(m, m.u64(m.u64(o + 0x10) + 0x30), m.u32(other + 8 + 0x8C * j))
        if b == 0 or m.vcall(b, 0x200) & 1:
            return
        idx = m.call(m.main + 0x11440F0, m.call(m.main + 0x11440E8, m.u64(o + 0x10)), n) & 0xFFFFFFFF
        idx = idx - (1 << 32) if idx & 0x80000000 else idx
        move = m.u16(moves + 2 * idx)
        m.put(req, 4, m.vcall(raid, 0x98)); m.put(req + 4, 2, move)
        m.call_void(m.main + 0x2842270, m.u64(m.u64(o + 0x78) + 0xB40), out, req)
        slot = m.u8(out)
        table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
        flag = fb.u8(m, data_record(m, table, move), 17)
        if flag not in (0, 3):
            target = 0
        else:
            target = m.vcall(b, 0x98) & 0xFFFFFFFF
            slot = m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), m.vcall(b, 0x98) & 0xFFFFFFFF)
        a = f + 0x48
        m.write(a, bytes(0x8C))
        m.put(a + 0x88, 1, 5); m.put(a + 0x84, 4, 0x5400000); m.put(a + 4, 4, 0xC)
        m.put(a + 0x10, 2, move); m.put(a + 8, 1, slot); m.put(a + 0xC, 4, target)
        m.put(a, 4, m.vcall(raid, 0x98))
        m.put(a + 0x88, 1, _class_of(m, o, m.vcall(raid, 0x98) & 0xFFFFFFFF)); m.put(a + 0x89, 2, 0)
        m.put(a + 0x54, 4, _next_action_serial(m, o))
        m.put(a + 0x84, 4, m.u32(entry + 0x84))
        m.call_void(m.main + 0x1820EB8, lst, a)


@lifted(0x113E9E4)
def raid_actions_of_turn(m, o, *_):
    with m.frame(0x10) as f:
        m.put(f + 8, 8, m.u64(o + 0x48))
        x = m.call(m.main + 0x113EA18, m.u64(o + 0x78))
        return _tail(m, m.main + 0x114CE2C, x, f, f + 8)



@lifted(0x287EAD4)
def queue_b2(m, o, *_):
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xB2, 0)


@lifted(0x17521D8)
def queue_c8(m, o, b, *_):
    """Command 0xc8 (id of b), unless b is null or its id is 0."""
    if b == 0:
        return
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    if ident == 0:
        return
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xC8, ident)


@lifted(0x11501BC)
def queue_ca(m, o, a, b, n, ids, *_):
    """Variadic command 0xca (a, b & 0xffff, then n (1..4) u32 ids from `ids`, ended by 0xffff0000)
    through 0x157ebc0; any other n sends no ids."""
    k = (n - 1) & 0xFFFFFFFF
    vals = [m.u32(ids + 4 * i) for i in range(k + 1)] if k <= 3 else []
    return _tail(m, m.main + 0x157EBC0, m.u64(o + 0x18), 0xCA, a & 0xFFFFFFFF, b & 0xFFFF, *vals, 0xFFFF0000)


def _raid_id_inline(m, rec):
    """_raid_id with 0x14b5634 / 0x114c614 inlined: the parties' list 1 (flag +0x90, first member +0x60)."""
    v = m.u32(rec + 0x18)
    if m.u8(m.u64(m.u64(rec + 8) + 0x38) + 0x499) >> 2 & 1 and v == 0:
        parties = m.u64(m.u64(rec + 0x10) + 0x30)
        if m.u8(parties + 0x90):
            b = m.u64(parties + 0x60)
            if b:
                v = m.vcall(b, 0x98) & 0xFFFFFFFF
                m.put(rec + 0x18, 4, v)
        else:
            v = 0
    return v


@lifted(0x2886D48)
def first_non_raid_actor(m, o, *_):
    """The entry (0x13813f4) of the first battler with an action in the list that is not the raid battler; 0."""
    if m.call(m.main + 0x1149348, m.call(m.main + 0x1149340, o)) & 0xFF == 0:
        return 0
    i = 0
    while True:
        e = m.call(m.main + 0x1149354, m.call(m.main + 0x1149340, o), i)
        if e and m.u32(e):
            ident = m.u32(e)
            if _raid_id_inline(m, m.u64(m.u64(o + 0x10) + 0x310)) != ident:
                return _tail(m, m.main + 0x13813F4, o, m.u32(e))
        i += 1
        if i >= m.call(m.main + 0x1149348, m.call(m.main + 0x1149340, o)) & 0xFF:
            return 0


@lifted(0x1140958)
def raid_turn_if_standing(m, o, *_):
    """Tail-calls 0x11425b0(o) while the raid battler exists and is still in the battle (vf 0x200 false)."""
    def raid():
        return m.call(m.main + 0xF6FC68, m.call(m.main + 0x11409B4, m.call(m.main + 0x1482534, o)))
    if raid() == 0:
        return 0
    r = m.vcall(raid(), 0x200)
    if r & 1:
        return r
    return _tail(m, m.main + 0x11425B0, o)


# 0x1482e80's message per kind 1..35 (jump table 0x3c6a6b4): (form, group, message). Form "F" sends
# (id, message, id), "H" (id, message, id, extra), "G" (id, message); kinds not listed send
# ("F", 0xca, 0x237).
_KIND_MESSAGES = {
    1: ("F", 0xCA, 0x242), 3: ("F", 0xCB, 0x5D), 4: ("F", 0xCB, 0x62), 6: ("F", 0xCB, 0x7A),
    7: ("F", 0xCB, 0x7B), 8: ("F", 0xCB, 0x71), 9: ("H", 0xCB, 0xC6), 10: ("H", 0xCB, 0xBE),
    11: ("H", 0xCB, 0xC1), 12: ("H", 0xCB, 0xC4), 13: ("H", 0xCB, 0x11E), 14: ("F", 0xCB, 0x11F),
    18: ("F", 0xCB, 0x94), 20: ("H", 0xCB, 0x15B), 23: ("F", 0xCA, 0x2BA), 26: ("G", 0xCA, 0x2F2),
    27: ("G", 0xCA, 0x305), 28: ("G", 0xCA, 0x306), 29: ("F", 0xCA, 0x30B), 30: ("F", 0xCA, 0x30C),
    31: ("F", 0xCA, 0x30C), 32: ("F", 0xCA, 0x30C), 33: ("F", 0xCB, 0x1B4), 34: ("F", 0xCB, 0x1BB),
}
_END = 0xFFFF0000


@lifted(0x1482E80)
def kind_message(m, o, b, extra, kind, *_):
    """Queue the message for battler b's state change `kind` through 0x157ebc0 (kind 2 also runs
    0x1366360, kind 15 adds commands 0xc7 and 0xc8, kind 22 picks one of a set of messages)."""
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    kind &= 0xFF
    q = m.u64(o + 0x18)
    send = lambda *a: _tail(m, m.main + 0x157EBC0, m.u64(o + 0x18), *a)
    if kind in (19, 25):
        return ident
    if kind == 2:
        m.call_void(m.main + 0x157EBC0, q, 0xCB, ident, 0x68, ident, _END)
        r = m.call(m.main + 0x1366360, m.u64(o + 8), m.u64(o + 0x10), b)
        if r & 0xFF == 0xFF:
            return send(0xCA, ident, 0x2EB, _END)
        return r
    if kind == 15:
        m.call_void(m.main + 0x119AFF0, q, 0xC7, ident, 0)
        m.call_void(m.main + 0x157EBC0, m.u64(o + 0x18), 0xCB, ident, 0x96, ident, _END)
        return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xC8, ident)
    if kind == 22:
        if m.vcall(b, 0x228, 0) & 1:
            return send(0xCA, ident, 0x2BB, ident, _END)
        i = m.call(m.main + 0x11440F0, m.call(m.main + 0x11440E8, m.u64(o + 0x10)), 4) & 0xFF
        return send(0xCA, ident, i + 0x2B5, ident, _END)
    form, group, msg = _KIND_MESSAGES.get(kind, ("F", 0xCA, 0x237))
    if form == "F":
        return send(group, ident, msg, ident, _END)
    if form == "H":
        return send(group, ident, msg, ident, extra & 0xFFFFFFFF, _END)
    return send(group, ident, msg, _END)


@lifted(0x284DF10)
def kind_2_284de20(m, o, a, *_):
    return _tail(m, m.main + 0x284DE20, o, a, 2)


@lifted(0x287EA80)
def set_and_queue_288d8c0(m, o, a, p, *_):
    """When 0x288c710([o+0x20], a, p) accepts, 0x288d8c0([o+0x18], a, p); 1 when it did."""
    if m.call(m.main + 0x288C710, m.u64(o + 0x20), a, p) & 1 == 0:
        return 0
    m.call_void(m.main + 0x288D8C0, m.u64(o + 0x18), a, p)
    return 1


@lifted(0x28533B8)
def target_of_code(m, _x0, code, b, out, ctx, obj, *_):
    """Write battler b's target descriptor for a script code into the 16 bytes at `out`: codes 0..5
    through 0x1480a6c, 6 a kind-2 descriptor from the object's two named values, 7 kind 3, else kind 1."""
    c = code & 0xFFFF
    if c <= 5:
        ident = m.vcall(b, 0x98)
        r = m.call(m.main + 0x1480A6C, ident, code, ident & 0xFFFFFFFF, ctx, obj)
        m.put(out, 8, r[0]); m.put(out + 8, 8, r[1])
        return
    m.put(out + 8, 8, 0)
    if c == 6:
        x = m.vcall(obj, 0x68, m.main + 0x3C69CC8)
        y = m.vcall(obj, 0x68, m.main + 0x3C69CD0)
        v = m.call(m.main + 0x179405C, ctx, x & 0xFFFFFFFF, y & 0xFFFFFFFF)
        lo, hi = m.vcall(b, 0x98) & 0xFFFFFFFF, (v & 0x3F) << 3 | 2
    elif c == 7:
        lo = m.vcall(b, 0x98) & 0xFFFFFFFF
        hi = (m.vcall(b, 0x98) & 0x3F) << 3 | 3
    else:
        lo, hi = m.vcall(b, 0x98) & 0xFFFFFFFF, 1
    m.put(out, 8, lo); m.put(out + 8, 8, hi)


@lifted(0x187495C)
def run_17ce0ec_for(m, o, b, *_):
    if b == 0:
        return
    return _tail(m, m.main + 0x17CE0EC, o, m.vcall(b, 0x98) & 0xFFFFFFFF, 0)


@lifted(0x287B7A4)
def flag_of_id(m, o, ident, *_):
    """Whether the u32-keyed map at o+0x2f0 holds `ident` with a nonzero value byte (through its at())."""
    from pokeldn.sv.battle.engine.containers import find
    ident &= 0xFFFFFFFF
    if not find(m, o + 0x2F0, ident, 4):
        return 0
    with m.frame(0x10) as f:
        m.put(f, 4, ident)
        return int(m.u8(m.call(m.main + 0x287B8E0, o + 0x2F0, f)) != 0)


@lifted(0x14B5634)
def party_list(m, parties, client, *_):
    """The member list (+0x28 + 0x38 * client) of a client's party; 0 past client 4."""
    client &= 0xFFFFFFFF
    return (parties + 0x38 * client + 0x28) & 0xFFFFFFFFFFFFFFFF if client <= 4 else 0


@lifted(0x2842270)
def target_slot(m, o, out, req, *_):
    """out = 0x10e21c0 for the entry of battler [req] (0x13813f4) and the move u16 at req+4."""
    e = m.call(m.main + 0x13813F4, o, m.u32(req))
    x = m.call(m.main + 0x11440E8, m.call(m.main + 0x1482534, o))
    y = m.call(m.main + 0x114E480, o)
    z = m.call(m.main + 0x1482534, o)
    m.put(out, 1, m.call(m.main + 0x10E21C0, y, z, e, m.u16(req + 4), x))


@lifted(0x11514B8)
def raid_action_order(m, o, act, lst, *_):
    """One past the order (+0x84) of the raid battler's action in the list; without one, what 0x113ecdc
    gives for `act` (request 0x102); 0 without a raid battler."""
    if m.call(m.main + 0xF6FC68, m.u64(m.u64(o + 0x10) + 0x310)) == 0:
        return 0
    k = 0
    while k < m.u8(lst + 0x2420):
        e = lst + 8 + 0x8C * k
        ident = m.u32(e)
        raid = m.call(m.main + 0xF6FC68, m.u64(m.u64(o + 0x10) + 0x310))
        if ident == m.vcall(raid, 0x98) & 0xFFFFFFFF:
            return (m.u32(e + 0x84) + 1) & 0xFFFFFFFF
        k += 1
    with m.frame(0x20) as f:
        m.put(f + 0x10, 8, act); m.put(f + 0x18, 2, 0x102)
        x = m.call(m.main + 0x28838F4, m.u64(o + 0x78))
        m.call_void(m.main + 0x113ECDC, x, f + 8, f + 0x10)
        return m.u32(f + 8)


@lifted(0x2844160)
def touch_shared_object(m, p, *_):
    """The object at [0xe7ecd0([p])+0x148], after taking and dropping one reference on its shared
    state (+0x30: u16 count +0x1a; the first reference builds the value at +8 through vf 0 of +0x10,
    the last one clears +0x10 and runs the object's vf 0x50). Abort paths are refused."""
    r = m.u64(m.call(m.main + 0xE7ECD0, m.u64(p)) + 0x148)
    if r == 0:
        return 0
    s = m.u64(r + 0x30)
    if m.u64(s + 0x10) == 0:
        raise UnliftedCall("AddReference abort: m_object is null")
    c = m.u16(s + 0x1A)
    m.put(s + 0x1A, 2, c + 1)
    if c == 0:
        m.put(s + 8, 8, m.vcall(m.u64(s + 0x10), 0))
        m.put(s + 0x1C, 4, 0xFFFFFFFE)
    elif c == 0xFFFF:
        raise UnliftedCall("AddReference abort: count overflow")
    s = m.u64(r + 0x30)
    c = m.u16(s + 0x1A)
    m.put(s + 0x1A, 2, c - 1)
    if c == 1:
        m.put(s + 0x10, 8, 0)
        m.vcall_void(r, 0x50)
    elif c == 0:
        raise UnliftedCall("Release abort: count underflow")
    return r



@lifted(0x284DE20)
def boost_once(m, o, a, k, *_):
    """When 0x283d6a0(o, 4) is `a`, the byte of [root+0xe0]'s id is k, and neither record +0x268 nor
    record 0x64 (k == 1) / 0x65 is set: 0x1353738([o+0x38], 0x38, 0x800, or 0xaac when 0x144b6d4 is
    nonzero), then mark that record pending."""
    k &= 0xFF
    if a & 0xFFFFFFFF != m.call(m.main + 0x283D6A0, o, 4) & 0xFF:
        return
    root = m.u64(m.u64(o + 0x38) + 0x78)
    if _owner_id(m, o, 0xE0) & 0xFF != k:
        return
    p = m.u64(root + 0x268)
    if p and m.u32(p + 0xC):
        return
    idx = 0x64 if k == 1 else 0x65
    p = m.u64(root + 8 * idx + 8)
    if p and m.u32(p + 0xC):
        return
    v = 0x800 if m.call(m.main + 0x144B6D4, m.u64(o + 8)) & 0xFFFFFFFF == 0 else 0xAAC
    m.call_void(m.main + 0x1353738, m.u64(o + 0x38), 0x38, v)
    _mark_pending(m, m.u64(m.u64(m.u64(o + 0x38) + 0x78) + 8 * idx + 8))


# ---- batch 1, second pass: the state-build step (ch6_s1) ----

from pokeldn.sv.battle.engine import pokemon as _pk  # noqa: E402


@lifted(0x92E438)
def field_1f0(m, o, *_):
    return m.u64(o + 0x1F0)


def _iv(shift):
    """IV word (block B +0x34) bits shift..shift+4."""
    def fn(m, acc, *_):
        return _pk.access(m, acc, lambda core: m.u32(_pk._target(m, acc, core, 1, 0x47422E0) + 0x34) >> shift & 0x1F)
    return fn


for _a, _shift in ((0xD97F74, 0), (0xD982BC, 5), (0xD98604, 10), (0xD98C94, 15), (0xD9894C, 20), (0xD98FDC, 25)):
    lifted(_a)(_iv(_shift))


def _block_a_byte(off):
    def fn(m, acc, *_):
        return _pk.access(m, acc, lambda core: m.u8(_pk._target(m, acc, core, 0, 0x4742290) + off))
    return fn


for _a, _off in ((0xD8FE2C, 0x1F), (0xD907F8, 0x21)):
    lifted(_a)(_block_a_byte(_off))

for _a, _off in ((0xE157B8, 6), (0xE16154, 0xC)):
    lifted(_a)(_pk._setter("party", _off, 2, 0, _pk.BAD_WRITE_PARTY, True))


@lifted(0xE14018)
def clamp_pp(m, pp, *_):
    """For each of the first n moves (n = how many of the four are set): PP above its maximum
    (0xbf5fe0(move, PP Ups)) is lowered to it."""
    acc = lambda: m.u64(pp + 0x70)
    n = sum(1 for i in range(4) if m.call(m.main + 0xDEDBC8, acc(), i) & 0xFFFF)
    for i in range(n):
        mx = m.call(m.main + 0xBF5FE0, m.call(m.main + 0xDEDBC8, acc(), i), m.call(m.main + 0xBF61D4, acc(), i))
        if mx & 0xFF < m.call(m.main + 0xDEE950, acc(), i) & 0xFF:
            again = m.call(m.main + 0xBF5FE0, m.call(m.main + 0xDEDBC8, acc(), i), m.call(m.main + 0xBF61D4, acc(), i))
            m.call_void(m.main + 0xDEDF30, acc(), i, again if again & 0xFF < mx & 0xFF else mx)


@lifted(0x287A6B8)
def level(m, o, *_):
    """The party record's level, or 0xe13da0(species, form, experience) when there is none."""
    acc = m.u64(m.u64(o + 0x48) + 0x70)
    if m.u64(acc + 8):
        return m.call(m.main + 0xD9987C, acc)
    species = m.call(m.main + 0xBF44F4, acc)
    form = m.call(m.main + 0xBF41A8, m.u64(m.u64(o + 0x48) + 0x70))
    exp = m.call(m.main + 0xE14B64, m.u64(m.u64(o + 0x48) + 0x70))
    return m.call(m.main + 0xE13DA0, species, form, exp) & 0xFF


@lifted(0x287A73C)
def move_of(m, o, i, *_):
    return m.call(m.main + 0xDEDBC8, m.u64(m.u64(o + 0x48) + 0x70), i)


@lifted(0x287A880)
def pp_ups_of(m, o, i, *_):
    return m.call(m.main + 0xBF61D4, m.u64(m.u64(o + 0x48) + 0x70), i)


@lifted(0x287A9DC)
def species_form_115b968(m, o, *_):
    """0x115b968 on {[0x46d8ee0] + 0x10, u16 species, u16 form}."""
    species = m.call(m.main + 0xBF44F4, m.u64(m.u64(o + 0x48) + 0x70))
    form = m.call(m.main + 0xBF41A8, m.u64(m.u64(o + 0x48) + 0x70))
    with m.frame(0x10) as p:
        m.put(p, 8, m.u64(m.main + 0x46D8EE0) + 0x10)
        m.put(p + 8, 2, species); m.put(p + 0xA, 2, form)
        return m.call(m.main + 0x115B968, p)


@lifted(0x287AAC0)
def release_plain(m, o, flag, *_):
    """When the record is kept plain (+0x19) and bit 0 of flag: 0xd679f0(record accessor), 1."""
    acc = m.u64(m.u64(o + 0x48) + 0x70)
    if m.u8(acc + 0x19) and flag & 1:
        m.call_void(m.main + 0xD679F0, acc)
        return 1
    return 0


@lifted(0xD677E8)
def keep_plain(m, acc, *_):
    """Lock the record, decrypt it, mark it kept plain (+0x19), unlock."""
    _pk.access(m, acc, lambda core: m.put(acc + 0x19, 1, 1))
    return acc + 0x28


def _personal(m, key_holder):
    """The personal record for (u16 +8) * 10000 + (u16 +0xa) from the static map (0x46d7438 guard
    0x46d7430, last 0x46d7440): node value +0x18, or the default at +0xd0."""
    from pokeldn.sv.battle.engine.containers import find
    table = static_table(m, 0x46D7430, 0x46D7438, 0x46D7440)
    key = m.u16(key_holder + 8) * 10000 + m.u16(key_holder + 0xA)
    node = find(m, table + 0x68, key, 8)
    return m.u64(node + 0x18) if node else m.u64(table + 0xD0)


def _personal_byte(k):
    """Byte k of the struct at vtable slot +0x30 (no presence check)."""
    def fn(m, key_holder, *_):
        t = _personal(m, key_holder)
        return m.u8(t + m.u16(t - m.s(t, 4) + 0x30) + k)
    return fn


for _a, _k in ((0xCEDDA8, 1), (0xCEE2D0, 3)):
    lifted(_a)(_personal_byte(_k))


@lifted(0x1012D44)
def personal_field_5(m, key_holder, *_):
    return fb.u8(m, _personal(m, key_holder), 5)


@lifted(0xFA24B4)
def init_fa24b4(m, p, *_):
    m.put(p, 8, 0)
    for o in range(0x38, 0x340, 0x10):
        m.put(p + o + 8, 8, 0); m.put(p + o, 4, 0)
    m.put(p + 0x3A2, 2, 10); m.put(p + 0x3A8, 1, 10); m.put(p + 0x3A4, 4, 0x0A0A0A0A); m.put(p + 0x3A9, 1, 0)
    m.put(p + 0x3AC, 2, 10); m.put(p + 0x3B2, 1, 10); m.put(p + 0x3AE, 4, 0x0A0A0A0A); m.put(p + 0x3B3, 1, 0)
    return p


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


# An id pool: u32 base +0, next fresh id +4, ids in use +8; freed ids in a deque<u32> (block map
# [+0x18, +0x20), allocator +0x60, start +0x50, size +0x58, blocks of 1024); a bitset of ids in use
# (words [+0x88, +0x90), bit count +0xc0); lock (owner, 0) at +0xd0, light event +0xe0.

def _pool_lock(m, pool):
    from pokeldn.sv.battle.engine.libc import FAKE_THREAD
    if m.u64(pool + 0xD0) or m.u64(pool + 0xD8):
        raise UnliftedCall("id pool already locked")
    m.put(pool + 0xD0, 8, FAKE_THREAD); m.put(pool + 0xD8, 8, 0)


def _pool_unlock(m, pool):
    from pokeldn.sv.battle.engine.libc import signal_light_event
    m.put(pool + 0xD0, 8, 0)
    signal_light_event(m, pool + 0xE0)


def _free_block(m, alloc, block):
    if m.vcall(alloc, 0xF8) & 1 and m.s(m.call(m.main + 0xB4E600) + 0x12C8, 4) >= 1:
        m.call_void(m.main + 0xB48FE8, alloc, block, 0x1000, 4)
    else:
        m.vcall_void(alloc, 0x18, block, 0x1000, 4)


@lifted(0xC1A7A0)
def pool_take(m, pool, *_):
    """Take an id: the last freed one (the deque's back, dropping a spare block) or the next fresh one;
    mark it in the bitset (grown to cover it) and count it."""
    _pool_lock(m, pool)
    size = m.u64(pool + 0x58)
    if size == 0:
        ident = m.u32(pool + 4)
        m.put(pool + 4, 4, ident + 1)
    else:
        size -= 1
        i = (m.u64(pool + 0x50) + size) & 0xFFFFFFFFFFFFFFFF
        ident = m.u32(m.u64(m.u64(pool + 0x18) + (i >> 10) * 8) + (i & 0x3FF) * 4)
        m.put(pool + 0x58, 8, size)
        span = (m.u64(pool + 0x20) - m.u64(pool + 0x18)) & 0xFFFFFFFFFFFFFFFF
        cap = (span * 0x80 - 1) & 0xFFFFFFFFFFFFFFFF if span else 0
        if (cap - i) & 0xFFFFFFFFFFFFFFFF >= 0x800:
            _free_block(m, m.u64(pool + 0x60), m.u64(m.u64(pool + 0x20) - 8))
            m.put(pool + 0x20, 8, m.u64(pool + 0x20) - 8)
    idx = (ident - m.u32(pool)) & 0xFFFFFFFF
    if m.u64(pool + 0xC0) <= idx:
        n = (idx + 1) & 0xFFFFFFFF
        words = (n >> 6) + (1 if n & 0x3F else 0)
        cur = ((m.u64(pool + 0x90) - m.u64(pool + 0x88)) & 0xFFFFFFFFFFFFFFFF) >> 3
        if words > cur:
            with m.frame(0x10) as z:
                m.put(z, 8, 0)
                m.call_void(m.main + 0xC1AA80, pool + 0x88, words - cur, z)
        elif words < cur:
            m.put(pool + 0x90, 8, m.u64(pool + 0x88) + words * 8)
        m.put(pool + 0xC0, 8, n)
        if n & 0x3F:
            last = m.u64(pool + 0x90) - 8
            m.put(last, 8, m.u64(last) & ~(0xFFFFFFFFFFFFFFFF << (n & 0x3F)))
    w = m.u64(pool + 0x88) + (idx >> 6) * 8
    m.put(w, 8, m.u64(w) | 1 << (idx & 0x3F))
    m.put(pool + 8, 4, m.u32(pool + 8) + 1)
    _pool_unlock(m, pool)
    return ident


@lifted(0x287AA90)
def keep_plain_once(m, o, *_):
    """0xd677e8 on the record accessor unless it is already kept plain: 1 when it was called."""
    acc = m.u64(m.u64(o + 0x48) + 0x70)
    if m.u8(acc + 0x19):
        return 0
    m.call_void(m.main + 0xD677E8, acc)
    return 1


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


@lifted(0x127EB14)
def reset_38_entries(m, o, *_):
    """For each of 38 entries of 0x28 bytes from +0x18 whose u32 +0x10 is set: clear its u64 +0xc and
    the low 3 bits of its u64 +0."""
    for k in range(38):
        e = o + 0x18 + 0x28 * k
        if m.u32(e + 0x10):
            m.put(e + 0xC, 8, 0)
            m.put(e, 8, m.u64(e) & ~7)


def _free(m, alloc, block, size):
    if m.vcall(alloc, 0xF8) & 1 and m.s(m.call(m.main + 0xB4E600) + 0x12C8, 4) >= 1:
        m.call_void(m.main + 0xB48FE8, alloc, block, size, 4)
    else:
        m.vcall_void(alloc, 0x18, block, size, 4)


@lifted(0x127E6E8)
def map_clear(m, o, *_):
    """Clear +0x70; when the map holds entries (+0x60): free its 0x20-byte nodes (list +0x38, allocator
    +0x40), empty the list and the buckets (+8, count +0x10), size 0."""
    m.put(o + 0x70, 1, 0)
    if m.u64(o + 0x60):
        _map_free_all(m, o, 0x20)


def _map_free_all(m, o, node_size):
    """Free every node of the map at o+8 (list +0x38, allocator +0x40), empty its buckets (+8, count
    +0x10), size (+0x60) 0."""
    node = m.u64(o + 0x38)
    while node:
        nxt = m.u64(node)
        _free(m, m.u64(o + 0x40), node, node_size)
        node = nxt
    m.put(o + 0x38, 8, 0)
    for i in range(m.u64(o + 0x10)):
        m.put(m.u64(o + 8) + 8 * i, 8, 0)
    m.put(o + 0x60, 8, 0)


@lifted(0x127381C)
def reset_127381c(m, o, *_):
    p = m.u64(o + 8)
    m.put(p + 0xA, 4, 0xFFFFFFFF); m.put(p + 0x938, 1, 0); m.put(p + 8, 1, 0); m.put(p + 0xE, 2, 0)
    m.put(p + 0x10, 4, 0); m.put(p + 0x14, 2, 10)
    m.call_void(m.main + 0x127399C, p + 0x18)
    r = m.call(m.main + 0x343C220, p + 0x60, 0, 0x6B)
    m.put(m.u64(o + 0x28), 1, 0)
    q = m.u64(o + 0x48)
    m.put(q + 8, 4, 0x05050505); m.put(q + 0xC, 1, 5)
    q = m.u64(o + 0x68)
    m.put(q + 0x18, 8, 0); m.put(q + 8, 8, 0); m.put(q + 0x10, 8, 0); m.put(q + 0x1E, 8, 0); m.put(q + 0x28, 4, 0)
    for k in range(0x98, 0x188, 8):
        m.put(o + k, 4, 0); m.put(o + k + 4, 1, 0)
    m.put(o + 0x88, 1, 0); m.put(o + 0x90, 8, 0)
    return r


@lifted(0x127D5CC)
def init_127d5cc(m, o, a, *_):
    m.put(o + 0xB0, 4, 0); m.put(o, 8, m.main + 0x44EE690)
    m.put(o + 0x4E, 2, 0); m.put(o + 0x56, 2, 0); m.put(o + 0x5E, 8, 0); m.put(o + 0x66, 8, 0)
    m.put(o + 0x6E, 2, 0); m.put(o + 0x80, 8, 0); m.put(o + 0x88, 4, 0); m.put(o + 0xB8, 8, 0)
    m.put(o + 0xC, 1, 0); m.put(o + 8, 4, 0); m.put(o + 0xE, 2, 0); m.put(o + 0x10, 4, 0)
    m.put(o + 0x70, 8, a); m.put(o + 0x78, 8, 0x1FFFFFFFFFFFFFFF)
    m.put(o + 0xA0, 8, 0x1FFFFFFFFFFFFFFF); m.put(o + 0xA8, 8, 0)
    m.put(o + 0xC0, 4, 0x3F800000); m.put(o + 0xD, 1, 5)
    for k in range(0x14, 0x5C, 8):
        m.put(o + k, 8, 0x500)
    m.put(o + 0x5C, 4, 0x500)
    m.put(o + 0x90, 8, 0); m.put(o + 0x98, 8, a)
    return o


@lifted(0xFA91F8)
def u16_8c(m, o, *_):
    return m.u16(o + 0x8C)


def _move_counted(m, o, src):
    """o = move(src) for a pointer counted at +0x28 (u32); the last reference runs vf 0x10."""
    old = m.u64(o)
    m.put(o, 8, 0)
    r = old
    if old:
        c = m.u32(old + 0x28)
        if c == 0:
            raise UnliftedCall("DecrementReference abort: count underflow")
        m.put(old + 0x28, 4, c - 1)
        if c == 1:
            r = m.vcall(old, 0x10)
    m.put(o, 8, m.u64(src)); m.put(src, 8, 0)
    return r


lifted(0xFAB748)(lambda m, o, src, *_: _move_counted(m, o, src))
lifted(0xFABCC4)(lambda m, o, src, *_: _move_counted(m, o, src))


@lifted(0xFA01F8)
def set_u16_slot(m, o, i, v, *_):
    i &= 0xFF
    if i <= 4:
        m.put(o + 0xA + 2 * i, 2, v)


@lifted(0xFA8298)
def assign_shared(m, o, p, *_):
    """o = p for objects whose shared state (+0x30) counts references (u16 +0x1a); the first reference
    builds +8 through vf 0 of +0x10 (+0x1c = -2), the last clears +0x10 and tail-calls the object's
    vf 0x50. Abort paths are refused."""
    if p:
        s = m.u64(p + 0x30)
        if m.u64(s + 0x10) == 0:
            raise UnliftedCall("AddReference abort: m_object is null")
        c = m.u16(s + 0x1A)
        if c == 0xFFFF:
            raise UnliftedCall("AddReference abort: count overflow")
        m.put(s + 0x1A, 2, c + 1)
        if c == 0:
            m.put(s + 8, 8, m.vcall(m.u64(s + 0x10), 0))
            m.put(s + 0x1C, 4, 0xFFFFFFFE)
    old = m.u64(o)
    m.put(o, 8, p)
    if old == 0:
        return 0
    s = m.u64(old + 0x30)
    c = m.u16(s + 0x1A)
    if c == 0:
        raise UnliftedCall("Release abort: count underflow")
    m.put(s + 0x1A, 2, c - 1)
    if c == 1:
        m.put(s + 0x10, 8, 0)
        return m.vcall(old, 0x50)
    return old


@lifted(0xFA6E40)
def map_at_u32(m, table, key_ptr, *_):
    """unordered_map<u32, ...>::at: the value slot (node+0x18); a missing key throws (0x288ddb0)."""
    from pokeldn.sv.battle.engine.containers import find
    node = find(m, table, m.u32(key_ptr), 4)
    if not node:
        raise UnliftedCall("unordered_map::at of a missing key (throws)")
    return node + 0x18


@lifted(0xFA9B4C)
def rule_bits(m, o, mask, *_):
    return int(m.u64(m.u64(o + 0x38) + 0x498) & mask != 0)


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


@lifted(0xFAEFF4)
def clear_1b(m, o, *_):
    m.put(o + 0x1B, 1, 0)


lifted(0xFA3AE0)(lambda m, o, src, *_: _move_counted(m, o, src))


@lifted(0x13F5EF8)
def field_150(m, o, *_):
    return m.u64(o + 0x150)


@lifted(0xF79BE8)
def copy_38_entries(m, dst, src, *_):
    """The 0x20 bytes at +0x10 of each of 38 entries of 0x28 bytes."""
    for k in range(38):
        m.write(dst + 0x10 + 0x28 * k, m.read(src + 0x10 + 0x28 * k, 0x20))


@lifted(0xF79060)
def map_assign_8(m, o, src, *_):
    """Empty the map at o+8 (0x20-byte nodes), then o[key] = value for each (u32 key +0x10, u64 value
    +0x14) node of src's list (+0x38), through operator[] 0xf7a448."""
    if m.u64(o + 0x60):
        _map_free_all(m, o, 0x20)
    node = m.u64(src + 0x38)
    while node:
        m.put(m.call(m.main + 0xF7A448, o + 8, node + 0x10), 8, m.u64(node + 0x14))
        node = m.u64(node)


@lifted(0xF78CB8)
def map_reset_16(m, o, *_):
    """Empty the map at o+8 (0x28-byte nodes) when it holds entries; then o[key] = 16 bytes for each
    node still on its own list (operator[] 0xf807f8)."""
    if m.u64(o + 0x60):
        _map_free_all(m, o, 0x28)
    node = m.u64(o + 0x38)
    while node:
        m.write(m.call(m.main + 0xF807F8, o + 8, node + 0x10), m.read(node + 0x14, 0x10))
        node = m.u64(node)


@lifted(0x17D3154)
def apply_record_17d3154(m, o, _x1, rec, *_):
    """For the Pokemon [rec]: when 0x17d31e0 gives a slot other than 10 and rec+0xa is set,
    0x2886d20(0x1143584(o), slot, 0x33); then tail-call 0x114fcd8(0x1143584(o), [rec], u16 rec+8, 0, 0,
    u8 rec+0xa)."""
    slot = m.call(m.main + 0x17D31E0, o, m.vcall(m.u64(rec), 0x98) & 0xFFFFFFFF)
    if slot & 0xFF != 0xA and m.u8(rec + 0xA):
        m.call_void(m.main + 0x2886D20, m.call(m.main + 0x1143584, o), slot & 0xFFFFFFFF, 0x33)
    m.call_void(m.main + 0x114FCD8, m.call(m.main + 0x1143584, o), m.u64(rec), m.u16(rec + 8), 0, 0,
                m.u8(rec + 0xA))


@lifted(0x2880580)
def apply_2880580(m, o, p, a, b, c, d, *_):
    """When p's vtable +0x540(a) holds: 0x1143a30(..., p, a, 0), 0x1148df8 for b and for c with
    0x171a7ec(0x32), then tail-call 0x171a604(..., p's id, d, 0xfe)."""
    if p == 0:
        return o
    r = m.vcall(p, 0x540, a & 0xFFFFFFFF)
    if r & 0xFF == 0:
        return r
    v = m.call(m.main + 0x171A7EC, 0x32) & 0xFFFFFFFF
    m.call_void(m.main + 0x1143A30, m.call(m.main + 0x1143584, o), p, a & 0xFFFFFFFF, 0)
    for x in (b, c):
        q = m.call(m.main + 0x1143584, o)
        m.call_void(m.main + 0x1148DF8, q, m.vcall(p, 0x98) & 0xFFFFFFFF, x & 0xFFFFFFFF, v)
    q = m.call(m.main + 0x1143584, o)
    return _tail(m, m.main + 0x171A604, q, m.vcall(p, 0x98) & 0xFFFFFFFF, d & 0xFFFFFFFF, 0xFE)


@lifted(0x119B6CC)
def insert_by_priority(m, o, new, *_):
    """Link the entry `new` (u16 id +0x10, prev +0x12, next +0x14, u32 priority +0x2c) into the chain
    headed by the u16 id at o+0x70 (entries found through 0xf7ba54 in their owner, value +8), ahead of
    the first entry of lower priority."""
    from pokeldn.sv.battle.engine.containers import find_value
    cur = find_value(m, o, m.u16(o + 0x70))
    if cur == 0:
        m.put(o + 0x70, 2, m.u16(new + 0x10))
        return
    prio = m.u32(new + 0x2C)
    if m.u32(cur + 0x2C) < prio:
        m.put(new + 0x14, 2, m.u16(cur + 0x10))
        m.put(cur + 0x12, 2, m.u16(new + 0x10))
        m.put(o + 0x70, 2, m.u16(new + 0x10))
        return
    while True:
        nxt = find_value(m, m.u64(cur + 8), m.u16(cur + 0x14))
        if nxt == 0:
            if new == 0:
                m.put(cur + 0x14, 2, 0xEE)
                return
            m.put(cur + 0x14, 2, m.u16(new + 0x10))
            m.put(new + 0x12, 2, m.u16(cur + 0x10))
            return
        if m.u32(nxt + 0x2C) < prio:
            prev = m.call(m.main + 0x119E440, nxt)
            if new == 0:
                m.put(prev + 0x14, 2, 0xEE)
            else:
                m.put(prev + 0x14, 2, m.u16(new + 0x10))
                m.put(new + 0x12, 2, m.u16(prev + 0x10))
            m.put(new + 0x14, 2, m.u16(nxt + 0x10))
            m.put(nxt + 0x12, 2, m.u16(new + 0x10))
            return
        cur = nxt


@lifted(0x171A624)
def apply_171a624(m, o, p, a, *_):
    """Unless p's vf 0x200: vf 0x540(a) 0 -> 0x1143a30(..., p, a, 3), 0x171a6dc(o, p, a), 1; 1..5 ->
    0x288756c(..., p, a), 2; else 0."""
    if m.vcall(p, 0x200) & 1:
        return 0
    r = m.vcall(p, 0x540, a & 0xFFFFFFFF) & 0xFF
    if r == 0:
        m.call_void(m.main + 0x1143A30, m.call(m.main + 0x1143584, o), p, a & 0xFFFFFFFF, 3)
        m.call_void(m.main + 0x171A6DC, o, p, a & 0xFFFFFFFF)
        return 1
    if r <= 5:
        m.call_void(m.main + 0x288756C, m.call(m.main + 0x1143584, o), p, a & 0xFFFFFFFF)
        return 2
    return 0


@lifted(0x171CA78)
def add_to_field_3f4(m, b, k, delta, *_):
    """Field k of the record at b+0x3f4 = vf 0x1d0(k, delta) + delta, then refresh the derived stat."""
    cur = m.vcall(b, 0x1D0, k, delta)
    m.call_void(m.main + 0x171CAC8, b + 0x3F4, k & 0xFFFFFFFF, (cur + delta) & 0xFFFFFFFF)
    return _tail(m, m.main + 0x171CB20, b, k & 0xFFFFFFFF)


@lifted(0x171CB20)
def refresh_stat(m, b, k, *_):
    """Stat k (1..5): u16 at b+0x3fe+2k = [b+0x48]'s vf 0x70(k) * byte b+0x3f5+k / 10 (jump table 0x3c6b49a)."""
    k &= 0xFF
    if not 1 <= k <= 5:
        return
    v = m.vcall(m.u64(b + 0x48), 0x70, k) & 0xFFFF
    m.put(b + 0x3FE + 2 * k, 2, (v * m.u8(b + 0x3F5 + k) & 0xFFFFFFFF) // 10)


@lifted(0x114AAB0)
def apply_record_114aab0(m, o, _x1, rec, *_):
    """rec: u32 id +0, flag +4, body +8. With the id's Pokemon (0x13813f4) and the flag: 0x187495c
    before and 0x17521d8 after 0x114b0ac(..., id, body); a negative s16 at body+2 sets
    0x139b698(o)+0xc0."""
    ident = m.u32(rec)
    p = m.call(m.main + 0x13813F4, o, ident) if ident else 0
    if p and m.u8(rec + 4):
        m.call_void(m.main + 0x187495C, m.call(m.main + 0x1143584, o), p)
    m.call_void(m.main + 0x114B0AC, m.call(m.main + 0x1143584, o), m.u32(rec), rec + 8)
    if p and m.u8(rec + 4):
        m.call_void(m.main + 0x17521D8, m.call(m.main + 0x1143584, o), p)
    r = m.call(m.main + 0x114AB84, rec + 8)
    if r & 1:
        r = m.call(m.main + 0x139B698, o)
        m.put(r + 0xC0, 1, 1)
    return r


@lifted(0x18FFCD0)
def matching_members(m, o, rule, out, *_):
    """Clear the 10 u32s at out, then walk the standing members (0x1147754 / 0x1360dbc) collecting ids
    whose 0x10e2da8 value is rule+0x34 or whose 0x144e790 byte is rule+0x38; the member with id
    rule+0x3c is taken last and ends the walk. The count."""
    m.write(out, bytes(0x28))
    a = m.call(m.main + 0x114E480, o)
    with m.frame(0x30) as it:
        m.call_void(m.main + 0x1147754, it, a, m.call(m.main + 0x1482534, o))
        n = 0
        while m.call(m.main + 0x1360DBC, it, it + 0x20) & 1:
            p = m.u64(it + 0x20)
            if m.vcall(p, 0x98) & 0xFFFFFFFF == m.u32(rule + 0x3C):
                m.put(out + 4 * n, 4, m.vcall(p, 0x98)); return n + 1
            t = m.call(m.main + 0x13813EC, m.call(m.main + 0x1482534, o))
            hit = m.call(m.main + 0x10E2DA8, t, m.vcall(p, 0x98) & 0xFFFFFFFF) & 0xFFFFFFFF == m.u32(rule + 0x34)
            if not hit:
                t = m.call(m.main + 0x13813EC, m.call(m.main + 0x1482534, o))
                hit = m.call(m.main + 0x144E790, t, m.vcall(p, 0x98) & 0xFFFFFFFF) & 0xFF == m.u8(rule + 0x38)
            if hit:
                m.put(out + 4 * n, 4, m.vcall(m.u64(it + 0x20), 0x98)); n += 1
        return n


@lifted(0xFAF048)
def fill_format_map(m, o, *_):
    """Clear +0x68, then set every (u16 key, byte) pair of the 0xd0-entry table at 0x3c6abe4 in the
    command-format map (0xfaf09c)."""
    m.put(o + 0x68, 8, 0)
    for i in range(0xD0):
        e = m.main + 0x3C6ABE4 + 4 * i
        v = m.u8(e + 2)
        m.put(m.call(m.main + 0xFAF09C, o, e), 1, v)


# (offset, size) pairs 0xf575d4 copies, in its order.
_COPY_F575D4 = ((0x400, 0x14), (0x414, 7), (0x47E, 4), (0x482, 5), (0x488, 7), (0x490, 6), (0x6EF, 2),
                (0x6F2, 4), (0x6F8, 4), (0x487, 1), (0x426, 0x58), (0x496, 8), (0x4A0, 0x100), (0x5A0, 8),
                (0x5A8, 0x24), (0x5CC, 0x120), (0x6EC, 3))


@lifted(0xF575D4)
def copy_f575d4(m, dst, src, *_):
    for off, n in _COPY_F575D4:
        m.write(dst + off, m.read(src + off, n))


@lifted(0x119B2A0)
def add_handler(m, o, pokemon, key, prio, *_):
    """Give the Pokemon a kind-0 handler for `key` unless one of its first 8 already answers it: the
    constructor paired with key in the 380-entry table at 0x44f7d60 (u16 key +0, function +8) builds
    the body, 0x119baac allocates the entry (u16s +0x12/+0x14 = 0xee, priority prio | 0x7000000,
    body +0x20, key +0x30, id +0x34/+0x38, [o+0x80] +0x3c, constructor's byte +0x3e, live +0x44) and
    0x119b6cc links it. 1 when made or when there is no room, else 0."""
    key &= 0xFFFF
    ident = m.vcall(pokemon, 0x98) & 0xFFFFFFFF
    h = m.call(m.main + 0x119B478, m.u64(m.u64(o + 8) + 0xD0), 0, ident)
    if h:
        if m.u16(h + 0x30) == key:
            return 0
        kind, hid, n = m.u8(h + 0x28), m.u32(h + 0x34), 0
        while True:
            h = m.call(m.main + 0xF7BA54, m.u64(h + 8), m.u16(h + 0x14))
            if h == 0:
                break
            n += 1
            while m.u8(h + 0x28) != kind or m.u32(h + 0x34) != hid or m.u8(h + 0x41):
                h = m.call(m.main + 0xF7BA54, m.u64(h + 8), m.u16(h + 0x14))
                if h == 0:
                    break
            if h == 0:
                break
            if n == 8 or m.u16(h + 0x30) == key:
                return 0
    table = m.main + 0x44F7D60
    for i in range(0x17C):
        if m.u16(table + 0x10 * i) == key:
            break
    else:
        return 0
    with m.frame(0x10) as out:
        body = m.call(m.u64(table + 0x10 * i + 8), out)
        if body == 0:
            return 0
        tag = m.u32(out)
    owner = m.u64(m.u64(o + 8) + 0xD0)
    serial = m.u32(o + 0x80)
    e = m.call(m.main + 0x119BAAC, owner, 0xFFFFFFFF)
    if e == 0:
        return 1
    m.put(e + 0x12, 4, 0x00EE00EE)
    m.write(e + 0x18, bytes(0x58))
    m.put(e + 0x2C, 4, prio | 0x7000000); m.put(e + 0x28, 1, 0); m.put(e + 0x20, 8, body)
    m.put(e + 0x3E, 1, tag); m.put(e + 0x30, 2, key); m.put(e + 0x34, 4, ident); m.put(e + 0x38, 4, ident)
    m.put(e + 0x3C, 2, serial); m.put(e + 0x44, 1, 1)
    m.call_void(m.main + 0x119B6CC, owner, e)
    return 1


_BASE_STAT = (0xCEDBF4, 0xCEDDA8, 0xCEDF60, 0xCEE2D0, 0xCEE488, 0xCEE118)   # jump table 0x3c62ca4


@lifted(0xCEDAA8)
def base_stat(m, pp, i, *_):
    """Base stat i (0..5) of the Pokemon's species and form, through a {[0x46d8ee0]+0x10, species,
    form} key; 0 out of range."""
    species = m.call(m.main + 0xBF44F4, m.u64(pp + 0x70))
    form = m.call(m.main + 0xBF41A8, m.u64(pp + 0x70))
    i &= 0xFF
    if i > 5:
        return 0
    with m.frame(0x10) as k:
        m.put(k, 8, m.u64(m.main + 0x46D8EE0) + 0x10); m.put(k + 8, 2, species); m.put(k + 0xA, 2, form)
        return m.call(m.main + _BASE_STAT[i], k) & 0xFF


@lifted(0xE13CB8)
def refresh_max_hp(m, pp, keep_fainted, *_):
    """Recompute the stats (0xe16488 with 0xe13ef0's max HP) and move current HP by the max HP's change,
    capped at the new maximum; a fainted Pokemon stays at 0 when keep_fainted."""
    def max_hp():
        acc = m.u64(pp + 0x70)
        return m.call(m.main + 0xC75438, acc) if m.u64(acc + 8) else m.call(m.main + 0xE13EF0, pp) & 0xFFFF
    old = max_hp() & 0xFFFFFFFF
    acc = m.u64(pp + 0x70)
    cur = (m.call(m.main + 0xCDF348, acc) if m.u64(acc + 8) else m.call(m.main + 0xE13EF0, pp) & 0xFFFF) & 0xFFFFFFFF
    m.call_void(m.main + 0xE16488, m.u64(pp + 0x70), m.call(m.main + 0xE13EF0, pp) & 0xFFFFFFFF)
    if cur == 0 and keep_fainted & 1:
        return
    new = max_hp() & 0xFFFFFFFF
    hp = (min(new, cur) if new < old else (cur - old + new)) & 0xFFFFFFFF
    top = m.call(m.main + 0xC75438, m.u64(pp + 0x70)) & 0xFFFFFFFF
    return _tail(m, m.main + 0xE14810, m.u64(pp + 0x70), min(top, hp))


@lifted(0xF57514)
def copy_f57514(m, dst, src, *_):
    """0xf575d4, then the u16s +0x716/+0x718 when src's +0x28 list (vf 0) holds the static 0x46d3f08
    (the game addresses them from src+0x28, after a pre-indexed load)."""
    m.call_void(m.main + 0xF575D4, dst, src)
    x = m.vcall(src + 0x28, 0)
    if m.u8(m.u64(m.main + 0x46D3F00)) & 1 == 0:
        raise UnliftedCall("static 0x46d3f08 not built")
    static = m.u64(m.main + 0x46D3F08)
    while x:
        if x == static:
            m.put(dst + 0x716, 2, m.u16(src + 0x716)); m.put(dst + 0x718, 2, m.u16(src + 0x718))
            return
        x = m.u64(x)


def _addref_28(m, p):
    c = m.u32(p + 0x28)
    if c == 0xFFFFFFFF:
        raise UnliftedCall("IncrementReference abort: count overflow")
    m.put(p + 0x28, 4, c + 1)


def _release_28(m, p):
    """Drop one reference on a pointer counted at +0x28; the last one runs vf 0x10."""
    c = m.u32(p + 0x28)
    if c == 0:
        raise UnliftedCall("DecrementReference abort: count underflow")
    m.put(p + 0x28, 4, c - 1)
    if c == 1:
        m.vcall_void(p, 0x10)


@lifted(0x288FD54)
def assign_counted(m, o, p, *_):
    """o = p (counted at +0x28); the old pointer goes through 0x175d10c."""
    if p:
        _addref_28(m, p)
    with m.frame(0x10) as tmp:
        m.put(tmp, 8, m.u64(o))
        m.put(o, 8, p)
        return _tail(m, m.main + 0x175D10C, tmp)


@lifted(0xFAAC98)
def pass_counted(m, o, src, *_):
    """0xfad6d0([o+0x50], &copy) with a counted copy of [src], released afterwards."""
    with m.frame(0x10) as tmp:
        p = m.u64(src)
        m.put(tmp, 8, p)
        if p:
            _addref_28(m, p)
        m.call_void(m.main + 0xFAD6D0, m.u64(o + 0x50), tmp)
        p = m.u64(tmp)
        if p:
            _release_28(m, p)


def _addref_shared(m, r):
    """AddReference on an object whose shared state (+0x30) counts at u16 +0x1a; the first reference
    builds +8 through vf 0 of +0x10 (+0x1c = -2)."""
    s = m.u64(r + 0x30)
    if m.u64(s + 0x10) == 0:
        raise UnliftedCall("AddReference abort: m_object is null")
    c = m.u16(s + 0x1A)
    if c == 0xFFFF:
        raise UnliftedCall("AddReference abort: count overflow")
    m.put(s + 0x1A, 2, c + 1)
    if c == 0:
        m.put(s + 8, 8, m.vcall(m.u64(s + 0x10), 0))
        m.put(s + 0x1C, 4, 0xFFFFFFFE)


def _release_shared(m, r):
    """ReleaseReference: the last one clears +0x10 of the shared state and runs the object's vf 0x50."""
    s = m.u64(r + 0x30)
    c = m.u16(s + 0x1A)
    if c == 0:
        raise UnliftedCall("ReleaseReference abort: count underflow")
    m.put(s + 0x1A, 2, c - 1)
    if c == 1:
        m.put(s + 0x10, 8, 0)
        m.vcall_void(r, 0x50)


@lifted(0xFA363C)
def check_fa363c(m, o, *_):
    """1 without [o+0x138]; else its vf 0x78(u8 o+0x95) & 1, the object held by a reference around the call
    (and touched once before)."""
    r = m.u64(o + 0x138)
    if r == 0:
        return 1
    _addref_shared(m, r)
    _release_shared(m, r)
    r = m.u64(o + 0x138)
    if r:
        _addref_shared(m, r)
    v = m.vcall(r, 0x78, m.u8(o + 0x95))
    if r:
        _release_shared(m, r)
    return v & 1


@lifted(0x343E6D0)
def initialize_light_event(m, event, signaled, mode, *_):
    """nn::os::InitializeLightEvent as measured for (not signaled, auto clear 1): bytes +0 and +1 = 1,
    state +4 = 0. Any other arguments are refused."""
    if signaled & 0xFF or mode & 0xFFFFFFFF != 1:
        raise UnliftedCall("InitializeLightEvent with unmeasured arguments")
    m.put(event, 1, 1); m.put(event + 1, 1, 1); m.put(event + 4, 4, 0)
    return event


@lifted(0xF78964)
def copy_entries_f78964(m, dst, src, *_):
    """For each node of src's map list (+0x38): the dst node of the same u16 key (map at dst+8) takes its
    u16s +0x28..+0x2c and 0x58 bytes from +0x30; then the u16s +0x70/+0x72."""
    from pokeldn.sv.battle.engine.containers import find_u16
    node = m.u64(src + 0x38)
    while node:
        d = find_u16(m, dst + 8, m.u16(node + 0x10))
        if not d:
            raise UnliftedCall("0xf78964 on a key dst lacks (the game faults)")
        for k in (0x28, 0x2A, 0x2C):
            m.put(d + k, 2, m.u16(node + k))
        m.write(d + 0x30, m.read(node + 0x30, 0x58))
        node = m.u64(node)
    m.put(dst + 0x70, 2, m.u16(src + 0x70)); m.put(dst + 0x72, 2, m.u16(src + 0x72))


def _reset_owned(destroy):
    """unique_ptr reset: o = p; destroying a previous object (vf 0x18 / `destroy`, then freeing it inside
    the 0xb4e600 deferred-free scope) is not lifted and refuses before any write."""
    def fn(m, o, p, *_):
        if m.u64(o):
            raise UnliftedCall(f"unique_ptr reset over an object ({destroy})")
        m.put(o, 8, p)
    return fn


lifted(0xFAF7B0)(_reset_owned("0x190c248"))
lifted(0x2890C54)(_reset_owned("vf 0x18"))


@lifted(0xFB0194)
def construct_fb0194(m, o, src, *_):
    """vtable main+0x4500158; +8..+0x50 from src (+0x38 a referenced shared object); 0xfaeb40(+0x58); 25
    entries of 0x180 bytes from +0x50b8 reset; then the game clears +0x58..+0xc468 again
    (0xc410 bytes) and +0x7640..+0xc464, and the tail +0xc468..+0xc4a0, +0xc4a3..+0xc4a5."""
    m.put(o, 8, m.main + 0x4500158)
    for k in range(7):
        m.put(o + 8 + 8 * k, 8, m.u64(src + 8 * k))
    shared = m.u64(src + 0x30)
    if shared:
        _addref_shared(m, shared)
    for k in range(3):
        m.put(o + 0x40 + 8 * k, 8, m.u64(src + 0x38 + 8 * k))
    m.call_void(m.main + 0xFAEB40, o + 0x58)
    for e in range(o + 0x50B8, o + 0x7638, 0x180):
        m.write(e, bytes(0x180))
        m.put(e + 0x160, 1, 5); m.put(e + 0x164, 8, 0); m.put(e + 0x16C, 1, 0); m.put(e + 0x16E, 2, 10)
        m.put(e + 0x170, 4, 0x0A0A0A0A); m.put(e + 0x174, 1, 10); m.put(e + 0x178, 2, 0)
        m.put(e + 0x17A, 1, 0); m.put(e + 0x17C, 2, 0)
    m.call_void(m.main + 0x12702C0, o + 0x50B8)
    m.put(o + 0xC4A3, 2, 0); m.put(o + 0xC4A5, 1, 0)
    m.write(o + 0x58, bytes(0xC410))
    m.call_void(m.main + 0x12702C0, o + 0x50B8)
    m.write(o + 0x7640, bytes(0x4E24))
    m.write(o + 0xC484, bytes(0x1C))
    m.write(o + 0xC468, bytes(0x1A))


@lifted(0xCEDA90)
def base_stat_of(m, o, i, *_):
    return m.call(m.main + 0xCEDAA8, m.u64(o + 0x48), i)


# Nature modifiers (s8, 25 natures x 5 stats Atk Def SpA SpD Spe) at 0x3c62e98.
_NATURE_3C62E98 = (
    0, 0, 0, 0, 0, 1, -1, 0, 0, 0, 1, 0, 0, 0, -1, 1, 0, -1, 0, 0, 1, 0, 0, -1, 0, -1, 1, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 1, 0, 0, -1, 0, 1, -1, 0, 0, 0, 1, 0, -1, 0, -1, 0, 0, 0, 1, 0, -1, 0, 0, 1, 0, 0, 0, 0,
    0, 0, 0, -1, 0, 1, 0, 0, 0, -1, 1, -1, 0, 1, 0, 0, 0, -1, 1, 0, 0, 0, 0, 1, 0, -1, 0, 0, 0, 0, 0, 0,
    0, 1, -1, 0, -1, 0, 0, 1, 0, 0, -1, 0, 1, 0, 0, 0, 0, 1, -1, 0, 0, -1, 1, 0, 0, 0, 0, 0, 0)


def _computed_stat(base_fn, iv_bit, iv_fn, ev_fn, col):
    """A stat computed from the core record: ((IV + 2 base + EV/4) * level / 100 + 5), times 0.9 or
    1.1 by nature; a hyper-trained IV (0xc1eb6c bit) counts 31."""
    def fn(m, pp, *_):
        acc = m.u64(pp + 0x70)
        if m.u64(acc + 8):
            level = m.call(m.main + 0xD9987C, acc)
        else:
            sp = m.call(m.main + 0xBF44F4, acc)
            fo = m.call(m.main + 0xBF41A8, m.u64(pp + 0x70))
            level = m.call(m.main + 0xE13DA0, sp, fo, m.call(m.main + 0xE14B64, m.u64(pp + 0x70))) & 0xFF
        sp = m.call(m.main + 0xBF44F4, m.u64(pp + 0x70))
        fo = m.call(m.main + 0xBF41A8, m.u64(pp + 0x70))
        with m.frame(0x10) as k:
            m.put(k, 8, m.u64(m.main + 0x46D8EE0) + 0x10); m.put(k + 8, 2, sp); m.put(k + 0xA, 2, fo)
            base = m.call(m.main + base_fn, k)
        if m.call(m.main + 0xC1EB6C, m.u64(pp + 0x70)) >> iv_bit & 1:
            iv = 0x1F
        else:
            iv = m.call(m.main + iv_fn, m.u64(pp + 0x70)) & 0xFFFF
        ev = m.call(m.main + ev_fn, m.u64(pp + 0x70))
        nature = m.call(m.main + 0xC4EA44, m.u64(pp + 0x70)) & 0xFFFF
        v = ((iv + 2 * (base & 0xFF) + (ev >> 2 & 0x3FFF)) * (level & 0xFF)) & 0xFFFFFFFF
        v = (v // 100 + 5) & 0xFFFFFFFF
        i = 5 * nature + col
        mod = _NATURE_3C62E98[i] if i < len(_NATURE_3C62E98) else m.s(m.main + 0x3C62E98 + i, 1)
        if mod in (-1, 1):
            v = ((v * (0x5A if mod == -1 else 0x6E)) & 0xFFFE) // 100
        return v
    return fn


lifted(0xE1415C)(_computed_stat(0xCEDDA8, 1, 0xD982BC, 0xD8FE2C, 0))
lifted(0xE14408)(_computed_stat(0xCEE118, 5, 0xD98C94, 0xD907F8, 4))


@lifted(0x288FD24)
def hold_counted_88(m, o, pp, *_):
    r = _tail(m, m.main + 0x288FD54, o + 0x88, m.u64(pp))
    m.put(o + 0xE6, 1, 1)
    return r


@lifted(0x2892AB4)
def tail_2897a10(m, o, pp, *_):
    return _tail(m, m.main + 0x2897A10, o + 0x48, m.u64(pp))


@lifted(0xFA58C8)
def set_pair_fa58c8(m, o, pair, *_):
    m.call_void(m.main + 0xFA6424, o + 0x58, m.u64(pair))
    return _tail(m, m.main + 0xFA6560, o + 0x60, m.u64(pair + 8))


@lifted(0x18B7DB4)
def register_by_byte(m, o, p, *_):
    """The entry for p's byte +0xe2 in the map at o+0x1a0 (0x18b7e00) takes p at +0x30."""
    with m.frame(0x10) as k:
        m.put(k, 4, m.call(m.main + 0x126B014, p) & 0xFF)
        r = m.call(m.main + 0x18B7E00, o + 0x1A0, k)
    if r:
        m.put(r + 0x30, 8, p)
    return r


@lifted(0x2897A10)
def assign_shared_ref(m, o, p, *_):
    """o = p (shared-state reference); the old one goes through 0x1858568."""
    if p:
        _addref_shared(m, p)
    with m.frame(0x10) as tmp:
        m.put(tmp, 8, m.u64(o))
        m.put(o, 8, p)
        return _tail(m, m.main + 0x1858568, tmp)


@lifted(0x15372E8)
def resolve_hit_15372e8(m, o, out, rec, *_):
    """rec: u32 target +0, attacker +4, u16 +8/+0xa, flags +0xc/+0xd/+0xf/+0x10/+0x11/+0x16, body
    +0x14. *out = whether the hit lands (neither 0x1872ce0 check on the target nor on the attacker
    refuses it); then the hit's commands (0x17d3110, 0x114b0ac or 0xcb/0x125) or the refusal's
    (0xcb/0x11d, 0xca/0x237), and 0xc8 for the target when +0xc."""
    m.put(out, 1, 0)
    team = m.u64(m.u64(o + 0x10) + 0x30)
    a = m.call(m.main + 0xF21C94, team, m.u32(rec + 4))
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), m.u32(rec))
    f10, f11 = m.u8(rec + 0x10), m.u8(rec + 0x11)
    t = m.u64(m.u64(o + 0x78) + 0x15E0)
    q = lambda: m.u64(m.u64(o + 0x20) + 0x18)
    if m.call(m.main + 0x1832E08, t, a) & 1:
        if not m.vcall(a, 0x1F8) & 1 or not m.u8(rec + 0xD):
            return
        target = m.u32(rec)
        return _tail(m, m.main + 0x157EBC0, q(), 0xCB, target, 0x11F, m.vcall(a, 0x98) & 0xFFFFFFFF, 0xFFFF0000)
    if b and not f11 and m.call(m.main + 0x1872CE0, t, b) & 1:
        why = 3
    elif not f10 and m.call(m.main + 0x1872CE0, t, a) & 1:
        why = 2
    else:
        why = 0
        m.put(out, 1, 1)
    if m.u8(rec + 0xC):
        m.call_void(m.main + 0x17CE0EC, m.u64(o + 0x20), m.u32(rec), 0)
    if m.u8(out):
        m.call_void(m.main + 0x17D3110, o, a, m.u16(rec + 8), m.u8(rec + 0xF))
        if m.u8(rec + 0x16) & 0x7F:
            m.call_void(m.main + 0x114B0AC, m.u64(o + 0x20), m.u32(rec), rec + 0x14)
        elif m.u16(rec + 0xA):
            m.call_void(m.main + 0x157EBC0, q(), 0xCB, m.u32(rec + 4), 0x125, m.u32(rec + 4), m.u16(rec + 0xA),
                        0xFFFF0000)
    elif why == 2:
        m.call_void(m.main + 0x157EBC0, q(), 0xCB, m.u32(rec), 0x11D, m.u32(rec + 4), 0xFFFF0000)
    elif why == 3:
        m.call_void(m.main + 0x157EBC0, q(), 0xCA, m.u32(rec), 0x237, 0xFFFF0000)
    if m.u8(rec + 0xC) and m.u32(rec):
        return _tail(m, m.main + 0x119AFF0, q(), 0xC8, m.u32(rec))


@lifted(0x173C128)
def pick_targets(m, o, a1, a2, *args):
    """Dispatch on the battle mode a2+0x36c: 2 -> 0x173f110 (setup flag 0x4d2 set) or 0x1740f7c, 1 ->
    0x173e564, else 0x173d77c; every argument (stack ones included) passes through."""
    mode = m.u32(a2 + 0x36C)
    if mode == 2:
        flag = m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x499) >> 2 & 1
        target = 0x173F110 if flag else 0x1740F7C
    else:
        target = 0x173E564 if mode == 1 else 0x173D77C
    return _tail(m, m.main + target, o, a1, a2, *args)


def _standing(m, o_it_owner, pokecon):
    """The standing-member walk the server inlines (0x1147774, then 0x1360dbc per member): yields each
    member (0 for an empty slot); nothing when no member stands."""
    from pokeldn.sv.battle.engine.flow import first_standing, next_standing
    with m.frame(0x30) as it:
        m.put(it, 8, m.u64(m.main + 0x46E2580) + 0x10)
        m.put(it + 8, 8, o_it_owner); m.put(it + 0x10, 8, pokecon)
        m.put(it + 0x18, 2, 0); m.put(it + 0x1A, 1, 1)
        first_standing(m, it)
        if m.u8(it + 0x1A):
            return
        while next_standing(m, it, it + 0x20):
            yield m.u64(it + 0x20)


@lifted(0x173F110)
def pick_targets_raid(m, o, a1, pokecon, attacker, a4, move, other, lst, done, *_):
    """The target list of a move in a raid: *done = 0, then by the move's target kind (u8 move+0xa,
    jump table 0x3c6a58c) members go into lst through the member-list append (at most 11, once each);
    kinds 0/3, 9 and 13 set *done. Kinds 5 and 8 are not lifted and refuse before any write."""
    from pokeldn.sv.battle.engine.flow import add_member
    kind = m.u8(move + 0xA)
    if kind in (5, 8):
        raise UnliftedCall(f"0x173f110 target kind {kind}")
    if kind in (1, 2) and 0xFF6F54 not in __import__("pokeldn.sv.battle.machine", fromlist=["x"]).FUNCTIONS:
        raise UnliftedCall("main+0xff6f54")
    if m.u8(m.u64(m.main + 0x46D7940)) & 1 == 0 or (kind == 7 and m.u8(m.u64(m.main + 0x46D3F00)) & 1 == 0):
        raise UnliftedCall("static not built")
    m.put(done, 1, 0)
    parties = m.u64(pokecon + 0x30)
    aid = lambda: m.vcall(attacker, 0x98) & 0xFFFFFFFF
    raid = lambda: _raid_id_inline(m, m.u64(m.u64(o + 0x10) + 0x310))
    a_id = aid()
    flag = 0
    if raid() != a_id:
        key = m.u16(move)
        table = m.u64(m.u64(m.main + 0x46D7948))
        m.put(m.u64(m.main + 0x46D7950), 8, table)
        rec = m.call(m.main + 0xBF60CC, table, key)
        with m.frame(0x10) as k:
            m.put(k, 8, m.u64(m.main + 0x46DDAD8) + 0x10); m.put(k + 8, 2, m.u16(move))
            if fb.u8(m, rec, 5) and not m.call(m.main + 0x20FEAE8, k) & 1:
                flag = 1
            else:
                m.put(k + 8, 2, m.u16(move))
                flag = int(m.call(m.main + 0x179412C, k) & 0xFFFF != 0)
    w28 = m.call(m.main + 0x173F034, o, a1, move, attacker, a4 & 0xFFFFFFFF) & 0xFFFFFFFF
    m.call(m.main + 0xFE161C, m.u64(pokecon + 0x290), aid())
    if kind in (0, 3):
        with m.frame(0x10) as out:
            m.call_void(m.main + 0x1153868, m.u64(m.u64(parties + 0x18) + 0x290), w28, out, out + 8)
            client, idx = m.u8(out), m.u8(out + 8)
        if client != 5 and idx < m.u8(parties + client * 0x38 + 0x58):
            b = m.u64(parties + client * 0x38 + idx * 8 + 0x28)
            if b:
                add_member(m, lst, b)
        m.put(done, 1, 1)
    elif kind == 1:
        p = m.call(m.main + 0xFF6F54, parties, w28)
        t = p if p and not m.vcall(p, 0x200) & 1 else attacker
        if flag and m.vcall(t, 0x98) & 0xFFFFFFFF != aid():
            t = attacker
        add_member(m, lst, t)
    elif kind == 2:
        if not m.u8(pokecon + 0x370):
            return
        p = m.call(m.main + 0xFF6F54, parties, w28)
        if p and m.vcall(p, 0x98) & 0xFFFFFFFF != aid():
            add_member(m, lst, p)
    elif kind == 4:
        if raid() != aid():
            for p in _standing(m, a1, pokecon):
                if flag:
                    if not m.call(m.main + 0x17D5D98, o, attacker, p) & 1 and m.vcall(p, 0x98) & 0xFFFFFFFF != aid():
                        add_member(m, lst, p)
                elif m.vcall(p, 0x98) & 0xFFFFFFFF != aid() and p:
                    add_member(m, lst, p)
        elif m.u8(move + 0x14):
            for p in _standing(m, a1, pokecon):
                if m.vcall(p, 0x98) & 0xFFFFFFFF != aid() and p:
                    add_member(m, lst, p)
        else:
            p = m.call(m.main + 0x2886D48, o)
            if p:
                add_member(m, lst, p)
    elif kind == 6:
        for p in _standing(m, a1, pokecon):
            r = m.call(m.main + 0x17D5D98, o, attacker, p) & 1
            if flag:
                if r and m.vcall(p, 0x98) & 0xFFFFFFFF == aid():
                    add_member(m, lst, p)
            elif p and r:
                add_member(m, lst, p)
    elif kind == 7:
        if other & 0xFFFFFFFF == 0:
            add_member(m, lst, attacker)
            return
        b = m.call(m.main + 0xF21C94, parties, other & 0xFFFFFFFF)
        if not b:
            return
        x = m.vcall(b + 0x28, 0)
        static = m.u64(m.main + 0x46D3F08)
        while x and x != static:
            x = m.u64(x)
        if x:
            add_member(m, lst, b)
    elif kind == 9:
        if raid() == aid():
            p = m.call(m.main + 0x2886D48, o)
        else:
            p = m.call(m.main + 0xF6FC68, m.u64(m.u64(o + 0x10) + 0x310))
        if p:
            add_member(m, lst, p)
        m.put(done, 1, 1)
    elif kind == 13:
        if other & 0xFFFFFFFF == 0:
            return
        b = m.call(m.main + 0xF21C94, parties, other & 0xFFFFFFFF)
        if b:
            add_member(m, lst, b)
        m.put(done, 1, 1)


def _peek_form(m, acc):
    """The form (u16 +0x1c of logical block 0) as the record's accessor reads it, decrypted on a
    copy (lift2._peek_block_u16)."""
    from pokeldn.sv.battle.engine import pokemon as _pk
    data = bytearray(m.read(m.u64(acc + 0x10), _pk.CORE))
    if m.u8(acc + 0x18):
        seed = int.from_bytes(data[0:4], "little")
        for i in range(_pk.BLOCKS, _pk.CORE, 2):
            seed = _pk._lcg(seed)
            v = (data[i] | data[i + 1] << 8) ^ (seed >> 16)
            data[i], data[i + 1] = v & 0xFF, v >> 8
        total = sum(data[i] | data[i + 1] << 8 for i in range(_pk.BLOCKS, _pk.CORE, 2)) & 0xFFFF
        if total != (data[6] | data[7] << 8):
            data[4] |= 4
    if data[4] >> 2 & 1:
        return m.u16(m.main + _pk.BAD_READ_CORE + _pk.BLOCKS + 0x1C)
    pos = _pk.BLOCK_POSITION[(int.from_bytes(data[0:4], "little") >> 13) & 0x1F][0]
    at = _pk.BLOCKS + 0x50 * pos + 0x1C
    return data[at] | data[at + 1] << 8


def _need_form_change(m, pp, form):
    """Refuse before any write when 0x133b218(pp, form) would change the form through a callee not
    lifted."""
    from pokeldn.sv.battle.machine import FUNCTIONS
    if 0x133B218 not in FUNCTIONS:
        raise UnliftedCall("main+0x133b218")
    if _peek_form(m, m.u64(pp + 0x70)) != form & 0xFFFF:
        for a in (0xBF41A8, 0xBF44F4, 0x133BA0C, 0xDF289C, 0xD99784, 0x133B78C, 0xDF2550, 0xBEC030,
                  0x133B4B4, 0xDF644C, 0xE13B9C):
            if a not in FUNCTIONS:
                raise UnliftedCall(f"form change: main+0x{a:x}")


def _holds_static(m, pp):
    x = m.vcall(pp + 0x28, 0)
    static = m.u64(m.main + 0x46DCD58)
    while x and x != static:
        x = m.u64(x)
    return x != 0


@lifted(0x2D1F4BC)
def refresh_form_hp(m, b, *_):
    """After 0x2d3dc58: when the Pokemon's +0x28 list (vf 0) holds the static 0x46dcd58, take its form
    (+0x718: the record's form when +0x6f, else +0x712 applied through 0x133b218), set +0x58 = stat 0 *
    u16 +0x3f4 / 10, move HP toward it (vf 0x2e8 up, vf 0x2e0 down) and tail-call vf 0x810. The
    0x133b218 branch refuses before any write when it would change the form through a callee not
    lifted."""
    if m.u8(m.u64(m.main + 0x46DCD50)) & 1 == 0:
        raise UnliftedCall("static 0x46dcd58 not built")
    if m.u8(b + 0x6F) == 0 and _holds_static(m, m.u64(b + 0x48)):
        _need_form_change(m, m.u64(m.u64(b + 0x48) + 0x48), m.u16(b + 0x712))
    m.call_void(m.main + 0x2D3DC58, b)
    pp = m.u64(b + 0x48)
    if not _holds_static(m, pp):
        return 0
    if m.u8(b + 0x6F):
        m.put(b + 0x718, 2, m.call(m.main + 0xBF41A8, m.u64(m.u64(pp + 0x48) + 0x70)))
    else:
        form = m.u16(b + 0x712)
        m.put(b + 0x718, 2, form)
        m.call_void(m.main + 0x133B218, m.u64(pp + 0x48), form, 0)
    hp = m.vcall(b, 0x108) & 0xFFFFFFFF
    cur = m.vcall(b, 0x110) & 0xFFFFFFFF
    v = m.vcall(m.u64(b + 0x48), 0x70, 0) & 0xFFFF
    top = ((v * m.u16(b + 0x3F4)) & 0xFFFFFFFF) // 10
    m.put(b + 0x58, 2, top)
    if cur & 0xFFFF < top & 0xFFFF:
        m.vcall_void(b, 0x2E8, (top - cur) & 0xFFFFFFFF)
    if cur & 0xFFFF > top & 0xFFFF and hp & 0xFFFF > top & 0xFFFF:
        m.vcall_void(b, 0x2E0, (hp - top) & 0xFFFFFFFF)
    fn = m.u64(m.u64(b) + 0x810)
    return _tail(m, fn, b, fn)


def _tls_stack_built(m):
    """The thread's object stack (lift0._tls_stack), refused before any write while its static is
    not built."""
    from pokeldn.sv.battle.engine.lift0 import _tls_stack
    if m.u8(m.main + 0x4765A38) & 1 == 0:
        raise UnliftedCall("static 0x4765a30 not built")
    return _tls_stack(m)


@lifted(0x17E5EBC)
def copy12_scoped(m, o, dst, src, *_):
    """With [o] pushed on the thread's object stack: copy 12 bytes src -> dst. Returns the stack."""
    top = m.u64(o)
    t = _tls_stack_built(m)
    if t:
        n = m.u64(t + 0x80)
        if n >= 0x10:
            raise UnliftedCall("abort: object stack full")
        m.put(t + 8 * n, 8, top)
        m.put(t + 0x80, 8, n + 1)
    x = m.u64(src); w = m.u32(src + 8)
    m.put(dst + 8, 4, w); m.put(dst, 8, x)
    if t:
        m.put(t + 0x80, 8, m.u64(t + 0x80) - 1)
    return t


@lifted(0xFA97BC)
def construct_fa97bc(m, o, *_):
    """Constructor: vtables 0x44ff200 / 0x44ff238, +8 the object on top of the thread's stack (or 0),
    three empty 0x28-byte lists at +0x30, +0x58, +0x80 (0xfa98a4, the last a tail call)."""
    t = _tls_stack_built(m)
    m.put(o + 0x10, 8, 0); m.put(o + 0x18, 4, 0)
    m.put(o, 8, m.u64(m.main + 0x46D66F8) + 0x10)
    top = 0
    if t:
        n = m.u64(t + 0x80)
        if n:
            top = m.u64(t + 8 * n - 8)
    m.put(o + 0x28, 4, 0)
    m.put(o, 8, m.main + 0x44FF200); m.put(o + 8, 8, top)
    m.put(o + 0x20, 8, m.main + 0x44FF238)
    m.call_void(m.main + 0xFA98A4, o + 0x30)
    m.call_void(m.main + 0xFA98A4, o + 0x58)
    m.call_void(m.main + 0xFA98A4, o + 0x80)
    return (o + 0x80) & 0xFFFFFFFFFFFFFFFF      # the leaf 0xfa98a4 leaves x0 as it got it


@lifted(0xB44204)
def handle_lookup(m, o, handle, *_):
    """Handle table at o (slot table +0x8040, reader lock +0x8110, light event +0x8120): writes to x8
    the live entry for `handle` (32-byte entries, 0x400 per block at [o + 0x30 + 32 * (handle >> 10)])
    with its u16 count (+0x18) raised, or 0 when the handle is freed or stale."""
    out = m.x8
    base, lock = o + 0x8040, o + 0x8110
    cur = m.call(m.main + 0x343C290)
    owner = m.u64(lock)
    if owner and owner != cur:
        raise UnliftedCall("handle table held by another thread")
    m.put(lock + 8, 8, m.u64(lock + 8) + 1)
    d = (handle - m.u32(base)) & 0xFFFFFFFF
    word = m.u64(m.u64(base + 0x88) + ((d >> 3) & 0x1FFFFFF8))
    m.put(lock + 8, 8, m.u64(lock + 8) - 1)
    r = m.call(m.main + 0x343E5E0, o + 0x8120)
    if (word >> (d & 63)) & 1 == 0:
        m.put(out, 8, 0)
        return r
    blk = m.u64(o + 0x30 + 32 * ((handle >> 10) & 0x3FFFFF))
    j = handle & 0x3FF
    if m.u64(blk + 0x8000) <= j:
        raise UnliftedCall("abort: handle past its block")
    e = blk + 32 * j
    if m.u64(e) != handle:
        m.put(out, 8, 0)
        return r
    m.put(out, 8, e)
    n = m.u16(e + 0x18)
    if n == 0xFFFF:
        raise UnliftedCall("abort: handle count overflow")
    m.put(e + 0x18, 2, n + 1)
    return r


@lifted(0xB44438)
def handle_free(m, o, p, *_):
    """Free the handle u32 *p of the table at o (writer lock +0xd0, light event +0xe0): when its bit in
    the live bitmap ([o + 0x88], index *p - *o) is set, push it on the free deque (map +0x18/+0x20,
    start +0x50, size +0x58, 0x400 u32 per block) under the allocator [o + 0x60] on the thread's object
    stack, clear the bit and lower the live count (+8). Tail-calls SignalLightEvent."""
    if m.u32(p) < m.u32(o):
        return o
    lock = o + 0xD0
    cur = m.call(m.main + 0x343C290)
    if m.u64(lock) or m.u64(lock + 8):
        raise UnliftedCall("handle table locked")
    d = (m.u32(p) - m.u32(o)) & 0xFFFFFFFF
    live = (m.u64(m.u64(o + 0x88) + ((d >> 3) & 0x1FFFFFF8)) >> (d & 63)) & 1
    if live:
        mp, me = m.u64(o + 0x18), m.u64(o + 0x20)
        cap = 0 if me == mp else ((me - mp) * 128 - 1) & 0xFFFFFFFFFFFFFFFF
        back = (m.u64(o + 0x50) + m.u64(o + 0x58)) & 0xFFFFFFFFFFFFFFFF
        if cap == back:
            raise UnliftedCall("free deque grows (0xb44724)")
        t = _tls_stack_built(m)
    m.put(lock, 8, cur); m.put(lock + 8, 8, 0)
    if live:
        slot = 0 if me == mp else m.u64(mp + 8 * (back >> 10)) + 4 * (back & 0x3FF)
        alloc = m.u64(o + 0x60)
        if t:
            n = m.u64(t + 0x80)
            if n >= 0x10:
                raise UnliftedCall("abort: object stack full")
            m.put(t + 8 * n, 8, alloc)
            m.put(t + 0x80, 8, n + 1)
        m.put(slot, 4, m.u32(p))
        if t:
            m.put(t + 0x80, 8, m.u64(t + 0x80) - 1)
        m.put(o + 0x58, 8, m.u64(o + 0x58) + 1)
        d = (m.u32(p) - m.u32(o)) & 0xFFFFFFFF
        w = m.u64(o + 0x88) + ((d >> 3) & 0x1FFFFFF8)
        m.put(w, 8, m.u64(w) & ~(1 << (d & 63)))
        m.put(o + 8, 4, m.u32(o + 8) - 1)
    m.put(lock, 8, 0)
    return m.call(m.main + 0x343E5E0, o + 0xE0)


@lifted(0x2D38B60)
def ref_slot_2d38b60(m, o, key, *_):
    """Writes to x8 the counted reference [o + 0x138 + 0x28 * s32 key+4 + 8 * u32 key+8] with its
    count (u16 +0x1a of the control block at +0x30) raised; the first reference builds the object
    (vf 0 of [cb + 0x10], kept at cb+8, cb+0x1c = -2)."""
    e = m.u64((o + 0x28 * m.s(key + 4, 4) + 8 * m.u32(key + 8) + 0x138) & 0xFFFFFFFFFFFFFFFF)
    if e:
        cb = m.u64(e + 0x30)
        if m.u64(cb + 0x10) == 0 or m.u16(cb + 0x1A) == 0xFFFF:
            raise UnliftedCall("abort in AddReference")
    m.put(m.x8, 8, e)
    if not e:
        return o
    n = m.u16(cb + 0x1A)
    m.put(cb + 0x1A, 2, n + 1)
    if n:
        return o
    r = m.vcall(m.u64(cb + 0x10), 0)
    m.put(cb + 8, 8, r); m.put(cb + 0x1C, 4, 0xFFFFFFFE)
    return r


def _bucket(h, n, pc):
    if pc <= 1:
        return h & (n - 1)
    return h if h < n else h % n


def _counted_in_list(m, o, v):
    """1 when the list at [o + 0x90] holds a node (u32 +0x1c != 0xff) whose +0x28 is v."""
    node = m.u64(o + 0x90)
    while node:
        if m.u32(node + 0x1C) != 0xFF and m.u64(node + 0x28) == v:
            return 1
        node = m.u64(node)
    return 0


@lifted(0x2A1D428)
def needs_more_2a1d428(m, o, *_):
    """1 unless fewer of the members counted below are in the list [o + 0x90] than 0x2014e38 says
    (the lookup of u32 +0x58 in the hash map +0x60/+0x68 and the +0xc8/+0xca/+0xcb flags answer
    first); the count walks either the 0x1319488 entries of [[o + 0xd8] + 0x10] (when +0xd0) or the
    static table [0x46d6ca0] through 0xca4118."""
    cfg = m.u64(o + 0x50)
    go_main = True
    if m.u32(cfg + 0x34) == 2:
        k = m.u8(cfg + 0x8D)
        if (k - 3) & 0xFFFFFFFF <= 3:
            return int(m.u8(o + 0xCA) != 0)
        if k == 0:
            key, want = m.u32(o + 0x58), m.u32(o + 0x5C)
            if want != 0xFF:
                if key == want:
                    return 0
            else:
                n = m.u64(o + 0x68)
                if n == 0:
                    return 1
                pc = bin(n).count("1")
                b = _bucket(key, n, pc)
                x = m.u64(m.u64(o + 0x60) + 8 * b)
                if x == 0:
                    return 1
                x = m.u64(x)
                while True:
                    if x == 0:
                        return 1
                    h = m.u64(x + 8)
                    if h == key:
                        if m.u32(x + 0x10) == key:
                            break
                    elif _bucket(h, n, pc) != b:
                        return 1
                    x = m.u64(x)
                if m.u32(x + 0x20) != 1:
                    return 1
            if m.u8(o + 0xCB):
                m.put(o + 0xCB, 1, 1)
                return 1
            g = m.u8(m.main + 0x4739728)
            m.put(o + 0xCB, 1, g)
            if g & 1:
                return 1
    if m.u8(o + 0xC8):
        return 1
    if m.call(m.main + 0x2014F8C, o) & 1 == 0:
        return 1
    cnt = 0
    if m.u8(o + 0xD0) == 0:
        if m.u8(m.u64(m.main + 0x46D6C98)) & 1 == 0:
            raise UnliftedCall("static at [0x46d6ca0] not built")
        tbl = m.u64(m.u64(m.main + 0x46D6CA0))
        m.put(m.u64(m.main + 0x46D6CA8), 8, tbl)
        lim = m.u32(m.main + 0x44DFCB0)
        if tbl and lim:
            src = m.u64(m.main + 0x46D0860)
            i = 0
            while True:
                if m.u64(tbl + 0x70) and lim > (i & 0xFF) and m.u64(src):
                    with m.frame(0x30) as p:
                        m.put(p + 0x28, 8, 0)
                        m.call_sret(m.main + 0xCA4118, p, m.u64(src), p + 0x28, i)
                        if m.u32(p) == 0 and m.u64(p + 0x28):
                            cnt += _counted_in_list(m, o, m.u64(p + 0x28))
                lim = m.u32(m.main + 0x44DFCB0)
                i = (i + 1) & 0xFFFFFFFF
                if i >= lim:
                    break
    else:
        h = m.u64(o + 0xD8)
        n = 0
        if h and m.u16(h + 0x1A) and m.u64(o + 0xD8) and m.u64(h + 0x10):
            n = m.call(m.main + 0x1319488, m.u64(h + 0x10) - 0x28) & 0xFFFF
        for i in range(n):
            v = 0
            h = m.u64(o + 0xD8)
            if h:
                x = m.u64(h + 0x10)
                if x:
                    e = m.u64(x + 0x148)
                    m.put(x + 0x1A8, 8, 0)
                    if e != m.u64(x + 0x150):
                        while True:
                            m.call_void(m.main + 0x12FCB68, x + 0x180, e + 8)
                            e += 0x10
                            if e == m.u64(x + 0x150):
                                break
                        if m.u64(x + 0x1A8) > i:
                            v = m.u64(m.u64(x + 0x1A0) + 8 * i)
            cnt += _counted_in_list(m, o, v)
    r = m.call(m.main + 0x2014E38, o)
    return int((cnt & 0xFFFF) < (r & 0xFF))


def _construct_counted_base(m, o):
    """The base part both 0xfa21a8 and 0xfae2c8 inline: vtable [0x46d8c78] (+0x10, +0x88, +0xd8 at
    +0, +0x20, +0x28), +8 the object on top of the thread's stack, then 0xc1a3f4(+0x30, +0x28), whose
    result it returns."""
    t = _tls_stack_built(m)
    m.put(o + 0x10, 8, 0); m.put(o + 0x18, 4, 0)
    m.put(o, 8, m.u64(m.main + 0x46D66F8) + 0x10)
    top = 0
    if t:
        n = m.u64(t + 0x80)
        if n:
            top = m.u64(t + 8 * n - 8)
    v = m.u64(m.main + 0x46D8C78)
    m.put(o, 8, v + 0x10); m.put(o + 8, 8, top)
    m.put(o + 0x20, 8, v + 0x88); m.put(o + 0x28, 8, v + 0xD8)
    m.put(o + 0x38, 8, 0); m.put(o + 0x30, 8, 0)
    return _tail(m, m.main + 0xC1A3F4, o + 0x30, o + 0x28)


@lifted(0xFAE2C8)
def construct_fae2c8(m, o, flag, *_):
    """Constructor: the counted base, vtables 0x44ed458 (+0x78, +0xc8), two empty lists (+0x40..+0x78
    and +0x80..+0xa8, each with the owner +8 and 0x1fffffffffffffff), the byte +0xb0 = flag."""
    r = _construct_counted_base(m, o)
    vt = m.main + 0x44ED458
    m.put(o, 8, vt); m.put(o + 0x20, 8, vt + 0x78); m.put(o + 0x28, 8, vt + 0xC8)
    top = m.u64(o + 8)
    m.put(o + 0x40, 8, 0); m.put(o + 0x48, 8, 0)
    m.put(o + 0x70, 8, 0); m.put(o + 0x78, 4, 0)
    m.put(o + 0xA0, 8, 0); m.put(o + 0xA8, 4, 0)
    m.put(o + 0xB0, 1, flag)
    m.put(o + 0x50, 8, 0); m.put(o + 0x58, 8, 0)
    m.put(o + 0x80, 8, 0); m.put(o + 0x88, 8, 0)
    m.put(o + 0x60, 8, top); m.put(o + 0x68, 8, 0x1FFFFFFFFFFFFFFF)
    m.put(o + 0x90, 8, top); m.put(o + 0x98, 8, 0x1FFFFFFFFFFFFFFF)
    return r


@lifted(0xFA21A8)
def construct_fa21a8(m, o, a, b, *_):
    """Constructor: vtables 0x45001e8 (+0x828, +0x878, +0x8d0 at +0x20, +0x28, +0x40), +8 the object on
    top of the thread's stack, 0xc1a3f4(+0x30, +0x28), 0xfa24b4(+0x48), the fields from +0x400 cleared
    (bytes +0x40d 2, +0x48e 10, 18 records of 16 bytes at +0x5d8 with byte 10), +0x700 a, +0x708 b.
    Returns o + 0x490 (memset's result)."""
    _construct_counted_base(m, o)
    vt = m.main + 0x45001E8
    m.put(o, 8, vt); m.put(o + 0x20, 8, vt + 0x828)
    m.put(o + 0x28, 8, vt + 0x878); m.put(o + 0x40, 8, vt + 0x8D0)
    m.call_void(m.main + 0xFA24B4, o + 0x48)
    for off, size, val in ((0x405, 8, 0), (0x400, 8, 0), (0x40D, 1, 2), (0x41C, 8, 0), (0x424, 1, 0),
                           (0x426, 8, 0), (0x42E, 1, 0), (0x410, 8, 0), (0x417, 4, 0), (0x430, 8, 0),
                           (0x438, 1, 0), (0x43A, 1, 0), (0x43C, 8, 0), (0x444, 1, 0), (0x44E, 1, 0),
                           (0x446, 8, 0), (0x450, 1, 0), (0x45A, 1, 0), (0x452, 8, 0), (0x464, 1, 0),
                           (0x45C, 8, 0), (0x466, 1, 0), (0x468, 8, 0), (0x470, 1, 0), (0x472, 8, 0),
                           (0x47A, 1, 0), (0x47C, 1, 0), (0x47E, 4, 0x10000), (0x482, 8, 0),
                           (0x48A, 4, 0), (0x48E, 1, 10)):
        m.put(o + off, size, val)
    m.write(o + 0x490, bytes(0x25C))
    for r in range(0x5D8, 0x6E8, 0x10):
        m.put(o + r, 1, 10); m.put(o + r + 0xC, 4, 0); m.put(o + r + 4, 4, 0); m.put(o + r + 8, 2, 0)
    m.put(o + 0x6E8, 1, 10)
    m.put(o + 0x6F2, 4, 0); m.put(o + 0x6F8, 4, 0); m.put(o + 0x6F0, 1, 0); m.put(o + 0x6EC, 4, 0)
    m.put(o + 0x700, 8, a); m.put(o + 0x708, 8, b)
    return o + 0x490


@lifted(0x114C0A0)
def release_kind3_of(m, q, key, *_):
    """Release (0x13608b0) every kind-3 entry of q's owner whose u16 (0xf7bb74) is `key`. Returns the
    last callee's x0 (0 when there is none)."""
    owner = m.call(m.main + 0x114C158, q)
    e = m.call(m.main + 0x114D844, owner, 3)
    if e == 0:
        return 0
    while True:
        nxt = m.call(m.main + 0x1155BDC, owner, e, 1)
        r = m.call(m.main + 0xF7BB74, e)
        if key & 0xFFFFFFFF == r & 0xFFFF:
            r = _tail(m, m.main + 0x13608B0, q, e)
            if r is None:
                r = q           # 0x13608b0's early return leaves x0
        if nxt == 0:
            return r
        e = nxt


@lifted(0x114BEE4)
def release_kind3_114bee4(m, o, key, *_):
    return m.call(m.main + 0x114C0A0, m.u64(o + 0x18), key)


@lifted(0x114BF8C)
def note_0x69(m, o, a, b, *_):
    """0x114bfdc([o+0x20], a, b) & 1 (x1, x2 pass through), then event 0x69 (a, b) to [o+0x18]
    (0x119aff0)."""
    r = m.call(m.main + 0x114BFDC, m.u64(o + 0x20), a, b)
    m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0x69, a & 0xFFFFFFFF, b & 0xFF)
    return r & 1


@lifted(0x183F0AC)
def apply_183f0ac(m, o, done, rec, *_):
    """*done = 0; unless vf 0x200 of the battler 0x13813f4(o, rec[0]) holds, run 0x157fbc0 and
    0x183f12c (rec[1], rec + 8) on it and set *done = 1."""
    m.put(done, 1, 0)
    b = m.call(m.main + 0x13813F4, o, m.u32(rec))
    if m.vcall(b, 0x200) & 1:
        return
    m.call_void(m.main + 0x157FBC0, m.call(m.main + 0x1143584, o), b, m.u32(rec + 4))
    m.call_void(m.main + 0x183F12C, m.call(m.main + 0x1143584, o), b, m.u32(rec + 4), rec + 8)
    m.put(done, 1, 1)


@lifted(0x171A4EC)
def count_171a4ec(m, o, *_):
    """Over the members 0x1147754 walks (0x114e480(o), 0x1482534(o)): how many pass 0x1142e68 and then
    0x171a59c."""
    n = 0
    with m.frame(0x40) as p:
        it, out = p, p + 0x38
        m.call_void(m.main + 0x1147754, it, m.call(m.main + 0x114E480, o), m.call(m.main + 0x1482534, o))
        while m.call(m.main + 0x1360DBC, it, out) & 1:
            a = m.call(m.main + 0x114E480, o)
            b = m.call(m.main + 0x1482534, o)
            if m.call(m.main + 0x1142E68, a, b, m.u64(out)) & 1:
                n += m.call(m.main + 0x171A59C, o, m.u64(out)) & 1
    return n & 0xFFFFFFFF


@lifted(0x286F330)
def post_82010c(m, o, ident, *_):
    """When the u32 +0xc of [[[o+0x38]+0x78]+0x20] (0 when null) is ident: 0x1807920 with the record
    {0, 0, 0x82010c, ident, zeros}."""
    x = m.u64(m.u64(m.u64(o + 0x38) + 0x78) + 0x20)
    if (m.u32(x + 0xC) if x else 0) != ident & 0xFFFFFFFF:
        return o
    with m.frame(0x30) as p:
        m.write(p, bytes(0x30))
        m.put(p + 8, 4, 0x82010C); m.put(p + 0xC, 4, ident)
        return m.call(m.main + 0x1807920, o, p)


@lifted(0x149FDF4)
def check_149fdf4(m, o, b, *_):
    """When 0x1589a40(o, b's vf 0x98) equals the byte +0x95 of [o+8]: tail-call 0x149fe94([o+8], b,
    (b's vf 0x118 & 0xff) + 0x1e <= 0x149fedc(o), signed)."""
    v = m.call(m.main + 0x1589A40, o, m.vcall(b, 0x98) & 0xFFFFFFFF)
    w = m.call(m.main + 0x149FE8C, m.u64(o + 8))
    if v & 0xFFFFFFFF != w & 0xFF:
        return w
    x = (m.vcall(b, 0x118) & 0xFF) + 0x1E
    y = m.call(m.main + 0x149FEDC, o) & 0xFFFFFFFF
    y = y - (1 << 32) if y & 0x80000000 else y
    return _tail(m, m.main + 0x149FE94, m.u64(o + 8), b, int(x <= y))


@lifted(0x147AC54)
def refresh_147ac54(m, o, ident, *_):
    """vf 0x5e8 on the party member `ident` (0xf21c94 on [[o+0x10]+0x30]), clear ident from the list
    [[o+0x10]+0xf0] (0x147acc4), then tail-call 0x114eb70(o, member) when it still exists."""
    from pokeldn.sv.battle.machine import FUNCTIONS
    if 0x114EB70 not in FUNCTIONS:
        raise UnliftedCall("main+0x114eb70")
    ident &= 0xFFFFFFFF
    m.vcall_void(m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), ident), 0x5E8)
    m.call_void(m.main + 0x147ACC4, m.u64(m.u64(o + 0x10) + 0xF0), ident)
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), ident)
    if b == 0:
        return 0
    return _tail(m, m.main + 0x114EB70, o, b)


@lifted(0x287F878)
def notify_287f878(m, o, ident, *_):
    """Event 6 when 0x1589a40(o, ident) (x1 passes through) is the byte +0x95 of [o+8], else event 7
    unless 0x1142ecc allows it: vf 0x48(event, 1) on the counted handle 0x1142424([o+8]) gives,
    released after."""
    v = m.call(m.main + 0x1589A40, o, ident)
    w = m.call(m.main + 0x149FE8C, m.u64(o + 8))
    if w & 0xFF == v & 0xFF:
        event = 6
    else:
        r = m.call(m.main + 0x1142ECC, m.call(m.main + 0x13813EC, m.u64(o + 0x10)), v & 0xFFFFFFFF,
                   w & 0xFFFFFFFF)
        if r & 1:
            return r
        event = 7
    with m.frame(0x10) as p:
        m.call_sret(m.main + 0x1142424, p, m.u64(o + 8))
        ref = m.u64(p)
    m.vcall_void(ref, 0x48, event, 1)
    if ref == 0:
        return 0
    c = m.u32(ref + 0x28)
    m.put(ref + 0x28, 4, c - 1)
    if c == 1:
        return _vtail(m, ref, 0x10)
    if c == 0:
        raise UnliftedCall("DecrementReference abort: count underflow")
    return ref


@lifted(0x87C6F4)
def static_87c6f4(m, *_):
    """Thunk (this - 0x28) tail-calling 0x87c3c0, a function-local static: [0x46d3ab0], read only once
    its guard [0x46d3aa8] is set."""
    if m.u8(m.u64(m.main + 0x46D3AA8)) & 1 == 0:
        raise UnliftedCall("static 0x46d3ab0 not built")
    return m.u64(m.main + 0x46D3AB0)


def _construct_keyed(m, o, key, mid, vt_got):
    """0x132f598 / 0x132f6e8: the counted base, an intermediate vtable, then the final one ([vt_got]
    +0x10, +0x90, +0xe0), +0x40 the u64 and +0x48 the u32 of key, +0x50 = 0."""
    r = _construct_counted_base(m, o)
    m.put(o, 8, mid[0]); m.put(o + 0x20, 8, mid[1]); m.put(o + 0x28, 8, mid[2])
    vt = m.u64(m.main + vt_got)
    x, w = m.u64(key), m.u32(key + 8)
    m.put(o, 8, vt + 0x10); m.put(o + 0x40, 8, x); m.put(o + 0x20, 8, vt + 0x90)
    m.put(o + 0x48, 4, w); m.put(o + 0x28, 8, vt + 0xE0); m.put(o + 0x50, 8, 0)
    return r


@lifted(0x132F598)
def construct_132f598(m, o, key, *_):
    vt = m.main + 0x44ED578
    return _construct_keyed(m, o, key, (vt, vt + 0x78, vt + 0xC8), 0x46E2558)


@lifted(0x132F6E8)
def construct_132f6e8(m, o, key, *_):
    vt = m.u64(m.main + 0x46E2560)
    return _construct_keyed(m, o, key, (vt + 0x10, vt + 0x88, vt + 0xD8), 0x46E2568)


def _dealloc(m, alloc, block, size, align):
    """Give a block back to an allocator: 0xb48fe8 when vf 0xf8 defers frees and the thread block's
    +0x12c8 is positive, else vf 0x18. Returns the callee's result."""
    if m.vcall(alloc, 0xF8) & 1 and m.s(m.call(m.main + 0xB4E600) + 0x12C8, 4) >= 1:
        return _tail(m, m.main + 0xB48FE8, alloc, block, size, align)
    return _vtail(m, alloc, 0x18, block, size, align)


@lifted(0x16B070C)
def destroy_deque_16b070c(m, d, *_):
    """Deque destructor: clear it (0x16b08e8), free each 0x1000-byte block of the map [d+8, d+0x10)
    to [d+0x50], empty the map and free its storage [d] (capacity [d+0x18]) to [d+0x20] (0x16b0828,
    a tail call)."""
    m.call_void(m.main + 0x16B08E8, d)
    p, end = m.u64(d + 8), m.u64(d + 0x10)
    while p != end:
        alloc = m.u64(d + 0x50)
        _dealloc(m, alloc, m.u64(p), 0x1000, 8)
        p += 8
    begin, end = m.u64(d + 8), m.u64(d + 0x10)
    if end != begin:
        m.put(d + 0x10, 8, begin)
    store = m.u64(d)
    if store == 0:
        return d
    return _dealloc(m, m.u64(d + 0x20), store, (m.u64(d + 0x18) - store) & 0xFFFFFFFFFFFFFFFF, 8)


def _state(m, o):
    return m.call(m.main + 0x11409B4, m.call(m.main + 0x1482534, o))


@lifted(0x2886460)
def clear_kind3(m, o, *_):
    """Unless 0x288651c holds on the state: 0x156616c(3, 0) and queue command 0xc1 (3, 0)."""
    r = m.call(m.main + 0x288651C, _state(m, o))
    if r & 1:
        return r
    m.call_void(m.main + 0x156616C, m.call(m.main + 0x1143584, o), 3, 0)
    return _tail(m, m.main + 0x114DC24, m.call(m.main + 0x1143584, o), 3, 0)


@lifted(0x1150E28)
def clear_kind2(m, o, n, *_):
    """When the state's +0x70 is 1: 0x156616c(2, n) and command 0xc1 (2, n); for n = 0, when
    0x126b004 of 0x114e480(o) holds and the state's u16 +0x26 is set, 0x287f844(o, -that) (inlined:
    0x288d228 on [o+0x20], then command 0x81 with the value sign-extended)."""
    n &= 0xFFFFFFFF
    r = m.call(m.main + 0x1150ED0, _state(m, o))
    if r & 1 == 0:
        return r
    m.call_void(m.main + 0x156616C, m.call(m.main + 0x1143584, o), 2, n)
    r = _tail(m, m.main + 0x114DC24, m.call(m.main + 0x1143584, o), 2, n)
    if n:
        return r
    r = m.call(m.main + 0x126B004, m.call(m.main + 0x114E480, o))
    if r & 0xFFFFFFFF == 0:
        return r
    st = _state(m, o)
    if m.u16(st + 0x26) == 0:
        return st
    v = (-m.u16(_state(m, o) + 0x26)) & 0xFFFFFFFF
    q = m.call(m.main + 0x1143584, o)
    m.call_void(m.main + 0x288D228, m.u64(q + 0x20), v)
    s16 = v & 0xFFFF
    return _tail(m, m.main + 0x119AFF0, m.u64(q + 0x18), 0x81, (s16 - 0x10000 if s16 & 0x8000 else s16) & 0xFFFFFFFF)


def _send_record(m, o, rec):
    """The common end of 0x1820d90 / 0x2886524 / 0x28865cc: a serial from 0x1820e44(0x1482534(o)) into
    rec+0x54 (0x1820e4c), then 0x1820eb8(0x1149340(o), rec), whose result it returns."""
    m.call_void(m.main + 0x1820E4C, m.call(m.main + 0x1820E44, m.call(m.main + 0x1482534, o)), rec + 0x54)
    return m.call(m.main + 0x1820EB8, m.call(m.main + 0x1149340, o), rec)


def _new_record(m, rec):
    m.call_void(m.main + 0x1146154, rec + 0x60)
    m.call_void(m.main + 0x1820E80, rec)


def _member_id(m, o):
    return m.vcall(m.call(m.main + 0x1142508, o), 0x98) & 0xFFFFFFFF


def _record_1820d90(m, o):
    """0x1820d90 (reached only as a tail call): record 0xd {member, 0x34: 5, 0x38: 2, 0x30: 3,
    0x3c: member}."""
    with m.frame(0xA0) as rec:
        _new_record(m, rec)
        m.put(rec + 0x34, 4, 5); m.put(rec + 0x38, 1, 2); m.put(rec + 4, 4, 0xD)
        m.put(rec + 0x3C, 4, 0); m.put(rec + 0x30, 2, 3)
        m.put(rec + 0x3C, 4, _member_id(m, o))
        m.put(rec, 4, _member_id(m, o))
        return _send_record(m, o, rec)


def _record_2886524(m, o):
    """0x2886524 (reached only as a tail call): record 0xd {member, 0x34: 5, 0x38: 0, 0x30: 0x3c}."""
    with m.frame(0xA0) as rec:
        _new_record(m, rec)
        m.put(rec + 0x34, 4, 5); m.put(rec + 0x38, 1, 2); m.put(rec + 0x30, 2, 0)
        m.put(rec + 0x3C, 4, 0); m.put(rec + 4, 4, 0xD)
        m.put(rec, 4, _member_id(m, o))
        m.put(rec + 0x38, 1, 0)
        m.put(rec + 0x30, 2, m.u16(rec + 0x30) | 0x3C)
        return _send_record(m, o, rec)


def _record_28865cc(m, o, v):
    """0x28865cc (reached only as a tail call): the byte 0x2842270 answers for {member, v}, then
    record 1 {member, +8 that byte, +0x10 v, +0x28 9, +0x88 0x1589a40(o, member)}."""
    v &= 0xFFFF
    mem = m.call(m.main + 0x1142508, o)
    with m.frame(0xA0) as rec:
        out = rec + 0x90
        m.put(rec, 4, 0); m.put(rec + 4, 2, 0)
        m.put(rec, 4, m.vcall(mem, 0x98))
        m.put(rec + 4, 2, v)
        t = m.call(m.main + 0x2842268, m.call(m.main + 0x1361214, o))
        m.call_void(m.main + 0x2842270, t, out, rec)
        b = m.u8(out)
        _new_record(m, rec)
        m.put(rec + 4, 4, 1); m.put(rec + 0x10, 2, v); m.put(rec + 8, 1, b)
        m.put(rec, 4, m.vcall(mem, 0x98))
        w = m.vcall(mem, 0x98) & 0xFFFFFFFF
        m.put(rec + 0x88, 1, m.call(m.main + 0x1589A40, o, w))
        m.put(rec + 0x28, 1, 9); m.put(rec + 0x89, 2, 0)
        return _send_record(m, o, rec)


@lifted(0x1151878)
def clear_kind4(m, o, k, *_):
    """For slot k (<= 5) whose 0x1151988 holds and whose state entry (+0x30 + 8k) has u16 +0 and +2
    set: 0x156616c(4, k), command 0xc1 (4, u16 +0), then by that u16 (jump table 0x3c6a55e) the tail
    call 0x1820d90(o), 0x2886524(o), 0x28865cc(o, u16 +6) or 0x28866d0(o). Kinds 3 and 4 refuse
    before any write while 0x10e21c0 / 0x28866d0 are not lifted."""
    from pokeldn.sv.battle.machine import FUNCTIONS
    sk = (k & 0xFFFFFFFF) - (1 << 32) if k & 0x80000000 else k & 0xFFFFFFFF
    r = m.call(m.main + 0x1151988, _state(m, o), k & 0xFFFFFFFF)
    if sk > 5 or r & 1 == 0:
        return r
    st = _state(m, o)
    e = (st + 8 * sk) & 0xFFFFFFFFFFFFFFFF
    if m.u16(e + 0x30) == 0 or m.u16(e + 0x32) == 0:
        return st
    for kind, need in ((3, 0x10E21C0), (4, 0x28866D0)):      # 0x10e21c0: 0x2842270's tail call
        if m.u16(e + 0x30) == kind and need not in FUNCTIONS:
            raise UnliftedCall(f"main+0x{need:x}")
    m.call_void(m.main + 0x156616C, m.call(m.main + 0x1143584, o), 4, k & 0xFFFFFFFF)
    r = _tail(m, m.main + 0x114DC24, m.call(m.main + 0x1143584, o), 4, m.u16(e + 0x30))
    kind = m.u16(e + 0x30)
    if kind == 1:
        return _record_1820d90(m, o)
    if kind == 2:
        return _record_2886524(m, o)
    if kind == 3:
        return _record_28865cc(m, o, m.u16(e + 0x36))
    if kind == 4:
        return _tail(m, m.main + 0x28866D0, o)
    return r


# 0x1148e44 (a tail call, inlined): record kind 1..5 -> its handler; kinds 1, 2, 4 take the u32 +4.
_RECORD_KINDS = {1: (0x114DBBC, True), 2: (0x1150E28, True), 3: (0x2886460, False),
                 4: (0x1151878, True), 5: (0x28864BC, False)}


@lifted(0x11424B8)
def clear_record(m, o, x1, rec, *_):
    """When 0x114d34c holds on the state and 0x1142508(o) gives a member: the handler of the record's
    kind byte (0x1148e44's jump table at 0x3c6a559)."""
    r = m.call(m.main + 0x114D34C, _state(m, o))
    if r & 1 == 0:
        return r
    r = m.call(m.main + 0x1142508, o)
    if r == 0:
        return 0
    kind = m.u8(rec)
    if kind not in _RECORD_KINDS:
        return o
    fn, word = _RECORD_KINDS[kind]
    if word:
        return _tail(m, m.main + fn, o, m.u32(rec + 4))
    return _tail(m, m.main + fn, o, rec)


@lifted(0x183F070)
def apply_183f070(m, o, rec, *_):
    """0x183f0ac on [[o+0x28]+0xf80] with a local done flag, which it returns."""
    with m.frame(0x10) as p:
        m.call_void(m.main + 0x183F0AC, m.u64(m.u64(o + 0x28) + 0xF80), p, rec)
        return m.u8(p)


@lifted(0x17E5E44)
def push_back12(m, v, src, *_):
    """Vector of 12-byte entries (data +0x20, size +0x28, capacity +0x30): append src (0x17e5ebc in
    place, 0x2014a90 when full)."""
    n = m.u64(v + 0x28)
    if n < m.u64(v + 0x30):
        r = m.call(m.main + 0x17E5EBC, v, m.u64(v + 0x20) + 12 * n, src)
        m.put(v + 0x28, 8, m.u64(v + 0x28) + 1)
        return r
    with m.frame(0x20) as p:
        m.put(p + 0x10, 8, m.u64(v + 0x20) + 12 * n)
        return m.call_sret(m.main + 0x2014A90, p, v, p + 0x10, src)


def _hash_find_u32(m, table, key):
    """The node of key in an unordered map of u32 keys (buckets [table], count [table+8]; node: next,
    hash +8, key +0x10), or 0."""
    n = m.u64(table + 8)
    if n == 0:
        return 0
    pc = bin(n).count("1")
    b = _bucket(key, n, pc)
    x = m.u64(m.u64(table) + 8 * b)
    x = m.u64(x) if x else 0
    while x:
        h = m.u64(x + 8)
        if h == key:
            if m.u32(x + 0x10) == key:
                return x
        elif _bucket(h, n, pc) != b:
            return 0
        x = m.u64(x)
    return 0


@lifted(0xFA6A44)
def counted_by_key(m, o, key, *_):
    """Writes to x8 the counted pointer (count +0x28 raised) the map at o+0x30 holds for u32 key
    (0xfa6bbc), or 0."""
    out = m.x8
    key &= 0xFFFFFFFF
    if m.u64(o + 0x38) == 0:
        m.put(out, 8, 0)
        return o
    if _hash_find_u32(m, o + 0x30, key) == 0:
        m.put(out, 8, 0)
        return o + 0x30
    with m.frame(0x10) as k:
        m.put(k, 4, key)
        e = m.call(m.main + 0xFA6BBC, o + 0x30, k)
    p = m.u64(e)
    m.put(out, 8, p)
    if p:
        c = m.u32(p + 0x28)
        if c == 0xFFFFFFFF:
            raise UnliftedCall("IncrementReference abort: count overflow")
        m.put(p + 0x28, 4, c + 1)
    return e


def _handle_table(m):
    """The handle table static [[0x46d3910]] (also stored to [[0x46d3918]]), refused while its guard
    [0x46d3908] is clear."""
    if m.u8(m.u64(m.main + 0x46D3908)) & 1 == 0:
        raise UnliftedCall("static at [0x46d3910] not built")
    t = m.u64(m.u64(m.main + 0x46D3910))
    m.put(m.u64(m.main + 0x46D3918), 8, t)
    return t


def _release_weak(m, e):
    """ReleaseWeakReference on a handle-table entry: lower its u16 count (+0x18); the last one marks
    +0x1c = -1 and frees the handle [e] (0xb44438), whose result it returns."""
    c = m.u16(e + 0x18)
    m.put(e + 0x18, 2, c - 1)
    if c == 0:
        raise UnliftedCall("ReleaseWeakReference abort: count underflow")
    if c != 1:
        return None
    old = m.u32(e + 0x1C)
    m.put(e + 0x1C, 4, 0xFFFFFFFF)
    if old == 0xFFFFFFFF:
        return None
    t = _handle_table(m)
    with m.frame(0x10) as p:
        m.put(p, 8, m.u64(e))
        return m.call(m.main + 0xB44438, t + 0x8040, p)


@lifted(0x168DF18)
def move_weak(m, dst, src, *_):
    """Move-assign a weak reference {entry, handle}: the handle (src+8) is looked up again in the table
    (0xb44204); src's entry and dst's old one are released; a stale handle resets dst (0x169222c)."""
    if m.u8(m.u64(m.main + 0x46D3908)) & 1 == 0:
        raise UnliftedCall("static at [0x46d3910] not built")
    h = m.u64(src + 8)
    m.put(src + 8, 8, 0)
    t = _handle_table(m)
    with m.frame(0x10) as p:
        r = m.call_sret(m.main + 0xB44204, p, t, h)
        ent = m.u64(p)
    old = m.u64(src)
    m.put(src, 8, 0)
    if old:
        x = _release_weak(m, old)
        r = r if x is None else x
    if ent == 0:
        return _tail(m, m.main + 0x169222C, dst)
    prev = m.u64(dst)
    m.put(dst, 8, 0)
    if prev:
        x = _release_weak(m, prev)
        r = r if x is None else x
    m.put(dst, 8, ent); m.put(dst + 8, 8, h)
    return r


@lifted(0x169222C)
def reset_weak(m, w, *_):
    """Reset a weak reference {entry, handle}: release the entry (_release_weak), zero both."""
    e = m.u64(w)
    m.put(w, 8, 0)
    r = _release_weak(m, e) if e else None
    m.put(w + 8, 8, 0)
    return w if r is None else r


def _copy_weak(m, dst, src):
    """0xb43ef0 (reached here by falling through): dst = a fresh weak reference to src's handle,
    looked up again in the table (0xb44204); dst's old entry is released; a stale handle leaves dst
    {0, 0}. Returns the last callee's result."""
    if m.u8(m.u64(m.main + 0x46D3908)) & 1 == 0:
        raise UnliftedCall("static at [0x46d3910] not built")
    h = m.u64(src + 8)
    t = _handle_table(m)
    with m.frame(0x10) as p:
        r = m.call_sret(m.main + 0xB44204, p, t, h)
        ent = m.u64(p)
    old = m.u64(dst)
    m.put(dst, 8, 0)
    if old:
        x = _release_weak(m, old)
        r = r if x is None else x
    if ent == 0:
        h = 0
    else:
        m.put(dst, 8, ent)
    m.put(dst + 8, 8, h)
    return r


@lifted(0xB43EE0)
def weak_of_30(m, o, *_):
    """Writes to x8 a weak reference copied from o+0x30 (0xb43ef0)."""
    out = m.x8
    m.put(out, 8, 0); m.put(out + 8, 8, 0)
    return _copy_weak(m, out, o + 0x30)


@lifted(0x127D824)
def reset_127d824(m, o, cfg, *_):
    """Reset the state's tables for a new round from cfg: +0x36c / +0x370 from cfg +0x10 / +0x14, each
    sub-table's reset (0x127e8b4, 0x127deec, 0x127ddc8, 0x127dcb8, 0x127eb14, 0x127dcfc, 0x127e2b8,
    0x127e548, 0x127e6e8, 0x127e0c8) or clear, the maps at [+0x2b0] / [+0x2f0] emptied (0x20 / 0x28
    byte nodes), 0x4a bytes copied into [+0x310]+0x1c, the seed 0x82a2b175229d6a5b at [+0x10]+0x10.
    Returns memcpy's result."""
    from pokeldn.sv.battle.machine import FUNCTIONS
    for a in (0x127E8B4, 0x127DEEC, 0x127DDC8, 0x127DCB8, 0x127EB14, 0x127DCFC, 0x127E2B8, 0xF785A8,
              0x127E548, 0x127E6E8, 0x127E0C8):     # 0xf785a8: 0x127e2b8's map insert
        if a not in FUNCTIONS:
            raise UnliftedCall(f"main+0x{a:x}")
    m.put(o + 0x36C, 4, m.u32(cfg + 0x10)); m.put(o + 0x370, 1, m.u8(cfg + 0x14))
    m.call_void(m.main + 0x127E8B4, m.u64(o + 0xD0))
    m.call_void(m.main + 0x127DEEC, m.u64(o + 0x30))
    m.call_void(m.main + 0x127DDC8, m.u64(o + 0x50))
    m.call_void(m.main + 0x127DCB8, m.u64(o + 0x70))
    m.call_void(m.main + 0x127EB14, m.u64(o + 0x90))
    m.call_void(m.main + 0x127DCFC, m.u64(o + 0xB0))
    m.call_void(m.main + 0x127E2B8, m.u64(o + 0xF0), o)
    m.call_void(m.main + 0x127E548, m.u64(o + 0x110))
    m.write(m.u64(o + 0x130) + 8, bytes(0x12C4))
    x = m.u64(o + 0x150); m.put(x + 8, 8, 0); m.put(x + 0x10, 4, 0)
    m.call_void(m.main + 0x127E6E8, m.u64(o + 0x170))
    m.put(m.u64(o + 0x190) + 8, 4, 0)
    x = m.u64(o + 0x1B0); m.put(x + 0x10, 4, 0); m.put(x + 8, 8, 0)
    x = m.u64(o + 0x1D0); m.put(x + 0x48, 1, 0); m.put(x + 0x18, 8, 0)
    m.put(m.u64(o + 0x1F0) + 8, 1, 0)
    m.write(m.u64(o + 0x210) + 8, bytes(0xD8))
    x = m.u64(o + 0x230)
    m.put(x + 8, 8, 0x0505050500000000); m.put(x + 0x10, 1, 5); m.put(x + 0x13, 1, 0); m.put(x + 0x11, 2, 0)
    m.call_void(m.main + 0x127E0C8, m.u64(o + 0x250))
    m.put(m.u64(o + 0x270) + 8, 8, 0)
    for off, node in ((0x2B0, 0x20), (0x2F0, 0x28)):
        x = m.u64(o + off)
        if m.u64(x + 0x60):
            _map_free_all(m, x, node)
    x = m.u64(o + 0x310)
    m.write(x + 0x1C, m.read(m.u64(m.u64(x + 8) + 0x38) + 0x514, 0x4A))
    m.write(x + 0x68, bytes(0x28))
    x = m.u64(o + 0x330)
    m.put(x + 0x10, 8, m.u64(m.u64(x) + 0x38) + 0x5B8)
    m.put(o + 0x35D, 8, 0); m.put(o + 0x358, 8, 0); m.put(o + 0x350, 8, 0); m.put(o + 0x368, 4, 0)
    x = m.u64(o + 0x10); v = m.u64(cfg + 0x20)
    m.put(x + 0x18, 8, v); m.put(x + 0x20, 8, 0); m.put(x + 8, 8, v); m.put(x + 0x10, 8, 0x82A2B175229D6A5B)
    m.put(m.u64(o + 8) + 0x30, 8, m.u64(cfg + 8))
    return (m.u64(o + 0x310) + 0x1C) & 0xFFFFFFFFFFFFFFFF


@lifted(0x1589E60)
def make_key_scoped(m, o, dst, src, *_):
    """With [o] pushed on the thread's object stack (slot from 0xf53840): dst = {u32 **src, byte 0}.
    Returns the stack (0 when the thread has none)."""
    top = m.u64(o)
    t = m.call(m.main + 0x343DA20, m.u32(m.call(m.main + 0xF53840)))
    if t:
        n = m.u64(t + 0x80)
        if n >= 0x10:
            raise UnliftedCall("abort: object stack full")
        m.put(t + 8 * n, 8, top)
        m.put(t + 0x80, 8, n + 1)
    m.put(dst, 4, m.u32(m.u64(src))); m.put(dst + 4, 1, 0)
    if t:
        m.put(t + 0x80, 8, m.u64(t + 0x80) - 1)
    return t


def _locked(m, acc, fn, *args):
    """Run 0x<fn>(acc, *args) holding the record accessor's lock (owner +0x20, light event +0x28)."""
    cur = m.call(m.main + 0x343C290)
    if m.u64(acc + 0x20):
        raise UnliftedCall("record accessor held by another thread")
    m.put(acc + 0x20, 8, cur)
    m.call_void(m.main + fn, acc, *args)
    m.put(acc + 0x20, 8, 0)
    m.call_void(m.main + 0x343E5E0, acc + 0x28)


@lifted(0xEEEA48)
def copy_core_record(m, pp, src, *_):
    """Copy src's core record into pp's: read it out of [src+0x70] (0xe32a60) and write it into
    [pp+0x70] (0xe14ea8), each under the accessor's lock, then recompute the stats (0xe13b9c(pp, 1))
    and tail-call 0xe14018(pp)."""
    with m.frame(0x160) as buf:
        _locked(m, m.u64(src + 0x70), 0xE32A60, buf, buf + 0x148)
        _locked(m, m.u64(pp + 0x70), 0xE14EA8, buf, buf + 0x148)
    m.call_void(m.main + 0xE13B9C, pp, 1)
    return _tail(m, m.main + 0xE14018, pp)


def _store_and_command_75(m, q, a, b):
    """0x11494a4 (reached only as a tail call): 0x11494e8([q+0x20], a, b) stores b in slot a, then
    command 0x75 (a & 0xff, b) on [q+0x18]."""
    a &= 0xFFFFFFFF; b &= 0xFFFFFFFF
    m.call_void(m.main + 0x11494E8, m.u64(q + 0x20), a, b)
    return _tail(m, m.main + 0x119AFF0, m.u64(q + 0x18), 0x75, a & 0xFF, b)


@lifted(0x1149124)
def count_open_1149124(m, o, flag, *_):
    """*flag = 1; for each entry i of the list 0x1149340(o) (count 0x1149348): 0x1149414(id, 7) and count
    those 0x11493a0 rejects; when any: the next value 0x1149380(.., 3) + 1, 0 (and *flag = 0) when it
    reaches 0x1149478, stored and announced (0x11494a4, inlined) for slot 3."""
    m.put(flag, 1, 1)
    lst = m.call(m.main + 0x1149340, o)
    r = m.call(m.main + 0x1149348, lst)
    if r & 0xFF == 0:
        return r
    cnt = 0
    i = 0
    while True:
        e = m.call(m.main + 0x1149354, lst, i)
        if e:
            m.call_void(m.main + 0x1149414, m.call(m.main + 0x1143584, o), m.u32(e), 7)
            cnt += ~m.call(m.main + 0x11493A0, m.call(m.main + 0x1482534, o), m.u32(e)) & 1
        i += 1
        r = m.call(m.main + 0x1149348, lst)
        if i >= r & 0xFF:
            break
    if cnt == 0:
        return r
    v = (m.call(m.main + 0x1149380, m.call(m.main + 0x1149378, m.call(m.main + 0x1482534, o)), 3) + 1) \
        & 0xFFFFFFFFFFFFFFFF
    lim = m.call(m.main + 0x1149478, m.call(m.main + 0x1482534, o)) & 0xFFFFFFFF
    lim = (lim - (1 << 32) if lim & 0x80000000 else lim) & 0xFFFFFFFFFFFFFFFF
    if v >= lim:
        v = 0
        m.put(flag, 1, 0)
    return _store_and_command_75(m, m.call(m.main + 0x1143584, o), 3, v)


def _add_handler_284dc00(m, q, a, ident, src):
    """0x284dc00 (reached only as a tail call): unless q already holds a kind-2 handler for ident
    (0x284db90), build one with the maker 0x284dcd0 gives (it fills a local u32), push it (0x114ed80:
    kind 2, ident, 3, 0, a & 0xff, the made value, the local) and set its fields 8 and 7 from
    0x174ae90(src) (0x284d154)."""
    r = m.call(m.main + 0x284DB90, q, a, ident)
    if r:
        return r
    f = m.call(m.main + 0x284DCD0, ident & 0xFFFFFFFF)
    if f == 0:
        return 0
    with m.frame(0x20) as p:
        local, x, y = p + 0x10, p + 8, p + 4
        v = m.call(f, local)
        if v == 0:
            return 0
        e = m.call(m.main + 0x114ED80, q, 2, ident & 0xFFFFFFFF, 3, 0, a & 0xFF, v, m.u32(local))
        if e == 0:
            return 0
        m.put(x, 4, 0); m.put(p, 8, 0)
        m.call_void(m.main + 0x174AE90, src, x, y, p)
        m.call_void(m.main + 0x284D154, e, 8, m.u32(x))
        return _tail(m, m.main + 0x284D154, e, 7, m.u32(y))


@lifted(0x288D114)
def add_handler_288d114(m, o, a, ident, src, *_):
    return _add_handler_284dc00(m, m.u64(o + 0x18), a, ident, src)


def _assign_strong_16f6dcc(m, slot, p):
    """0x16f6dcc (reached only as a tail call): slot = p, a counted reference (control block +0x30:
    object +0x10, count u16 +0x1a; the first reference builds the object with its vf 0, kept at +8,
    +0x1c = -2); the old one's last reference clears +0x10 and tail-calls its vf 0x50."""
    if p:
        cb = m.u64(p + 0x30)
        if m.u64(cb + 0x10) == 0 or m.u16(cb + 0x1A) == 0xFFFF:
            raise UnliftedCall("abort in AddReference")
        n = m.u16(cb + 0x1A)
        m.put(cb + 0x1A, 2, n + 1)
        if n == 0:
            m.put(cb + 8, 8, m.vcall(m.u64(cb + 0x10), 0))
            m.put(cb + 0x1C, 4, 0xFFFFFFFE)
    old = m.u64(slot)
    m.put(slot, 8, p)
    if old == 0:
        return 0
    cb = m.u64(old + 0x30)
    c = m.u16(cb + 0x1A)
    m.put(cb + 0x1A, 2, c - 1)
    if c == 1:
        m.put(cb + 0x10, 8, 0)
        return _vtail(m, old, 0x50)
    if c == 0:
        raise UnliftedCall("ReleaseReference abort: count underflow")
    return old


@lifted(0x2891404)
def assign_2e0(m, o, pp, *_):
    return _assign_strong_16f6dcc(m, o + 0x2E0, m.u64(pp))
