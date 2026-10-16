"""The setup's rule value per battler and the rule records moves and effects run."""

from pokeldn.sv.battle.engine.calls import M32, _need, _tail, m_s32
from pokeldn.sv.battle.machine import UnliftedCall, lifted


def _rule_s32(m, pokecon, ident):
    """The setup map's value for `ident` as the game clamps it: below 5 kept (signed), else 0; absent 0."""
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(pokecon + 0x290) + 8) + 0x50), ident)
    if p == 0:
        return None
    v = m.s(p, 4)
    return (v if v < 5 else 0) & 0xFFFFFFFF


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


@lifted(0x1589A40)
def rule_value_290(m, o, key, *_):
    """The setup map's value for `key` ([[o+0x10]+0x290] owner), 0 when absent or above 4."""
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50), key)
    if p == 0:
        return 0
    v = m.s(p, 4)
    return v & 0xFFFFFFFF if v < 5 else 0


def _rule_or_0(m, o, key):
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50), key)
    if p == 0:
        return None
    v = m.s(p, 4)
    return v & 0xFFFFFFFF if v < 5 else 0


@lifted(0x162B830)
def class_matches_95(m, o, ident, *_):
    """Whether battler `ident`'s class in the setup map equals the byte at [o+8]+0x95."""
    from pokeldn.sv.battle.engine.containers import battler
    b = battler(m, m.u64(m.u64(o + 0x10) + 0x30), ident)
    want = m.u64(o + 8)
    v = _rule_or_0(m, o, m.vcall(b, 0x98) & 0xFFFFFFFF)
    return int((v or 0) == m.u8(want + 0x95))


def _class_of(m, o, ident):
    v = _rule_or_0(m, o, ident)
    return 0 if v is None else v


@lifted(0xFA9B4C)
def rule_bits(m, o, mask, *_):
    return int(m.u64(m.u64(o + 0x38) + 0x498) & mask != 0)


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


def _rule_499_bit2(m, o):
    return m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x499) >> 2 & 1


@lifted(0xFECB7C)
def rule_allows_move(m, b, *_):
    """0 when the battler has no rule object (+0x700), its move (+0x47e) has field 6 set, or the
    shared object at [+0x708]+0x190 answers the 0x50fc5612cd4b7875 query; else whether [+0x700]+0xcc
    is set."""
    if m.u64(b + 0x700) == 0:
        return 0
    with m.frame(0x10) as p:
        m.put(p, 8, m.u64(m.main + 0x46DDAC0) + 0x10)
        m.put(p + 8, 2, m.u16(b + 0x47E))
        if m.call(m.main + 0xFECCD8, p) & 1:
            return 0
    holder = m.u64(b + 0x708)
    v = m.vcall(b, 0x2B8, m.u64(b + 0x700)) & 0xFFFFFFFF
    obj = m.u64(holder + 0x190)
    if obj:
        _need(m, m.u64(m.u64(obj) + 0x28))
        count = m.u32(obj + 0x28)
        if count == 0xFFFFFFFF:
            raise UnliftedCall("reference counter overflow abort")
        m.put(obj + 0x28, 4, count + 1)
    r = m.vcall(obj, 0x28, 0x50FC5612CD4B7875, v)
    if obj:
        count = m.u32(obj + 0x28)
        if count == 0:
            raise UnliftedCall("reference counter underflow abort")
        m.put(obj + 0x28, 4, count - 1)
        if count == 1:
            m.vcall_void(obj, 0x10)
    if r & 1:
        return 0
    return int(m.u32(m.u64(b + 0x700) + 0xCC) != 0)


@lifted(0x149FEDC)
def max_118_unmatched(m, o, *_):
    """The largest vf 0x118 byte (at least 1) over the battlers the iterator 0x1147754([o+8], [o+0x10])
    hands out for which 0x1142ecc(0x13813ec([o+0x10]), 0x149fe8c([o+8]), 0x1589a40(o, id)) is false."""
    best = 1
    with m.frame(0x30) as it:
        cur = it + 0x28
        m.put(cur, 8, 0)
        m.call_void(m.main + 0x1147754, it, m.u64(o + 8), m.u64(o + 0x10))
        while m.call(m.main + 0x1360DBC, it, cur) & 1:
            a = m.call(m.main + 0x149FE8C, m.u64(o + 8)) & 0xFFFFFFFF
            ident = m.vcall(m.u64(cur), 0x98) & 0xFFFFFFFF
            c = m.call(m.main + 0x1589A40, o, ident) & 0xFFFFFFFF
            if m.call(m.main + 0x1142ECC, m.call(m.main + 0x13813EC, m.u64(o + 0x10)), a, c) & 1 == 0:
                v = m.vcall(m.u64(cur), 0x118) & 0xFF
                best = max(best, v)
    return best


@lifted(0x179498C)
def query_then_apply(m, o, done, r, *_):
    """r = (a, b, u16 key, pair, byte, u32, u16, byte): build the aux record (0x1146154, 0x1794b18), run
    0x1794f10, then query 0x1795308 with the request; when it answers 0, apply it through 0x17959d4 with
    the aux record and *done = 1."""
    m.put(done, 1, 0)
    with m.frame(0xF0) as sp:
        aux, pair, ans, req = sp + 0x20, sp + 0x10, sp + 0x48, sp + 0x50
        m.call_void(m.main + 0x1146154, aux)
        m.call_void(m.main + 0x1794B18, m.call(m.main + 0x1146E90, o), m.u16(r + 0x10), m.u64(r), m.u64(r + 8), aux)
        m.put(pair, 8, m.u64(r + 0x18)); m.put(pair + 8, 8, m.u64(r + 0x20))
        m.call_void(m.main + 0x1794F10, m.call(m.main + 0x1146E90, o), m.u64(r), m.u64(r + 8), m.u16(r + 0x10), pair)
        a, b, key = m.u64(r), m.u64(r + 8), m.u16(r + 0x10)
        b28, w2c, h30, b32 = m.u8(r + 0x28), m.u32(r + 0x2C), m.u16(r + 0x30), m.u8(r + 0x32)
        m.put(req + 0x10, 2, 0); m.put(req, 8, 0); m.put(req + 8, 8, 0)
        m.call_void(m.main + 0x179372C, req + 0x18)
        m.put(req + 0x2C, 8, 0)
        m.put(req, 8, a); m.put(req + 8, 8, b); m.put(req + 0x10, 2, key)
        m.put(req + 0x28, 1, b28); m.put(req + 0x2C, 4, w2c); m.put(req + 0x31, 2, h30); m.put(req + 0x33, 1, b32)
        m.put(req + 0x18, 8, m.u64(pair)); m.put(req + 0x20, 8, m.u64(pair + 8))
        m.call_void(m.main + 0x1795308, m.call(m.main + 0x1794B08, m.call(m.main + 0x1361214, o)), ans, req)
        if m.u8(ans):
            return
        a, b, key = m.u64(r), m.u64(r + 8), m.u16(r + 0x10)
        m.put(req + 0x10, 2, 0); m.put(req, 8, 0); m.put(req + 8, 8, 0)
        m.call_void(m.main + 0x179372C, req + 0x18)
        m.put(req + 0x28, 2, 1); m.put(req + 0x30, 8, 0); m.put(req + 0x38, 1, 0)
        m.put(req + 0x10, 2, key); m.put(req, 8, a); m.put(req + 8, 8, b)
        m.put(req + 0x18, 8, m.u64(pair)); m.put(req + 0x20, 8, m.u64(pair + 8))
        v = m.call(m.main + 0x17CE3AC, aux)
        m.put(req + 0x38, 1, 0)
        m.put(req + 0x29, 1, ~v & 1)
        m.put(req + 0x30, 8, aux)
        m.call_void(m.main + 0x17959D4, m.call(m.main + 0x1794B10, m.call(m.main + 0x1361214, o)), ans, req)
    m.put(done, 1, 1)


@lifted(0x13808BC)
def check_each_rule(m, o, done, r, *_):
    """r = (key ptr, battler, x, u32, byte): for each of the 0x1380e28(key) rules, 0x13831ec gives a kind
    and value; kind 0 marks the aux record (0x138155c), any other asks 0x1380c5c (kind 9 asks kinds 1..5
    and ORs the answers); a yes runs 0x13836dc and sets *done."""
    m.put(done, 1, 0)
    b = m.u64(r + 8)
    ident = m.vcall(b, 0x98) & M32
    x = m.u64(r + 0x10)
    key = m.u16(m.u64(r))
    with m.frame(0x100) as sp:
        aux, kind_p, val_p, out, req = sp + 0x30, sp + 0x2C, sp + 0x28, sp + 0x50, sp + 0x58
        m.call_void(m.main + 0x1380C4C, aux)
        flag = m.call(m.main + 0x1382688, m.call(m.main + 0x1146E90, o), b, x, key) & 1
        count = m.call(m.main + 0x1380E28, key) & 0xFF
        i = 0
        while count and i != count:
            m.call_void(m.main + 0x13831EC, m.call(m.main + 0x1146E90, o), key, i, b, x, kind_p, val_p)
            kind = m.u8(kind_p)
            if not kind:
                m.call_void(m.main + 0x138155C, aux, 1)
            else:
                value, w, c = m.u32(val_p), m.u32(r + 0x18), m.u8(r + 0x1C)
                yes = 0
                for k in (range(1, 6) if kind == 9 else (kind,)):
                    m.put(req + 0x10, 1, k); m.put(req + 0x1A, 8, 0); m.put(req + 0x14, 4, value)
                    m.put(req + 0x18, 1, 0); m.put(req, 4, ident); m.put(req + 8, 8, x)
                    m.put(req + 0x1C, 4, w); m.put(req + 0x20, 1, c); m.put(req + 0x21, 1, flag)
                    m.put(req + 0x28, 8, aux); m.put(req + 0x30, 1, 1); m.put(req + 0x38, 8, 0); m.put(req + 0x40, 1, 0)
                    m.call_void(m.main + 0x1380C5C, m.u64(m.u64(o + 0x78) + 0x1580), out, req)
                    yes |= m.u8(out)
                if yes:
                    m.call_void(m.main + 0x13836DC, m.call(m.main + 0x1146E90, o), x, key, kind, m.u32(val_p))
                    m.put(done, 1, 1)
            i += 1
        m.call_void(m.main + 0x1380C48, aux)


@lifted(0x2880128)
def rule_case_4(m, o, rule, *_):
    """0x283e66c for every member 0x18ffcd0 matches to `rule`."""
    with m.frame(0x50) as sp:
        n = m.call(m.main + 0x18FFCD0, o, rule, sp + 8) & M32
        for i in range(n if n < 0x80000000 else 0):
            m.put(sp + 0x48, 4, m.u32(sp + 8 + 4 * i))
            x = m.call(m.main + 0x283E664, m.call(m.main + 0x1361214, o))
            m.call_void(m.main + 0x283E66C, x, sp, sp + 0x48)


@lifted(0x2880194)
def rule_case_8(m, o, rule, *_):
    """A rank change record (user [rule], target, kind 0x10, descriptor 0x1794970(user, target, 1), flag
    +0x25, +0x27 for species 0xd7) through 0x19042ec for every matched member."""
    with m.frame(0x80) as sp:
        ids = sp + 0x58
        n = m.call(m.main + 0x18FFCD0, o, rule, ids) & M32
        for i in range(n if n < 0x80000000 else 0):
            ident = m.u32(ids + 4 * i)
            bb = m.call(m.main + 0x13813F4, o, ident)
            rec = sp + 8
            m.call_void(m.main + 0x283E210, rec)
            user = m.u32(rule)
            m.put(rec, 4, user); m.put(rec + 4, 4, ident); m.put(rec + 8, 2, 0x10)
            d = m.call(m.main + 0x1794970, user, ident, 1)
            m.put(rec + 0x10, 8, d[0]); m.put(rec + 0x18, 8, d[1])
            if m.vcall(bb, 0xF8) & 0xFFFF == 0xD7:
                m.put(rec + 0x27, 1, 1)
            m.put(rec + 0x25, 1, 1)
            x = m.call(m.main + 0x19042E4, m.call(m.main + 0x1361214, o))
            m.call_void(m.main + 0x19042EC, x, sp, rec)


@lifted(0x2880274)
def rule_case_10(m, o, rule, *_):
    """Unless byte +0x38 is 2: 0x283f0dc with {[rule], +0x38 byte, 0, 0, 0, 0, 1}."""
    kind = m.u8(rule + 0x38)
    if kind == 2:
        return
    with m.frame(0x20) as sp:
        req = sp + 0x10
        m.put(req + 5, 4, 0); m.put(req + 9, 1, 1)
        m.put(req, 4, m.u32(rule)); m.put(req + 4, 1, kind)
        x = m.call(m.main + 0x283F0D4, m.call(m.main + 0x1361214, o, rule))
        return _tail(m, m.main + 0x283F0DC, x, sp + 8, req)


@lifted(0x28802C4)
def rule_case_20(m, o, rule, *_):
    """0x2880580 (6, 1, 3, 1) and (7, 2, 4, 2) on every matched member."""
    with m.frame(0x30) as sp:
        n = m.call(m.main + 0x18FFCD0, o, rule, sp + 8) & M32
        for i in range(n if n < 0x80000000 else 0):
            bb = m.call(m.main + 0x13813F4, o, m.u32(sp + 8 + 4 * i))
            m.call_void(m.main + 0x2880580, o, bb, 6, 1, 3, 1)
            m.call_void(m.main + 0x2880580, o, bb, 7, 2, 4, 2)


@lifted(0x2880358)
def rule_case_40(m, o, rule, *_):
    """For every matched member and k = 1..5: when 0x17d5ce0 finds an entry, record {[rule], entry, k, 1,
    +0x30 = 1} through 0x1380c5c."""
    _need(m, m.main + 0x17D5CE0)
    with m.frame(0x80) as sp:
        ids = sp + 0x58
        n = m.call(m.main + 0x18FFCD0, o, rule, ids) & M32
        for i in range(n if n < 0x80000000 else 0):
            ident = m.u32(ids + 4 * i)
            for k in range(1, 6):
                e = m.call(m.main + 0x17D5CE0, o, ident)
                if not e:
                    continue
                r = sp + 0x10
                m.write(r, bytes(0x48))
                m.put(r, 4, m.u32(rule)); m.put(r + 8, 8, e); m.put(r + 0x10, 1, k)
                m.put(r + 0x14, 4, 1); m.put(r + 0x30, 1, 1)
                x = m.call(m.main + 0x18675D8, m.call(m.main + 0x1361214, o))
                m.call_void(m.main + 0x1380C5C, x, sp + 8, r)


@lifted(0x1873FD4)
def battler_vf_388(m, o, ident, *_):
    """vf 0x388 of the battler `ident` (x1 then holds the method's own address)."""
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), ident)
    f = m.u64(m.u64(b) + 0x388)
    return _tail(m, f, b, f)


@lifted(0x1873F8C)
def rule_mark_queued(m, o, ident, *_):
    """0x1873fd4([o+0x20], ident) & 1 (x1 passes through), then command 0xf with `ident` on the queue
    [o+0x18]."""
    r = m.call(m.main + 0x1873FD4, m.u64(o + 0x20), ident)
    m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0xF, ident & M32)
    return r & 1


@lifted(0x1873F14)
def rule_mark(m, o, out, ident, *_):
    """out[0] = 0; for the battler u32 [ident] when it is not out (vf 0x200): 0x1873f8c with its id."""
    m.put(out, 1, 0)
    b = m.call(m.main + 0x13813F4, o, m.u32(ident))
    if m.vcall(b, 0x200) & 1:
        return
    q = m.call(m.main + 0x1143584, o)
    m.put(out, 1, m.call(m.main + 0x1873F8C, q, m.vcall(b, 0x98) & M32) & 1)


@lifted(0x18FFC04)
def rule_kind_1(m, o, rule, *_):
    """0x1873f14 on [0x1361214(o)+0xe40] for each member 0x18ffcd0 matches."""
    with m.frame(0x50) as sp:
        ids, cell = sp + 8, sp + 0x48
        n = m_s32(m.call(m.main + 0x18FFCD0, o, rule, ids))
        for i in range(max(n, 0)):
            m.put(cell, 4, m.u32(ids + 4 * i))
            x = m.call(m.main + 0x283E624, m.call(m.main + 0x1361214, o))
            m.call_void(m.main + 0x1873F14, x, sp, cell)


@lifted(0x17CDE54)
def rule_kind_2(m, o, rule, *_):
    """0x17cdf14 on [0x1361214(o)+0xae0] with the request {u32 [rule], 0x32, the 0x18ffcd0 members,
    their count at +0x30, +0x35 = 1}."""
    with m.frame(0xA0) as sp:
        req = sp + 0x40
        m.write(req, bytes(0x31))
        m.put(req + 0x32, 4, 0)
        m.put(req + 4, 4, 0x31)
        m.call_void(m.main + 0x1146154, req + 0x38)
        m.put(req, 4, m.u32(rule))
        n = m.call(m.main + 0x18FFCD0, o, rule, sp + 0x18) & M32
        if 1 <= n < 0x80000000:
            m.write(req + 8, m.read(sp + 0x18, 4 * n))
        m.put(req + 4, 4, 0x32)
        m.put(req + 0x30, 1, n)
        m.put(req + 0x35, 1, 1)
        x = m.call(m.main + 0x17CDF0C, m.call(m.main + 0x1361214, o))
        return _tail(m, m.main + 0x17CDF14, x, sp + 8, req)


# u16 rule+0x30 -> handler (jump table 0x3c6a4c0 for 1..8): 1 and 2 are tail calls to other functions.
_RULE_CASES = {1: 0x18FFC04, 2: 0x17CDE54, 4: 0x2880128, 8: 0x2880194, 0x10: 0x2880274, 0x20: 0x28802C4,
               0x40: 0x2880358}


@lifted(0x28800C0)
def run_rule(m, o, rule, *_):
    """Run a rule record by its kind (u16 +0x30)."""
    target = _RULE_CASES.get(m.u16(rule + 0x30))
    if target is None:
        return
    return _tail(m, m.main + target, o, rule)


def _rule_check(m, o, p, a, b, c, flag):
    """0x13808bc on the record {a, b, c, u32 [p], flag}: (its result, the done byte)."""
    with m.frame(0x30) as sp:
        r = sp + 0x10
        m.put(r, 8, a); m.put(r + 8, 8, b); m.put(r + 0x10, 8, c)
        m.put(r + 0x18, 4, m.u32(p)); m.put(r + 0x1C, 1, flag)
        x = m.call(m.main + 0x13808B4, m.call(m.main + 0x1361214, o, p))
        res = _tail(m, m.main + 0x13808BC, x, sp + 8, r)
        return res, m.u8(sp + 8)


@lifted(0x157A974)
def rule_check_flagged(m, o, p, a, b, c, *_):
    """Whether 0x13808bc ran a rule for {a, b, c, u32 [p], 1}."""
    return _rule_check(m, o, p, a, b, c, 1)[1]


@lifted(0x1380874)
def rule_check(m, o, p, a, b, c, *_):
    return _rule_check(m, o, p, a, b, c, 0)[0]


@lifted(0x13807EC)
def rule_check_if_hit(m, o, _x1, r, *_):
    """Unless battler [r+0x18] is out (vf 0x200): when event 0x6c ([r+8], [r+0x10], [r+0x18]) rolls a yes,
    0x1380874 on r's four fields."""
    v = m.vcall(m.u64(r + 0x18), 0x200)
    if v & 1:
        return v
    v = m.call(m.main + 0x1383AD8, m.call(m.main + 0x1146E90, o), m.u64(r + 8), m.u64(r + 0x10), m.u64(r + 0x18))
    if not v & 1:
        return v
    return _tail(m, m.main + 0x1380874, o, m.u64(r), m.u64(r + 8), m.u64(r + 0x10), m.u64(r + 0x18))


@lifted(0x1580554)
def apply_move_rules(m, o, out, r, *_):
    """r = (move ptr, user, target, ..., u32 +0x18): for each of the 0x1380e28(move) rules, 0x13831ec gives
    a kind and value; kind 0 marks the aux record (0x138155c), others run 0x138112c on a record {user id,
    target id, kind (1..5 for kind 9), value, +0x14 [r+0x18], +0x19 the 0x1382688 bit, +0x20 aux}; any yes
    sets out[0]. out+4 = 0x15808e4(aux)."""
    m.put(out, 1, 0); m.put(out + 4, 4, 0)
    b, t = m.u64(r + 8), m.u64(r + 0x10)
    ident = m.vcall(b, 0x98) & M32
    key = m.u16(m.u64(r))
    with m.frame(0x60) as sp:
        aux = sp
        m.call_void(m.main + 0x1380C4C, aux)
        m.call_void(m.main + 0x15808D0, aux)
        bit = m.call(m.main + 0x1382688, m.call(m.main + 0x1146E90, o), b, t, key) & 1
        n = m.call(m.main + 0x1380E28, key) & 0xFF
        res, q, kv = sp + 0x28, sp + 0x30, sp + 0x58
        for i in range(n):
            m.call_void(m.main + 0x13831EC, m.call(m.main + 0x1146E90, o), key, i, b, t, kv, kv + 4)
            kind = m.u8(kv)
            if not kind:
                m.call_void(m.main + 0x138155C, aux, 1)
                continue
            value, extra = m.u32(kv + 4), m.u32(r + 0x18)
            hit = 0
            for k in (range(1, 6) if kind == 9 else (kind,)):
                m.write(q, bytes(0x28))
                m.put(q, 4, ident)
                m.put(q + 4, 4, m.vcall(t, 0x98) & M32)
                m.put(q + 8, 1, k); m.put(q + 0xC, 4, value); m.put(q + 0x10, 1, 0)
                m.put(q + 0x14, 4, extra); m.put(q + 0x19, 1, bit); m.put(q + 0x20, 8, aux)
                m.call_void(m.main + 0x138112C, m.u64(m.u64(o + 0x78) + 0x15A0), res, q)
                hit |= m.u8(res)
            if hit:
                m.put(out, 1, 1)
        m.put(out + 4, 4, m.call(m.main + 0x15808E4, aux))
        m.call_void(m.main + 0x15808C8, aux)
        m.call_void(m.main + 0x1380C48, aux)


@lifted(0x1154E9C)
def run_rule_kinds(m, o, _x1, rule, *_):
    """0x28800c0 on a copy of the rule record (0x8c bytes, +0x60.. through 0x28800b8) once per kind bit
    0..6 set in its u16 +0x30, the copy's +0x30 holding that one bit; then 0x1155138."""
    with m.frame(0x90) as sp:
        for k in range(7):
            if not m.u16(rule + 0x30) >> k & 1:
                continue
            m.write(sp, m.read(rule, 0x54))
            m.put(sp + 0x54, 8, m.u64(rule + 0x54)); m.put(sp + 0x5C, 1, m.u8(rule + 0x5C))
            m.call_void(m.main + 0x28800B8, sp + 0x60, rule + 0x60)
            m.put(sp + 0x84, 8, m.u64(rule + 0x84))
            m.put(sp + 0x30, 2, 1 << k)
            m.call_void(m.main + 0x28800C0, o, sp)
    return _tail(m, m.main + 0x1155138, o, rule)


@lifted(0x288B434)
def move_rule_outcome(m, o, mv, b, *_):
    """Event 0xca (b, u16 [mv]): yes runs 0x157a950, no queues 0x157a95c with b's id."""
    if m.call(m.main + 0x2836708, m.call(m.main + 0x1146E90, o), b, m.u16(mv)) & 1:
        return _tail(m, m.main + 0x157A950, m.call(m.main + 0x139B698, o) + 0x10)
    q = m.call(m.main + 0x1143584, o)
    return _tail(m, m.main + 0x157A95C, q, m.vcall(b, 0x98) & M32)


@lifted(0x288B4B4)
def weather_request_for(m, o, kind, turns, src, *_):
    """The weather request {kind, turns + the setup value 0x46e2708 (vf 0x68 of 0x114acbc(o)), turns,
    src} through 0x1149ed0 on [0x1361214(o)+0x1c0]: its answer (0 when set)."""
    add = m.vcall(m.call(m.main + 0x114ACBC, o, kind), 0x68, m.u64(m.main + 0x46E2708))
    with m.frame(0x20) as sp:
        r = sp + 0x10
        m.put(r + 8, 2, 0)
        m.put(r, 1, kind); m.put(r + 1, 1, add + turns); m.put(r + 2, 1, turns)
        m.put(r + 4, 4, src)
        x = m.call(m.main + 0x113E064, m.call(m.main + 0x1361214, o))
        m.call_void(m.main + 0x1149ED0, x, sp + 8, r)
        return m.u8(sp + 8)


# Messages 0x307, 0x308, 0x30a for weathers 5..7, 0x237 otherwise: the game shifts this constant by 16 per
# step and passes the low 32 bits on.
_WEATHER_LOCK_MESSAGES = 0x30A03080307


@lifted(0x288B538)
def weather_locked_message(m, o, b, *_):
    """Record 0x1146154 headed by the message for the current weather (0x114a08c), sent for b through
    0x114b0ac."""
    with m.frame(0x30) as sp:
        m.call_void(m.main + 0x1146154, sp)
        w = m.call(m.main + 0x114A08C, m.call(m.main + 0x148253C, m.call(m.main + 0x1482534, o)))
        i = (w - 5) & 0xFF
        msg = (_WEATHER_LOCK_MESSAGES >> (16 * i)) & M32 if i < 3 else 0x237
        m.call_void(m.main + 0x2843244, sp, 1, msg)
        q = m.call(m.main + 0x1143584, o)
        return _tail(m, m.main + 0x114B0AC, q, m.vcall(b, 0x98) & M32, sp)


@lifted(0x288B370)
def move_weather_rule(m, o, b, kind, *_):
    """Set weather `kind` from b's move: turns from event 0xa0; on success 0x157a950, when the weather
    is locked (2) the message 0x288b538, else 0x157a95c with b's id."""
    turns = m.call(m.main + 0x2835CF0, m.call(m.main + 0x1146E90, o), kind, b) & M32
    r = m.call(m.main + 0x288B4B4, o, kind, turns, m.vcall(b, 0x98) & M32) & 0xFF
    if r == 2:
        return _tail(m, m.main + 0x288B538, o, b)
    if r == 0:
        return _tail(m, m.main + 0x157A950, m.call(m.main + 0x139B698, o) + 0x10)
    q = m.call(m.main + 0x1143584, o)
    return _tail(m, m.main + 0x157A95C, q, m.vcall(b, 0x98) & M32)


@lifted(0x288B1F8)
def move_rule(m, o, _x1, r, *_):
    """By 0x28056f0(move): a nonzero kind goes to 0x288b370, else 0x288b434."""
    k = m.call(m.main + 0x28056F0, m.u16(m.u64(r))) & 0xFF
    if k:
        return _tail(m, m.main + 0x288B370, o, m.u64(r + 8), k)
    return _tail(m, m.main + 0x288B434, o, m.u64(r), m.u64(r + 8))


@lifted(0x1580064)
def apply_move_rules_of(m, o, out_hit, out_n, a, b, mv, extra, *_):
    """0x1580554 on the record {mv, a, b, u32 extra, 1}; out_hit (byte) and out_n (u32) get its answers."""
    with m.frame(0x30) as sp:
        r = sp + 0x10
        m.write(r, bytes(0x20))
        m.put(r, 8, mv); m.put(r + 8, 8, a); m.put(r + 0x10, 8, b)
        m.put(r + 0x18, 4, extra); m.put(r + 0x1C, 1, 1)
        x = m.call(m.main + 0x15800C4, m.call(m.main + 0x1361214, o, out_hit))
        m.call_void(m.main + 0x1580554, x, sp + 8, r)
        m.put(out_hit, 1, m.u8(sp + 8))
        m.put(out_n, 4, m.u32(sp + 0xC))


@lifted(0x1142520)
def run_rule_kinds_of(m, o, rule, *_):
    """0x1154e9c on [o+0x78]'s object with a copy of the rule record (+0x60.. through 0x1820f40)."""
    with m.frame(0xA0) as sp:
        m.write(sp + 0x60, bytes(0x24))
        m.write(sp, m.read(rule, 0x54))
        m.put(sp + 0x54, 8, m.u64(rule + 0x54)); m.put(sp + 0x5C, 1, m.u8(rule + 0x5C))
        m.call_void(m.main + 0x1820F40, sp + 0x60, rule + 0x60)
        m.put(sp + 0x84, 8, m.u64(rule + 0x84))
        x = m.call(m.main + 0x11425A8, m.u64(o + 0x78))
        m.call_void(m.main + 0x1154E9C, x, sp + 0x98, sp)


@lifted(0x1533EBC)
def rule_check_if_hit_of(m, o, a, b, c, *_):
    """0x13807ec with the record {c, b, a, a}."""
    with m.frame(0x30) as sp:
        r = sp + 0x10
        m.put(r, 8, c); m.put(r + 8, 8, b); m.put(r + 0x10, 8, a); m.put(r + 0x18, 8, a)
        x = m.call(m.main + 0x13807E4, m.call(m.main + 0x1361214, o, a))
        return _tail(m, m.main + 0x13807EC, x, sp + 8, r)


@lifted(0x13807B0)
def rule_check_if_hit_rec(m, o, a, b, c, d, *_):
    """0x13807ec with the record {a, b, c, d}."""
    with m.frame(0x30) as sp:
        r = sp + 0x10
        m.put(r, 8, a); m.put(r + 8, 8, b); m.put(r + 0x10, 8, c); m.put(r + 0x18, 8, d)
        x = m.call(m.main + 0x13807E4, m.call(m.main + 0x1361214, o, a))
        return _tail(m, m.main + 0x13807EC, x, sp + 8, r)


@lifted(0x287ED8C)
def rule_check_3(m, o, a, b, c, w, *_):
    """0x13808bc on the record {c, a, b, u32 w, 1}."""
    with m.frame(0x30) as sp:
        r = sp + 0x10
        m.put(r, 8, c); m.put(r + 8, 8, a); m.put(r + 0x10, 8, b)
        m.put(r + 0x18, 4, w); m.put(r + 0x1C, 1, 1)
        x = m.call(m.main + 0x13808B4, m.call(m.main + 0x1361214, o, a))
        return _tail(m, m.main + 0x13808BC, x, sp + 8, r)


@lifted(0x157A874)
def rule_check_each_target(m, o, _x1, r, *_):
    """0x157a974 (r's first three fields, target) for each target of [r+0x18]; a yes runs 0x157a950. With
    none and +0xc0 of 0x139b698 clear: 0x157a95c for [r+0x10]."""
    lst = m.u64(r + 0x18)
    m.call_void(m.main + 0x1143D7C, lst)
    hit = False
    t = m.call(m.main + 0x158003C, m.u64(r + 0x18))
    while t:
        if m.call(m.main + 0x157A974, o, m.u64(r), m.u64(r + 8), m.u64(r + 0x10), t) & 1:
            m.call_void(m.main + 0x157A950, m.call(m.main + 0x139B698, o) + 0x10)
            hit = True
        t = m.call(m.main + 0x158003C, m.u64(r + 0x18))
    if hit or m.u8(m.call(m.main + 0x139B698, o) + 0xC0):
        return
    q = m.call(m.main + 0x1143584, o)
    return _tail(m, m.main + 0x157A95C, q, m.vcall(m.u64(r + 0x10), 0x98) & M32)


@lifted(0x15799A8)
def rule_check_each_target_of(m, o, a, b, c, d, *_):
    """0x157a874 on [o+0x78]'s object with {a, c, b, d}."""
    with m.frame(0x30) as sp:
        r = sp + 0x10
        m.put(r, 8, a); m.put(r + 8, 8, c); m.put(r + 0x10, 8, b); m.put(r + 0x18, 8, d)
        x = m.call(m.main + 0x15799DC, m.u64(o + 0x78))
        return _tail(m, m.main + 0x157A874, x, sp + 8, r)


@lifted(0x1536FB0)
def on_rule_side(m, o, b, *_):
    """Whether the setup's rule value for b's id (0..4, 0 when absent) equals byte +0x95 of [o+8]."""
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50),
               m.vcall(b, 0x98) & M32)
    v = m.s(p, 4) if p else 0
    v = v if v < 5 else 0
    return int(v & M32 == m.u8(m.u64(o + 8) + 0x95))


def _rule_side(m, o, b):
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50),
               m.vcall(b, 0x98) & M32)
    v = m.s(p, 4) if p else 0
    return v if v < 5 else 0
