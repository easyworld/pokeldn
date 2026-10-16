"""The end of a turn: residual damage, the condition countdowns, the side condition ticks and the
resumable end-of-turn state machine."""

from pokeldn.sv.battle.engine.calls import M32, _need, _s32, _tail, m_s32
from pokeldn.sv.battle.engine.statics import _has_static, _raid_class
from pokeldn.sv.battle.machine import lifted


@lifted(0x1143030)
def first_of_pair(m, o, *rest):
    """The first byte 0x113fa64 writes for the object 0x114a964 returns."""
    p = m.call(m.main + 0x114A964, m.u64(o + 0x78), *rest[:7])
    with m.frame(0x10) as f:
        m.call_void(m.main + 0x113FA64, p, f, f + 8)
        return m.u8(f)


@lifted(0x114309C)
def tick_timer(m, o, *_):
    """Advance the running timer at [[o+0x10]+0x70] (flag +0x19, count +0x10, limit +8, 0xff never
    ends): the flag byte when it expires (then cleared with +0x14), else 0."""
    t = m.u64(m.u64(o + 0x10) + 0x70)
    flag = m.u8(t + 0x19)
    if flag == 0:
        return 0
    limit = m.u32(t + 8)
    if limit == 0xFF:
        return 0
    n = (m.u32(t + 0x10) + 1) & 0xFFFFFFFF
    m.put(t + 0x10, 4, n)
    if limit > n:
        return 0
    m.put(t + 0x19, 1, 0); m.put(t + 0x14, 4, 0)
    return flag


@lifted(0x1143060)
def tick_timer_queue_50(m, o, *_):
    r = m.call(m.main + 0x114309C, m.u64(o + 0x20)) & 0xFFFFFFFF
    m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0x50, 0)
    return r


@lifted(0x13602D8)
def run_1360318(m, o, arg, *_):
    """0x1360318 on 0x1360310's object with a stack record (arg at +8, u16 0x101 at +0x10)."""
    with m.frame(0x18) as f:
        m.put(f + 8, 8, arg); m.put(f + 0x10, 2, 0x101)
        x = m.call(m.main + 0x1361214, o, arg)
        x = m.call(m.main + 0x1360310, x, arg)
        return _tail(m, m.main + 0x1360318, x, f, f + 8)


@lifted(0x127DCB8)
def reset_timer(m, t, *_):
    m.put(t + 0x1B, 1, 0)
    m.write(t + 0x38, bytes(0x3F0))
    m.put(t + 0x19, 2, 0x100); m.put(t + 8, 4, 0xFF); m.put(t + 0x10, 8, 0)


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


@lifted(0x11502BC)
def mark_flagged(m, o, *_):
    if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49A) >> 1 & 1 == 0:
        return
    with m.frame(0xC0) as p:
        it = p + 0x10
        m.call_void(m.main + 0x1143D84, it)
        m.put(p + 8, 8, it)
        m.call_void(m.main + 0x1143DF0, m.call(m.main + 0x1143DE8, m.u64(o + 0x78)), p, p + 8)
        m.call_void(m.main + 0x1143D7C, it)
        pk = m.call(m.main + 0x158003C, it)
        while pk:
            if m.call(m.main + 0x1142E68, m.u64(o + 8), m.u64(o + 0x10), pk) & 1 == 0 and _has_static(m, pk):
                if m.call(m.main + 0x1680124, pk) & 1 and m.vcall(pk, 0x510, 0x19) & 1:
                    t = m.u64(o + 0x20)
                    m.call_void(m.main + 0x115044C, t, m.vcall(pk, 0x98) & 0xFFFFFFFF)
                    t = m.u64(o + 0x20)
                    m.call_void(m.main + 0x115043C, t, m.vcall(pk, 0x98) & 0xFFFFFFFF)
            pk = m.call(m.main + 0x158003C, it)


def _rule_index(m, table, ident):
    """The setup map's s32 for `ident` below 5, else 0; 0 when absent."""
    p = m.call(m.main + 0x10E2DD4, table, ident & M32)
    if not p:
        return 0
    v = m.s(p, 4)
    return v if v < 5 else 0


@lifted(0x1680124)
def get_714(m, b, *_): return m.u8(b + 0x714)


@lifted(0x168012C)
def clear_entry_flag(m, t, k, ident, flag, *_):
    """In row k (0..4, 0x60 bytes) of t: the first of the six entries (u32 id at +0x10 + 0x10 j) holding
    `ident` takes flag & 1 in its byte +0xe when that byte is 0."""
    k &= 0xFF
    if k > 4:
        return
    for j in range(1, 7):
        e = t + 0x60 * k + 0x10 * j
        if m.u32(e) == ident & M32:
            if m.u8(e + 0xE) == 0:
                m.put(e + 0xE, 1, flag & 1)
            return


@lifted(0x1680000)
def note_raid_flag(m, o, b, *_):
    """For a raid battler b: 0x168012c on [[o+0x10]+0x250] with b's setup index, id and byte +0x714."""
    if not _raid_class(m, b):
        return
    ident = m.vcall(b, 0x98) & M32
    k = _rule_index(m, m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50), ident)
    t = m.u64(m.u64(o + 0x10) + 0x250)
    return _tail(m, m.main + 0x168012C, t, k & M32, ident, m.call(m.main + 0x1680124, b) & 1)


@lifted(0x1150480)
def reset_raid_battler(m, o, ident, *_):
    """For the raid battler `ident`: clear +0x714, vf 0x4d8(0x1c); with setup flag 0x49c bit 1, zero its
    index's u64 in [[o+0x10]+0x210]+0x80 and byte in [[o+0x10]+0x2d0]+8; then 0x1680000."""
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), ident)
    b = b if _raid_class(m, b) else 0
    m.put(b + 0x714, 1, 0)
    m.vcall_void(b, 0x4D8, 0x1C)
    if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49C) >> 1 & 1:
        k = _rule_index(m, m.u64(m.u64(o + 0x10) + 0x50), ident)
        m.put(m.u64(m.u64(o + 0x10) + 0x210) + 8 * (k & M32) + 0x80, 8, 0)
        m.put(m.u64(m.u64(o + 0x10) + 0x2D0) + 4 * k + 8, 1, 0)
    return _tail(m, m.main + 0x1680000, o, b)


@lifted(0x115044C)
def reset_raid_battler_queued(m, o, ident, *_):
    """0x1150480([o+0x20], ident), then command 0x80 with ident."""
    m.call_void(m.main + 0x1150480, m.u64(o + 0x20), ident)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x80, ident & M32)


@lifted(0x1142D98)
def run_1142dcc(m, o, *_):
    """0x1142dcc(0x1142dc4([o+0x78]), two out slots on the stack)."""
    with m.frame(0x10) as p:
        return _tail(m, m.main + 0x1142DCC, m.call(m.main + 0x1142DC4, m.u64(o + 0x78)), p, p + 8)


@lifted(0x1141D4C)
def turn_end(m, o, *_):
    """End a turn: 0x121b9b4; vf 0x2c8 and 0x568 and command 0x43 for each member 0x1143e3c lists;
    0x283c488, 0x282fbf4; vf 0x448 and command 0x23 for each id in [[o+0x40]+0x68] (then cleared);
    vf 0 of each listed member's +0x28; 0x121bdb0 with codes 5 and (rule 0x49c bit 1) 0x1a; result 9
    from 0x1399e20; the turn counter (at most 9999), command 0x2d, 0x2d21a74."""
    with m.frame(0x100) as sp:
        lst, a, b = sp + 8, sp + 0xD8, sp + 0xB8

        def listed():
            m.write(lst, bytes(0x8F))
            m.write(sp + 0x98, bytes(0x18)); m.put(sp + 0xB0, 2, 0)
            h = m.u64(m.u64(o + 0x78) + 0x1280)
            m.call_void(m.main + 0x1144704, h, lst)
            m.put(a, 8, lst)
            m.call_void(m.main + 0x1143E3C, m.u64(m.u64(h + 0x78) + 0x17E0), b, a)
            m.put(lst + 0xA8, 1, 0)
            if not m.u8(lst + 0xA6):
                return
            t = m.u64(lst)
            m.put(lst + 0xA8, 1, 1)
            while t:
                yield t
                i = m.u8(lst + 0xA8)
                if i >= m.u8(lst + 0xA6):
                    return
                m.put(lst + 0xA8, 1, i + 1)
                t = m.u64(lst + 8 * i)

        m.put(lst, 1, 1)
        m.call_void(m.main + 0x121B9B4, m.u64(m.u64(o + 0x78) + 0x1F60), a, lst)
        for t in listed():
            c = m.u64(o + 0x20)
            ident = m.vcall(t, 0x98) & M32
            pc = m.u64(m.u64(c + 0x20) + 0x10)
            m.vcall_void(m.call(m.main + 0xF21C94, m.u64(pc + 0x30), ident), 0x2C8)
            m.vcall_void(m.call(m.main + 0xF21C94, m.u64(pc + 0x30), ident), 0x568)
            m.call_void(m.main + 0x119AFF0, m.u64(c + 0x18), 0x43, ident)
        m.call_void(m.main + 0x283C488, m.u64(o + 0x30))
        m.call_void(m.main + 0x282FBF4, m.u64(o + 0x38))
        ids = m.u64(m.u64(o + 0x40) + 0x68)
        k = 0
        while k < m.s(ids + 0x28, 4):
            ident = m.u8(ids + 8 + k) if k < 0x1E else 0
            c = m.u64(o + 0x20)
            b2 = m.call(m.main + 0xF21C94, m.u64(m.u64(m.u64(c + 0x20) + 0x10) + 0x30), ident)
            m.vcall_void(b2, 0x448)
            m.call_void(m.main + 0x119AFF0, m.u64(c + 0x18), 0x23, ident)
            k += 1
            ids = m.u64(m.u64(o + 0x40) + 0x68)
        m.write(ids + 8, bytes(0x1E)); m.put(ids + 0x28, 4, 0)
        for t in listed():
            m.vcall(t + 0x28, 0)
            m.call(m.main + 0x2D1FD38)
        for code, on in ((5, True), (0x1A, None)):
            if on is None and not m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49C) >> 1 & 1:
                continue
            m.put(lst, 8, code); m.put(lst + 8, 2, 0); m.put(lst + 0xA, 1, 0); m.put(lst + 0xC, 2, 0)
            m.put(a, 1, 0)
            m.call_void(m.main + 0x121BDB0, m.u64(m.u64(o + 0x78) + 0x1D40), a, lst)
    flag = m.u64(m.u64(o + 0x40) + 0x28)
    if not m.u8(flag) and m.call(m.main + 0x1399E20, o) & 1:
        m.put(m.u64(m.u64(o + 0x40) + 0x28), 1, 9)
    c = m.u64(o + 0x20)
    t = m.u64(m.u64(m.u64(c + 0x20) + 0x10) + 0x210)
    if m.u64(t + 8) <= 0x270E:
        m.put(t + 8, 8, m.u64(t + 8) + 1)
    m.call_void(m.main + 0x119AFF0, m.u64(c + 0x18), 0x2D, 0)
    m.call_void(m.main + 0x2D21A74, m.u64(o + 0x40))
    m.put(m.u64(o + 0x40) + 0x88, 1, 0)
    m.put(m.u64(o + 0x40) + 0x90, 8, 0)


def _thunk_78(getter, target):
    def fn(m, o, a, *_):
        with m.frame(0x10) as f:
            m.put(f + 8, 8, a)
            m.call_void(m.main + target, m.call(m.main + getter, m.u64(o + 0x78)), f, f + 8)
    return fn


# Thunks: target([o+0x78] through getter, sp, &arg).
for _addr, _spec in {0x113E948: (0x113E974, 0x1141D4C), 0x11438B4: (0x1143DE8, 0x1143DF0),
                     0x1143DB8: (0x1143DE8, 0x1143DF0), 0x114A904: (0x1143DE8, 0x1143DF0)}.items():
    lifted(_addr)(_thunk_78(*_spec))


@lifted(0x288A9F8)
def run_1360318_of(m, o, b, *_):
    """0x1360318 on 0x1360310's object with a stack record (b at +8, u16 0x101 at +0x10)."""
    with m.frame(0x20) as f:
        m.put(f + 0x10, 8, b); m.put(f + 0x18, 2, 0x101)
        x = m.call(m.main + 0x1360310, m.call(m.main + 0x1361214, o, b), b)
        return _tail(m, m.main + 0x1360318, x, f + 8, f + 0x10)


@lifted(0x1360604)
def clear_battler_marks(m, o, b, *_):
    """0x13606c4, 0x1360728, 0x136078c and 0x13607f0 on 0x1143584(o) with b's id."""
    for a in (0x13606C4, 0x1360728, 0x136078C):
        q = m.call(m.main + 0x1143584, o)
        m.call_void(m.main + a, q, m.vcall(b, 0x98) & M32)
    q = m.call(m.main + 0x1143584, o)
    return _tail(m, m.main + 0x13607F0, q, m.vcall(b, 0x98) & M32)


@lifted(0x136024C)
def battler_left(m, o, _x1, r, *_):
    """Clear everything tied to the battler [r]: 0x13618ac, 0x13602d8, 0x1360604, 0x1360ce8, 0x1360404,
    0x1360ffc, then 0x136038c with 0x1360558's answer."""
    m.call_void(m.main + 0x13618AC, m.call(m.main + 0x1146E90, o), m.u64(r))
    m.call_void(m.main + 0x13602D8, o, m.u64(r))
    v = m.call(m.main + 0x1360558, o, m.u64(r))
    for a in (0x1360604, 0x1360CE8, 0x1360404, 0x1360FFC):
        m.call_void(m.main + a, o, m.u64(r))
    return _tail(m, m.main + 0x136038C, o, m.u64(r), v & 1)


@lifted(0x1143394)
def raise_pending_field_conditions(m, o, *_):
    """0x28889a0(k) for each field condition k = 1..13 that 0x114358c reports."""
    for k in range(1, 14):
        if m.call(m.main + 0x114358C, m.call(m.main + 0x1143584, o), k) & 1:
            if k == 13:
                return _tail(m, m.main + 0x28889A0, o, k)
            m.call_void(m.main + 0x28889A0, o, k)


@lifted(0x1142F64)
def raise_pending_field_conditions_of(m, o, *_):
    with m.frame(0x10) as f:
        return _tail(m, m.main + 0x1143394, m.call(m.main + 0x1142F90, m.u64(o + 0x78)), f, f + 8)


@lifted(0x1360214)
def battler_left_of(m, o, b, *_):
    with m.frame(0x10) as f:
        m.put(f + 8, 8, b)
        return _tail(m, m.main + 0x136024C, m.call(m.main + 0x1360244, m.u64(o + 0x78)), f, f + 8)


@lifted(0x1143694)
def end_of_turn_damage(m, o, *_):
    """For each member of 0x11438b4's list that is not down (vf 0x200) and has neither condition 5 nor 4
    (vf 0x4d0): w = the field value 0x116ec0c (per battler through 0x116ee6c), the amount 0x1145270([o+0x38],
    b, w, a) applied through 0x1150d88 when nonzero, then 0x1144df8 on {b, 1, 0}; stops when
    [[[o+0x40]+0x28]] reads 8. a = max(1, vf 0x140 >> 4 & 0xfff) when w is 4 and none of the vf 0x300
    conditions 5, 8, 4 holds, else 0."""
    with m.frame(0xD0) as f:
        lst, rec, out = f, f + 0xB0, f + 0xC8
        m.call_void(m.main + 0x1143D84, lst)
        m.call_void(m.main + 0x11438B4, o, lst)
        m.call_void(m.main + 0x1143D7C, lst)
        while True:
            i = m.u8(lst + 0xA8)
            if i >= m.u8(lst + 0xA6):
                return
            m.put(lst + 0xA8, 1, i + 1)
            b = m.u64(lst + 8 * i)
            if not b:
                return
            if not (m.vcall(b, 0x200) & 1 or m.vcall(b, 0x4D0, 5) & 1 or m.vcall(b, 0x4D0, 4) & 1):
                ident = m.vcall(b, 0x98) & M32
                w = m.u64(m.u64(m.u64(o + 0x78) + 0xC80) + 0x38)
                weather = m.call(m.main + 0x116EC0C, w) & M32
                if ident:
                    weather = m.call(m.main + 0x116EE6C, w, ident, weather) & M32
                amount = 0
                if weather & 0xFF == 4 and not (m.vcall(b, 0x300, 5) & 1 or m.vcall(b, 0x300, 8) & 1
                                                 or m.vcall(b, 0x300, 4) & 1):
                    v = m.vcall(b, 0x140) & M32
                    amount = (v >> 4 & 0xFFF) if v & 0xFFFF >= 0x10 else 1
                r = m.call(m.main + 0x1145270, m.u64(o + 0x38), b, weather, amount) & M32
                if r:
                    x = m.call(m.main + 0x134ED30, m.u64(m.call(m.main + 0x1482534, o) + 0x70))
                    m.call_void(m.main + 0x1150D88, o, b, weather, r, x & M32)
                m.put(rec, 8, b); m.put(rec + 8, 1, 1); m.put(rec + 0x10, 8, 0)
                m.call_void(m.main + 0x1144DF8, m.call(m.main + 0x114389C, m.u64(o + 0x78)), out, rec)
            if m.call(m.main + 0x11438A4, m.call(m.main + 0x113DE70, m.call(m.main + 0x113DE68, o)), 8) & 1:
                return


@lifted(0x1142FD0)
def end_of_turn_residual(m, o, out, *_):
    """out = 0; when 0x1143060 (on 0x1143584(o)) answers w, tail 0x1150144(o, w); else 0x1143694 and out
    = 0x1143030(o) & 1."""
    q = m.call(m.main + 0x1143584, o)
    t = m.u64(m.u64(m.u64(q + 0x20) + 0x10) + 0x70)
    if m.u8(t + 0x19) and m.u32(t + 8) != 0xFF and m.u32(t + 8) <= (m.u32(t + 0x10) + 1) & M32:
        _need(m, m.main + 0x1150144)        # the timer 0x114309c expires
    m.put(out, 1, 0)
    w = m.call(m.main + 0x1143060, q)
    if w & 0xFF:
        return _tail(m, m.main + 0x1150144, o, w & M32)
    m.call_void(m.main + 0x1143694, o)
    m.put(out, 1, m.call(m.main + 0x1143030, o) & 1)


@lifted(0x1150144)
def timer_expired(m, o, kind, *_):
    """The timer of 0x114309c ran out with `kind`: command 0x99 (kind), the timer reset with command 0x54
    (0x2883060), 0x114beb0(0), 0x2888ae0; when setup byte 0x113e058 is set, 0x2888b10 with it."""
    m.call_void(m.main + 0x2888AD0, m.call(m.main + 0x1143584, o), kind & M32)
    m.call_void(m.main + 0x2883060, m.call(m.main + 0x1143584, o))
    m.call_void(m.main + 0x114BEB0, m.call(m.main + 0x1143584, o), 0)
    m.call_void(m.main + 0x2888AE0, o)
    v = m.call(m.main + 0x113E058, m.call(m.main + 0x114E480, o))
    if v & 0xFF:
        return _tail(m, m.main + 0x2888B10, o, v)
    return v


@lifted(0x2883060)
def reset_timer_queue_54(m, c, *_):
    m.call_void(m.main + 0x288CFE0, m.u64(c + 0x20))
    return _tail(m, m.main + 0x119AFF0, m.u64(c + 0x18), 0x54)


@lifted(0x288CFE0)
def reset_running_timer(m, o, *_):
    """0x288cfec on the timer [[o+0x10]+0x70]."""
    return _tail(m, m.main + 0x288CFEC, m.u64(m.u64(o + 0x10) + 0x70))


@lifted(0x288CFEC)
def stop_timer(m, t, *_):
    m.put(t + 0x19, 1, 0); m.put(t + 8, 4, 0); m.put(t + 0x10, 8, 0)


@lifted(0x1142F98)
def end_of_turn_residual_of(m, o, *_):
    """0x1142fd0 on 0x1142fc8([o+0x78]); its out byte."""
    with m.frame(0x10) as f:
        m.call_void(m.main + 0x1142FD0, m.call(m.main + 0x1142FC8, m.u64(o + 0x78)), f, f + 8)
        return m.u8(f)


@lifted(0x176989C)
def residual_hit(m, o, b, amount, *_):
    """A message (head 0x7f, b's id) and 0x114af54 (on 0x1807cbc(0x1361214(o))) with {b, amount, 4, b's
    id, message, faint check 1}; when it applied, 0x2881c58 (b's id, 4, amount)."""
    with m.frame(0x60) as f:
        msg, out, r = f, f + 0x28, f + 0x30
        m.call_void(m.main + 0x1146154, msg)
        m.call_void(m.main + 0x2843244, msg, 2, 0x7F)
        m.call_void(m.main + 0x284325C, msg, m.vcall(b, 0x98) & M32)
        m.put(r, 8, b); m.put(r + 8, 4, amount); m.put(r + 0xC, 1, 4)
        m.put(r + 0x10, 4, m.vcall(b, 0x98)); m.put(r + 0x18, 8, msg); m.put(r + 0x20, 1, 1)
        m.call_void(m.main + 0x114AF54, m.call(m.main + 0x1807CBC, m.call(m.main + 0x1361214, o)), out, r)
        if m.u8(out):
            q = m.call(m.main + 0x1143584, o)
            m.call_void(m.main + 0x2881C58, q, m.vcall(b, 0x98) & M32, 4, amount & M32)


# The condition kinds 0x114a094 walks after its first kind 0x24 (0x3c69dd0, 45 u16).
_EOT_KINDS = (0x24, 0x15, 0x12, 0x5, 0x4, 0x9, 0xA, 0x8, 0x2E, 0x2B, 0x30, 0xB, 0xC, 0x17, 0xD, 0x1F, 0x21,
              0xF, 0x13, 0x1D, 0x1E, 0x26, 0x25, 0x27, 0x28, 0x29, 0x18, 0x2D, 0xE, 0x14, 0x1, 0x2, 0x3, 0x7,
              0x6, 0x10, 0x11, 0x16, 0x19, 0x1A, 0x1B, 0x1C, 0x20, 0x22, 0x23)
# Kinds 4 / 5 / 9 / 10 of 0x114a094: (text for 0x114ade8, byte +0xc of the hit, u16 head of its message).
_EOT_DAMAGE = {4: (0x2C, 0x27, 0x58), 5: (0x2B, 0x26, 0x52), 9: (0x44, 0x28, 0x6D), 10: (0x43, 0x29, 0x156)}
# Follow-ups by kind after the damage step (jump table 0x3c6a641 and the compares after it).
_EOT_AFTER = {0x12: 0x114C778, 0x14: 0x114B30C, 0x15: 0x114B3A8, 0x17: 0x114B514, 8: 0x114FE90,
              0x24: 0x114B454, 0x2B: 0x114C9E4}
# Kinds whose condition ended with a message (0x114a970): jump table 0x3c6a633.
_EOT_ENDED = {0xE: (0x114AE50, True), 0xF: (0x114ABE8, False), 0x13: (0x114AB94, False),
              0x14: (0x114AC3C, True)}


def _eot_kind_30(m, o, b, x29):
    """Kind 0x30 of 0x114a094: when vf 0x280(5) is positive, messages 0x1150748 and 0x1151258 naming the
    condition's source (vf 0x240(0x30)) and b."""
    if m.vcall(b, 0x200) & 1:
        return
    ident = m.vcall(b, 0x98) & M32
    pair = m.vcall(b, 0x240, 0x30)
    x0, x1 = (pair[0], pair[1]) if isinstance(pair, tuple) else (pair, 0)
    Z, W = x29 - 0x30, x29 - 0xB0
    m.put(Z, 8, x0); m.put(Z + 8, 8, x1)
    src = x0 & M32
    m.put(x29 - 0x38, 1, 0)
    if _s32(m.vcall(b, 0x280, 5)) < 1:
        return
    m.write(W + 4, bytes(0x2C))
    m.put(W, 4, 0x0A0A0095)
    m.put(W, 2, 0x96 if m.call(m.main + 0x114BD20, Z) & 1 else 0x95)
    pos = m.u64(m.u64(o + 0x10) + 0xF0)
    m.put(W + 2, 1, m.call(m.main + 0x1381420, pos, src))
    m.put(W + 3, 1, m.call(m.main + 0x1381420, pos, ident))
    m.call_void(m.main + 0x1150748, m.u64(m.u64(o + 0x78) + 0x9A0), x29 - 0x40, W)
    m.put(W + 0x38, 2, 0); m.put(W + 0x3C, 4, 0); m.put(W + 0x40, 1, 0)
    m.put(W + 0x42, 8, 0x0102000001000000)
    m.write(W + 0xC, bytes(0x28)); m.write(W + 0x4C, bytes(0x20))
    m.put(W + 4, 1, 1); m.put(W + 0x34, 2, 0xFF05); m.put(W + 0x6C, 4, 0)
    m.put(W, 4, src); m.put(W + 8, 4, ident); m.put(W + 0x36, 1, 0)
    m.call_void(m.main + 0x1151258, m.u64(m.u64(o + 0x78) + 0xE20), x29 - 0x38, W)


@lifted(0x114A094)
def end_of_turn_conditions(m, o, out, *_):
    """For each condition kind (0x24, then 0x3c69dd0's list) and each member of 0x114a904's list not down
    and not in position 10: vf 0x570 of the party member ticks the condition (command 0x19 (id, kind));
    one that ended with a message (0x114a970) is reported (0x114aab0) and gets its kind's follow-up;
    otherwise the amount vf 0x428 checked by 0x114b630 and 0x114b9a4 is applied through 0x114af54 (with
    the kind's text and message head), then the kind's after-step. Stops when [[[o+0x40]+0x28]] reads 8,
    or after the list once 0x114a808 and 0x13603fc both hold; out = 0x114a934(o) & 1."""
    m.put(out, 1, 0)
    with m.frame(0x200) as sp:
        x29 = sp + 0x190
        lst, X, Y, V, Z, res = sp + 0x18, x29 - 0xC0, x29 - 0xC4, x29 - 0xB0, x29 - 0x30, x29 - 0x38
        m.call_void(m.main + 0x1143D84, lst)
        m.call_void(m.main + 0x114A904, o, lst)
        k = 0
        while True:
            kind = _EOT_KINDS[k]
            n = m.u8(lst + 0xA6)
            m.put(lst + 0xA8, 1, 0)
            while n:
                i = m.u8(lst + 0xA8)
                m.put(lst + 0xA8, 1, i + 1)
                b = m.u64(lst + 8 * i)
                if not b:
                    break
                _eot_member(m, o, b, kind, X, Y, V, Z, res)
                if m.u8(m.u64(m.u64(o + 0x40) + 0x28)) == 8 or m.u8(lst + 0xA8) >= m.u8(lst + 0xA6):
                    break
            k += 1
            if m.call(m.main + 0x114A808, o) & 1:
                if m.call(m.main + 0x13603FC, o) & 1 or k > 0x2C:
                    break
            elif k > 0x2C:
                break
        m.put(out, 1, m.call(m.main + 0x114A934, o) & 1)


def _eot_member(m, o, b, kind, X, Y, V, Z, res):
    if m.vcall(b, 0x200) & 1:
        return
    if m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), m.vcall(b, 0x98) & M32) & 0xFF == 0xA:
        return
    m.put(X + 8, 8, 0); m.put(X, 4, 0)
    q = m.u64(o + 0x20)
    ident = m.vcall(b, 0x98) & M32
    pm = m.call(m.main + 0xF21C94, m.u64(m.u64(m.u64(q + 0x20) + 0x10) + 0x30), ident)
    ticked = m.vcall(pm, 0x570, kind, X, Y) & 1
    m.call_void(m.main + 0x119AFF0, m.u64(q + 0x18), 0x19, ident, kind)
    if not ticked:
        return
    if m.u8(Y):
        m.write(Z, bytes(0x24))
        if m.call(m.main + 0x114A970, kind, X, m.vcall(b, 0x98) & M32, 0, Z) & 1:
            m.put(V + 4, 1, 0)
            m.write(V + 8, bytes(0x24))
            m.put(V, 4, m.vcall(b, 0x98))
            m.write(V + 8, m.read(Z, 0x24))
            m.call_void(m.main + 0x114AAB0, m.u64(m.u64(o + 0x78) + 0xD80), res, V)
        if kind in _EOT_ENDED:
            fn, with_x = _EOT_ENDED[kind]
            m.call_void(m.main + fn, o, b, *((X,) if with_x else ()))
        return
    if m.vcall(b, 0x200) & 1:
        return
    amount = m.vcall(b, 0x428, kind, m.call(m.main + 0x114ACBC, o)) & M32
    if amount and not (m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49C) >> 1 & 1 and m.vcall(b, 0x510, 0x19) & 1):
        amount = m.call(m.main + 0x114B630, m.u64(o + 0x38), b, kind, amount) & M32
        arg = (0x0029280000002627 >> (8 * (kind - 4))) & M32 if 0 <= kind - 4 < 7 else 0
        if amount and m.call(m.main + 0x114B9A4, m.u64(m.u64(m.u64(o + 0x78) + 0x17A0) + 0x38), b,
                             amount, arg) & 1:
            if kind in _EOT_DAMAGE:
                text, extra, head = _EOT_DAMAGE[kind]
                m.call_void(m.main + 0x114ADE8, m.u64(o + 0x20), b, text)
                v = m.vcall(b, 0x240, kind)
                m.write(Z, bytes(0x24))
                m.put(Z, 2, head)
                m.put(Z + 2, 2, 0x82); m.put(Z + 4, 4, m.vcall(b, 0x98))
            else:
                if kind == 0x2E:
                    m.call_void(m.main + 0x114ADE8, m.u64(o + 0x20), b, 0x98)
                v = m.vcall(b, 0x240, kind)
                m.write(Z, bytes(0x24))
                extra = 0
                if kind == 0x2E:
                    m.put(Z, 2, 0x7D)
                    m.put(Z + 2, 2, 0x102); m.put(Z + 4, 4, m.vcall(b, 0x98)); m.put(Z + 8, 4, 0x360)
            v0 = v[0] if isinstance(v, tuple) else v
            m.put(V + 0x18, 8, Z); m.put(V, 8, b); m.put(V + 8, 4, amount); m.put(V + 0x10, 4, v0)
            m.put(V + 0xC, 1, extra); m.put(V + 0x20, 1, 1)
            m.call_void(m.main + 0x114AF54, m.u64(m.u64(o + 0x78) + 0x17C0), res, V)
    if kind == 0x30:
        _eot_kind_30(m, o, b, Z + 0x30)
    elif kind in _EOT_AFTER:
        m.call_void(m.main + _EOT_AFTER[kind], o, b)


@lifted(0x114335C)
def end_of_turn_conditions_of(m, o, *_):
    """0x114a094 on 0x114338c([o+0x78]); its out byte."""
    with m.frame(0x10) as f:
        m.call_void(m.main + 0x114A094, m.call(m.main + 0x114338C, m.u64(o + 0x78)), f, f + 8)
        return m.u8(f)


@lifted(0x1149510)
def hp_rule_reached(m, x, *_):
    """By the setup's rule word [[[x]+0x38]+0x498]: bit 32 (and member 1's vf 0x90(0x3fd, 0)) or bit 33:
    whether member 1 (0xfa0028) has round(vf 0x560(6) * vf 0x110 / 100) >= vf 0x108 (u16 values)."""
    bits = m.u64(m.u64(m.u64(x) + 0x38) + 0x498)
    if bits >> 32 & 1:
        p = m.call(m.main + 0xFA0028, m.u64(m.u64(x + 8) + 0x30), 1, 0)
        if not m.vcall(p, 0x90, 0x3FD, 0) & 1:
            return 0
    elif bits >> 33 & 1:
        p = m.call(m.main + 0xFA0028, m.u64(m.u64(x + 8) + 0x30), 1, 0)
    else:
        return 0
    pct = m.vcall(p, 0x560, 6) & M32
    prod = pct * (m.vcall(p, 0x110) & 0xFFFF) & M32
    q = prod // 100
    if prod - q * 100 > 0x31:
        q += 1
    return int(q >= m.vcall(p, 0x108) & 0xFFFF)


def _step(m, o):
    s = m.u64(o + 0x40) + 0x88
    m.put(s, 1, m.u8(s) + 1)


def _sides_flag(m, o):
    """Whether one of the first four entries ([[o+0x68]+0x5c], stride 8, count +0x7c) reads 1."""
    t = m.u64(o + 0x68)
    return any(i <= 3 and m.u8(t + 0x5C + 8 * i) == 1 for i in range(m.u32(t + 0x7C)))


@lifted(0x11428A4)
def turn_end_steps(m, o, *_):
    """The end-of-turn state machine, resumable at the step byte [[o+0x40]+0x88] (0..0x16): commands 0xb2
    / 0xc5, 0x11502bc, the raid faint pass (kind 0xf4) or 0x1142f98, 0x1145240, 0x1143158, faint passes
    0x99 / 0x9a / 0x9b, 0x114335c, 0x114318c, 0x1142f64, 0x1142d98, the rule 0x49c bit 1 step; each check
    of 0x114a808, the battle state 8 and [[o+0x50]+0x1b] can end it. The result written to
    [[o+0x40]+0x28] is 7 when 0x114a808 holds, else by the exit (0x0000000805060104 >> 8 * code)."""
    q = m.u64(o + 0x20)
    raid = m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x499) >> 2 & 1
    state = m.u64(o + 0x40)

    def over():
        return m.call(m.main + 0x114A808, o) & 1

    def ended():
        return m.u8(m.u64(m.u64(o + 0x40) + 0x28)) == 8

    def quit_flag():
        return m.u8(m.u64(o + 0x50) + 0x1B)

    def faint(kind):
        with m.frame(0x10) as f:
            m.put(f + 8, 2, kind)
            m.call_void(m.main + 0x11449F4, m.u64(m.u64(o + 0x78) + 0x18C0), f, f + 8)
            return m.u8(f)

    def run(s):
        """The steps from s on; returns the exit code (None: no result written)."""
        if s > 0x16:
            return None
        if s <= 0:
            m.call_void(m.main + 0x119AFF0, m.u64(q + 0x18), 0xB2, 0); _step(m, o)
        if s <= 1:
            m.call_void(m.main + 0x11502BC, o); _step(m, o)
        if s <= 2:
            _step(m, o)
            if m.call(m.main + 0x1143624, o) & 1:
                faint(0xF4)
                if quit_flag():
                    return 1
                return 2 if _sides_flag(m, o) else None
        if s <= 3:
            if raid:
                m.call_void(m.main + 0x119AFF0, m.u64(q + 0x18), 0xC5, 0)
            _step(m, o)
            if m.call(m.main + 0x1142F98, o) & 1:
                return 0
        for at, body in ((4, None), (5, "quit_1145240"), (6, 0x1143158), (7, 0x99), (8, None), (9, "quit"),
                         (10, 0x114335C), (11, None), (12, "quit"), (13, 0x114318C), (14, 0x1142F64),
                         (15, "sides"), (16, "step"), (17, 0x1142D98), (18, "rule"), (19, 0x9A), (20, None),
                         (21, "quit"), (22, 0x9B)):
            if s > at:
                continue
            if body is None:                                # 4, 8, 11, 20
                _step(m, o)
                if over():
                    return None
                if ended():
                    return 4
            elif body in ("quit", "quit_1145240"):
                _step(m, o)
                if quit_flag():
                    if body == "quit_1145240":
                        m.call_void(m.main + 0x1145240, o)
                    return 1
            elif body in (0x1143158, 0x114318C, 0x1142F64, 0x1142D98):
                m.call_void(m.main + body, o); _step(m, o)
            elif body in (0x99, 0x9A):
                _step(m, o)
                if faint(body):
                    return 0
            elif body == 0x114335C:
                _step(m, o)
                if m.call(m.main + 0x114335C, o) & 1:
                    return 0
            elif body == "sides":
                _step(m, o)
                if _sides_flag(m, o):
                    return 2
            elif body == "step":
                _step(m, o)
            elif body == "rule":
                if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49C) >> 1 & 1 and \
                        m.call(m.main + 0x1149510, m.u64(m.u64(o + 0x10) + 0x330)) & 1:
                    m.call_void(m.main + 0x11519AC, m.u64(m.u64(o + 0x78) + 0x1F80))
                _step(m, o)
            else:                                           # 22
                faint(0x9B); _step(m, o)
                return None
        return None

    code = run(m.u8(state + 0x88))
    if raid:
        m.call_void(m.main + 0x119AFF0, m.u64(q + 0x18), 0xC5, 1)
    if over():
        return _tail(m, m.main + 0x113FA5C, m.u64(m.u64(o + 0x40) + 0x28), 7)
    if code is None:
        return
    return _tail(m, m.main + 0x113FA5C, m.u64(m.u64(o + 0x40) + 0x28), 0x0000000805060104 >> (8 * code))


@lifted(0x113E97C)
def turn_end_of(m, o, *_):
    """0x11428a4 on 0x113e9a8([o+0x78])."""
    with m.frame(0x10) as f:
        return _tail(m, m.main + 0x11428A4, m.call(m.main + 0x113E9A8, m.u64(o + 0x78)), f, f + 8)
