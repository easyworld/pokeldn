"""Damage: the formula, type effectiveness, critical hits, the same-type bonus, the hits applied and the
HP changes."""

from pokeldn.sv.battle.engine.calls import M32, M64, _f32, _need, _s32, _tail
from pokeldn.sv.battle.engine.events import _event, _id, _ratio_bounded, _value, ev_param, ev_pop, ev_push
from pokeldn.sv.battle.engine.members import _clear_members
from pokeldn.sv.battle.engine.references import _ref_drop, _ref_take
from pokeldn.sv.battle.engine.statics import _has_static, _held_static
from pokeldn.sv.battle.machine import lifted


@lifted(0x153354C)
def apply_hits_153354c(m, o, _unused, args, *_):
    """For each entry of the hit record *args (12-byte entries from +4, count bytes +0 and +1) marked
    active (bit 3 of +0xa): run 0x28810e4 for its battler (u32 +4) when vf 0x588 holds, and hand the
    result to 0x2881128 with args[4]."""
    rec = m.u64(args)
    if (m.u8(rec) + m.u8(rec + 1)) & 0xFFFFFFFF == 0:
        return
    hits = []
    k = 0
    while k < m.u8(rec) + m.u8(rec + 1):
        e = rec + 4 + 12 * k
        if m.u8(e + 0xA) >> 3 & 1:
            b = m.call(m.main + 0x13813F4, o, m.u32(e + 4))
            hits.append((b, m.u16(e), m.u8(e + 8), m.u8(e + 0xA) & 1))
        k += 1
    for b, move, slot, flag in hits:
        if m.vcall(b, 0x588) & 1:
            v = m.call(m.main + 0x28810E4, o, m.u64(args + 8), m.u64(args + 0x10), m.u64(args + 0x18), b,
                       move, slot, flag)
            m.call_void(m.main + 0x2881128, m.u64(args + 0x20), b, v & 0xFFFFFFFF, 1)


def _scale_entry(m, e, factor):
    """0x1353760: an entry in state 3 (+0xa) scales its s32 +0xc by factor/4096 (rounded), kept within
    [+0x10, +0x14] unless both bounds are 0."""
    if m.u8(e + 0xA) != 3:
        return
    v = ((m.s(e + 0xC, 4) * _s32(factor) + 0x800) & 0xFFFFFFFFFFFFFFFF) >> 12
    v = _s32(v)
    lo, hi = m.s(e + 0x10, 4), m.s(e + 0x14, 4)
    if hi | lo:
        v = min(hi, max(lo, v))
    m.put(e + 0xC, 4, v)


@lifted(0x1353738)
def scale_table_entry(m, t, i, factor, *_):
    """Entry i (below 0x86) of the table at t+0x78 through 0x1353760."""
    i &= 0xFFFF
    if i > 0x85:
        return
    e = m.u64(m.u64(t + 0x78) + 8 + 8 * i)
    if e:
        _scale_entry(m, e, factor)


# Rodata keys the hit-count lookups pass to vf 0x68 of their table (0x3c6b528..0x3c6b550).
_HIT_KEY = {4: 0x3C6B530, 5: 0x3C6B528, 9: 0x3C6B538, 10: 0x3C6B540}


def _per_hit(m, b, d):
    hp = m.vcall(b, 0x140) & 0xFFFF
    d = d or 1
    return hp // d if d <= hp else 1


@lifted(0x114FCD8)
def change_hp(m, o, b, delta, a, c, show, *_):
    """Apply an HP change to the battler: a gain runs vf 0x2e8 and queues command 3 (id, delta u16); a
    loss runs 0x13fced4 (id, -delta, a, c) and queues command 1 (id, c, -delta u16, a u8). With `show`
    set, command 0x9a (id, delta) follows when the battler has a slot."""
    delta &= 0xFFFFFFFF
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    d = _s32(delta)
    if d >= 1:
        m.vcall_void(b, 0x2E8, delta)
        m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 3, ident, delta & 0xFFFF)
    elif d < 0:
        n = (-delta) & 0xFFFFFFFF
        m.call_void(m.main + 0x13FCED4, m.u64(o + 0x20), m.vcall(b, 0x98) & 0xFFFFFFFF, n,
                    a & 0xFFFFFFFF, c & 0xFFFFFFFF)
        i2 = m.vcall(b, 0x98) & 0xFFFFFFFF
        m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 1, i2, c & 0xFFFFFFFF, n & 0xFFFF, a & 0xFF)
    if show & 1 == 0:
        return
    pos = m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), ident)
    if pos & 0xFF == 10:
        return
    m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0x9A, ident, delta)


@lifted(0x1533CA0)
def percent_round(m, a, b, *_):
    """a * b / 100 (32-bit), rounded half up."""
    v = (a * b) & 0xFFFFFFFF
    q, r = divmod(v, 100)
    return q + 1 if r > 0x31 else q


@lifted(0x15F9F38)
def check_kind_4(m, o, flag, a, b, kind, result, *_):
    m.put(flag, 1, 0)
    kind &= 0xFF
    result &= 0xFFFFFFFF
    with m.frame(0x30) as p:
        if result & 0xFF == 0:
            if kind == 4:
                m.put(p, 8, b); m.put(p + 8, 1, 1)
                q = m.call(m.main + 0x15FA02C, m.call(m.main + 0x1361214, o))
                m.call_void(m.main + 0x15FA034, q, p + 0x20, p)
                if m.u8(p + 0x20) == 0:
                    return 7
            return 0
        if kind == 4:
            m.put(p, 8, b); m.put(p + 8, 1, 0)
            q = m.call(m.main + 0x15FA02C, m.call(m.main + 0x1361214, o))
            m.call_void(m.main + 0x15FA034, q, p + 0x20, p)
            if m.u8(p + 0x20) and m.call(m.main + 0x15FA528, m.u64(o + 0x38), a, b) & 1 == 0:
                m.put(flag, 1, 1)
                return 0
        return result


@lifted(0x1533284)
def flag_type_match(m, o, pk, move, *_):
    if not _has_static(m, pk):
        return
    f714 = m.u8(pk + 0x714)
    if f714 == 0 and m.vcall(pk, 0x4D0, 0x1C) & 1 == 0:
        return
    b = m.u8(pk + 0x715)
    t = m.u8(move + 8)
    expect = b if b < 0x13 else 0x12     # the table at 0x3c630a1 (step 2) maps 0..0x12 to itself
    if t == 0x12 or t != expect:
        if b != 0x63:
            return
        r = m.call(m.main + 0x2D2219C, pk, t, m.u16(move))
        if r & 0xFF == 0x12:
            return
        shift = 0x1F if r & 0xFF == 0x63 else r & 0x1F
        if m.u32(pk + 0x71C) >> shift & 1:
            return
    base = m.u64(m.u64(o + 0x40) + 8)
    m.put(base + m.u8(base + 0x938) * 0xC4 + 0x1F, 1, 1)


@lifted(0x2D2219C)
def effective_type(m, b, t, move, *_):
    """The type a move takes: 0x1f for moves 0x353 and 0x38a (the latter when vf 0x88(0x3fd)) on a
    battler holding the static, flagged at +0x714 and with 0x63 at +0x715; else `t`."""
    t &= 0xFFFFFFFF
    if not _has_static(m, b) or m.u8(b + 0x714) == 0 or m.u8(b + 0x715) != 0x63:
        return t
    move &= 0xFFFF
    if move == 0x353:
        return 0x1F
    if move == 0x38A:
        return 0x1F if m.vcall(b, 0x88, 0x3FD) & 1 else t
    return t


@lifted(0x28764E0)
def base_damage(m, o, p, *_):
    """The damage formula over (power, level, attack, defense) at p: ((2 * level / 5 + 2) * power *
    attack / defense) / 50 + 2, unless the reference-counted object at +0x128 holds a replacement
    function (+0x30, called with its +0x50)."""
    obj = m.u64(o + 0x128)
    if obj:
        fn = m.u64(obj + 0x30)
        if m.u32(obj + 0x28) == 0:
            _need(m, m.u64(m.u64(obj) + 0x10))
        if fn:
            _need(m, fn)
        _ref_take(m, obj)
        fn = m.u64(obj + 0x30)
        _ref_drop(m, obj)
        if fn:
            obj = m.u64(o + 0x128)
            _ref_take(m, obj)
            r = m.call(m.u64(obj + 0x30), obj + 0x50, p) & 0xFFFFFFFF
            _ref_drop(m, obj)
            return r
    power, level, attack, defense = m.u32(p), m.u32(p + 4), m.u32(p + 8), m.u32(p + 0xC)
    v = (attack * power * ((((level << 1) & 0xFFFFFFFF) // 5 + 2) & 0xFFFFFFFF)) & 0xFFFFFFFF
    v = v // defense if defense else 0
    return (v // 50 + 2) & 0xFFFFFFFF


@lifted(0x1535450)
def record_hits(m, o, _x1, ctx, *_):
    """For each of the u8 [ctx+0x18] targets ([ctx+0x20]: battlers at +0, u16 amounts at +0x30): add the
    battler to the member list [ctx+0x28] (pointers +0, u16 sums +0x58, +0x6e, flags +0x84, count +0xa6,
    high mark +0xa7, at most 11) and add the amount to every matching entry, then hand the hit to the
    target's handler (0xf21c94, vf 0x788), message 0x42 and vf 0x508(2)."""
    i = 0
    while i < m.u8(ctx + 0x18):
        lst = m.u64(ctx + 0x28)
        hits = m.u64(ctx + 0x20)
        v = m.u64(hits + 8 * i)
        amount = m.u16(hits + 0x30 + 2 * i)
        n = m.u8(lst + 0xA6)
        if v and n < 0xB and all(m.u64(lst + 8 * k) != v for k in range(n)):
            m.put(lst + 8 * n, 8, v)
            m.put(lst + 0x84 + m.u8(lst + 0xA6), 1, 0)
            m.put(lst + 0x58 + 2 * m.u8(lst + 0xA6), 2, 0)
            m.put(lst + 0x6E + 2 * m.u8(lst + 0xA6), 2, 0)
            n = (m.u8(lst + 0xA6) + 1) & 0xFF
            m.put(lst + 0xA6, 1, n)
            if m.u8(lst + 0xA7) < n:
                m.put(lst + 0xA7, 1, n)
        if n:
            if m.u64(lst) == v:
                m.put(lst + 0x58, 2, m.u16(lst + 0x58) + amount)
                m.put(lst + 0x84, 1, 1)
                n = m.u8(lst + 0xA6)
            if n >= 2:
                if m.u64(lst + 8) == v:
                    m.put(lst + 0x5A, 2, m.u16(lst + 0x5A) + amount)
                    m.put(lst + 0x85, 1, 1)
                    n = m.u8(lst + 0xA6)
                if n >= 3:
                    k = 0
                    while True:
                        if m.u64(lst + 0x10 + 8 * k) == v:
                            m.put(lst + 0x5C + 2 * k, 2, m.u16(lst + 0x5C + 2 * k) + amount)
                            m.put(lst + 0x86 + k, 1, 1)
                            n = m.u8(lst + 0xA6)
                        k += 1
                        if k + 2 >= n:
                            break
        target = m.u64(hits + 8 * i)
        amount = m.u16(hits + 0x30 + 2 * i)
        root = m.u64(m.u64(m.u64(o + 0x78) + 0x60) + 0x20)
        move = m.u64(ctx + 0x10)
        mid, b8, b9 = m.u16(move), m.u8(move + 8), m.u8(move + 9)
        user = m.u64(ctx)
        flag = m.u8(ctx + 8)
        tid = m.vcall(target, 0x98) & 0xFFFFFFFF
        uid = m.vcall(user, 0x98) & 0xFFFFFFFF
        with m.frame(0x10) as p:
            m.put(p, 2, mid); m.put(p + 2, 2, amount); m.put(p + 4, 1, b9); m.put(p + 5, 1, b8)
            m.put(p + 8, 4, uid); m.put(p + 0xC, 1, flag)
            h = m.call(m.main + 0xF21C94, m.u64(m.u64(m.u64(root + 0x20) + 0x10) + 0x30), tid)
            m.vcall_void(h, 0x788, p)
        que = m.u64(root + 0x18)
        tid = m.vcall(target, 0x98) & 0xFFFFFFFF
        uid = m.vcall(user, 0x98) & 0xFFFFFFFF
        m.call_void(m.main + 0x119AFF0, que, 0x42, tid, uid, flag, b8, b9, mid, amount)
        m.vcall_void(m.u64(m.u64(ctx + 0x20) + 8 * i), 0x508, 2)
        i += 1


@lifted(0x15368CC)
def damage_messages(m, o, user, move, n, targets, effects, amounts, *_):
    """For each of n targets: 0x13fced4([o+0x20], target, amount, 3, user) and message 2 (target, user,
    amount, 3); then group 0xd0 of (target id, effect byte) pairs, and message 0x8e (n, 2 when an effect
    byte is above 7, else 3 when one is below 7, else 1, the u16 move)."""
    n &= 0xFFFFFFFF
    hi = lo = 0
    for i in range(n):
        t = m.u64(targets + 8 * i)
        amount = m.u16(amounts + 2 * i)
        uid = m.vcall(user, 0x98) & 0xFFFFFFFF
        tid = m.vcall(t, 0x98) & 0xFFFFFFFF
        m.call_void(m.main + 0x13FCED4, m.u64(o + 0x20), tid, amount, 3, uid)
        tid = m.vcall(t, 0x98) & 0xFFFFFFFF
        m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 2, tid, uid, amount, 3)
        e = m.u8(effects + i)
        hi += e > 7
        lo += e < 7
    que = m.u64(o + 0x18)
    at = m.u32(que + 0x68)
    m.put(que + 0x70 + at, 1, 0)
    m.put(que + 0x70 + ((at + 1) & 0xFFFFFFFF), 1, 0xD0)
    m.put(que + 0x68, 4, at + 3)
    m.put(que + 0x70 + ((at + 2) & 0xFFFFFFFF), 1, n << 1)
    for i in range(n):
        q = m.u64(o + 0x18)
        v = m.vcall(m.u64(targets + 8 * i), 0x98)
        at = m.u32(q + 0x68); m.put(q + 0x68, 4, at + 1); m.put(q + 0x70 + at, 1, v)
        q = m.u64(o + 0x18)
        at = m.u32(q + 0x68); m.put(q + 0x68, 4, at + 1); m.put(q + 0x70 + at, 1, m.u8(effects + i))
    k = 2 if hi & 0xFF else (3 if lo & 0xFF else 1)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x8E, n & 0xFF, k, m.u16(move))


@lifted(0x1353730)
def scale_record_of(m, o, index, factor, *_):
    return _tail(m, m.main + 0x1353738, m.u64(o + 0x38), index, factor)


@lifted(0x2844B30)
def scale_34_if_c(m, o, *_):
    """When entry 0x16 is 0xc and the battler of entry 3 qualifies, scale record 0x34 by 0x14cd/4096."""
    if m.call(m.main + 0x2844360, o, 0x16) & M32 != 0xC:
        return
    ident = m.call(m.main + 0x2844360, o, 3)
    if m.call(m.main + 0x2844800, o, ident & M32) & 1 == 0:
        return
    return _tail(m, m.main + 0x1353730, o, 0x34, 0x14CD)


# Critical-hit odds by stage 0..3 (rodata 0x3bb273c): one in 24, 8, 2, 1.
_CRIT_ODDS = (24, 8, 2, 1)


@lifted(0x282DF44)
def critical_hit(m, o, a, b, move, out, *_):
    """Whether attacker a lands a critical hit on b with `move`: field 12 of the move (6 = always) plus
    a's vf 0x290 gives the stage, event 0x45 (parameters 4/3 the ids, 0x2f the stage, 0x48 a block)
    adjusts it; stage 0..3 rolls one in 24/8/2/1, halved odds (shift) for a flag the 0x460 check sets,
    which goes to [out] on a crit. Rule bit 14 of +0x498 forbids crits."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    f = fb.u8(m, m.call(m.main + 0xBF60CC, table, move & M32), 12)
    always = f == 6
    stage = 6 if always else (f + (m.vcall(a, 0x290) & 0xFF)) & M32
    def read(ctx):
        return _value(m, ctx, 0x248), _value(m, ctx, 0x180)
    blocked, stage = _event(m, o, 0x45, ((4, _id(m, b), 4, 0x28), (3, _id(m, a), 4, 0x20), (0x2F, stage, 0, 0x180),
                                         (0x48, 0, 1, 0x248)), None, read)
    blocked = int(blocked != 0)
    if always or blocked:
        return blocked ^ 1
    stage = min(_s32(stage), 3) & 0xFF
    rule = m.u64(m.u64(o + 8) + 0x38)
    flag = 0
    if not m.u8(rule + 0x499) & 4 and m.u32(rule + 0x30) <= 1:
        x = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x18) + 0x290) + 8) + 0x50), m.vcall(a, 0x98) & M32)
        if not (x and m.s(x, 4) <= 4 and m.s(x, 4) != 0):
            flag = int(m.vcall(a, 0x460) & 0xFF == 0xFF)
    if stage > 3:
        return 0
    n = _CRIT_ODDS[stage] >> flag or 1
    crit = 1 if n < 2 else int(m.call(m.main + 0x11440F0, m.u64(m.u64(o + 0x18) + 0x10), n) & 0xFF == 0)
    if not crit or m.u64(rule + 0x498) >> 14 & 1:
        return 0
    m.put(out, 1, flag)
    return 1


@lifted(0x283355C)
def survive_hit(m, o, a, b, flag, dmg, *_):
    """When damage [dmg] would knock b out: event 0x97 (parameters 3/4 the ids, 0x59 flag, 0x3f 0) may name
    a survival kind; else a roll below the 0x460-based percent gives 5, the rule's 0x1142e68 check 6, a
    held flag (+0x714) 7. A kind leaves b at 1 HP ([dmg] = HP - 1) and comes back; 0 otherwise."""
    hp = m.vcall(b, 0x108) & 0xFFFF
    if m.u16(dmg) < hp:
        return 0
    kind = _event(m, o, 0x97, ((3, _id(m, a), 4, 0x20), (4, _id(m, b), 4, 0x28), (0x59, flag & 1, 4, 0x2D0),
                               (0x3F, 0, 1, 0x200)), 0x200)
    if kind & 0xFF == 0:
        rule = m.u64(m.u64(o + 8) + 0x38)
        pct = 0
        if not m.u8(rule + 0x499) & 4 and m.u32(rule + 0x30) <= 1:
            x = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x18) + 0x290) + 8) + 0x50), m.vcall(b, 0x98) & M32)
            if not (x and m.s(x, 4) < 5 and m.s(x, 4) != 0):
                f = m.vcall(b, 0x460) & 0xFF
                pct = 0x14 if f == 0xFF else 0xF if f >= 0xDC else 10 if f >= 0xB4 else 0
        if m.call(m.main + 0x114DA8C, m.u64(m.u64(o + 0x18) + 0x10), pct) & 1:
            kind = 5
        elif m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49A) & 0x20 and \
                m.call(m.main + 0x1142E68, m.u64(o + 8), m.u64(o + 0x18), b) & 1:
            kind = 6
        else:
            if not _held_static(m, b):
                return 0
            if not (m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49A) & 2
                    and not m.call(m.main + 0x1142E68, m.u64(o + 8), m.u64(o + 0x18), b) & 1 and m.u8(b + 0x714)):
                return 0
            kind = 7
    m.put(dmg, 2, (m.vcall(b, 0x108) - 1) & 0xFFFF)
    return kind & M32


@lifted(0x2D0C404)
def type_bonus(m, o, b, t, *_):
    """The same-type bonus (4096 = x1) of battler b for move type t, Terastallized types included:
    events 0x57 (parameters 2 b's id, 0x59 vf 0x300(t)) and 0x58 (0x4b whether 0x59 came back set, 0x38
    the bonus) on one frame, then the Tera rules (x2 / x2.25 for a matching Tera type, x1.2 floor for a
    Tera type a type of b's does not carry)."""
    u4 = m.vcall(b, 0x300, t) & 1
    held = _held_static(m, b)
    stellar_none = not held
    p = b if held else 0
    if not held or not m.u8(b + 0x714) or m.u8(b + 0x715) == 0x63:
        bonus, u5, u20 = 0x1000, 1, 1
    else:
        u5 = (m.call(m.main + 0x2D1F884, b) & 1) ^ 1
        u6 = m.vcall(b, 0x300, t) & 1
        u7 = m.call(m.main + 0x2D1F784, b, t) & 1
        u20 = u6 ^ 1
        bonus = 0x1800 if u6 | u7 else 0x1000
    ev_push(m, m.u64(o + 0x10))
    ev_param(m, m.u64(o + 0x10), 2, m.vcall(b, 0x98) & M32, 4, 0x18)
    ev_param(m, m.u64(o + 0x10), 0x59, u4, 1, 0x2D0)
    m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), 0x57, 8, 1)
    r = _value(m, m.u64(o + 0x10), 0x2D0)
    base = 0x1800 if r else bonus
    ev_param(m, m.u64(o + 0x10), 0x4B, int(r != 0), 4, 0x260)
    ev_param(m, m.u64(o + 0x10), 0x38, base, 0, 0x1C8)
    m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), 0x58, 8, 1)
    v = _value(m, m.u64(o + 0x10), 0x1C8)
    if (u5 | u20) & 1 == 0:
        res = 0x2400 if v == 0x2000 else 0x2000
    elif stellar_none or not m.u8(p + 0x714) or m.u8(p + 0x715) != 0x63:
        res = v
    elif t & 0xFF == 0x12:
        res = base
    else:
        tt = 0x1F if t & 0xFF == 99 else t
        if (m.u32(p + 0x71C) >> (tt & 0x1F)) & 1:
            res = base
        else:
            res = 0x2000 if base == 0x1800 else 0x1333
    ev_pop(m, m.u64(o + 0x10))
    return res & M32


@lifted(0x176923C)
def drain_amount(m, o, b, move, base, out, *_):
    """The HP percentage effect of `move` for b (field 3 of the move 8 means none): event 0x6b (parameters
    3 b's id, 0x38 the move's 0x1419734 percent or, failing that, 0x141a340's, 0x39, 0x48, 0x59) adds
    0x39 to 0x38; a 0x48 without 0x59 or a zero sum gives 0. The amount is that percent (at least 1) of
    `base`, or of b's max HP for a 0x141a340 move; [out] = 0x59 set."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    ident = m.vcall(b, 0x98) & M32
    with m.frame(0x10) as k:
        m.put(k, 8, m.u64(m.main + 0x46DDAD8) + 0x10); m.put(k + 8, 2, move)
        d = m.call(m.main + 0x1419734, k) & 0xFF
        m.put(out, 1, 0)
        use_hp = False
        if d == 0:
            m.put(k, 8, m.u64(m.main + 0x46DDAD8) + 0x10); m.put(k + 8, 2, move)
            d = m.call(m.main + 0x141A340, k) & 0xFF
            use_hp = d != 0
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    if fb.u8(m, m.call(m.main + 0xBF60CC, table, move & M32), 3) == 8:
        return 0
    def read(ctx):
        return (_value(m, ctx, 0x1C8), _value(m, ctx, 0x248) & 0xFF, _value(m, ctx, 0x2D0) & 0xFF,
                _value(m, ctx, 0x1D0))
    a, blocked, kept, extra = _event(m, o, 0x6B, ((3, ident, 4, 0x20), (0x38, d, 0, 0x1C8), (0x39, 0, 0, 0x1D0),
                                                  (0x48, 0, 1, 0x248), (0x59, 0, 1, 0x2D0)), None, read)
    if blocked and not kept:
        return 0
    pct = (extra + a) & 0xFF
    if pct == 0:
        return 0
    if use_hp:
        base = m.vcall(b, 0x140) & 0xFFFF
    elif base & M32 == 0:
        m.put(out, 1, int(kept != 0))
        return 0
    v = m.call(m.main + 0x1769890, m.call(m.main + 0x1533CA0, base & M32, pct), 1)
    m.put(out, 1, int(kept != 0))
    return v


# Type chart (rodata 0x3c6286c): attacking type row, defending type column; 0 none, 2 half, 4 normal,
# 8 double.
_TYPE_CHART = (
    (4, 4, 4, 4, 4, 2, 4, 0, 2, 4, 4, 4, 4, 4, 4, 4, 4, 4), (8, 4, 2, 2, 4, 8, 2, 0, 8, 4, 4, 4, 4, 2, 8, 4, 8, 2),
    (4, 8, 4, 4, 4, 2, 8, 4, 2, 4, 4, 8, 2, 4, 4, 4, 4, 4), (4, 4, 4, 2, 2, 2, 4, 2, 0, 4, 4, 8, 4, 4, 4, 4, 4, 8),
    (4, 4, 0, 8, 4, 8, 2, 4, 8, 8, 4, 2, 8, 4, 4, 4, 4, 4), (4, 2, 8, 4, 2, 4, 8, 4, 2, 8, 4, 4, 4, 4, 8, 4, 4, 4),
    (4, 2, 2, 2, 4, 4, 4, 2, 2, 2, 4, 8, 4, 8, 4, 4, 8, 2), (0, 4, 4, 4, 4, 4, 4, 8, 4, 4, 4, 4, 4, 8, 4, 4, 2, 4),
    (4, 4, 4, 4, 4, 8, 4, 4, 2, 2, 2, 4, 2, 4, 8, 4, 4, 8), (4, 4, 4, 4, 4, 2, 8, 4, 8, 2, 2, 8, 4, 4, 8, 2, 4, 4),
    (4, 4, 4, 4, 8, 8, 4, 4, 4, 8, 2, 2, 4, 4, 4, 2, 4, 4), (4, 4, 2, 2, 8, 8, 2, 4, 2, 2, 8, 2, 4, 4, 4, 2, 4, 4),
    (4, 4, 8, 4, 0, 4, 4, 4, 4, 4, 8, 2, 2, 4, 4, 2, 4, 4), (4, 8, 4, 8, 4, 4, 4, 4, 2, 4, 4, 4, 4, 2, 4, 4, 0, 4),
    (4, 4, 8, 4, 8, 4, 4, 4, 2, 2, 2, 8, 4, 4, 2, 8, 4, 4), (4, 4, 4, 4, 4, 4, 4, 4, 2, 4, 4, 4, 4, 4, 4, 8, 4, 0),
    (4, 2, 4, 4, 4, 4, 4, 8, 4, 4, 4, 4, 4, 8, 4, 4, 2, 2), (4, 8, 4, 2, 4, 4, 4, 4, 2, 2, 4, 4, 4, 4, 4, 8, 8, 4))
# Effectiveness level -> factor (rodata 0x3c629b0).
_EFFECT_FACTOR = (0, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096)
_CHART_LEVEL = {4: 7, 2: 6, 8: 8}


def _chart(t, d):
    return _TYPE_CHART[t][d] if t < 18 and d < 18 else 0


@lifted(0x1330100)
def type_effect_level(m, o, a, b, mtype, dtype, second, *_):
    """The effectiveness level (7 = normal) of move type `mtype` against b's defending type `dtype` for
    attacker a: event 0x50 (0x51 for the second type) with parameters 3/4 the ids, 0x15/0x16 the types,
    0x52/0x53 (0), 0x3d (14) and 0x17 (18), b's own conditions 0x11, 0x15 and 0x20 setting 0x52/0x53;
    0x53 forces 7, a returned 0x3d other than 14 stands, 0x17 a second type combines with it, and 0x52
    turns no effect into 7."""
    event = 0x51 if second & 1 else 0x50
    mtype &= 0xFF
    dtype &= 0xFF
    ev_push(m, m.u64(o + 0x10))
    for kind, value, typ, slot in ((3, _id(m, a), 4, 0x20), (4, _id(m, b), 4, 0x28), (0x15, lambda: dtype, 4, 0xB0),
                                   (0x16, lambda: mtype, 4, 0xB8), (0x52, lambda: 0, 1, 0x298),
                                   (0x53, lambda: 0, 1, 0x2A0), (0x3D, lambda: 0xE, 1, 0x1F0),
                                   (0x17, lambda: 0x12, 1, 0xC0)):
        ev_param(m, m.u64(o + 0x10), kind, value() & M32, typ, slot)
    if m.vcall(b, 0x220, 0x11) & 1:
        with m.frame(0x10) as pair:
            r = m.vcall(b, 0x240, 0x11)
            m.put(pair, 8, r[0]); m.put(pair + 8, 8, r[1])
            v = m.call(m.main + 0xF7FFE0, pair)
            if v & 0xFF == _value(m, m.u64(o + 0x10), 0xB0) & 0xFF:
                k = 0x53 if m.call(m.main + 0x114BD20, pair) & 1 else 0x52
                m.call_void(m.main + 0x15FA4DC, m.u64(o + 0x10), k, 1)
    t16 = _value(m, m.u64(o + 0x10), 0xB8) & 0xFF
    for state in (0x15, 0x20):
        if m.vcall(b, 0x220, state) & 1 and t16 == 4:
            m.call_void(m.main + 0x15FA4DC, m.u64(o + 0x10), 0x52, 1)
    m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), event, 8, 1)
    ctx = m.u64(o + 0x10)
    keep = _value(m, ctx, 0x298)
    force = _value(m, ctx, 0x2A0)
    rec = m.u64(m.u64(ctx + 0x78) + 0xC0)
    other = m.u8(rec + 0xC) if rec else 0
    eff = _value(m, ctx, 0x1F0)
    ev_pop(m, ctx)
    if force:
        return 7
    if eff & 0xFF == 0xE:
        eff = 7
        if mtype != 0x12 and dtype != 0x12:
            c = _chart(mtype, dtype)
            eff = 7 if c == 4 else 6 if c == 2 else c if c in (8, 0) else 0
    if other != 0x12:
        if dtype == 0x12:
            hit, lvl = 1, 7
        else:
            c2 = _chart(other, dtype)
            hit, lvl = (1, _CHART_LEVEL[c2]) if c2 in _CHART_LEVEL else (0, 0)
        f = (_EFFECT_FACTOR[lvl] * _EFFECT_FACTOR[eff & 0xFF] & M32) >> 6
        if f > 0xFFF:
            f = 0x1000
        if hit and eff & 0xFF and f == 0:
            f = 1
        if f == 0:
            eff = 0
        else:
            k = (f & -f).bit_length() - 1
            eff = k + 1 if k < 0xC else 0xD
    if eff & 0xFF == 0 and keep:
        return 7
    return eff & M32


@lifted(0x1353760)
def scale_entry(m, e, factor, *_):
    _scale_entry(m, e, factor)


def _combine_effect(x, y):
    """Two effectiveness levels multiplied (factor 2^(level-1)), back to a level: 0 none, 7 normal, at
    most 13; a nonzero pair never gives none."""
    f = (_EFFECT_FACTOR[x & 0xFF] * _EFFECT_FACTOR[y & 0xFF] & M32) >> 6
    f = f if f < 0x1000 else 0x1000
    if f == 0 and x & 0xFF and y & 0xFF:
        f = 1
    if f == 0:
        return 0
    k = (f & -f).bit_length() - 1
    return k + 1 if k <= 11 else 0xD


@lifted(0x132FEF4)
def type_effectiveness(m, o, a, b, t, flag, *_):
    """The effectiveness level of move type t on b (7 = normal; type 18 is typeless): its first type,
    combined with its second and third when they differ."""
    if t & 0xFF == 0x12:
        return 7
    types = m.vcall(b, 0x2F8) & M32
    t1, t2, t3 = types & 0x1F, (types >> 5) & 0x1F, (types >> 10) & 0x1F
    lvl = m.call(m.main + 0x1330100, o, a, b, t, t1, flag & 1) & M32
    if t3 == 0x12 and t1 == t2:
        return lvl
    if t2 != 0x12 and t2 != t1:
        lvl = _combine_effect(lvl, m.call(m.main + 0x1330100, o, a, b, t, t2, flag & 1))
    if t3 in (t2, 0x12, t1):
        return lvl
    return _combine_effect(lvl, m.call(m.main + 0x1330100, o, a, b, t, t3, flag & 1))


def _level_doubled(lvl):
    """An effectiveness level with its factor doubled (factor 2^(level-1), capped at 4096)."""
    f = (_EFFECT_FACTOR[lvl & 0xFF] & 0x1FFFFFF) << 1
    f = f if f < 0x1000 else 0x1000
    if f == 0 and lvl & 0xFF:
        f = 1
    if f == 0:
        return 0
    k = (f & -f).bit_length() - 1
    return k + 1 if k <= 11 else 0xD


@lifted(0x157BB8C)
def move_effectiveness(m, o, out, r, *_):
    """The effectiveness of record r's move (attacker +0, target +8, move record +0x10, flags +0x18 and
    +0x19) into out (byte; u16 7 first): typeless (18) is 7 and stops for move 0xa5; +0x19 hands over to
    0x2d2532c; else the type chart (0x132fef4), the 0x15f9f38 adjustment, a doubling for type 9 against a
    battler with condition 0x2a, and events 0x52 and 0x53 (0x2d0c9d8)."""
    a, b, mv = m.u64(r), m.u64(r + 8), m.u64(r + 0x10)
    if m.u8(r + 0x19):
        _need(m, m.main + 0x2D2532C)
    m.put(out, 2, 7)
    if m.u8(mv + 8) == 0x12:
        m.put(out, 1, 7)
        if m.u16(mv) == 0xA5:
            return
    if m.u8(r + 0x19):
        return _tail(m, m.main + 0x2D2532C, o, out, r)
    lvl = m.call(m.main + 0x132FEF4, m.u64(o + 0x38), a, b, m.u8(mv + 8), m.u8(r + 0x18))
    if not m.u8(r + 0x18):
        lvl = m.call(m.main + 0x15F9F38, o, out + 1, a, b, m.u8(m.u64(r + 0x10) + 8), lvl & M32)
    if m.u8(m.u64(r + 0x10) + 8) == 9 and m.vcall(m.u64(r + 8), 0x220, 0x2A) & 1:
        lvl = _level_doubled(lvl)
    v = m.call(m.main + 0x2D0C9D8, m.u64(o + 0x38), 0x52, a, b, m.u8(m.u64(r + 0x10) + 8), lvl & M32)
    if not m.u8(r + 0x18):
        v = m.call(m.main + 0x2D0C9D8, m.u64(o + 0x38), 0x53, a, b, m.u8(m.u64(r + 0x10) + 8), v & M32)
    m.put(out, 1, v)


@lifted(0x15343A0)
def apply_hits_15343a0(m, o, _x, r, *_):
    """r = (user, state, hits, extra); hits holds p[0]+p[1] entries of 0xc bytes from +4 (u16 amount,
    u32 target id, flags at +0xa). Once per state ([state+1] == 0) 0x1535060 per target, then
    0x153485c per target; bump [state+1]; 0x1149414(user) per entry with flag bit 0; then each target
    takes vf 0x550(2, amount) and command 0x37, plus vf 0x550(5, 1) when flag bit 3 is clear."""
    def count(p):
        return m.u8(p) + m.u8(p + 1)

    def battler(ident):
        return m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), ident & M32)

    user, state, extra = m.u64(r), m.u64(r + 8), m.u64(r + 0x18)
    p = m.u64(r + 0x10)
    if m.u8(state + 1) == 0 and count(p):
        i = 0
        while i < count(p):
            m.call_void(m.main + 0x1535060, m.u64(o + 0x38), user, battler(m.u32(p + 8 + 0xC * i)), extra)
            i += 1
    p = m.u64(r + 0x10)
    i = 0
    while i < count(p):
        m.call_void(m.main + 0x153485C, m.u64(o + 0x38), user, battler(m.u32(p + 8 + 0xC * i)), extra)
        i += 1
    m.put(state + 1, 1, m.u8(state + 1) + 1)
    p = m.u64(r + 0x10)
    if not count(p):
        return
    user = m.u64(r)
    i = 0
    while i < count(p):
        if m.u8(p + 0xE + 0xC * i) & 1:
            m.call_void(m.main + 0x1149414, m.u64(o + 0x20), m.vcall(user, 0x98) & M32, 0)
        i += 1
    p = m.u64(r + 0x10)
    i = 0
    while i < count(p):
        e = p + 4 + 0xC * i
        ident, amount = m.u32(e + 4), m.u16(e)
        for kind, v in ((2, amount),) + (((5, 1),) if not m.u8(e + 0xA) >> 3 & 1 else ()):
            c = m.u64(o + 0x20)
            b = m.call(m.main + 0xF21C94, m.u64(m.u64(m.u64(c + 0x20) + 0x10) + 0x30), ident)
            m.vcall_void(b, 0x550, kind, v)
            m.call_void(m.main + 0x119AFF0, m.u64(c + 0x18), 0x37, ident, kind, v)
        i += 1


def _slot_level(m, o, b):
    slots = m.u64(m.u64(m.u64(m.call(m.main + 0x1482534, o) + 0x290) + 8) + 0x50)
    p = m.call(m.main + 0x10E2DD4, slots, m.vcall(b, 0x98) & M32)
    v = m.s(p, 4) if p else 0
    return v if v < 5 else 0


def _scale12(v, factor):
    """(v * factor) >> 12 in 32 bits, rounded up when the dropped part exceeds 0x800."""
    p = (v * factor) & M32
    return (p >> 12) + (1 if p & 0xFFF > 0x800 else 0)


def _percent_factor(pct):
    """int32(float32(pct) / 100 * 4096 +- 0.5), as float32 operations."""
    q = _f32(_f32(float(pct)) / _f32(100.0))
    x = _f32(_f32(q * 4096.0) + (0.5 if q > 0 else -0.5))
    if x != x:
        return 0
    return max(-0x80000000, min(0x7FFFFFFF, int(x))) & M32


@lifted(0xF7C344)
def damage(m, o, att, dfn, mv, eff, scale, crit, fixed_roll, b9, weather, out, *_):
    """The damage of the move record mv (+0 move, +4 power, +8 type, +9 category, +0xb, +0xc) from att to
    dfn: events 0x93, 0x5d / 0x5e (a fixed amount or none), 0x47 / 0x48 (power), 0x49 / 0x4b / 0x4c
    (attack, its battler and stat), 0x4a / 0x4d (defense), the base formula 0x28764e0, `scale`, weather 0x56,
    spread 0x2d, critical hit, the random roll, same-type bonus, effectiveness level `eff` (7 = x1), burn,
    then 0x5f / 0x60. out (u16) = the damage (at least 1); returns whether 0x5e / 0x5d fixed it."""
    ctx = lambda: m.u64(o + 0x10)
    P = lambda kind, value, typ, slot: ev_param(m, ctx(), kind, value & M32, typ, slot)
    fire = lambda ev: m.call_void(m.main + 0xF7B310, ctx(), ev, 8, 1)
    val = lambda slot: _value(m, ctx(), slot)
    val16 = lambda slot: (m.u16(m.u64(m.u64(ctx() + 0x78) + slot) + 0xC) if m.u64(m.u64(ctx() + 0x78) + slot) else 0)
    named = lambda key: m.vcall(m.call(m.main + 0x11521A0, o), 0x68, key) & M32
    idf = lambda b: m.vcall(b, 0x98) & M32
    eff &= 0xFF; crit &= 1; b9 &= 1; weather &= 0xFF
    # event 0x93
    ev_push(m, ctx())
    P(2, idf(dfn), 4, 0x18); P(0x60, 0, 1, 0x308); P(0x76, 0, 1, 0x3B8)
    fire(0x93)
    r60 = val(0x308)
    ev_pop(m, ctx())
    # events 0x5d / 0x5e on the outer frame, kept open to the end
    ev_push(m, ctx())
    P(0x3D, eff, 4, 0x1F0)
    P(3, idf(att), 4, 0x20); P(4, idf(dfn), 4, 0x28); P(0x4C, crit, 4, 0x268)
    P(0x16, m.u8(mv + 8), 4, 0xB8); P(0x12, m.u16(mv), 4, 0x98); P(99, m.u8(mv + 0xB), 4, 0x320)
    P(0x1B, m.u8(mv + 9), 4, 0xE0); P(0x19, m.u32(mv + 0xC), 4, 0xD0); P(0x4D, b9, 4, 0x270)
    P(0x60, int(r60 != 0), 4, 0x308); P(0x3A, 0, 0, 0x1D8); P(0x3B, 0, 0, 0x1E0); P(0x3C, 0, 0, 0x1E8)
    fire(0x5D); fire(0x5E)
    fixed, r1e0, r1e8 = val(0x1D8), val(0x1E0), val(0x1E8)
    stopped = int((r1e0 | r1e8) != 0)
    dmg = fixed if r1e8 == 0 else 0
    if not stopped:
        dmg = _damage_body(m, o, att, dfn, mv, eff, scale, crit, fixed_roll, weather, P, fire, val, val16, named,
                           idf, ctx)
    fire(0x60)
    ev_pop(m, ctx())
    dmg &= M32
    if dmg == 0 and r1e8 == 0:
        dmg = 1
    m.put(out, 2, dmg)
    return stopped


def _damage_body(m, o, att, dfn, mv, eff, scale, crit, fixed_roll, weather, P, fire, val, val16, named, idf, ctx):
    # power: events 0x47 / 0x48
    ev_push(m, ctx())
    P(3, idf(att), 4, 0x20); P(4, idf(dfn), 4, 0x28)
    P(0x12, m.u16(mv), 4, 0x98); P(0x16, m.u8(mv + 8), 4, 0xB8); P(0x1B, m.u8(mv + 9), 4, 0xE0)
    P(99, m.u8(mv + 0xB), 4, 0x320); P(0x5D, 0, 1, 0x2F0); P(0x5E, 0, 1, 0x2F8)
    P(0x33, m.u16(mv + 4), 1, 0x1A0)
    fire(0x47)
    _ratio_bounded(m, ctx(), 0x34, 0x1A8, 0x29, 0x200000)
    fire(0x48)
    pw, ratio = val16(0x1A0), val(0x1A8)
    ev_pop(m, ctx())
    if m.vcall(att, 0x4D0, 0x14) & 1:
        ratio = (ratio << int(m.u8(mv + 8) == 0xC)) & M32
    power = _scale12(ratio, pw)
    power = _tera_floor(m, o, att, mv, power)
    # attack: events 0x49 / 0x4b / 0x4c
    ev_push(m, ctx())
    P(3, idf(att), 4, 0x20); P(4, idf(dfn), 4, 0x28); P(0x40, 0, 0, 0x208); P(0x59, 0, 0, 0x2D0)
    fire(0x49)
    raw_atk, alt = val(0x2D0), val(0x208)
    src = att
    if alt:
        src = m.call(m.main + 0xF21C94, m.call(m.main + 0xE7E284, m.u64(o + 0x18)), alt)
    ev_push(m, ctx())
    P(3, idf(src), 4, 0x20); P(0x12, m.u16(mv), 4, 0x98)
    P(0x41, 10 if m.u8(mv + 9) == 2 else 8, 1, 0x210)
    fire(0x4B)
    stat = val(0x210)
    ev_pop(m, ctx())
    if raw_atk:
        slot = 0xB8
    elif crit and stat in (8, 9, 10, 11):
        stage = m.vcall(src, 0xB0, stat - 7) & M32
        slot = 0xB0 if stage < 0x80000000 and stage >= 6 else 0xB8
    else:
        slot = 0xB0
    a = m.vcall(src, slot, stat)
    P(0x12, m.u16(mv), 4, 0x98); P(0x16, m.u8(mv + 8), 4, 0xB8); P(0x1B, m.u8(mv + 9), 4, 0xE0)
    P(0x36, a & 0xFFFF, 0, 0x1B8)
    _ratio_bounded(m, ctx(), 0x38, 0x1C8, 0x19A, 0x20000)
    P(0x5A, 0, 1, 0x2D8)
    fire(0x4C)
    av, ar = val16(0x1B8), val(0x1C8)
    no_burn = int(val(0x2D8) != 0)
    ev_pop(m, ctx())
    atk = _scale12(ar, av)
    # defense: events 0x4a / 0x4d
    cat = m.u8(mv + 9)
    dstat = 0xB if cat == 2 else 9
    ev_push(m, ctx())
    P(3, idf(att), 4, 0x20); P(4, idf(dfn), 4, 0x28); P(0x41, dstat, 4, 0x210)
    P(0x42, 0, 0, 0x218); P(0x59, 0, 1, 0x2D0)
    fire(0x4A)
    raw_def, swap = val(0x2D0), val(0x218)
    ev_pop(m, ctx())
    if swap & 1:
        dstat = 9 if cat == 2 else 0xB
    if raw_def & 0xFF:
        slot = 0xB8
    elif crit:
        slot = 0xE8
    else:
        slot = 0xB0
    d = m.vcall(dfn, slot, dstat) & M32
    if m.call(m.main + 0x116EC0C, o) & 0xFF == 4:
        has = m.vcall(dfn, 0x300, 5)
        if dstat == 0xB and has & 1:
            d = _scale12(d & 0xFFFF, _percent_factor(named(m.main + 0x3C69ED0)))
    if m.call(m.main + 0x116EC0C, o) & 0xFF == 3:
        has = m.vcall(dfn, 0x300, 0xE)
        if dstat == 9 and has & 1:
            d = _scale12(_percent_factor(named(m.main + 0x3C69ED8)), d & 0xFFFF)
    dcat = cat
    if swap & 1:
        dcat = 1 if cat == 2 else 2
    ev_push(m, ctx())
    P(3, idf(att), 4, 0x20); P(4, idf(dfn), 4, 0x28)
    P(0x12, m.u16(mv), 4, 0x98); P(0x16, m.u8(mv + 8), 4, 0xB8); P(0x1B, dcat, 4, 0xE0)
    P(0x37, d & 0xFFFF, 0, 0x1C0)
    _ratio_bounded(m, ctx(), 0x38, 0x1C8, 0x19A, 0x20000)
    fire(0x4D)
    dv, dr = val16(0x1C0), val(0x1C8)
    ev_pop(m, ctx())
    dfv = _scale12(dr, dv)
    # base damage
    with m.frame(0x10) as rec:
        m.put(rec, 4, power & 0xFFFF); m.put(rec + 4, 4, m.vcall(att, 0x118) & 0xFF)
        m.put(rec + 8, 4, atk & 0xFFFF); m.put(rec + 0xC, 4, dfv & 0xFFFF)
        dmg = m.call(m.main + 0x28764E0, m.u64(o + 8), rec) & M32
    scale &= M32
    if scale != 0x1000:
        dmg = _scale12(dmg, scale)
    holder = m.call(m.main + 0x11521A0, o)
    pct = 100
    if 1 <= weather <= 6:
        t = m.u8(mv + 8)
        key = None
        if weather in (1, 6):
            key = {9: 0x46E26D8, 10: 0x46E26D0}.get(t)
        elif weather in (2, 5):
            key = {9: 0x46E26D0, 10: 0x46E26D8}.get(t)
        if key is not None:
            pct = m.vcall(holder, 0x68, m.u64(m.main + key)) & M32
    factor = _percent_factor(pct)
    ev_push(m, ctx())
    P(0x3E, weather, 4, 0x1F8)
    P(2, idf(att), 4, 0x18); P(3, idf(att), 4, 0x20); P(4, idf(dfn), 4, 0x28)
    P(0x12, m.u16(mv), 4, 0x98); P(0x16, m.u8(mv + 8), 4, 0xB8)
    P(0x38, factor, 0, 0x1C8)
    fire(0x56)
    wf = val(0x1C8)
    ev_pop(m, ctx())
    if wf != 0x1000:
        dmg = _scale12(wf, dmg)
    if m.vcall(dfn, 0x220, 0x2D) & 1:
        dmg = ((named(m.main + 0x3C69EA8) * dmg) & M32) // 100
    if crit:
        dmg = ((named(m.main + 0x3C69EB0) * dmg) & M32) // 100
    if not m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49A) >> 4 & 1:
        r = named(m.u64(m.main + 0x46E26C8))
        if not fixed_roll & 1:
            n = (r + 1) & M32
            r = m.call(m.main + 0x11440F0, m.u64(m.u64(o + 0x18) + 0x10), n) if n >= 2 else 0
        dmg = ((((100 - r) & 0xFFFF) * dmg) & M32) // 100
    t = m.u8(mv + 8)
    stab_type = t
    if t == 0x12:
        stab_type = m.call(m.main + 0x2D2219C, att, 0x12, m.u16(mv)) & M32
    if t != 0x12 or stab_type & 0xFF != 0x12:
        dmg = _scale12(m.call(m.main + 0x2D0C404, o, att, stab_type) & M32, dmg)
    dmg &= M32
    if eff == 0:
        dmg = 0
    elif 1 <= eff <= 6:
        dmg >>= 7 - eff
    elif 8 <= eff <= 13:
        dmg = (dmg << (eff - 7)) & M32
    if m.u8(mv + 9) == 1 and m.vcall(att, 0x230) & 0xFFFF == 4 and not no_burn:
        dmg = ((named(m.main + 0x3C69EC0) * dmg) & M32) // 100
    # 0x5f on the outer frame
    _ratio_bounded(m, ctx(), 0x38, 0x1C8, 0x29, 0x20000)
    P(0x35, dmg, 0, 0x1B0); P(100, 0, 1, 0x328); P(0x65, 0, 1, 0x330)
    fire(0x5F)
    return _scale12(val(0x1B0), val(0x1C8))


def _tera_floor(m, o, att, mv, power):
    """A Terastallized battler's move of its Tera type (or a Stellar one's first use of a type) below the
    named floor (0x3c69ec8) is raised to it, outside multi-hit moves (field 9 > 1), moves with positive
    priority-like field 8, and the listed exceptions."""
    node = m.vcall(att + 0x28, 0)
    static = m.call(m.main + 0x2D1FD38)
    while node and node != static:
        node = m.u64(node)
    if not node:
        return power
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    t, key = m.u8(mv + 8), m.u16(mv)
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    if fb.u8(m, m.call(m.main + 0xBF60CC, table, key), 9) > 1:
        return power
    if not m.u8(att + 0x714):
        return power
    has = m.vcall(att, 0x300, t)
    if m.u8(att + 0x714) and m.u8(att + 0x715) == 0x63:
        if t == 0x12:
            return power
        bit = 0x1F if t == 0x63 else t
        if m.u32(att + 0x71C) >> (bit & 31) & 1:
            return power
    elif not has & 1:
        return power
    key = m.u16(mv)
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    rec = m.call(m.main + 0xBF60CC, table, key)
    f8 = fb.u8(m, rec, 8)
    if f8 and (f8 if f8 < 0x80 else f8 - 0x100) > 0:
        return power
    k = m.u16(mv)
    if k < 0x1BF:
        if k < 0x11C:
            if k in (0x43, 0xAF, 0xB3):
                return power
        elif (k - 0x143 < 0x34 and 0x8002000000001 >> (k - 0x143) & 1) or k == 0x11C:
            return power
    elif k <= 0x216:
        if k - 0x1BF < 0x28 and 0xA000008001 >> (k - 0x1BF) & 1:
            return power
    elif k in (0x217, 0x334, 0x390):
        return power
    v = m.vcall(m.call(m.main + 0x11521A0, o), 0x68, m.main + 0x3C69EC8) & M32
    sv = v - (1 << 32) if v & 0x80000000 else v
    return v if sv > (power & 0xFFFF) else power


def _tera_percent(m, user, mv, base, same, other):
    """`base` percent, replaced by `same` (or `other`) read lazily when the user is of the 0x46d3f08 class,
    Terastallized (+0x714) and the move's type is (or is not) its Tera type (0x2a71f50 of +0x715)."""
    if not base:
        return 0
    node = m.vcall(user + 0x28, 0)
    static = m.call(m.main + 0x2D1FD38)
    while node and node != static:
        node = m.u64(node)
    if not node or not m.u8(user + 0x714):
        return base
    t = m.u8(mv + 8)
    v = same() if t == m.call(m.main + 0x2A71F50, m.u8(user + 0x715)) & 0xFF else other()
    return v if v else base


def _percent_round(v, pct):
    """v * pct / 100 in 32 bits, rounded up from a remainder of 50."""
    p = (v * pct) & M32
    return (p // 100 + (1 if p % 100 > 0x31 else 0)) & 0xFFFF


@lifted(0x1535C8C)
def damage_each_target(m, o, out, r, *_):
    """For each target of the list [r+8], the damage 0xf7c344 of user [r] with move record [r+0x10] at the
    target's effectiveness ([r+0x18], 10 {id, level} pairs, 7 when absent) and scale [r+0x20]: raid and
    multi-battle percentages, substitutes (vf 0x588 and 0x1382688) taking min(damage, vf 0x590), the
    0x560(6) survival cap, 0x283355c, then 0x287b2d4 with [r+0x28]. out: +0 hits, +1 substitute hits,
    12-byte rows from +4 {u16 damage, +4 id, +8 level, +9 0x283355c, +0xa flags}. In multi-battles, a
    0x1820eb8 record for the field battler with condition 0x19."""
    rules = lambda: m.u64(m.u64(o + 8) + 0x38)
    user, mv, tab = m.u64(r), m.u64(r + 0x10), m.u64(r + 0x18)
    slot_level = lambda b: _slot_level_of(m, o, m.vcall(b, 0x98) & M32)
    with m.frame(0x20) as sp:
        crit_out, dmgp, capp = sp, sp + 4, sp + 8
        m.put(crit_out, 1, 0)
        m.put(out, 2, 0)
        m.put(m.u64(r + 8) + 0xA8, 1, 0)
        lst = m.u64(r + 8)
        i = m.u8(lst + 0xA8)
        if i < m.u8(lst + 0xA6):
            m.put(lst + 0xA8, 1, i + 1)
            t = m.u64(lst + 8 * i)
            idx = 0
            while t:
                if m.vcall(t, 0x588) & 1:
                    sub = m.call(m.main + 0x1382688, m.u64(o + 0x38), user, t, m.u16(mv)) & 1 ^ 1
                else:
                    sub = 0
                e = out + idx * 0xC
                m.put(e + 8, 4, m.vcall(t, 0x98) & M32)
                key = m.u16(mv)
                crit = _crit_roll(m, o, user, t, key, crit_out)
                m.put(e + 0xE, 1, (m.u8(e + 0xE) & 0xFC) | (crit & 1) | (m.u8(crit_out) << 1) & 0xFF)
                ident = m.u32(e + 8)
                eff = 7
                for k in range(10):
                    if m.u32(tab + 8 * k) == ident:
                        eff = m.u8(tab + 8 * k + 4)
                        break
                m.put(e + 0xC, 1, eff)
                scale = m.u32(r + 0x20)
                tid = m.vcall(t, 0x98) & M32
                f = m.u64(m.u64(o + 0x78) + 0xC80)
                w = m.call(m.main + 0x116EC0C, m.u64(f + 0x38))
                if tid:
                    w = m.call(m.main + 0x116EE6C, m.u64(f + 0x38), tid, w)
                res = m.call(m.main + 0xF7C344, m.u64(o + 0x38), user, t, mv, eff, scale, crit & 1, 0, sub, w & 0xFF,
                             dmgp) & 1
                if m.u8(rules() + 0x49C) >> 1 & 1 and slot_level(user) == 1 and slot_level(t) != 1 \
                        and m.vcall(user, 0x510, 0x1B) & 1:
                    m.put(dmgp, 2, 9999)
                if m.u8(rules() + 0x499) >> 2 & 1 and m.vcall(user, 0x4D0, 0x1B) & 1:
                    m.put(dmgp, 2, _percent_round(m.u16(dmgp), 0x96))
                    b = m.call(m.main + 0x17D5CEC, m.u64(m.u64(o + 0x10) + 0x30), m.vcall(user, 0x98) & M32)
                    if b:
                        m.call_void(m.main + 0x1140198, m.u64(o + 0x20), b, 0x1B)
                pct = _target_percent(m, o, user, t, mv)
                if pct is not None:
                    m.put(dmgp, 2, _percent_round(pct, m.u16(dmgp)))
                fl = (m.u8(e + 0xE) & 0xFB) | (4 if res else 0)
                m.put(e + 0xE, 1, fl)
                dmg = m.u16(dmgp)
                m.put(e + 4, 2, dmg)
                if res:
                    fl &= 0xFC
                    m.put(e + 0xE, 1, fl)
                    m.put(e + 0xC, 1, 7)
                fl = (fl & 0xF7) | (8 if sub else 0)
                m.put(e + 0xE, 1, fl)
                if sub:
                    cap = m.vcall(t, 0x590) & M32
                    m.put(e + 4, 2, cap if cap < dmg else dmg)
                    m.put(e + 0xD, 1, 0)
                    m.put(out + 1, 1, m.u8(out + 1) + 1)
                else:
                    hp = m.vcall(t, 0x108) & 0xFFFF
                    left = hp if hp < dmg else dmg
                    if m.vcall(t, 0x560, 6) & M32 and _survival_cap_applies(m, o, t):
                        p6 = m.vcall(t, 0x560, 6) & M32
                        capv = _percent_round(p6, m.vcall(t, 0x110) & 0xFFFF)
                        if ((hp - left) & M32) <= capv:
                            left = (hp - capv) & M32
                            q = m.u64(o + 0x20)
                            b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), m.vcall(t, 0x98) & M32)
                            m.call_void(m.main + 0x1148470, q, b, 0x19)
                            if m.u8(rules() + 0x49A) >> 1 & 1:
                                m.call_void(m.main + 0x1148894, m.u64(o + 0x48), m.vcall(t, 0x98) & M32)
                    m.put(capp, 2, left)
                    m.put(e + 0xD, 1, m.call(m.main + 0x283355C, m.u64(o + 0x38), user, t, 1, capp))
                    m.put(e + 4, 2, m.u16(capp))
                    m.put(out, 1, m.u8(out) + 1)
                if m.u64(r + 0x28):
                    m.call_void(m.main + 0x287B2D4, m.u64(r + 0x28), m.u64(o + 0x10), user, t, m.u8(e + 0xC))
                lst = m.u64(r + 8)
                i = m.u8(lst + 0xA8)
                if i >= m.u8(lst + 0xA6):
                    break
                idx += 1
                m.put(lst + 0xA8, 1, i + 1)
                t = m.u64(lst + 8 * i)
    _field_record(m, o)


def _slot_level_of(m, o, ident):
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50), ident)
    if not p:
        return 0
    v = m.s(p, 4)
    return v & M32 if v < 5 else 0


def _crit_roll(m, o, user, t, key, crit_out):
    flags = m.u64(m.u64(m.u64(o + 8) + 0x38) + 0x498)
    if flags >> 8 & 1:
        v = m.call(m.main + 0x144E784, o, m.vcall(t, 0x98) & M32)
        if m.call(m.main + 0x200B8A8, m.u64(m.u64(o + 0x10) + 0x290), v) & 1:
            return 0
        flags = m.u64(m.u64(m.u64(o + 8) + 0x38) + 0x498)
    if flags >> 11 & 1 and not m.vcall(t, 0x78) & 1:
        x = m.call(m.main + 0x114E498, o, _slot_level_of(m, o, m.vcall(t, 0x98) & M32))
        if not m.call(m.main + 0x284404C, x) & 0xFF:
            return 0
    return m.call(m.main + 0x282DF44, m.u64(o + 0x38), user, t, key, crit_out) & M32


def _target_percent(m, o, user, t, mv):
    """The raid (rule bit 2: the raid battler as target, record +0x70 == 1, percent +0x2a / +0x2c / +0x2e)
    or multi-battle (rule 0x49c bit 1, target at slot level 1: per-turn row +0x6b4 / +0x6b6 / +0x6b8)
    damage percent; None when neither applies."""
    from pokeldn.sv.battle.engine.raid import _raid_id
    rules = lambda: m.u64(m.u64(o + 8) + 0x38)
    if m.u8(rules() + 0x499) >> 2 & 1:
        ident = m.vcall(t, 0x98) & M32
        if _raid_id(m, m.u64(m.u64(o + 0x10) + 0x310)) == ident:
            rec = m.u64(m.u64(o + 0x10) + 0x310)
            if m.u32(rec + 0x70) == 1:
                base = m.u16(rec + 0x2A)
                if not base:
                    return None
                return _tera_percent(m, user, mv, base, lambda: m.u16(rec + 0x2C), lambda: m.u16(rec + 0x2E))
    if not m.u8(rules() + 0x49C) >> 1 & 1:
        return None
    if _slot_level_raw(m, o, m.vcall(t, 0x98) & M32) != 1:
        return None
    r = m.u64(m.u64(o + 8) + 0x38)
    row = r + m.s(m.u64(m.u64(o + 0x10) + 0x210) + 0x28, 4) * 10
    base = m.u16(row + 0x6B4)
    if not base:
        return None
    return _tera_percent(m, user, mv, base, lambda: m.u16(row + 0x6B6), lambda: m.u16(row + 0x6B8))


def _slot_level_raw(m, o, ident):
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50), ident)
    return m.u32(p) if p else None


def _survival_cap_applies(m, o, t):
    if m.call(m.main + 0x1142E68, m.u64(o + 8), m.u64(o + 0x10), t) & 1:
        return False
    flags = m.u64(m.u64(m.u64(o + 8) + 0x38) + 0x498)
    if flags >> 0xC & 1:
        return True
    if flags >> 0x11 & 1:
        node = m.vcall(t + 0x28, 0)
        static = m.call(m.main + 0x2D1FD38)
        while node and node != static:
            node = m.u64(node)
        if not node:
            return False
        return not m.call(m.main + 0x1142E68, m.u64(o + 8), m.u64(o + 0x10), t) & 1 and bool(m.u8(t + 0x714))
    if flags >> 0x21 & 1:
        return m.u64(m.u64(m.u64(o + 0x10) + 0x210) + 0x28) <= 3
    return False


def _field_record(m, o):
    """Multi-battles: unless a kind-0xf record is queued, a 0x1820eb8 record {field battler id, kind 0xf,
    +0x4c = 2, +0x54 counter, +0x84 order key 0x113ecdc, +0x88 slot level} when the field battler holds
    condition 0x19."""
    rules = lambda: m.u64(m.u64(o + 8) + 0x38)
    if not m.u8(rules() + 0x49C) >> 1 & 1:
        return
    fb_of = lambda: m.call(m.main + 0xFA0028, m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x330) + 8) + 0x30), 1, 0)
    if not m.vcall(fb_of(), 0x510, 0x19) & 1 or not m.u8(rules() + 0x49C) >> 1 & 1:
        return
    q = m.u64(o + 0x48)
    for k in range(m.u8(q + 0x2420)):
        if m.u32(q + 0xC + 0x8C * k) == 0xF:
            return
    x = fb_of()
    with m.frame(0xB0) as sp:
        A, key = sp, sp + 0x90
        m.write(A, bytes(0x8C))
        m.put(A + 0x88, 1, 5); m.put(A + 0x84, 4, 0x5400000); m.put(A + 4, 4, 0xF); m.put(A + 0x4C, 1, 2)
        m.put(A, 4, m.vcall(x, 0x98) & M32)
        m.put(A + 0x88, 1, _slot_level_of(m, o, m.vcall(x, 0x98) & M32))
        m.put(A + 0x89, 2, 0)
        m.put(key + 8, 8, A); m.put(key + 0x10, 2, 0x103)
        m.call_void(m.main + 0x113ECDC, m.u64(m.u64(o + 0x78) + 0x120), key, key + 8)
        m.put(A + 0x84, 4, m.u32(key))
        cnt = m.u64(m.u64(o + 0x10) + 0x190)
        n = m.u32(cnt + 8)
        if n == 0:
            n = 1
            m.put(cnt + 8, 4, 1)
        m.put(A + 0x54, 4, n)
        m.put(cnt + 8, 4, m.u32(cnt + 8) + 1)
        m.call_void(m.main + 0x1820EB8, m.u64(o + 0x48), A)


@lifted(0x114AF54)
def apply_damage(m, o, out, r, *_):
    """r = {battler, u32 amount, u8 +0xc, u32 +0x10, source +0x18, u8 faint check +0x20}: when amount is
    nonzero, 0x1152ae8 / 0x114fcd8 (minus amount) / vf 0x508(2) / 0x114b0ac (when 0x17ce3ac holds for the
    source) / 0x114b5dc / 0x1152da8, the rule 0x49c bit 1 follow-up 0x11519ac, 0x2888690 when +0x20 is
    set; out = 1."""
    rule = m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49C) >> 1 & 1
    if rule and m.u32(r + 8):
        _need(m, m.main + 0x1149510)
        _need(m, m.main + 0x11519AC)
    m.put(out, 1, 0)
    if m.u32(r + 8) == 0:
        return
    m.call_void(m.main + 0x1152AE8, m.call(m.main + 0x1146E90, o), m.u64(r), m.u32(r + 8))
    m.call_void(m.main + 0x114FCD8, m.u64(o + 0x20), m.u64(r), -m.u32(r + 8) & M32, m.u8(r + 0xC),
                m.u32(r + 0x10), 1)
    m.vcall_void(m.u64(r), 0x508, 2)
    src = m.u64(r + 0x18)
    if src and m.call(m.main + 0x17CE3AC, src) & 1:
        q = m.u64(o + 0x20)
        m.call_void(m.main + 0x114B0AC, q, m.vcall(m.u64(r), 0x98) & M32, m.u64(r + 0x18))
    m.call_void(m.main + 0x114B5DC, o, m.u64(r))
    m.call_void(m.main + 0x1152DA8, m.call(m.main + 0x1146E90, o), m.u64(r), m.u32(r + 8))
    if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49C) >> 1 & 1:
        x22 = m.u64(o + 0x10)
        ident = m.vcall(m.u64(r), 0x98) & M32
        p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(x22 + 0x290) + 8) + 0x50), ident)
        if p and m.u32(p) == 1 and m.call(m.main + 0x1149510, m.u64(m.u64(o + 0x10) + 0x330)) & 1:
            m.call_void(m.main + 0x11519AC, m.u64(m.u64(o + 0x78) + 0x1F80))
    if m.u8(r + 0x20):
        m.call_void(m.main + 0x2888690, o, m.u64(r))
    m.put(out, 1, 1)


_HIT_EFFECT = {1: 0x28810A0, 5: 0x1832F0C, 6: 0x1832F0C}


@lifted(0x15327C4)
def apply_hits(m, o, out, p, *_):
    """p = {user, +8, results R, +0x18 move, +0x20, u8 +0x28, +0x30}; R = {u8 n0, u8 n1, entries of 0xc
    bytes from +4: u16 damage, u32 target id +4, u8 +8, u8 effect +9, flags +0xa (bit 3 skip, bits 0..1
    critical)}. Runs 0x153354c and 0x15343a0, gathers the targets not skipped into A (battlers +0, u16
    +0x30, u8 +0x3c, critical +0x42, effect +0x48), then 0x15368cc, 0x1533cc8, 0x1535450, each effect
    (1: 0x28810a0, 5 / 6: 0x1832f0c, else 0x2833bb4), 0x1532dec, 0x1533284, 0x16d9d10 per target and
    0x153379c; with no target, 0x1532dec, 0x1533284 and 0x1532fe4. *out (u32) = the summed damage after
    0x1533ef0."""
    m.put(out, 4, 0)
    R = m.u64(p + 0x10)
    if m.u8(R) + m.u8(R + 1) == 0:
        return
    t = m.u64(o + 0x78)
    pos = m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), m.vcall(m.u64(p), 0x98) & M32)
    with m.frame(0x100) as f:
        A, S, res = f, f + 0xA0, f + 0xD0          # S mirrors the game's x29-0x38 block
        P = [m.u64(p + 8 * k) for k in range(7)]
        for k, v in enumerate((P[2], P[1], P[3], P[0], P[6])):
            m.put(A + 8 * k, 8, v)
        m.call_void(m.main + 0x153354C, m.u64(t + 0x8E0), S, A)
        for k, v in enumerate((m.u64(p), m.u64(p + 0x20), m.u64(p + 0x10), m.u64(p + 0x18))):
            m.put(A + 8 * k, 8, v)
        m.call_void(m.main + 0x15343A0, m.u64(t + 0x540), S, A)
        R = m.u64(p + 0x10)
        c = 0
        if m.u8(R) + m.u8(R + 1):
            x26 = m.u64(t + 0x420)
            k = 0
            while k < m.u8(R) + m.u8(R + 1):
                e = R + 4 + 0xC * k
                fl = m.u8(e + 0xA)
                if not fl >> 3 & 1:
                    m.put(A + 8 * c, 8, m.call(m.main + 0xF21C94, m.u64(m.u64(x26 + 0x10) + 0x30), m.u32(e + 4)))
                    m.put(A + 0x30 + 2 * c, 2, m.u16(e))
                    m.put(A + 0x3C + c, 1, m.u8(e + 8))
                    m.put(A + 0x48 + c, 1, m.u8(e + 9))
                    m.put(A + 0x42 + c, 1, (2 if fl & 2 else 1) if fl & 1 else 0)
                    c += 1
                k += 1
        if c == 0:
            m.put(S, 8, A); m.put(S + 8, 8, m.u64(p + 8)); m.put(S + 0x10, 8, m.u64(p + 0x18))
            m.put(S + 0x18, 8, m.u64(p)); m.put(S + 0x20, 1, 0)
            m.call_void(m.main + 0x1532DEC, m.u64(m.u64(o + 0x78) + 0x1A40), res, S)
            m.call_void(m.main + 0x1533284, o, m.u64(p), m.u64(p + 0x18))
            R = m.u64(p + 0x10)
            if m.u8(R) + m.u8(R + 1):
                m.call_void(m.main + 0x1532FE4, o, m.u64(p), m.u64(p + 0x18))
        else:
            m.call_void(m.main + 0x15368CC, m.u64(o + 0x20), m.u64(p), m.u64(p + 0x18), c, A, A + 0x3C, A + 0x30)
            m.put(S, 8, A); m.put(S + 8, 8, m.u64(p + 0x18)); m.put(S + 0x10, 8, m.u64(p))
            m.put(S + 0x18, 8, m.u64(p + 0x20)); m.put(S + 0x20, 1, c); m.put(S + 0x21, 1, m.u8(p + 0x28))
            m.call_void(m.main + 0x1533CC8, m.u64(m.u64(o + 0x78) + 0x14A0), res, S)
            m.put(S, 8, m.u64(p)); m.put(S + 0x10, 8, m.u64(p + 0x18)); m.put(S + 0x18, 1, c)
            m.put(S + 8, 1, pos); m.put(S + 0x20, 8, A); m.put(S + 0x28, 8, m.u64(p + 0x30))
            m.call_void(m.main + 0x1535450, m.u64(m.u64(o + 0x78) + 0x15C0), res, S)
            for i in range(c):
                kind = m.u8(A + 0x48 + i)
                if kind:
                    x = m.u64(m.u64(o + 0x78) + 0x1340)
                    b = m.u64(A + 8 * i)
                    if kind in _HIT_EFFECT:
                        m.call_void(m.main + _HIT_EFFECT[kind], x, b, kind)
                    else:
                        m.call_void(m.main + 0x2833BB4, m.u64(x + 0x38), b, kind)
            m.put(S, 8, A); m.put(S + 8, 8, m.u64(p + 8)); m.put(S + 0x10, 8, m.u64(p + 0x18))
            m.put(S + 0x18, 8, m.u64(p)); m.put(S + 0x20, 1, c)
            m.call_void(m.main + 0x1532DEC, m.u64(m.u64(o + 0x78) + 0x1A40), res, S)
            m.call_void(m.main + 0x1533284, o, m.u64(p), m.u64(p + 0x18))
            for i in range(max(c, 1)):
                m.call_void(m.main + 0x16D9D10, m.u64(m.u64(m.u64(o + 0x78) + 0x1A60) + 0x38), m.u64(p),
                            m.u64(A + 8 * i), m.u64(p + 0x18), m.u8(A + 0x3C + i), m.u16(A + 0x30 + 2 * i),
                            int(m.u8(A + 0x42 + i) != 0), 0)
            m.put(S, 8, A); m.put(S + 8, 8, m.u64(p + 0x18)); m.put(S + 0x10, 8, m.u64(p + 0x20))
            m.put(S + 0x18, 8, m.u64(p)); m.put(S + 0x20, 1, c)
            m.call_void(m.main + 0x153379C, m.u64(m.u64(o + 0x78) + 0x280), res, S)
    R = m.u64(p + 0x10)
    n = m.u8(R) + m.u8(R + 1)
    total = sum(m.u16(R + 4 + 0xC * k) for k in range(max(n, 1))) & M32 if n else 0
    m.call_void(m.main + 0x1533EF0, m.u64(o + 0x38), m.u64(p), m.u64(p + 0x18), total)
    m.put(out, 4, total)


@lifted(0x176917C)
def recoil_or_drain(m, o, _x, r, *_):
    """r = {b, move, u32 base}: for b standing and not in position 10, the amount 0x176923c; applied
    through 0x176989c when its flag is set, else when 0x2881c1c allows it."""
    b = m.u64(r)
    ident = m.vcall(b, 0x98) & M32
    if m.vcall(b, 0x200) & 1:
        return
    if m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), ident) & 0xFF == 0xA:
        return
    with m.frame(0x10) as f:
        amount = m.call(m.main + 0x176923C, m.u64(o + 0x38), m.u64(r), m.u16(m.u64(r + 8)), m.u32(r + 0x10),
                        f) & M32
        if not amount:
            return
        if m.u8(f) or m.call(m.main + 0x2881C1C, o, m.u64(r), amount) & 1:
            m.call_void(m.main + 0x176989C, o, m.u64(r), amount)


def _scale_4096(v):
    """int(f32(v) / 100 * 4096 + (+-0.5)), all in float32 (0x15322fc)."""
    x = _f32(_f32(float(_s32(v))) / _f32(100.0))
    return int(_f32(_f32(x * _f32(4096.0)) + (0.5 if x > 0 else -0.5)))


@lifted(0x1531FB0)
def apply_move_damage(m, o, out, r, *_):
    """r = {user +0, +8, move +0x10, +0x18, targets list +0x28, +0x30, +0x38, command slots +0x40, +0x48}:
    two target lists (0x1532554, 0x153268c), each through the damage pass 0x1535c8c (spread ratio 0x1000
    for one target, else the rule ratio vf 0x68 of 0x114acbc's object on main+0x3c6a510, as a 4096
    factor) into a hit record, both recorded by 0x15323d4; five commands reserved through 0x10afcb8
    (0x9c, 0x7e x3, 0x8b) into the u16 slots [r+0x40]; then 0x15327c4 on each record, *out += the damage;
    after a first record with damage, a battler on the rule side (0x1536fb0) makes the counted object of
    0x114e480 (0x1142424) run vf 0x48(3, 1). Ends with the raw command bytes 00 d1 01 00 on the queue."""
    from pokeldn.sv.battle.engine.references import _release_ref
    L = m.u64(r + 0x28)
    multi = int(m.u8(L + 0xA6) > 1)
    if m.u8(L + 0xA7) == 1:
        ratio = 0x1000
    else:
        x = m.call(m.main + 0x114ACBC, o)
        ratio = _scale_4096(m.vcall(x, 0x68, m.main + 0x3C6A510))
        L = m.u64(r + 0x28)
    with m.frame(0x400) as sp:
        x29 = sp + 0x380
        L1, L2, H1, H2, A, T = sp + 0x1B8, sp + 0x108, sp + 0x88, sp + 8, x29 - 0x38, x29 - 0xB8
        _clear_members(m, L1)
        _clear_members(m, L2)
        m.call_void(m.main + 0x1532554, L, m.u64(o + 0x10), m.u64(r), L1)
        m.call_void(m.main + 0x153268C, m.u64(r + 0x28), m.u64(o + 0x10), m.u64(r), L2)
        m.write(H1 + 4, bytes(0x78))
        m.write(H2 + 4, bytes(0x78))
        for lst, H in ((L1, H1), (L2, H2)):
            m.put(A, 8, m.u64(r)); m.put(A + 8, 8, lst); m.put(A + 0x10, 8, m.u64(r + 0x10))
            m.put(A + 0x18, 8, m.u64(r + 0x18)); m.put(A + 0x20, 4, ratio); m.put(A + 0x28, 8, m.u64(r + 0x48))
            m.put(T, 2, 0)
            m.write(T + 4, bytes(0x78))
            m.call_void(m.main + 0x1535C8C, m.u64(m.u64(o + 0x78) + 0x140), T, A)
            m.put(H, 2, m.u16(T))
            m.write(H + 4, m.read(T + 4, 0x78))
        m.call_void(m.main + 0x15323D4, o, H1)
        m.call_void(m.main + 0x15323D4, o, H2)
        q = m.u64(o + 0x18)
        slots = m.u64(r + 0x40)
        for off, cmd in ((0, 0x9C), (4, 0x7E), (6, 0x7E), (8, 0x7E), (2, 0x8B)):
            m.put(slots + off, 2, m.call(m.main + 0x10AFCB8, q, cmd, 0xCF, 0))
        for k, H in enumerate((H1, H2)):
            P = T
            m.put(P, 8, m.u64(r)); m.put(P + 8, 8, m.u64(r + 8)); m.put(P + 0x10, 8, H)
            m.put(P + 0x18, 8, m.u64(r + 0x10)); m.put(P + 0x20, 8, m.u64(r + 0x38))
            m.put(P + 0x28, 1, multi); m.put(P + 0x30, 8, m.u64(r + 0x30))
            m.call_void(m.main + 0x15327C4, m.u64(m.u64(o + 0x78) + 0x8C0), A, P)
            dealt = m.u32(A)
            if k == 0 and dealt and m.call(m.main + 0x1536FB0, o, m.u64(r)) & 1:
                x = m.call(m.main + 0x114E480, o)
                m.x8 = T
                m.call_void(m.main + 0x1142424, x)
                obj = m.u64(T)
                m.vcall_void(obj, 0x48, 3, 1)
                obj = m.u64(T)
                if obj:
                    _release_ref(m, obj)
            m.put(out, 4, m.u32(out) + dealt)
        q = m.u64(o + 0x18)
        n = m.u32(q + 0x68)
        for i, v in enumerate((0, 0xD1, 1)):
            m.put(q + 0x70 + ((n + i) & M32), 1, v)
        m.put(q + 0x68, 4, n + 4)
        m.put(q + 0x70 + ((n + 3) & M32), 1, 0)


@lifted(0x2882BE4)
def multi_hit(m, o, out, slots, x3, x4, x5, x6, x7, s0, s1, *_):
    """0x2881cc0 on 0x2882c58([o+0x78]) with {x5, x6, x7, s0, s1, x4, x3} and a result {u32 amount, 10
    bytes of 0xff}: *out = the amount, the 10 bytes copied to `slots`."""
    with m.frame(0x60) as f:
        res, B = f, f + 0x10
        m.put(res + 4, 8, M64); m.put(res + 0xC, 2, 0xFFFF)
        for k, v in enumerate((x5, x6, x7, s0, s1, x4, x3)):
            m.put(B + 8 * k, 8, v)
        m.call_void(m.main + 0x2881CC0, m.call(m.main + 0x2882C58, m.u64(o + 0x78)), res, B)
        m.put(out, 4, m.u32(res))
        m.put(slots + 8, 2, m.u16(res + 0xC)); m.put(slots, 8, m.u64(res + 4))
