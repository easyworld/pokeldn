"""The event dispatcher (0xf7b5d8): the handler chain it walks, the parameter frames handlers read and
write, the event frame's records, and the server's calls that each raise one event."""

from pokeldn.sv.battle.engine.calls import M32, _s32, _tail
from pokeldn.sv.battle.engine.members import _for_each_member
from pokeldn.sv.battle.machine import lifted


def _entry_c(m, o, slot):
    e = m.u64(o + 0x20)
    return m.u32(e + 0xC) if e else 0


def _entry_id(m, t, off):
    e = m.u64(t + off)
    return m.u32(e + 0xC) if e else 0


@lifted(0x28422F0)
def run_15fa034(m, o, arg, *_):
    """The byte 0x15fa034 writes for the object 0x15fa02c returns from [o+0x28]."""
    p = m.call(m.main + 0x15FA02C, m.u64(o + 0x28), arg)
    with m.frame(0x10) as f:
        m.call_void(m.main + 0x15FA034, p, f, arg)
        return m.u8(f)


@lifted(0x114B0AC)
def dispatch_record(m, o, p, rec, *_):
    """Run the record's handler by its kind (bits 0..6 of +2: 1 or 2) and its flag bit 30: 0x11501bc /
    0x114b210 without the flag, 0x19609cc / 0x288d7a8 with it (then with +0x20 as an extra argument).
    1 when a handler ran."""
    p &= 0xFFFFFFFF
    a = m.call(m.main + 0x114B1D4, rec) & 0xFFFFFFFF
    c = m.call(m.main + 0x114B1F0, rec) & 0xFFFF
    x = m.call(m.main + 0x114B1DC, rec)
    if m.call(m.main + 0x114B1FC, rec) & 1 == 0:
        k = m.call(m.main + 0x114B1E4, rec) & 0xFFFFFFFF
        if k == 2:
            m.call_void(m.main + 0x114B210, o, p, a, c, x)
        elif k == 1:
            m.call_void(m.main + 0x11501BC, o, p, a, c, x)
        else:
            return 0
        return 1
    e = m.call(m.main + 0x114B208, rec) & 0xFFFFFFFF
    k = m.call(m.main + 0x114B1E4, rec) & 0xFFFFFFFF
    if k == 2:
        m.call_void(m.main + 0x288D7A8, o, p, a, e, c, x)
    elif k == 1:
        m.call_void(m.main + 0x19609CC, o, p, a, e, c, x)
    else:
        return 0
    return 1


def _owner_id(m, o, slot):
    """The u32 id (+0xc) of the object at [[o+0x38]+0x78]+slot, 0 when there is none."""
    p = m.u64(m.u64(m.u64(o + 0x38) + 0x78) + slot)
    return m.u32(p + 0xC) if p else 0


def _mark_pending(m, rec):
    """A record whose state byte (+0xa) is 0 or 1 gets +0xc = 1, and state 1 moves to 2."""
    if not rec or m.u8(rec + 0xA) > 1:
        return 0
    m.put(rec + 0xC, 4, 1)
    if m.u8(rec + 0xA) == 1:
        m.put(rec + 0xA, 1, 2)
    return 1


# Event parameter frames, as the handlers inline them: a pool of 0x60 parameter records (pointers at
# pool + 8 + 32i, u16 kind at +8, used count at pool+0xc08) and a stack of 31 frames (stack+0x408).


def ev_push(m, ctx):
    """Open a frame: claim the next free record as a frame marker (kind 1), make the next frame current."""
    pool = m.u64(ctx + 0x38)
    c = m.u32(pool + 0xC08)
    while c <= 0x5F:
        e = m.u64(pool + 32 * c + 8)
        if m.u16(e + 8) == 0:
            if c <= 0x5E:
                m.put(e + 8, 2, 1)
                m.put(pool + 0xC08, 4, m.u32(pool + 0xC08) + 1)
            break
        c += 1
        m.put(pool + 0xC08, 4, c)
    stk = m.u64(ctx + 0x58)
    n = m.u32(stk + 0x408)
    if n <= 0x1E:
        m.put(stk + 0x408, 4, n + 1)
        stk = m.u64(ctx + 0x58)
        n = m.u32(stk + 0x408)
    m.put(ctx + 0x78, 8, m.u64(stk + 32 * n + 8))


def ev_param(m, ctx, kind, value, typ, slot):
    """Set parameter `kind` of the current frame (reusing a record of that kind above the used count,
    else the first free one) and note it in the frame at `slot`."""
    pool = m.u64(ctx + 0x38)
    i = m.u32(pool + 0xC08)
    while i < 0x60:
        k = m.u16(m.u64(pool + 32 * i + 8) + 8)
        if k == 0 or k == kind:
            break
        i += 1
    else:
        return
    e = m.u64(pool + 32 * i + 8)
    if e == 0:
        return
    m.put(e + 8, 2, kind); m.put(e + 0xC, 4, value); m.put(e + 0xA, 1, typ)
    m.put(e + 0x10, 8, 0); m.put(e + 0x18, 8, 0)
    m.put(m.u64(ctx + 0x78) + slot, 8, e)


def ev_pop(m, ctx):
    """Close the current frame: clear it, release its records back to the frame marker below."""
    stk = m.u64(ctx + 0x58)
    n = m.u32(stk + 0x408)
    if n:
        m.write(m.u64(stk + 32 * n + 8) + 8, bytes(0x430))
        m.put(stk + 0x408, 4, m.u32(stk + 0x408) - 1)
        stk = m.u64(ctx + 0x58)
        n = m.u32(stk + 0x408)
    m.put(ctx + 0x78, 8, m.u64(stk + 32 * n + 8))
    pool = m.u64(ctx + 0x38)
    c = m.u32(pool + 0xC08)
    if c == 0:
        return
    if c & 0xFFFF <= 0x5F:
        j = c & 0xFFFF
        while True:
            e = m.u64(pool + 32 * j + 8)
            if m.u16(e + 8) == 0:
                break
            m.put(e + 8, 2, 0)
            j += 1
            if j & 0xFFFF == 0x60:
                break
        c = m.u32(pool + 0xC08)
    c = (c - 1) & 0xFFFFFFFF
    m.put(pool + 0xC08, 4, c)
    m.put(m.u64(pool + 32 * c + 8) + 8, 2, 0)
    c = m.u32(pool + 0xC08)
    while c:
        c -= 1
        m.put(pool + 0xC08, 4, c)
        if m.u16(m.u64(pool + 32 * c + 8) + 8) == 1:
            m.put(pool + 0xC08, 4, c + 1)
            return


@lifted(0x157E064)
def event_c5(m, o, a, b, _x3, out, *_):
    """Unless vf 0x4e8 of b is 0x20: event 0xc5 with parameters 3 (id a), 4 (id b), 0x24 (that value),
    0x49 (1) and 0x56 ([out]); returns whether parameter 0x49 came back nonzero, [out] gets 0x56's."""
    m.put(out, 1, 1)
    v = m.vcall(b, 0x4E8) & 0xFFFFFFFF
    if v == 0x20:
        return 0
    ev_push(m, m.u64(o + 0x10))
    ctx = m.u64(o + 0x10)
    ev_param(m, ctx, 3, m.vcall(a, 0x98), 4, 0x20)
    ctx = m.u64(o + 0x10)
    ev_param(m, ctx, 4, m.vcall(b, 0x98), 4, 0x28)
    ev_param(m, m.u64(o + 0x10), 0x24, v, 4, 0x128)
    ev_param(m, m.u64(o + 0x10), 0x49, 1, 1, 0x250)
    ev_param(m, m.u64(o + 0x10), 0x56, m.u8(out), 1, 0x2B8)
    m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), 0xC5, 8, 1)
    frame = m.u64(m.u64(o + 0x10) + 0x78)
    p = m.u64(frame + 0x250)
    r = int(p != 0 and m.u32(p + 0xC) != 0)
    p = m.u64(frame + 0x2B8)
    m.put(out, 1, int(p != 0 and m.u32(p + 0xC) != 0))
    ev_pop(m, m.u64(o + 0x10))
    return r


@lifted(0x17776D8)
def event_bc_if_2a8(m, o, _a, p, *_):
    """When vf 0x2a8 of battler [p] is nonzero, tail-calls 0x1777748(0x1146e90(o), battler, byte p+4)."""
    from pokeldn.sv.battle.engine.containers import battler
    b = battler(m, m.u64(m.u64(o + 0x10) + 0x30), m.u32(p))
    if m.vcall(b, 0x2A8) & 0xFFFF == 0:
        return
    return _tail(m, m.main + 0x1777748, m.call(m.main + 0x1146E90, o), b, m.u8(p + 4))


@lifted(0x15372E8)
def resolve_hit_15372e8(m, o, out, rec, *_):
    """rec: u32 target +0, attacker +4, u16 +8/+0xa, flags +0xc/+0xd/+0xf/+0x10/+0x11/+0x16, body
    +0x14. *out = whether the hit lands (neither 0x1872ce0 check on the target nor on the attacker
    refuses it); then the hit's commands (0x17d3110, 0x114b0ac or 0xcb/0x125) or the refusal's
    (0xcb/0x11d, 0xca/0x237), and 0xc8 for the target when +0xc."""
    m.put(out, 1, 0)
    team = m.u64(m.u64(o + 0x10) + 0x30)
    a = m.call(m.main + 0xF21C94, team, m.u32(rec + 4))
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), m.u32(rec))
    f10, f11 = m.u8(rec + 0x10), m.u8(rec + 0x11)
    t = m.u64(m.u64(o + 0x78) + 0x15E0)
    q = lambda: m.u64(m.u64(o + 0x20) + 0x18)
    if m.call(m.main + 0x1832E08, t, a) & 1:
        if not m.vcall(a, 0x1F8) & 1 or not m.u8(rec + 0xD):
            return
        target = m.u32(rec)
        return _tail(m, m.main + 0x157EBC0, q(), 0xCB, target, 0x11F, m.vcall(a, 0x98) & 0xFFFFFFFF, 0xFFFF0000)
    if b and not f11 and m.call(m.main + 0x1872CE0, t, b) & 1:
        why = 3
    elif not f10 and m.call(m.main + 0x1872CE0, t, a) & 1:
        why = 2
    else:
        why = 0
        m.put(out, 1, 1)
    if m.u8(rec + 0xC):
        m.call_void(m.main + 0x17CE0EC, m.u64(o + 0x20), m.u32(rec), 0)
    if m.u8(out):
        m.call_void(m.main + 0x17D3110, o, a, m.u16(rec + 8), m.u8(rec + 0xF))
        if m.u8(rec + 0x16) & 0x7F:
            m.call_void(m.main + 0x114B0AC, m.u64(o + 0x20), m.u32(rec), rec + 0x14)
        elif m.u16(rec + 0xA):
            m.call_void(m.main + 0x157EBC0, q(), 0xCB, m.u32(rec + 4), 0x125, m.u32(rec + 4), m.u16(rec + 0xA),
                        0xFFFF0000)
    elif why == 2:
        m.call_void(m.main + 0x157EBC0, q(), 0xCB, m.u32(rec), 0x11D, m.u32(rec + 4), 0xFFFF0000)
    elif why == 3:
        m.call_void(m.main + 0x157EBC0, q(), 0xCA, m.u32(rec), 0x237, 0xFFFF0000)
    if m.u8(rec + 0xC) and m.u32(rec):
        return _tail(m, m.main + 0x119AFF0, q(), 0xC8, m.u32(rec))


@lifted(0x15FA034)
def check_b0(m, o, out, arg, *_):
    if m.u32(m.u64(m.u64(o + 0x10) + 0x70) + 0xB0):
        m.put(out, 1, 0)
        return
    r = m.call(m.main + 0x15FA084, m.u64(o + 0x38), m.u64(arg), m.u8(arg + 8))
    m.put(out, 1, r & 1)     # the game clears `out` before the call; the callee never sees it


@lifted(0x17D3110)
def run_17d3154(m, o, a, b, c, *_):
    """0x17d3154(0x17d314c([o+0x78]), an out slot, &{a, u16 b, c & 1})."""
    with m.frame(0x20) as p:
        m.put(p + 8, 8, a); m.put(p + 0x10, 2, b); m.put(p + 0x12, 1, c & 1)
        return _tail(m, m.main + 0x17D3154, m.call(m.main + 0x17D314C, m.u64(o + 0x78)), p, p + 8)


@lifted(0x288B6FC)
def query_15372e8(m, o, b, key, arg, *_):
    """Build a request {u32 0, b's id, u16 key, flags 1 at +0xd/+0xe/+0xf/+0x11, sub-record +0x14 from
    0x287eca8(arg)} and return the byte 0x15372e8 answers for 0x1537120(0x1361214(o))."""
    with m.frame(0x50) as s:
        out = s + 0x40
        m.write(s, bytes(0x40))
        m.put(s + 0xE, 4, 0x01000101)
        m.call_void(m.main + 0x1146154, s + 0x14)
        m.put(s + 4, 4, m.vcall(b, 0x98))
        m.put(s + 8, 2, key)
        m.put(s + 0x10, 1, 0)
        m.put(s + 0xD, 1, 1)
        m.call_void(m.main + 0x287ECA8, s + 0x14, arg)
        r = m.call(m.main + 0x1537120, m.call(m.main + 0x1361214, o))
        m.call_void(m.main + 0x15372E8, r, out, s)
        return m.u8(out)


@lifted(0x116EC0C)
def event_9d(m, o, *_):
    """Event 0x9d with parameter 0x48 (0): the byte +0x19 of [[o + 0x18] + 0x70] unless a handler set
    0x48, else 0."""
    ev_push(m, m.u64(o + 0x10))
    ev_param(m, m.u64(o + 0x10), 0x48, 0, 1, 0x248)
    m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), 0x9D, 8, 1)
    ctx = m.u64(o + 0x10)
    p = m.u64(m.u64(ctx + 0x78) + 0x248)
    clear = p == 0 or m.u32(p + 0xC) == 0
    ev_pop(m, ctx)
    return m.u8(m.u64(m.u64(o + 0x18) + 0x70) + 0x19) if clear else 0


@lifted(0x116EE6C)
def event_9e(m, o, ident, v, *_):
    """Event 0x9e with parameters 2 (ident), 0x3e (v & 0xff) and 0x48 (0): v unless a handler set
    0x48, else 0."""
    ev_push(m, m.u64(o + 0x10))
    ev_param(m, m.u64(o + 0x10), 2, ident & M32, 0, 0x18)
    ev_param(m, m.u64(o + 0x10), 0x3E, v & 0xFF, 0, 0x1F8)
    ev_param(m, m.u64(o + 0x10), 0x48, 0, 1, 0x248)
    m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), 0x9E, 8, 1)
    ctx = m.u64(o + 0x10)
    p = m.u64(m.u64(ctx + 0x78) + 0x248)
    set_ = p != 0 and m.u32(p + 0xC) != 0
    ev_pop(m, ctx)
    return 0 if set_ else v & M32


def _bump_record(m, rec, value):
    """A record in state 0 or 1 (+0xa) takes `value` at +0xc; state 1 moves to 2."""
    if rec == 0:
        return
    s = m.u8(rec + 0xA)
    if s > 1:
        return
    m.put(rec + 0xC, 4, value)
    if s == 1:
        m.put(rec + 0xA, 1, 2)


def _id_at(m, t, off):
    p = m.u64(t + off)
    return m.u32(p + 0xC) if p else 0


@lifted(0xF80340)
def filter_7(m, f, *_):
    """Filter 7: kind 5, the source's id +0x38 equal to +0x20, and 0x197a6e0 naming one of two hashes."""
    if m.u8(f + 0x1A) != 5:
        return 0
    if m.u32(f + 0x20) != m.call(m.main + 0xF803C8, m.u64(f + 0x10)) & M32:
        return 0
    h = m.call(m.main + 0x197A6E0, m.u64(f), m.u16(f + 0x1C))
    return int(h in (0xFD429E44243A2B76, 0x08E01121DFC5148F))


@lifted(0xF80294)
def run_filter(m, kind, f, *_):
    """The handler filter `kind` (1..7) over the event record f (jump table 0x3c69ee8): 0 = let it run."""
    kind = (kind - 1) & 0xFFFF
    if kind > 6:
        return 0
    if kind == 0:
        return int(m.u8(f + 0x1A) == 4 and m.u16(f + 0x1C) == 0x6A)
    if kind == 5:
        v = m.u16(f + 0x1C)
        return (0x20003 >> v) & 1 if m.u8(f + 0x1A) == 2 and v < 0x12 else 0
    target = (None, 0x283D160, 0x283D210, 0x283D4A0, 0x283D520, None, 0xF80340)[kind]
    return _tail(m, m.main + target, f)


def _handler_chain(m, ctx):
    """The first handler record of the chain at [[ctx + 8] + 0xd0] (the map keyed by its u16 +0x70)."""
    owner = m.u64(m.u64(ctx + 8) + 0xD0)
    return m.call(m.main + 0xF7BA54, owner, m.u16(owner + 0x70))


@lifted(0xF7B5D8)
def dispatch_one(m, ctx, event, kind, check, rec, *_):
    """Run handler record `rec` for `event` when it is live, of `kind` (8 = any), past its turn gate
    (+0x3c), enabled, holding an entry for the event, and (with `check`) not stopped by its battler's
    state or a higher handler's filter. Returns the record after it in its chain."""
    nxt = m.call(m.main + 0xF7BA54, m.u64(rec + 8), m.u16(rec + 0x14))
    if m.u8(rec + 0x3F) and not m.u8(rec + 0x40):
        return nxt
    if m.u8(rec + 0x42):
        return nxt
    kind &= 0xFF
    if kind != 8 and m.u8(rec + 0x28) != kind:
        return nxt
    gate = m.u16(rec + 0x3C)
    if gate and not m.u32(ctx + 0x80) > gate:
        return nxt
    if not m.u8(rec + 0x44):
        return nxt
    event &= 0xFFFF
    if event == 0x95 and m.call(m.main + 0xF7C230, rec) & 1 == 0:
        return nxt
    n = m.u8(rec + 0x3E)
    entry = m.u64(rec + 0x20)
    while n:
        if m.u16(entry) == event:
            break
        entry += 0x10
        n -= 1
    else:
        return nxt
    if check & 1:
        b = 0
        ident = m.u32(rec + 0x38)
        if ident:
            b = m.call(m.main + 0xF21C94, m.u64(m.u64(ctx + 8) + 0x30), ident)
            if m.u8(rec + 0x28) == 4 and b:
                if m.vcall(b, 0x220, 0x10) & 1 or m.vcall(b, 0x438) & 1:
                    return nxt
                if m.vcall(b, 0x5B0) & 1:
                    if m.call(m.main + 0xF7BB80, m.call(m.main + 0xF7BB74, rec)) & 1:
                        return nxt
        if event != 0xD7 and m.u8(rec + 0x28) == 5:
            if m.call(m.main + 0x1482544, m.call(m.main + 0x148253C, m.u64(ctx + 8)), 5) & 1:
                return nxt
            if b and (m.vcall(b, 0x220, 0x13) & 1 or m.vcall(b, 0x510, 9) & 1):
                return nxt
        with m.frame(0x30) as f:
            h = _handler_chain(m, ctx)
            while h:
                k = m.u16(h + 0x18)
                if k and not m.u8(h + 0x42):
                    hb = 0
                    if m.u8(h + 0x28) == 4:
                        hb = m.call(m.main + 0xF79790, m.u64(m.u64(ctx + 8) + 0x30), m.u32(h + 0x38))
                    if not hb or not (m.vcall(hb, 0x220, 0x10) & 1 or m.vcall(hb, 0x438) & 1):
                        m.put(f, 8, m.u64(ctx)); m.put(f + 8, 8, m.u64(ctx + 8)); m.put(f + 0x10, 8, h)
                        m.put(f + 0x18, 2, event); m.put(f + 0x1A, 1, m.u8(rec + 0x28))
                        m.put(f + 0x1C, 2, m.call(m.main + 0xF7BB74, rec))
                        m.put(f + 0x20, 4, m.u32(rec + 0x34))
                        if m.call(m.main + 0xF80294, k, f) & 1:
                            return nxt
                h = m.call(m.main + 0xF7BA54, m.u64(h + 8), m.u16(h + 0x14))
    m.put(rec + 0x3F, 1, 1)
    with m.frame(0x50) as a:
        for i in range(7):
            m.put(a + 8 * i, 8, m.u64(ctx + 8 * i))
        m.put(a + 0x38, 8, ctx); m.put(a + 0x40, 8, m.u64(ctx + 0x78)); m.put(a + 0x48, 8, rec)
        m.call_void(m.u64(entry + 8), a, m.u32(rec + 0x34))
    if m.u8(rec + 0x40):
        m.call_void(m.main + 0xF7C238, rec)
    else:
        m.put(rec + 0x3F, 1, 0)
    if not m.u8(rec + 0x41):
        return nxt
    while nxt and not m.u8(nxt + 0x44):
        nxt = m.call(m.main + 0xF7BA54, m.u64(rec + 8), m.u16(rec + 0x14))
    if not m.u8(rec + 0x44):
        return nxt
    if m.u8(rec + 0x3F):
        m.call_void(m.main + 0x1360CDC, rec, 1)
    else:
        m.call_void(m.main + 0x13608E0, m.u64(m.u64(ctx + 8) + 0xD0), rec)
    return nxt


@lifted(0xF7B310)
def dispatch(m, ctx, event, kind, check, *_):
    """Run every handler of the chain for `event`, one nesting level deeper (+0x80); leaving the outermost
    level clears every handler's turn gate (+0x3c)."""
    m.put(ctx + 0x80, 4, m.u32(ctx + 0x80) + 1)
    rec = _handler_chain(m, ctx)
    while rec:
        r = m.call(m.main + 0xF7B5D8, ctx, event & M32, kind & M32, check & 1, rec)
        if r == 0:
            break
        if not m.u8(r + 0x44):
            r = m.call(m.main + 0xF7BA54, m.u64(rec + 8), m.u16(rec + 0x14))
        rec = r
    depth = (m.u32(ctx + 0x80) - 1) & M32
    m.put(ctx + 0x80, 4, depth)
    if depth:
        return
    rec = _handler_chain(m, ctx)
    while rec:
        m.put(rec + 0x3C, 2, 0)
        rec = m.call(m.main + 0xF7BA54, m.u64(rec + 8), m.u16(rec + 0x14))


def _value(m, ctx, slot):
    """The u32 value of the current frame's parameter at `slot`, 0 when it is not set."""
    p = m.u64(m.u64(ctx + 0x78) + slot)
    return m.u32(p + 0xC) if p else 0


@lifted(0x15FA4DC)
def set_param(m, ctx, kind, value, *_):
    """Parameter `kind` (<= 0x85) of the current frame takes `value` when in state 0 or 1 (state 1 moves
    to 2); returns whether it did."""
    kind &= 0xFFFF
    if kind > 0x85:
        return 0
    rec = m.u64(m.u64(ctx + 0x78) + 8 * kind + 8)
    if rec == 0 or m.u8(rec + 0xA) > 1:
        return 0
    _bump_record(m, rec, value)
    return 1


@lifted(0x15FA084)
def event_12(m, o, b, flag, *_):
    """Event 0x12 for battler b with parameters 2 (its id), 0x59 (flag and b's vf 0x300(2)) and 0x48 (0);
    states 0x15/0x20 set 0x48, 0x21/0x1f set 0x59. Returns 0x59 set and 0x48 clear."""
    f = m.vcall(b, 0x300, 2) & 1 if flag & 1 else 0
    ev_push(m, m.u64(o + 0x10))
    ctx = m.u64(o + 0x10)
    ev_param(m, ctx, 2, m.vcall(b, 0x98) & M32, 4, 0x18)
    ev_param(m, m.u64(o + 0x10), 0x59, f, 1, 0x2D0)
    ev_param(m, m.u64(o + 0x10), 0x48, 0, 1, 0x248)
    m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), 0x12, 8, 1)
    if m.vcall(b, 0x220, 0x15) & 1:
        m.call_void(m.main + 0x15FA4DC, m.u64(o + 0x10), 0x48, 1)
    if m.vcall(b, 0x220, 0x20) & 1:
        m.call_void(m.main + 0x15FA4DC, m.u64(o + 0x10), 0x48, 1)
    if m.vcall(b, 0x220, 0x21) & 1 or m.vcall(b, 0x220, 0x1F) & 1:
        m.call_void(m.main + 0x15FA4DC, m.u64(o + 0x10), 0x59, 1)
    ctx = m.u64(o + 0x10)
    a = _value(m, ctx, 0x2D0)
    c = _value(m, ctx, 0x248)
    ev_pop(m, ctx)
    return int(a != 0 and c == 0)


def _t78(m, o):
    """The current event frame [[o + 0x38] + 0x78]."""
    return m.u64(m.u64(o + 0x38) + 0x78)


@lifted(0x28427A0)
def listed_id(m, o, i, *_):
    """Id i (a signed byte below the count) of the list at [t + 0x30], entries from [t + 0x38]."""
    t = _t78(m, o)
    p = m.u64(t + 0x30)
    if p == 0:
        return 0
    if i & 0x80 or m.u32(p + 0xC) <= i & 0xFF:
        return 0
    e = m.u64(t + 8 * (i & 0xFF) + 0x38)
    return m.u32(e + 0xC) if e else 0


@lifted(0x2842730)
def is_listed(m, o, ident, *_):
    """Whether `ident` is one of the ids of the list at [t + 0x30]."""
    p = m.u64(_t78(m, o) + 0x30)
    if p == 0:
        return 0
    n = m.u32(p + 0xC)
    i = 0
    while n:
        if m.call(m.main + 0x28427A0, o, i) & M32 == ident & M32:
            return 1
        i = (i + 1) & M32
        if i == n:
            break
    return 0


def _bump_inc(m, rec):
    """A record in state 0 or 1 adds one (as a byte) to +0xc; state 1 moves to 2."""
    if rec == 0:
        return
    s = m.u8(rec + 0xA)
    if s > 1:
        return
    m.put(rec + 0xC, 4, (m.u32(rec + 0xC) + 1) & 0xFF)
    if s == 1:
        m.put(rec + 0xA, 1, 2)


@lifted(0x28533B0)
def put_u32(m, p, v, *_):
    m.put(p, 4, v)


@lifted(0x2836050)
def event_d9(m, o, ident, sub, desc, *_):
    """Event 0xd9 with parameters 2 (ident), 0x66 (sub) and 0x27 (0): a positive 0x27 shifts the target
    descriptor and becomes its count."""
    ev_push(m, m.u64(o + 0x10))
    ev_param(m, m.u64(o + 0x10), 2, ident & M32, 4, 0x18)
    ev_param(m, m.u64(o + 0x10), 0x66, sub & 0xFF, 4, 0x338)
    ev_param(m, m.u64(o + 0x10), 0x27, 0, 0, 0x140)
    m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), 0xD9, 8, 1)
    n = _s32(_value(m, m.u64(o + 0x10), 0x140))
    if n > 0:
        m.call_void(m.main + 0x28363E0, desc, n & M32)
        m.call_void(m.main + 0x2836430, desc, n & M32)
    ev_pop(m, m.u64(o + 0x10))


@lifted(0x1382688)
def event_05(m, o, a, b, key, *_):
    """Event 5 with parameters 3 (a's id), 4 (b's id), 0x12 (key) and 0x59 (0x1382ab0(key)): whether a
    handler set 0x59."""
    flag = m.call(m.main + 0x1382AB0, key) & 1
    ev_push(m, m.u64(o + 0x10))
    ctx = m.u64(o + 0x10)
    ev_param(m, ctx, 3, m.vcall(a, 0x98) & M32, 4, 0x20)
    ctx = m.u64(o + 0x10)
    ev_param(m, ctx, 4, m.vcall(b, 0x98) & M32, 4, 0x28)
    ev_param(m, m.u64(o + 0x10), 0x12, key & 0xFFFF, 4, 0x98)
    ev_param(m, m.u64(o + 0x10), 0x59, flag, 1, 0x2D0)
    m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), 5, 8, 1)
    ctx = m.u64(o + 0x10)
    r = _value(m, ctx, 0x2D0)
    ev_pop(m, ctx)
    return int(r != 0)


def _event(m, o, event, params, result=None, read=None):
    """Raise `event` on the context [o + 0x10] with params (kind, value, type, slot), in order (type "ptr":
    the value is a pointer kept at +0x18; "ratio": a 4096-based ratio, see _ratio_param); the u32
    value at `result`'s slot (0 when unset), or what read(ctx) returns, comes back, taken before the
    frame closes."""
    ev_push(m, m.u64(o + 0x10))
    for kind, value, typ, slot in params:
        if callable(value):
            value = value()
        if typ == "ptr":
            _ptr_param(m, m.u64(o + 0x10), kind, value, slot)
        elif typ == "ratio":
            _ratio_param(m, m.u64(o + 0x10), kind, slot)
        else:
            ev_param(m, m.u64(o + 0x10), kind, value & M32, typ, slot)
    m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), event, 8, 1)
    ctx = m.u64(o + 0x10)
    r = _value(m, ctx, result) if result is not None else read(ctx) if read else 0
    ev_pop(m, m.u64(o + 0x10))
    return r


@lifted(0x1381580)
def event_79(m, o, b, stat, _user, _key, amount, *_):
    """Event 0x79 with parameters 2 (b's id), 0x22 (stat) and 0x23 (amount): the amount handlers leave."""
    return _event(m, o, 0x79, ((2, lambda: m.vcall(b, 0x98), 4, 0x18), (0x22, stat & 0xFF, 4, 0x118),
                               (0x23, amount, 1, 0x120)), 0x120)


@lifted(0x1382CAC)
def event_7d(m, o, b, user, stat, amount, flag, *_):
    """Event 0x7d with parameters 4 (b's id), 3 (user), 0x22 (stat), 0x23 (amount), 0x68 (flag) and 0x74
    (0): whether a handler set 0x74."""
    ident = m.vcall(b, 0x98)
    return int(_event(m, o, 0x7D, ((4, ident, 4, 0x28), (3, user, 4, 0x20), (0x22, stat & 0xFF, 4, 0x118),
                                   (0x23, amount, 4, 0x120), (0x68, flag & 0xFF, 4, 0x348), (0x74, 0, 1, 0x3A8)),
                      0x3A8) != 0)


@lifted(0x1381BF4)
def event_7c(m, o, user, b, stat, amount, flag, *_):
    """Event 0x7c with parameters 3 (user), 2 (b's id), 0x22 (stat), 0x23 (amount) and 0x68 (flag)."""
    _event(m, o, 0x7C, ((3, user, 4, 0x20), (2, lambda: m.vcall(b, 0x98), 4, 0x18), (0x22, stat & 0xFF, 4, 0x118),
                        (0x23, amount, 4, 0x120), (0x68, flag & 0xFF, 4, 0x348)))


@lifted(0x28868B4)
def event_7e(m, o, b, user, stat, amount, *_):
    """Event 0x7e with parameters 4 (b's id), 3 (user), 0x22 (stat) and 0x23 (amount)."""
    _event(m, o, 0x7E, ((4, lambda: m.vcall(b, 0x98), 4, 0x28), (3, user, 4, 0x20), (0x22, stat & 0xFF, 4, 0x118),
                        (0x23, amount, 4, 0x120)))


@lifted(0x1382074)
def event_7e_of(m, o, r, amount, *_):
    return _tail(m, m.main + 0x28868B4, m.call(m.main + 0x1146E90, o), m.u64(r + 8), m.u32(r), m.u8(r + 0x10),
                 amount & M32)


@lifted(0x13820A8)
def event_7a(m, o, b, stat, user, amount, flag, value, *_):
    """Event 0x7a with parameters 2 (b's id), 3 (user), 0x22 (stat), 0x23 (amount), 0x68 (flag), 0x1a (value)
    and 0x48 (0): whether no handler set 0x48."""
    return int(_event(m, o, 0x7A, ((2, lambda: m.vcall(b, 0x98), 4, 0x18), (3, user, 4, 0x20),
                                   (0x22, stat & 0xFF, 4, 0x118), (0x23, amount, 4, 0x120),
                                   (0x68, flag & 0xFF, 4, 0x348), (0x1A, value, 4, 0xD8), (0x48, 0, 1, 0x248)),
                      0x248) == 0)


@lifted(0x1384484)
def event_7b(m, o, b, value, *_):
    """Event 0x7b with parameters 2 (b's id) and 0x1a (value)."""
    _event(m, o, 0x7B, ((2, lambda: m.vcall(b, 0x98), 4, 0x18), (0x1A, value, 4, 0xD8)))


@lifted(0x2836450)
def event_da(m, o, ident, sub, *_):
    """Event 0xda with parameters 2 (ident) and 0x66 (sub)."""
    _event(m, o, 0xDA, ((2, ident, 4, 0x18), (0x66, sub & 0xFF, 4, 0x338)))


@lifted(0x2836A78)
def event_db(m, o, ident, kind, *_):
    """Event 0xdb with parameters 2 (ident) and 0x67 (kind)."""
    _event(m, o, 0xDB, ((2, ident, 4, 0x18), (0x67, kind, 4, 0x340)))


def _param_record(m, ctx, kind, slot):
    """ev_param's record choice for `kind` (a record of that kind above the used count, else the first
    free one), noted in the frame at `slot`; 0 when none."""
    pool = m.u64(ctx + 0x38)
    i = m.u32(pool + 0xC08)
    while i < 0x60:
        k = m.u16(m.u64(pool + 32 * i + 8) + 8)
        if k == 0 or k == kind:
            break
        i += 1
    else:
        return 0
    e = m.u64(pool + 32 * i + 8)
    if e:
        m.put(e + 8, 2, kind)
        m.put(m.u64(ctx + 0x78) + slot, 8, e)
    return e


def _side_event(event):
    def fn(m, o, ident, side, pos, desc, *_):
        """Event with parameters 2 (ident), 0x5b (pos), 0x5c (side) and 0x1f (the descriptor's address)."""
        ev_push(m, m.u64(o + 0x10))
        ev_param(m, m.u64(o + 0x10), 2, ident & M32, 4, 0x18)
        ev_param(m, m.u64(o + 0x10), 0x5B, pos & 0xFF, 4, 0x2E0)
        ev_param(m, m.u64(o + 0x10), 0x5C, side & M32, 4, 0x2E8)
        e = _param_record(m, m.u64(o + 0x10), 0x1F, 0x100)
        if e:
            m.write(e + 0xC, bytes(0xC)); m.put(e + 0x18, 8, desc); m.put(e + 0xA, 1, 0)
        m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), event, 8, 1)
        ev_pop(m, m.u64(o + 0x10))
    return fn


# Side condition events: 0xcb before it is placed, 0xf2 once placed.
lifted(0x283AAE8)(_side_event(0xCB))
lifted(0x283AEC0)(_side_event(0xF2))


@lifted(0x1147308)
def dispatch_unchecked(m, ctx, event, *_):
    return _tail(m, m.main + 0xF7B310, ctx, event, 8, 0)


@lifted(0x283544C)
def event_8a(m, o, b, *_):
    """Event 0x8a (handlers run unchecked) with parameter 2 (b's id)."""
    ev_push(m, m.u64(o + 0x10))
    ev_param(m, m.u64(o + 0x10), 2, m.vcall(b, 0x98) & M32, 4, 0x18)
    m.call_void(m.main + 0x1147308, m.u64(o + 0x10), 0x8A)
    ev_pop(m, m.u64(o + 0x10))


@lifted(0x2835034)
def event_88(m, o, b, u, kind, d0, d1, *_):
    """Event 0x88 with parameters 4 (b's id), 3 (u's id, 0 without one), 0x1e (kind) and 0x1f (the
    descriptor (d0, d1) on the stack)."""
    with m.frame(0x10) as d:
        m.put(d, 8, d0); m.put(d + 8, 8, d1)
        ev_push(m, m.u64(o + 0x10))
        ev_param(m, m.u64(o + 0x10), 4, m.vcall(b, 0x98) & M32, 4, 0x28)
        ev_param(m, m.u64(o + 0x10), 3, m.vcall(u, 0x98) & M32 if u else 0, 4, 0x20)
        ev_param(m, m.u64(o + 0x10), 0x1E, kind & 0xFFFF, 4, 0xF8)
        e = _param_record(m, m.u64(o + 0x10), 0x1F, 0x100)
        if e:
            m.write(e + 0xC, bytes(0xC)); m.put(e + 0x18, 8, d); m.put(e + 0xA, 1, 0)
        m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), 0x88, 8, 1)
        ev_pop(m, m.u64(o + 0x10))


@lifted(0x1795EA4)
def event_e0(m, o, b, u, kind, sub, *_):
    """Event 0xe0 with parameters 3 (u's id), 4 (b's id), 0x1e (kind), 0x6b (sub) and 0x59 (0): whether a
    handler set 0x59; 0 without a user."""
    if u == 0:
        return 0
    return int(_event(m, o, 0xE0, ((3, lambda: m.vcall(u, 0x98), 4, 0x20), (4, lambda: m.vcall(b, 0x98), 4, 0x28),
                                   (0x1E, kind & 0xFFFF, 4, 0xF8), (0x6B, sub & 0xFF, 4, 0x360),
                                   (0x59, 0, 1, 0x2D0)), 0x2D0) != 0)


@lifted(0x1796364)
def event_85(m, o, u, b, kind, sub, out, *_):
    """Event 0x85 with parameters 3 (u's id, 0 without one), 4 (b's id), 0x1e (kind), 0x6b (sub), 0x48 and
    0x4a (0): out (byte) = 0x4a set; returns 0x48 set."""
    ev_push(m, m.u64(o + 0x10))
    for kind_, value, typ, slot in ((3, lambda: m.vcall(u, 0x98) if u else 0, 4, 0x20),
                                    (4, lambda: m.vcall(b, 0x98), 4, 0x28), (0x1E, lambda: kind & 0xFFFF, 4, 0xF8),
                                    (0x6B, lambda: sub & 0xFF, 4, 0x360), (0x48, lambda: 0, 1, 0x248),
                                    (0x4A, lambda: 0, 1, 0x258)):
        ev_param(m, m.u64(o + 0x10), kind_, value() & M32, typ, slot)
    m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), 0x85, 8, 1)
    ctx = m.u64(o + 0x10)
    r = _value(m, ctx, 0x248)
    m.put(out, 1, int(_value(m, ctx, 0x258) != 0))
    ev_pop(m, m.u64(o + 0x10))
    return int(r != 0)


def _form_event(event, flag_kind, flag_slot, want):
    def fn(m, o, ident, form, kind, *_):
        """Event with parameters 2 (ident), 0x10 (form), 0x6c (kind) and a flag (0)."""
        r = _event(m, o, event, ((2, ident, 4, 0x18), (0x10, form & 0xFFFF, 4, 0x88), (0x6C, kind & 0xFF, 4, 0x368),
                                 (flag_kind, 0, 1, flag_slot)), flag_slot)
        return int((r != 0) == want)
    return fn


# Event 0xde returns whether no handler set 0x48; 0xdf whether one set 0x56.
lifted(0x283B434)(_form_event(0xDE, 0x48, 0x248, False))
lifted(0x283B83C)(_form_event(0xDF, 0x56, 0x2B8, True))


def _id(m, b):
    return lambda: m.vcall(b, 0x98)


@lifted(0x1144BD8)
def event_for_id(m, o, ident, event, *_):
    """Event `event` with parameter 2 (ident)."""
    _event(m, o, event & M32, ((2, ident, 4, 0x18),))


@lifted(0x113FFFC)
def event_e6(m, o, *_):
    _event(m, o, 0xE6, ())


@lifted(0x282FBF4)
def event_e7(m, o, *_):
    _event(m, o, 0xE7, ())


@lifted(0x2836D2C)
def event_dc(m, o, ident, *_):
    _event(m, o, 0xDC, ((2, ident, 0, 0x18),))


@lifted(0x28315CC)
def event_03(m, o, b, v, *_):
    _event(m, o, 3, ((3, _id(m, b), 4, 0x20), (0x12, v & 0xFFFF, 4, 0x98)))


@lifted(0x173C518)
def event_2f(m, o, b, flag, *_):
    """Event 0x2f with parameters 2 (b's id) and 0x73 (flag): whether 0x73 is set after it."""
    return int(_event(m, o, 0x2F, ((2, _id(m, b), 4, 0x18), (0x73, flag & 1, 1, 0x3A0)), 0x3A0) != 0)


@lifted(0x13DC120)
def event_17(m, o, b, v, *_):
    _event(m, o, 0x17, ((2, _id(m, b), 0, 0x18), (0x12, v & 0xFFFF, 0, 0x98)))


@lifted(0x173CB54)
def event_e9(m, o, a, b, c, *_):
    """Event 0xe9 with parameters 3, 4 and 2 (the three battlers' ids) and 0x73 (0): whether a handler
    set 0x73."""
    return int(_event(m, o, 0xE9, ((3, _id(m, a), 4, 0x20), (4, _id(m, b), 4, 0x28), (2, _id(m, c), 4, 0x18),
                                   (0x73, 0, 1, 0x3A0)), 0x3A0) != 0)


@lifted(0x2D0C9D8)
def event_with_3d(m, o, event, a, b, x, y, *_):
    """Event `event` with parameters 3 (a's id), 4 (b's id), 0x16 (x) and 0x3d (y): 0x3d after it."""
    return _event(m, o, event & M32, ((3, _id(m, a), 4, 0x20), (4, _id(m, b), 4, 0x28), (0x16, x & 0xFF, 4, 0xB8),
                                      (0x3D, y & 0xFF, 1, 0x1F0)), 0x1F0)


@lifted(0x11409E4)
def event_02(m, o, b, v, *_):
    _event(m, o, 2, ((2, _id(m, b), 4, 0x18), (0xC, v, 4, 0x68)))


@lifted(0x1140D7C)
def event_01(m, o, p, *_):
    """Event 1 with parameters 2 (p+0), 0xc (p+4) and 0x12 (the u16 p+0x10 when p+4 is 1)."""
    v = m.u16(p + 0x10) if m.u32(p + 4) == 1 else 0
    _event(m, o, 1, ((2, m.u32(p), 4, 0x18), (0xC, m.u32(p + 4), 4, 0x68), (0x12, v, 4, 0x98)))


@lifted(0x173CF60)
def event_e8(m, o, b, p, *_):
    """Event 0xe8 with parameters 2 (b's id), 0x12 (u16 [p]) and 0x77 (0): whether a handler set 0x77."""
    return int(_event(m, o, 0xE8, ((2, _id(m, b), 4, 0x18), (0x12, m.u16(p), 4, 0x98), (0x77, 0, 1, 0x3C0)),
                      0x3C0) != 0)


@lifted(0x173D2DC)
def event_2e(m, o, b, p, *_):
    """Event 0x2e with parameters 3 (b's id), 0x16 (byte p+8), 0x12 (u16 [p]), 4 and 0x57 (0): the id a
    handler left in 4."""
    return _event(m, o, 0x2E, ((3, _id(m, b), 4, 0x20), (0x16, m.u16(p + 8) & 0xFF, 4, 0xB8), (0x12, m.u16(p), 4, 0x98),
                               (4, 0, 1, 0x28), (0x57, 0, 1, 0x2C0)), 0x28)


@lifted(0x2830B98)
def event_ce(m, o, b, p, *_):
    """Event 0xce with parameters 3 (b's id), 0x12 (u16 [p]) and 0x16 (byte p+8), which comes back to p+8."""
    ev_push(m, m.u64(o + 0x10))
    ev_param(m, m.u64(o + 0x10), 3, m.vcall(b, 0x98) & M32, 4, 0x20)
    ev_param(m, m.u64(o + 0x10), 0x12, m.u16(p), 4, 0x98)
    ev_param(m, m.u64(o + 0x10), 0x16, m.u16(p + 8) & 0xFF, 1, 0xB8)
    m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), 0xCE, 8, 1)
    m.put(p + 8, 1, _value(m, m.u64(o + 0x10), 0xB8))
    ev_pop(m, m.u64(o + 0x10))


@lifted(0x283126C)
def event_with_move(m, o, b, p, event, *_):
    _event(m, o, event & M32, ((3, _id(m, b), 4, 0x20), (0x12, m.u16(p), 4, 0x98), (0x16, m.u16(p + 8) & 0xFF, 4, 0xB8)))


@lifted(0x2830F0C)
def event_24(m, o, b, p, q, *_):
    _event(m, o, 0x24, ((3, _id(m, b), 4, 0x20), (0x12, m.u16(q), 4, 0x98), (0x14, m.u16(p), 4, 0xA8)))


def _ratio_param(m, ctx, kind, slot):
    """A type-3 parameter holding the ratio 4096/4096 with its bounds 0x19a and 0x20000."""
    e = _param_record(m, ctx, kind, slot)
    if e:
        m.put(e + 0xC, 4, 0x1000); m.put(e + 0x10, 4, 0x19A); m.put(e + 0x14, 4, 0x20000); m.put(e + 0x18, 8, 0)
        m.put(e + 0xA, 1, 3)


def _ptr_param(m, ctx, kind, ptr, slot):
    """A parameter that carries a pointer at +0x18 (type 0, value 0)."""
    e = _param_record(m, ctx, kind, slot)
    if e:
        m.write(e + 0xC, bytes(0xC)); m.put(e + 0x18, 8, ptr); m.put(e + 0xA, 1, 0)


@lifted(0x28374BC)
def event_1a(m, o, b, _x, kind, out, *_):
    """Event 0x1a with parameters 2 (b's id), 0xe (kind), 0x12 and 0xd (10): out = (u16 0x12, byte 0xd);
    returns whether no handler set 0x48."""
    def read(ctx):
        m.put(out, 2, _value(m, ctx, 0x98))
        m.put(out + 2, 1, _value(m, ctx, 0x70))
        return _value(m, ctx, 0x248)
    r = _event(m, o, 0x1A, ((2, _id(m, b), 4, 0x18), (0xE, kind & 0xFF, 4, 0x78), (0x12, 0, 0, 0x98),
                            (0xD, 10, 0, 0x70), (0x48, 0, 1, 0x248)), None, read)
    return int(r == 0)


@lifted(0x28380B0)
def event_1b(m, o, b, _x, v, ptr, *_):
    """Event 0x1b with parameters 2 (b's id), 0x12 (v), 0x44 (the pointer) and 0x59 (0): whether a
    handler set 0x59."""
    ev_push(m, m.u64(o + 0x10))
    ev_param(m, m.u64(o + 0x10), 2, m.vcall(b, 0x98) & M32, 4, 0x18)
    ev_param(m, m.u64(o + 0x10), 0x12, v & 0xFFFF, 4, 0x98)
    _ptr_param(m, m.u64(o + 0x10), 0x44, ptr, 0x228)
    ev_param(m, m.u64(o + 0x10), 0x59, 0, 1, 0x2D0)
    m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), 0x1B, 8, 1)
    r = _value(m, m.u64(o + 0x10), 0x2D0)
    ev_pop(m, m.u64(o + 0x10))
    return int(r != 0)


@lifted(0x157D2E4)
def event_1e(m, o, a, b, p, *_):
    """Event 0x1e with parameters 3 (a's id), 4 (b's id), 0x12 (u16 [p]) and 0x59 (0): whether a handler
    set 0x59."""
    return int(_event(m, o, 0x1E, ((3, _id(m, a), 4, 0x20), (4, _id(m, b), 4, 0x28), (0x12, m.u16(p), 4, 0x98),
                                   (0x59, 0, 1, 0x2D0)), 0x2D0) != 0)


@lifted(0x172A19C)
def event_06(m, o, b, p, out1, out2, *_):
    """Event 6 with parameters 3 (b's id), 0xd (byte [p]), 0x59 and 0x78 (0): out1/out2 = 0x59/0x78 set,
    [p] = 0xd."""
    def read(ctx):
        m.put(out1, 1, int(_value(m, ctx, 0x2D0) != 0))
        m.put(out2, 1, int(_value(m, ctx, 0x3C8) != 0))
        m.put(p, 1, _value(m, ctx, 0x70))
    _event(m, o, 6, ((3, _id(m, b), 4, 0x20), (0xD, m.u8(p), 1, 0x70), (0x59, 0, 1, 0x2D0), (0x78, 0, 0, 0x3C8)),
           None, read)


def _targets(m, lst, first=6):
    """Parameters first+i (the target ids) for the list of battlers at lst (count byte +0xa6)."""
    return tuple((first + i, _id(m, m.u64(lst + 8 * i)), 4, 8 * (first + i) + 8) for i in range(m.u8(lst + 0xA6)))


@lifted(0x2831890)
def event_04(m, o, b, v, flag, p, *_):
    _event(m, o, 4, ((2, _id(m, b), 4, 0x18), (0x12, v & 0xFFFF, 4, 0x98), (0x59, flag & 1, 4, 0x2D0),
                     (0x71, (m.u32(p + 4) >> 3) & 1, 4, 0x390)))


@lifted(0x114020C)
def event_0f(m, o, b, v, *_):
    """Event 0xf with parameters 2 (b's id), 0x11 (b's vf 0x4a8) and 0x12 (v): 0x11 after it."""
    f = m.vcall(b, 0x4A8) & 0xFF
    return _event(m, o, 0xF, ((2, _id(m, b), 4, 0x18), (0x11, f, 1, 0x90), (0x12, v & 0xFFFF, 0, 0x98)), 0x90)


@lifted(0x283292C)
def event_1c(m, o, b, v, lst, out_a, out_b, *_):
    """Event 0x1c with parameters 0x12 (v), 3 (b's id), 5 (target count), 6.. (the targets), 2 and 4 (0):
    out_a/out_b = 2/4 after it; returns whether 2 is set."""
    def read(ctx):
        m.put(out_a, 4, _value(m, ctx, 0x18))
        m.put(out_b, 4, _value(m, ctx, 0x28))
    _event(m, o, 0x1C, ((0x12, v & 0xFFFF, 4, 0x98), (3, _id(m, b), 4, 0x20), (5, m.u8(lst + 0xA6), 4, 0x30))
           + _targets(m, lst) + ((2, 0, 1, 0x18), (4, 0, 0, 0x28)), None, read)
    return int(m.u32(out_a) != 0)


@lifted(0x157A86C)
def put_u16(m, p, v, *_):
    m.put(p, 2, v)


@lifted(0x157A070)
def event_26(m, o, p2, b, mv, lst, out, *_):
    """Event 0x26 with parameters 3 and 2 (b's id), 0x12/0x16 (the move u16 [mv] and byte mv+8), 0x6f/0x71
    (bits 1 and 3 of p2+4), 5 and 6.. (the targets), 0x43 and 0x13 (0): returns 0x43; a nonzero 0x13 goes
    to [out]."""
    flags = m.u32(p2 + 4)
    def read(ctx):
        return _value(m, ctx, 0x220), _value(m, ctx, 0xA0)
    r, v = _event(m, o, 0x26, ((3, _id(m, b), 4, 0x20), (2, _id(m, b), 4, 0x18), (0x12, m.u16(mv), 4, 0x98),
                               (0x16, m.u16(mv + 8) & 0xFF, 4, 0xB8), (0x6F, (flags >> 1) & 1, 4, 0x380),
                               (0x71, (flags >> 3) & 1, 4, 0x390), (5, m.u8(lst + 0xA6), 4, 0x30))
                  + _targets(m, lst) + ((0x43, 0, 1, 0x220), (0x13, 0, 1, 0xA0)), None, read)
    if v & 0xFFFF:
        m.call_void(m.main + 0x157A86C, out, v)
    return r


def _move_targets_event(event):
    def fn(m, o, mv, b, lst, *_):
        """Event with parameters 3 (b's id), 0x12/99 (the move u16 [mv] and byte mv+0xb), 5 and 6.. (the
        targets)."""
        _event(m, o, event, ((3, _id(m, b), 4, 0x20), (0x12, m.u16(mv), 4, 0x98), (99, m.u8(mv + 0xB), 4, 0x320),
                             (5, m.u8(lst + 0xA6), 4, 0x30)) + _targets(m, lst))
    return fn


lifted(0x157D6F4)(_move_targets_event(0x33))
lifted(0x157DBAC)(_move_targets_event(0x35))


@lifted(0x1578F08)
def event_move_flags(m, o, ident, v, p, event, *_):
    """Event `event` with parameters 2 (ident), 0x12 (v) and 0x6f..0x72 (bits 1, 2, 3 and 0 of p+4)."""
    f = m.u32(p + 4)
    _event(m, o, event & M32, ((2, ident, 4, 0x18), (0x12, v & 0xFFFF, 4, 0x98), (0x6F, (f >> 1) & 1, 4, 0x380),
                               (0x70, (f >> 2) & 1, 4, 0x388), (0x71, (f >> 3) & 1, 4, 0x390), (0x72, f & 1, 4, 0x398)))


@lifted(0x157E558)
def event_3c(m, o, a, b, mv, *_):
    """Event 0x3c with parameters 3 (a's id), 4 (b's id), 0x12/99 (the move) and 0x59 (0): whether a
    handler set 0x59."""
    return int(_event(m, o, 0x3C, ((3, _id(m, a), 4, 0x20), (4, _id(m, b), 4, 0x28), (0x12, m.u16(mv), 4, 0x98),
                                   (99, m.u8(mv + 0xB), 4, 0x320), (0x59, 0, 1, 0x2D0)), 0x2D0) != 0)


def _targets_until_null(m, lst, first=6):
    """Like _targets, stopping at the first empty entry."""
    out = []
    for i in range(m.u8(lst + 0xA6)):
        b = m.u64(lst + 8 * i)
        if b == 0:
            break
        out.append((first + i, _id(m, b), 4, 8 * (first + i) + 8))
    return tuple(out)


@lifted(0x1605888)
def event_69(m, o, b, x, v, lst, *_):
    """Event 0x69 with parameters 5 and 6.. (the targets), 3 (b's id), 0x12 (v), 0x18 (x) and 0x23 (1):
    0x23 after it."""
    return _event(m, o, 0x69, ((5, m.u8(lst + 0xA6), 4, 0x30),) + _targets_until_null(m, lst)
                  + ((3, _id(m, b), 4, 0x20), (0x12, v & 0xFFFF, 4, 0x98), (0x18, x & 0xFF, 4, 0xC8), (0x23, 1, 0, 0x120)),
                  0x120)


@lifted(0x282EB24)
def event_damage_scale(m, o, event, a, b, mv, *_):
    """Event `event` with parameters 3 (a's id), 4 (b's id), 0x12/0x1b (the move u16 [mv] and byte mv+9),
    0x2e (field 6 of the move) and the ratio 0x38 (4096 within 0x19a..0x20000): returns 0x2e * 0x38 / 4096,
    rounded half down."""
    with m.frame(0x10) as k:
        m.put(k, 8, m.u64(m.main + 0x46DDAD8) + 0x10); m.put(k + 8, 2, m.u16(mv))
        f = m.call(m.main + 0x13B1F10, k)
    ev_push(m, m.u64(o + 0x10))
    for kind, value, typ, slot in ((3, _id(m, a), 4, 0x20), (4, _id(m, b), 4, 0x28), (0x12, lambda: m.u16(mv), 4, 0x98),
                                   (0x1B, lambda: m.u8(mv + 9), 4, 0xE0), (0x2E, lambda: f & 0xFFFF, 1, 0x178)):
        ev_param(m, m.u64(o + 0x10), kind, value() & M32, typ, slot)
    e = _param_record(m, m.u64(o + 0x10), 0x38, 0x1C8)
    if e:
        m.put(e + 0xC, 4, 0x1000); m.put(e + 0x10, 4, 0x19A); m.put(e + 0x14, 4, 0x20000); m.put(e + 0x18, 8, 0)
        m.put(e + 0xA, 1, 3)
    m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), event & M32, 8, 1)
    ctx = m.u64(o + 0x10)
    x, y = _value(m, ctx, 0x178), _value(m, ctx, 0x1C8)
    ev_pop(m, ctx)
    p = (x * y) & M32
    return (p >> 12) + int(p & 0xFFF > 0x800)


@lifted(0x173E018)
def event_30(m, o, b, mv, ident, out, *_):
    """Event 0x30 with parameters 3 (b's id), 0x16/0x12 (the move), 0x62, 0x61 (0) and 4 (ident): [out] =
    0x62; returns 4 when a handler changed it, else 0."""
    def read(ctx):
        m.put(out, 1, _value(m, ctx, 0x318))
        return _value(m, ctx, 0x28)
    r = _event(m, o, 0x30, ((3, _id(m, b), 4, 0x20), (0x16, m.u16(mv + 8) & 0xFF, 4, 0xB8), (0x12, m.u16(mv), 4, 0x98),
                            (0x62, 0, 0, 0x318), (0x61, 0, 0, 0x310), (4, ident, 0, 0x28)), None, read)
    return r if r != ident & M32 else 0


@lifted(0x173DB88)
def event_31(m, o, b, v, mv, f, *_):
    _event(m, o, 0x31, ((3, _id(m, b), 4, 0x20), (4, v & 0xFFFF, 4, 0x28), (0x16, m.u16(mv + 8) & 0xFF, 4, 0xB8),
                        (0x12, m.u16(mv), 4, 0x98), (0x62, f & 0xFF, 4, 0x318)))


@lifted(0x2833DE4)
def event_a8(m, o, b, mv, lst, *_):
    _event(m, o, 0xA8, ((3, _id(m, b), 4, 0x20), (0x12, m.u16(mv), 4, 0x98), (0x16, m.u16(mv + 8) & 0xFF, 4, 0xB8),
                        (5, m.u8(lst + 0xA6), 4, 0x30)) + _targets(m, lst))


def _pair_move_event(event):
    def fn(m, o, a, b, mv, *_):
        """Event with parameters 3 (a's id), 4 (b's id) and 0x12/0x16 (the move u16 [mv] and byte mv+8)."""
        _event(m, o, event, ((3, _id(m, a), 4, 0x20), (4, _id(m, b), 4, 0x28), (0x12, m.u16(mv), 4, 0x98),
                             (0x16, m.u16(mv + 8) & 0xFF, 4, 0xB8)))
    return fn


lifted(0x1535060)(_pair_move_event(0x5B))
lifted(0x153485C)(_pair_move_event(0x5C))


@lifted(0x2837164)
def event_46(m, o, mv, a, b, *_):
    _event(m, o, 0x46, ((3, _id(m, a), 4, 0x20), (4, _id(m, b), 4, 0x28), (99, m.u8(mv + 0xB), 4, 0x320)))


@lifted(0x174FB1C)
def event_3e(m, o, a, b, mv, *_):
    """Event 0x3e with parameters 3 (a's id), 4 (b's id), 0x16 (byte mv+8) and 0x59 (0): whether a handler
    set 0x59."""
    return int(_event(m, o, 0x3E, ((3, _id(m, a), 4, 0x20), (4, _id(m, b), 4, 0x28), (0x16, m.u8(mv + 8), 4, 0xB8),
                                   (0x59, 0, 1, 0x2D0)), 0x2D0) != 0)


@lifted(0x153391C)
def event_d4(m, o, b, mv, *_):
    """Event 0xd4 with parameters 3 (b's id), 0x12 (u16 [mv]) and 0x59 (0): whether a handler set 0x59."""
    return int(_event(m, o, 0xD4, ((3, _id(m, b), 4, 0x20), (0x12, m.u16(mv), 4, 0x98), (0x59, 0, 1, 0x2D0)),
                      0x2D0) != 0)


@lifted(0x1533EF0)
def event_67_68(m, o, b, mv, x, *_):
    """Event 0x67 with parameters 3 (b's id), 0x12/0x16 (the move), 0x35 (x) and 0x4f (0); unless a handler
    set 0x4f, event 0x68 on the same parameters."""
    ev_push(m, m.u64(o + 0x10))
    for kind, value, typ, slot in ((3, _id(m, b), 4, 0x20), (0x12, lambda: m.u16(mv), 4, 0x98),
                                   (0x16, lambda: m.u16(mv + 8) & 0xFF, 4, 0xB8), (0x35, lambda: x, 4, 0x1B0),
                                   (0x4F, lambda: 0, 1, 0x280)):
        ev_param(m, m.u64(o + 0x10), kind, value() & M32, typ, slot)
    m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), 0x67, 8, 1)
    if _value(m, m.u64(o + 0x10), 0x280) == 0:
        m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), 0x68, 8, 1)
    ev_pop(m, m.u64(o + 0x10))


@lifted(0x1145270)
def event_a3(m, o, b, x, y, *_):
    """Event 0xa3 with parameters 2 (b's id), 0x3e (x), 0x48 (0) and 0x35 (y): 0x35 after it, or 0 when a
    handler set 0x48."""
    def read(ctx):
        return _value(m, ctx, 0x1B0), _value(m, ctx, 0x248)
    r, stop = _event(m, o, 0xA3, ((2, _id(m, b), 4, 0x18), (0x3E, x & 0xFF, 4, 0x1F8), (0x48, 0, 1, 0x248),
                                  (0x35, y, 0, 0x1B0)), None, read)
    return 0 if stop & 0xFF else r


@lifted(0x153570C)
def event_8c(m, o, key, b, *_):
    """Event 0x8c with parameters 3 (b's id), 0x28 (field 13 of record `key`), 0x4c, 0x48 and 0x29 (0): the
    chance (0x29, or the field when set), doubled when 0x4c is set; 0 when 0x48 is set and the field is."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    f = fb.u8(m, m.call(m.main + 0xBF60CC, table, key & M32), 13)
    def read(ctx):
        return _value(m, ctx, 0x248), _value(m, ctx, 0x268), _value(m, ctx, 0x150)
    a, c, v = _event(m, o, 0x8C, ((3, _id(m, b), 4, 0x20), (0x28, f, 4, 0x148), (0x4C, 0, 1, 0x268),
                                  (0x48, 0, 1, 0x248), (0x29, 0, 0, 0x150)), None, read)
    if f:
        v = f
    if a == 0 or f == 0:
        return (v << int(c != 0)) & M32
    return 0


@lifted(0x1534C4C)
def event_8d(m, o, b, x, *_):
    """Event 0x8d with parameters 4 (b's id), 0x29 (x) and 0x48 (0): unless a handler set 0x48 or the rule
    bit 21 of +0x498 is set, a roll below 0x29 percent."""
    def read(ctx):
        return _value(m, ctx, 0x150), _value(m, ctx, 0x248)
    v, stop = _event(m, o, 0x8D, ((4, _id(m, b), 4, 0x28), (0x29, x, 0, 0x150), (0x48, 0, 1, 0x248)), None, read)
    if stop == 0 and v and not (m.u64(m.u64(m.u64(o + 8) + 0x38) + 0x498) >> 21) & 1:
        return m.call(m.main + 0x114DA8C, m.u64(m.u64(o + 0x18) + 0x10), v)
    return 0


@lifted(0x1582144)
def event_4f(m, o, mv, b, *_):
    """Event 0x4f with parameters 3 (b's id), 0x12/0x16 (the move) and 0x59 (0): whether a handler set
    0x59."""
    return int(_event(m, o, 0x4F, ((3, _id(m, b), 0, 0x20), (0x12, m.u16(mv), 0, 0x98), (0x16, m.u16(mv + 8) & 0xFF, 0, 0xB8),
                                   (0x59, 0, 1, 0x2D0)), 0x2D0) != 0)


@lifted(0x1794B18)
def event_81(m, o, kind, a, b, ptr, *_):
    _event(m, o, 0x81, ((3, _id(m, a), 4, 0x20), (4, _id(m, b), 4, 0x28), (0x44, ptr, "ptr", 0x228),
                        (0x1E, kind & 0xFFFF, 4, 0xF8)))


@lifted(0x1794F10)
def event_82(m, o, a, b, kind, ptr, *_):
    _event(m, o, 0x82, ((3, _id(m, a), 4, 0x20), (4, _id(m, b), 4, 0x28), (0x1E, kind & 0xFFFF, 4, 0xF8),
                        (0x1F, ptr, "ptr", 0x100)))


@lifted(0x13836DC)
def event_7f(m, o, b, v, stat, amount, *_):
    _event(m, o, 0x7F, ((3, _id(m, b), 4, 0x20), (0x12, v & 0xFFFF, 4, 0x98), (0x22, stat & 0xFF, 4, 0x118),
                        (0x23, amount, 4, 0x120)))


def _amount_event(event):
    def fn(m, o, b, x, *_):
        """Event with parameters 2 (b's id) and 0x35 (x)."""
        _event(m, o, event, ((2, _id(m, b), 4, 0x18), (0x35, x, 4, 0x1B0)))
    return fn


lifted(0x1152AE8)(_amount_event(0xA5))
lifted(0x1152DA8)(_amount_event(0xA6))


@lifted(0x114B630)
def event_8b(m, o, b, kind, x, *_):
    """Event 0x8b with parameters 2 (b's id), 0x1e (kind) and 0x35 (x): 0x35 after it."""
    return _event(m, o, 0x8B, ((2, _id(m, b), 4, 0x18), (0x1E, kind & 0xFFFF, 4, 0xF8), (0x35, x, 0, 0x1B0)), 0x1B0)


@lifted(0x114B9A4)
def event_a4(m, o, b, _x, v, *_):
    """Event 0xa4 with parameters 4 (b's id), 0x69 (v) and 0x59 (1): whether 0x59 is still set."""
    return int(_event(m, o, 0xA4, ((4, _id(m, b), 4, 0x28), (0x69, v & 0xFF, 4, 0x350), (0x59, 1, 1, 0x2D0)),
                      0x2D0) != 0)


@lifted(0x13618AC)
def event_cf(m, o, b, *_):
    _event(m, o, 0xCF, ((2, _id(m, b), 0, 0x18),))


@lifted(0x114F6FC)
def event_ec(m, o, ident, out, *_):
    """Event 0xec with parameters 2 (ident), 0x7c, 0x7d and 0x7e (0): out = the u16s 0x7d and 0x7e; returns
    0x7c."""
    def read(ctx):
        r = _value(m, ctx, 0x3E8)
        m.put(out, 2, _value(m, ctx, 0x3F0)); m.put(out + 2, 2, _value(m, ctx, 0x3F8))
        return r
    return _event(m, o, 0xEC, ((2, ident, 4, 0x18), (0x7C, 0, 0, 0x3E8), (0x7D, 0, 1, 0x3F0), (0x7E, 0, 1, 0x3F8)),
                  None, read)


@lifted(0x2836F48)
def event_dd(m, o, ident, *_):
    _event(m, o, 0xDD, ((2, ident, 0, 0x18),))


@lifted(0x157FDB0)
def event_28(m, o, _x, p, *_):
    """event_move_flags 0x28 on 0x1146e90(o) for the record p (id +0, move u16 +4, flags [p+8])."""
    return event_move_flags(m, m.call(m.main + 0x1146E90, o), m.u32(p), m.u16(p + 4), m.u64(p + 8), 0x28)


@lifted(0x2836708)
def event_ca(m, o, b, v, *_):
    """Event 0xca with parameters 3 (b's id), 0x12 (v) and 0x78 (0): whether a handler set 0x78."""
    return int(_event(m, o, 0xCA, ((3, _id(m, b), 0, 0x20), (0x12, v & 0xFFFF, 0, 0x98), (0x78, 0, 0, 0x3C8)),
                      0x3C8) != 0)


@lifted(0x1946418)
def event_ed(m, o, b, *_):
    """Event 0xed with parameters 3 (b's id) and 0x5f (0x83): 0x5f after it."""
    return _event(m, o, 0xED, ((3, _id(m, b), 4, 0x20), (0x5F, 0x83, 1, 0x300)), 0x300)


@lifted(0x158097C)
def event_3d(m, o, b, f, *_):
    _event(m, o, 0x3D, ((2, _id(m, b), 4, 0x18), (0x54, f & 1, 4, 0x2A8)))


@lifted(0x1581494)
def event_4e(m, o, b, mv, *_):
    """Event 0x4e with parameters 3 (b's id), 0x12 (u16 [mv]) and 0x59 (0): whether a handler set 0x59."""
    return int(_event(m, o, 0x4E, ((3, _id(m, b), 0, 0x20), (0x12, m.u16(mv), 0, 0x98), (0x59, 0, 1, 0x2D0)),
                      0x2D0) != 0)


@lifted(0x28384CC)
def event_23(m, o, b, v, kind, *_):
    _event(m, o, 0x23, ((2, _id(m, b), 4, 0x18), (0x12, v & 0xFFFF, 4, 0x98), (0x25, kind & 0xFF, 4, 0x130)))


@lifted(0x2834C3C)
def event_eb(m, o, ptr, a, b, v, *_):
    _event(m, o, 0xEB, ((3, _id(m, a), 4, 0x20), (4, _id(m, b), 4, 0x28), (0x12, v & 0xFFFF, 4, 0x98),
                        (0x44, ptr, "ptr", 0x228)))


@lifted(0x288B67C)
def event_eb_text(m, o, text, a, b, v, *_):
    """Start the text record (kind 2, 0x82) with b's id, then event 0xeb carrying it."""
    m.call_void(m.main + 0x2843244, text, 2, 0x82)
    m.call_void(m.main + 0x284325C, text, m.vcall(b, 0x98) & M32)
    return _tail(m, m.main + 0x2834C3C, m.call(m.main + 0x1146E90, o), text, a, b, v)


@lifted(0x13831EC)
def event_78(m, o, ident, i, b, c, pb, pv, *_):
    """[pb] = 0x17710a4(ident, i, pv); event 0x78 with parameters 3/4 (b's and c's ids), 0x22 ([pb]), 0x23
    ([pv]) and 0x38 (1) writes 0x22 and 0x23 back, 0x23 times a 0x38 above 1."""
    m.put(pb, 1, m.call(m.main + 0x17710A4, ident, i, pv))
    def read(ctx):
        m.put(pb, 1, _value(m, ctx, 0x118))
        v = _value(m, ctx, 0x120)
        m.put(pv, 4, v)
        rec = m.u64(m.u64(ctx + 0x78) + 0x1C8)
        if rec and m.u8(rec + 0xC) > 1:
            m.put(pv, 4, m.u8(rec + 0xC) * v)
    _event(m, o, 0x78, ((3, _id(m, b), 4, 0x20), (4, _id(m, c), 4, 0x28), (0x22, m.u8(pb), 0, 0x118),
                        (0x23, lambda: m.u32(pv), 0, 0x120), (0x38, 1, 0, 0x1C8)), None, read)


@lifted(0x1383AD8)
def event_6c(m, o, mv, a, b, *_):
    """Event 0x6c with parameters 3/4 (a's and b's ids), 0x12 (u16 [mv]), 0x48 (0) and 0x29 (the move's
    chance): unless a handler set 0x48 or rule bit 5 of +0x49a is set, a roll below 0x29 percent."""
    pct = m.call(m.main + 0x1384028, m.u16(mv), 0)
    def read(ctx):
        return _value(m, ctx, 0x248), _value(m, ctx, 0x150)
    stop, v = _event(m, o, 0x6C, ((3, _id(m, a), 4, 0x20), (4, _id(m, b), 4, 0x28), (0x12, m.u16(mv), 4, 0x98),
                                  (0x48, 0, 1, 0x248), (0x29, pct, 0, 0x150)), None, read)
    if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49A) & 0x20 or stop & 0xFF:
        return 0
    return m.call(m.main + 0x114DA8C, m.u64(m.u64(o + 0x18) + 0x10), v) & 1


@lifted(0x283955C)
def event_b9(m, o, a, b, mv, *_):
    """Event 0xb9 with parameters 3/4 (a's and b's ids), 0x12 (mv) and 0x38 (0): b's max HP (vf 0x140)
    times the ratio 0x38 / 4096 (rounded half down) or, unset, the move's percent of it; at least 1,
    at most the max HP."""
    pct = m.call(m.main + 0x20FB1A8, mv & M32)
    r = _event(m, o, 0xB9, ((3, _id(m, a), 4, 0x20), (4, _id(m, b), 4, 0x28), (0x12, mv & 0xFFFF, 4, 0x98),
                            (0x38, 0, 0, 0x1C8)), 0x1C8)
    hp = m.vcall(b, 0x140) & 0xFFFF
    if r:
        x = (r * hp) & M32
        v = (x >> 12) + int(x & 0xFFF > 0x800)
    else:
        v = m.call(m.main + 0x1533CA0, hp, pct) & M32
    if v == 0:
        return 1
    return min(v, hp)


@lifted(0x1144194)
def event_13(m, o, b, flag, *_):
    """Event 0x13 with parameters 2 (b's id), 0x32 (b's vf 0x190), 0x59 (1), 0x51 (0) and the ratio 0x38:
    0x32 scaled by 0x38 (and, for a form-1 battler with 0x59 still set, by 0x11521a0's percent), capped
    at 10000; with `flag` and 0x51 set, 10000 minus it."""
    w = m.vcall(b, 0x190) & 0xFFFF
    def read(ctx):
        x = (_value(m, ctx, 0x198) * _value(m, ctx, 0x1C8)) & M32
        v = (x >> 12) + int(x & 0xFFF > 0x800)
        if m.vcall(b, 0x230) & 0xFFFF == 1 and _value(m, ctx, 0x2D0):
            n = m.vcall(m.call(m.main + 0x11521A0, o), 0x68, m.main + 0x3C69EE0)
            v = ((n * v) & M32) // 100
        r = v if v >> 4 < 0x271 else 10000
        if flag & 1 and _value(m, ctx, 0x290):
            r = (10000 - r) & M32
        return r
    return _event(m, o, 0x13, ((2, _id(m, b), 4, 0x18), (0x32, w, 4, 0x198), (0x59, 1, 0, 0x2D0), (0x51, 0, 0, 0x290),
                               (0x38, 0, "ratio", 0x1C8)), None, read)


@lifted(0x113EFD0)
def event_11(m, o, key, b, *_):
    """Event 0x11 with parameters 3 (b's id), 0x12 (move `key`), 0x16 (its field 2) and 0x19 (its s8 field 8
    plus 7): 0x19 after it."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    rec = m.call(m.main + 0xBF60CC, table, key & M32)
    off = fb.field(m, rec, 8)
    s = m.s(rec + off, 1) if off else 0
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    t = fb.u8(m, m.call(m.main + 0xBF60CC, table, key & M32), 2)
    return _event(m, o, 0x11, ((3, _id(m, b), 4, 0x20), (0x12, key & 0xFFFF, 4, 0x98), (0x16, t, 4, 0xB8),
                               (0x19, (s + 7) & M32, 0, 0xD0)), 0xD0)


@lifted(0x14826C0)
def event_with_targets(m, o, b, v, event, p, lst, *_):
    """Event `event` with parameters 0x12 (v), 2 (b's id), 0x19/0x1b (u32 p+0xc and byte p+9, 0 without p),
    0x25 (0), 5 and 6.. (the targets, none without lst) and, with p, 0x16 (byte p+8): 0x25 after it."""
    params = ((0x12, v & 0xFFFF, 4, 0x98), (2, _id(m, b), 4, 0x18), (0x19, m.u32(p + 0xC) if p else 0, 4, 0xD0),
              (0x1B, m.u8(p + 9) if p else 0, 4, 0xE0), (0x25, 0, 1, 0x130), (5, m.u8(lst + 0xA6) if lst else 0, 4, 0x30))
    if lst:
        params += _targets(m, lst)
    if p:
        params += ((0x16, m.u8(p + 8), 4, 0xB8),)
    return _event(m, o, event & M32, params, 0x130)


@lifted(0x1536CF4)
def event_8e(m, o, b, *_):
    _event(m, o, 0x8E, ((2, _id(m, b), 0, 0x18),))


@lifted(0x16D9D10)
def events_62_66(m, o, a, b, mv, x, y, f1, f2, *_):
    """Events 0x62..0x66 in turn on one frame: parameters 3/4 (a's and b's ids), 0x14/0x12/0x16/0x1b/99
    (the move record: u16 +2, u16 +0, byte +8, byte +9, byte +0xb), 0x3d (x), 0x35 (y), 0x4c/0x4d (the
    flags) and 0x4e (0)."""
    def raise_rest(ctx):
        for event in (99, 100, 0x65, 0x66):
            m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), event, 8, 1)
    _event(m, o, 0x62, ((3, _id(m, a), 4, 0x20), (4, _id(m, b), 4, 0x28), (0x14, m.u16(mv + 2), 4, 0xA8),
                        (0x12, m.u16(mv), 4, 0x98), (0x3D, x & 0xFF, 4, 0x1F0), (0x16, m.u16(mv + 8) & 0xFF, 4, 0xB8),
                        (0x1B, m.u8(mv + 9), 4, 0xE0), (0x35, y, 4, 0x1B0), (0x4C, f1 & 1, 4, 0x268),
                        (0x4D, f2 & 1, 4, 0x270), (99, m.u8(mv + 0xB), 4, 0x320), (0x4E, 0, 1, 0x278)), None, raise_rest)


@lifted(0x19B3E28)
def event_cc_cd(m, o, mv, b, lst, out, *_):
    """Event 0xcc (0xcd when 0x19b445c(lst) is false) with parameters 3 (b's id), 5 and 6.. (the targets),
    0x59/0x47 (1), 0x78 (0) and 0x12 (u16 [mv]): [out] = 0x59 still set; returns 0x78 set."""
    ev_push(m, m.u64(o + 0x10))
    ev_param(m, m.u64(o + 0x10), 3, m.vcall(b, 0x98) & M32, 4, 0x20)
    c = m.call(m.main + 0x19B445C, lst) & 0xFF
    for kind, value, typ, slot in ((5, lambda: m.u8(lst + 0xA6), 4, 0x30),
                                   (0x59, lambda: 1, 1, 0x2D0), (0x47, lambda: 1, 1, 0x240), (0x78, lambda: 0, 0, 0x3C8)) \
            + _targets(m, lst) + ((0x12, lambda: m.u16(mv), 4, 0x98),):
        ev_param(m, m.u64(o + 0x10), kind, value() & M32, typ, slot)
    m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), 0xCC if c else 0xCD, 8, 1)
    ctx = m.u64(o + 0x10)
    m.put(out, 1, int(_value(m, ctx, 0x2D0) != 0))
    r = _value(m, ctx, 0x3C8)
    ev_pop(m, ctx)
    return int(r != 0)


@lifted(0x282D080)
def event_2c(m, o, move, move2, x, b, lst, p, *_):
    """Event 0x2c over the move record p: parameters 2 (b's id), 0x12 (move), 0x16/0x1d/0x1b/99/0x1c/0x6d/
    0x7a (the record's bytes +8, u16 +6, +9, +0xb, +0xa, +0x12, +0x13), 5 and 6.. (the targets); the record
    is rewritten from what comes back, with move, move2 and x at +0, +2 and +0xc."""
    def read(ctx):
        return (_value(m, ctx, 0xB8), _value(m, ctx, 0xF0), _value(m, ctx, 0xE0), _value(m, ctx, 0xE8),
                _value(m, ctx, 0x320), _value(m, ctx, 0x370), _value(m, ctx, 0x3D8))
    v16, v1d, v1b, v1c, v63, v6d, v7a = _event(m, o, 0x2C, (
        (2, _id(m, b), 4, 0x18), (0x12, move & 0xFFFF, 4, 0x98), (0x16, m.u8(p + 8), 1, 0xB8), (0x1D, m.u16(p + 6), 0, 0xF0),
        (0x1B, m.u8(p + 9), 0, 0xE0), (99, m.u8(p + 0xB), 0, 0x320), (0x1C, m.u8(p + 0xA), 0, 0xE8),
        (0x6D, m.u8(p + 0x12), 0, 0x370), (0x7A, m.u8(p + 0x13), 1, 0x3D8), (5, m.u8(lst + 0xA6), 4, 0x30))
        + _targets(m, lst), None, read)
    m.put(p, 2, move); m.put(p + 2, 2, move2); m.put(p + 8, 1, v16); m.put(p + 6, 2, v1d); m.put(p + 9, 1, v1b)
    m.put(p + 0xB, 1, int(v63 != 0)); m.put(p + 0xA, 1, v1c); m.put(p + 0x12, 1, int(v6d != 0)); m.put(p + 0xC, 4, x)
    m.put(p + 0x13, 1, int(v7a != 0))


@lifted(0x157C844)
def event_hit_check(m, o, mv, a, b, levels, event, o1, o2, o3, o4, text, *_):
    """Event `event` for a hit by a on b: the text record `text` cleared and passed as 0x44, parameters 3/4
    the ids, 0x12/0x16/0x19/0x1c/0x55 from the move record (u16 +0, byte +8, u32 +0xc, byte +0xa, byte
    +0x10), 0x3d b's effectiveness level from the ten (id, level) pairs at `levels` (14 when absent) and
    0x47/0x59/0x75/0x76 (0), which come back as the bytes o1..o4."""
    m.write(text, bytes(0x24))
    ident = m.vcall(b, 0x98) & M32
    lvl = 0xE
    for i in range(10):
        if m.u32(levels + 8 * i) == ident:
            lvl = m.u8(levels + 8 * i + 4)
            break
    def read(ctx):
        for out, slot in ((o1, 0x240), (o2, 0x2D0), (o3, 0x3B0), (o4, 0x3B8)):
            m.put(out, 1, int(_value(m, ctx, slot) != 0))
    _event(m, o, event & M32, ((3, _id(m, a), 4, 0x20), (4, _id(m, b), 4, 0x28), (0x12, m.u16(mv), 4, 0x98),
                               (0x16, m.u16(mv + 8) & 0xFF, 4, 0xB8), (0x19, m.u32(mv + 0xC), 4, 0xD0),
                               (0x1C, m.u16(mv + 0xA) & 0xFF, 4, 0xE8), (0x55, m.u16(mv + 0x10) & 0xFF, 4, 0x2B0),
                               (0x44, text, "ptr", 0x228), (0x3D, lvl, 4, 0x1F0), (0x47, 0, 1, 0x240),
                               (0x59, 0, 1, 0x2D0), (0x75, 0, 1, 0x3B0), (0x76, 0, 1, 0x3B8)), None, read)


@lifted(0x1583930)
def event_a9(m, o, b, lst, flags, mv, f1, single, event, *_):
    """Damage dealt by b's move: parameters 3 (b's id), 0x54 (f1), 0x12/0x16/0x1b/99 (the move record),
    0x6e (bit 0 of flags+4); then each target that took damage (flag +0x84 of its first entry: 1, or
    nonzero without `single`) becomes parameter 6.. and adds its damage (u16 +0x58, plus +0x6e without
    `single`). With any: 5 (their count), 0x4e/0x4f (0) and 0x35 (the sum) for event 0xa9, then `event`
    unless a handler set 0x4f."""
    ev_push(m, m.u64(o + 0x10))
    for kind, value, typ, slot in ((3, _id(m, b), 4, 0x20), (0x54, lambda: f1 & 1, 4, 0x2A8),
                                   (0x12, lambda: m.u16(mv), 4, 0x98), (0x16, lambda: m.u16(mv + 8) & 0xFF, 4, 0xB8),
                                   (0x1B, lambda: m.u8(mv + 9), 4, 0xE0), (99, lambda: m.u8(mv + 0xB), 4, 0x320),
                                   (0x6E, lambda: m.u32(flags + 4) & 1, 4, 0x378)):
        ev_param(m, m.u64(o + 0x10), kind, value() & M32, typ, slot)
    n = m.u8(lst + 0xA6)
    total = 0
    k = 0
    for i in range(n):
        cnt = m.u8(lst + 0xA6)
        t = m.u64(lst + 8 * i) if i < cnt else 0
        for j in range(cnt):
            hit = m.u8(lst + 0x84 + j)
            if m.u64(lst + 8 * j) == t and (hit == 1 if single & 1 else hit != 0):
                total += m.u16(lst + 0x58 + 2 * j) + (0 if single & 1 else m.u16(lst + 0x6E + 2 * j))
                ev_param(m, m.u64(o + 0x10), 6 + k, m.vcall(t, 0x98) & M32, 4, 8 * (6 + k) + 8)
                k += 1
                break
    if k:
        for kind, value, typ, slot in ((5, k, 4, 0x30), (0x4E, 0, 1, 0x278), (0x4F, 0, 1, 0x280),
                                       (0x35, total & M32, 4, 0x1B0)):
            ev_param(m, m.u64(o + 0x10), kind, value, typ, slot)
        m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), 0xA9, 8, 1)
        if _value(m, m.u64(o + 0x10), 0x280) == 0:
            m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), event & M32, 8, 1)
    ev_pop(m, m.u64(o + 0x10))


@lifted(0x173C1F4)
def events_30_31(m, o, b, mv, ident, out, *_):
    """Event 0x30 then 0x31 for b's move: returns 0x30's id (byte), [out] = its flag set."""
    with m.frame(0x10) as f:
        m.put(f, 1, 0)
        r = m.call(m.main + 0x173E018, m.u64(o + 0x38), b, mv, ident, f) & 0xFF
        m.call_void(m.main + 0x173DB88, m.u64(o + 0x38), b, r, mv, m.u8(f))
        m.put(out, 1, int(m.u8(f) != 0))
        return r


@lifted(0x174FF2C)
def event_3f(m, o, a, b, *_):
    _event(m, o, 0x3F, ((3, _id(m, a), 4, 0x20), (4, _id(m, b), 4, 0x28)))


@lifted(0x172A670)
def event_07(m, o, b, *_):
    _event(m, o, 7, ((3, _id(m, b), 4, 0x20),))


@lifted(0x1605670)
def event_69_for(m, o, b, x, lst, *_):
    """b's vf 0x700(x) kind (4 = none): event 0x69 for it, the 0x1605774 check, vf 0x6e0 on b's own battler
    and queue 7 (id, kind); returns the check's result."""
    k = m.vcall(b, 0x700, x) & M32
    if k & 0xFF == 4:
        return 0
    r = m.call(m.main + 0x1605888, m.u64(o + 0x38), b, k, x & M32, lst)
    with m.frame(0x20) as f:
        m.put(f + 8, 8, b); m.put(f + 0x10, 1, k); m.put(f + 0x11, 1, r); m.put(f, 1, 0)
        m.call_void(m.main + 0x1605774, m.u64(m.u64(o + 0x78) + 0x5A0), f, f + 8)
        ident = m.vcall(b, 0x98) & M32
        q = m.u64(o + 0x20)
        bb = m.call(m.main + 0xF21C94, m.u64(m.u64(m.u64(q + 0x20) + 0x10) + 0x30), ident)
        m.vcall_void(bb, 0x6E0, k)
        m.call_void(m.main + 0x119AFF0, m.u64(q + 0x18), 7, ident, k & 0xFF)
        return int(m.u8(f) != 0)


@lifted(0x2832EA8)
def raise_avoided(m, o, user, target, move, *_):
    """Event 0xd1 with the user (3), the target (4), the move id (0x12) and move[0xb] (0x63)."""
    _event(m, o, 0xD1, [(3, lambda: m.vcall(user, 0x98), 4, 0x20), (4, lambda: m.vcall(target, 0x98), 4, 0x28),
                        (0x12, lambda: m.u16(move), 4, 0x98), (0x63, lambda: m.u8(move + 0xB), 4, 0x320)])


@lifted(0x11496A0)
def pool_clear(m, pool, *_):
    """Free every one of the 0x60 parameter records (kind 0) and reset the used count."""
    m.put(pool + 0xC08, 4, 0)
    for i in range(0x60):
        m.put(m.u64(pool + 32 * i + 8) + 8, 2, 0)


@lifted(0x1155180)
def frames_clear(m, stk, *_):
    """Reset the frame stack: count 0, all 32 frames zeroed."""
    m.put(stk + 0x408, 4, 0)
    for i in range(32):
        m.write(m.u64(stk + 32 * i + 8) + 8, bytes(0x430))


@lifted(0x1777748)
def raise_bc(m, o, b, flag, *_):
    """Event 0xbc with b's id (2) and flag (0x31)."""
    _event(m, o, 0xBC, [(2, lambda: m.vcall(b, 0x98), 4, 0x18), (0x31, flag & 0xFF, 4, 0x190)])


@lifted(0x1483140)
def event_e1(m, o, b, mv, *_):
    """Event 0xe1 with b's id (3) and the move (0x12): whether a handler set 0x48."""
    return int(_event(m, o, 0xE1, [(3, lambda: m.vcall(b, 0x98), 4, 0x20), (0x12, mv & 0xFFFF, 4, 0x98),
                                   (0x48, 0, 1, 0x248)], 0x248) != 0)


@lifted(0x14834BC)
def event_1f(m, o, b, mv, k, *_):
    """Event 0x1f with b's id (2), k (0x25) and the move (0x12): whether a handler set 0x48."""
    return int(_event(m, o, 0x1F, [(2, lambda: m.vcall(b, 0x98), 4, 0x18), (0x25, k & 0xFF, 4, 0x130),
                                   (0x12, mv & 0xFFFF, 4, 0x98), (0x48, 0, 1, 0x248)], 0x248) != 0)


@lifted(0x2830050)
def event_0e(m, o, b, *_):
    """Event 0xe with b's id (2): whether a handler set 0x48."""
    return int(_event(m, o, 0xE, [(2, lambda: m.vcall(b, 0x98), 4, 0x18), (0x48, 0, 1, 0x248)], 0x248) != 0)


@lifted(0x2831C94)
def event_f1(m, o, b, mv, flag, p, *_):
    """Event 0xf1 with b's id (2), the move (0x12), its type byte (0x16), flag (0x59) and bit 3 of
    [p+4] (0x71): whether 0x73 stays set."""
    return int(_event(m, o, 0xF1, ((2, _id(m, b), 4, 0x18), (0x12, lambda: m.u16(mv), 4, 0x98),
                                   (0x16, lambda: m.u8(mv + 8), 4, 0xB8), (0x59, flag & 1, 4, 0x2D0),
                                   (0x71, lambda: m.u32(p + 4) >> 3 & 1, 4, 0x390), (0x73, 1, 1, 0x3A0)),
                      0x3A0) != 0)


@lifted(0x17CE520)
def event_e5(m, o, b, *_):
    """Event 0xe5 with b's id (2): whether a handler cleared 0x73."""
    return int(_event(m, o, 0xE5, ((2, _id(m, b), 4, 0x18), (0x73, 1, 1, 0x3A0)), 0x3A0) == 0)


@lifted(0x15803E4)
def run_157fdb0(m, o, b, mv, flags, *_):
    """0x157fdb0 with the record {b's id, u16 [mv], flags at +8}."""
    with m.frame(0x30) as sp:
        m.write(sp, bytes(0x10))
        m.put(sp, 4, m.vcall(b, 0x98) & M32)
        m.put(sp + 8, 8, flags); m.put(sp + 4, 2, m.u16(mv))
        x = m.call(m.main + 0x157FDA8, m.call(m.main + 0x1361214, o))
        m.call_void(m.main + 0x157FDB0, x, sp + 0x28, sp)


@lifted(0x282F9D4)
def event_b4(m, o, ident, *_):
    """Event 0xb4 with the id (2)."""
    _event(m, o, 0xB4, ((2, ident, 4, 0x18),))


def _ratio_bounded(m, ctx, kind, slot, lo, hi):
    """A type-3 parameter holding the ratio 4096/4096 with bounds lo and hi."""
    e = _param_record(m, ctx, kind, slot)
    if e:
        m.put(e + 0xC, 4, 0x1000); m.put(e + 0x10, 4, lo); m.put(e + 0x14, 4, hi); m.put(e + 0x18, 8, 0)
        m.put(e + 0xA, 1, 3)


@lifted(0x2833BB4)
def event_98(m, o, b, *_):
    """Event 0x98 with b's id (2)."""
    _event(m, o, 0x98, ((2, lambda: m.vcall(b, 0x98), 4, 0x18),))


@lifted(0x1580120)
def event_b1(m, x, mv, b, *_):
    """Event 0xb1 with b's id (3) and the u16 move (0x12)."""
    _event(m, x, 0xB1, ((3, lambda: m.vcall(b, 0x98), 4, 0x20), (0x12, lambda: m.u16(mv), 4, 0x98)))


@lifted(0x2833298)
def event_d5(m, o, b, _x, mv, *_):
    """Event 0xd5 with b's id (3) and the u16 move (0x12)."""
    _event(m, o, 0xD5, ((3, lambda: m.vcall(b, 0x98), 4, 0x20), (0x12, lambda: m.u16(mv), 4, 0x98)))


@lifted(0x11470D4)
def event_with_id(m, o, b, event, *_):
    """Event `event` raised through 0x1147308 (handlers flag 0) with b's id (2)."""
    ctx = m.u64(o + 0x10)
    ev_push(m, ctx)
    ev_param(m, m.u64(o + 0x10), 2, m.vcall(b, 0x98) & M32, 4, 0x18)
    m.call_void(m.main + 0x1147308, m.u64(o + 0x10), event & M32)
    ev_pop(m, m.u64(o + 0x10))


@lifted(0x1147AD8)
def event_75(m, o, lst, *_):
    """Event 0x75 with each member's id of lst as parameters 6, 7, ... and their count (5)."""
    n = m.u8(lst + 0xA6)
    params = [(6 + i, (lambda i=i: m.vcall(m.u64(lst + 8 * i), 0x98)), 4, 0x38 + 8 * i) for i in range(n)]
    _event(m, o, 0x75, params + [(5, n, 4, 0x30)])


@lifted(0x1146B30)
def event_77(m, o, *_):
    """Event 0x77 with no parameters."""
    _event(m, o, 0x77, ())


@lifted(0x1146E98)
def event_for(m, x, b, event, *_):
    """Event `event` with b's id (2)."""
    _event(m, x, event & M32, ((2, lambda: m.vcall(b, 0x98), 4, 0x18),))


def _events_each(event, raiser=0x1146E98):
    def fn(m, o, lst, *_):
        _for_each_member(m, lst, lambda b: m.call_void(m.main + raiser, m.call(m.main + 0x1146E90, o), b, event))
    return fn


lifted(0x11467F4)(_events_each(0x70))
lifted(0x114686C)(_events_each(0x71))


@lifted(0x1147314)
def event_76(m, o, *_):
    """Event 0x76 with no parameters."""
    _event(m, o, 0x76, ())


@lifted(0x2835CF0)
def event_a0(m, o, kind, b, *_):
    """Event 0xa0 with parameters 0x3e (kind), 3 (b's id) and 0x27 (0): the value 0x27 comes back with."""
    return _event(m, o, 0xA0, ((0x3E, kind & 0xFF, 4, 0x1F8), (3, lambda: m.vcall(b, 0x98), 4, 0x20),
                               (0x27, 0, 0, 0x140)), result=0x140)


@lifted(0x1151590)
def event_a1(m, o, kind, *_):
    """Event 0xa1 with parameters 0x3e (kind) and 0x48 (0); when 0x48 comes back 0, event 0xa2 in the same
    frame."""
    ev_push(m, m.u64(o + 0x10))
    ev_param(m, m.u64(o + 0x10), 0x3E, kind & 0xFF, 4, 0x1F8)
    ev_param(m, m.u64(o + 0x10), 0x48, 0, 1, 0x248)
    m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), 0xA1, 8, 1)
    ctx = m.u64(o + 0x10)
    if _value(m, ctx, 0x248) == 0:
        m.call_void(m.main + 0xF7B310, ctx, 0xA2, 8, 1)
    ev_pop(m, m.u64(o + 0x10))
