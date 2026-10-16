"""The commands the server writes into the round's queue: the target summary rows (0x7e), the action
summary (0x8b), the effect record (0xc9), the totals (0x9c), and the message and text commands each
step queues."""

from pokeldn.sv.battle.engine.calls import M32, _need, _tail
from pokeldn.sv.battle.engine.members import _unique_ids
from pokeldn.sv.battle.engine.queue import push, write_at
from pokeldn.sv.battle.machine import UnliftedCall, lifted

# Byte offsets in the summary record of the three target rows' five bytes each (0x15799f0).
_ROW_BYTES = ((0xD, 0x10, 0x13, 0x16, 0x19), (0xE, 0x11, 0x14, 0x17, 0x1A), (0xF, 0x12, 0x15, 0x18, 0x1B))


@lifted(0x1579490)
def queue_length(m, que, *_): return m.u32(que + 0x68)


@lifted(0x15799F0)
def push_target_row(m, que, info, row, *_):
    row &= 0xFF
    if row > 2:
        return
    push(m, que, 0x7E, row, *(m.u8(info + o) for o in _ROW_BYTES[row]))


@lifted(0x1942118)
def push_effect(m, o, a, b, c, d, *_):
    push(m, m.u64(o + 0x18), 0xC9, a, 0, b & 0xFFFF, c & 0xFF, d & 1)


@lifted(0x157FE4C)
def write_totals(m, o, info, pos, *_):
    write_at(m, m.u64(o + 0x18), pos, 0x9C, *(m.u32(info + 0x30 + 4 * i) for i in range(6)))


@lifted(0x1579498)
def write_summary(m, o, base, info, slots, *_):
    """The action's summary: totals (0x9c) when any, the three target rows (0x7e) and the line 0x8b, into
    the positions reserved in `slots` (u16 at +2.. ; 0xffff at +2 means append instead)."""
    que = m.u64(o + 0x18)
    if m.u32(info + 0x30) != 0:
        write_totals(m, o, info, m.u16(slots))
    move = m.u16(info) or m.u16(base)
    args = (m.u8(info + 2), m.u8(info + 3), move, m.u8(base + 8), m.u8(info + 4), m.u8(info + 6),
            m.u8(info + 0xC), m.u8(info + 7), m.u8(base + 0xA), m.u8(info + 5))
    if m.u16(slots + 2) != 0xFFFF:
        for row in range(3):
            write_at(m, que, m.u16(slots + 4 + 2 * row), 0x7E, row,
                     *(m.u8(info + o) for o in _ROW_BYTES[row]))
        write_at(m, que, m.u16(slots + 2), 0x8B, *args)
        return
    for row in range(3):
        push_target_row(m, que, info, row)
    push(m, que, 0x8B, *args)


@lifted(0x1941FB4)
def close_effect(m, o, rec, info, *_):
    """Close an effect record: note where the queue stands, find whether the queue holds a command in
    0x88..0xcd between the record's start and info's end (the read cursor is restored), then write
    0xc9 at the reserved position or append it."""
    from pokeldn.sv.battle.engine.queue import read_command
    que = m.u64(o + 8)
    pos = m.u16(rec + 2)
    if pos == 0xFFFF:
        pos = queue_length(m, que) & 0xFFFF
    m.put(rec + 4, 2, pos)
    if m.u8(rec + 0xD):
        found = 1
    else:
        found = 0
        end = m.u16(info + 0xA)
        if pos != 0xFFFF and end != 0xFFFF:
            saved = m.u32(que + 0x6C)
            m.put(que + 0x6C, 4, pos)
            at = pos
            with m.frame(0x50) as out:
                while not (end <= at and at != m.u32(que + 0x68)):
                    m.put(out + 0x40, 4, 0xFFFFFFFF)
                    command = read_command(m, que, out, 0x10, out + 0x40)
                    where = m.u32(out + 0x40)
                    if (command - 0x88) & 0xFFFF < 0x46 and pos <= where < end:
                        found = 1
                        break
                    at = m.u32(que + 0x6C)
            m.put(que + 0x6C, 4, saved)
    if m.s(rec + 2, 2) == -1:
        push_effect(m, m.u64(o + 0x10), m.u32(rec + 8), m.u16(rec + 6), m.u8(rec + 0xC), found)
    else:
        write_at(m, m.u64(m.u64(o + 0x10) + 0x18), m.u16(rec + 2), 0xC9, m.u32(rec + 8), 0,
                 m.u16(rec + 6), m.u8(rec + 0xC), found)
    m.put(rec, 1, 1)


@lifted(0x174AE90)
def unpack_three(m, o, a, b, c, *_):
    m.put(a, 4, m.u32(o + 0xC)); m.put(b, 4, m.u64(o + 8)); m.put(c, 4, m.u32(o))


@lifted(0x2843244)
def set_head(m, o, low, value, *_):
    """Store a u16 at +0 and the low 7 bits of the u16 at +2 (bits 14 and 15 kept, the count cleared)."""
    m.put(o, 2, value)
    m.put(o + 2, 2, m.u16(o + 2) & 0xC000 | low & 0x7F)


@lifted(0x284325C)
def push_u32(m, o, value, *_):
    """Append a u32 at +4 to a list of at most 8 whose count is bits 7..13 of the u16 at +2."""
    h = m.u16(o + 2)
    n = h >> 7 & 0x7F
    if n < 8:
        m.put(o + 2, 2, (h + 0x80) & 0x3F80 | h & 0xC07F)
        m.put(o + 4 + 4 * n, 4, value)


@lifted(0x288426C)
def queue_10(m, o, arg, *_):
    r = m.call(m.main + 0x288CE48, m.u64(o + 0x20), arg)
    m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0x10, arg & 0xFFFFFFFF)
    return r & 1


@lifted(0x1361AD8)
def queue_34(m, o, arg, *_):
    r = m.call(m.main + 0x288C730, m.u64(o + 0x20), arg)
    m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0x34, arg & 0xFF)
    return r & 1


@lifted(0x288D8C0)
def queue_32(m, q, arg, src, *_):
    """Queue command 0x32 with the three words 0x174ae90 unpacks from `src`."""
    m.call_void(m.main + 0x119AFF0, q, 0x32, arg & 0xFF, m.u32(src + 0xC), m.u32(src + 8), m.u32(src))


@lifted(0x1149414)
def set_550_queue_37(m, o, ident, v, *_):
    """vf 0x550 (v, 1) on battler `ident`, then queue command 0x37 (ident, v, 1)."""
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(m.u64(o + 0x20) + 0x10) + 0x30), ident)
    m.vcall_void(b, 0x550, v & 0xFFFFFFFF, 1)
    m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0x37, ident & 0xFFFFFFFF, v & 0xFF, 1)


@lifted(0x2886D20)
def queue_a7(m, o, pos, v, *_):
    """Queue command 0xa7 (pos, v u16) unless pos is 10 (none)."""
    if pos & 0xFF == 10:
        return
    m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0xA7, pos & 0xFFFFFFFF, v & 0xFFFF)


@lifted(0x13DBFD4)
def apply_and_queue_5b(m, o, ident, v, *_):
    """0x13dc030 on battler `ident` with v, then queue command 0x5b (ident, v)."""
    q = m.u64(o + 0x20)
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(q + 0x10) + 0x30), ident)
    m.call_void(m.main + 0x13DC030, m.u64(q + 0x18), b, v & 0xFFFFFFFF)
    m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0x5B, ident & 0xFFFFFFFF, v & 0xFFFFFFFF)


@lifted(0x114ADE8)
def queue_a7_for(m, o, b, v, *_):
    """Queue command 0xa7 (the battler's slot 0x1381420, v u16) unless it has no slot."""
    pos = m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), m.vcall(b, 0x98) & 0xFFFFFFFF)
    if pos & 0xFF == 10:
        return
    m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0xA7, pos & 0xFFFFFFFF, v & 0xFFFF)


@lifted(0x1360728)
def run_136075c_queue_62(m, o, ident, *_):
    m.call_void(m.main + 0x136075C, m.u64(o + 0x20), ident)
    m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0x62, ident & 0xFFFFFFFF)


@lifted(0x1155138)
def queue_c2(m, o, rec, *_):
    """Queue command 0xc2 (u16 rec+0x30, u32 rec+0, u8 rec+0x38) through 0x1155168."""
    q = m.call(m.main + 0x1143584, o, rec)
    m.call_void(m.main + 0x119AFF0, m.u64(q + 0x18), 0xC2, m.u16(rec + 0x30), m.u32(rec), m.u8(rec + 0x38))


@lifted(0x157EF30)
def queue_cb_49(m, q, ident, t, *_):
    """Queue command 0xcb (ident, 0x49, t's id) through the 0xffff0000-terminated push 0x157ebc0."""
    other = m.vcall(t, 0x98) & 0xFFFFFFFF
    return _tail(m, m.main + 0x157EBC0, m.u64(q + 0x18), 0xCB, ident & 0xFFFFFFFF, 0x49, other, 0xFFFF0000)


@lifted(0x1807920)
def run_114aab0(m, o, arg, *_):
    """0x114aab0(0x1807950([o+0x28]), a scratch u64, arg)."""
    p = m.call(m.main + 0x1807950, m.u64(o + 0x28))
    with m.frame(0x10) as f:
        return _tail(m, m.main + 0x114AAB0, p, f, arg)


@lifted(0x171A59C)
def note_kind_7(m, o, b, *_):
    """When 0x171a624(b, 7) gives a value: 0x171a604(queue, b's id (vf 0x98), 2, value) and 1."""
    r = m.call(m.main + 0x171A624, o, b, 7)
    if r & 0xFFFFFFFF == 0:
        return r
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    q = m.call(m.main + 0x1143584, o)
    m.call_void(m.main + 0x171A604, q, ident, 2, r & 0xFFFFFFFF)
    return 1


@lifted(0x183F12C)
def record_and_command_7d(m, o, b, a, pair, *_):
    """0x183f194([o+0x20], b's id (vf 0x98), a, pair), then the tail call of command 0x7d (0x119aff0) on
    [o+0x18] with (a & 0xff, id, pair[0], pair[1])."""
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    m.call_void(m.main + 0x183F194, m.u64(o + 0x20), ident, a & 0xFFFFFFFF, pair)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x7D, a & 0xFF, ident, m.u32(pair),
                 m.u32(pair + 4))


@lifted(0x28870EC)
def command_c0(m, o, a, b, *_):
    """The tail call of command 0xc0 (0x119aff0) on [o+0x18] with (a, b & 0xff)."""
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xC0, a & 0xFFFFFFFF, b & 0xFF)


@lifted(0x157FBC0)
def battler_4d8_command_1e(m, o, b, v, *_):
    """vf 0x4d8(v) on the main battler for b's id (0xf21c94), then the tail call of command 0x1e
    (0x119aff0) on [o+0x18] with (id, v)."""
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    t = m.call(m.main + 0xF21C94, m.u64(m.u64(m.u64(o + 0x20) + 0x10) + 0x30), ident)
    m.vcall_void(t, 0x4D8, v & 0xFFFFFFFF)
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x1E, ident, v & 0xFFFFFFFF)


@lifted(0x1361C58)
def message_by_kind(m, o, a, kind, *_):
    """The tail call of 0x287ee68([o+0x20], a, message) for the message `kind` 1..9 picks (jump table
    0x3c6a4f8): 1 0x267, 2 0x269, 4 0x2aa, 5 0x2ac, 8 by 0x13616dc's 1..4 (0x2c1, 0x2c3, 0x2c5, 0x33d),
    9 0x37a; the others send nothing."""
    k = (kind - 1) & 0xFFFFFFFF
    msg = {0: 0x267, 1: 0x269, 3: 0x2AA, 4: 0x2AC, 8: 0x37A}.get(k)
    if k == 7:
        r = m.call(m.main + 0x13616DC, m.u64(m.u64(o + 0x10) + 0x70))
        j = (r - 1) & 0xFF
        if j >= 4:
            return r
        msg = 0x033D02C502C302C1 >> (16 * j)
    if msg is None:
        return o
    return _tail(m, m.main + 0x287EE68, m.u64(o + 0x20), a & 0xFFFFFFFF, msg)


@lifted(0x288C240)
def note_kind(m, o, b, a, kind, *_):
    """Kinds 1, 0x11, 0x1a and 0x23 first record (b's id, a, 0x10a) in a fresh 0x139b698 entry through
    0x282410c; every kind goes to 0x1482e80; kinds 2, 3 and 4 then queue 0x2a, 0x2e or 0x2d for b
    (0x114ade8, the tail call); kind 0x17 builds an entry (0x1480a6c), sends it through 0x1581080 and
    0x288c444, then queues 0x2a."""
    from pokeldn.sv.battle.machine import FUNCTIONS, UnliftedCall
    k = kind & 0xFF
    marked = k <= 0x23 and (1 << k) & 0x804020002
    for need, when in ((0x282410C, marked), (0x1581080, k == 0x17), (0x288C444, k == 0x17)):
        if when and need not in FUNCTIONS:          # reached after the first writes
            raise UnliftedCall(f"main+0x{need:x}")
    if marked:
        e = m.call(m.main + 0x139B698, o)
        e2 = m.call(m.main + 0x139B698, o)
        m.put(e + 8, 4, m.vcall(b, 0x98))
        m.put(e + 6, 2, a)
        m.put(e + 0xC, 2, 0x10A)
        m.call_void(m.main + 0x282410C, m.call(m.main + 0x1578F00, o), e, e2 + 0x10)
    r = _tail(m, m.main + 0x1482E80, m.call(m.main + 0x1143584, o), b, a & 0xFFFFFFFF, kind & 0xFFFFFFFF)
    if k in (2, 3, 4):
        msg = {2: 0x2A, 3: 0x2E, 4: 0x2D}[k]
        return _tail(m, m.main + 0x114ADE8, m.call(m.main + 0x1143584, o), b, msg)
    if k != 0x17:
        return r
    r1 = m.call(m.main + 0x11440E8, m.call(m.main + 0x1482534, o))
    r2 = m.call(m.main + 0x114ACBC, o)
    h = m.call(m.main + 0x14D96D8, m.call(m.main + 0x1482534, o))
    pair = m.call(m.main + 0x1480A6C, h, 2, m.vcall(b, 0x98) & 0xFFFFFFFF, r1, r2)
    with m.frame(0x10) as sp:
        m.put(sp, 8, pair[0]); m.put(sp + 8, 8, pair[1])
        m.call_void(m.main + 0x1581080, m.call(m.main + 0x1143584, o), m.vcall(b, 0x98) & 0xFFFFFFFF, 0)
        m.call_void(m.main + 0x288C444, m.call(m.main + 0x1143584, o), b, 2, sp)
        return _tail(m, m.main + 0x114ADE8, m.call(m.main + 0x1143584, o), b, 0x2A)


@lifted(0x288D228)
def add_u16_8(m, o, n, *_):
    p = m.call(m.main + 0xFA01F0, m.u64(o + 0x10))
    m.put(p + 8, 2, m.u16(p + 8) + n)


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


@lifted(0x288D9F0)
def queue_4a(m, q, a, b, src, *_):
    """Command 0x4a (a & 0xff, b, then the three values 0x174ae90 reads out of `src`)."""
    with m.frame(0x10) as f:
        m.put(f, 8, 0); m.put(f + 8, 4, 0)
        m.call_void(m.main + 0x174AE90, src, f + 4, f, f + 8)
        m.call_void(m.main + 0x119AFF0, q, 0x4A, a & 0xFF, b & 0xFFFFFFFF, m.u32(f + 4), m.u32(f), m.u32(f + 8))


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


@lifted(0x156616C)
def add_and_queue_85(m, o, kind, n, *_):
    m.call_void(m.main + 0x15661B0, m.u64(o + 0x20), kind & 0xFFFFFFFF, n & 0xFFFFFFFF)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x85, kind & 0xFF, n & 0xFFFFFFFF)


@lifted(0x114DC24)
def queue_c1(m, o, a, b, *_):
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xC1, a & 0xFF, b & 0xFFFFFFFF)


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


@lifted(0x287EA80)
def set_and_queue_288d8c0(m, o, a, p, *_):
    """When 0x288c710([o+0x20], a, p) accepts, 0x288d8c0([o+0x18], a, p); 1 when it did."""
    if m.call(m.main + 0x288C710, m.u64(o + 0x20), a, p) & 1 == 0:
        return 0
    m.call_void(m.main + 0x288D8C0, m.u64(o + 0x18), a, p)
    return 1


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


def _store_and_command_75(m, q, a, b):
    """0x11494a4 (reached only as a tail call): 0x11494e8([q+0x20], a, b) stores b in slot a, then
    command 0x75 (a & 0xff, b) on [q+0x18]."""
    a &= 0xFFFFFFFF; b &= 0xFFFFFFFF
    m.call_void(m.main + 0x11494E8, m.u64(q + 0x20), a, b)
    return _tail(m, m.main + 0x119AFF0, m.u64(q + 0x18), 0x75, a & 0xFF, b)


@lifted(0x11494E8)
def set_entry_of_five(m, o, i, v, *_):
    i &= 0xFF
    if i < 5:
        m.put(m.u64(m.u64(o + 0x10) + 0x210) + 8 + 8 * i, 8, v & 0xFFFFFFFF)


def _kind(kind, address):
    def fn(m, out, *_):
        m.put(out, 4, kind)
        return m.main + address
    return fn


# Type descriptors: store a kind, return a rodata address. (function, kind, address)
for _addr, _kind_v, _ret in ((0x2D18260, 1, 0x44FAC10), (0x2D187A0, 1, 0x44FAF00), (0x2D17240, 3, 0x44FA8A0),
                             (0x2D17840, 1, 0x44F9750), (0x2D180E0, 1, 0x44FAA40)):
    lifted(_addr)(_kind(_kind_v, _ret))


@lifted(0x1820E4C)
def next_serial(m, o, out, *_):
    v = m.u32(o + 8)
    if v == 0:
        v = 1
        m.put(o + 8, 4, 1)
    m.put(out, 4, v)
    m.put(o + 8, 4, m.u32(o + 8) + 1)


@lifted(0x28858AC)
def push_pair(m, o, a, b, *_):
    with m.frame(0x20) as p:
        m.put(p, 1, 0)
        m.put(p + 8, 4, a); m.put(p + 0xC, 4, b)
        m.put(p + 0x10, 2, 0); m.put(p + 0x12, 1, 0); m.put(p + 0x14, 2, 0)
        return _tail(m, m.main + 0x121BDB0, m.call(m.main + 0x114E520, m.u64(o + 0x78)), p, p + 8)


@lifted(0x174AE20)
def queue_0x13(m, o, a, b, src, *_):
    with m.frame(0x10) as p:
        m.put(p, 4, 0); m.put(p + 8, 8, 0)
        m.call_void(m.main + 0x174AE90, src, p + 0xC, p + 8, p)
        return _tail(m, m.main + 0x119AFF0, o, 0x13, a & 0xFFFFFFFF, b & 0xFF, m.u32(p + 0xC), m.u32(p + 8),
                     m.u32(p))


@lifted(0x115043C)
def queue_bd(m, o, arg, *_):
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xBD, arg & 0xFFFFFFFF)


def _queue_id_kind(kind):
    """Hand (battler id, kind) to 0x17776d8 on the object at [o+0x78]+0x2e0."""
    def fn(m, o, b, *_):
        ident = m.vcall(b, 0x98)
        with m.frame(0x10) as p:
            m.put(p + 8, 4, ident); m.put(p + 0xC, 1, kind)
            m.call_void(m.main + 0x17776D8, m.call(m.main + 0x17776D0, m.u64(o + 0x78)), p, p + 8)
    return fn


lifted(0x177767C)(_queue_id_kind(4))
lifted(0x114B5DC)(_queue_id_kind(1))


@lifted(0x288C710)
def forward_28787e0(m, o, v, pair, *_):
    return _tail(m, m.main + 0x28787E0, m.u64(m.u64(o + 0x10) + 0x70), v, m.u64(pair), m.u64(pair + 8))


# Index -> (value, value with a second argument; -1 means none), from the tables at 0x3c6afa0 and
# 0x3c6af36 (rows of three s16) for the indexes the mask 0x140465cff admits.
_COMMAND_VALUES = {0: (94, 297), 1: (105, 298), 2: (99, 299), 3: (89, 300), 4: (83, 296), 5: (118, 301),
                   6: (114, 302), 7: (126, 126), 10: (191, -1), 11: (194, -1), 12: (199, -1), 14: (284, -1),
                   17: (126, 126), 18: (239, -1), 22: (187, -1), 30: (216, -1), 32: (362, -1)}


@lifted(0x114A970)
def build_command(m, kind, src, arg, extra, out, *_):
    """Fill a message header at `out` for kind 1..33: u16 id, u16 flags with the argument count in
    bits 7..13, then u32 arguments; kind 0x12 adds 0x49, kind 8 adds 0xf7ffe0 of `src`."""
    w8 = (kind - 1) & 0xFFFFFFFF
    i = w8 & 0xFFFF
    if i > 0x20 or not (0x140465CFF >> (w8 & 63)) & 1:
        return 0
    a, b = _COMMAND_VALUES[i]
    extra &= 0xFFFF
    v = b if extra else a
    if v < 0:
        v = a
    hi = m.u16(out + 2) & 0xC000
    m.put(out, 2, v)
    flags = hi | 0x82
    m.put(out + 2, 2, flags)
    m.put(out + 4, 4, arg)
    if extra:
        flags = hi | 0x102
        m.put(out + 2, 2, flags)
        m.put(out + 8, 4, extra)
    k = kind & 0xFFFF
    n = flags >> 7 & 0x7F
    if k == 0x12 and n <= 7:
        m.put(out + 2, 2, ((flags + 0x80) & 0x3F80) | (flags & 0xC07F))
        m.put(out + 4 * n + 4, 4, 0x49)
    elif k == 8 and n <= 7:
        r = m.call(m.main + 0xF7FFE0, src)
        m.put(out + 2, 2, ((flags + 0x80) & 0x3F80) | (flags & 0xC07F))
        m.put(out + 4 * n + 4, 4, r & 0xFFFF)
    return 1


@lifted(0x1148DF8)
def note_and_queue_74(m, o, a, b, c, *_):
    m.call_void(m.main + 0x288D134, m.u64(o + 0x20), a, b, c)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x74, a & 0xFFFFFFFF, b & 0xFF, c & 0xFFFF)


@lifted(0x11438E4)
def use_counter(m, o, b, i, a, c, d, *_):
    """Count down the battler's counter i (vf 0x540); when it reaches zero queue the two 0x74
    messages for `a` and `c` with 0x171a7ec(0x32) and hand `d` to 0x171a604."""
    i &= 0xFFFFFFFF
    if m.vcall(b, 0x540, i) & 0xFF == 0:
        return
    n = (m.vcall(b, 0x540, i) - 1) & 0xFFFFFFFF
    m.call_void(m.main + 0x1143A30, m.call(m.main + 0x1143584, o), b, i, n)
    if n & 0xFF:
        return
    v = m.call(m.main + 0x171A7EC, 0x32) & 0xFFFFFFFF
    for arg in (a, c):
        x = m.call(m.main + 0x1143584, o)
        m.call_void(m.main + 0x1148DF8, x, m.vcall(b, 0x98) & 0xFFFFFFFF, arg & 0xFFFFFFFF, v)
    x = m.call(m.main + 0x1143584, o)
    return _tail(m, m.main + 0x171A604, x, m.vcall(b, 0x98) & 0xFFFFFFFF, d & 0xFFFFFFFF, 0xFF)


@lifted(0x171A604)
def queue_bf(m, o, a, b, c, *_):
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xBF, a & 0xFFFFFFFF, b & 0xFF, c & 0xFF)


@lifted(0x171A6DC)
def queue_73_pair(m, o, b, kind, *_):
    """For kind 7 (stats 2 and 4) or 6 (stats 1 and 3), hand the battler's id with each stat and
    0x171a7ec(0x32) to 0x171a804."""
    v = m.call(m.main + 0x171A7EC, 0x32) & 0xFFFFFFFF
    kind &= 0xFFFFFFFF
    if kind == 7:
        stats = (2, 4)
    elif kind == 6:
        stats = (1, 3)
    else:
        return
    x = m.call(m.main + 0x1143584, o)
    m.call_void(m.main + 0x171A804, x, m.vcall(b, 0x98) & 0xFFFFFFFF, stats[0], v)
    x = m.call(m.main + 0x1143584, o)
    return _tail(m, m.main + 0x171A804, x, m.vcall(b, 0x98) & 0xFFFFFFFF, stats[1], v)


@lifted(0x287EE68)
def queue_ca_287ee68(m, o, a, b, *_):
    return _tail(m, m.main + 0x157EBC0, m.u64(o + 0x18), 0xCA, a & 0xFFFFFFFF, b & 0xFFFF, 0xFFFF0000)


@lifted(0x157EBC0)
def push_terminated(m, que, command, *varargs):
    """The variadic push whose u32 arguments end at 0xffff0000: the format byte (+0x12) of the
    command's node in the queue's map at +0 (0 when absent), then 0x119bf58 over the arguments."""
    from pokeldn.sv.battle.engine.containers import find_u16
    node = find_u16(m, que, command)
    fmt = m.u8(node + 0x12) if node else 0
    with m.frame(0x40) as arr:
        m.write(arr, bytes(0x40))
        for k, v in enumerate(varargs):
            v &= 0xFFFFFFFF
            m.put(arr + 4 * k, 4, v)
            if v == 0xFFFF0000:
                break
        return _tail(m, m.main + 0x119BF58, que, command, fmt, arr)


@lifted(0x114B210)
def queue_cb(m, o, a, b, n, vals, *_):
    """Message 0xcb with `a`, `b` and the first n (1..4; otherwise none) u32 values at `vals`."""
    n &= 0xFFFFFFFF
    extra = [m.u32(vals + 4 * k) for k in range(n)] if 1 <= n <= 4 else []
    return _tail(m, m.main + 0x157EBC0, m.u64(o + 0x18), 0xCB, a & 0xFFFFFFFF, b & 0xFFFF, *extra,
                 0xFFFF0000)


@lifted(0x1536F5C)
def push_cb_pair(m, o, a, b, c, *_):
    """Message 0xcb with (a, c & 0xffff, b's id from vf 0x98) on the queue [o+0x18]."""
    v = m.vcall(b, 0x98)
    return _tail(m, m.main + 0x157EBC0, m.u64(o + 0x18), 0xCB, a & 0xFFFFFFFF, c & 0xFFFF, v & 0xFFFFFFFF,
                 0xFFFF0000)


@lifted(0x2888060)
def send_record(m, o, req, side, *_):
    """Unless the u16 req+0x1a is 0x9c, 0x2888154(0x17d31e0(o, [req]), 0x28230f4(..., side, 0), it); then
    0x114b0ac([req], a copy of req+0x20 (0x28800b8), with 0x2888170(0, side) when +0x44), bracketed by
    0x17ce0e4 / 0x17ce27c when +0x1c."""
    need = [0x28800B8, 0x1143584, 0x114B0AC]
    if m.u16(req + 0x1A) != 0x9C:
        need += [0x17D31E0, 0x1482534, 0x13813EC, 0x28230F4, 0x2888154]
    if m.u8(req + 0x1C):
        need += [0x17CE0E4, 0x17CE27C]
    if m.u8(req + 0x44):
        need += [0x2888170]
    for a in need:
        _need(m, m.main + a)
    if m.u16(req + 0x1A) != 0x9C:
        a = m.call(m.main + 0x17D31E0, o, m.u32(req)) & 0xFFFFFFFF
        t = m.call(m.main + 0x13813EC, m.call(m.main + 0x1482534, o))
        b = m.call(m.main + 0x28230F4, t, side & 0xFFFFFFFF, 0) & 0xFFFFFFFF
        m.call_void(m.main + 0x2888154, m.call(m.main + 0x1143584, o), a, b, m.u16(req + 0x1A))
    if m.u8(req + 0x1C):
        m.call_void(m.main + 0x17CE0E4, m.call(m.main + 0x1143584, o), m.u32(req))
    with m.frame(0x30) as p:
        m.call_void(m.main + 0x28800B8, p, req + 0x20)
        if m.u8(req + 0x44):
            m.call_void(m.main + 0x2888170, p, 0, side & 0xFF)
        m.call_void(m.main + 0x114B0AC, m.call(m.main + 0x1143584, o), m.u32(req), p)
    if m.u8(req + 0x1C):
        m.call_void(m.main + 0x17CE27C, m.call(m.main + 0x1143584, o), m.u32(req))


@lifted(0x13606C4)
def note_and_queue_5f(m, o, ident, *_):
    """0x13606f8([o+0x20], ident) (ident passes through in x1), then message 0x5f(ident)."""
    _need(m, m.main + 0x119AFF0)
    m.call_void(m.main + 0x13606F8, m.u64(o + 0x20), ident)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x5F, ident & 0xFFFFFFFF)


@lifted(0x288DD40)
def push_65(m, que, a, b, rec, *_):
    """Queue command 0x65 (a & 0xff, b, then the record's three fields as 0x174ae90 unpacks them)."""
    with m.frame(0x10) as p:
        m.write(p, bytes(0xC))
        m.call_void(m.main + 0x174AE90, rec, p + 4, p, p + 8)
        return _tail(m, m.main + 0x119AFF0, que, 0x65, a & 0xFF, b & M32, m.u32(p + 4), m.u32(p), m.u32(p + 8))


# Message ids for kind 1 by sub-kind 1..6 (the jump table at 0x3c6a6d7), and sub-kind 15.
_KIND1_TEXT = {1: 0x5F, 2: 0x6A, 3: 0x64, 4: 0x5A, 5: 0x54, 6: 0x77, 15: 0xA}
# Message ids for kind 2, sub-kind 1..6 (rodata 0x3c6a8ac).
_KIND2_TEXT = (0x60, 0x6B, 0x65, 0x5B, 0x55, 0x78)


@lifted(0x287DB9C)
def push_status_text(m, o, who, holder, kind, sub, flag, *_):
    """Queue the message for (kind, sub): 0xcb (who, text, holder's id) for the known ones, 0xca (who,
    0x237) otherwise; kind 1 sub 20 queues nothing."""
    hid = m.vcall(holder, 0x98)
    kind &= 0xFF
    sub &= 0xFFFF
    q = m.u64(o + 0x18)
    if kind == 2:
        if flag & 0xFF == 5 and (sub - 1) & 0xFFFF <= 5:
            text = _KIND2_TEXT[(sub - 1) & 0xFFFF]
        else:
            text = 0x48
    elif kind == 1 and sub == 20:
        return hid
    elif kind == 1 and sub in _KIND1_TEXT:
        text = _KIND1_TEXT[sub]
    else:
        return _tail(m, m.main + 0x157EBC0, q, 0xCA, who & M32, 0x237, 0xFFFF0000)
    return _tail(m, m.main + 0x157EBC0, q, 0xCB, who & M32, text, hid & M32, 0xFFFF0000)


@lifted(0x17CE27C)
def push_c8_if(m, o, ident, *_):
    if ident & M32 == 0:
        return
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xC8, ident & M32)


@lifted(0x114BEB0)
def set_and_queue_6a(m, o, v, *_):
    m.call_void(m.main + 0x114BEE4, m.u64(o + 0x20), v)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x6A, v & M32)


@lifted(0x287EAE4)
def queue_aa(m, o, v, *_):
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xAA, v & 0xFF)


@lifted(0x287EBCC)
def show_text_for(m, o, ident, flag, text, *_):
    """Send the record (ident, flag bit, the 0x24-byte text) through 0x114aab0 on 0x1807950's queue."""
    with m.frame(0x40) as s:
        m.write(s, bytes(0x2C))
        m.put(s, 4, ident); m.put(s + 4, 1, flag & 1)
        m.call_void(m.main + 0x287ECA8, s + 8, text)
        q = m.call(m.main + 0x1807950, m.call(m.main + 0x1361214, o))
        return _tail(m, m.main + 0x114AAB0, q, s + 0x30, s)


@lifted(0x287EC30)
def show_text_48(m, o, ident, flag, *_):
    """show_text_for with the text (kind 2, 0x48) naming ident."""
    with m.frame(0x30) as t:
        m.write(t, bytes(0x24))
        m.call_void(m.main + 0x2843244, t, 2, 0x48)
        m.call_void(m.main + 0x284325C, t, ident)
        m.call_void(m.main + 0x284E2A0, t)
        m.call_void(m.main + 0x287EBCC, o, ident, flag & 1, t)


@lifted(0x284E2A0)
def set_bit_15(m, t, *_):
    m.put(t + 2, 2, m.u16(t + 2) | 0x8000)


@lifted(0x157A95C)
def push_ca_237(m, o, who, *_):
    return _tail(m, m.main + 0x157EBC0, m.u64(o + 0x18), 0xCA, who & M32, 0x237, 0xFFFF0000)


@lifted(0x157EBA0)
def report_pair(m, o, a, text, b, *_):
    """Queue command 0xcb (a, text, b) on [o+0x18]."""
    return _tail(m, m.main + 0x157EBC0, m.u64(o + 0x18), 0xCB, a & M32, text & 0xFFFF, b & M32, 0xFFFF0000)


@lifted(0x2882B74)
def report_b4(m, o, a, b, c, d, e, f, *_):
    """Queue command 0xb4 (a, b, c, d, e, f) on [o+0x18]."""
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xB4, a & M32, b & M32, c & M32, d & 0xFFFF,
                 e & 0xFFFF, f & 0xFFFF)


@lifted(0x1832FA4)
def report_b3(m, o, a, b, *_):
    """Queue command 0xb3 (a, b) on [o+0x18]."""
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xB3, a & M32, b & M32)


@lifted(0x2882914)
def report_ca(m, o, a, text, b, *_):
    """Queue command 0xca (a, text, b) on [o+0x18]."""
    return _tail(m, m.main + 0x157EBC0, m.u64(o + 0x18), 0xCA, a & M32, text & 0xFFFF, b & M32, 0xFFFF0000)


@lifted(0x288B9B0)
def report_cb_75(m, o, b, *_):
    """0x114ade8(b, 0x2f), then command 0xcb (b, 0x75, b)."""
    m.call_void(m.main + 0x114ADE8, o, b, 0x2F)
    q = m.u64(o + 0x18)
    a = m.vcall(b, 0x98) & M32
    return _tail(m, m.main + 0x157EBC0, q, 0xCB, a, 0x75, m.vcall(b, 0x98) & M32, 0xFFFF0000)


@lifted(0x288BA20)
def report_cb_70(m, o, b, *_):
    """0x114ade8(b, 0x30), then command 0xcb (b, 0x70, b, vf 0x238(7))."""
    v = m.vcall(b, 0x238, 7) & 0xFFFF
    m.call_void(m.main + 0x114ADE8, o, b, 0x30)
    q = m.u64(o + 0x18)
    a = m.vcall(b, 0x98) & M32
    return _tail(m, m.main + 0x157EBC0, q, 0xCB, a, 0x70, m.vcall(b, 0x98) & M32, v, 0xFFFF0000)


@lifted(0x1140198)
def apply_and_queue_1f(m, o, b, v, *_):
    """0x1142484([o+0x20], id, v), then command 0x1f (id, v)."""
    m.call_void(m.main + 0x1142484, m.u64(o + 0x20), m.vcall(b, 0x98) & M32, v & M32)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x1F, m.vcall(b, 0x98) & M32, v & M32)


@lifted(0x16EEB20)
def bond_full_command(m, o, b, *_):
    """Command 0xb4 (id, 1, 1, 0x2e8, id, 0) when 0x16eeb98 reads 0xff."""
    r = m.call(m.main + 0x16EEB98, m.u64(o + 8), m.u64(o + 0x10), b)
    if r & 0xFF != 0xFF:
        return r
    ident = m.vcall(b, 0x98) & M32
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xB4, ident, 1, 1, 0x2E8, ident & 0xFFFF, 0)


def _cb_names(m, q, ident, base, count, ids):
    if not 1 <= count <= 4:
        return
    pad = ids + [0] * (4 - len(ids))
    args = [pad[0]] + [pad[k] if len(ids) > k else pad[0] for k in range(1, count)]
    m.call_void(m.main + 0x157EBC0, q, 0xCB, ident, base + count - 1, *args, 0xFFFF0000)


@lifted(0x28851C8)
def side_texts(m, o, b, n, kinds, lst, listed, *_):
    """Texts for the n battlers at lst by kind byte (>= 8: the other side, < 7: b's side): with `listed`,
    command 0xcb naming up to four distinct ids (texts 2..5 and 6..9), else command 0xca 0x23e / 0x23f;
    0x16eeb20 when one of the other side fails 0x1142e68."""
    c28 = c27 = c26 = 0
    for i in range(n & M32):
        k = m.u8(kinds + i)
        if k >= 8:
            c28 = (c28 + 1) & 0xFF
            r = m.call(m.main + 0x1142E68, m.u64(o + 8), m.u64(o + 0x10), m.u64(lst + 8 * i))
            c27 = (c27 + (~r & 1)) & 0xFF
            k = m.u8(kinds + i)
        if k < 7:
            c26 = (c26 + 1) & 0xFF
    if c27:
        _need(m, m.main + 0x16EEB20)
    ident = m.vcall(b, 0x98) & M32
    q = lambda: m.u64(o + 0x18)
    if not listed & 1:
        if c28:
            m.call_void(m.main + 0x157EBC0, q(), 0xCA, ident, 0x23E, 0xFFFF0000)
            if c27:
                return _tail(m, m.main + 0x16EEB20, o, b)
            return
        if c26:
            return _tail(m, m.main + 0x157EBC0, q(), 0xCA, ident, 0x23F, 0xFFFF0000)
        return
    if c28:
        ids = _unique_ids(m, n & M32, kinds, lst, lambda k: k >= 8)
        _cb_names(m, q(), ident, 2, c28, ids)
        if c27:
            m.call_void(m.main + 0x16EEB20, o, b)
    if c26:
        ids = _unique_ids(m, n & M32, kinds, lst, lambda k: k <= 6)
        _cb_names(m, q(), ident, 6, c26, ids)


@lifted(0x14A0860)
def set_and_queue_09(m, o, ident, v, *_):
    """0x14a08a4([o+0x20], id, v), then command 9 (id, v byte)."""
    m.call_void(m.main + 0x14A08A4, m.u64(o + 0x20), ident, v)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 9, ident & M32, v & 0xFF)


@lifted(0x2880E44)
def queue_record_8(m, o, *_):
    """0x1154148 on [o+0x78]'s object with a 0x1149604 record: kind 8, byte 0x13616e4([o+8]), pair
    0x113e080(0)."""
    with m.frame(0x70) as sp:
        m.write(sp, bytes(0x50))
        m.call_void(m.main + 0x1149604, sp)
        m.put(sp + 4, 4, 8)
        m.put(sp + 8, 1, m.call(m.main + 0x13616E4, m.u64(o + 8)))
        p = m.call(m.main + 0x113E080, 0)
        m.put(sp + 0x10, 8, p[0]); m.put(sp + 0x18, 8, p[1])
        x = m.call(m.main + 0x113DFC4, m.u64(o + 0x78))
        return _tail(m, m.main + 0x1154148, x, sp + 0x68, sp)


@lifted(0x13607F0)
def set_and_queue_5d(m, o, ident, *_):
    m.call_void(m.main + 0x1360F0C, m.u64(o + 0x20), ident)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x5D, ident & M32)


@lifted(0x147AC20)
def set_and_queue_29(m, o, ident, *_):
    m.call_void(m.main + 0x147AC54, m.u64(o + 0x20), ident)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x29, ident & M32)


@lifted(0x1946378)
def queue_text_by_kind(m, o, b, x, kind, flag, *_):
    """0x114ade8([o+0x20], x, text): 0x84 with `flag`; for kind 1 the text event 0xed leaves; else 0x85
    for b, then 0x1832fa4 (b's id, 0)."""
    c = m.u64(o + 0x20)
    if flag & 1:
        return _tail(m, m.main + 0x114ADE8, c, x, 0x84)
    if kind & 0xFF == 1:
        v = m.call(m.main + 0x1946418, m.u64(o + 0x38), b) & M32
        return _tail(m, m.main + 0x114ADE8, m.u64(o + 0x20), x, v)
    ident = m.vcall(b, 0x98) & M32
    m.call_void(m.main + 0x114ADE8, m.u64(o + 0x20), b, 0x85)
    return _tail(m, m.main + 0x1832FA4, m.u64(o + 0x20), ident, 0)


@lifted(0x2881C58)
def apply_and_queue_37(m, c, ident, kind, v, *_):
    """b's vf 0x550(kind, v) for the battler `ident`, then command 0x37 (id, kind byte, v)."""
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(m.u64(c + 0x20) + 0x10) + 0x30), ident)
    m.vcall_void(b, 0x550, kind & M32, v & M32)
    return _tail(m, m.main + 0x119AFF0, m.u64(c + 0x18), 0x37, ident & M32, kind & 0xFF, v & M32)


@lifted(0x2888A5C)
def count_and_queue_4c(m, c, a, b, *_):
    """When 0x13df9d4([c+0x10], a, b) finds a record: bump its +0x1c count and queue command 0x4c (a byte, b)."""
    x = m.call(m.main + 0x13DF9D4, m.u64(c + 0x10), a, b)
    if not x:
        return
    m.call_void(m.main + 0x288DA88, x)
    return _tail(m, m.main + 0x119AFF0, m.u64(c + 0x18), 0x4C, a & 0xFF, b & M32)


@lifted(0x2888AD0)
def queue_99(m, c, v, *_):
    return _tail(m, m.main + 0x119AFF0, m.u64(c + 0x18), 0x99, v & 0xFF)


@lifted(0x2888AE0)
def weather_event_none(m, o, *_):
    """0x114bf24 on 0x114bf1c([o+0x78]) with kind 0."""
    with m.frame(0x10) as sp:
        m.put(sp + 8, 1, 0)
        x = m.call(m.main + 0x114BF1C, m.u64(o + 0x78))
        return _tail(m, m.main + 0x114BF24, x, sp, sp + 8)


@lifted(0x2888B10)
def weather_request_of(m, o, kind, *_):
    """0x1149ed0 on 0x113e064([o+0x78]) with the request {kind, 0xff, 0xff, u32 0, u16 0 at +8}."""
    with m.frame(0x20) as sp:
        req = sp + 0x10
        m.put(req + 8, 2, 0); m.put(req, 1, kind); m.put(req + 1, 2, 0xFFFF); m.put(req + 4, 4, 0)
        x = m.call(m.main + 0x113E064, m.u64(o + 0x78))
        return _tail(m, m.main + 0x1149ED0, x, sp + 8, req)


def _reserve_c9(m, o):
    """Reserve a group 0xcf (placeholder command 0xc9) in [[o+0x28]+8] and note it in the current
    0xc4-byte entry of [[o+0x40]+8] (index +0x938) at +0xa."""
    x = m.u64(m.u64(o + 0x40) + 8)
    i = m.u8(x + 0x938)
    v = m.call(m.main + 0x10AFCB8, m.u64(m.u64(o + 0x28) + 8), 0xC9, 0xCF, 0)
    m.put(x + i * 0xC4 + 0xA, 2, v)


@lifted(0x287F844)
def add_and_queue_81(m, c, v, *_):
    """0x288d228([c+0x20], v), then command 0x81 with v as a signed 16-bit value."""
    m.call_void(m.main + 0x288D228, m.u64(c + 0x20), v)
    s = v & 0xFFFF
    s = s - 0x10000 if s & 0x8000 else s
    return _tail(m, m.main + 0x119AFF0, m.u64(c + 0x18), 0x81, s & M32)


@lifted(0x2888474)
def release_and_queue_66(m, c, side, k, *_):
    m.call_void(m.main + 0x288D11C, m.u64(c + 0x20), side, k)
    return _tail(m, m.main + 0x119AFF0, m.u64(c + 0x18), 0x66, side & 0xFF, k & M32)


@lifted(0x1832F80)
def report_ca_text(m, q, a, text, b, v, *_):
    """Command 0xca (a, text, b, v) through 0x157ebc0."""
    return _tail(m, m.main + 0x157EBC0, m.u64(q + 0x18), 0xCA, a & M32, text & 0xFFFF, b & M32, v & M32,
                 0xFFFF0000)


@lifted(0x1832F0C)
def text_2cf(m, o, b, *_):
    """Text 0x2cf naming b (command 0xca with 0x1589a40's value), then command 0xb3 (b's id, 0)."""
    ident = m.vcall(b, 0x98) & M32
    v = m.call(m.main + 0x1589A40, o, ident)
    m.call_void(m.main + 0x1832F80, m.call(m.main + 0x1143584, o), ident, 0x2CF, ident, v & 0xFF)
    return _tail(m, m.main + 0x1832FA4, m.call(m.main + 0x1143584, o), ident, 0)


@lifted(0x28810A0)
def text_ab(m, o, b, *_):
    """Command 0xcb (b's id, text 0xab, b's id) through 0x157eba0."""
    ident = m.vcall(b, 0x98) & M32
    return _tail(m, m.main + 0x157EBA0, m.call(m.main + 0x1143584, o), ident, 0xAB, ident)


@lifted(0x134ED6C)
def weather_turns_left(m, w, *_):
    """0 without a weather (u8 +0x19); 0xff for an endless one (u32 +8 is 0xff); else +8 minus +0x10."""
    if not m.u8(w + 0x19):
        return 0
    n = m.u32(w + 8)
    return 0xFF if n == 0xFF else (n - m.u32(w + 0x10)) & M32


@lifted(0x114A040)
def weather_may_replace(m, o, kind, *_):
    """0 when the current weather (u8 +0x19 of 0x148253c(0x1482534(o))) is 5..7 and `kind` is 1..4."""
    cur = m.call(m.main + 0x114A08C, m.call(m.main + 0x148253C, m.call(m.main + 0x1482534, o))) & 0xFF
    return int((cur - 5) & 0xFF > 2) | int((kind - 1) & 0xFF > 3)


@lifted(0x1149F90)
def weather_check(m, o, out, req, *_):
    """out[0] = 0 when the weather request (u8 kind [req], u8 turns [req+1]) may change the weather; 2
    when the weather is locked (+0x1a clear) or 0x114a040 refuses; 1 for a kind above 7 or for the
    same endless weather already up."""
    m.put(out, 1, 1)
    if m.u8(req) > 7:
        return
    w = m.call(m.main + 0x148253C, m.call(m.main + 0x1482534, o))
    if m.call(m.main + 0x114A038, w) & 1 == 0 or m.call(m.main + 0x114A040, o, m.u8(req)) & 1 == 0:
        m.put(out, 1, 2)
        return
    if m.u8(req) != m.call(m.main + 0x114A08C, w) & 0xFF:
        m.put(out, 1, 0)
        return
    if m.u8(req + 1) != 0xFF:
        return
    if m.call(m.main + 0x134ED6C, w) & M32 != 0xFF:
        m.put(out, 1, 0)


@lifted(0x1149F50)
def weather_check_of(m, o, kind, turns, *_):
    """0x1149f90 on [0x1361214(o)+0x200] for {kind, turns}: its answer."""
    with m.frame(0x10) as sp:
        m.put(sp + 8, 1, kind); m.put(sp + 9, 1, turns)
        x = m.call(m.main + 0x1149F88, m.call(m.main + 0x1361214, o))
        m.call_void(m.main + 0x1149F90, x, sp, sp + 8)
        return m.u8(sp)


@lifted(0x114C1F4)
def weather_store(m, o, kind, turns, a, src, *_):
    """The weather block [[o+0x10]+0x70]: kind at +0x19, turns +8, a +0xc, 0 at +0x10, src +0x14."""
    w = m.u64(m.u64(o + 0x10) + 0x70)
    m.put(w + 0x19, 1, kind)
    m.put(w + 8, 4, turns & 0xFF); m.put(w + 0xC, 4, a & 0xFF)
    m.put(w + 0x10, 4, 0); m.put(w + 0x14, 4, src)


@lifted(0x114C164)
def weather_set(m, o, kind, turns, a, src, e, f, *_):
    """0x114c1f4([o+0x20], ...), then commands 0x79 (kind, turns, a, src, e) and 0x88 (kind, src, e, f & 1)."""
    m.call_void(m.main + 0x114C1F4, m.u64(o + 0x20), kind, turns, a, src)
    m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0x79, kind & 0xFF, turns & 0xFF, a & 0xFF, src & M32,
                e & M32)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x88, kind & 0xFF, src & M32, e & 0xFF, f & 1)


@lifted(0x114BF24)
def weather_event_of(m, o, out, kind, *_):
    return _tail(m, m.main + 0x1151590, m.call(m.main + 0x1146E90, o), m.u8(kind))


@lifted(0x114BEEC)
def weather_event(m, o, kind, *_):
    """0x114bf24 on [0x1361214(o)+0x1e0] with the kind."""
    with m.frame(0x10) as sp:
        m.put(sp + 8, 1, kind)
        x = m.call(m.main + 0x114BF1C, m.call(m.main + 0x1361214, o))
        return _tail(m, m.main + 0x114BF24, x, sp, sp + 8)


@lifted(0x114BF48)
def weather_trigger(m, o, src, kind, *_):
    """Trigger 0x121bdb0 on [0x1361214(o)+0x1d40] with the record {9, src, kind at +0xa}."""
    with m.frame(0x20) as sp:
        r = sp + 0x10
        m.put(r + 0xC, 2, 0); m.put(r + 8, 2, 0)
        m.put(r, 4, 9); m.put(r + 4, 4, src)
        m.put(r + 0xA, 1, kind)
        m.put(sp + 8, 1, 0)
        x = m.call(m.main + 0x114E520, m.call(m.main + 0x1361214, o))
        return _tail(m, m.main + 0x121BDB0, x, sp + 8, r)


@lifted(0x114BE34)
def weather_apply(m, o, out, req, *_):
    """Apply the weather request: 0x114beb0 (0), 0x114bf8c (0, kind), 0x114c164 with its fields,
    0x114beec (kind), then 0x114bf48 (src, kind)."""
    m.call_void(m.main + 0x114BEB0, m.call(m.main + 0x1143584, o), 0)
    m.call_void(m.main + 0x114BF8C, m.call(m.main + 0x1143584, o), 0, m.u8(req))
    m.call_void(m.main + 0x114C164, m.call(m.main + 0x1143584, o), m.u8(req), m.u8(req + 1), m.u8(req + 2),
                m.u32(req + 4), m.u8(req + 8), m.u8(req + 9))
    m.call_void(m.main + 0x114BEEC, o, m.u8(req))
    return _tail(m, m.main + 0x114BF48, o, m.u32(req + 4), m.u8(req))


@lifted(0x114BDE4)
def weather_apply_of(m, o, kind, turns, a, src, e, *_):
    """0x114be34 on [0x1361214(o)+0x220] with {kind, turns, a, src, e, +9 = 1}."""
    with m.frame(0x20) as sp:
        r = sp + 0x10
        m.put(r + 9, 1, 1)
        m.put(r, 1, kind); m.put(r + 1, 1, turns); m.put(r + 2, 1, a)
        m.put(r + 4, 4, src); m.put(r + 8, 1, e)
        x = m.call(m.main + 0x114BE2C, m.call(m.main + 0x1361214, o))
        return _tail(m, m.main + 0x114BE34, x, sp + 8, r)


@lifted(0x1149ED0)
def weather_request(m, o, out, req, *_):
    """out[0] = 0x1149f50's answer (0 when req+8 is set); when 0, 0x114bde4 with the request's fields."""
    if m.u8(req + 8) == 0:
        r = m.call(m.main + 0x1149F50, o, m.u8(req), m.u8(req + 1)) & 0xFF
        m.put(out, 1, r)
        if r:
            return
    else:
        m.put(out, 1, 0)
    return _tail(m, m.main + 0x114BDE4, o, m.u8(req), m.u8(req + 1), m.u8(req + 2), m.u32(req + 4),
                 m.u8(req + 9))
