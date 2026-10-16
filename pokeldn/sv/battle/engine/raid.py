"""The raid battler: its cached id, its extra actions, its turn and the record the server keeps for it."""

from pokeldn.sv.battle.engine import flatbuffer as fb
from pokeldn.sv.battle.engine.calls import M32, _f32, _need, _tail
from pokeldn.sv.battle.engine.containers import data_record
from pokeldn.sv.battle.engine.data import static_table
from pokeldn.sv.battle.engine.messages import _store_and_command_75
from pokeldn.sv.battle.engine.rules import _class_of, _rule_or_0, _rule_s32
from pokeldn.sv.battle.machine import lifted


@lifted(0x15662A0)
def start_record(m, rec, value, *_):
    """State 0 -> 1: keep `value` (u32) at +0x68 and vf 0x108 of 0xf6fc68's object (u16) at +0x90."""
    if m.u32(rec + 0x70):
        return
    m.put(rec + 0x70, 4, 1)
    m.put(rec + 0x68, 8, value & 0xFFFFFFFF)
    p = m.call(m.main + 0xF6FC68, rec, value)
    m.put(rec + 0x90, 4, m.vcall(p, 0x108) & 0xFFFF)


@lifted(0x15661E0)
def record_event(m, rec, kind, v, *_):
    """Apply event `kind` (1..7) with argument `v` to the record at [server]+0x310."""
    kind = (kind & 0xFF) - 1
    if kind == 0:
        start_record(m, rec, v & 0xFFFFFFFF)
    elif kind == 1:
        if m.u32(rec + 0x70) == 1:
            m.put(rec + 0x70, 4, 2)
            if v & 0xFFFFFFFF == 1:
                m.put(rec + 0x7C, 8, 0xFFFFFFFFFFFFFFFF); m.put(rec + 0x84, 2, 0xFFFF)
    elif kind == 2:
        m.put(rec + 0x8D, 1, 1)
    elif kind == 3:
        i = v & 0xFFFFFFFF
        i = i - (1 << 32) if i & 0x80000000 else i
        if i <= 5:
            m.put(rec + 0x86 + i, 1, 1)
    elif kind == 4:
        m.put(rec + 0x8C, 1, 1)
    elif kind == 5:
        if v & 0xFF <= 4:
            m.put(rec + 0x7C + 2 * (v & 0xFF), 2, 0)
    elif kind == 6:
        if m.u32(rec + 0x70) == 1:
            m.put(rec + 0x78, 4, m.u32(rec + 0x78) + v)


@lifted(0x15661B0)
def server_record_event(m, o, kind, v, *_):
    return record_event(m, m.call(m.main + 0x11409B4, m.u64(o + 0x10)), kind, v)


@lifted(0x1142508)
def record_object(m, o, *rest):
    """Tail call of 0xf6fc68 on the record at [[o+0x10]+0x310]."""
    rec = m.call(m.main + 0x11409B4, m.call(m.main + 0x1482534, o))
    return m.call(m.main + 0xF6FC68, rec, *rest[:7])


@lifted(0x162B7F0)
def note_raid_side(m, o, p, ident, *_):
    """For a nonzero id that 0x162b830 accepts, the tail call of 0x162b8a0: when [o+8]'s +0x30 count is
    below 2, keep the id's rule value at [[o+8]+0x40]+0x278 and its byte +4 (6 when absent) at +0x27c."""
    ident &= 0xFFFFFFFF
    if ident == 0 or m.call(m.main + 0x162B830, o, p, ident) & 1 == 0:
        return
    s, pokecon = m.u64(o + 8), m.u64(o + 0x10)
    if m.u32(m.u64(s + 0x38) + 0x30) > 1:
        return
    v = _rule_s32(m, pokecon, ident)
    m.put(m.u64(s + 0x40) + 0x278, 4, v or 0)
    q = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(pokecon + 0x290) + 8) + 0x50), ident)
    m.put(m.u64(s + 0x40) + 0x27C, 4, m.u8(q + 4) if q else 6)


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


def _raid_id(m, rec):
    """The raid battler id the record caches at +0x18, looked up once while setup flag 0x4d2 is set."""
    if m.u8(m.u64(m.u64(rec + 8) + 0x38) + 0x499) >> 2 & 1 and m.u32(rec + 0x18) == 0:
        lst = m.call(m.main + 0x14B5634, m.u64(m.u64(rec + 0x10) + 0x30), 1)
        b = m.call(m.main + 0x114C614, lst, 0)
        if b:
            m.put(rec + 0x18, 4, m.vcall(b, 0x98))
    return m.u32(rec + 0x18)


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


@lifted(0x1143624)
def raid_count_open(m, o, *_):
    """In battle mode 2: whether 0x1149124 finds any (on [[o+0x78]+0x1f00]); 0 otherwise."""
    if m.call(m.main + 0x1143680, o) & M32 != 2:
        return 0
    with m.frame(0x10) as f:
        m.put(f, 1, 0)
        m.call_void(m.main + 0x1149124, m.call(m.main + 0x114368C, m.u64(o + 0x78)), f, f + 8)
        return int(m.u8(f) != 0)


@lifted(0x2D35A50)
def mark_raid_bit(m, o, ident, bit, *_):
    """Set bit `bit` of +0x6f4 on battler `ident` when it is of the 0x46d3f08 class, flag +0x6ec is set,
    +0x6ed is 0x63 and +0x6e8 is not 0x3fd."""
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), ident)
    if not b:
        return
    node = m.vcall(b + 0x28, 0)
    static = m.call(m.main + 0x2D1FD38)
    while node and node != static:
        node = m.u64(node)
    if not node:
        return
    if m.u8(b + 0x6EC) and m.u8(b + 0x6ED) == 0x63 and m.u16(b + 0x6E8) != 0x3FD:
        m.put(b + 0x6F4, 4, m.u32(b + 0x6F4) | (1 << (bit & 31)))


@lifted(0x11425B0)
def raid_turn(m, o, *_):
    """When the raid record [o+0x68] has no pending count (+0x7c), 0xf6dd84 fills it; with a count and
    0x1142804 false, the record list from 0x114fb2c is copied into a 35-entry request (count byte +0x231)
    for 0x1145be0."""
    x = m.call(m.main + 0x11427FC, o)
    if m.u32(x + 0x7C):
        return x
    x = m.call(m.main + 0x11427FC, o)
    r = m.call(m.main + 0xF6DD84, x, 0)
    if not m.u32(x + 0x7C):
        return r
    for a in (0x1142804, 0x114FB2C, 0xF6FC54, 0x1145BD8, 0x1145BE0):
        _need(m, m.main + a)
    r = m.call(m.main + 0x1142804, x)
    if r & 1:
        return r
    with m.frame(0x2A0) as sp:
        lst = sp + 0x260
        m.write(lst, bytes(0x40))
        m.call_void(m.main + 0x114FB2C, x, lst)
        n = m.u32(x + 0x7C)
        req = sp + 0x18
        m.write(req, bytes(0x238))
        for k in range(n):
            m.call_void(m.main + 0xF6FC54, req + 0x70 + 0x10 * k, lst + 0x10 * k)
        m.put(req + 0x231, 1, n)
        m.put(sp + 8, 8, m.call(m.main + 0x1149340, o)); m.put(sp + 0x10, 8, req)
        y = m.call(m.main + 0x1145BD8, m.call(m.main + 0x1361214, o))
        return _tail(m, m.main + 0x1145BE0, y, sp, sp + 8)


@lifted(0x287F508)
def level_ratio(m, o, *_):
    """Over clients 0..4 present (0xe7e28c), the first member's vf 0x118 level: the mean level of those
    0x1142ecc pairs with the battle's side, divided by the level of the last other one; 1.0 when either is
    missing (float32 in s0)."""
    from pokeldn.sv.battle.machine import Float32
    same_sum = same_n = other = 0
    for k in range(5):
        if not m.call(m.main + 0xE7E28C, m.call(m.main + 0x13813EC, m.u64(o + 0x10)), k) & 1:
            continue
        b = m.call(m.main + 0x114E4C0, m.call(m.main + 0xE7E3C8, m.u64(m.u64(o + 0x10) + 0x30), k), 0)
        lvl = m.vcall(b, 0x118) & 0xFF
        a = m.call(m.main + 0x149FE8C, m.u64(o + 8))
        c = m.call(m.main + 0x1589A40, o, m.vcall(b, 0x98) & M32)
        same = m.call(m.main + 0x1142ECC, m.call(m.main + 0x13813EC, m.u64(o + 0x10)), a & M32, c & M32) & 1
        if same:
            same_sum = (same_sum + lvl) & M32
            same_n = (same_n + 1) & M32
        else:
            other = lvl
    if not other or not same_n:
        return Float32(1.0)
    mean = _f32(_f32(float(same_sum)) / _f32(float(same_n)))
    return Float32(_f32(mean / _f32(float(other))))


def _fcvtzu32(x):
    if x != x or x <= 0:
        return 0
    return min(int(x), M32)


@lifted(0x287F3D4)
def raid_level_drain(m, o, b, *_):
    """In a raid, for a battler of the battle's side (0x1142e68) that 0x287f478 does not exempt: n =
    float32(0x126b004 * 0.125 * 0x287f508 ratio), queued as -n through 0x287f844."""
    if not m.call(m.main + 0x126B004, m.u64(o + 8)) & M32:
        return
    if not m.call(m.main + 0x1142E68, m.u64(o + 8), m.u64(o + 0x10), b) & 1:
        return
    if not m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x499) >> 2 & 1:
        return
    if m.call(m.main + 0x287F478, o, b) & 1:
        return
    s8 = _f32(float(m.call(m.main + 0x126B004, m.u64(o + 8)) & M32))
    ratio = m.call(m.main + 0x287F508, o)
    n = _fcvtzu32(_f32(float(ratio) * _f32(s8 * 0.125)))
    if not n:
        return
    return _tail(m, m.main + 0x287F844, m.u64(o + 0x20), (-n) & M32)


def _raid_member_id(m, o):
    """[[o+0x10]+0x310]'s cached id (+0x18), looked up once (0x14b5634 member 0) under rule 0x499 bit 2."""
    x = m.u64(m.u64(o + 0x10) + 0x310)
    if m.u8(m.u64(m.u64(x + 8) + 0x38) + 0x499) >> 2 & 1 and m.u32(x + 0x18) == 0:
        b = m.call(m.main + 0x114C614, m.call(m.main + 0x14B5634, m.u64(m.u64(x + 0x10) + 0x30), 1), 0)
        if b:
            m.put(x + 0x18, 4, m.vcall(b, 0x98))
    return m.u32(x + 0x18)


# --- the raid boss's queued actions: up to four (u8 kind +0x5c + 8i, u32 value +0x60 + 8i), count +0x7c,
# in the object at [server module + 0x1b0] (docs/sv_raid.md, The boss's actions) --------------------------

@lifted(0xFAF024)
def clear_actions(m, x, *_):
    """The four queued actions and the count cleared."""
    for i in range(4):
        m.put(x + 0x5C + 8 * i, 1, 0); m.put(x + 0x60 + 8 * i, 4, 0)
    m.put(x + 0x78, 8, 0)


@lifted(0x1142804)
def has_shield_action(m, x, *_):
    """Whether one of the first four queued actions is of kind 1 (the shield)."""
    n = m.u32(x + 0x7C)
    return int(any(i <= 3 and m.u8(x + 0x5C + 8 * i) == 1 for i in range(n)))


@lifted(0x114FC70)
def raid_id(m, rec, *_):
    """The raid battler's id the record caches at +0x18 (_raid_id)."""
    return _raid_id(m, rec)


@lifted(0x114FB2C)
def action_words(m, x, out, *_):
    """Each queued action as a request block action at out + 0x10 * i: the word's kind 0xc (bits 0..3),
    the action's kind byte in bits 4..11, its value's low u16 in bits 32..47, bits 20..31 kept from out,
    the rest clear; the actor u32 the raid battler's id (0x114fc70). Returns the count."""
    n = m.u32(x + 0x7C)
    for i in range(n):
        ident = m.call(m.main + 0x114FC70, m.u64(m.u64(x + 8) + 0x310)) & 0xFFFFFFFF
        a = out + 0x10 * i
        w = m.u64(a) & 0xFFF00000 | 0xC | m.u8(x + 0x5C + 8 * i) << 4 | m.u16(x + 0x60 + 8 * i) << 32
        m.put(a + 8, 4, ident)
        m.put(a, 8, w)
        n = m.u32(x + 0x7C)
    return n
