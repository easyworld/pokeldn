"""Party member lists and the walks over the members still in the battle."""

from pokeldn.sv.battle.engine.calls import M32, _need, _tail, _vtail
from pokeldn.sv.battle.engine.rules import _rule_499_bit2
from pokeldn.sv.battle.engine.slots import SIDE
from pokeldn.sv.battle.machine import UnliftedCall, lifted


@lifted(0x114E4C0)
def member(m, lst, i, *_):
    i &= 0xFF
    return m.u64(lst + 8 * i) if i < m.u8(lst + 0x30) else 0


@lifted(0xE7E454)
def able_members(m, lst, *_):
    """How many members of a party list (count at +0x30) are able (vf 0x208)."""
    n = 0
    i = 0
    while i < m.u8(lst + 0x30):
        n = (n + (m.vcall(m.u64(lst + 8 * i), 0x208) & 1)) & 0xFFFFFFFF
        i += 1
    return n


@lifted(0x10D3F10)
def first_not_78(m, o, *_):
    """When flag bit 3 of [[o+0x10]+0x38]+0x499 is set: the first party member, client by client, for which
    vf 0x78 is false, skipping clients on the side of client byte [o+0x10]+0x95; else 0."""
    if m.u8(m.u64(m.u64(o + 0x10) + 0x38) + 0x499) >> 3 & 1 == 0:
        return 0
    for c in range(5):
        setup = m.u64(m.u64(m.u64(o + 8) + 0x290) + 8)
        if m.call(m.main + 0xE7E2A0, m.u32(setup + 0x36C), m.u8(setup + 0x370), c) & 1 == 0:
            continue
        s = m.u64(o + 8)
        sides = SIDE.get(m.u32(s + 0x36C))
        v = m.u8(m.u64(o + 0x10) + 0x95)
        if sides is not None and v <= 4 and sides[v] <= 1:
            a, t = sides[v], sides[c]
            if a == t or t == 3 or (t == 4 and a != 0) or (t == 5 and a != 1):
                continue
        parties = m.u64(s + 0x30) + 0x38 * c
        i = 0
        while i < m.u8(parties + 0x58):
            b = m.u64(parties + 0x28 + 8 * i)
            if m.vcall(b, 0x78) & 1 == 0:
                return b
            i += 1
    return 0


@lifted(0x1360404)
def each_standing_1360480(m, o, arg, *_):
    """0x1360480 (queue object, member, arg) for every party member still in the battle."""
    with m.frame(0x40) as f:
        it, out = f, f + 0x38
        m.put(out, 8, 0)
        a = m.call(m.main + 0x114E480, o, arg)
        b = m.call(m.main + 0x1482534, o)
        m.call_void(m.main + 0x1147754, it, a, b)
        while m.call(m.main + 0x1360DBC, it, out) & 1:
            q = m.call(m.main + 0x1143584, o)
            m.call_void(m.main + 0x1360480, q, m.u64(out), arg)


@lifted(0x11430E4)
def run_11438e4_pair(m, o, b, *_):
    """For a battler still in the battle (vf 0x200 clear): 0x11438e4 with (6, 1, 3, 1), then (7, 2, 4, 2)."""
    if m.vcall(b, 0x200) & 1:
        return
    m.call_void(m.main + 0x11438E4, o, b, 6, 1, 3, 1)
    return _tail(m, m.main + 0x11438E4, o, b, 7, 2, 4, 2)


@lifted(0x1142DCC)
def each_standing_11430e4(m, o, *rest):
    """When 0x113f5b8 allows it: 0x11430e4 for every party member still in the battle that 0x1142e68
    accepts."""
    if m.call(m.main + 0x113F5B8, m.call(m.main + 0x114E480, o, *rest[:7]), *rest[:7]) & 1 == 0:
        return
    with m.frame(0x30) as f:
        it, out = f, f + 0x20
        a = m.call(m.main + 0x114E480, o)
        b = m.call(m.main + 0x1482534, o)
        m.call_void(m.main + 0x1147754, it, a, b)
        while m.call(m.main + 0x1360DBC, it, out) & 1:
            a = m.call(m.main + 0x114E480, o)
            b = m.call(m.main + 0x1482534, o)
            if m.call(m.main + 0x1142E68, a, b, m.u64(out)) & 1:
                m.call_void(m.main + 0x11430E4, o, m.u64(out))


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


@lifted(0x1143D84)
def clear_member_list(m, lst, *_):
    m.write(lst, bytes(0x8F))
    m.put(lst + 0x90, 8, 0); m.put(lst + 0x98, 8, 0); m.put(lst + 0xA0, 8, 0); m.put(lst + 0xA8, 2, 0)


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


@lifted(0x14B5634)
def party_list(m, parties, client, *_):
    """The member list (+0x28 + 0x38 * client) of a client's party; 0 past client 4."""
    client &= 0xFFFFFFFF
    return (parties + 0x38 * client + 0x28) & 0xFFFFFFFFFFFFFFFF if client <= 4 else 0


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


def _standing_of(m, o_it_owner, pokecon):
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


def _standing(m, o):
    """Each party member still in the battle, as the server's inlined iterator (0x1147774 then the
    0x1360dbc step) hands them out."""
    from pokeldn.sv.battle.engine.flow import first_standing, next_standing
    with m.frame(0x28) as it:
        m.put(it, 8, m.u64(m.main + 0x46E2580) + 0x10)
        m.put(it + 8, 8, m.u64(o + 8)); m.put(it + 0x10, 8, m.u64(o + 0x10))
        m.put(it + 0x18, 2, 0); m.put(it + 0x1A, 1, 1)
        first_standing(m, it)
        while next_standing(m, it, it + 0x20):
            yield m.u64(it + 0x20)


@lifted(0x114140C)
def note_standing_ids(m, o, *_):
    """Add each standing member's id to the byte list at [[o+0x40]+0x68] (30 bytes from +8, count +0x28)."""
    if _rule_499_bit2(m, o):
        return
    for b in _standing(m, o):
        v = m.vcall(b, 0x98) & 0xFFFFFFFF
        t = m.u64(m.u64(o + 0x40) + 0x68)
        if m.call(m.main + 0x114E624, t, v) & 1 == 0:
            n = m.s(t + 0x28, 4)
            if n <= 0x1D:
                m.put(t + 8 + n, 1, v)
                m.put(t + 0x28, 4, m.u32(t + 0x28) + 1)


@lifted(0x1147754)
def standing_iterator(m, it, setup, pokecon, *_):
    """Build the standing-member iterator (vtable main+0x4500bb0) and point it at the first member."""
    m.put(it + 0x18, 2, 0)
    m.put(it, 8, m.main + 0x4500BB0)
    m.put(it + 0x1A, 1, 1)
    m.put(it + 8, 8, setup); m.put(it + 0x10, 8, pokecon)
    return _tail(m, m.main + 0x1147774, it)


@lifted(0xFA1F30)
def push_side_battler(m, o, side, ident, *_):
    """Append battler `ident` (map o+0x140) to side's list (o + side*0x38: objects +0x28, count u8 +0x58),
    taking and dropping a reference on its control block; nothing when the id is unknown, a null entry
    when the node holds none."""
    from pokeldn.sv.battle.engine.containers import find
    node = find(m, o + 0x140, ident & 0xFFFFFFFF, 4)
    if not node:
        return o
    obj = m.u64(node + 0x18)
    row = o + (side & 0xFF) * 0x38
    if obj == 0:
        c = m.u8(row + 0x58)
        m.put(row + 0x58, 1, c + 1)
        m.put(row + 0x28 + 8 * c, 8, 0)
        return o
    ctl = m.u64(obj + 0x30)
    inner = m.u64(ctl + 0x10)
    if inner == 0:
        raise UnliftedCall("AddReference abort: m_object is null")
    count = m.u16(ctl + 0x1A)
    if count == 0xFFFF:
        raise UnliftedCall("AddReference abort: counter overflow")
    if count == 0:
        _need(m, m.u64(m.u64(inner)))
        _need(m, m.u64(m.u64(obj) + 0x50))
    r = o
    m.put(ctl + 0x1A, 2, count + 1)
    if count == 0:
        r = m.vcall(inner, 0)
        m.put(ctl + 8, 8, r)
        m.put(ctl + 0x1C, 4, 0xFFFFFFFE)
    c = m.u8(row + 0x58)
    m.put(row + 0x58, 1, c + 1)
    m.put(row + 0x28 + 8 * c, 8, obj)
    ctl = m.u64(obj + 0x30)
    count = m.u16(ctl + 0x1A)
    if count == 0:
        raise UnliftedCall("ReleaseReference abort: counter underflow")
    m.put(ctl + 0x1A, 2, count - 1)
    if count == 1:
        m.put(ctl + 0x10, 8, 0)
        return _vtail(m, obj, 0x50)
    return r


def _first_party_id(m, x):
    """The cached id at x+0x18, filled from the party's first member when the rule (bit 2 of byte
    0x499) asks for it and it is unset."""
    if m.u8(m.u64(m.u64(x + 8) + 0x38) + 0x499) & 4 and m.u32(x + 0x18) == 0:
        p = m.call(m.main + 0x114C614, m.call(m.main + 0x14B5634, m.u64(m.u64(x + 0x10) + 0x30), 1), 0)
        if p:
            m.put(x + 0x18, 4, m.vcall(p, 0x98))
    return m.u32(x + 0x18)


@lifted(0x2888968)
def run_1361bb0(m, o, b, *_):
    with m.frame(0x10) as f:
        m.put(f + 8, 8, b)
        m.call_void(m.main + 0x1361BB0, m.call(m.main + 0x1360F04, m.call(m.main + 0x1361214, o)), f, f + 8)


@lifted(0x283E66C)
def queue_10_if_standing(m, o, out, p, *_):
    """out (byte) = 0x288426c for battler [p] when it is standing, else 0."""
    b = m.call(m.main + 0x13813F4, o, m.u32(p))
    if m.vcall(b, 0x200) & 1:
        m.put(out, 1, 0)
        return
    m.put(out, 1, m.call(m.main + 0x288426C, m.call(m.main + 0x1143584, o), m.u32(p)) & 1)


@lifted(0x1584710)
def member_byte_84(m, lst, b, *_):
    """The +0x84 byte of b's entry in the member list, 0 when b is not in it."""
    for i in range(m.u8(lst + 0xA6)):
        if m.u64(lst + 8 * i) == b:
            return m.u8(lst + 0x84 + i)
    return 0


def _clear_members(m, lst):
    m.write(lst, bytes(0x8F))
    m.write(lst + 0x90, bytes(0x18)); m.put(lst + 0xA8, 2, 0)


@lifted(0x114C614)
def list_member(m, lst, i, *_):
    """Member i of a battler list (count at +0x30), 0 past the end."""
    i &= 0xFF
    return m.u64(lst + 8 * i) if m.u8(lst + 0x30) > i else 0


def _unique_ids(m, n, kinds, lst, pick):
    ids = []
    for i in range(n):
        if not pick(m.u8(kinds + i)):
            continue
        v = m.vcall(m.u64(lst + 8 * i), 0x98) & M32
        if len(ids) <= 9 and v not in ids:
            ids.append(v)
    return ids


@lifted(0x2880EA4)
def fill_members(m, o, lst, *_):
    with m.frame(0x10) as f:
        m.put(f + 8, 8, lst)
        x = m.call(m.main + 0x1143DE8, m.u64(o + 0x78))
        return _tail(m, m.main + 0x1143DF0, x, f, f + 8)


@lifted(0x2880ED4)
def run_17776d8_17(m, o, b, *_):
    """0x17776d8 with the record {b's id, 0x17}."""
    with m.frame(0x20) as f:
        r = f + 0x18
        m.put(r, 4, m.vcall(b, 0x98) & M32); m.put(r + 4, 1, 0x17)
        x = m.call(m.main + 0x17776D0, m.u64(o + 0x78))
        return _tail(m, m.main + 0x17776D8, x, f + 8, r)


@lifted(0x2880D90)
def mark_able_members_17(m, o, *_):
    """0x2880ed4 for every member 0x2880ea4 lists that can act (vf 0x208)."""
    with m.frame(0xB0) as lst:
        m.write(lst, bytes(0xAA))
        m.call_void(m.main + 0x2880EA4, o, lst)
        m.put(lst + 0xA8, 1, 0)
        if not m.u8(lst + 0xA6):
            return
        m.put(lst + 0xA8, 1, 1)
        p = m.u64(lst)
        while p:
            if m.vcall(p, 0x208) & 1:
                m.call_void(m.main + 0x2880ED4, o, p)
            i = m.u8(lst + 0xA8)
            if i >= m.u8(lst + 0xA6):
                break
            m.put(lst + 0xA8, 1, i + 1)
            p = m.u64(lst + 8 * i)


@lifted(0x1361BB0)
def each_standing_not_allied(m, o, _out, pb, *_):
    """0x2884b18 for every standing member that 0x15c04a4 does not pair with the battler [pb]."""
    uid = m.vcall(m.u64(pb), 0x98) & M32
    with m.frame(0x30) as sp:
        it, cur = sp, sp + 0x28
        m.call_void(m.main + 0x1147754, it, m.call(m.main + 0x114E480, o), m.call(m.main + 0x1482534, o))
        while m.call(m.main + 0x1360DBC, it, cur) & 1:
            t = m.u64(cur)
            if not m.call(m.main + 0x15C04A4, o, uid, m.vcall(t, 0x98) & M32) & 1:
                m.call_void(m.main + 0x2884B18, o, t)


def _for_each_member(m, lst, fn):
    """The game's walk of a member list: cursor +0xa8 from 0, stop at a null entry or the count +0xa6."""
    n = m.u8(lst + 0xA6)
    m.put(lst + 0xA8, 1, 0)
    if not n:
        return
    t = m.u64(lst)
    m.put(lst + 0xA8, 1, 1)
    while t:
        fn(t)
        i = m.u8(lst + 0xA8)
        if i >= m.u8(lst + 0xA6):
            return
        m.put(lst + 0xA8, 1, i + 1)
        t = m.u64(lst + 8 * i)


@lifted(0x114E224)
def add_id(m, p, v, *_):
    """Add the u32 v to the set at p (count byte +8, at most 10, values from +0xc) once."""
    n = m.u8(p + 8)
    if n > 9:
        return p
    if any(m.u32(p + 0xC + 4 * i) == v & M32 for i in range(n)):
        return p
    m.put(p + 0xC + 4 * n, 4, v)
    m.put(p + 8, 1, n + 1)
    return p


@lifted(0x1147A58)
def add_member_once(m, lst, b, *_):
    from pokeldn.sv.battle.engine.flow import add_member
    if b:
        add_member(m, lst, b)
    return lst


def _walk_standing(m, it):
    """The inlined walk of a standing-member iterator (0x1147774 / 0x1147754 built it): hand out the current
    entry, move to the next member not down (vf 0x200) by the slot's position count (0xff9128), then
    yield the handed-out one; ends after the last."""
    if m.u8(it + 0x1A):
        return
    pokecon = m.u64(it + 0x10)
    while True:
        client, idx = m.u8(it + 0x18), m.u8(it + 0x19)
        pl = m.u64(pokecon + 0x30) + 0x38 * client + 0x28 if client <= 4 else 0
        b = m.u64(pl + 8 * idx) if idx < m.u8(pl + 0x30) else 0
        i = (idx + 1) & 0xFF
        m.put(it + 0x19, 1, i)
        done = True
        if client <= 4:
            while True:
                setup = m.u64(m.u64(pokecon + 0x290) + 8)
                n = m.call(m.main + 0xFF9128, m.u32(setup + 0x36C), m.u8(setup + 0x370), client) & 0xFF
                found = False
                while n > i:
                    base = m.u64(pokecon + 0x30) + 0x38 * client
                    if m.u8(base + 0x58) > i:
                        x = m.u64(base + 0x28 + 8 * i)
                        if x and not m.vcall(x, 0x200) & 1:
                            found = True
                            break
                    i = (i + 1) & 0xFF
                    m.put(it + 0x19, 1, i)
                if found:
                    done = False
                    break
                client = (client + 1) & 0xFF
                m.put(it + 0x18, 1, client); m.put(it + 0x19, 1, 0)
                i = 0
                if client > 4:
                    break
        if done:
            m.put(it + 0x1A, 1, 1)
        yield b
        if done:
            return


@lifted(0x11474B0)
def standing_in_set(m, o, lst, ids, *_):
    """Add to lst every standing member (iterator over [o+8], [o+0x10]) whose id is in the set ids (count
    byte +8, u32s from +0xc)."""
    with m.frame(0x20) as it:
        m.call_void(m.main + 0x1147754, it, m.u64(o + 8), m.u64(o + 0x10))
        for b in _walk_standing(m, it):
            ident = m.vcall(b, 0x98) & M32
            if any(m.u32(ids + 0xC + 4 * k) == ident for k in range(m.u8(ids + 8))):
                m.call_void(m.main + 0x1147A58, lst, b)


@lifted(0x114EA98)
def swap_members(m, lst, i, j, *_):
    i &= 0xFF; j &= 0xFF
    a, b = m.u64(lst + 8 * i), m.u64(lst + 8 * j)
    m.put(lst + 8 * i, 8, b); m.put(lst + 8 * j, 8, a)
