"""Using a move: the checks before it, the move record, accuracy and hit count, and the steps that run it."""

from pokeldn.sv.battle.engine.calls import M32, M64, _need, _s32, _tail, _vtail
from pokeldn.sv.battle.engine.damage import _slot_level
from pokeldn.sv.battle.engine.data import static_table
from pokeldn.sv.battle.engine.events import _event, _id, _param_record, _value, ev_param, ev_pop, ev_push
from pokeldn.sv.battle.engine.members import _clear_members, _first_party_id, _for_each_member
from pokeldn.sv.battle.engine.messages import _reserve_c9
from pokeldn.sv.battle.engine.references import _counted_vf48
from pokeldn.sv.battle.engine.rules import _rule_side
from pokeldn.sv.battle.engine.targets import _move_field_3
from pokeldn.sv.battle.machine import UnliftedCall, lifted


@lifted(0x28056F0)
def move_class(m, move, *_):
    move &= 0xFFFF
    return {0xC9: 4, 0xF0: 2, 0xF1: 1, 0x102: 3, 0x371: 3, 0x373: 3}.get(move, 0)


@lifted(0x157EEB8)
def queue_move_result(m, o, b, t, v, flag, *_):
    """Tail call of 0x1580450 (flag bit 0) or 0x157ef30 with the queue object, b's id, t and v."""
    q = m.call(m.main + 0x1143584, o, b)
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    target = 0x1580450 if flag & 1 else 0x157EF30
    return _tail(m, m.main + target, q, ident, t, v & 0xFFFFFFFF)


@lifted(0x287A81C)
def set_pp_capped(m, o, i, n, *_):
    """Set the PP of move i of [[o+0x48]+0x70] to n, capped at its maximum (0xbf5fe0 of the move and its
    PP Ups); the tail call of 0xdedf30."""
    acc = m.u64(m.u64(o + 0x48) + 0x70)
    move = m.call(m.main + 0xDEDBC8, acc, i) & 0xFFFFFFFF
    ups = m.call(m.main + 0xBF61D4, acc, i & 0xFFFFFFFF) & 0xFFFFFFFF
    top = m.call(m.main + 0xBF5FE0, move, ups) & 0xFFFFFFFF
    v = top if top & 0xFF < n & 0xFF else n & 0xFFFFFFFF
    return m.call(m.main + 0xDEDF30, acc, i & 0xFFFFFFFF, v)


@lifted(0x2D3B3E8)
def load_moves(m, b, src, reset, *_):
    """Copy the four moves of `src` (vf 0xf0 move, 0x108 / 0x110 / 0x120 its three bytes) into the 0x16-byte
    slots at b+0x426, clearing a slot's u32 at +5 when its move changed (all four when `reset`, which
    also copies each slot's first 9 bytes to +0xa and sets +0x14); the number of moves. vf 0x1a0 / 0x1a8
    save and restore a flag of `src` around it."""
    keep = m.vcall(src, 0x1A0) & 0xFFFFFFFF
    if reset & 1:
        for i in range(4):
            m.put(b + 0x42B + 0x16 * i, 4, 0)
    n = 0
    for i in range(4):
        s = b + 0x426 + 0x16 * i
        move = m.vcall(src, 0xF0, i) & 0xFFFF
        if m.u16(s) != move:
            m.put(s + 5, 4, 0)
        m.put(s, 2, move)
        if move == 0:
            m.put(s + 2, 2, 0)
            v = 0
        else:
            m.put(s + 2, 1, m.vcall(src, 0x108, i))
            m.put(s + 3, 1, m.vcall(src, 0x110, i))
            v = m.vcall(src, 0x120, i)
            n += 1
        m.put(s + 4, 1, v)
    if reset & 1:
        for i in range(4):
            s = b + 0x426 + 0x16 * i
            m.write(s + 0xA, m.read(s, 9))
            m.put(s + 0x14, 1, 1)
    m.vcall_void(src, 0x1A8, keep & 1)
    return n


@lifted(0x1579420)
def fill_entry(m, o, a, entry, src, *_):
    v = m.u16(src + 2)
    if v == 0xFFFF:
        v = m.call(m.main + 0x1579490, m.u64(o + 8))
    m.put(entry + 0xA, 2, v)
    m.call_void(m.main + 0x1579498, m.u64(o + 0x10), a, entry, src)
    m.put(entry + 4, 1, 0); m.put(entry + 9, 1, 1)


@lifted(0x287A73C)
def move_of(m, o, i, *_):
    return m.call(m.main + 0xDEDBC8, m.u64(m.u64(o + 0x48) + 0x70), i)


@lifted(0x157B674)
def move_blocked(m, o, attacker, target, move, *_):
    def cond(c): return m.vcall(target, 0x300, c) & 1
    if cond(0xB) and m.call(m.main + 0x157B7A0, m.u16(move)) & 1:
        return 1
    if cond(7) and m.u16(move) in (0x14F, 0xD4):
        return 1
    if cond(0xE) and m.u16(move) == 0x149:
        return 1
    a = m.vcall(attacker, 0x98) & 0xFFFFFFFF
    t = m.vcall(target, 0x98) & 0xFFFFFFFF
    if cond(0x10) and m.u8(move + 0x12) and m.call(m.main + 0x15C04A4, o, a, t) & 1 == 0:
        return 1
    return 0


@lifted(0x2D3C9E0)
def spend_pp(m, b, i, n, *_):
    """Take n PP from move slot i (current +0x432, floored at 0); a slot flagged at +0x43a also sets
    +0x428 and tells the Pokemon object (slot 0x118)."""
    s = b + 0x16 * (i & 0xFF)
    n &= 0xFF
    if m.u8(s + 0x43A):
        _need(m, m.u64(m.u64(m.u64(b + 0x48)) + 0x118))
    left = (max(m.u8(s + 0x432), n) - n) & 0xFFFFFFFF
    m.put(s + 0x432, 1, left)
    if m.u8(s + 0x43A) == 0:
        return
    m.put(s + 0x428, 1, left)
    return _vtail(m, m.u64(b + 0x48), 0x118, i, left)


@lifted(0x157B7A0)
def move_check_157fc44(m, move, *rest):
    return _tail(m, m.main + 0x157FC44, move, *rest[:6])


@lifted(0x153314C)
def move_kind_8_message(m, o, _x1, ctx, *_):
    """For a move (u16 at [ctx]) whose record field 5 (static 0x46d7948) is 8: when 0x1536cb0 agrees,
    message 0xcb with ([ctx+8]'s id, 0x122, [ctx+0x10]) through 0x1536f5c."""
    from pokeldn.sv.battle.engine.containers import data_record
    if m.u8(m.u64(m.main + 0x46D7940)) & 1 == 0:
        raise UnliftedCall("static 0x46d7948 not built")
    move = m.u16(m.u64(ctx))
    rec = data_record(m, m.u64(m.u64(m.main + 0x46D7948)), move)
    vt = rec - m.s(rec, 4)
    kind8 = m.u16(vt) >= 0xB and m.u16(vt + 0xA) and m.u8(rec + m.u16(vt + 0xA)) == 8
    if kind8:
        for a in (0x1536894, 0x1533CA0, 0x1536CB0, 0x1143584):
            _need(m, m.main + a)
    static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    if not kind8:
        return rec
    k = m.call(m.main + 0x1536894, m.u16(m.u64(ctx)))
    k = m.call(m.main + 0x1533CA0, m.u32(ctx + 0x18), k & 0xFFFFFFFF)
    r = m.call(m.main + 0x1536CB0, o, m.u64(ctx + 8), m.u64(ctx + 0x10), k & 0xFFFFFFFF)
    if r & 1 == 0:
        return r
    owner = m.call(m.main + 0x1143584, o)
    ident = m.vcall(m.u64(ctx + 8), 0x98)
    return _tail(m, m.main + 0x1536F5C, owner, ident & 0xFFFFFFFF, m.u64(ctx + 0x10), 0x122)


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


@lifted(0x14D973C)
def move_flag_5(m, move, *_):
    """Field 5 of the move record (u8 != 0)."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    return int(fb.u8(m, m.call(m.main + 0xBF60CC, table, move & M32), 5) != 0)


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
    from pokeldn.sv.battle.engine.raid import _raid_id
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


def _move_record_byte(m, ident, field):
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


@lifted(0x148268C)
def level_limit(m, rules_owner, level, *_):
    """Byte +0xbb of the level-`level` entry (0xc0 bytes from [x+0x38]+0xc8), 100 past level 4."""
    level &= 0xFF
    if level > 4:
        return 0x64
    return m.u8(m.u64(rules_owner + 0x38) + level * 0xC0 + 0xC8 + 0xBB)


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


@lifted(0x2D326E0)
def move_use_record(m, o, _x1, r, *_):
    """Bookkeeping after a move is chosen (r: +0 flags, +8 battler, +0x10 move {u16 id, u8 type at +8},
    +0x18..+0x1c flags, +0x1e u16 slot move, +0x20 target byte): vf 0x3f8 and command 0x1d when the use
    counts, else the status check; command 0x86 for a typed move outside raids; event 0xf1; command 0x5b
    for both moves."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    from pokeldn.sv.battle.engine.raid import _raid_id
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


@lifted(0x288ADB4)
def run_288b1f8(m, o, a, b, *_):
    with m.frame(0x20) as sp:
        r = sp + 0x10
        m.put(r, 8, b); m.put(r + 8, 8, a)
        x = m.call(m.main + 0x288B1F0, m.u64(o + 0x78))
        return _tail(m, m.main + 0x288B1F8, x, sp + 8, r)


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


def _copy_move_out(m, out, A, S, pos):
    m.put(out + 0x20, 1, pos)
    m.put(out + 0x15, 8, m.u64(A + 0x25))
    m.put(out + 8, 8, m.u64(S)); m.put(out + 0x10, 8, m.u64(S + 8))


@lifted(0x2D32DB0)
def run_chosen_move(m, o, out, r, *_):
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
            from pokeldn.sv.battle.engine.raid import _raid_id
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


@lifted(0x157FD04)
def move_event_cc_of(m, o, a, b, c, *_):
    """0x1581288 on [o+0x78]'s object with {b, a, c}."""
    with m.frame(0x20) as sp:
        r = sp + 8
        m.put(r, 8, b); m.put(r + 8, 8, a); m.put(r + 0x10, 8, c)
        x = m.call(m.main + 0x157FD38, m.u64(o + 0x78))
        return _tail(m, m.main + 0x1581288, x, sp, r)


@lifted(0x2882BA4)
def move_kind_9(m, o, a, b, c, d, e, *_):
    """0x28813c8 on 0x2882bdc([o+0x78]) with {c, b, a, d, e}."""
    with m.frame(0x30) as f:
        for k, v in enumerate((c, b, a, d, e)):
            m.put(f + 8 + 8 * k, 8, v)
        m.call_void(m.main + 0x28813C8, m.call(m.main + 0x2882BDC, m.u64(o + 0x78)), f, f + 8)


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


@lifted(0x1579A58)
def move_field_21_step(m, o, a, b, c, *_):
    """0x1580c40 on 0x1579a90([o+0x78]) with {a, b, c}; its result byte."""
    with m.frame(0x20) as f:
        m.put(f + 8, 8, a); m.put(f + 0x10, 8, b); m.put(f + 0x18, 8, c)
        m.call_void(m.main + 0x1580C40, m.call(m.main + 0x1579A90, m.u64(o + 0x78)), f, f + 8)
        return m.u8(f)


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
