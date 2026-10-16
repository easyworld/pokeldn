"""Stat stages and stat changes: the stage bytes, the checks before a change, the change itself and its
messages."""

from pokeldn.sv.battle.engine.calls import M32, _need, _s32, _tail, m_s32
from pokeldn.sv.battle.engine.slots import _in_play
from pokeldn.sv.battle.machine import lifted


@lifted(0x2899E30)
def field_3f4(m, o, k, *_):
    """Tail call of 0x177a19c on o+0x3f4: field k (0 the u16, 1..5 the bytes at +2..+6), 10 past them."""
    k &= 0xFF
    p = o + 0x3F4
    if k == 0:
        return m.u16(p)
    return m.u8(p + 1 + k) if k <= 5 else 10


@lifted(0x171CAC8)
def set_field_3f4(m, p, k, v, *_):
    """Field k of the 0x177a19c record: 0 the u16 at +0, 1..5 the bytes at +2..+6."""
    k &= 0xFF
    if k == 0:
        m.put(p, 2, v)
    elif k <= 5:
        m.put(p + 1 + k, 1, v)


@lifted(0x2D3D518)
def take_stage(m, b, stat, n, *_):
    """Take up to n (u8) from the positive stage byte of stat 1..7 (+0x414..+0x41a); returns what was
    taken (n itself, all 32 bits, when the stage covers it)."""
    k = (stat - 1) & 0xFFFFFFFF
    if k > 6:
        return 0
    p = b + 0x414 + k
    v = m.s(p, 1)
    if v < 1:
        return 0
    v &= 0xFF
    r = v if v < n & 0xFF else n & 0xFFFFFFFF
    m.put(p, 1, v - r)
    return r


@lifted(0x2D3CEA0)
def stage_limit_call(m, b, stat, *_):
    """Tail call of vf 0xb8 when the stage that `stat` 8..11 reads is at its limit, else vf 0xb0 (with
    `stat`): 8 reads +0x414 (limit above 5), 10 +0x416 (6 or more), 9 and 11 read +0x415 or +0x417 (above
    6), swapped when the entry at +0x700 has +0xb8 set."""
    e = m.u64(b + 0x700)
    k = (stat - 8) & 0xFFFFFFFF
    swap = e != 0 and m.u32(e + 0xB8) != 0
    slot = 0xB0
    if k == 0:
        slot = 0xB8 if not m.s(b + 0x414, 1) > 5 else 0xB0
    elif k == 2:
        slot = 0xB8 if not m.s(b + 0x416, 1) >= 6 else 0xB0
    elif k in (1, 3):
        off = 0x415 if (k == 1) != swap else 0x417
        slot = 0xB8 if not m.s(b + off, 1) <= 6 else 0xB0
    return _tail(m, m.u64(m.u64(b) + slot), b, stat)


@lifted(0x2899CEC)
def set_field_3f4_hp(m, b, k, v, *_):
    """Set field k of the record at +0x3f4 (0x171cac8). For field 0, the max HP scale: the new max
    (vf 0x70 of [b+0x48] times the u16 at +0x3f4, over 10) goes to +0x58, and the HP follows: raised by
    the gain (vf 0x2e8) or cut down to the new max (vf 0x2e0)."""
    set_field_3f4(m, b + 0x3F4, k, v)
    if k & 0xFF:
        return
    hp = m.vcall(b, 0x108) & 0xFFFFFFFF
    mx = m.vcall(b, 0x110) & 0xFFFFFFFF
    r = m.vcall(m.u64(b + 0x48), 0x70, 0) & 0xFFFF
    nm = ((r * m.u16(b + 0x3F4)) & 0xFFFFFFFF) // 10
    m.put(b + 0x58, 2, nm)
    if mx & 0xFFFF < nm & 0xFFFF:
        m.vcall_void(b, 0x2E8, (nm - mx) & 0xFFFFFFFF)
    if mx & 0xFFFF <= nm & 0xFFFF or hp & 0xFFFF <= nm & 0xFFFF:
        return
    return _tail(m, m.u64(m.u64(b) + 0x2E0), b, (hp - nm) & 0xFFFFFFFF)


@lifted(0x2899FE0)
def cap_seven_at_6(m, p, *_):
    """Lower each of the seven signed bytes at p above 6 to 6; 1 when any was lowered."""
    hit = 0
    for k in range(7):
        if m.s(p + k, 1) >= 7:
            m.put(p + k, 1, 6)
            hit = 1
    return hit


# Stage kinds 1..7 -> the stage bytes at +0x414..+0x41a.
def _stage_byte(kind):
    kind &= 0xFFFFFFFF
    return 0x413 + kind if 1 <= kind <= 7 else None


@lifted(0x2D3D2D0)
def stage_can_move(m, o, kind, up, *_):
    """Whether the signed stage byte can still rise (up > 0: below 12) or fall (above 0)."""
    off = _stage_byte(kind)
    v = m.s(o + off, 1) if off else 0
    return int(v < 0xC) if m_s32(up) > 0 else int(v > 0)


@lifted(0x2D3D48C)
def stage_raise(m, o, kind, n, *_):
    """Raise a stage byte by n (u8), capped at 12; returns the amount added."""
    off = _stage_byte(kind)
    if not off:
        return 0
    v = m.s(o + off, 1)
    if v > 0xB:
        return 0
    r = (0xC - v) if v + (n & 0xFF) > 0xC else n
    r &= 0xFFFFFFFF
    m.put(o + off, 1, r + v)
    return r


@lifted(0x171CA78)
def add_to_field_3f4(m, b, k, delta, *_):
    """Field k of the record at b+0x3f4 = vf 0x1d0(k, delta) + delta, then refresh the derived stat."""
    cur = m.vcall(b, 0x1D0, k, delta)
    m.call_void(m.main + 0x171CAC8, b + 0x3F4, k & 0xFFFFFFFF, (cur + delta) & 0xFFFFFFFF)
    return _tail(m, m.main + 0x171CB20, b, k & 0xFFFFFFFF)


@lifted(0x171CB20)
def refresh_stat(m, b, k, *_):
    """Stat k (1..5): u16 at b+0x3fe+2k = [b+0x48]'s vf 0x70(k) * byte b+0x3f5+k / 10 (jump table 0x3c6b49a)."""
    k &= 0xFF
    if not 1 <= k <= 5:
        return
    v = m.vcall(m.u64(b + 0x48), 0x70, k) & 0xFFFF
    m.put(b + 0x3FE + 2 * k, 2, (v * m.u8(b + 0x3F5 + k) & 0xFFFFFFFF) // 10)


# Stat stage multipliers (numerator, denominator) for stages 0..12, the table at 0x3c69d73.
_STAGE = ((2, 8), (2, 7), (2, 6), (2, 5), (2, 4), (2, 3), (2, 2), (3, 2), (4, 2), (5, 2), (6, 2), (7, 2), (8, 2))
# Stat id -> (getter slot, stage byte) for the staged stats (jump tables 0x3c6b49f / 0x3c6b4ae).
_STAGED = {8: (0xC0, 0x414), 9: (0xC8, 0x415), 10: (0xD0, 0x416), 11: (0xD8, 0x417), 12: (0xE0, 0x418)}


@lifted(0x2D3B894)
def stat_value(m, b, which, *_):
    """Stat `which`: 1..7 the signed stage bytes +0x414..+0x41a, 8..12 a stat (vf 0xc0..0xe0) times
    its stage, 13 / 14 the u16 at +0x5a / +0x58, 15 the byte at +0x62. With a rule object (+0x700)
    whose +0xb8 is set, 9 and 11 trade places."""
    which &= 0xFFFFFFFF
    if not 1 <= which <= 15:
        return 0
    if which <= 7:
        return (((m.u8(b + 0x413 + which) ^ 0x80) - 0x80) & 0xFFFFFFFF)
    if which == 13:
        return m.u16(b + 0x5A)
    if which == 14:
        return m.u16(b + 0x58)
    if which == 15:
        return m.u8(b + 0x62)
    rule = m.u64(b + 0x700)
    if rule and which in (9, 11) and m.u32(rule + 0xB8):
        which = 20 - which
    slot, stage = _STAGED[which]
    v = m.vcall(b, slot) & 0xFFFFFFFF
    s = m.u8(b + stage)
    if s <= 12:
        num, den = _STAGE[s]
        v = ((v * num) & 0xFFFF) // den
    return v & 0xFFFF


# Message ids for a stat change of stat k + 1 (k 0..6), by the result r of the change (r < 2, r == 2,
# r > 2): words +4, +8, +0xc of the 16-byte rows at 0x3c6a6ec (raised), 0x3c6a75c (raised, with a
# cause) and 0x3c6a804 (lowered).
_RAISED = tuple((11 + k, 18 + k, 25 + k) for k in range(7))
_RAISED_BY = tuple((303 + k, 310 + k, 317 + k) for k in range(7))
_LOWERED = tuple((32 + k, 39 + k, 46 + k) for k in range(7))


@lifted(0x13818F8)
def stat_change_messages(m, o, who, b, stat, amount, cause, show, quiet, *_):
    """Change stat `stat` of battler b by the signed `amount` (vf 0x370 up, vf 0x378 down; stat 8 goes to
    0x288db34) and queue its messages: 0xc / 0xd and, unless quiet is 2, 0x92 / 0x93; with `show`,
    message 0xcb (who, the text id, b, cause or the stat)."""
    s = stat & 0xFF
    amount = amount & 0xFFFFFFFF
    amount = amount - (1 << 32) if amount >> 31 else amount
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    q = (quiet & 0xFF) == 2
    if s == 8:
        if amount < 1:
            return
        m.call_void(m.main + 0x288DB34, o, m.vcall(b, 0x98) & 0xFFFFFFFF, amount & 0xFFFFFFFF)
        if not q:
            m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0x92, ident, 8, amount & 0xFF)
        if show & 1 == 0:
            return
        i2 = m.vcall(b, 0x98) & 0xFFFFFFFF
        return _tail(m, m.main + 0x157EBC0, m.u64(o + 0x18), 0xCB, who & 0xFFFFFFFF, 0x150, i2, 0xFFFF0000)
    up = amount >= 1
    if up:
        r = m.vcall(b, 0x370, s, amount & 0xFFFFFFFF) & 0xFF
    else:
        r = m.vcall(b, 0x378, s, -amount & 0xFFFFFFFF) & 0xFF
    m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0xC if up else 0xD, ident, s, r)
    if not q:
        m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0x92 if up else 0x93, ident, s, r)
    if show & 1 == 0:
        return
    k = (stat - 1) & 0xFF
    if k > 6:
        return
    col = 1 if r == 2 else (2 if r > 2 else 0)
    if not up:
        extra = (stat & 0xFFFFFFFF,)
        text = _LOWERED[k][col]
    elif cause & 0xFFFF:
        extra = (cause & 0xFFFF,)
        text = _RAISED_BY[k][col]
    else:
        extra = ()
        text = _RAISED[k][col]
    return _tail(m, m.main + 0x157EBC0, m.u64(o + 0x18), 0xCB, who & 0xFFFFFFFF, text, ident, *extra,
                 0xFFFF0000)


@lifted(0x2899DE0)
def set_stat_multiplier(m, b, which, value, *_):
    """Battler vf 0x1c8: store vf 0x1d0 - value as multiplier `which` of the block at +0x3f4 (0x171cac8),
    then recompute that stat (0x171cb20)."""
    _need(m, m.main + 0x171CAC8)
    _need(m, m.main + 0x171CB20)
    v = m.vcall(b, 0x1D0, which, value)  # x1, x2 pass through to the getter
    m.call_void(m.main + 0x171CAC8, b + 0x3F4, which & 0xFFFFFFFF, (v - value) & 0xFFFFFFFF)
    return _tail(m, m.main + 0x171CB20, b, which & 0xFFFFFFFF)


@lifted(0x2883ECC)
def any_stage_blocked(m, o, r, *_):
    """With r+0x40 set and a user: whether any standing target (ids r+8, count r+4) has vf 0x270(stat
    r+0x34, amount r+0x35) true."""
    if not m.u8(r + 0x40) or m.u32(r) == 0:
        return 0
    if m.call(m.main + 0x13813F4, o, m.u32(r)) == 0:
        return 0
    stat = m.u8(r + 0x34)
    amount = m.s(r + 0x35, 1) & M32
    for i in range(m.u8(r + 4)):
        b = _in_play(m, o, m.u32(r + 8 + 4 * i))
        if b == 0 or m.vcall(b, 0x200) & 1:
            continue
        if m.vcall(b, 0x270, stat, amount) & 1:
            return 1
    return 0


@lifted(0x2883F94)
def change_stages(m, o, r, *_):
    """Change stat r+0x34 by r+0x35 on each standing target (ids r+8, count r+4) through 0x1380c5c;
    without r+0x47 each success also sends the text r+0x4c. Returns whether any changed."""
    _need(m, m.main + 0x1382688)
    keep = m.u8(r + 0x47)
    text = r + 0x4C if keep else 0
    any_ = 0
    for i in range(m.u8(r + 4)):
        b = _in_play(m, o, m.u32(r + 8 + 4 * i))
        if b == 0 or m.vcall(b, 0x200) & 1:
            continue
        if m.u8(r + 0x49):
            flag = 1
        elif m.u32(r):
            u = m.call(m.main + 0x13813F4, o, m.u32(r))
            flag = m.call(m.main + 0x1382688, m.call(m.main + 0x1146E90, o), u, b, 0) & 1
        else:
            flag = 0
        with m.frame(0x50) as a:
            m.write(a, bytes(0x48))
            m.put(a, 4, m.u32(r)); m.put(a + 8, 8, b); m.put(a + 0x10, 1, m.u8(r + 0x34))
            m.put(a + 0x14, 4, m.s(r + 0x35, 1)); m.put(a + 0x18, 1, m.u8(r + 0x36))
            m.put(a + 0x1A, 2, m.u16(r + 0x38)); m.put(a + 0x1C, 4, m.u32(r + 0x3C))
            m.put(a + 0x20, 1, m.u8(r + 0x45)); m.put(a + 0x21, 1, flag)
            m.put(a + 0x30, 1, m.u8(r + 0x44) ^ 1); m.put(a + 0x38, 8, text); m.put(a + 0x40, 1, m.u8(r + 0x48))
            out = a + 0x48
            m.call_void(m.main + 0x1380C5C, m.call(m.main + 0x18675D8, m.call(m.main + 0x1361214, o)), out, a)
            done = m.u8(out)
        if keep:
            any_ |= int(done != 0)
        elif done:
            m.call_void(m.main + 0x114B0AC, m.call(m.main + 0x1143584, o), m.u32(r), r + 0x4C)
            any_ = 1
    return any_


@lifted(0x1151258)
def stage_command(m, o, out, r, *_):
    """out (byte) = whether the stat-stage command r changed anything; a blocked change still starts and
    ends the user's action."""
    _need(m, m.main + 0x1382688); _need(m, m.main + 0x1381580)
    if m.call(m.main + 0x114A808, o) & 1 and m.call(m.main + 0x13603FC, o) & 1:
        m.put(out, 1, 0)
        return
    b = m.call(m.main + 0x13813F4, o, m.u32(r)) if m.u32(r) else 0
    if m.call(m.main + 0x2883ECC, o, r) & 1 == 0:
        m.put(out, 1, m.call(m.main + 0x2883F94, o, r) & 1)
        return
    m.call_void(m.main + 0x17522E0, m.call(m.main + 0x1143584, o), b, m.u16(r + 0x42))
    m.put(out, 1, m.call(m.main + 0x2883F94, o, r) & 1)
    return _tail(m, m.main + 0x17521D8, m.call(m.main + 0x1143584, o), b)


@lifted(0x283E270)
def stage_command_of(m, o, r, *_):
    with m.frame(0x10) as out:
        m.put(out, 1, 0)
        m.call_void(m.main + 0x1151258, m.call(m.main + 0x283E2A8, m.u64(o + 0x28)), out, r)
        return m.u8(out)


@lifted(0x138155C)
def note_result(m, rec, v, *_):
    """Append v to the result log at rec (five u32, count +0x14) when it records (+0x18)."""
    if not m.u8(rec + 0x18):
        return
    n = m.u32(rec + 0x14)
    if n > 4:
        return
    m.put(rec + 0x14, 4, n + 1)
    m.put(rec + 4 * n, 4, v)


@lifted(0x138112C)
def stage_change_allowed(m, o, out, r, *_):
    """out (byte) = whether battler [r+4] may take stat change (stat r+8, amount r+0x14 / 0x1381580);
    a refusal shows its message when r+0x18 is set and logs 2, 3 or 4 to the result log [r+0x20]."""
    _need(m, m.main + 0x1381580)
    b = m.call(m.main + 0x13813F4, o, m.u32(r + 4))
    show = m.u8(r + 0x18)
    rec = m.u64(r + 0x20)
    ok = 0

    def refused(code):
        m.put(out, 1, ok)
        if rec:
            return _tail(m, m.main + 0x138155C, rec, code)

    if m.call(m.main + 0x114A808, o) & 1 and m.call(m.main + 0x13603FC, o) & 1:
        m.put(out, 1, 0)
        return
    v = m.call(m.main + 0x13813E4, m.call(m.main + 0x1482534, o))
    if m.call(m.main + 0x1381400, v, m.u32(r + 4)) & 1 == 0:
        m.put(out, 1, 0)
        return
    side = m.call(m.main + 0x13813EC, m.call(m.main + 0x1482534, o))
    if m.call(m.main + 0x1381540, side) & 1:
        side = m.call(m.main + 0x13813EC, m.call(m.main + 0x1482534, o))
        if m.call(m.main + 0x138423C, side, m.u32(r + 4)) & 0xFF == 0:
            if show:
                m.call_void(m.main + 0x1536F5C, m.call(m.main + 0x1143584, o), m.u32(r), b, 0x48)
                m.put(m.call(m.main + 0x139B698, o) + 0xC0, 1, 1)
            return refused(4)
    n = _s32(m.call(m.main + 0x1381580, m.call(m.main + 0x1146E90, o), b, m.u8(r + 8), m.u32(r),
                    m.u16(r + 0x12), m.u32(r + 0xC)))
    k = m.u8(r + 8)
    if k == 8:
        v = m.vcall(b, 0x290) & 0xFF
        go = not (n >= 1 and v == 3) and (n >= 0 or v != 0)
    else:
        go = m.vcall(b, 0x270, k, n & M32) & 1
    if not go:
        if show:
            if m.u8(r + 8) != 8:
                k = m.u8(r + 8)
                who = m.u32(r)
                ident = m.vcall(b, 0x98) & M32
                q = m.call(m.main + 0x1143584, o)
                m.call_void(m.main + (0x2886CA8 if n >= 1 else 0x2886CE4), q, who, ident, k)
            m.put(m.call(m.main + 0x139B698, o) + 0xC0, 1, 1)
        return refused(2)
    if m.vcall(b, 0x588) & 1 and not m.u8(r + 0x19):
        who = m.u32(r)
        if m.vcall(b, 0x98) & M32 != who:
            if show:
                m.call_void(m.main + 0x1536F5C, m.call(m.main + 0x1143584, o), who, b, 0x48)
            return refused(3)
    if m.call(m.main + 0x13820A8, m.call(m.main + 0x1146E90, o), b, m.u8(r + 8), m.u32(r), n & M32,
              m.u8(r + 0x10), m.u32(r + 0x14)) & 1:
        m.put(out, 1, 1)
        return
    if show:
        m.put(m.call(m.main + 0x139B698, o) + 0xC0, 1, 1)
        m.call_void(m.main + 0x1384484, m.call(m.main + 0x1146E90, o), b, m.u32(r + 0x14))
    return refused(4)


@lifted(0x138106C)
def stage_change_allowed_of(m, o, r, *_):
    with m.frame(0x40) as a:
        m.write(a, bytes(0x30))
        m.put(a + 8, 4, m.u32(r))
        m.put(a + 0xC, 4, m.vcall(m.u64(r + 8), 0x98))
        m.put(a + 0x10, 1, m.u8(r + 0x10)); m.put(a + 0x14, 4, m.u32(r + 0x14)); m.put(a + 0x18, 1, m.u8(r + 0x18))
        m.put(a + 0x1A, 2, m.u16(r + 0x1A)); m.put(a + 0x1C, 4, m.u32(r + 0x1C))
        m.put(a + 0x20, 1, m.u8(r + 0x20)); m.put(a + 0x21, 1, m.u8(r + 0x21)); m.put(a + 0x28, 8, m.u64(r + 0x28))
        m.call_void(m.main + 0x138112C, m.call(m.main + 0x1381124, m.call(m.main + 0x1361214, o)), a, a + 8)
        return m.u8(a)


@lifted(0x1380C5C)
def change_stage(m, o, out, r, *_):
    """Change a stat stage (record r: user +0, target +8, stat +0x10, ...): out = (allowed, amount)."""
    _need(m, m.main + 0x1381580)
    if m.call(m.main + 0x138106C, o, r) & 1 == 0:
        m.put(out, 1, 0); m.put(out + 4, 4, 0)
        return
    if m.u64(r + 0x38):
        m.call_void(m.main + 0x114B0AC, m.call(m.main + 0x1143584, o), m.u32(r), m.u64(r + 0x38))
    n = m.call(m.main + 0x1380D4C, o, r) & M32
    x = m.call(m.main + 0x1380D80, o, r, n)
    if x & 1:
        m.put(out, 1, 1); m.put(out + 4, 4, 0)
        return _tail(m, m.main + 0x1382074, o, r, n)
    m.call_void(m.main + 0x1380DB8, x, r, n)
    m.call_void(m.main + 0x13818F8, m.call(m.main + 0x1143584, o), m.u32(r), m.u64(r + 8), m.u8(r + 0x10), n,
                m.u16(r + 0x1A), m.u8(r + 0x30), m.u8(r + 0x40))
    m.call_void(m.main + 0x1380DF0, o, r, n)
    m.put(out, 1, 1); m.put(out + 4, 4, n)


@lifted(0x1380D4C)
def stage_amount(m, o, r, *_):
    return _tail(m, m.main + 0x1381580, m.call(m.main + 0x1146E90, o), m.u64(r + 8), m.u8(r + 0x10), m.u32(r),
                 m.u16(r + 0x1A), m.u32(r + 0x14))


@lifted(0x1380D80)
def stage_blocked(m, o, r, n, *_):
    return _tail(m, m.main + 0x1382CAC, m.call(m.main + 0x1146E90, o), m.u64(r + 8), m.u32(r), m.u8(r + 0x10),
                 n & M32, m.u8(r + 0x18))


@lifted(0x1380DF0)
def stage_changed(m, o, r, n, *_):
    return _tail(m, m.main + 0x1381BF4, m.call(m.main + 0x1146E90, o), m.u32(r), m.u64(r + 8), m.u8(r + 0x10),
                 n & M32, m.u8(r + 0x18))


def _stat_text(base):
    def fn(m, o, who, ident, stat, *_):
        """Queue 0xcb (who, text for stat 1..7, ident): the texts from rodata (+4 of 8-byte rows)."""
        i = (stat - 1) & 0xFF
        if i > 6:
            return
        return _tail(m, m.main + 0x157EBC0, m.u64(o + 0x18), 0xCB, who & M32, base + i, ident & M32, 0xFFFF0000)
    return fn


# Stat-change refusal texts: 53..59 when the stat cannot rise (0x3c6a7cc), 60..66 when it cannot fall
# (0x3c6a874).
lifted(0x2886CA8)(_stat_text(53))
lifted(0x2886CE4)(_stat_text(60))


@lifted(0x19042EC)
def rank_change(m, o, out, r, *_):
    """Run the rank change record r (user +0, target +4, kind +8, descriptor +0x10, flags +0x20..+0x27, text
    +0x28): 0x1795308 checks it, 0x17959d4 applies it, between the user's action start and end when +0x22
    is set. out (byte) = whether it was applied."""
    _need(m, m.main + 0x1795308); _need(m, m.main + 0x17959D4)
    u = m.call(m.main + 0x13813F4, o, m.u32(r)) if m.u32(r) else 0
    v = m.call(m.main + 0x13813E4, m.call(m.main + 0x1482534, o))
    if m.call(m.main + 0x1381400, v, m.u32(r + 4)) & 1 == 0:
        m.put(out, 1, 0)
        return
    b = m.call(m.main + 0x13813F4, o, m.u32(r + 4))
    if m.vcall(b, 0x200) & 1 and not m.u8(r + 0x27):
        m.put(out, 1, 0)
        return
    with m.frame(0x50) as f:
        res = f + 0x48
        s = f
        m.write(s, bytes(0x34))
        m.call_void(m.main + 0x179372C, s + 0x18)
        m.put(s, 8, u); m.put(s + 8, 8, b); m.put(s + 0x10, 2, m.u16(r + 8))
        m.put(s + 0x18, 8, m.u64(r + 0x10)); m.put(s + 0x20, 8, m.u64(r + 0x18))
        m.put(s + 0x28, 1, m.u8(r + 0x20)); m.put(s + 0x2C, 4, 0); m.put(s + 0x30, 1, m.u8(r + 0x21))
        m.put(s + 0x31, 1, m.u8(r + 0x23)); m.put(s + 0x32, 1, m.u8(r + 0x23)); m.put(s + 0x33, 1, 0)
        m.call_void(m.main + 0x1795308, m.call(m.main + 0x1794B08, m.call(m.main + 0x1361214, o)), res, s)
        if m.u8(res):
            m.put(out, 1, 0)
            return
        if m.u8(r + 0x22):
            m.call_void(m.main + 0x187495C, m.call(m.main + 0x1143584, o), u)
        m.put(s + 0x10, 2, 0); m.write(s, bytes(0x10))
        m.call_void(m.main + 0x179372C, s + 0x18)
        m.put(s + 0x29, 1, 0); m.put(s + 0x30, 8, 0); m.put(s + 0x38, 1, 0)
        m.put(s + 0x10, 2, m.u16(r + 8)); m.put(s, 8, u); m.put(s + 8, 8, b)
        m.write(s + 0x18, m.read(r + 0x10, 0x10))
        m.put(s + 0x28, 1, m.u8(r + 0x24))
        own = 0 if m.u8(r + 0x25) else (m.call(m.main + 0x17CE3AC, r + 0x28) ^ 1) & 1
        m.put(s + 0x30, 8, r + 0x28); m.put(s + 0x29, 1, own); m.put(s + 0x38, 1, m.u8(r + 0x26))
        m.call_void(m.main + 0x17959D4, m.call(m.main + 0x1794B10, m.call(m.main + 0x1361214, o)), res, s)
    if m.u8(r + 0x22):
        m.call_void(m.main + 0x17521D8, m.call(m.main + 0x1143584, o), u)
    m.put(out, 1, 1)


@lifted(0x19042B0)
def rank_change_of(m, o, r, *_):
    with m.frame(0x10) as out:
        m.call_void(m.main + 0x19042EC, m.call(m.main + 0x19042E4, m.u64(o + 0x28)), out, r)
        return m.u8(out)


@lifted(0x2899FD8)
def clamp_stages_of(m, b, *_):
    return _tail(m, m.main + 0x2899FE0, b + 0x414)


@lifted(0x287EE84)
def rank_change_check(m, o, user, target, desc, *_):
    """Whether 0x1795308 allows the rank change record {user, target, kind 0x1793e2c(desc), descriptor
    from 0x287db40, flags +0x29 = +0x2a = 1}."""
    kind = m.call(m.main + 0x1793E2C, desc) & 0xFFFF
    sel = m.call(m.main + 0x1793E94, desc) & 0xFFFF
    with m.frame(0x70) as sp:
        d = sp + 8
        m.call_void(m.main + 0x179372C, d)
        m.call_void(m.main + 0x287DB40, o, sel, user, d)
        r = sp + 0x18
        m.write(r, bytes(0x38))
        m.call_void(m.main + 0x179372C, r + 0x18)
        m.put(r + 0x10, 2, kind)
        m.put(r, 8, user); m.put(r + 8, 8, target)
        m.put(r + 0x31, 1, 1); m.put(r + 0x32, 1, 1)
        m.put(r + 0x18, 8, m.u64(d)); m.put(r + 0x20, 8, m.u64(d + 8))
        x = m.call(m.main + 0x1794B08, m.call(m.main + 0x1361214, o))
        m.call_void(m.main + 0x1795308, x, sp + 0x68, r)
        return m.u8(sp + 0x68)


@lifted(0x288ADEC)
def rank_change_each_target(m, o, _x1, r, *_):
    """When 0x157ea90([r+0x10]) holds: for each target of the list [r+0x10], the rank change record {user
    [r+8], target, kind 0x1793e2c(move), descriptor from 0x287db40, +0x30 = 0x101} through 0x179498c; a
    yes runs 0x157a950. With none applied and 0x139b698's +0xc0 clear: 0x157a95c with the user's id."""
    if m.call(m.main + 0x157EA90, m.u64(r + 0x10)) & M32 == 0:
        return
    kind = m.call(m.main + 0x1793E2C, m.u16(m.u64(r))) & 0xFFFF
    sel = m.call(m.main + 0x1793E94, m.u16(m.u64(r))) & 0xFFFF
    m.call_void(m.main + 0x1143D7C, m.u64(r + 0x10))
    applied = False
    with m.frame(0x70) as sp:
        d, rec, res = sp + 8, sp + 0x18, sp + 0x68
        t = m.call(m.main + 0x158003C, m.u64(r + 0x10))
        while t:
            m.call_void(m.main + 0x179372C, d)
            m.call_void(m.main + 0x287DB40, o, sel, m.u64(r + 8), d)
            user = m.u64(r + 8)
            m.write(rec, bytes(0x38))
            m.call_void(m.main + 0x179372C, rec + 0x18)
            m.put(rec, 8, user); m.put(rec + 8, 8, t); m.put(rec + 0x10, 2, kind)
            m.put(rec + 0x18, 8, m.u64(d)); m.put(rec + 0x20, 8, m.u64(d + 8))
            m.put(rec + 0x30, 2, 0x101)
            x = m.call(m.main + 0x1793738, m.call(m.main + 0x1361214, o))
            m.call_void(m.main + 0x179498C, x, res, rec)
            if m.u8(res):
                m.call_void(m.main + 0x157A950, m.call(m.main + 0x139B698, o) + 0x10)
                applied = True
            t = m.call(m.main + 0x158003C, m.u64(r + 0x10))
    if applied or m.u8(m.call(m.main + 0x139B698, o) + 0xC0):
        return
    q = m.call(m.main + 0x1143584, o)
    m.call_void(m.main + 0x157A95C, q, m.vcall(m.u64(r + 8), 0x98) & M32)


@lifted(0x287EDCC)
def drop_unchangeable(m, o, mv, b, lst, *_):
    """Drop (0x157bf08) every target of lst whose rank change 0x287ee84 allows; whether one was kept."""
    m.call_void(m.main + 0x1143D7C, lst)
    kept = 0
    t = m.call(m.main + 0x158003C, lst)
    while t:
        if m.call(m.main + 0x287EE84, o, b, t, m.u16(mv)) & 1:
            m.call_void(m.main + 0x157BF08, lst, t)
        else:
            kept = 1
        t = m.call(m.main + 0x158003C, lst)
    return kept


@lifted(0x1793664)
def stat_change_by_move(m, o, mv, user, target, *_):
    """When event 0x1793740 gives the move's rank change kind and the target is not out: the rank change
    record {user, target, kind, descriptor} through 0x179498c."""
    with m.frame(0x50) as sp:
        d = sp + 0x40
        m.call_void(m.main + 0x179372C, d)
        v = m.call(m.main + 0x1793740, m.call(m.main + 0x1146E90, o), m.u16(mv), user, target, d)
        if not v & 0xFFFF:
            return
        if m.vcall(target, 0x200) & 1:
            return
        r = sp + 8
        m.write(r, bytes(0x38))
        m.call_void(m.main + 0x179372C, r + 0x18)
        m.put(r, 8, user); m.put(r + 8, 8, target); m.put(r + 0x10, 2, v)
        m.put(r + 0x18, 8, m.u64(d)); m.put(r + 0x20, 8, m.u64(d + 8))
        x = m.call(m.main + 0x1793738, m.call(m.main + 0x1361214, o))
        m.call_void(m.main + 0x179498C, x, sp, r)


@lifted(0x15804D0)
def rank_targets_or_text(m, o, _x1, r, *_):
    """0x287edcc on r; with no target kept, +0xc0 clear and +0xc1 set (0x139b698): text 0x237 for [r+8]."""
    if m.call(m.main + 0x287EDCC, o, m.u64(r), m.u64(r + 8), m.u64(r + 0x10)) & 1:
        return
    if m.u8(m.call(m.main + 0x139B698, o) + 0xC0):
        return
    if not m.u8(m.call(m.main + 0x139B698, o) + 0xC1):
        return
    q = m.call(m.main + 0x1143584, o)
    return _tail(m, m.main + 0x287EE68, q, m.vcall(m.u64(r + 8), 0x98) & M32, 0x237)


@lifted(0x186F0B0)
def raise_negative_stages(m, p, *_):
    """Each of the seven signed stage bytes at p below 6 becomes 6; whether any did."""
    hit = 0
    for k in range(7):
        if m.s(p + k, 1) <= 5:
            m.put(p + k, 1, 6)
            hit = 1
    return hit


@lifted(0x186F0A8)
def raise_negative_stages_of(m, b, *_):
    return _tail(m, m.main + 0x186F0B0, b + 0x414)
