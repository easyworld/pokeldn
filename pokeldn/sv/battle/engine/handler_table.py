"""The handler table: handler records in a free list and per-owner chains, adding and releasing them,
and the item, ability and entry handler factories."""

from pokeldn.sv.battle.engine.battler import _main_battler
from pokeldn.sv.battle.engine.calls import M32, M64, _need, _s32, _tail
from pokeldn.sv.battle.machine import UnliftedCall, lifted


@lifted(0x283C488)
def release_finished(m, o, *_):
    """Walk the active list of the pool at [[o+8]+0xd0]: an element in state 7 (+0x28) with +0x44 set is
    released (0x13608e0), or handed to 0x1360cdc when +0x3f is set."""
    from pokeldn.sv.battle.engine.containers import find
    pool = m.u64(m.u64(o + 8) + 0xD0)
    key = m.u16(pool + 0x70)
    if key == 0xEE:
        return
    node = find(m, pool + 8, key, 2)
    if not node:
        return
    e = node + 0x18
    while True:
        nxt = m.call(m.main + 0xF7BA54, m.u64(e + 8), m.u16(e + 0x14))
        if m.u8(e + 0x28) == 7 and m.u8(e + 0x44):
            if m.u8(e + 0x3F) == 0:
                m.call_void(m.main + 0x13608E0, m.u64(m.u64(o + 8) + 0xD0), e)
            else:
                m.call_void(m.main + 0x1360CDC, e, 1)
        if nxt == 0:
            return
        e = nxt


@lifted(0x119E440)
def previous_element(m, e, *_):
    """The element before e in its keyed list (key +0x12 in the map at [e+8]+8), or 0."""
    from pokeldn.sv.battle.engine.containers import find
    key = m.u16(e + 0x12)
    if key == 0xEE:
        return 0
    node = find(m, m.u64(e + 8) + 8, key, 2)
    return node + 0x18 if node else 0


@lifted(0x127C86C)
def free_element(m, owner, e, *_):
    """Unlink e, clear its 0x58-byte payload and push it on the front of the free list (head key
    owner+0x72)."""
    from pokeldn.sv.battle.engine.containers import _key_node, unlink
    unlink(m, e)
    m.put(e + 0x12, 4, 0xEE00EE)
    m.write(e + 0x18, bytes(0x58))
    free = _key_node(m, owner + 8, m.u16(owner + 0x72))
    if free:
        m.put(e + 0x14, 2, m.u16(free + 0x28))
        m.put(free + 0x2A, 2, m.u16(e + 0x10))
    else:
        m.put(e + 0x14, 2, 0xEE)
    m.put(owner + 0x72, 2, m.u16(e + 0x10))


@lifted(0x1155BDC)
def follow_link(m, o, e, loose, *_):
    """Follow e's chain of links: each entry's u16 key (+0x14, 0xee ends it) names the next entry in the
    map at [entry+8]+8; the first whose byte +0x28 (and, unless `loose`, u32 +0x34) match e's and whose
    byte +0x41 is clear; 0 when the chain ends."""
    from pokeldn.sv.battle.engine.containers import find
    if e == 0:
        return 0
    side, tag = m.u8(e + 0x28), m.u32(e + 0x34)
    x = e
    while True:
        key = m.u16(x + 0x14)
        if key == 0xEE:
            return 0
        node = find(m, m.u64(x + 8) + 8, key, 2)
        if node == 0:
            return 0
        x = node + 0x18
        if m.u8(x + 0x28) == side and (loose & 1 or m.u32(x + 0x34) == tag) and m.u8(x + 0x41) == 0:
            return x


@lifted(0x1360830)
def release_kind_4(m, o, b, *_):
    """Release (0x13608b0) every kind-4 handler of b's id (0x119b478 on [[o+8]+0xd0]) until one whose
    u32 +0x68 is set; that one, or 0."""
    h = m.u64(m.u64(o + 8) + 0xD0)
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    e = m.call(m.main + 0x119B478, h, 4, ident)
    while e and m.u32(e + 0x68) == 0:
        m.call_void(m.main + 0x13608B0, o, e)
        e = m.call(m.main + 0x119B478, h, 4, ident)
    return e


@lifted(0x13606F8)
def release_kind_4_of(m, o, ident, *_):
    """The tail call of 0x1360830([o+0x18], the main battler for ident)."""
    from pokeldn.sv.battle.engine.containers import battler
    b = battler(m, m.u64(m.u64(o + 0x10) + 0x30), ident)
    return _tail(m, m.main + 0x1360830, m.u64(o + 0x18), b)


@lifted(0x114BFDC)
def run_effect_entry(m, o, kind, arg, *_):
    """0x114bff0 on [o+0x18], inlined: the function 0x114c070 gives for `kind` called with a local u32 and
    arg; a nonzero result is pushed by 0x114ed80 (3, kind, 4, 0, arg & 0xff, result, the local) and
    gives 1, else 0."""
    q = m.u64(o + 0x18)
    f = m.call(m.main + 0x114C070, kind & 0xFFFFFFFF)
    with m.frame(0x10) as local:
        if f == 0:
            m.put(local, 4, 0)
            return 0
        r = m.call(f, local, arg & 0xFFFFFFFF)
        if r == 0:
            return 0
        m.call_void(m.main + 0x114ED80, q, 3, kind & 0xFFFFFFFF, 4, 0, arg & 0xFF, r, m.u32(local))
        return 1


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


@lifted(0x284DB90)
def handler_with_key(m, o, ident, key, *_):
    """The first kind-2 handler of `ident` whose u16 (0xf7bb74) is `key`, or 0."""
    owner = m.call(m.main + 0x114C158, o)
    h = m.call(m.main + 0x119B478, owner, 2, ident & 0xFF)
    while h and m.call(m.main + 0xF7BB74, h) & 0xFFFF != key & 0xFFFFFFFF:
        h = m.call(m.main + 0x1155BDC, owner, h, 0)
    return h


@lifted(0x13DC030)
def release_matching(m, o, pokemon, key, *_):
    """Walk the kind-0 handlers of the Pokemon's id (0x119b478 over [[o+8]+0xd0]) and, for each one
    whose u16 +0x30 is `key`, +0x68 clear and +0x44 set, release it (+0x3f clear) or retire it."""
    table = m.u64(m.u64(o + 8) + 0xD0)
    cur = m.call(m.main + 0x119B478, table, 0, m.vcall(pokemon, 0x98) & 0xFFFFFFFF)
    while cur:
        kind, ident = m.u8(cur + 0x28), m.u32(cur + 0x34)
        nxt = cur
        while True:
            nxt = m.call(m.main + 0xF7BA54, m.u64(nxt + 8), m.u16(nxt + 0x14))
            if nxt == 0 or (m.u8(nxt + 0x28) == kind and m.u32(nxt + 0x34) == ident
                            and m.u8(nxt + 0x41) == 0):
                break
        if m.u16(cur + 0x30) == key & 0xFFFF and m.u32(cur + 0x68) == 0 and m.u8(cur + 0x44):
            if m.u8(cur + 0x3F) == 0:
                m.call_void(m.main + 0x13608E0, m.u64(m.u64(o + 8) + 0xD0), cur)
            else:
                m.call_void(m.main + 0x1360CDC, cur, 1)
        cur = nxt


@lifted(0x13607C0)
def release_battler(m, o, ident, *_):
    b = _main_battler(m, o, ident)
    return _tail(m, m.main + 0x1360B30, m.u64(o + 0x18), b)


@lifted(0x1360CE8)
def release_condition_1a_of(m, o, pk, *_):
    """For each standing member under condition 0x1a whose condition value (vf 0x4f0) is the
    Pokemon's id, hand it to 0x287f998."""
    with m.frame(0x30) as p:
        it, out, holder = p, p + 0x20, p + 0x28
        m.put(holder, 8, o); m.put(out, 8, 0)
        a = m.call(m.main + 0x114E480, o)
        m.call_void(m.main + 0x1147754, it, a, m.call(m.main + 0x1482534, o))
        while m.call(m.main + 0x1360DBC, it, out) & 1:
            b = m.u64(out)
            if m.vcall(b, 0x4D0, 0x1A) & 1:
                v = m.u32(m.vcall(b, 0x4F0, 0x1A))
                if m.vcall(pk, 0x98) & 0xFFFFFFFF == v:
                    m.call_void(m.main + 0x287F998, holder, m.u64(out))


@lifted(0x13608B0)
def release_if_live(m, o, e, *_):
    """Release a live element (+0x44) to the free list of [[o+8]+0xd0] (0x13608e0); one still held
    (+0x3f) is marked for release instead (0x1360cdc(e, 1))."""
    if e == 0 or m.u8(e + 0x44) == 0:
        return
    if m.u8(e + 0x3F):
        return _tail(m, m.main + 0x1360CDC, e, 1)
    return _tail(m, m.main + 0x13608E0, m.u64(m.u64(o + 8) + 0xD0), e)


@lifted(0x114ED80)
def new_entry(m, o, kind, key, level, low, value, ptr, flag, *_):
    """Take the head of the free list of [[o+8]+0xd0] (0x119baac(-1)), fill it (kind +0x28, ptr +0x20,
    key +0x30, value +0x34, value again +0x38 for kinds 0, 4 and 5, (~level << 24) + 0x9000000 | low at
    +0x2c, flag +0x3e, u16 [o+0x80] at +0x3c, live +0x44) and add it with 0x119b6cc."""
    _need(m, m.main + 0x119B6CC)
    serial = m.u32(o + 0x80)
    table = m.u64(m.u64(o + 8) + 0xD0)
    e = m.call(m.main + 0x119BAAC, table, 0xFFFFFFFF)
    if e == 0:
        return 0
    k = kind & 0xFF
    v2 = value if (1 << (k & 0x1F)) & 0x31 else 0
    if k > 5:
        v2 = 0
    m.put(e + 0x12, 4, 0xEE00EE)
    m.write(e + 0x18, bytes(0x58))
    m.put(e + 0x2C, 4, ((~level & 0xFFFFFFFF) << 24) + 0x9000000 | low & 0xFFFFFFFF)
    m.put(e + 0x28, 1, kind)
    m.put(e + 0x20, 8, ptr)
    m.put(e + 0x3E, 1, flag)
    m.put(e + 0x30, 2, key)
    m.put(e + 0x34, 4, value)
    m.put(e + 0x38, 4, v2)
    m.put(e + 0x3C, 2, serial)
    m.put(e + 0x44, 1, 1)
    m.call_void(m.main + 0x119B6CC, table, e)
    return e


@lifted(0x114D844)
def first_live_of_kind(m, owner, kind, *_):
    """The first element of the active list (head key owner+0x70) that is live (+0x44), of kind `kind`
    (+0x28) and not retired (+0x41); else 0."""
    from pokeldn.sv.battle.engine.containers import _element
    e = _element(m, owner + 8, m.u16(owner + 0x70))
    while e:
        if m.u8(e + 0x44) and m.u8(e + 0x28) == kind & 0xFF and m.u8(e + 0x41) == 0:
            return e
        e = _element(m, m.u64(e + 8) + 8, m.u16(e + 0x14))
    return 0


@lifted(0x127E8B4)
def release_all_127e8b4(m, owner, *_):
    """Hand every element of the active list (head key owner+0x70) to 0x127c86c in order (the next one
    looked up before), then mark the list empty (0xee)."""
    from pokeldn.sv.battle.engine.containers import _element
    e = _element(m, owner + 8, m.u16(owner + 0x70))
    if e:
        _need(m, m.main + 0x127C86C)
    while e:
        nxt = _element(m, m.u64(e + 8) + 8, m.u16(e + 0x14))
        m.call_void(m.main + 0x127C86C, owner, e)
        e = nxt
    m.put(owner + 0x70, 2, 0xEE)


@lifted(0x2888018)
def add_handler_and_push_65(m, o, a, b, rec, *_):
    m.call_void(m.main + 0x288D114, m.u64(o + 0x20), a, b, rec)    # x1..x3 passed through
    return _tail(m, m.main + 0x288DD40, m.u64(o + 0x18), a, b, rec)


@lifted(0x1360C00)
def release_kind5(m, o, b, *_):
    """Walk b's kind-5 handlers (0x119b478 / 0xf7ba54 to the next with the same +0x28 and +0x34 and
    +0x41 clear); each with +0x68 clear and +0x44 set is marked (+0x41 = 1) when +0x3f is set, else
    released through 0x13608e0."""
    mm = lambda: m.u64(m.u64(o + 8) + 0xD0)
    cur = m.call(m.main + 0x119B478, mm(), 5, m.vcall(b, 0x98) & M32)
    while cur:
        k28, k34 = m.u8(cur + 0x28), m.u32(cur + 0x34)
        nxt = cur
        while True:
            nxt = m.call(m.main + 0xF7BA54, m.u64(nxt + 8), m.u16(nxt + 0x14))
            if not nxt or (m.u8(nxt + 0x28) == k28 and m.u32(nxt + 0x34) == k34 and not m.u8(nxt + 0x41)):
                break
        if not m.u32(cur + 0x68) and m.u8(cur + 0x44):
            if m.u8(cur + 0x3F):
                m.call_void(m.main + 0x1360CDC, cur, 1)
            else:
                m.call_void(m.main + 0x13608E0, mm(), cur)
        cur = nxt


@lifted(0x1360B30)
def release_kind6(m, o, b, *_):
    """Release (0x13608b0) b's kind-6 handlers whose 0xf7bb74 value is the u32 at b's vf 0x468."""
    ident = m.vcall(b, 0x98) & M32
    want = m.u32(m.vcall(b, 0x468))
    mm = m.u64(m.u64(o + 8) + 0xD0)
    h = m.call(m.main + 0x119B478, mm, 6, ident)
    while h:
        if want == m.call(m.main + 0xF7BB74, h) & 0xFFFF:
            m.call_void(m.main + 0x13608B0, o, h)
            h = m.call(m.main + 0x119B478, mm, 6, ident)
        else:
            h = m.call(m.main + 0x1155BDC, mm, h, 0)


@lifted(0x284DD00)
def release_side_handler(m, q, side, k, *_):
    """Release (0x13608b0) the side handler 0x284db90 finds; whether there was one."""
    h = m.call(m.main + 0x284DB90, q, side, k)
    if not h:
        return 0
    m.call_void(m.main + 0x13608B0, q, h)
    return 1


@lifted(0x288D11C)
def release_side_handler_of(m, x, side, k, *_):
    return _tail(m, m.main + 0x284DD00, m.u64(x + 0x18), side, k)


@lifted(0x114E8B0)
def add_entry_handler(m, q, b, *_):
    """For b's handler kind u32 [vf 0x468] 1..3: the factory at [main+0x44f1168 + 0x10 * (kind - 1) + 8]
    (it fills a local u32) and, when it gives one, 0x114ed80(q, 6, kind, 0, vf 0xe0 & 0xffff, b's id,
    the handler, the local); 1 when pushed."""
    kind = m.u32(m.vcall(b, 0x468))
    with m.frame(0x10) as local:
        if _s32(kind) > 3:
            return 0
        if not 0 <= kind - 1 < 3:
            m.put(local, 4, 0)
            return 0
        f = m.u64(m.main + 0x44F1168 + 0x10 * (kind - 1) + 8)
        h = m.call(f, local)
        if not h:
            return 0
        w = m.vcall(b, 0xE0) & 0xFFFF
        ident = m.vcall(b, 0x98) & M32
        r = m.call(m.main + 0x114ED80, q, 6, kind, 0, w, ident, h, m.u32(local))
        return int(r != 0)


@lifted(0x114E5AC)
def add_entry_handler_of(m, o, ident, *_):
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), ident & M32)
    return _tail(m, m.main + 0x114E8B0, m.u64(o + 0x18), b)


@lifted(0x114E578)
def entry_handler_command(m, o, ident, *_):
    m.call_void(m.main + 0x114E5AC, m.u64(o + 0x20), ident & M32)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x6B, ident & M32)


@lifted(0x114F4D0)
def add_ability_handler(m, o, pc, b, *_):
    """Register b's handler for vf 0x2a8: the counted object [pc+0x190] maps it (vf 0x30) to a key looked up
    in the 211-entry table main+0x44f14d0 ({key, factory}, 16 bytes; entry 0xd2 counts as absent); the
    factory fills a local u32 and returns the handler, which takes a free element of [[o+8]+0xd0]
    (0x119baac) set up as kind 5 (+0x12 0x00ee00ee, +0x20 handler, +0x2c 0x0100 << 16 | vf 0xe0, +0x30
    the value, +0x34 / +0x38 b's id, +0x3c u16 [o+0x80], +0x3e the local, +0x44 1) and linked by priority
    (0x119b6cc)."""
    from pokeldn.sv.battle.engine.references import _release_ref
    v = m.vcall(b, 0x2A8) & M32
    x = m.u64(pc + 0x190)
    if x:
        if m.u32(x + 0x28) == M32:
            raise UnliftedCall("IncrementReference abort")
        m.put(x + 0x28, 4, m.u32(x + 0x28) + 1)
    key = m.vcall(x, 0x30, v)
    if x:
        _release_ref(m, x)
    idx = None
    for k in range(0xD3):
        if m.u64(m.main + 0x44F14D0 + 0x10 * k) == key:
            idx = k
            break
    with m.frame(0x10) as local:
        if idx is None or idx == 0xD2:
            m.put(local, 4, 0)
            return
        f = m.u64(m.main + 0x44F14D0 + 0x10 * idx + 8)
        h = m.call(f, local)
        if not h:
            return
        w = m.vcall(b, 0xE0) & M32
        ident = m.vcall(b, 0x98) & M32
        tag = m.u32(local)
        pri = m.u32(o + 0x80)
        pool = m.u64(m.u64(o + 8) + 0xD0)
        e = m.call(m.main + 0x119BAAC, pool, M64)
        if not e:
            return
        m.put(e + 0x12, 4, 0x00EE00EE)
        m.write(e + 0x18, bytes(0x58))
        m.put(e + 0x28, 1, 5)
        m.put(e + 0x2C, 4, 0x01000000 | w & 0xFFFF)
        m.put(e + 0x20, 8, h)
        m.put(e + 0x3E, 1, tag)
        m.put(e + 0x30, 2, v)
        m.put(e + 0x34, 4, ident); m.put(e + 0x38, 4, ident)
        m.put(e + 0x3C, 2, pri)
        m.put(e + 0x44, 1, 1)
        m.call_void(m.main + 0x119B6CC, pool, e)


@lifted(0x114E798)
def add_ability_handler_command(m, o, ident, *_):
    """0x114f4d0 for battler ident (on [[o+0x20]+0x18], [[o+0x20]+8]), then command 0x61 (ident)."""
    x = m.u64(o + 0x20)
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(x + 0x10) + 0x30), ident & M32)
    m.call_void(m.main + 0x114F4D0, m.u64(x + 0x18), m.u64(x + 8), b)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x61, ident & M32)


@lifted(0x13BE3A0)
def add_item_handler(m, o, b, item, *_):
    """Register b's handler for the u16 `item`: the factory of the matching entry of main+0x44f6a60 ({u16
    key, factory}, 16 bytes, 304 entries) fills a local u32 (low half kept) and returns the handler, which
    takes a free element of [[o+8]+0xd0] set up as kind 4 (+0x2c: 0x02 << 24 when the local's high half is
    0, else (9 - 1 - high) << 24, low half vf 0xe0) and linked by priority (0x119b6cc)."""
    key = item & 0xFFFF
    idx = None
    for k in range(0x130):
        if m.u16(m.main + 0x44F6A60 + 0x10 * k) == key:
            idx = k
            break
    with m.frame(0x10) as local:
        if idx is None:
            m.put(local, 4, 0)
            return
        h = m.call(m.u64(m.main + 0x44F6A60 + 0x10 * idx + 8), local)
        if not h:
            return
        ident = m.vcall(b, 0x98) & M32
        w = m.vcall(b, 0xE0) & M32
        tag = m.u32(local)
        m.put(local, 4, tag & 0xFFFF)
        pool = m.u64(m.u64(o + 8) + 0xD0)
        pri = m.u32(o + 0x80)
        e = m.call(m.main + 0x119BAAC, pool, M64)
        if not e:
            return
        hi = tag >> 16
        word = 0x2000000 if hi == 0 else (0x9000000 + ((~hi & M32) << 24)) & M32
        word = (word & 0xFFFF0000) | (w & 0xFFFF)
        m.put(e + 0x12, 4, 0x00EE00EE)
        m.write(e + 0x18, bytes(0x58))
        m.put(e + 0x28, 1, 4)
        m.put(e + 0x2C, 4, word)
        m.put(e + 0x20, 8, h)
        m.put(e + 0x3E, 1, tag)
        m.put(e + 0x30, 2, item)
        m.put(e + 0x34, 4, ident); m.put(e + 0x38, 4, ident)
        m.put(e + 0x3C, 2, pri)
        m.put(e + 0x44, 1, 1)
        m.call_void(m.main + 0x119B6CC, pool, e)


@lifted(0x114F1EC)
def add_item_handlers(m, o, pc, b, *_):
    """Item handlers for b: the held item (vf 0xf0), then each extra item 0x114f6fc lists (up to its count),
    each through 0x13be3a0 and command 0x5e (b's id, item)."""
    ident = m.vcall(b, 0x98) & M32
    item = m.vcall(b, 0xF0) & M32

    def one(it):
        x = m.u64(o + 0x20)
        bb = m.call(m.main + 0xF21C94, m.u64(m.u64(x + 0x10) + 0x30), ident)
        m.call_void(m.main + 0x13BE3A0, m.u64(x + 0x18), bb, it)
        m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0x5E, ident, it)

    one(item)
    with m.frame(0x20) as f:
        n = m.call(m.main + 0x114F6FC, pc, ident, f) & 0xFF
        for j in range(n):
            one(m.u16(f + 2 * j))


# Handler factories of the item (0x44f6a60), ability (0x44f14d0) and entry (0x44f1168) tables, all of one
# shape: *out = u32 tag, return the handler descriptor main+R. (address, tag, R)
_FACTORIES = (
    (0x2D0DB80, 1, 0x44F1198),
    (0x2D0E180, 5, 0x44F2200),
    (0x2D0E1A0, 5, 0x44F2250),
    (0x2D0E1C0, 5, 0x44F22A0),
    (0x2D0E1E0, 5, 0x44F22F0),
    (0x2D0E200, 5, 0x44F2340),
    (0x2D0E220, 5, 0x44F2390),
    (0x2D0E240, 5, 0x44F23E0),
    (0x2D0E260, 7, 0x44F2430),
    (0x2D0E280, 4, 0x44F24A0),
    (0x2D0E2A0, 3, 0x44F24E0),
    (0x2D0E2C0, 4, 0x44F2510),
    (0x2D0E2E0, 4, 0x44F2580),
    (0x2D0E300, 4, 0x44F25C0),
    (0x2D0E320, 4, 0x44F2600),
    (0x2D0E340, 4, 0x44F2640),
    (0x2D0E360, 4, 0x44F2680),
    (0x2D0E380, 4, 0x44F26C0),
    (0x2D0E3A0, 4, 0x44F2700),
    (0x2D0E3C0, 4, 0x44F2740),
    (0x2D0E3E0, 4, 0x44F2780),
    (0x2D0E400, 4, 0x44F27C0),
    (0x2D0E420, 4, 0x44F2800),
    (0x2D0E440, 4, 0x44F2840),
    (0x2D0E460, 3, 0x44F2880),
    (0x2D0E480, 3, 0x44F28B0),
    (0x2D0E4A0, 3, 0x44F28E0),
    (0x2D0E4C0, 3, 0x44F2910),
    (0x2D0E4E0, 3, 0x44F2940),
    (0x2D0E500, 3, 0x44F2970),
    (0x2D0E520, 3, 0x44F29A0),
    (0x2D0E540, 3, 0x44F29D0),
    (0x2D0E560, 3, 0x44F2A00),
    (0x2D0E580, 3, 0x44F2A30),
    (0x2D0E5A0, 3, 0x44F2A60),
    (0x2D0E5C0, 3, 0x44F2A90),
    (0x2D0E5E0, 3, 0x44F2AC0),
    (0x2D0E600, 3, 0x44F2AF0),
    (0x2D0E620, 3, 0x44F2B20),
    (0x2D0E640, 3, 0x44F2B50),
    (0x2D0E660, 3, 0x44F2B80),
    (0x2D0E680, 3, 0x44F2BB0),
    (0x2D0E6A0, 3, 0x44F2C10),
    (0x2D0E6C0, 5, 0x44F2C40),
    (0x2D0E6E0, 3, 0x44F2C90),
    (0x2D0E700, 3, 0x44F2CC0),
    (0x2D0E720, 6, 0x44F2D20),
    (0x2D0E740, 4, 0x44F2D80),
    (0x2D0E760, 3, 0x44F2DC0),
    (0x2D0E780, 1, 0x44F2DF0),
    (0x2D0E7A0, 1, 0x44F2E00),
    (0x2D0E7C0, 4, 0x44F2E10),
    (0x2D0E7E0, 1, 0x44F2E50),
    (0x2D0E800, 2, 0x44F2E60),
    (0x2D0E820, 1, 0x44F2EB0),
    (0x2D0E840, 1, 0x44F2EA0),
    (0x2D0E860, 1, 0x44F2EE0),
    (0x2D0E880, 1, 0x44F2EF0),
    (0x2D0E8A0, 1, 0x44F2F00),
    (0x2D0E8C0, 1, 0x44F2F10),
    (0x2D0E8E0, 1, 0x44F2F20),
    (0x2D0E900, 1, 0x44F2F30),
    (0x2D0E920, 1, 0x44F2F40),
    (0x2D0E940, 1, 0x44F2F50),
    (0x2D0E960, 2, 0x44F3380),
    (0x2D0E980, 1, 0x44F2EC0),
    (0x2D0E9A0, 1, 0x44F2ED0),
    (0x2D0E9C0, 1, 0x44F3550),
    (0x2D0E9E0, 1, 0x44F2F60),
    (0x2D0EA00, 4, 0x44F2F70),
    (0x2D0EA20, 1, 0x44F3140),
    (0x2D0EA40, 4, 0x44F2FB0),
    (0x2D0EA60, 4, 0x44F2FF0),
    (0x2D0EA80, 1, 0x44F33E0),
    (0x2D0EAA0, 1, 0x44F33F0),
    (0x2D0EAC0, 1, 0x44F3400),
    (0x2D0EAE0, 1, 0x44F3410),
    (0x2D0EB00, 1, 0x44F3420),
    (0x2D0EB20, 1, 0x44F3430),
    (0x2D0EB40, 1, 0x44F3440),
    (0x2D0EB60, 1, 0x44F3450),
    (0x2D0EB80, 1, 0x44F3460),
    (0x2D0EBA0, 1, 0x44F3470),
    (0x2D0EBC0, 2, 0x44F2E80),
    (0x2D0EBE0, 2, 0x44F3480),
    (0x2D0EC00, 1, 0x44F34A0),
    (0x2D0EC20, 1, 0x44F34B0),
    (0x2D0EC40, 1, 0x44F34C0),
    (0x2D0EC60, 1, 0x44F34D0),
    (0x2D0EC80, 1, 0x44F34E0),
    (0x2D0ECA0, 1, 0x44F34F0),
    (0x2D0ECC0, 1, 0x44F3500),
    (0x2D0ECE0, 1, 0x44F3510),
    (0x2D0ED00, 1, 0x44F3520),
    (0x2D0ED20, 1, 0x44F3530),
    (0x2D0ED40, 1, 0x44F3540),
    (0x2D0ED60, 2, 0x44F3030),
    (0x2D0ED80, 3, 0x44F3050),
    (0x2D0EDA0, 1, 0x44F3080),
    (0x2D0EDC0, 2, 0x44F3090),
    (0x2D0EDE0, 1, 0x44F30B0),
    (0x2D0EE00, 1, 0x44F30C0),
    (0x2D0EE20, 1, 0x44F30D0),
    (0x2D0EE40, 1, 0x44F30E0),
    (0x2D0EE60, 3, 0x44F30F0),
    (0x2D0EE80, 2, 0x44F3120),
    (0x2D0EEA0, 2, 0x44F33A0),
    (0x2D0EEC0, 2, 0x44F33C0),
    (0x2D0EEE0, 1, 0x44F3560),
    (0x2D0EF00, 1, 0x44F3570),
    (0x2D0EF20, 2, 0x44F3580),
    (0x2D0EF40, 1, 0x44F3150),
    (0x2D0EF60, 1, 0x44F3340),
    (0x2D0EF80, 1, 0x44F3350),
    (0x2D0EFA0, 1, 0x44F3360),
    (0x2D0EFC0, 1, 0x44F3370),
    (0x2D0EFE0, 2, 0x44F3160),
    (0x2D0F000, 1, 0x44F3180),
    (0x2D0F020, 1, 0x44F3190),
    (0x2D0F040, 1, 0x44F31A0),
    (0x2D0F060, 1, 0x44F31B0),
    (0x2D0F080, 1, 0x44F31C0),
    (0x2D0F0A0, 1, 0x44F31D0),
    (0x2D0F0C0, 1, 0x44F31E0),
    (0x2D0F0E0, 1, 0x44F31F0),
    (0x2D0F100, 1, 0x44F3200),
    (0x2D0F120, 1, 0x44F3210),
    (0x2D0F140, 1, 0x44F3220),
    (0x2D0F160, 1, 0x44F3230),
    (0x2D0F180, 1, 0x44F3240),
    (0x2D0F1A0, 1, 0x44F3250),
    (0x2D0F1C0, 1, 0x44F3260),
    (0x2D0F1E0, 1, 0x44F3270),
    (0x2D0F200, 1, 0x44F3280),
    (0x2D0F220, 1, 0x44F3290),
    (0x2D0F240, 1, 0x44F32A0),
    (0x2D0F260, 1, 0x44F32B0),
    (0x2D0F280, 1, 0x44F32C0),
    (0x2D0F2A0, 1, 0x44F32D0),
    (0x2D0F2C0, 1, 0x44F32E0),
    (0x2D0F2E0, 1, 0x44F32F0),
    (0x2D0F300, 2, 0x44F3300),
    (0x2D0F320, 1, 0x44F3320),
    (0x2D0F340, 1, 0x44F3330),
    (0x2D0F360, 1, 0x44F35A0),
    (0x2D0F380, 1, 0x44F35B0),
    (0x2D0F3A0, 1, 0x44F35C0),
    (0x2D0F3C0, 3, 0x44F35D0),
    (0x2D0F3E0, 1, 0x44F3600),
    (0x2D0F400, 1, 0x44F3610),
    (0x2D0F420, 1, 0x44F3620),
    (0x2D0F440, 2, 0x44F3630),
    (0x2D0F460, 2, 0x44F36C0),
    (0x2D0F480, 3, 0x44F36E0),
    (0x2D0F4A0, 2, 0x44F3710),
    (0x2D0F4C0, 5, 0x44F3730),
    (0x2D0F4E0, 3, 0x44F37B0),
    (0x2D0F500, 3, 0x44F37E0),
    (0x2D0F520, 3, 0x44F3810),
    (0x2D0F540, 3, 0x44F3840),
    (0x2D0F560, 3, 0x44F3870),
    (0x2D0F580, 3, 0x44F38A0),
    (0x2D0F5A0, 3, 0x44F38D0),
    (0x2D0F5C0, 3, 0x44F3900),
    (0x2D0F5E0, 3, 0x44F3930),
    (0x2D0F600, 3, 0x44F3960),
    (0x2D0F620, 3, 0x44F3990),
    (0x2D0F640, 3, 0x44F39C0),
    (0x2D0F660, 3, 0x44F39F0),
    (0x2D0F680, 3, 0x44F3A20),
    (0x2D0F6A0, 3, 0x44F3A50),
    (0x2D0F6C0, 3, 0x44F3A80),
    (0x2D0F6E0, 3, 0x44F3AB0),
    (0x2D0F700, 1, 0x44F2CF0),
    (0x2D0F720, 2, 0x44F2D00),
    (0x2D0F740, 2, 0x44F3680),
    (0x2D0F760, 3, 0x44F2BE0),
    (0x2D0F780, 3, 0x44F2550),
    (0x2D0F7A0, 3, 0x44F3650),
    (0x2D0F7C0, 2, 0x44F3780),
    (0x2D0F7E0, 1, 0x44F37A0),
    (0x2D0F800, 2, 0x44F36A0),
    (0x2D0F820, 3, 0x44F3AE0),
    (0x2D0F840, 1, 0x44F3B10),
    (0x2D0F860, 1, 0x44F3B20),
    (0x2D0F880, 1, 0x44F3B30),
    (0x2D0F8A0, 4, 0x44F3B40),
    (0x2D0F8C0, 4, 0x44F3B80),
    (0x2D0F8E0, 4, 0x44F3BC0),
    (0x2D0F900, 4, 0x44F3C00),
    (0x2D0F920, 4, 0x44F3C40),
    (0x2D0F940, 4, 0x44F3C80),
    (0x2D0F960, 7, 0x44F3CC0),
    (0x2D0F980, 3, 0x44F3D30),
    (0x2D0F9A0, 3, 0x44F3D60),
    (0x2D0F9C0, 3, 0x44F3D90),
    (0x2D0F9E0, 2, 0x44F3DC0),
    (0x2D0FA00, 5, 0x44F3DE0),
    (0x2D0FA20, 1, 0x44F3E30),
    (0x2D0FA40, 5, 0x44F3E40),
    (0x2D0FA60, 1, 0x44F3E90),
    (0x2D0FA80, 1, 0x44F3EA0),
    (0x2D0FAA0, 1, 0x44F3EB0),
    (0x2D0FAC0, 1, 0x44F3EC0),
    (0x2D113F0, 2, 0x44F4250),
    (0x2D11410, 2, 0x44F4270),
    (0x2D11430, 3, 0x44F4290),
    (0x2D114A0, 1, 0x44F42C0),
    (0x2D114C0, 1, 0x44F42D0),
    (0x2D114E0, 1, 0x44F42E0),
    (0x2D11500, 1, 0x44F42F0),
    (0x2D11520, 1, 0x44F4300),
    (0x2D11540, 1, 0x44F4310),
    (0x2D11560, 1, 0x44F4320),
    (0x2D11580, 2, 0x44F4330),
    (0x2D115C0, 6, 0x44F4360),
    (0x2D115E0, 1, 0x44F43C0),
    (0x2D11600, 2, 0x44F43D0),
    (0x2D11620, 2, 0x44F43F0),
    (0x2D11640, 1, 0x44F4410),
    (0x2D11660, 1, 0x44F4420),
    (0x2D11680, 1, 0x44F4430),
    (0x2D116A0, 1, 0x44F4440),
    (0x2D116C0, 1, 0x44F4450),
    (0x2D11740, 1, 0x44F4460),
    (0x2D11760, 1, 0x44F4470),
    (0x2D11780, 1, 0x44F4480),
    (0x2D117A0, 1, 0x44F4490),
    (0x2D117C0, 1, 0x44F44A0),
    (0x2D117E0, 1, 0x44F44B0),
    (0x2D11800, 1, 0x44F44C0),
    (0x2D11820, 1, 0x44F44D0),
    (0x2D11840, 10, 0x44F44E0),
    (0x2D11860, 1, 0x44F4580),
    (0x2D11880, 1, 0x44F4590),
    (0x2D118A0, 1, 0x44F45A0),
    (0x2D118C0, 1, 0x44F45B0),
    (0x2D119B0, 1, 0x44F45C0),
    (0x2D119D0, 1, 0x44F45D0),
    (0x2D11A40, 2, 0x44F45E0),
    (0x2D11B10, 3, 0x44F4600),
    (0x2D11C30, 2, 0x44F4630),
    (0x2D11CF0, 1, 0x44F4650),
    (0x2D11D80, 3, 0x44F4660),
    (0x2D11DA0, 5, 0x44F4690),
    (0x2D11DC0, 6, 0x44F46E0),
    (0x2D11E30, 5, 0x44F4740),
    (0x2D11E50, 5, 0x44F4790),
    (0x2D11E70, 5, 0x44F47E0),
    (0x2D11E90, 6, 0x44F4830),
    (0x2D11EB0, 7, 0x44F4890),
    (0x2D11ED0, 5, 0x44F4900),
    (0x2D11EF0, 2, 0x44F4950),
    (0x2D11F10, 2, 0x44F4970),
    (0x2D11F30, 2, 0x44F4990),
    (0x2D11F50, 1, 0x44F49B0),
    (0x2D11F70, 2, 0x44F49C0),
    (0x2D11F90, 7, 0x44F49E0),
    (0x2D11FB0, 7, 0x44F4A50),
    (0x2D11FD0, 7, 0x44F4AC0),
    (0x2D11FF0, 2, 0x44F4B30),
    (0x2D12050, 1, 0x44F4B50),
    (0x2D12070, 1, 0x44F4B60),
    (0x2D12090, 2, 0x44F4B70),
    (0x2D120B0, 5, 0x44F4B90),
    (0x2D12250, 3, 0x44F4BE0),
    (0x2D12320, 1, 0x44F4C10),
    (0x2D12340, 1, 0x44F4C20),
    (0x2D12360, 1, 0x44F4C30),
    (0x2D12380, 1, 0x44F4C40),
    (0x2D123F0, 1, 0x44F4C50),
    (0x2D12470, 1, 0x44F4C60),
    (0x2D12490, 1, 0x44F4C70),
    (0x2D124B0, 1, 0x44F4C80),
    (0x2D124D0, 1, 0x44F4C90),
    (0x2D124F0, 1, 0x44F4CA0),
    (0x2D12510, 1, 0x44F4CB0),
    (0x2D12530, 1, 0x44F4CC0),
    (0x2D12550, 1, 0x44F4CD0),
    (0x2D12590, 1, 0x44F4CF0),
    (0x2D125B0, 1, 0x44F4D00),
    (0x2D125D0, 1, 0x44F4D10),
    (0x2D12640, 2, 0x44F4D20),
    (0x2D126D0, 2, 0x44F4D40),
    (0x2D126F0, 1, 0x44F4D60),
    (0x2D12710, 2, 0x44F4D70),
    (0x2D12730, 2, 0x44F4D90),
    (0x2D12750, 2, 0x44F4DB0),
    (0x2D12770, 2, 0x44F4DD0),
    (0x2D12790, 3, 0x44F4DF0),
    (0x2D127B0, 3, 0x44F4E20),
    (0x2D128E0, 2, 0x44F4E50),
    (0x2D12900, 3, 0x44F4E70),
    (0x2D12920, 2, 0x44F4EA0),
    (0x2D12940, 1, 0x44F4EC0),
    (0x2D12960, 1, 0x44F4ED0),
    (0x2D12980, 1, 0x44F4EE0),
    (0x2D129A0, 6, 0x44F4EF0),
    (0x2D12A00, 1, 0x44F4F50),
    (0x2D12A20, 4, 0x44F4F60),
    (0x2D12AE0, 1, 0x44F4FA0),
    (0x2D12B00, 5, 0x44F4FB0),
    (0x2D12C10, 5, 0x44F5000),
    (0x2D12CD0, 3, 0x44F5050),
    (0x2D12CF0, 1, 0x44F5080),
    (0x2D12D10, 2, 0x44F5090),
    (0x2D12D30, 5, 0x44F50B0),
    (0x2D12D50, 8, 0x44F5100),
    (0x2D12D70, 4, 0x44F5180),
    (0x2D12DE0, 4, 0x44F51C0),
    (0x2D12E50, 1, 0x44F5200),
    (0x2D12E70, 2, 0x44F5210),
    (0x2D12E90, 6, 0x44F5230),
    (0x2D12F40, 3, 0x44F5290),
    (0x2D12FE0, 3, 0x44F52C0),
    (0x2D13000, 1, 0x44F52F0),
    (0x2D13070, 1, 0x44F5300),
    (0x2D130F0, 1, 0x44F5310),
    (0x2D13110, 1, 0x44F5320),
    (0x2D13130, 1, 0x44F5330),
    (0x2D13150, 2, 0x44F5340),
    (0x2D13170, 1, 0x44F5360),
    (0x2D13190, 1, 0x44F5370),
    (0x2D131B0, 1, 0x44F5380),
    (0x2D13300, 1, 0x44F5390),
    (0x2D13320, 1, 0x44F53A0),
    (0x2D13340, 6, 0x44F53B0),
    (0x2D133B0, 1, 0x44F5410),
    (0x2D133D0, 1, 0x44F5420),
    (0x2D133F0, 1, 0x44F5430),
    (0x2D13410, 1, 0x44F5440),
    (0x2D13430, 1, 0x44F5450),
    (0x2D13450, 1, 0x44F5460),
    (0x2D13470, 1, 0x44F5470),
    (0x2D13490, 1, 0x44F5480),
    (0x2D134B0, 1, 0x44F5490),
    (0x2D134D0, 1, 0x44F54A0),
    (0x2D134F0, 2, 0x44F54B0),
    (0x2D13530, 1, 0x44F54E0),
    (0x2D13550, 2, 0x44F54F0),
    (0x2D13620, 2, 0x44F5510),
    (0x2D13640, 1, 0x44F5530),
    (0x2D136D0, 1, 0x44F5540),
    (0x2D136F0, 2, 0x44F5550),
    (0x2D13710, 3, 0x44F5570),
    (0x2D13730, 2, 0x44F55A0),
    (0x2D138F0, 3, 0x44F55C0),
    (0x2D13960, 2, 0x44F55F0),
    (0x2D13980, 1, 0x44F5610),
    (0x2D139A0, 1, 0x44F5620),
    (0x2D139C0, 1, 0x44F5630),
    (0x2D139E0, 1, 0x44F5640),
    (0x2D13A00, 3, 0x44F5650),
    (0x2D13A60, 1, 0x44F5680),
    (0x2D13A80, 1, 0x44F5690),
    (0x2D13AA0, 1, 0x44F56A0),
    (0x2D13AC0, 1, 0x44F56B0),
    (0x2D13AE0, 1, 0x44F56C0),
    (0x2D13B00, 3, 0x44F56D0),
    (0x2D13BB0, 3, 0x44F5700),
    (0x2D13BD0, 1, 0x44F5730),
    (0x2D13BF0, 1, 0x44F5740),
    (0x2D13C10, 1, 0x44F5750),
    (0x2D13C30, 1, 0x44F5760),
    (0x2D13CC0, 2, 0x44F5770),
    (0x2D13CE0, 3, 0x44F5790),
    (0x2D13D00, 1, 0x44F57C0),
    (0x2D13DA0, 1, 0x44F57D0),
    (0x2D13DC0, 3, 0x44F57E0),
    (0x2D13DE0, 1, 0x44F5810),
    (0x2D13E00, 2, 0x44F5820),
    (0x2D13E20, 5, 0x44F5840),
    (0x2D13E40, 3, 0x44F5890),
    (0x2D13E60, 2, 0x44F58C0),
    (0x2D13F10, 1, 0x44F58E0),
    (0x2D13F30, 1, 0x44F58F0),
    (0x2D13F50, 1, 0x44F5900),
    (0x2D13F70, 3, 0x44F5910),
    (0x2D13F90, 3, 0x44F5940),
    (0x2D13FB0, 3, 0x44F5970),
    (0x2D14010, 1, 0x44F59A0),
    (0x2D14030, 5, 0x44F59B0),
    (0x2D140B0, 1, 0x44F5A00),
    (0x2D140D0, 1, 0x44F5A10),
    (0x2D140F0, 1, 0x44F5A20),
    (0x2D14110, 1, 0x44F5A30),
    (0x2D14130, 3, 0x44F5A40),
    (0x2D14160, 3, 0x44F5A70),
    (0x2D14180, 3, 0x44F5AA0),
    (0x2D141A0, 2, 0x44F5AD0),
    (0x2D14220, 1, 0x44F5AF0),
    (0x2D14240, 3, 0x44F5B00),
    (0x2D142A0, 1, 0x44F5B30),
    (0x2D142C0, 1, 0x44F5B40),
    (0x2D142E0, 2, 0x44F5B50),
    (0x2D14430, 3, 0x44F5B70),
    (0x2D14470, 4, 0x44F5BA0),
    (0x2D14490, 1, 0x44F5BE0),
    (0x2D144B0, 1, 0x44F5BF0),
    (0x2D144D0, 6, 0x44F5C00),
    (0x2D144F0, 1, 0x44F5C60),
    (0x2D14510, 1, 0x44F5C70),
    (0x2D14530, 1, 0x44F5C80),
    (0x2D14550, 1, 0x44F5C90),
    (0x2D14570, 1, 0x44F5CA0),
    (0x2D14590, 3, 0x44F5CB0),
    (0x2D145B0, 1, 0x44F5CE0),
    (0x2D145D0, 1, 0x44F5CF0),
    (0x2D145F0, 2, 0x44F5D00),
    (0x2D14660, 1, 0x44F5D20),
    (0x2D14680, 1, 0x44F5D30),
    (0x2D146A0, 1, 0x44F5D40),
    (0x2D146C0, 1, 0x44F5D50),
    (0x2D146E0, 1, 0x44F5D60),
    (0x2D14700, 1, 0x44F5D70),
    (0x2D14720, 4, 0x44F5D80),
    (0x2D14740, 6, 0x44F5DC0),
    (0x2D147D0, 1, 0x44F5E20),
    (0x2D147F0, 3, 0x44F5E30),
    (0x2D14810, 6, 0x44F5E60),
    (0x2D14860, 1, 0x44F5EC0),
    (0x2D14880, 3, 0x44F5ED0),
    (0x2D148E0, 1, 0x44F5F00),
    (0x2D14990, 2, 0x44F5F30),
    (0x2D149B0, 2, 0x44F5F50),
    (0x2D149D0, 2, 0x44F5F70),
    (0x2D149F0, 3, 0x44F5F90),
    (0x2D14A10, 1, 0x44F5FC0),
    (0x2D14A30, 3, 0x44F5FD0),
    (0x2D14CB0, 6, 0x44F6000),
    (0x2D14D70, 9, 0x44F6060),
    (0x2D14E50, 4, 0x44F60F0),
    (0x2D14F30, 5, 0x44F6130),
    (0x2D14F50, 1, 0x44F6180),
    (0x2D14F70, 2, 0x44F6190),
    (0x2D14F90, 2, 0x44F61B0),
    (0x2D14FB0, 2, 0x44F61D0),
    (0x2D15070, 3, 0x44F61F0),
    (0x2D150F0, 3, 0x44F6220),
    (0x2D15110, 3, 0x44F6250),
    (0x2D15130, 1, 0x44F6280),
    (0x2D15150, 1, 0x44F6290),
    (0x2D15170, 6, 0x44F62A0),
    (0x2D15190, 1, 0x44F6300),
    (0x2D151B0, 1, 0x44F6310),
    (0x2D151D0, 1, 0x44F6320),
    (0x2D151F0, 3, 0x44F6330),
    (0x2D15260, 4, 0x44F6360),
    (0x2D15280, 4, 0x44F63A0),
    (0x2D152F0, 3, 0x44F63E0),
    (0x2D15310, 2, 0x44F6410),
    (0x2D153D0, 3, 0x44F6430),
    (0x2D153F0, 1, 0x44F6460),
    (0x2D15410, 4, 0x44F6470),
    (0x2D15430, 3, 0x44F64B0),
    (0x2D15450, 3, 0x44F64E0),
    (0x2D15470, 1, 0x44F6510),
    (0x2D15490, 4, 0x44F6520),
    (0x2D154B0, 7, 0x44F6560),
    (0x2D154D0, 7, 0x44F65D0),
    (0x2D154F0, 7, 0x44F6640),
    (0x2D15510, 1, 0x44F66B0),
    (0x2D15620, 2, 0x44F66C0),
    (0x2D15640, 1, 0x44F66E0),
    (0x2D15660, 4, 0x44F66F0),
    (0x2D15680, 2, 0x44F6730),
    (0x2D156A0, 2, 0x44F6750),
    (0x2D156C0, 2, 0x44F6770),
    (0x2D156E0, 8, 0x44F6790),
    (0x2D15800, 7, 0x44F6810),
    (0x2D158C0, 2, 0x44F6880),
    (0x2D15B40, 7, 0x44F68A0),
    (0x2D15C70, 2, 0x44F6910),
    (0x2D15DB0, 2, 0x44F6930),
    (0x2D15DE0, 2, 0x44F6950),
    (0x2D15E10, 2, 0x44F6970),
    (0x2D15E40, 5, 0x44F6990),
    (0x2D16230, 2, 0x44F69E0),
    (0x2D16420, 2, 0x44F6A00),
    (0x2D16700, 2, 0x44F6A20),
    (0x2D16880, 1, 0x44F6A40),
    (0x2D16A40, 1, 0x44F6A50),
    (0x2D115A0, 0x80001, 0x44F4350), (0x2D12570, 0x50001, 0x44F4CE0), (0x2D13510, 0x50001, 0x44F54D0),
)


def _factory(tag, r):
    def fn(m, out, *_):
        m.put(out, 4, tag)
        return m.main + r
    return fn


for _addr, _tag, _r in _FACTORIES:
    lifted(_addr)(_factory(_tag, _r))


@lifted(0x2D0DF50)
def factory_by_kind(m, out, kind, *_):
    """Kinds 5..7: tag (1, 1, 3) [0x3c69f60] and the descriptor pointer [0x44f1498 + 8 i]; any other
    kind: tag 1 and main+0x44f12f8."""
    i = (kind - 5) & 0xFF
    if i > 2:
        m.put(out, 4, 1)
        return m.main + 0x44F12F8
    m.put(out, 4, (1, 1, 3)[i])
    return m.u64(m.main + 0x44F1498 + 8 * i)
