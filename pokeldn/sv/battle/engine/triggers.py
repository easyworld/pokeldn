"""The raid's scripted triggers: a flatbuffer vector of entries, each a kind and its conditions."""

from pokeldn.sv.battle.engine import flatbuffer as fb
from pokeldn.sv.battle.engine.containers import battler
from pokeldn.sv.battle.engine.flow import party
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
    from pokeldn.sv.battle.engine.getters import static_46d3f08
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
