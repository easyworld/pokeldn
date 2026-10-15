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
            node = m.vcall(b + 0x28, 0)
            static = m.call(m.main + 0x2D1FD38)
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
    node = m.vcall(b + 0x28, 0)
    static = m.call(m.main + 0x2D1FD38)
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
    static = m.call(m.main + 0x2D1FD38)
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
            m.call(m.main + 0x2D1FD38)
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


@lifted(0x157BA2C)
def drop_immune_targets(m, o, _x, r, *_):
    """r = (user, move, lst, end, byte): drop each target that neither 0x157d2e4 nor 0x157ef78 keeps
    (0x157bf08, 0x157eeb8 unless the move hits several of them, 0x158097c); a list left empty ends the
    move through 0x157bf90 (1) when end is set."""
    lst = m.u64(r + 0x10)
    if not m.u8(lst + 0xA6) or (m.u8(lst + 0xA7) == 1 and m.u64(lst) == m.u64(r)):
        return
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


@lifted(0x176A354)
@lifted(0x171987C)
def free_buckets(m, pair, ptr, *_):
    """Free a bucket array of [pair] entries through the allocator [pair+8] (vf 0x18, or 0xb48fe8 when
    frees are deferred). 0x176a354 is the same code."""
    size, alloc = m.u64(pair) * 8, m.u64(pair + 8)
    if _frees_deferred(m, alloc):
        return _tail(m, m.main + 0xB48FE8, alloc, ptr, size, 4)
    return _tail(m, m.u64(m.u64(alloc) + 0x18), alloc, ptr, size, 4)


@lifted(0xF8001C)
def do_rehash(m, table, n, *_):
    """libc++ __do_rehash of a u32-keyed map (buckets +0, count +8, bucket allocator +0x10, first node
    +0x30): a fresh zeroed array of n buckets, the old one freed, the node chain regrouped by bucket."""
    return _do_rehash(m, table, n, 0x171987C)


@lifted(0x1589FF0)
def do_rehash_u8(m, table, n, *_):
    """0xf8001c's code for the u32 -> u8 map of 0x1589bc0, freeing through 0x176a354."""
    return _do_rehash(m, table, n, 0x176A354)


def _free_bucket_array(m, table, old, free, align):
    if free is not None:
        return m.call_void(m.main + free, table + 8, old)
    size, alloc = m.u64(table + 8) * 8, m.u64(table + 0x10)
    if _frees_deferred(m, alloc):
        return m.call_void(m.main + 0xB48FE8, alloc, old, size, align)
    m.vcall_void(alloc, 0x18, old, size, align)


def _do_rehash(m, table, n, free, align=4, key=4):
    """`free` is the bucket free's address, or None for the free inlined with `align`; `key` is the
    key's width at node +0x10."""
    old = m.u64(table)
    if old and _frees_deferred(m, m.u64(table + 0x10)) and 0xB48FE8 not in FUNCTIONS:
        raise UnliftedCall("main+0xb48fe8")
    if n == 0:
        m.put(table, 8, 0)
        if old:
            _free_bucket_array(m, table, old, free, align)
        m.put(table + 8, 8, 0)
        return
    arr = m.vcall(m.u64(table + 0x10), 0x10, n * 8, align)
    if not arr:
        raise UnliftedCall("allocator out of memory")
    m.put(table, 8, arr)
    if old:
        _free_bucket_array(m, table, old, free, align)
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
            while m.u64(np) and m.read(cp + 0x10, key) == m.read(m.u64(np) + 0x10, key):
                np = m.u64(np)
            m.put(pp, 8, m.u64(np))
            head = m.u64(arr + 8 * chash)
            m.put(np, 8, m.u64(head))
            m.put(head, 8, cp)
        cp = m.u64(pp)


@lifted(0xFAF460)
def do_rehash_u16(m, table, n, *_):
    """__do_rehash of the u16-keyed command-format map: 0xf8001c's shape with the bucket free inlined
    and alignment 2."""
    return _do_rehash(m, table, n, None, align=2, key=2)


@lifted(0xFAF09C)
def format_slot(m, table, key_ptr, *_):
    """operator[] of the queue's command-format map (u16 key at node +0x10, u8 value at +0x12): the
    value of the key's node, inserting a zero one (0x18-byte node from [table+0x38], align 2, pushed on
    the thread's object stack while built) and growing through 0xfaf460 when the load allows."""
    import math
    import struct
    from pokeldn.sv.battle.engine.containers import find_u16, _bucket
    from pokeldn.sv.battle.engine.lift0 import _tls_stack
    key = m.u16(key_ptr)
    node = find_u16(m, table, key)
    if node:
        return node + 0x12
    n = m.u64(table + 8)
    node = m.vcall(m.u64(table + 0x38), 0x10, 0x18, 2)
    if not node:
        raise UnliftedCall("allocator out of memory")
    alloc = m.u64(table + 0x38)
    t = _tls_stack(m)
    if t:
        depth = m.u64(t + 0x80)
        if depth >= 0x10:
            raise UnliftedCall("abort: object stack full")
        m.put(t + 8 * depth, 8, alloc)
        m.put(t + 0x80, 8, depth + 1)
    m.put(node + 0x10, 2, m.u16(key_ptr)); m.put(node + 0x12, 1, 0)
    if t:
        m.put(t + 0x80, 8, m.u64(t + 0x80) - 1)
    m.put(node, 8, 0); m.put(node + 8, 8, key)
    size1 = _f32(float(m.u64(table + 0x58) + 1))
    load = struct.unpack("<f", m.read(table + 0x60, 4))[0]
    if n == 0 or _f32(load * _f32(float(n))) < size1:
        grow = (n << 1) | int(n < 3 or not _pow2(n))
        need = math.ceil(_f32(size1 / load))
        _rehash(m, table, max(grow, need), 0xFAF460)
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
    return node + 0x12


@lifted(0xF7C240)
def rehash(m, table, want, *_):
    """libc++ rehash(want) of a u32-keyed map: grow to want (rounded to a prime unless a power of two);
    shrink only down to what the size and max load (+0x60) allow."""
    return _rehash(m, table, want, 0xF8001C)


@lifted(0x1589EEC)
def rehash_u8(m, table, want, *_):
    """0xf7c240's code, tail-calling 0x1589ff0."""
    return _rehash(m, table, want, 0x1589FF0)


def _rehash(m, table, want, do):
    import math
    import struct
    if want == 1:
        want = 2
    elif want & (want - 1):
        want = m.call(m.main + 0x343D400, want)
    n = m.u64(table + 8)
    if want > n:
        return _tail(m, m.main + do, table, want)
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
        return _tail(m, m.main + do, table, new)


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


@lifted(0x114C614)
def list_member(m, lst, i, *_):
    """Member i of a battler list (count at +0x30), 0 past the end."""
    i &= 0xFF
    return m.u64(lst + 8 * i) if m.u8(lst + 0x30) > i else 0


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


@lifted(0x1142484)
def battler_vf_4e0(m, o, ident, v, *_):
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), ident)
    return _tail(m, m.u64(m.u64(b) + 0x4E0), b, v)


@lifted(0x1140198)
def apply_and_queue_1f(m, o, b, v, *_):
    """0x1142484([o+0x20], id, v), then command 0x1f (id, v)."""
    m.call_void(m.main + 0x1142484, m.u64(o + 0x20), m.vcall(b, 0x98) & M32, v & M32)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x1F, m.vcall(b, 0x98) & M32, v & M32)


@lifted(0x2831C94)
def event_f1(m, o, b, mv, flag, p, *_):
    """Event 0xf1 with b's id (2), the move (0x12), its type byte (0x16), flag (0x59) and bit 3 of
    [p+4] (0x71): whether 0x73 stays set."""
    return int(_event(m, o, 0xF1, ((2, _id(m, b), 4, 0x18), (0x12, lambda: m.u16(mv), 4, 0x98),
                                   (0x16, lambda: m.u8(mv + 8), 4, 0xB8), (0x59, flag & 1, 4, 0x2D0),
                                   (0x71, lambda: m.u32(p + 4) >> 3 & 1, 4, 0x390), (0x73, 1, 1, 0x3A0)),
                      0x3A0) != 0)


@lifted(0x1581098)
def drain_4e8(m, o, b, *_):
    """Apply b's vf 0x4e8 values through 0x1140198 until it answers 0x20."""
    while True:
        w = m.vcall(b, 0x4E8)
        if w & M32 == 0x20:
            return w
        m.call_void(m.main + 0x1140198, m.call(m.main + 0x1143584, o), b, w & M32)


@lifted(0x1580E50)
def request_1b(m, o, b, *_):
    """With b's condition 0x1b: a request {id, 0x1b, id, +0x30 = 1, +0x35 = 1} through 0x17cdf14, then vf
    0x508(0xb)."""
    r = m.vcall(b, 0x220, 0x1B)
    if not r & 1:
        return r
    with m.frame(0x70) as sp:
        m.write(sp, bytes(0x70))
        q = sp + 0x10
        m.put(q + 4, 4, 0x31)
        m.call_void(m.main + 0x1146154, q + 0x38)
        m.put(q, 4, m.vcall(b, 0x98) & M32); m.put(q + 4, 4, 0x1B)
        m.put(q + 8, 4, m.vcall(b, 0x98) & M32)
        m.put(q + 0x30, 1, 1); m.put(q + 0x35, 1, 1)
        m.call_void(m.main + 0x17CDF14, m.call(m.main + 0x17CDF0C, m.call(m.main + 0x1361214, o)), sp, q)
    return m.vcall(b, 0x508, 0xB)


@lifted(0x1580E18)
def get_1860(m, o, *_): return m.u64(o + 0x1860)


@lifted(0x1580E20)
def request_1b_then_drain(m, o, _out, pb, *_):
    m.call_void(m.main + 0x1580E50, o, m.u64(pb))
    return _tail(m, m.main + 0x1581098, o, m.u64(pb))


@lifted(0x288A9C8)
def run_1580e20(m, o, b, *_):
    with m.frame(0x10) as f:
        m.put(f + 8, 8, b)
        x = m.call(m.main + 0x1580E18, m.call(m.main + 0x1361214, o, b), b)
        return _tail(m, m.main + 0x1580E20, x, f, f + 8)


@lifted(0x288A9F8)
def run_1360318_of(m, o, b, *_):
    """0x1360318 on 0x1360310's object with a stack record (b at +8, u16 0x101 at +0x10)."""
    with m.frame(0x20) as f:
        m.put(f + 0x10, 8, b); m.put(f + 0x18, 2, 0x101)
        x = m.call(m.main + 0x1360310, m.call(m.main + 0x1361214, o, b), b)
        return _tail(m, m.main + 0x1360318, x, f + 8, f + 0x10)


@lifted(0x2D326E0)
def move_use_record(m, o, _x1, r, *_):
    """Bookkeeping after a move is chosen (r: +0 flags, +8 battler, +0x10 move {u16 id, u8 type at +8},
    +0x18..+0x1c flags, +0x1e u16 slot move, +0x20 target byte): vf 0x3f8 and command 0x1d when the use
    counts, else the status check; command 0x86 for a typed move outside raids; event 0xf1; command 0x5b
    for both moves."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    from pokeldn.sv.battle.engine.lift1 import _raid_id
    b = lambda: m.u64(r + 8)
    rules = lambda: m.u64(m.u64(o + 8) + 0x38)
    if not m.u8(r + 0x19):
        q = m.u64(o + 0x20)
        m.call_void(m.main + 0x157BF90, q, m.vcall(b(), 0x98) & M32, 0)
    m.vcall_void(b(), 0x508, 3)
    take = False
    if m.u8(rules() + 0x499) >> 2 & 1:
        ident = m.vcall(b(), 0x98) & M32
        if _raid_id(m, m.u64(m.u64(o + 0x10) + 0x310)) == ident:
            if m.u8(r + 0x19) or not m.vcall(b(), 0x220, 0x1A) & 1:
                take = True
            else:
                v = m.vcall(b(), 0x3E8)
                take = m.u16(m.u64(r + 0x10)) == v & 0xFFFF
    if m.u8(rules() + 0x49C) >> 1 & 1:
        ident = m.vcall(b(), 0x98) & M32
        p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50), ident)
        take = bool(p and m.u32(p) == 1) or take
    if not take and m.u8(r + 0x18):
        take = True
    if not take and m.u8(r + 0x1A):
        take = m.u16(m.u64(r + 0x10)) == m.vcall(b(), 0x260) & 0xFFFF
    if not take and m.u8(r + 0x1C) == 2:
        take = m.u16(m.u64(r + 0x10)) == m.vcall(b(), 0x268) & 0xFFFF
    if not take:
        take = m.u16(m.u64(r + 0x10)) == 0xA5
    if take:
        c = m.u64(o + 0x20)
        ident = m.vcall(b(), 0x98) & M32
        mv = m.u64(r + 0x10)
        f19, slot, tgt = m.u8(r + 0x19), m.u16(r + 0x1E), m.u8(r + 0x20)
        key, kind = m.u16(mv), m.u8(mv + 8)
        x = m.call(m.main + 0xF21C94, m.u64(m.u64(m.u64(c + 0x20) + 0x10) + 0x30), ident)
        m.vcall_void(x, 0x3F8, tgt, kind, int(f19 != 0), key, slot)
        m.call_void(m.main + 0x119AFF0, m.u64(c + 0x18), 0x1D, ident, tgt, kind, f19, 0, key, slot)
    elif m.vcall(b(), 0x540, 3) & 0xFF and not m.u8(m.u64(r) + 4) >> 3 & 1:
        m.call_void(m.main + 0x1143A30, m.u64(o + 0x20), m.u64(r + 8), 3, 0)
    if not m.u8(rules() + 0x499) >> 2 & 1 and m.u8(r + 0x19):
        key = m.u16(m.u64(r + 0x10))
        if key != 0xA5:
            table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
            rec = m.call(m.main + 0xBF60CC, table, key)
            if fb.u8(m, rec, 4) and (m.u8(r + 0x1C) | 4) == 4:
                mv = m.u64(r + 0x10)
                kind = m.u8(mv + 8)
                if kind == 0x12:
                    kind = m.call(m.main + 0x2D2219C, m.u64(r + 8), 0x12, m.u16(mv)) & M32
                c = m.u64(o + 0x20)
                ident = m.vcall(b(), 0x98) & M32
                m.call_void(m.main + 0x2D35A50, m.u64(c + 0x20), ident, kind)
                m.call_void(m.main + 0x119AFF0, m.u64(c + 0x18), 0x86, ident, kind)
    if m.u8(r + 0x1B) and m.vcall(b(), 0x4E8) & M32 != 0x20:
        m.call_void(m.main + 0x288A9C8, o, m.u64(r + 8))
    if m.vcall(b(), 0x510, 0xB) & 1:
        c = m.u64(o + 0x20)
        m.call_void(m.main + 0x119AFF0, m.u64(c + 0x18), 0x8C, m.vcall(b(), 0x98) & M32, 0)
        m.call_void(m.main + 0x288A9F8, o, m.u64(r + 8))
    mv, head, bb, f19 = m.u64(r + 0x10), m.u64(r), m.u64(r + 8), m.u8(r + 0x19)
    m.call_void(m.main + 0x2831890, m.u64(o + 0x38), bb, m.u16(mv), f19, head)
    if m.vcall(bb, 0x4D0, 0x14) & 1 and m.u8(mv + 8) == 0xC \
            and m.call(m.main + 0x2831C94, m.u64(o + 0x38), bb, mv, int(f19 != 0), head) & 1:
        m.call_void(m.main + 0x1140198, m.u64(o + 0x20), bb, 0x14)
    for which in (0, 1):
        c = m.u64(o + 0x20)
        ident = m.vcall(b(), 0x98) & M32
        d = m.u64(c + 0x20)
        key = m.u16(r + 0x1E) if which == 0 else m.u16(m.u64(r + 0x10))
        x = m.call(m.main + 0xF21C94, m.u64(m.u64(d + 0x10) + 0x30), ident)
        m.call_void(m.main + 0x13DC030, m.u64(d + 0x18), x, key)
        if which == 0:
            m.call_void(m.main + 0x119AFF0, m.u64(c + 0x18), 0x5B, ident, key)
    return _tail(m, m.main + 0x119AFF0, m.u64(c + 0x18), 0x5B, ident, key)


@lifted(0x16EEB20)
def bond_full_command(m, o, b, *_):
    """Command 0xb4 (id, 1, 1, 0x2e8, id, 0) when 0x16eeb98 reads 0xff."""
    r = m.call(m.main + 0x16EEB98, m.u64(o + 8), m.u64(o + 0x10), b)
    if r & 0xFF != 0xFF:
        return r
    ident = m.vcall(b, 0x98) & M32
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xB4, ident, 1, 1, 0x2E8, ident & 0xFFFF, 0)


def _unique_ids(m, n, kinds, lst, pick):
    ids = []
    for i in range(n):
        if not pick(m.u8(kinds + i)):
            continue
        v = m.vcall(m.u64(lst + 8 * i), 0x98) & M32
        if len(ids) <= 9 and v not in ids:
            ids.append(v)
    return ids


def _cb_names(m, q, ident, base, count, ids):
    if not 1 <= count <= 4:
        return
    pad = ids + [0] * (4 - len(ids))
    args = [pad[0]] + [pad[k] if len(ids) > k else pad[0] for k in range(1, count)]
    m.call_void(m.main + 0x157EBC0, q, 0xCB, ident, base + count - 1, *args, 0xFFFF0000)


@lifted(0x28851C8)
def side_texts(m, o, b, n, kinds, lst, listed, *_):
    """Texts for the n battlers at lst by kind byte (>= 8: the other side, < 7: b's side): with `listed`,
    command 0xcb naming up to four distinct ids (texts 2..5 and 6..9), else command 0xca 0x23e / 0x23f;
    0x16eeb20 when one of the other side fails 0x1142e68."""
    c28 = c27 = c26 = 0
    for i in range(n & M32):
        k = m.u8(kinds + i)
        if k >= 8:
            c28 = (c28 + 1) & 0xFF
            r = m.call(m.main + 0x1142E68, m.u64(o + 8), m.u64(o + 0x10), m.u64(lst + 8 * i))
            c27 = (c27 + (~r & 1)) & 0xFF
            k = m.u8(kinds + i)
        if k < 7:
            c26 = (c26 + 1) & 0xFF
    if c27:
        _need(m, m.main + 0x16EEB20)
    ident = m.vcall(b, 0x98) & M32
    q = lambda: m.u64(o + 0x18)
    if not listed & 1:
        if c28:
            m.call_void(m.main + 0x157EBC0, q(), 0xCA, ident, 0x23E, 0xFFFF0000)
            if c27:
                return _tail(m, m.main + 0x16EEB20, o, b)
            return
        if c26:
            return _tail(m, m.main + 0x157EBC0, q(), 0xCA, ident, 0x23F, 0xFFFF0000)
        return
    if c28:
        ids = _unique_ids(m, n & M32, kinds, lst, lambda k: k >= 8)
        _cb_names(m, q(), ident, 2, c28, ids)
        if c27:
            m.call_void(m.main + 0x16EEB20, o, b)
    if c26:
        ids = _unique_ids(m, n & M32, kinds, lst, lambda k: k <= 6)
        _cb_names(m, q(), ident, 6, c26, ids)


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


@lifted(0x2899FD8)
def clamp_stages_of(m, b, *_):
    return _tail(m, m.main + 0x2899FE0, b + 0x414)


# Side-effect end texts by kind (s32 table 0x3c6a8c4); kinds with bit clear in 0x279ff have none.
_SIDE_END_TEXT = (0x271, 0x275, 0x27D, 0x281, 0x285, 0x289, 0x28D, 0x291, 0x295, 0x271, 0x271, 0x29D, 0x2A1,
                  0x2A5, 0x2CB, 0x271, 0x271, 0x279)


@lifted(0x288835C)
def side_end_text(m, o, who, side, kind, *_):
    """Command 0xca (who, text for `kind`, side byte) for the kinds bit-set in 0x279ff."""
    kind &= M32
    if kind > 0x11 or not 0x279FF >> kind & 1:
        return
    return _tail(m, m.main + 0x157EBC0, m.u64(o + 0x18), 0xCA, who & M32, _SIDE_END_TEXT[kind], side & 0xFF,
                 0xFFFF0000)


def _personal_by_species(getter):
    def fn(m, pp, *_):
        """Personal-table value `getter` reads for the Pokemon's species and form; for Arceus (0x1ed) with
        ability 0x79 and Silvally (0x305) with ability 0xe1, the type from the held item instead."""
        acc = lambda: m.u64(pp + 0x70)
        species = m.call(m.main + 0xBF44F4, acc())
        ability = m.call(m.main + 0x103B8A0, acc()) & 0xFFFF
        if species & 0xFFFF == 0x1ED and ability == 0x79:
            return _tail(m, m.main + 0x20F8278, m.call(m.main + 0xD974E0, acc()))
        if species & 0xFFFF == 0x305 and ability == 0xE1:
            return _tail(m, m.main + 0x20F77F4, m.call(m.main + 0xD974E0, acc()))
        form = m.call(m.main + 0xBF41A8, acc())
        with m.frame(0x10) as k:
            m.put(k, 8, m.u64(m.main + 0x46D8EE0) + 0x10); m.put(k + 8, 2, species); m.put(k + 0xA, 2, form)
            return m.call(m.main + getter, k)
    return fn


lifted(0x103B7D0)(_personal_by_species(0x1012D44))
lifted(0x1055170)(_personal_by_species(0x1046124))


@lifted(0x287A9D4)
def pokeparam_1055170(m, o, *_):
    return _tail(m, m.main + 0x1055170, m.u64(o + 0x48))


# Stat getters on the record [pp+0x70] by index 0..5 (jump table 0x3c62c8c).
_STAT_OF = (0xD97F74, 0xD982BC, 0xD98604, 0xD9894C, 0xD98FDC, 0xD98C94)


@lifted(0xD97F14)
def stat_of(m, pp, i, *_):
    i &= 0xFF
    if i > 5:
        return 0
    return _tail(m, m.main + _STAT_OF[i], m.u64(pp + 0x70))


@lifted(0x2D3C7A4)
def set_slot_byte(m, o, i, v, *_):
    """Byte +0x438 of entry i (0x16 bytes, count +0x482) = v, and +0x42e when +0x43a is set."""
    i &= 0xFF
    if m.u8(o + 0x482) <= i:
        return
    e = o + i * 0x16
    m.put(e + 0x438, 1, v)
    if m.u8(e + 0x43A):
        m.put(e + 0x42E, 1, v)


def _request(m, o, ident_of, code):
    """A one-battler request {id, code, id, +0x30 = 1, +0x35 = 1} through 0x17cdf14."""
    with m.frame(0x70) as sp:
        m.write(sp, bytes(0x70))
        q = sp + 0x10
        m.put(q + 4, 4, 0x31)
        m.call_void(m.main + 0x1146154, q + 0x38)
        m.put(q, 4, ident_of() & M32)
        m.put(q + 4, 4, code); m.put(q + 8, 4, ident_of() & M32)
        m.put(q + 0x30, 1, 1); m.put(q + 0x35, 1, 1)
        return _tail(m, m.main + 0x17CDF14, m.call(m.main + 0x17CDF0C, m.call(m.main + 0x1361214, o)), sp, q)


@lifted(0x1150CE8)
def request_code_32(m, o, *_):
    """Request code 0x32 for the battler 0x1142508 names."""
    return _request(m, o, lambda: m.vcall(m.call(m.main + 0x1142508, o), 0x98), 0x32)


@lifted(0x114DBBC)
def clear_when_free(m, o, v, *_):
    """When [x + 0x70] is 0 (x = 0x11409b4(0x1482534(o))): 0x156616c and 0x114dc24 with (1, v), then
    request code 0x32."""
    x = m.call(m.main + 0x11409B4, m.call(m.main + 0x1482534, o))
    r = m.call(m.main + 0x114DC38, x)
    if not r & 1:
        return r
    m.call_void(m.main + 0x156616C, m.call(m.main + 0x1143584, o), 1, v & M32)
    m.call_void(m.main + 0x114DC24, m.call(m.main + 0x1143584, o), 1, v & M32)
    return _tail(m, m.main + 0x1150CE8, o)


@lifted(0x17CE520)
def event_e5(m, o, b, *_):
    """Event 0xe5 with b's id (2): whether a handler cleared 0x73."""
    return int(_event(m, o, 0xE5, ((2, _id(m, b), 4, 0x18), (0x73, 1, 1, 0x3A0)), 0x3A0) == 0)


@lifted(0x287FE9C)
def run_17776d8_7(m, o, b, *_):
    """0x17776d8 with the record {b's id, 7}."""
    with m.frame(0x20) as f:
        r = f + 0x10
        m.put(r, 4, m.vcall(b, 0x98) & M32); m.put(r + 4, 1, 7)
        x = m.call(m.main + 0x17776D0, m.call(m.main + 0x1361214, o))
        m.call_void(m.main + 0x17776D8, x, f + 8, r)


@lifted(0x184A028)
def drop_entries_of(m, o, key, *_):
    """Clear every tagged 16-byte entry (+0x80, +0x90, +0xa0, then 46 from +0xb0) whose 0x184a110 value is
    `key`; clearing +0xa0 also clears +0x110 and byte +0x399."""
    key &= M32
    if not key:
        return
    for off in (0x80, 0x90, 0xA0):
        e = o + off
        if m.u8(e + 8) & 7 and m.call(m.main + 0x184A110, e) & M32 == key:
            m.write(e, bytes(16))
            if off == 0xA0:
                m.put(o + 0x399, 1, 0)
                m.write(o + 0x110, bytes(16))
    for i in range(0, 0x2E0, 0x10):
        e = o + 0xB0 + i
        if m.u8(e + 8) & 7 and m.call(m.main + 0x184A110, e) & M32 == key:
            m.write(e, bytes(16))


@lifted(0x14A0860)
def set_and_queue_09(m, o, ident, v, *_):
    """0x14a08a4([o+0x20], id, v), then command 9 (id, v byte)."""
    m.call_void(m.main + 0x14A08A4, m.u64(o + 0x20), ident, v)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 9, ident & M32, v & 0xFF)


@lifted(0x15803E4)
def run_157fdb0(m, o, b, mv, flags, *_):
    """0x157fdb0 with the record {b's id, u16 [mv], flags at +8}."""
    with m.frame(0x30) as sp:
        m.write(sp, bytes(0x10))
        m.put(sp, 4, m.vcall(b, 0x98) & M32)
        m.put(sp + 8, 8, flags); m.put(sp + 4, 2, m.u16(mv))
        x = m.call(m.main + 0x157FDA8, m.call(m.main + 0x1361214, o))
        m.call_void(m.main + 0x157FDB0, x, sp + 0x28, sp)


# Target kind by the move's field 17 (1..9) when [o+0x36c] is set (jump table 0x3c69d6a): a request
# kind for 0xfe171c, "self" (the user's position) or None (no target, 10).
_TARGET_KIND = {0: 2, 1: 4, 2: 5, 3: 2, 7: "self", 9: 2}


@lifted(0x10E21C0)
def random_target(m, _x0, o, b, move, rng, *_):
    """The position a move of b without a chosen target aims at: by the move's field 17 (Curse 0xae: 7,
    0 for b's vf 0x300(7)); single battles ([o+0x36c] 0) go through 0x173db04, others pick at random
    (0x11440f0 on rng) among 0xfe171c's ids, then 0x1138ce0's positions; 10 for none."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    single = m.u32(o + 0x36C) == 0
    pos = m.call(m.main + 0xFE161C, m.u64(o + 0x290), m.vcall(b, 0x98) & M32) & M32
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    kind = fb.u8(m, m.call(m.main + 0xBF60CC, table, move & M32), 17)
    if move & 0xFFFF == 0xAE:
        kind = 0 if m.vcall(b, 0x300, 7) & 1 else 7
    if single:
        if kind == 0 or (kind <= 9 and 0x238 >> kind & 1):
            return _tail(m, m.main + 0x173DB04, m.u64(o + 0x290), pos, 0)
        return pos if kind <= 9 and 0x82 >> kind & 1 else 0xA
    with m.frame(0x60) as sp:
        req = sp + 0x58
        m.call_void(m.main + 0x10E2464, req)
        how = _TARGET_KIND.get(kind)
        if how is None:
            return 0xA
        if how == "self":
            return pos
        ids = sp + 0x10
        m.call_void(m.main + 0x10E244C, ids, how, pos)
        m.call_void(m.main + 0x10E2474, req, ids)
        mode = m.u32(o + 0x36C)
        w = m.call(m.main + 0x10E2458, m.u64(o + 0x290)) & M32
        n = m.call(m.main + 0xFE171C, req, mode, w, m.u64(o + 0x30), ids) & 0xFF
        if n:
            i = m.call(m.main + 0x11440F0, rng, n) & 0xFF
            return m.call(m.main + 0xFE161C, m.u64(o + 0x290), m.u32(ids + 4 * i)) & M32
        n = m.call(m.main + 0x1138CE0, req, mode, w, sp + 4) & 0xFF
        if not n:
            return 0xA
        i = m.call(m.main + 0x11440F0, rng, n) & 0xFF
        return m.u8(sp + 4 + i)


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


@lifted(0x121C054)
def friendship(m, acc, *_):
    """The current handler's friendship: byte +0x20 of logical block 2 when its +0x1c is set, else byte
    +0x1a of logical block 3 (stand-ins 0x4742330 / 0x4742380 for a record flagged bad)."""
    from pokeldn.sv.battle.engine.pokemon import _target, access
    def read(core):
        c = _target(m, acc, core, 2, 0x4742330)
        if m.u8(c + 0x1C):
            return m.u8(c + 0x20)
        return m.u8(_target(m, acc, core, 3, 0x4742380) + 0x1A)
    return access(m, acc, read)


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


@lifted(0x1143158)
def status_requests_of(m, o, *_):
    with m.frame(0x10) as f:
        return _tail(m, m.main + 0x1143AF4, m.call(m.main + 0x1143184, m.u64(o + 0x78)), f, f + 8)


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


@lifted(0x157FD40)
def run_157fdb0_78(m, o, b, mv, flags, *_):
    """0x157fdb0 on [o+0x78]'s object with the record {b's id, u16 [mv], flags at +8}."""
    with m.frame(0x30) as sp:
        m.write(sp, bytes(0x10))
        m.put(sp, 4, m.vcall(b, 0x98) & M32)
        m.put(sp + 4, 2, m.u16(mv)); m.put(sp + 8, 8, flags)
        x = m.call(m.main + 0x157FDA8, m.u64(o + 0x78))
        return _tail(m, m.main + 0x157FDB0, x, sp + 0x28, sp)


def _run_288aa70(m, o, b, mv, flag, *_):
    """0x288aa70 with the record {b, u16 [mv], flag byte}."""
    with m.frame(0x20) as sp:
        r = sp + 0x10
        m.write(r, bytes(0x10))
        m.put(r, 8, b); m.put(r + 8, 2, m.u16(mv)); m.put(r + 0xA, 1, flag)
        x = m.call(m.main + 0x288AA68, m.call(m.main + 0x1361214, o, b))
        return _tail(m, m.main + 0x288AA70, x, sp + 8, r)


lifted(0x1482DA8)(_run_288aa70)
lifted(0x288BB98)(_run_288aa70)


@lifted(0x288B124)
def apply_to_each_target(m, o, _x1, r, *_):
    """For each target 0x158003c hands out of the list [r+0x10] (reset by 0x1143d7c): event value
    0x283955c(b, t, move), a record from 0x288b67c, and 0x288b6fc; a yes runs 0x157a950."""
    key, b = m.u16(m.u64(r)), m.u64(r + 8)
    m.call_void(m.main + 0x1143D7C, m.u64(r + 0x10))
    with m.frame(0x30) as sp:
        rec = sp + 8
        t = m.call(m.main + 0x158003C, m.u64(r + 0x10))
        while t:
            v = m.call(m.main + 0x283955C, m.call(m.main + 0x1146E90, o), b, t, key) & M32
            m.call_void(m.main + 0x1146154, rec)
            m.call_void(m.main + 0x288B67C, o, rec, b, t, key)
            if m.call(m.main + 0x288B6FC, o, t, v, rec) & 1:
                m.call_void(m.main + 0x157A950, m.call(m.main + 0x139B698, o) + 0x10)
            t = m.call(m.main + 0x158003C, m.u64(r + 0x10))


@lifted(0x2880E44)
def queue_record_8(m, o, *_):
    """0x1154148 on [o+0x78]'s object with a 0x1149604 record: kind 8, byte 0x13616e4([o+8]), pair
    0x113e080(0)."""
    with m.frame(0x70) as sp:
        m.write(sp, bytes(0x50))
        m.call_void(m.main + 0x1149604, sp)
        m.put(sp + 4, 4, 8)
        m.put(sp + 8, 1, m.call(m.main + 0x13616E4, m.u64(o + 8)))
        p = m.call(m.main + 0x113E080, 0)
        m.put(sp + 0x10, 8, p[0]); m.put(sp + 0x18, 8, p[1])
        x = m.call(m.main + 0x113DFC4, m.u64(o + 0x78))
        return _tail(m, m.main + 0x1154148, x, sp + 0x68, sp)


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


@lifted(0x2D02BE8)
def static_476a198(m, *_):
    """The function-local static at main+0x476a198 (guard byte 0x476a1a0), built from 0x28024a0."""
    guard = m.main + 0x476A1A0
    if m.u8(guard) & 1 == 0 and m.call(m.main + 0x343CF10, guard) & M32:
        m.put(m.main + 0x476A198, 8, m.call(m.main + 0x28024A0))
        m.call_void(m.main + 0x343CF20, guard)
    return m.main + 0x476A198


@lifted(0x2D37AA8)
def static_46e2f70(m, *_):
    """The function-local static [0x46e2f70] (guard [0x46e2f68]), built from 0x28024a0."""
    guard = m.u64(m.main + 0x46E2F68)
    if m.u8(guard) & 1 == 0 and m.call(m.main + 0x343CF10, guard) & M32:
        slot = m.u64(m.main + 0x46E2F70)
        m.put(slot, 8, m.call(m.main + 0x28024A0))
        m.call_void(m.main + 0x343CF20, guard)
    return m.u64(m.main + 0x46E2F70)


@lifted(0x1360558)
def is_type_7f(m, o, b, *_):
    """Whether b's vf 0xf8 is 0x7f or event 0xec lists 0x7f among its (count 0x7c) u16 values."""
    if m.vcall(b, 0xF8) & 0xFFFF == 0x7F:
        return 1
    with m.frame(0x10) as f:
        out = f + 0xC
        n = m.call(m.main + 0x114F6FC, m.call(m.main + 0x1146E90, o), m.vcall(b, 0x98) & M32, out) & 0xFF
        for i in range(n):
            if m.u16(out + 2 * i) == 0x7F:
                return 1
    return 0


@lifted(0x13607F0)
def set_and_queue_5d(m, o, ident, *_):
    m.call_void(m.main + 0x1360F0C, m.u64(o + 0x20), ident)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x5D, ident & M32)


@lifted(0x1360604)
def clear_battler_marks(m, o, b, *_):
    """0x13606c4, 0x1360728, 0x136078c and 0x13607f0 on 0x1143584(o) with b's id."""
    for a in (0x13606C4, 0x1360728, 0x136078C):
        q = m.call(m.main + 0x1143584, o)
        m.call_void(m.main + a, q, m.vcall(b, 0x98) & M32)
    q = m.call(m.main + 0x1143584, o)
    return _tail(m, m.main + 0x13607F0, q, m.vcall(b, 0x98) & M32)


@lifted(0x147AC20)
def set_and_queue_29(m, o, ident, *_):
    m.call_void(m.main + 0x147AC54, m.u64(o + 0x20), ident)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x29, ident & M32)


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


@lifted(0x288B1F8)
def move_rule(m, o, _x1, r, *_):
    """By 0x28056f0(move): a nonzero kind goes to 0x288b370, else 0x288b434."""
    k = m.call(m.main + 0x28056F0, m.u16(m.u64(r))) & 0xFF
    if k:
        return _tail(m, m.main + 0x288B370, o, m.u64(r + 8), k)
    return _tail(m, m.main + 0x288B434, o, m.u64(r), m.u64(r + 8))


@lifted(0x1946378)
def queue_text_by_kind(m, o, b, x, kind, flag, *_):
    """0x114ade8([o+0x20], x, text): 0x84 with `flag`; for kind 1 the text event 0xed leaves; else 0x85
    for b, then 0x1832fa4 (b's id, 0)."""
    c = m.u64(o + 0x20)
    if flag & 1:
        return _tail(m, m.main + 0x114ADE8, c, x, 0x84)
    if kind & 0xFF == 1:
        v = m.call(m.main + 0x1946418, m.u64(o + 0x38), b) & M32
        return _tail(m, m.main + 0x114ADE8, m.u64(o + 0x20), x, v)
    ident = m.vcall(b, 0x98) & M32
    m.call_void(m.main + 0x114ADE8, m.u64(o + 0x20), b, 0x85)
    return _tail(m, m.main + 0x1832FA4, m.u64(o + 0x20), ident, 0)


@lifted(0x2885718)
def after_hit_each_target(m, o, _x1, r, *_):
    """r = (user, ?, u32 count, targets, kind bytes, flag byte +0x28): for each target with a kind,
    0x1946378, mark 8 (0x287fe5c) for the target, mark 0x1b for the user unless 0x118ab58 pairs them, and
    0x1148470(user, 0x1a); then 0x2837164 for every target."""
    i = 0
    while i < m.u32(r + 0x10):
        t = lambda: m.u64(m.u64(r + 0x18) + 8 * i)
        k = m.u8(m.u64(r + 0x20) + i)
        if k:
            m.call_void(m.main + 0x1946378, o, m.u64(r), t(), k, m.u8(r + 0x28))
            m.call_void(m.main + 0x287FE5C, o, 8, m.vcall(t(), 0x98) & M32)
            setup = m.u64(m.u64(o + 0x10) + 0x290)
            uid = m.vcall(m.u64(r), 0x98) & M32
            if not m.call(m.main + 0x118AB58, setup, uid, m.vcall(t(), 0x98) & M32) & 1:
                m.call_void(m.main + 0x287FE5C, o, 0x1B, m.vcall(m.u64(r), 0x98) & M32)
            c = m.u64(o + 0x20)
            uid = m.vcall(m.u64(r), 0x98) & M32
            u = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), uid)
            m.call_void(m.main + 0x1148470, c, u, 0x1A)
        m.call_void(m.main + 0x2837164, m.u64(o + 0x38), m.u64(r + 8), m.u64(r), t())
        i += 1


@lifted(0x1532EFC)
def run_if_kind_7(m, o, _x1, r, *_):
    """0x1533ebc(o, [r+0x10], [r+8], [r]) when the move [r+8] has field 3 equal to 7."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    rec = m.call(m.main + 0xBF60CC, table, m.u16(m.u64(r + 8)))
    if fb.u8(m, rec, 3) != 7:
        return
    return _tail(m, m.main + 0x1533EBC, o, m.u64(r + 0x10), m.u64(r + 8), m.u64(r))


def _record_call(getter, fn, out_first):
    def lift(m, o, a, b, c=0, *_):
        """fn on [o+0x78]'s object (getter) with the record {b, a, c} on the stack."""
        with m.frame(0x20) as sp:
            r = sp + 8
            m.put(r, 8, b); m.put(r + 8, 8, a); m.put(r + 0x10, 8, c)
            x = m.call(m.main + getter, m.u64(o + 0x78))
            return _tail(m, m.main + fn, x, sp if out_first else sp + 0x18, r)
    return lift


lifted(0x288ACE0)(_record_call(0x288ADE4, 0x288ADEC, True))
lifted(0x288AD80)(_record_call(0x288B11C, 0x288B124, True))


@lifted(0x288ADB4)
def run_288b1f8(m, o, a, b, *_):
    with m.frame(0x20) as sp:
        r = sp + 0x10
        m.put(r, 8, b); m.put(r + 8, 8, a)
        x = m.call(m.main + 0x288B1F0, m.u64(o + 0x78))
        return _tail(m, m.main + 0x288B1F8, x, sp + 8, r)


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


@lifted(0x287ED8C)
def rule_check_3(m, o, a, b, c, w, *_):
    """0x13808bc on the record {c, a, b, u32 w, 1}."""
    with m.frame(0x30) as sp:
        r = sp + 0x10
        m.put(r, 8, c); m.put(r + 8, 8, a); m.put(r + 0x10, 8, b)
        m.put(r + 0x18, 4, w); m.put(r + 0x1C, 1, 1)
        x = m.call(m.main + 0x13808B4, m.call(m.main + 0x1361214, o, a))
        return _tail(m, m.main + 0x13808BC, x, sp + 8, r)


@lifted(0x287ECB0)
def move_effect_failed(m, o, b, t, mv, w, how, *_):
    """By `how`: 2 runs 0x287ed8c; 1 queues command 0xcb text 0x48 (b, t); 0 queues 0x157a95c for b; 0 and 1
    then set +0xc0 of 0x139b698(o)."""
    how &= M32
    if how == 2:
        return _tail(m, m.main + 0x287ED8C, o, b, t, mv, w)
    if how == 1:
        q = m.call(m.main + 0x1143584, o)
        bi = m.vcall(b, 0x98) & M32
        m.call_void(m.main + 0x157EBA0, q, bi, 0x48, m.vcall(t, 0x98) & M32)
    elif how == 0:
        q = m.call(m.main + 0x1143584, o)
        m.call_void(m.main + 0x157A95C, q, m.vcall(b, 0x98) & M32)
    else:
        return
    m.put(m.call(m.main + 0x139B698, o) + 0xC0, 1, 1)


@lifted(0x1533028)
def run_by_kind(m, o, _x1, r, *_):
    """Unless byte +0x24 is set, by the move [r+8]'s field 3: 4 and 8 run 0x1793664(o, [r+8], [r+0x10],
    [r+0x18]), 6 runs 0x13807b0(o, [r], [r+8], [r+0x10], [r+0x18])."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    kind = fb.u8(m, m.call(m.main + 0xBF60CC, table, m.u16(m.u64(r + 8))), 3)
    if m.u8(r + 0x24):
        return
    if kind in (4, 8):
        return _tail(m, m.main + 0x1793664, o, m.u64(r + 8), m.u64(r + 0x10), m.u64(r + 0x18))
    if kind == 6:
        return _tail(m, m.main + 0x13807B0, o, m.u64(r), m.u64(r + 8), m.u64(r + 0x10), m.u64(r + 0x18))


@lifted(0x1533CC8)
def hit_texts_and_marks(m, o, _x1, r, *_):
    """r = (target list L, ?, user, info, count byte +0x20, flag +0x21): with info+6, the side texts
    (0x28851c8) and per-target marks (0x28858ac 6 / 0x15 / 0x1c / 0x14, 0x1148470 0x18); else info+4 = 7
    takes L's first kind. Then 0x2885718 on {user, [r+8], count, L, L+0x42, flag}."""
    info = m.u64(r + 0x18)
    if m.u8(info + 6):
        L = m.u64(r)
        m.call_void(m.main + 0x28851C8, m.u64(o + 0x20), m.u64(r + 0x10), m.u8(r + 0x20), L + 0x3C, L,
                    m.u8(r + 0x21))
        i = 0
        while i < m.u8(r + 0x20):
            L = m.u64(r)
            k = m.u8(L + i + 0x3C)
            user = lambda: m.vcall(m.u64(r + 0x10), 0x98) & M32
            if k >= 8:
                m.call_void(m.main + 0x28858AC, o, 6, m.vcall(m.u64(L + 8 * i), 0x98) & M32)
                c = m.u64(o + 0x20)
                u = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), user())
                m.call_void(m.main + 0x1148470, c, u, 0x18)
                m.call_void(m.main + 0x28858AC, o, 0x15, user())
                setup = m.u64(m.u64(o + 0x10) + 0x290)
                ui = user()
                if not m.call(m.main + 0x118AB58, setup, ui, m.vcall(m.u64(m.u64(r) + 8 * i), 0x98) & M32) & 1:
                    m.call_void(m.main + 0x28858AC, o, 0x1C, user())
            elif k != 7:
                m.call_void(m.main + 0x28858AC, o, 0x14, user())
            i += 1
    elif m.u8(info + 4) == 7:
        m.put(info + 4, 1, m.u8(m.u64(r) + 0x3C))
    L = m.u64(r)
    with m.frame(0x40) as sp:
        m.write(sp, bytes(0x30))
        m.put(sp, 8, m.u64(r + 0x10)); m.put(sp + 8, 8, m.u64(r + 8)); m.put(sp + 0x10, 4, m.u8(r + 0x20))
        m.put(sp + 0x18, 8, L); m.put(sp + 0x20, 8, L + 0x42); m.put(sp + 0x28, 1, m.u8(r + 0x21))
        m.call_void(m.main + 0x2885718, m.u64(m.u64(o + 0x78) + 0x520), sp + 0x38, sp)


@lifted(0x157FE88)
def keep_affected_targets(m, o, p, mv, b, lst, *_):
    """For each target of lst, 0x1580064 (b, target, mv, u32 [p]); a target it does not hit is dropped
    (0x157bf08), after 0x287ecb0 when 0x157ea90(lst) was 1."""
    single = m.call(m.main + 0x157EA90, lst) & M32 == 1
    m.call_void(m.main + 0x1143D7C, lst)
    t = m.call(m.main + 0x158003C, lst)
    with m.frame(0x10) as f:
        while t:
            m.call_void(m.main + 0x1580064, o, f + 0xC, f + 8, b, t, mv, m.u32(p))
            if not m.u8(f + 0xC):
                if single:
                    m.call_void(m.main + 0x287ECB0, o, b, t, mv, m.u32(p), m.u32(f + 8))
                m.call_void(m.main + 0x157BF08, lst, t)
            t = m.call(m.main + 0x158003C, lst)


@lifted(0x1532DEC)
def per_target_effects(m, o, _x1, r, *_):
    """r = (targets L, ?, move ptr, ?, count byte +0x20): per target 0x15333f0 {t, 0x153570c value},
    0x153314c {move, [r+0x18], t, L's u16 +0x30+2i} and 0x1533028 {[r+8], move, [r+0x18], t, u16, 0}; then
    0x1532efc {[r+8], move, [r+0x18]}. The records share one stack area, as in the game."""
    obj = lambda off: m.u64(m.u64(o + 0x78) + off)
    with m.frame(0x40) as sp:
        m.write(sp, bytes(0x30))
        i = 0
        while i < m.u8(r + 0x20):
            t = m.u64(m.u64(r) + 8 * i)
            w = m.call(m.main + 0x153570C, m.u64(o + 0x38), m.u16(m.u64(r + 0x10)), m.u64(r + 0x18))
            m.put(sp + 0x10, 4, w); m.put(sp + 8, 8, t)
            m.call_void(m.main + 0x15333F0, obj(0x1780), sp, sp + 8)
            L = m.u64(r)
            t, key = m.u64(L + 8 * i), m.u16(L + 2 * i + 0x30)
            m.put(sp + 0x10, 8, m.u64(r + 0x18)); m.put(sp + 0x18, 8, t)
            m.put(sp + 8, 8, m.u64(r + 0x10)); m.put(sp + 0x20, 4, key)
            m.call_void(m.main + 0x153314C, obj(0x560), sp, sp + 8)
            L = m.u64(r)
            t, key = m.u64(L + 8 * i), m.u16(L + 2 * i + 0x30)
            m.put(sp + 0x18, 8, m.u64(r + 0x18)); m.put(sp + 0x20, 8, t)
            m.put(sp + 8, 8, m.u64(r + 8)); m.put(sp + 0x10, 8, m.u64(r + 0x10))
            m.put(sp + 0x28, 4, key); m.put(sp + 0x2C, 1, 0)
            m.call_void(m.main + 0x1533028, obj(0x1A00), sp, sp + 8)
            i += 1
        m.put(sp + 0x10, 8, m.u64(r + 0x10)); m.put(sp + 0x18, 8, m.u64(r + 0x18))
        m.put(sp + 8, 8, m.u64(r + 8))
        m.call_void(m.main + 0x1532EFC, obj(0x1A20), sp, sp + 8)


@lifted(0x157E9FC)
def keep_affected_and_note(m, o, _x1, r, *_):
    """0x157fe88 on r's four fields; with two or more targets and 0x157ee90 true afterwards, 0x157a95c for
    the user [r+0x10] and +0xc0 of 0x139b698 set."""
    n = m.call(m.main + 0x157EA90, m.u64(r + 0x18)) & M32
    m.call_void(m.main + 0x157FE88, o, m.u64(r), m.u64(r + 8), m.u64(r + 0x10), m.u64(r + 0x18))
    if n < 2 or not m.call(m.main + 0x157EE90, m.u64(r + 0x18)) & 1:
        return
    q = m.call(m.main + 0x1143584, o)
    m.call_void(m.main + 0x157A95C, q, m.vcall(m.u64(r + 0x10), 0x98) & M32)
    m.put(m.call(m.main + 0x139B698, o) + 0xC0, 1, 1)


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


@lifted(0x157EE90)
def emptied(m, lst, *_):
    """Whether the target list had targets (+0xa7 or +0xa9) and has none left (+0xa6)."""
    if not m.u8(lst + 0xA7) and not m.u8(lst + 0xA9):
        return 0
    return int(m.u8(lst + 0xA6) == 0)


@lifted(0x288BAB4)
def request_thaw(m, o, b, mv, *_):
    """Request {id, 3, id, +0x30 = 1, +0x35 = 1} with text (2, 0x66, id, move) through 0x17cdf14."""
    with m.frame(0x70) as sp:
        m.write(sp, bytes(0x70))
        q = sp + 0x10
        m.put(q + 4, 4, 0x31)
        m.call_void(m.main + 0x1146154, q + 0x38)
        m.put(q, 4, m.vcall(b, 0x98) & M32); m.put(q + 4, 4, 3)
        m.put(q + 8, 4, m.vcall(b, 0x98) & M32)
        m.put(q + 0x30, 1, 1); m.put(q + 0x35, 1, 1)
        m.call_void(m.main + 0x2843244, q + 0x38, 2, 0x66)
        m.call_void(m.main + 0x284325C, q + 0x38, m.vcall(b, 0x98) & M32)
        m.call_void(m.main + 0x284325C, q + 0x38, mv & 0xFFFF)
        x = m.call(m.main + 0x17CDF0C, m.call(m.main + 0x1361214, o))
        return _tail(m, m.main + 0x17CDF14, x, sp, q)


@lifted(0x1481CE0)
def move_blocked_text(m, o, b, mv, *_):
    """By b's status (vf 0x230): 2 queues 0x1482e80 (move, 2) and text 0x2a; 3 with a thawing move
    (0x1482d70) runs 0x288bab4."""
    st = m.vcall(b, 0x230) & 0xFFFF
    if st == 2:
        m.call_void(m.main + 0x1482E80, m.call(m.main + 0x1143584, o), b, m.u16(mv), 2)
        return _tail(m, m.main + 0x114ADE8, m.call(m.main + 0x1143584, o), b, 0x2A)
    if st == 3 and m.call(m.main + 0x1482D70, m.u16(mv)) & 1:
        return _tail(m, m.main + 0x288BAB4, o, b, m.u16(mv))


@lifted(0x1481C6C)
def check_move_use(m, o, out, r, *_):
    """out = 0; 0x1481d90 on r (battler, move, ignore byte +0x10, choice +0x18): a refusal code queues
    0x1482da8 and sets out, else 0x1481ce0."""
    m.put(out, 1, 0)
    v = m.call(m.main + 0x1481D90, o, m.u64(r), m.u64(r + 8), m.u8(r + 0x10), m.u64(r + 0x18))
    if not v & 0xFF:
        return _tail(m, m.main + 0x1481CE0, o, m.u64(r), m.u64(r + 8))
    m.call_void(m.main + 0x1482DA8, o, m.u64(r), m.u64(r + 8), v)
    m.put(out, 1, 1)


@lifted(0x1361224)
def raise_side_condition(m, o, out, r, *_):
    """r = (u32 kind, battler or 0): set the condition (0x1361ad8 for the field, 0x13616f0 + command 0x33
    for a battler); when it takes, 0x114beb0 and 0x1361c58, then 0x2880d90 for kind 5, 0x2880e44 for kind 8,
    and for kind 9 vf 0x4e0(0x1d) or 0x282f9d4 on every standing member in speed order. out = whether it
    took. Kind 8 is skipped when 0x13616dc and 0x13616e4 agree."""
    m.put(out, 1, 0)
    kind, b = m.u32(r), m.u64(r + 8)
    if kind == 5:
        _need(m, m.main + 0x2880D90)
    if kind == 9:
        _need(m, m.main + 0x282F9D4)
    if kind == 8 and m.call(m.main + 0x13616DC, m.u64(m.u64(o + 0x10) + 0x70)) & 0xFF \
            == m.call(m.main + 0x13616E4, m.u64(o + 8)) & 0xFF:
        return
    c = m.u64(o + 0x20)
    if not b:
        ok = m.call(m.main + 0x1361AD8, c, kind)
    else:
        ident = m.vcall(b, 0x98) & M32
        ok = m.call(m.main + 0x13616F0, m.u64(m.u64(m.u64(c + 0x20) + 0x10) + 0x70), kind, ident)
        m.call_void(m.main + 0x119AFF0, m.u64(c + 0x18), 0x33, ident, kind & 0xFF)
    if not ok & 1:
        return
    m.call_void(m.main + 0x114BEB0, m.u64(o + 0x20), m.u32(r))
    bid = m.vcall(m.u64(r + 8), 0x98) & M32 if m.u64(r + 8) else 0
    m.call_void(m.main + 0x1361C58, o, bid, m.u32(r))
    if m.u32(r) == 5:
        m.call_void(m.main + 0x2880D90, o)
    if m.u32(r) == 8:
        m.call_void(m.main + 0x2880E44, o)
    if m.u32(r) == 9:
        with m.frame(0xF0) as sp:
            lst = sp + 0x38
            m.call_void(m.main + 0x1144704, o, lst)
            m.put(sp + 8, 8, lst)
            m.call_void(m.main + 0x1143E3C, m.u64(m.u64(o + 0x78) + 0x17E0), sp + 0x10, sp + 8)
            m.put(lst + 0xA8, 1, 0)
            if m.u8(lst + 0xA6):
                m.put(lst + 0xA8, 1, 1)
                p = m.u64(lst)
                while p:
                    if m.vcall(p, 0x4D0, 0x1D) & 1:
                        m.vcall_void(p, 0x4E0, 0x1D)
                    else:
                        m.call_void(m.main + 0x282F9D4, m.u64(o + 0x38), m.vcall(p, 0x98) & M32)
                    i = m.u8(lst + 0xA8)
                    if i >= m.u8(lst + 0xA6):
                        break
                    m.put(lst + 0xA8, 1, i + 1)
                    p = m.u64(lst + 8 * i)
    m.put(out, 1, 1)


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


@lifted(0x282F9D4)
def event_b4(m, o, ident, *_):
    """Event 0xb4 with the id (2)."""
    _event(m, o, 0xB4, ((2, ident, 4, 0x18),))


def _raise_condition(m, o, kind, b):
    with m.frame(0x20) as sp:
        r = sp + 0x10
        m.write(r, bytes(0x10))
        m.put(r, 4, kind); m.put(r + 8, 8, b)
        x = m.call(m.main + 0x136121C, m.call(m.main + 0x1361214, o))
        return _tail(m, m.main + 0x1361224, x, sp + 8, r)


@lifted(0x28889A0)
def raise_field_condition(m, o, kind, *_):
    """0x1361224 with {kind, no battler}."""
    return _raise_condition(m, o, kind & M32, 0)


@lifted(0x1360FFC)
def raise_every_condition(m, o, b, *_):
    """0x1361224 with {k, b} for k = 0..13."""
    for k in range(14):
        r = _raise_condition(m, o, k, b)
    return r


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


def _move_field_3(m, mv):
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    return fb.u8(m, m.call(m.main + 0xBF60CC, table, m.u16(mv)), 3)


def _emptied(m, lst):
    return (m.u8(lst + 0xA7) or m.u8(lst + 0xA9)) and not m.u8(lst + 0xA6)


@lifted(0x157A9BC)
def filter_targets(m, o, out, r, *_):
    """The target pass before a move runs. r = (flags, move, user, target list L, +0x20 / +0x21 / +0x22
    bytes, +0x28, +0x30). Drops targets that are out or at position 10, the lone target when it is the
    user (unless the move's type byte is 7 or the user holds condition 0xc and kind 0x1d1 allows it), runs
    the handler chains 0x157b7a4 / 0x157b8d8 / 0x157c08c / 0x157c404 / 0x157bd30 / 0x157b588 /
    0x15804d0 / 0x157e9fc / 0x157ba2c by move kind (field 3), the kind-9 speed check (texts 0x4a / 0x49,
    0x282e5d8), and the kind-0x3d1 redirection pass (0x282d99c). An emptied list ends the move: 0x157a95c
    or 0x15800cc, then 0x157fd40 and out = 1."""
    m.put(out, 1, 0)
    lst = m.u64(r + 0x18)
    tab = m.u64(m.u64(o + 0x10) + 0xF0)
    m.put(lst + 0xA8, 1, 0)
    if m.u8(lst + 0xA6):
        i = 0
        while True:
            m.put(lst + 0xA8, 1, i + 1)
            p = m.u64(lst + 8 * (i & 0xFF))
            if not p:
                break
            if m.vcall(p, 0x200) & 1 or m.call(m.main + 0x1381420, tab, m.vcall(p, 0x98) & M32) & 0xFF == 0xA:
                m.call_void(m.main + 0x157BF08, lst, p)
            i = m.u8(lst + 0xA8)
            if i >= m.u8(lst + 0xA6):
                break
    lst = m.u64(r + 0x18)
    if m.u8(lst + 0xA7) == 1 and m.u8(lst + 0xA6) and m.u64(lst):
        p0, mv, user = m.u64(lst), m.u64(r + 8), m.u64(r + 0x10)
        if m.vcall(p0, 0x98) & M32 == m.vcall(user, 0x98) & M32 and m.u8(mv + 0xA) != 7:
            if m.vcall(user, 0x510, 0xC) & 1:
                m.call_void(m.main + 0x157BF08, lst, p0)
            else:
                k = _move_field_3(m, mv)
                if k <= 8 and 0x1D1 >> k & 1:
                    m.call_void(m.main + 0x157BF08, lst, p0)
    obj = lambda off: m.u64(m.u64(o + 0x78) + off)
    finder = lambda: m.u64(obj(0x240) + 0x38)
    with m.frame(0x40) as sp:
        R = sp + 0x18
        m.write(sp, bytes(0x40))
        if _emptied(m, m.u64(r + 0x18)):
            if not m.call(m.main + 0x1581494, finder(), m.u64(r + 0x10), m.u64(r + 8)) & 1:
                m.call_void(m.main + 0x157A95C, m.u64(o + 0x20), m.vcall(m.u64(r + 0x10), 0x98) & M32)
                m.put(out, 1, 1)
                return
        m.put(R, 8, m.u64(r + 8)); m.put(R + 8, 8, m.u64(r + 0x10)); m.put(R + 0x10, 8, m.u64(r + 0x18))
        m.call_void(m.main + 0x157B7A4, obj(0x480), sp + 0x10, R)
        m.put(R, 8, m.u64(r + 8)); m.put(R + 8, 8, m.u64(r + 0x10))
        m.put(R + 0x10, 8, m.u64(r + 0x18)); m.put(R + 0x18, 8, m.u64(r + 0x30))
        m.call_void(m.main + 0x157B8D8, obj(0x440), sp + 0x10, R)
        m.put(R + 0x20, 8, m.u64(r + 0x28))
        m.put(R, 8, m.u64(r + 0x10)); m.put(R + 8, 8, m.u64(r + 8))
        m.put(R + 0x10, 8, m.u64(r + 0x30)); m.put(R + 0x18, 8, m.u64(r + 0x18))
        m.call_void(m.main + 0x157C08C, obj(0x3C0), sp + 0x10, R)
        lst = m.u64(r + 0x18)
        if m.u8(lst + 0xA6):
            mv, user = m.u64(r + 8), m.u64(r + 0x10)
            h = obj(0x3E0)
            extra = m.u64(r + 0x28)
            m.put(R + 0x22, 1, 0)
            m.put(R, 8, mv); m.put(R + 8, 8, user); m.put(R + 0x10, 8, lst); m.put(R + 0x18, 8, m.u64(r + 0x30))
            m.put(R + 0x20, 2, 0x3A)
            m.call_void(m.main + 0x157C404, m.u64(m.u64(h + 0x78) + 0x360), sp + 0x10, R)
            if extra and _emptied(m, lst):
                m.call_void(m.main + 0x157BF90, m.u64(h + 0x20), m.vcall(user, 0x98) & M32, 2)
        mv, user, lst = m.u64(r + 8), m.u64(r + 0x10), m.u64(r + 0x18)
        f21, x28, x30 = m.u8(r + 0x21), m.u64(r + 0x28), m.u64(r + 0x30)
        k = _move_field_3(m, mv)
        call = k <= 9 and 0x3D1 >> k & 1
        if not call:
            v = m.call(m.main + 0x1582144, m.u64(o + 0x38), mv, user)
            call = f21 or v & 1
        if call:
            m.put(R, 8, user); m.put(R + 8, 8, mv); m.put(R + 0x20, 8, x28)
            m.put(R + 0x10, 8, x30); m.put(R + 0x18, 8, lst)
            m.call_void(m.main + 0x157BD30, obj(0x380), sp + 0x10, R)
        user, lst, mv, x30 = m.u64(r + 0x10), m.u64(r + 0x18), m.u64(r + 8), m.u64(r + 0x30)
        h = obj(0x3A0)
        for code, flag in ((0x36, 1), (0x37, 0)):
            m.put(R, 8, mv); m.put(R + 8, 8, user)
            m.put(R + 0x20, 2, code); m.put(R + 0x22, 1, flag)
            m.put(R + 0x10, 8, lst); m.put(R + 0x18, 8, x30)
            m.call_void(m.main + 0x157C404, m.u64(m.u64(h + 0x78) + 0x360), sp + 0x10, R)
        m.call_void(m.main + 0x157B588, h, user, mv, lst)
        mv, user, lst = m.u64(r + 8), m.u64(r + 0x10), m.u64(r + 0x18)
        if _move_field_3(m, mv) == 1:
            m.put(R + 8, 8, user); m.put(R + 0x10, 8, lst); m.put(R, 8, mv)
            m.call_void(m.main + 0x15804D0, m.call(m.main + 0x157BF00, m.u64(o + 0x78)), sp + 0x10, R)
        head, mv, user, lst = m.u64(r), m.u64(r + 8), m.u64(r + 0x10), m.u64(r + 0x18)
        if _move_field_3(m, mv) == 2:
            m.put(R + 0x10, 8, user); m.put(R + 0x18, 8, lst); m.put(R, 8, head); m.put(R + 8, 8, mv)
            m.call_void(m.main + 0x157E9FC, m.call(m.main + 0x157B580, m.u64(o + 0x78)), sp + 0x10, R)
        mv, user, lst = m.u64(r + 8), m.u64(r + 0x10), m.u64(r + 0x18)
        x28, b22 = m.u64(r + 0x28), m.u8(r + 0x22)
        if _move_field_3(m, mv) != 9:
            m.put(R, 8, user); m.put(R + 8, 8, mv); m.put(R + 0x20, 1, b22)
            m.put(R + 0x10, 8, lst); m.put(R + 0x18, 8, x28)
            m.call_void(m.main + 0x157BA2C, obj(0x460), sp + 0x10, R)
        else:
            _speed_pass(m, o, user, lst, mv, R)
        if _emptied(m, m.u64(r + 0x18)) and \
                not m.call(m.main + 0x1581494, finder(), m.u64(r + 0x10), m.u64(r + 8)) & 1:
            return _end_move(m, o, out, r)
        if m.u8(r + 0x20):
            return
        mv, user, lst = m.u64(r + 8), m.u64(r + 0x10), m.u64(r + 0x18)
        k = _move_field_3(m, mv)
        if not (k <= 9 and 0x3D1 >> k & 1) and not m.call(m.main + 0x1382AB0, m.u16(mv)) & 1:
            m.put(lst + 0xA8, 1, 0)
            if m.u8(lst + 0xA6):
                p = m.u64(lst)
                m.put(lst + 0xA8, 1, 1)
                while p:
                    if p != user and m.vcall(p, 0x588) & 1 \
                            and not m.call(m.main + 0x1382688, m.u64(o + 0x38), user, p, m.u16(mv)) & 1:
                        m.call_void(m.main + 0x282D99C, m.u64(o + 0x38), user, p)
                        m.call_void(m.main + 0x157BF08, lst, p)
                    i = m.u8(lst + 0xA8)
                    if i >= m.u8(lst + 0xA6):
                        break
                    m.put(lst + 0xA8, 1, i + 1)
                    p = m.u64(lst + 8 * i)
        if not _emptied(m, m.u64(r + 0x18)):
            return
        if m.call(m.main + 0x1581494, finder(), m.u64(r + 0x10), m.u64(r + 8)) & 1:
            return
        m.call_void(m.main + 0x15800CC, o, m.u64(r + 0x10))
        return _end_move(m, o, out, r)


def _end_move(m, o, out, r):
    m.call_void(m.main + 0x157FD40, o, m.u64(r + 0x10), m.u64(r + 8), m.u64(r))
    m.put(out, 1, 1)


def _speed_pass(m, o, user, lst, mv, scratch):
    """Kind 9: each target faster than the user (vf 0x118) or failing the rule checks is dropped with text
    0x4a; 0x282e5d8 may keep it or drop it (text 0x49 unless it set its flag)."""
    if not m.u8(lst + 0xA6):
        return
    if m.u8(lst + 0xA7) == 1 and m.u64(lst) == user:
        return
    s = m.vcall(user, 0x118) & 0xFF
    m.put(lst + 0xA8, 1, 0)
    if not m.u8(lst + 0xA6):
        if m.u8(lst + 0xA7) or m.u8(lst + 0xA9):
            m.call_void(m.main + 0x157BF90, m.u64(o + 0x20), m.vcall(user, 0x98) & M32, 1)
        return
    p = m.u64(lst)
    m.put(lst + 0xA8, 1, 1)
    if not p:
        return

    def text(code, p):
        q = m.u64(o + 0x20)
        a = m.vcall(user, 0x98) & M32
        m.call_void(m.main + 0x157EBC0, m.u64(q + 0x18), 0xCB, a, code, m.vcall(p, 0x98) & M32, 0xFFFF0000)

    def blocked(p):
        if m.call(m.main + 0x1142E68, m.u64(o + 8), m.u64(o + 0x10), p) & 1:
            return False
        flags = m.u64(m.u64(m.u64(o + 8) + 0x38) + 0x498)
        if flags >> 10 & 1:
            return True
        if flags >> 11 & 1:
            if not m.vcall(p, 0x78) & 1:
                return True
            flags = m.u64(m.u64(m.u64(o + 8) + 0x38) + 0x498)
        if flags & 0x10001000:
            return True
        if not flags >> 0x11 & 1:
            return False
        node = m.vcall(p + 0x28, 0)
        static = m.call(m.main + 0x2D1FD38)
        while node:
            if node == static:
                return bool(m.u8(p + 0x714))
            node = m.u64(node)
        return False

    while True:
        if s < m.vcall(p, 0x118) & 0xFF:
            text(0x4A, p)
            m.call_void(m.main + 0x157BF08, lst, p)
        elif blocked(p):
            text(0x4A, p)
            m.call_void(m.main + 0x157BF08, lst, p)
        else:
            m.put(scratch, 1, 0)
            if not m.call(m.main + 0x282E5D8, m.u64(o + 0x38), scratch, user, p, mv) & 1:
                if not m.u8(scratch):
                    text(0x49, p)
                m.call_void(m.main + 0x157BF08, lst, p)
        i, n = m.u8(lst + 0xA8), m.u8(lst + 0xA6)
        if i >= n:
            break
        m.put(lst + 0xA8, 1, i + 1)
        p = m.u64(lst + 8 * i)
        if not p:
            n = m.u8(lst + 0xA6)
            break
    if m.u8(lst + 0xA7):
        if not n:
            m.call_void(m.main + 0x157BF90, m.u64(o + 0x20), m.vcall(user, 0x98) & M32, 1)
    elif not n and m.u8(lst + 0xA9):
        m.call_void(m.main + 0x157BF90, m.u64(o + 0x20), m.vcall(user, 0x98) & M32, 1)


@lifted(0x2881C58)
def apply_and_queue_37(m, c, ident, kind, v, *_):
    """b's vf 0x550(kind, v) for the battler `ident`, then command 0x37 (id, kind byte, v)."""
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(m.u64(c + 0x20) + 0x10) + 0x30), ident)
    m.vcall_void(b, 0x550, kind & M32, v & M32)
    return _tail(m, m.main + 0x119AFF0, m.u64(c + 0x18), 0x37, ident & M32, kind & 0xFF, v & M32)


@lifted(0x1581288)
def move_event_cc(m, o, _x1, r, *_):
    """Move 0x11d tail-calls 0x288b7ac, 0xa4 asks 0x288b7e4 (a yes runs 0x157a950); others raise event
    0xcc / 0xcd: a yes runs 0x157a950, else with its flag set and +0xc0 clear 0x157a95c for [r+8]."""
    key = m.u16(m.u64(r))
    if key == 0x11D:
        return _tail(m, m.main + 0x288B7AC, o, m.u64(r + 8), m.u64(r + 0x10))
    if key == 0xA4:
        if m.call(m.main + 0x288B7E4, o, m.u64(r + 8)) & 1:
            return _tail(m, m.main + 0x157A950, m.call(m.main + 0x139B698, o) + 0x10)
        return
    with m.frame(0x10) as f:
        flag = f + 0xC
        m.put(flag, 1, 0)
        v = m.call(m.main + 0x19B3E28, m.call(m.main + 0x1146E90, o), m.u64(r), m.u64(r + 8), m.u64(r + 0x10),
                   flag)
        if v & 1:
            m.call_void(m.main + 0x157A950, m.call(m.main + 0x139B698, o) + 0x10)
            return
        if not m.u8(flag) or m.u8(m.call(m.main + 0x139B698, o) + 0xC0):
            return
        q = m.call(m.main + 0x1143584, o)
        m.call_void(m.main + 0x157A95C, q, m.vcall(m.u64(r + 8), 0x98) & M32)


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


@lifted(0x2888A5C)
def count_and_queue_4c(m, c, a, b, *_):
    """When 0x13df9d4([c+0x10], a, b) finds a record: bump its +0x1c count and queue command 0x4c (a byte, b)."""
    x = m.call(m.main + 0x13DF9D4, m.u64(c + 0x10), a, b)
    if not x:
        return
    m.call_void(m.main + 0x288DA88, x)
    return _tail(m, m.main + 0x119AFF0, m.u64(c + 0x18), 0x4C, a & 0xFF, b & M32)


@lifted(0x1723914)
def side_slot_value(m, t, side, pos, *_):
    """The u64 at +0x30 of entry (side, pos): 0x28 bytes per side 0..3, 8 per position 0..4; 0 outside."""
    side &= 0xFF
    pos = pos & M32
    if side > 3 or (pos if pos < 0x80000000 else pos - (1 << 32)) > 4:
        return 0
    return m.u64(t + side * 0x28 + 8 * pos + 0x30)


@lifted(0x11480F8)
def bump_side_slot(m, c, side, pos, *_):
    """Raise entry (side, pos) of [[c+0x20]+0x10]+0x210 by one, up to the side's cap ([0x46e2f38]); then
    command 0x2e (side, pos)."""
    pos = pos & M32
    side &= 0xFF
    bad = side > 3 or (pos if pos < 0x80000000 else pos - (1 << 32)) > 4
    if not bad:
        e = m.u64(m.u64(m.u64(c + 0x20) + 0x10) + 0x210) + side * 0x28 + 8 * pos + 0x30
        cap = m.u64(m.u64(m.main + 0x46E2F38) + 8 * side)
        if cap > m.u64(e):
            m.put(e, 8, m.u64(e) + 1)
    return _tail(m, m.main + 0x119AFF0, m.u64(c + 0x18), 0x2E, side, pos & 0xFF)


# Kind of r+4 -> (0x28870ec kind, text, check, its text): 0x1153068's three branches.
_SIDE_KIND = {1: (0x417, 0x2887104, 0x35E), 2: (0x418, 0x171A4EC, 0x35F), 3: (0x419, 0x28871B4, 0x360)}


@lifted(0x1153068)
def side_event(m, o, _x1, r, *_):
    """For battler id [r] with side count 0x11531d4 at most 2: by kind byte r+4 (1..3) the command
    0x28870ec, its text and, when the kind's counter is positive, a second text (kind 3 then 0x28872dc);
    then 0x11480f8 bumps the side's slot."""
    ident = m.u32(r)
    k = m.u8(r + 4)
    if k in _SIDE_KIND:
        _need(m, m.main + _SIDE_KIND[k][1])
        if k == 3:
            _need(m, m.main + 0x28872DC)
    c = m.call(m.main + 0x1589A40, o, ident) & M32
    if m.call(m.main + 0x11531D4, o, 1, c) <= 2 and k in _SIDE_KIND:
        text, counter, more = _SIDE_KIND[k]
        m.call_void(m.main + 0x28870EC, m.call(m.main + 0x1143584, o), ident, k)
        m.call_void(m.main + 0x287EE68, m.call(m.main + 0x1143584, o), ident, text)
        n = m.call(m.main + counter, o) & M32
        if n and n < 0x80000000:
            m.call_void(m.main + 0x287EE68, m.call(m.main + 0x1143584, o), ident, more)
        if k == 3:
            m.call_void(m.main + 0x28872DC, o, ident)
    return _tail(m, m.main + 0x11480F8, m.call(m.main + 0x1143584, o), 1, c)


def _reserve_c9(m, o):
    """Reserve a group 0xcf (placeholder command 0xc9) in [[o+0x28]+8] and note it in the current
    0xc4-byte entry of [[o+0x40]+8] (index +0x938) at +0xa."""
    x = m.u64(m.u64(o + 0x40) + 8)
    i = m.u8(x + 0x938)
    v = m.call(m.main + 0x10AFCB8, m.u64(m.u64(o + 0x28) + 8), 0xC9, 0xCF, 0)
    m.put(x + i * 0xC4 + 0xA, 2, v)


def _copy_move_out(m, out, A, S, pos):
    m.put(out + 0x20, 1, pos)
    m.put(out + 0x15, 8, m.u64(A + 0x25))
    m.put(out + 8, 8, m.u64(S)); m.put(out + 0x10, 8, m.u64(S + 8))


@lifted(0x2D32DB0)
def run_move(m, o, out, r, *_):
    """Run the move of the action record [r] (+0 user id, +4 kind, +8 target position, +0xc, +0x10 move,
    +0x28, +0x54 choice, +0x58 flags, +0x84 packed): move records through 0xf7a750, the usability check
    0x1481c6c, the called-move hook 0x28374bc, target selection 0x173bcf8, the before-move events and
    checks (0x282d080, 0x2d34760, 0x288bc10, 0x14826c0, 0x172a09c, 0x288be44), the move log entry and
    command 0x7b, then 0x283292c. out: u32 result (0 refused, 1 ran, 2 / 3 stopped by 0x172a09c /
    0x288be44, 4 with a follow-up at +0xd8), +4 / +5 flags, +8.. the move record, +0x20 the target
    position, +0x28 the target list."""
    with m.frame(0x1A0) as sp:
        x29 = sp + 0x1A0
        A, S, Q, P = x29 - 0xC0, x29 - 0xA8, x29 - 0x80, x29 - 0x68
        L = sp + 0x30
        m.write(sp, bytes(0x1A0))
        rec = m.u64(r)
        user = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), m.u32(rec))
        w23 = m.u32(rec + 0x84)
        if m.vcall(user, 0x220, 0x2D) & 1:
            c = m.u64(o + 0x20)
            ident = m.vcall(user, 0x98) & M32
            b2 = m.call(m.main + 0xF21C94, m.u64(m.u64(m.u64(c + 0x20) + 0x10) + 0x30), ident)
            m.vcall_void(b2, 0x610, 0x2D)
            m.call_void(m.main + 0x119AFF0, m.u64(c + 0x18), 0x15, ident, 0x2D)
        m.put(sp + 0x28, 2, 0); m.put(sp + 0x2A, 1, 10)
        hi = (w23 >> 16) & 0x3F
        w23 &= 0x3FFFFF
        v = m.call(m.main + 0x287DA44, o, rec) & M32
        mv = m.u16(rec + 0x10)
        if v & 0xFFFF:
            m.call_void(m.main + 0x2830838, m.u64(o + 0x38), user, mv, v)
            pos = m.call(m.main + 0x10E21C0, m.u64(o + 8), m.u64(o + 0x10), user, v,
                         m.u64(m.u64(o + 0x10) + 0x10))
            m.put(rec + 0x10, 2, v); m.put(rec + 8, 1, pos)
            mv = v
        k20, k24 = (hi - 7) & M32, mv & M32
        w24 = m.u16(rec + 0x10) if m.u32(rec + 4) == 1 else 0
        pos8, u0c = m.u8(rec + 8), m.u32(rec + 0xC)
        c1a = m.vcall(user, 0x220, 0x1A)
        c1b = m.vcall(user, 0x220, 0x1B)
        c = m.u64(o + 0x20)
        ident = m.vcall(user, 0x98) & M32
        d = m.u64(c + 0x20)
        b2 = m.call(m.main + 0xF21C94, m.u64(m.u64(d + 0x10) + 0x30), ident)
        if m.call(m.main + 0x119B2A0, m.u64(d + 0x18), b2, w24, w23) & 1:
            m.call_void(m.main + 0x119AFF0, m.u64(c + 0x18), 0x5A, ident, w24, w23)
        m.call_void(m.main + 0x28315CC, m.u64(o + 0x38), user, w24)
        m.call_void(m.main + 0xF7A750, m.u64(o + 0x38), w24, k24, k20, user, S)
        rules = lambda: m.u64(m.u64(o + 8) + 0x38)
        if m.u8(rules() + 0x499) >> 2 & 1:
            from pokeldn.sv.battle.engine.lift1 import _raid_id
            ident = m.vcall(user, 0x98) & M32
            if _raid_id(m, m.u64(m.u64(o + 0x10) + 0x310)) == ident and m.u8(rec + 0x28) == 9:
                m.put(S + 0x14, 1, 1)
        special = False
        if m.u8(rules() + 0x49C) >> 1 & 1:
            x = m.u64(o + 0x10)
            p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(x + 0x290) + 8) + 0x50), m.vcall(user, 0x98) & M32)
            special = bool(p) and m.u32(p) == 1 and m.vcall(user, 0x510, 0x1B) & 1
        obj = lambda off: m.u64(m.u64(o + 0x78) + off)
        if special:
            m.put(P + 0x18, 8, out + 0x28); m.put(P, 8, user); m.put(P + 8, 8, S)
            m.put(P + 0x10, 1, pos8); m.put(P + 0x14, 4, u0c)
            m.call_void(m.main + 0x173BCF8, obj(0x1680), Q, P)
            m.call_void(m.main + 0xF7A750, m.u64(o + 0x38), w24, k24, k20, user, S)
            m.call_void(m.main + 0x2830F0C, m.u64(o + 0x38), user, A, S)
            m.write(P, bytes(0x24))
            if m.call(m.main + 0x28380B0, m.u64(o + 0x38), user, k24, w24, P) & 1:
                m.call_void(m.main + 0x114B0AC, m.u64(o + 0x20), m.vcall(user, 0x98) & M32, P)
            else:
                _reserve_c9(m, o)
            m.call_void(m.main + 0x283126C, m.u64(o + 0x38), user, S, 0x25)
            _copy_move_out(m, out, A, S, pos8)
            m.put(out + 4, 2, 0x101)
            m.put(out, 4, 1)
            return
        m.put(P + 0x18, 8, rec + 0x54); m.put(P, 8, user); m.put(P + 8, 8, S)
        either = (c1a | c1b) & 1
        m.put(P + 0x10, 1, either)
        m.call_void(m.main + 0x1481C6C, obj(0x1AA0), Q, P)
        if m.u8(Q):
            m.put(out + 4, 2, 0)
            _copy_move_out(m, out, A, S, pos8)
            m.put(out, 4, 0)
            return
        if not m.call(m.main + 0x28374BC, m.u64(o + 0x38), user, k24, pos8, sp + 0x28) & 1:
            ident = m.vcall(user, 0x98) & M32
            c = m.u64(o + 0x20)
            m.call_void(m.main + 0x119AFF0, m.u64(c + 0x18), 0xC9, ident, 0, k24 & 0xFFFF, pos8, 0)
            m.call_void(m.main + 0xF7A750, m.u64(o + 0x38), k24, k24, k20, user, A)
            m.put(P + 0x18, 8, L); m.put(P, 8, user); m.put(P + 8, 8, A)
            m.put(P + 0x10, 1, pos8); m.put(P + 0x14, 4, u0c)
            m.call_void(m.main + 0x173BCF8, obj(0x1680), Q, P)
            hit = m.call(m.main + 0x1605670, o, user, k24, L) & 1
            m.call_void(m.main + 0x288AA30, o, user, k24, 0x24)
            m.put(out + 0x20, 1, pos8); m.put(out + 5, 1, hit); m.put(out + 4, 1, 0)
            m.put(out + 0x15, 8, m.u64(A + 0x25))
            m.put(out + 8, 8, m.u64(S)); m.put(out + 0x10, 8, m.u64(S + 8))
            m.put(out, 4, 0)
            return
        nm = m.u16(sp + 0x28)
        if nm == 0:
            m.call_void(m.main + 0xF7A750, m.u64(o + 0x38), k24, k24, k20, user, A)
            m.call_void(m.main + 0xF7A750, m.u64(o + 0x38), w24, k24, k20, user, S)
            use, tpos = w24, pos8
        else:
            np = m.u8(sp + 0x2A)
            u0c = m.call(m.main + 0x11464B0, o, np) & M32
            c = m.u64(o + 0x20)
            ident = m.vcall(user, 0x98) & M32
            d = m.u64(c + 0x20)
            b2 = m.call(m.main + 0xF21C94, m.u64(m.u64(d + 0x10) + 0x30), ident)
            if m.call(m.main + 0x119B2A0, m.u64(d + 0x18), b2, nm, w23) & 1:
                m.call_void(m.main + 0x119AFF0, m.u64(c + 0x18), 0x5A, ident, nm, w23)
            pv = m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), m.vcall(user, 0x98) & M32)
            w24c = m.call(m.main + 0x288AB14, o, k24, pos8)
            ident = m.vcall(user, 0x98) & M32
            c = m.u64(o + 0x20)
            m.call_void(m.main + 0x119AFF0, m.u64(c + 0x18), 0xC9, ident, 0, k24 & 0xFFFF, pos8, 0)
            _called_move_message(m, o, A, S, Q, P, k24, pv, w24c)
            m.call_void(m.main + 0xF7A750, m.u64(o + 0x38), k24, k24, k20, user, A)
            m.call_void(m.main + 0xF7A750, m.u64(o + 0x38), nm, k24, k20, user, S)
            v = m.call(m.main + 0x288AC08, o, user, S) & 0xFF
            if v:
                m.call_void(m.main + 0x288AA30, o, user, m.u16(S), v)
                hit = m.call(m.main + 0x1605670, o, user, k24, L) & 1
                m.put(out + 8, 8, m.u64(S)); m.put(out + 0x10, 8, m.u64(S + 8))
                m.put(out + 0x15, 8, m.u64(A + 0x25)); m.put(out + 0x20, 1, np)
                m.put(out + 5, 1, hit); m.put(out + 4, 1, 0); m.put(out, 4, 0)
                return
            use, tpos = nm, np
        return _run_move_common(m, o, out, rec, user, A, S, Q, P, use, tpos, u0c, k24, k20, either)


def _called_move_message(m, o, A, S, Q, P, k24, pv, w24c):
    """The called-move message (0x1579498) built on the stack areas Q / P and the 10-byte record at
    A+0x30, as 0x2d32db0 lays them out."""
    m.write(A + 0x4D, bytes(8)); m.write(Q, bytes(0x10))
    s0a = m.u8(S + 0xA)
    m.put(Q, 2, k24)
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    m.put(Q + 8, 1, fb.u8(m, m.call(m.main + 0xBF60CC, table, k24), 2))
    m.put(A + 0x5C, 8, 0xFFFF000000000000)
    m.put(P + 0xC, 1, 0)
    m.write(P + 0x30, bytes(0x18))
    m.put(A + 0x6D, 8, 0x0007000007000007)
    m.put(A + 0x65, 8, 0x0000070000070000)
    m.put(A + 0x75, 8, 0x0700000700000700)
    m.put(A + 0x7D, 8, 0x0000070000070000)
    m.put(P + 0x2D, 1, 7)
    m.put(P + 2, 1, pv)
    m.put(Q + 0xA, 1, s0a)
    m.put(P + 3, 1, w24c)
    m.put(P, 2, k24)
    m.put(A + 0x38, 2, 0xFFFF); m.put(A + 0x30, 8, M64)
    x = m.u64(o + 0x28)
    m.put(P + 0xA, 2, m.call(m.main + 0x1579490, m.u64(x + 8)))
    m.call_void(m.main + 0x1579498, m.u64(x + 0x10), Q, P, A + 0x30)


def _run_move_common(m, o, out, rec, user, A, S, Q, P, use, tpos, u0c, k24, k20, either):
    obj = lambda off: m.u64(m.u64(o + 0x78) + off)
    lst = out + 0x28
    m.put(P, 8, user); m.put(P + 8, 8, S); m.put(P + 0x18, 8, lst)
    m.put(P + 0x10, 1, tpos); m.put(P + 0x14, 4, u0c)
    m.call_void(m.main + 0x173BCF8, obj(0x1680), Q, P)
    m.call_void(m.main + 0x282D080, m.u64(o + 0x38), use, k24, k20, user, lst, S)
    if either or m.u8(rec + 0x58) >> 3 & 1:
        hit = 0
    else:
        hit = m.call(m.main + 0x1605670, o, user, k24, lst)
    m.call_void(m.main + 0x2830F0C, m.u64(o + 0x38), user, A, S)
    m.call_void(m.main + 0x2830B98, m.u64(o + 0x38), user, S)
    ident = m.vcall(user, 0x98) & M32
    m.put(P + 0xA, 1, 0); m.put(P + 0xC, 2, 0)
    m.put(P, 4, 4); m.put(P + 4, 4, ident); m.put(P + 8, 2, use)
    m.put(Q, 1, 0)
    m.call_void(m.main + 0x121BDB0, obj(0x1D40), Q, P)
    m.write(P, bytes(0x24))
    if m.call(m.main + 0x28380B0, m.u64(o + 0x38), user, k24, use, P) & 1:
        m.call_void(m.main + 0x114B0AC, m.u64(o + 0x20), m.vcall(user, 0x98) & M32, P)
    else:
        _reserve_c9(m, o)

    def stopped(code):
        _copy_move_out(m, out, A, S, tpos)
        m.put(out + 5, 1, hit & 1); m.put(out + 4, 1, 0)
        m.put(out, 4, code)

    if m.u16(S) != 0xA5:
        h = obj(0x1AC0)
        v = m.call(m.main + 0x2D34760, h, user, S, lst) & M32
        if v & 0xFF:
            m.call_void(m.main + 0x288BB98, h, user, S, v)
            return stopped(0)
    m.put(P, 8, user); m.put(P + 8, 8, S)
    m.call_void(m.main + 0x288BC10, obj(0x1B00), Q, P)
    if m.u8(Q):
        return stopped(0)
    ctx = m.u64(o + 0x10)
    m.put(ctx + 0x360, 8, m.u64(S + 0x10)); m.put(ctx + 0x358, 8, m.u64(S + 8)); m.put(ctx + 0x350, 8, m.u64(S))
    setup, x22 = m.u64(o + 8), m.u64(o + 0x10)
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(x22 + 0x290) + 8) + 0x50), m.vcall(user, 0x98) & M32)
    lvl = 0
    if p:
        lv = m.s(p, 4)
        lvl = lv & M32 if lv < 5 else 0
    if lvl == m.u8(setup + 0x95):
        g = m.u64(m.u64(o + 8) + 0x130)
        if not g:
            raise UnliftedCall("0x2d32db0: null object at [[o+8]+0x130] (the game traps)")
        n = m.u32(g + 0x28)
        if n == M32:
            raise UnliftedCall("0x2d32db0: reference count overflow (the game traps)")
        m.put(g + 0x28, 4, n + 1)
        m.vcall_void(g, 0x48, 1, 1)
        n = m.u32(g + 0x28)
        m.put(g + 0x28, 4, (n - 1) & M32)
        if n == 1:
            m.vcall_void(g, 0x10)
        elif n == 0:
            raise UnliftedCall("0x2d32db0: reference count underflow (the game traps)")
    if m.vcall(user, 0x220, 0x23) & 1:
        m.write(P, bytes(0x5C))
        m.put(P + 4, 4, 0x31)
        ident = m.vcall(user, 0x98) & M32
        m.put(P, 4, ident); m.put(P + 4, 4, 0x23)
        m.put(P + 8, 4, m.vcall(user, 0x98) & M32)
        m.put(P + 0x30, 1, 1); m.put(P + 0x35, 1, 1)
        m.call_void(m.main + 0x17CDF14, obj(0xAE0), Q, P)
        m.vcall_void(user, 0x508, 0xE)
    if m.u16(S) != 0xA5:
        h = obj(0x1AE0)
        v = m.call(m.main + 0x14826C0, m.u64(h + 0x38), user, m.u16(S), 0x22, S, lst) & M32
        if v & 0xFF:
            m.call_void(m.main + 0x288BBD4, h, user, S, v)
            return stopped(0)
    m.put(Q, 2, 0)
    m.put(P, 8, user); m.put(P + 8, 8, S); m.put(P + 0x10, 1, tpos)
    m.call_void(m.main + 0x172A09C, obj(0x1B60), Q, P)
    m.put(out + 4, 1, m.u8(Q + 1))
    if m.u8(Q):
        _copy_move_out(m, out, A, S, tpos)
        m.put(out + 5, 1, hit & 1); m.put(out, 4, 2)
        return
    m.put(P, 8, user); m.put(P + 8, 2, use); m.put(P + 0xA, 1, tpos)
    m.call_void(m.main + 0x288BE44, obj(0x1B40), Q, P)
    if m.u8(Q):
        _copy_move_out(m, out, A, S, tpos)
        m.put(out + 4, 1, 0); m.put(out + 5, 1, hit & 1); m.put(out, 4, 3)
        return
    turn = m.u32(m.u64(m.u64(o + 0x10) + 0x210) + 8)
    ident = m.vcall(user, 0x98) & M32
    c = m.u64(o + 0x20)
    log = m.u64(m.u64(m.u64(c + 0x20) + 0x10) + 0x130)
    n = m.u32(log + 8)
    e = log + n * 0xC
    m.put(e + 0x14, 2, use); m.put(e + 0xC, 4, turn); m.put(e + 0x10, 4, ident); m.put(e + 0x16, 1, 0)
    m.put(log + 8, 4, 0 if n + 1 >= 0x190 else n + 1)
    m.call_void(m.main + 0x119AFF0, m.u64(c + 0x18), 0x7B, use, turn, ident)
    m.call_void(m.main + 0x283126C, m.u64(o + 0x38), user, S, 0x25)
    m.put(P, 4, 0); m.put(Q, 4, 0)
    m.call_void(m.main + 0x283292C, m.u64(o + 0x38), user, use, lst, P, Q)
    follow = m.u32(P)
    _copy_move_out(m, out, A, S, tpos)
    m.put(out + 5, 1, hit & 1)
    if not follow:
        m.put(out + 4, 1, 1); m.put(out, 4, 1)
        return
    w1 = m.u32(Q)
    fpos = m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), w1) & 0xFF if w1 else 0xA
    m.put(out + 0x108, 1, fpos); m.put(out + 0xDC, 4, follow); m.put(out + 0xD8, 1, 1)
    m.put(out + 4, 1, 0); m.put(out, 4, 4)


@lifted(0x11410E0)
def side_event_of(m, o, p, *_):
    """0x1153068 on [o+0x78]'s object with {u32 [p], byte [p+0x25]}."""
    with m.frame(0x10) as sp:
        r = sp + 8
        m.put(r, 4, m.u32(p)); m.put(r + 4, 1, m.u8(p + 0x25))
        x = m.call(m.main + 0x114111C, m.u64(o + 0x78))
        return _tail(m, m.main + 0x1153068, x, sp, r)


@lifted(0x157FD04)
def move_event_cc_of(m, o, a, b, c, *_):
    """0x1581288 on [o+0x78]'s object with {b, a, c}."""
    with m.frame(0x20) as sp:
        r = sp + 8
        m.put(r, 8, b); m.put(r + 8, 8, a); m.put(r + 0x10, 8, c)
        x = m.call(m.main + 0x157FD38, m.u64(o + 0x78))
        return _tail(m, m.main + 0x1581288, x, sp, r)


@lifted(0x15799A8)
def rule_check_each_target_of(m, o, a, b, c, d, *_):
    """0x157a874 on [o+0x78]'s object with {a, c, b, d}."""
    with m.frame(0x30) as sp:
        r = sp + 0x10
        m.put(r, 8, a); m.put(r + 8, 8, c); m.put(r + 0x10, 8, b); m.put(r + 0x18, 8, d)
        x = m.call(m.main + 0x15799DC, m.u64(o + 0x78))
        return _tail(m, m.main + 0x157A874, x, sp + 8, r)


@lifted(0x136038C)
def end_check_after_faint(m, o, b, flag, *_):
    """When the battle is over (0x114a808 false) and `flag`: 0x1361bb0 with b."""
    if m.call(m.main + 0x114A808, o) & 1:
        if m.call(m.main + 0x13603FC, o) & 1:
            return
    if not flag & 1:
        return
    with m.frame(0x20) as sp:
        m.put(sp + 0x18, 8, b)
        x = m.call(m.main + 0x1360F04, m.call(m.main + 0x1361214, o))
        m.call_void(m.main + 0x1361BB0, x, sp + 8, sp + 0x18)


@lifted(0x136024C)
def battler_left(m, o, _x1, r, *_):
    """Clear everything tied to the battler [r]: 0x13618ac, 0x13602d8, 0x1360604, 0x1360ce8, 0x1360404,
    0x1360ffc, then 0x136038c with 0x1360558's answer."""
    m.call_void(m.main + 0x13618AC, m.call(m.main + 0x1146E90, o), m.u64(r))
    m.call_void(m.main + 0x13602D8, o, m.u64(r))
    v = m.call(m.main + 0x1360558, o, m.u64(r))
    for a in (0x1360604, 0x1360CE8, 0x1360404, 0x1360FFC):
        m.call_void(m.main + a, o, m.u64(r))
    return _tail(m, m.main + 0x136038C, o, m.u64(r), v & 1)


@lifted(0x1360F04)
def get_1320(m, o, *_): return m.u64(o + 0x1320)


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


@lifted(0x1143394)
def raise_pending_field_conditions(m, o, *_):
    """0x28889a0(k) for each field condition k = 1..13 that 0x114358c reports."""
    for k in range(1, 14):
        if m.call(m.main + 0x114358C, m.call(m.main + 0x1143584, o), k) & 1:
            if k == 13:
                return _tail(m, m.main + 0x28889A0, o, k)
            m.call_void(m.main + 0x28889A0, o, k)


@lifted(0x287F844)
def add_and_queue_81(m, c, v, *_):
    """0x288d228([c+0x20], v), then command 0x81 with v as a signed 16-bit value."""
    m.call_void(m.main + 0x288D228, m.u64(c + 0x20), v)
    s = v & 0xFFFF
    s = s - 0x10000 if s & 0x8000 else s
    return _tail(m, m.main + 0x119AFF0, m.u64(c + 0x18), 0x81, s & M32)


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


@lifted(0x288DA60)
def end_side_condition(m, rec, *_):
    """When the count +0x20 is set: clear the kind bits (low 3) of +0x10 and the 8 bytes at +0x1c; 1."""
    if not m.u32(rec + 0x20):
        return 0
    v = m.u64(rec + 0x10) & ~7 & M64
    m.put(rec + 0x1C, 8, 0)
    m.put(rec + 0x10, 8, v)
    return 1


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


@lifted(0x2888400)
def end_side_condition_and_queue(m, c, side, k, *_):
    """For side 0 or 1: end the side condition k (0x288da60) and queue command 0x4b (side, k)."""
    if not m.call(m.main + 0x288D980, side) & 1:
        return 0
    x = m.call(m.main + 0x13DF9D4, m.u64(c + 0x10), side, k)
    if not x:
        return 0
    if not m.call(m.main + 0x288DA60, x) & 1:
        return 0
    m.call_void(m.main + 0x119AFF0, m.u64(c + 0x18), 0x4B, side & 0xFF, k & M32)
    return 1


@lifted(0x2888474)
def release_and_queue_66(m, c, side, k, *_):
    m.call_void(m.main + 0x288D11C, m.u64(c + 0x20), side, k)
    return _tail(m, m.main + 0x119AFF0, m.u64(c + 0x18), 0x66, side & 0xFF, k & M32)


@lifted(0x11431C0)
def tick_side_conditions(m, o, *_):
    """For both sides and the 19 side conditions with a count (+0x20 of each 0x28-byte entry from
    [[o+0x10]+0x90]+8) whose kind (low 3 bits of +0x10) is 2 or 4: count one turn (0x2888a5c); when the
    count is reached (0x2888ab8), end it (0x2888400 / 0x2888474) and queue its end text 0x288835c."""
    for side, base in ((0, 0x28), (1, 0x320)):
        for k in range(0x13):
            e = m.u64(m.u64(o + 0x10) + 0x90) + base + 0x28 * k
            if not m.u32(e):
                continue
            x = e - 0x20
            p = m.call(m.main + 0x1143354, x)
            kind = m.u32(p + 8) & 7
            if kind not in (2, 4):
                continue
            m.call_void(m.main + 0x2888A5C, m.call(m.main + 0x1143584, o), side, k)
            if not m.call(m.main + 0x2888AB8, x) & 1:
                continue
            if m.call(m.main + 0x2888400, m.call(m.main + 0x1143584, o), side, k) & 1:
                m.call_void(m.main + 0x2888474, m.call(m.main + 0x1143584, o), side, k)
            m.call_void(m.main + 0x288835C, m.call(m.main + 0x1143584, o), m.u32(p), side, k)


@lifted(0x1142F64)
def raise_pending_field_conditions_of(m, o, *_):
    with m.frame(0x10) as f:
        return _tail(m, m.main + 0x1143394, m.call(m.main + 0x1142F90, m.u64(o + 0x78)), f, f + 8)


@lifted(0x1360214)
def battler_left_of(m, o, b, *_):
    with m.frame(0x10) as f:
        m.put(f + 8, 8, b)
        return _tail(m, m.main + 0x136024C, m.call(m.main + 0x1360244, m.u64(o + 0x78)), f, f + 8)


@lifted(0x114318C)
def tick_side_conditions_of(m, o, *_):
    with m.frame(0x10) as f:
        return _tail(m, m.main + 0x11431C0, m.call(m.main + 0x11431B8, m.u64(o + 0x78)), f, f + 8)


def _ratio_bounded(m, ctx, kind, slot, lo, hi):
    """A type-3 parameter holding the ratio 4096/4096 with bounds lo and hi."""
    e = _param_record(m, ctx, kind, slot)
    if e:
        m.put(e + 0xC, 4, 0x1000); m.put(e + 0x10, 4, lo); m.put(e + 0x14, 4, hi); m.put(e + 0x18, 8, 0)
        m.put(e + 0xA, 1, 3)


def _scale12(v, factor):
    """(v * factor) >> 12 in 32 bits, rounded up when the dropped part exceeds 0x800."""
    p = (v * factor) & M32
    return (p >> 12) + (1 if p & 0xFFF > 0x800 else 0)


def _percent_factor(pct):
    """int32(float32(pct) / 100 * 4096 +- 0.5), as float32 operations."""
    q = _f32(_f32(float(pct)) / _f32(100.0))
    x = _f32(_f32(q * 4096.0) + (0.5 if q > 0 else -0.5))
    if x != x:
        return 0
    return max(-0x80000000, min(0x7FFFFFFF, int(x))) & M32


@lifted(0xF7C344)
def damage(m, o, att, dfn, mv, eff, scale, crit, fixed_roll, b9, weather, out, *_):
    """The damage of the move record mv (+0 move, +4 power, +8 type, +9 category, +0xb, +0xc) from att to
    dfn: events 0x93, 0x5d / 0x5e (a fixed amount or none), 0x47 / 0x48 (power), 0x49 / 0x4b / 0x4c
    (attack, its battler and stat), 0x4a / 0x4d (defense), the base formula 0x28764e0, `scale`, weather 0x56,
    spread 0x2d, critical hit, the random roll, same-type bonus, effectiveness level `eff` (7 = x1), burn,
    then 0x5f / 0x60. out (u16) = the damage (at least 1); returns whether 0x5e / 0x5d fixed it."""
    ctx = lambda: m.u64(o + 0x10)
    P = lambda kind, value, typ, slot: ev_param(m, ctx(), kind, value & M32, typ, slot)
    fire = lambda ev: m.call_void(m.main + 0xF7B310, ctx(), ev, 8, 1)
    val = lambda slot: _value(m, ctx(), slot)
    val16 = lambda slot: (m.u16(m.u64(m.u64(ctx() + 0x78) + slot) + 0xC) if m.u64(m.u64(ctx() + 0x78) + slot) else 0)
    named = lambda key: m.vcall(m.call(m.main + 0x11521A0, o), 0x68, key) & M32
    idf = lambda b: m.vcall(b, 0x98) & M32
    eff &= 0xFF; crit &= 1; b9 &= 1; weather &= 0xFF
    # event 0x93
    ev_push(m, ctx())
    P(2, idf(dfn), 4, 0x18); P(0x60, 0, 1, 0x308); P(0x76, 0, 1, 0x3B8)
    fire(0x93)
    r60 = val(0x308)
    ev_pop(m, ctx())
    # events 0x5d / 0x5e on the outer frame, kept open to the end
    ev_push(m, ctx())
    P(0x3D, eff, 4, 0x1F0)
    P(3, idf(att), 4, 0x20); P(4, idf(dfn), 4, 0x28); P(0x4C, crit, 4, 0x268)
    P(0x16, m.u8(mv + 8), 4, 0xB8); P(0x12, m.u16(mv), 4, 0x98); P(99, m.u8(mv + 0xB), 4, 0x320)
    P(0x1B, m.u8(mv + 9), 4, 0xE0); P(0x19, m.u32(mv + 0xC), 4, 0xD0); P(0x4D, b9, 4, 0x270)
    P(0x60, int(r60 != 0), 4, 0x308); P(0x3A, 0, 0, 0x1D8); P(0x3B, 0, 0, 0x1E0); P(0x3C, 0, 0, 0x1E8)
    fire(0x5D); fire(0x5E)
    fixed, r1e0, r1e8 = val(0x1D8), val(0x1E0), val(0x1E8)
    stopped = int((r1e0 | r1e8) != 0)
    dmg = fixed if r1e8 == 0 else 0
    if not stopped:
        dmg = _damage_body(m, o, att, dfn, mv, eff, scale, crit, fixed_roll, weather, P, fire, val, val16, named,
                           idf, ctx)
    fire(0x60)
    ev_pop(m, ctx())
    dmg &= M32
    if dmg == 0 and r1e8 == 0:
        dmg = 1
    m.put(out, 2, dmg)
    return stopped


def _damage_body(m, o, att, dfn, mv, eff, scale, crit, fixed_roll, weather, P, fire, val, val16, named, idf, ctx):
    # power: events 0x47 / 0x48
    ev_push(m, ctx())
    P(3, idf(att), 4, 0x20); P(4, idf(dfn), 4, 0x28)
    P(0x12, m.u16(mv), 4, 0x98); P(0x16, m.u8(mv + 8), 4, 0xB8); P(0x1B, m.u8(mv + 9), 4, 0xE0)
    P(99, m.u8(mv + 0xB), 4, 0x320); P(0x5D, 0, 1, 0x2F0); P(0x5E, 0, 1, 0x2F8)
    P(0x33, m.u16(mv + 4), 1, 0x1A0)
    fire(0x47)
    _ratio_bounded(m, ctx(), 0x34, 0x1A8, 0x29, 0x200000)
    fire(0x48)
    pw, ratio = val16(0x1A0), val(0x1A8)
    ev_pop(m, ctx())
    if m.vcall(att, 0x4D0, 0x14) & 1:
        ratio = (ratio << int(m.u8(mv + 8) == 0xC)) & M32
    power = _scale12(ratio, pw)
    power = _tera_floor(m, o, att, mv, power)
    # attack: events 0x49 / 0x4b / 0x4c
    ev_push(m, ctx())
    P(3, idf(att), 4, 0x20); P(4, idf(dfn), 4, 0x28); P(0x40, 0, 0, 0x208); P(0x59, 0, 0, 0x2D0)
    fire(0x49)
    raw_atk, alt = val(0x2D0), val(0x208)
    src = att
    if alt:
        src = m.call(m.main + 0xF21C94, m.call(m.main + 0xE7E284, m.u64(o + 0x18)), alt)
    ev_push(m, ctx())
    P(3, idf(src), 4, 0x20); P(0x12, m.u16(mv), 4, 0x98)
    P(0x41, 10 if m.u8(mv + 9) == 2 else 8, 1, 0x210)
    fire(0x4B)
    stat = val(0x210)
    ev_pop(m, ctx())
    if raw_atk:
        slot = 0xB8
    elif crit and stat in (8, 9, 10, 11):
        stage = m.vcall(src, 0xB0, stat - 7) & M32
        slot = 0xB0 if stage < 0x80000000 and stage >= 6 else 0xB8
    else:
        slot = 0xB0
    a = m.vcall(src, slot, stat)
    P(0x12, m.u16(mv), 4, 0x98); P(0x16, m.u8(mv + 8), 4, 0xB8); P(0x1B, m.u8(mv + 9), 4, 0xE0)
    P(0x36, a & 0xFFFF, 0, 0x1B8)
    _ratio_bounded(m, ctx(), 0x38, 0x1C8, 0x19A, 0x20000)
    P(0x5A, 0, 1, 0x2D8)
    fire(0x4C)
    av, ar = val16(0x1B8), val(0x1C8)
    no_burn = int(val(0x2D8) != 0)
    ev_pop(m, ctx())
    atk = _scale12(ar, av)
    # defense: events 0x4a / 0x4d
    cat = m.u8(mv + 9)
    dstat = 0xB if cat == 2 else 9
    ev_push(m, ctx())
    P(3, idf(att), 4, 0x20); P(4, idf(dfn), 4, 0x28); P(0x41, dstat, 4, 0x210)
    P(0x42, 0, 0, 0x218); P(0x59, 0, 1, 0x2D0)
    fire(0x4A)
    raw_def, swap = val(0x2D0), val(0x218)
    ev_pop(m, ctx())
    if swap & 1:
        dstat = 9 if cat == 2 else 0xB
    if raw_def & 0xFF:
        slot = 0xB8
    elif crit:
        slot = 0xE8
    else:
        slot = 0xB0
    d = m.vcall(dfn, slot, dstat) & M32
    if m.call(m.main + 0x116EC0C, o) & 0xFF == 4:
        has = m.vcall(dfn, 0x300, 5)
        if dstat == 0xB and has & 1:
            d = _scale12(d & 0xFFFF, _percent_factor(named(m.main + 0x3C69ED0)))
    if m.call(m.main + 0x116EC0C, o) & 0xFF == 3:
        has = m.vcall(dfn, 0x300, 0xE)
        if dstat == 9 and has & 1:
            d = _scale12(_percent_factor(named(m.main + 0x3C69ED8)), d & 0xFFFF)
    dcat = cat
    if swap & 1:
        dcat = 1 if cat == 2 else 2
    ev_push(m, ctx())
    P(3, idf(att), 4, 0x20); P(4, idf(dfn), 4, 0x28)
    P(0x12, m.u16(mv), 4, 0x98); P(0x16, m.u8(mv + 8), 4, 0xB8); P(0x1B, dcat, 4, 0xE0)
    P(0x37, d & 0xFFFF, 0, 0x1C0)
    _ratio_bounded(m, ctx(), 0x38, 0x1C8, 0x19A, 0x20000)
    fire(0x4D)
    dv, dr = val16(0x1C0), val(0x1C8)
    ev_pop(m, ctx())
    dfv = _scale12(dr, dv)
    # base damage
    with m.frame(0x10) as rec:
        m.put(rec, 4, power & 0xFFFF); m.put(rec + 4, 4, m.vcall(att, 0x118) & 0xFF)
        m.put(rec + 8, 4, atk & 0xFFFF); m.put(rec + 0xC, 4, dfv & 0xFFFF)
        dmg = m.call(m.main + 0x28764E0, m.u64(o + 8), rec) & M32
    scale &= M32
    if scale != 0x1000:
        dmg = _scale12(dmg, scale)
    holder = m.call(m.main + 0x11521A0, o)
    pct = 100
    if 1 <= weather <= 6:
        t = m.u8(mv + 8)
        key = None
        if weather in (1, 6):
            key = {9: 0x46E26D8, 10: 0x46E26D0}.get(t)
        elif weather in (2, 5):
            key = {9: 0x46E26D0, 10: 0x46E26D8}.get(t)
        if key is not None:
            pct = m.vcall(holder, 0x68, m.u64(m.main + key)) & M32
    factor = _percent_factor(pct)
    ev_push(m, ctx())
    P(0x3E, weather, 4, 0x1F8)
    P(2, idf(att), 4, 0x18); P(3, idf(att), 4, 0x20); P(4, idf(dfn), 4, 0x28)
    P(0x12, m.u16(mv), 4, 0x98); P(0x16, m.u8(mv + 8), 4, 0xB8)
    P(0x38, factor, 0, 0x1C8)
    fire(0x56)
    wf = val(0x1C8)
    ev_pop(m, ctx())
    if wf != 0x1000:
        dmg = _scale12(wf, dmg)
    if m.vcall(dfn, 0x220, 0x2D) & 1:
        dmg = ((named(m.main + 0x3C69EA8) * dmg) & M32) // 100
    if crit:
        dmg = ((named(m.main + 0x3C69EB0) * dmg) & M32) // 100
    if not m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49A) >> 4 & 1:
        r = named(m.u64(m.main + 0x46E26C8))
        if not fixed_roll & 1:
            n = (r + 1) & M32
            r = m.call(m.main + 0x11440F0, m.u64(m.u64(o + 0x18) + 0x10), n) if n >= 2 else 0
        dmg = ((((100 - r) & 0xFFFF) * dmg) & M32) // 100
    t = m.u8(mv + 8)
    stab_type = t
    if t == 0x12:
        stab_type = m.call(m.main + 0x2D2219C, att, 0x12, m.u16(mv)) & M32
    if t != 0x12 or stab_type & 0xFF != 0x12:
        dmg = _scale12(m.call(m.main + 0x2D0C404, o, att, stab_type) & M32, dmg)
    dmg &= M32
    if eff == 0:
        dmg = 0
    elif 1 <= eff <= 6:
        dmg >>= 7 - eff
    elif 8 <= eff <= 13:
        dmg = (dmg << (eff - 7)) & M32
    if m.u8(mv + 9) == 1 and m.vcall(att, 0x230) & 0xFFFF == 4 and not no_burn:
        dmg = ((named(m.main + 0x3C69EC0) * dmg) & M32) // 100
    # 0x5f on the outer frame
    _ratio_bounded(m, ctx(), 0x38, 0x1C8, 0x29, 0x20000)
    P(0x35, dmg, 0, 0x1B0); P(100, 0, 1, 0x328); P(0x65, 0, 1, 0x330)
    fire(0x5F)
    return _scale12(val(0x1B0), val(0x1C8))


def _tera_floor(m, o, att, mv, power):
    """A Terastallized battler's move of its Tera type (or a Stellar one's first use of a type) below the
    named floor (0x3c69ec8) is raised to it, outside multi-hit moves (field 9 > 1), moves with positive
    priority-like field 8, and the listed exceptions."""
    node = m.vcall(att + 0x28, 0)
    static = m.call(m.main + 0x2D1FD38)
    while node and node != static:
        node = m.u64(node)
    if not node:
        return power
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    t, key = m.u8(mv + 8), m.u16(mv)
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    if fb.u8(m, m.call(m.main + 0xBF60CC, table, key), 9) > 1:
        return power
    if not m.u8(att + 0x714):
        return power
    has = m.vcall(att, 0x300, t)
    if m.u8(att + 0x714) and m.u8(att + 0x715) == 0x63:
        if t == 0x12:
            return power
        bit = 0x1F if t == 0x63 else t
        if m.u32(att + 0x71C) >> (bit & 31) & 1:
            return power
    elif not has & 1:
        return power
    key = m.u16(mv)
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    rec = m.call(m.main + 0xBF60CC, table, key)
    f8 = fb.u8(m, rec, 8)
    if f8 and (f8 if f8 < 0x80 else f8 - 0x100) > 0:
        return power
    k = m.u16(mv)
    if k < 0x1BF:
        if k < 0x11C:
            if k in (0x43, 0xAF, 0xB3):
                return power
        elif (k - 0x143 < 0x34 and 0x8002000000001 >> (k - 0x143) & 1) or k == 0x11C:
            return power
    elif k <= 0x216:
        if k - 0x1BF < 0x28 and 0xA000008001 >> (k - 0x1BF) & 1:
            return power
    elif k in (0x217, 0x334, 0x390):
        return power
    v = m.vcall(m.call(m.main + 0x11521A0, o), 0x68, m.main + 0x3C69EC8) & M32
    sv = v - (1 << 32) if v & 0x80000000 else v
    return v if sv > (power & 0xFFFF) else power


def _tera_percent(m, user, mv, base, same, other):
    """`base` percent, replaced by `same` (or `other`) read lazily when the user is of the 0x46d3f08 class,
    Terastallized (+0x714) and the move's type is (or is not) its Tera type (0x2a71f50 of +0x715)."""
    if not base:
        return 0
    node = m.vcall(user + 0x28, 0)
    static = m.call(m.main + 0x2D1FD38)
    while node and node != static:
        node = m.u64(node)
    if not node or not m.u8(user + 0x714):
        return base
    t = m.u8(mv + 8)
    v = same() if t == m.call(m.main + 0x2A71F50, m.u8(user + 0x715)) & 0xFF else other()
    return v if v else base


def _percent_round(v, pct):
    """v * pct / 100 in 32 bits, rounded up from a remainder of 50."""
    p = (v * pct) & M32
    return (p // 100 + (1 if p % 100 > 0x31 else 0)) & 0xFFFF


@lifted(0x1535C8C)
def damage_each_target(m, o, out, r, *_):
    """For each target of the list [r+8], the damage 0xf7c344 of user [r] with move record [r+0x10] at the
    target's effectiveness ([r+0x18], 10 {id, level} pairs, 7 when absent) and scale [r+0x20]: raid and
    multi-battle percentages, substitutes (vf 0x588 and 0x1382688) taking min(damage, vf 0x590), the
    0x560(6) survival cap, 0x283355c, then 0x287b2d4 with [r+0x28]. out: +0 hits, +1 substitute hits,
    12-byte rows from +4 {u16 damage, +4 id, +8 level, +9 0x283355c, +0xa flags}. In multi-battles, a
    0x1820eb8 record for the field battler with condition 0x19."""
    rules = lambda: m.u64(m.u64(o + 8) + 0x38)
    user, mv, tab = m.u64(r), m.u64(r + 0x10), m.u64(r + 0x18)
    slot_level = lambda b: _slot_level_of(m, o, m.vcall(b, 0x98) & M32)
    with m.frame(0x20) as sp:
        crit_out, dmgp, capp = sp, sp + 4, sp + 8
        m.put(crit_out, 1, 0)
        m.put(out, 2, 0)
        m.put(m.u64(r + 8) + 0xA8, 1, 0)
        lst = m.u64(r + 8)
        i = m.u8(lst + 0xA8)
        if i < m.u8(lst + 0xA6):
            m.put(lst + 0xA8, 1, i + 1)
            t = m.u64(lst + 8 * i)
            idx = 0
            while t:
                if m.vcall(t, 0x588) & 1:
                    sub = m.call(m.main + 0x1382688, m.u64(o + 0x38), user, t, m.u16(mv)) & 1 ^ 1
                else:
                    sub = 0
                e = out + idx * 0xC
                m.put(e + 8, 4, m.vcall(t, 0x98) & M32)
                key = m.u16(mv)
                crit = _crit_roll(m, o, user, t, key, crit_out)
                m.put(e + 0xE, 1, (m.u8(e + 0xE) & 0xFC) | (crit & 1) | (m.u8(crit_out) << 1) & 0xFF)
                ident = m.u32(e + 8)
                eff = 7
                for k in range(10):
                    if m.u32(tab + 8 * k) == ident:
                        eff = m.u8(tab + 8 * k + 4)
                        break
                m.put(e + 0xC, 1, eff)
                scale = m.u32(r + 0x20)
                tid = m.vcall(t, 0x98) & M32
                f = m.u64(m.u64(o + 0x78) + 0xC80)
                w = m.call(m.main + 0x116EC0C, m.u64(f + 0x38))
                if tid:
                    w = m.call(m.main + 0x116EE6C, m.u64(f + 0x38), tid, w)
                res = m.call(m.main + 0xF7C344, m.u64(o + 0x38), user, t, mv, eff, scale, crit & 1, 0, sub, w & 0xFF,
                             dmgp) & 1
                if m.u8(rules() + 0x49C) >> 1 & 1 and slot_level(user) == 1 and slot_level(t) != 1 \
                        and m.vcall(user, 0x510, 0x1B) & 1:
                    m.put(dmgp, 2, 9999)
                if m.u8(rules() + 0x499) >> 2 & 1 and m.vcall(user, 0x4D0, 0x1B) & 1:
                    m.put(dmgp, 2, _percent_round(m.u16(dmgp), 0x96))
                    b = m.call(m.main + 0x17D5CEC, m.u64(m.u64(o + 0x10) + 0x30), m.vcall(user, 0x98) & M32)
                    if b:
                        m.call_void(m.main + 0x1140198, m.u64(o + 0x20), b, 0x1B)
                pct = _target_percent(m, o, user, t, mv)
                if pct is not None:
                    m.put(dmgp, 2, _percent_round(pct, m.u16(dmgp)))
                fl = (m.u8(e + 0xE) & 0xFB) | (4 if res else 0)
                m.put(e + 0xE, 1, fl)
                dmg = m.u16(dmgp)
                m.put(e + 4, 2, dmg)
                if res:
                    fl &= 0xFC
                    m.put(e + 0xE, 1, fl)
                    m.put(e + 0xC, 1, 7)
                fl = (fl & 0xF7) | (8 if sub else 0)
                m.put(e + 0xE, 1, fl)
                if sub:
                    cap = m.vcall(t, 0x590) & M32
                    m.put(e + 4, 2, cap if cap < dmg else dmg)
                    m.put(e + 0xD, 1, 0)
                    m.put(out + 1, 1, m.u8(out + 1) + 1)
                else:
                    hp = m.vcall(t, 0x108) & 0xFFFF
                    left = hp if hp < dmg else dmg
                    if m.vcall(t, 0x560, 6) & M32 and _survival_cap_applies(m, o, t):
                        p6 = m.vcall(t, 0x560, 6) & M32
                        capv = _percent_round(p6, m.vcall(t, 0x110) & 0xFFFF)
                        if ((hp - left) & M32) <= capv:
                            left = (hp - capv) & M32
                            q = m.u64(o + 0x20)
                            b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), m.vcall(t, 0x98) & M32)
                            m.call_void(m.main + 0x1148470, q, b, 0x19)
                            if m.u8(rules() + 0x49A) >> 1 & 1:
                                m.call_void(m.main + 0x1148894, m.u64(o + 0x48), m.vcall(t, 0x98) & M32)
                    m.put(capp, 2, left)
                    m.put(e + 0xD, 1, m.call(m.main + 0x283355C, m.u64(o + 0x38), user, t, 1, capp))
                    m.put(e + 4, 2, m.u16(capp))
                    m.put(out, 1, m.u8(out) + 1)
                if m.u64(r + 0x28):
                    m.call_void(m.main + 0x287B2D4, m.u64(r + 0x28), m.u64(o + 0x10), user, t, m.u8(e + 0xC))
                lst = m.u64(r + 8)
                i = m.u8(lst + 0xA8)
                if i >= m.u8(lst + 0xA6):
                    break
                idx += 1
                m.put(lst + 0xA8, 1, i + 1)
                t = m.u64(lst + 8 * i)
    _field_record(m, o)


def _slot_level_of(m, o, ident):
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50), ident)
    if not p:
        return 0
    v = m.s(p, 4)
    return v & M32 if v < 5 else 0


def _crit_roll(m, o, user, t, key, crit_out):
    flags = m.u64(m.u64(m.u64(o + 8) + 0x38) + 0x498)
    if flags >> 8 & 1:
        v = m.call(m.main + 0x144E784, o, m.vcall(t, 0x98) & M32)
        if m.call(m.main + 0x200B8A8, m.u64(m.u64(o + 0x10) + 0x290), v) & 1:
            return 0
        flags = m.u64(m.u64(m.u64(o + 8) + 0x38) + 0x498)
    if flags >> 11 & 1 and not m.vcall(t, 0x78) & 1:
        x = m.call(m.main + 0x114E498, o, _slot_level_of(m, o, m.vcall(t, 0x98) & M32))
        if not m.call(m.main + 0x284404C, x) & 0xFF:
            return 0
    return m.call(m.main + 0x282DF44, m.u64(o + 0x38), user, t, key, crit_out) & M32


def _target_percent(m, o, user, t, mv):
    """The raid (rule bit 2: the raid battler as target, record +0x70 == 1, percent +0x2a / +0x2c / +0x2e)
    or multi-battle (rule 0x49c bit 1, target at slot level 1: per-turn row +0x6b4 / +0x6b6 / +0x6b8)
    damage percent; None when neither applies."""
    from pokeldn.sv.battle.engine.lift1 import _raid_id
    rules = lambda: m.u64(m.u64(o + 8) + 0x38)
    if m.u8(rules() + 0x499) >> 2 & 1:
        ident = m.vcall(t, 0x98) & M32
        if _raid_id(m, m.u64(m.u64(o + 0x10) + 0x310)) == ident:
            rec = m.u64(m.u64(o + 0x10) + 0x310)
            if m.u32(rec + 0x70) == 1:
                base = m.u16(rec + 0x2A)
                if not base:
                    return None
                return _tera_percent(m, user, mv, base, lambda: m.u16(rec + 0x2C), lambda: m.u16(rec + 0x2E))
    if not m.u8(rules() + 0x49C) >> 1 & 1:
        return None
    if _slot_level_raw(m, o, m.vcall(t, 0x98) & M32) != 1:
        return None
    r = m.u64(m.u64(o + 8) + 0x38)
    row = r + m.s(m.u64(m.u64(o + 0x10) + 0x210) + 0x28, 4) * 10
    base = m.u16(row + 0x6B4)
    if not base:
        return None
    return _tera_percent(m, user, mv, base, lambda: m.u16(row + 0x6B6), lambda: m.u16(row + 0x6B8))


def _slot_level_raw(m, o, ident):
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50), ident)
    return m.u32(p) if p else None


def _survival_cap_applies(m, o, t):
    if m.call(m.main + 0x1142E68, m.u64(o + 8), m.u64(o + 0x10), t) & 1:
        return False
    flags = m.u64(m.u64(m.u64(o + 8) + 0x38) + 0x498)
    if flags >> 0xC & 1:
        return True
    if flags >> 0x11 & 1:
        node = m.vcall(t + 0x28, 0)
        static = m.call(m.main + 0x2D1FD38)
        while node and node != static:
            node = m.u64(node)
        if not node:
            return False
        return not m.call(m.main + 0x1142E68, m.u64(o + 8), m.u64(o + 0x10), t) & 1 and bool(m.u8(t + 0x714))
    if flags >> 0x21 & 1:
        return m.u64(m.u64(m.u64(o + 0x10) + 0x210) + 0x28) <= 3
    return False


def _field_record(m, o):
    """Multi-battles: unless a kind-0xf record is queued, a 0x1820eb8 record {field battler id, kind 0xf,
    +0x4c = 2, +0x54 counter, +0x84 order key 0x113ecdc, +0x88 slot level} when the field battler holds
    condition 0x19."""
    rules = lambda: m.u64(m.u64(o + 8) + 0x38)
    if not m.u8(rules() + 0x49C) >> 1 & 1:
        return
    fb_of = lambda: m.call(m.main + 0xFA0028, m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x330) + 8) + 0x30), 1, 0)
    if not m.vcall(fb_of(), 0x510, 0x19) & 1 or not m.u8(rules() + 0x49C) >> 1 & 1:
        return
    q = m.u64(o + 0x48)
    for k in range(m.u8(q + 0x2420)):
        if m.u32(q + 0xC + 0x8C * k) == 0xF:
            return
    x = fb_of()
    with m.frame(0xB0) as sp:
        A, key = sp, sp + 0x90
        m.write(A, bytes(0x8C))
        m.put(A + 0x88, 1, 5); m.put(A + 0x84, 4, 0x5400000); m.put(A + 4, 4, 0xF); m.put(A + 0x4C, 1, 2)
        m.put(A, 4, m.vcall(x, 0x98) & M32)
        m.put(A + 0x88, 1, _slot_level_of(m, o, m.vcall(x, 0x98) & M32))
        m.put(A + 0x89, 2, 0)
        m.put(key + 8, 8, A); m.put(key + 0x10, 2, 0x103)
        m.call_void(m.main + 0x113ECDC, m.u64(m.u64(o + 0x78) + 0x120), key, key + 8)
        m.put(A + 0x84, 4, m.u32(key))
        cnt = m.u64(m.u64(o + 0x10) + 0x190)
        n = m.u32(cnt + 8)
        if n == 0:
            n = 1
            m.put(cnt + 8, 4, 1)
        m.put(A + 0x54, 4, n)
        m.put(cnt + 8, 4, m.u32(cnt + 8) + 1)
        m.call_void(m.main + 0x1820EB8, m.u64(o + 0x48), A)


@lifted(0x1589DD4)
def build_u8_node(m, table, key, key_pp, *_):
    """Node of the u32 -> u8 map (0x18 bytes from the allocator [table+0x38]): {next 0, hash key, key
    u32 **key_pp, value 0}; x8 gets {node, table+0x38, constructed 1}."""
    out = m.x8
    alloc = table + 0x38
    node = m.vcall(m.u64(alloc), 0x10, 0x18, 4)
    if not node:
        raise UnliftedCall("allocator out of memory")
    m.put(out, 8, node); m.put(out + 8, 8, alloc)
    m.call_void(m.main + 0x1589E60, alloc, node + 0x10, key_pp)
    m.put(out + 0x10, 1, 1)
    m.put(node, 8, 0); m.put(node + 8, 8, key)


@lifted(0x1589BC0)
def map_u8_slot(m, table, key_ptr, *_):
    """unordered_map<u32, u8>::operator[]: the value (node+0x14) of the u32 at key_ptr; a missing key gets
    a node from 0x1589dd4, growing the buckets through 0x1589eec past the max load."""
    import math
    import struct
    from pokeldn.sv.battle.engine.containers import find, _bucket
    key = m.u32(key_ptr)
    node = find(m, table, key, 4)
    if node:
        return node + 0x14
    n = m.u64(table + 8)
    with m.frame(0x20) as f:
        m.put(f, 8, key_ptr)
        m.x8 = f + 8
        m.call_void(m.main + 0x1589DD4, table, key, f)
        node = m.u64(f + 8)
    size1 = _f32(float(m.u64(table + 0x58) + 1))
    load = struct.unpack("<f", m.read(table + 0x60, 4))[0]
    if n == 0 or _f32(load * _f32(float(n))) < size1:
        grow = (n << 1) | int(n < 3 or not _pow2(n))
        need = math.ceil(_f32(size1 / load))
        m.call_void(m.main + 0x1589EEC, table, max(grow, need))
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


@lifted(0x1589A7C)
def note_fainted(m, p, ident, *_):
    """Append ident to the u32 list at p+8 (count byte +0x9e, at most 0x1e, flag byte p+0x80+i cleared),
    set its byte in the u32 -> u8 map at p+0x2f0, and count it (capped at 100) in the u16 at
    p+0x2e0 + 2 * 0x10e2da8([p+0x358] setup, ident)."""
    ident &= M32
    n = m.u8(p + 0x9E)
    if n <= 0x1D:
        m.put(p + 8 + 4 * n, 4, ident)
        m.put(p + 8 + n + 0x78, 1, 0)
        m.put(p + 0x9E, 1, m.u8(p + 0x9E) + 1)
    side = m.call(m.main + 0x10E2DA8, m.call(m.main + 0xE7E27C, m.u64(p + 0x358)), ident) & 0xFF
    with m.frame(0x10) as f:
        m.put(f, 4, ident)
        m.put(m.call(m.main + 0x1589BC0, p + 0x2F0, f), 1, 1)
    c = p + 0x2E0 + 2 * side
    v = m.u16(c)
    if v <= 0x63:
        m.put(c, 2, v + 1)


@lifted(0x1589990)
def battler_fainted(m, o, rec, ident, *_):
    """Record a faint: 0x1589a7c(rec, ident); when no party member of 0x114e498(o, rule value) is able,
    rank the side (0x1589b18); then the battler's vf 0x550(1, 1) and command 0x37 (ident, 1, 1)."""
    ident &= M32
    v = m.call(m.main + 0x1589A40, o, ident) & M32
    m.call_void(m.main + 0x1589A7C, rec, ident)
    lst = m.call(m.main + 0x114E498, o, v)
    if not m.call(m.main + 0xE7E454, lst) & 0xFF:
        m.call_void(m.main + 0x1589B18, m.call(m.main + 0x1589A74, m.call(m.main + 0x113DE68, o)), v)
    x = m.u64(o + 0x20)
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(m.u64(x + 0x20) + 0x10) + 0x30), ident)
    m.vcall_void(b, 0x550, 1, 1)
    return _tail(m, m.main + 0x119AFF0, m.u64(x + 0x18), 0x37, ident, 1, 1)


def _raid_class(m, b):
    """Whether battler b's class list (vf 0 of b+0x28) holds the static 0x46d3f08; refuses while the
    static is not built (0x2d1fd38 builds it)."""
    node = m.vcall(b + 0x28, 0)
    static = m.call(m.main + 0x2D1FD38)
    while node:
        if node == static:
            return True
        node = m.u64(node)
    return False


@lifted(0x1144DF8)
def battler_faints(m, o, out, rec, *_):
    """rec = {battler, byte announce, x}: when the battler is not yet marked fainted in [[o+0x10]+0x110]
    (0x287b7a4) and vf 0x200 says it is down, run the faint: 0x288dbd0, 0x14a07e0, 0x287f270, 0x1589990,
    the rule 0x49c bit 1 follow-up 0x11519ac, 0x1536f5c when announced, the raid boss steps (class
    0x46d3f08 with +0x714 set), command 0x94, the rule 0x499 bit 2 flag 8 (vf 0x550 + command 0x37), then
    0x1360214 .. 0x2836f48; out = 1 when it ran."""
    b = m.u64(rec)
    tbl = m.u64(m.u64(o + 0x10) + 0x110)
    ident = m.vcall(b, 0x98) & M32
    down = not m.call(m.main + 0x287B7A4, tbl, ident) & 1 and m.vcall(b, 0x200) & 1
    if down:
        if _raid_class(m, b) and m.u8(b + 0x714):
            for a in (0x28426A8, 0x115044C, 0x187FE48):
                _need(m, m.main + a)
        if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49C) >> 1 & 1:
            _need(m, m.main + 0x11519AC)
    m.put(out, 1, 0)
    if not down:
        return
    x = m.u64(rec + 0x10)
    m.call_void(m.main + 0x288DBD0, m.u64(o + 0x20), b, x)
    m.call_void(m.main + 0x14A07E0, o, m.u64(rec + 0x10))
    m.call_void(m.main + 0x287F270, o, m.u64(rec + 0x10), b)
    m.call_void(m.main + 0x1589990, o, tbl, ident)
    if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49C) >> 1 & 1:
        x24 = m.u64(o + 0x10)
        i2 = m.vcall(b, 0x98) & M32
        p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(x24 + 0x290) + 8) + 0x50), i2)
        if p and m.u32(p) == 1 and m.vcall(b, 0x200) & 1:
            m.call_void(m.main + 0x11519AC, m.u64(m.u64(o + 0x78) + 0x1F80))
    if m.u8(rec + 8):
        q = m.u64(o + 0x20)
        m.call_void(m.main + 0x1536F5C, q, m.vcall(b, 0x98) & M32, b, 0)
    if _raid_class(m, b) and m.u8(b + 0x714) and m.vcall(b, 0x588) & 1:
        with m.frame(0x20) as f:
            m.put(f + 0x10, 8, b); m.put(f + 0x18, 1, 0)
            m.call_void(m.main + 0x28426A8, m.u64(m.u64(o + 0x78) + 0x1480), f + 8, f + 0x10)
    w24 = m.vcall(b, 0x478) & M32
    m.vcall_void(b, 0x470)
    w25 = m.call(m.main + 0x15C0434, o, ident, w24) & 1
    m.call_void(m.main + 0x119AFF0, m.u64(m.u64(o + 0x20) + 0x18), 0x94, ident, 0)
    if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x499) >> 2 & 1:
        x26 = m.u64(o + 0x20)
        bb = m.call(m.main + 0xF21C94, m.u64(m.u64(m.u64(x26 + 0x20) + 0x10) + 0x30), ident)
        m.vcall_void(bb, 0x550, 8, 1)
        m.call_void(m.main + 0x119AFF0, m.u64(x26 + 0x18), 0x37, ident, 8, 1)
    m.call_void(m.main + 0x1360214, o, b)
    m.call_void(m.main + 0x2836D2C, m.u64(o + 0x38), ident)
    if _raid_class(m, b) and m.u8(b + 0x714):
        m.call_void(m.main + 0x115044C, m.u64(o + 0x20), m.vcall(b, 0x98) & M32)
        h = m.u16(b + 0x710)
        skip = False
        if h == 0x3F3:
            if m.u16(b + 0x718) == m.u16(b + 0x712):
                skip = True
            else:
                m.call_void(m.main + 0x187FE48, m.u64(o + 0x20), m.vcall(b, 0x98) & M32, m.u16(b + 0x712), 0)
                h = m.u16(b + 0x710)
        if not skip and h == 0x3FD and m.u16(b + 0x718) != m.u16(b + 0x712):
            m.call_void(m.main + 0x187FE48, m.u64(o + 0x20), m.vcall(b, 0x98) & M32, m.u16(b + 0x712), 0)
    m.call_void(m.main + 0x147AC20, m.u64(o + 0x20), ident)
    m.call_void(m.main + 0x1148894, m.u64(o + 0x48), ident)
    m.call_void(m.main + 0x149FDF4, o, b)
    m.call_void(m.main + 0x287F3D4, o, b)
    if w25:
        m.call_void(m.main + 0x1437580, m.u64(o + 0x20), w24)
    m.call_void(m.main + 0x287F878, o, ident)
    m.call_void(m.main + 0x162B7F0, o, ident, w24)
    m.call_void(m.main + 0x2836F48, m.u64(o + 0x38), ident)
    m.put(out, 1, 1)


def _static_built(m, guard_got):
    """A function-local static's guard (its address at main+guard_got); the engine never builds one."""
    if m.u8(m.u64(m.main + guard_got)) & 1 == 0:
        raise UnliftedCall(f"static guard [main+0x{guard_got:x}] not built")


def _in_class(m, obj, static_got):
    """Whether obj's class list (vf 0 of obj) holds the static whose address is at main+static_got."""
    node, static = m.vcall(obj, 0), m.u64(m.main + static_got)
    while node:
        if node == static:
            return True
        node = m.u64(node)
    return False


@lifted(0x149FE94)
def friendship_event(m, s, b, close, *_):
    """Outside raids (rule 0x499 bit 2) and battles of kind [s+0x30] > 1: 0x13801c0 with the hashed event
    name 0x91878d2e67dac9bc (close in level) or 0xed853956cb8c2ca7."""
    if m.u8(m.u64(s + 0x38) + 0x499) >> 2 & 1 or m.u32(m.u64(s + 0x38) + 0x30) > 1:
        return s
    key = 0x91878D2E67DAC9BC if close & 1 else 0xED853956CB8C2CA7
    return _tail(m, m.main + 0x13801C0, s, b, key)


@lifted(0x13801C0)
def friendship_both_sides(m, s, b, key, *_):
    """0x1380220 for b's id on the members [s+0x170] and [s+0x150], with {&key, key} on the stack."""
    with m.frame(0x10) as f:
        m.put(f, 8, f + 8); m.put(f + 8, 8, key)
        ident = m.vcall(b, 0x98) & M32
        m.call_void(m.main + 0x1380220, f, m.u64(s + 0x170), ident)
        return _tail(m, m.main + 0x1380220, f, m.u64(s + 0x150), ident)


@lifted(0x1380220)
def friendship_member(m, ctx, side, ident, *_):
    """When member `ident` of [side+0x30] (0xf79790) is of the class 0x46d3f08: 0x13802f4 on its stored
    Pokemon (0x1380644) with the key **ctx."""
    r = m.call(m.main + 0xF79790, m.u64(side + 0x30), ident & M32)
    lst = m.vcall(r + 0x28, 0)
    static = m.call(m.main + 0x2D1FD38)
    while lst:
        if lst == static:
            pp = m.call(m.main + 0x1380644, r)
            return _tail(m, m.main + 0x13802F4, pp, m.u64(m.u64(ctx)))
        lst = m.u64(lst)
    return 0


@lifted(0x1380644)
def stored_pokemon(m, r, *_):
    """[[r+0x48]+0x48] when [r+0x48]+0x28 is of the class at [main+0x46dcd58], else 0."""
    x = m.u64(r + 0x48) + 0x28
    node = m.vcall(x, 0)
    _static_built(m, 0x46DCD50)
    static = m.u64(m.main + 0x46DCD58)
    while node:
        if node == static:
            return m.u64(x + 0x20)
        node = m.u64(node)
    return 0


@lifted(0x13802F4)
def friendship_apply(m, pp, key, *_):
    """0x1380380 on the friendship table (the static at [main+0x46d78e0], also stored at main+0x4742260)."""
    _static_built(m, 0x46D78D8)
    t = m.u64(m.u64(m.main + 0x46D78E0))
    m.put(m.main + 0x4742260, 8, t)
    return _tail(m, m.main + 0x1380380, t, pp, key)


@lifted(0x1380380)
def friendship_change(m, t, pp, key, *_):
    """The u64-keyed map at t+0x28 maps an event name to three s32 deltas (friendship below 100, below
    160, above): unless the record is an egg or bad, friendship += 0x1380500's delta, clamped to 0..255
    (0xdf7530), then the stats are recomputed (0xe13b9c(pp, 1))."""
    from pokeldn.sv.battle.engine.containers import find
    node = find(m, t + 0x28, key & M64, 8)
    if not node:
        return
    acc = m.u64(pp + 0x70)
    if m.call(m.main + 0xBF4CFC, acc) & 1:
        return
    if m.u16(m.u64(acc + 0x10) + 4) >> 2 & 1:
        return
    cur = m.call(m.main + 0x121C054, acc) & M32
    d = m.call(m.main + 0x1380500, cur, pp, node + 0x18)
    v = _s32(d + cur)
    v = min(max(v, 0), 0xFF)
    m.call_void(m.main + 0xDF7530, m.u64(pp + 0x70), v)
    return _tail(m, m.main + 0xE13B9C, pp, 1)


@lifted(0x1380500)
def friendship_delta(m, _x, pp, deltas, *_):
    """deltas[0 / 1 / 2] by friendship (< 100, < 160, else); a gain gets +1 in a Luxury Ball (0xb) and
    x1.5 (float32, truncated) when the item lookup at [[main+0x46d90c8]]+0x250 answers 0x5c for the held
    item."""
    import struct
    acc = m.u64(pp + 0x70)
    f = _s32(m.call(m.main + 0x121C054, acc))
    v = _s32(m.u32(deltas + 4 * (0 if f < 0x64 else 1 if f < 0xA0 else 2)))
    if v < 1:
        return v & M32
    ball = m.call(m.main + 0x1300BA8, m.u64(pp + 0x70)) & 0xFF
    bonus = int((ball - 1) & 0xFF < 0x1A and ball == 0xB)
    item = m.call(m.main + 0xD974E0, m.u64(pp + 0x70)) & 0xFFFF
    _static_built(m, 0x46D89B0)
    g = m.u64(m.u64(m.main + 0x46D90C8))
    fn = m.u64(g + 0x250)
    if fn and fn - m.main not in FUNCTIONS:
        raise UnliftedCall(f"main+0x{fn - m.main:x}")
    m.put(m.u64(m.main + 0x46D89C0), 8, m.u64(m.u64(m.main + 0x46D89B8)))
    v = (v + bonus) & M32
    if not fn:
        return v
    with m.frame(0x10) as k:
        m.put(k, 2, item)
        r = m.call(fn, g + 0x270, k)
    if r & 0xFFFF == 0x5C:
        x = struct.unpack("<f", struct.pack("<f", float(_s32(v))))[0] * 1.5
        return int(_f32(x)) & M32
    return v


@lifted(0x1300BA8)
def ball(m, acc, *_):
    """Byte +0x2c of logical block 3 (stand-in 0x4742380 for a bad record)."""
    from pokeldn.sv.battle.engine.pokemon import _getter
    return _getter(3, 0x2C, 1, 0, 0x4742380, False)(m, acc)


@lifted(0xDF7530)
def set_friendship(m, acc, v, *_):
    """The current handler's friendship: block 2 +0x20 when block 2 +0x1c is set, else block 3 +0x1a
    (stand-ins 0x4742480 / 0x47424d0 for a bad record, chosen by the read stand-in's +0x1c at
    0x474234c)."""
    from pokeldn.sv.battle.engine.pokemon import access, block
    def write(core):
        if m.u8(core + 4) >> 2 & 1:
            if m.u8(m.main + 0x474234C):
                m.put(m.main + 0x4742480 + 0x20, 1, v)
            else:
                m.put(m.main + 0x47424D0 + 0x1A, 1, v)
        elif m.u8(block(m, core, 2) + 0x1C):
            m.put(block(m, core, 2) + 0x20, 1, v)
        else:
            m.put(block(m, core, 3) + 0x1A, 1, v)
        return 0
    access(m, acc, write)
    return acc + 0x28


def _standing_by_speed(m, o, lst, pl, out):
    """Clear lst, fill it with the standing members (0x1144704 on [[o+0x78]+0x1280]) and sort them by
    speed (0x1143e3c on that object's [[+0x78]+0x17e0])."""
    _clear_members(m, lst)
    x = m.u64(m.u64(o + 0x78) + 0x1280)
    m.call_void(m.main + 0x1144704, x, lst)
    m.put(pl, 8, lst)
    m.call_void(m.main + 0x1143E3C, m.u64(m.u64(x + 0x78) + 0x17E0), out, pl)


def _faint_one(m, o, b, kind, rec, out):
    """0x1144bd8([o+0x38], b's id, kind), then 0x1144df8([[o+0x78]+0x400]) on {b, announce 1, 0}."""
    m.call_void(m.main + 0x1144BD8, m.u64(o + 0x38), m.vcall(b, 0x98) & M32, kind)
    m.put(rec, 8, b); m.put(rec + 8, 1, 1); m.put(rec + 0x10, 8, 0)
    m.call_void(m.main + 0x1144DF8, m.u64(m.u64(o + 0x78) + 0x400), out, rec)


@lifted(0x1145690)
def raid_faints(m, o, kind_ptr, *_):
    """The raid case of 0x11449f4: each standing member, fastest first, that is one of the raid
    record's entries ([o+0x48] +8, stride 0x8c, count byte +0x2420) faints through 0x1144df8."""
    with m.frame(0xE0) as f:
        lst, pl, rec, out = f, f + 0xB0, f + 0xB8, f + 0xD0
        _standing_by_speed(m, o, lst, pl, out)
        r = m.call(m.main + 0x1149340, o)
        n = m.u8(lst + 0xA6)
        m.put(lst + 0xA8, 1, 0)
        if n == 0:
            return
        b = m.u64(lst)
        m.put(lst + 0xA8, 1, 1)
        while b:
            ident = m.vcall(b, 0x98) & M32
            if any(m.u32(r + 8 + 0x8C * k) == ident for k in range(m.u8(r + 0x2420))):
                _faint_one(m, o, b, m.u16(kind_ptr), rec, out)
            i = m.u8(lst + 0xA8)
            if i >= m.u8(lst + 0xA6):
                return
            m.put(lst + 0xA8, 1, i + 1)
            b = m.u64(lst + 8 * i)


@lifted(0x11449F4)
def faint_pass(m, o, out, kind_ptr, *_):
    """After an action of kind u16 [kind_ptr]: 0x1144bd8 with id 0, then (raid kind 0xf4: 0x1145690)
    every standing member, fastest first, goes through 0x1144df8 until the battle ends ([[o+0x40]+0x28]
    reads 8, or 0x114a808 and 0x13603fc both hold); out = 0x113fa64's answer."""
    m.call_void(m.main + 0x1144BD8, m.u64(o + 0x38), 0, m.u16(kind_ptr))
    if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x499) >> 2 & 1 and m.u16(kind_ptr) == 0xF4:
        return _tail(m, m.main + 0x1145690, o, kind_ptr)

    def over():
        return m.call(m.main + 0x114A808, o) & 1 and m.call(m.main + 0x13603FC, o) & 1

    with m.frame(0xE0) as f:
        lst, pl, rec, res = f, f + 0xB0, f + 0xB8, f + 0xD0
        if over():
            m.call_void(m.main + 0x113FA64, m.u64(m.u64(o + 0x78) + 0x2A0), pl, lst)
            m.put(out, 1, m.u8(pl))
            return
        _standing_by_speed(m, o, lst, pl, res)
        n = m.u8(lst + 0xA6)
        m.put(lst + 0xA8, 1, 0)
        b = m.u64(lst) if n else 0
        if b:
            m.put(lst + 0xA8, 1, 1)
        while b:
            _faint_one(m, o, b, m.u16(kind_ptr), rec, res)
            if m.u8(m.u64(m.u64(o + 0x40) + 0x28)) == 8 or over():
                break
            i = m.u8(lst + 0xA8)
            if i >= m.u8(lst + 0xA6):
                break
            m.put(lst + 0xA8, 1, i + 1)
            b = m.u64(lst + 8 * i)
        m.call_void(m.main + 0x113FA64, m.u64(m.u64(o + 0x78) + 0x2A0), res, rec)
        m.put(out, 1, m.u8(res))


@lifted(0x153379C)
def faint_after_move(m, o, _x, r, *_):
    """r = {targets, {_, u16 move at +2}, move record, user, u8 count}: after 0x153391c's check (true:
    0x1536f20 on the user), each target faints through 0x1144df8 with announce = record byte +5 and
    x = {user, move}, then the user with announce 1."""
    x22 = m.u64(m.u64(o + 0x78) + 0x260)
    user = m.u64(r + 0x18)
    if m.call(m.main + 0x153391C, m.u64(x22 + 0x38), user, m.u64(r + 8)) & 1:
        m.call_void(m.main + 0x1536F20, x22, user)
    with m.frame(0x40) as f:
        rec, s, out = f, f + 0x18, f + 0x28
        n = m.u8(r + 0x20)
        if n:
            announce = m.u8(m.u64(r + 0x10) + 5)
            i = 0
            while i < n:
                m.put(s, 8, m.u64(r + 0x18)); m.put(s + 8, 2, m.u16(m.u64(r + 8) + 2))
                m.put(rec, 8, m.u64(m.u64(r) + 8 * i)); m.put(rec + 8, 1, announce); m.put(rec + 0x10, 8, s)
                m.call_void(m.main + 0x1144DF8, m.u64(m.u64(o + 0x78) + 0x400), out, rec)
                i += 1
                n = m.u8(r + 0x20)
        m.put(rec, 8, m.u64(r + 0x18)); m.put(rec + 8, 1, 1); m.put(rec + 0x10, 8, 0)
        m.call_void(m.main + 0x1144DF8, m.u64(m.u64(o + 0x78) + 0x400), s, rec)


@lifted(0x2888690)
def faint_battler(m, o, b, *_):
    """0x1144df8(0x114389c([o+0x78])) on {b, announce 1, 0}."""
    with m.frame(0x20) as f:
        m.put(f + 8, 8, b); m.put(f + 0x10, 1, 1); m.put(f + 0x18, 8, 0)
        m.call_void(m.main + 0x1144DF8, m.call(m.main + 0x114389C, m.u64(o + 0x78)), f, f + 8)


@lifted(0x1536F20)
def faint_battler_of(m, o, b, *_):
    """0x1144df8(0x114389c(0x1361214(o))) on {b, announce 1, 0}."""
    with m.frame(0x20) as f:
        m.put(f + 8, 8, b); m.put(f + 0x10, 1, 1); m.put(f + 0x18, 8, 0)
        x = m.call(m.main + 0x114389C, m.call(m.main + 0x1361214, o))
        m.call_void(m.main + 0x1144DF8, x, f, f + 8)


@lifted(0x1143694)
def end_of_turn_damage(m, o, *_):
    """For each member of 0x11438b4's list that is not down (vf 0x200) and has neither condition 5 nor 4
    (vf 0x4d0): w = the field value 0x116ec0c (per battler through 0x116ee6c), the amount 0x1145270([o+0x38],
    b, w, a) applied through 0x1150d88 when nonzero, then 0x1144df8 on {b, 1, 0}; stops when
    [[[o+0x40]+0x28]] reads 8. a = max(1, vf 0x140 >> 4 & 0xfff) when w is 4 and none of the vf 0x300
    conditions 5, 8, 4 holds, else 0."""
    with m.frame(0xD0) as f:
        lst, rec, out = f, f + 0xB0, f + 0xC8
        m.call_void(m.main + 0x1143D84, lst)
        m.call_void(m.main + 0x11438B4, o, lst)
        m.call_void(m.main + 0x1143D7C, lst)
        while True:
            i = m.u8(lst + 0xA8)
            if i >= m.u8(lst + 0xA6):
                return
            m.put(lst + 0xA8, 1, i + 1)
            b = m.u64(lst + 8 * i)
            if not b:
                return
            if not (m.vcall(b, 0x200) & 1 or m.vcall(b, 0x4D0, 5) & 1 or m.vcall(b, 0x4D0, 4) & 1):
                ident = m.vcall(b, 0x98) & M32
                w = m.u64(m.u64(m.u64(o + 0x78) + 0xC80) + 0x38)
                weather = m.call(m.main + 0x116EC0C, w) & M32
                if ident:
                    weather = m.call(m.main + 0x116EE6C, w, ident, weather) & M32
                amount = 0
                if weather & 0xFF == 4 and not (m.vcall(b, 0x300, 5) & 1 or m.vcall(b, 0x300, 8) & 1
                                                 or m.vcall(b, 0x300, 4) & 1):
                    v = m.vcall(b, 0x140) & M32
                    amount = (v >> 4 & 0xFFF) if v & 0xFFFF >= 0x10 else 1
                r = m.call(m.main + 0x1145270, m.u64(o + 0x38), b, weather, amount) & M32
                if r:
                    x = m.call(m.main + 0x134ED30, m.u64(m.call(m.main + 0x1482534, o) + 0x70))
                    m.call_void(m.main + 0x1150D88, o, b, weather, r, x & M32)
                m.put(rec, 8, b); m.put(rec + 8, 1, 1); m.put(rec + 0x10, 8, 0)
                m.call_void(m.main + 0x1144DF8, m.call(m.main + 0x114389C, m.u64(o + 0x78)), out, rec)
            if m.call(m.main + 0x11438A4, m.call(m.main + 0x113DE70, m.call(m.main + 0x113DE68, o)), 8) & 1:
                return


@lifted(0x134ED30)
def field_14(m, o, *_):
    return m.u32(o + 0x14)


@lifted(0x114AF54)
def apply_damage(m, o, out, r, *_):
    """r = {battler, u32 amount, u8 +0xc, u32 +0x10, source +0x18, u8 faint check +0x20}: when amount is
    nonzero, 0x1152ae8 / 0x114fcd8 (minus amount) / vf 0x508(2) / 0x114b0ac (when 0x17ce3ac holds for the
    source) / 0x114b5dc / 0x1152da8, the rule 0x49c bit 1 follow-up 0x11519ac, 0x2888690 when +0x20 is
    set; out = 1."""
    rule = m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49C) >> 1 & 1
    if rule and m.u32(r + 8):
        _need(m, m.main + 0x1149510)
        _need(m, m.main + 0x11519AC)
    m.put(out, 1, 0)
    if m.u32(r + 8) == 0:
        return
    m.call_void(m.main + 0x1152AE8, m.call(m.main + 0x1146E90, o), m.u64(r), m.u32(r + 8))
    m.call_void(m.main + 0x114FCD8, m.u64(o + 0x20), m.u64(r), -m.u32(r + 8) & M32, m.u8(r + 0xC),
                m.u32(r + 0x10), 1)
    m.vcall_void(m.u64(r), 0x508, 2)
    src = m.u64(r + 0x18)
    if src and m.call(m.main + 0x17CE3AC, src) & 1:
        q = m.u64(o + 0x20)
        m.call_void(m.main + 0x114B0AC, q, m.vcall(m.u64(r), 0x98) & M32, m.u64(r + 0x18))
    m.call_void(m.main + 0x114B5DC, o, m.u64(r))
    m.call_void(m.main + 0x1152DA8, m.call(m.main + 0x1146E90, o), m.u64(r), m.u32(r + 8))
    if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49C) >> 1 & 1:
        x22 = m.u64(o + 0x10)
        ident = m.vcall(m.u64(r), 0x98) & M32
        p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(x22 + 0x290) + 8) + 0x50), ident)
        if p and m.u32(p) == 1 and m.call(m.main + 0x1149510, m.u64(m.u64(o + 0x10) + 0x330)) & 1:
            m.call_void(m.main + 0x11519AC, m.u64(m.u64(o + 0x78) + 0x1F80))
    if m.u8(r + 0x20):
        m.call_void(m.main + 0x2888690, o, m.u64(r))
    m.put(out, 1, 1)


@lifted(0x1142FD0)
def end_of_turn_residual(m, o, out, *_):
    """out = 0; when 0x1143060 (on 0x1143584(o)) answers w, tail 0x1150144(o, w); else 0x1143694 and out
    = 0x1143030(o) & 1."""
    q = m.call(m.main + 0x1143584, o)
    t = m.u64(m.u64(m.u64(q + 0x20) + 0x10) + 0x70)
    if m.u8(t + 0x19) and m.u32(t + 8) != 0xFF and m.u32(t + 8) <= (m.u32(t + 0x10) + 1) & M32:
        _need(m, m.main + 0x1150144)        # the timer 0x114309c expires
    m.put(out, 1, 0)
    w = m.call(m.main + 0x1143060, q)
    if w & 0xFF:
        return _tail(m, m.main + 0x1150144, o, w & M32)
    m.call_void(m.main + 0x1143694, o)
    m.put(out, 1, m.call(m.main + 0x1143030, o) & 1)


@lifted(0x1142F98)
def end_of_turn_residual_of(m, o, *_):
    """0x1142fd0 on 0x1142fc8([o+0x78]); its out byte."""
    with m.frame(0x10) as f:
        m.call_void(m.main + 0x1142FD0, m.call(m.main + 0x1142FC8, m.u64(o + 0x78)), f, f + 8)
        return m.u8(f)


@lifted(0x1532FE4)
def faint_user_if(m, o, user, x, *_):
    """When 0x153391c([[[o+0x78]+0x260]+0x38], user, x) holds: 0x1536f20 on the user."""
    t = m.u64(m.u64(o + 0x78) + 0x260)
    r = m.call(m.main + 0x153391C, m.u64(t + 0x38), user, x)
    if not r & 1:
        return r
    return _tail(m, m.main + 0x1536F20, t, user)


@lifted(0x1832F80)
def report_ca_text(m, q, a, text, b, v, *_):
    """Command 0xca (a, text, b, v) through 0x157ebc0."""
    return _tail(m, m.main + 0x157EBC0, m.u64(q + 0x18), 0xCA, a & M32, text & 0xFFFF, b & M32, v & M32,
                 0xFFFF0000)


@lifted(0x1832F0C)
def text_2cf(m, o, b, *_):
    """Text 0x2cf naming b (command 0xca with 0x1589a40's value), then command 0xb3 (b's id, 0)."""
    ident = m.vcall(b, 0x98) & M32
    v = m.call(m.main + 0x1589A40, o, ident)
    m.call_void(m.main + 0x1832F80, m.call(m.main + 0x1143584, o), ident, 0x2CF, ident, v & 0xFF)
    return _tail(m, m.main + 0x1832FA4, m.call(m.main + 0x1143584, o), ident, 0)


@lifted(0x28810A0)
def text_ab(m, o, b, *_):
    """Command 0xcb (b's id, text 0xab, b's id) through 0x157eba0."""
    ident = m.vcall(b, 0x98) & M32
    return _tail(m, m.main + 0x157EBA0, m.call(m.main + 0x1143584, o), ident, 0xAB, ident)


@lifted(0x2833BB4)
def event_98(m, o, b, *_):
    """Event 0x98 with b's id (2)."""
    _event(m, o, 0x98, ((2, lambda: m.vcall(b, 0x98), 4, 0x18),))


_HIT_EFFECT = {1: 0x28810A0, 5: 0x1832F0C, 6: 0x1832F0C}


@lifted(0x15327C4)
def apply_hits(m, o, out, p, *_):
    """p = {user, +8, results R, +0x18 move, +0x20, u8 +0x28, +0x30}; R = {u8 n0, u8 n1, entries of 0xc
    bytes from +4: u16 damage, u32 target id +4, u8 +8, u8 effect +9, flags +0xa (bit 3 skip, bits 0..1
    critical)}. Runs 0x153354c and 0x15343a0, gathers the targets not skipped into A (battlers +0, u16
    +0x30, u8 +0x3c, critical +0x42, effect +0x48), then 0x15368cc, 0x1533cc8, 0x1535450, each effect
    (1: 0x28810a0, 5 / 6: 0x1832f0c, else 0x2833bb4), 0x1532dec, 0x1533284, 0x16d9d10 per target and
    0x153379c; with no target, 0x1532dec, 0x1533284 and 0x1532fe4. *out (u32) = the summed damage after
    0x1533ef0."""
    m.put(out, 4, 0)
    R = m.u64(p + 0x10)
    if m.u8(R) + m.u8(R + 1) == 0:
        return
    t = m.u64(o + 0x78)
    pos = m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), m.vcall(m.u64(p), 0x98) & M32)
    with m.frame(0x100) as f:
        A, S, res = f, f + 0xA0, f + 0xD0          # S mirrors the game's x29-0x38 block
        P = [m.u64(p + 8 * k) for k in range(7)]
        for k, v in enumerate((P[2], P[1], P[3], P[0], P[6])):
            m.put(A + 8 * k, 8, v)
        m.call_void(m.main + 0x153354C, m.u64(t + 0x8E0), S, A)
        for k, v in enumerate((m.u64(p), m.u64(p + 0x20), m.u64(p + 0x10), m.u64(p + 0x18))):
            m.put(A + 8 * k, 8, v)
        m.call_void(m.main + 0x15343A0, m.u64(t + 0x540), S, A)
        R = m.u64(p + 0x10)
        c = 0
        if m.u8(R) + m.u8(R + 1):
            x26 = m.u64(t + 0x420)
            k = 0
            while k < m.u8(R) + m.u8(R + 1):
                e = R + 4 + 0xC * k
                fl = m.u8(e + 0xA)
                if not fl >> 3 & 1:
                    m.put(A + 8 * c, 8, m.call(m.main + 0xF21C94, m.u64(m.u64(x26 + 0x10) + 0x30), m.u32(e + 4)))
                    m.put(A + 0x30 + 2 * c, 2, m.u16(e))
                    m.put(A + 0x3C + c, 1, m.u8(e + 8))
                    m.put(A + 0x48 + c, 1, m.u8(e + 9))
                    m.put(A + 0x42 + c, 1, (2 if fl & 2 else 1) if fl & 1 else 0)
                    c += 1
                k += 1
        if c == 0:
            m.put(S, 8, A); m.put(S + 8, 8, m.u64(p + 8)); m.put(S + 0x10, 8, m.u64(p + 0x18))
            m.put(S + 0x18, 8, m.u64(p)); m.put(S + 0x20, 1, 0)
            m.call_void(m.main + 0x1532DEC, m.u64(m.u64(o + 0x78) + 0x1A40), res, S)
            m.call_void(m.main + 0x1533284, o, m.u64(p), m.u64(p + 0x18))
            R = m.u64(p + 0x10)
            if m.u8(R) + m.u8(R + 1):
                m.call_void(m.main + 0x1532FE4, o, m.u64(p), m.u64(p + 0x18))
        else:
            m.call_void(m.main + 0x15368CC, m.u64(o + 0x20), m.u64(p), m.u64(p + 0x18), c, A, A + 0x3C, A + 0x30)
            m.put(S, 8, A); m.put(S + 8, 8, m.u64(p + 0x18)); m.put(S + 0x10, 8, m.u64(p))
            m.put(S + 0x18, 8, m.u64(p + 0x20)); m.put(S + 0x20, 1, c); m.put(S + 0x21, 1, m.u8(p + 0x28))
            m.call_void(m.main + 0x1533CC8, m.u64(m.u64(o + 0x78) + 0x14A0), res, S)
            m.put(S, 8, m.u64(p)); m.put(S + 0x10, 8, m.u64(p + 0x18)); m.put(S + 0x18, 1, c)
            m.put(S + 8, 1, pos); m.put(S + 0x20, 8, A); m.put(S + 0x28, 8, m.u64(p + 0x30))
            m.call_void(m.main + 0x1535450, m.u64(m.u64(o + 0x78) + 0x15C0), res, S)
            for i in range(c):
                kind = m.u8(A + 0x48 + i)
                if kind:
                    x = m.u64(m.u64(o + 0x78) + 0x1340)
                    b = m.u64(A + 8 * i)
                    if kind in _HIT_EFFECT:
                        m.call_void(m.main + _HIT_EFFECT[kind], x, b, kind)
                    else:
                        m.call_void(m.main + 0x2833BB4, m.u64(x + 0x38), b, kind)
            m.put(S, 8, A); m.put(S + 8, 8, m.u64(p + 8)); m.put(S + 0x10, 8, m.u64(p + 0x18))
            m.put(S + 0x18, 8, m.u64(p)); m.put(S + 0x20, 1, c)
            m.call_void(m.main + 0x1532DEC, m.u64(m.u64(o + 0x78) + 0x1A40), res, S)
            m.call_void(m.main + 0x1533284, o, m.u64(p), m.u64(p + 0x18))
            for i in range(max(c, 1)):
                m.call_void(m.main + 0x16D9D10, m.u64(m.u64(m.u64(o + 0x78) + 0x1A60) + 0x38), m.u64(p),
                            m.u64(A + 8 * i), m.u64(p + 0x18), m.u8(A + 0x3C + i), m.u16(A + 0x30 + 2 * i),
                            int(m.u8(A + 0x42 + i) != 0), 0)
            m.put(S, 8, A); m.put(S + 8, 8, m.u64(p + 0x18)); m.put(S + 0x10, 8, m.u64(p + 0x20))
            m.put(S + 0x18, 8, m.u64(p)); m.put(S + 0x20, 1, c)
            m.call_void(m.main + 0x153379C, m.u64(m.u64(o + 0x78) + 0x280), res, S)
    R = m.u64(p + 0x10)
    n = m.u8(R) + m.u8(R + 1)
    total = sum(m.u16(R + 4 + 0xC * k) for k in range(max(n, 1))) & M32 if n else 0
    m.call_void(m.main + 0x1533EF0, m.u64(o + 0x38), m.u64(p), m.u64(p + 0x18), total)
    m.put(out, 4, total)


@lifted(0x176989C)
def residual_hit(m, o, b, amount, *_):
    """A message (head 0x7f, b's id) and 0x114af54 (on 0x1807cbc(0x1361214(o))) with {b, amount, 4, b's
    id, message, faint check 1}; when it applied, 0x2881c58 (b's id, 4, amount)."""
    with m.frame(0x60) as f:
        msg, out, r = f, f + 0x28, f + 0x30
        m.call_void(m.main + 0x1146154, msg)
        m.call_void(m.main + 0x2843244, msg, 2, 0x7F)
        m.call_void(m.main + 0x284325C, msg, m.vcall(b, 0x98) & M32)
        m.put(r, 8, b); m.put(r + 8, 4, amount); m.put(r + 0xC, 1, 4)
        m.put(r + 0x10, 4, m.vcall(b, 0x98)); m.put(r + 0x18, 8, msg); m.put(r + 0x20, 1, 1)
        m.call_void(m.main + 0x114AF54, m.call(m.main + 0x1807CBC, m.call(m.main + 0x1361214, o)), out, r)
        if m.u8(out):
            q = m.call(m.main + 0x1143584, o)
            m.call_void(m.main + 0x2881C58, q, m.vcall(b, 0x98) & M32, 4, amount & M32)


# The condition kinds 0x114a094 walks after its first kind 0x24 (0x3c69dd0, 45 u16).
_EOT_KINDS = (0x24, 0x15, 0x12, 0x5, 0x4, 0x9, 0xA, 0x8, 0x2E, 0x2B, 0x30, 0xB, 0xC, 0x17, 0xD, 0x1F, 0x21,
              0xF, 0x13, 0x1D, 0x1E, 0x26, 0x25, 0x27, 0x28, 0x29, 0x18, 0x2D, 0xE, 0x14, 0x1, 0x2, 0x3, 0x7,
              0x6, 0x10, 0x11, 0x16, 0x19, 0x1A, 0x1B, 0x1C, 0x20, 0x22, 0x23)
# Kinds 4 / 5 / 9 / 10 of 0x114a094: (text for 0x114ade8, byte +0xc of the hit, u16 head of its message).
_EOT_DAMAGE = {4: (0x2C, 0x27, 0x58), 5: (0x2B, 0x26, 0x52), 9: (0x44, 0x28, 0x6D), 10: (0x43, 0x29, 0x156)}
# Follow-ups by kind after the damage step (jump table 0x3c6a641 and the compares after it).
_EOT_AFTER = {0x12: 0x114C778, 0x14: 0x114B30C, 0x15: 0x114B3A8, 0x17: 0x114B514, 8: 0x114FE90,
              0x24: 0x114B454, 0x2B: 0x114C9E4}
# Kinds whose condition ended with a message (0x114a970): jump table 0x3c6a633.
_EOT_ENDED = {0xE: (0x114AE50, True), 0xF: (0x114ABE8, False), 0x13: (0x114AB94, False),
              0x14: (0x114AC3C, True)}


def _eot_kind_30(m, o, b, x29):
    """Kind 0x30 of 0x114a094: when vf 0x280(5) is positive, messages 0x1150748 and 0x1151258 naming the
    condition's source (vf 0x240(0x30)) and b."""
    if m.vcall(b, 0x200) & 1:
        return
    ident = m.vcall(b, 0x98) & M32
    pair = m.vcall(b, 0x240, 0x30)
    x0, x1 = (pair[0], pair[1]) if isinstance(pair, tuple) else (pair, 0)
    Z, W = x29 - 0x30, x29 - 0xB0
    m.put(Z, 8, x0); m.put(Z + 8, 8, x1)
    src = x0 & M32
    m.put(x29 - 0x38, 1, 0)
    if _s32(m.vcall(b, 0x280, 5)) < 1:
        return
    m.write(W + 4, bytes(0x2C))
    m.put(W, 4, 0x0A0A0095)
    m.put(W, 2, 0x96 if m.call(m.main + 0x114BD20, Z) & 1 else 0x95)
    pos = m.u64(m.u64(o + 0x10) + 0xF0)
    m.put(W + 2, 1, m.call(m.main + 0x1381420, pos, src))
    m.put(W + 3, 1, m.call(m.main + 0x1381420, pos, ident))
    m.call_void(m.main + 0x1150748, m.u64(m.u64(o + 0x78) + 0x9A0), x29 - 0x40, W)
    m.put(W + 0x38, 2, 0); m.put(W + 0x3C, 4, 0); m.put(W + 0x40, 1, 0)
    m.put(W + 0x42, 8, 0x0102000001000000)
    m.write(W + 0xC, bytes(0x28)); m.write(W + 0x4C, bytes(0x20))
    m.put(W + 4, 1, 1); m.put(W + 0x34, 2, 0xFF05); m.put(W + 0x6C, 4, 0)
    m.put(W, 4, src); m.put(W + 8, 4, ident); m.put(W + 0x36, 1, 0)
    m.call_void(m.main + 0x1151258, m.u64(m.u64(o + 0x78) + 0xE20), x29 - 0x38, W)


@lifted(0x114A094)
def end_of_turn_conditions(m, o, out, *_):
    """For each condition kind (0x24, then 0x3c69dd0's list) and each member of 0x114a904's list not down
    and not in position 10: vf 0x570 of the party member ticks the condition (command 0x19 (id, kind));
    one that ended with a message (0x114a970) is reported (0x114aab0) and gets its kind's follow-up;
    otherwise the amount vf 0x428 checked by 0x114b630 and 0x114b9a4 is applied through 0x114af54 (with
    the kind's text and message head), then the kind's after-step. Stops when [[[o+0x40]+0x28]] reads 8,
    or after the list once 0x114a808 and 0x13603fc both hold; out = 0x114a934(o) & 1."""
    m.put(out, 1, 0)
    with m.frame(0x200) as sp:
        x29 = sp + 0x190
        lst, X, Y, V, Z, res = sp + 0x18, x29 - 0xC0, x29 - 0xC4, x29 - 0xB0, x29 - 0x30, x29 - 0x38
        m.call_void(m.main + 0x1143D84, lst)
        m.call_void(m.main + 0x114A904, o, lst)
        k = 0
        while True:
            kind = _EOT_KINDS[k]
            n = m.u8(lst + 0xA6)
            m.put(lst + 0xA8, 1, 0)
            while n:
                i = m.u8(lst + 0xA8)
                m.put(lst + 0xA8, 1, i + 1)
                b = m.u64(lst + 8 * i)
                if not b:
                    break
                _eot_member(m, o, b, kind, X, Y, V, Z, res)
                if m.u8(m.u64(m.u64(o + 0x40) + 0x28)) == 8 or m.u8(lst + 0xA8) >= m.u8(lst + 0xA6):
                    break
            k += 1
            if m.call(m.main + 0x114A808, o) & 1:
                if m.call(m.main + 0x13603FC, o) & 1 or k > 0x2C:
                    break
            elif k > 0x2C:
                break
        m.put(out, 1, m.call(m.main + 0x114A934, o) & 1)


def _eot_member(m, o, b, kind, X, Y, V, Z, res):
    if m.vcall(b, 0x200) & 1:
        return
    if m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), m.vcall(b, 0x98) & M32) & 0xFF == 0xA:
        return
    m.put(X + 8, 8, 0); m.put(X, 4, 0)
    q = m.u64(o + 0x20)
    ident = m.vcall(b, 0x98) & M32
    pm = m.call(m.main + 0xF21C94, m.u64(m.u64(m.u64(q + 0x20) + 0x10) + 0x30), ident)
    ticked = m.vcall(pm, 0x570, kind, X, Y) & 1
    m.call_void(m.main + 0x119AFF0, m.u64(q + 0x18), 0x19, ident, kind)
    if not ticked:
        return
    if m.u8(Y):
        m.write(Z, bytes(0x24))
        if m.call(m.main + 0x114A970, kind, X, m.vcall(b, 0x98) & M32, 0, Z) & 1:
            m.put(V + 4, 1, 0)
            m.write(V + 8, bytes(0x24))
            m.put(V, 4, m.vcall(b, 0x98))
            m.write(V + 8, m.read(Z, 0x24))
            m.call_void(m.main + 0x114AAB0, m.u64(m.u64(o + 0x78) + 0xD80), res, V)
        if kind in _EOT_ENDED:
            fn, with_x = _EOT_ENDED[kind]
            m.call_void(m.main + fn, o, b, *((X,) if with_x else ()))
        return
    if m.vcall(b, 0x200) & 1:
        return
    amount = m.vcall(b, 0x428, kind, m.call(m.main + 0x114ACBC, o)) & M32
    if amount and not (m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49C) >> 1 & 1 and m.vcall(b, 0x510, 0x19) & 1):
        amount = m.call(m.main + 0x114B630, m.u64(o + 0x38), b, kind, amount) & M32
        arg = (0x0029280000002627 >> (8 * (kind - 4))) & M32 if 0 <= kind - 4 < 7 else 0
        if amount and m.call(m.main + 0x114B9A4, m.u64(m.u64(m.u64(o + 0x78) + 0x17A0) + 0x38), b,
                             amount, arg) & 1:
            if kind in _EOT_DAMAGE:
                text, extra, head = _EOT_DAMAGE[kind]
                m.call_void(m.main + 0x114ADE8, m.u64(o + 0x20), b, text)
                v = m.vcall(b, 0x240, kind)
                m.write(Z, bytes(0x24))
                m.put(Z, 2, head)
                m.put(Z + 2, 2, 0x82); m.put(Z + 4, 4, m.vcall(b, 0x98))
            else:
                if kind == 0x2E:
                    m.call_void(m.main + 0x114ADE8, m.u64(o + 0x20), b, 0x98)
                v = m.vcall(b, 0x240, kind)
                m.write(Z, bytes(0x24))
                extra = 0
                if kind == 0x2E:
                    m.put(Z, 2, 0x7D)
                    m.put(Z + 2, 2, 0x102); m.put(Z + 4, 4, m.vcall(b, 0x98)); m.put(Z + 8, 4, 0x360)
            v0 = v[0] if isinstance(v, tuple) else v
            m.put(V + 0x18, 8, Z); m.put(V, 8, b); m.put(V + 8, 4, amount); m.put(V + 0x10, 4, v0)
            m.put(V + 0xC, 1, extra); m.put(V + 0x20, 1, 1)
            m.call_void(m.main + 0x114AF54, m.u64(m.u64(o + 0x78) + 0x17C0), res, V)
    if kind == 0x30:
        _eot_kind_30(m, o, b, Z + 0x30)
    elif kind in _EOT_AFTER:
        m.call_void(m.main + _EOT_AFTER[kind], o, b)


@lifted(0x114335C)
def end_of_turn_conditions_of(m, o, *_):
    """0x114a094 on 0x114338c([o+0x78]); its out byte."""
    with m.frame(0x10) as f:
        m.call_void(m.main + 0x114A094, m.call(m.main + 0x114338C, m.u64(o + 0x78)), f, f + 8)
        return m.u8(f)


@lifted(0x113FA5C)
def store_byte(m, p, v, *_):
    m.put(p, 1, v)


@lifted(0x2888998)
def field_1f60(m, o, *_):
    return m.u64(o + 0x1F60)


@lifted(0x1145240)
def triggers_after_turn(m, o, *_):
    """0x121b9b4 on [[o+0x78]+0x1f60] with flag 0."""
    with m.frame(0x10) as f:
        m.put(f + 8, 1, 0)
        m.call_void(m.main + 0x121B9B4, m.call(m.main + 0x2888998, m.u64(o + 0x78)), f, f + 8)


@lifted(0x1149510)
def hp_rule_reached(m, x, *_):
    """By the setup's rule word [[[x]+0x38]+0x498]: bit 32 (and member 1's vf 0x90(0x3fd, 0)) or bit 33:
    whether member 1 (0xfa0028) has round(vf 0x560(6) * vf 0x110 / 100) >= vf 0x108 (u16 values)."""
    bits = m.u64(m.u64(m.u64(x) + 0x38) + 0x498)
    if bits >> 32 & 1:
        p = m.call(m.main + 0xFA0028, m.u64(m.u64(x + 8) + 0x30), 1, 0)
        if not m.vcall(p, 0x90, 0x3FD, 0) & 1:
            return 0
    elif bits >> 33 & 1:
        p = m.call(m.main + 0xFA0028, m.u64(m.u64(x + 8) + 0x30), 1, 0)
    else:
        return 0
    pct = m.vcall(p, 0x560, 6) & M32
    prod = pct * (m.vcall(p, 0x110) & 0xFFFF) & M32
    q = prod // 100
    if prod - q * 100 > 0x31:
        q += 1
    return int(q >= m.vcall(p, 0x108) & 0xFFFF)


def _step(m, o):
    s = m.u64(o + 0x40) + 0x88
    m.put(s, 1, m.u8(s) + 1)


def _sides_flag(m, o):
    """Whether one of the first four entries ([[o+0x68]+0x5c], stride 8, count +0x7c) reads 1."""
    t = m.u64(o + 0x68)
    return any(i <= 3 and m.u8(t + 0x5C + 8 * i) == 1 for i in range(m.u32(t + 0x7C)))


@lifted(0x11428A4)
def turn_end_steps(m, o, *_):
    """The end-of-turn state machine, resumable at the step byte [[o+0x40]+0x88] (0..0x16): commands 0xb2
    / 0xc5, 0x11502bc, the raid faint pass (kind 0xf4) or 0x1142f98, 0x1145240, 0x1143158, faint passes
    0x99 / 0x9a / 0x9b, 0x114335c, 0x114318c, 0x1142f64, 0x1142d98, the rule 0x49c bit 1 step; each check
    of 0x114a808, the battle state 8 and [[o+0x50]+0x1b] can end it. The result written to
    [[o+0x40]+0x28] is 7 when 0x114a808 holds, else by the exit (0x0000000805060104 >> 8 * code)."""
    q = m.u64(o + 0x20)
    raid = m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x499) >> 2 & 1
    state = m.u64(o + 0x40)

    def over():
        return m.call(m.main + 0x114A808, o) & 1

    def ended():
        return m.u8(m.u64(m.u64(o + 0x40) + 0x28)) == 8

    def quit_flag():
        return m.u8(m.u64(o + 0x50) + 0x1B)

    def faint(kind):
        with m.frame(0x10) as f:
            m.put(f + 8, 2, kind)
            m.call_void(m.main + 0x11449F4, m.u64(m.u64(o + 0x78) + 0x18C0), f, f + 8)
            return m.u8(f)

    def run(s):
        """The steps from s on; returns the exit code (None: no result written)."""
        if s > 0x16:
            return None
        if s <= 0:
            m.call_void(m.main + 0x119AFF0, m.u64(q + 0x18), 0xB2, 0); _step(m, o)
        if s <= 1:
            m.call_void(m.main + 0x11502BC, o); _step(m, o)
        if s <= 2:
            _step(m, o)
            if m.call(m.main + 0x1143624, o) & 1:
                faint(0xF4)
                if quit_flag():
                    return 1
                return 2 if _sides_flag(m, o) else None
        if s <= 3:
            if raid:
                m.call_void(m.main + 0x119AFF0, m.u64(q + 0x18), 0xC5, 0)
            _step(m, o)
            if m.call(m.main + 0x1142F98, o) & 1:
                return 0
        for at, body in ((4, None), (5, "quit_1145240"), (6, 0x1143158), (7, 0x99), (8, None), (9, "quit"),
                         (10, 0x114335C), (11, None), (12, "quit"), (13, 0x114318C), (14, 0x1142F64),
                         (15, "sides"), (16, "step"), (17, 0x1142D98), (18, "rule"), (19, 0x9A), (20, None),
                         (21, "quit"), (22, 0x9B)):
            if s > at:
                continue
            if body is None:                                # 4, 8, 11, 20
                _step(m, o)
                if over():
                    return None
                if ended():
                    return 4
            elif body in ("quit", "quit_1145240"):
                _step(m, o)
                if quit_flag():
                    if body == "quit_1145240":
                        m.call_void(m.main + 0x1145240, o)
                    return 1
            elif body in (0x1143158, 0x114318C, 0x1142F64, 0x1142D98):
                m.call_void(m.main + body, o); _step(m, o)
            elif body in (0x99, 0x9A):
                _step(m, o)
                if faint(body):
                    return 0
            elif body == 0x114335C:
                _step(m, o)
                if m.call(m.main + 0x114335C, o) & 1:
                    return 0
            elif body == "sides":
                _step(m, o)
                if _sides_flag(m, o):
                    return 2
            elif body == "step":
                _step(m, o)
            elif body == "rule":
                if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49C) >> 1 & 1 and \
                        m.call(m.main + 0x1149510, m.u64(m.u64(o + 0x10) + 0x330)) & 1:
                    m.call_void(m.main + 0x11519AC, m.u64(m.u64(o + 0x78) + 0x1F80))
                _step(m, o)
            else:                                           # 22
                faint(0x9B); _step(m, o)
                return None
        return None

    code = run(m.u8(state + 0x88))
    if raid:
        m.call_void(m.main + 0x119AFF0, m.u64(q + 0x18), 0xC5, 1)
    if over():
        return _tail(m, m.main + 0x113FA5C, m.u64(m.u64(o + 0x40) + 0x28), 7)
    if code is None:
        return
    return _tail(m, m.main + 0x113FA5C, m.u64(m.u64(o + 0x40) + 0x28), 0x0000000805060104 >> (8 * code))


@lifted(0x113E97C)
def turn_end_of(m, o, *_):
    """0x11428a4 on 0x113e9a8([o+0x78])."""
    with m.frame(0x10) as f:
        return _tail(m, m.main + 0x11428A4, m.call(m.main + 0x113E9A8, m.u64(o + 0x78)), f, f + 8)


@lifted(0x176917C)
def recoil_or_drain(m, o, _x, r, *_):
    """r = {b, move, u32 base}: for b standing and not in position 10, the amount 0x176923c; applied
    through 0x176989c when its flag is set, else when 0x2881c1c allows it."""
    b = m.u64(r)
    ident = m.vcall(b, 0x98) & M32
    if m.vcall(b, 0x200) & 1:
        return
    if m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), ident) & 0xFF == 0xA:
        return
    with m.frame(0x10) as f:
        amount = m.call(m.main + 0x176923C, m.u64(o + 0x38), m.u64(r), m.u16(m.u64(r + 8)), m.u32(r + 0x10),
                        f) & M32
        if not amount:
            return
        if m.u8(f) or m.call(m.main + 0x2881C1C, o, m.u64(r), amount) & 1:
            m.call_void(m.main + 0x176989C, o, m.u64(r), amount)


@lifted(0x1536FB0)
def on_rule_side(m, o, b, *_):
    """Whether the setup's rule value for b's id (0..4, 0 when absent) equals byte +0x95 of [o+8]."""
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50),
               m.vcall(b, 0x98) & M32)
    v = m.s(p, 4) if p else 0
    v = v if v < 5 else 0
    return int(v & M32 == m.u8(m.u64(o + 8) + 0x95))


def _scale_4096(v):
    """int(f32(v) / 100 * 4096 + (+-0.5)), all in float32 (0x15322fc)."""
    x = _f32(_f32(float(_s32(v))) / _f32(100.0))
    return int(_f32(_f32(x * _f32(4096.0)) + (0.5 if x > 0 else -0.5)))


@lifted(0x1531FB0)
def apply_move_damage(m, o, out, r, *_):
    """r = {user +0, +8, move +0x10, +0x18, targets list +0x28, +0x30, +0x38, command slots +0x40, +0x48}:
    two target lists (0x1532554, 0x153268c), each through the damage pass 0x1535c8c (spread ratio 0x1000
    for one target, else the rule ratio vf 0x68 of 0x114acbc's object on main+0x3c6a510, as a 4096
    factor) into a hit record, both recorded by 0x15323d4; five commands reserved through 0x10afcb8
    (0x9c, 0x7e x3, 0x8b) into the u16 slots [r+0x40]; then 0x15327c4 on each record, *out += the damage;
    after a first record with damage, a battler on the rule side (0x1536fb0) makes the counted object of
    0x114e480 (0x1142424) run vf 0x48(3, 1). Ends with the raw command bytes 00 d1 01 00 on the queue."""
    from pokeldn.sv.battle.engine.lift0 import _release_ref
    L = m.u64(r + 0x28)
    multi = int(m.u8(L + 0xA6) > 1)
    if m.u8(L + 0xA7) == 1:
        ratio = 0x1000
    else:
        x = m.call(m.main + 0x114ACBC, o)
        ratio = _scale_4096(m.vcall(x, 0x68, m.main + 0x3C6A510))
        L = m.u64(r + 0x28)
    with m.frame(0x400) as sp:
        x29 = sp + 0x380
        L1, L2, H1, H2, A, T = sp + 0x1B8, sp + 0x108, sp + 0x88, sp + 8, x29 - 0x38, x29 - 0xB8
        _clear_members(m, L1)
        _clear_members(m, L2)
        m.call_void(m.main + 0x1532554, L, m.u64(o + 0x10), m.u64(r), L1)
        m.call_void(m.main + 0x153268C, m.u64(r + 0x28), m.u64(o + 0x10), m.u64(r), L2)
        m.write(H1 + 4, bytes(0x78))
        m.write(H2 + 4, bytes(0x78))
        for lst, H in ((L1, H1), (L2, H2)):
            m.put(A, 8, m.u64(r)); m.put(A + 8, 8, lst); m.put(A + 0x10, 8, m.u64(r + 0x10))
            m.put(A + 0x18, 8, m.u64(r + 0x18)); m.put(A + 0x20, 4, ratio); m.put(A + 0x28, 8, m.u64(r + 0x48))
            m.put(T, 2, 0)
            m.write(T + 4, bytes(0x78))
            m.call_void(m.main + 0x1535C8C, m.u64(m.u64(o + 0x78) + 0x140), T, A)
            m.put(H, 2, m.u16(T))
            m.write(H + 4, m.read(T + 4, 0x78))
        m.call_void(m.main + 0x15323D4, o, H1)
        m.call_void(m.main + 0x15323D4, o, H2)
        q = m.u64(o + 0x18)
        slots = m.u64(r + 0x40)
        for off, cmd in ((0, 0x9C), (4, 0x7E), (6, 0x7E), (8, 0x7E), (2, 0x8B)):
            m.put(slots + off, 2, m.call(m.main + 0x10AFCB8, q, cmd, 0xCF, 0))
        for k, H in enumerate((H1, H2)):
            P = T
            m.put(P, 8, m.u64(r)); m.put(P + 8, 8, m.u64(r + 8)); m.put(P + 0x10, 8, H)
            m.put(P + 0x18, 8, m.u64(r + 0x10)); m.put(P + 0x20, 8, m.u64(r + 0x38))
            m.put(P + 0x28, 1, multi); m.put(P + 0x30, 8, m.u64(r + 0x30))
            m.call_void(m.main + 0x15327C4, m.u64(m.u64(o + 0x78) + 0x8C0), A, P)
            dealt = m.u32(A)
            if k == 0 and dealt and m.call(m.main + 0x1536FB0, o, m.u64(r)) & 1:
                x = m.call(m.main + 0x114E480, o)
                m.x8 = T
                m.call_void(m.main + 0x1142424, x)
                obj = m.u64(T)
                m.vcall_void(obj, 0x48, 3, 1)
                obj = m.u64(T)
                if obj:
                    _release_ref(m, obj)
            m.put(out, 4, m.u32(out) + dealt)
        q = m.u64(o + 0x18)
        n = m.u32(q + 0x68)
        for i, v in enumerate((0, 0xD1, 1)):
            m.put(q + 0x70 + ((n + i) & M32), 1, v)
        m.put(q + 0x68, 4, n + 4)
        m.put(q + 0x70 + ((n + 3) & M32), 1, 0)


@lifted(0x2882BDC)
def field_840(m, o, *_):
    return m.u64(o + 0x840)


@lifted(0x2882C58)
def field_860(m, o, *_):
    return m.u64(o + 0x860)


@lifted(0x2882BA4)
def move_kind_9(m, o, a, b, c, d, e, *_):
    """0x28813c8 on 0x2882bdc([o+0x78]) with {c, b, a, d, e}."""
    with m.frame(0x30) as f:
        for k, v in enumerate((c, b, a, d, e)):
            m.put(f + 8 + 8 * k, 8, v)
        m.call_void(m.main + 0x28813C8, m.call(m.main + 0x2882BDC, m.u64(o + 0x78)), f, f + 8)


@lifted(0x2882BE4)
def multi_hit(m, o, out, slots, x3, x4, x5, x6, x7, s0, s1, *_):
    """0x2881cc0 on 0x2882c58([o+0x78]) with {x5, x6, x7, s0, s1, x4, x3} and a result {u32 amount, 10
    bytes of 0xff}: *out = the amount, the 10 bytes copied to `slots`."""
    with m.frame(0x60) as f:
        res, B = f, f + 0x10
        m.put(res + 4, 8, M64); m.put(res + 0xC, 2, 0xFFFF)
        for k, v in enumerate((x5, x6, x7, s0, s1, x4, x3)):
            m.put(B + 8 * k, 8, v)
        m.call_void(m.main + 0x2881CC0, m.call(m.main + 0x2882C58, m.u64(o + 0x78)), res, B)
        m.put(out, 4, m.u32(res))
        m.put(slots + 8, 2, m.u16(res + 0xC)); m.put(slots, 8, m.u64(res + 4))


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


def _rule_side(m, o, b):
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50),
               m.vcall(b, 0x98) & M32)
    v = m.s(p, 4) if p else 0
    return v if v < 5 else 0


@lifted(0x1579A98)
def run_move_hits(m, o, _x, r, *_):
    """r = {user, move, +0x10, +0x18, targets, u8 +0x28}: 0x2833de4, the hit count 0x19d40f4 into X,
    0x174fa60, then the damage: move field 3 == 9 -> 0x2882ba4; X+3 set, or one target and two hits or
    more -> 0x2882be4; else 0x1531fb0 over D. Then 0x176917c (recoil / drain), 0x15835ac (after-move
    steps), the slot record [[o+0x40]+8] + 0xc4 * byte +0x938 when K+2 was set (0x1579498), the per-side
    counter and command 0x2e when damage was dealt (rule 0x49c bit 1 needs a target 0x17d5d98 refuses
    and the user without condition 0x1c), 0x15660d0 in raids, and triggers 0x121bdb0 (2 per target, 3,
    0x19, 0x1e per target on the rule side)."""
    with m.frame(0x1A0) as sp:
        x29 = sp + 0x140
        K, M, X, D, out = sp + 0x18, sp + 0x28, x29 - 0x68, x29 - 0x50, x29 - 0x58
        m.call_void(m.main + 0x2833DE4, m.u64(o + 0x38), m.u64(r), m.u64(r + 8), m.u64(r + 0x20))
        m.call_void(m.main + 0x19D40F4, m.u64(o + 0x38), m.u64(r), m.u16(m.u64(r + 8)), X, m.u8(r + 0x28))
        m.put(M, 8, m.u64(r)); m.put(M + 8, 8, m.u64(r + 8)); m.put(M + 0x10, 8, m.u64(r + 0x20))
        m.call_void(m.main + 0x174FA60, m.u64(m.u64(o + 0x78) + 0x820), D, M)
        _clear_members(m, M)
        m.put(K + 8, 2, 0xFFFF); m.put(K, 8, M64)
        R = [m.u64(r + 8 * k) for k in range(5)]
        if not m.u8(R[4] + 0xA6):
            dealt = 0
        elif _move_field_3(m, R[1]) == 9:
            m.call_void(m.main + 0x2882BA4, o, m.u64(r), m.u64(r + 8), m.u64(r + 0x18), m.u64(r + 0x20), M)
            dealt = 0
        else:
            m.put(x29 - 0x5C, 4, 0)
            R = [m.u64(r + 8 * k) for k in range(5)]
            if m.u8(X + 3) or (m.u8(R[4] + 0xA7) == 1 and m.u8(X) >= 2):
                m.call_void(m.main + 0x2882BE4, o, x29 - 0x5C, K, X, M, R[0], R[2], R[1], R[3], R[4])
                dealt = m.u32(x29 - 0x5C)
            else:
                m.put(D, 8, R[0]); m.put(D + 8, 8, R[2]); m.put(D + 0x20, 1, m.u8(r + 0x28))
                m.put(D + 0x28, 8, R[4]); m.put(D + 0x30, 8, M); m.put(D + 0x10, 8, R[1])
                m.put(D + 0x18, 8, R[3]); m.put(D + 0x38, 8, X); m.put(D + 0x40, 8, K)
                m.put(D + 0x48, 8, m.u64(m.u64(o + 0x10) + 0x150))
                m.put(out, 4, 0)
                m.call_void(m.main + 0x1531FB0, m.u64(m.u64(o + 0x78) + 0x900), out, D)
                dealt = m.u32(out)
                m.put(x29 - 0x5C, 4, dealt)
        m.put(D, 8, m.u64(r)); m.put(D + 8, 8, m.u64(r + 8)); m.put(D + 0x10, 4, dealt)
        m.call_void(m.main + 0x176917C, m.u64(m.u64(o + 0x78) + 0x920), out, D)
        m.put(D, 8, m.u64(r + 0x10)); m.put(D + 8, 8, m.u64(r + 8)); m.put(D + 0x20, 1, m.u8(r + 0x28))
        m.put(D + 0x10, 8, m.u64(r)); m.put(D + 0x18, 8, M)
        m.call_void(m.main + 0x15835AC, m.u64(m.u64(o + 0x78) + 0x880), out, D)
        if m.s(K + 2, 2) != -1:
            base = m.u64(m.u64(o + 0x40) + 8)
            e = base + 0xC4 * m.u8(base + 0x938)
            mv = m.u64(r + 8)
            if not m.u8(e + 0x20):
                m.put(e + 0x20, 1, 1); m.put(e + 0x21, 1, 1)
            m.put(e + 0x24, 1, 1)
            v = m.u16(K + 2)
            x27 = m.u64(o + 0x28)
            if v == 0xFFFF:
                v = m.call(m.main + 0x1579490, m.u64(x27 + 8))
            m.put(e + 0x22, 2, v)
            m.call_void(m.main + 0x1579498, m.u64(x27 + 0x10), mv, e + 0x18, K)
            m.put(e + 0x1C, 1, 0); m.put(e + 0x21, 1, 1)
        if not dealt:
            return
        side = _rule_side(m, o, m.u64(r))
        count = True
        if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49C) >> 1 & 1:
            count = False
            if not m.vcall(m.u64(r), 0x4D0, 0x1C) & 1:
                user = m.u64(r)
                i = 0
                while i < m.u8(M + 0xA6):
                    t = m.u64(M + 8 * i)
                    if t and not m.call(m.main + 0x17D5D98, o, user, t) & 1:
                        count = True
                        break
                    i += 1
        if count:
            q = m.u64(o + 0x20)
            if side <= 4:
                slot = m.u64(m.u64(m.u64(q + 0x20) + 0x10) + 0x210) + 8 * (side & M32) + 0x80
                v = m.u64(slot)
                if v <= 2:
                    m.put(slot, 8, v + 1)
            m.call_void(m.main + 0x119AFF0, m.u64(q + 0x18), 0x2E, 2, side & 0xFF)
        if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x499) >> 2 & 1 and m.u8(M + 0xA6):
            m.call_void(m.main + 0x15660D0, o, M, dealt)

        def trigger(kind, ident):
            m.put(D + 8, 2, 0); m.put(D + 0xA, 1, 0); m.put(D + 0xC, 2, 0)
            m.put(D, 4, kind); m.put(D + 4, 4, ident)
            m.put(out, 1, 0)
            m.call_void(m.main + 0x121BDB0, m.u64(m.u64(o + 0x78) + 0x1D40), out, D)

        _for_each_member(m, M, lambda t: trigger(2, m.vcall(t, 0x98)))
        trigger(3, 0)
        trigger(0x19, 0)
        if _rule_side(m, o, m.u64(r)) & M32 != m.u8(m.u64(o + 8) + 0x95):
            return
        _for_each_member(m, M, lambda t: trigger(0x1E, m.vcall(t, 0x98)))


@lifted(0x1580120)
def event_b1(m, x, mv, b, *_):
    """Event 0xb1 with b's id (3) and the u16 move (0x12)."""
    _event(m, x, 0xB1, ((3, lambda: m.vcall(b, 0x98), 4, 0x20), (0x12, lambda: m.u16(mv), 4, 0x98)))


@lifted(0x288AFA0)
def field_6c0(m, o, *_):
    return m.u64(o + 0x6C0)


@lifted(0x288B040)
def field_700(m, o, *_):
    return m.u64(o + 0x700)


@lifted(0x288AD14)
def move_kind_5(m, o, a, b, c, d, *_):
    """0x288afa8 on 0x288afa0([o+0x78]) with {a, c, b, d}."""
    with m.frame(0x30) as f:
        r = f + 0x10
        m.put(r, 8, a); m.put(r + 8, 8, c); m.put(r + 0x10, 8, b); m.put(r + 0x18, 8, d)
        m.call_void(m.main + 0x288AFA8, m.call(m.main + 0x288AFA0, m.u64(o + 0x78)), f + 8, r)


@lifted(0x288AD48)
def move_kind_12(m, o, a, mv, c, *_):
    """0x288b048 on 0x288b040([o+0x78]) with {u16 move, a, c}."""
    with m.frame(0x20) as f:
        r = f + 8
        m.put(r, 2, m.u16(mv)); m.put(r + 8, 8, a); m.put(r + 0x10, 8, c)
        m.call_void(m.main + 0x288B048, m.call(m.main + 0x288B040, m.u64(o + 0x78)), f, r)


# 0x1578b8c's status-move handlers by kind byte r+0x19 (jump table 0x3c6a66c): address, argument order
# over r's qwords (0 user, 1 +8, 2 move, 5 +0x28).
_STATUS_KIND = {1: (0x288ACE0, (0, 2, 5)), 2: (0x15799A8, (1, 0, 2, 5)), 3: (0x288AD80, (0, 2, 5)),
                5: (0x288AD14, (1, 0, 2, 5)), 10: (0x288ADB4, (0, 2)), 11: (0x157FD04, (0, 2, 5)),
                12: (0x288AD48, (0, 2, 5)), 13: (0x157FD04, (0, 2, 5))}


@lifted(0x1578B8C)
def run_move(m, o, _x, r, *_):
    """r = {user, +8, move, u8 damaging +0x18, u8 kind +0x19, targets +0x20, +0x28}: a damaging move runs
    0x1579a98 with {user, move, +8, targets, +0x28, 0}; otherwise the handler of its kind (1, 2, 3, 5, 10,
    11, 12, 13), then event 0xb1 (0x1580120)."""
    q = [m.u64(r + 8 * k) for k in range(6)]
    if m.u8(r + 0x18):
        with m.frame(0x40) as f:
            A = f
            m.put(A, 8, q[0]); m.put(A + 8, 8, q[2]); m.put(A + 0x10, 8, q[1]); m.put(A + 0x18, 8, q[4])
            m.put(A + 0x20, 8, q[5]); m.put(A + 0x28, 1, 0)
            m.call_void(m.main + 0x1579A98, m.u64(m.u64(o + 0x78) + 0x8A0), f + 0x30, A)
        return
    kind = m.u8(r + 0x19)
    if kind in _STATUS_KIND:
        fn, order = _STATUS_KIND[kind]
        m.call_void(m.main + fn, o, *(q[k] for k in order))
    user, mv = m.u64(r), m.u64(r + 0x10)
    return _tail(m, m.main + 0x1580120, m.call(m.main + 0x1146E90, o), mv, user)


@lifted(0x1579A90)
def field_1bc0(m, o, *_):
    return m.u64(o + 0x1BC0)


@lifted(0x1579A58)
def move_field_21_step(m, o, a, b, c, *_):
    """0x1580c40 on 0x1579a90([o+0x78]) with {a, b, c}; its result byte."""
    with m.frame(0x20) as f:
        m.put(f + 8, 8, a); m.put(f + 0x10, 8, b); m.put(f + 0x18, 8, c)
        m.call_void(m.main + 0x1580C40, m.call(m.main + 0x1579A90, m.u64(o + 0x78)), f, f + 8)
        return m.u8(f)


@lifted(0x2833298)
def event_d5(m, o, b, _x, mv, *_):
    """Event 0xd5 with b's id (3) and the u16 move (0x12)."""
    _event(m, o, 0xD5, ((3, lambda: m.vcall(b, 0x98), 4, 0x20), (0x12, lambda: m.u16(mv), 4, 0x98)))


def _move_field(m, mv_id, field, write=True):
    """Byte field `field` of the move's record (table 0x46d7948; refused while not built). write=False
    reads without the game's note of the table in its second static."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    if write:
        table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    else:
        if m.u8(m.u64(m.main + 0x46D7940)) & 1 == 0:
            raise UnliftedCall("static 0x46d7948 not built")
        table = m.u64(m.u64(m.main + 0x46D7948))
    return fb.u8(m, m.call(m.main + 0xBF60CC, table, mv_id & 0xFFFF), field)


def _counted_vf48(m, o, a, b, scratch):
    """vf 0x48(a, b) on the counted object of 0x114e480 (0x1142424), the reference then dropped."""
    from pokeldn.sv.battle.engine.lift0 import _release_ref
    x = m.call(m.main + 0x114E480, o)
    m.x8 = scratch
    m.call_void(m.main + 0x1142424, x)
    m.vcall_void(m.u64(scratch), 0x48, a, b)
    obj = m.u64(scratch)
    if obj:
        _release_ref(m, obj)


@lifted(0x15784B8)
def use_move(m, o, out, r, *_):
    """r = {user, +8, move, +0x18}: out = {done, field-21 result}. The rule side's moves 0x96 / 0xa5 run
    vf 0x48(4 / 5, 1) on 0x114e480's counted object; a move with field 21 goes through 0x1579a58 first
    (2: done, 1: stop, 3: event 0xd5). Then five reserved commands, the slot record (0x1578ab4,
    0x157a070, 0x157a950), the target pass 0x157a9bc; when it keeps the move, 0x1578b8c with the damaging
    flag (field 3 in {0, 4, 6, 7, 8, 9}) and kind; 0x1578ce8, 0x1578f08 (0x29), the PP use (vf 0x700,
    vf 0x768 / 0x770 on the party member, command 8) and 0x1144df8 on the user; out[0] = not kept."""
    mv = m.u16(m.u64(r + 0x10))
    if _move_field(m, mv, 21, write=False):
        _need(m, m.main + 0x1580C40)
    m.put(out, 1, 0)
    with m.frame(0x120) as sp:
        x29 = sp + 0xB0
        L, S, D, res = sp, sp + 0x58, x29 - 0x48, x29 - 0x10
        kind = _move_field(m, mv, 3)
        R = [m.u64(r + 8 * k) for k in range(4)]
        if _rule_side(m, o, R[0]) & M32 == m.u8(m.u64(o + 8) + 0x95):
            if mv == 0x96:
                _counted_vf48(m, o, 4, 1, sp + 0x100)
            elif mv == 0xA5:
                _counted_vf48(m, o, 5, 1, sp + 0x100)
        if _move_field(m, mv, 21):
            c = m.call(m.main + 0x1579A58, o, R[0], R[2], R[3]) & 0xFF
            m.put(out + 1, 1, c)
            if c == 2:
                m.put(out, 1, 1)
                return
            if c == 1:
                return
            if c == 3:
                return _tail(m, m.main + 0x2833298, m.u64(o + 0x38), R[0], R[3], R[2])
        q = m.u64(o + 0x18)
        for off, cmd in ((0, 0x9C), (4, 0x7E), (6, 0x7E), (8, 0x7E), (2, 0x8B)):
            m.put(S + off, 2, m.call(m.main + 0x10AFCB8, q, cmd, 0xCF, 0))

        def slot():
            base = m.u64(m.u64(o + 0x40) + 8)
            return base + 0xC4 * m.u8(base + 0x938) + 0x18

        m.call_void(m.main + 0x1578AB4, slot(), m.u64(r), m.u64(r + 0x18), m.u64(m.u64(o + 0x10) + 0xF0))
        R = [m.u64(r + 8 * k) for k in range(4)]
        if m.call(m.main + 0x157A070, m.u64(o + 0x38), R[1], R[0], R[2], R[3], slot()) & 0xFF:
            m.call_void(m.main + 0x157A950, slot())
        for i in range(10):
            m.put(L + 8 * i, 4, 0); m.put(L + 8 * i + 4, 2, 0xE)
        m.put(L + 0x50, 4, 0)
        R = [m.u64(r + 8 * k) for k in range(4)]
        m.put(D + 0x1F, 4, 0)
        m.put(D + 0x10, 8, R[0]); m.put(D + 0x18, 8, 0)
        m.put(D + 0x18, 8, R[3])
        m.put(D, 8, R[1]); m.put(D + 8, 8, R[2])
        m.put(D + 0x20, 1, 0)
        m.put(D + 0x28, 8, m.u64(m.u64(o + 0x10) + 0x170)); m.put(D + 0x30, 8, L)
        m.call_void(m.main + 0x157A9BC, m.u64(m.u64(o + 0x78) + 0x1B20), res, D)
        stopped = m.u8(res)
        if not stopped:
            damaging = int(kind < 10 and 0x3D1 >> kind & 1)
            R = [m.u64(r + 8 * k) for k in range(4)]
            m.put(D + 0x10, 8, R[2]); m.put(D, 8, R[0]); m.put(D + 8, 8, R[1])
            m.put(D + 0x18, 1, damaging); m.put(D + 0x20, 8, L); m.put(D + 0x28, 8, R[3])
            m.put(D + 0x19, 1, kind)
            m.call_void(m.main + 0x1578B8C, m.u64(m.u64(o + 0x78) + 0x1BE0), res, D)
        R = [m.u64(r + 8 * k) for k in range(4)]
        m.put(D + 0x20, 1, stopped ^ 1)
        m.put(D, 8, R[0]); m.put(D + 8, 8, R[1]); m.put(D + 0x10, 8, R[2]); m.put(D + 0x18, 8, S)
        m.call_void(m.main + 0x1578CE8, m.u64(m.u64(o + 0x78) + 0x1C00), res, D)
        m.call_void(m.main + 0x1578F08, m.u64(o + 0x38), m.vcall(m.u64(r), 0x98) & M32, mv, m.u64(r + 8), 0x29)
        b = m.u64(r)
        v = m.u16(m.u64(r + 0x10) + 2)
        ident = m.vcall(b, 0x98) & M32
        k = m.vcall(b, 0x700, v) & M32
        if k & 0xFF <= 3:
            q = m.u64(o + 0x20)
            pm = m.call(m.main + 0xF21C94, m.u64(m.u64(m.u64(q + 0x20) + 0x10) + 0x30), ident)
            c = m.vcall(pm, 0x768, k) & 0xFF
            m.vcall_void(pm, 0x770, k, M32 if c == 0xFF else c + 1)
            m.call_void(m.main + 0x119AFF0, m.u64(q + 0x18), 8, ident, k & 0xFF)
        m.put(D, 8, m.u64(r)); m.put(D + 8, 1, 1); m.put(D + 0x10, 8, 0)
        m.call_void(m.main + 0x1144DF8, m.u64(m.u64(o + 0x78) + 0x400), res, D)
        m.put(out, 1, stopped ^ 1)


@lifted(0x2880F5C)
def field_1ca0(m, o, *_):
    return m.u64(o + 0x1CA0)


@lifted(0x2880F28)
def action_kind_4(m, o, a, b, mv, *_):
    """0x2880f64 on 0x2880f5c([o+0x78]) with {a, b, u16 move}."""
    with m.frame(0x20) as f:
        m.put(f + 8, 8, a); m.put(f + 0x10, 8, b); m.put(f + 0x18, 2, mv)
        m.call_void(m.main + 0x2880F64, m.call(m.main + 0x2880F5C, m.u64(o + 0x78)), f, f + 8)


def _raid_member_id(m, o):
    """[[o+0x10]+0x310]'s cached id (+0x18), looked up once (0x14b5634 member 0) under rule 0x499 bit 2."""
    x = m.u64(m.u64(o + 0x10) + 0x310)
    if m.u8(m.u64(m.u64(x + 8) + 0x38) + 0x499) >> 2 & 1 and m.u32(x + 0x18) == 0:
        b = m.call(m.main + 0x114C614, m.call(m.main + 0x14B5634, m.u64(m.u64(x + 0x10) + 0x30), 1), 0)
        if b:
            m.put(x + 0x18, 4, m.vcall(b, 0x98))
    return m.u32(x + 0x18)


def _raid_action_c1(m, o, b, act, flag):
    """Under rule 0x499 bit 2: command 0xc1 (9, flag) when b is the raid member and the action's byte
    +0x28 is 9."""
    if not m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x499) >> 2 & 1:
        return
    ident = m.vcall(b, 0x98) & M32
    if _raid_member_id(m, o) == ident and m.u8(act + 0x28) == 9:
        m.call_void(m.main + 0x119AFF0, m.u64(m.u64(o + 0x20) + 0x18), 0xC1, 9, flag)


def _copy(m, dst, src, n):
    m.write(dst, m.read(src, n))


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


# The queue's command formats, reset at each round start: entry i of 0x3c6abe4 is {u16 command, u8 format,
# pad}; the format bytes in order.
_ROUND_FORMATS = (
    0x00, 0xD4, 0xD4, 0x62, 0x21, 0x93, 0x93, 0x52, 0x52, 0x52, 0x93, 0x93, 0x93, 0x93, 0x29,
    0x21, 0x21, 0x21, 0x72, 0x75, 0x21, 0x62, 0x04, 0xA3, 0x62, 0x62, 0xA3, 0x93, 0x62, 0x67,
    0x52, 0x52, 0x52, 0x52, 0x52, 0x21, 0x62, 0x21, 0x62, 0x65, 0x21, 0x21, 0x21, 0x11, 0x11,
    0x01, 0x02, 0x02, 0x84, 0x22, 0x84, 0x52, 0x01, 0x93, 0x63, 0xB3, 0x21, 0x72, 0x72, 0x62,
    0x21, 0x01, 0x01, 0x21, 0x21, 0x72, 0x67, 0x21, 0x01, 0x57, 0x63, 0x02, 0x63, 0xC3, 0x85,
    0x02, 0x02, 0x43, 0x21, 0x52, 0x01, 0x52, 0x52, 0x01, 0x00, 0x23, 0x72, 0x93, 0xC4, 0x72,
    0x83, 0x62, 0x62, 0x21, 0x62, 0x21, 0x72, 0x21, 0x21, 0x28, 0x02, 0x85, 0x02, 0x02, 0x02,
    0x02, 0x01, 0x21, 0x21, 0xA3, 0x02, 0x01, 0x00, 0x52, 0xC4, 0xA3, 0xA3, 0x22, 0x02, 0x21,
    0x01, 0x45, 0x01, 0x83, 0x00, 0x84, 0x21, 0x21, 0x22, 0x11, 0x72, 0x57, 0x53, 0x22, 0x62,
    0x02, 0xC3, 0xD3, 0xC4, 0x1A, 0x86, 0x52, 0xA3, 0x53, 0x21, 0x52, 0x21, 0xA4, 0xA4, 0x52,
    0x21, 0x22, 0x12, 0x14, 0x01, 0x72, 0x52, 0x66, 0x52, 0x23, 0x00, 0x28, 0x00, 0x17, 0x42,
    0x53, 0x21, 0x11, 0x12, 0x53, 0x53, 0x11, 0x12, 0x21, 0x01, 0x01, 0x72, 0xA3, 0x21, 0x01,
    0x52, 0x96, 0x01, 0x02, 0x52, 0x00, 0x52, 0x00, 0x52, 0x01, 0x01, 0x11, 0x62, 0x21, 0x65,
    0x10, 0x10, 0x20, 0x20, 0x93, 0x52, 0x22, 0x83, 0x72, 0x52, 0x01, 0x02, 0x02)


def _raid_round_start(m, o):
    """Rule 0x499 bit 2 at round start: for each standing member (0x1147774 order) that is in the raid
    record ([o+0x48] +8, stride 0x8c, count +0x2420): condition 0xc ends (0x1140198, 0x1148470 0x13), vf
    0x4b0(1) on its party member and command 0x51 (id, 1), and its id joins the list [[o+0x40]+0x68]
    (0x114e624; at most 30 ids at +8, count +0x28)."""
    from pokeldn.sv.battle.engine.slots import positions_of_slot
    rec = m.u64(o + 0x48)
    with m.frame(0x20) as it:
        m.put(it, 8, m.u64(m.main + 0x46E2580) + 0x10)
        m.put(it + 8, 8, m.u64(o + 8)); m.put(it + 0x10, 8, m.u64(o + 0x10))
        m.put(it + 0x18, 2, 0); m.put(it + 0x1A, 1, 1)
        m.call_void(m.main + 0x1147774, it)
        if m.u8(it + 0x1A):
            return
        pokecon = m.u64(it + 0x10)
        client, idx = m.u8(it + 0x18), m.u8(it + 0x19)

        def plist(c):
            return m.u64(pokecon + 0x30) + 0x38 * c + 0x28 if c <= 4 else 0

        while True:
            pl = plist(client)
            b = m.u64(pl + 8 * idx) if idx < m.u8(pl + 0x30) else 0
            i = (idx + 1) & 0xFF
            done = True
            if client <= 4:
                while client < 5:
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
                    if found:
                        done = False
                        break
                    client += 1
                    i = 0
                idx = i
            ident = m.vcall(b, 0x98) & M32
            if any(m.u32(rec + 8 + 0x8C * k) == ident for k in range(m.u8(rec + 0x2420))):
                if m.vcall(b, 0x4D0, 0xC) & 1:
                    m.call_void(m.main + 0x1140198, m.u64(o + 0x20), b, 0xC)
                    m.call_void(m.main + 0x1148470, m.u64(o + 0x20), b, 0x13)
                q = m.u64(o + 0x20)
                pm = m.call(m.main + 0xF21C94, m.u64(m.u64(m.u64(q + 0x20) + 0x10) + 0x30), m.vcall(b, 0x98) & M32)
                m.vcall_void(pm, 0x4B0, 1)
                m.call_void(m.main + 0x119AFF0, m.u64(q + 0x18), 0x51, m.vcall(b, 0x98) & M32, 1)
                lst = m.u64(m.u64(o + 0x40) + 0x68)
                ident = m.vcall(b, 0x98) & M32
                if not m.call(m.main + 0x114E624, lst, ident) & 1:
                    n = m.s(lst + 0x28, 4)
                    if n <= 0x1D:
                        m.put(lst + 8 + n, 1, ident)
                        m.put(lst + 0x28, 4, m.u32(lst + 0x28) + 1)
            if done:
                return


@lifted(0x113E3D0)
def run_round(m, o, out, r, *_):
    """One round: battle state 0, queue length 0 and its formats reset; once per round (flag bit 1 of
    [[o+0x40]+0x90]) the turn start 0x113fd2c and the action count cleared; the actions [r] taken in
    (0x1145e40, 0x1145c10); in raids the round-start step and the side counters [o+0x68] cleared with
    0x113e9e4, then sorted (0x113ea20) and 0x113f6b4; then sorted again and run (0x113f7d0); while the
    state stays 0, the turn end 0x113e97c and 0x113e9b0; states 0 and 5..8 run 0x113e948. *out = the
    state."""
    state = lambda: m.u8(m.u64(m.u64(o + 0x40) + 0x28))
    m.put(m.u64(m.u64(o + 0x40) + 0x28), 1, 0)
    q = m.u64(o + 0x18)
    m.put(q + 0x68, 8, 0)
    for i, fmt in enumerate(_ROUND_FORMATS):
        m.put(m.call(m.main + 0xFAF09C, q, m.main + 0x3C6ABE4 + 4 * i), 1, fmt)
    st = m.u64(o + 0x40)
    first = not m.u64(st + 0x90) >> 1 & 1
    with m.frame(0x20) as f:
        def holder():
            m.put(f + 0x10, 8, m.u64(o + 0x48))
            return f + 0x10
        if first:
            m.put(st + 0x90, 8, m.u64(st + 0x90) | 2)
            m.call_void(m.main + 0x113FD2C, m.u64(m.u64(o + 0x78) + 0x19A0), f + 8, f + 0x10)
            m.put(m.u64(o + 0x48) + 0x2420, 1, 0)
        rec = m.u64(o + 0x48)
        x = m.u64(m.u64(o + 0x78) + 0x1820)
        m.call_void(m.main + 0x1145E40, x, rec, m.u64(r))
        m.call_void(m.main + 0x1145C10, x, rec)
        if first:
            if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x499) >> 2 & 1:
                _raid_round_start(m, o)
                t = m.u64(o + 0x68)
                for off, n in ((0x5C, 1), (0x60, 4), (0x64, 1), (0x68, 4), (0x6C, 1), (0x70, 4), (0x74, 1),
                               (0x78, 8)):
                    m.put(t + off, n, 0)
                m.call_void(m.main + 0x113E9E4, o)
            m.call_void(m.main + 0x113EA20, m.u64(m.u64(o + 0x78) + 0x1800), f + 8, holder())
            m.call_void(m.main + 0x113F6B4, m.u64(m.u64(o + 0x78) + 0x7C0), f + 8, holder())
        m.call_void(m.main + 0x113EA20, m.u64(m.u64(o + 0x78) + 0x1800), f + 8, holder())
        m.call_void(m.main + 0x113F7D0, m.u64(m.u64(o + 0x78) + 0x1560), f + 8, holder())
    s = state()
    if s == 0:
        m.call_void(m.main + 0x113E97C, o)
        s = state()
        if s == 0:
            m.call_void(m.main + 0x113E9B0, o)
            s = state()
    if 5 <= s <= 8 or s == 0:
        m.call_void(m.main + 0x113E948, o, 0)
    m.put(out, 1, state())


# 0x113c8a0's builders that tail-call another function with (o, out, size, x3, kind): kind -> address
# (jump table 0x3c6b406 over (kind - 3) / 2, odd kinds 3..77).
_BUILDER_TAILS = {3: 0x114BD5C, 7: 0x113E08C, 11: 0x114BD5C, 15: 0x11513EC, 17: 0x113DCA8, 19: 0x1153E38,
                  23: 0x11457F4, 25: 0x1153CB0, 27: 0x1150EE0, 29: 0x1150ADC, 31: 0x1153FC0, 35: 0x1153350,
                  37: 0x114C220, 61: 0x1150C58, 77: 0x11534C0}


@lifted(0x113C8A0)
def build_message(m, o, out, size, count, kind, *_):
    """The server's per-kind message builder: *out / *size get the message (0 when none). Kind 21 runs a
    round: the queue reset ([[o+0x10]+0x68] 0, formats from 0x3c6abe4), the 0x5060-byte buffer o+0x58
    zeroed and opened with the 0x238 bytes of [o+0x40], 0x113e3d0, the queue bytes copied to o+0x294
    (length o+0x290), *out = o+0x58, *size = 0x5060, *count += 1, the round's state at o+0xc4a5, and
    [o+0x40]'s request block cleared. Kind 9 hands o+0xc468 (4 bytes), kinds 41..51 [o+0x48] (6), kind 75
    three bytes of [o+0x30]+0x10 at o+0xc4a0; others tail-call their builder or leave nothing."""
    kind &= M32
    tail = _BUILDER_TAILS.get(kind)
    if tail:
        _need(m, m.main + tail)
    m.put(out, 8, 0); m.put(size, 4, 0)
    if tail:
        return _tail(m, m.main + tail, o, out, size, count, kind)
    if kind == 21:
        q = m.u64(o + 0x10)
        m.put(q + 0x68, 8, 0)
        for i, fmt in enumerate(_ROUND_FORMATS):
            m.put(m.call(m.main + 0xFAF09C, q, m.main + 0x3C6ABE4 + 4 * i), 1, fmt)
        buf = o + 0x58
        m.write(buf, bytes(0x5060))
        req = m.u64(o + 0x40)
        m.write(buf, m.read(req, 0x238))
        with m.frame(0x20) as f:
            m.put(f + 0x18, 8, req)
            m.call_void(m.main + 0x113E3D0, m.u64(m.u64(m.u64(o + 8) + 0x18) + 0x1760), f + 8, f + 0x18)
            result = m.u8(f + 8)
        q = m.u64(o + 0x10)
        n = m.u32(q + 0x68)
        m.put(o + 0x290, 4, n)
        m.write(o + 0x294, m.read(q + 0x70, n))
        m.put(out, 8, buf); m.put(size, 4, 0x5060)
        m.put(count, 8, m.u64(count) + 1)
        m.put(o + 0xC4A5, 1, result)
        req = m.u64(o + 0x40)
        for off in range(0, 0x230, 0x10):
            m.put(req + off, 8, 0)
        m.put(req + 0x234, 1, 0); m.put(req + 0x230, 4, 0)
    elif kind == 9:
        m.put(out, 8, o + 0xC468); m.put(size, 4, 4)
    elif 41 <= kind <= 51 and kind & 1:
        m.put(out, 8, m.u64(o + 0x48)); m.put(size, 4, 6)
    elif kind in (33, 71):
        m.put(out, 8, 0); m.put(size, 4, 0)
    elif kind == 75:
        p = m.u64(o + 0x30) + 0x10
        a, b, c = m.u32(p), m.u32(p + 4), m.u32(p + 8)
        m.put(o + 0xC4A0, 1, a); m.put(o + 0xC4A1, 1, b); m.put(o + 0xC4A2, 1, c)
        m.put(out, 8, o + 0xC4A0); m.put(size, 4, 3)


# The battle start (message kind 17, 0x113dca8): leaves under 0x113dd68.
def _getter_at(off):
    def fn(m, o, *_):
        return m.u64(o + off)
    return fn


for _addr, _off in {0x113DDCC: 0x16E0, 0x113DEB4: 0x940, 0x113DF30: 0x1F0, 0x1146734: 0xA0, 0x114E21C: 0x13E0,
                    0x114E490: 0x68, 0x113E064: 0x1C0}.items():
    lifted(_addr)(_getter_at(_off))


@lifted(0x113E06C)
def setup_3c(m, o, *_):
    return m.u64(o + 0x38) + 0x3C


@lifted(0x113E058)
def setup_byte_41(m, o, *_):
    return m.u8(m.u64(o + 0x38) + 0x41)


@lifted(0x1145AA0)
def byte_at(m, p, *_):
    return m.u8(p)


@lifted(0x1145AA8)
def clear_byte(m, p, *_):
    m.put(p, 1, 0)
    return p


@lifted(0x113DE78)
def byte_set(m, p, *_):
    return int(m.u8(p) != 0)


@lifted(0x114E488)
def zero_114e488(m, *_):
    return 0


@lifted(0x2A10D7C)
def identity_2a10d7c(m, x, *_):
    return x


@lifted(0x2D3B81C)
def add_byte(m, b, v, *_):
    """Add v to the byte set at b+0x3c2 (count +0x3c1, at most 30) once."""
    n = m.u8(b + 0x3C1)
    if any(m.u8(b + 0x3C2 + i) == v & M32 for i in range(n)):
        return b
    if n and n - 1 > 0x1C:
        return b
    m.put(b + 0x3C2 + n, 1, v); m.put(b + 0x3C1, 1, n + 1)
    return b


@lifted(0x2D14970)
def kind_2(m, p, *_):
    m.put(p, 4, 2)
    return m.main + 0x44F5F10


@lifted(0x2D3DBC4)
def reset_turn_record(m, b, v, *_):
    """u16 +0x48a = v, +0x488 = 0, byte +0x6e = 1, the 0x125 bytes from +0x5cc zeroed."""
    m.put(b + 0x48A, 2, v); m.put(b + 0x488, 2, 0); m.put(b + 0x6E, 1, 1)
    m.write(b + 0x5CC, bytes(0x125))
    return b + 0x5CC


@lifted(0x114E550)
def first_turn_flag(m, o, b, *_):
    """0 under rule 0x49b bit 0, else whether u32 [[b+0x70]+0xcc] is 0."""
    if m.u8(m.u64(o + 0x38) + 0x49B) & 1:
        return 0
    return int(m.u32(m.u64(b + 0x70) + 0xCC) == 0)


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


@lifted(0x11466DC)
def init_list_44fce50(m, p, *_):
    """An object of vtable main+0x44fce50 with an empty list (byte +8, +0xc..+0x33 zero)."""
    m.write(p + 0xC, bytes(0x28)); m.put(p, 8, m.main + 0x44FCE50); m.put(p + 8, 1, 0)
    return p


@lifted(0x113DF48)
def start_condition_message(m, o, *_):
    """When 0x13616e4 answers v: request 0x1154148 (on [[o+0x78]+0xbe0]) with record {0x4b init, +4 8,
    +8 v, +9 1, +0x10 0x113e080(0)}."""
    v = m.call(m.main + 0x13616E4, m.call(m.main + 0x114E480, o)) & 0xFF
    if not v:
        return
    with m.frame(0x60) as f:
        rec = f + 0x10
        m.call_void(m.main + 0x1149604, rec)
        m.put(rec + 4, 4, 8); m.put(rec + 8, 1, v); m.put(rec + 9, 1, 1)
        p = m.call(m.main + 0x113E080, 0)
        x0, x1 = (p[0], p[1]) if isinstance(p, tuple) else (p, 0)
        m.put(rec + 0x10, 8, x0); m.put(rec + 0x18, 8, x1)
        m.call_void(m.main + 0x1154148, m.call(m.main + 0x113DFC4, m.call(m.main + 0x1361214, o)), f + 8, rec)


@lifted(0x113DFCC)
def start_weather_message(m, o, *_):
    """When the setup's byte +0x41 is set: request 0x1149ed0 (on [[o+0x78]+0x1c0]) with {v, 0xff, 0, 0,
    0x100}, then 0x1142850(q, 0) unless byte +7 of the setup's +0x3c block is set."""
    v = m.call(m.main + 0x113E058, m.call(m.main + 0x114E480, o)) & 0xFF
    if not v:
        return
    with m.frame(0x20) as f:
        m.put(f, 1, v); m.put(f + 1, 2, 0xFF); m.put(f + 4, 4, 0); m.put(f + 8, 2, 0x100)
        m.call_void(m.main + 0x1149ED0, m.call(m.main + 0x113E064, m.call(m.main + 0x1361214, o)), f + 0x18, f)
    if not m.u8(m.call(m.main + 0x113E06C, m.call(m.main + 0x114E480, o)) + 7):
        m.call_void(m.main + 0x1142850, m.call(m.main + 0x1143584, o), 0)


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


@lifted(0xC9C090)
def position_of(m, o, client, idx, *_):
    """Battle position (0..10) of entry idx of client slot `client` under the setup's mode +0x36c and rule
    +0x370: the slots own positions 0, 1, 2, 3 and 4..8 in turn (slot per position by mode; mode 1 uses
    tables 0x3c69d34 / 0x3c69d48); 9 or 10 when it falls past them."""
    s = m.u64(o + 8)
    mode, rule = m.u32(s + 0x36C), m.u8(s + 0x370)
    c = client & 0xFF
    idx &= M32

    def take(owner, result):
        nonlocal idx
        if owner == c:
            if idx & 0xFF == 0:
                return result
            idx = (idx - 1) & M32
        return None

    r = take(0 if mode < 3 else 5, 0)
    if r is not None:
        return r
    w = (5 if rule == 0 else 2) if mode == 2 else (1 if mode in (0, 1) else 5)
    r = take(w, 1)
    if r is not None:
        return r
    if mode == 2:
        w = 5 if rule < 2 else 3
    elif mode == 1:
        w = (2, 2, 2, 0, 2)[rule - 1] if 0 <= rule - 1 < 5 else 0      # 0x3c69d34
    else:
        w = 5
    r = take(w, 2)
    if r is not None:
        return r
    if mode == 2:
        w = 5 if rule < 3 else 4
    elif mode == 1:
        w = (3, 3, 3, 3, 5)[rule - 1] if 0 <= rule - 1 < 5 else 1      # 0x3c69d48
    else:
        w = 5
    r = take(w, 3)
    if r is not None:
        return r
    w = 1 if mode == 2 else 5
    if w == c:
        v = idx & 0xFF
        if v < 4:
            return (idx + 4) & M32
        if v == 4:
            return 8
        idx = (idx - 5) & M32
        return 9 if idx & 0xFF == 0 else 10
    return 10


@lifted(0x11468F0)
def raid_boss_start_message(m, o, *_):
    """Under rule 0x49b bit 3: when member 1 (0xfa0028) is of the class 0x46d3f08 with u16 +0x710 0x3f3 and
    byte +0x714 clear, request 0x11505c0 (on [[o+0x78]+0x1d60]) with its id."""
    if not m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49B) >> 3 & 1:
        return
    b = m.call(m.main + 0xFA0028, m.u64(m.u64(o + 0x10) + 0x30), 1, 0)
    if not _raid_class(m, b):
        return
    if m.u16(b + 0x710) != 0x3F3 or m.u8(b + 0x714):
        return
    with m.frame(0x20) as f:
        m.put(f + 0x18, 1, m.vcall(b, 0x98))
        m.call_void(m.main + 0x11505C0, m.u64(m.u64(o + 0x78) + 0x1D60), f + 8, f + 0x18)


@lifted(0x1146A08)
def rule_side_start(m, o, lst, *_):
    """Under rule 0x49c bit 1: the first member of lst on rule side 1 with vf 0x90(0x3fd, 2) runs
    0x2d1dfe4(0) and commands 0x87 / 0xc6 (3, 0)."""
    if not m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49C) >> 1 & 1:
        return
    hit = []

    def visit(b):
        if hit:
            return
        p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50),
                   m.vcall(b, 0x98) & M32)
        if p and m.u32(p) == 1 and m.vcall(b, 0x90, 0x3FD, 2) & 1:
            hit.append(b)

    n = m.u8(lst + 0xA6)
    m.put(lst + 0xA8, 1, 0)
    if n:
        b = m.u64(lst)
        m.put(lst + 0xA8, 1, 1)
        while b:
            visit(b)
            if hit:
                break
            i = m.u8(lst + 0xA8)
            if i >= m.u8(lst + 0xA6):
                break
            m.put(lst + 0xA8, 1, i + 1)
            b = m.u64(lst + 8 * i)
    if not hit:
        return
    q = m.u64(o + 0x20)
    m.call_void(m.main + 0x2D1DFE4, m.u64(m.u64(m.u64(q + 0x20) + 0x10) + 0x330), 0)
    m.call_void(m.main + 0x119AFF0, m.u64(q + 0x18), 0x87, 3, 0)
    return _tail(m, m.main + 0x119AFF0, m.u64(m.u64(o + 0x20) + 0x18), 0xC6, 3, 0)


@lifted(0x289A224)
def reset_on_entry(m, b, *_):
    """A battler's state on entering: vf 0x7f0(0, 1, 1, 1), 0x14807d0, the turn fields and the 46 per-turn
    qwords from +0xe8 cleared, +0x486 = 0x12, the stage bytes +0x414..+0x41a back to 6 (byte +0x392
    kept), then vf 0x628(0)."""
    m.vcall_void(b, 0x7F0, 0, 1, 1, 1)
    m.call_void(m.main + 0x14807D0, b)
    m.put(b + 0x496, 4, 0)
    m.vcall_void(b, 0x580)
    for off in (0x435, 0x42B, 0x44B, 0x441, 0x461, 0x457, 0x477, 0x46D):
        m.put(b + off, 1, 0)
    m.put(b + 0x490, 4, 0); m.put(b + 0x486, 1, 0x12); m.put(b + 0x48C, 2, 0)
    keep = m.u8(b + 0x392)
    for off in range(0xE8, 0x388, 0x10):
        m.put(b + off, 8, 0)
    m.put(b + 0x390, 8, 0); m.put(b + 0x3C0, 1, 0)
    for off in (0x3B8, 0x3B0, 0x3A8, 0x3A0, 0x398, 0x388):
        m.put(b + off, 8, 0)
    m.put(b + 0x392, 1, keep)
    for off in range(0x414, 0x41B):
        if m.u8(b + off) != 6:
            m.put(b + off, 1, 6)
    return _tail(m, m.u64(m.u64(b) + 0x628), b, 0)


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


@lifted(0x114EAB4)
def pair_with_others(m, p, pokecon, idx, members, *_):
    """For entry idx of p's u32 table (+8, stride 8, flag byte +0xc): every other flagged entry not on the
    same side (0x118ab58) is introduced both ways through the members' vf 0x4b8."""
    v = m.u32(p + 8 * (idx & 0xFF) + 8)
    if not v:
        return
    for k in range(11):
        e = p + 8 * k
        if not m.u8(e + 0xC):
            continue
        w = m.u32(e + 8)
        if not w or w == v:
            continue
        if m.call(m.main + 0x118AB58, m.u64(pokecon + 0x290), w, v) & 1:
            continue
        m.vcall_void(m.call(m.main + 0xF21C94, members, m.u32(e + 8)), 0x4B8, v)
        m.vcall_void(m.call(m.main + 0xF21C94, members, v), 0x4B8, m.u32(e + 8))


@lifted(0x114F348)
def raid_member_entered(m, o, b, *_):
    """In battle kinds 0 and 1, a member of the class 0x46d3f08 is passed to vf 0x30 of the counted
    object [o+0x130] (a reference held around the call)."""
    from pokeldn.sv.battle.engine.lift0 import _release_ref
    if not b or m.u32(m.u64(o + 0x38) + 0x30) > 1:
        return
    if not _raid_class(m, b):
        return
    x = m.u64(o + 0x130)
    if not x:
        raise UnliftedCall("0x114f348: no object at +0x130 (the game traps)")
    if m.u32(x + 0x28) == M32:
        raise UnliftedCall("IncrementReference abort")
    m.put(x + 0x28, 4, m.u32(x + 0x28) + 1)
    m.vcall_void(x, 0x30, b)
    return _release_ref(m, x)


lifted(0x11467EC)(_getter_at(0x17E0))


@lifted(0x113DF38)
def set_flag_byte(m, p, v, *_):
    m.put(p + (v & 0xFFFF) + 8, 1, 1)


@lifted(0x113DF08)
def set_flag_of(m, o, v, *_):
    """Byte +8+v of [[o+0x10]+0x1f0] = 1."""
    return _tail(m, m.main + 0x113DF38, m.call(m.main + 0x113DF30, m.u64(o + 0x10)), v & M32)


@lifted(0x114E4E0)
def trigger_kind(m, o, kind, ident, *_):
    """Trigger 0x121bdb0 (on [[o+0x78]+0x1d40]) with {kind, ident, 0, 0, 0}."""
    with m.frame(0x20) as f:
        m.put(f + 0x18, 2, 0); m.put(f + 0x1A, 1, 0); m.put(f + 0x1C, 2, 0)
        m.put(f + 0x10, 4, kind); m.put(f + 0x14, 4, ident)
        m.put(f + 8, 1, 0)
        m.call_void(m.main + 0x121BDB0, m.call(m.main + 0x114E520, m.call(m.main + 0x1361214, o)), f + 8, f + 0x10)


@lifted(0x114E5DC)
def add_entered(m, lst, ident, *_):
    """Append the id byte to the list (+8, count s32 +0x28, at most 30) unless 0x114e624 finds it."""
    if m.call(m.main + 0x114E624, lst, ident) & 1:
        return
    n = m.s(lst + 0x28, 4)
    if n > 0x1D:
        return
    m.put(lst + 8 + n, 1, ident)
    m.put(lst + 0x28, 4, m.u32(lst + 0x28) + 1)


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


@lifted(0x114EE74)
def mark_entered(m, o, ident, *_):
    """Byte +0xb of the entry holding ident among the six u32s at +0x10.. (stride 0x10) of the side's
    0x60-byte record [[o+0x10]+0x250] (side by the setup's rule value, 0..4) = 1."""
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50), ident & M32)
    side = (m.s(p, 4) if p else 0)
    side = (side if side < 5 else 0) & 0xFF
    if side > 4:
        return
    base = m.u64(m.u64(o + 0x10) + 0x250) + side * 0x60
    for k in range(1, 7):
        if m.u32(base + 0x10 * k) == ident & M32:
            m.put(base + 0x10 * k + 0xB, 1, 1)
            return


@lifted(0x114EF5C)
def pair_raid_members(m, o, lst, client, *_):
    """For the members of lst from the slot's position count on (class 0x46d3f08 with vf 0xf8 0x95): the last
    able member (vf 0x208) at or after them gets vf 0x2d0; one before it pairs with that member's party
    record: vf 0x2d0 when either carries conditions 0x3f3 / 0x3fd (vf 0x88) with +0x714 set, else
    vf 0x1e8(its id)."""
    n = m.u8(lst + 0x30)
    last = 0
    k = n
    while k:
        last = (k - 1) & 0xFF
        if last == 0:
            break
        if m.vcall(m.u64(lst + 8 * last), 0x208) & 1:
            break
        k -= 1
    s = m.u64(o + 8)
    i = m.call(m.main + 0xFF9128, m.u32(s + 0x36C), m.u8(s + 0x370), client & 0xFF) & M32
    if _s32(i) >= m.u8(lst + 0x30):
        return
    while True:
        if m.u8(lst + 0x30) > i & 0xFF:
            b = m.u64(lst + 8 * (i & 0xFF))
            if b and _raid_class(m, b) and m.vcall(b, 0xF8) & 0xFFFF == 0x95:
                if _s32(i) >= last:
                    m.vcall_void(b, 0x2D0)
                else:
                    ident = m.vcall(m.u64(lst + 8 * last), 0x98) & M32
                    pm = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 8) + 0x30), ident)
                    if not pm or not _raid_class(m, pm):
                        m.vcall_void(b, 0x1E8, ident)
                    elif (m.vcall(pm, 0x88, 0x3F3) & 1 and m.u8(pm + 0x714)) or \
                            (m.vcall(pm, 0x88, 0x3F3) & 1 and m.u8(b + 0x714)) or \
                            (m.vcall(pm, 0x88, 0x3FD) & 1 and m.u8(pm + 0x714)) or \
                            (m.vcall(pm, 0x88, 0x3FD) & 1 and m.u8(b + 0x714)):
                        m.vcall_void(b, 0x2D0)
                    else:
                        m.vcall_void(b, 0x1E8, ident)
        i = (i + 1) & M32
        if not _s32(i) < m.u8(lst + 0x30):
            return


@lifted(0x1146E98)
def event_for(m, x, b, event, *_):
    """Event `event` with b's id (2)."""
    _event(m, x, event & M32, ((2, lambda: m.vcall(b, 0x98), 4, 0x18),))


@lifted(0x113DED4)
def entered_flag_command(m, q, v, *_):
    """0x113df08([q+0x20], v), then command 0x2b (v & 0xffff)."""
    m.call_void(m.main + 0x113DF08, m.u64(q + 0x20), v & M32)
    return _tail(m, m.main + 0x119AFF0, m.u64(q + 0x18), 0x2B, v & 0xFFFF)


@lifted(0x113DEBC)
def entered_flag_0(m, x, *_):
    return _tail(m, m.main + 0x113DED4, m.call(m.main + 0x1143584, x), 0)


@lifted(0x113DE88)
def entered_flag_0_of(m, o, *_):
    with m.frame(0x10) as f:
        return _tail(m, m.main + 0x113DEBC, m.call(m.main + 0x113DEB4, m.call(m.main + 0x1361214, o)), f, f + 8)


@lifted(0x11467BC)
def sort_list_by_speed(m, o, lst, *_):
    """0x1143e3c on 0x11467ec([o+0x78]) with the list."""
    with m.frame(0x10) as f:
        m.put(f + 8, 8, lst)
        m.call_void(m.main + 0x1143E3C, m.call(m.main + 0x11467EC, m.u64(o + 0x78)), f, f + 8)


def _events_each(event, raiser=0x1146E98):
    def fn(m, o, lst, *_):
        _for_each_member(m, lst, lambda b: m.call_void(m.main + raiser, m.call(m.main + 0x1146E90, o), b, event))
    return fn


lifted(0x11467F4)(_events_each(0x70))
lifted(0x114686C)(_events_each(0x71))


@lifted(0x1146CDC)
def entry_events(m, o, lst, *_):
    """For each member of lst: event 0x73 (0x11470d4), then 0x74, 0x72 and 0xd7 (0x1146e98), then event
    0x75 over the list (0x1147ad8) and 0x1147314."""
    _events_each(0x73, 0x11470D4)(m, o, lst)
    for ev in (0x74, 0x72, 0xD7):
        _events_each(ev)(m, o, lst)
    m.call_void(m.main + 0x1147AD8, m.call(m.main + 0x1146E90, o), lst)
    return _tail(m, m.main + 0x1147314, m.call(m.main + 0x1146E90, o))


@lifted(0x1147314)
def event_76(m, o, *_):
    """Event 0x76 with no parameters."""
    _event(m, o, 0x76, ())


@lifted(0x114E848)
def entered_mark_command(m, o, b, *_):
    """0x114ee74 with b's id (vf 0x2d8 when vf 0x3b8 holds, else vf 0x98), then command 0x4e (id)."""
    ident = (m.vcall(b, 0x2D8) if m.vcall(b, 0x3B8) & 1 else m.vcall(b, 0x98)) & M32
    m.call_void(m.main + 0x114EE74, m.u64(o + 0x20), ident)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x4E, ident)


@lifted(0x114E578)
def entry_handler_command(m, o, ident, *_):
    m.call_void(m.main + 0x114E5AC, m.u64(o + 0x20), ident & M32)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x6B, ident & M32)


@lifted(0x114ECEC)
def pair_raid_members_of(m, o, client, *_):
    """When client slot `client` takes part (0xe7e2a0): 0x114ef5c on its party list, then command 0x3d."""
    pc = m.u64(m.u64(o + 0x10) + 0x290)
    s = m.u64(pc + 8)
    if not m.call(m.main + 0xE7E2A0, m.u32(s + 0x36C), m.u8(s + 0x370), client & 0xFF) & 1:
        return
    x8 = m.u64(m.u64(o + 0x20) + 0x10)
    c = client & M32
    lst = 0 if c > 4 else m.u64(x8 + 0x30) + c * 0x38 + 0x28
    m.call_void(m.main + 0x114EF5C, m.u64(x8 + 0x290), lst, c)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x3D, client & 0xFF)


@lifted(0x114E19C)
def entry_steps_of(m, o, lst, *_):
    with m.frame(0x10) as f:
        m.put(f + 8, 8, lst)
        m.call_void(m.main + 0x114673C, m.call(m.main + 0x1146734, m.call(m.main + 0x1361214, o)), f, f + 8)


@lifted(0x114E1CC)
def send_out_of(m, o, ids, a, b, c, *_):
    """0x114e268 on [[o+0x78]+0x13e0] with bytes {a, b, c}; the id it answers joins the set ids."""
    with m.frame(0x20) as f:
        m.put(f + 0x10, 1, a); m.put(f + 0x11, 1, b); m.put(f + 0x12, 1, c)
        m.call_void(m.main + 0x114E268, m.call(m.main + 0x114E21C, m.call(m.main + 0x1361214, o)), f + 8, f + 0x10)
        m.call_void(m.main + 0x114E224, ids, m.u32(f + 8))


@lifted(0x114673C)
def entry_steps(m, o, _x, idsp, *_):
    """The steps after sending out: 0x11468f0, the standing members in the id set [idsp] (0x11474b0),
    0x1146a08, sorted by speed (0x11467bc), events 0x70 / 0x71 (0x11467f4, 0x114686c) and 0x1146cdc."""
    m.call_void(m.main + 0x11468F0, o)
    with m.frame(0xB0) as lst:
        m.call_void(m.main + 0x1143D84, lst)
        m.call_void(m.main + 0x11474B0, o, lst, m.u64(idsp))
        for fn in (0x1146A08, 0x11467BC, 0x11467F4, 0x114686C, 0x1146CDC):
            m.call_void(m.main + fn, o, lst)


@lifted(0xF7BEDC)
def do_rehash_f7bedc(m, table, n, *_):
    """0xf8001c's __do_rehash with the bucket free (0x171987c's code) inlined."""
    return _do_rehash(m, table, n, 0x171987C)


@lifted(0xF785A8)
def _map_u8_slot_inline(m, table, key_ptr, *_):
    """0xf785a8: unordered_map<u32, u8>::operator[] with the node build inlined (0x18-byte node from the allocator
    [table+0x38], pushed on the thread's object stack while its key and zero value are written) and the
    rehash inlined (tail 0xf7bedc)."""
    import math
    import struct
    from pokeldn.sv.battle.engine.containers import find, _bucket
    from pokeldn.sv.battle.engine.lift0 import _tls_stack
    key = m.u32(key_ptr)
    node = find(m, table, key, 4)
    if node:
        return node + 0x14
    n = m.u64(table + 8)
    alloc = m.u64(table + 0x38)
    node = m.vcall(alloc, 0x10, 0x18, 4)
    if not node:
        raise UnliftedCall("allocator out of memory")
    t = _tls_stack(m)
    if t:
        depth = m.u64(t + 0x80)
        if depth >= 0x10:
            raise UnliftedCall("abort: object stack full")
        m.put(t + 8 * depth, 8, m.u64(table + 0x38))
        m.put(t + 0x80, 8, depth + 1)
    m.put(node + 0x10, 4, m.u32(key_ptr)); m.put(node + 0x14, 1, 0)
    if t:
        m.put(t + 0x80, 8, m.u64(t + 0x80) - 1)
    m.put(node, 8, 0); m.put(node + 8, 8, key)
    size1 = _f32(float(m.u64(table + 0x58) + 1))
    load = struct.unpack("<f", m.read(table + 0x60, 4))[0]
    if n == 0 or _f32(load * _f32(float(n))) < size1:
        grow = (n << 1) | int(n < 3 or not _pow2(n))
        need = math.ceil(_f32(size1 / load))
        _rehash(m, table, max(grow, need), 0xF7BEDC)
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


@lifted(0x114EA98)
def swap_members(m, lst, i, j, *_):
    i &= 0xFF; j &= 0xFF
    a, b = m.u64(lst + 8 * i), m.u64(lst + 8 * j)
    m.put(lst + 8 * i, 8, b); m.put(lst + 8 * j, 8, a)


@lifted(0x114E98C)
def place_in_battle(m, o, client, idx, dest, w, *_):
    """Move party entry idx of client slot `client` to dest (0x114ea98) when they differ, then vf 0x5d0(w)
    and vf 0x5d8 on it, give it its position (0xc9c090) in the position table [[o+0x10]+0xf0] (+8 by
    position, map +0x60), pair it with the others (0x114eab4) and tail 0x114eb70(o, b)."""
    c = client & 0xFF
    lst = 0 if c > 4 else m.u64(m.u64(o + 0x10) + 0x30) + c * 0x38 + 0x28
    if idx & 0xFF != dest & 0xFF:
        m.call_void(m.main + 0x114EA98, lst, idx, dest)
    b = m.u64(lst + 8 * (idx & 0xFF))
    m.vcall_void(b, 0x5D0, w & M32)
    m.vcall_void(b, 0x5D8)
    pos = m.call(m.main + 0xC9C090, m.u64(m.u64(o + 0x10) + 0x290), client & M32, idx & M32) & M32
    pc = m.u64(o + 0x10)
    table = m.u64(pc + 0xF0)
    ident = m.vcall(b, 0x98) & M32
    with m.frame(0x10) as k:
        m.put(k, 4, ident)
        m.put(table + 8 * (pos & 0xFF) + 8, 4, ident)
        m.put(_map_u8_slot_inline(m, table + 0x60, k), 1, pos)       # 0xf785a8
    m.call_void(m.main + 0x114EAB4, table, pc, pos, m.u64(pc + 0x30))
    return _tail(m, m.main + 0x114EB70, o, b)


@lifted(0x114E7EC)
def place_in_battle_command(m, o, client, idx, dest, w, *_):
    """0x114e98c on [o+0x20], then command 0x16 (client, idx, dest bytes, w & 0xffff)."""
    m.call_void(m.main + 0x114E98C, m.u64(o + 0x20), client, idx, dest, w)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x16, client & 0xFF, idx & 0xFF, dest & 0xFF, w & 0xFFFF)


@lifted(0x114F4D0)
def add_ability_handler(m, o, pc, b, *_):
    """Register b's handler for vf 0x2a8: the counted object [pc+0x190] maps it (vf 0x30) to a key looked up
    in the 211-entry table main+0x44f14d0 ({key, factory}, 16 bytes; entry 0xd2 counts as absent); the
    factory fills a local u32 and returns the handler, which takes a free element of [[o+8]+0xd0]
    (0x119baac) set up as kind 5 (+0x12 0x00ee00ee, +0x20 handler, +0x2c 0x0100 << 16 | vf 0xe0, +0x30
    the value, +0x34 / +0x38 b's id, +0x3c u16 [o+0x80], +0x3e the local, +0x44 1) and linked by priority
    (0x119b6cc)."""
    from pokeldn.sv.battle.engine.lift0 import _release_ref
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


@lifted(0x114E268)
def send_out(m, o, out, args, *_):
    """Send out entry args[1] of client slot args[0] to place args[2]: the slot's start step (0x114ecec on
    a first turn by 0x114e550, else 0x11500d0), triggers 1 / 0x1f for the leaving member and 0x20 for
    *out, the placement 0x114e7ec, then for the entering member its item and ability handlers (0x114f1ec,
    0x114e798), entry handler (0x114e578), 0x114f348, the entered list (0x114e5dc) and mark (0x114e848);
    *out = its id."""
    first = m.call(m.main + 0x114E550, m.call(m.main + 0x114E480, o), m.call(m.main + 0x1482534, o)) & 1
    q = m.call(m.main + 0x1143584, o)
    m.call_void(m.main + (0x114ECEC if first else 0x11500D0), q, m.u8(args))
    lst = m.call(m.main + 0x114E498, o, m.u8(args))
    leaving = m.vcall(m.call(m.main + 0x114E4C0, lst, m.u8(args + 2)), 0x98) & M32
    m.call_void(m.main + 0x114E4E0, o, 1, leaving)
    m.call_void(m.main + 0x114E4E0, o, 0x1F, leaving)
    m.call_void(m.main + 0x114E4E0, o, 0x20, m.u32(out))
    q = m.call(m.main + 0x1143584, o)
    a2, a1, a0 = m.u8(args + 2), m.u8(args + 1), m.u8(args)
    w = m.call(m.main + 0x114E528, o, 0)
    m.call_void(m.main + 0x114E7EC, q, a0, a1, a2, w)
    b = m.call(m.main + 0x114E4C0, m.call(m.main + 0x114E498, o, m.u8(args)), m.u8(args + 1))
    ident = m.vcall(b, 0x98) & M32
    q = m.call(m.main + 0x1143584, o)
    m.call_void(m.main + 0x114F1EC, q, m.call(m.main + 0x1146E90, o), b)
    m.call_void(m.main + 0x114E798, m.call(m.main + 0x1143584, o), m.vcall(b, 0x98) & M32)
    m.call_void(m.main + 0x114E578, m.call(m.main + 0x1143584, o), m.vcall(b, 0x98) & M32)
    m.call_void(m.main + 0x114F348, m.call(m.main + 0x114E480, o), b)
    m.call_void(m.main + 0x114E5DC, m.call(m.main + 0x114E490, m.call(m.main + 0x113DE68, o)), ident)
    m.call_void(m.main + 0x114E848, m.call(m.main + 0x1143584, o), b)
    if m.call(m.main + 0x114E488, m.call(m.main + 0x114E480, o)) & 1:
        x = m.call(m.main + 0x113DF30, m.call(m.main + 0x1482534, o))
        if m.call(m.main + 0x147992C, x, 0) & 1:
            m.call_void(m.main + 0x281C364, m.call(m.main + 0x11468E8, o), ident)
    m.put(out, 4, ident)


@lifted(0x114DC48)
def send_out_all(m, o, *_):
    """Send out every client slot's first members (0..4; per slot as many as its positions, 0xff9128),
    skipping empty or down ones: 0x114e1cc(o, ids, client, i, i) into an id set (0x11466dc), then the
    entry steps 0x114e19c on that set."""
    with m.frame(0x40) as ids:
        m.call_void(m.main + 0x11466DC, ids)
        for c in range(5):
            pc = m.u64(o + 0x10)
            parties = m.u64(pc + 0x30)
            s = m.u64(m.u64(pc + 0x290) + 8)
            n = m.call(m.main + 0xFF9128, m.u32(s + 0x36C), m.u8(s + 0x370), c) & M32
            i = 0
            while i != n:
                if m.u8(parties + 0x38 * c + 0x58) > i & 0xFF:
                    b = m.u64(parties + 0x38 * c + 0x28 + 8 * (i & 0xFF))
                    if b and not m.vcall(b, 0x200) & 1:
                        m.call_void(m.main + 0x114E1CC, o, ids, c, i, i)
                i = (i + 1) & M32
        m.call_void(m.main + 0x114E19C, o, ids)


@lifted(0x113DDD4)
def battle_start(m, o, out, *_):
    """The battle start: clear the start flag ([[o+0x40]+0x28] byte), weather / field and condition start
    messages (0x113dfcc, 0x113df48), send everyone out (0x114dc48); unless the flag got set, event 0x77
    (0x1146b30) and the entered flag 0 (0x113de88); *out = the flag."""
    flag = lambda: m.call(m.main + 0x113DE70, m.call(m.main + 0x113DE68, o))
    m.call_void(m.main + 0x1145AA8, flag())
    m.call_void(m.main + 0x113DFCC, o)
    m.call_void(m.main + 0x113DF48, o)
    m.call_void(m.main + 0x114DC48, o)
    if not m.call(m.main + 0x113DE78, flag()) & 1:
        m.call_void(m.main + 0x1146B30, m.call(m.main + 0x1146E90, o))
    if not m.call(m.main + 0x113DE78, flag()) & 1:
        m.call_void(m.main + 0x113DE88, o)
    m.put(out, 1, m.call(m.main + 0x1145AA0, flag()))


@lifted(0x113DD9C)
def battle_start_of(m, o, *_):
    with m.frame(0x10) as f:
        m.call_void(m.main + 0x113DDD4, m.call(m.main + 0x113DDCC, m.u64(o + 0x18)), f, f + 8)
        return m.u8(f)


@lifted(0x113DD68)
def battle_start_message(m, o, out, *_):
    """0xfaf048 on [o+0x10], then *out = 0x113dd9c(o)."""
    m.call_void(m.main + 0xFAF048, m.u64(o + 0x10))
    m.put(out, 1, m.call(m.main + 0x113DD9C, o))


@lifted(0x113DCA8)
def build_battle_start(m, o, out, size, count, *_):
    """Message kind 17, the battle start: queue reset (length 0, formats from 0x3c6abe4), 0x113dd68 on
    [o+8]; *out = the queue bytes ([o+0x10]+0x70), *size = its length, *count += 1, the start flag at
    o+0xc4a5 and o+0xc4a3 cleared."""
    q = m.u64(o + 0x10)
    m.put(q + 0x68, 8, 0)
    for i, fmt in enumerate(_ROUND_FORMATS):
        m.put(m.call(m.main + 0xFAF09C, q, m.main + 0x3C6ABE4 + 4 * i), 1, fmt)
    with m.frame(0x10) as f:
        m.call_void(m.main + 0x113DD68, m.u64(o + 8), f)
        flag = m.u8(f)
    m.put(out, 8, m.u64(o + 0x10) + 0x70)
    m.put(size, 4, m.u32(m.u64(o + 0x10) + 0x68))
    m.put(count, 8, m.u64(count) + 1)
    m.put(o + 0xC4A5, 1, flag)
    m.put(o + 0xC4A3, 1, 0)


# --- function-local statics: the guards and the constructors they run --------------------------------

@lifted(0x343CF10)
def guard_acquire(m, guard, *_):
    """__cxa_guard_acquire (the SDK's 0x53c49a0, through [0x46ca080]): 0 when byte 0 says built or byte 1
    reads 1 (released); else byte 1 = 2 (in progress) and 1. A guard in progress elsewhere waits on the
    condition variable 0x5b318b8: refused. The guard mutex 0x5b318c0 is taken and given back (no net write)."""
    if m.u8(guard):
        return 0
    b = m.u8(guard + 1)
    if b & 2:
        raise UnliftedCall("guard acquire while another construction is in progress")
    if b == 1:
        return 0
    m.put(guard + 1, 1, 2)
    return 1


def _override(address):
    """Replace an earlier module's registration (it refused a static's first construction)."""
    def register(fn):
        FUNCTIONS[address] = fn
        fn.address = address
        return fn
    return register


@_override(0x2D1FD38)
def static_46d3f08(m, *_):
    """The raid battler class's static [0x46d3f08] (guard [0x46d3f00]), built from 0x1a07aa4 on first use."""
    guard = m.u64(m.main + 0x46D3F00)
    if m.u8(guard) & 1 == 0 and m.call(m.main + 0x343CF10, guard) & M32:
        slot = m.u64(m.main + 0x46D3F08)
        m.put(slot, 8, m.call(m.main + 0x1A07AA4))
        m.call_void(m.main + 0x343CF20, guard)
    return m.u64(m.main + 0x46D3F08)


@_override(0x28024A0)
def static_46e2578(m, *_):
    """The static chain [0x46e2578] -> [0x46d3ab0] -> [0x46d39b8] -> [0x46d39c8] (0), each level under its
    own guard; the outer slot."""
    from pokeldn.sv.battle.engine.lift0 import _static_chain
    _static_chain(m, ((0x46E2570, 0x46E2578), (0x46D3AA8, 0x46D3AB0), (0x46D39B0, 0x46D39B8),
                      (0x46D39C0, 0x46D39C8)))
    return m.u64(m.main + 0x46E2578)
