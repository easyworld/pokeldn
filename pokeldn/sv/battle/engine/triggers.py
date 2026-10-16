"""The raid's scripted triggers: a flatbuffer vector of entries, each a kind and its conditions."""

from pokeldn.sv.battle.engine import flatbuffer as fb
from pokeldn.sv.battle.engine.calls import _udiv32
from pokeldn.sv.battle.engine.containers import battler
from pokeldn.sv.battle.machine import lifted

NOT_FOUND = 0xFFFFFFFF
# Kind -> condition function taking (owner, entry, argument) (0x17f457c's jump table).
_CHECK_P3 = {1: 0x16DA624, 2: 0x2899508, 0x1E: 0x2899508, 3: 0x28996FC, 6: 0x16DA764, 7: 0x16DA764,
             8: 0x16DA764, 0xE: 0x16DA764, 0x17: 0x16DA764, 0x1B: 0x16DA764, 0x1C: 0x16DA764,
             0x1D: 0x16DA764, 0xC: 0x2899898, 0x14: 0x289959C, 0x15: 0x289959C}
_CHECK_HI = {0xF: 0x2899B20, 0x10: 0x19044E0, 0x11: 0x28999DC, 0x12: 0xFF8E80, 0x13: 0x2D3AF4C}


def _fired(m, o, i):
    return m.u64(m.u64(o + 0x10) + 8 * (i >> 6)) >> (i & 0x3F) & 1


def _in_static_list(m, b):
    """Whether the battler's list (slot 0 of the object at +0x28) holds the static at 0x46d3f08."""
    from pokeldn.sv.battle.engine.statics import static_46d3f08
    node = m.vcall(b + 0x28, 0)
    target = static_46d3f08(m)
    while node:
        if node == target:
            return True
        node = m.u64(node)
    return False


@lifted(0x17F457C)
def first_trigger(m, o, kind, arg, arg2, *_):
    """Index of the first unfired trigger entry of `kind` whose condition holds, else 0xffffffff."""
    kind &= 0xFFFFFFFF
    root = m.u64(o + 8)
    if root == 0:
        return NOT_FOUND
    count, first = fb.vector(m, root, 0)
    if count == 0:
        return NOT_FOUND
    lo, hi = arg & 0xFFFFFFFF, (arg2 >> 32) & 0xFFFFFFFF
    i = 0
    while True:
        if not _fired(m, o, i):
            entry = fb.element_table(m, first, i)
            if fb.u8(m, entry, 0) == kind:
                if _check(m, o, kind, entry, arg, arg2, lo, hi):
                    return i
        i = (i + 1) & 0xFF
        count, first = fb.vector(m, m.u64(o + 8), 0)
        if i >= count:
            return NOT_FOUND


def _check(m, o, kind, entry, arg, arg2, lo, hi):
    """Whether the entry's condition holds."""
    server = m.u64(o + 0x50)
    if kind in (0, 5, 0xB):
        return True if m.u64(m.u64(server + 0x210) + 8) == fb.u32(m, entry, 1) else None
    if kind == 10:
        return True
    if kind in _CHECK_P3:
        return True if m.call(m.main + _CHECK_P3[kind], o, entry, lo) & 1 else None
    if kind == 4:
        return True if m.call(m.main + 0x181F184, o, entry, lo, (arg >> 32) & 0xFFFFFFFF) & 1 else None
    if kind == 9:
        return True if m.call(m.main + 0x2899834, o, entry, lo, (arg >> 48) & 0xFFFF) & 1 else None
    if kind == 0xD:
        return True if m.call(m.main + 0x2899978, o, entry, lo, arg2 & 0xFFFFFFFF) & 1 else None
    if kind in _CHECK_HI:
        return True if m.call(m.main + _CHECK_HI[kind], o, entry, hi) & 1 else None
    if kind in (0x16, 0x20):
        if m.call(m.main + 0x16DA764, o, entry, lo) & 1 == 0:
            return None
        a, c = fb.u32(m, entry, 2), fb.u32(m, entry, 3)
        b = battler(m, m.u64(server + 0x30), lo)
        if b and _in_static_list(m, b) and m.u16(b + 0x710) == a & 0xFFFF:
            if c > 0xFE or m.u16(b + 0x718) == c & 0xFFFF:
                return True
        return None
    if kind == 0x18:
        if fb.s32(m, entry, 1) != (arg2 >> 32) - (1 << 32 if (arg2 >> 63) & 1 else 0):
            return None
        from pokeldn.sv.battle.machine import UnliftedCall
        raise UnliftedCall("trigger kind 0x18")
    if kind == 0x19:
        parties = m.u64(server + 0x30)
        boss = m.u64(parties + 0x60)
        if m.u8(parties + 0x90) == 0 or boss == 0:
            return None
        if m.vcall(boss, 0x90, fb.u32(m, entry, 1), fb.u32(m, entry, 2)) & 1 == 0:
            return None
        share = (fb.s32(m, entry, 3) * (m.vcall(boss, 0x110) & 0xFFFF)) & 0xFFFFFFFF
        limit = share // 100 + (1 if share % 100 > 0x31 else 0)
        return True if m.vcall(boss, 0x108) & 0xFFFF <= limit else None
    if kind == 0x1A:
        want = fb.s32(m, entry, 1)
        p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(server + 0x290) + 8) + 0x50), lo)
        got = 0 if p == 0 else m.s(p, 4)
        got = 0 if got > 4 else got
        if got != want:
            return None
        if fb.u32(m, entry, 2) == 0:
            return True
        b = battler(m, m.u64(server + 0x30), lo)
        if b and _in_static_list(m, b):
            if m.call(m.main + 0x1FFEBAC, m.u64(server + 0x290), b) & 1:
                if fb.s32(m, entry, 3) == m.s(m.u64(server + 0x210) + 0x28, 4):
                    return True
        return None
    if kind == 0x1F:
        if m.call(m.main + 0x16DA764, o, entry, lo) & 1 == 0:
            return None
        parties = m.u64(server + 0x30)
        if m.u16(entry - m.s(entry, 4)) < 7:
            limit, plist = 0, parties + 0x28
        else:
            client = fb.u32(m, entry, 1)
            limit = fb.u32(m, entry, 2)
            plist = parties + 0x28 + 0x38 * client if client < 5 else 0
        n = m.u8(plist + 0x30)
        able = sum(m.vcall(m.u64(plist + 8 * k), 0x208) & 1 for k in range(n)) & 0xFF
        return True if able <= limit else None
    return None


@lifted(0x121BDB0)
def fire_trigger(m, o, fired, event, *_):
    """Fire the first trigger matching `event` (kind u32, then argument fields) and queue command 0xb6;
    `*fired` is 1 when a kind 0xf..0x13 or 0x18 trigger with an argument ran its action."""
    m.put(fired, 1, 0)
    server = m.u64(o + 0x10)
    kind = m.u32(event)
    if m.call(m.main + 0x114A808, o) & 1 == 0:
        if kind == 0:
            for i in range(5):
                if m.u64(m.u64(m.u64(o + 0x10) + 0x210) + 0xA8 + 8 * i):
                    m.call_void(m.main + 0x172384C, m.u64(o + 0x20), 3, i)
            kind = m.u32(event)
    elif kind not in (6, 8):
        return
    a, b, c = m.u16(event + 8), m.u8(event + 0xA), m.u16(event + 0xC)
    if kind == 0x1A:
        p = m.call(m.main + 0xFA0028, m.u64(server + 0x30), 0, 0)
        ident = m.vcall(p, 0x98) & 0xFFFFFFFF
    else:
        ident = m.u32(event + 4)
    if ident == 0:
        arg2 = c | 0x500000000
    else:
        p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(server + 0x290) + 8) + 0x50), ident)
        v = m.s(p, 4) if p else 0
        arg2 = ((v if v < 5 else 0) & 0xFFFFFFFF) << 32 | c
    i = m.call(m.main + 0x17F457C, m.u64(server + 0x1D0), kind, a << 32 | b << 48 | ident, arg2) & 0xFFFFFFFF
    if i >> 31:
        return
    m.call_void(m.main + 0x1345BC4, m.u64(o + 0x20), i, kind)
    m.call_void(m.main + 0x119AFF0, m.u64(m.u64(o + 0x20) + 0x18), 0xB6, i & 0xFF, kind & 0xFF)
    kind = m.u32(event)
    if m.u32(event + 4) == 0 or kind < 0xF or (kind >= 0x14 and kind != 0x18):
        return
    triggers = m.u64(m.u64(o + 0x10) + 0x1D0)
    action = m.call(m.main + 0x2D3AFBC, triggers, i) & 0xFFFFFFFF
    if action:
        target = m.call(m.main + 0x2D3B030, triggers, i) & 0xFFFFFFFF
        if target == 0 or target != m.u32(event + 4):
            m.call_void(m.main + 0x17D5C04, o, action)
        else:
            who = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), target)
            m.call_void(m.main + 0x18672A0, o, action, target, who)
        if m.u32(event) == 2:
            m.call_void(m.main + 0x119AFF0, m.u64(m.u64(o + 0x20) + 0x18), 0x2D, 2)
    m.put(fired, 1, 1)
    return


@lifted(0x121BC6C)
def fire_for_client(m, o, kind, client, *_):
    """Fire trigger `kind` (0x121bdb0) for the first able member (vf 0x208) of client slot `client`;
    1 when its action ran."""
    client &= 0xFFFFFFFF
    setup = m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8)
    if m.call(m.main + 0xE7E2A0, m.u32(setup + 0x36C), m.u8(setup + 0x370), client & 0xFF) & 1 == 0:
        return 0
    setup = m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8)
    n = m.call(m.main + 0xFF9128, m.u32(setup + 0x36C), m.u8(setup + 0x370), client & 0xFF) & 0xFFFFFFFF
    if n == 0 or n >= 0x80000000:
        return 0
    i = 0
    while True:
        plist = m.u64(m.u64(o + 0x10) + 0x30) + 0x38 * client + 0x28 if client <= 4 else 0
        if i & 0xFF < m.u8(plist + 0x30):
            b = m.u64(plist + 8 * (i & 0xFF))
            if b and m.vcall(b, 0x208) & 1:
                with m.frame(0x18) as f:
                    fired, event = f, f + 8
                    m.put(event + 8, 2, 0); m.put(event + 0xA, 1, 0); m.put(event + 0xC, 2, 0)
                    m.put(event, 4, kind); m.put(event + 4, 4, 0)
                    m.put(event + 4, 4, m.vcall(b, 0x98))
                    m.put(fired, 1, 0)
                    m.call_void(m.main + 0x121BDB0, m.u64(m.u64(o + 0x78) + 0x1D40), fired, event)
                    return int(m.u8(fired) != 0)
        i = (i + 1) & 0xFFFFFFFF
        if i == n:
            return 0


@lifted(0x287FE5C)
def fire_event(m, o, kind, ident, *_):
    """Fire trigger (kind, id) through 0x121bdb0 on the server's trigger owner."""
    with m.frame(0x18) as f:
        fired, event = f, f + 8
        m.put(event + 8, 2, 0); m.put(event + 0xA, 1, 0); m.put(event + 0xC, 2, 0)
        m.put(event, 4, kind); m.put(event + 4, 4, ident)
        m.put(fired, 1, 0)
        x = m.call(m.main + 0x1361214, o, kind, ident)
        x = m.call(m.main + 0x114E520, x, kind, ident)
        m.call_void(m.main + 0x121BDB0, x, fired, event)


def _push_trigger(m, o, kind, value):
    """Append (kind u8 at +0x5c, value u32 at +0x60) to the four-entry list counted at +0x7c."""
    n = m.u32(o + 0x7C)
    if n > 3:
        return
    m.put(o + 0x5C + 8 * n, 1, kind); m.put(o + 0x60 + 8 * n, 4, value)
    m.put(o + 0x7C, 4, m.u32(o + 0x7C) + 1)


def _hp_percent(m, o):
    """100 * vf 0x108 / vf 0x110 of the raid battler (0xf6fc68), as the game's u32 udiv computes it."""
    a = m.vcall(m.call(m.main + 0xF6FC68, m.u64(m.u64(o + 8) + 0x310)), 0x108) & 0xFFFF
    c = m.vcall(m.call(m.main + 0xF6FC68, m.u64(m.u64(o + 8) + 0x310)), 0x110) & 0xFFFF
    return _udiv32(a * 100, c)


def _turn_percent(m, o, p, thresh):
    """Whether 100 * 0xf91070(p, limit, ...) / limit stays at or below `thresh` (limit u16 at
    [[[o+8]+0x290]+0x10]+0x8a; a zero limit passes)."""
    s = m.u64(m.u64(o + 8) + 0x290)
    d = m.u16(m.u64(s + 0x10) + 0x8A)
    if d == 0:
        return True
    x = m.call(m.main + 0xF91070, p, d, m.s(m.u64(m.u64(s + 8) + 0x1B0) + 8, 2) & 0xFFFFFFFFFFFFFFFF)
    d = m.u16(m.u64(s + 0x10) + 0x8A)
    q = (x * 100 & 0xFFFFFFFFFFFFFFFF) // d if d else 0
    return q & 0xFFFFFFFF <= thresh


@lifted(0xF6F87C)
def raid_start_trigger(m, o, p, *_):
    """Queue the raid's opening trigger: kind 1 by turn (p set, threshold +0x14) or HP (threshold +0x12)
    before the record starts; kind 2 by 0xf70010 against +0x18 once it runs. 1 when one fired."""
    rec = m.u64(m.u64(o + 8) + 0x310)
    st = m.u32(rec + 0x70)
    if st:
        if p or st != 1:
            return 0
        t = m.u16(o + 0x18)
        if t == 0 or m.call(m.main + 0xF6FC68, rec) == 0:
            return 0
        c = m.vcall(m.call(m.main + 0xF6FC68, m.u64(m.u64(o + 8) + 0x310)), 0x110) & 0xFFFF
        a = m.call(m.main + 0xF70010, m.u64(m.u64(o + 8) + 0x310)) & 0xFFFFFFFF
        if _udiv32(a * 100, c) < m.u16(o + 0x18):
            return 0
        _push_trigger(m, o, 2, 1)
        return 1
    if m.u8(rec + 0x8D):
        return 0
    if p:
        t = m.u16(o + 0x14)
        if t == 0 or not _turn_percent(m, o, p, t):
            return 0
        v = m.call(m.main + 0xF70AF0, p, m.u16(m.u64(o) + 0x8A))
        _push_trigger(m, o, 1, v & 0xFFFFFFFF)
        return 1
    t = m.u16(o + 0x12)
    if t == 0 or m.call(m.main + 0xF6FC68, rec) == 0:
        return 0
    if _hp_percent(m, o) > m.u16(o + 0x12):
        return 0
    _push_trigger(m, o, 1, 0)
    return 1


@lifted(0xF6FA5C)
def raid_triggers(m, o, p, *_):
    """Queue kind-4 triggers for each of the six entries at +0x24 (kind u16, mode u16, threshold u16)
    not yet fired (record +0x86 + i): mode 1 by turn when p is set, mode 2 by HP otherwise; kind 3
    skips a raid battler under condition 0x1a or 0x17 or with vf 0x230 of 2 or 3. 1 when any fired."""
    count = 0
    for i in range(6):
        e = o + 0x24 + 8 * i
        if m.u16(e) == 0 or m.u16(e + 2) == 0:
            continue
        rec = m.u64(m.u64(o + 8) + 0x310)
        if m.u8(rec + 0x86 + i):
            continue
        if m.u16(e) == 3:
            b = m.call(m.main + 0xF6FC68, rec)
            if m.vcall(b, 0x220, 0x1A) & 1 or m.vcall(b, 0x220, 0x17) & 1:
                continue
            if m.vcall(b, 0x230) & 0xFFFF in (2, 3):
                continue
        mode = m.u16(e + 2)
        if p:
            if mode != 1 or not _turn_percent(m, o, p, m.u16(e + 4)):
                continue
        else:
            if mode != 2 or m.call(m.main + 0xF6FC68, m.u64(m.u64(o + 8) + 0x310)) == 0:
                continue
            if _hp_percent(m, o) > m.u16(e + 4):
                continue
        _push_trigger(m, o, 4, i)
        count += 1
    return int(count > 0)


@lifted(0x121B9B4)
def any_trigger_fired(m, o, out, flag, *_):
    """*out = 1 when a trigger of kind 0xf, 0x18, 0x12, 0x10 or 0x11 (then 0x13 when *flag is set)
    fires for any client slot 0..4 (0x121bc6c), stopping at the first."""
    for kind in (0xF, 0x18, 0x12, 0x10, 0x11, 0x13):
        if kind == 0x13 and m.u8(flag) == 0:
            break
        for c in range(5):
            if m.call(m.main + 0x121BC6C, o, kind, c) & 1:
                m.put(out, 1, 1)
                return
    m.put(out, 1, 0)


@lifted(0xF70010)
def remaining_90(m, o, *_):
    if m.u32(o + 0x70) != 1:
        return 0
    n = m.u32(o + 0x90)
    v = m.vcall(m.call(m.main + 0xF6FC68, o), 0x108) & 0xFFFF
    if n <= v:
        return 0
    n = m.u32(o + 0x90)
    return (n - (m.vcall(m.call(m.main + 0xF6FC68, o), 0x108) & 0xFFFF)) & 0xFFFFFFFF


@lifted(0xF6DD84)
def queue_low_hp(m, o, b, *_):
    """With fewer than four entries queued (+0x7c), queue a kind-3 entry (+0x5c + 8n) for a battler
    whose share (0xf91070, in percent of [[o+8]+0x290]+0x10 +0x8a) is at most 10, then OR in the
    0xf6f87c, 0xf6fa5c and 0xf6de7c checks."""
    if m.u32(o + 0x7C) > 3:
        return 0
    f = m.call(m.main + 0xF6F87C, o, b) & 1
    if b and m.u8(m.u64(m.u64(o + 8) + 0x310) + 0x8D) == 0:
        pc = m.u64(m.u64(o + 8) + 0x290)
        s = m.u16(m.u64(pc + 0x10) + 0x8A)
        low = True
        if s:
            r = m.call(m.main + 0xF91070, b, s, m.s(m.u64(m.u64(pc + 8) + 0x1B0) + 8, 2) & 0xFFFFFFFFFFFFFFFF)
            d = m.u16(m.u64(pc + 0x10) + 0x8A)
            q = ((r * 100) & 0xFFFFFFFFFFFFFFFF) // d if d else 0
            low = q & 0xFFFFFFFF <= 10
        if low:
            f = 1
            n = m.u32(o + 0x7C)
            if n <= 3:
                m.put(o + 8 * n + 0x5C, 1, 3)
                m.put(o + 8 * n + 0x60, 4, 1)
                m.put(o + 0x7C, 4, m.u32(o + 0x7C) + 1)
    a = m.call(m.main + 0xF6FA5C, o, b)
    c = m.call(m.main + 0xF6DE7C, o, b)
    return (c | a | f) & 1


@lifted(0x1145240)
def triggers_after_turn(m, o, *_):
    """0x121b9b4 on [[o+0x78]+0x1f60] with flag 0."""
    with m.frame(0x10) as f:
        m.put(f + 8, 1, 0)
        m.call_void(m.main + 0x121B9B4, m.call(m.main + 0x2888998, m.u64(o + 0x78)), f, f + 8)


@lifted(0x114E4E0)
def trigger_kind(m, o, kind, ident, *_):
    """Trigger 0x121bdb0 (on [[o+0x78]+0x1d40]) with {kind, ident, 0, 0, 0}."""
    with m.frame(0x20) as f:
        m.put(f + 0x18, 2, 0); m.put(f + 0x1A, 1, 0); m.put(f + 0x1C, 2, 0)
        m.put(f + 0x10, 4, kind); m.put(f + 0x14, 4, ident)
        m.put(f + 8, 1, 0)
        m.call_void(m.main + 0x121BDB0, m.call(m.main + 0x114E520, m.call(m.main + 0x1361214, o)), f + 8, f + 0x10)
