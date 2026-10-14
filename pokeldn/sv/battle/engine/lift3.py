"""Lifted battle server functions, batch 3: the event dispatcher 0xf7b5d8 and its handlers."""

from pokeldn.sv.battle.machine import FUNCTIONS, UnliftedCall, lifted
from pokeldn.sv.battle.engine.lift1 import ev_param, ev_pop, ev_push

M32 = 0xFFFFFFFF
M64 = 0xFFFFFFFFFFFFFFFF


def _tail(m, address, *args):
    """A tail call: the callee's result, or None when the callee is void."""
    fn = FUNCTIONS.get(address - m.main)
    if fn is None:
        raise UnliftedCall(f"main+0x{address - m.main:x}")
    return fn(m, *args)


def _need(m, address):
    """Refuse the round before any write when a callee reached later is not lifted."""
    if address - m.main not in FUNCTIONS:
        raise UnliftedCall(f"main+0x{address - m.main:x}")


def _s32(v):
    v &= M32
    return v - (1 << 32) if v & 0x80000000 else v


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


@lifted(0x2844B90)
def apply_16_if_pending(m, o, *_):
    """When the battler of entry 4 qualifies and has key 2 or 0xe pending, apply record (id, 0x10)."""
    ident = m.call(m.main + 0x2844360, o, 4) & M32
    if m.call(m.main + 0x2844800, o, ident) & 1 == 0:
        return
    if m.call(m.main + 0x2844C10, o, ident, 2) & 1 == 0 and m.call(m.main + 0x2844C10, o, ident, 0xE) & 1 == 0:
        return
    with m.frame(0x10) as p:
        m.put(p, 4, ident); m.put(p + 4, 4, 0x10); m.put(p + 8, 8, 0)
        m.call_void(m.main + 0x183F070, o, p)


@lifted(0x2D15530)
def second_side_event(m, o, ident, *_):
    """When `ident` is the id at [t + 0x28] but not [t + 0x20] (t = [[o + 0x38] + 0x78]) and [t + 0x270]
    is clear, and the battler's vcall 0x208 says yes: run record (ident, 1, 0x1020400, ident, [t+0x98]
    u16) through 0x1807920, then apply record (ident, 0x14) through 0x183f070."""
    ident &= M32
    t = m.u64(m.u64(o + 0x38) + 0x78)
    p = m.u64(t + 0x20)
    if (m.u32(p + 0xC) if p else 0) == ident:
        return
    p = m.u64(t + 0x28)
    if (m.u32(p + 0xC) if p else 0) != ident:
        return
    p = m.u64(t + 0x270)
    if p and m.u32(p + 0xC):
        return
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 8) + 0x30), ident)
    if m.vcall(b, 0x208) & 1 == 0:
        return
    p = m.u64(m.u64(m.u64(o + 0x38) + 0x78) + 0x98)
    with m.frame(0x30) as s:
        m.write(s, bytes(0x2C))
        m.put(s, 4, ident); m.put(s + 4, 1, 1)
        m.put(s + 8, 4, 0x1020400); m.put(s + 0xC, 4, ident)
        m.put(s + 0x10, 4, m.u16(p + 0xC) if p else 0)
        m.call_void(m.main + 0x1807920, o, s)
        m.put(s, 4, ident); m.put(s + 4, 4, 0x14); m.put(s + 8, 8, 0)
        m.call_void(m.main + 0x183F070, o, s)


@lifted(0x288DD40)
def push_65(m, que, a, b, rec, *_):
    """Queue command 0x65 (a & 0xff, b, then the record's three fields as 0x174ae90 unpacks them)."""
    with m.frame(0x10) as p:
        m.write(p, bytes(0xC))
        m.call_void(m.main + 0x174AE90, rec, p + 4, p, p + 8)
        return _tail(m, m.main + 0x119AFF0, que, 0x65, a & 0xFF, b & M32, m.u32(p + 4), m.u32(p), m.u32(p + 8))


@lifted(0x2888018)
def add_handler_and_push_65(m, o, a, b, rec, *_):
    m.call_void(m.main + 0x288D114, m.u64(o + 0x20), a, b, rec)    # x1..x3 passed through
    return _tail(m, m.main + 0x288DD40, m.u64(o + 0x18), a, b, rec)


# Message ids for kind 1 by sub-kind 1..6 (the jump table at 0x3c6a6d7), and sub-kind 15.
_KIND1_TEXT = {1: 0x5F, 2: 0x6A, 3: 0x64, 4: 0x5A, 5: 0x54, 6: 0x77, 15: 0xA}
# Message ids for kind 2, sub-kind 1..6 (rodata 0x3c6a8ac).
_KIND2_TEXT = (0x60, 0x6B, 0x65, 0x5B, 0x55, 0x78)


@lifted(0x287DB9C)
def push_status_text(m, o, who, holder, kind, sub, flag, *_):
    """Queue the message for (kind, sub): 0xcb (who, text, holder's id) for the known ones, 0xca (who,
    0x237) otherwise; kind 1 sub 20 queues nothing."""
    hid = m.vcall(holder, 0x98)
    kind &= 0xFF
    sub &= 0xFFFF
    q = m.u64(o + 0x18)
    if kind == 2:
        if flag & 0xFF == 5 and (sub - 1) & 0xFFFF <= 5:
            text = _KIND2_TEXT[(sub - 1) & 0xFFFF]
        else:
            text = 0x48
    elif kind == 1 and sub == 20:
        return hid
    elif kind == 1 and sub in _KIND1_TEXT:
        text = _KIND1_TEXT[sub]
    else:
        return _tail(m, m.main + 0x157EBC0, q, 0xCA, who & M32, 0x237, 0xFFFF0000)
    return _tail(m, m.main + 0x157EBC0, q, 0xCB, who & M32, text, hid & M32, 0xFFFF0000)


@lifted(0x17CE0EC)
def flag_and_push_25_c7(m, o, ident, v, *_):
    """For a nonzero id: 0x17ce148([o + 0x20]), then queue 0x25 (ident) and 0xc7 (ident, v)."""
    if ident & M32 == 0:
        return
    m.call_void(m.main + 0x17CE148, m.u64(o + 0x20), ident)
    q = m.u64(o + 0x18)
    m.call_void(m.main + 0x119AFF0, q, 0x25, ident & M32)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xC7, ident & M32, v & M32)


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


@lifted(0x116EBBC)
def weather_of(m, o, out, ident_ptr, *_):
    """out (byte) = event 0x9d's answer, passed through event 0x9e for a nonzero [ident_ptr]."""
    v = m.call(m.main + 0x116EC0C, m.u64(o + 0x38), out, ident_ptr)
    ident = m.u32(ident_ptr)
    if ident:
        v = m.call(m.main + 0x116EE6C, m.u64(o + 0x38), ident, v & M32)
    m.put(out, 1, v)


@lifted(0x14C78D0)
def weather_for(m, o, ident, *_):
    with m.frame(0x10) as p:
        m.put(p, 4, ident)
        m.call_void(m.main + 0x116EBBC, m.call(m.main + 0x116EBB4, m.u64(o + 0x28)), p + 8, p)
        return m.u8(p + 8)


@lifted(0x287DD04)
def holder_weather_1_or_6(m, o, holder, *_):
    with m.frame(0x10) as p:
        m.put(p, 4, m.vcall(holder, 0x98))
        x = m.call(m.main + 0x116EBB4, m.call(m.main + 0x1361214, o))
        m.call_void(m.main + 0x116EBBC, x, p + 8, p)
        return m.call(m.main + 0x14C7890, m.u8(p + 8)) & 1


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


@lifted(0x2866DA0)
def weather_2_or_5_sets_2d0(m, o, ident, *_):
    t = m.u64(m.u64(o + 0x38) + 0x78)
    if _id_at(m, t, 0x20) != ident & M32:
        return
    w = m.call(m.main + 0x14C78D0, o, _id_at(m, t, 0x28)) & 0xFF
    if w not in (2, 5):
        return
    _bump_record(m, m.u64(m.u64(m.u64(o + 0x38) + 0x78) + 0x2D0), 1)


@lifted(0x2866E40)
def weather_sets_178(m, o, ident, *_):
    t = m.u64(m.u64(o + 0x38) + 0x78)
    if _id_at(m, t, 0x20) != ident & M32:
        return
    if m.call(m.main + 0x14C7890, m.call(m.main + 0x14C78D0, o, ident)) & 1 == 0:
        return
    _bump_record(m, m.u64(m.u64(m.u64(o + 0x38) + 0x78) + 0x178), 0x32)


@lifted(0xF7C230)
def f_f7c230(m, rec, *_): return m.u8(rec + 0x43)


@lifted(0xF7C238)
def clear_40(m, rec, *_):
    m.put(rec + 0x40, 1, 0)


@lifted(0xF7BB80)
def f_f7bb80(m, v, *_):
    return _tail(m, m.main + 0x20FAA24, v)


@lifted(0xF803C8)
def f_f803c8(m, o, *_): return m.u32(o + 0x38)


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


def _battler_of(m, o, ident):
    return m.call(m.main + 0xF21C94, m.u64(m.u64(o + 8) + 0x30), ident)


@lifted(0x285B720)
def target_flag5_sets_180(m, o, ident, *_):
    """For the event's actor `ident`: when the target battler has flag 5, record 0x180 takes 3."""
    t = _t78(m, o)
    if _id_at(m, t, 0x20) != ident & M32:
        return
    b = _battler_of(m, o, _id_at(m, t, 0x28))
    if m.vcall(b, 0x220, 5) & 1 == 0:
        return
    _bump_record(m, m.u64(_t78(m, o) + 0x180), 3)


@lifted(0x2856350)
def run_82(m, o, ident, kind, *_):
    """For the event's subject `ident`: 0x1752230, record (ident, 0, kind, 0x82, ident) through
    0x1807920, then 0x1752150."""
    if _id_at(m, _t78(m, o), 0x18) != ident & M32:
        return
    _need(m, m.main + 0x1752150)
    m.call_void(m.main + 0x1752230, o, ident)
    with m.frame(0x30) as s:
        m.write(s, bytes(0x2C))
        m.put(s, 4, ident); m.put(s + 8, 2, kind); m.put(s + 0xA, 2, 0x82); m.put(s + 0xC, 4, ident)
        m.call_void(m.main + 0x1807920, o, s)
    m.call_void(m.main + 0x1752150, o, ident)


@lifted(0x2856340)
def run_82_a2(m, o, ident, *_):
    return _tail(m, m.main + 0x2856350, o, ident, 0xA2)


@lifted(0x283D6F0)
def same_side_of(m, o, a, b, *_):
    return _tail(m, m.main + 0x118AB58, m.u64(m.u64(o + 8) + 0x290), a, b)


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


@lifted(0x28563F0)
def count_120(m, o, ident, *_):
    """Unless the actor is on `ident`'s side: when `ident` is listed, or the move's item id has kind 10
    or passes 0x2823e90, record 0x120 counts one more."""
    t = _t78(m, o)
    if m.call(m.main + 0x283D6F0, o, _id_at(m, t, 0x20), ident) & 1:
        return
    if not m.call(m.main + 0x2842730, o, ident) & 1:
        v = _id_at(m, _t78(m, o), 0x98)
        if m.call(m.main + 0x20FAD50, v) & 0xFF != 0xA and not m.call(m.main + 0x2823E90, v) & 1:
            return
    _bump_inc(m, m.u64(_t78(m, o) + 0x120))


@lifted(0x2872D60)
def weather_change_sets_3c8(m, o, ident, kind, *_):
    """For the event's actor `ident`, when the field state is not `kind`: record (ident, 8, kind; 0x9c,
    pack(ident, 5)) through 0x283fbf0; when it applies, record 0x3c8 takes 1."""
    if _id_at(m, _t78(m, o), 0x20) != ident & M32:
        return
    v = m.call(m.main + 0x13616DC, m.call(m.main + 0x148253C, m.u64(o + 8), ident))
    if v & 0xFF == kind & 0xFF:
        return
    with m.frame(0x50) as s:
        m.write(s, bytes(0x50))
        m.put(s, 4, ident); m.put(s + 4, 4, 8); m.put(s + 8, 1, kind)
        m.call_void(m.main + 0x179372C, s + 0x10)
        m.put(s + 0x20, 2, 0x9C)
        r = m.call(m.main + 0x28616B0, ident & M32, 5)
        m.put(s + 0x10, 8, r[0]); m.put(s + 0x18, 8, r[1])
        ok = m.call(m.main + 0x283FBF0, o, s) & 1
    if ok:
        _bump_record(m, m.u64(_t78(m, o) + 0x3C8), 1)


@lifted(0x285CB30)
def apply_field(m, o, ident, kind, src, *_):
    """When the field state is not `kind`: record (ident, 8, kind; ident, 0x2a, 0x9c, flag 0x4a, the 0x24
    bytes at src) through 0x283fbf0."""
    v = m.call(m.main + 0x13616DC, m.call(m.main + 0x148253C, m.u64(o + 8)))
    if v & 0xFF == kind & 0xFF:
        return
    with m.frame(0x50) as s:
        m.write(s, bytes(0x50))
        m.put(s, 4, ident); m.put(s + 4, 4, 8); m.put(s + 8, 1, kind)
        m.put(s + 0x10, 8, ident & M32); m.put(s + 0x18, 8, 0x2A)
        m.put(s + 0x20, 2, 0x9C); m.put(s + 0x4A, 1, 1)
        if src:
            m.write(s + 0x24, m.read(src, 0x24))
        m.call_void(m.main + 0x283FBF0, o, s)


@lifted(0x285CB00)
def apply_field_3(m, o, ident, *_):
    if _id_at(m, _t78(m, o), 0x18) != ident & M32:
        return
    return _tail(m, m.main + 0x285CB30, o, ident, 3, 0)


@lifted(0x2850640)
def type_match_scales_34(m, o, ident, *_):
    """For the event's actor `ident`, when neither it nor the target has kind 2 (vf 0x120): scale record
    0x34 by 0x1400 when the kinds match, else 0xc00."""
    t = _t78(m, o)
    if _id_at(m, t, 0x20) != ident & M32:
        return
    tgt = _id_at(m, t, 0x28)
    a = _battler_of(m, o, ident)
    b = _battler_of(m, o, tgt)
    ka = m.vcall(a, 0x120) & 0xFF
    kb = m.vcall(b, 0x120) & 0xFF
    if ka == 2 or kb == 2:
        return
    return _tail(m, m.main + 0x1353738, m.u64(o + 0x38), 0x34, 0x1400 if ka == kb else 0xC00)


@lifted(0x286C320)
def apply_side(m, o, ident, a, b, pair, c, d, e, *_):
    """For the event's actor `ident`: record (ident, b; pair, a, c, d, 0x81, e, flag 0x4c) through
    0x283ef60; returns whether it applied."""
    if _id_at(m, _t78(m, o), 0x20) != ident & M32:
        return 0
    with m.frame(0x50) as s:
        m.write(s, bytes(0x50))
        m.put(s, 4, ident); m.put(s + 4, 4, b)
        m.call_void(m.main + 0x179372C, s + 8)
        m.write(s + 8, m.read(pair, 0x10))
        m.put(s + 0x18, 1, a); m.put(s + 0x1A, 2, c); m.put(s + 0x20, 2, d); m.put(s + 0x22, 2, 0x81)
        m.put(s + 0x24, 4, e); m.put(s + 0x44, 1, 1)
        return m.call(m.main + 0x283EF60, o, s) & 1


@lifted(0x286C400)
def apply_side_1(m, o, ident, *_):
    """apply_side kind 1 (text 0x273) with the field class of `ident`; when it applies, record 0x3c8
    takes 1."""
    cls = m.call(m.main + 0x283D690, o, ident) & M32
    r = m.call(m.main + 0x28616B0, ident & M32, 5)
    with m.frame(0x10) as pair:
        m.put(pair, 8, r[0]); m.put(pair + 8, 8, r[1])
        ok = m.call(m.main + 0x286C320, o, ident & M32, cls, 1, pair, 0x9C, 0x273, cls & 0xFF) & 1
    if ok:
        _bump_record(m, m.u64(_t78(m, o) + 0x3C8), 1)


@lifted(0x28533B0)
def put_u32(m, p, v, *_):
    m.put(p, 4, v)


@lifted(0x28531C0)
def protect_redirect(m, o, ident, *_):
    """For the event's target `ident`, when record 0xf8 holds kind 1, 4 or 5 and the actor is another
    battler: record (ident, actor, kind; target descriptor, 0x101) through 0x19042b0; kind 5 aims at
    the entry 0x1f object's descriptor when it is the last one."""
    t = _t78(m, o)
    if _id_at(m, t, 0x28) != ident & M32:
        return
    p = m.u64(t + 0xF8)
    if p == 0:
        return
    kind = m.u32(p + 0xC)
    k = kind & 0xFFFF
    if k > 5 or (1 << k) & 0x32 == 0:
        return
    p = m.u64(t + 0x20)
    if p == 0:
        return
    actor = m.u32(p + 0xC)
    if actor == 0 or actor == ident & M32:
        return
    for a in (0x19042B0, 0x1795308, 0x17959D4):
        _need(m, m.main + a)
    b = _battler_of(m, o, ident)
    obj = m.call(m.main + 0x283D5E0, o, 0x1F)
    with m.frame(0x50) as s:
        m.write(s, bytes(0x4C))
        m.put(s + 0x24, 1, 1)
        m.put(s, 4, ident); m.put(s + 4, 4, actor); m.put(s + 8, 2, kind)
        done = False
        if k == 5 and m.call(m.main + 0x2853340, obj, m.call(m.main + 0x2844160, o)) & 1:
            m.write(s + 0x10, m.read(obj, 0x10))
            m.call_void(m.main + 0x28533B0, s + 0x10, ident)
            done = True
        if not done:
            x4 = m.u64(m.u64(o + 8) + 0x10)
            x5 = m.call(m.main + 0x2844160, o)
            m.call_void(m.main + 0x28533B8, m.u64(m.u64(o + 8) + 8), kind, b, s + 0x10, x4, x5)
        m.put(s + 0x22, 2, 0x101)
        m.call_void(m.main + 0x19042B0, o, s)


@lifted(0x284F010)
def apply_pending_status(m, o, ident, *_):
    """For the event's subject `ident`: the ids 0x2843d30 collects for (2, 0x2843aa0's byte) go out as a
    record (ident, n, ids) through 0x283e270, between 0x1752230 and 0x1752150."""
    if _id_at(m, _t78(m, o), 0x18) != ident & M32:
        return
    with m.frame(0x40) as q:
        out = q + 0x10
        m.put(q, 4, 2); m.put(q + 4, 1, m.call(m.main + 0x2843AA0, o, ident))
        n = m.call(m.main + 0x2843D30, o, q, out) & 0xFF
        if n == 0:
            return
        for a in (0x283E270, 0x1752150, 0x1382688, 0x1381580):
            _need(m, m.main + a)
        m.call_void(m.main + 0x1752230, o, ident)
        with m.frame(0x70) as s:
            m.write(s, bytes(0x70))
            m.put(s + 0x34, 2, 0xFF01); m.put(s + 0x36, 1, 1); m.put(s + 0x45, 1, 1)
            m.put(s, 4, ident); m.put(s + 4, 1, n)
            m.write(s + 8, m.read(out, 4 * n))
            m.call_void(m.main + 0x283E270, o, s)
        m.call_void(m.main + 0x1752150, o, ident)


@lifted(0x1752268)
def f_1752268(m, o, *_): return m.u64(o + 0x11C0)


@lifted(0x1752184)
def f_1752184(m, o, *_): return m.u64(o + 0x11E0)


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


@lifted(0x20FAD50)
def item_field_3(m, ident, *_):
    """Field 3 (u8) of record `ident` in the table of the static at 0x46d7948."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    return fb.u8(m, m.call(m.main + 0xBF60CC, table, ident & M32), 3)


def _add_unique(m, s, b):
    """Add byte b to the set at s (count at +0xb, at most 11) unless it holds it."""
    n = m.u8(s + 0xB)
    if n > 10:
        return
    b &= 0xFF
    if b in m.read(s, n):
        return
    m.put(s + n, 1, b)
    m.put(s + 0xB, 1, n + 1)


@lifted(0x1138D9C)
def targets_mode_0(m, p, s, w, *_):
    """The positions target kind [p] (subject byte p+4) reaches in a single battle, into the set s."""
    k = m.u32(p)
    if k > 9:
        return
    bit = 1 << k
    if bit & 0x8C:
        _add_unique(m, s, m.call(m.main + 0x113AECC, 0, w, m.u8(p + 4), 0))
    elif bit & 0x240:
        _add_unique(m, s, 0); _add_unique(m, s, 1)
    elif k == 4:
        _add_unique(m, s, m.u8(p + 4))


@lifted(0x1138F20)
def targets_mode_1(m, p, s, w, *_):
    """The positions target kind [p] (subject byte p+4) reaches in a double battle, into the set s."""
    k = m.u32(p)
    me = m.u8(p + 4)
    near = lambda i: m.call(m.main + 0x113A588, 1, w, me, i)
    foe = lambda i: m.call(m.main + 0x113AECC, 1, w, me, i)
    if k == 8:
        _add_unique(m, s, me); _add_unique(m, s, near(1))
    elif k in (1, 5):
        _add_unique(m, s, near(1))
    elif k in (2, 7):
        _add_unique(m, s, foe(0)); _add_unique(m, s, foe(1))
    elif k == 3:
        _add_unique(m, s, foe(0)); _add_unique(m, s, foe(1)); _add_unique(m, s, near(1))
    elif k == 4:
        b = near(1) & 0xFF
        _add_unique(m, s, min(me, b)); _add_unique(m, s, max(me, b))
    elif k in (6, 9):
        for i in range(4):
            _add_unique(m, s, i)


@lifted(0x11393FC)
def targets_mode_2(m, p, s, w, *_):
    """The positions target kind [p] (subject byte p+4) reaches in a raid, into the set s."""
    k = m.u32(p)
    me = m.u8(p + 4)
    near = lambda i: m.call(m.main + 0x113A588, 2, w, me, i)
    foe = lambda i: m.call(m.main + 0x113AECC, 2, w, me, i)
    if k == 8:
        _add_unique(m, s, me)
        for i in range(1, 6):
            _add_unique(m, s, near(i))
    elif k in (1, 5):
        for i in range(1, 6):
            _add_unique(m, s, near(i))
    elif k in (2, 7):
        for i in range(6):
            _add_unique(m, s, foe(i))
    elif k == 3:
        for i in range(6):
            _add_unique(m, s, foe(i))
        for i in range(1, 6):
            _add_unique(m, s, near(i))
    elif k == 4:
        for i in range(11):
            if m.call(m.main + 0x113B494, 2, w, me, i) & 1:
                _add_unique(m, s, i)
    elif k in (6, 9):
        for i in range(10):
            _add_unique(m, s, i)


@lifted(0xFE171C)
def collect_targets(m, p, mode, w, field, out, *_):
    """The ids of the standing battlers at the positions target record p reaches (by battle mode),
    into the u32 array out; returns how many."""
    k = m.u32(p)
    me = m.u8(p + 4)
    with m.frame(0x20) as f:
        lst = f
        s = f + 0x10
        if k == 0:
            m.put(lst, 1, me)
            n = int(me != 0xA)
        elif me == 0xA:
            return 0
        else:
            m.write(s, b"\x0a" * 11 + b"\x00")
            mode &= M32
            fn = 0x11393FC if mode == 2 else 0x1138F20 if mode == 1 else 0x1138D9C
            m.call_void(m.main + fn, p, s, w)
            n = m.u8(s + 0xB)
            if n:
                m.write(lst, m.read(s, n))
        count = 0
        for i in range(n):
            m.call_void(m.main + 0x1153868, m.u64(m.u64(field + 0x18) + 0x290), m.u8(lst + i), s, f + 0xC)
            side = m.u8(s)
            if side == 5:
                continue
            slot = m.u8(f + 0xC)
            if slot >= m.u8(field + side * 0x38 + 0x58):
                continue
            b = m.u64(field + side * 0x38 + slot * 8 + 0x28)
            if b == 0 or m.vcall(b, 0x200) & 1:
                continue
            m.put(out + 4 * (count & 0xFF), 4, m.vcall(b, 0x98))
            count += 1
        return count & M32


@lifted(0x2843D30)
def collect_targets_of(m, o, p, out, *_):
    mode = m.call(m.main + 0x144B6D4, m.u64(o + 8))
    w = m.call(m.main + 0x281B234, m.u64(o + 8))
    return _tail(m, m.main + 0xFE171C, p, mode & M32, w & M32, m.u64(m.u64(o + 8) + 0x30), out)


# Position class by side for each battle mode (rodata 0x3c6a450, 0x3c6a455, 0x3c6a45a).
_SIDE_CLASS = {0: (0, 1, 2, 2, 2), 1: (0, 1, 0, 1, 2), 2: (0, 1, 0, 0, 0)}


@lifted(0x282329C)
def slot_in_play(m, o, pos, *_):
    """Whether position `pos` (<= 10) is on a side and its slot is below the side's position count."""
    if pos & 0xFF > 0xA:
        return 0
    with m.frame(0x10) as f:
        m.call_void(m.main + 0x1153868, o, pos, f + 4, f)
        side = m.u8(f + 4)
        if side == 5:
            return 0
        rule = m.u64(o + 8)
        mode = m.u32(rule + 0x36C)
        cls = _SIDE_CLASS[mode][side] if mode in _SIDE_CLASS and side <= 4 else 2
        n = m.call(m.main + 0x113AA70, mode, m.u8(rule + 0x370), cls) & M32
        return int(n > m.u8(f))


@lifted(0x2843AA0)
def position_of(m, o, ident, *_):
    """The position of `ident`, or 10 when it is not in play."""
    pos = m.call(m.main + 0x1381420, m.call(m.main + 0x13813E4, m.u64(o + 8)), ident) & M32
    if m.call(m.main + 0x282329C, m.u64(m.u64(o + 8) + 0x290), pos) & 1:
        return pos
    return 0xA


@lifted(0x20FCBD0)
def item_flag_41(m, key, *_):
    """Field 41 (u8 != 0) of the record for the u16 id at key+8 in the table of the static at 0x46d7948."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    return int(fb.u8(m, m.call(m.main + 0xBF60CC, table, m.u16(key + 8)), 41) != 0)


@lifted(0x20FCB98)
def item_flag_41_of(m, ident, *_):
    with m.frame(0x10) as k:
        m.put(k, 8, m.u64(m.main + 0x46DDAD8) + 0x10); m.put(k + 8, 2, ident)
        return m.call(m.main + 0x20FCBD0, k) & 1


@lifted(0x2823E90)
def item_flag_41_tail(m, ident, *_):
    return _tail(m, m.main + 0x20FCB98, ident)


@lifted(0x1154148)
def apply_condition(m, o, out, r, *_):
    """Apply the condition record r (id +0, kind +4, sub +8/+9, target descriptor +0x10, message +0x20,
    text +0x24, flags +0x48..+0x4a); out (byte) = whether it took."""
    for a in ((0x2836050, 0x2836450) if m.u32(r + 4) == 8 else (0x2836A78,)):
        _need(m, m.main + a)
    with m.frame(0x40) as f:
        text = f
        m.call_void(m.main + 0x1146154, text)
        ident = m.u32(r)
        if m.u8(r + 0x4A):
            m.call_void(m.main + 0x17CE0E4, m.call(m.main + 0x1143584, o), ident)
        kind = m.u32(r + 4)
        if kind == 8:
            desc = f + 0x30
            m.write(desc, m.read(r + 0x10, 0x10))
            m.call_void(m.main + 0x2836050, m.call(m.main + 0x1146E90, o), ident, m.u8(r + 8), desc)
            ok = m.call(m.main + 0x28806B0, o, ident, m.u8(r + 8), desc, m.u8(r + 9)) & 1
            m.call_void(m.main + 0x2880738, text, m.u8(r + 8), m.u8(r + 9))
        else:
            ok = m.call(m.main + 0x28807C0, o, kind, r + 0x10, m.u8(r + 0x49)) & 1
        if ok and not m.u8(r + 0x48):
            if m.u16(r + 0x20) != 0x9C:
                m.call_void(m.main + 0x2880868, m.call(m.main + 0x1143584, o), m.u16(r + 0x20))
            own = m.call(m.main + 0x17CE3AC, r + 0x24) & 1
            m.call_void(m.main + 0x114B0AC, m.call(m.main + 0x1143584, o), m.u32(r), r + 0x24 if own else text)
        if m.u8(r + 0x4A):
            m.call_void(m.main + 0x17CE27C, m.call(m.main + 0x1143584, o), m.u32(r))
        kind = m.u32(r + 4)
        if kind == 8 and ok:
            m.call_void(m.main + 0x2836450, m.call(m.main + 0x1146E90, o), m.u32(r), m.u8(r + 8))
            kind = m.u32(r + 4)
        if kind != 8 and ok:
            m.call_void(m.main + 0x2836A78, m.call(m.main + 0x1146E90, o), m.u32(r), m.u32(r + 4))
            kind = m.u32(r + 4)
            if kind == 9:
                m.call_void(m.main + 0x2880878, o)
                kind = m.u32(r + 4)
        if kind == 2 and ok:
            m.call_void(m.main + 0x288090C, o, m.u32(r))
        m.put(out, 1, ok)


@lifted(0x283FBF0)
def apply_condition_of(m, o, r, *_):
    with m.frame(0x10) as out:
        m.call_void(m.main + 0x1154148, m.call(m.main + 0x113DFC4, m.u64(o + 0x28)), out, r)
        return m.u8(out)


@lifted(0x17CE0E4)
def flag_and_push_25_c7_0(m, o, ident, *_):
    return _tail(m, m.main + 0x17CE0EC, o, ident, 0)


@lifted(0x17CE27C)
def push_c8_if(m, o, ident, *_):
    if ident & M32 == 0:
        return
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xC8, ident & M32)


@lifted(0x28363E0)
def descriptor_shift(m, d, n, *_):
    """A descriptor of kind 2 or 4 (low bits & 0x1c7) moves its index (bits 3..8) by n."""
    for kind in (2, 4):
        v = m.u64(d + 8)
        if v & 0x1C7 == kind:
            i = (((v + (n << 3)) & M32) >> 3) & 0x3F
            m.put(d + 8, 8, v & ~(0x3F << 3) | i << 3)


@lifted(0x2836430)
def descriptor_set_count(m, d, n, *_):
    """A descriptor of kind 1..4 (low 3 bits) takes n as its u16 at bits 9..24."""
    v = m.u64(d + 8)
    if 1 <= v & 7 <= 4:
        m.put(d + 8, 8, v & ~(0xFFFF << 9) | (n & 0xFFFF) << 9)


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


@lifted(0x114BEB0)
def set_and_queue_6a(m, o, v, *_):
    m.call_void(m.main + 0x114BEE4, m.u64(o + 0x20), v)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x6A, v & M32)


@lifted(0x287EAE4)
def queue_aa(m, o, v, *_):
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xAA, v & 0xFF)


@lifted(0x287E9E8)
def start_field(m, o, out, r, *_):
    """out (byte) = whether the field effect (kind r+4, descriptor r+8) started: then 0x114beb0(8), unless
    r+0x18 is 1 queue 0xb2 and 0xaa (kind), then 0x114bf8c(8, kind)."""
    ok = m.call(m.main + 0x287EA80, m.call(m.main + 0x1143584, o), m.u8(r + 4), r + 8) & 1
    if ok:
        m.call_void(m.main + 0x114BEB0, m.call(m.main + 0x1143584, o), 8)
        if m.u8(r + 0x18) != 1:
            m.call_void(m.main + 0x287EAD4, m.call(m.main + 0x1143584, o))
            m.call_void(m.main + 0x287EAE4, m.call(m.main + 0x1143584, o), m.u8(r + 4))
        m.call_void(m.main + 0x114BF8C, m.call(m.main + 0x1143584, o), 8, m.u8(r + 4))
    m.put(out, 1, ok)


@lifted(0x28806B0)
def start_field_of(m, o, ident, kind, desc, flag, *_):
    with m.frame(0x30) as r:
        m.write(r, bytes(0x20))
        m.call_void(m.main + 0x179372C, r + 8)
        m.put(r, 4, ident); m.put(r + 4, 1, kind)
        m.write(r + 8, m.read(desc, 0x10))
        m.put(r + 0x18, 1, flag)
        out = r + 0x20
        m.call_void(m.main + 0x287E9E8, m.call(m.main + 0x288093C, m.call(m.main + 0x1361214, o)), out, r)
        return m.u8(out)


@lifted(0x113A588)
def nth_position_on_side(m, mode, rule, pos, i, *_):
    """Scanning positions from `pos` (mod 11), the (i mod count)-th one whose client is on the side class
    0xc9c750 names; `pos` when the side has no positions."""
    from pokeldn.sv.battle.engine.slots import SIDE_CLASS, slot_of_position
    side = m.call(m.main + 0xC9C750, mode, rule, pos, i) & 0xFF
    n = m.call(m.main + 0x113AA70, mode, rule, side) & M32
    mode &= M32
    if n == 0 or mode not in SIDE_CLASS:
        return pos & M32
    k = (i & 0xFF) % n
    j = 0
    for step in range(11):
        p = ((pos & 0xFF) + step) % 11
        slot = slot_of_position(mode, rule & 0xFF, p)
        if slot == 5 or SIDE_CLASS[mode][slot] != side:
            continue
        if j == k:
            return p
        j += 1
    return pos & M32


@lifted(0x2878714)
def add_condition_id(m, o, k, v, *_):
    """Add id v to the list of active condition k (<= 13, at most 11 ids at o + 0x2c k + 0xe0)."""
    k &= M32
    if _s32(k) > 0xD or m.u32(o + 0xA8 + 4 * k) == 0:
        return 0
    c = m.u32(o + 0x70 + 4 * k)
    if c > 10:
        return 0
    lst = o + 0x2C * k + 0xE0
    v &= M32
    for i in range(c):
        if m.u32(lst + 4 * i) == v:
            return 0
    m.put(lst + 4 * c, 4, v)
    m.put(o + 0x70 + 4 * k, 4, c + 1)
    return 1


@lifted(0x2878668)
def start_condition(m, o, k, desc, v, *_):
    """Start condition k unless active: its descriptor, u16 v, cleared counters and list, and the
    descriptor's packed index as its first id."""
    k &= M32
    if m.u32(o + 0xA8 + 4 * k):
        return 0
    m.put(o + 0xA8 + 4 * k, 4, 1)
    m.put(o + 0x348 + 16 * k, 8, m.u64(desc)); m.put(o + 0x350 + 16 * k, 8, m.u64(desc + 8))
    m.put(o + 0x38 + 4 * k, 4, 0); m.put(o + 0x70 + 4 * k, 4, 0)
    m.put(o + 0x1C + 2 * k, 2, v)
    m.write(o + 0x2C * k + 0xE0, bytes(0x2C))
    n = m.call(m.main + 0x184A110, desc) & M32
    if n:
        m.call_void(m.main + 0x2878714, o, k, n)
    return 1


@lifted(0x28787E0)
def set_field_kind(m, o, kind, d0, d1, *_):
    """Set the field kind (+0x18) when it changes: an active state clears its counters; a nonzero kind
    starts condition 8 with descriptor (d0, d1)."""
    kind &= 0xFF
    if m.u8(o + 0x18) == kind:
        return 0
    if m.u32(o + 0xC8):
        for off, n in ((0x3D0, 8), (0x3C8, 8), (0x58, 4), (0x90, 4), (0xC8, 4), (0x240, 8), (0x248, 8),
                       (0x250, 8), (0x258, 8), (0x260, 8), (0x268, 4)):
            m.put(o + off, n, 0)
    if kind:
        with m.frame(0x10) as d:
            m.put(d, 8, d0); m.put(d + 8, 8, d1)
            m.call_void(m.main + 0x2878668, o, 8, d, kind)
    m.put(o + 0x18, 1, kind)
    return 1


@lifted(0x13603FC)
def true_13603fc(m, *_): return 1


def _in_play(m, o, ident):
    """The battler `ident` when its id is in play, else 0."""
    v = m.call(m.main + 0x13813E4, m.call(m.main + 0x1482534, o))
    if m.call(m.main + 0x1381400, v, ident) & 1 == 0:
        return 0
    return m.call(m.main + 0x13813F4, o, ident)


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


@lifted(0x283E2A8)
def f_283e2a8(m, o, *_): return m.u64(o + 0xE20)


@lifted(0x283E270)
def stage_command_of(m, o, r, *_):
    with m.frame(0x10) as out:
        m.put(out, 1, 0)
        m.call_void(m.main + 0x1151258, m.call(m.main + 0x283E2A8, m.u64(o + 0x28)), out, r)
        return m.u8(out)


@lifted(0x18675D8)
def f_18675d8(m, o, *_): return m.u64(o + 0x1580)


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


@lifted(0x283EF9C)
def place_side_condition(m, o, out, r, *_):
    """Place side condition r (ident +0, side +4, descriptor +8, pos +0x18) on each position 0x2823478
    names that takes it (0x2887f9c): queue it, send the record, raise 0xf2. out = whether any took."""
    _need(m, m.main + 0x283AAE8); _need(m, m.main + 0x283AEC0)
    took = 0
    with m.frame(0x30) as f:
        d = f + 0x10
        m.write(d, m.read(r + 8, 0x10))
        m.call_void(m.main + 0x283AAE8, m.call(m.main + 0x1146E90, o), m.u32(r), m.u32(r + 4), m.u8(r + 0x18), d)
        m.put(f + 8, 1, 0)
        lst = f + 0xC
        m.call_void(m.main + 0x2823478, m.call(m.main + 0x13813EC, m.call(m.main + 0x1482534, o)), lst, f + 8,
                    m.u8(r + 0x18))
        i = 0
        while i < m.u8(f + 8):
            p = m.u8(lst + i)
            if m.call(m.main + 0x2887F9C, m.call(m.main + 0x1143584, o), p, m.u32(r + 4), d) & 1:
                m.call_void(m.main + 0x2888018, m.call(m.main + 0x1143584, o), p, m.u32(r + 4), d)
                m.call_void(m.main + 0x2888060, o, r, m.u8(lst + i))
                m.call_void(m.main + 0x283AEC0, m.call(m.main + 0x1146E90, o), m.u32(r), m.u32(r + 4),
                            m.u8(r + 0x18), d)
                took = 1
            i += 1
    m.put(out, 1, took)


@lifted(0x283EF60)
def place_side_condition_of(m, o, r, *_):
    with m.frame(0x10) as out:
        m.call_void(m.main + 0x283EF9C, m.call(m.main + 0x283EF94, m.u64(o + 0x28)), out, r)
        return m.u8(out)


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


# Type masks for kinds 1, 3, 4 and 18 of 0x1795308 (a battler's three type fields, bits 10..14, 0..4
# and 5..9 of vf 0x2f8): kinds whose own type blocks them.
_TYPE_BLOCKS = {1: (0x3000, 0xC, 0x180), 3: (0x3800, 0xE, 0x1C0), 4: (0x2400, 9, 0x120), 18: (0x2C00, 0xB, 0x160)}


def _first_party_id(m, x):
    """The cached id at x+0x18, filled from the party's first member when the rule (bit 2 of byte
    0x499) asks for it and it is unset."""
    if m.u8(m.u64(m.u64(x + 8) + 0x38) + 0x499) & 4 and m.u32(x + 0x18) == 0:
        p = m.call(m.main + 0x114C614, m.call(m.main + 0x14B5634, m.u64(m.u64(x + 0x10) + 0x30), 1), 0)
        if p:
            m.put(x + 0x18, 4, m.vcall(p, 0x98))
    return m.u32(x + 0x18)


@lifted(0x1795308)
def can_take_condition(m, o, out, s, *_):
    """Check status condition record s (user +0, target +8, kind +0x10, sub +0x28, flags +0x30..+0x33):
    when the target is immune, already holds it or a check refuses, show why (when +0x31 is set) and
    out = 1; otherwise out = whether 0x1796364 lets it apply."""
    o10 = m.u64(o + 0x10)
    flag_a = flag_b = 0
    code = None
    if m.call(m.main + 0x1381540, m.call(m.main + 0x13813EC, o10)) & 1 and not m.vcall(m.u64(s + 8), 0x78) & 1:
        if m.u8(s + 0x31):
            uid = m.vcall(m.u64(s), 0x98)
            m.call_void(m.main + 0x287DB9C, m.call(m.main + 0x1143584, o), uid & M32, m.u64(s + 8), 2,
                        m.u16(s + 0x10), m.u8(s + 0x28))
            m.put(m.call(m.main + 0x139B698, o) + 0xC0, 1, 1)
        m.put(out, 1, 1)
        return
    u, b = m.u64(s), m.u64(s + 8)
    k, sub, mode = m.u16(s + 0x10), m.u8(s + 0x28), m.u8(s + 0x30)
    if mode != 2 and m.vcall(b, 0x220, k) & 1:
        flag_a, flag_b, code = 1, 1, 1
    else:
        apply = False
        if k <= 5 and m.vcall(b, 0x230) & 0xFFFF and mode == 0:
            code = 3
        elif m.call(m.main + 0x1795EA4, m.call(m.main + 0x1146E90, o), b, u, k, sub) & 1:
            apply = True
        else:
            if m.u8(m.u64(m.main + 0x46D3F00)) & 1 == 0:
                raise UnliftedCall("static 0x46d3f08 not built")
            node = m.vcall(b + 0x28, 0)
            static = m.u64(m.main + 0x46D3F08)
            while node:
                if node == static:
                    if k == 0x2A and m.u8(b + 0x714):
                        code, flag_a = 2, 1
                    break
                node = m.u64(node)
            if code is None:
                r = m.call(m.main + 0x287DD04, o, b)
                if k == 3 and r & 1:
                    code = 3
                elif k in _TYPE_BLOCKS:
                    v = m.vcall(b, 0x2F8)
                    a, c, d = _TYPE_BLOCKS[k]
                    if v & 0x7C00 == a or v & 0x1F == c or v & 0x3E0 == d:
                        code, flag_a = 2, 1
                    else:
                        apply = True
                elif k == 5:
                    v = m.vcall(b, 0x2F8)
                    if (v & 0x3E0 in (0x100, 0x60) or v & 0x1F in (8, 3) or v & 0x7C00 in (0xC00, 0x2000)):
                        code, flag_a = 2, 1
                    else:
                        apply = True
                elif k in (7, 12):
                    uid = m.vcall(b, 0x98) & M32
                    first = _first_party_id(m, m.u64(o10 + 0x310))
                    if first == uid:
                        code, flag_a = 2, 1
                    elif k == 7:
                        apply = True
                    else:
                        bb = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), m.vcall(b, 0x98) & M32)
                        if bb == 0 or m.vcall(bb, 0x78) & 1:
                            apply = True
                        else:
                            code, flag_a = 2, 1
                elif k == 14:
                    if m.vcall(b, 0x230) & 0xFFFF:
                        code = 3
                    else:
                        apply = True
                elif k == 16:
                    from pokeldn.sv.battle.engine import flatbuffer as fb
                    from pokeldn.sv.battle.engine.data import static_table
                    if m.call(m.main + 0x287DD60, o, b) & 1:
                        code = 3
                    else:
                        v = m.vcall(b, 0xF0)
                        table = static_table(m, 0x46DDAA8, 0x46DDAB0, 0x46DDAB8)
                        if fb.u8(m, m.call(m.main + 0xF74860, table, v), 6):
                            code = 3
                        else:
                            apply = True
                elif k == 0x1C and m.call(m.main + 0xF7FFE0, s + 0x18) & 0xFFFF == 0xA5:
                    code = 3
                else:
                    apply = True
        if apply:
            with m.frame(0x10) as f:
                m.put(f, 1, 0)
                r = m.call(m.main + 0x1796364, m.call(m.main + 0x1146E90, o), u, b, k, sub, f) & 1
                if r and (m.u8(s + 0x32) | m.u8(f)):
                    m.call_void(m.main + 0x287DD9C, m.call(m.main + 0x1146E90, o), m.u64(s + 8), m.u64(s),
                                m.u16(s + 0x10), m.u8(s + 0x28), m.u32(s + 0x2C))
                    m.put(m.call(m.main + 0x139B698, o) + 0xC0, 1, 1)
            m.put(out, 1, r)
            return
    if m.u8(s + 0x31) and (flag_a or m.u8(s + 0x28) != 5 or not m.u8(s + 0x33)):
        uid = m.vcall(m.u64(s), 0x98)
        k = m.u16(s + 0x10)
        if flag_b and k == 0x14:
            m.put(m.call(m.main + 0x139B698, o) + 0xC1, 1, 1)
        else:
            m.call_void(m.main + 0x287DB9C, m.call(m.main + 0x1143584, o), uid & M32, m.u64(s + 8), code, k,
                        m.u8(s + 0x28))
            m.put(m.call(m.main + 0x139B698, o) + 0xC0, 1, 1)
    m.put(out, 1, 1)


# 0x17959d4: the a7 text when a condition is applied with +0x28 set, kinds 1..7 (jump table 0x3c6a484).
_APPLY_A7 = {1: 0x2E, 2: 0x2A, 3: 0x2D, 4: 0x2C, 5: 0x2B, 6: 0x2F, 7: 0x30}
# The 0x82 message per kind 1..21 when +0x29 is set (jump table 0x3c6a48b); kind 5 is 0x4f or 0x50,
# kinds 8, 10, 16 and 20 send an empty message.
_APPLY_TEXT = {1: 0x5C, 2: 0x67, 3: 0x61, 4: 0x56, 6: 0x74, 7: 0x6E, 9: 0x6C, 11: 0xBD, 12: 0xC0, 13: 0xC5,
               14: 0xDA, 15: 0x11B, 17: 0x7C, 18: 0xCA, 19: 0xEE, 21: 0xF1}


@lifted(0x17959D4)
def apply_condition_record(m, o, _out, s, *_):
    """Apply status condition record s (user +0, target +8, kind +0x10, descriptor +0x18, flags +0x28,
    +0x29, text +0x30, +0x38): set it on the target, queue it, send its messages, then the kind's
    follow-up (0x2835034 for kinds 0..5, 0x287e310 for 16, else 0x2d0cdf4)."""
    k = m.u16(s + 0x10)
    for a in (0x2835034,) if k <= 5 else (0x287E310, 0x283544C) if k == 0x10 else (0x2D0CDF4,):
        _need(m, m.main + a)
    b = m.u64(s + 8)
    q = m.u64(o + 0x20)
    k = m.u16(s + 0x10)
    desc = s + 0x18
    bid = m.vcall(b, 0x98) & M32
    m.vcall_void(b, 0x368, k, desc)
    m.call_void(m.main + 0x174AE20, m.u64(q + 0x18), bid, k, desc)
    if k <= 5:
        m.call_void(m.main + 0x119AFF0, m.u64(q + 0x18), 0x90, bid, k)
    if m.u8(s + 0x28):
        k2 = m.u16(s + 0x10)
        if k2 in _APPLY_A7:
            m.call_void(m.main + 0x114ADE8, m.u64(o + 0x20), m.u64(s + 8), _APPLY_A7[k2])
    b = m.u64(s + 8)
    k = m.u16(s + 0x10)
    u = m.u64(s)
    flag = m.u8(s + 0x29)
    text = m.u64(s + 0x30)
    if u:
        uid = m.vcall(u, 0x98) & M32
    elif b:
        uid = m.vcall(b, 0x98) & M32
    else:
        uid = 0
    if b and flag:
        with m.frame(0x30) as msg:
            m.write(msg, bytes(0x24))
            if 1 <= k <= 21 and k not in (8, 10, 16, 20):
                if k == 5:
                    n = m.vcall(m.call(m.main + 0x114ACBC, o), 0x68, m.u64(m.main + 0x46E2700))
                    v = m.u64(s + 0x20)
                    t = 0x50 if v & 7 == 1 and (v >> 3) & 0x3F == (n - 1) & M32 else 0x4F
                else:
                    t = _APPLY_TEXT[k]
                m.put(msg, 2, t)
                m.put(msg + 4, 4, m.vcall(b, 0x98))
                m.put(msg + 2, 2, 0x82)
                if k == 0xD:
                    v = m.call(m.main + 0xF7FFE0, desc)
                    m.put(msg + 2, 2, 0x102)
                    m.put(msg + 8, 4, v & 0xFFFF)
            m.call_void(m.main + 0x114B0AC, m.u64(o + 0x20), uid, msg)
    elif text:
        m.call_void(m.main + 0x114B0AC, m.u64(o + 0x20), uid, text)
    u, b, k = m.u64(s), m.u64(s + 8), m.u16(s + 0x10)
    if m.u8(m.u64(m.main + 0x46D3F00)) & 1 == 0:
        raise UnliftedCall("static 0x46d3f08 not built")
    node = m.vcall(b + 0x28, 0)
    static = m.u64(m.main + 0x46D3F08)
    while node and node != static:
        node = m.u64(node)
    if node and k == 3 and m.u16(b + 0x710) == 0x1EC and m.u16(b + 0x718) == 1:
        m.call_void(m.main + 0x282F7A4, m.u64(o + 0x38), b)
        m.call_void(m.main + 0x13606C4, m.u64(o + 0x20), m.vcall(b, 0x98) & M32)
        m.call_void(m.main + 0x187FF90, b, 0, 0)
        m.call_void(m.main + 0x187FE48, m.u64(o + 0x20), m.vcall(b, 0x98) & M32, 0, 0)
        m.call_void(m.main + 0x119AFF0, m.u64(m.u64(o + 0x20) + 0x18), 0xAC, m.vcall(b, 0x98) & M32)
        m.call_void(m.main + 0x114F1EC, m.u64(o + 0x20), m.u64(o + 0x38), b)
        who = m.vcall(u, 0x98) & M32 if u else 0
        m.call_void(m.main + 0x157EBC0, m.u64(m.u64(o + 0x20) + 0x18), 0xCB, who, 0x4C, m.vcall(b, 0x98) & M32,
                    0xFFFF0000)
    k = m.u16(s + 0x10)
    if k <= 5:
        m.call_void(m.main + 0x2835034, m.u64(o + 0x38), m.u64(s + 8), m.u64(s), k, m.u64(s + 0x18), m.u64(s + 0x20))
    elif k == 0x10:
        m.call_void(m.main + 0x287E310, o, m.u64(s + 8), m.u64(s), k)
    else:
        m.call_void(m.main + 0x2D0CDF4, m.u64(o + 0x38), m.u64(s + 8), m.u64(s), k)
    if not m.u8(s + 0x38):
        m.call_void(m.main + 0x177767C, o, m.u64(s + 8))
    if m.u16(s + 0x10) == 5:
        with m.frame(0x20) as f:
            m.put(f + 8, 8, 0x1D); m.put(f + 0x10, 2, 0); m.put(f + 0x12, 1, 0); m.put(f + 0x14, 2, 0)
            m.put(f + 0xC, 4, m.vcall(m.u64(s + 8), 0x98))
            m.put(f, 1, 0)
            m.call_void(m.main + 0x121BDB0, m.u64(m.u64(o + 0x78) + 0x1D40), f, f + 8)


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


@lifted(0x2888968)
def run_1361bb0(m, o, b, *_):
    with m.frame(0x10) as f:
        m.put(f + 8, 8, b)
        m.call_void(m.main + 0x1361BB0, m.call(m.main + 0x1360F04, m.call(m.main + 0x1361214, o)), f, f + 8)


@lifted(0x287E388)
def after_condition_16(m, o, _out, pb, *_):
    """Event 0x8a for battler [pb]; a battler of form 0x7f then goes through 0x2888968."""
    b = m.u64(pb)
    m.call_void(m.main + 0x283544C, m.call(m.main + 0x1146E90, o), b)
    if m.vcall(b, 0xF0) & 0xFFFF == 0x7F:
        return _tail(m, m.main + 0x2888968, o, b)


@lifted(0x287E310)
def condition_16(m, o, b, *_):
    """Unless b is form 0x100 or vf 0x438 says so: 0x287e388 for b."""
    if m.vcall(b, 0xF0) & 0xFFFF != 0x100 and m.vcall(b, 0x438) & 1:
        return
    with m.frame(0x10) as f:
        m.put(f, 8, b)
        m.call_void(m.main + 0x287E388, m.call(m.main + 0x287E380, m.u64(o + 0x78)), f + 8, f)


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


@lifted(0x287E240)
def form_change_allowed(m, o, out, p, *_):
    """out (byte) = whether battler [p] may change form: a fainted one passes; event 0xde must not refuse,
    then with p+9 set event 0xdf decides the result."""
    b = m.u64(p)
    if m.vcall(b, 0x200) & 1:
        m.put(out, 1, 1)
        return
    ident = m.vcall(b, 0x98) & M32
    form = m.vcall(b, 0xF0) & M32
    if m.call(m.main + 0x283B434, m.call(m.main + 0x1146E90, o), ident, form, m.u8(p + 8)) & 1:
        m.put(out, 1, 0)
        return
    m.put(out, 1, 1)
    if m.u8(p + 9):
        return _tail(m, m.main + 0x283B83C, m.call(m.main + 0x1146E90, o), ident, form, m.u8(p + 8))


@lifted(0x287DD60)
def form_change_allowed_of(m, o, b, *_):
    with m.frame(0x20) as f:
        m.put(f + 0x10, 8, b); m.put(f + 0x18, 2, 0x100)
        m.call_void(m.main + 0x287E240, m.call(m.main + 0x287E238, m.call(m.main + 0x1361214, o)), f + 8, f + 0x10)
        return m.u8(f + 8)


def _id(m, b):
    return lambda: m.vcall(b, 0x98)


@lifted(0x1144BD8)
def event_for(m, o, ident, event, *_):
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


@lifted(0x288AA70)
def use_move_event(m, o, _x, r, *_):
    """For move record r (battler +0, move u16 +8, kind +0xa): kind 5 runs 0x288c1d0 and stops when
    0x288c200 and the battle end say so; other kinds note through 0x288c240. Then event 0x23."""
    b = m.u64(r)
    kind = m.u8(r + 0xA)
    if kind == 5:
        m.call_void(m.main + 0x288C1D0, o, b, r, kind)
        if m.call(m.main + 0x288C200, o, m.u64(r)) & 1 and m.call(m.main + 0x114A808, o) & 1 \
                and m.call(m.main + 0x13603FC, o) & 1:
            return
    else:
        m.call_void(m.main + 0x288C240, o, b, m.u16(r + 8), kind)
    return _tail(m, m.main + 0x28384CC, m.call(m.main + 0x1146E90, o), m.u64(r), m.u16(r + 8), m.u8(r + 0xA))


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


@lifted(0x15333F0)
def flinch_or_8e(m, o, out, r, *_):
    """For record r (battler +0, chance +8): a battler other than the party's first, when its own one is
    gone, takes state 6 (vf 0x510(5) set) or 4 (0x1534c4c's roll) through vf 0x508 and out = 1; a missed
    roll below 100 stops; otherwise event 0x8e for it."""
    m.put(out, 1, 0)
    b = m.u64(r)
    own = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), m.vcall(b, 0x98) & M32)
    if own == 0 or m.vcall(own, 0x78) & 1:
        ident = m.vcall(b, 0x98) & M32
        if _first_party_id(m, m.u64(m.u64(o + 0x10) + 0x310)) != ident:
            if m.vcall(b, 0x510, 5) & 1:
                state = 6
            elif m.call(m.main + 0x1534C4C, m.u64(o + 0x38), b, m.u32(r + 8)) & 1:
                state = 4
            elif m.u32(r + 8) < 100:
                return
            else:
                state = None
            if state is not None:
                m.vcall_void(m.u64(r), 0x508, state)
                m.put(out, 1, 1)
                return
    return _tail(m, m.main + 0x1536CF4, m.u64(o + 0x38), m.u64(r))


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


def _held_static(m, b):
    """Whether b's list at +0x28 (vf 0 of that subobject) holds the static at 0x46d3f08."""
    node = m.vcall(b + 0x28, 0)
    if m.u8(m.u64(m.main + 0x46D3F00)) & 1 == 0:
        raise UnliftedCall("static 0x46d3f08 not built")
    static = m.u64(m.main + 0x46D3F08)
    while node and node != static:
        node = m.u64(node)
    return node != 0


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


@lifted(0x1793740)
def secondary_condition(m, o, mv, a, b, out, *_):
    """The move's secondary condition on b: its kind, chance and target descriptor (0x1793efc), event
    0x84 (parameters 4/3 the ids, 0x12 the move, 0x1f the descriptor, 0x1e the kind, 0x48 0, 0x29 the
    chance); unless rule bit 5 of +0x49a, a kind, a positive chance, no 0x48 and a roll below it give
    the kind with the descriptor in out (16 bytes); 0 otherwise."""
    with m.frame(0x10) as d:
        m.call_void(m.main + 0x179372C, d)
        kind = m.call(m.main + 0x1793E2C, mv)
        x = m.call(m.main + 0x1793E94, mv)
        pct = m.call(m.main + 0x1793E60, mv)
        r = m.u64(o + 0x18)
        m.call_void(m.main + 0x1793EFC, m.u64(r + 8), x, a, d, m.u64(r + 0x10))
        def read(ctx):
            return _value(m, ctx, 0xF8), _value(m, ctx, 0x150), _value(m, ctx, 0x248)
        k, c, stop = _event(m, o, 0x84, ((4, _id(m, b), 4, 0x28), (3, _id(m, a), 4, 0x20), (0x12, mv & 0xFFFF, 4, 0x98),
                                         (0x1F, d, "ptr", 0x100), (0x1E, kind & 0xFFFF, 0, 0xF8), (0x48, 0, 1, 0x248),
                                         (0x29, pct, 0, 0x150)), None, read)
        if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49A) & 0x20:
            return 0
        if k & 0xFFFF == 0 or _s32(c) < 1 or stop & 0xFF:
            return 0
        if not m.call(m.main + 0x114DA8C, m.u64(m.u64(o + 0x18) + 0x10), c) & 1:
            return 0
        m.write(out, m.read(d, 0x10))
        return k


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


@lifted(0x113EE0C)
def move_accuracy_stage(m, o, r, *_):
    """For action record r of kind 1 (battler id +0, move u16 +0x10): event 0x11's value for the move,
    queued between 0x5a and 0x5b when 0x119b2a0 accepts the move; kind 5 gives 7, others 0."""
    kind = m.u32(r + 4)
    if kind != 1:
        return 7 if kind == 5 else 0
    ident = m.u32(r)
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), ident)
    mv = m.u16(r + 0x10) if m.u32(r + 4) == 1 else 0
    pp = m.vcall(b, 0x190) & 0xFFFF
    q = m.u64(o + 0x20)
    h = m.u64(q + 0x20)
    bb = m.call(m.main + 0xF21C94, m.u64(m.u64(h + 0x10) + 0x30), ident)
    if not m.call(m.main + 0x119B2A0, m.u64(h + 0x18), bb, mv, pp) & 1:
        return _tail(m, m.main + 0x113EFD0, m.u64(o + 0x38), mv, b)
    m.call_void(m.main + 0x119AFF0, m.u64(q + 0x18), 0x5A, ident, mv, pp)
    v = m.call(m.main + 0x113EFD0, m.u64(o + 0x38), mv, b)
    q = m.u64(o + 0x20)
    h = m.u64(q + 0x20)
    bb = m.call(m.main + 0xF21C94, m.u64(m.u64(h + 0x10) + 0x30), ident)
    m.call_void(m.main + 0x13DC030, m.u64(h + 0x18), bb, mv)
    m.call_void(m.main + 0x119AFF0, m.u64(q + 0x18), 0x5B, ident, mv)
    return v


@lifted(0x1578CE8)
def move_used(m, o, _x, r, *_):
    """After move record r (battler +0, flags [r+8], move [r+0x10], entry [r+0x18], live +0x20): with the
    current entry (+0x18 of the 0xc4 rows at [[o+0x40]+8]) open, fill it (0x1579420) when not filled
    (+0x21), mark the latest log row (+0x16), queue 0x7c, flag a standing battler's move whose field 22
    is set (0x157fbc0, 0xc) and raise event 0x27 for it; a dead record only fills; a closed entry hands
    a live record to 0x15803e4."""
    base = m.u64(m.u64(o + 0x40) + 8)
    e = base + m.u8(base + 0x938) * 0xC4
    entry = e + 0x18
    if not m.u8(r + 0x20):
        if m.u8(e + 0x20):
            return _tail(m, m.main + 0x1579420, m.call(m.main + 0x1578F00, o), m.u64(r + 0x10), entry, m.u64(r + 0x18))
        return
    if not m.u8(e + 0x20):
        return _tail(m, m.main + 0x15803E4, o, m.u64(r), m.u64(r + 0x10), m.u64(r + 8))
    if not m.u8(e + 0x21):
        m.call_void(m.main + 0x1579420, m.call(m.main + 0x1578F00, o), m.u64(r + 0x10), entry, m.u64(r + 0x18))
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    q = m.u64(o + 0x20)
    t = m.u64(m.u64(m.u64(q + 0x20) + 0x10) + 0x130)
    i = _s32(m.u32(t + 8) - 1)
    i = 0x18F if i < 0 else i
    m.put(t + 0xC * i + 0x16, 1, 1)
    m.call_void(m.main + 0x119AFF0, m.u64(q + 0x18), 0x7C)
    if not m.vcall(m.u64(r), 0x200) & 1:
        table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
        if fb.u8(m, m.call(m.main + 0xBF60CC, table, m.u16(m.u64(r + 0x10))), 22):
            m.call_void(m.main + 0x157FBC0, m.u64(o + 0x20), m.u64(r), 0xC)
    ident = m.vcall(m.u64(r), 0x98) & M32
    return _tail(m, m.main + 0x1578F08, m.u64(o + 0x38), ident, m.u16(m.u64(r + 0x10)), m.u64(r + 8), 0x27)


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


@lifted(0x114BD20)
def condition_bit_25(m, pair, *_):
    """Bit 25 of a condition entry's second word, for kinds 1 to 4."""
    w = m.u64(pair + 8)
    return (w >> 25) & 1 if 1 <= w & 7 <= 4 else 0


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


@lifted(0xF7A750)
def build_move_record(m, o, move, move2, x, b, out, *_):
    """Build the move record `out` for b using `move`: events 0x2a and 0x2b on one frame with parameters
    2 (b's id), 0x12 (move), 0x16 (its type, field 2), 0x1d (b's vf 0x2f8), 0x1b (field 4), 99 (field 20
    set), 0x1c (field 17), 0x6d, 0x7a and 0x52 (0); a b condition 0x25 sets 0x16. The record takes what
    comes back (type 0x12 when 0x52 was set), field 5 at +4, move2 at +2 and x at +0xc."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    v2f8 = m.vcall(b, 0x2F8)
    def field(i, fn=fb.u8):
        table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
        return fn(m, m.call(m.main + 0xBF60CC, table, move & M32), i)
    f2 = field(2)
    f17 = field(17)
    f20 = int(field(20) != 0)
    f4 = field(4)
    f5 = field(5)
    ev_push(m, m.u64(o + 0x10))
    for kind, value, typ, slot in ((2, _id(m, b), 4, 0x18), (0x12, lambda: move & 0xFFFF, 4, 0x98), (0x16, lambda: f2, 1, 0xB8),
                                   (0x1D, lambda: v2f8 & 0xFFFF, 0, 0xF0), (0x1B, lambda: f4, 0, 0xE0),
                                   (99, lambda: f20, 0, 0x320), (0x1C, lambda: f17, 0, 0xE8), (0x6D, lambda: 0, 0, 0x370),
                                   (0x7A, lambda: 0, 1, 0x3D8), (0x52, lambda: 0, 1, 0x298)):
        ev_param(m, m.u64(o + 0x10), kind, value() & M32, typ, slot)
    if m.vcall(b, 0x220, 0x25) & 1:
        with m.frame(0x10) as pair:
            r = m.vcall(b, 0x240, 0x25)
            m.put(pair, 8, r[0]); m.put(pair + 8, 8, r[1])
            ctx = m.u64(o + 0x10)
            m.call_void(m.main + 0x15FA4DC, ctx, 0x16, m.call(m.main + 0xF7FFE0, pair))
    m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), 0x2A, 8, 1)
    rec = m.u64(m.u64(m.u64(o + 0x10) + 0x78) + 0xB8)
    if rec:
        m.put(rec + 0xA, 1, 1)
    m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), 0x2B, 8, 1)
    ctx = m.u64(o + 0x10)
    t, v1d, v1b, v1c = (_value(m, ctx, s) for s in (0xB8, 0xF0, 0xE0, 0xE8))
    b63, b6d, b7a = (int(_value(m, ctx, s) != 0) for s in (0x320, 0x370, 0x3D8))
    ok = _value(m, ctx, 0x298) == 0
    ev_pop(m, ctx)
    m.put(out, 2, move); m.put(out + 2, 2, move2); m.put(out + 8, 1, t); m.put(out + 0xC, 4, x); m.put(out + 0x10, 4, 0)
    m.put(out + 6, 2, v1d); m.put(out + 9, 1, v1b); m.put(out + 0xB, 1, b63); m.put(out + 0xA, 1, v1c)
    m.put(out + 0x12, 1, b6d); m.put(out + 4, 2, f5); m.put(out + 0x13, 1, b7a)
    if not ok:
        m.put(out + 8, 1, 0x12)


@lifted(0x1353760)
def scale_entry(m, e, factor, *_):
    from pokeldn.sv.battle.engine.lift0 import _scale_entry
    _scale_entry(m, e, factor)


# Accuracy stage 0..12 -> (numerator, denominator) (rodata 0x3c69d8d).
_ACCURACY_RATIO = ((6, 18), (6, 16), (6, 14), (6, 12), (6, 10), (6, 8), (6, 6), (8, 6), (10, 6), (12, 6), (14, 6),
                   (16, 6), (18, 6))


def _not_ally(m, o, ident):
    """Whether `ident`'s side entry (0x10e2dd4) is missing or outside 1..4."""
    x = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x18) + 0x290) + 8) + 0x50), ident)
    return x == 0 or m.s(x, 4) > 4 or m.s(x, 4) == 0


@lifted(0x157EF78)
def move_hits(m, o, a, b, mv, out, *_):
    """Whether a's move [mv] hits b: a protected target or a move whose field 6 is 'e' always does; event
    0x40 (parameters 3/4 the ids, 0x59) can make it sure, as can b's condition 0x21; otherwise the
    move's accuracy (0x282eb24, event 0x42) goes through the accuracy/evasion stages of event 0x41
    (0x2a/0x2b, the ratio 0x38, 0x52 to ignore evasion), the rule's adjustments, and a roll."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    if out:
        m.put(out, 1, 0)
    if m.call(m.main + 0x157C614, m.u64(o + 0x18), a, b) & 1:
        return 1
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    if fb.u8(m, m.call(m.main + 0xBF60CC, table, m.u16(mv)), 6) == 0x65:
        return 1
    sure = _event(m, o, 0x40, ((3, _id(m, a), 4, 0x20), (4, _id(m, b), 4, 0x28), (0x59, 0, 1, 0x2D0)), 0x2D0)
    if sure or m.vcall(b, 0x220, 0x21) & 1:
        return 1
    acc = m.call(m.main + 0x282EB24, o, 0x42, a, b, mv) & M32
    ev_push(m, m.u64(o + 0x10))
    for kind, value, typ, slot in ((3, _id(m, a), 4, 0x20), (4, _id(m, b), 4, 0x28), (0x52, lambda: 0, 1, 0x298),
                                   (0x2A, lambda: m.vcall(a, 0xB0, 6), 0, 0x158),
                                   (0x2B, lambda: m.vcall(b, 0xB0, 7), 0, 0x160)):
        ev_param(m, m.u64(o + 0x10), kind, value() & M32, typ, slot)
    e = _param_record(m, m.u64(o + 0x10), 0x38, 0x1C8)
    if e:
        m.put(e + 0xC, 4, 0x1000); m.put(e + 0x10, 4, 0x29); m.put(e + 0x14, 4, 0x20000); m.put(e + 0x18, 8, 0)
        m.put(e + 0xA, 1, 3)
    m.call_void(m.main + 0xF7B310, m.u64(o + 0x10), 0x41, 8, 1)
    frame = m.u64(m.u64(o + 0x10) + 0x78)
    rec = m.u64(frame + 0x158)
    stage = (m.s(rec + 0xC, 1) if rec else 0) + 6
    evasion = _value(m, m.u64(o + 0x10), 0x160)
    ignore = _value(m, m.u64(o + 0x10), 0x298)
    b4 = m.vcall(b, 0x220, 0x11) & 0xFF
    if m.vcall(a, 0x510, 0xE) & 1:
        rec = m.u64(m.u64(m.u64(o + 0x10) + 0x78) + 0x1C8)
        if rec:
            m.call_void(m.main + 0x1353760, rec, 0x1333)
    ratio = _value(m, m.u64(o + 0x10), 0x1C8)
    ev_pop(m, m.u64(o + 0x10))
    ev8 = _s32(evasion << 24) >> 24
    if not (ignore & 0xFF == 0 and (_s32(evasion << 24) < 0x6000001 or b4 ^ 1)):
        ev8 = 6
    s = max(stage - ev8, 0)
    s = min(s, 12)
    num, den = _ACCURACY_RATIO[s]
    acc = min(((acc * num) & M32) // den, 100)
    p = (acc * ratio) & M32
    acc = min((p >> 12) + int(p & 0xFFF > 0x800), 100)
    rule = m.u64(m.u64(o + 8) + 0x38)
    if not m.u8(rule + 0x499) & 4 and m.u32(rule + 0x30) < 2:
        if _not_ally(m, o, m.vcall(b, 0x98) & M32) and m.vcall(b, 0x460) & 0xFF == 0xFF:
            acc = acc - 10 if acc > 9 else 0
            if out:
                m.put(out, 1, 1)
    flags = m.u64(rule + 0x498)
    if flags & 0x200000:
        acc = 100
    final = acc
    if flags >> 33 & 1:
        x = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x18) + 0x290) + 8) + 0x50), m.vcall(a, 0x98) & M32)
        if x and m.s(x, 4) == 1:
            y = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x18) + 0x290) + 8) + 0x50), m.vcall(b, 0x98) & M32)
            if (y == 0 or m.s(y, 4) != 1) and m.vcall(a, 0x510, 0x1B) & 1:
                final = 100
    return m.call(m.main + 0x114DA8C, m.u64(m.u64(o + 0x18) + 0x10), final) & 1


@lifted(0x19D40F4)
def hit_count(m, o, b, move, out, flag, *_):
    """The number of hits of b's `move` into the 7-byte record out: field 9 of the move gives the most
    hits (above 1 a roll, 0x19d4f2c); event 0x44 (parameters 3 b's id, 0x2c the most, 0x12 the move, 0x54
    flag, 0x2d the roll, 0x59/0x49/0x85 0) then event 0xf3 with what came back decide the count +0, the
    byte +2 (0x49), whether it may stop early +3 and the single-hit flags +5/+6."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    most = fb.u8(m, m.call(m.main + 0xBF60CC, table, move & M32), 9)
    if most > 1:
        r = m.u64(o + 0x18)
        n = m.call(m.main + 0x19D4F2C, m.u64(r + 8), most, m.u64(r + 0x10)) & 0xFF
    else:
        n, most = 1, 1
    m.put(out + 1, 1, 0); m.put(out + 4, 1, 7)
    def read(ctx):
        rec = m.u64(m.u64(ctx + 0x78) + 0x170)
        return (m.u8(rec + 0xC) if rec else 0), _value(m, ctx, 0x2D0), _value(m, ctx, 0x250), _value(m, ctx, 0x430)
    a, b59, c49, d85 = _event(m, o, 0x44, ((3, _id(m, b), 4, 0x20), (0x2C, most, 4, 0x168), (0x12, move & 0xFFFF, 4, 0x98),
                                           (0x54, flag & 1, 4, 0x2A8), (0x2D, n, 0, 0x170), (0x59, 0, 1, 0x2D0),
                                           (0x49, 0, 1, 0x250), (0x85, 0, 1, 0x430)), None, read)
    def final(ctx):
        v = _value(m, ctx, 0x170)
        c = _value(m, ctx, 0x250)
        if most < 2:
            if v & 0xFE == 0:
                vals = (1, 0, 0, 1, 1)
            else:
                vals = (v, c, 0, 0, 0)
        elif _value(m, ctx, 0x430) == 0 and _value(m, ctx, 0x2D0):
            vals = (most, 0, 1, 0, 0)
        else:
            vals = (v, c, 1, 0, 0)
        for off, val in zip((0, 2, 3, 5, 6), vals):
            m.put(out + off, 1, val)
    _event(m, o, 0xF3, ((3, _id(m, b), 4, 0x20), (0x2C, most, 4, 0x168), (0x12, move & 0xFFFF, 4, 0x98),
                        (0x54, flag & 1, 4, 0x2A8), (0x59, b59, 4, 0x2D0), (0x85, d85, 4, 0x430), (0x2D, a, 0, 0x170),
                        (0x49, c49, 1, 0x250)), None, final)


@lifted(0x19D4F2C)
def roll_hits(m, _x, most, rand, *_):
    """For a 2-to-5-hit move (most 5) a roll below 100: 2 hits under 35, 3 under 70, 4 under 85, else 5;
    other values come back unchanged."""
    from pokeldn.sv.battle.engine.random import step
    if most & 0xFF != 5:
        return most & M32
    m.put(rand + 0x20, 8, m.u64(rand + 0x20) + 1)
    s0, s1 = m.u64(rand + 8), m.u64(rand + 0x10)
    while True:
        out, s0, s1 = step(s0, s1)
        if out & 0x7F < 100:
            break
    m.put(rand + 8, 8, s0); m.put(rand + 0x10, 8, s1)
    r = out & 0x7F
    return 2 if r < 35 else 3 if r < 70 else 4 if r < 85 else 5


@lifted(0x173C1F4)
def events_30_31(m, o, b, mv, ident, out, *_):
    """Event 0x30 then 0x31 for b's move: returns 0x30's id (byte), [out] = its flag set."""
    with m.frame(0x10) as f:
        m.put(f, 1, 0)
        r = m.call(m.main + 0x173E018, m.u64(o + 0x38), b, mv, ident, f) & 0xFF
        m.call_void(m.main + 0x173DB88, m.u64(o + 0x38), b, r, mv, m.u8(f))
        m.put(out, 1, int(m.u8(f) != 0))
        return r


@lifted(0x174FA60)
def check_each_target_3e(m, o, _x, r, *_):
    """For each target of the list [r+0x10] (cursor +0xa8): when event 0x3e (user [r], move [r+8]) says
    so, 0x157a950 on the current entry, 0x174ff2c and drop the target (0x157bf08)."""
    _need(m, m.main + 0x174FF2C)
    lst = m.u64(r + 0x10)
    m.put(lst + 0xA8, 1, 0)
    while True:
        lst = m.u64(r + 0x10)
        i = m.u8(lst + 0xA8)
        if i >= m.u8(lst + 0xA6):
            return
        m.put(lst + 0xA8, 1, i + 1)
        t = m.u64(lst + 8 * i)
        if t == 0:
            return
        if m.call(m.main + 0x174FB1C, m.u64(o + 0x38), m.u64(r), t, m.u64(r + 8)) & 1:
            m.call_void(m.main + 0x157A950, m.call(m.main + 0x139B698, o) + 0x10)
            m.call_void(m.main + 0x174FF2C, m.u64(o + 0x38), m.u64(r), t)
            m.call_void(m.main + 0x157BF08, m.u64(r + 0x10), t)


@lifted(0x174FF2C)
def event_3f(m, o, a, b, *_):
    _event(m, o, 0x3F, ((3, _id(m, a), 4, 0x20), (4, _id(m, b), 4, 0x28)))


@lifted(0x157C508)
def hit_check_of(m, o, out, r, *_):
    """Run the hit check 0x157c844 for record r (move +0, user +8, target +0x10, levels +0x18, event
    u16 +0x20); out (byte) = whether it applies. With a text it is shown for the target (when +0x22)
    and 0xc0 of the current entry takes the second flag; without one, a target with neither flag gets
    0x287ec30 (when +0x22)."""
    with m.frame(0x40) as f:
        text = f + 0x10
        flags = f
        m.write(text, bytes(0x24))
        m.write(flags, bytes(4))
        m.call_void(m.main + 0x157C844, m.u64(o + 0x38), m.u64(r), m.u64(r + 8), m.u64(r + 0x10), m.u64(r + 0x18),
                    m.u16(r + 0x20), flags, flags + 1, flags + 2, flags + 3, text)
        if not m.u8(flags):
            m.put(out, 1, 0)
            return
        m.put(out, 1, 1)
        if m.call(m.main + 0x17CE3AC, text) & 1:
            if m.u8(r + 0x22):
                ident = m.vcall(m.u64(r + 0x10), 0x98) & M32
                m.call_void(m.main + 0x287EBCC, o, ident, m.u8(flags + 3), text)
                m.put(m.call(m.main + 0x139B698, o) + 0xC0, 1, m.u8(flags + 1))
        elif not (m.u8(flags + 1) | m.u8(flags + 2)) and m.u8(r + 0x22):
            ident = m.vcall(m.u64(r + 0x10), 0x98) & M32
            m.call_void(m.main + 0x287EC30, o, ident, m.u8(flags + 3))


@lifted(0x287EBCC)
def show_text_for(m, o, ident, flag, text, *_):
    """Send the record (ident, flag bit, the 0x24-byte text) through 0x114aab0 on 0x1807950's queue."""
    with m.frame(0x40) as s:
        m.write(s, bytes(0x2C))
        m.put(s, 4, ident); m.put(s + 4, 1, flag & 1)
        m.call_void(m.main + 0x287ECA8, s + 8, text)
        q = m.call(m.main + 0x1807950, m.call(m.main + 0x1361214, o))
        return _tail(m, m.main + 0x114AAB0, q, s + 0x30, s)


@lifted(0x287EC30)
def show_text_48(m, o, ident, flag, *_):
    """show_text_for with the text (kind 2, 0x48) naming ident."""
    with m.frame(0x30) as t:
        m.write(t, bytes(0x24))
        m.call_void(m.main + 0x2843244, t, 2, 0x48)
        m.call_void(m.main + 0x284325C, t, ident)
        m.call_void(m.main + 0x284E2A0, t)
        m.call_void(m.main + 0x287EBCC, o, ident, flag & 1, t)


@lifted(0x284E2A0)
def set_bit_15(m, t, *_):
    m.put(t + 2, 2, m.u16(t + 2) | 0x8000)


@lifted(0x158125C)
def clear_ffff(m, p, *_):
    m.put(p, 8, M64); m.put(p + 8, 2, 0xFFFF)


@lifted(0x157A95C)
def push_ca_237(m, o, who, *_):
    return _tail(m, m.main + 0x157EBC0, m.u64(o + 0x18), 0xCA, who & M32, 0x237, 0xFFFF0000)


@lifted(0x172A670)
def event_07(m, o, b, *_):
    _event(m, o, 7, ((3, _id(m, b), 4, 0x20),))


@lifted(0x172A5F0)
def note_move_entry(m, o, pos, p, mv, *_):
    """The current entry's move part (+0x10: move u16 [mv], pos, p, 0, 0) filled through 0x1579420."""
    e = m.call(m.main + 0x139B698, o) + 0x10
    m.put(e, 2, m.u16(mv)); m.put(e + 2, 1, pos); m.put(e + 3, 1, p); m.put(e + 4, 1, 0); m.put(e + 6, 2, 0)
    with m.frame(0x10) as f:
        m.call_void(m.main + 0x158125C, f)
        m.call_void(m.main + 0x1579420, m.call(m.main + 0x1578F00, o), mv, e, f)


@lifted(0x172A09C)
def use_move_6(m, o, out, r, *_):
    """Event 6 for record r (battler +0, move +8, byte +0x10): out[0] = whether it went on; out[1] = whether
    the move is noted as used (0x172a5f0, event 7), otherwise the 0x237 text."""
    b, mv = m.u64(r), m.u64(r + 8)
    m.put(out, 2, 0)
    with m.frame(0x10) as f:
        m.put(f, 1, m.u8(r + 0x10)); m.put(f + 4, 1, 0); m.put(f + 8, 1, 0)
        m.call_void(m.main + 0x172A19C, m.u64(o + 0x38), b, f, f + 8, f + 4)
        if not m.u8(f + 8):
            return
        side = m.call(m.main + 0x13813EC, m.call(m.main + 0x1482534, o))
        pos = m.call(m.main + 0xFE161C, side, m.vcall(b, 0x98) & M32)
        if m.u8(f + 4):
            m.call_void(m.main + 0x172A5F0, o, pos & M32, m.u8(f), mv)
            m.call_void(m.main + 0x172A670, m.u64(o + 0x38), b)
            m.put(out + 1, 1, 1)
        else:
            m.call_void(m.main + 0x157A95C, m.call(m.main + 0x1143584, o), m.vcall(m.u64(r), 0x98) & M32)
        m.put(out, 1, 1)


@lifted(0x157C404)
def hit_check_each(m, o, _x, r, *_):
    """For each target of the list [r+0x10] (cursor +0xa8) not protected (0x157c614, when +0x22): the hit
    check 0x157c508 for (move [r], user [r+8], target, levels [r+0x18], event u16 +0x20, show flag: the
    move's +0x13 clear or a single target); a target it applies to leaves the list."""
    lst = m.u64(r + 0x10)
    m.put(lst + 0xA8, 1, 0)
    with m.frame(0x30) as s:
        while True:
            lst = m.u64(r + 0x10)
            i = m.u8(lst + 0xA8)
            if i >= m.u8(lst + 0xA6):
                return
            m.put(lst + 0xA8, 1, i + 1)
            t = m.u64(lst + 8 * i)
            if t == 0:
                return
            if m.u8(r + 0x22) and m.call(m.main + 0x157C614, m.u64(o + 0x10), m.u64(r + 8), t) & 1:
                continue
            mv = m.u64(r)
            m.put(s, 8, mv); m.put(s + 8, 8, m.u64(r + 8)); m.put(s + 0x10, 8, t); m.put(s + 0x18, 8, m.u64(r + 0x18))
            m.put(s + 0x20, 2, m.u16(r + 0x20))
            m.put(s + 0x22, 1, (m.u8(mv + 0x13) ^ 1) | int(m.u8(m.u64(r + 0x10) + 0xA6) < 2))
            out = s + 0x28
            m.call_void(m.main + 0x157C508, m.u64(m.u64(o + 0x78) + 0x300), out, s)
            if m.u8(out):
                m.call_void(m.main + 0x157BF08, m.u64(r + 0x10), t)


@lifted(0x1143624)
def raid_count_open(m, o, *_):
    """In battle mode 2: whether 0x1149124 finds any (on [[o+0x78]+0x1f00]); 0 otherwise."""
    if m.call(m.main + 0x1143680, o) & M32 != 2:
        return 0
    with m.frame(0x10) as f:
        m.put(f, 1, 0)
        m.call_void(m.main + 0x1149124, m.call(m.main + 0x114368C, m.u64(o + 0x78)), f, f + 8)
        return int(m.u8(f) != 0)


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


@lifted(0x113EE04)
def f_113ee04(m, o, *_):
    return _tail(m, m.main + 0x144B6C8, m.u64(o + 8))


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


@lifted(0x13DBEA4)
def note_chosen_moves(m, o, *_):
    """For each move action (kind 1 at +4, move u16 +0x10) of the 0x8c-byte rows at [o+0x48]+8 (count
    +0x2420) that 0x119b2a0 accepts: queue 0x5a (id, move, PP), event 0x17 and 0x13dbfd4."""
    i = 0
    while True:
        rows = m.u64(o + 0x48)
        n = m.u8(rows + 0x2420)
        if i >= n:
            return
        e = rows + 8 + 0x8C * i
        if m.u32(e + 4) == 1 and m.u16(e + 0x10):
            mv = m.u16(e + 0x10)
            b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), m.u32(e))
            ident = m.u32(e)
            q = m.u64(o + 0x20)
            pp = m.vcall(b, 0x190) & 0xFFFF
            h = m.u64(q + 0x20)
            bb = m.call(m.main + 0xF21C94, m.u64(m.u64(h + 0x10) + 0x30), ident)
            if m.call(m.main + 0x119B2A0, m.u64(h + 0x18), bb, mv, pp) & 1:
                m.call_void(m.main + 0x119AFF0, m.u64(q + 0x18), 0x5A, ident, mv, pp)
                m.call_void(m.main + 0x13DC120, m.call(m.main + 0x1146E90, o), b, mv)
                m.call_void(m.main + 0x13DBFD4, m.u64(o + 0x20), ident, mv)
        i += 1


@lifted(0x283E66C)
def queue_10_if_standing(m, o, out, p, *_):
    """out (byte) = 0x288426c for battler [p] when it is standing, else 0."""
    b = m.call(m.main + 0x13813F4, o, m.u32(p))
    if m.vcall(b, 0x200) & 1:
        m.put(out, 1, 0)
        return
    m.put(out, 1, m.call(m.main + 0x288426C, m.call(m.main + 0x1143584, o), m.u32(p)) & 1)


@lifted(0x1143E3C)
def sort_targets_by_speed(m, o, _x, pl, *_):
    """Sort the target list [pl] (battlers +0, u16 +0x58 and +0x90 alongside, count +0xa6) fastest first
    by event 0x13 speed; a tie swaps on a coin flip."""
    lst = m.u64(pl)
    n = m.u8(lst + 0xA6)
    if n == 0:
        return
    speed = []
    for k in range(n):
        lst = m.u64(pl)
        b = m.u64(lst + 8 * k) if k < m.u8(lst + 0xA6) else 0
        speed.append(m.call(m.main + 0x1144194, m.u64(o + 0x38), b, 1) & 0xFFFF)
    for i in range(max(n, 1)):
        for j in range(i + 1, n):
            a, c = speed[i], speed[j]
            swap = a < c
            if a == c:
                rand = m.call(m.main + 0x11440E8, m.u64(o + 0x10))
                swap = m.call(m.main + 0x11440F0, rand, 2) & M32 != 0
            if not swap:
                continue
            if i < 0xB and j < 0xB:
                lst = m.u64(pl)
                for base, size in ((0, 8), (0x58, 2), (0x90, 2)):
                    x, y = m.u(lst + base + size * i, size), m.u(lst + base + size * j, size)
                    m.put(lst + base + size * i, size, y); m.put(lst + base + size * j, size, x)
            speed[i], speed[j] = c, a


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


@lifted(0x11421F0)
def random_below(m, o, n, *_):
    return _tail(m, m.main + 0x11440F0, m.call(m.main + 0x11440E8, m.u64(o + 0x10)), n & M32)


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


@lifted(0x14D973C)
def move_flag_5(m, move, *_):
    """Field 5 of the move record (u8 != 0)."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    return int(fb.u8(m, m.call(m.main + 0xBF60CC, table, move & M32), 5) != 0)


@lifted(0x157C08C)
def move_targets_pass(m, o, _x, r, *_):
    """The target-selection pass of a move (user [r], move [r+8], levels [r+0x10], targets [r+0x18]):
    hit checks for events 0x32, 0x34 (between events 0x33 and 0x35), a per-target pass for moves whose
    field 23 is set (event 0x3c, the 0x38 hit check, dropping the targets that avoid it through
    0x287f1a8), then 0x39; a move that lost all its targets ends through 0x157bf90 (4) when +0x20 is
    set."""
    def checks(event):
        with m.frame(0x30) as f:
            s = f + 8
            m.put(s, 8, m.u64(r + 8)); m.put(s + 8, 8, m.u64(r)); m.put(s + 0x10, 8, m.u64(r + 0x18))
            m.put(s + 0x18, 8, m.u64(r + 0x10)); m.put(s + 0x20, 2, event); m.put(s + 0x22, 1, 0)
            m.call_void(m.main + 0x157C404, m.u64(m.u64(o + 0x78) + 0x360), f, s)
    checks(0x32)
    lst = m.u64(r + 0x18)
    ended = (m.u8(lst + 0xA7) or m.u8(lst + 0xA9)) and m.u8(lst + 0xA6) == 0
    user, mv, levels = m.u64(r), m.u64(r + 8), m.u64(r + 0x10)
    m.call_void(m.main + 0x157D6F4, m.u64(o + 0x38), mv, user, lst)
    checks(0x34)
    m.call_void(m.main + 0x157DBAC, m.u64(o + 0x38), mv, user, lst)
    user, mv, levels, lst = m.u64(r), m.u64(r + 8), m.u64(r + 0x10), m.u64(r + 0x18)
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    if fb.u8(m, m.call(m.main + 0xBF60CC, table, m.u16(mv)), 23):
        m.put(lst + 0xA8, 1, 0)
        t = 0
        if m.u8(lst + 0xA6):
            t = m.u64(lst)
            m.put(lst + 0xA8, 1, 1)
        while t:
            drop = False
            if m.vcall(t, 0x510, 7) & 1:
                if not m.vcall(t, 0x510, 0x10) & 1 or m.call(m.main + 0x14D973C, m.u16(mv)) & 1:
                    drop = not m.call(m.main + 0x157E558, m.u64(o + 0x38), user, t, mv) & 1
            elif not m.call(m.main + 0x157E558, m.u64(o + 0x38), user, t, mv) & 1:
                with m.frame(0x30) as f:
                    s = f + 8
                    m.put(s, 8, mv); m.put(s + 8, 8, user); m.put(s + 0x10, 8, t); m.put(s + 0x18, 8, levels)
                    m.put(s + 0x20, 2, 0x38); m.put(s + 0x22, 1, 1)
                    m.call_void(m.main + 0x157C508, m.u64(m.u64(o + 0x78) + 0x300), f, s)
                    drop = m.u8(f) != 0
            if drop:
                single = not (m.u8(mv + 0x13) != 0 and m.u8(lst + 0xA6) > 1)
                m.call_void(m.main + 0x157BF08, lst, t)
                if single and not m.u8(m.call(m.main + 0x139B698, o) + 0xC0):
                    m.call_void(m.main + 0x287F1A8, o, user, t, mv)
                m.put(m.call(m.main + 0x139B698, o) + 0xC0, 1, 0)
            i = m.u8(lst + 0xA8)
            if i >= m.u8(lst + 0xA6):
                break
            m.put(lst + 0xA8, 1, i + 1)
            t = m.u64(lst + 8 * i)
    checks(0x39)
    if ended:
        return
    lst = m.u64(r + 0x18)
    if not (m.u8(lst + 0xA7) or m.u8(lst + 0xA9)) or m.u8(lst + 0xA6) or m.u64(r + 0x20) == 0:
        return
    return _tail(m, m.main + 0x157BF90, m.call(m.main + 0x1143584, o), m.vcall(m.u64(r), 0x98) & M32, 4)


def _f32(x):
    import struct
    return struct.unpack("<f", struct.pack("<f", x))[0]


def _u32_map_needs_rehash(m, table, key):
    """True when operator[] of a missing `key` grows the buckets (0xf7c240)."""
    from pokeldn.sv.battle.engine.containers import find
    if find(m, table, key & M32, 4):
        return False
    import struct
    n = m.u64(table + 8)
    load = struct.unpack("<f", m.read(table + 0x60, 4))[0]
    return n == 0 or _f32(_f32(load) * _f32(float(n))) < _f32(float(m.u64(table + 0x58) + 1))


@lifted(0xF7A448)
def map_u32_slot(m, table, key_ptr, *_):
    """unordered_map<u32, u32[2]>::operator[]: the value (node+0x14) of the u32 at key_ptr; a missing key
    gets a zeroed node from the allocator [table+0x38] (pushed on the thread's object stack while the
    node is built), growing the buckets through 0xf7c240 past the max load."""
    from pokeldn.sv.battle.engine.containers import find, _bucket
    from pokeldn.sv.battle.engine.lift0 import _tls_stack
    key = m.u32(key_ptr)
    node = find(m, table, key, 4)
    if node:
        return node + 0x14
    n = m.u64(table + 8)
    alloc = m.u64(table + 0x38)
    node = m.vcall(alloc, 0x10, 0x20, 4)
    if not node:
        raise UnliftedCall("allocator out of memory")
    t = _tls_stack(m)
    if t:
        depth = m.u64(t + 0x80)
        if depth >= 0x10:
            raise UnliftedCall("abort: object stack full")
        m.put(t + 8 * depth, 8, m.u64(table + 0x38))
        m.put(t + 0x80, 8, depth + 1)
    m.put(node + 0x10, 4, m.u32(key_ptr)); m.put(node + 0x14, 8, 0)
    if t:
        m.put(t + 0x80, 8, m.u64(t + 0x80) - 1)
    m.put(node, 8, 0); m.put(node + 8, 8, key)
    if _u32_map_needs_rehash(m, table, key):
        import math
        import struct
        load = struct.unpack("<f", m.read(table + 0x60, 4))[0]
        grow = (n << 1) | int(n < 3 or not n & (n - 1) == 0)
        need = math.ceil(_f32(_f32(float(m.u64(table + 0x58) + 1)) / _f32(load)))
        m.call_void(m.main + 0xF7C240, table, max(grow, need))
        n = m.u64(table + 8)
    b = _bucket(key, n)
    buckets = m.u64(table)
    prev = m.u64(buckets + 8 * b)
    if prev == 0:
        head = table + 0x30
        m.put(node, 8, m.u64(head))
        m.put(head, 8, node)
        m.put(buckets + 8 * b, 8, head)
        nxt = m.u64(node)
        if nxt:
            m.put(buckets + 8 * _bucket(m.u64(nxt + 8), n), 8, node)
    else:
        m.put(node, 8, m.u64(prev))
        m.put(prev, 8, node)
    m.put(table + 0x58, 8, m.u64(table + 0x58) + 1)
    return node + 0x14


@lifted(0x157C00C)
def mark_bit(m, o, ident, kind, *_):
    """Set bit `kind` (0..4) in word [o+0x70] of the entry for `ident` in the map at o+8, adding a zeroed
    entry first."""
    kind &= 0xFF
    if kind > 4:
        return
    with m.frame(0x10) as f:
        m.put(f, 4, ident & M32)
        if not m.call(m.main + 0x157EA98, o + 8, f):
            m.put(m.call(m.main + 0xF7A448, o + 8, f), 8, 0)
        p = m.call(m.main + 0xF7A448, o + 8, f) + 4 * m.u8(o + 0x70)
        m.put(p, 4, m.u32(p) | (1 << kind))


@lifted(0x157BFD4)
def mark_bit_of(m, o, ident, kind, *_):
    """0x157c00c on [[o+0x10]+0x170]."""
    return _tail(m, m.main + 0x157C00C, m.u64(m.u64(o + 0x10) + 0x170), ident & M32, kind & M32)


@lifted(0x157BF90)
def mark_and_report(m, o, ident, kind, *_):
    """Mark bit `kind` for `ident` (0x157bfd4 on [o+0x20]), then queue command 0x52 (ident, kind)."""
    m.call_void(m.main + 0x157BFD4, m.u64(o + 0x20), ident & M32, kind & M32)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x52, ident & M32, kind & 0xFF)


@lifted(0x157EBA0)
def report_pair(m, o, a, text, b, *_):
    """Queue command 0xcb (a, text, b) on [o+0x18]."""
    return _tail(m, m.main + 0x157EBC0, m.u64(o + 0x18), 0xCB, a & M32, text & 0xFFFF, b & M32, 0xFFFF0000)


@lifted(0x2832EA8)
def raise_avoided(m, o, user, target, move, *_):
    """Event 0xd1 with the user (3), the target (4), the move id (0x12) and move[0xb] (0x63)."""
    _event(m, o, 0xD1, [(3, lambda: m.vcall(user, 0x98), 4, 0x20), (4, lambda: m.vcall(target, 0x98), 4, 0x28),
                        (0x12, lambda: m.u16(move), 4, 0x98), (0x63, lambda: m.u8(move + 0xB), 4, 0x320)])


@lifted(0x287F1DC)
def field_1380(m, o, *_):
    return m.u64(o + 0x1380)


@lifted(0x287F1E4)
def target_avoided(m, o, _x, args, *_):
    """args = (user, target, move): 0x114ade8(target, 0x76), command 0xcb (user, 0xae, target),
    0x1146e90, then event 0xd1."""
    user, target, move = m.u64(args), m.u64(args + 8), m.u64(args + 0x10)
    m.call_void(m.main + 0x114ADE8, m.call(m.main + 0x1143584, o), target, 0x76)
    q = m.call(m.main + 0x1143584, o)
    a = m.vcall(user, 0x98) & M32
    m.call_void(m.main + 0x157EBA0, q, a, 0xAE, m.vcall(target, 0x98) & M32)
    m.call_void(m.main + 0x1146E90, o)
    return _tail(m, m.main + 0x2832EA8, o, user, target, move)


@lifted(0x287F1A8)
def on_target_avoided(m, o, user, target, move, *_):
    """0x287f1e4 on [[o+0x78]+0x1380] with (user, target, move)."""
    with m.frame(0x20) as f:
        m.put(f + 8, 8, user); m.put(f + 0x10, 8, target); m.put(f + 0x18, 8, move)
        m.call_void(m.main + 0x287F1E4, m.call(m.main + 0x287F1DC, m.u64(o + 0x78)), f, f + 8)


@lifted(0x173C16C)
def redirect_target(m, o, battler, b, mv, out, *_):
    """Events 0x30/0x31 (0x173c1f4) with battler's id: a nonzero result is resolved through 0x13813f4,
    else battler itself."""
    r = m.call(m.main + 0x173C1F4, o, b, mv, m.vcall(battler, 0x98) & M32, out) & M32
    if not r:
        return battler
    return _tail(m, m.main + 0x13813F4, o, r)


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


@lifted(0x113FD2C)
def turn_reset(m, o, *_):
    """Start a turn: flip the marks' half (clearing it), shift the three 0x98-byte history blocks,
    clear the per-turn flags, the event pool and frames, the queue cursors, then 0x1141160, 0x11416c0,
    0x114140c, command 0xb5 and 0x113fffc, 0x121bdb0."""
    t = m.u64(m.u64(o + 0x10) + 0x170)
    h = (~m.u8(t + 0x70)) & 1
    m.put(t + 0x70, 1, h)
    n = m.u64(t + 0x38)
    while n:
        m.put(n + 0x14 + 4 * h, 4, 0)
        n = m.u64(n)
    b = m.u64(m.u64(o + 0x10) + 0x110)
    m.write(b + 0x1D0, m.read(b + 0x138, 0x98))
    m.write(b + 0x138, m.read(b + 0xA0, 0x98))
    m.write(b + 0xA0, m.read(b + 8, 0x98))
    m.write(b + 8, bytes(0x98))
    m.write(b + 0x268, bytes(0x78))
    m.put(b + 0x2EA, 1, 0)
    e = m.call(m.main + 0x113FEE0, m.u64(m.u64(m.u64(o + 0x30) + 8) + 0xD0))
    while e:
        if m.u8(e + 0x42):
            m.put(e + 0x42, 1, 0)
        e = m.call(m.main + 0xF7BA54, m.u64(e + 8), m.u16(e + 0x14))
    c = m.u64(o + 0x30)
    if m.u32(m.u64(c + 0x38) + 0xC08):
        m.call_void(m.main + 0x11496A0, m.u64(c + 0x38))
        m.call_void(m.main + 0x1155180, m.u64(c + 0x58))
        stk = m.u64(c + 0x58)
        m.put(c + 0x78, 8, m.u64(stk + 32 * m.u32(stk + 0x408) + 8))
    m.put(m.u64(o + 0x50) + 0x1B, 1, 0)
    q = m.u64(o + 0x58)
    v = m.u64(q + 0x28)
    for k in range(5):
        m.put(q + 8 * k, 8, v)
    m.call_void(m.main + 0x1141160, o)
    m.call_void(m.main + 0x11416C0, o)
    m.call_void(m.main + 0x114140C, o)
    m.call_void(m.main + 0x119AFF0, m.u64(m.u64(o + 0x20) + 0x18), 0xB5, 0)
    m.call_void(m.main + 0x113FFFC, m.u64(o + 0x38))
    with m.frame(0x20) as f:
        m.write(f, bytes(0x20))
        m.call_void(m.main + 0x121BDB0, m.u64(m.u64(o + 0x78) + 0x1D40), f, f + 8)


@lifted(0x173C7FC)
def add_all_matching(m, o, a, lst, *_):
    """For a list holding a user ([lst]), append each other standing member that 0x173cb54 accepts."""
    from pokeldn.sv.battle.engine.flow import add_member
    from pokeldn.sv.battle.engine.lift1 import _standing
    if not m.u8(lst + 0xA6):
        return
    user = m.u64(lst)
    uid = m.vcall(user, 0x98) & M32
    for b in _standing(m, m.u64(o + 8), m.u64(o + 0x10)):
        if m.vcall(b, 0x98) & M32 == uid:
            continue
        if m.call(m.main + 0x173CB54, m.u64(o + 0x38), a, user, b) & 1:
            add_member(m, lst, b)


@lifted(0x15343A0)
def apply_hits(m, o, _x, r, *_):
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


@lifted(0x1584710)
def member_byte_84(m, lst, b, *_):
    """The +0x84 byte of b's entry in the member list, 0 when b is not in it."""
    for i in range(m.u8(lst + 0xA6)):
        if m.u64(lst + 8 * i) == b:
            return m.u8(lst + 0x84 + i)
    return 0


@lifted(0x2882ADC)
def request_code_3(m, o, b, *_):
    """Apply a one-battler request {b's id, code 3, b's id, +0x30 = 1} through 0x17cdf14."""
    with m.frame(0x70) as sp:
        m.write(sp, bytes(0x70))
        r = sp + 0x10
        m.put(r + 4, 4, 0x31)
        m.call_void(m.main + 0x1146154, r + 0x38)
        m.put(r, 4, m.vcall(b, 0x98) & M32); m.put(r + 4, 4, 3)
        m.put(r + 8, 4, m.vcall(b, 0x98) & M32)
        m.put(r + 0x35, 1, 0); m.put(r + 0x30, 1, 1)
        m.call_void(m.main + 0x17CDF14, m.call(m.main + 0x17CDF0C, m.u64(o + 0x78)), sp, r)


@lifted(0x2882B74)
def report_b4(m, o, a, b, c, d, e, f, *_):
    """Queue command 0xb4 (a, b, c, d, e, f) on [o+0x18]."""
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xB4, a & M32, b & M32, c & M32, d & 0xFFFF,
                 e & 0xFFFF, f & 0xFFFF)


@lifted(0x1777748)
def raise_bc(m, o, b, flag, *_):
    """Event 0xbc with b's id (2) and flag (0x31)."""
    _event(m, o, 0xBC, [(2, lambda: m.vcall(b, 0x98), 4, 0x18), (0x31, flag & 0xFF, 4, 0x190)])


@lifted(0x15835AC)
def after_move_hits(m, o, _x, r, *_):
    """r = (?, move, user, targets, flag): for move kind 9 (move[8]) run 0x2882adc on each target in
    state 3 whose list byte is 1; queue command 0xb4 (text 0x2e9) for each standing target at a fifth of
    its maximum or below outside rule bit 2 with fewer than two of [[o+8]+0x38]+0x30; events 0xab, 0xaa,
    0xac (0x1583930); 0x1777748 for each target with vf 0x2a8; events 0xad, 0xae, 0xaf; then event
    0xb0 with the user (3), the flag (0x54) and the move id (0x12)."""
    def walk(lst):
        m.put(lst + 0xA8, 1, 0)
        if not m.u8(lst + 0xA6):
            return
        t = m.u64(lst)
        m.put(lst + 0xA8, 1, 1)
        while t:
            yield t
            i = m.u8(lst + 0xA8)
            if i >= m.u8(lst + 0xA6):
                return
            m.put(lst + 0xA8, 1, i + 1)
            t = m.u64(lst + 8 * i)

    def steps(*spec):
        for second, event in spec:
            m.call_void(m.main + 0x1583930, m.u64(o + 0x38), m.u64(r + 0x10), m.u64(r + 0x18), m.u64(r),
                        m.u64(r + 8), m.u8(r + 0x20), second, event)

    if m.u8(m.u64(r + 8) + 8) == 9:
        lst = m.u64(r + 0x18)
        for t in walk(lst):
            if m.vcall(t, 0x230) & 0xFFFF == 3 and m.call(m.main + 0x1584710, lst, t) & M32 == 1:
                m.call_void(m.main + 0x2882ADC, o, t)
    lst = m.u64(r + 0x18)
    n = m.u8(lst + 0xA6)
    last = n - 1
    i = 0
    while last >= 0:
        b = m.u64(lst + 8 * i) if i < n else 0
        rules = m.u64(m.u64(o + 8) + 0x38)
        if not m.u8(rules + 0x499) >> 2 & 1 and m.u32(rules + 0x30) < 2:
            h = m.u64(m.u64(o + 0x10) + 0x290)
            p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(h + 8) + 0x50), m.vcall(b, 0x98) & M32)
            if (not p or m.s(p, 4) > 4 or m.s(p, 4) == 0) and m.vcall(b, 0x460) & 0xFF == 0xFF \
                    and not m.vcall(b, 0x200) & 1:
                hp = m.vcall(b, 0x108) & 0xFFFF
                top = m.vcall(b, 0x110) & 0xFFFF
                if hp << 8 <= top * 0x80 and hp and hp << 8 <= (top << 8) // 5:
                    ident = m.vcall(b, 0x98) & M32
                    m.call_void(m.main + 0x2882B74, m.call(m.main + 0x1143584, o), ident, 1, 1, 0x2E9, ident, 0)
        if i == last:
            break
        n = m.u8(lst + 0xA6)
        i += 1
    steps((0, 0xAB), (1, 0xAA), (0, 0xAC))
    for t in walk(m.u64(r + 0x18)):
        c = m.u64(m.u64(o + 0x78) + 0x2E0)
        b = m.call(m.main + 0xF21C94, m.u64(m.u64(c + 0x10) + 0x30), m.vcall(t, 0x98) & M32)
        if m.vcall(b, 0x2A8) & 0xFFFF:
            m.call_void(m.main + 0x1777748, m.u64(c + 0x38), b, 1)
    steps((0, 0xAD), (0, 0xAE), (1, 0xAF))
    user, mv, flag = m.u64(r + 0x10), m.u64(r + 8), m.u8(r + 0x20)
    _event(m, m.u64(o + 0x38), 0xB0, [(3, lambda: m.vcall(user, 0x98), 4, 0x20), (0x54, flag & 1, 4, 0x2A8),
                                      (0x12, lambda: m.u16(mv), 4, 0x98)])


@lifted(0x1141D4C)
def turn_end(m, o, *_):
    """End a turn: 0x121b9b4; vf 0x2c8 and 0x568 and command 0x43 for each member 0x1143e3c lists;
    0x283c488, 0x282fbf4; vf 0x448 and command 0x23 for each id in [[o+0x40]+0x68] (then cleared);
    vf 0 of each listed member's +0x28; 0x121bdb0 with codes 5 and (rule 0x49c bit 1) 0x1a; result 9
    from 0x1399e20; the turn counter (at most 9999), command 0x2d, 0x2d21a74."""
    if m.u8(m.u64(m.main + 0x46D3F00)) & 1 == 0:
        raise UnliftedCall("static 0x46d3f08 not built")
    with m.frame(0x100) as sp:
        lst, a, b = sp + 8, sp + 0xD8, sp + 0xB8

        def listed():
            m.write(lst, bytes(0x8F))
            m.write(sp + 0x98, bytes(0x18)); m.put(sp + 0xB0, 2, 0)
            h = m.u64(m.u64(o + 0x78) + 0x1280)
            m.call_void(m.main + 0x1144704, h, lst)
            m.put(a, 8, lst)
            m.call_void(m.main + 0x1143E3C, m.u64(m.u64(h + 0x78) + 0x17E0), b, a)
            m.put(lst + 0xA8, 1, 0)
            if not m.u8(lst + 0xA6):
                return
            t = m.u64(lst)
            m.put(lst + 0xA8, 1, 1)
            while t:
                yield t
                i = m.u8(lst + 0xA8)
                if i >= m.u8(lst + 0xA6):
                    return
                m.put(lst + 0xA8, 1, i + 1)
                t = m.u64(lst + 8 * i)

        m.put(lst, 1, 1)
        m.call_void(m.main + 0x121B9B4, m.u64(m.u64(o + 0x78) + 0x1F60), a, lst)
        for t in listed():
            c = m.u64(o + 0x20)
            ident = m.vcall(t, 0x98) & M32
            pc = m.u64(m.u64(c + 0x20) + 0x10)
            m.vcall_void(m.call(m.main + 0xF21C94, m.u64(pc + 0x30), ident), 0x2C8)
            m.vcall_void(m.call(m.main + 0xF21C94, m.u64(pc + 0x30), ident), 0x568)
            m.call_void(m.main + 0x119AFF0, m.u64(c + 0x18), 0x43, ident)
        m.call_void(m.main + 0x283C488, m.u64(o + 0x30))
        m.call_void(m.main + 0x282FBF4, m.u64(o + 0x38))
        ids = m.u64(m.u64(o + 0x40) + 0x68)
        k = 0
        while k < m.s(ids + 0x28, 4):
            ident = m.u8(ids + 8 + k) if k < 0x1E else 0
            c = m.u64(o + 0x20)
            b2 = m.call(m.main + 0xF21C94, m.u64(m.u64(m.u64(c + 0x20) + 0x10) + 0x30), ident)
            m.vcall_void(b2, 0x448)
            m.call_void(m.main + 0x119AFF0, m.u64(c + 0x18), 0x23, ident)
            k += 1
            ids = m.u64(m.u64(o + 0x40) + 0x68)
        m.write(ids + 8, bytes(0x1E)); m.put(ids + 0x28, 4, 0)
        for t in listed():
            m.vcall(t + 0x28, 0)
        for code, on in ((5, True), (0x1A, None)):
            if on is None and not m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49C) >> 1 & 1:
                continue
            m.put(lst, 8, code); m.put(lst + 8, 2, 0); m.put(lst + 0xA, 1, 0); m.put(lst + 0xC, 2, 0)
            m.put(a, 1, 0)
            m.call_void(m.main + 0x121BDB0, m.u64(m.u64(o + 0x78) + 0x1D40), a, lst)
    flag = m.u64(m.u64(o + 0x40) + 0x28)
    if not m.u8(flag) and m.call(m.main + 0x1399E20, o) & 1:
        m.put(m.u64(m.u64(o + 0x40) + 0x28), 1, 9)
    c = m.u64(o + 0x20)
    t = m.u64(m.u64(m.u64(c + 0x20) + 0x10) + 0x210)
    if m.u64(t + 8) <= 0x270E:
        m.put(t + 8, 8, m.u64(t + 8) + 1)
    m.call_void(m.main + 0x119AFF0, m.u64(c + 0x18), 0x2D, 0)
    m.call_void(m.main + 0x2D21A74, m.u64(o + 0x40))
    m.put(m.u64(o + 0x40) + 0x88, 1, 0)
    m.put(m.u64(o + 0x40) + 0x90, 8, 0)


def _thunk_78(getter, target):
    def fn(m, o, a, *_):
        with m.frame(0x10) as f:
            m.put(f + 8, 8, a)
            m.call_void(m.main + target, m.call(m.main + getter, m.u64(o + 0x78)), f, f + 8)
    return fn


# Thunks: target([o+0x78] through getter, sp, &arg).
for _addr, _spec in {0x113E948: (0x113E974, 0x1141D4C), 0x11438B4: (0x1143DE8, 0x1143DF0),
                     0x1143DB8: (0x1143DE8, 0x1143DF0), 0x114A904: (0x1143DE8, 0x1143DF0)}.items():
    lifted(_addr)(_thunk_78(*_spec))


def _walk_pre(m, lst):
    """The member list walk with the cursor (+0xa8) advanced before each read."""
    m.put(lst + 0xA8, 1, 0)
    while True:
        i = m.u8(lst + 0xA8)
        if i >= m.u8(lst + 0xA6):
            return
        m.put(lst + 0xA8, 1, i + 1)
        t = m.u64(lst + 8 * i)
        if not t:
            return
        yield t


@lifted(0x157B8D8)
def collect_target_flags(m, o, _x, r, *_):
    """r = (a, b, lst, out): out = up to 10 (target id, two flag bytes from 0x157bb8c), unset entries
    (0, 0xe), count at +0x50."""
    out = m.u64(r + 0x18)
    m.put(out + 0x50, 4, 0)
    for k in range(10):
        m.put(out + 8 * k, 4, 0); m.put(out + 8 * k + 4, 2, 0xE)
    lst = m.u64(r + 0x10)
    for t in _walk_pre(m, lst):
        with m.frame(0x28) as sp:
            m.write(sp, bytes(0x28))
            m.put(sp + 8, 8, m.u64(r + 8)); m.put(sp + 0x10, 8, t); m.put(sp + 0x18, 8, m.u64(r))
            m.call_void(m.main + 0x157BB8C, m.u64(m.u64(o + 0x78) + 0x4A0), sp, sp + 8)
            b0, b1 = m.u8(sp), m.u8(sp + 1)
        out = m.u64(r + 0x18)
        ident = m.vcall(t, 0x98) & M32
        n = m.u32(out + 0x50)
        if n <= 9:
            m.put(out + 8 * n, 4, ident); m.put(out + 8 * n + 4, 1, b0); m.put(out + 8 * n + 5, 1, b1)
            m.put(out + 0x50, 4, n + 1)
        lst = m.u64(r + 0x10)


def _mark_needs_node(m, o, user):
    """Refuse up front when 0x157bf90 would allocate a node for the user (the allocator may refuse after
    this function has written)."""
    from pokeldn.sv.battle.engine.containers import find
    try:
        x = m.u64(m.call(m.main + 0x1143584, o) + 0x20)
        table = m.u64(m.u64(x + 0x10) + 0x170) + 8
        found = find(m, table, m.vcall(user, 0x98) & M32, 4)
    except Exception:       # a replay maps only the pages the native run touched
        found = 0
    if not found:
        raise UnliftedCall("0x157bf90 would insert into its u32 map")


@lifted(0x157BA2C)
def drop_immune_targets(m, o, _x, r, *_):
    """r = (user, move, lst, end, byte): drop each target that neither 0x157d2e4 nor 0x157ef78 keeps
    (0x157bf08, 0x157eeb8 unless the move hits several of them, 0x158097c); a list left empty ends the
    move through 0x157bf90 (1) when end is set."""
    lst = m.u64(r + 0x10)
    if not m.u8(lst + 0xA6) or (m.u8(lst + 0xA7) == 1 and m.u64(lst) == m.u64(r)):
        return
    if m.u64(r + 0x18):
        _mark_needs_node(m, o, m.u64(r))
    with m.frame(0x10) as flag:
        for t in _walk_pre(m, m.u64(r + 0x10)):
            user, mv = m.u64(r), m.u64(r + 8)
            m.put(flag, 1, 0)
            if m.call(m.main + 0x157D2E4, m.u64(o + 0x38), user, t, mv) & 1:
                continue
            if m.call(m.main + 0x157EF78, m.u64(o + 0x38), user, t, mv, flag) & 1:
                continue
            lst = m.u64(r + 0x10)
            n, many = m.u8(lst + 0xA6), m.u8(m.u64(r + 8) + 0x13)
            m.call_void(m.main + 0x157BF08, lst, t)
            if n < 2 or not many:
                m.call_void(m.main + 0x157EEB8, o, m.u64(r), t, m.u16(m.u64(r + 8)), m.u8(flag))
            m.call_void(m.main + 0x158097C, m.u64(o + 0x38), m.u64(r), m.u8(r + 0x20))
    if not m.u64(r + 0x18):
        return
    lst = m.u64(r + 0x10)
    if (m.u8(lst + 0xA7) or m.u8(lst + 0xA9)) and not m.u8(lst + 0xA6):
        q = m.call(m.main + 0x1143584, o)
        m.call_void(m.main + 0x157BF90, q, m.vcall(m.u64(r), 0x98) & M32, 1)


def _pow2(n):
    return n & (n - 1) == 0


def _frees_deferred(m, alloc):
    return m.vcall(alloc, 0xF8) & 1 and m.s(m.call(m.main + 0xB4E600) + 0x12C8, 4) >= 1


@lifted(0x171987C)
def free_buckets(m, pair, ptr, *_):
    """Free a bucket array of [pair] entries through the allocator [pair+8] (vf 0x18, or 0xb48fe8 when
    frees are deferred)."""
    size, alloc = m.u64(pair) * 8, m.u64(pair + 8)
    if _frees_deferred(m, alloc):
        return _tail(m, m.main + 0xB48FE8, alloc, ptr, size, 4)
    return _tail(m, m.u64(m.u64(alloc) + 0x18), alloc, ptr, size, 4)


@lifted(0xF8001C)
def do_rehash(m, table, n, *_):
    """libc++ __do_rehash of a u32-keyed map (buckets +0, count +8, bucket allocator +0x10, first node
    +0x30): a fresh zeroed array of n buckets, the old one freed, the node chain regrouped by bucket."""
    old = m.u64(table)
    if old and _frees_deferred(m, m.u64(table + 0x10)) and 0xB48FE8 not in FUNCTIONS:
        raise UnliftedCall("main+0xb48fe8")
    if n == 0:
        m.put(table, 8, 0)
        if old:
            m.call_void(m.main + 0x171987C, table + 8, old)
        m.put(table + 8, 8, 0)
        return
    arr = m.vcall(m.u64(table + 0x10), 0x10, n * 8, 4)
    if not arr:
        raise UnliftedCall("allocator out of memory")
    m.put(table, 8, arr)
    if old:
        m.call_void(m.main + 0x171987C, table + 8, old)
    m.put(table + 8, 8, n)
    for i in range(n):
        m.put(arr + 8 * i, 8, 0)
    pp = m.u64(table + 0x30)
    if not pp:
        return

    def bucket(h):
        return h & (n - 1) if _pow2(n) else h % n

    phash = bucket(m.u64(pp + 8))
    m.put(arr + 8 * phash, 8, table + 0x30)
    cp = m.u64(pp)
    while cp:
        chash = bucket(m.u64(cp + 8))
        if chash == phash:
            pp = cp
        elif m.u64(arr + 8 * chash) == 0:
            m.put(arr + 8 * chash, 8, pp)
            pp, phash = cp, chash
        else:
            np = cp
            while m.u64(np) and m.u32(cp + 0x10) == m.u32(m.u64(np) + 0x10):
                np = m.u64(np)
            m.put(pp, 8, m.u64(np))
            head = m.u64(arr + 8 * chash)
            m.put(np, 8, m.u64(head))
            m.put(head, 8, cp)
        cp = m.u64(pp)


@lifted(0xF7C240)
def rehash(m, table, want, *_):
    """libc++ rehash(want) of a u32-keyed map: grow to want (rounded to a prime unless a power of two);
    shrink only down to what the size and max load (+0x60) allow."""
    import math
    import struct
    if want == 1:
        want = 2
    elif want & (want - 1):
        want = m.call(m.main + 0x343D400, want)
    n = m.u64(table + 8)
    if want > n:
        return _tail(m, m.main + 0xF8001C, table, want)
    if want == n:
        return
    load = struct.unpack("<f", m.read(table + 0x60, 4))[0]
    need = math.ceil(_f32(_f32(float(m.u64(table + 0x58))) / _f32(load)))
    if n < 3 or not _pow2(n):
        need = m.call(m.main + 0x343D400, need)
    elif need >= 2:
        need = 1 << (need - 1).bit_length()
    new = max(need, want)
    if new < n:
        return _tail(m, m.main + 0xF8001C, table, new)


def _clear_members(m, lst):
    m.write(lst, bytes(0x8F))
    m.write(lst + 0x90, bytes(0x18)); m.put(lst + 0xA8, 2, 0)


@lifted(0x173BCF8)
def select_targets(m, o, _x, r, *_):
    """r = (user, move, byte, slot id u32 at +0x14, lst): fill lst with the move's targets (0x173c128,
    then 0x173c16c for a lone redirected target or 0x173c7fc, then 0x173c268), then keep only those still
    in the battle whose position 0x1381420 is not 10; lst+0xa9 takes the high mark before the filter."""
    from pokeldn.sv.battle.engine.flow import add_member
    with m.frame(0xC0) as sp:
        flag, redirected, copy = sp + 0xC, sp + 8, sp + 0x10
        a1 = m.u64(o + 8)
        m.put(flag, 1, 0)
        pos = m.u8(r + 0x10)
        keep = 0 if m.u8(m.u64(r + 8) + 0x10) else \
            m.call(m.main + 0x173D2DC, m.u64(o + 0x38), m.u64(r), m.u64(r + 8)) & 0xFF
        _clear_members(m, m.u64(r + 0x18))
        user, mv = m.u64(r), m.u64(r + 8)
        place = m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), m.u32(r + 0x14)) & 0xFF
        if place != 0xA and m.call(m.main + 0x173CF60, m.u64(o + 0x38), user, mv) & 1:
            pos = m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), m.u32(r + 0x14)) & M32
        m.call_void(m.main + 0x173C128, o, a1, m.u64(o + 0x10), m.u64(r), pos, m.u64(r + 8), keep,
                    m.u64(r + 0x18), flag)
        f = m.call(m.main + 0x173C518, m.u64(o + 0x38), m.u64(r), m.u8(flag)) & 1
        m.put(flag, 1, f)
        m.put(redirected, 1, 0)
        lst = m.u64(r + 0x18)
        if m.u8(lst + 0xA6) == 1 and f:
            t = m.call(m.main + 0x173C16C, o, m.u64(lst), m.u64(r), m.u64(r + 8), redirected)
            _clear_members(m, m.u64(r + 0x18))
            if t:
                add_member(m, m.u64(r + 0x18), t)
            if not m.u8(redirected):
                m.call_void(m.main + 0x173C7FC, o, m.u64(r), m.u64(r + 0x18))
        else:
            m.call_void(m.main + 0x173C7FC, o, m.u64(r), lst)
        m.call_void(m.main + 0x173C268, o, 0, m.u64(r), m.u64(r + 8), 0, m.u64(r + 0x18))
        lst = m.u64(r + 0x18)
        m.write(copy, m.read(lst, 0xA8))
        high = m.u8(lst + 0xA7)
        m.put(copy + 0xA9, 1, m.u8(lst + 0xA9))
        places = m.u64(m.u64(o + 0x10) + 0xF0)
        m.put(copy + 0xA8, 1, 0)
        n = m.u8(copy + 0xA6)
        if n:
            m.put(copy + 0xA8, 1, 1)
            t = m.u64(copy)
            while t:
                if m.vcall(t, 0x200) & 1 or \
                        m.call(m.main + 0x1381420, places, m.vcall(t, 0x98) & M32) & 0xFF == 0xA:
                    m.call_void(m.main + 0x157BF08, copy, t)
                i = m.u8(copy + 0xA8)
                n = m.u8(copy + 0xA6)
                if i >= n:
                    break
                m.put(copy + 0xA8, 1, i + 1)
                t = m.u64(copy + 8 * i)
            _clear_members(m, lst)
            for i in range(n):
                t = m.u64(copy + 8 * i)
                out = m.vcall(t, 0x200) & 1
                if t and not out:
                    add_member(m, lst, t)
        else:
            _clear_members(m, lst)
        m.put(lst + 0xA9, 1, high)


@lifted(0x1832FA4)
def report_b3(m, o, a, b, *_):
    """Queue command 0xb3 (a, b) on [o+0x18]."""
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xB3, a & M32, b & M32)


_FORM_TEXT = {1: 0x2D3, 2: 0x2D0, 3: 0x2D4, 4: 0x2D2, 5: 0x2D1}   # jump table 0x3c6a62e


@lifted(0x1143AF4)
def status_requests(m, o, *_):
    """For each member 0x1143db8 lists, outside rule bit 2 with fewer than two of [[o+8]+0x38]+0x30: one
    with no slot level 1..4, vf 0x460 >= 220, a status (vf 0x230) and 0x114d360(0x14) nonzero applies the
    request {id, status, id, text by status} through 0x17cdf14, then command 0xb3 (id, 0)."""
    with m.frame(0x190) as sp:
        lst = sp + 8
        m.call_void(m.main + 0x1143D84, lst)
        m.call_void(m.main + 0x1143DB8, o, lst)
        m.call_void(m.main + 0x1143D7C, lst)
        for t in _walk_pre_resume(m, lst):
            rules = m.u64(m.u64(o + 8) + 0x38)
            if m.u8(rules + 0x499) >> 2 & 1 or m.u32(rules + 0x30) > 1:
                continue
            slots = m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50)
            p = m.call(m.main + 0x10E2DD4, slots, m.vcall(t, 0x98) & M32)
            if p and 0 < m.s(p, 4) <= 4:
                continue
            if m.vcall(t, 0x460) & 0xFF < 0xDC:
                continue
            status = m.vcall(t, 0x230) & 0xFFFF
            if not status or not m.call(m.main + 0x114D360, o, 0x14) & M32:
                continue
            ident = m.vcall(t, 0x98) & M32
            slots = m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50)
            p = m.call(m.main + 0x10E2DD4, slots, ident)
            level = 0
            if p:
                v = m.s(p, 4)
                level = v & 0xFF if v < 5 else 0
            req = sp + 0xC8
            m.write(req, bytes(0x60))
            m.put(req, 4, ident); m.put(req + 4, 4, status); m.put(req + 8, 4, ident)
            m.put(req + 0x30, 1, 1); m.put(req + 0x35, 1, 1)
            if status in _FORM_TEXT:
                m.put(req + 0x38, 2, _FORM_TEXT[status]); m.put(req + 0x3A, 2, 0x101)
                m.put(req + 0x3C, 4, ident); m.put(req + 0x40, 4, level)
            m.call_void(m.main + 0x17CDF14, m.u64(m.u64(o + 0x78) + 0xAE0), sp + 0xB8, req)
            q = m.call(m.main + 0x1143584, o)
            m.call_void(m.main + 0x1832FA4, q, m.vcall(t, 0x98) & M32, 0)


def _walk_pre_resume(m, lst):
    """The member list walk advancing the cursor (+0xa8) before each read, from where it stands."""
    while True:
        i = m.u8(lst + 0xA8)
        if i >= m.u8(lst + 0xA6):
            return
        m.put(lst + 0xA8, 1, i + 1)
        t = m.u64(lst + 8 * i)
        if not t:
            return
        yield t


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


def _move_field_5(m, move):
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    return fb.u8(m, m.call(m.main + 0xBF60CC, table, move & 0xFFFF), 5)


@lifted(0x2D34760)
def move_refusal(m, o, b, mv, lst, *_):
    """0x14826c0 (kind 0x21) first; then, unless the move has field 5: in a raid (rule bit 2) 0x24 when the
    attacker is not the raid battler, 0x1150ed0 holds and a target is; with rule 0x49c bit 1, 0x24 when
    the attacker is not at slot level 1 and a target at level 1 answers vf 0x4d0(0x1e)."""
    from pokeldn.sv.battle.engine.lift1 import _raid_id
    r = m.call(m.main + 0x14826C0, m.u64(o + 0x38), b, m.u16(mv), 0x21, mv, lst) & M32
    if r & 0xFF:
        return r
    rules = lambda: m.u64(m.u64(o + 8) + 0x38)
    if m.u8(rules() + 0x499) >> 2 & 1 and not _move_field_5(m, m.u16(mv)):
        ident = m.vcall(b, 0x98) & M32
        rec = m.u64(m.u64(o + 0x10) + 0x310)
        if _raid_id(m, rec) != ident and m.call(m.main + 0x1150ED0, m.u64(m.u64(o + 0x10) + 0x310)) & 1 \
                and lst and m.u8(lst + 0xA6):
            res = 0
            for i in range(m.u8(lst + 0xA6)):
                tid = m.vcall(m.u64(lst + 8 * i), 0x98) & M32
                if _raid_id(m, m.u64(m.u64(o + 0x10) + 0x310)) == tid:
                    res = 0x24
            if res:
                return res
    if not m.u8(rules() + 0x49C) >> 1 & 1 or _move_field_5(m, m.u16(mv)):
        return 0

    def level_1(x):
        slots = m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50)
        p = m.call(m.main + 0x10E2DD4, slots, m.vcall(x, 0x98) & M32)
        return p and m.s(p, 4) == 1

    if not lst or level_1(b):
        return 0
    res = 0
    for i in range(m.u8(lst + 0xA6)):
        t = m.u64(lst + 8 * i)
        if level_1(t) and m.vcall(t, 0x4D0, 0x1E) & 1:
            res = 0x24
    return res


def _move_flag_of_key(field):
    def fn(m, key, *_):
        return int(_move_field(m, m.u16(key + 8), field) != 0)
    return fn


def _move_flag_of_id(predicate):
    def fn(m, ident, *_):
        with m.frame(0x10) as k:
            m.put(k, 8, m.u64(m.main + 0x46DDAD8) + 0x10); m.put(k + 8, 2, ident & 0xFFFF)
            return m.call(m.main + predicate, k) & 1
    return fn


def _move_field(m, ident, field):
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    return fb.u8(m, m.call(m.main + 0xBF60CC, table, ident & 0xFFFF), field)


# Move-record flags: predicate on the id wrapper (vtable [0x46ddad8]+0x10, u16 id at +8) -> field, and the
# wrapper builders that call them.
for _addr, _field in {0x20FBCD0: 30, 0x20FC058: 33, 0x20FC21C: 35, 0x20FBE94: 31, 0x15B1DB4: 28}.items():
    lifted(_addr)(_move_flag_of_key(_field))
for _addr, _pred in {0x151BD40: 0x20FBCD0, 0x151BD78: 0x20FC058, 0x15B1D7C: 0x15B1DB4, 0x17A0DEC: 0x20FC21C,
                     0x1482D70: 0x20FBE94}.items():
    lifted(_addr)(_move_flag_of_id(_pred))


def _code_request(m, b, code, queue, extra=None):
    """Apply the one-battler request {b's id, code, b's id, +0x30 = 1} through 0x17cdf14 on `queue`;
    `extra(aux)` fills the aux record at +0x38 and the request takes +0x35 = 1."""
    with m.frame(0x70) as sp:
        m.write(sp, bytes(0x70))
        r = sp + 0x10
        m.put(r + 4, 4, 0x31)
        m.call_void(m.main + 0x1146154, r + 0x38)
        m.put(r, 4, m.vcall(b, 0x98) & M32); m.put(r + 4, 4, code)
        m.put(r + 8, 4, m.vcall(b, 0x98) & M32)
        m.put(r + 0x30, 1, 1); m.put(r + 0x35, 1, 1 if extra else 0)
        if extra:
            extra(r + 0x38)
        m.call_void(m.main + 0x17CDF14, queue, sp, r)


@lifted(0x288B840)
def request_code_2(m, o, b, *_):
    _code_request(m, b, 2, m.call(m.main + 0x17CDF0C, m.call(m.main + 0x1361214, o)))


@lifted(0x1482DE4)
def request_code_3_of(m, o, b, *_):
    _code_request(m, b, 3, m.call(m.main + 0x17CDF0C, m.call(m.main + 0x1361214, o)))


@lifted(0x288B8DC)
def request_code_6(m, o, b, *_):
    def extra(aux):
        m.call_void(m.main + 0x2843244, aux, 2, 0x76)
        m.call_void(m.main + 0x284325C, aux, m.vcall(b, 0x98) & M32)
    _code_request(m, b, 6, m.call(m.main + 0x17CDF0C, m.call(m.main + 0x1361214, o)), extra)


@lifted(0x2882914)
def report_ca(m, o, a, text, b, *_):
    """Queue command 0xca (a, text, b) on [o+0x18]."""
    return _tail(m, m.main + 0x157EBC0, m.u64(o + 0x18), 0xCA, a & M32, text & 0xFFFF, b & M32, 0xFFFF0000)


@lifted(0x288B9B0)
def report_cb_75(m, o, b, *_):
    """0x114ade8(b, 0x2f), then command 0xcb (b, 0x75, b)."""
    m.call_void(m.main + 0x114ADE8, o, b, 0x2F)
    q = m.u64(o + 0x18)
    a = m.vcall(b, 0x98) & M32
    return _tail(m, m.main + 0x157EBC0, q, 0xCB, a, 0x75, m.vcall(b, 0x98) & M32, 0xFFFF0000)


@lifted(0x288BA20)
def report_cb_70(m, o, b, *_):
    """0x114ade8(b, 0x30), then command 0xcb (b, 0x70, b, vf 0x238(7))."""
    v = m.vcall(b, 0x238, 7) & 0xFFFF
    m.call_void(m.main + 0x114ADE8, o, b, 0x30)
    q = m.u64(o + 0x18)
    a = m.vcall(b, 0x98) & M32
    return _tail(m, m.main + 0x157EBC0, q, 0xCB, a, 0x70, m.vcall(b, 0x98) & M32, v, 0xFFFF0000)


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


@lifted(0x148268C)
def level_limit(m, rules_owner, level, *_):
    """Byte +0xbb of the level-`level` entry (0xc0 bytes from [x+0x38]+0xc8), 100 past level 4."""
    level &= 0xFF
    if level > 4:
        return 0x64
    return m.u8(m.u64(rules_owner + 0x38) + level * 0xC0 + 0xC8 + 0xBB)


def _slot_level(m, o, b):
    slots = m.u64(m.u64(m.u64(m.call(m.main + 0x1482534, o) + 0x290) + 8) + 0x50)
    p = m.call(m.main + 0x10E2DD4, slots, m.vcall(b, 0x98) & M32)
    v = m.s(p, 4) if p else 0
    return v if v < 5 else 0


@lifted(0x1482568)
def obey_check(m, o, b, *_):
    """0 when vf 0x7c8 does not exceed the level limit; else rolls through 0x11421f0: 0 when the first
    roll passes, 4 with vf 0x228(0), else 3 or 4 by a second roll, 2 when 0x2830050 refuses."""
    w21 = m.vcall(b, 0x7C8) & 0xFF
    lim = m.call(m.main + 0x148268C, m.u64(o + 8), _slot_level(m, o, b)) & 0xFF
    if w21 <= lim:
        return 0
    if lim > m.call(m.main + 0x11421F0, o, w21 + lim + 1) & 0xFFFF:
        return 0
    if m.vcall(b, 0x228, 0) & 1:
        return 4
    roll = m.call(m.main + 0x11421F0, o, 0x100) & M32
    d = w21 - lim
    if d > roll & 0xFFFF and not m.call(m.main + 0x2830050, m.u64(o + 0x38), b) & 1:
        return 2
    return 4 if d <= (roll - d) & 0xFFFF else 3


def _sub_flag(m, o, k):
    return m.call(m.main + 0x1482544, m.call(m.main + 0x148253C, m.call(m.main + 0x1482534, o)), k) & 1


def _named_chance(m, o, name):
    q = m.call(m.main + 0x114ACBC, o)
    return m.call(m.main + 0x114D360, o, m.vcall(q, 0x68, m.main + name) & M32) & M32


def _cond_value(m, b, cond):
    with m.frame(0x10) as pair:
        r = m.vcall(b, 0x240, cond)
        m.put(pair, 8, r[0]); m.put(pair + 8, 8, r[1])
        return m.call(m.main + 0xF7FFE0, pair) & 0xFFFF


@lifted(0x1481D90)
def move_check(m, o, b, mv, ignore, choice, *_):
    """Whether b can use the move at mv (u16 id, u16 slot): 0 when it can, else the refusal code (1 for a
    slot vf 0x690 reads as 0, 2 and 4 by status 2 and 3, the rest by condition and rule)."""
    if m.vcall(b, 0x230) & 0xFFFF == 2 and m.vcall(b, 0x3C0) & 1:
        m.call_void(m.main + 0x288B840, o, b)
    if m.vcall(b, 0x230) & 0xFFFF == 2 and not m.call(m.main + 0x14834BC, m.u64(o + 0x38), b, m.u16(mv), 2) & 1:
        return 2
    key = m.u16(mv)
    thawed = False
    if m.vcall(b, 0x230) & 0xFFFF == 3:
        if not m.call(m.main + 0x1483140, m.u64(o + 0x38), b, key) & 1 and m.call(m.main + 0x1482D70, key) & 1:
            thawed = True
        elif _named_chance(m, o, 0x3C6A688):
            m.call_void(m.main + 0x1482DE4, o, b)
    if m.vcall(b, 0x230) & 0xFFFF == 3 and not thawed:
        return 4
    obey = 0
    rules = m.u64(m.u64(o + 8) + 0x38)
    if not m.u8(rules + 0x499) >> 2 & 1 and m.u32(rules + 0x30) <= 1:
        slots = m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50)
        p = m.call(m.main + 0x10E2DD4, slots, m.vcall(b, 0x98) & M32)
        lvl = (m.s(p, 4) if m.s(p, 4) < 5 else 0) if p else 0
        if lvl == m.u8(m.u64(o + 8) + 0x95):
            obey = m.call(m.main + 0x1482568, o, b) & 0xFF
            if obey == 4:
                return 0x16
            if obey == 2:
                return 0x17
    if not ignore & 1 and not m.u8(choice + 4) >> 3 & 1:
        slot = m.vcall(b, 0x700, m.u16(mv + 2))
        if slot & 0xFF != 4 and not m.vcall(b, 0x690, slot) & 0xFFFF:
            return 1
    key = m.u16(mv)
    if key == 0 or not _move_field(m, key, 1):
        return 0x24
    if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x704) and m.call(m.main + 0x17A0DEC, m.u16(mv)) & 1:
        return 0x1A
    r = m.call(m.main + 0x14826C0, m.u64(o + 0x38), b, m.u16(mv), 0x20, mv, 0) & M32
    if r & 0xFF:
        return r
    if m.vcall(b, 0x510, 6) & 1 and m.u16(mv) == 0x108:
        return 7
    if m.vcall(b, 0x510, 4) & 1:
        return 6
    if m.vcall(b, 0x220, 0xD) & 1 and m.u16(mv) != 0xA5 and m.u16(mv) == _cond_value(m, b, 0xD):
        return 9
    if m.vcall(b, 0x220, 0xF) & 1 and m.call(m.main + 0x151BD78, m.u16(mv)) & 1:
        return 0xD
    if m.vcall(b, 0x220, 0x18) & 1 and m.call(m.main + 0x15B1D7C, m.u16(mv)) & 1:
        return 0x21
    if _sub_flag(m, o, 2) and m.call(m.main + 0x151BD40, m.u16(mv)) & 1:
        return 0x14
    if m.u16(mv) != 0xA5:
        if m.vcall(b, 0x220, 0x17) & 1:
            v = _cond_value(m, b, 0x17)
            if v != 0xA5 and m.u16(mv) != v:
                return 0x11
        cur = m.u16(mv)
        if m.vcall(b, 0x220, 0x1A) & 1:
            cur = m.vcall(b, 0x3E8) & 0xFFFF
            if m.u16(mv) != cur:
                return 0x11
        if cur != 0xA5 and not _sub_flag(m, o, 5) and not m.vcall(b, 0x220, 0x13) & 1 \
                and m.vcall(b, 0x220, 0x1C) & 1 and m.vcall(b, 0x430) & 0xFFFF != cur:
            return 0x11
        if m.vcall(b, 0x220, 0xB) & 1 and not m.call(m.main + 0x14D973C, m.u16(mv)) & 1:
            return 0xA
        if _sub_flag(m, o, 3):
            x = m.call(m.main + 0x148253C, m.call(m.main + 0x1482534, o))
            if m.call(m.main + 0x151BDB0, x, m.call(m.main + 0x1482534, o), b, m.u16(mv)) & 1:
                return 0xC
    if obey == 3:
        q = m.call(m.main + 0x1143584, o)
        a = m.vcall(b, 0x98) & M32
        m.call_void(m.main + 0x2882914, q, a, 0x2B5, m.vcall(b, 0x98) & M32)
        return 5
    if m.vcall(b, 0x220, 6) & 1:
        if m.vcall(b, 0x3C8) & 1:
            m.call_void(m.main + 0x288B8DC, o, b)
        else:
            m.call_void(m.main + 0x288B9B0, m.call(m.main + 0x1143584, o), b)
            if _named_chance(m, o, 0x3C6A690):
                return 5
    if m.vcall(b, 0x230) & 0xFFFF == 1 and _named_chance(m, o, 0x3C6A680):
        return 3
    if m.vcall(b, 0x220, 7) & 1:
        m.call_void(m.main + 0x288BA20, m.call(m.main + 0x1143584, o), b)
        return 8 if _named_chance(m, o, 0x3C6A698) else 0
    return 0
