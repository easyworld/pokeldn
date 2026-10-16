"""Move targets: the positions a target kind reaches, the target list a move builds, and the passes that
drop targets from it."""

from pokeldn.sv.battle.engine import flatbuffer as fb
from pokeldn.sv.battle.engine.calls import M32, _need, _s32, _tail
from pokeldn.sv.battle.engine.members import _clear_members, _standing_of, clear_member_list
from pokeldn.sv.battle.engine.raid import _raid_id_inline
from pokeldn.sv.battle.engine.slots import SIDE, _flag_2fd
from pokeldn.sv.battle.machine import Pair, UnliftedCall, lifted


@lifted(0x157B588)
def walk_targets_48(m, o, b, arg, lst, *_):
    """Walk a member list (cursor +0xa8): each member 0x157b674 accepts gets command 0x48 queued
    (0x157eba0) and is handed to 0x157bf08."""
    m.put(lst + 0xA8, 1, 0)
    if m.u8(lst + 0xA6) == 0:
        return
    t = m.u64(lst)
    m.put(lst + 0xA8, 1, 1)
    while t:
        if m.call(m.main + 0x157B674, o, b, t, arg) & 1:
            q = m.call(m.main + 0x1143584, o)
            a = m.vcall(b, 0x98) & 0xFFFFFFFF
            c = m.vcall(t, 0x98) & 0xFFFFFFFF
            m.call_void(m.main + 0x157EBA0, q, a, 0x48, c)
            m.call_void(m.main + 0x157BF08, lst, t)
        i = m.u8(lst + 0xA8)
        if i >= m.u8(lst + 0xA6):
            return
        m.put(lst + 0xA8, 1, i + 1)
        t = m.u64(lst + 8 * i)


@lifted(0x157B7A4)
def walk_targets_157e064(m, o, _unused, args, *_):
    """For each member of the list args[2] (cursor +0xa8) that 0x157c614 rejects and 0x157e064 accepts
    (move u16 *args[0]): hand it to 0x157bf08, and queue 0x157ef30 unless 0x157ea90 > 1 with byte +0x13
    of args[0] set, or 0x157e064 cleared its flag."""
    lst = m.u64(args + 0x10)
    m.put(lst + 0xA8, 1, 0)
    while True:
        lst = m.u64(args + 0x10)
        i = m.u8(lst + 0xA8)
        if i >= m.u8(lst + 0xA6):
            return
        m.put(lst + 0xA8, 1, i + 1)
        t = m.u64(lst + 8 * i)
        if t == 0:
            return
        if m.call(m.main + 0x157C614, m.u64(o + 0x10), m.u64(args + 8), t) & 1:
            continue
        with m.frame(0x10) as flag:
            m.put(flag, 1, 1)
            ok = m.call(m.main + 0x157E064, m.u64(o + 0x38), m.u64(args + 8), t, m.u16(m.u64(args)), flag) & 1
            if not ok:
                continue
            mv = m.u64(args)
            many = (m.call(m.main + 0x157EA90, m.u64(args + 0x10)) & 0xFFFFFFFF) > 1
            strict = m.u8(mv + 0x13) != 0
            m.call_void(m.main + 0x157BF08, m.u64(args + 0x10), t)
            if (many and strict) or m.u8(flag) == 0:
                continue
        q = m.call(m.main + 0x1143584, o)
        ident = m.vcall(m.u64(args + 8), 0x98) & 0xFFFFFFFF
        m.call_void(m.main + 0x157EF30, q, ident, t, m.u16(m.u64(args)))


@lifted(0x173C268)
def redirect_lone_target(m, o, ctx, b, arg, _p5, lst, *_):
    """When the attacker's side holds more than one position and the list holds one target that is
    out of the battle (vf 0x200) and not kept by 0x17d5d98 (nor the raid battler in a raid): drop it
    (0x157bf08) and add the target 0x1138ae0 picks (kind 6) instead. 0 when no target replaces it."""
    pokecon = m.u64(o + 0x10)
    owner = m.u64(pokecon + 0x290)
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50),
               m.vcall(b, 0x98) & 0xFFFFFFFF)
    v = 0
    if p:
        w = m.s(p, 4)
        v = w & 0xFF if w < 5 else 0
    s = m.u64(owner + 8)
    pos = m.call(m.main + 0x1365B00, m.u32(s + 0x36C), m.u8(s + 0x370), v, 0) & 0xFF
    s = m.u64(owner + 8)
    mode = m.u32(s + 0x36C)
    side = SIDE[mode][pos] if mode in SIDE and pos <= 4 else 2
    n = m.call(m.main + 0x113AA70, mode, m.u8(s + 0x370), side)
    if n & 0xFE == 0 or m.u8(lst + 0xA6) != 1:
        return 1
    t = m.u64(lst)
    if m.vcall(t, 0x200) & 1 == 0:
        return 1
    if m.call(m.main + 0x17D5D98, o, b, t) & 1:
        return 1
    if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x499) >> 2 & 1:
        rec = m.u64(m.u64(o + 0x10) + 0x310)
        mine = m.vcall(b, 0x98) & 0xFFFFFFFF
        raid = m.u32(rec + 0x18)
        if m.u8(m.u64(m.u64(rec + 8) + 0x38) + 0x499) >> 2 & 1 and raid == 0:
            parties = m.u64(m.u64(rec + 0x10) + 0x30)
            if m.u8(parties + 0x90) == 0:
                raid = 0
            elif m.u64(parties + 0x60):
                raid = m.vcall(m.u64(parties + 0x60), 0x98) & 0xFFFFFFFF
                m.put(rec + 0x18, 4, raid)
        if raid == mine:
            return 0
    m.call_void(m.main + 0x157BF08, lst, t)
    with m.frame(0x30) as f:
        r = m.call(m.main + 0x1138AE0, o, f, 6, b, arg) & 0xFFFFFFFF
        if r & 0xFF == 0:
            return 0
        new = m.u64(f) if r & 0xFF == 1 else m.call(m.main + 0x2886E3C, o, f, r)
    if new == 0:
        return 0
    n = m.u8(lst + 0xA6)
    if n > 10 or any(m.u64(lst + 8 * i) == new for i in range(n)):
        return 1
    m.put(lst + 8 * n, 8, new)
    m.put(lst + 0x84 + m.u8(lst + 0xA6), 1, 0)
    m.put(lst + 0x58 + 2 * m.u8(lst + 0xA6), 2, 0)
    m.put(lst + 0x6E + 2 * m.u8(lst + 0xA6), 2, 0)
    n = (m.u8(lst + 0xA6) + 1) & 0xFF
    m.put(lst + 0xA6, 1, n)
    if m.u8(lst + 0xA7) < n:
        m.put(lst + 0xA7, 1, n)
    return 1


def _mode2_target(c, e):
    """0xfa6f4c."""
    c &= 0xFF
    if c <= 3:
        return int(e == 1)
    if c == 4:
        return int(e != 0)
    if c == 5:
        return int(e & 0xFFFFFFFD != 0)
    if c == 6:
        return 1 if e > 3 else int(e & 0xF == 1)
    return 0


def _mode1_target(m, flag, c, e):
    """0xfad7c4."""
    c &= 0xFF
    se = _s32(e)
    if c == 0:
        if se > 4:
            return 0
        return _flag_2fd(m, e) if flag & 0xFF else int(e == 1)
    if c in (2, 4):
        return int(se < 5 and e & 0xFFFFFFFD == 1)
    if c in (3, 5):
        return int(se < 5 and e & 0xFFFFFFFB != 0)
    return 0


@lifted(0xFA5F84)
def target_allowed(m, mode, flag, c, d, e, *_):
    """Whether target class e fits the rule c in battle mode `mode` (0, 1 with flag, 2)."""
    mode &= 0xFFFFFFFF; e &= 0xFFFFFFFF
    if mode == 2:
        return _mode2_target(c, e)
    if mode == 1:
        return _mode1_target(m, flag, c, e)
    if mode != 0 or _s32(e) > 4:
        return 0
    if flag & 0xFF and d & 0xFFFFFFFF == 3:
        return _flag_2fd(m, e)
    return int(e == 1)


@lifted(0x287F478)
def target_allowed_for(m, o, b, *_):
    """Tail call of 0xfa5f84 with the battle's mode, flags and the battler's target class (0x1589a40)."""
    a = m.call(m.main + 0x144B6D4, m.u64(o + 0x10))
    f = m.call(m.main + 0x1365ADC, m.u64(o + 8))
    c = m.call(m.main + 0x281B234, m.u64(o + 0x10))
    e = m.call(m.main + 0x1589A40, o, m.vcall(b, 0x98) & 0xFFFFFFFF)
    d = m.call(m.main + 0x144B6C8, m.u64(o + 8))
    return target_allowed(m, a, f, c, d, e)


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


@lifted(0x2842270)
def target_slot(m, o, out, req, *_):
    """out = 0x10e21c0 for the entry of battler [req] (0x13813f4) and the move u16 at req+4."""
    e = m.call(m.main + 0x13813F4, o, m.u32(req))
    x = m.call(m.main + 0x11440E8, m.call(m.main + 0x1482534, o))
    y = m.call(m.main + 0x114E480, o)
    z = m.call(m.main + 0x1482534, o)
    m.put(out, 1, m.call(m.main + 0x10E21C0, y, z, e, m.u16(req + 4), x))


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


# Side class per battle mode 0, 1, 2 and opposing position 0..4 (0x3c6a450, 0x3c6a455, 0x3c6a45a).
_OPPOSING_SIDE = ((0, 1, 2, 2, 2), (0, 1, 0, 1, 2), (0, 1, 0, 0, 0))


def _add_opposing(m, o, pokecon, parties, ident, pos, lst):
    """Kind 5 for a non-raid attacker: every position of the side class the attacker's opposing client
    (0x1365b00) maps to, its member (0x173da74) appended."""
    from pokeldn.sv.battle.engine.flow import add_member
    st = m.u64(pokecon + 0x290)
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(st + 8) + 0x50), ident)
    v = m.s(p, 4) if p else 0
    k = v & 0xFF if v < 5 else 0
    setup = m.u64(st + 8)
    r = m.call(m.main + 0x1365B00, m.u32(setup + 0x36C), m.u8(setup + 0x370), k, 0) & 0xFF
    setup = m.u64(st + 8)
    mode = m.u32(setup + 0x36C)
    side = _OPPOSING_SIDE[mode][r] if mode <= 2 and r <= 4 else 2
    n = m.call(m.main + 0x113AA70, mode, m.u8(setup + 0x370), side) & M32
    for j in range(n):
        e = m.call(m.main + 0x173DA74, o, parties, pos, j)
        if e:
            add_member(m, lst, e)


@lifted(0x173DB04)
def nth_position_off_side(m, st, pos, nth, *_):
    """The nth position (0x113a588) on the side opposite position pos's (0x3b72710: class 0 <-> 1, else 2)."""
    setup = m.u64(st + 8)
    mode, rule = m.u32(setup + 0x36C), m.u8(setup + 0x370)
    c = m.call(m.main + 0xC9C750, mode, rule, pos) & 0xFF
    side = (1, 0)[c] if c <= 1 else 2
    x = m.call(m.main + 0x113AF40, mode, rule, side, 0)
    return _tail(m, m.main + 0x113A588, mode, rule, x, nth)


@lifted(0x173DA74)
def nth_member_off_side(m, o, parties, pos, nth, *_):
    """The party member at the position 0x173db04 gives, or 0."""
    st = m.u64(m.u64(o + 0x10) + 0x290)
    q = m.call(m.main + 0x173DB04, st, pos, nth)
    with m.frame(0x10) as out:
        m.call_void(m.main + 0x1153868, m.u64(m.u64(o + 0x10) + 0x290), q, out + 4, out + 8)
        client, idx = m.u8(out + 4), m.u8(out + 8)
    if client > 4 or idx >= m.u8(parties + client * 0x38 + 0x58):
        return 0
    return m.u64(parties + client * 0x38 + idx * 8 + 0x28)


@lifted(0x173F110)
def pick_targets_raid(m, o, a1, pokecon, attacker, a4, move, other, lst, done, *_):
    """The target list of a move in a raid: *done = 0, then by the move's target kind (u8 move+0xa,
    jump table 0x3c6a58c) members go into lst through the member-list append (at most 11, once each);
    kinds 0/3, 9 and 13 set *done."""
    from pokeldn.sv.battle.engine.flow import add_member
    kind = m.u8(move + 0xA)
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
    pos = m.call(m.main + 0xFE161C, m.u64(pokecon + 0x290), aid()) & 0xFF
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
    elif kind == 5 and raid() != aid():
        _add_opposing(m, o, pokecon, parties, aid(), pos, lst)
    elif kind in (4, 5):
        if raid() != aid():
            for p in _standing_of(m, a1, pokecon):
                if flag:
                    if not m.call(m.main + 0x17D5D98, o, attacker, p) & 1 and m.vcall(p, 0x98) & 0xFFFFFFFF != aid():
                        add_member(m, lst, p)
                elif m.vcall(p, 0x98) & 0xFFFFFFFF != aid() and p:
                    add_member(m, lst, p)
        elif m.u8(move + 0x14):
            for p in _standing_of(m, a1, pokecon):
                if m.vcall(p, 0x98) & 0xFFFFFFFF != aid() and p:
                    add_member(m, lst, p)
        else:
            p = m.call(m.main + 0x2886D48, o)
            if p:
                add_member(m, lst, p)
    elif kind == 6:
        for p in _standing_of(m, a1, pokecon):
            r = m.call(m.main + 0x17D5D98, o, attacker, p) & 1
            if flag:
                if r and m.vcall(p, 0x98) & 0xFFFFFFFF == aid():
                    add_member(m, lst, p)
            elif p and r:
                add_member(m, lst, p)
    elif kind == 8:
        for p in _standing_of(m, a1, pokecon):
            if raid() == aid():
                t = m.call(m.main + 0x2886D48, o)
                if t:
                    add_member(m, lst, t)
                add_member(m, lst, attacker)
            elif flag:
                if m.vcall(p, 0x98) & M32 == aid() or not m.call(m.main + 0x17D5D98, o, attacker, p) & 1:
                    add_member(m, lst, p)
            elif p:
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


@lifted(0x288818C)
def mark_bits(m, o, out, row, bits, *_):
    """For each of 19 indexes set in the bit field `bits` (byte count, then the bytes) that 0x28883a0
    accepts, set out[row*0x13 + i]; 1 if any was set."""
    row &= 0xFFFFFFFF
    base = out + 0x13 * (row & 0xFF)
    hit = 0
    for i in range(0x13):
        k = (i >> 3) + 1
        if k < m.u8(bits) and m.u8(bits + k) >> (i & 7) & 1 \
                and m.call(m.main + 0x28883A0, o, row, i) & 1:
            hit = 1
            m.put(base + i, 1, 1)
    return hit


@lifted(0x157BF08)
def remove_member(m, lst, b, *_):
    """Take a battler out of a member list (pointers from +0, count +0xa6), closing the gap; the byte
    at +0xa8 drops by one too."""
    n = m.u8(lst + 0xA6)
    for i in range(n):
        if m.u64(lst + 8 * i) != b:
            continue
        cur = n
        if i + 1 < n:
            m.put(lst + 8 * i, 8, m.u64(lst + 8 * i + 8))
            cur = m.u8(lst + 0xA6)
            j = i
            while j + 2 < cur:
                m.put(lst + 8 * j + 8, 8, m.u64(lst + 8 * j + 0x10))
                cur = m.u8(lst + 0xA6)
                j += 1
        m.put(lst + 0xA6, 1, cur - 1)
        m.put(lst + 0xA8, 1, m.u8(lst + 0xA8) - 1)
        return


@lifted(0x1480A6C)
def make_entry(m, o, kind, value, src, b, *_):
    """A 16-byte entry returned in x0 and x1: x0 = value (its upper half as 0x179372c leaves it), x1 = 1
    for kinds 1 and 3..5, for kind 2: 2 with 0x179405c of the battler's two 0x68 reads in bits 3..8."""
    with m.frame(0x10) as p:
        m.call_void(m.main + 0x179372C, p)
        k = kind & 0xFFFF
        m.put(p + 8, 8, 0)
        if 3 <= k <= 5 or k == 1:
            hi = 1
        elif k == 2:
            x = m.vcall(b, 0x68, m.u64(m.main + 0x46E25C8)) & 0xFFFFFFFF
            y = m.vcall(b, 0x68, m.u64(m.main + 0x46E25D0)) & 0xFFFFFFFF
            m.put(p, 4, value)
            m.put(p + 8, 8, 2)
            r = m.call(m.main + 0x179405C, src, x, y)
            hi = (2 & ~0x1F8) | ((r & 0x3F) << 3)
        else:
            hi = 0
        m.put(p + 8, 8, hi)
        m.put(p, 4, value)
        return Pair(m.u64(p), hi)


@lifted(0x15C0434)
def other_side_target(m, o, a, t, *_):
    a &= 0xFFFFFFFF; t &= 0xFFFFFFFF
    if m.call(m.main + 0x15C04B0, m.u64(m.u64(o + 0x10) + 0x30), t) & 1 == 0:
        return 0
    if m.call(m.main + 0x15C04A4, o, a, t) & 1:
        return 0
    return int(t != 0 and t != a)


def _add_unique(m, s, b):
    """Add byte b to the set at s (count at +0xb, at most 11) unless it holds it."""
    n = m.u8(s + 0xB)
    if n > 10:
        return
    b &= 0xFF
    if b in m.read(s, n):
        return
    m.put(s + n, 1, b)
    m.put(s + 0xB, 1, n + 1)


@lifted(0x1138D9C)
def targets_mode_0(m, p, s, w, *_):
    """The positions target kind [p] (subject byte p+4) reaches in a single battle, into the set s."""
    k = m.u32(p)
    if k > 9:
        return
    bit = 1 << k
    if bit & 0x8C:
        _add_unique(m, s, m.call(m.main + 0x113AECC, 0, w, m.u8(p + 4), 0))
    elif bit & 0x240:
        _add_unique(m, s, 0); _add_unique(m, s, 1)
    elif k == 4:
        _add_unique(m, s, m.u8(p + 4))


@lifted(0x1138F20)
def targets_mode_1(m, p, s, w, *_):
    """The positions target kind [p] (subject byte p+4) reaches in a double battle, into the set s."""
    k = m.u32(p)
    me = m.u8(p + 4)
    near = lambda i: m.call(m.main + 0x113A588, 1, w, me, i)
    foe = lambda i: m.call(m.main + 0x113AECC, 1, w, me, i)
    if k == 8:
        _add_unique(m, s, me); _add_unique(m, s, near(1))
    elif k in (1, 5):
        _add_unique(m, s, near(1))
    elif k in (2, 7):
        _add_unique(m, s, foe(0)); _add_unique(m, s, foe(1))
    elif k == 3:
        _add_unique(m, s, foe(0)); _add_unique(m, s, foe(1)); _add_unique(m, s, near(1))
    elif k == 4:
        b = near(1) & 0xFF
        _add_unique(m, s, min(me, b)); _add_unique(m, s, max(me, b))
    elif k in (6, 9):
        for i in range(4):
            _add_unique(m, s, i)


@lifted(0x11393FC)
def targets_mode_2(m, p, s, w, *_):
    """The positions target kind [p] (subject byte p+4) reaches in a raid, into the set s."""
    k = m.u32(p)
    me = m.u8(p + 4)
    near = lambda i: m.call(m.main + 0x113A588, 2, w, me, i)
    foe = lambda i: m.call(m.main + 0x113AECC, 2, w, me, i)
    if k == 8:
        _add_unique(m, s, me)
        for i in range(1, 6):
            _add_unique(m, s, near(i))
    elif k in (1, 5):
        for i in range(1, 6):
            _add_unique(m, s, near(i))
    elif k in (2, 7):
        for i in range(6):
            _add_unique(m, s, foe(i))
    elif k == 3:
        for i in range(6):
            _add_unique(m, s, foe(i))
        for i in range(1, 6):
            _add_unique(m, s, near(i))
    elif k == 4:
        for i in range(11):
            if m.call(m.main + 0x113B494, 2, w, me, i) & 1:
                _add_unique(m, s, i)
    elif k in (6, 9):
        for i in range(10):
            _add_unique(m, s, i)


@lifted(0xFE171C)
def collect_targets(m, p, mode, w, field, out, *_):
    """The ids of the standing battlers at the positions target record p reaches (by battle mode),
    into the u32 array out; returns how many."""
    k = m.u32(p)
    me = m.u8(p + 4)
    with m.frame(0x20) as f:
        lst = f
        s = f + 0x10
        if k == 0:
            m.put(lst, 1, me)
            n = int(me != 0xA)
        elif me == 0xA:
            return 0
        else:
            m.write(s, b"\x0a" * 11 + b"\x00")
            mode &= M32
            fn = 0x11393FC if mode == 2 else 0x1138F20 if mode == 1 else 0x1138D9C
            m.call_void(m.main + fn, p, s, w)
            n = m.u8(s + 0xB)
            if n:
                m.write(lst, m.read(s, n))
        count = 0
        for i in range(n):
            m.call_void(m.main + 0x1153868, m.u64(m.u64(field + 0x18) + 0x290), m.u8(lst + i), s, f + 0xC)
            side = m.u8(s)
            if side == 5:
                continue
            slot = m.u8(f + 0xC)
            if slot >= m.u8(field + side * 0x38 + 0x58):
                continue
            b = m.u64(field + side * 0x38 + slot * 8 + 0x28)
            if b == 0 or m.vcall(b, 0x200) & 1:
                continue
            m.put(out + 4 * (count & 0xFF), 4, m.vcall(b, 0x98))
            count += 1
        return count & M32


@lifted(0x2843D30)
def collect_targets_of(m, o, p, out, *_):
    mode = m.call(m.main + 0x144B6D4, m.u64(o + 8))
    w = m.call(m.main + 0x281B234, m.u64(o + 8))
    return _tail(m, m.main + 0xFE171C, p, mode & M32, w & M32, m.u64(m.u64(o + 8) + 0x30), out)


@lifted(0x174FA60)
def check_each_target_3e(m, o, _x, r, *_):
    """For each target of the list [r+0x10] (cursor +0xa8): when event 0x3e (user [r], move [r+8]) says
    so, 0x157a950 on the current entry, 0x174ff2c and drop the target (0x157bf08)."""
    _need(m, m.main + 0x174FF2C)
    lst = m.u64(r + 0x10)
    m.put(lst + 0xA8, 1, 0)
    while True:
        lst = m.u64(r + 0x10)
        i = m.u8(lst + 0xA8)
        if i >= m.u8(lst + 0xA6):
            return
        m.put(lst + 0xA8, 1, i + 1)
        t = m.u64(lst + 8 * i)
        if t == 0:
            return
        if m.call(m.main + 0x174FB1C, m.u64(o + 0x38), m.u64(r), t, m.u64(r + 8)) & 1:
            m.call_void(m.main + 0x157A950, m.call(m.main + 0x139B698, o) + 0x10)
            m.call_void(m.main + 0x174FF2C, m.u64(o + 0x38), m.u64(r), t)
            m.call_void(m.main + 0x157BF08, m.u64(r + 0x10), t)


@lifted(0x1143E3C)
def sort_targets_by_speed(m, o, _x, pl, *_):
    """Sort the target list [pl] (battlers +0, u16 +0x58 and +0x90 alongside, count +0xa6) fastest first
    by event 0x13 speed; a tie swaps on a coin flip."""
    lst = m.u64(pl)
    n = m.u8(lst + 0xA6)
    if n == 0:
        return
    speed = []
    for k in range(n):
        lst = m.u64(pl)
        b = m.u64(lst + 8 * k) if k < m.u8(lst + 0xA6) else 0
        speed.append(m.call(m.main + 0x1144194, m.u64(o + 0x38), b, 1) & 0xFFFF)
    for i in range(max(n, 1)):
        for j in range(i + 1, n):
            a, c = speed[i], speed[j]
            swap = a < c
            if a == c:
                rand = m.call(m.main + 0x11440E8, m.u64(o + 0x10))
                swap = m.call(m.main + 0x11440F0, rand, 2) & M32 != 0
            if not swap:
                continue
            if i < 0xB and j < 0xB:
                lst = m.u64(pl)
                for base, size in ((0, 8), (0x58, 2), (0x90, 2)):
                    x, y = m.u(lst + base + size * i, size), m.u(lst + base + size * j, size)
                    m.put(lst + base + size * i, size, y); m.put(lst + base + size * j, size, x)
            speed[i], speed[j] = c, a


@lifted(0x157C08C)
def move_targets_pass(m, o, _x, r, *_):
    """The target-selection pass of a move (user [r], move [r+8], levels [r+0x10], targets [r+0x18]):
    hit checks for events 0x32, 0x34 (between events 0x33 and 0x35), a per-target pass for moves whose
    field 23 is set (event 0x3c, the 0x38 hit check, dropping the targets that avoid it through
    0x287f1a8), then 0x39; a move that lost all its targets ends through 0x157bf90 (4) when +0x20 is
    set."""
    def checks(event):
        with m.frame(0x30) as f:
            s = f + 8
            m.put(s, 8, m.u64(r + 8)); m.put(s + 8, 8, m.u64(r)); m.put(s + 0x10, 8, m.u64(r + 0x18))
            m.put(s + 0x18, 8, m.u64(r + 0x10)); m.put(s + 0x20, 2, event); m.put(s + 0x22, 1, 0)
            m.call_void(m.main + 0x157C404, m.u64(m.u64(o + 0x78) + 0x360), f, s)
    checks(0x32)
    lst = m.u64(r + 0x18)
    ended = (m.u8(lst + 0xA7) or m.u8(lst + 0xA9)) and m.u8(lst + 0xA6) == 0
    user, mv, levels = m.u64(r), m.u64(r + 8), m.u64(r + 0x10)
    m.call_void(m.main + 0x157D6F4, m.u64(o + 0x38), mv, user, lst)
    checks(0x34)
    m.call_void(m.main + 0x157DBAC, m.u64(o + 0x38), mv, user, lst)
    user, mv, levels, lst = m.u64(r), m.u64(r + 8), m.u64(r + 0x10), m.u64(r + 0x18)
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    if fb.u8(m, m.call(m.main + 0xBF60CC, table, m.u16(mv)), 23):
        m.put(lst + 0xA8, 1, 0)
        t = 0
        if m.u8(lst + 0xA6):
            t = m.u64(lst)
            m.put(lst + 0xA8, 1, 1)
        while t:
            drop = False
            if m.vcall(t, 0x510, 7) & 1:
                if not m.vcall(t, 0x510, 0x10) & 1 or m.call(m.main + 0x14D973C, m.u16(mv)) & 1:
                    drop = not m.call(m.main + 0x157E558, m.u64(o + 0x38), user, t, mv) & 1
            elif not m.call(m.main + 0x157E558, m.u64(o + 0x38), user, t, mv) & 1:
                with m.frame(0x30) as f:
                    s = f + 8
                    m.put(s, 8, mv); m.put(s + 8, 8, user); m.put(s + 0x10, 8, t); m.put(s + 0x18, 8, levels)
                    m.put(s + 0x20, 2, 0x38); m.put(s + 0x22, 1, 1)
                    m.call_void(m.main + 0x157C508, m.u64(m.u64(o + 0x78) + 0x300), f, s)
                    drop = m.u8(f) != 0
            if drop:
                single = not (m.u8(mv + 0x13) != 0 and m.u8(lst + 0xA6) > 1)
                m.call_void(m.main + 0x157BF08, lst, t)
                if single and not m.u8(m.call(m.main + 0x139B698, o) + 0xC0):
                    m.call_void(m.main + 0x287F1A8, o, user, t, mv)
                m.put(m.call(m.main + 0x139B698, o) + 0xC0, 1, 0)
            i = m.u8(lst + 0xA8)
            if i >= m.u8(lst + 0xA6):
                break
            m.put(lst + 0xA8, 1, i + 1)
            t = m.u64(lst + 8 * i)
    checks(0x39)
    if ended:
        return
    lst = m.u64(r + 0x18)
    if not (m.u8(lst + 0xA7) or m.u8(lst + 0xA9)) or m.u8(lst + 0xA6) or m.u64(r + 0x20) == 0:
        return
    return _tail(m, m.main + 0x157BF90, m.call(m.main + 0x1143584, o), m.vcall(m.u64(r), 0x98) & M32, 4)


@lifted(0x157C00C)
def mark_bit(m, o, ident, kind, *_):
    """Set bit `kind` (0..4) in word [o+0x70] of the entry for `ident` in the map at o+8, adding a zeroed
    entry first."""
    kind &= 0xFF
    if kind > 4:
        return
    with m.frame(0x10) as f:
        m.put(f, 4, ident & M32)
        if not m.call(m.main + 0x157EA98, o + 8, f):
            m.put(m.call(m.main + 0xF7A448, o + 8, f), 8, 0)
        p = m.call(m.main + 0xF7A448, o + 8, f) + 4 * m.u8(o + 0x70)
        m.put(p, 4, m.u32(p) | (1 << kind))


@lifted(0x157BFD4)
def mark_bit_of(m, o, ident, kind, *_):
    """0x157c00c on [[o+0x10]+0x170]."""
    return _tail(m, m.main + 0x157C00C, m.u64(m.u64(o + 0x10) + 0x170), ident & M32, kind & M32)


@lifted(0x157BF90)
def mark_and_report(m, o, ident, kind, *_):
    """Mark bit `kind` for `ident` (0x157bfd4 on [o+0x20]), then queue command 0x52 (ident, kind)."""
    m.call_void(m.main + 0x157BFD4, m.u64(o + 0x20), ident & M32, kind & M32)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x52, ident & M32, kind & 0xFF)


@lifted(0x287F1E4)
def target_avoided(m, o, _x, args, *_):
    """args = (user, target, move): 0x114ade8(target, 0x76), command 0xcb (user, 0xae, target),
    0x1146e90, then event 0xd1."""
    user, target, move = m.u64(args), m.u64(args + 8), m.u64(args + 0x10)
    m.call_void(m.main + 0x114ADE8, m.call(m.main + 0x1143584, o), target, 0x76)
    q = m.call(m.main + 0x1143584, o)
    a = m.vcall(user, 0x98) & M32
    m.call_void(m.main + 0x157EBA0, q, a, 0xAE, m.vcall(target, 0x98) & M32)
    m.call_void(m.main + 0x1146E90, o)
    return _tail(m, m.main + 0x2832EA8, o, user, target, move)


@lifted(0x287F1A8)
def on_target_avoided(m, o, user, target, move, *_):
    """0x287f1e4 on [[o+0x78]+0x1380] with (user, target, move)."""
    with m.frame(0x20) as f:
        m.put(f + 8, 8, user); m.put(f + 0x10, 8, target); m.put(f + 0x18, 8, move)
        m.call_void(m.main + 0x287F1E4, m.call(m.main + 0x287F1DC, m.u64(o + 0x78)), f, f + 8)


@lifted(0x173C16C)
def redirect_target(m, o, battler, b, mv, out, *_):
    """Events 0x30/0x31 (0x173c1f4) with battler's id: a nonzero result is resolved through 0x13813f4,
    else battler itself."""
    r = m.call(m.main + 0x173C1F4, o, b, mv, m.vcall(battler, 0x98) & M32, out) & M32
    if not r:
        return battler
    return _tail(m, m.main + 0x13813F4, o, r)


@lifted(0x173C7FC)
def add_all_matching(m, o, a, lst, *_):
    """For a list holding a user ([lst]), append each other standing member that 0x173cb54 accepts."""
    from pokeldn.sv.battle.engine.flow import add_member
    from pokeldn.sv.battle.engine.members import _standing_of
    if not m.u8(lst + 0xA6):
        return
    user = m.u64(lst)
    uid = m.vcall(user, 0x98) & M32
    for b in _standing_of(m, m.u64(o + 8), m.u64(o + 0x10)):
        if m.vcall(b, 0x98) & M32 == uid:
            continue
        if m.call(m.main + 0x173CB54, m.u64(o + 0x38), a, user, b) & 1:
            add_member(m, lst, b)


def _walk_pre(m, lst):
    """The member list walk with the cursor (+0xa8) advanced before each read."""
    m.put(lst + 0xA8, 1, 0)
    while True:
        i = m.u8(lst + 0xA8)
        if i >= m.u8(lst + 0xA6):
            return
        m.put(lst + 0xA8, 1, i + 1)
        t = m.u64(lst + 8 * i)
        if not t:
            return
        yield t


@lifted(0x157B8D8)
def collect_target_flags(m, o, _x, r, *_):
    """r = (a, b, lst, out): out = up to 10 (target id, two flag bytes from 0x157bb8c), unset entries
    (0, 0xe), count at +0x50."""
    out = m.u64(r + 0x18)
    m.put(out + 0x50, 4, 0)
    for k in range(10):
        m.put(out + 8 * k, 4, 0); m.put(out + 8 * k + 4, 2, 0xE)
    lst = m.u64(r + 0x10)
    for t in _walk_pre(m, lst):
        with m.frame(0x28) as sp:
            m.write(sp, bytes(0x28))
            m.put(sp + 8, 8, m.u64(r + 8)); m.put(sp + 0x10, 8, t); m.put(sp + 0x18, 8, m.u64(r))
            m.call_void(m.main + 0x157BB8C, m.u64(m.u64(o + 0x78) + 0x4A0), sp, sp + 8)
            b0, b1 = m.u8(sp), m.u8(sp + 1)
        out = m.u64(r + 0x18)
        ident = m.vcall(t, 0x98) & M32
        n = m.u32(out + 0x50)
        if n <= 9:
            m.put(out + 8 * n, 4, ident); m.put(out + 8 * n + 4, 1, b0); m.put(out + 8 * n + 5, 1, b1)
            m.put(out + 0x50, 4, n + 1)
        lst = m.u64(r + 0x10)


@lifted(0x157BA2C)
def drop_immune_targets(m, o, _x, r, *_):
    """r = (user, move, lst, end, byte): drop each target that neither 0x157d2e4 nor 0x157ef78 keeps
    (0x157bf08, 0x157eeb8 unless the move hits several of them, 0x158097c); a list left empty ends the
    move through 0x157bf90 (1) when end is set."""
    lst = m.u64(r + 0x10)
    if not m.u8(lst + 0xA6) or (m.u8(lst + 0xA7) == 1 and m.u64(lst) == m.u64(r)):
        return
    with m.frame(0x10) as flag:
        for t in _walk_pre(m, m.u64(r + 0x10)):
            user, mv = m.u64(r), m.u64(r + 8)
            m.put(flag, 1, 0)
            if m.call(m.main + 0x157D2E4, m.u64(o + 0x38), user, t, mv) & 1:
                continue
            if m.call(m.main + 0x157EF78, m.u64(o + 0x38), user, t, mv, flag) & 1:
                continue
            lst = m.u64(r + 0x10)
            n, many = m.u8(lst + 0xA6), m.u8(m.u64(r + 8) + 0x13)
            m.call_void(m.main + 0x157BF08, lst, t)
            if n < 2 or not many:
                m.call_void(m.main + 0x157EEB8, o, m.u64(r), t, m.u16(m.u64(r + 8)), m.u8(flag))
            m.call_void(m.main + 0x158097C, m.u64(o + 0x38), m.u64(r), m.u8(r + 0x20))
    if not m.u64(r + 0x18):
        return
    lst = m.u64(r + 0x10)
    if (m.u8(lst + 0xA7) or m.u8(lst + 0xA9)) and not m.u8(lst + 0xA6):
        q = m.call(m.main + 0x1143584, o)
        m.call_void(m.main + 0x157BF90, q, m.vcall(m.u64(r), 0x98) & M32, 1)


@lifted(0x173BCF8)
def select_targets(m, o, _x, r, *_):
    """r = (user, move, byte, slot id u32 at +0x14, lst): fill lst with the move's targets (0x173c128,
    then 0x173c16c for a lone redirected target or 0x173c7fc, then 0x173c268), then keep only those still
    in the battle whose position 0x1381420 is not 10; lst+0xa9 takes the high mark before the filter."""
    from pokeldn.sv.battle.engine.flow import add_member
    with m.frame(0xC0) as sp:
        flag, redirected, copy = sp + 0xC, sp + 8, sp + 0x10
        a1 = m.u64(o + 8)
        m.put(flag, 1, 0)
        pos = m.u8(r + 0x10)
        keep = 0 if m.u8(m.u64(r + 8) + 0x10) else \
            m.call(m.main + 0x173D2DC, m.u64(o + 0x38), m.u64(r), m.u64(r + 8)) & 0xFF
        _clear_members(m, m.u64(r + 0x18))
        user, mv = m.u64(r), m.u64(r + 8)
        place = m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), m.u32(r + 0x14)) & 0xFF
        if place != 0xA and m.call(m.main + 0x173CF60, m.u64(o + 0x38), user, mv) & 1:
            pos = m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), m.u32(r + 0x14)) & M32
        m.call_void(m.main + 0x173C128, o, a1, m.u64(o + 0x10), m.u64(r), pos, m.u64(r + 8), keep,
                    m.u64(r + 0x18), flag)
        f = m.call(m.main + 0x173C518, m.u64(o + 0x38), m.u64(r), m.u8(flag)) & 1
        m.put(flag, 1, f)
        m.put(redirected, 1, 0)
        lst = m.u64(r + 0x18)
        if m.u8(lst + 0xA6) == 1 and f:
            t = m.call(m.main + 0x173C16C, o, m.u64(lst), m.u64(r), m.u64(r + 8), redirected)
            _clear_members(m, m.u64(r + 0x18))
            if t:
                add_member(m, m.u64(r + 0x18), t)
            if not m.u8(redirected):
                m.call_void(m.main + 0x173C7FC, o, m.u64(r), m.u64(r + 0x18))
        else:
            m.call_void(m.main + 0x173C7FC, o, m.u64(r), lst)
        m.call_void(m.main + 0x173C268, o, 0, m.u64(r), m.u64(r + 8), 0, m.u64(r + 0x18))
        lst = m.u64(r + 0x18)
        m.write(copy, m.read(lst, 0xA8))
        high = m.u8(lst + 0xA7)
        m.put(copy + 0xA9, 1, m.u8(lst + 0xA9))
        places = m.u64(m.u64(o + 0x10) + 0xF0)
        m.put(copy + 0xA8, 1, 0)
        n = m.u8(copy + 0xA6)
        if n:
            m.put(copy + 0xA8, 1, 1)
            t = m.u64(copy)
            while t:
                if m.vcall(t, 0x200) & 1 or \
                        m.call(m.main + 0x1381420, places, m.vcall(t, 0x98) & M32) & 0xFF == 0xA:
                    m.call_void(m.main + 0x157BF08, copy, t)
                i = m.u8(copy + 0xA8)
                n = m.u8(copy + 0xA6)
                if i >= n:
                    break
                m.put(copy + 0xA8, 1, i + 1)
                t = m.u64(copy + 8 * i)
            _clear_members(m, lst)
            for i in range(n):
                t = m.u64(copy + 8 * i)
                out = m.vcall(t, 0x200) & 1
                if t and not out:
                    add_member(m, lst, t)
        else:
            _clear_members(m, lst)
        m.put(lst + 0xA9, 1, high)


def _walk_pre_resume(m, lst):
    """The member list walk advancing the cursor (+0xa8) before each read, from where it stands."""
    while True:
        i = m.u8(lst + 0xA8)
        if i >= m.u8(lst + 0xA6):
            return
        m.put(lst + 0xA8, 1, i + 1)
        t = m.u64(lst + 8 * i)
        if not t:
            return
        yield t


# Target kind by the move's field 17 (1..9) when [o+0x36c] is set (jump table 0x3c69d6a): a request
# kind for 0xfe171c, "self" (the user's position) or None (no target, 10).
_TARGET_KIND = {0: 2, 1: 4, 2: 5, 3: 2, 7: "self", 9: 2}


@lifted(0x10E21C0)
def random_target(m, _x0, o, b, move, rng, *_):
    """The position a move of b without a chosen target aims at: by the move's field 17 (Curse 0xae: 7,
    0 for b's vf 0x300(7)); single battles ([o+0x36c] 0) go through 0x173db04, others pick at random
    (0x11440f0 on rng) among 0xfe171c's ids, then 0x1138ce0's positions; 10 for none."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    single = m.u32(o + 0x36C) == 0
    pos = m.call(m.main + 0xFE161C, m.u64(o + 0x290), m.vcall(b, 0x98) & M32) & M32
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    kind = fb.u8(m, m.call(m.main + 0xBF60CC, table, move & M32), 17)
    if move & 0xFFFF == 0xAE:
        kind = 0 if m.vcall(b, 0x300, 7) & 1 else 7
    if single:
        if kind == 0 or (kind <= 9 and 0x238 >> kind & 1):
            return _tail(m, m.main + 0x173DB04, m.u64(o + 0x290), pos, 0)
        return pos if kind <= 9 and 0x82 >> kind & 1 else 0xA
    with m.frame(0x60) as sp:
        req = sp + 0x58
        m.call_void(m.main + 0x10E2464, req)
        how = _TARGET_KIND.get(kind)
        if how is None:
            return 0xA
        if how == "self":
            return pos
        ids = sp + 0x10
        m.call_void(m.main + 0x10E244C, ids, how, pos)
        m.call_void(m.main + 0x10E2474, req, ids)
        mode = m.u32(o + 0x36C)
        w = m.call(m.main + 0x10E2458, m.u64(o + 0x290)) & M32
        n = m.call(m.main + 0xFE171C, req, mode, w, m.u64(o + 0x30), ids) & 0xFF
        if n:
            i = m.call(m.main + 0x11440F0, rng, n) & 0xFF
            return m.call(m.main + 0xFE161C, m.u64(o + 0x290), m.u32(ids + 4 * i)) & M32
        n = m.call(m.main + 0x1138CE0, req, mode, w, sp + 4) & 0xFF
        if not n:
            return 0xA
        i = m.call(m.main + 0x11440F0, rng, n) & 0xFF
        return m.u8(sp + 4 + i)


@lifted(0x157FD40)
def run_157fdb0_78(m, o, b, mv, flags, *_):
    """0x157fdb0 on [o+0x78]'s object with the record {b's id, u16 [mv], flags at +8}."""
    with m.frame(0x30) as sp:
        m.write(sp, bytes(0x10))
        m.put(sp, 4, m.vcall(b, 0x98) & M32)
        m.put(sp + 4, 2, m.u16(mv)); m.put(sp + 8, 8, flags)
        x = m.call(m.main + 0x157FDA8, m.u64(o + 0x78))
        return _tail(m, m.main + 0x157FDB0, x, sp + 0x28, sp)


@lifted(0x288B124)
def apply_to_each_target(m, o, _x1, r, *_):
    """For each target 0x158003c hands out of the list [r+0x10] (reset by 0x1143d7c): event value
    0x283955c(b, t, move), a record from 0x288b67c, and 0x288b6fc; a yes runs 0x157a950."""
    key, b = m.u16(m.u64(r)), m.u64(r + 8)
    m.call_void(m.main + 0x1143D7C, m.u64(r + 0x10))
    with m.frame(0x30) as sp:
        rec = sp + 8
        t = m.call(m.main + 0x158003C, m.u64(r + 0x10))
        while t:
            v = m.call(m.main + 0x283955C, m.call(m.main + 0x1146E90, o), b, t, key) & M32
            m.call_void(m.main + 0x1146154, rec)
            m.call_void(m.main + 0x288B67C, o, rec, b, t, key)
            if m.call(m.main + 0x288B6FC, o, t, v, rec) & 1:
                m.call_void(m.main + 0x157A950, m.call(m.main + 0x139B698, o) + 0x10)
            t = m.call(m.main + 0x158003C, m.u64(r + 0x10))


@lifted(0x2885718)
def after_hit_each_target(m, o, _x1, r, *_):
    """r = (user, ?, u32 count, targets, kind bytes, flag byte +0x28): for each target with a kind,
    0x1946378, mark 8 (0x287fe5c) for the target, mark 0x1b for the user unless 0x118ab58 pairs them, and
    0x1148470(user, 0x1a); then 0x2837164 for every target."""
    i = 0
    while i < m.u32(r + 0x10):
        t = lambda: m.u64(m.u64(r + 0x18) + 8 * i)
        k = m.u8(m.u64(r + 0x20) + i)
        if k:
            m.call_void(m.main + 0x1946378, o, m.u64(r), t(), k, m.u8(r + 0x28))
            m.call_void(m.main + 0x287FE5C, o, 8, m.vcall(t(), 0x98) & M32)
            setup = m.u64(m.u64(o + 0x10) + 0x290)
            uid = m.vcall(m.u64(r), 0x98) & M32
            if not m.call(m.main + 0x118AB58, setup, uid, m.vcall(t(), 0x98) & M32) & 1:
                m.call_void(m.main + 0x287FE5C, o, 0x1B, m.vcall(m.u64(r), 0x98) & M32)
            c = m.u64(o + 0x20)
            uid = m.vcall(m.u64(r), 0x98) & M32
            u = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), uid)
            m.call_void(m.main + 0x1148470, c, u, 0x1A)
        m.call_void(m.main + 0x2837164, m.u64(o + 0x38), m.u64(r + 8), m.u64(r), t())
        i += 1


def _record_call(getter, fn, out_first):
    def lift(m, o, a, b, c=0, *_):
        """fn on [o+0x78]'s object (getter) with the record {b, a, c} on the stack."""
        with m.frame(0x20) as sp:
            r = sp + 8
            m.put(r, 8, b); m.put(r + 8, 8, a); m.put(r + 0x10, 8, c)
            x = m.call(m.main + getter, m.u64(o + 0x78))
            return _tail(m, m.main + fn, x, sp if out_first else sp + 0x18, r)
    return lift


lifted(0x288ACE0)(_record_call(0x288ADE4, 0x288ADEC, True))
lifted(0x288AD80)(_record_call(0x288B11C, 0x288B124, True))


@lifted(0x157FE88)
def keep_affected_targets(m, o, p, mv, b, lst, *_):
    """For each target of lst, 0x1580064 (b, target, mv, u32 [p]); a target it does not hit is dropped
    (0x157bf08), after 0x287ecb0 when 0x157ea90(lst) was 1."""
    single = m.call(m.main + 0x157EA90, lst) & M32 == 1
    m.call_void(m.main + 0x1143D7C, lst)
    t = m.call(m.main + 0x158003C, lst)
    with m.frame(0x10) as f:
        while t:
            m.call_void(m.main + 0x1580064, o, f + 0xC, f + 8, b, t, mv, m.u32(p))
            if not m.u8(f + 0xC):
                if single:
                    m.call_void(m.main + 0x287ECB0, o, b, t, mv, m.u32(p), m.u32(f + 8))
                m.call_void(m.main + 0x157BF08, lst, t)
            t = m.call(m.main + 0x158003C, lst)


@lifted(0x1532DEC)
def per_target_effects(m, o, _x1, r, *_):
    """r = (targets L, ?, move ptr, ?, count byte +0x20): per target 0x15333f0 {t, 0x153570c value},
    0x153314c {move, [r+0x18], t, L's u16 +0x30+2i} and 0x1533028 {[r+8], move, [r+0x18], t, u16, 0}; then
    0x1532efc {[r+8], move, [r+0x18]}. The records share one stack area, as in the game."""
    obj = lambda off: m.u64(m.u64(o + 0x78) + off)
    with m.frame(0x40) as sp:
        m.write(sp, bytes(0x30))
        i = 0
        while i < m.u8(r + 0x20):
            t = m.u64(m.u64(r) + 8 * i)
            w = m.call(m.main + 0x153570C, m.u64(o + 0x38), m.u16(m.u64(r + 0x10)), m.u64(r + 0x18))
            m.put(sp + 0x10, 4, w); m.put(sp + 8, 8, t)
            m.call_void(m.main + 0x15333F0, obj(0x1780), sp, sp + 8)
            L = m.u64(r)
            t, key = m.u64(L + 8 * i), m.u16(L + 2 * i + 0x30)
            m.put(sp + 0x10, 8, m.u64(r + 0x18)); m.put(sp + 0x18, 8, t)
            m.put(sp + 8, 8, m.u64(r + 0x10)); m.put(sp + 0x20, 4, key)
            m.call_void(m.main + 0x153314C, obj(0x560), sp, sp + 8)
            L = m.u64(r)
            t, key = m.u64(L + 8 * i), m.u16(L + 2 * i + 0x30)
            m.put(sp + 0x18, 8, m.u64(r + 0x18)); m.put(sp + 0x20, 8, t)
            m.put(sp + 8, 8, m.u64(r + 8)); m.put(sp + 0x10, 8, m.u64(r + 0x10))
            m.put(sp + 0x28, 4, key); m.put(sp + 0x2C, 1, 0)
            m.call_void(m.main + 0x1533028, obj(0x1A00), sp, sp + 8)
            i += 1
        m.put(sp + 0x10, 8, m.u64(r + 0x10)); m.put(sp + 0x18, 8, m.u64(r + 0x18))
        m.put(sp + 8, 8, m.u64(r + 8))
        m.call_void(m.main + 0x1532EFC, obj(0x1A20), sp, sp + 8)


@lifted(0x157E9FC)
def keep_affected_and_note(m, o, _x1, r, *_):
    """0x157fe88 on r's four fields; with two or more targets and 0x157ee90 true afterwards, 0x157a95c for
    the user [r+0x10] and +0xc0 of 0x139b698 set."""
    n = m.call(m.main + 0x157EA90, m.u64(r + 0x18)) & M32
    m.call_void(m.main + 0x157FE88, o, m.u64(r), m.u64(r + 8), m.u64(r + 0x10), m.u64(r + 0x18))
    if n < 2 or not m.call(m.main + 0x157EE90, m.u64(r + 0x18)) & 1:
        return
    q = m.call(m.main + 0x1143584, o)
    m.call_void(m.main + 0x157A95C, q, m.vcall(m.u64(r + 0x10), 0x98) & M32)
    m.put(m.call(m.main + 0x139B698, o) + 0xC0, 1, 1)


@lifted(0x157EE90)
def emptied(m, lst, *_):
    """Whether the target list had targets (+0xa7 or +0xa9) and has none left (+0xa6)."""
    if not m.u8(lst + 0xA7) and not m.u8(lst + 0xA9):
        return 0
    return int(m.u8(lst + 0xA6) == 0)


def _move_field_3(m, mv):
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    return fb.u8(m, m.call(m.main + 0xBF60CC, table, m.u16(mv)), 3)


def _emptied(m, lst):
    return (m.u8(lst + 0xA7) or m.u8(lst + 0xA9)) and not m.u8(lst + 0xA6)


@lifted(0x157A9BC)
def filter_targets(m, o, out, r, *_):
    """The target pass before a move runs. r = (flags, move, user, target list L, +0x20 / +0x21 / +0x22
    bytes, +0x28, +0x30). Drops targets that are out or at position 10, the lone target when it is the
    user (unless the move's type byte is 7 or the user holds condition 0xc and kind 0x1d1 allows it), runs
    the handler chains 0x157b7a4 / 0x157b8d8 / 0x157c08c / 0x157c404 / 0x157bd30 / 0x157b588 /
    0x15804d0 / 0x157e9fc / 0x157ba2c by move kind (field 3), the kind-9 speed check (texts 0x4a / 0x49,
    0x282e5d8), and the kind-0x3d1 redirection pass (0x282d99c). An emptied list ends the move: 0x157a95c
    or 0x15800cc, then 0x157fd40 and out = 1."""
    m.put(out, 1, 0)
    lst = m.u64(r + 0x18)
    tab = m.u64(m.u64(o + 0x10) + 0xF0)
    m.put(lst + 0xA8, 1, 0)
    if m.u8(lst + 0xA6):
        i = 0
        while True:
            m.put(lst + 0xA8, 1, i + 1)
            p = m.u64(lst + 8 * (i & 0xFF))
            if not p:
                break
            if m.vcall(p, 0x200) & 1 or m.call(m.main + 0x1381420, tab, m.vcall(p, 0x98) & M32) & 0xFF == 0xA:
                m.call_void(m.main + 0x157BF08, lst, p)
            i = m.u8(lst + 0xA8)
            if i >= m.u8(lst + 0xA6):
                break
    lst = m.u64(r + 0x18)
    if m.u8(lst + 0xA7) == 1 and m.u8(lst + 0xA6) and m.u64(lst):
        p0, mv, user = m.u64(lst), m.u64(r + 8), m.u64(r + 0x10)
        if m.vcall(p0, 0x98) & M32 == m.vcall(user, 0x98) & M32 and m.u8(mv + 0xA) != 7:
            if m.vcall(user, 0x510, 0xC) & 1:
                m.call_void(m.main + 0x157BF08, lst, p0)
            else:
                k = _move_field_3(m, mv)
                if k <= 8 and 0x1D1 >> k & 1:
                    m.call_void(m.main + 0x157BF08, lst, p0)
    obj = lambda off: m.u64(m.u64(o + 0x78) + off)
    finder = lambda: m.u64(obj(0x240) + 0x38)
    with m.frame(0x40) as sp:
        R = sp + 0x18
        m.write(sp, bytes(0x40))
        if _emptied(m, m.u64(r + 0x18)):
            if not m.call(m.main + 0x1581494, finder(), m.u64(r + 0x10), m.u64(r + 8)) & 1:
                m.call_void(m.main + 0x157A95C, m.u64(o + 0x20), m.vcall(m.u64(r + 0x10), 0x98) & M32)
                m.put(out, 1, 1)
                return
        m.put(R, 8, m.u64(r + 8)); m.put(R + 8, 8, m.u64(r + 0x10)); m.put(R + 0x10, 8, m.u64(r + 0x18))
        m.call_void(m.main + 0x157B7A4, obj(0x480), sp + 0x10, R)
        m.put(R, 8, m.u64(r + 8)); m.put(R + 8, 8, m.u64(r + 0x10))
        m.put(R + 0x10, 8, m.u64(r + 0x18)); m.put(R + 0x18, 8, m.u64(r + 0x30))
        m.call_void(m.main + 0x157B8D8, obj(0x440), sp + 0x10, R)
        m.put(R + 0x20, 8, m.u64(r + 0x28))
        m.put(R, 8, m.u64(r + 0x10)); m.put(R + 8, 8, m.u64(r + 8))
        m.put(R + 0x10, 8, m.u64(r + 0x30)); m.put(R + 0x18, 8, m.u64(r + 0x18))
        m.call_void(m.main + 0x157C08C, obj(0x3C0), sp + 0x10, R)
        lst = m.u64(r + 0x18)
        if m.u8(lst + 0xA6):
            mv, user = m.u64(r + 8), m.u64(r + 0x10)
            h = obj(0x3E0)
            extra = m.u64(r + 0x28)
            m.put(R + 0x22, 1, 0)
            m.put(R, 8, mv); m.put(R + 8, 8, user); m.put(R + 0x10, 8, lst); m.put(R + 0x18, 8, m.u64(r + 0x30))
            m.put(R + 0x20, 2, 0x3A)
            m.call_void(m.main + 0x157C404, m.u64(m.u64(h + 0x78) + 0x360), sp + 0x10, R)
            if extra and _emptied(m, lst):
                m.call_void(m.main + 0x157BF90, m.u64(h + 0x20), m.vcall(user, 0x98) & M32, 2)
        mv, user, lst = m.u64(r + 8), m.u64(r + 0x10), m.u64(r + 0x18)
        f21, x28, x30 = m.u8(r + 0x21), m.u64(r + 0x28), m.u64(r + 0x30)
        k = _move_field_3(m, mv)
        call = k <= 9 and 0x3D1 >> k & 1
        if not call:
            v = m.call(m.main + 0x1582144, m.u64(o + 0x38), mv, user)
            call = f21 or v & 1
        if call:
            m.put(R, 8, user); m.put(R + 8, 8, mv); m.put(R + 0x20, 8, x28)
            m.put(R + 0x10, 8, x30); m.put(R + 0x18, 8, lst)
            m.call_void(m.main + 0x157BD30, obj(0x380), sp + 0x10, R)
        user, lst, mv, x30 = m.u64(r + 0x10), m.u64(r + 0x18), m.u64(r + 8), m.u64(r + 0x30)
        h = obj(0x3A0)
        for code, flag in ((0x36, 1), (0x37, 0)):
            m.put(R, 8, mv); m.put(R + 8, 8, user)
            m.put(R + 0x20, 2, code); m.put(R + 0x22, 1, flag)
            m.put(R + 0x10, 8, lst); m.put(R + 0x18, 8, x30)
            m.call_void(m.main + 0x157C404, m.u64(m.u64(h + 0x78) + 0x360), sp + 0x10, R)
        m.call_void(m.main + 0x157B588, h, user, mv, lst)
        mv, user, lst = m.u64(r + 8), m.u64(r + 0x10), m.u64(r + 0x18)
        if _move_field_3(m, mv) == 1:
            m.put(R + 8, 8, user); m.put(R + 0x10, 8, lst); m.put(R, 8, mv)
            m.call_void(m.main + 0x15804D0, m.call(m.main + 0x157BF00, m.u64(o + 0x78)), sp + 0x10, R)
        head, mv, user, lst = m.u64(r), m.u64(r + 8), m.u64(r + 0x10), m.u64(r + 0x18)
        if _move_field_3(m, mv) == 2:
            m.put(R + 0x10, 8, user); m.put(R + 0x18, 8, lst); m.put(R, 8, head); m.put(R + 8, 8, mv)
            m.call_void(m.main + 0x157E9FC, m.call(m.main + 0x157B580, m.u64(o + 0x78)), sp + 0x10, R)
        mv, user, lst = m.u64(r + 8), m.u64(r + 0x10), m.u64(r + 0x18)
        x28, b22 = m.u64(r + 0x28), m.u8(r + 0x22)
        if _move_field_3(m, mv) != 9:
            m.put(R, 8, user); m.put(R + 8, 8, mv); m.put(R + 0x20, 1, b22)
            m.put(R + 0x10, 8, lst); m.put(R + 0x18, 8, x28)
            m.call_void(m.main + 0x157BA2C, obj(0x460), sp + 0x10, R)
        else:
            _speed_pass(m, o, user, lst, mv, R)
        if _emptied(m, m.u64(r + 0x18)) and \
                not m.call(m.main + 0x1581494, finder(), m.u64(r + 0x10), m.u64(r + 8)) & 1:
            return _end_move(m, o, out, r)
        if m.u8(r + 0x20):
            return
        mv, user, lst = m.u64(r + 8), m.u64(r + 0x10), m.u64(r + 0x18)
        k = _move_field_3(m, mv)
        if not (k <= 9 and 0x3D1 >> k & 1) and not m.call(m.main + 0x1382AB0, m.u16(mv)) & 1:
            m.put(lst + 0xA8, 1, 0)
            if m.u8(lst + 0xA6):
                p = m.u64(lst)
                m.put(lst + 0xA8, 1, 1)
                while p:
                    if p != user and m.vcall(p, 0x588) & 1 \
                            and not m.call(m.main + 0x1382688, m.u64(o + 0x38), user, p, m.u16(mv)) & 1:
                        m.call_void(m.main + 0x282D99C, m.u64(o + 0x38), user, p)
                        m.call_void(m.main + 0x157BF08, lst, p)
                    i = m.u8(lst + 0xA8)
                    if i >= m.u8(lst + 0xA6):
                        break
                    m.put(lst + 0xA8, 1, i + 1)
                    p = m.u64(lst + 8 * i)
        if not _emptied(m, m.u64(r + 0x18)):
            return
        if m.call(m.main + 0x1581494, finder(), m.u64(r + 0x10), m.u64(r + 8)) & 1:
            return
        m.call_void(m.main + 0x15800CC, o, m.u64(r + 0x10))
        return _end_move(m, o, out, r)


def _end_move(m, o, out, r):
    m.call_void(m.main + 0x157FD40, o, m.u64(r + 0x10), m.u64(r + 8), m.u64(r))
    m.put(out, 1, 1)


def _speed_pass(m, o, user, lst, mv, scratch):
    """Kind 9: each target faster than the user (vf 0x118) or failing the rule checks is dropped with text
    0x4a; 0x282e5d8 may keep it or drop it (text 0x49 unless it set its flag)."""
    if not m.u8(lst + 0xA6):
        return
    if m.u8(lst + 0xA7) == 1 and m.u64(lst) == user:
        return
    s = m.vcall(user, 0x118) & 0xFF
    m.put(lst + 0xA8, 1, 0)
    if not m.u8(lst + 0xA6):
        if m.u8(lst + 0xA7) or m.u8(lst + 0xA9):
            m.call_void(m.main + 0x157BF90, m.u64(o + 0x20), m.vcall(user, 0x98) & M32, 1)
        return
    p = m.u64(lst)
    m.put(lst + 0xA8, 1, 1)
    if not p:
        return

    def text(code, p):
        q = m.u64(o + 0x20)
        a = m.vcall(user, 0x98) & M32
        m.call_void(m.main + 0x157EBC0, m.u64(q + 0x18), 0xCB, a, code, m.vcall(p, 0x98) & M32, 0xFFFF0000)

    def blocked(p):
        if m.call(m.main + 0x1142E68, m.u64(o + 8), m.u64(o + 0x10), p) & 1:
            return False
        flags = m.u64(m.u64(m.u64(o + 8) + 0x38) + 0x498)
        if flags >> 10 & 1:
            return True
        if flags >> 11 & 1:
            if not m.vcall(p, 0x78) & 1:
                return True
            flags = m.u64(m.u64(m.u64(o + 8) + 0x38) + 0x498)
        if flags & 0x10001000:
            return True
        if not flags >> 0x11 & 1:
            return False
        node = m.vcall(p + 0x28, 0)
        static = m.call(m.main + 0x2D1FD38)
        while node:
            if node == static:
                return bool(m.u8(p + 0x714))
            node = m.u64(node)
        return False

    while True:
        if s < m.vcall(p, 0x118) & 0xFF:
            text(0x4A, p)
            m.call_void(m.main + 0x157BF08, lst, p)
        elif blocked(p):
            text(0x4A, p)
            m.call_void(m.main + 0x157BF08, lst, p)
        else:
            m.put(scratch, 1, 0)
            if not m.call(m.main + 0x282E5D8, m.u64(o + 0x38), scratch, user, p, mv) & 1:
                if not m.u8(scratch):
                    text(0x49, p)
                m.call_void(m.main + 0x157BF08, lst, p)
        i, n = m.u8(lst + 0xA8), m.u8(lst + 0xA6)
        if i >= n:
            break
        m.put(lst + 0xA8, 1, i + 1)
        p = m.u64(lst + 8 * i)
        if not p:
            n = m.u8(lst + 0xA6)
            break
    if m.u8(lst + 0xA7):
        if not n:
            m.call_void(m.main + 0x157BF90, m.u64(o + 0x20), m.vcall(user, 0x98) & M32, 1)
    elif not n and m.u8(lst + 0xA9):
        m.call_void(m.main + 0x157BF90, m.u64(o + 0x20), m.vcall(user, 0x98) & M32, 1)
