"""A battler's chosen action: the packed action word of a round's action block, decoded into the server's
0x8c-byte action entry, the action list, its order and running each action."""

from pokeldn.sv.battle.engine.battler import _main_battler
from pokeldn.sv.battle.engine.calls import M32, _tail
from pokeldn.sv.battle.engine.getters import _copy
from pokeldn.sv.battle.engine.members import _clear_members
from pokeldn.sv.battle.engine.raid import _raid_member_id
from pokeldn.sv.battle.machine import lifted

ENTRY = 0x8C


@lifted(0x11461B4)
def decode_action(m, o, entry, word_ptr, client, *_):
    """Decode the packed action at word_ptr (u64 word, then the actor's id) for `client`. 0 for the
    kinds the server ignores; 1 otherwise. Low nibble of the word = kind; a fight (1) carries the
    target position in bits 4..7 and the move in bits 8..23."""
    w = m.u64(word_ptr)
    if w & 0x100F == 0x1003:
        return 0
    client &= 0xFF
    m.write(entry, bytes(ENTRY))
    m.put(entry + 0x84, 4, 0x5400000); m.put(entry + 0x88, 1, 5); m.put(entry + 0x58, 4, 0x20)
    kind = w & 0xF
    lo = w & 0xFFFFFFFF
    if kind == 1:
        m.put(entry + 4, 4, 1)
        m.put(entry + 0x10, 2, lo >> 8)
        m.put(entry + 8, 1, (lo & 0xFF) >> 4)
        m.put(entry + 0xC, 4, m.call(m.main + 0x11464B0, o, (lo & 0xFF) >> 4))
        m.put(entry + 0x12, 1, lo >> 25 & 1)
    elif kind == 2:
        m.put(entry + 4, 4, 2); m.put(entry + 0x14, 4, m.u32(word_ptr + 4))
        m.put(entry + 0x18, 2, lo >> 4); m.put(entry + 0x1A, 1, lo >> 20)
    elif kind == 3:
        m.put(entry + 4, 4, 3); m.put(entry + 0x1C, 1, (lo & 0xFF) >> 4)
        m.put(entry + 0x1D, 1, m.u8(word_ptr + 1) & 0xF); m.put(entry + 0x1E, 1, lo >> 12 & 1)
    elif kind == 4:
        m.put(entry + 4, 4, 6); m.put(entry + 0x1F, 1, lo >> 4); m.put(entry + 0x20, 1, lo >> 12 & 0xF)
        m.put(entry + 0x21, 1, m.u16(word_ptr + 2))
    elif kind == 5:
        m.put(entry + 4, 4, 4); m.put(entry + 0x24, 1, 0); m.put(entry + 0x23, 1, (w & 0xFF) >> 4 & 1)
    elif kind == 6:
        m.put(entry + 4, 4, 5); m.put(entry + 0x22, 1, lo >> 4)
    elif kind in (7, 10, 11):
        m.put(entry + 4, 4, {7: 7, 10: 8, 11: 9}[kind])
    elif kind == 9:
        m.put(entry + 4, 4, 10); m.put(entry + 0x25, 1, lo >> 4)
    elif kind == 0xC:
        m.put(entry + 4, 4, 0xB); m.put(entry + 0x28, 1, w >> 4); m.put(entry + 0x2C, 4, m.u32(word_ptr + 4))
    elif kind == 0xD:
        m.put(entry + 4, 4, 0xE); m.put(entry + 0x40, 1, (w & 0xFF) >> 4)
        m.put(entry + 0x41, 1, m.u8(word_ptr + 1) & 0xF); m.put(entry + 0x42, 1, lo >> 12 & 0xF)
        m.put(entry + 0x43, 1, w >> 60); m.put(entry + 0x4A, 2, m.u8(word_ptr + 7) & 0xF)
        m.put(entry + 0x44, 2, m.u16(word_ptr + 2) & 0xFFF); m.put(entry + 0x46, 2, m.u16(word_ptr + 4) & 0xFFF)
        m.put(entry + 0x48, 2, (w >> 44) & 0xFFF)
    else:
        return 0
    if lo & 0xF == 3:
        plist = m.u64(m.u64(o + 0x10) + 0x30) + 0x38 * client + 0x28 if client < 5 else 0
        b = m.call(m.main + 0x114C614, plist, (lo >> 4) & 0xF)
        actor = m.vcall(b, 0x98) if b else 0
    else:
        actor = m.u64(word_ptr + 8)
    m.put(entry, 4, actor)
    m.put(entry + 0x88, 1, client)
    m.put(entry + 0x89, 2, 0); m.put(entry + 0x8B, 1, 0)
    counter = m.u64(m.u64(o + 0x10) + 0x190)
    n = m.u32(counter + 8)
    if n == 0:
        n = 1
        m.put(counter + 8, 4, 1)
    m.put(entry + 0x54, 4, n)
    m.put(counter + 8, 4, m.u32(counter + 8) + 1)
    return 1


BLOCK, COUNTS = 0x70, 0x230      # one 0x70-byte block of (action word, actor id) pairs per client


@lifted(0x1145E40)
def collect_actions(m, o, actions, header, *_):
    """Decode every action of a round's action header into the server's action list: client c's
    count is the byte at header+0x230+c and its pairs start at header+0x70*c."""
    from pokeldn.sv.battle.engine.getters import append_action
    with m.frame(0xA0) as entry, m.frame(0x10) as word:
        for client in range(5):
            for k in range(m.u8(header + COUNTS + client)):
                pair = header + BLOCK * client + 0x10 * k
                m.write(word, m.read(pair, 0x10))
                if decode_action(m, o, entry, word, client) & 1:
                    append_action(m, actions, entry)


@lifted(0x1820E80)
def init_action(m, p, *_):
    m.write(p, bytes(0x8C))
    m.put(p + 0x88, 1, 5); m.put(p + 0x84, 4, 0x5400000)


@lifted(0x1145BD8)
def action_owner(m, o, *_):
    return m.u64(o + 0x1820)


@lifted(0x1145BE0)
def take_actions(m, o, _x1, req, *_):
    """The actions of a request ({list, header} at req) decoded into the list (0x1145e40), then rebuilt
    (0x1145c10)."""
    lst = m.u64(req)
    m.call_void(m.main + 0x1145E40, o, lst, m.u64(req + 8))
    return _tail(m, m.main + 0x1145C10, o, m.u64(req))


@lifted(0x1145C10)
def rebuild_actions(m, o, src, *_):
    """Rebuild each action of `src` (kind 1 with +0x12 set) through 0x1149638 into a local list, then
    append that list's entries back to `src`."""
    with m.frame(0x24C0) as f:
        e, lst = f + 8, f + 0x98
        m.call_void(m.main + 0x12708F4, lst)
        i = 0
        while i < m.u8(src + 0x2420):
            a = src + 8 + 0x8C * i
            if m.u32(a + 4) == 1 and m.u8(a + 0x12):
                m.call_void(m.main + 0x1146154, e + 0x60)
                m.call_void(m.main + 0x1149638, o, e, a)
                m.call_void(m.main + 0x1146164, lst, e)
            i += 1
        j = 0
        while j < m.u8(lst + 0x2420):
            m.call_void(m.main + 0x1146164, src, lst + 8 + 0x8C * j)
            j += 1


@lifted(0x12708F4)
def init_action_list(m, o, *_):
    """Constructor of the action list (vtable 0x44ee488): bytes +0x60..+0x84 of each of the 66 entries
    (0x8c bytes from +8) and the count at +0x2420 are zeroed."""
    m.put(o, 8, m.main + 0x44EE488)
    for k in range(0x42):
        m.write(o + 0x68 + 0x8C * k, bytes(0x24))
    m.put(o + 0x2420, 1, 0)


@lifted(0x187495C)
def run_17ce0ec_for(m, o, b, *_):
    if b == 0:
        return
    return _tail(m, m.main + 0x17CE0EC, o, m.vcall(b, 0x98) & 0xFFFFFFFF, 0)


@lifted(0x1148948)
def find_after(m, o, after, ident, *_):
    """The first entry (0x8c bytes from +8, count at +0x2420) past `after` whose u32 is `ident`, or 0."""
    n = m.u8(o + 0x2420)
    d = (after - o + 0x84) & 0xFFFFFFFFFFFFFFFF
    i = 0
    while True:
        if n == i:
            k = n
            break
        i += 1
        d = (d - 0x8C) & 0xFFFFFFFFFFFFFFFF
        if d == 0:
            k = i
            break
    ident &= 0xFFFFFFFF
    for j in range(k & 0xFF, n):
        e = o + 8 + 0x8C * j
        if m.u32(e) == ident:
            return e
    return 0


@lifted(0x1820EB8)
def append_entry(m, o, src, *_):
    """Copy an entry into the next free 0x8c-byte slot (from +8, count at +0x2420, at most 0x42)."""
    n = m.u8(o + 0x2420)
    if n > 0x41:
        return 0
    e = o + 0x8C * n
    m.write(e + 8, m.read(src, 0x54))
    m.put(e + 0x5C, 8, m.u64(src + 0x54))
    m.put(e + 0x64, 1, m.u8(src + 0x5C))
    m.write(e + 0x68, m.read(src + 0x60, 0x24))     # 0x1820f40: a 0x24-byte memcpy
    m.put(e + 0x8C, 8, m.u64(src + 0x84))
    m.put(o + 0x2420, 1, m.u8(o + 0x2420) + 1)
    return 1


@lifted(0x1148894)
def mark_id_entries(m, o, ident, *_):
    """For the first entry (0x8c bytes from +8) holding `ident`: set its +0x89, then +0x81 of every
    later entry holding it."""
    ident &= 0xFFFFFFFF
    for i in range(m.u8(o + 0x2420)):
        e = o + 8 + 0x8C * i
        if m.u32(e) == ident:
            m.put(e + 0x89, 1, 1)
            e = find_after(m, o, e, ident)
            while e:
                m.put(e + 0x81, 1, 1)
                e = find_after(m, o, e, ident)
            return


@lifted(0x17CE148)
def flag_battler_entry(m, o, ident, *_):
    return _tail(m, m.main + 0x17CE178, o, _main_battler(m, o, ident))


@lifted(0x17CE178)
def flag_entry_of(m, o, b, *_):
    """Flag the battler's entry in its class's row of the table at [o+0x10]+0x250."""
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    pokecon = m.u64(o + 0x10)
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(pokecon + 0x290) + 8) + 0x50), ident)
    cls = 0 if p == 0 or m.s(p, 4) >= 5 else m.u32(p)
    return _tail(m, m.main + 0x17CE1E4, m.u64(m.u64(o + 0x10) + 0x250), cls, ident)


@lifted(0x17CE1E4)
def flag_entry(m, table, row, ident, *_):
    """In row `row` (0..4, 0x60 bytes) set the flag byte (+0xc) of the first of six 16-byte entries
    from +0x10 whose u32 is `ident`."""
    row &= 0xFF
    if row > 4:
        return
    ident &= 0xFFFFFFFF
    for k in range(1, 7):
        e = table + 0x60 * row + 0x10 * k
        if m.u32(e) == ident:
            m.put(e + 0xC, 1, 1)
            return


@lifted(0x1140D40)
def run_11424b8(m, o, e, *_):
    """0x11424b8(0x1140d74([o+0x78]), an out slot, &[e+0x28])."""
    with m.frame(0x10) as p:
        m.put(p + 8, 8, m.u64(e + 0x28))
        return _tail(m, m.main + 0x11424B8, m.call(m.main + 0x1140D74, m.u64(o + 0x78)), p, p + 8)


@lifted(0x17CE0EC)
def flag_and_push_25_c7(m, o, ident, v, *_):
    """For a nonzero id: 0x17ce148([o + 0x20]), then queue 0x25 (ident) and 0xc7 (ident, v)."""
    if ident & M32 == 0:
        return
    m.call_void(m.main + 0x17CE148, m.u64(o + 0x20), ident)
    q = m.u64(o + 0x18)
    m.call_void(m.main + 0x119AFF0, q, 0x25, ident & M32)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xC7, ident & M32, v & M32)


@lifted(0x17522E0)
def flag_and_push_of(m, q, b, v, *_):
    if b == 0:
        return
    return _tail(m, m.main + 0x17CE0EC, q, m.vcall(b, 0x98) & M32, v & 0xFFFF)


@lifted(0x1752270)
def start_action(m, o, out, p, *_):
    """out = whether the id [p] is present; when it is, 0x17ce0ec(the queue, its battler's id, u16 p+4)."""
    m.put(out, 1, 0)
    v = m.call(m.main + 0x13813E4, m.call(m.main + 0x1482534, o))
    if m.call(m.main + 0x1381400, v, m.u32(p)) & 1 == 0:
        return
    b = m.call(m.main + 0x13813F4, o, m.u32(p))
    m.call_void(m.main + 0x17522E0, m.call(m.main + 0x1143584, o), b, m.u16(p + 4))
    m.put(out, 1, 1)


@lifted(0x1752230)
def start_action_of(m, o, ident, *_):
    with m.frame(0x10) as s:
        m.put(s + 8, 4, ident); m.put(s + 0xC, 2, 0)
        m.call_void(m.main + 0x1752270, m.call(m.main + 0x1752268, m.u64(o + 0x28)), s, s + 8)
        return m.u8(s)


@lifted(0x175218C)
def end_action(m, o, out, p, *_):
    b = m.call(m.main + 0x13813F4, o, m.u32(p))
    m.call_void(m.main + 0x17521D8, m.call(m.main + 0x1143584, o), b)
    m.put(out, 1, 1)


@lifted(0x1752150)
def end_action_of(m, o, ident, *_):
    with m.frame(0x10) as s:
        m.put(s + 8, 4, ident)
        m.call_void(m.main + 0x175218C, m.call(m.main + 0x1752184, m.u64(o + 0x28)), s, s + 8)
        return m.u8(s)


# 0x113ecdc: priority class (bits 22..24) by action kind 1..15 (jump table 0x3c6a4a6); kind 4 is 7
# unless the rule says otherwise, kind 8 packs to 0.
_ACTION_CLASS = {1: 1, 2: 4, 3: 5, 5: 1, 6: 6, 7: 2, 9: 1, 10: 4, 11: 4, 12: 1, 13: 2, 14: 4, 15: 4}


@lifted(0x113ECDC)
def action_order_key(m, o, out, r, *_):
    """The 32-bit order key of action r (record [r], kind +4): class bits 22..24, byte r+8 in bits 25..27,
    byte r+9 in bits 13..15, the move's 0x113ee0c value in bits 16..21 and the speed (0x1144194) in bits
    0..12; kind 8 is 0 and kind 0 0x5402000."""
    rec = m.u64(r)
    kind = m.u32(rec + 4)
    if kind == 8:
        m.put(out, 4, 0)
        return
    if kind == 0:
        m.put(out, 4, 0x5402000)
        return
    if kind == 4:
        cls = 7 if m.call(m.main + 0x113EE04, o) & M32 or m.u8(rec + 0x88) != 1 else 1
    else:
        cls = _ACTION_CLASS.get(kind, 1)
    hi = m.u8(r + 8)
    lo = m.u8(r + 9)
    ident = m.u32(m.u64(r))
    speed = 0
    if ident:
        b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), ident)
        speed = m.call(m.main + 0x1144194, m.u64(o + 0x38), b, 1) & 0x1FFF
    pr = m.call(m.main + 0x113EE0C, o, m.u64(r))
    m.put(out, 4, cls << 22 | (hi & 7) << 25 | (lo & 7) << 13 | (pr & 0x3F) << 16 | speed)


@lifted(0x113F6B4)
def note_speeds(m, o, _x, p, *_):
    """For each active entry (kind 1 at +0xc) of the 0x8c-byte rows at [p] (count +0x2420): the battler's
    event 0xf value for its move goes to its own battler (vf 0x4b0) and to queue 0x51."""
    i = 0
    while i < m.u8(m.u64(p) + 0x2420):
        e = m.u64(p) + 0x8C * i
        if m.u32(e + 0xC) == 1:
            b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), m.u32(e + 8))
            v = m.call(m.main + 0x114020C, m.u64(o + 0x38), b, m.u16(e + 0x18)) & M32
            q = m.u64(o + 0x20)
            h = m.u64(q + 0x20)
            bb = m.call(m.main + 0xF21C94, m.u64(m.u64(h + 0x10) + 0x30), m.vcall(b, 0x98) & M32)
            m.vcall_void(bb, 0x4B0, v)
            m.call_void(m.main + 0x119AFF0, m.u64(q + 0x18), 0x51, m.vcall(b, 0x98) & M32, v & 0xFF)
        i += 1


@lifted(0x113EA20)
def sort_actions(m, o, _x, p, *_):
    """Order the action rows at [p] (records at +8 + 0x8c i, count +0x2420): each gets its order key
    (0x113ecdc, at record +0x84), then a selection sort puts the largest first; equal keys swap on a
    coin flip (0x11421f0)."""
    base = m.u64(p)
    i = 0
    while i < m.u8(base + 0x2420):
        rec = base + 8 + 0x8C * i
        with m.frame(0x20) as s:
            m.put(s + 8, 8, rec); m.put(s + 0x10, 1, (m.u32(rec + 0x84) >> 25) & 7)
            ident = m.u32(rec)
            v = 1
            if ident:
                v = m.vcall(m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), ident), 0x4A8)
            m.put(s + 0x11, 1, v)
            m.call_void(m.main + 0x113ECDC, m.u64(m.u64(o + 0x78) + 0x120), s, s + 8)
            m.put(rec + 0x84, 4, m.u32(s))
        i += 1
    base = m.u64(p)
    n = m.u8(base + 0x2420)
    if n < 2:
        return
    for i in range(n - 1):
        for j in range(i + 1, n):
            cnt = m.u8(base + 0x2420)
            ri, rj = base + 8 + 0x8C * i, base + 8 + 0x8C * j
            ki = m.u32((ri if i < cnt else 0) + 0x84)
            kj = m.u32((rj if j < cnt else 0) + 0x84)
            if ki > kj:
                continue
            if ki == kj:
                if m.call(m.main + 0x11421F0, o, 2) & M32 == 0:
                    continue
                cnt = m.u8(base + 0x2420)
            if i < cnt and j < cnt:
                m.call_void(m.main + 0x113EF60, ri, rj)


@lifted(0x113EF60)
def swap_action_rows(m, a, b, *_):
    """Swap two 0x8c-byte action rows."""
    x, y = m.read(a, 0x8C), m.read(b, 0x8C)
    m.write(a, y); m.write(b, x)


@lifted(0x1143DF0)
def standing_by_speed(m, o, _x, p, *_):
    """The standing members of [p] (0x1144704), sorted fastest first (0x1143e3c)."""
    m.call_void(m.main + 0x1144704, o, m.u64(p), p)
    with m.frame(0x10) as f:
        m.put(f + 8, 8, m.u64(p))
        m.call_void(m.main + 0x1143E3C, m.u64(m.u64(o + 0x78) + 0x17E0), f, f + 8)


def _standing_by_speed(m, o, lst, pl, out):
    """Clear lst, fill it with the standing members (0x1144704 on [[o+0x78]+0x1280]) and sort them by
    speed (0x1143e3c on that object's [[+0x78]+0x17e0])."""
    _clear_members(m, lst)
    x = m.u64(m.u64(o + 0x78) + 0x1280)
    m.call_void(m.main + 0x1144704, x, lst)
    m.put(pl, 8, lst)
    m.call_void(m.main + 0x1143E3C, m.u64(m.u64(x + 0x78) + 0x17E0), out, pl)


@lifted(0x2880F28)
def action_kind_4(m, o, a, b, mv, *_):
    """0x2880f64 on 0x2880f5c([o+0x78]) with {a, b, u16 move}."""
    with m.frame(0x20) as f:
        m.put(f + 8, 8, a); m.put(f + 0x10, 8, b); m.put(f + 0x18, 2, mv)
        m.call_void(m.main + 0x2880F64, m.call(m.main + 0x2880F5C, m.u64(o + 0x78)), f, f + 8)


def _raid_action_c1(m, o, b, act, flag):
    """Under rule 0x499 bit 2: command 0xc1 (9, flag) when b is the raid member and the action's byte
    +0x28 is 9."""
    if not m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x499) >> 2 & 1:
        return
    ident = m.vcall(b, 0x98) & M32
    if _raid_member_id(m, o) == ident and m.u8(act + 0x28) == 9:
        m.call_void(m.main + 0x119AFF0, m.u64(m.u64(o + 0x20) + 0x18), 0xC1, 9, flag)


@lifted(0x11522CC)
def run_action(m, o, _x, r, *_):
    """Run the battler's chosen action [r]: the move pick 0x2d32db0 into a 0x140-byte result whose parts
    are copied into the action (sp+0x98), the move record (sp+0x148) and two 0x30-byte blocks; result 1
    runs the move (0x15784b8), result 4 goes to 0x2880f28. Then the slot record (+0xe .. +0x15,
    0x1941fb4), the bookkeeping 0x2d326e0, the pending list of [[o+0x78]+0x1360] (0x2884b70), and the
    raid command 0xc1 (9, 0 / 1) around it. The stack layout mirrors the game's frame (sp = x29 - 0x2b0):
    the copies move padding bytes too."""
    state = m.u64(o + 0x40)
    if not m.u64(state + 0x90) >> 2 & 1:
        m.put(state + 0x90, 8, m.u64(state + 0x90) | 4)
        m.call_void(m.main + 0x13DBEA4, o)
    act = m.u64(r)
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), m.u32(act))
    with m.frame(0x2C0) as sp:
        x29 = sp + 0x2B0
        m.put(sp + 0x24, 4, m.vcall(b, 0x4E8))
        m.put(sp + 0x20, 4, m.vcall(b, 0x220, 0x1A))
        _raid_action_c1(m, o, b, act, 0)
        z = lambda a, n: m.write(sp + a, bytes(n))
        z(0x155, 8); z(0x148, 0x10)
        z(0x98, 0x8F)
        m.put(sp + 0x28, 8, act); m.put(x29 - 0x10, 8, act)
        z(0x138, 8); z(0x140, 2); z(0x5C, 4); z(0x54, 8); z(0x4C, 8); z(0x128, 0x10)
        z(0x44, 8); z(0x3C, 8); z(0x34, 8)
        m.put(sp + 0x60, 8, 0x0A0A0A0A0A0A0A0A); m.put(sp + 0x67, 4, 0x0A0A0A0A)
        for a in (0x6C, 0x74, 0x7C, 0x84, 0x8C):
            z(a, 8)
        z(0x94, 4); z(0x175, 8)
        m.put(sp + 8, 8, sp + 0x6C); m.put(sp + 0x10, 8, sp + 0x34)
        z(0x168, 0x10)
        z(0x188, 0x8F)
        z(0x218, 8); z(0x220, 8); z(0x228, 8); z(0x230, 2); z(0x238, 1)
        for a in (0x23C, 0x244, 0x24C, 0x254, 0x25C):
            z(a, 8)
        z(0x264, 4)
        m.put(sp + 0x26F, 4, 0x0A0A0A0A); m.put(sp + 0x268, 8, 0x0A0A0A0A0A0A0A0A)
        for a in (0x27C, 0x284, 0x274, 0x28C, 0x294):
            z(a, 8)
        z(0x29C, 4)
        m.call_void(m.main + 0x2D32DB0, m.u64(m.u64(o + 0x78) + 0x1C40), sp + 0x160, x29 - 0x10)
        _copy(m, sp + 0x148, sp + 0x168, 0x10)
        v175, b165 = m.u64(sp + 0x175), m.u8(sp + 0x165)
        m.put(sp + 0x155, 8, v175)
        b180, code, picked = m.u8(sp + 0x180), m.u32(sp + 0x160), m.u8(sp + 0x164)
        m.put(sp + 0x18, 4, b180); m.put(sp + 0x1C, 4, b165)
        _copy(m, sp + 0x98, sp + 0x188, 0x58)
        _copy(m, sp + 0xF0, sp + 0x1E0, 0x10)
        for d, s, n in ((0xFE, 0x1EE, 8), (0x106, 0x1F6, 8), (0x10E, 0x1FE, 8), (0x114, 0x204, 8),
                        (0x11C, 0x20C, 8), (0x123, 0x213, 4), (0x136, 0x226, 8)):
            _copy(m, sp + d, sp + s, n)
        _copy(m, sp + 0x128, sp + 0x218, 0x10)
        _copy(m, sp + 0x13E, sp + 0x22E, 1)
        _copy(m, sp + 0x13F, sp + 0x22F, 2)
        _copy(m, sp + 0x141, sp + 0x231, 1)
        m.put(sp + 0x30, 1, m.u8(sp + 0x238))
        _copy(m, sp + 0x34, sp + 0x23C, 0x2C)
        m.put(sp + 0x60, 8, m.u64(sp + 0x268))
        m.put(sp + 0x67, 4, m.u32(sp + 0x26F))
        _copy(m, sp + 0x6C, sp + 0x274, 0x2C)
        flag = 0
        if code == 4:
            m.call_void(m.main + 0x2880F28, o, sp + 0x30, b, m.u16(sp + 0x148))
        elif code == 1:
            m.put(sp + 0x160, 8, b); m.put(sp + 0x168, 8, act + 0x54)
            m.put(sp + 0x170, 8, sp + 0x148); m.put(sp + 0x178, 8, sp + 0x98)
            m.put(x29 - 0xF, 1, 0)
            m.call_void(m.main + 0x15784B8, m.u64(m.u64(o + 0x78) + 0x1A80), x29 - 0x10, sp + 0x160)
            flag, picked = m.u8(x29 - 0xF), m.u8(x29 - 0x10)
        m.put(sp + 0x28, 4, picked)
        base = m.u64(m.u64(o + 0x40) + 8)
        e = base + 0xC4 * m.u8(base + 0x938)
        b180 = m.u32(sp + 0x18)
        if m.s(e + 0xA, 2) != -1:
            m.put(e + 0x10, 4, m.vcall(b, 0x98))
            m.put(e + 0xE, 2, m.u16(sp + 0x148))
            m.put(e + 0x14, 1, b180)
            if m.u16(sp + 0x148) == 0x90:
                w = 1
            else:
                cur = m.u64(m.u64(o + 0x40) + 8)
                w = int(m.u8(cur + 0xC4 * m.u8(cur + 0x938) + 0x21) == 0)
            m.put(e + 0x15, 1, w)
            if not m.u8(e + 8) and m.s(e + 0xA, 2) != -1:
                m.call_void(m.main + 0x1941FB4, m.u64(o + 0x28), e + 8, e + 0x18)
        m.put(sp + 0x17C, 1, flag)
        m.put(sp + 0x160, 8, act + 0x54); m.put(sp + 0x168, 8, b); m.put(sp + 0x170, 8, sp + 0x148)
        m.put(sp + 0x178, 1, m.u32(sp + 0x1C))
        m.put(sp + 0x17A, 1, m.u32(sp + 0x20) & 1)
        m.put(sp + 0x17B, 1, int(m.u32(sp + 0x24) != 0x20))
        m.put(sp + 0x179, 1, m.u32(sp + 0x28))
        m.put(sp + 0x17E, 2, m.u16(act + 0x10))
        m.put(sp + 0x180, 1, b180)
        m.call_void(m.main + 0x2D326E0, m.u64(m.u64(o + 0x78) + 0x1C20), x29 - 0x10, sp + 0x160)
        x21 = m.u64(m.u64(o + 0x78) + 0x1360)

        def pend():
            base = m.u64(m.u64(x21 + 0x40) + 8)
            return base + 0xC4 * m.u8(base + 0x938)

        if m.u8(pend() + 0x60):
            mv = m.u16(sp + 0x148)
            j = 0
            while True:
                e2 = pend()
                m.call_void(m.main + 0x2884B70, x21, m.u32(e2 + 0x64 + 4 * j), m.u32(e2 + 0x9C + 4 * j),
                            m.u8(e2 + 0x90 + j), mv)
                j += 1
                if j >= m.u8(pend() + 0x60):
                    break
        _raid_action_c1(m, o, b, act, 1)


# 0x11405a0's handlers by action kind u32 [act+4] (jump table 0x3c6a54a), called with (o, act).
_ACTION_KIND = {2: 0x1142180, 3: 0x11409BC, 5: 0x1141CEC, 6: 0x1140CA4, 7: 0x1140D04, 10: 0x11410E0,
                11: 0x1140D40, 12: 0x1140CD4, 13: 0x1142520}


@lifted(0x11405A0)
def run_one_action(m, o, _x, r, *_):
    """Run the action [r] once (byte +0x89 marks it): skipped without a kind or an actor, or when the
    actor is not usable (vf 0x208), at position 10, or under condition 0x1a. Vf 0x220(0x22) can hand it
    to 0x114fe20; flags +0x58 & 0x18 run 0x114cb7c; event 1 (0x1140d7c), vf 0x508(0), then the kind's
    handler (1: 0x11522cc; 4: 0x1142114, battle state 8 when it holds; 8: state 7; 14 / 15: 0x1141124
    and the rule step by byte +0x4c). Raids then run 0x1140958; kinds 1 and 2 clear the actor (vf 0x508(1),
    vf 0x4d8(0) on its party member, command 0x1e); unless the state is 8, 0x11409e4 closes it."""
    act = m.u64(r)
    if m.u8(act + 0x89):
        return
    m.put(act + 0x89, 1, 1)
    act = m.u64(r)
    if not m.u32(act + 4) or not m.u32(act):
        return
    members = m.u64(m.u64(o + 0x10) + 0x30)
    b = m.call(m.main + 0xF21C94, members, m.u32(act))
    if not m.vcall(b, 0x208) & 1:
        return
    if m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), m.vcall(b, 0x98) & M32) & 0xFF == 0xA:
        return
    if m.vcall(b, 0x4D0, 0x1A) & 1:
        return
    act = m.u64(r)
    pm = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), m.u32(act))
    if m.vcall(pm, 0x220, 0x22) & 1:
        if not (m.u32(act + 4) == 4 and m.call(m.main + 0x1821D0C, m.u64(o + 8)) & M32 == 2):
            return _tail(m, m.main + 0x114FE20, o, m.u64(r))
    a = m.u64(r)
    if m.u8(a + 0x58) & 0x18:
        m.call_void(m.main + 0x114CB7C, m.u64(o + 0x20), m.u32(a), m.u8(a + 0x5C), a + 0x60)
        a = m.u64(r)
    m.call_void(m.main + 0x1140D7C, m.u64(o + 0x38), a)
    m.vcall_void(b, 0x508, 0)
    act = m.u64(r)
    kind = m.u32(act + 4)
    state = lambda: m.u64(m.u64(o + 0x40) + 0x28)
    with m.frame(0x40) as f:
        if kind == 1:
            m.put(f + 0x18, 8, act)
            m.call_void(m.main + 0x11522CC, m.u64(m.u64(o + 0x78) + 0x680), f, f + 0x18)
        elif kind == 4:
            if m.call(m.main + 0x1142114, o, act) & 1:
                m.put(state(), 1, 8)
        elif kind == 8:
            m.put(state(), 1, 7)
        elif kind in (14, 15):
            if kind == 14:
                m.call_void(m.main + 0x1141124, o, act)
            x = m.u64(m.u64(o + 0x78) + 0x1F80)
            k = m.u8(act + 0x4C)
            if k == 2:
                m.call_void(m.main + 0x11519AC, x)
            elif k == 1:
                m.call_void(m.main + 0x114CC24, x)
        elif kind in _ACTION_KIND:
            m.call_void(m.main + _ACTION_KIND[kind], o, act)
        if m.u8(state()) != 7 and m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x499) >> 2 & 1:
            m.call_void(m.main + 0x1140958, m.call(m.main + 0x1140950, m.u64(o + 0x78)), f + 0x20, f + 0x28)
    if m.u32(m.u64(r) + 4) - 1 & M32 <= 1:
        m.vcall_void(b, 0x508, 1)
        q = m.u64(o + 0x20)
        pm = m.call(m.main + 0xF21C94, m.u64(m.u64(m.u64(q + 0x20) + 0x10) + 0x30), m.vcall(b, 0x98) & M32)
        m.vcall_void(pm, 0x4D8, 0)
        m.call_void(m.main + 0x119AFF0, m.u64(q + 0x18), 0x1E, m.vcall(b, 0x98) & M32, 0)
    if m.u8(state()) == 8:
        return
    a = m.u64(r)
    b2 = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), m.u32(a))
    m.call_void(m.main + 0x11409E4, m.u64(o + 0x38), b2, m.u32(a + 4))


@lifted(0x113F94C)
def run_action_in_slot(m, o, _x, r, *_):
    """Open a slot record (count byte +0x938 of [[o+0x40]+8], at most 11; record 0xc4 bytes: +8 0, +0xa
    0xffffffff, +0xe 0, +0x10 0, +0x14 0xa, 0x127399c on +0x18, +0x60 0x6b zero bytes), run the action [r]
    (0x11405a0), close the slot, then 0x113fa64's answer: battle state 7 when 0x114a808 holds, else 4
    when the answer is set and the state is not 1."""
    act = m.u64(r)
    base = m.u64(m.u64(o + 0x40) + 8)
    c = m.u8(base + 0x938)
    if c <= 0xA:
        m.put(base + 0x938, 1, c + 1)
        e = base + 0xC4 * ((c + 1) & 0xFF)
        m.put(e + 0xA, 4, M32); m.put(e + 8, 1, 0); m.put(e + 0xE, 2, 0); m.put(e + 0x10, 4, 0)
        m.put(e + 0x14, 2, 0xA)
        m.call_void(m.main + 0x127399C, e + 0x18)
        m.write(e + 0x60, bytes(0x6B))
    with m.frame(0x30) as f:
        m.put(f + 8, 8, act)
        m.call_void(m.main + 0x11405A0, m.u64(m.u64(o + 0x78) + 0x14E0), f + 0x10, f + 8)
        base = m.u64(m.u64(o + 0x40) + 8)
        c = m.u8(base + 0x938)
        if c:
            m.put(base + 0x938, 1, c - 1)
        m.call_void(m.main + 0x113FA64, m.u64(m.u64(o + 0x78) + 0x2A0), f + 0x18, f + 0x20)
        answer = m.u8(f + 0x18)
    over = m.call(m.main + 0x114A808, o) & 1
    p = m.u64(m.u64(o + 0x40) + 0x28)
    if over:
        return _tail(m, m.main + 0x113FA5C, p, 7)
    if answer and m.u8(p) != 1:
        return _tail(m, m.main + 0x113FA5C, p, 4)


def _next_action(m, rec):
    """The first of the record's actions (count byte +0x2420, 0x8c bytes from +8) not yet run (+0x89)."""
    for k in range(m.u8(rec + 0x2420)):
        if not m.u8(rec + 0x91 + 0x8C * k):
            return k
    return None


@lifted(0x113F7D0)
def run_actions(m, o, _x, r, *_):
    """Run the turn's actions [r] in order: sort them (0x113ea20), then repeatedly run the first not yet
    run (0x113f94c) and re-sort, until none is left or the battle state is neither 0 nor 8; in state 8
    only kind-4 actions run, the others are marked run."""
    rec = m.u64(r)
    if _next_action(m, rec) is None:
        return
    with m.frame(0x10) as f:
        def sort():
            m.put(f + 8, 8, rec)
            m.call_void(m.main + 0x113EA20, m.u64(m.u64(o + 0x78) + 0x1800), f, f + 8)
        sort()
        while m.u8(rec + 0x2420):
            k = _next_action(m, rec)
            if k is None:
                return
            if m.u8(m.u64(m.u64(o + 0x40) + 0x28)) == 8 and m.u32(rec + 0x8C * k + 0xC) != 4:
                m.put(rec + 0x91 + 0x8C * k, 1, 1)
            else:
                m.put(f + 8, 8, rec + 0x8C * k + 8)
                m.call_void(m.main + 0x113F94C, m.u64(m.u64(o + 0x78) + 0x14C0), f, f + 8)
            st = m.u8(m.u64(m.u64(o + 0x40) + 0x28))
            if st not in (0, 8):
                return
            if _next_action(m, rec) is None:
                return
            sort()


@lifted(0x11467BC)
def sort_list_by_speed(m, o, lst, *_):
    """0x1143e3c on 0x11467ec([o+0x78]) with the list."""
    with m.frame(0x10) as f:
        m.put(f + 8, 8, lst)
        m.call_void(m.main + 0x1143E3C, m.call(m.main + 0x11467EC, m.u64(o + 0x78)), f, f + 8)
