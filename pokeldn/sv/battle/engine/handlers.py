"""The effect handlers the event dispatcher runs: their checks on an attacker and a target, and their
bodies, which read the event frame and write its records."""

from pokeldn.sv.battle.engine.battler import _battler_of
from pokeldn.sv.battle.engine.calls import M32, _need, _tail, _vtail
from pokeldn.sv.battle.engine.damage import scale_table_entry
from pokeldn.sv.battle.engine.events import (
    _bump_inc, _bump_record, _entry_c, _entry_id, _id_at, _mark_pending, _owner_id, _t78,
)
from pokeldn.sv.battle.engine.slots import within_side
from pokeldn.sv.battle.machine import UnliftedCall, lifted


def _at_99(m, o, b):
    """Within its side's room and answering 99 to vf 0xf8."""
    return within_side(m, m.u64(o + 0xF0), o, m.vcall(b, 0x98)) & 1 and m.vcall(b, 0xF8) & 0xFFFF == 99


@lifted(0x157C614)
def protected_from(m, o, attacker, target, *_):
    """1 unless the target has flag 0x1a (vf 0x4d0); then by conditions 0x1d, 0x1e (bound to the
    target) on the attacker and 0x2d on the target."""
    if m.vcall(target, 0x4D0, 0x1A) & 1:
        return 0
    if _at_99(m, o, attacker) or _at_99(m, o, target) or m.vcall(attacker, 0x220, 0x1D) & 1:
        return 1
    if m.vcall(attacker, 0x220, 0x1E) & 1:
        bound = m.vcall(attacker, 0x238, 0x1E) & 0xFF
        if m.vcall(target, 0x98) & 0xFFFFFFFF == bound:
            return 1
    return m.vcall(target, 0x220, 0x2D)


@lifted(0x113FA64)
def round_check(m, o, out, *_):
    """*out = whether the six-record pass (0x113fb60 then 0x113fcc8) found anything to do; only in
    battle modes 0 and 1 with +0x706 clear."""
    m.put(out, 1, 0)
    setup = m.u64(m.u64(o + 8) + 0x38)
    if m.u32(setup + 0x30) > 1 or m.u8(setup + 0x706):
        return
    with m.frame(0x60) as recs:
        for i in range(6):
            m.write(recs + 0x10 * i, bytes(0xD) + b"\x01")
        m.call_void(m.main + 0x113FB60, o, recs)
        if not any(m.u32(recs + 0x10 * i) for i in range(6)):
            return
        if m.call(m.main + 0x113FC80, o) & 1:
            m.call_void(m.main + 0x114221C, o)
        m.put(out, 1, m.call(m.main + 0x113FCC8, o, recs) & 1)


@lifted(0x288BC10)
def handler_288bc10(m, o, done, args, *_):
    m.put(done, 1, 0)
    b, ctx = m.u64(args), m.u64(args + 8)
    if m.vcall(b, 0x220, 0x26) & 1 == 0 or m.u8(ctx + 8) != 9:
        return
    v = m.vcall(m.u64(args), 0x140) & 0xFFFF
    v = m.call(m.main + 0x1769890, m.call(m.main + 0x1533CA0, v, 0x19), 1) & 0xFFFFFFFF
    m.call_void(m.main + 0x288BCDC, o, m.u64(args), m.u64(args + 8))
    if m.call(m.main + 0x288BD44, o, m.u64(args), v) & 1:
        m.call_void(m.main + 0x288BD80, o, m.u64(args), v)
        m.call_void(m.main + 0x288BE08, o, m.u64(args))
    m.put(done, 1, 1)


@lifted(0x288BE44)
def handler_288be44(m, o, done, args, *_):
    m.put(done, 1, 0)
    b = m.u64(args)
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    kind = m.u16(args + 8)
    if (kind - 0x206) & 0xFFFFFFFF > 2:
        return
    sub = m.u8(args + 0xA)
    if m.vcall(b, 0x510, 10) & 1 or m.vcall(b, 0x5C8) & 1:
        return
    with m.frame(0x50) as f:
        found = f + 0x4C
        m.put(found, 4, 0)
        m.call_void(m.main + 0x288BF94, o, f + 8, found, ident, kind, sub)
        if m.u32(found) == 0:
            return
        target = m.u8(m.call(m.main + 0x288C100, o, m.u64(f + 8)))
    other = m.call(m.main + 0x13813F4, o, target)
    m.vcall_void(b, 0x508, 10)
    m.vcall_void(other, 0x5B8, ident, kind)
    m.call_void(m.main + 0x281C698, m.call(m.main + 0x1149340, o), target, 0)
    m.call_void(m.main + 0x2882F60, m.call(m.main + 0x1143584, o), ident, 0x16B, ident, target)
    m.put(done, 1, 1)


@lifted(0x1832E44)
def out_or_1f8(m, o, done, args, *_):
    """*done = 1 when the battler (args[0]) is not able (vf 0x208) or vf 0x1f8 holds."""
    m.put(done, 1, 0)
    if m.vcall(m.u64(args), 0x208) & 1 == 0 or m.vcall(m.u64(args), 0x1F8) & 1:
        m.put(done, 1, 1)


@lifted(0x1872D20)
def handler_1872d20(m, o, done, args, *_):
    m.put(done, 1, 0)
    if m.vcall(m.u64(args), 0x220, 0xF) & 1 == 0:
        return
    if m.u8(args + 8):
        q = m.call(m.main + 0x1143584, o)
        a = m.vcall(m.u64(args), 0x98) & 0xFFFFFFFF
        b = m.vcall(m.u64(args), 0x98) & 0xFFFFFFFF
        m.call_void(m.main + 0x157EBA0, q, a, 0x11D, b)
    m.put(done, 1, 1)


@lifted(0x2D1B240)
def count_218(m, o, ident, *_):
    """When entry +0x20 has id `ident` and entry +0x210 is kind 0xb: count up entry +0x218 (state +0xa
    below 2), moving state 1 to 2."""
    t = m.u64(m.u64(o + 0x38) + 0x78)
    if _entry_c(m, t, 0x20) != ident & 0xFFFFFFFF:
        return
    e = m.u64(t + 0x210)
    if e == 0 or m.u32(e + 0xC) != 0xB:
        return
    e = m.u64(t + 0x218)
    if e == 0 or m.u8(e + 0xA) > 1:
        return
    m.put(e + 0xC, 4, m.u32(e + 0xC) + 1)
    if m.u8(e + 0xA) == 1:
        m.put(e + 0xA, 1, 2)


@lifted(0x2D1A640)
def set_2d0(m, o, ident, *_):
    """When entry +0x20 has id `ident`: set +0xc of entry +0x2d0 (state +0xa below 2) to 1, moving
    state 1 to 2."""
    t = m.u64(m.u64(o + 0x38) + 0x78)
    if _entry_c(m, t, 0x20) != ident & 0xFFFFFFFF:
        return
    e = m.u64(t + 0x2D0)
    if e == 0 or m.u8(e + 0xA) > 1:
        return
    m.put(e + 0xC, 4, 1)
    if m.u8(e + 0xA) == 1:
        m.put(e + 0xA, 1, 2)


@lifted(0x1832E08)
def run_1832e44(m, o, b, *_):
    with m.frame(0x10) as f:
        m.put(f + 8, 8, b)
        x = m.call(m.main + 0x1361214, o, b)
        x = m.call(m.main + 0x1832E3C, x, b)
        m.call_void(m.main + 0x1832E44, x, f, f + 8)
        return m.u8(f)


def _damage_request(m, o, ident, other, amount, kind, flags, code):
    """The 0x40-byte request 0x1807960 takes (byte +0xb and +0x3c.. are left as the stack holds them)."""
    with m.frame(0x40) as r:
        m.put(r, 4, ident); m.put(r + 4, 4, other)
        m.put(r + 8, 2, amount); m.put(r + 0xA, 1, kind)
        m.put(r + 0xC, 4, ident); m.write(r + 0x10, bytes(flags))
        m.put(r + 0x14, 4, 0xA0A0000); m.put(r + 0x18, 4, code); m.put(r + 0x1C, 4, other)
        m.write(r + 0x20, bytes(0x1C))
        m.call_void(m.main + 0x1807960, o, r)


@lifted(0x2852CA0)
def chip_2852ca0(m, o, ident, *_):
    """When entry +0x28 is `ident`, entry +0x270 is inactive and entry +0x320 active: request 0x82008f
    against the battler of entry +0x20 (if it is still in) for 1/8 of its vf 0x140, at least 1."""
    ident &= 0xFFFFFFFF
    t = m.u64(m.u64(o + 0x38) + 0x78)
    if _entry_id(m, t, 0x28) != ident or _entry_id(m, t, 0x270) or not _entry_id(m, t, 0x320):
        return
    other = _entry_id(m, t, 0x20)
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 8) + 0x30), other)
    if m.vcall(b, 0x200) & 1:
        return
    move = m.call(m.main + 0x283D5F0, o) & 0xFFFF
    kind = 0x14 if move == 0x18 else (0x15 if move == 0xA0 else 0)
    v = m.vcall(b, 0x140)
    amount = (v >> 3) & 0x1FFF if v & 0xFFFF >= 8 else 1
    _damage_request(m, o, ident, other, amount, kind, (0, 1, 1, 0), 0x82008F)


@lifted(0x2852DF0)
def chip_2852df0(m, o, ident, *_):
    """When entry +0x28 is `ident`, entry +0x320 active and battler `ident` out (vf 0x200): request
    0x820087 against the battler of entry +0x20 for 1/4 of its vf 0x140, at least 1."""
    ident &= 0xFFFFFFFF
    t = m.u64(m.u64(o + 0x38) + 0x78)
    if _entry_id(m, t, 0x28) != ident or not _entry_id(m, t, 0x320):
        return
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 8) + 0x30), ident)
    if m.vcall(b, 0x200) & 1 == 0:
        return
    other = _entry_id(m, m.u64(m.u64(o + 0x38) + 0x78), 0x20)
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 8) + 0x30), other)
    v = m.vcall(b, 0x140)
    amount = (v >> 2) & 0x3FFF if v & 0xFFFF >= 4 else 1
    _damage_request(m, o, ident, other, amount, 0x16, (1, 1, 1, 0), 0x820087)


@lifted(0x285A680)
def set_b8_kind(m, o, ident, value, *_):
    """[o+0x48]+0x48 = 1 when entry +0x18 is `ident`, entry +0xb8 is idle (0x16962f0 zero) and its state
    (+0xa) is below 2: its +0xc takes `value` (u8) and state 1 becomes 2. 0 otherwise."""
    m.put(m.u64(o + 0x48) + 0x48, 4, 0)
    t = m.u64(m.u64(o + 0x38) + 0x78)
    if _entry_id(m, t, 0x18) != ident & 0xFFFFFFFF:
        return
    if m.call(m.main + 0x16962F0, o) & 0xFF:
        return
    e = m.u64(m.u64(m.u64(o + 0x38) + 0x78) + 0xB8)
    done = 0
    if e and m.u8(e + 0xA) <= 1:
        m.put(e + 0xC, 4, value & 0xFF)
        if m.u8(e + 0xA) == 1:
            m.put(e + 0xA, 1, 2)
        done = 1
    m.put(m.u64(o + 0x48) + 0x48, 4, done)


@lifted(0x285A740)
def set_b8_kind_11(m, o, ident, *_):
    return set_b8_kind(m, o, ident, 0x11)


# @lifted(0x283E66C)  waits for a callee lifted elsewhere
def handler_283e66c(m, o, done, args, *_):
    """*done = 0x288426c's bit for the battler args[0] (u32 id) unless it is out (vf 0x200)."""
    m.put(done, 1, 0)
    b = m.call(m.main + 0x13813F4, o, m.u32(args))
    if m.vcall(b, 0x200) & 1:
        return
    q = m.call(m.main + 0x1143584, o)
    m.put(done, 1, m.call(m.main + 0x288426C, q, m.u32(args)) & 1)


@lifted(0x1605774)
def handler_1605774(m, o, done, args, *_):
    """Stat change handler: raise stat args[1] (u8 +8, not 4) of battler args[0] by at most +9 steps as
    vf 0x690 allows, through vf 0x6d0 and command 5, when the rule checks (0x1142e68) pass."""
    m.put(done, 1, 0)
    if m.u8(args + 8) == 4:
        return
    flags = m.u64(m.u64(m.u64(o + 8) + 0x38) + 0x498)
    if flags >> 10 & 1:
        if m.call(m.main + 0x1142E68, m.u64(o + 8), m.u64(o + 0x10), m.u64(args)) & 1 == 0:
            return
        flags = m.u64(m.u64(m.u64(o + 8) + 0x38) + 0x498)
    if flags >> 33 & 1:
        if m.call(m.main + 0x1142E68, m.u64(o + 8), m.u64(o + 0x10), m.u64(args)) & 1 == 0:
            return
    b = m.u64(args)
    want = m.u8(args + 9)
    v = m.vcall(b, 0x690, m.u8(args + 8)) & 0xFFFFFFFF
    n = want if m.u8(args + 9) < v & 0xFFFF else v
    if n & 0xFF == 0:
        return
    stat = m.u8(args + 8)
    q = m.u64(o + 0x20)
    ident = m.vcall(m.u64(args), 0x98) & 0xFFFFFFFF
    t = m.call(m.main + 0xF21C94, m.u64(m.u64(m.u64(q + 0x20) + 0x10) + 0x30), ident)
    m.vcall_void(t, 0x6D0, stat, n)
    m.call_void(m.main + 0x119AFF0, m.u64(q + 0x18), 5, ident, stat, n & 0xFF)
    m.put(done, 1, 1)


@lifted(0x284FE80)
def boost_at_third_hp(m, o, ident, *_):
    """Tail call of 0x284fe90 with kind 9: when entry +0x20 is `ident`, its battler is at or below a
    third of its max HP (0x17286d0) and entry +0xb8 holds kind 9, entry 0x38 scales by 0x1800/4096."""
    ident &= 0xFFFFFFFF
    t = m.u64(m.u64(o + 0x38) + 0x78)
    if _entry_id(m, t, 0x20) != ident:
        return
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 8) + 0x30), ident)
    lim = m.call(m.main + 0x17286D0, m.vcall(b, 0x110) & 0xFFFF, 3) & 0xFFFFFFFF
    if lim < m.vcall(b, 0x108) & 0xFFFF:
        return
    if m.call(m.main + 0x16962F0, o) & 0xFF != 9:
        return
    scale_table_entry(m, m.u64(o + 0x38), 0x38, 0x1800)


@lifted(0x14A07E0)
def handler_14a07e0(m, o, args, *_):
    """For args[0]'s battler: tail call of 0x14a0860 (its id, vf 0x700 of the u16 args+8) when that
    value is 0..3."""
    if args == 0 or m.u64(args) == 0:
        return
    b = m.u64(args)
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    k = m.vcall(m.u64(args), 0x700, m.u16(args + 8)) & 0xFFFFFFFF
    if k & 0xFF > 3:
        return
    return _tail(m, m.main + 0x14A0860, m.u64(o + 0x20), ident, k)


@lifted(0x2844C10)
def mark_pending_248(m, o, ident, key, *_):
    root = m.u64(m.u64(o + 0x38) + 0x78)
    if _owner_id(m, o, 0x28) != ident & 0xFFFFFFFF:
        return 0
    p = m.u64(root + 0xF8)
    if (m.u32(p + 0xC) if p else 0) & 0xFFFF != key & 0xFFFF:
        return 0
    return _mark_pending(m, m.u64(root + 0x248))


@lifted(0x2D1A5F0)
def mark_pending_298(m, o, ident, *_):
    if _owner_id(m, o, 0x18) == ident & 0xFFFFFFFF:
        _mark_pending(m, m.u64(m.u64(m.u64(o + 0x38) + 0x78) + 0x298))


def _boost_if_kind(m, o, ident, kind):
    """0x2853510: when the owner id matches and the action kind (0x16962f0) is `kind` with a nonzero
    [[o+0x48]+0x48], tail-calls 0x1353738([o+0x38], 0x34, 0x1333)."""
    if _owner_id(m, o, 0x20) != ident & 0xFFFFFFFF:
        return
    if m.call(m.main + 0x16962F0, o) & 0xFF != kind & 0xFF:
        return
    if m.u32(m.u64(o + 0x48) + 0x48) == 0:
        return
    m.call_void(m.main + 0x1353738, m.u64(o + 0x38), 0x34, 0x1333)


@lifted(0x285A750)
def boost_if_kind_11(m, o, ident, *_):
    _boost_if_kind(m, o, ident, 0x11)


@lifted(0x28680A0)
def boost_if_flag_4(m, o, ident, *_):
    """When the owner id matches and the battler named at +0x28 has vf 0x4d0(4), tail-calls
    0x1353738([o+0x38], 0x38, 0x2000)."""
    from pokeldn.sv.battle.engine.containers import battler
    if _owner_id(m, o, 0x20) != ident & 0xFFFFFFFF:
        return
    b = battler(m, m.u64(m.u64(o + 8) + 0x30), _owner_id(m, o, 0x28))
    if m.vcall(b, 0x4D0, 4) & 1:
        return _tail(m, m.main + 0x1353738, m.u64(o + 0x38), 0x38, 0x2000)


@lifted(0x2872E70)
def kind_3_2872d60(m, o, a, *_):
    return _tail(m, m.main + 0x2872D60, o, a, 3)


@lifted(0x284DF10)
def kind_2_284de20(m, o, a, *_):
    return _tail(m, m.main + 0x284DE20, o, a, 2)


@lifted(0x284DE20)
def boost_once(m, o, a, k, *_):
    """When 0x283d6a0(o, 4) is `a`, the byte of [root+0xe0]'s id is k, and neither record +0x268 nor
    record 0x64 (k == 1) / 0x65 is set: 0x1353738([o+0x38], 0x38, 0x800, or 0xaac when 0x144b6d4 is
    nonzero), then mark that record pending."""
    k &= 0xFF
    if a & 0xFFFFFFFF != m.call(m.main + 0x283D6A0, o, 4) & 0xFF:
        return
    root = m.u64(m.u64(o + 0x38) + 0x78)
    if _owner_id(m, o, 0xE0) & 0xFF != k:
        return
    p = m.u64(root + 0x268)
    if p and m.u32(p + 0xC):
        return
    idx = 0x64 if k == 1 else 0x65
    p = m.u64(root + 8 * idx + 8)
    if p and m.u32(p + 0xC):
        return
    v = 0x800 if m.call(m.main + 0x144B6D4, m.u64(o + 8)) & 0xFFFFFFFF == 0 else 0xAAC
    m.call_void(m.main + 0x1353738, m.u64(o + 0x38), 0x38, v)
    _mark_pending(m, m.u64(m.u64(m.u64(o + 0x38) + 0x78) + 8 * idx + 8))


@lifted(0x286F330)
def post_82010c(m, o, ident, *_):
    """When the u32 +0xc of [[[o+0x38]+0x78]+0x20] (0 when null) is ident: 0x1807920 with the record
    {0, 0, 0x82010c, ident, zeros}."""
    x = m.u64(m.u64(m.u64(o + 0x38) + 0x78) + 0x20)
    if (m.u32(x + 0xC) if x else 0) != ident & 0xFFFFFFFF:
        return o
    with m.frame(0x30) as p:
        m.write(p, bytes(0x30))
        m.put(p + 8, 4, 0x82010C); m.put(p + 0xC, 4, ident)
        return m.call(m.main + 0x1807920, o, p)


@lifted(0x287F878)
def notify_287f878(m, o, ident, *_):
    """Event 6 when 0x1589a40(o, ident) (x1 passes through) is the byte +0x95 of [o+8], else event 7
    unless 0x1142ecc allows it: vf 0x48(event, 1) on the counted handle 0x1142424([o+8]) gives,
    released after."""
    v = m.call(m.main + 0x1589A40, o, ident)
    w = m.call(m.main + 0x149FE8C, m.u64(o + 8))
    if w & 0xFF == v & 0xFF:
        event = 6
    else:
        r = m.call(m.main + 0x1142ECC, m.call(m.main + 0x13813EC, m.u64(o + 0x10)), v & 0xFFFFFFFF,
                   w & 0xFFFFFFFF)
        if r & 1:
            return r
        event = 7
    with m.frame(0x10) as p:
        m.call_sret(m.main + 0x1142424, p, m.u64(o + 8))
        ref = m.u64(p)
    m.vcall_void(ref, 0x48, event, 1)
    if ref == 0:
        return 0
    c = m.u32(ref + 0x28)
    m.put(ref + 0x28, 4, c - 1)
    if c == 1:
        return _vtail(m, ref, 0x10)
    if c == 0:
        raise UnliftedCall("DecrementReference abort: count underflow")
    return ref


@lifted(0x183F070)
def apply_183f070(m, o, rec, *_):
    """0x183f0ac on [[o+0x28]+0xf80] with a local done flag, which it returns."""
    with m.frame(0x10) as p:
        m.call_void(m.main + 0x183F0AC, m.u64(m.u64(o + 0x28) + 0xF80), p, rec)
        return m.u8(p)


@lifted(0x1872CE0)
def check_1640(m, o, b, *_):
    with m.frame(0x18) as p:
        m.put(p + 8, 8, b); m.put(p + 0x10, 1, 0)
        q = m.call(m.main + 0x1872D18, m.call(m.main + 0x1361214, o))
        m.call_void(m.main + 0x1872D20, q, p, p + 8)
        return m.u8(p)


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


@lifted(0x287DD04)
def holder_weather_1_or_6(m, o, holder, *_):
    with m.frame(0x10) as p:
        m.put(p, 4, m.vcall(holder, 0x98))
        x = m.call(m.main + 0x116EBB4, m.call(m.main + 0x1361214, o))
        m.call_void(m.main + 0x116EBBC, x, p + 8, p)
        return m.call(m.main + 0x14C7890, m.u8(p + 8)) & 1


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


@lifted(0x284F540)
def weather_scales_38(m, o, ident, *_):
    """For the event's actor `ident` under a weather 0x14c7890 accepts: 0x1353738([o+0x38], 0x38,
    0x2000)."""
    if _id_at(m, _t78(m, o), 0x18) != ident & M32:
        return
    if m.call(m.main + 0x14C7890, m.call(m.main + 0x14C78D0, o, ident)) & 1 == 0:
        return
    return _tail(m, m.main + 0x1353738, m.u64(o + 0x38), 0x38, 0x2000)


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
