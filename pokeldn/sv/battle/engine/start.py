"""The battle start: sending out each client's first members, their entry steps and events, and the start
messages."""

from pokeldn.sv.battle.engine.calls import M32, _need, _s32, _tail, _vtail
from pokeldn.sv.battle.engine.containers import _map_u8_slot_inline
from pokeldn.sv.battle.engine.events import _events_each
from pokeldn.sv.battle.engine.round import _ROUND_FORMATS
from pokeldn.sv.battle.engine.statics import _raid_class
from pokeldn.sv.battle.machine import UnliftedCall, lifted


def _copy_side_records(m, b):
    """Copy the four 10-byte records at +0x426/+0x43c/+0x452/+0x468 to +0x430/+0x446/+0x45c/+0x472
    (u64 then a byte), mark each copied (+0x43a, +0x450, +0x466) and count those with a non-zero u16
    in +0x482."""
    m.put(b + 0x482, 1, 0)
    v = m.u64(b + 0x426)
    m.put(b + 0x430, 8, v)
    m.put(b + 0x438, 1, m.u8(b + 0x42E))
    n = 1 if v & 0xFFFF else 0
    if n:
        m.put(b + 0x482, 1, n)
    for src, dst, flag, byte_src, byte_dst in ((0x43C, 0x446, 0x43A, 0x444, 0x44E), (0x452, 0x45C, 0x450, 0x45A, 0x464),
                                               (0x468, 0x472, 0x466, 0x470, 0x47A)):
        bv = m.u8(b + byte_src)
        m.put(b + flag, 1, 1)
        m.put(b + byte_dst, 1, bv)
        v = m.u64(b + src)
        m.put(b + dst, 8, v)
        if v & 0xFFFF:
            n += 1
            m.put(b + 0x482, 1, n)


@lifted(0x2D3DC58)
def reset_on_switch(m, b, *_):
    """A battler's reset when it is sent out: the side records copied (_copy_side_records), the turn
    state and the 48 handler slots cleared, the stat stages back to 6, max HP from the core (vf 0x70(0)
    times +0x3f4 / 10) with the HP adjusted to it (vf 0x2e8 / 0x2e0), then vf 0x810; flag 0x1c is
    restored through vf 0x4d8 when vf 0x4d0 had it."""
    vt = m.u64(b)
    for slot in (0x4D0, 0x568, 0x2D0, 0x580, 0x108, 0x110, 0x810, 0x2E8, 0x2E0):
        _need(m, m.u64(vt + slot))
    _need(m, m.main + 0x14807D0)
    _need(m, m.u64(m.u64(m.u64(b + 0x48)) + 0x70))
    if m.u8(b + 0x6C):
        _need(m, m.u64(vt + 0x7F0))
    flag = m.vcall(b, 0x4D0, 0x1C)
    if flag & 1:
        _need(m, m.u64(vt + 0x4D8))
    m.put(b + 0x496, 4, 0)
    m.call_void(m.main + 0x14807D0, b)
    if m.u8(b + 0x6C):
        m.vcall_void(b, 0x7F0, 0, 1, 1, 1)
        _copy_side_records(m, b)
        m.put(b + 0x47C, 1, 1)
        m.put(b + 0x6C, 1, 0)
    _copy_side_records(m, b)
    m.put(b + 0x486, 1, 0x12)
    m.put(b + 0x47C, 1, 1)
    for off in (0x435, 0x42B, 0x44B, 0x441, 0x461, 0x457, 0x477, 0x46D):
        m.put(b + off, 1, 0)
    m.put(b + 0x490, 4, 0)
    m.put(b + 0x48C, 2, 0)
    m.put(b + 0x5A0, 8, 0)
    m.vcall_void(b, 0x568)
    m.vcall_void(b, 0x2D0)
    m.put(b + 0x487, 1, 1)
    m.vcall_void(b, 0x580)
    for k in range(48):
        m.put(b + 0x88 + 0x10 * k, 8, 0)
    m.put(b + 0x3C0, 1, 0)
    m.write(b + 0x388, bytes(0x38))
    for k in range(7):
        m.put(b + 0x414 + k, 1, 6)
    m.put(b + 0x47E, 2, m.u16(b + 0x60))
    hp = m.vcall(b, 0x108) & 0xFFFFFFFF
    cur = m.vcall(b, 0x110) & 0xFFFFFFFF
    base = m.vcall(m.u64(b + 0x48), 0x70, 0) & 0xFFFF
    top = ((base * m.u16(b + 0x3F4)) & 0xFFFFFFFF) // 10
    m.put(b + 0x58, 2, top)
    top16 = top & 0xFFFF
    if cur & 0xFFFF < top16:
        m.vcall_void(b, 0x2E8, (top - cur) & 0xFFFFFFFF)
    if cur & 0xFFFF > top16 and hp & 0xFFFF > top16:
        m.vcall_void(b, 0x2E0, (hp - top) & 0xFFFFFFFF)
    m.vcall_void(b, 0x810)
    if flag & 1:
        return _vtail(m, b, 0x4D8, 0x1C)


# The battle start (message kind 17, 0x113dca8): leaves under 0x113dd68.
def _getter_at(off):
    def fn(m, o, *_):
        return m.u64(o + off)
    return fn


for _addr, _off in {0x113DDCC: 0x16E0, 0x113DEB4: 0x940, 0x113DF30: 0x1F0, 0x1146734: 0xA0, 0x114E21C: 0x13E0,
                    0x114E490: 0x68, 0x113E064: 0x1C0}.items():
    lifted(_addr)(_getter_at(_off))


@lifted(0x113DF48)
def start_condition_message(m, o, *_):
    """When 0x13616e4 answers v: request 0x1154148 (on [[o+0x78]+0xbe0]) with record {0x4b init, +4 8,
    +8 v, +9 1, +0x10 0x113e080(0)}."""
    v = m.call(m.main + 0x13616E4, m.call(m.main + 0x114E480, o)) & 0xFF
    if not v:
        return
    with m.frame(0x60) as f:
        rec = f + 0x10
        m.call_void(m.main + 0x1149604, rec)
        m.put(rec + 4, 4, 8); m.put(rec + 8, 1, v); m.put(rec + 9, 1, 1)
        p = m.call(m.main + 0x113E080, 0)
        x0, x1 = (p[0], p[1]) if isinstance(p, tuple) else (p, 0)
        m.put(rec + 0x10, 8, x0); m.put(rec + 0x18, 8, x1)
        m.call_void(m.main + 0x1154148, m.call(m.main + 0x113DFC4, m.call(m.main + 0x1361214, o)), f + 8, rec)


@lifted(0x113DFCC)
def start_weather_message(m, o, *_):
    """When the setup's byte +0x41 is set: request 0x1149ed0 (on [[o+0x78]+0x1c0]) with {v, 0xff, 0, 0,
    0x100}, then 0x1142850(q, 0) unless byte +7 of the setup's +0x3c block is set."""
    v = m.call(m.main + 0x113E058, m.call(m.main + 0x114E480, o)) & 0xFF
    if not v:
        return
    with m.frame(0x20) as f:
        m.put(f, 1, v); m.put(f + 1, 2, 0xFF); m.put(f + 4, 4, 0); m.put(f + 8, 2, 0x100)
        m.call_void(m.main + 0x1149ED0, m.call(m.main + 0x113E064, m.call(m.main + 0x1361214, o)), f + 0x18, f)
    if not m.u8(m.call(m.main + 0x113E06C, m.call(m.main + 0x114E480, o)) + 7):
        m.call_void(m.main + 0x1142850, m.call(m.main + 0x1143584, o), 0)


@lifted(0x11468F0)
def raid_boss_start_message(m, o, *_):
    """Under rule 0x49b bit 3: when member 1 (0xfa0028) is of the class 0x46d3f08 with u16 +0x710 0x3f3 and
    byte +0x714 clear, request 0x11505c0 (on [[o+0x78]+0x1d60]) with its id."""
    if not m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49B) >> 3 & 1:
        return
    b = m.call(m.main + 0xFA0028, m.u64(m.u64(o + 0x10) + 0x30), 1, 0)
    if not _raid_class(m, b):
        return
    if m.u16(b + 0x710) != 0x3F3 or m.u8(b + 0x714):
        return
    with m.frame(0x20) as f:
        m.put(f + 0x18, 1, m.vcall(b, 0x98))
        m.call_void(m.main + 0x11505C0, m.u64(m.u64(o + 0x78) + 0x1D60), f + 8, f + 0x18)


@lifted(0x1146A08)
def rule_side_start(m, o, lst, *_):
    """Under rule 0x49c bit 1: the first member of lst on rule side 1 with vf 0x90(0x3fd, 2) runs
    0x2d1dfe4(0) and commands 0x87 / 0xc6 (3, 0)."""
    if not m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49C) >> 1 & 1:
        return
    hit = []

    def visit(b):
        if hit:
            return
        p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50),
                   m.vcall(b, 0x98) & M32)
        if p and m.u32(p) == 1 and m.vcall(b, 0x90, 0x3FD, 2) & 1:
            hit.append(b)

    n = m.u8(lst + 0xA6)
    m.put(lst + 0xA8, 1, 0)
    if n:
        b = m.u64(lst)
        m.put(lst + 0xA8, 1, 1)
        while b:
            visit(b)
            if hit:
                break
            i = m.u8(lst + 0xA8)
            if i >= m.u8(lst + 0xA6):
                break
            m.put(lst + 0xA8, 1, i + 1)
            b = m.u64(lst + 8 * i)
    if not hit:
        return
    q = m.u64(o + 0x20)
    m.call_void(m.main + 0x2D1DFE4, m.u64(m.u64(m.u64(q + 0x20) + 0x10) + 0x330), 0)
    m.call_void(m.main + 0x119AFF0, m.u64(q + 0x18), 0x87, 3, 0)
    return _tail(m, m.main + 0x119AFF0, m.u64(m.u64(o + 0x20) + 0x18), 0xC6, 3, 0)


@lifted(0x289A224)
def reset_on_entry(m, b, *_):
    """A battler's state on entering: vf 0x7f0(0, 1, 1, 1), 0x14807d0, the turn fields and the 46 per-turn
    qwords from +0xe8 cleared, +0x486 = 0x12, the stage bytes +0x414..+0x41a back to 6 (byte +0x392
    kept), then vf 0x628(0)."""
    m.vcall_void(b, 0x7F0, 0, 1, 1, 1)
    m.call_void(m.main + 0x14807D0, b)
    m.put(b + 0x496, 4, 0)
    m.vcall_void(b, 0x580)
    for off in (0x435, 0x42B, 0x44B, 0x441, 0x461, 0x457, 0x477, 0x46D):
        m.put(b + off, 1, 0)
    m.put(b + 0x490, 4, 0); m.put(b + 0x486, 1, 0x12); m.put(b + 0x48C, 2, 0)
    keep = m.u8(b + 0x392)
    for off in range(0xE8, 0x388, 0x10):
        m.put(b + off, 8, 0)
    m.put(b + 0x390, 8, 0); m.put(b + 0x3C0, 1, 0)
    for off in (0x3B8, 0x3B0, 0x3A8, 0x3A0, 0x398, 0x388):
        m.put(b + off, 8, 0)
    m.put(b + 0x392, 1, keep)
    for off in range(0x414, 0x41B):
        if m.u8(b + off) != 6:
            m.put(b + off, 1, 6)
    return _tail(m, m.u64(m.u64(b) + 0x628), b, 0)


@lifted(0x114EAB4)
def pair_with_others(m, p, pokecon, idx, members, *_):
    """For entry idx of p's u32 table (+8, stride 8, flag byte +0xc): every other flagged entry not on the
    same side (0x118ab58) is introduced both ways through the members' vf 0x4b8."""
    v = m.u32(p + 8 * (idx & 0xFF) + 8)
    if not v:
        return
    for k in range(11):
        e = p + 8 * k
        if not m.u8(e + 0xC):
            continue
        w = m.u32(e + 8)
        if not w or w == v:
            continue
        if m.call(m.main + 0x118AB58, m.u64(pokecon + 0x290), w, v) & 1:
            continue
        m.vcall_void(m.call(m.main + 0xF21C94, members, m.u32(e + 8)), 0x4B8, v)
        m.vcall_void(m.call(m.main + 0xF21C94, members, v), 0x4B8, m.u32(e + 8))


@lifted(0x114F348)
def raid_member_entered(m, o, b, *_):
    """In battle kinds 0 and 1, a member of the class 0x46d3f08 is passed to vf 0x30 of the counted
    object [o+0x130] (a reference held around the call)."""
    from pokeldn.sv.battle.engine.references import _release_ref
    if not b or m.u32(m.u64(o + 0x38) + 0x30) > 1:
        return
    if not _raid_class(m, b):
        return
    x = m.u64(o + 0x130)
    if not x:
        raise UnliftedCall("0x114f348: no object at +0x130 (the game traps)")
    if m.u32(x + 0x28) == M32:
        raise UnliftedCall("IncrementReference abort")
    m.put(x + 0x28, 4, m.u32(x + 0x28) + 1)
    m.vcall_void(x, 0x30, b)
    return _release_ref(m, x)


lifted(0x11467EC)(_getter_at(0x17E0))


@lifted(0x113DF38)
def set_flag_byte(m, p, v, *_):
    m.put(p + (v & 0xFFFF) + 8, 1, 1)


@lifted(0x113DF08)
def set_flag_of(m, o, v, *_):
    """Byte +8+v of [[o+0x10]+0x1f0] = 1."""
    return _tail(m, m.main + 0x113DF38, m.call(m.main + 0x113DF30, m.u64(o + 0x10)), v & M32)


@lifted(0x114E5DC)
def add_entered(m, lst, ident, *_):
    """Append the id byte to the list (+8, count s32 +0x28, at most 30) unless 0x114e624 finds it."""
    if m.call(m.main + 0x114E624, lst, ident) & 1:
        return
    n = m.s(lst + 0x28, 4)
    if n > 0x1D:
        return
    m.put(lst + 8 + n, 1, ident)
    m.put(lst + 0x28, 4, m.u32(lst + 0x28) + 1)


@lifted(0x114EE74)
def mark_entered(m, o, ident, *_):
    """Byte +0xb of the entry holding ident among the six u32s at +0x10.. (stride 0x10) of the side's
    0x60-byte record [[o+0x10]+0x250] (side by the setup's rule value, 0..4) = 1."""
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50), ident & M32)
    side = (m.s(p, 4) if p else 0)
    side = (side if side < 5 else 0) & 0xFF
    if side > 4:
        return
    base = m.u64(m.u64(o + 0x10) + 0x250) + side * 0x60
    for k in range(1, 7):
        if m.u32(base + 0x10 * k) == ident & M32:
            m.put(base + 0x10 * k + 0xB, 1, 1)
            return


@lifted(0x114EF5C)
def pair_raid_members(m, o, lst, client, *_):
    """For the members of lst from the slot's position count on (class 0x46d3f08 with vf 0xf8 0x95): the last
    able member (vf 0x208) at or after them gets vf 0x2d0; one before it pairs with that member's party
    record: vf 0x2d0 when either carries conditions 0x3f3 / 0x3fd (vf 0x88) with +0x714 set, else
    vf 0x1e8(its id)."""
    n = m.u8(lst + 0x30)
    last = 0
    k = n
    while k:
        last = (k - 1) & 0xFF
        if last == 0:
            break
        if m.vcall(m.u64(lst + 8 * last), 0x208) & 1:
            break
        k -= 1
    s = m.u64(o + 8)
    i = m.call(m.main + 0xFF9128, m.u32(s + 0x36C), m.u8(s + 0x370), client & 0xFF) & M32
    if _s32(i) >= m.u8(lst + 0x30):
        return
    while True:
        if m.u8(lst + 0x30) > i & 0xFF:
            b = m.u64(lst + 8 * (i & 0xFF))
            if b and _raid_class(m, b) and m.vcall(b, 0xF8) & 0xFFFF == 0x95:
                if _s32(i) >= last:
                    m.vcall_void(b, 0x2D0)
                else:
                    ident = m.vcall(m.u64(lst + 8 * last), 0x98) & M32
                    pm = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 8) + 0x30), ident)
                    if not pm or not _raid_class(m, pm):
                        m.vcall_void(b, 0x1E8, ident)
                    elif (m.vcall(pm, 0x88, 0x3F3) & 1 and m.u8(pm + 0x714)) or \
                            (m.vcall(pm, 0x88, 0x3F3) & 1 and m.u8(b + 0x714)) or \
                            (m.vcall(pm, 0x88, 0x3FD) & 1 and m.u8(pm + 0x714)) or \
                            (m.vcall(pm, 0x88, 0x3FD) & 1 and m.u8(b + 0x714)):
                        m.vcall_void(b, 0x2D0)
                    else:
                        m.vcall_void(b, 0x1E8, ident)
        i = (i + 1) & M32
        if not _s32(i) < m.u8(lst + 0x30):
            return


@lifted(0x113DED4)
def entered_flag_command(m, q, v, *_):
    """0x113df08([q+0x20], v), then command 0x2b (v & 0xffff)."""
    m.call_void(m.main + 0x113DF08, m.u64(q + 0x20), v & M32)
    return _tail(m, m.main + 0x119AFF0, m.u64(q + 0x18), 0x2B, v & 0xFFFF)


@lifted(0x113DEBC)
def entered_flag_0(m, x, *_):
    return _tail(m, m.main + 0x113DED4, m.call(m.main + 0x1143584, x), 0)


@lifted(0x113DE88)
def entered_flag_0_of(m, o, *_):
    with m.frame(0x10) as f:
        return _tail(m, m.main + 0x113DEBC, m.call(m.main + 0x113DEB4, m.call(m.main + 0x1361214, o)), f, f + 8)


@lifted(0x1146CDC)
def entry_events(m, o, lst, *_):
    """For each member of lst: event 0x73 (0x11470d4), then 0x74, 0x72 and 0xd7 (0x1146e98), then event
    0x75 over the list (0x1147ad8) and 0x1147314."""
    _events_each(0x73, 0x11470D4)(m, o, lst)
    for ev in (0x74, 0x72, 0xD7):
        _events_each(ev)(m, o, lst)
    m.call_void(m.main + 0x1147AD8, m.call(m.main + 0x1146E90, o), lst)
    return _tail(m, m.main + 0x1147314, m.call(m.main + 0x1146E90, o))


@lifted(0x114E848)
def entered_mark_command(m, o, b, *_):
    """0x114ee74 with b's id (vf 0x2d8 when vf 0x3b8 holds, else vf 0x98), then command 0x4e (id)."""
    ident = (m.vcall(b, 0x2D8) if m.vcall(b, 0x3B8) & 1 else m.vcall(b, 0x98)) & M32
    m.call_void(m.main + 0x114EE74, m.u64(o + 0x20), ident)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x4E, ident)


@lifted(0x114ECEC)
def pair_raid_members_of(m, o, client, *_):
    """When client slot `client` takes part (0xe7e2a0): 0x114ef5c on its party list, then command 0x3d."""
    pc = m.u64(m.u64(o + 0x10) + 0x290)
    s = m.u64(pc + 8)
    if not m.call(m.main + 0xE7E2A0, m.u32(s + 0x36C), m.u8(s + 0x370), client & 0xFF) & 1:
        return
    x8 = m.u64(m.u64(o + 0x20) + 0x10)
    c = client & M32
    lst = 0 if c > 4 else m.u64(x8 + 0x30) + c * 0x38 + 0x28
    m.call_void(m.main + 0x114EF5C, m.u64(x8 + 0x290), lst, c)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x3D, client & 0xFF)


@lifted(0x114E19C)
def entry_steps_of(m, o, lst, *_):
    with m.frame(0x10) as f:
        m.put(f + 8, 8, lst)
        m.call_void(m.main + 0x114673C, m.call(m.main + 0x1146734, m.call(m.main + 0x1361214, o)), f, f + 8)


@lifted(0x114E1CC)
def send_out_of(m, o, ids, a, b, c, *_):
    """0x114e268 on [[o+0x78]+0x13e0] with bytes {a, b, c}; the id it answers joins the set ids."""
    with m.frame(0x20) as f:
        m.put(f + 0x10, 1, a); m.put(f + 0x11, 1, b); m.put(f + 0x12, 1, c)
        m.call_void(m.main + 0x114E268, m.call(m.main + 0x114E21C, m.call(m.main + 0x1361214, o)), f + 8, f + 0x10)
        m.call_void(m.main + 0x114E224, ids, m.u32(f + 8))


@lifted(0x114673C)
def entry_steps(m, o, _x, idsp, *_):
    """The steps after sending out: 0x11468f0, the standing members in the id set [idsp] (0x11474b0),
    0x1146a08, sorted by speed (0x11467bc), events 0x70 / 0x71 (0x11467f4, 0x114686c) and 0x1146cdc."""
    m.call_void(m.main + 0x11468F0, o)
    with m.frame(0xB0) as lst:
        m.call_void(m.main + 0x1143D84, lst)
        m.call_void(m.main + 0x11474B0, o, lst, m.u64(idsp))
        for fn in (0x1146A08, 0x11467BC, 0x11467F4, 0x114686C, 0x1146CDC):
            m.call_void(m.main + fn, o, lst)


@lifted(0x114E98C)
def place_in_battle(m, o, client, idx, dest, w, *_):
    """Move party entry idx of client slot `client` to dest (0x114ea98) when they differ, then vf 0x5d0(w)
    and vf 0x5d8 on it, give it its position (0xc9c090) in the position table [[o+0x10]+0xf0] (+8 by
    position, map +0x60), pair it with the others (0x114eab4) and tail 0x114eb70(o, b)."""
    c = client & 0xFF
    lst = 0 if c > 4 else m.u64(m.u64(o + 0x10) + 0x30) + c * 0x38 + 0x28
    if idx & 0xFF != dest & 0xFF:
        m.call_void(m.main + 0x114EA98, lst, idx, dest)
    b = m.u64(lst + 8 * (idx & 0xFF))
    m.vcall_void(b, 0x5D0, w & M32)
    m.vcall_void(b, 0x5D8)
    pos = m.call(m.main + 0xC9C090, m.u64(m.u64(o + 0x10) + 0x290), client & M32, idx & M32) & M32
    pc = m.u64(o + 0x10)
    table = m.u64(pc + 0xF0)
    ident = m.vcall(b, 0x98) & M32
    with m.frame(0x10) as k:
        m.put(k, 4, ident)
        m.put(table + 8 * (pos & 0xFF) + 8, 4, ident)
        m.put(_map_u8_slot_inline(m, table + 0x60, k), 1, pos)       # 0xf785a8
    m.call_void(m.main + 0x114EAB4, table, pc, pos, m.u64(pc + 0x30))
    return _tail(m, m.main + 0x114EB70, o, b)


@lifted(0x114E7EC)
def place_in_battle_command(m, o, client, idx, dest, w, *_):
    """0x114e98c on [o+0x20], then command 0x16 (client, idx, dest bytes, w & 0xffff)."""
    m.call_void(m.main + 0x114E98C, m.u64(o + 0x20), client, idx, dest, w)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x16, client & 0xFF, idx & 0xFF, dest & 0xFF, w & 0xFFFF)


@lifted(0x114E268)
def send_out(m, o, out, args, *_):
    """Send out entry args[1] of client slot args[0] to place args[2]: the slot's start step (0x114ecec on
    a first turn by 0x114e550, else 0x11500d0), triggers 1 / 0x1f for the leaving member and 0x20 for
    *out, the placement 0x114e7ec, then for the entering member its item and ability handlers (0x114f1ec,
    0x114e798), entry handler (0x114e578), 0x114f348, the entered list (0x114e5dc) and mark (0x114e848);
    *out = its id."""
    first = m.call(m.main + 0x114E550, m.call(m.main + 0x114E480, o), m.call(m.main + 0x1482534, o)) & 1
    q = m.call(m.main + 0x1143584, o)
    m.call_void(m.main + (0x114ECEC if first else 0x11500D0), q, m.u8(args))
    lst = m.call(m.main + 0x114E498, o, m.u8(args))
    leaving = m.vcall(m.call(m.main + 0x114E4C0, lst, m.u8(args + 2)), 0x98) & M32
    m.call_void(m.main + 0x114E4E0, o, 1, leaving)
    m.call_void(m.main + 0x114E4E0, o, 0x1F, leaving)
    m.call_void(m.main + 0x114E4E0, o, 0x20, m.u32(out))
    q = m.call(m.main + 0x1143584, o)
    a2, a1, a0 = m.u8(args + 2), m.u8(args + 1), m.u8(args)
    w = m.call(m.main + 0x114E528, o, 0)
    m.call_void(m.main + 0x114E7EC, q, a0, a1, a2, w)
    b = m.call(m.main + 0x114E4C0, m.call(m.main + 0x114E498, o, m.u8(args)), m.u8(args + 1))
    ident = m.vcall(b, 0x98) & M32
    q = m.call(m.main + 0x1143584, o)
    m.call_void(m.main + 0x114F1EC, q, m.call(m.main + 0x1146E90, o), b)
    m.call_void(m.main + 0x114E798, m.call(m.main + 0x1143584, o), m.vcall(b, 0x98) & M32)
    m.call_void(m.main + 0x114E578, m.call(m.main + 0x1143584, o), m.vcall(b, 0x98) & M32)
    m.call_void(m.main + 0x114F348, m.call(m.main + 0x114E480, o), b)
    m.call_void(m.main + 0x114E5DC, m.call(m.main + 0x114E490, m.call(m.main + 0x113DE68, o)), ident)
    m.call_void(m.main + 0x114E848, m.call(m.main + 0x1143584, o), b)
    if m.call(m.main + 0x114E488, m.call(m.main + 0x114E480, o)) & 1:
        x = m.call(m.main + 0x113DF30, m.call(m.main + 0x1482534, o))
        if m.call(m.main + 0x147992C, x, 0) & 1:
            m.call_void(m.main + 0x281C364, m.call(m.main + 0x11468E8, o), ident)
    m.put(out, 4, ident)


@lifted(0x114DC48)
def send_out_all(m, o, *_):
    """Send out every client slot's first members (0..4; per slot as many as its positions, 0xff9128),
    skipping empty or down ones: 0x114e1cc(o, ids, client, i, i) into an id set (0x11466dc), then the
    entry steps 0x114e19c on that set."""
    with m.frame(0x40) as ids:
        m.call_void(m.main + 0x11466DC, ids)
        for c in range(5):
            pc = m.u64(o + 0x10)
            parties = m.u64(pc + 0x30)
            s = m.u64(m.u64(pc + 0x290) + 8)
            n = m.call(m.main + 0xFF9128, m.u32(s + 0x36C), m.u8(s + 0x370), c) & M32
            i = 0
            while i != n:
                if m.u8(parties + 0x38 * c + 0x58) > i & 0xFF:
                    b = m.u64(parties + 0x38 * c + 0x28 + 8 * (i & 0xFF))
                    if b and not m.vcall(b, 0x200) & 1:
                        m.call_void(m.main + 0x114E1CC, o, ids, c, i, i)
                i = (i + 1) & M32
        m.call_void(m.main + 0x114E19C, o, ids)


@lifted(0x113DDD4)
def battle_start(m, o, out, *_):
    """The battle start: clear the start flag ([[o+0x40]+0x28] byte), weather / field and condition start
    messages (0x113dfcc, 0x113df48), send everyone out (0x114dc48); unless the flag got set, event 0x77
    (0x1146b30) and the entered flag 0 (0x113de88); *out = the flag."""
    flag = lambda: m.call(m.main + 0x113DE70, m.call(m.main + 0x113DE68, o))
    m.call_void(m.main + 0x1145AA8, flag())
    m.call_void(m.main + 0x113DFCC, o)
    m.call_void(m.main + 0x113DF48, o)
    m.call_void(m.main + 0x114DC48, o)
    if not m.call(m.main + 0x113DE78, flag()) & 1:
        m.call_void(m.main + 0x1146B30, m.call(m.main + 0x1146E90, o))
    if not m.call(m.main + 0x113DE78, flag()) & 1:
        m.call_void(m.main + 0x113DE88, o)
    m.put(out, 1, m.call(m.main + 0x1145AA0, flag()))


@lifted(0x113DD9C)
def battle_start_of(m, o, *_):
    with m.frame(0x10) as f:
        m.call_void(m.main + 0x113DDD4, m.call(m.main + 0x113DDCC, m.u64(o + 0x18)), f, f + 8)
        return m.u8(f)


@lifted(0x113DD68)
def battle_start_message(m, o, out, *_):
    """0xfaf048 on [o+0x10], then *out = 0x113dd9c(o)."""
    m.call_void(m.main + 0xFAF048, m.u64(o + 0x10))
    m.put(out, 1, m.call(m.main + 0x113DD9C, o))


@lifted(0x113DCA8)
def build_battle_start(m, o, out, size, count, *_):
    """Message kind 17, the battle start: queue reset (length 0, formats from 0x3c6abe4), 0x113dd68 on
    [o+8]; *out = the queue bytes ([o+0x10]+0x70), *size = its length, *count += 1, the start flag at
    o+0xc4a5 and o+0xc4a3 cleared."""
    q = m.u64(o + 0x10)
    m.put(q + 0x68, 8, 0)
    for i, fmt in enumerate(_ROUND_FORMATS):
        m.put(m.call(m.main + 0xFAF09C, q, m.main + 0x3C6ABE4 + 4 * i), 1, fmt)
    with m.frame(0x10) as f:
        m.call_void(m.main + 0x113DD68, m.u64(o + 8), f)
        flag = m.u8(f)
    m.put(out, 8, m.u64(o + 0x10) + 0x70)
    m.put(size, 4, m.u32(m.u64(o + 0x10) + 0x68))
    m.put(count, 8, m.u64(count) + 1)
    m.put(o + 0xC4A5, 1, flag)
    m.put(o + 0xC4A3, 1, 0)
