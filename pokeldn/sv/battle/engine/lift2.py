"""Lifted battle server functions, batch 2 (moved to their topic module once reviewed)."""

from pokeldn.sv.battle.machine import FUNCTIONS, Pair, UnliftedCall, lifted
from pokeldn.sv.battle.engine.containers import battler


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


def _vtail(m, obj, slot, *args):
    return _tail(m, m.u64(m.u64(obj) + slot), obj, *args)


def _main_battler(m, o, ident):
    return battler(m, m.u64(m.u64(o + 0x10) + 0x30), ident)


@lifted(0x14C7890)
def is_1_or_6(m, v, *_): return int(v & 0xFF in (1, 6))


@lifted(0x114B1D4)
def u16_at_0(m, p, *_): return m.u16(p)


@lifted(0x17CE3AC)
def low7_of_2(m, p, *_): return int(m.u8(p + 2) & 0x7F != 0)


@lifted(0x1149380)
def entry_of_five(m, o, i, *_):
    i &= 0xFF
    return m.u64(o + 8 + 8 * i) if i < 5 else 0


@lifted(0x11494E8)
def set_entry_of_five(m, o, i, v, *_):
    i &= 0xFF
    if i < 5:
        m.put(m.u64(m.u64(o + 0x10) + 0x210) + 8 + 8 * i, 8, v & 0xFFFFFFFF)


def _kind(kind, address):
    def fn(m, out, *_):
        m.put(out, 4, kind)
        return m.main + address
    return fn


# Type descriptors: store a kind, return a rodata address. (function, kind, address)
for _addr, _kind_v, _ret in ((0x2D18260, 1, 0x44FAC10), (0x2D187A0, 1, 0x44FAF00), (0x2D17240, 3, 0x44FA8A0),
                             (0x2D17840, 1, 0x44F9750), (0x2D180E0, 1, 0x44FAA40)):
    lifted(_addr)(_kind(_kind_v, _ret))


@lifted(0x139B698)
def current_c4_entry(m, o, *_):
    base = m.u64(m.u64(o + 0x40) + 8)
    return base + m.u8(base + 0x938) * 0xC4 + 8


@lifted(0x1143AB8)
def battler_set_5a0(m, o, ident, i, v, *_):
    b = _main_battler(m, o, ident)
    return _vtail(m, b, 0x530, i & 0xFFFFFFFF, v & 0xFFFFFFFF)


@lifted(0x183F194)
def battler_4f8(m, o, ident, a, b2, *_):
    b = _main_battler(m, o, ident)
    return _vtail(m, b, 0x4F8, a & 0xFFFFFFFF, b2)


@lifted(0x288CE48)
def battler_398(m, o, ident, *_):
    return _vtail(m, _main_battler(m, o, ident), 0x398)


@lifted(0x14375B4)
def battler_4a0(m, o, ident, *_):
    b = _main_battler(m, o, ident)
    if b == 0:
        return
    return _vtail(m, b, 0x4A0)


@lifted(0x2D3BAE0)
def species_402_406(m, b, *_):
    p = m.u64(b + 0x700)
    return m.u16(b + 0x402) if p and m.u32(p + 0xB8) else m.u16(b + 0x406)


@lifted(0x1381400)
def has_id(m, o, ident, *_): return int(m.call(m.main + 0x1381420, o, ident) & 0xFF != 10)


@lifted(0x114A934)
def first_byte_of_2a0(m, o, *_):
    with m.frame(0x10) as p:
        m.call_void(m.main + 0x113FA64, m.call(m.main + 0x114A964, m.u64(o + 0x78)), p, p + 8)
        return m.u8(p)


@lifted(0x1820E4C)
def next_serial(m, o, out, *_):
    v = m.u32(o + 8)
    if v == 0:
        v = 1
        m.put(o + 8, 4, 1)
    m.put(out, 4, v)
    m.put(o + 8, 4, m.u32(o + 8) + 1)


@lifted(0x114E498)
def entry_38(m, o, i, *_):
    i &= 0xFF
    return 0 if i > 4 else m.u64(m.u64(o + 0x10) + 0x30) + i * 0x38 + 0x28


@lifted(0x2D14150)
def clear_core_48(m, b, *_): m.put(m.u64(b + 0x48) + 0x48, 4, 0)


@lifted(0x10E2474)
def copy_5(m, dst, src, *_):
    m.put(dst, 4, m.u32(src)); m.put(dst + 4, 1, m.u8(src + 4))


@lifted(0x15808D0)
def init_0x19(m, p, *_):
    m.write(p, bytes(0x18)); m.put(p + 0x18, 1, 1)


@lifted(0x2880944)
def clear_0x24b(m, p, *_): m.write(p, bytes(0x24))


@lifted(0xF53840)
def static_4765a30(m, *_):
    """A function-local static, built on first use; the engine only reads one already built."""
    if m.u8(m.main + 0x4765A38) & 1 == 0:
        raise UnliftedCall("static 0x4765a30 not built")
    return m.main + 0x4765A30


@lifted(0x2D1FF04)
def static_46dcd58(m, *_):
    """A function-local static (guard and storage reached through the GOT); read only once built."""
    if m.u8(m.u64(m.main + 0x46DCD50)) & 1 == 0:
        raise UnliftedCall("static 0x46dcd58 not built")
    return m.u64(m.main + 0x46DCD58)


@lifted(0x284DB90)
def handler_with_key(m, o, ident, key, *_):
    """The first kind-2 handler of `ident` whose u16 (0xf7bb74) is `key`, or 0."""
    owner = m.call(m.main + 0x114C158, o)
    h = m.call(m.main + 0x119B478, owner, 2, ident & 0xFF)
    while h and m.call(m.main + 0xF7BB74, h) & 0xFFFF != key & 0xFFFFFFFF:
        h = m.call(m.main + 0x1155BDC, owner, h, 0)
    return h


@lifted(0x13DC030)
def release_matching(m, o, pokemon, key, *_):
    """Walk the kind-0 handlers of the Pokemon's id (0x119b478 over [[o+8]+0xd0]) and, for each one
    whose u16 +0x30 is `key`, +0x68 clear and +0x44 set, release it (+0x3f clear) or retire it."""
    table = m.u64(m.u64(o + 8) + 0xD0)
    cur = m.call(m.main + 0x119B478, table, 0, m.vcall(pokemon, 0x98) & 0xFFFFFFFF)
    while cur:
        kind, ident = m.u8(cur + 0x28), m.u32(cur + 0x34)
        nxt = cur
        while True:
            nxt = m.call(m.main + 0xF7BA54, m.u64(nxt + 8), m.u16(nxt + 0x14))
            if nxt == 0 or (m.u8(nxt + 0x28) == kind and m.u32(nxt + 0x34) == ident
                            and m.u8(nxt + 0x41) == 0):
                break
        if m.u16(cur + 0x30) == key & 0xFFFF and m.u32(cur + 0x68) == 0 and m.u8(cur + 0x44):
            if m.u8(cur + 0x3F) == 0:
                m.call_void(m.main + 0x13608E0, m.u64(m.u64(o + 8) + 0xD0), cur)
            else:
                m.call_void(m.main + 0x1360CDC, cur, 1)
        cur = nxt




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


@lifted(0x15F9F38)
def check_kind_4(m, o, flag, a, b, kind, result, *_):
    m.put(flag, 1, 0)
    kind &= 0xFF
    result &= 0xFFFFFFFF
    with m.frame(0x30) as p:
        if result & 0xFF == 0:
            if kind == 4:
                m.put(p, 8, b); m.put(p + 8, 1, 1)
                q = m.call(m.main + 0x15FA02C, m.call(m.main + 0x1361214, o))
                m.call_void(m.main + 0x15FA034, q, p + 0x20, p)
                if m.u8(p + 0x20) == 0:
                    return 7
            return 0
        if kind == 4:
            m.put(p, 8, b); m.put(p + 8, 1, 0)
            q = m.call(m.main + 0x15FA02C, m.call(m.main + 0x1361214, o))
            m.call_void(m.main + 0x15FA034, q, p + 0x20, p)
            if m.u8(p + 0x20) and m.call(m.main + 0x15FA528, m.u64(o + 0x38), a, b) & 1 == 0:
                m.put(flag, 1, 1)
                return 0
        return result


@lifted(0x113F4F8)
def settle_state(m, o, *_):
    r = m.call(m.main + 0x113F5B8, m.call(m.main + 0x114E480, o))
    if r & 1:
        return r
    if m.call(m.main + 0x113F630, m.call(m.main + 0x113F5B0, m.call(m.main + 0x1482534, o))) & 1 == 0:
        e = m.call(m.main + 0x113F5B0, m.call(m.main + 0x1482534, o))
        r = m.call(m.main + 0x113F5C8, e, 0)
        if r & 0xFF == 0:
            return r
    a = m.call(m.main + 0x114E480, o)
    flag = m.call(m.main + 0x114E550, a, m.call(m.main + 0x1482534, o)) & 1
    x = m.call(m.main + 0x1143584, o)
    m.call_void(m.main + (0x1148C58 if flag else 0x114C994), x)
    m.call_void(m.main + 0x113F5F0, o)
    p = m.call(m.main + 0x113DE70, m.call(m.main + 0x113DE68, o))
    m.put(p, 1, 2)   # tail call to 0x113fa5c, a byte store returning its pointer
    return p


@lifted(0x28858AC)
def push_pair(m, o, a, b, *_):
    with m.frame(0x20) as p:
        m.put(p, 1, 0)
        m.put(p + 8, 4, a); m.put(p + 0xC, 4, b)
        m.put(p + 0x10, 2, 0); m.put(p + 0x12, 1, 0); m.put(p + 0x14, 2, 0)
        return _tail(m, m.main + 0x121BDB0, m.call(m.main + 0x114E520, m.u64(o + 0x78)), p, p + 8)


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


def _static_46d3f08(m):
    """The address of the static built by 0x1a07aa4; the engine only reads one already built."""
    if m.u8(m.u64(m.main + 0x46D3F00)) & 1 == 0:
        raise UnliftedCall("static 0x46d3f08 not built")
    return m.u64(m.main + 0x46D3F08)


def _has_static(m, obj):
    """Whether the list returned by the first virtual of the subobject at +0x28 holds that static."""
    node = m.vcall(obj + 0x28, 0)
    target = _static_46d3f08(m)
    while node:
        if node == target:
            return True
        node = m.u64(node)
    return False


@lifted(0x11502BC)
def mark_flagged(m, o, *_):
    if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49A) >> 1 & 1 == 0:
        return
    with m.frame(0xC0) as p:
        it = p + 0x10
        m.call_void(m.main + 0x1143D84, it)
        m.put(p + 8, 8, it)
        m.call_void(m.main + 0x1143DF0, m.call(m.main + 0x1143DE8, m.u64(o + 0x78)), p, p + 8)
        m.call_void(m.main + 0x1143D7C, it)
        pk = m.call(m.main + 0x158003C, it)
        while pk:
            if m.call(m.main + 0x1142E68, m.u64(o + 8), m.u64(o + 0x10), pk) & 1 == 0 and _has_static(m, pk):
                if m.call(m.main + 0x1680124, pk) & 1 and m.vcall(pk, 0x510, 0x19) & 1:
                    t = m.u64(o + 0x20)
                    m.call_void(m.main + 0x115044C, t, m.vcall(pk, 0x98) & 0xFFFFFFFF)
                    t = m.u64(o + 0x20)
                    m.call_void(m.main + 0x115043C, t, m.vcall(pk, 0x98) & 0xFFFFFFFF)
            pk = m.call(m.main + 0x158003C, it)


@lifted(0x1533284)
def flag_type_match(m, o, pk, move, *_):
    if not _has_static(m, pk):
        return
    f714 = m.u8(pk + 0x714)
    if f714 == 0 and m.vcall(pk, 0x4D0, 0x1C) & 1 == 0:
        return
    b = m.u8(pk + 0x715)
    t = m.u8(move + 8)
    expect = b if b < 0x13 else 0x12     # the table at 0x3c630a1 (step 2) maps 0..0x12 to itself
    if t == 0x12 or t != expect:
        if b != 0x63:
            return
        r = m.call(m.main + 0x2D2219C, pk, t, m.u16(move))
        if r & 0xFF == 0x12:
            return
        shift = 0x1F if r & 0xFF == 0x63 else r & 0x1F
        if m.u32(pk + 0x71C) >> shift & 1:
            return
    base = m.u64(m.u64(o + 0x40) + 8)
    m.put(base + m.u8(base + 0x938) * 0xC4 + 0x1F, 1, 1)


@lifted(0x2D1F784)
def has_type(m, b, t, *_):
    t &= 0xFF
    if t == 0x12:
        return 0
    r = m.vcall(b, 0x220, 0x19) & 1
    c1, c2 = m.u8(b + 0x40A), m.u8(b + 0x40B)
    a = c1 == 0x12 or (r and c1 == 2)
    z = c2 == 0x12 or (r and c2 == 2)
    if m.vcall(b, 0x4D0, 0x17) & 1:
        if not a:
            if z:
                c2 = c1
        elif not z:
            c1 = c2
        else:
            c1 = c2 = 0x12
    elif a:
        c1 = c2 = 0 if z else c2
    elif z:
        c2 = c1
    return int(c1 == t or c2 == t)


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


@lifted(0x147ACC4)
def clear_id(m, o, ident, *_):
    """Clear the first of ten (u32 id, flag byte) entries from +8 that is flagged and holds `ident`."""
    ident &= 0xFFFFFFFF
    for i in range(10):
        if m.u8(o + 0xC + 8 * i) and m.u32(o + 8 + 8 * i) == ident:
            m.put(o + 8 + 8 * i, 4, 0)
            return


@lifted(0x13607C0)
def release_battler(m, o, ident, *_):
    b = _main_battler(m, o, ident)
    return _tail(m, m.main + 0x1360B30, m.u64(o + 0x18), b)


@lifted(0x1380DB8)
def count_sign(m, o, e, n, *_):
    """Signal the sign of `n` (0x15 positive, 0x16 negative) to [e+8] through slot 0x508, unless the
    byte at e+0x10 is 8."""
    if m.u8(e + 0x10) == 8:
        return
    n &= 0xFFFFFFFF
    if n == 0:
        return
    return _vtail(m, m.u64(e + 8), 0x508, 0x16 if n & 0x80000000 else 0x15)


@lifted(0x13616F0)
def remove_id(m, o, i, ident, *_):
    """Drop `ident` from list i (0..13): flag at +0xa8+4i, count at +0x70+4i, ten u32 slots at
    +0xe0+0x2c*i. Returns 1 when the list became empty and was cleared."""
    i &= 0xFFFFFFFF
    if (i ^ 0x80000000) - 0x80000000 > 0xD:
        return 0
    flag, count = o + 0xA8 + 4 * i, o + 0x70 + 4 * i
    if m.u32(flag) == 0:
        return 0
    n = m.u32(count)
    arr = o + 0x2C * i + 0xE0
    ident &= 0xFFFFFFFF
    for j in range(n):
        if m.u32(arr + 4 * j) == ident:
            break
    else:
        return 0
    if j <= 9:
        k = j
        if j & 1:
            m.put(arr + 4 * j, 4, m.u32(arr + 4 * j + 4))
            k = j + 1
        if j != 9:
            for off in range(4 * k, 0x28, 8):
                a, b = m.u32(arr + off + 4), m.u32(arr + off + 8)
                m.put(arr + off, 4, a); m.put(arr + off + 4, 4, b)
        j = 10
    n = (n - 1) & 0xFFFFFFFF
    m.put(arr + 4 * j, 4, 0)
    m.put(count, 4, n)
    pair = o + 8 + 0x10 * i + 0x340
    if n == 0:
        m.write(pair, bytes(0x10))
        m.put(o + 4 * i + 0x38, 4, 0)
        m.put(count, 4, 0); m.put(flag, 4, 0)
        m.put(arr + 0x28, 4, 0)
        m.write(arr, bytes(0x28))
        return 1
    if m.call(m.main + 0x184A110, pair) & 0xFFFFFFFF == ident:
        m.call_void(m.main + 0x28787A0, pair, m.u32(arr))
    return 0


def _standing(m, o):
    """Each party member still in the battle, as the server's inlined iterator (0x1147774 then the
    0x1360dbc step) hands them out."""
    from pokeldn.sv.battle.engine.flow import first_standing, next_standing
    with m.frame(0x28) as it:
        m.put(it, 8, m.u64(m.main + 0x46E2580) + 0x10)
        m.put(it + 8, 8, m.u64(o + 8)); m.put(it + 0x10, 8, m.u64(o + 0x10))
        m.put(it + 0x18, 2, 0); m.put(it + 0x1A, 1, 1)
        first_standing(m, it)
        while next_standing(m, it, it + 0x20):
            yield m.u64(it + 0x20)


def _rule_499_bit2(m, o):
    return m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x499) >> 2 & 1


@lifted(0x1141160)
def standing_condition_c(m, o, *_):
    if _rule_499_bit2(m, o):
        return
    for b in _standing(m, o):
        if m.vcall(b, 0x4D0, 0xC) & 1:
            m.call_void(m.main + 0x1140198, m.u64(o + 0x20), b, 0xC)
            m.call_void(m.main + 0x1148470, m.u64(o + 0x20), b, 0x13)


@lifted(0x114140C)
def note_standing_ids(m, o, *_):
    """Add each standing member's id to the byte list at [[o+0x40]+0x68] (30 bytes from +8, count +0x28)."""
    if _rule_499_bit2(m, o):
        return
    for b in _standing(m, o):
        v = m.vcall(b, 0x98) & 0xFFFFFFFF
        t = m.u64(m.u64(o + 0x40) + 0x68)
        if m.call(m.main + 0x114E624, t, v) & 1 == 0:
            n = m.s(t + 0x28, 4)
            if n <= 0x1D:
                m.put(t + 8 + n, 1, v)
                m.put(t + 0x28, 4, m.u32(t + 0x28) + 1)


@lifted(0x2D3B780)
def bump_490(m, b, *_):
    """Raise the byte counter behind slots 0x490 (get) and 0x498 (set) by one, unless it is 0xff."""
    v = m.vcall(b, 0x490)
    if ~v & 0xFF == 0:
        return
    return _vtail(m, b, 0x498, (v + 1) & 0xFFFFFFFF)


@lifted(0x13B1F10)
def move_field_6(m, key_holder, *_):
    """Field 6 (a byte) of the record for the u16 id at key_holder+8; 0x65 reads as 0x64."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.containers import data_record
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    v = fb.u8(m, data_record(m, table, m.u16(key_holder + 8)), 6)
    return 0x64 if v == 0x65 else v


@lifted(0x1365E90)
def clients_off_side(m, mode, rule, pos, *_):
    """How many of the clients 0..4 present in this mode (0xe7e2a0) map to a class other than the one
    of `pos` (tables 0x3c6a450 / 455 / 45a, 2 outside them)."""
    from pokeldn.sv.battle.engine.getters import _MODE_TABLES
    raw = (mode, rule)
    mode &= 0xFFFFFFFF; rule &= 0xFFFFFFFF; pos &= 0xFFFFFFFF
    n = 0
    for c in range(5):
        if m.call(m.main + 0xE7E2A0, *(raw if c == 0 else (mode, rule)), c) & 1 == 0:
            continue
        if mode not in _MODE_TABLES or 4 < (pos ^ 0x80000000) - 0x80000000:
            side = 2
        elif pos < 5:
            side = _MODE_TABLES[mode][pos]
        else:
            side = m.u8(m.main + 0x3C6A450 + 5 * mode + pos)
        n += side != (_MODE_TABLES[mode][c] if mode in _MODE_TABLES else 2)
    return n & 0xFF


def _keyed(m, address, key):
    """Call `address` with a stack object (vtable [0x46ddad8]+0x10, u16 key at +8)."""
    with m.frame(0x10) as p:
        m.put(p, 8, m.u64(m.main + 0x46DDAD8) + 0x10)
        m.put(p + 8, 2, key)
        return m.call(m.main + address, p)


@lifted(0x1382AB0)
def keyed_flag(m, key, *_): return _keyed(m, 0x1382AE8, key) & 1


@lifted(0x20FB1A8)
def keyed_byte(m, key, *_):
    return (((_keyed(m, 0x20FB1E0, key) & 0xFF) ^ 0x80) - 0x80) & 0xFFFFFFFF


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


@lifted(0x174AE20)
def queue_0x13(m, o, a, b, src, *_):
    with m.frame(0x10) as p:
        m.put(p, 4, 0); m.put(p + 8, 8, 0)
        m.call_void(m.main + 0x174AE90, src, p + 0xC, p + 8, p)
        return _tail(m, m.main + 0x119AFF0, o, 0x13, a & 0xFFFFFFFF, b & 0xFF, m.u32(p + 0xC), m.u32(p + 8),
                     m.u32(p))


@lifted(0x171A850)
def battler_1c0(m, o, ident, a, b, *_):
    bt = _main_battler(m, o, ident)
    if bt == 0:
        return
    return _vtail(m, bt, 0x1C0, a & 0xFFFFFFFF, b & 0xFFFFFFFF)


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


@lifted(0x1872CE0)
def check_1640(m, o, b, *_):
    with m.frame(0x18) as p:
        m.put(p + 8, 8, b); m.put(p + 0x10, 1, 0)
        q = m.call(m.main + 0x1872D18, m.call(m.main + 0x1361214, o))
        m.call_void(m.main + 0x1872D20, q, p, p + 8)
        return m.u8(p)


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


@lifted(0x2D19610)
def advance_2d0(m, o, ident, *_):
    s = m.u64(m.u64(o + 0x38) + 0x78)
    p = m.u64(s + 0x20)
    if (m.u32(p + 0xC) if p else 0) != ident & 0xFFFFFFFF:
        return
    q = m.u64(s + 0x2D0)
    if q == 0 or m.u8(q + 0xA) > 1:
        return
    m.put(q + 0xC, 4, 1)
    if m.u8(q + 0xA) == 1:
        m.put(q + 0xA, 1, 2)


@lifted(0x288818C)
def mark_bits(m, o, out, row, bits, *_):
    """For each of 19 indexes set in the bit field `bits` (byte count, then the bytes) that 0x28883a0
    accepts, set out[row*0x13 + i]; 1 if any was set."""
    row &= 0xFFFFFFFF
    base = out + 0x13 * (row & 0xFF)
    hit = 0
    for i in range(0x13):
        k = (i >> 3) + 1
        if k < m.u8(bits) and m.u8(bits + k) >> (i & 7) & 1 \
                and m.call(m.main + 0x28883A0, o, row, i) & 1:
            hit = 1
            m.put(base + i, 1, 1)
    return hit


@lifted(0x157BF08)
def remove_member(m, lst, b, *_):
    """Take a battler out of a member list (pointers from +0, count +0xa6), closing the gap; the byte
    at +0xa8 drops by one too."""
    n = m.u8(lst + 0xA6)
    for i in range(n):
        if m.u64(lst + 8 * i) != b:
            continue
        cur = n
        if i + 1 < n:
            m.put(lst + 8 * i, 8, m.u64(lst + 8 * i + 8))
            cur = m.u8(lst + 0xA6)
            j = i
            while j + 2 < cur:
                m.put(lst + 8 * j + 8, 8, m.u64(lst + 8 * j + 0x10))
                cur = m.u8(lst + 0xA6)
                j += 1
        m.put(lst + 0xA6, 1, cur - 1)
        m.put(lst + 0xA8, 1, m.u8(lst + 0xA8) - 1)
        return


@lifted(0x2D2219C)
def effective_type(m, b, t, move, *_):
    """The type a move takes: 0x1f for moves 0x353 and 0x38a (the latter when vf 0x88(0x3fd)) on a
    battler holding the static, flagged at +0x714 and with 0x63 at +0x715; else `t`."""
    t &= 0xFFFFFFFF
    if not _has_static(m, b) or m.u8(b + 0x714) == 0 or m.u8(b + 0x715) != 0x63:
        return t
    move &= 0xFFFF
    if move == 0x353:
        return 0x1F
    if move == 0x38A:
        return 0x1F if m.vcall(b, 0x88, 0x3FD) & 1 else t
    return t


@lifted(0x115043C)
def queue_bd(m, o, arg, *_):
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xBD, arg & 0xFFFFFFFF)


@lifted(0x1360CDC)
def set_41(m, e, v, *_): m.put(e + 0x41, 1, v & 1)


@lifted(0x157B7A0)
def move_check_157fc44(m, move, *rest):
    return _tail(m, m.main + 0x157FC44, move, *rest[:6])


@lifted(0x15FA034)
def check_b0(m, o, out, arg, *_):
    if m.u32(m.u64(m.u64(o + 0x10) + 0x70) + 0xB0):
        m.put(out, 1, 0)
        return
    r = m.call(m.main + 0x15FA084, m.u64(o + 0x38), m.u64(arg), m.u8(arg + 8))
    m.put(out, 1, r & 1)     # the game clears `out` before the call; the callee never sees it


@lifted(0xFECB7C)
def rule_allows_move(m, b, *_):
    """0 when the battler has no rule object (+0x700), its move (+0x47e) has field 6 set, or the
    shared object at [+0x708]+0x190 answers the 0x50fc5612cd4b7875 query; else whether [+0x700]+0xcc
    is set."""
    if m.u64(b + 0x700) == 0:
        return 0
    with m.frame(0x10) as p:
        m.put(p, 8, m.u64(m.main + 0x46DDAC0) + 0x10)
        m.put(p + 8, 2, m.u16(b + 0x47E))
        if m.call(m.main + 0xFECCD8, p) & 1:
            return 0
    holder = m.u64(b + 0x708)
    v = m.vcall(b, 0x2B8, m.u64(b + 0x700)) & 0xFFFFFFFF
    obj = m.u64(holder + 0x190)
    if obj:
        _need(m, m.u64(m.u64(obj) + 0x28))
        count = m.u32(obj + 0x28)
        if count == 0xFFFFFFFF:
            raise UnliftedCall("reference counter overflow abort")
        m.put(obj + 0x28, 4, count + 1)
    r = m.vcall(obj, 0x28, 0x50FC5612CD4B7875, v)
    if obj:
        count = m.u32(obj + 0x28)
        if count == 0:
            raise UnliftedCall("reference counter underflow abort")
        m.put(obj + 0x28, 4, count - 1)
        if count == 1:
            m.vcall_void(obj, 0x10)
    if r & 1:
        return 0
    return int(m.u32(m.u64(b + 0x700) + 0xCC) != 0)


@lifted(0x11521A0)
def shared_148(m, o, *_):
    """The object at [[o+8]+0x48]+0x148, after taking and dropping a reference on its control block
    (+0x30: object +0x10, u16 count +0x1a); the first reference builds +8, the last releases (vf 0x50)."""
    obj = m.u64(m.u64(m.u64(o + 8) + 0x48) + 0x148)
    if obj == 0:
        return 0
    ctl = m.u64(obj + 0x30)
    inner = m.u64(ctl + 0x10)
    if inner == 0:
        raise UnliftedCall("AddReference abort: m_object is null")
    count = m.u16(ctl + 0x1A)
    if count == 0xFFFF:
        raise UnliftedCall("AddReference abort: counter overflow")
    if count == 0:
        _need(m, m.u64(m.u64(inner)))
    m.put(ctl + 0x1A, 2, count + 1)
    if count == 0:
        m.put(ctl + 8, 8, m.vcall(inner, 0))
        m.put(ctl + 0x1C, 4, 0xFFFFFFFE)
    ctl = m.u64(obj + 0x30)
    count = m.u16(ctl + 0x1A)
    if count == 0:
        raise UnliftedCall("ReleaseReference abort: counter underflow")
    m.put(ctl + 0x1A, 2, count - 1)
    if count == 1:
        m.put(ctl + 0x10, 8, 0)
        m.vcall_void(obj, 0x50)
    return obj


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


def _s32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v & 0x80000000 else v


def _class_of(m, mode, i):
    """Entry i of the mode's five-entry class table (0x3c6a450 + 5 * mode), indexed as a u32."""
    from pokeldn.sv.battle.engine.getters import _MODE_TABLES
    i &= 0xFFFFFFFF
    return _MODE_TABLES[mode][i] if i < 5 else m.u8(m.main + 0x3C6A450 + 5 * mode + i)


@lifted(0x1365B00)
def nth_client_off_side(m, mode, rule, pos, nth, *_):
    """Walking the clients after `pos` ((pos + k) % 5), the (nth % count)-th present one whose class
    differs from pos's, counting with 0x1365e90; 5 when there is none."""
    n = m.call(m.main + 0x1365E90, mode, rule, pos, nth) & 0xFF
    nth &= 0xFF
    target = nth % n if n else nth
    mode &= 0xFFFFFFFF; rule &= 0xFFFFFFFF
    p = _s32(pos)
    count = 0
    for k in range(5):
        s = _s32(p + k)
        c = (s - int(s / 5) * 5) & 0xFFFFFFFF
        if c == pos & 0xFFFFFFFF or m.call(m.main + 0xE7E2A0, mode, rule, c) & 1 == 0 or mode > 2:
            continue
        mine = _class_of(m, mode, p) if p <= 4 else 2
        if mine == _class_of(m, mode, c):
            continue
        if count == target:
            return c
        count = (count + 1) & 0xFFFFFFFF
    return 5


def _negative_field(index):
    """The record's signed byte field `index`, negated when below zero, else 0."""
    def fn(m, key_holder, *_):
        from pokeldn.sv.battle.engine import flatbuffer as fb
        from pokeldn.sv.battle.engine.containers import data_record
        from pokeldn.sv.battle.engine.data import static_table
        table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
        v = fb.u8(m, data_record(m, table, m.u16(key_holder + 8)), index)
        return (0x100 - v) if v & 0x80 else 0
    return fn


lifted(0x1419734)(_negative_field(15))
lifted(0x141A340)(_negative_field(16))


@lifted(0x287B2D4)
def count_outcome(m, counters, pokecon, attacker, target, kind, *_):
    """Count one outcome in the u16 counters (at most 9999): +8 / +0xc / +0xa by `kind` (0, below 8,
    8 and up; 7 is not counted) on one side, +0xe / +0x12 / +0x10 on the other, picked by the two
    battlers' classes in the setup's map; nothing when 0x118ab58 holds or both classes are set."""
    a = m.vcall(attacker, 0x98) & 0xFFFFFFFF
    t = m.vcall(target, 0x98) & 0xFFFFFFFF

    def cls(ident):
        p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(pokecon + 0x290) + 8) + 0x50), ident)
        return 0 if p == 0 or m.s(p, 4) >= 5 else m.u32(p) & 0xFF
    ca, ct = cls(a), cls(t)
    r = m.call(m.main + 0x118AB58, m.u64(pokecon + 0x290), a, t)
    kind &= 0xFF
    if r & 1 or (ca and ct):
        return
    offs = (8, 0xC, 0xA) if ca == 0 else (0xE, 0x12, 0x10)
    if kind == 7:
        return
    at = counters + (offs[0] if kind == 0 else offs[1] if kind < 8 else offs[2])
    v = m.u16(at)
    if v <= 0x270E:
        m.put(at, 2, v + 1)


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


def _queue_id_kind(kind):
    """Hand (battler id, kind) to 0x17776d8 on the object at [o+0x78]+0x2e0."""
    def fn(m, o, b, *_):
        ident = m.vcall(b, 0x98)
        with m.frame(0x10) as p:
            m.put(p + 8, 4, ident); m.put(p + 0xC, 1, kind)
            m.call_void(m.main + 0x17776D8, m.call(m.main + 0x17776D0, m.u64(o + 0x78)), p, p + 8)
    return fn


lifted(0x177767C)(_queue_id_kind(4))
lifted(0x114B5DC)(_queue_id_kind(1))


@lifted(0x288C710)
def forward_28787e0(m, o, v, pair, *_):
    return _tail(m, m.main + 0x28787E0, m.u64(m.u64(o + 0x10) + 0x70), v, m.u64(pair), m.u64(pair + 8))


@lifted(0x1480A6C)
def make_entry(m, o, kind, value, src, b, *_):
    """A 16-byte entry returned in x0 and x1: x0 = value (its upper half as 0x179372c leaves it), x1 = 1
    for kinds 1 and 3..5, for kind 2: 2 with 0x179405c of the battler's two 0x68 reads in bits 3..8."""
    with m.frame(0x10) as p:
        m.call_void(m.main + 0x179372C, p)
        k = kind & 0xFFFF
        m.put(p + 8, 8, 0)
        if 3 <= k <= 5 or k == 1:
            hi = 1
        elif k == 2:
            x = m.vcall(b, 0x68, m.u64(m.main + 0x46E25C8)) & 0xFFFFFFFF
            y = m.vcall(b, 0x68, m.u64(m.main + 0x46E25D0)) & 0xFFFFFFFF
            m.put(p, 4, value)
            m.put(p + 8, 8, 2)
            r = m.call(m.main + 0x179405C, src, x, y)
            hi = (2 & ~0x1F8) | ((r & 0x3F) << 3)
        else:
            hi = 0
        m.put(p + 8, 8, hi)
        m.put(p, 4, value)
        return Pair(m.u64(p), hi)


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


@lifted(0x286FE20)
def double_on_condition(m, o, ident, *_):
    s = m.u64(m.u64(o + 0x38) + 0x78)
    p = m.u64(s + 0x20)
    if (m.u32(p + 0xC) if p else 0) != ident & 0xFFFFFFFF:
        return
    q = m.u64(s + 0x28)
    b = battler(m, m.u64(m.u64(o + 8) + 0x30), m.u32(q + 0xC) if q else 0)
    if m.vcall(b, 0x230) & 0xFFFF == 0 and m.vcall(b, 0x228, 1) & 1 == 0:
        return
    return _tail(m, m.main + 0x181D0D0, o, 2)


@lifted(0x283D690)
def mode_class_of(m, o, key, *_):
    return _tail(m, m.main + 0x144E790, m.u64(m.u64(o + 8) + 0x290), key)


# Index -> (value, value with a second argument; -1 means none), from the tables at 0x3c6afa0 and
# 0x3c6af36 (rows of three s16) for the indexes the mask 0x140465cff admits.
_COMMAND_VALUES = {0: (94, 297), 1: (105, 298), 2: (99, 299), 3: (89, 300), 4: (83, 296), 5: (118, 301),
                   6: (114, 302), 7: (126, 126), 10: (191, -1), 11: (194, -1), 12: (199, -1), 14: (284, -1),
                   17: (126, 126), 18: (239, -1), 22: (187, -1), 30: (216, -1), 32: (362, -1)}


@lifted(0x114A970)
def build_command(m, kind, src, arg, extra, out, *_):
    """Fill a message header at `out` for kind 1..33: u16 id, u16 flags with the argument count in
    bits 7..13, then u32 arguments; kind 0x12 adds 0x49, kind 8 adds 0xf7ffe0 of `src`."""
    w8 = (kind - 1) & 0xFFFFFFFF
    i = w8 & 0xFFFF
    if i > 0x20 or not (0x140465CFF >> (w8 & 63)) & 1:
        return 0
    a, b = _COMMAND_VALUES[i]
    extra &= 0xFFFF
    v = b if extra else a
    if v < 0:
        v = a
    hi = m.u16(out + 2) & 0xC000
    m.put(out, 2, v)
    flags = hi | 0x82
    m.put(out + 2, 2, flags)
    m.put(out + 4, 4, arg)
    if extra:
        flags = hi | 0x102
        m.put(out + 2, 2, flags)
        m.put(out + 8, 4, extra)
    k = kind & 0xFFFF
    n = flags >> 7 & 0x7F
    if k == 0x12 and n <= 7:
        m.put(out + 2, 2, ((flags + 0x80) & 0x3F80) | (flags & 0xC07F))
        m.put(out + 4 * n + 4, 4, 0x49)
    elif k == 8 and n <= 7:
        r = m.call(m.main + 0xF7FFE0, src)
        m.put(out + 2, 2, ((flags + 0x80) & 0x3F80) | (flags & 0xC07F))
        m.put(out + 4 * n + 4, 4, r & 0xFFFF)
    return 1


@lifted(0x287B8E0)
def map_at_u32(m, table, key_ptr, *_):
    """unordered_map<u32, ...>::at: the value (node+0x14) for the u32 at key_ptr; a missing key throws."""
    from pokeldn.sv.battle.engine.containers import find
    node = find(m, table, m.u32(key_ptr), 4)
    if not node:
        raise UnliftedCall("unordered_map::at of a missing key (throws)")
    return node + 0x14


@lifted(0x1794620)
def record_byte_11(m, key_holder, *_):
    """The byte 4 past field 11 of the record for the u16 id at key_holder+8; the field is read without
    a vtable size check."""
    from pokeldn.sv.battle.engine.containers import data_record
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    rec = data_record(m, table, m.u16(key_holder + 8))
    return m.u8(rec + m.u16(rec - m.s(rec, 4) + 0x1A) + 4)


def _triple_byte(k):
    """Byte k of the i-th (0..2) three-byte entry at field 18 of the record for the u16 id at
    key_holder+8; the field is read without a vtable size check."""
    def fn(m, key_holder, i, *_):
        from pokeldn.sv.battle.engine.containers import data_record
        from pokeldn.sv.battle.engine.data import static_table
        i &= 0xFF
        if i > 2:
            return 0
        table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
        rec = data_record(m, table, m.u16(key_holder + 8))
        return m.u8(rec + m.u16(rec - m.s(rec, 4) + 0x28) + 3 * i + k)
    return fn


lifted(0x1771130)(_triple_byte(1))
lifted(0x1384070)(_triple_byte(2))


@lifted(0x115B968)
def form_record_u16(m, key_holder, *_):
    """The u16 at +0xa past field 0 of the record keyed by u16(+8) * 10000 + u16(+0xa) in the static
    table 0x46d7438 (its default at +0xd0); the field is read without a vtable size check."""
    from pokeldn.sv.battle.engine.containers import find
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7430, 0x46D7438, 0x46D7440)
    key = m.u16(key_holder + 8) * 10000 + m.u16(key_holder + 0xA)
    node = find(m, table + 0x68, key, 8)
    rec = m.u64(node + 0x18) if node else m.u64(table + 0xD0)
    return m.u16(rec + m.u16(rec - m.s(rec, 4) + 4) + 0xA)


def _ref_take(m, obj):
    count = m.u32(obj + 0x28)
    if count == 0xFFFFFFFF:
        raise UnliftedCall("reference counter overflow abort")
    m.put(obj + 0x28, 4, count + 1)


def _ref_drop(m, obj):
    count = m.u32(obj + 0x28)
    if count == 0:
        raise UnliftedCall("reference counter underflow abort")
    m.put(obj + 0x28, 4, count - 1)
    if count == 1:
        m.vcall_void(obj, 0x10)


@lifted(0x28764E0)
def base_damage(m, o, p, *_):
    """The damage formula over (power, level, attack, defense) at p: ((2 * level / 5 + 2) * power *
    attack / defense) / 50 + 2, unless the reference-counted object at +0x128 holds a replacement
    function (+0x30, called with its +0x50)."""
    obj = m.u64(o + 0x128)
    if obj:
        fn = m.u64(obj + 0x30)
        if m.u32(obj + 0x28) == 0:
            _need(m, m.u64(m.u64(obj) + 0x10))
        if fn:
            _need(m, fn)
        _ref_take(m, obj)
        fn = m.u64(obj + 0x30)
        _ref_drop(m, obj)
        if fn:
            obj = m.u64(o + 0x128)
            _ref_take(m, obj)
            r = m.call(m.u64(obj + 0x30), obj + 0x50, p) & 0xFFFFFFFF
            _ref_drop(m, obj)
            return r
    power, level, attack, defense = m.u32(p), m.u32(p + 4), m.u32(p + 8), m.u32(p + 0xC)
    v = (attack * power * ((((level << 1) & 0xFFFFFFFF) // 5 + 2) & 0xFFFFFFFF)) & 0xFFFFFFFF
    v = v // defense if defense else 0
    return (v // 50 + 2) & 0xFFFFFFFF


@lifted(0x1147754)
def standing_iterator(m, it, setup, pokecon, *_):
    """Build the standing-member iterator (vtable main+0x4500bb0) and point it at the first member."""
    m.put(it + 0x18, 2, 0)
    m.put(it, 8, m.main + 0x4500BB0)
    m.put(it + 0x1A, 1, 1)
    m.put(it + 8, 8, setup); m.put(it + 0x10, 8, pokecon)
    return _tail(m, m.main + 0x1147774, it)


@lifted(0x1148DF8)
def note_and_queue_74(m, o, a, b, c, *_):
    m.call_void(m.main + 0x288D134, m.u64(o + 0x20), a, b, c)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x74, a & 0xFFFFFFFF, b & 0xFF, c & 0xFFFF)


@lifted(0x11438E4)
def use_counter(m, o, b, i, a, c, d, *_):
    """Count down the battler's counter i (vf 0x540); when it reaches zero queue the two 0x74
    messages for `a` and `c` with 0x171a7ec(0x32) and hand `d` to 0x171a604."""
    i &= 0xFFFFFFFF
    if m.vcall(b, 0x540, i) & 0xFF == 0:
        return
    n = (m.vcall(b, 0x540, i) - 1) & 0xFFFFFFFF
    m.call_void(m.main + 0x1143A30, m.call(m.main + 0x1143584, o), b, i, n)
    if n & 0xFF:
        return
    v = m.call(m.main + 0x171A7EC, 0x32) & 0xFFFFFFFF
    for arg in (a, c):
        x = m.call(m.main + 0x1143584, o)
        m.call_void(m.main + 0x1148DF8, x, m.vcall(b, 0x98) & 0xFFFFFFFF, arg & 0xFFFFFFFF, v)
    x = m.call(m.main + 0x1143584, o)
    return _tail(m, m.main + 0x171A604, x, m.vcall(b, 0x98) & 0xFFFFFFFF, d & 0xFFFFFFFF, 0xFF)


@lifted(0x171A604)
def queue_bf(m, o, a, b, c, *_):
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xBF, a & 0xFFFFFFFF, b & 0xFF, c & 0xFF)


@lifted(0x171A6DC)
def queue_73_pair(m, o, b, kind, *_):
    """For kind 7 (stats 2 and 4) or 6 (stats 1 and 3), hand the battler's id with each stat and
    0x171a7ec(0x32) to 0x171a804."""
    v = m.call(m.main + 0x171A7EC, 0x32) & 0xFFFFFFFF
    kind &= 0xFFFFFFFF
    if kind == 7:
        stats = (2, 4)
    elif kind == 6:
        stats = (1, 3)
    else:
        return
    x = m.call(m.main + 0x1143584, o)
    m.call_void(m.main + 0x171A804, x, m.vcall(b, 0x98) & 0xFFFFFFFF, stats[0], v)
    x = m.call(m.main + 0x1143584, o)
    return _tail(m, m.main + 0x171A804, x, m.vcall(b, 0x98) & 0xFFFFFFFF, stats[1], v)


@lifted(0x287EE68)
def queue_ca(m, o, a, b, *_):
    return _tail(m, m.main + 0x157EBC0, m.u64(o + 0x18), 0xCA, a & 0xFFFFFFFF, b & 0xFFFF, 0xFFFF0000)


@lifted(0x287F270)
def raise_on_species_271(m, o, holder, pk, *_):
    """When the Pokemon holds the static, is species 0x271 (+0x710) and the 0x4690abda0b4ec6c4 query
    holds, raise the holder's battler's stat 3 by one (vf 0x550) and queue message 0x37."""
    if holder == 0 or pk == 0 or m.u64(holder) == 0:
        return
    if not _has_static(m, pk) or m.u16(pk + 0x710) != 0x271:
        return
    v = m.vcall(pk, 0x2A8) & 0xFFFFFFFF
    if m.call(m.main + 0x151BB5C, m.u64(o + 8), 0x4690ABDA0B4EC6C4, v) & 1 == 0:
        return
    ident = m.vcall(m.u64(holder), 0x98) & 0xFFFFFFFF
    q = m.u64(o + 0x20)
    b = battler(m, m.u64(m.u64(m.u64(q + 0x20) + 0x10) + 0x30), ident)
    m.vcall_void(b, 0x550, 3, 1)
    return _tail(m, m.main + 0x119AFF0, m.u64(q + 0x18), 0x37, ident, 3, 1)


@lifted(0x157EBC0)
def push_terminated(m, que, command, *varargs):
    """The variadic push whose u32 arguments end at 0xffff0000: the format byte (+0x12) of the
    command's node in the queue's map at +0 (0 when absent), then 0x119bf58 over the arguments."""
    from pokeldn.sv.battle.engine.containers import find_u16
    node = find_u16(m, que, command)
    fmt = m.u8(node + 0x12) if node else 0
    with m.frame(0x40) as arr:
        m.write(arr, bytes(0x40))
        for k, v in enumerate(varargs):
            v &= 0xFFFFFFFF
            m.put(arr + 4 * k, 4, v)
            if v == 0xFFFF0000:
                break
        return _tail(m, m.main + 0x119BF58, que, command, fmt, arr)


# The allocator's size classes between 0x221 and 0xaa0 (the constants compared in 0xee5860).
_SIZE_CLASSES = (0x240, 0x260, 0x270, 0x280, 0x2A0, 0x2D0, 0x2E0, 0x300, 0x330, 0x360, 0x380, 0x3B0, 0x400,
                 0x450, 0x490, 0x4C0, 0x550, 0x600, 0x660, 0x6D0, 0x800, 0x990, 0xAA0)


@lifted(0xEE5860)
def size_class(m, size, align, *_):
    """The allocation size for `size` at alignment `align` (clamped to 0x10..0x1000): rounded up to the
    alignment, then above 0x1e0 to the first size class the alignment divides, else to a page."""
    M = 0xFFFFFFFFFFFFFFFF
    a = align if align < 0x1000 else 0x1000
    a = a if a > 0x10 else 0x10
    r = size % a
    n = ((a - r if r else 0) + size) & M
    if a == 0x1000 or n < 0x1E1:
        return n
    if n == 0x1F0:
        return 0x200
    if n < 0x221:
        return n
    for c in _SIZE_CLASSES:
        if n <= c and c % a == 0:
            return c
    return ((0x1000 - (n & 0xFFF) if n & 0xFFF else 0) + n) & M


@lifted(0xBF44F4)
def species(m, acc, *_):
    """The species: the u16 at the start of block A."""
    from pokeldn.sv.battle.engine.pokemon import access, block
    return access(m, acc, lambda core: m.u16(block(m, core, 0)))


@lifted(0x287A8C0)
def form_check_133b78c(m, b, *_):
    core = m.u64(b + 0x48)
    r = m.call(m.main + 0x103B8A0, m.u64(core + 0x70))
    if r & 0xFFFF < 0x137:
        return r
    s = m.call(m.main + 0xBF44F4, m.u64(core + 0x70))
    f = m.call(m.main + 0xBF41A8, m.u64(core + 0x70))
    g = m.call(m.main + 0xD99784, core)
    return _tail(m, m.main + 0x133B78C, s & 0xFFFFFFFF, f & 0xFFFFFFFF, g & 0xFFFFFFFF)


@lifted(0x1793E94)
def packed_move_info(m, key, *_):
    """Bits 0..3: 0x1794478 of the record for u16 `key`; when it is non-zero, bits 4..9 0x1794620 and
    bits 10..15 0x17947c8."""
    with m.frame(0x10) as p:
        m.put(p, 8, m.u64(m.main + 0x46DDAD8) + 0x10)
        m.put(p + 8, 2, key)
        r = m.call(m.main + 0x1794478, p)
        v = r & 0xF
        if r & 0xFF:
            a = m.call(m.main + 0x1794620, p)
            c = m.call(m.main + 0x17947C8, p)
            v = v | (a & 0x3F) << 4 | (c & 0x3FFFFF) << 10
        return v & 0xFFFF


@lifted(0x287A68C)
def core_b80208(m, b, *_):
    return _tail(m, m.main + 0xB80208, m.u64(m.u64(b + 0x48) + 0x70))


@lifted(0x1384028)
def keyed_triple_byte_2(m, key, i, *_):
    if i & 0xFFFFFFFF > 2:
        return 0
    with m.frame(0x10) as p:
        m.put(p, 8, m.u64(m.main + 0x46DDAD8) + 0x10)
        m.put(p + 8, 2, key)
        return m.call(m.main + 0x1384070, p, i) & 0xFF


@lifted(0x15C0434)
def other_side_target(m, o, a, t, *_):
    a &= 0xFFFFFFFF; t &= 0xFFFFFFFF
    if m.call(m.main + 0x15C04B0, m.u64(m.u64(o + 0x10) + 0x30), t) & 1 == 0:
        return 0
    if m.call(m.main + 0x15C04A4, o, a, t) & 1:
        return 0
    return int(t != 0 and t != a)


@lifted(0x1360CE8)
def release_condition_1a_of(m, o, pk, *_):
    """For each standing member under condition 0x1a whose condition value (vf 0x4f0) is the
    Pokemon's id, hand it to 0x287f998."""
    with m.frame(0x30) as p:
        it, out, holder = p, p + 0x20, p + 0x28
        m.put(holder, 8, o); m.put(out, 8, 0)
        a = m.call(m.main + 0x114E480, o)
        m.call_void(m.main + 0x1147754, it, a, m.call(m.main + 0x1482534, o))
        while m.call(m.main + 0x1360DBC, it, out) & 1:
            b = m.u64(out)
            if m.vcall(b, 0x4D0, 0x1A) & 1:
                v = m.u32(m.vcall(b, 0x4F0, 0x1A))
                if m.vcall(pk, 0x98) & 0xFFFFFFFF == v:
                    m.call_void(m.main + 0x287F998, holder, m.u64(out))


@lifted(0xD679F0)
def seal_record(m, acc, *_):
    """Under the record's lock clear keep-plain (+0x19) and, when the record is plain, store its
    checksum and encrypt the core and party records."""
    from pokeldn.sv.battle.engine.libc import FAKE_THREAD, signal_light_event
    from pokeldn.sv.battle.engine.pokemon import BLOCKS, CORE, _checksum, _xor_words
    if m.u64(acc + 0x20) != 0:
        raise UnliftedCall("pokemon record already locked")
    m.put(acc + 0x20, 8, FAKE_THREAD)
    m.put(acc + 0x19, 1, 0)
    if m.u8(acc + 0x18) == 0:
        core = m.u64(acc + 0x10)
        if core:
            m.put(core + 6, 2, _checksum(m, core))
            _xor_words(m, core + BLOCKS, (CORE - BLOCKS) // 2, m.u32(core))
        party = m.u64(acc + 8)
        if party and m.u64(acc + 0x10):
            _xor_words(m, party, 8, m.u32(m.u64(acc + 0x10)))
        m.put(acc + 0x18, 1, 1)
    m.put(acc + 0x20, 8, 0)
    return signal_light_event(m, acc + 0x28)


def _record_tail(target, deref=True):
    """A battler method that tail-calls `target` with its core (+0x48), or with the core's record
    accessor (+0x70) when `deref`, passing the caller's other arguments through."""
    def fn(m, b, *rest):
        core = m.u64(b + 0x48)
        return _tail(m, m.main + target, m.u64(core + 0x70) if deref else core, *rest[:6])
    return fn


for _addr, _target, _deref in ((0x287A8A8, 0xBEC030, True), (0x287A8B4, 0xD97B78, True),
                               (0x287A728, 0xE14B64, True), (0x287A734, 0xD97F14, False)):
    lifted(_addr)(_record_tail(_target, _deref))


@lifted(0x287A5B4)
def party_or_stored_c75438(m, b, *rest):
    """0xc75438 of the record accessor when it holds a party record, else 0xe13ef0 of the core."""
    core = m.u64(b + 0x48)
    acc = m.u64(core + 0x70)
    if m.u64(acc + 8):
        return _tail(m, m.main + 0xC75438, acc, *rest[:6])
    return m.call(m.main + 0xE13EF0, core, *rest[:6]) & 0xFFFF


@lifted(0x17D5D98)
def same_side_pair(m, o, a, b, *_):
    ia = m.vcall(a, 0x98) & 0xFFFFFFFF
    ib = m.vcall(b, 0x98) & 0xFFFFFFFF
    return _tail(m, m.main + 0x118AB58, m.u64(m.u64(o + 0x10) + 0x290), ia, ib)


@lifted(0x114B210)
def queue_cb(m, o, a, b, n, vals, *_):
    """Message 0xcb with `a`, `b` and the first n (1..4; otherwise none) u32 values at `vals`."""
    n &= 0xFFFFFFFF
    extra = [m.u32(vals + 4 * k) for k in range(n)] if 1 <= n <= 4 else []
    return _tail(m, m.main + 0x157EBC0, m.u64(o + 0x18), 0xCB, a & 0xFFFFFFFF, b & 0xFFFF, *extra,
                 0xFFFF0000)


@lifted(0x113AECC)
def side_of_c9c750(m, a, b, c, d, *_):
    """0x113a588 of (a, b, 0x113af40(a, b, k, 0), d), where k is 1, 0 or 2 for 0xc9c750's 0, 1 or
    anything else (table 0x3b72710)."""
    r = m.call(m.main + 0xC9C750, a, b, c, d) & 0xFF
    k = (1, 0)[r] if r <= 1 else 2
    s = m.call(m.main + 0x113AF40, a & 0xFFFFFFFF, b & 0xFFFFFFFF, k, 0)
    return _tail(m, m.main + 0x113A588, a & 0xFFFFFFFF, b & 0xFFFFFFFF, s & 0xFFFFFFFF, d & 0xFFFFFFFF)


# Batch 2, second pass: the battle-state build (0x2892ac0 and its callees).
from pokeldn.sv.battle.engine import pokemon as _pk  # noqa: E402
from pokeldn.sv.battle.engine.data import static_table  # noqa: E402

# Record accessors in the layout of pokemon._GETTERS / _SETTERS.
for _a, *_spec in ((0xC1EB6C, 3, 0x2E, 1, 0, 0x4742380, False), (0xD8FAE8, 0, 0x1E, 1, 0, 0x4742290, False),
                   (0xD904B4, 0, 0x22, 1, 0, 0x4742290, False)):
    lifted(_a)(_pk._getter(*_spec))
for _a, *_spec in ((0xE16488, "party", 2, 2, 0, 0x47423D0, True), (0xE15AEC, "party", 8, 2, 0, 0x47423D0, True),
                   (0xE15150, "party", 0, 1, 0, 0x47423D0, True)):
    lifted(_a)(_pk._setter(*_spec))


def _encrypt(m, acc):
    core = m.u64(acc + 0x10)
    if core:
        m.put(core + 6, 2, _pk._checksum(m, core))
        _pk._xor_words(m, core + _pk.BLOCKS, (_pk.CORE - _pk.BLOCKS) // 2, m.u32(core))
    party = m.u64(acc + 8)
    if party and m.u64(acc + 0x10):
        _pk._xor_words(m, party, 8, m.u32(m.u64(acc + 0x10)))
    m.put(acc + 0x18, 1, 1)


def _decrypt(m, acc):
    _pk._crypt(m, acc)
    m.put(acc + 0x18, 1, 0)
    core = m.u64(acc + 0x10)
    if m.u16(core + 6) != _pk._checksum(m, core):
        m.put(core + 4, 2, m.u16(core + 4) | 4)


@lifted(0xFCA6E8)
def unlocked_block1_3d(m, acc, *_):
    """Byte 0x3d of block B, decrypting and re-encrypting the record without taking its lock."""
    if m.u8(acc + 0x18):
        _decrypt(m, acc)
    core = m.u64(acc + 0x10)
    v = m.u8(_pk._target(m, acc, core, 1, 0x47422E0) + 0x3D)
    if m.u8(acc + 0x18) == 0 and m.u8(acc + 0x19) == 0:
        _encrypt(m, acc)
    return v


@lifted(0xE32A60)
def copy_encrypted(m, acc, core_out, party_out, *_):
    """Copy the encrypted core record (0x148 bytes) and party record (16) out, encrypting a record kept
    plain (+0x19) for the copy and restoring it after."""
    plain = m.u8(acc + 0x19)
    if plain:
        m.put(acc + 0x19, 1, 0)
        if m.u8(acc + 0x18) == 0:
            _encrypt(m, acc)
    if core_out:
        m.write(core_out, m.read(m.u64(acc + 0x10), _pk.CORE))
    if party_out:
        m.write(party_out, m.read(m.u64(acc + 8), 16))
    if plain:
        if m.u8(acc + 0x18):
            _decrypt(m, acc)
        m.put(acc + 0x19, 1, 1)
    return core_out if core_out else acc


def _personal_table(m, key_holder):
    """The personal record for (u16 +8) * 10000 + (u16 +0xa) (static map 0x46d7438), else its default."""
    from pokeldn.sv.battle.engine.containers import find
    table = static_table(m, 0x46D7430, 0x46D7438, 0x46D7440)
    key = m.u16(key_holder + 8) * 10000 + m.u16(key_holder + 0xA)
    node = find(m, table + 0x68, key, 8)
    return m.u64(node + 0x18) if node else m.u64(table + 0xD0)


@lifted(0xCEE118)
def personal_byte_5(m, key_holder, *_):
    """Byte 5 of the personal record's struct at field +0x30."""
    t = _personal_table(m, key_holder)
    return m.u8(t + m.u16(t - m.s(t, 4) + 0x30) + 5)


@lifted(0xE13DA0)
def level_for_exp(m, species, form, exp, *_):
    """The level (1..100) whose experience threshold the growth rate (0xb860e0) puts at or below exp:
    the u32 thresholds at [table field 0] + rate * 0x194 + level * 4 of the static at 0x46da7c8."""
    exp &= 0xFFFFFFFF
    level = 1
    with m.frame(0x10) as p:
        while True:
            m.put(p, 8, m.u64(m.main + 0x46D8EE0) + 0x10)
            m.put(p + 8, 2, species); m.put(p + 0xA, 2, form)
            rate = m.call(m.main + 0xB860E0, p) & 0xFF
            table = static_table(m, 0x46DA7C0, 0x46DA7C8, 0x46DA7D0)
            root = m.vcall(m.u64(table + 0x30), 0x70)
            if root == 0:
                need = 1
            else:
                t = root + m.u32(root)
                rows = t + m.u16(t - m.s(t, 4) + 4)
                need = m.u32(rows + (0 if rate > 8 else rate) * 0x194 + level * 4)
            if need > exp:
                break
            level += 1
            if level == 0x65:
                return 100
    return level - 1 if level & 0xFF >= 2 else 1


@lifted(0x2014160)
def hash_of_id(m, owner, key, *_):
    """The 64-bit name hash of u16 id `key` (282 entries of 0x18 bytes from +0x30); 0 if unknown."""
    table = static_table(m, 0x46D8900, 0x46D8908, 0x46D8910)
    key &= 0xFFFF
    if key:
        for i in range(0x11A):
            if m.u16(table + 0x38 + 0x18 * i) == key:
                return m.u64(table + 0x30 + 0x18 * i)
    return 0


@lifted(0x2A1C178)
def is_zero_u16(m, _o, v, *_): return int(v & 0xFFFF == 0)


@lifted(0x2A70AB4)
def destroy_event_holder(m, p, *_):
    """Set the vtable 0x44a92f8 and finalize the light event at +0x28 (nn::os::FinalizeLightEvent
    clears its byte +1)."""
    m.put(p, 8, m.main + 0x44A92F8)
    m.put(p + 0x29, 1, 0)
    return p + 0x28


@lifted(0x13736D8)
def refresh_battle_stats(m, b, reset, scale, *_):
    """reset: +0x40a/+0x40b from vf 0x350/0x358, +0x410 = 0, +0x40c = 0x12. Always +0x40d from the
    core's vf 0x130. scale: the u16 stats +0x400..+0x408 = core vf 0x70(1..5) * byte +0x3f6.. / 10."""
    if reset & 1:
        m.put(b + 0x40A, 1, m.vcall(b, 0x350))
        m.put(b + 0x40B, 1, m.vcall(b, 0x358))
        m.put(b + 0x410, 4, 0)
        m.put(b + 0x40C, 1, 0x12)
    m.put(b + 0x40D, 1, m.vcall(m.u64(b + 0x48), 0x130))
    if scale & 1:
        for i in range(5):
            v = m.vcall(m.u64(b + 0x48), 0x70, i + 1) & 0xFFFF
            m.put(b + 0x400 + 2 * i, 2, (v * m.u8(b + 0x3F6 + i) & 0xFFFFFFFF) // 10)


@lifted(0x14806D0)
def apply_five_flags(m, b, flags, *_):
    """For each non-zero byte k of flags +4..+8, vf 0x370(k - 3, byte)."""
    vals = [m.u8(flags + 4 + k) for k in range(5)]
    if not any(vals):
        return b
    r = b
    for k, v in enumerate(vals):
        if v:
            r = _vtail(m, b, 0x370, k + 1, v)
    return r


@lifted(0xFA1F30)
def push_side_battler(m, o, side, ident, *_):
    """Append battler `ident` (map o+0x140) to side's list (o + side*0x38: objects +0x28, count u8 +0x58),
    taking and dropping a reference on its control block; nothing when the id is unknown, a null entry
    when the node holds none."""
    from pokeldn.sv.battle.engine.containers import find
    node = find(m, o + 0x140, ident & 0xFFFFFFFF, 4)
    if not node:
        return o
    obj = m.u64(node + 0x18)
    row = o + (side & 0xFF) * 0x38
    if obj == 0:
        c = m.u8(row + 0x58)
        m.put(row + 0x58, 1, c + 1)
        m.put(row + 0x28 + 8 * c, 8, 0)
        return o
    ctl = m.u64(obj + 0x30)
    inner = m.u64(ctl + 0x10)
    if inner == 0:
        raise UnliftedCall("AddReference abort: m_object is null")
    count = m.u16(ctl + 0x1A)
    if count == 0xFFFF:
        raise UnliftedCall("AddReference abort: counter overflow")
    if count == 0:
        _need(m, m.u64(m.u64(inner)))
        _need(m, m.u64(m.u64(obj) + 0x50))
    r = o
    m.put(ctl + 0x1A, 2, count + 1)
    if count == 0:
        r = m.vcall(inner, 0)
        m.put(ctl + 8, 8, r)
        m.put(ctl + 0x1C, 4, 0xFFFFFFFE)
    c = m.u8(row + 0x58)
    m.put(row + 0x58, 1, c + 1)
    m.put(row + 0x28 + 8 * c, 8, obj)
    ctl = m.u64(obj + 0x30)
    count = m.u16(ctl + 0x1A)
    if count == 0:
        raise UnliftedCall("ReleaseReference abort: counter underflow")
    m.put(ctl + 0x1A, 2, count - 1)
    if count == 1:
        m.put(ctl + 0x10, 8, 0)
        return _vtail(m, obj, 0x50)
    return r


@lifted(0xE13EF0)
def computed_max_hp(m, pp, *_):
    """Max HP from the core record: (IV + 2 * base + EV / 4) * level / 100 + level + 10; 1 for species
    0x124. The level is the party record's, or the one the experience gives."""
    for a in (0xBF41A8, 0xCEDBF4, 0xD97F74, 0xE14B64, 0xE13DA0, 0xD9987C, 0xC1EB6C, 0xD8FAE8):
        _need(m, m.main + a)
    acc = m.u64(pp + 0x70)
    species = m.call(m.main + 0xBF44F4, acc) & 0xFFFF
    if m.u64(acc + 8):
        level = m.call(m.main + 0xD9987C, acc) & 0xFF
    else:
        s = m.call(m.main + 0xBF44F4, acc)
        f = m.call(m.main + 0xBF41A8, m.u64(pp + 0x70))
        e = m.call(m.main + 0xE14B64, m.u64(pp + 0x70))
        level = m.call(m.main + 0xE13DA0, s & 0xFFFFFFFF, f & 0xFFFFFFFF, e & 0xFFFFFFFF) & 0xFF
    s = m.call(m.main + 0xBF44F4, m.u64(pp + 0x70))
    f = m.call(m.main + 0xBF41A8, m.u64(pp + 0x70))
    with m.frame(0x10) as p:
        m.put(p, 8, m.u64(m.main + 0x46D8EE0) + 0x10)
        m.put(p + 8, 2, s); m.put(p + 0xA, 2, f)
        base = m.call(m.main + 0xCEDBF4, p) & 0xFF
    if m.call(m.main + 0xC1EB6C, m.u64(pp + 0x70)) & 1:
        iv = 0x1F
    else:
        iv = m.call(m.main + 0xD97F74, m.u64(pp + 0x70)) & 0xFFFF
    ev = m.call(m.main + 0xD8FAE8, m.u64(pp + 0x70)) & 0xFFFFFFFF
    if species == 0x124:
        return 1
    return (((iv + 2 * base + (ev >> 2 & 0x3FFF)) * level & 0xFFFFFFFF) // 100 + level + 10) & 0xFFFFFFFF


@lifted(0x1536F5C)
def push_cb_pair(m, o, a, b, c, *_):
    """Message 0xcb with (a, c & 0xffff, b's id from vf 0x98) on the queue [o+0x18]."""
    v = m.vcall(b, 0x98)
    return _tail(m, m.main + 0x157EBC0, m.u64(o + 0x18), 0xCB, a & 0xFFFFFFFF, c & 0xFFFF, v & 0xFFFFFFFF,
                 0xFFFF0000)


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


@lifted(0x1535450)
def record_hits(m, o, _x1, ctx, *_):
    """For each of the u8 [ctx+0x18] targets ([ctx+0x20]: battlers at +0, u16 amounts at +0x30): add the
    battler to the member list [ctx+0x28] (pointers +0, u16 sums +0x58, +0x6e, flags +0x84, count +0xa6,
    high mark +0xa7, at most 11) and add the amount to every matching entry, then hand the hit to the
    target's handler (0xf21c94, vf 0x788), message 0x42 and vf 0x508(2)."""
    i = 0
    while i < m.u8(ctx + 0x18):
        lst = m.u64(ctx + 0x28)
        hits = m.u64(ctx + 0x20)
        v = m.u64(hits + 8 * i)
        amount = m.u16(hits + 0x30 + 2 * i)
        n = m.u8(lst + 0xA6)
        if v and n < 0xB and all(m.u64(lst + 8 * k) != v for k in range(n)):
            m.put(lst + 8 * n, 8, v)
            m.put(lst + 0x84 + m.u8(lst + 0xA6), 1, 0)
            m.put(lst + 0x58 + 2 * m.u8(lst + 0xA6), 2, 0)
            m.put(lst + 0x6E + 2 * m.u8(lst + 0xA6), 2, 0)
            n = (m.u8(lst + 0xA6) + 1) & 0xFF
            m.put(lst + 0xA6, 1, n)
            if m.u8(lst + 0xA7) < n:
                m.put(lst + 0xA7, 1, n)
        if n:
            if m.u64(lst) == v:
                m.put(lst + 0x58, 2, m.u16(lst + 0x58) + amount)
                m.put(lst + 0x84, 1, 1)
                n = m.u8(lst + 0xA6)
            if n >= 2:
                if m.u64(lst + 8) == v:
                    m.put(lst + 0x5A, 2, m.u16(lst + 0x5A) + amount)
                    m.put(lst + 0x85, 1, 1)
                    n = m.u8(lst + 0xA6)
                if n >= 3:
                    k = 0
                    while True:
                        if m.u64(lst + 0x10 + 8 * k) == v:
                            m.put(lst + 0x5C + 2 * k, 2, m.u16(lst + 0x5C + 2 * k) + amount)
                            m.put(lst + 0x86 + k, 1, 1)
                            n = m.u8(lst + 0xA6)
                        k += 1
                        if k + 2 >= n:
                            break
        target = m.u64(hits + 8 * i)
        amount = m.u16(hits + 0x30 + 2 * i)
        root = m.u64(m.u64(m.u64(o + 0x78) + 0x60) + 0x20)
        move = m.u64(ctx + 0x10)
        mid, b8, b9 = m.u16(move), m.u8(move + 8), m.u8(move + 9)
        user = m.u64(ctx)
        flag = m.u8(ctx + 8)
        tid = m.vcall(target, 0x98) & 0xFFFFFFFF
        uid = m.vcall(user, 0x98) & 0xFFFFFFFF
        with m.frame(0x10) as p:
            m.put(p, 2, mid); m.put(p + 2, 2, amount); m.put(p + 4, 1, b9); m.put(p + 5, 1, b8)
            m.put(p + 8, 4, uid); m.put(p + 0xC, 1, flag)
            h = m.call(m.main + 0xF21C94, m.u64(m.u64(m.u64(root + 0x20) + 0x10) + 0x30), tid)
            m.vcall_void(h, 0x788, p)
        que = m.u64(root + 0x18)
        tid = m.vcall(target, 0x98) & 0xFFFFFFFF
        uid = m.vcall(user, 0x98) & 0xFFFFFFFF
        m.call_void(m.main + 0x119AFF0, que, 0x42, tid, uid, flag, b8, b9, mid, amount)
        m.vcall_void(m.u64(m.u64(ctx + 0x20) + 8 * i), 0x508, 2)
        i += 1


@lifted(0x15368CC)
def damage_messages(m, o, user, move, n, targets, effects, amounts, *_):
    """For each of n targets: 0x13fced4([o+0x20], target, amount, 3, user) and message 2 (target, user,
    amount, 3); then group 0xd0 of (target id, effect byte) pairs, and message 0x8e (n, 2 when an effect
    byte is above 7, else 3 when one is below 7, else 1, the u16 move)."""
    n &= 0xFFFFFFFF
    hi = lo = 0
    for i in range(n):
        t = m.u64(targets + 8 * i)
        amount = m.u16(amounts + 2 * i)
        uid = m.vcall(user, 0x98) & 0xFFFFFFFF
        tid = m.vcall(t, 0x98) & 0xFFFFFFFF
        m.call_void(m.main + 0x13FCED4, m.u64(o + 0x20), tid, amount, 3, uid)
        tid = m.vcall(t, 0x98) & 0xFFFFFFFF
        m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 2, tid, uid, amount, 3)
        e = m.u8(effects + i)
        hi += e > 7
        lo += e < 7
    que = m.u64(o + 0x18)
    at = m.u32(que + 0x68)
    m.put(que + 0x70 + at, 1, 0)
    m.put(que + 0x70 + ((at + 1) & 0xFFFFFFFF), 1, 0xD0)
    m.put(que + 0x68, 4, at + 3)
    m.put(que + 0x70 + ((at + 2) & 0xFFFFFFFF), 1, n << 1)
    for i in range(n):
        q = m.u64(o + 0x18)
        v = m.vcall(m.u64(targets + 8 * i), 0x98)
        at = m.u32(q + 0x68); m.put(q + 0x68, 4, at + 1); m.put(q + 0x70 + at, 1, v)
        q = m.u64(o + 0x18)
        at = m.u32(q + 0x68); m.put(q + 0x68, 4, at + 1); m.put(q + 0x70 + at, 1, m.u8(effects + i))
    k = 2 if hi & 0xFF else (3 if lo & 0xFF else 1)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x8E, n & 0xFF, k, m.u16(move))


@lifted(0xFAB500)
def clear_12(m, p, *_):
    m.put(p, 8, 0); m.put(p + 8, 4, 0)


@lifted(0xFA98A4)
def clear_fa98a4(m, p, *_):
    m.write(p, bytes(0x1B)); m.put(p + 0x20, 8, 0)


@lifted(0xFA949C)
def clear_fa949c(m, p, *_):
    m.write(p + 0x30, bytes(0x1B)); m.write(p + 0x50, bytes(0x23)); m.write(p + 0x78, bytes(0x23))
    m.put(p + 0xA0, 8, 0)


@lifted(0xFA6268)
def set_30(m, p, v, *_): m.put(p + 0x30, 8, v)


@lifted(0xFAF004)
def clear_2420(m, p, *_): m.put(p + 0x2420, 1, 0)


@lifted(0xFAF010)
def fill_five_from_28(m, p, *_):
    v = m.u64(p + 0x28)
    for k in range(5):
        m.put(p + 8 * k, 8, v)


@lifted(0xFB00C0)
def field_170(m, p, *_): return m.u64(p + 0x170)


@lifted(0xFB00D8)
def field_1d0(m, p, *_): return m.u64(p + 0x1D0)


@lifted(0xFA58C0)
def byte_e3(m, p, *_): return m.u8(p + 0xE3)


@lifted(0x16F814C)
def byte_712_of_38(m, p, *_): return m.u8(m.u64(p + 0x38) + 0x712)


@lifted(0xFA38C8)
def kind_2_in_37(m, a, b, *_):
    """1 when a is 2 and b - 1 (0..5) is a set bit of 0x37."""
    k = (b - 1) & 0xFFFFFFFF
    if a & 0xFFFFFFFF == 2 and k & 0xFF <= 5:
        return 0x37 >> (k & 0x1F) & 1
    return 0


@lifted(0xFA47C8)
def copy_24_to_40(m, p, src, *_):
    m.put(p + 0x40, 8, m.u64(src)); m.put(p + 0x50, 8, m.u64(src + 0x10)); m.put(p + 0x48, 8, m.u64(src + 8))


@lifted(0xFA0154)
def spread_8c(m, o, dst, *_):
    """0xfa01f8(0xfa01f0(dst), i, u16 o+0x8c) for i in 0..4."""
    for i in range(4):
        m.call_void(m.main + 0xFA01F8, m.call(m.main + 0xFA01F0, dst), i, m.u16(o + 0x8C))
    return _tail(m, m.main + 0xFA01F8, m.call(m.main + 0xFA01F0, dst), 4, m.u16(o + 0x8C))


@lifted(0x127E0C8)
def init_entries_127e0c8(m, p, *_):
    """30 entries of 0x10 from +0x10: u64 0, u32 0x102, bytes +0xc and +0xe cleared."""
    for k in range(1, 0x1F):
        e = p + 0x10 * k
        m.put(e, 8, 0); m.put(e + 8, 4, 0x102); m.put(e + 0xC, 1, 0); m.put(e + 0xE, 1, 0)
    return p + 0xD0  # x0 after the pre-indexed stores


@lifted(0x127DCFC)
def clear_flags_127dcfc(m, p, *_):
    for k in range(50):
        m.put(p + 0x15 + 0x18 * k, 1, 0)


def _move_ref(m, dst, src, *_):
    """Move-assign an intrusive reference (u32 count at +0x28): drop dst's object (vf 0x10 at the last
    reference), then take src's and clear src."""
    old = m.u64(dst)
    if old:
        count = m.u32(old + 0x28)
        if count == 0:
            raise UnliftedCall("DecrementReference abort: counter underflow")
        if count == 1:
            _need(m, m.u64(m.u64(old) + 0x10))
    m.put(dst, 8, 0)
    if old:
        m.put(old + 0x28, 4, count - 1)
        if count == 1:
            m.vcall_void(old, 0x10)
    v = m.u64(src)
    m.put(src, 8, 0)
    m.put(dst, 8, v)


for _a in (0xFAB6BC, 0xFAB860):
    lifted(_a)(_move_ref)


@lifted(0xFA6424)
def assign_shared(m, dst, new, *_):
    """Store `new` at dst after taking a reference on its control block (+0x30: object +0x10, u16 count
    +0x1a; the first reference builds +8 through vf 0 of +0x10), then drop the old object's (the last
    one clears +0x10 and runs its vf 0x50). The old object is the result."""
    if new:
        ctl = m.u64(new + 0x30)
        inner = m.u64(ctl + 0x10)
        if inner == 0:
            raise UnliftedCall("AddReference abort: m_object is null")
        count = m.u16(ctl + 0x1A)
        if count == 0xFFFF:
            raise UnliftedCall("AddReference abort: counter overflow")
        if count == 0:
            _need(m, m.u64(m.u64(inner)))
    old = m.u64(dst)
    if old:
        oc = m.u16(m.u64(old + 0x30) + 0x1A)
        if oc == 0 and not (new and m.u64(new + 0x30) == m.u64(old + 0x30)):
            raise UnliftedCall("ReleaseReference abort: counter underflow")
        if oc == 1 and not (new and m.u64(new + 0x30) == m.u64(old + 0x30)):
            _need(m, m.u64(m.u64(old) + 0x50))
    if new:
        m.put(ctl + 0x1A, 2, count + 1)
        if count == 0:
            m.put(ctl + 8, 8, m.vcall(inner, 0))
            m.put(ctl + 0x1C, 4, 0xFFFFFFFE)
    old = m.u64(dst)
    m.put(dst, 8, new)
    if old == 0:
        return 0
    ctl = m.u64(old + 0x30)
    c = m.u16(ctl + 0x1A)
    m.put(ctl + 0x1A, 2, c - 1)
    if c == 1:
        m.put(ctl + 0x10, 8, 0)
        return _vtail(m, old, 0x50)
    if c == 0:
        raise UnliftedCall("ReleaseReference abort: counter underflow")
    return old


lifted(0xFA95F8)(_move_ref)


@lifted(0xFA0028)
def side_slot_typed(m, o, side, k, *_):
    """Entry k of side's list (o + side*0x38: objects +0x28, count u8 +0x58) when the type list from its
    +0x28 interface (vf 0) holds the static 0x46d3f08; else 0."""
    side &= 0xFF; k &= 0xFF
    if side > 4 or m.u8(o + side * 0x38 + 0x58) <= k:
        return 0
    obj = m.u64(o + side * 0x38 + 8 * k + 0x28)
    if obj == 0:
        return 0
    node = m.vcall(obj + 0x28, 0)
    if m.u8(m.u64(m.main + 0x46D3F00)) & 1 == 0:
        raise UnliftedCall("static 0x46d3f08 not built")
    static = m.u64(m.main + 0x46D3F08)
    while node:
        if node == static:
            return obj
        node = m.u64(node)
    return 0


@lifted(0x1142D98)
def run_1142dcc(m, o, *_):
    """0x1142dcc(0x1142dc4([o+0x78]), two out slots on the stack)."""
    with m.frame(0x10) as p:
        return _tail(m, m.main + 0x1142DCC, m.call(m.main + 0x1142DC4, m.u64(o + 0x78)), p, p + 8)


@lifted(0x17D3110)
def run_17d3154(m, o, a, b, c, *_):
    """0x17d3154(0x17d314c([o+0x78]), an out slot, &{a, u16 b, c & 1})."""
    with m.frame(0x20) as p:
        m.put(p + 8, 8, a); m.put(p + 0x10, 2, b); m.put(p + 0x12, 1, c & 1)
        return _tail(m, m.main + 0x17D3154, m.call(m.main + 0x17D314C, m.u64(o + 0x78)), p, p + 8)


@lifted(0x1858568)
def release_shared(m, p, *_):
    """Drop a reference on [p]'s control block (+0x30, u16 count +0x1a); the last one clears +0x10 and
    runs the object's vf 0x50."""
    obj = m.u64(p)
    if obj == 0:
        return 0
    ctl = m.u64(obj + 0x30)
    c = m.u16(ctl + 0x1A)
    if c == 0:
        raise UnliftedCall("ReleaseReference abort: counter underflow")
    if c == 1:
        _need(m, m.u64(m.u64(obj) + 0x50))
    m.put(ctl + 0x1A, 2, c - 1)
    if c == 1:
        m.put(ctl + 0x10, 8, 0)
        return _vtail(m, obj, 0x50)
    return obj


lifted(0x18584F0)(release_shared)


@lifted(0x18B7E00)
def find_u32_at(m, table, key_ptr, *_):
    """The node holding the u32 at key_ptr, or 0."""
    from pokeldn.sv.battle.engine.containers import find
    return find(m, table, m.u32(key_ptr), 4)


@lifted(0xF79790)
def battler_checked(m, o, ident, *_):
    """The battler with id `ident` (map o+0x140) when present (count, then at), else 0."""
    return battler(m, o, ident)


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


@lifted(0x13608B0)
def release_if_live(m, o, e, *_):
    """Release a live element (+0x44) to the free list of [[o+8]+0xd0] (0x13608e0); one still held
    (+0x3f) is marked for release instead (0x1360cdc(e, 1))."""
    if e == 0 or m.u8(e + 0x44) == 0:
        return
    if m.u8(e + 0x3F):
        return _tail(m, m.main + 0x1360CDC, e, 1)
    return _tail(m, m.main + 0x13608E0, m.u64(m.u64(o + 8) + 0xD0), e)


@lifted(0x114ED80)
def new_entry(m, o, kind, key, level, low, value, ptr, flag, *_):
    """Take the head of the free list of [[o+8]+0xd0] (0x119baac(-1)), fill it (kind +0x28, ptr +0x20,
    key +0x30, value +0x34, value again +0x38 for kinds 0, 4 and 5, (~level << 24) + 0x9000000 | low at
    +0x2c, flag +0x3e, u16 [o+0x80] at +0x3c, live +0x44) and add it with 0x119b6cc."""
    _need(m, m.main + 0x119B6CC)
    serial = m.u32(o + 0x80)
    table = m.u64(m.u64(o + 8) + 0xD0)
    e = m.call(m.main + 0x119BAAC, table, 0xFFFFFFFF)
    if e == 0:
        return 0
    k = kind & 0xFF
    v2 = value if (1 << (k & 0x1F)) & 0x31 else 0
    if k > 5:
        v2 = 0
    m.put(e + 0x12, 4, 0xEE00EE)
    m.write(e + 0x18, bytes(0x58))
    m.put(e + 0x2C, 4, ((~level & 0xFFFFFFFF) << 24) + 0x9000000 | low & 0xFFFFFFFF)
    m.put(e + 0x28, 1, kind)
    m.put(e + 0x20, 8, ptr)
    m.put(e + 0x3E, 1, flag)
    m.put(e + 0x30, 2, key)
    m.put(e + 0x34, 4, value)
    m.put(e + 0x38, 4, v2)
    m.put(e + 0x3C, 2, serial)
    m.put(e + 0x44, 1, 1)
    m.call_void(m.main + 0x119B6CC, table, e)
    return e


@lifted(0x114D844)
def first_live_of_kind(m, owner, kind, *_):
    """The first element of the active list (head key owner+0x70) that is live (+0x44), of kind `kind`
    (+0x28) and not retired (+0x41); else 0."""
    from pokeldn.sv.battle.engine.containers import _element
    e = _element(m, owner + 8, m.u16(owner + 0x70))
    while e:
        if m.u8(e + 0x44) and m.u8(e + 0x28) == kind & 0xFF and m.u8(e + 0x41) == 0:
            return e
        e = _element(m, m.u64(e + 8) + 8, m.u16(e + 0x14))
    return 0


def _peek_block_u16(m, acc, logical, off):
    """The u16 at `off` of logical block `logical` as an accessor would read it, without touching the
    record (decrypted on a copy)."""
    core = m.u64(acc + 0x10)
    data = bytearray(m.read(core, _pk.CORE))
    if m.u8(acc + 0x18):
        seed = int.from_bytes(data[0:4], "little")
        for i in range(_pk.BLOCKS, _pk.CORE, 2):
            seed = _pk._lcg(seed)
            v = (data[i] | data[i + 1] << 8) ^ (seed >> 16)
            data[i], data[i + 1] = v & 0xFF, v >> 8
        total = sum(data[i] | data[i + 1] << 8 for i in range(_pk.BLOCKS, _pk.CORE, 2)) & 0xFFFF
        if total != (data[6] | data[7] << 8):
            data[4] |= 4
    if data[4] >> 2 & 1:
        return m.u16(m.main + _pk.BAD_READ_CORE + _pk.BLOCKS + 0x50 * logical + off)
    pos = _pk.BLOCK_POSITION[(int.from_bytes(data[0:4], "little") >> 13) & 0x1F][logical]
    at = _pk.BLOCKS + 0x50 * pos + off
    return data[at] | data[at + 1] << 8


@lifted(0x133B218)
def change_form(m, pp, form, ctx, *_):
    """Give the Pokemon form `form` unless it has it: 0x133ba0c, the form (0xdf289c), the ability for
    (species, form, 0xd99784) (0x133b78c, 0xdf2550), 0x133b4b4 of the gender (0xdf644c), then the stats
    (0xe13b9c(pp, 1))."""
    _need(m, m.main + 0xBF41A8)
    if _peek_block_u16(m, m.u64(pp + 0x70), 0, 0x1C) != form & 0xFFFF:
        for a in (0x133BA0C, 0xDF289C, 0xD99784, 0x133B78C, 0xDF2550, 0xBEC030, 0x133B4B4, 0xDF644C, 0xE13B9C):
            _need(m, m.main + a)
    acc = m.u64(pp + 0x70)
    species = m.call(m.main + 0xBF44F4, acc) & 0xFFFFFFFF
    if m.call(m.main + 0xBF41A8, m.u64(pp + 0x70)) & 0xFFFF == form & 0xFFFF:
        return
    form &= 0xFFFFFFFF
    m.call_void(m.main + 0x133BA0C, pp, form, ctx)
    m.call_void(m.main + 0xDF289C, m.u64(pp + 0x70), form)
    g = m.call(m.main + 0xD99784, pp)
    a = m.call(m.main + 0x133B78C, species, form, g & 0xFFFFFFFF)
    m.call_void(m.main + 0xDF2550, m.u64(pp + 0x70), a & 0xFFFFFFFF)
    g = m.call(m.main + 0xBEC030, m.u64(pp + 0x70))
    a = m.call(m.main + 0x133B4B4, species, form, g & 0xFFFFFFFF)
    m.call_void(m.main + 0xDF644C, m.u64(pp + 0x70), a & 0xFFFFFFFF)
    return _tail(m, m.main + 0xE13B9C, pp, 1)


def _copy_side_records(m, b):
    """Copy the four 10-byte records at +0x426/+0x43c/+0x452/+0x468 to +0x430/+0x446/+0x45c/+0x472
    (u64 then a byte), mark each copied (+0x43a, +0x450, +0x466) and count those with a non-zero u16
    in +0x482."""
    m.put(b + 0x482, 1, 0)
    v = m.u64(b + 0x426)
    m.put(b + 0x430, 8, v)
    m.put(b + 0x438, 1, m.u8(b + 0x42E))
    n = 1 if v & 0xFFFF else 0
    if n:
        m.put(b + 0x482, 1, n)
    for src, dst, flag, byte_src, byte_dst in ((0x43C, 0x446, 0x43A, 0x444, 0x44E), (0x452, 0x45C, 0x450, 0x45A, 0x464),
                                               (0x468, 0x472, 0x466, 0x470, 0x47A)):
        bv = m.u8(b + byte_src)
        m.put(b + flag, 1, 1)
        m.put(b + byte_dst, 1, bv)
        v = m.u64(b + src)
        m.put(b + dst, 8, v)
        if v & 0xFFFF:
            n += 1
            m.put(b + 0x482, 1, n)


@lifted(0x2D3DC58)
def reset_on_switch(m, b, *_):
    """A battler's reset when it is sent out: the side records copied (_copy_side_records), the turn
    state and the 48 handler slots cleared, the stat stages back to 6, max HP from the core (vf 0x70(0)
    times +0x3f4 / 10) with the HP adjusted to it (vf 0x2e8 / 0x2e0), then vf 0x810; flag 0x1c is
    restored through vf 0x4d8 when vf 0x4d0 had it."""
    vt = m.u64(b)
    for slot in (0x4D0, 0x568, 0x2D0, 0x580, 0x108, 0x110, 0x810, 0x2E8, 0x2E0):
        _need(m, m.u64(vt + slot))
    _need(m, m.main + 0x14807D0)
    _need(m, m.u64(m.u64(m.u64(b + 0x48)) + 0x70))
    if m.u8(b + 0x6C):
        _need(m, m.u64(vt + 0x7F0))
    flag = m.vcall(b, 0x4D0, 0x1C)
    if flag & 1:
        _need(m, m.u64(vt + 0x4D8))
    m.put(b + 0x496, 4, 0)
    m.call_void(m.main + 0x14807D0, b)
    if m.u8(b + 0x6C):
        m.vcall_void(b, 0x7F0, 0, 1, 1, 1)
        _copy_side_records(m, b)
        m.put(b + 0x47C, 1, 1)
        m.put(b + 0x6C, 1, 0)
    _copy_side_records(m, b)
    m.put(b + 0x486, 1, 0x12)
    m.put(b + 0x47C, 1, 1)
    for off in (0x435, 0x42B, 0x44B, 0x441, 0x461, 0x457, 0x477, 0x46D):
        m.put(b + off, 1, 0)
    m.put(b + 0x490, 4, 0)
    m.put(b + 0x48C, 2, 0)
    m.put(b + 0x5A0, 8, 0)
    m.vcall_void(b, 0x568)
    m.vcall_void(b, 0x2D0)
    m.put(b + 0x487, 1, 1)
    m.vcall_void(b, 0x580)
    for k in range(48):
        m.put(b + 0x88 + 0x10 * k, 8, 0)
    m.put(b + 0x3C0, 1, 0)
    m.write(b + 0x388, bytes(0x38))
    for k in range(7):
        m.put(b + 0x414 + k, 1, 6)
    m.put(b + 0x47E, 2, m.u16(b + 0x60))
    hp = m.vcall(b, 0x108) & 0xFFFFFFFF
    cur = m.vcall(b, 0x110) & 0xFFFFFFFF
    base = m.vcall(m.u64(b + 0x48), 0x70, 0) & 0xFFFF
    top = ((base * m.u16(b + 0x3F4)) & 0xFFFFFFFF) // 10
    m.put(b + 0x58, 2, top)
    top16 = top & 0xFFFF
    if cur & 0xFFFF < top16:
        m.vcall_void(b, 0x2E8, (top - cur) & 0xFFFFFFFF)
    if cur & 0xFFFF > top16 and hp & 0xFFFF > top16:
        m.vcall_void(b, 0x2E0, (hp - top) & 0xFFFFFFFF)
    m.vcall_void(b, 0x810)
    if flag & 1:
        return _vtail(m, b, 0x4D8, 0x1C)


@lifted(0x2842E80)
def battler_308(m, o, ident, *_):
    """vf 0x308 of the battler with id `ident` (0xf79790 on [[o+8]+0x30])."""
    b = m.call(m.main + 0xF79790, m.u64(m.u64(o + 8) + 0x30), ident)
    return _vtail(m, b, 0x308)


# Nature modifiers (0x3c62e98, 5 bytes per nature: Atk, Def, Spe, SpA, SpD; 1 raised, 0xff lowered).
_NATURE = (
    (0, 0, 0, 0, 0), (1, 255, 0, 0, 0), (1, 0, 0, 0, 255), (1, 0, 255, 0, 0), (1, 0, 0, 255, 0),
    (255, 1, 0, 0, 0), (0, 0, 0, 0, 0), (0, 1, 0, 0, 255), (0, 1, 255, 0, 0), (0, 1, 0, 255, 0),
    (255, 0, 0, 0, 1), (0, 255, 0, 0, 1), (0, 0, 0, 0, 0), (0, 0, 255, 0, 1), (0, 0, 0, 255, 1),
    (255, 0, 1, 0, 0), (0, 255, 1, 0, 0), (0, 0, 1, 0, 255), (0, 0, 0, 0, 0), (0, 0, 1, 255, 0),
    (255, 0, 0, 1, 0), (0, 255, 0, 1, 0), (0, 0, 0, 1, 255), (0, 0, 255, 1, 0), (0, 0, 0, 0, 0))


def _computed_stat(base_fn, trained_bit, iv_fn, ev_fn, column):
    """A stat from the core record: (IV, or 31 when hyper trained, + 2 * base + EV / 4) * level / 100 + 5,
    times 1.1 or 0.9 for the nature."""
    def fn(m, pp, *_):
        for a in (0xBF41A8, base_fn, iv_fn, ev_fn, 0xC4EA44, 0xE14B64, 0xE13DA0, 0xD9987C):
            _need(m, m.main + a)
        acc = m.u64(pp + 0x70)
        if m.u64(acc + 8):
            level = m.call(m.main + 0xD9987C, acc) & 0xFF
        else:
            s = m.call(m.main + 0xBF44F4, acc)
            f = m.call(m.main + 0xBF41A8, m.u64(pp + 0x70))
            e = m.call(m.main + 0xE14B64, m.u64(pp + 0x70))
            level = m.call(m.main + 0xE13DA0, s & 0xFFFFFFFF, f & 0xFFFFFFFF, e & 0xFFFFFFFF) & 0xFF
        s = m.call(m.main + 0xBF44F4, m.u64(pp + 0x70))
        f = m.call(m.main + 0xBF41A8, m.u64(pp + 0x70))
        with m.frame(0x10) as p:
            m.put(p, 8, m.u64(m.main + 0x46D8EE0) + 0x10)
            m.put(p + 8, 2, s); m.put(p + 0xA, 2, f)
            base = m.call(m.main + base_fn, p) & 0xFF
        if m.call(m.main + 0xC1EB6C, m.u64(pp + 0x70)) >> trained_bit & 1:
            iv = 0x1F
        else:
            iv = m.call(m.main + iv_fn, m.u64(pp + 0x70)) & 0xFFFF
        ev = m.call(m.main + ev_fn, m.u64(pp + 0x70)) & 0xFFFFFFFF
        nature = m.call(m.main + 0xC4EA44, m.u64(pp + 0x70)) & 0xFFFF
        v = (((iv + 2 * base + (ev >> 2 & 0x3FFF)) * level & 0xFFFFFFFF) // 100 + 5) & 0xFFFFFFFF
        mod = _NATURE[nature][column] if nature < len(_NATURE) else m.u8(m.main + 0x3C62E98 + 5 * nature + column)
        if mod == 0xFF:
            return (v * 90 & 0xFFFE) // 100
        if mod == 1:
            return (v * 110 & 0xFFFE) // 100
        return v
    return fn


for _a, _spec in ((0xE142B0, (0xCEDF60, 2, 0xD98604, 0xD90170, 1)), (0xE146B8, (0xCEE488, 4, 0xD98FDC, 0xD90B3C, 3))):
    lifted(_a)(_computed_stat(*_spec))


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


@lifted(0x17CDF14)
def apply_pending_codes(m, o, out, req, *_):
    """For each of the u8 [req+0x30] battlers (ids at req+8) able to act (vf 0x208), consume its pending
    codes (0x17ce294 on a copy of req+4) until none is left: code 0x1c may be skipped by 0x17ce520;
    each other one is recorded (0x17ce41c) and applied (0x17ce354 when +0x35, else 0x114a970 then
    0x114b0ac), code 0x13 also runs 0x287fe9c, and out[0] / out[1 + i] are set. With +0x34 the run is
    bracketed by 0x17ce0e4 / 0x17ce27c."""
    bracket = m.u8(req + 0x34)
    if bracket:
        for a in (0x1143584, 0x17CE0E4, 0x17CE27C):
            _need(m, m.main + a)
    if m.u8(req + 0x30):
        for a in (0x17CE294, 0x17CE520, 0x1146E90, 0x179372C, 0x17CE41C, 0x1143584, 0x114A970, 0x114B0AC,
                  0x287FE9C, 0x1146154):
            _need(m, m.main + a)
    m.put(out + 5, 8, 0)
    m.put(out, 8, 0)
    if bracket:
        m.call_void(m.main + 0x17CE0E4, m.call(m.main + 0x1143584, o), m.u32(req))
    if m.u8(req + 0x30):
        i = 0
        with m.frame(0x50) as sp:
            while True:
                b = m.call(m.main + 0x13813F4, o, m.u32(req + 8 + 4 * i))
                if m.vcall(b, 0x208) & 1:
                    m.put(sp + 0x14, 4, m.u32(req + 4))
                    while True:
                        code = m.call(m.main + 0x17CE294, 0, b, sp + 0x14) & 0xFFFFFFFF
                        if code & 0xFFFF == 0:
                            break
                        if code & 0xFFFF == 0x1C and m.call(m.main + 0x17CE520, m.call(m.main + 0x1146E90, o), b) & 1:
                            continue
                        m.call_void(m.main + 0x179372C, sp)
                        m.call_void(m.main + 0x17CE41C, m.call(m.main + 0x1143584, o), b, code, sp)
                        who = m.u32(req)
                        if m.u8(req + 0x35):
                            m.call_void(m.main + 0x17CE354, o, who, req + 0x38)
                        else:
                            key = m.u16(req + 0x32)
                            m.call_void(m.main + 0x1146154, sp + 0x18)
                            ident = m.vcall(b, 0x98) & 0xFFFFFFFF
                            if m.call(m.main + 0x114A970, code, sp, ident, key, sp + 0x18) & 1:
                                m.call_void(m.main + 0x114B0AC, m.call(m.main + 0x1143584, o), who, sp + 0x18)
                        if code & 0xFFFF == 0x13:
                            m.call_void(m.main + 0x287FE9C, o, b)
                        m.put(out, 1, 1)
                        m.put(out + i + 1, 1, 1)
                i += 1
                if i >= m.u8(req + 0x30):
                    break
    if bracket:
        m.call_void(m.main + 0x17CE27C, m.call(m.main + 0x1143584, o), m.u32(req))


@lifted(0x149FEDC)
def max_118_unmatched(m, o, *_):
    """The largest vf 0x118 byte (at least 1) over the battlers the iterator 0x1147754([o+8], [o+0x10])
    hands out for which 0x1142ecc(0x13813ec([o+0x10]), 0x149fe8c([o+8]), 0x1589a40(o, id)) is false."""
    best = 1
    with m.frame(0x30) as it:
        cur = it + 0x28
        m.put(cur, 8, 0)
        m.call_void(m.main + 0x1147754, it, m.u64(o + 8), m.u64(o + 0x10))
        while m.call(m.main + 0x1360DBC, it, cur) & 1:
            a = m.call(m.main + 0x149FE8C, m.u64(o + 8)) & 0xFFFFFFFF
            ident = m.vcall(m.u64(cur), 0x98) & 0xFFFFFFFF
            c = m.call(m.main + 0x1589A40, o, ident) & 0xFFFFFFFF
            if m.call(m.main + 0x1142ECC, m.call(m.main + 0x13813EC, m.u64(o + 0x10)), a, c) & 1 == 0:
                v = m.vcall(m.u64(cur), 0x118) & 0xFF
                best = max(best, v)
    return best


@lifted(0x2888060)
def send_record(m, o, req, side, *_):
    """Unless the u16 req+0x1a is 0x9c, 0x2888154(0x17d31e0(o, [req]), 0x28230f4(..., side, 0), it); then
    0x114b0ac([req], a copy of req+0x20 (0x28800b8), with 0x2888170(0, side) when +0x44), bracketed by
    0x17ce0e4 / 0x17ce27c when +0x1c."""
    need = [0x28800B8, 0x1143584, 0x114B0AC]
    if m.u16(req + 0x1A) != 0x9C:
        need += [0x17D31E0, 0x1482534, 0x13813EC, 0x28230F4, 0x2888154]
    if m.u8(req + 0x1C):
        need += [0x17CE0E4, 0x17CE27C]
    if m.u8(req + 0x44):
        need += [0x2888170]
    for a in need:
        _need(m, m.main + a)
    if m.u16(req + 0x1A) != 0x9C:
        a = m.call(m.main + 0x17D31E0, o, m.u32(req)) & 0xFFFFFFFF
        t = m.call(m.main + 0x13813EC, m.call(m.main + 0x1482534, o))
        b = m.call(m.main + 0x28230F4, t, side & 0xFFFFFFFF, 0) & 0xFFFFFFFF
        m.call_void(m.main + 0x2888154, m.call(m.main + 0x1143584, o), a, b, m.u16(req + 0x1A))
    if m.u8(req + 0x1C):
        m.call_void(m.main + 0x17CE0E4, m.call(m.main + 0x1143584, o), m.u32(req))
    with m.frame(0x30) as p:
        m.call_void(m.main + 0x28800B8, p, req + 0x20)
        if m.u8(req + 0x44):
            m.call_void(m.main + 0x2888170, p, 0, side & 0xFF)
        m.call_void(m.main + 0x114B0AC, m.call(m.main + 0x1143584, o), m.u32(req), p)
    if m.u8(req + 0x1C):
        m.call_void(m.main + 0x17CE27C, m.call(m.main + 0x1143584, o), m.u32(req))


@lifted(0xB4E600)
def thread_block(m, *_):
    """The calling thread's 0x12d0-byte block in TLS slot u32 0x4759408, allocated zeroed through the
    allocator at 0x4759430 (vf 0x10) on first use."""
    if m.u8(m.main + 0x4759410) & 1 == 0:
        raise UnliftedCall("static 0x4759408 not built")
    slot = m.u32(m.main + 0x4759408)
    if m.call(m.main + 0x343DA20, slot) == 0:
        if m.u8(m.main + 0x4759438) & 1 == 0:
            raise UnliftedCall("static 0x4759430 not built")
        block = m.vcall(m.u64(m.main + 0x4759430), 0x10, 0x12D0, 8)
        m.write(block, bytes(0x12D0))
        m.call_void(m.main + 0x343DA30, m.u32(m.main + 0x4759408), block)
    return m.call(m.main + 0x343DA20, m.u32(m.main + 0x4759408))


@lifted(0xFA9DA8)
def copy_ref_190(m, src, *_):
    """The intrusive reference at src+0x190, copied into the result (x8) with its count (+0x28) raised."""
    out = m.x8
    v = m.u64(src + 0x190)
    if v and m.u32(v + 0x28) == 0xFFFFFFFF:
        raise UnliftedCall("IncrementReference abort: counter overflow")
    m.put(out, 8, v)
    if v:
        m.put(v + 0x28, 4, m.u32(v + 0x28) + 1)
    return src


@lifted(0x2899DE0)
def set_stat_multiplier(m, b, which, value, *_):
    """Battler vf 0x1c8: store vf 0x1d0 - value as multiplier `which` of the block at +0x3f4 (0x171cac8),
    then recompute that stat (0x171cb20)."""
    _need(m, m.main + 0x171CAC8)
    _need(m, m.main + 0x171CB20)
    v = m.vcall(b, 0x1D0, which, value)  # x1, x2 pass through to the getter
    m.call_void(m.main + 0x171CAC8, b + 0x3F4, which & 0xFFFFFFFF, (v - value) & 0xFFFFFFFF)
    return _tail(m, m.main + 0x171CB20, b, which & 0xFFFFFFFF)


def _tls_top(m):
    """(the TLS block of slot u32 0x4765a30, the last of its u64 entries counted at +0x80, or 0)."""
    if m.u8(m.main + 0x4765A38) & 1 == 0:
        raise UnliftedCall("static 0x4765a30 not built")
    v = m.call(m.main + 0x343DA20, m.u32(m.main + 0x4765A30))
    if v == 0 or m.u64(v + 0x80) == 0:
        return v, 0
    return v, m.u64(v + 8 * m.u64(v + 0x80) - 8)


@lifted(0xFAC3A0)
def init_fac3a0(m, p, *_):
    """Construct the object: vtables 0x44ed828 / 0x44ed860, +8 the current TLS entry (_tls_top), and at
    +0x48 the record 0xfac480 builds (the entry again, 0x1fffffffffffffff, 0, 0)."""
    _, top = _tls_top(m)
    if top == 0:
        raise UnliftedCall("main+0xf60ed0")
    m.put(p + 0x10, 8, 0); m.put(p + 0x18, 4, 0)
    m.put(p, 8, m.u64(m.main + 0x46D66F8) + 0x10)
    m.put(p + 0x28, 4, 0)
    m.put(p, 8, m.main + 0x44ED828); m.put(p + 8, 8, top)
    m.put(p + 0x20, 8, m.main + 0x44ED860)
    m.put(p + 0x40, 8, 0); m.put(p + 0x30, 8, 0); m.put(p + 0x38, 8, 0)
    v, top = _tls_top(m)
    q = p + 0x48
    m.put(q + 0x18, 4, 0); m.put(q, 8, top); m.put(q + 8, 8, 0x1FFFFFFFFFFFFFFF); m.put(q + 0x10, 8, 0)
    return v


@lifted(0xFA5E0C)
def copy_shared_in_context(m, ctx, out, src, *_):
    """With [ctx] pushed on the TLS context stack (slot 0x4765a30, at most 16 entries, count +0x80):
    *out = *src, taking a reference on its control block (+0x30; the first builds +8 through vf 0 of
    +0x10)."""
    if m.u8(m.main + 0x4765A38) & 1 == 0:
        raise UnliftedCall("static 0x4765a30 not built")
    v = m.call(m.main + 0x343DA20, m.u32(m.main + 0x4765A30))
    if v and m.u64(v + 0x80) >= 0x10:
        raise UnliftedCall("TLS context stack full")
    obj = m.u64(src)
    if obj:
        ctl = m.u64(obj + 0x30)
        if m.u64(ctl + 0x10) == 0:
            raise UnliftedCall("AddReference abort: m_object is null")
        count = m.u16(ctl + 0x1A)
        if count == 0xFFFF:
            raise UnliftedCall("AddReference abort: counter overflow")
        if count == 0:
            _need(m, m.u64(m.u64(m.u64(ctl + 0x10))))
    r = v
    if v:
        n = m.u64(v + 0x80)
        m.put(v + 8 * n, 8, m.u64(ctx))
        m.put(v + 0x80, 8, n + 1)
    m.put(out, 8, obj)
    if obj:
        m.put(ctl + 0x1A, 2, count + 1)
        if count == 0:
            r = m.vcall(m.u64(ctl + 0x10), 0)
            m.put(ctl + 8, 8, r)
            m.put(ctl + 0x1C, 4, 0xFFFFFFFE)
    if v:
        m.put(v + 0x80, 8, m.u64(v + 0x80) - 1)
    return r


@lifted(0xFA6BBC)
def at_u32(m, table, key_ptr, *_):
    """unordered_map::at for the u32 at key_ptr: the value slot (node+0x18); a missing key throws."""
    from pokeldn.sv.battle.engine.containers import find
    node = find(m, table, m.u32(key_ptr), 4)
    if node == 0:
        raise UnliftedCall("unordered_map::at: key not found")
    return node + 0x18


@lifted(0xFA38F8)
def assign_ref(m, dst, new, *_):
    """Copy-assign an intrusive reference (u32 count at +0x28): raise new's count, store it, drop the old
    object's (vf 0x10 at the last reference)."""
    if new and m.u32(new + 0x28) == 0xFFFFFFFF:
        raise UnliftedCall("IncrementReference abort: counter overflow")
    old = m.u64(dst)
    if old:
        c = m.u32(old + 0x28) + (1 if old == new else 0)
        if c == 0:
            raise UnliftedCall("DecrementReference abort: counter underflow")
        if c == 1:
            _need(m, m.u64(m.u64(old) + 0x10))
    if new:
        m.put(new + 0x28, 4, m.u32(new + 0x28) + 1)
    m.put(dst, 8, new)
    if old == 0:
        return 0
    c = m.u32(old + 0x28)
    m.put(old + 0x28, 4, c - 1)
    if c == 1:
        return _vtail(m, old, 0x10)
    return old


def _map_clear(m, buckets, first, alloc, size, node_size):
    """unordered_map::clear: free each node (the allocator's vf 0x18(node, size, 4), or 0xb48fe8 when its
    vf 0xf8 says frees are deferred and the thread block's +0x12c8 is positive), then zero the buckets."""
    if m.u64(size) == 0:
        return
    node = m.u64(first)
    while node:
        a = m.u64(alloc)
        nxt = m.u64(node)
        if m.vcall(a, 0xF8) & 1 and m.s(m.call(m.main + 0xB4E600) + 0x12C8, 4) >= 1:
            m.call_void(m.main + 0xB48FE8, a, node, node_size, 4)
        else:
            m.vcall_void(a, 0x18, node, node_size, 4)
        node = nxt
    m.put(first, 8, 0)
    n = m.u64(buckets + 8)
    for i in range(n):
        m.put(m.u64(buckets) + 8 * i, 8, 0)
    m.put(size, 8, 0)


def _need_free(m, alloc, first):
    if m.u64(first):
        a = m.u64(alloc)
        _need(m, m.u64(m.u64(a) + 0xF8)); _need(m, m.u64(m.u64(a) + 0x18)); _need(m, m.main + 0xB48FE8)


@lifted(0x127DDC8)
def clear_127ddc8(m, p, *_):
    """Clear +0x70 and the map at +8 (first node +0x38, allocator +0x40, size +0x60, nodes 0x20)."""
    if m.u64(p + 0x60):
        _need_free(m, p + 0x40, p + 0x38)
    m.put(p + 0x70, 4, 0)
    _map_clear(m, p + 8, p + 0x38, p + 0x40, p + 0x60, 0x20)


@lifted(0x127E548)
def clear_127e548(m, p, *_):
    """Zero +8..+0x2ec and clear the map at +0x2f0 (first node +0x320, allocator +0x328, size +0x348,
    nodes 0x18)."""
    if m.u64(p + 0x348):
        _need_free(m, p + 0x328, p + 0x320)
    m.write(p + 8, bytes(0x2E4))
    _map_clear(m, p + 0x2F0, p + 0x320, p + 0x328, p + 0x348, 0x18)


@lifted(0x127E8B4)
def release_all_127e8b4(m, owner, *_):
    """Hand every element of the active list (head key owner+0x70) to 0x127c86c in order (the next one
    looked up before), then mark the list empty (0xee)."""
    from pokeldn.sv.battle.engine.containers import _element
    e = _element(m, owner + 8, m.u16(owner + 0x70))
    if e:
        _need(m, m.main + 0x127C86C)
    while e:
        nxt = _element(m, m.u64(e + 8) + 8, m.u16(e + 0x14))
        m.call_void(m.main + 0x127C86C, owner, e)
        e = nxt
    m.put(owner + 0x70, 2, 0xEE)


@lifted(0x114EB70)
def note_718_in_side(m, o, b, *_):
    """For a battler whose type list (+0x28 interface, vf 0) holds the static 0x46d3f08: store its u16
    +0x718 at +6 of the entry holding its id among the six 0x10-byte entries from +0x10 of its side's
    0x60-byte row ([[o+0x10]+0x250]; side from the setup map, 0..4)."""
    node = m.vcall(b + 0x28, 0)
    if m.u8(m.u64(m.main + 0x46D3F00)) & 1 == 0:
        raise UnliftedCall("static 0x46d3f08 not built")
    static = m.u64(m.main + 0x46D3F08)
    while node != static:
        if node == 0:
            return
        node = m.u64(node)
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    v = m.u16(b + 0x718)
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50), ident)
    side = 0
    if p:
        side = m.s(p, 4)
        if side >= 5:
            side = 0
        if side & 0xFF > 4:
            return
        side &= 0xFF
    row = m.u64(m.u64(o + 0x10) + 0x250) + side * 0x60
    for k in range(1, 7):
        if m.u32(row + 0x10 * k) == ident:
            m.put(row + 0x10 * k + 6, 2, v)
            return


@lifted(0x2844800)
def not_flagged_and_not_308(m, o, ident, *_):
    """1 unless 0x28422f0 holds for {0x283d610(o), 1} or battler `ident`'s vf 0x308 (0x2842e80) does."""
    with m.frame(0x10) as p:
        m.put(p, 8, m.call(m.main + 0x283D610, o, ident))
        m.put(p + 8, 1, 1)
        if m.call(m.main + 0x28422F0, o, p) & 1:
            return 0
    return (m.call(m.main + 0x2842E80, o, ident & 0xFFFFFFFF) ^ 1) & 1


@lifted(0x1140D40)
def run_11424b8(m, o, e, *_):
    """0x11424b8(0x1140d74([o+0x78]), an out slot, &[e+0x28])."""
    with m.frame(0x10) as p:
        m.put(p + 8, 8, m.u64(e + 0x28))
        return _tail(m, m.main + 0x11424B8, m.call(m.main + 0x1140D74, m.u64(o + 0x78)), p, p + 8)


@lifted(0xE13B9C)
def recompute_stats(m, pp, keep, *_):
    """Keep the record plain (0xd677e8) unless it already is, then store the level for its experience
    and every stat (0xe13cb8(keep & 1) for HP, then Atk, Def, SpA, SpD, Spe) into the party record;
    drop the plain hold again (0xd679f0) when this call took it."""
    for a in (0xD677E8, 0xBF41A8, 0xE14B64, 0xE13DA0, 0xE15150, 0xE13CB8, 0xE1415C, 0xE15484, 0xE142B0,
              0xE157B8, 0xE14560, 0xE15E20, 0xE146B8, 0xE16154, 0xE14408, 0xE15AEC, 0xD679F0):
        _need(m, m.main + a)
    took = m.u8(m.u64(pp + 0x70) + 0x19) == 0
    if took:
        m.call(m.main + 0xD677E8, m.u64(pp + 0x70))
    s = m.call(m.main + 0xBF44F4, m.u64(pp + 0x70)) & 0xFFFFFFFF
    f = m.call(m.main + 0xBF41A8, m.u64(pp + 0x70)) & 0xFFFFFFFF
    e = m.call(m.main + 0xE14B64, m.u64(pp + 0x70)) & 0xFFFFFFFF
    lv = m.call(m.main + 0xE13DA0, s, f, e) & 0xFFFFFFFF
    m.call_void(m.main + 0xE15150, m.u64(pp + 0x70), lv)
    m.call_void(m.main + 0xE13CB8, pp, keep & 1)
    r = None
    for get, put in ((0xE1415C, 0xE15484), (0xE142B0, 0xE157B8), (0xE14560, 0xE15E20), (0xE146B8, 0xE16154),
                     (0xE14408, 0xE15AEC)):
        v = m.call(m.main + get, pp) & 0xFFFFFFFF
        r = _tail(m, m.main + put, m.u64(pp + 0x70), v)
    if took and m.u8(m.u64(pp + 0x70) + 0x19):
        return _tail(m, m.main + 0xD679F0, m.u64(pp + 0x70))
    return r


@lifted(0x28024A0)
def static_46e2578(m, *_):
    """A function-local static (guard and storage through the GOT); read only once built."""
    if m.u8(m.u64(m.main + 0x46E2570)) & 1 == 0:
        raise UnliftedCall("static 0x46e2578 not built")
    return m.u64(m.main + 0x46E2578)


@lifted(0x13606C4)
def note_and_queue_5f(m, o, ident, *_):
    """0x13606f8([o+0x20], ident) (ident passes through in x1), then message 0x5f(ident)."""
    _need(m, m.main + 0x119AFF0)
    m.call_void(m.main + 0x13606F8, m.u64(o + 0x20), ident)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x5F, ident & 0xFFFFFFFF)


@lifted(0x283F0DC)
def apply_side_effects(m, o, out, req, *_):
    """For each target 0x2823478 lists for the u8 req+4: 0x288818c(o, flags, target, req+5) (out set when
    one holds); then for each of the 2 x 19 flags set, 0x288835c([req], side, k); bracketed by
    0x17ce0e4 / 0x17ce27c when req+9 and 0x2888224(flags) hold."""
    for a in (0x1482534, 0x13813EC, 0x2823478, 0x288818C, 0x2888224, 0x1143584, 0x288835C):
        _need(m, m.main + a)
    if m.u8(req + 9):
        _need(m, m.main + 0x17CE0E4); _need(m, m.main + 0x17CE27C)
    m.put(out, 1, 0)
    with m.frame(0x30) as sp:
        flags = sp + 8
        m.write(sp, bytes(0x30))
        t = m.call(m.main + 0x13813EC, m.call(m.main + 0x1482534, o))
        m.call_void(m.main + 0x2823478, t, sp + 4, sp, m.u8(req + 4))
        i = 0
        while i < m.u8(sp):
            if m.call(m.main + 0x288818C, o, flags, m.u8(sp + 4 + i), req + 5) & 1:
                m.put(out, 1, 1)
            i += 1
        if m.u8(req + 9) and m.call(m.main + 0x2888224, flags) & 1:
            m.call_void(m.main + 0x17CE0E4, m.call(m.main + 0x1143584, o), m.u32(req))
        for side in range(2):
            for k in range(0x13):
                if m.u8(flags + side * 0x13 + k):
                    m.call_void(m.main + 0x288835C, m.call(m.main + 0x1143584, o), m.u32(req), side, k)
        if m.u8(req + 9) and m.call(m.main + 0x2888224, flags) & 1:
            m.call_void(m.main + 0x17CE27C, m.call(m.main + 0x1143584, o), m.u32(req))
