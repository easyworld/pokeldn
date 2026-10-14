"""Lifted battle server functions, batch 0 (moved to their topic module once reviewed)."""

from pokeldn.sv.battle.machine import Pair, lifted


@lifted(0x114B1E4)
def bits_0_7(m, o, *_): return m.u16(o + 2) & 0x7F


@lifted(0x114B1F0)
def bits_7_14(m, o, *_): return m.u16(o + 2) >> 7 & 0x7F


@lifted(0x114B1FC)
def bit_30(m, o, *_): return m.u8(o + 3) >> 6 & 1


@lifted(0x114AB84)
def bit_31(m, o, *_): return int(m.s(o + 2, 2) < 0)


@lifted(0x2D171C0)
def kind_2(m, out, *_):
    m.put(out, 4, 2)
    return m.main + 0x44F9F20


@lifted(0x174AE90)
def unpack_three(m, o, a, b, c, *_):
    m.put(a, 4, m.u32(o + 0xC)); m.put(b, 4, m.u64(o + 8)); m.put(c, 4, m.u32(o))


@lifted(0x1380C48)
def nop(m, *_): return


@lifted(0x2843244)
def set_head(m, o, low, value, *_):
    """Store a u16 at +0 and the low 7 bits of the u16 at +2 (bits 14 and 15 kept, the count cleared)."""
    m.put(o, 2, value)
    m.put(o + 2, 2, m.u16(o + 2) & 0xC000 | low & 0x7F)


@lifted(0x284325C)
def push_u32(m, o, value, *_):
    """Append a u32 at +4 to a list of at most 8 whose count is bits 7..13 of the u16 at +2."""
    h = m.u16(o + 2)
    n = h >> 7 & 0x7F
    if n < 8:
        m.put(o + 2, 2, (h + 0x80) & 0x3F80 | h & 0xC07F)
        m.put(o + 4 + 4 * n, 4, value)


@lifted(0x1820F40)
def copy_0x24(m, dst, src, *_):
    m.write(dst, m.read(src, 0x24))
    return dst


@lifted(0x1151988)
def slot_free(m, o, i, *_):
    i &= 0xFFFFFFFF
    if i >= 0x80000000:
        i -= 1 << 32
    return int(i < 6 and m.u8(o + i + 0x86) == 0)


@lifted(0x114E4C0)
def member(m, lst, i, *_):
    i &= 0xFF
    return m.u64(lst + 8 * i) if i < m.u8(lst + 0x30) else 0


@lifted(0x16962F0)
def entry_b8_c(m, o, *_):
    e = m.u64(m.u64(m.u64(o + 0x38) + 0x78) + 0xB8)
    return m.u32(e + 0xC) if e else 0


@lifted(0x114DC38)
def zero_0x70(m, o, *_): return int(m.u32(o + 0x70) == 0)


@lifted(0x288D980)
def below_2(m, v, *_): return int(v & 0xFF < 2)


@lifted(0x1143354)
def plus_8(m, o, *_): return (o + 8) & 0xFFFFFFFFFFFFFFFF


@lifted(0x113E080)
def with_one(m, v, *_): return Pair(v & 0xFFFFFFFF, 1)


@lifted(0x288DA88)
def count_0x1c(m, o, *_):
    m.put(o + 0x1C, 4, m.u32(o + 0x1C) + 1)


@lifted(0x2899E30)
def field_3f4(m, o, k, *_):
    """Tail call of 0x177a19c on o+0x3f4: field k (0 the u16, 1..5 the bytes at +2..+6), 10 past them."""
    k &= 0xFF
    p = o + 0x3F4
    if k == 0:
        return m.u16(p)
    return m.u8(p + 1 + k) if k <= 5 else 10


@lifted(0x2D3BAB4)
def value_402_406(m, o, *_):
    p = m.u64(o + 0x700)
    return m.u16(o + 0x406) if p and m.u32(p + 0xB8) else m.u16(o + 0x402)


def _is_prime(n):
    if n < 2:
        return False
    i = 2
    while i * i <= n:
        if n % i == 0:
            return False
        i += 1
    return True


@lifted(0x343D400)
def next_prime(m, n, *_):
    """libc++ std::__next_prime: the smallest prime >= n (0 stays 0, its small_primes table starts at 0)."""
    if n == 0:
        return 0
    while not _is_prime(n):
        n += 1
    return n


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


@lifted(0x287DA44)
def changed_condition_17(m, o, action, *_):
    """The value of the battler's condition 0x17 when the action (kind 1, flags +0x58 & 0x18 clear, u16
    +0x10 not 0xa5) names another one and vf 0x698 accepts it; else 0."""
    if m.u8(action + 0x58) & 0x18:
        return 0
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), m.u32(action))
    if m.vcall(b, 0x220, 0x17) & 1 == 0 or m.u32(action + 4) != 1:
        return 0
    cur = m.u16(action + 0x10)
    if cur == 0xA5:
        return 0
    with m.frame(16) as pair:
        p = m.vcall(b, 0x240, 0x17)
        m.put(pair, 8, p[0]); m.put(pair + 8, 8, p[1])
        v = m.call(m.main + 0xF7FFE0, pair) & 0xFFFFFFFF
    if cur == v & 0xFFFF:
        return 0
    return v if m.vcall(b, 0x698, v) & 0xFFFF else 0


@lifted(0x173F034)
def client_for_0xae(m, o, ctx, action, b, client, *_):
    """`client`, unless the action is 0xae: then (u8 +0xa: 7) the battler's own client slot, or (0) the
    result of 0x10e21c0 when the slots differ in a way 0x163f398 accepts."""
    client &= 0xFFFFFFFF
    pokecon = m.u64(o + 0x10)
    own = m.call(m.main + 0xFE161C, m.u64(pokecon + 0x290), m.vcall(b, 0x98) & 0xFFFFFFFF) & 0xFFFFFFFF
    if m.u16(action) != 0xAE:
        return client
    kind = m.u8(action + 0xA)
    if kind == 7:
        return own
    if kind != 0:
        return client
    if client & 0xFF != 10 and own & 0xFF != client & 0xFF \
            and m.call(m.main + 0x163F398, m.u64(m.u64(o + 0x10) + 0x290), own, client) & 1 == 0:
        return client
    x = m.call(m.main + 0x11440E8, m.u64(o + 0x10))
    return m.call(m.main + 0x10E21C0, ctx, m.u64(o + 0x10), b, 0xAE, x) & 0xFFFFFFFF


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


@lifted(0x2D3D8D8)
def set_slot_pair(m, b, i, pair, *_):
    """Store a 16-byte pair at +0x80 + 16i and clear byte +0x390 + i; slots below 6 run vf 0x608 first."""
    k = i & 0xFFFF
    if k <= 5:
        m.vcall_void(b, 0x608, i, pair)
    m.write(b + 0x80 + 16 * k, m.read(pair, 16))
    m.put(b + 0x390 + k, 1, 0)


@lifted(0x11484E4)
def battler_508(m, o, ident, arg, *_):
    """Tail call of vf 0x508 on battler `ident` with `arg`."""
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), ident)
    m.vcall_void(b, 0x508, arg & 0xFFFFFFFF)


@lifted(0x1832E44)
def out_or_1f8(m, o, done, args, *_):
    """*done = 1 when the battler (args[0]) is not able (vf 0x208) or vf 0x1f8 holds."""
    m.put(done, 1, 0)
    if m.vcall(m.u64(args), 0x208) & 1 == 0 or m.vcall(m.u64(args), 0x1F8) & 1:
        m.put(done, 1, 1)


@lifted(0x283E210)
def init_283e210(m, p, *_):
    m.put(p, 8, 0); m.put(p + 8, 2, 0)
    m.call_void(m.main + 0x179372C, p + 0x10)
    m.put(p + 0x20, 8, 0x100000000)
    m.call_void(m.main + 0x1146154, p + 0x28)


@lifted(0x1820E80)
def init_action(m, p, *_):
    m.write(p, bytes(0x8C))
    m.put(p + 0x88, 1, 5); m.put(p + 0x84, 4, 0x5400000)


@lifted(0x1143030)
def first_of_pair(m, o, *rest):
    """The first byte 0x113fa64 writes for the object 0x114a964 returns."""
    p = m.call(m.main + 0x114A964, m.u64(o + 0x78), *rest[:7])
    with m.frame(0x10) as f:
        m.call_void(m.main + 0x113FA64, p, f, f + 8)
        return m.u8(f)


@lifted(0x19375B0)
def condition_bits_3_8(m, pair, *_):
    """Bits 3..8 of the entry's second word when its kind (bits 0..2) is 2 or 4; else 0."""
    w = m.u64(pair + 8) & 0xFFFFFFFF
    return w >> 3 & 0x3F if w & 7 in (2, 4) else 0


@lifted(0x114309C)
def tick_timer(m, o, *_):
    """Advance the running timer at [[o+0x10]+0x70] (flag +0x19, count +0x10, limit +8, 0xff never
    ends): the flag byte when it expires (then cleared with +0x14), else 0."""
    t = m.u64(m.u64(o + 0x10) + 0x70)
    flag = m.u8(t + 0x19)
    if flag == 0:
        return 0
    limit = m.u32(t + 8)
    if limit == 0xFF:
        return 0
    n = (m.u32(t + 0x10) + 1) & 0xFFFFFFFF
    m.put(t + 0x10, 4, n)
    if limit > n:
        return 0
    m.put(t + 0x19, 1, 0); m.put(t + 0x14, 4, 0)
    return flag


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


@lifted(0xE7E454)
def able_members(m, lst, *_):
    """How many members of a party list (count at +0x30) are able (vf 0x208)."""
    n = 0
    i = 0
    while i < m.u8(lst + 0x30):
        n = (n + (m.vcall(m.u64(lst + 8 * i), 0x208) & 1)) & 0xFFFFFFFF
        i += 1
    return n


def _entry_c(m, o, slot):
    e = m.u64(o + 0x20)
    return m.u32(e + 0xC) if e else 0


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


@lifted(0x16EEB98)
def unruled_460(m, o, pokecon, b, *_):
    """vf 0x460 of the battler when flag bit 2 of +0x499 is clear, +0x30 is below 2 and the battler's
    rule value (setup map) is absent, 0 or above 4; else 0."""
    s = m.u64(o + 0x38)
    if m.u8(s + 0x499) >> 2 & 1 or m.u32(s + 0x30) > 1:
        return 0
    setup = m.u64(pokecon + 0x290)
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(setup + 8) + 0x50), m.vcall(b, 0x98) & 0xFFFFFFFF)
    if p:
        v = m.s(p, 4)
        if 0 < v <= 4:
            return 0
    return m.vcall(b, 0x460)


@lifted(0x28056F0)
def move_class(m, move, *_):
    move &= 0xFFFF
    return {0xC9: 4, 0xF0: 2, 0xF1: 1, 0x102: 3, 0x371: 3, 0x373: 3}.get(move, 0)


@lifted(0x283D5E0)
def entry_18(m, o, i, *_):
    """Tail call of 0x283c90c on [o+0x38]: the u64 at +0x18 of entry i (below 0x86), or 0."""
    i &= 0xFFFF
    if i < 0x86:
        e = m.u64(m.u64(m.u64(o + 0x38) + 0x78) + 8 + 8 * i)
        if e:
            return m.u64(e + 0x18)
    return 0


@lifted(0x2D3C0CC)
def condition_2_or_d5(m, b, kind, *_):
    """1 for kind 1 when vf 0xf8 is 0xd5; else vf 0x220 with 2."""
    if kind & 0xFFFFFFFF == 1 and m.vcall(b, 0xF8) & 0xFFFF == 0xD5:
        return 1
    return m.vcall(b, 0x220, 2)


@lifted(0x157B588)
def walk_targets_48(m, o, b, arg, lst, *_):
    """Walk a member list (cursor +0xa8): each member 0x157b674 accepts gets command 0x48 queued
    (0x157eba0) and is handed to 0x157bf08."""
    m.put(lst + 0xA8, 1, 0)
    if m.u8(lst + 0xA6) == 0:
        return
    t = m.u64(lst)
    m.put(lst + 0xA8, 1, 1)
    while t:
        if m.call(m.main + 0x157B674, o, b, t, arg) & 1:
            q = m.call(m.main + 0x1143584, o)
            a = m.vcall(b, 0x98) & 0xFFFFFFFF
            c = m.vcall(t, 0x98) & 0xFFFFFFFF
            m.call_void(m.main + 0x157EBA0, q, a, 0x48, c)
            m.call_void(m.main + 0x157BF08, lst, t)
        i = m.u8(lst + 0xA8)
        if i >= m.u8(lst + 0xA6):
            return
        m.put(lst + 0xA8, 1, i + 1)
        t = m.u64(lst + 8 * i)


@lifted(0x113E9B0)
def run_113f4f8(m, o, *rest):
    p = m.call(m.main + 0x113E9DC, m.u64(o + 0x78), *rest[:7])
    with m.frame(0x10) as f:
        m.call_void(m.main + 0x113F4F8, p, f, f + 8)


@lifted(0x1360524)
def battler_618(m, o, ident, arg, *_):
    """Tail call of vf 0x618 on battler `ident` with `arg`."""
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), ident)
    m.vcall_void(b, 0x618, arg & 0xFFFFFFFF)


@lifted(0x288426C)
def queue_10(m, o, arg, *_):
    r = m.call(m.main + 0x288CE48, m.u64(o + 0x20), arg)
    m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0x10, arg & 0xFFFFFFFF)
    return r & 1


@lifted(0x1832E08)
def run_1832e44(m, o, b, *_):
    with m.frame(0x10) as f:
        m.put(f + 8, 8, b)
        x = m.call(m.main + 0x1361214, o, b)
        x = m.call(m.main + 0x1832E3C, x, b)
        m.call_void(m.main + 0x1832E44, x, f, f + 8)
        return m.u8(f)


@lifted(0x1143060)
def tick_timer_queue_50(m, o, *_):
    r = m.call(m.main + 0x114309C, m.u64(o + 0x20)) & 0xFFFFFFFF
    m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0x50, 0)
    return r


@lifted(0x1361AD8)
def queue_34(m, o, arg, *_):
    r = m.call(m.main + 0x288C730, m.u64(o + 0x20), arg)
    m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0x34, arg & 0xFF)
    return r & 1


@lifted(0x288D8C0)
def queue_32(m, q, arg, src, *_):
    """Queue command 0x32 with the three words 0x174ae90 unpacks from `src`."""
    m.call_void(m.main + 0x119AFF0, q, 0x32, arg & 0xFF, m.u32(src + 0xC), m.u32(src + 8), m.u32(src))


# Rows of (unused, value when the flag is not 1, value when it is 1) for kinds 1..4 (0x3c6a4c8).
_HEAD_VALUES = ((1, 704, 981), (2, 706, 982), (3, 708, 983), (4, 828, 984))


@lifted(0x2880738)
def init_head(m, o, kind, flag, *_):
    """Reset with 0x2880944, then for kinds 1..4 set the head value from 0x3c6a4c8 with low bits 1."""
    m.call_void(m.main + 0x2880944, o, kind, flag)
    k = (kind - 1) & 0xFF
    if k > 3:
        return
    v = _HEAD_VALUES[k][2 if flag & 0xFF == 1 else 1]
    m.call_void(m.main + 0x2843244, o, 1, v)


@lifted(0x2D21A74)
def clear_counters(m, o, *_):
    """Clear 30 (u32, flag byte) pairs from +0x98, 8 bytes apart."""
    for i in range(30):
        m.put(o + 0x98 + 8 * i, 4, 0); m.put(o + 0x9C + 8 * i, 1, 0)


@lifted(0x171CAC8)
def set_field_3f4(m, p, k, v, *_):
    """Field k of the 0x177a19c record: 0 the u16 at +0, 1..5 the bytes at +2..+6."""
    k &= 0xFF
    if k == 0:
        m.put(p, 2, v)
    elif k <= 5:
        m.put(p + 1 + k, 1, v)


@lifted(0xBF5FE0)
def boosted_field_7(m, ident, level, *_):
    """Field 7 (u8) of record `ident` raised by 20% per level, levels above 2 counting as 3."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    rec = m.call(m.main + 0xBF60CC, table, ident & 0xFFFFFFFF)
    v = fb.u8(m, rec, 7)
    level &= 0xFFFFFFFF
    if level & 0xFF >= 3:
        level = 3
    f = (level * 5 & 0x3F) << 2
    return (v + ((v * f) & 0xFFFFFFFF) // 100) & 0xFFFFFFFF


@lifted(0x283C488)
def release_finished(m, o, *_):
    """Walk the active list of the pool at [[o+8]+0xd0]: an element in state 7 (+0x28) with +0x44 set is
    released (0x13608e0), or handed to 0x1360cdc when +0x3f is set."""
    from pokeldn.sv.battle.engine.containers import find
    pool = m.u64(m.u64(o + 8) + 0xD0)
    key = m.u16(pool + 0x70)
    if key == 0xEE:
        return
    node = find(m, pool + 8, key, 2)
    if not node:
        return
    e = node + 0x18
    while True:
        nxt = m.call(m.main + 0xF7BA54, m.u64(e + 8), m.u16(e + 0x14))
        if m.u8(e + 0x28) == 7 and m.u8(e + 0x44):
            if m.u8(e + 0x3F) == 0:
                m.call_void(m.main + 0x13608E0, m.u64(m.u64(o + 8) + 0xD0), e)
            else:
                m.call_void(m.main + 0x1360CDC, e, 1)
        if nxt == 0:
            return
        e = nxt


def _record_field11(at, size):
    """Bytes at `at` of the inline struct in field 11 of the data record for the u16 id at o+8."""
    def fn(m, o, *_):
        from pokeldn.sv.battle.engine.containers import data_record
        from pokeldn.sv.battle.engine.data import static_table
        table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
        rec = data_record(m, table, m.u16(o + 8))
        off = m.u16(rec - m.s(rec, 4) + 0x1A)   # read without the vtable size check, as the game does
        return m.u(rec + off + at, size)
    return fn


for _addr, _at, _size in ((0x179412C, 0, 2), (0x17942D0, 2, 1), (0x17947C8, 5, 1)):
    lifted(_addr)(_record_field11(_at, _size))


@lifted(0x10D3F10)
def first_not_78(m, o, *_):
    """When flag bit 3 of [[o+0x10]+0x38]+0x499 is set: the first party member, client by client, for which
    vf 0x78 is false, skipping clients on the side of client byte [o+0x10]+0x95; else 0."""
    if m.u8(m.u64(m.u64(o + 0x10) + 0x38) + 0x499) >> 3 & 1 == 0:
        return 0
    for c in range(5):
        setup = m.u64(m.u64(m.u64(o + 8) + 0x290) + 8)
        if m.call(m.main + 0xE7E2A0, m.u32(setup + 0x36C), m.u8(setup + 0x370), c) & 1 == 0:
            continue
        s = m.u64(o + 8)
        sides = SIDE.get(m.u32(s + 0x36C))
        v = m.u8(m.u64(o + 0x10) + 0x95)
        if sides is not None and v <= 4 and sides[v] <= 1:
            a, t = sides[v], sides[c]
            if a == t or t == 3 or (t == 4 and a != 0) or (t == 5 and a != 1):
                continue
        parties = m.u64(s + 0x30) + 0x38 * c
        i = 0
        while i < m.u8(parties + 0x58):
            b = m.u64(parties + 0x28 + 8 * i)
            if m.vcall(b, 0x78) & 1 == 0:
                return b
            i += 1
    return 0


def _entry_id(m, t, off):
    e = m.u64(t + off)
    return m.u32(e + 0xC) if e else 0


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


# Position -> client slot rows read by 0xc9c750: mode 0 (0x3c6a348), mode 1 by rule 1..5 (0x44fccb8 ->
# 0x3c6a3a0 x3, 0x3c6a3cc, 0x3c6a3f8) or any other rule (0x3c6a374), mode 2 (0x3c6a424).
_C9_MODE0 = (0, 1)
_C9_MODE1 = {1: (0, 1, 2, 3), 2: (0, 1, 2, 3), 3: (0, 1, 2, 3), 4: (0, 1, 0, 3), 5: (0, 1, 2)}
_C9_MODE1_OTHER = (0, 1, 0, 1)
_C9_MODE2 = (0, 2, 3, 4, 1, 1, 1, 1, 1, 1, 5)
_C9_MODE2_EMPTY = {0: 0x40E, 1: 0x40C}


@lifted(0xC9C750)
def side_of_position(m, mode, rule, pos, *_):
    """The side class (0x3c6a450 tables) of the client at battle position `pos`; 2 when none."""
    mode &= 0xFFFFFFFF; rule &= 0xFF; pos &= 0xFF
    if mode == 0:
        return SIDE[0][_C9_MODE0[pos]] if pos < 2 else 2
    if mode == 1:
        if pos > 10:
            return 2
        row = _C9_MODE1.get(rule, _C9_MODE1_OTHER)
        slot = row[pos] if pos < len(row) else 5
        return SIDE[1][slot] if slot <= 4 else 2
    if mode != 2 or pos > 10:
        return 2
    if rule in _C9_MODE2_EMPTY:
        if _C9_MODE2_EMPTY[rule] >> pos & 1:
            return 2
    elif pos == 10 or (rule == 2 and pos == 3):
        return 2
    return SIDE[2][_C9_MODE2[pos]]


SIDE = {0: (0, 1, 2, 2, 2), 1: (0, 1, 0, 1, 2), 2: (0, 1, 0, 0, 0)}   # 0x3c6a450, 0x3c6a455, 0x3c6a45a


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


@lifted(0x1380E28)
def field18_count(m, ident, *_):
    """How many of the three bytes in field 18 of the data record for `ident` are set (0x1380ea4)."""
    with m.frame(0x10) as key:
        m.put(key, 8, m.u64(m.main + 0x46DDAD8) + 0x10); m.put(key + 8, 2, ident)
        return sum(int(m.call(m.main + 0x1380EA4, key, i) & 0xFF != 0) for i in range(3))


@lifted(0x15662A0)
def start_record(m, rec, value, *_):
    """State 0 -> 1: keep `value` (u32) at +0x68 and vf 0x108 of 0xf6fc68's object (u16) at +0x90."""
    if m.u32(rec + 0x70):
        return
    m.put(rec + 0x70, 4, 1)
    m.put(rec + 0x68, 8, value & 0xFFFFFFFF)
    p = m.call(m.main + 0xF6FC68, rec, value)
    m.put(rec + 0x90, 4, m.vcall(p, 0x108) & 0xFFFF)


@lifted(0x15661E0)
def record_event(m, rec, kind, v, *_):
    """Apply event `kind` (1..7) with argument `v` to the record at [server]+0x310."""
    kind = (kind & 0xFF) - 1
    if kind == 0:
        start_record(m, rec, v & 0xFFFFFFFF)
    elif kind == 1:
        if m.u32(rec + 0x70) == 1:
            m.put(rec + 0x70, 4, 2)
            if v & 0xFFFFFFFF == 1:
                m.put(rec + 0x7C, 8, 0xFFFFFFFFFFFFFFFF); m.put(rec + 0x84, 2, 0xFFFF)
    elif kind == 2:
        m.put(rec + 0x8D, 1, 1)
    elif kind == 3:
        i = v & 0xFFFFFFFF
        i = i - (1 << 32) if i & 0x80000000 else i
        if i <= 5:
            m.put(rec + 0x86 + i, 1, 1)
    elif kind == 4:
        m.put(rec + 0x8C, 1, 1)
    elif kind == 5:
        if v & 0xFF <= 4:
            m.put(rec + 0x7C + 2 * (v & 0xFF), 2, 0)
    elif kind == 6:
        if m.u32(rec + 0x70) == 1:
            m.put(rec + 0x78, 4, m.u32(rec + 0x78) + v)


@lifted(0x15661B0)
def server_record_event(m, o, kind, v, *_):
    return record_event(m, m.call(m.main + 0x11409B4, m.u64(o + 0x10)), kind, v)


@lifted(0x2D1F884)
def has_type_715(m, b, *_):
    """Whether the type byte at +0x715 (when +0x714 is set) is one of the battler's two types (+0x40a,
    +0x40b), after vf 0x220 (0x19) and vf 0x4d0 (0x17) mask them; 0x12 is no type (0x3c630a0 maps 0..0x12
    to itself)."""
    if m.u8(b + 0x714) == 0:
        return 0
    c = m.vcall(b, 0x220, 0x19) & 1
    t1, t2 = m.u8(b + 0x40A), m.u8(b + 0x40B)
    r = m.vcall(b, 0x4D0, 0x17) & 1
    a = t1 == 0x12 or (c and t1 == 2)
    z = t2 == 0x12 or (c and t2 == 2)
    if r:
        if a and z:
            t1 = t2 = 0x12
        elif a:
            t1 = t2
        elif z:
            t2 = t1
    elif a:
        t2 = 0 if z else t2
        t1 = t2
    elif z:
        t2 = t1
    k = m.u8(b + 0x715)
    t = k if k <= 0x12 else 0x12
    return int(t == t1 or t == t2)


@lifted(0x1142508)
def record_object(m, o, *rest):
    """Tail call of 0xf6fc68 on the record at [[o+0x10]+0x310]."""
    rec = m.call(m.main + 0x11409B4, m.call(m.main + 0x1482534, o))
    return m.call(m.main + 0xF6FC68, rec, *rest[:7])


@lifted(0x1149414)
def set_550_queue_37(m, o, ident, v, *_):
    """vf 0x550 (v, 1) on battler `ident`, then queue command 0x37 (ident, v, 1)."""
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(m.u64(o + 0x20) + 0x10) + 0x30), ident)
    m.vcall_void(b, 0x550, v & 0xFFFFFFFF, 1)
    m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0x37, ident & 0xFFFFFFFF, v & 0xFF, 1)


def _udiv32(a, b):
    """AArch64 udiv: division by zero gives 0."""
    return (a & 0xFFFFFFFF) // (b & 0xFFFFFFFF) if b & 0xFFFFFFFF else 0


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


def _tail(m, address, *args):
    """A tail call whose result passes through unchanged (None when the callee is void)."""
    from pokeldn.sv.battle.machine import FUNCTIONS, UnliftedCall
    fn = FUNCTIONS.get(address - m.main)
    if fn is None:
        raise UnliftedCall(f"main+0x{address - m.main:x}")
    return fn(m, *args)


@lifted(0x28422F0)
def run_15fa034(m, o, arg, *_):
    """The byte 0x15fa034 writes for the object 0x15fa02c returns from [o+0x28]."""
    p = m.call(m.main + 0x15FA02C, m.u64(o + 0x28), arg)
    with m.frame(0x10) as f:
        m.call_void(m.main + 0x15FA034, p, f, arg)
        return m.u8(f)


@lifted(0x1793E2C)
def record_field11_u16(m, ident, *_):
    """0x179412c on a stack key (vtable [0x46ddad8] + 0x10, u16 id at +8); the game returns its w0."""
    with m.frame(0x10) as key:
        m.put(key, 8, m.u64(m.main + 0x46DDAD8) + 0x10); m.put(key + 8, 2, ident)
        return m.call(m.main + 0x179412C, key)


@lifted(0x288D134)
def battler_1c8(m, o, ident, a, b, *_):
    """Tail call of vf 0x1c8 (a, b) on battler `ident`, nothing when there is none."""
    t = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), ident)
    if t == 0:
        return 0
    return _tail(m, m.u64(m.u64(t) + 0x1C8), t, a & 0xFFFFFFFF, b & 0xFFFFFFFF)


# @lifted(0x283E66C)  waits for a callee lifted elsewhere
def handler_283e66c(m, o, done, args, *_):
    """*done = 0x288426c's bit for the battler args[0] (u32 id) unless it is out (vf 0x200)."""
    m.put(done, 1, 0)
    b = m.call(m.main + 0x13813F4, o, m.u32(args))
    if m.vcall(b, 0x200) & 1:
        return
    q = m.call(m.main + 0x1143584, o)
    m.put(done, 1, m.call(m.main + 0x288426C, q, m.u32(args)) & 1)


@lifted(0x13602D8)
def run_1360318(m, o, arg, *_):
    """0x1360318 on 0x1360310's object with a stack record (arg at +8, u16 0x101 at +0x10)."""
    with m.frame(0x18) as f:
        m.put(f + 8, 8, arg); m.put(f + 0x10, 2, 0x101)
        x = m.call(m.main + 0x1361214, o, arg)
        x = m.call(m.main + 0x1360310, x, arg)
        return _tail(m, m.main + 0x1360318, x, f, f + 8)


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


@lifted(0x157B7A4)
def walk_targets_157e064(m, o, _unused, args, *_):
    """For each member of the list args[2] (cursor +0xa8) that 0x157c614 rejects and 0x157e064 accepts
    (move u16 *args[0]): hand it to 0x157bf08, and queue 0x157ef30 unless 0x157ea90 > 1 with byte +0x13
    of args[0] set, or 0x157e064 cleared its flag."""
    lst = m.u64(args + 0x10)
    m.put(lst + 0xA8, 1, 0)
    while True:
        lst = m.u64(args + 0x10)
        i = m.u8(lst + 0xA8)
        if i >= m.u8(lst + 0xA6):
            return
        m.put(lst + 0xA8, 1, i + 1)
        t = m.u64(lst + 8 * i)
        if t == 0:
            return
        if m.call(m.main + 0x157C614, m.u64(o + 0x10), m.u64(args + 8), t) & 1:
            continue
        with m.frame(0x10) as flag:
            m.put(flag, 1, 1)
            ok = m.call(m.main + 0x157E064, m.u64(o + 0x38), m.u64(args + 8), t, m.u16(m.u64(args)), flag) & 1
            if not ok:
                continue
            mv = m.u64(args)
            many = (m.call(m.main + 0x157EA90, m.u64(args + 0x10)) & 0xFFFFFFFF) > 1
            strict = m.u8(mv + 0x13) != 0
            m.call_void(m.main + 0x157BF08, m.u64(args + 0x10), t)
            if (many and strict) or m.u8(flag) == 0:
                continue
        q = m.call(m.main + 0x1143584, o)
        ident = m.vcall(m.u64(args + 8), 0x98) & 0xFFFFFFFF
        m.call_void(m.main + 0x157EF30, q, ident, t, m.u16(m.u64(args)))


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


def _rule_s32(m, pokecon, ident):
    """The setup map's value for `ident` as the game clamps it: below 5 kept (signed), else 0; absent 0."""
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(pokecon + 0x290) + 8) + 0x50), ident)
    if p == 0:
        return None
    v = m.s(p, 4)
    return (v if v < 5 else 0) & 0xFFFFFFFF


@lifted(0x162B7F0)
def note_raid_side(m, o, p, ident, *_):
    """For a nonzero id that 0x162b830 accepts, the tail call of 0x162b8a0: when [o+8]'s +0x30 count is
    below 2, keep the id's rule value at [[o+8]+0x40]+0x278 and its byte +4 (6 when absent) at +0x27c."""
    ident &= 0xFFFFFFFF
    if ident == 0 or m.call(m.main + 0x162B830, o, p, ident) & 1 == 0:
        return
    s, pokecon = m.u64(o + 8), m.u64(o + 0x10)
    if m.u32(m.u64(s + 0x38) + 0x30) > 1:
        return
    v = _rule_s32(m, pokecon, ident)
    m.put(m.u64(s + 0x40) + 0x278, 4, v or 0)
    q = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(pokecon + 0x290) + 8) + 0x50), ident)
    m.put(m.u64(s + 0x40) + 0x27C, 4, m.u8(q + 4) if q else 6)


@lifted(0x14807D0)
def reset_32_flags(m, b, *_):
    """Clear the u32 at +0x49a and run vf 0x500 for 0..31."""
    m.put(b + 0x49A, 4, 0)
    for i in range(32):
        m.vcall_void(b, 0x500, i)


@lifted(0x283D6A0)
def entry_mode_class(m, o, i, *_):
    """Tail call of 0x144e790 with the id of entry i (below 0x86) of [[o+0x38]+0x78], 0 when none."""
    i &= 0xFFFF
    ident = 0
    if i <= 0x85:
        e = m.u64(m.u64(m.u64(o + 0x38) + 0x78) + 8 + 8 * i)
        if e:
            ident = m.u32(e + 0xC)
    return m.call(m.main + 0x144E790, m.u64(m.u64(o + 8) + 0x290), ident)


@lifted(0x17D31E0)
def slot_in_f0(m, o, ident, *_):
    """Tail call of 0x1381420 on [[o+0x10]+0xf0]."""
    return m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), ident)


@lifted(0x157EA98)
def find_u32(m, table, key_ptr, *_):
    """The node of the u32-keyed map holding the key at key_ptr, or 0."""
    from pokeldn.sv.battle.engine.containers import find
    return find(m, table, m.u32(key_ptr), 4)


@lifted(0x287DB40)
def build_condition(m, o, packed, b, out, *_):
    """Tail call of 0x1793efc with the server's 0x14d96d8 object, the u16 packed value and 0x11440e8's."""
    x = m.call(m.main + 0x11440E8, m.u64(o + 0x10))
    y = m.call(m.main + 0x14D96D8, m.u64(o + 0x10))
    return _tail(m, m.main + 0x1793EFC, y, packed & 0xFFFF, b, out, x)


@lifted(0xE7E28C)
def client_in_battle(m, o, slot, *_):
    """Tail call of 0xe7e2a0 with the setup's mode and rule."""
    s = m.u64(o + 8)
    return m.call(m.main + 0xE7E2A0, m.u32(s + 0x36C), m.u8(s + 0x370), slot & 0xFF)


@lifted(0x173C268)
def redirect_target(m, o, ctx, b, arg, _p5, lst, *_):
    """When the attacker's side holds more than one position and the list holds one target that is
    out of the battle (vf 0x200) and not kept by 0x17d5d98 (nor the raid battler in a raid): drop it
    (0x157bf08) and add the target 0x1138ae0 picks (kind 6) instead. 0 when no target replaces it."""
    pokecon = m.u64(o + 0x10)
    owner = m.u64(pokecon + 0x290)
    p = m.call(m.main + 0x10E2DD4, m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50),
               m.vcall(b, 0x98) & 0xFFFFFFFF)
    v = 0
    if p:
        w = m.s(p, 4)
        v = w & 0xFF if w < 5 else 0
    s = m.u64(owner + 8)
    pos = m.call(m.main + 0x1365B00, m.u32(s + 0x36C), m.u8(s + 0x370), v, 0) & 0xFF
    s = m.u64(owner + 8)
    mode = m.u32(s + 0x36C)
    side = SIDE[mode][pos] if mode in SIDE and pos <= 4 else 2
    n = m.call(m.main + 0x113AA70, mode, m.u8(s + 0x370), side)
    if n & 0xFE == 0 or m.u8(lst + 0xA6) != 1:
        return 1
    t = m.u64(lst)
    if m.vcall(t, 0x200) & 1 == 0:
        return 1
    if m.call(m.main + 0x17D5D98, o, b, t) & 1:
        return 1
    if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x499) >> 2 & 1:
        rec = m.u64(m.u64(o + 0x10) + 0x310)
        mine = m.vcall(b, 0x98) & 0xFFFFFFFF
        raid = m.u32(rec + 0x18)
        if m.u8(m.u64(m.u64(rec + 8) + 0x38) + 0x499) >> 2 & 1 and raid == 0:
            parties = m.u64(m.u64(rec + 0x10) + 0x30)
            if m.u8(parties + 0x90) == 0:
                raid = 0
            elif m.u64(parties + 0x60):
                raid = m.vcall(m.u64(parties + 0x60), 0x98) & 0xFFFFFFFF
                m.put(rec + 0x18, 4, raid)
        if raid == mine:
            return 0
    m.call_void(m.main + 0x157BF08, lst, t)
    with m.frame(0x30) as f:
        r = m.call(m.main + 0x1138AE0, o, f, 6, b, arg) & 0xFFFFFFFF
        if r & 0xFF == 0:
            return 0
        new = m.u64(f) if r & 0xFF == 1 else m.call(m.main + 0x2886E3C, o, f, r)
    if new == 0:
        return 0
    n = m.u8(lst + 0xA6)
    if n > 10 or any(m.u64(lst + 8 * i) == new for i in range(n)):
        return 1
    m.put(lst + 8 * n, 8, new)
    m.put(lst + 0x84 + m.u8(lst + 0xA6), 1, 0)
    m.put(lst + 0x58 + 2 * m.u8(lst + 0xA6), 2, 0)
    m.put(lst + 0x6E + 2 * m.u8(lst + 0xA6), 2, 0)
    n = (m.u8(lst + 0xA6) + 1) & 0xFF
    m.put(lst + 0xA6, 1, n)
    if m.u8(lst + 0xA7) < n:
        m.put(lst + 0xA7, 1, n)
    return 1


@lifted(0x153354C)
def apply_hits(m, o, _unused, args, *_):
    """For each entry of the hit record *args (12-byte entries from +4, count bytes +0 and +1) marked
    active (bit 3 of +0xa): run 0x28810e4 for its battler (u32 +4) when vf 0x588 holds, and hand the
    result to 0x2881128 with args[4]."""
    rec = m.u64(args)
    if (m.u8(rec) + m.u8(rec + 1)) & 0xFFFFFFFF == 0:
        return
    hits = []
    k = 0
    while k < m.u8(rec) + m.u8(rec + 1):
        e = rec + 4 + 12 * k
        if m.u8(e + 0xA) >> 3 & 1:
            b = m.call(m.main + 0x13813F4, o, m.u32(e + 4))
            hits.append((b, m.u16(e), m.u8(e + 8), m.u8(e + 0xA) & 1))
        k += 1
    for b, move, slot, flag in hits:
        if m.vcall(b, 0x588) & 1:
            v = m.call(m.main + 0x28810E4, o, m.u64(args + 8), m.u64(args + 0x10), m.u64(args + 0x18), b,
                       move, slot, flag)
            m.call_void(m.main + 0x2881128, m.u64(args + 0x20), b, v & 0xFFFFFFFF, 1)


def _scale_entry(m, e, factor):
    """0x1353760: an entry in state 3 (+0xa) scales its s32 +0xc by factor/4096 (rounded), kept within
    [+0x10, +0x14] unless both bounds are 0."""
    if m.u8(e + 0xA) != 3:
        return
    v = ((m.s(e + 0xC, 4) * _s32(factor) + 0x800) & 0xFFFFFFFFFFFFFFFF) >> 12
    v = _s32(v)
    lo, hi = m.s(e + 0x10, 4), m.s(e + 0x14, 4)
    if hi | lo:
        v = min(hi, max(lo, v))
    m.put(e + 0xC, 4, v)


def _s32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v & 0x80000000 else v


@lifted(0x1353738)
def scale_entry(m, t, i, factor, *_):
    """Entry i (below 0x86) of the table at t+0x78 through 0x1353760."""
    i &= 0xFFFF
    if i > 0x85:
        return
    e = m.u64(m.u64(t + 0x78) + 8 + 8 * i)
    if e:
        _scale_entry(m, e, factor)


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
    scale_entry(m, m.u64(o + 0x38), 0x38, 0x1800)


# Rodata keys the hit-count lookups pass to vf 0x68 of their table (0x3c6b528..0x3c6b550).
_HIT_KEY = {4: 0x3C6B530, 5: 0x3C6B528, 9: 0x3C6B538, 10: 0x3C6B540}


@lifted(0x2D3C2E8)
def hits_to_faint(m, b, kind, table, *_):
    """How many hits of fixed damage kind `kind` the battler takes before fainting: its HP (vf 0x140)
    divided by vf 0x68 of `table` for the kind's key, at least 1; 0 when vf 0x220 rejects the kind."""
    if m.vcall(b, 0x220, kind, table) & 1 == 0:   # x1, x2 pass through to the virtual call
        return 0
    kind &= 0xFFFF
    if kind in (6, 7, 8):
        return 0
    if kind == 5:
        n = m.vcall(table, 0x68, m.u64(m.main + 0x46E2700)) & 0xFFFFFFFF
        w = m.u64(b + 0xD8)
        if w & 7 == 1 and (w >> 3 & 0x3F) == (n - 1) & 0xFFFFFFFF:
            d = m.vcall(table, 0x68, m.u64(m.main + 0x46E2700)) & 0xFFFFFFFF
            return (_per_hit(m, b, d) * m.u8(b + 0x395)) & 0xFFFFFFFF
        key = _HIT_KEY[5]
    elif kind == 9:
        if m.vcall(b, 0x228, 1) & 1 == 0:
            return 0
        key = _HIT_KEY[9]
    elif kind in _HIT_KEY:
        key = _HIT_KEY[kind]
    elif kind == 0x2E:
        if m.vcall(b, 0x300, 10) & 1 or m.vcall(b, 0x300, 8) & 1:
            key = 0x3C6B548
        else:
            key = 0x3C6B550
    else:
        return 0
    d = m.vcall(table, 0x68, m.main + key) & 0xFFFFFFFF
    return _per_hit(m, b, d)


def _per_hit(m, b, d):
    hp = m.vcall(b, 0x140) & 0xFFFF
    d = d or 1
    return hp // d if d <= hp else 1


@lifted(0x20FEAE8)
def record_flag_56(m, o, *_):
    """Field 56 of the data record for the u16 id at o+8, as a bool."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.containers import data_record
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    return int(fb.u8(m, data_record(m, table, m.u16(o + 8)), 56) != 0)


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


@lifted(0x2886D20)
def queue_a7(m, o, pos, v, *_):
    """Queue command 0xa7 (pos, v u16) unless pos is 10 (none)."""
    if pos & 0xFF == 10:
        return
    m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0xA7, pos & 0xFFFFFFFF, v & 0xFFFF)


@lifted(0x13DBFD4)
def apply_and_queue_5b(m, o, ident, v, *_):
    """0x13dc030 on battler `ident` with v, then queue command 0x5b (ident, v)."""
    q = m.u64(o + 0x20)
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(q + 0x10) + 0x30), ident)
    m.call_void(m.main + 0x13DC030, m.u64(q + 0x18), b, v & 0xFFFFFFFF)
    m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0x5B, ident & 0xFFFFFFFF, v & 0xFFFFFFFF)


@lifted(0x114ACBC)
def touch_shared(m, o, *_):
    """The object at [0xe7ecd0([o+8])]+0x148 after taking and dropping one reference on its counter
    (+0x30: u16 count +0x1a; the first reference builds +8 from +0x10's vf 0 and sets +0x1c to -2; the
    last clears +0x10 and runs the object's vf 0x50)."""
    from pokeldn.sv.battle.machine import UnliftedCall
    obj = m.u64(m.call(m.main + 0xE7ECD0, m.u64(o + 8)) + 0x148)
    if obj == 0:
        return 0
    ctl = m.u64(obj + 0x30)
    if m.u64(ctl + 0x10) == 0:
        raise UnliftedCall("AddReference abort: m_object is null")
    n = m.u16(ctl + 0x1A)
    m.put(ctl + 0x1A, 2, n + 1)
    if n == 0:
        src = m.u64(ctl + 0x10)
        m.put(ctl + 8, 8, m.call(m.u64(m.u64(src)), src))
        m.put(ctl + 0x1C, 4, 0xFFFFFFFE)
    elif n == 0xFFFF:
        raise UnliftedCall("AddReference abort: counter overflow")
    ctl = m.u64(obj + 0x30)
    n = m.u16(ctl + 0x1A)
    m.put(ctl + 0x1A, 2, n - 1)
    if n == 1:
        m.put(ctl + 0x10, 8, 0)
        m.vcall_void(obj, 0x50)
    elif n == 0:
        raise UnliftedCall("ReleaseReference abort: count is 0")
    return obj


@lifted(0x114ADE8)
def queue_a7_for(m, o, b, v, *_):
    """Queue command 0xa7 (the battler's slot 0x1381420, v u16) unless it has no slot."""
    pos = m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), m.vcall(b, 0x98) & 0xFFFFFFFF)
    if pos & 0xFF == 10:
        return
    m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0xA7, pos & 0xFFFFFFFF, v & 0xFFFF)


@lifted(0x17710A4)
def field18_entry(m, ident, i, out, *_):
    """For i below 3: *out = the s8 0x1771130 gives for byte i of field 18 of record `ident` when that
    byte (0x1380ea4) is set, else 0; returns 0x1380ea4's result (0 for i >= 3)."""
    i &= 0xFFFFFFFF
    if i >= 3:
        m.put(out, 4, 0)
        return 0
    with m.frame(0x10) as key:
        m.put(key, 8, m.u64(m.main + 0x46DDAD8) + 0x10); m.put(key + 8, 2, ident)
        r = m.call(m.main + 0x1380EA4, key, i) & 0xFFFFFFFF
        v = 0
        if r & 0xFF:
            v = m.call(m.main + 0x1771130, key, i) & 0xFF
            v = v - 0x100 if v & 0x80 else v
        m.put(out, 4, v)
        return r


@lifted(0x1360404)
def each_standing_1360480(m, o, arg, *_):
    """0x1360480 (queue object, member, arg) for every party member still in the battle."""
    with m.frame(0x40) as f:
        it, out = f, f + 0x38
        m.put(out, 8, 0)
        a = m.call(m.main + 0x114E480, o, arg)
        b = m.call(m.main + 0x1482534, o)
        m.call_void(m.main + 0x1147754, it, a, b)
        while m.call(m.main + 0x1360DBC, it, out) & 1:
            q = m.call(m.main + 0x1143584, o)
            m.call_void(m.main + 0x1360480, q, m.u64(out), arg)


@lifted(0x11430E4)
def run_11438e4_pair(m, o, b, *_):
    """For a battler still in the battle (vf 0x200 clear): 0x11438e4 with (6, 1, 3, 1), then (7, 2, 4, 2)."""
    if m.vcall(b, 0x200) & 1:
        return
    m.call_void(m.main + 0x11438E4, o, b, 6, 1, 3, 1)
    return _tail(m, m.main + 0x11438E4, o, b, 7, 2, 4, 2)


def _flag_2fd(m, e):
    """The byte table at 0x3c6a2fd, indexed as the game does (uxtw of a value at most 4)."""
    return int(m.u8(m.main + 0x3C6A2FD + (e & 0xFFFFFFFF)) != 0)


def _mode2_target(c, e):
    """0xfa6f4c."""
    c &= 0xFF
    if c <= 3:
        return int(e == 1)
    if c == 4:
        return int(e != 0)
    if c == 5:
        return int(e & 0xFFFFFFFD != 0)
    if c == 6:
        return 1 if e > 3 else int(e & 0xF == 1)
    return 0


def _mode1_target(m, flag, c, e):
    """0xfad7c4."""
    c &= 0xFF
    se = _s32(e)
    if c == 0:
        if se > 4:
            return 0
        return _flag_2fd(m, e) if flag & 0xFF else int(e == 1)
    if c in (2, 4):
        return int(se < 5 and e & 0xFFFFFFFD == 1)
    if c in (3, 5):
        return int(se < 5 and e & 0xFFFFFFFB != 0)
    return 0


@lifted(0xFA5F84)
def target_allowed(m, mode, flag, c, d, e, *_):
    """Whether target class e fits the rule c in battle mode `mode` (0, 1 with flag, 2)."""
    mode &= 0xFFFFFFFF; e &= 0xFFFFFFFF
    if mode == 2:
        return _mode2_target(c, e)
    if mode == 1:
        return _mode1_target(m, flag, c, e)
    if mode != 0 or _s32(e) > 4:
        return 0
    if flag & 0xFF and d & 0xFFFFFFFF == 3:
        return _flag_2fd(m, e)
    return int(e == 1)


@lifted(0x287F478)
def target_allowed_for(m, o, b, *_):
    """Tail call of 0xfa5f84 with the battle's mode, flags and the battler's target class (0x1589a40)."""
    a = m.call(m.main + 0x144B6D4, m.u64(o + 0x10))
    f = m.call(m.main + 0x1365ADC, m.u64(o + 8))
    c = m.call(m.main + 0x281B234, m.u64(o + 0x10))
    e = m.call(m.main + 0x1589A40, o, m.vcall(b, 0x98) & 0xFFFFFFFF)
    d = m.call(m.main + 0x144B6C8, m.u64(o + 8))
    return target_allowed(m, a, f, c, d, e)


@lifted(0x15C04A4)
def same_side_ids(m, o, a, b, *_):
    """Tail call of 0x118ab58 on [[o+0x10]+0x290]."""
    return m.call(m.main + 0x118AB58, m.u64(m.u64(o + 0x10) + 0x290), a, b)


@lifted(0x15C04B0)
def has_battler(m, o, ident, *_):
    """Whether the u32-keyed battler map at o+0x140 holds a nonzero battler for `ident`."""
    from pokeldn.sv.battle.engine.containers import find
    node = find(m, o + 0x140, ident & 0xFFFFFFFF, 4)
    return int(node != 0 and m.u64(node + 0x18) != 0)


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


@lifted(0x119E440)
def previous_element(m, e, *_):
    """The element before e in its keyed list (key +0x12 in the map at [e+8]+8), or 0."""
    from pokeldn.sv.battle.engine.containers import find
    key = m.u16(e + 0x12)
    if key == 0xEE:
        return 0
    node = find(m, m.u64(e + 8) + 8, key, 2)
    return node + 0x18 if node else 0


@lifted(0x1360728)
def run_136075c_queue_62(m, o, ident, *_):
    m.call_void(m.main + 0x136075C, m.u64(o + 0x20), ident)
    m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0x62, ident & 0xFFFFFFFF)


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


@lifted(0x1155138)
def queue_c2(m, o, rec, *_):
    """Queue command 0xc2 (u16 rec+0x30, u32 rec+0, u8 rec+0x38) through 0x1155168."""
    q = m.call(m.main + 0x1143584, o, rec)
    m.call_void(m.main + 0x119AFF0, m.u64(q + 0x18), 0xC2, m.u16(rec + 0x30), m.u32(rec), m.u8(rec + 0x38))


@lifted(0x157EEB8)
def queue_move_result(m, o, b, t, v, flag, *_):
    """Tail call of 0x1580450 (flag bit 0) or 0x157ef30 with the queue object, b's id, t and v."""
    q = m.call(m.main + 0x1143584, o, b)
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    target = 0x1580450 if flag & 1 else 0x157EF30
    return _tail(m, m.main + target, q, ident, t, v & 0xFFFFFFFF)


@lifted(0x157EF30)
def queue_cb_49(m, q, ident, t, *_):
    """Queue command 0xcb (ident, 0x49, t's id) through the 0xffff0000-terminated push 0x157ebc0."""
    other = m.vcall(t, 0x98) & 0xFFFFFFFF
    return _tail(m, m.main + 0x157EBC0, m.u64(q + 0x18), 0xCB, ident & 0xFFFFFFFF, 0x49, other, 0xFFFF0000)


@lifted(0x283D610)
def battler_by_id(m, o, ident, *_):
    """Tail call of 0xf21c94 on [[o+8]+0x30]."""
    return m.call(m.main + 0xF21C94, m.u64(m.u64(o + 8) + 0x30), ident)


@lifted(0x114FCD8)
def change_hp(m, o, b, delta, a, c, show, *_):
    """Apply an HP change to the battler: a gain runs vf 0x2e8 and queues command 3 (id, delta u16); a
    loss runs 0x13fced4 (id, -delta, a, c) and queues command 1 (id, c, -delta u16, a u8). With `show`
    set, command 0x9a (id, delta) follows when the battler has a slot."""
    delta &= 0xFFFFFFFF
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    d = _s32(delta)
    if d >= 1:
        m.vcall_void(b, 0x2E8, delta)
        m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 3, ident, delta & 0xFFFF)
    elif d < 0:
        n = (-delta) & 0xFFFFFFFF
        m.call_void(m.main + 0x13FCED4, m.u64(o + 0x20), m.vcall(b, 0x98) & 0xFFFFFFFF, n,
                    a & 0xFFFFFFFF, c & 0xFFFFFFFF)
        i2 = m.vcall(b, 0x98) & 0xFFFFFFFF
        m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 1, i2, c & 0xFFFFFFFF, n & 0xFFFF, a & 0xFF)
    if show & 1 == 0:
        return
    pos = m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), ident)
    if pos & 0xFF == 10:
        return
    m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0x9A, ident, delta)


@lifted(0x12D0848)
def init_0x80(m, o, src, *_):
    """Vtable 0x44fcd70 at +0, then the 0x78 bytes of src at +8."""
    m.put(o, 8, m.main + 0x44FCD70)
    m.write(o + 8, m.read(src, 0x78))


@lifted(0x127C86C)
def free_element(m, owner, e, *_):
    """Unlink e, clear its 0x58-byte payload and push it on the front of the free list (head key
    owner+0x72)."""
    from pokeldn.sv.battle.engine.containers import _key_node, unlink
    unlink(m, e)
    m.put(e + 0x12, 4, 0xEE00EE)
    m.write(e + 0x18, bytes(0x58))
    free = _key_node(m, owner + 8, m.u16(owner + 0x72))
    if free:
        m.put(e + 0x14, 2, m.u16(free + 0x28))
        m.put(free + 0x2A, 2, m.u16(e + 0x10))
    else:
        m.put(e + 0x14, 2, 0xEE)
    m.put(owner + 0x72, 2, m.u16(e + 0x10))


@lifted(0xB860E0)
def record_field10_by_pair(m, o, *_):
    """Field 10 (u8) of the record keyed u16 +8 * 10000 + u16 +0xa in the table static 0x46d7438."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.containers import find
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7430, 0x46D7438, 0x46D7440)
    key = m.u16(o + 8) * 10000 + m.u16(o + 0xA)
    node = find(m, table + 0x68, key, 8)
    rec = m.u64(node + 0x18) if node else m.u64(table + 0xD0)
    return fb.u8(m, rec, 10)


# Position -> client slot rows (5 = none): 0x3c6a348, 0x3c6a374, 0x3c6a3a0, 0x3c6a3cc, 0x3c6a3f8, 0x3c6a424.
_ROW_348 = (0, 1) + (5,) * 9
_ROW_374 = (0, 1, 0, 1) + (5,) * 7
_ROW_3A0 = (0, 1, 2, 3) + (5,) * 7
_ROW_3CC = (0, 1, 0, 3) + (5,) * 7
_ROW_3F8 = (0, 1, 2) + (5,) * 8
_ROW_424 = (0, 2, 3, 4, 1, 1, 1, 1, 1, 1, 5)


@lifted(0x127E444)
def position_used(m, o, pos, *_):
    """Whether battle position `pos` belongs to a client in the setup's mode and rule."""
    s = m.u64(o + 8)
    mode, rule, pos = m.u32(s + 0x36C), m.u8(s + 0x370), pos & 0xFF
    if mode > 2 or pos > 10:
        return 0
    if mode == 0:
        slot = _ROW_348[pos]
    elif mode == 1:
        if rule == 5:
            row = _ROW_3F8
        elif 1 <= rule <= 3:
            row = _ROW_3A0
        elif rule == 4:
            row = _ROW_3CC
        else:
            row = _ROW_374
        slot = row[pos]
    else:
        empty = (rule == 0 and 1 <= pos <= 3) or (rule == 1 and pos & 0xFE == 2) or (rule == 2 and pos == 3)
        slot = 5 if empty else _ROW_424[pos]
    return int(slot != 5)


@lifted(0x127DCB8)
def reset_timer(m, t, *_):
    m.put(t + 0x1B, 1, 0)
    m.write(t + 0x38, bytes(0x3F0))
    m.put(t + 0x19, 2, 0x100); m.put(t + 8, 4, 0xFF); m.put(t + 0x10, 8, 0)


@lifted(0x12702C0)
def init_slots(m, o, *_):
    """Zero 0x2588 bytes, then give each of the 25 0x180-byte slots from +0x160 its defaults (kind 5,
    four 0xa bytes at +0x10, 0xa at +0xe and +0x14)."""
    m.write(o, bytes(0x2588))
    for k in range(25):
        b = o + 0x160 + 0x180 * k
        m.put(b, 1, 5); m.put(b + 0xE, 2, 0xA); m.put(b + 0x10, 4, 0x0A0A0A0A); m.put(b + 0x14, 1, 0xA)


@lifted(0x2D1FE78)
def hash_aa4611a0(m, *_): return 0xAA4611A011782F5A


@lifted(0x287A7D4)
def boosted_field_7_of(m, o, level, *_):
    """Tail call of 0xbf5fe0 with the record id 0xdedbc8 and the level 0xbf61d4 give for [[o+0x48]+0x70]."""
    p = m.u64(m.u64(o + 0x48) + 0x70)
    ident = m.call(m.main + 0xDEDBC8, p, level) & 0xFFFFFFFF   # x1 still holds level
    lv = m.call(m.main + 0xBF61D4, m.u64(m.u64(o + 0x48) + 0x70), level & 0xFFFFFFFF) & 0xFFFFFFFF
    return m.call(m.main + 0xBF5FE0, ident, lv)


@lifted(0x1142DCC)
def each_standing_11430e4(m, o, *rest):
    """When 0x113f5b8 allows it: 0x11430e4 for every party member still in the battle that 0x1142e68
    accepts."""
    if m.call(m.main + 0x113F5B8, m.call(m.main + 0x114E480, o, *rest[:7]), *rest[:7]) & 1 == 0:
        return
    with m.frame(0x30) as f:
        it, out = f, f + 0x20
        a = m.call(m.main + 0x114E480, o)
        b = m.call(m.main + 0x1482534, o)
        m.call_void(m.main + 0x1147754, it, a, b)
        while m.call(m.main + 0x1360DBC, it, out) & 1:
            a = m.call(m.main + 0x114E480, o)
            b = m.call(m.main + 0x1482534, o)
            if m.call(m.main + 0x1142E68, a, b, m.u64(out)) & 1:
                m.call_void(m.main + 0x11430E4, o, m.u64(out))


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


def _pokemon_tail(target):
    """A tail call of `target` on the Pokemon record [[o+0x48]+0x70], other arguments passed through."""
    def fn(m, o, *rest):
        return _tail(m, m.main + target, m.u64(m.u64(o + 0x48) + 0x70), *rest[:7])
    return fn


for _addr, _target in ((0x287A7C8, 0xDEE950), (0x287A9B4, 0xD974E0), (0x287A93C, 0x121C054)):
    lifted(_addr)(_pokemon_tail(_target))


@lifted(0x287A5E8)
def pokemon_species(m, o, *rest):
    """0xcdf348 of the Pokemon record [[o+0x48]+0x70] when its +8 is set, else 0xe13ef0 of [o+0x48] (u16)."""
    p = m.u64(m.u64(o + 0x48) + 0x70)
    if m.u64(p + 8):
        return _tail(m, m.main + 0xCDF348, p, *rest[:7])
    return m.call(m.main + 0xE13EF0, m.u64(o + 0x48), *rest[:7]) & 0xFFFF


def _move_ref(m, dst, src, *_):
    """Move-assign an intrusive pointer (u32 count at +0x28; the last reference runs vf 0x10). Returns
    x0 as the game leaves it: the old pointer, or what vf 0x10 returned."""
    from pokeldn.sv.battle.machine import UnliftedCall
    old = m.u64(dst)
    m.put(dst, 8, 0)
    r = old
    if old:
        n = m.u32(old + 0x28)
        m.put(old + 0x28, 4, n - 1)
        if n == 1:
            r = m.vcall(old, 0x10)
        elif n == 0:
            raise UnliftedCall("DecrementReferenceInternal abort")
    v = m.u64(src)
    m.put(src, 8, 0)
    m.put(dst, 8, v)
    return r


for _addr in (0xFAB7D4, 0xFAC0EC, 0xFA9200):
    lifted(_addr)(_move_ref)


@lifted(0xFA9BA8)
def init_fa9ba8(m, o, p, *_):
    m.put(o + 0x18, 8, p); m.put(o + 0x20, 8, 0)
    m.put(o + 8, 8, p); m.put(o + 0x10, 8, 0x82A2B175229D6A5B)


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


def _pair_record(m, o):
    """The record keyed u16 +8 * 10000 + u16 +0xa in the table static 0x46d7438, else its default."""
    from pokeldn.sv.battle.engine.containers import find
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7430, 0x46D7438, 0x46D7440)
    node = find(m, table + 0x68, m.u16(o + 8) * 10000 + m.u16(o + 0xA), 8)
    return m.u64(node + 0x18) if node else m.u64(table + 0xD0)


@lifted(0x1046124)
def record_field6_by_pair(m, o, *_):
    from pokeldn.sv.battle.engine import flatbuffer as fb
    return fb.u8(m, _pair_record(m, o), 6)


def _pair_struct22(at):
    """Byte `at` of the inline struct in field 22 of the pair-keyed record (no vtable size check)."""
    def fn(m, o, *_):
        rec = _pair_record(m, o)
        return m.u8(rec + m.u16(rec - m.s(rec, 4) + 0x30) + at)
    return fn


for _addr, _at in ((0xCEDBF4, 0), (0xCEDF60, 2), (0xCEE488, 4)):
    lifted(_addr)(_pair_struct22(_at))


@lifted(0xFAEB40)
def clear_entries_35(m, o, *_):
    """Clear 35 (u64, u32) entries 0x10 apart, then the u32 at +0x230 and the byte at +0x234."""
    for k in range(35):
        m.put(o + 0x10 * k, 8, 0); m.put(o + 0x10 * k + 8, 4, 0)
    m.put(o + 0x230, 4, 0); m.put(o + 0x234, 1, 0)


@lifted(0xFA9128)
def set_30_from(m, o, src, *_):
    m.put(o + 0x30, 8, m.u64(src))


@lifted(0xFB00D0)
def get_10(m, o, *_): return m.u64(o + 0x10)


@lifted(0xFB00B8)
def get_190(m, o, *_): return m.u64(o + 0x190)


@lifted(0x2A1D994)
def is_entry_58(m, o, v, *_):
    """0 when byte +0x710 of [o+0x50] is set, else whether the u32 at +0x58 equals v."""
    if m.u8(m.u64(o + 0x50) + 0x710):
        return 0
    return int(m.u32(o + 0x58) == v & 0xFFFFFFFF)


@lifted(0xFAAD24)
def copy_ref(m, dst, src, *_):
    """Copy an intrusive pointer, taking a reference (u32 count at +0x28)."""
    from pokeldn.sv.battle.machine import UnliftedCall
    p = m.u64(src)
    m.put(dst, 8, p)
    if p:
        n = m.u32(p + 0x28)
        m.put(p + 0x28, 4, n + 1)
        if n == 0xFFFFFFFF:
            raise UnliftedCall("IncrementReference abort")
    return dst


def _release_ref(m, p):
    """Drop one reference of an intrusive pointer (u32 count at +0x28); the last one runs vf 0x10.
    Returns x0 as the game leaves it."""
    from pokeldn.sv.battle.machine import UnliftedCall
    n = m.u32(p + 0x28)
    m.put(p + 0x28, 4, n - 1)
    if n == 1:
        return _tail(m, m.u64(m.u64(p) + 0x10), p)
    if n == 0:
        raise UnliftedCall("DecrementReferenceInternal abort")
    return p


@lifted(0x175D10C)
def release_ref(m, holder, *_):
    p = m.u64(holder)
    return _release_ref(m, p) if p else 0


@lifted(0xFAD6D0)
def add_ref_slot(m, o, src, *_):
    """Store *src, with a reference taken, in the first empty of the four slots at +0x60..+0x78
    (nothing when all four are taken)."""
    from pokeldn.sv.battle.machine import UnliftedCall
    ret = o
    for off in (0x60, 0x68, 0x70, 0x78):
        if m.u64(o + off) == 0:
            slot = o + off
            break
    else:
        return o + 0x78
    if off == 0x78:
        ret = o + 0x78
    v = m.u64(src)
    if v == 0:
        m.put(slot, 8, 0)
        return ret
    n = m.u32(v + 0x28)
    m.put(v + 0x28, 4, n + 1)
    if n == 0xFFFFFFFF:
        raise UnliftedCall("IncrementReference abort")
    m.put(slot, 8, v)
    return 0


@lifted(0xFA0110)
def run_fa06a0(m, o, p, *_):
    """When [[o+0x38]+0x708] is set: tail call of 0xfa06a0 (0x1345c30(p), that pointer)."""
    if m.u64(m.u64(o + 0x38) + 0x708) == 0:
        return o
    r = m.call(m.main + 0x1345C30, p)
    return _tail(m, m.main + 0xFA06A0, r, m.u64(m.u64(o + 0x38) + 0x708))


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


@lifted(0x2899FE0)
def cap_seven_at_6(m, p, *_):
    """Lower each of the seven signed bytes at p above 6 to 6; 1 when any was lowered."""
    hit = 0
    for k in range(7):
        if m.s(p + k, 1) >= 7:
            m.put(p + k, 1, 6)
            hit = 1
    return hit


@lifted(0x343CF20)
def guard_release(m, guard, *_):
    """__cxa_guard_release (the SDK's, through [0x46ca088]): byte 0 and byte 1 (complete) set to 1 under
    the guard mutex; a waiter (byte 1 bit 2) needs the condition variable."""
    from pokeldn.sv.battle.machine import UnliftedCall
    if m.u8(guard + 1) >> 2 & 1:
        raise UnliftedCall("guard release with a waiter")
    m.put(guard, 1, 1)
    m.put(guard + 1, 1, 1)
    return 0


def _static_chain(m, levels):
    """Function-local statics nested in each other: each (guard GOT, slot GOT) level, once built, holds
    the address of the next level's slot (the last holds 0)."""
    guard, slot = (m.u64(m.main + a) for a in levels[0])
    if m.u8(guard) & 1 or m.call(m.main + 0x343CF10, guard) & 0xFFFFFFFF == 0:
        return
    if len(levels) > 1:
        _static_chain(m, levels[1:])
        m.put(slot, 8, m.u64(m.main + levels[1][1]))
    else:
        m.put(slot, 8, 0)
    m.call_void(m.main + 0x343CF20, guard)


@lifted(0x1A07AA4)
def static_1a07aa4(m, *_):
    """A four-level static chain (guards 0x46d3e70, 0x46d3aa8, 0x46d39b0, 0x46d39c0); its outer slot."""
    _static_chain(m, ((0x46D3E70, 0x46D3E78), (0x46D3AA8, 0x46D3AB0), (0x46D39B0, 0x46D39B8),
                      (0x46D39C0, 0x46D39C8)))
    return m.u64(m.main + 0x46D3E78)


@lifted(0xEF2F38)
def bind_record(m, acc, core, party, *_):
    """Point a record accessor at a plain core and party record, then seal them (checksum, encrypt)."""
    from pokeldn.sv.battle.engine.pokemon import BLOCKS, CORE, _checksum, _xor_words
    m.put(acc + 0x18, 2, 0)
    m.put(acc + 8, 8, party)
    m.put(acc + 0x10, 8, core)
    if core:
        m.put(core + 6, 2, _checksum(m, core))
        _xor_words(m, core + BLOCKS, (CORE - BLOCKS) // 2, m.u32(core))
    if party and core:
        _xor_words(m, party, 8, m.u32(core))
    m.put(acc + 0x18, 1, 1)
    return acc


@lifted(0xE14EA8)
def load_record(m, acc, core, party, *_):
    """Copy a sealed core record (0x148 bytes) and party record (16) into an accessor's buffers, check the
    checksum (bad: flag bit 2 at +4) and seal them again."""
    from pokeldn.sv.battle.engine.pokemon import BLOCKS, CORE, _checksum, _xor_words
    r = acc
    if core:
        r = m.u64(acc + 0x10)
        m.write(r, m.read(core, CORE))
    if party:
        m.write(m.u64(acc + 8), m.read(party, 16))
    c = m.u64(acc + 0x10)
    m.put(acc + 0x18, 2, 1)
    _xor_words(m, c + BLOCKS, (CORE - BLOCKS) // 2, m.u32(c))
    p = m.u64(acc + 8)
    if p:
        _xor_words(m, p, 8, m.u32(m.u64(acc + 0x10)))
    c = m.u64(acc + 0x10)
    m.put(acc + 0x18, 1, 0)
    if m.u16(c + 6) != _checksum(m, c):
        m.put(c + 4, 2, m.u16(c + 4) | 4)
    if m.u8(acc + 0x19) == 0:
        c = m.u64(acc + 0x10)
        if c:
            m.put(c + 6, 2, _checksum(m, c))
            _xor_words(m, c + BLOCKS, (CORE - BLOCKS) // 2, m.u32(c))
        p = m.u64(acc + 8)
        if p and m.u64(acc + 0x10):
            _xor_words(m, p, 8, m.u32(m.u64(acc + 0x10)))
        m.put(acc + 0x18, 1, 1)
    return r


def _record_accessors():
    """More accessors of the stored Pokemon record (pokemon._GETTERS / _SETTERS layout)."""
    from pokeldn.sv.battle.engine.pokemon import _getter, _setter
    for a, *spec in ((0xD90170, 0, 0x20, 1, 0, 0x4742290, False),
                     (0xD90B3C, 0, 0x23, 1, 0, 0x4742290, False),
                     (0xD9782C, 1, 0x3C, 1, 0, 0x47422E0, False)):
        lifted(a)(_getter(*spec))
    for a, *spec in ((0xE15484, "party", 4, 2, 0, 0x47423D0, True),
                     (0xE15E20, "party", 0xA, 2, 0, 0x47423D0, True)):
        lifted(a)(_setter(*spec))


_record_accessors()


def _record_accessors_2():
    from pokeldn.sv.battle.engine.pokemon import _getter
    lifted(0xC4EA44)(_getter(0, 0x19, 1, 0, 0x4742290, False))


_record_accessors_2()


@lifted(0x1373610)
def refresh_716(m, o, a, b, *_):
    """0x13736d8, then when the type chain of [o+0x48]+0x28 (vf 0) holds the static 0x46dcd58: +0x716 =
    0xbf44f4 of [[o+0x48]+0x48]+0x70."""
    m.call_void(m.main + 0x13736D8, o, a & 1, b & 1)
    p = m.u64(o + 0x48)
    t = m.vcall(p + 0x28, 0)
    guard = m.u64(m.main + 0x46DCD50)
    if m.u8(guard) & 1 == 0 and m.call(m.main + 0x343CF10, guard) & 0xFFFFFFFF:
        m.put(m.u64(m.main + 0x46DCD58), 8, m.call(m.main + 0x19F5520))
        m.call_void(m.main + 0x343CF20, guard)
    want = m.u64(m.main + 0x46DCD58)
    while t:
        if t == want:
            v = m.call(m.main + 0xBF44F4, m.u64(m.u64(p + 0x48) + 0x70))
            m.put(o + 0x716, 2, v)
            return v
        t = m.u64(t)
    return 0


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


@lifted(0x287A9CC)
def pokeparam_103b7d0(m, o, *_):
    """The tail call of 0x103b7d0 on [o+0x48]."""
    return _tail(m, m.main + 0x103B7D0, m.u64(o + 0x48))


@lifted(0xFA0E60)
def construct_fa0e60(m, o, *_):
    """Constructor (vtable 0x4500ae0 / 0x4500b18): +8 the last entry of the thread's stack at the TLS slot
    [0x4765a30] (count +0x80, entries from +0), the six slots +0x30..+0x58 and the byte +0x60 cleared.
    The tail call 0xfa102c releases the six slots, all empty here, and returns 0."""
    t = _tls_stack(m)
    top = 0
    if t:
        n = m.u64(t + 0x80)
        if n:
            top = m.u64(t + 8 * n - 8)
    m.put(o + 0x10, 8, 0)               # the base constructor's stores, moved after the TLS read
    m.put(o + 0x18, 4, 0)
    m.put(o + 0x28, 4, 0)
    m.put(o, 8, m.main + 0x4500AE0)
    m.put(o + 8, 8, top)
    m.put(o + 0x20, 8, m.main + 0x4500B18)
    m.put(o + 0x60, 1, 0)
    m.write(o + 0x30, bytes(0x30))
    return 0


@lifted(0xFA13D0)
def form_by_item(m, o, holder, *_):
    """For the Pokemon at *holder: species 0x2cc runs 0x133b218(1, 0); species 0x378 / 0x379 in form 0
    whose held item's name hash ([o+0x190] vf 0x30) is the matching one also do, as the tail call."""
    from pokeldn.sv.battle.machine import FUNCTIONS, UnliftedCall
    if 0x133B218 not in FUNCTIONS:          # reached after the getters write
        raise UnliftedCall("main+0x133b218")
    acc = lambda: m.u64(m.u64(holder) + 0x70)
    species = m.call(m.main + 0xBF44F4, acc()) & 0xFFFFFFFF
    form = m.call(m.main + 0xBF41A8, acc()) & 0xFFFFFFFF
    item = m.call(m.main + 0xD974E0, acc()) & 0xFFFFFFFF
    if species & 0xFFFF == 0x2CC:
        m.call_void(m.main + 0x133B218, m.u64(holder), 1, 0)
    t = m.u64(o + 0x190)
    if t:
        n = m.u32(t + 0x28)
        m.put(t + 0x28, 4, n + 1)
        if n == 0xFFFFFFFF:
            raise UnliftedCall("IncrementReference abort")
    r = m.vcall(t, 0x30, item)
    h = r
    if t:
        n = m.u32(t + 0x28)
        m.put(t + 0x28, 4, n - 1)
        if n == 1:
            r = _tail(m, m.u64(m.u64(t) + 0x10), t)
        elif n == 0:
            raise UnliftedCall("DecrementReference abort")
    if form & 0xFFFF == 0 and (species & 0xFFFF, h) in ((0x378, 0x8DF6C2E67AAFBBDF),
                                                          (0x379, 0x082F905FCEFDE31B)):
        return m.call(m.main + 0x133B218, m.u64(holder), 1, 0)
    return r


@lifted(0xD8FA80)
def effort(m, o, i, *_):
    """EV i (0 HP .. 5 Spe) of [[o+0x48]+0x70]; 0 for i above 5 (0xd8fa88, jump table 0x3c62c98)."""
    i &= 0xFF
    if i > 5:
        return 0
    getter = (0xD8FAE8, 0xD8FE2C, 0xD90170, 0xD904B4, 0xD90B3C, 0xD907F8)[i]
    return m.call(m.main + getter, m.u64(m.u64(o + 0x48) + 0x70))


@lifted(0xE14560)
def computed_spa(m, pp, *_):
    """Sp. Atk computed from the core record (lift1._computed_stat: base 0xcee2d0, hyper-training bit 3,
    IV 0xd9894c, EV 0xd904b4, nature column 2)."""
    from pokeldn.sv.battle.engine.lift1 import _computed_stat
    return _computed_stat(0xCEE2D0, 3, 0xD9894C, 0xD904B4, 2)(m, pp)


def _holds_pokeparam_type(m, p):
    """Whether the type chain p+0x28 vf 0 returns (linked by +0) holds the static 0x46dcd58 (built by
    0x19f5520 on first use); with x0 as the game leaves it when the chain does not."""
    t = x0 = m.vcall(p + 0x28, 0)
    guard = m.u64(m.main + 0x46DCD50)
    if m.u8(guard) & 1 == 0:
        x0 = m.call(m.main + 0x343CF10, guard) & 0xFFFFFFFF
        if x0:
            m.put(m.u64(m.main + 0x46DCD58), 8, m.call(m.main + 0x19F5520))
            x0 = m.call(m.main + 0x343CF20, guard)
    want = m.u64(m.main + 0x46DCD58)
    while t:
        if t == want:
            return True, x0
        t = m.u64(t)
    return False, x0


@lifted(0x287A330)
def refresh_pokeparam(m, o, full, a, b, again, *_):
    """Copy values of the Pokemon object [o+0x48] into the battler: when `full`, +0x5a (vf 0x80) and
    +0x58 (vf 0x70(0) * u16 +0x3f4 / 10); +0x54 (vf 0xb8); own vf 0x7f8(b, a); when b, +0x47e (vf 0x140);
    when `again`, own vf 0x810 before and (as the tail call) after; the form (0xbf41a8) at +0x718 when
    the object's type chain holds 0x46dcd58."""
    from pokeldn.sv.battle.machine import FUNCTIONS, UnliftedCall
    if 0x103B7D0 not in FUNCTIONS:          # reached after the first writes (vf 0x7f8, vf 0x350, 0x287a9cc)
        raise UnliftedCall("main+0x103b7d0")
    if full & 1:
        p = m.u64(o + 0x48)
        m.put(o + 0x5A, 2, m.vcall(p, 0x80))
        v = m.vcall(m.u64(o + 0x48), 0x70, 0) & 0xFFFF
        m.put(o + 0x58, 2, ((v * m.u16(o + 0x3F4)) & 0xFFFFFFFF) // 10)
    m.put(o + 0x54, 4, m.vcall(m.u64(o + 0x48), 0xB8))
    m.vcall_void(o, 0x7F8, b & 1, a & 1)
    if b & 1:
        m.put(o + 0x47E, 2, m.vcall(m.u64(o + 0x48), 0x140))
    if again & 1:
        m.vcall_void(o, 0x810)
    p = m.u64(o + 0x48)
    found, x0 = _holds_pokeparam_type(m, p)
    if found:
        x0 = m.call(m.main + 0xBF41A8, m.u64(m.u64(p + 0x48) + 0x70))
        m.put(o + 0x718, 2, x0)
    if again & 1:
        return _tail(m, m.u64(m.u64(o) + 0x810), o)
    return x0


@lifted(0xFA1220)
def form_by_item_all(m, o, holder, *_):
    """0xfa13d0 for each of the [*holder+0x60] members (+0x30, at most 6) whose type chain holds
    0x46dcd58, through a counted reference to its Pokemon object (+0x48)."""
    from pokeldn.sv.battle.machine import FUNCTIONS, UnliftedCall
    if 0x133B218 not in FUNCTIONS:          # 0xfa13d0 reaches it after this writes
        raise UnliftedCall("main+0x133b218")
    n = m.u8(m.u64(holder) + 0x60)
    x0 = o
    for i in range(n):
        p = m.u64(m.u64(holder) + 0x30 + 8 * i) if i <= 5 else 0
        if not _holds_pokeparam_type(m, p)[0]:
            x0 = 0
            continue
        pp = m.u64(p + 0x48)
        with m.frame(0x10) as local:
            m.put(local, 8, pp)
            if pp == 0:
                x0 = m.call(m.main + 0xFA13D0, o, local)
                continue
            c = m.u32(pp + 0x28)
            m.put(pp + 0x28, 4, c + 1)
            if c == 0xFFFFFFFF:
                raise UnliftedCall("IncrementReference abort")
            x0 = m.call(m.main + 0xFA13D0, o, local)
        c = m.u32(pp + 0x28)
        m.put(pp + 0x28, 4, c - 1)
        if c == 1:
            x0 = _tail(m, m.u64(m.u64(pp) + 0x10), pp)
        elif c == 0:
            raise UnliftedCall("DecrementReference abort")
    return x0


@lifted(0x127DEEC)
def clear_127deec(m, o, *_):
    """Clear the five 0x38-byte records from +0x28 (0x30 zero bytes and the flag byte after them); a
    nonempty map at +0x140 (count +0x198) is emptied through its allocator, which the engine refuses."""
    from pokeldn.sv.battle.machine import UnliftedCall
    if m.u64(o + 0x198):
        raise UnliftedCall("0x127deec with a nonempty map")
    for i in range(5):
        m.write(o + 0x28 + 0x38 * i, bytes(0x31))
    return o


@lifted(0x127E2B8)
def build_slot_table(m, out, s, *_):
    """Fill the 11 slot entries of `out` (8 bytes from +8, initialised 0x0000_0500_0000_0000) for the
    battle's 2, 4 or 10 slots (u32 [s+0x36c], table 0x3c69db8): a slot 0x127e444 accepts takes kind
    0xe1eea8 (+5) when that is not 5; then each slot's member (0x1153868 kind and index, the member list
    [s+0x30]) unless vf 0x200 says otherwise stores its id (vf 0x98) at +0 and in the map at +0x60
    (0xf785a8), or 0."""
    from pokeldn.sv.battle.machine import FUNCTIONS, UnliftedCall
    if 0xF785A8 not in FUNCTIONS:           # reached after the first writes
        raise UnliftedCall("main+0xf785a8")
    for k in range(11):
        m.put(out + 8 + 8 * k, 8, 0x50000000000)
    mode = m.u32(s + 0x36C)
    last = (1, 3, 9)[mode] if mode <= 2 else 3       # 0x3c69db8
    for i in range(last + 1):
        e = out + 8 + 8 * i
        if m.call(m.main + 0x127E444, m.u64(s + 0x290), i) & 1 and m.u8(e + 4) == 0:
            kind = m.call(m.main + 0xE1EEA8, m.u64(s + 0x290), i)
            if kind & 0xFF != 5:
                m.put(e + 4, 1, 1)
                m.put(e + 5, 1, kind)
                m.put(e, 4, 0)
    x0 = 0
    with m.frame(0x10) as f:
        for i in range(last + 1):
            e = out + 8 + 8 * i
            x0 = m.call(m.main + 0x1153868, m.u64(s + 0x290), i, f, f + 4)
            kind = m.u8(f)
            if kind == 5:
                continue
            idx = m.u8(f + 4)
            lst = m.u64(s + 0x30) + 0x38 * kind
            b = m.u64(lst + 0x28 + 8 * idx) if m.u8(lst + 0x58) > idx else 0
            if b == 0:
                m.put(e, 4, 0)
                continue
            x0 = m.vcall(b, 0x200)
            if x0 & 1:
                m.put(e, 4, 0)
                continue
            ident = m.vcall(b, 0x98) & 0xFFFFFFFF
            m.put(f + 8, 4, ident)
            m.put(e, 4, ident)
            x0 = m.call(m.main + 0xF785A8, out + 0x60, f + 8)
            m.put(x0, 1, i)
    return x0


@lifted(0x343D5B0)
def ticks_to_ns(m, ticks, *_):
    """nn::os::ConvertToTimeSpan (the SDK's, through [0x46ca3d0]): ticks of the 19.2 MHz counter as
    nanoseconds, saturated at the s64 limits."""
    t = ticks - (1 << 64) if ticks >> 63 else ticks
    if t > 0x0275254609ABE000:
        return 0x7FFFFFFFFFFFFFFF
    if t < -0x0275254609ABE000:
        return 1 << 63
    div = lambda a, b: abs(a) // b * (1 if a >= 0 else -1)      # C division, toward zero
    q = div(t, 19200000)
    frac = div((t - q * 19200000) * 1000000000, 19200000)
    return (q * 1000000000 + frac) & 0xFFFFFFFFFFFFFFFF


@lifted(0x127EFC0)
def construct_127efc0(m, o, *_):
    """Constructor (vtable 0x44ff128, 0x5f8 bytes): two arrays of 19 entries of 0x28 bytes, from +8 and
    +0x300, each entry zero but for its vtable ([0x46e2f58] + 0x10) and its index as a u32 at +0x18."""
    vt = m.u64(m.main + 0x46E2F58) + 0x10
    data = bytearray(0x5F8)
    data[0:8] = (m.main + 0x44FF128).to_bytes(8, "little")
    for base in (8, 0x300):
        for k in range(19):
            e = base + 0x28 * k
            data[e:e + 8] = vt.to_bytes(8, "little")
            data[e + 0x18:e + 0x1C] = k.to_bytes(4, "little")
    m.write(o, bytes(data))
    return o


@lifted(0xFA91A0)
def draw_five(m, o, *_):
    """Five u16 values of 0xfa91f8 on [o+0x30] stored at +0x98..+0xa0."""
    r = 0
    for k in range(5):
        r = m.call(m.main + 0xFA91F8, m.u64(o + 0x30))
        m.put(o + 0x98 + 2 * k, 2, r)
    return r


@lifted(0xFA47B4)
def set_40_x2(m, o, src, *_):
    m.put(o + 0x40, 8, m.u64(src))
    m.put(o + 0x48, 8, m.u64(src + 8))
    return o


@lifted(0xFA47E4)
def set_40_x3(m, o, src, *_):
    m.put(o + 0x40, 8, m.u64(src))
    m.put(o + 0x48, 8, m.u64(src + 8))
    m.put(o + 0x50, 8, m.u64(src + 0x10))
    return o


@lifted(0x1807920)
def run_114aab0(m, o, arg, *_):
    """0x114aab0(0x1807950([o+0x28]), a scratch u64, arg)."""
    p = m.call(m.main + 0x1807950, m.u64(o + 0x28))
    with m.frame(0x10) as f:
        return _tail(m, m.main + 0x114AAB0, p, f, arg)


@lifted(0x171A59C)
def note_kind_7(m, o, b, *_):
    """When 0x171a624(b, 7) gives a value: 0x171a604(queue, b's id (vf 0x98), 2, value) and 1."""
    r = m.call(m.main + 0x171A624, o, b, 7)
    if r & 0xFFFFFFFF == 0:
        return r
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    q = m.call(m.main + 0x1143584, o)
    m.call_void(m.main + 0x171A604, q, ident, 2, r & 0xFFFFFFFF)
    return 1


@lifted(0xFAFB78)
def reset_tables(m, o, *_):
    """Clear +0x78 (u64) and +0x80 (u32); in [o+0x58] the count +0x408 and the 0x430 bytes after the
    header of each of its 32 tables (pointers every 0x20 from +8); in [o+0x38] the count +0xc08 and
    the u16 +8 of each of its 96 entries (pointers every 0x20 from +8)."""
    t = m.u64(o + 0x58)
    m.put(o + 0x80, 4, 0)
    m.put(o + 0x78, 8, 0)
    first = m.u64(t + 8)
    m.put(t + 0x408, 4, 0)
    r = 0
    for k in range(32):
        r = (first if k == 0 else m.u64(t + 8 + 0x20 * k)) + 8
        m.write(r, bytes(0x430))
    e = m.u64(o + 0x38)
    m.put(e + 0xC08, 4, 0)
    for k in range(96):
        m.put(m.u64(e + 8 + 0x20 * k) + 8, 2, 0)
    return r


def _weak_table(m):
    """The weak handle table [[0x46d3910]] (its static built on first use), also noted in [0x46d3918]."""
    guard = m.u64(m.main + 0x46D3908)
    if m.u8(guard) & 1 == 0 and m.call(m.main + 0x343CF10, guard) & 0xFFFFFFFF:
        m.call_void(m.main + 0x190, m.u64(m.main + 0x46D3DE8), m.u64(m.main + 0x46D3910), m.main + 0x4383000)
        m.call_void(m.main + 0x343CF20, guard)
    table = m.u64(m.u64(m.main + 0x46D3910))
    m.put(m.u64(m.main + 0x46D3918), 8, table)
    return table


def _release_weak(m, p, x0):
    """ReleaseWeakReference on the slot p: drop the u16 count at +0x18; the last one marks the slot dead
    (u32 +0x1c = -1) and, when it was not, hands its id (+0) back to the table's pool (0xb44438).
    Returns x0 as the game leaves it (`x0` unless 0xb44438 ran)."""
    from pokeldn.sv.battle.machine import FUNCTIONS, UnliftedCall
    n = m.u16(p + 0x18)
    if n == 0:
        raise UnliftedCall("ReleaseWeakReference abort")
    if n == 1 and m.u32(p + 0x1C) != 0xFFFFFFFF and 0xB44438 not in FUNCTIONS:
        raise UnliftedCall("main+0xb44438")
    m.put(p + 0x18, 2, n - 1)
    if n != 1:
        return x0
    was = m.u32(p + 0x1C)
    m.put(p + 0x1C, 4, 0xFFFFFFFF)
    if was == 0xFFFFFFFF:
        return x0
    table = _weak_table(m)
    with m.frame(0x10) as f:
        m.put(f, 8, m.u64(p))
        return _tail(m, m.main + 0xB44438, table + 0x8040, f)


@lifted(0x17E5A08)
def release_weak(m, holder, *_):
    """ReleaseWeakReference on the slot *holder (none when 0)."""
    p = m.u64(holder)
    return _release_weak(m, p, holder) if p else holder


@lifted(0xC1A3F4)
def make_weak(m, holder, obj, *_):
    """holder = {a weak handle to obj from the table (0xc1a58c), the slot's id}; the handle it held is
    released first."""
    from pokeldn.sv.battle.machine import FUNCTIONS, UnliftedCall
    old = m.u64(holder)
    if old and m.u16(old + 0x18) == 1 and m.u32(old + 0x1C) != 0xFFFFFFFF and 0xB44438 not in FUNCTIONS:
        raise UnliftedCall("main+0xb44438")
    table = _weak_table(m)
    with m.frame(0x10) as h:
        x0 = m.call_sret(m.main + 0xC1A58C, h, table, obj)
        old = m.u64(holder)
        m.put(holder, 8, 0)
        if old:
            x0 = _release_weak(m, old, x0)
        e = m.u64(h)
        m.put(holder, 8, e)
        m.put(holder + 8, 8, m.u64(e))
    return x0


def _copy_with_map(m, o, src, size, map_at, insert):
    """Copy `size` bytes from +8 of `src`, then rebuild the map at `map_at` (count +0x58 of it, nodes
    from +0x30 of src's map: key +0x10, byte +0x14) through `insert`. Emptying a nonempty map goes
    through its allocator, which the engine refuses."""
    from pokeldn.sv.battle.machine import FUNCTIONS, UnliftedCall
    if m.u64(o + map_at + 0x58):
        raise UnliftedCall("copy over a nonempty map")
    node = m.u64(src + map_at + 0x30)
    if node and insert not in FUNCTIONS:
        raise UnliftedCall(f"main+0x{insert:x}")
    m.write(o + 8, m.read(src + 8, size))
    x0 = o + 8
    while node:
        v = m.u8(node + 0x14)
        x0 = m.call(m.main + insert, o + map_at, node + 0x10)
        m.put(x0, 1, v)
        node = m.u64(node)
    return x0


@lifted(0xF7842C)
def copy_with_map(m, o, src, *_):
    """0x58 bytes and the map at +0x60 (inserter 0xf785a8)."""
    return _copy_with_map(m, o, src, 0x58, 0x60, 0xF785A8)


@lifted(0xF78E88)
def copy_with_map_2f0(m, o, src, *_):
    """0x2e4 bytes and the map at +0x2f0 (inserter 0x1589bc0)."""
    return _copy_with_map(m, o, src, 0x2E4, 0x2F0, 0x1589BC0)


@lifted(0x183F12C)
def record_and_command_7d(m, o, b, a, pair, *_):
    """0x183f194([o+0x20], b's id (vf 0x98), a, pair), then the tail call of command 0x7d (0x119aff0) on
    [o+0x18] with (a & 0xff, id, pair[0], pair[1])."""
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    m.call_void(m.main + 0x183F194, m.u64(o + 0x20), ident, a & 0xFFFFFFFF, pair)
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x7D, a & 0xFF, ident, m.u32(pair),
                 m.u32(pair + 4))


@lifted(0x28870EC)
def command_c0(m, o, a, b, *_):
    """The tail call of command 0xc0 (0x119aff0) on [o+0x18] with (a, b & 0xff)."""
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0xC0, a & 0xFFFFFFFF, b & 0xFF)


@lifted(0x157FBC0)
def battler_4d8_command_1e(m, o, b, v, *_):
    """vf 0x4d8(v) on the main battler for b's id (0xf21c94), then the tail call of command 0x1e
    (0x119aff0) on [o+0x18] with (id, v)."""
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    t = m.call(m.main + 0xF21C94, m.u64(m.u64(m.u64(o + 0x20) + 0x10) + 0x30), ident)
    m.vcall_void(t, 0x4D8, v & 0xFFFFFFFF)
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x1E, ident, v & 0xFFFFFFFF)


@lifted(0x1361C58)
def message_by_kind(m, o, a, kind, *_):
    """The tail call of 0x287ee68([o+0x20], a, message) for the message `kind` 1..9 picks (jump table
    0x3c6a4f8): 1 0x267, 2 0x269, 4 0x2aa, 5 0x2ac, 8 by 0x13616dc's 1..4 (0x2c1, 0x2c3, 0x2c5, 0x33d),
    9 0x37a; the others send nothing."""
    k = (kind - 1) & 0xFFFFFFFF
    msg = {0: 0x267, 1: 0x269, 3: 0x2AA, 4: 0x2AC, 8: 0x37A}.get(k)
    if k == 7:
        r = m.call(m.main + 0x13616DC, m.u64(m.u64(o + 0x10) + 0x70))
        j = (r - 1) & 0xFF
        if j >= 4:
            return r
        msg = 0x033D02C502C302C1 >> (16 * j)
    if msg is None:
        return o
    return _tail(m, m.main + 0x287EE68, m.u64(o + 0x20), a & 0xFFFFFFFF, msg)


@lifted(0x17CE41C)
def raise_level(m, o, b, n, out, *_):
    """For n (u16) nonzero: b's vf 0x240(n) result (16 bytes) into `out` when given; then on the main
    battler for b's id, n up to 5: vf 0x608, command 0x14 and, unless the id has slot 10 (0x1381420),
    command 0x90 (id, 0) as the tail call; above 5: vf 0x610(n) and command 0x15 (id, n)."""
    if n & 0xFFFF == 0:
        return o
    if out:
        r = m.vcall(b, 0x240, n & 0xFFFFFFFF)
        m.put(out, 8, r[0]); m.put(out + 8, 8, r[1])
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    t = m.call(m.main + 0xF21C94, m.u64(m.u64(m.u64(o + 0x20) + 0x10) + 0x30), ident)
    if n & 0xFFFF > 5:
        m.vcall_void(t, 0x610, n & 0xFFFFFFFF)
        return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x15, ident, n & 0xFFFF)
    m.vcall_void(t, 0x608)
    m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0x14, ident)
    s = m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), ident)
    if s & 0xFF == 0xA:
        return s
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x90, ident, 0)


@lifted(0x1155BDC)
def follow_link(m, o, e, loose, *_):
    """Follow e's chain of links: each entry's u16 key (+0x14, 0xee ends it) names the next entry in the
    map at [entry+8]+8; the first whose byte +0x28 (and, unless `loose`, u32 +0x34) match e's and whose
    byte +0x41 is clear; 0 when the chain ends."""
    from pokeldn.sv.battle.engine.containers import find
    if e == 0:
        return 0
    side, tag = m.u8(e + 0x28), m.u32(e + 0x34)
    x = e
    while True:
        key = m.u16(x + 0x14)
        if key == 0xEE:
            return 0
        node = find(m, m.u64(x + 8) + 8, key, 2)
        if node == 0:
            return 0
        x = node + 0x18
        if m.u8(x + 0x28) == side and (loose & 1 or m.u32(x + 0x34) == tag) and m.u8(x + 0x41) == 0:
            return x


def _assign_strong(m, holder, p, x0):
    """*holder = p as a strong reference: p's control block ([p+0x30]) gains one (u16 +0x1a; the first
    one also stores vf 0 of the object +0x10 at +8 and -2 at +0x1c); the old value's block loses one,
    the last one clearing +0x10 and ending in the old object's vf 0x50 (the tail call). `x0` is what the
    caller leaves in x0 otherwise ("holder" or "old")."""
    from pokeldn.sv.battle.machine import UnliftedCall
    old = m.u64(holder)
    if p:
        c = m.u64(p + 0x30)
        if m.u64(c + 0x10) == 0 or m.u16(c + 0x1A) == 0xFFFF:
            raise UnliftedCall("AddReference abort")
    if old and m.u16(m.u64(old + 0x30) + 0x1A) == 0:
        raise UnliftedCall("ReleaseReference abort")
    if p:
        n = m.u16(c + 0x1A)
        m.put(c + 0x1A, 2, n + 1)
        if n == 0:
            obj = m.u64(c + 0x10)
            r = m.call(m.u64(m.u64(obj)), obj, p)
            m.put(c + 8, 8, r)
            m.put(c + 0x1C, 4, 0xFFFFFFFE)
    m.put(holder, 8, p)
    ret = holder if x0 == "holder" else old
    if old == 0:
        return ret
    c = m.u64(old + 0x30)
    n = m.u16(c + 0x1A)
    m.put(c + 0x1A, 2, n - 1)
    if n != 1:
        return ret
    m.put(c + 0x10, 8, 0)
    return _tail(m, m.u64(m.u64(old) + 0x50), old)


@lifted(0xFA6560)
def assign_strong(m, holder, p, *_):
    return _assign_strong(m, holder, p, "holder")


@lifted(0xFA3DA0)
def assign_strong_2(m, holder, p, *_):
    return _assign_strong(m, holder, p, "old")


@lifted(0xF79260)
def copy_50_entries(m, o, src, *_):
    """Copy the first 12 bytes of each of the 50 entries of 0x18 bytes from +0x10."""
    for k in range(50):
        e = 0x10 + 0x18 * k
        m.write(o + e, m.read(src + e, 12))
    return o


@lifted(0x1360830)
def release_kind_4(m, o, b, *_):
    """Release (0x13608b0) every kind-4 handler of b's id (0x119b478 on [[o+8]+0xd0]) until one whose
    u32 +0x68 is set; that one, or 0."""
    h = m.u64(m.u64(o + 8) + 0xD0)
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    e = m.call(m.main + 0x119B478, h, 4, ident)
    while e and m.u32(e + 0x68) == 0:
        m.call_void(m.main + 0x13608B0, o, e)
        e = m.call(m.main + 0x119B478, h, 4, ident)
    return e


@lifted(0x13606F8)
def release_kind_4_of(m, o, ident, *_):
    """The tail call of 0x1360830([o+0x18], the main battler for ident)."""
    from pokeldn.sv.battle.engine.containers import battler
    b = battler(m, m.u64(m.u64(o + 0x10) + 0x30), ident)
    return _tail(m, m.main + 0x1360830, m.u64(o + 0x18), b)


@lifted(0x114BFDC)
def run_effect_entry(m, o, kind, arg, *_):
    """0x114bff0 on [o+0x18], inlined: the function 0x114c070 gives for `kind` called with a local u32 and
    arg; a nonzero result is pushed by 0x114ed80 (3, kind, 4, 0, arg & 0xff, result, the local) and
    gives 1, else 0."""
    q = m.u64(o + 0x18)
    f = m.call(m.main + 0x114C070, kind & 0xFFFFFFFF)
    with m.frame(0x10) as local:
        if f == 0:
            m.put(local, 4, 0)
            return 0
        r = m.call(f, local, arg & 0xFFFFFFFF)
        if r == 0:
            return 0
        m.call_void(m.main + 0x114ED80, q, 3, kind & 0xFFFFFFFF, 4, 0, arg & 0xFF, r, m.u32(local))
        return 1


def _tls_stack(m):
    """The thread's object stack at the TLS slot [0x4765a30] (built on first use), or 0."""
    guard = m.main + 0x4765A38
    if m.u8(guard) & 1 == 0 and m.call(m.main + 0x343CF10, guard) & 0xFFFFFFFF:
        m.call_void(m.main + 0xF538C0, m.main + 0x4765A30, m.main + 0x27BF190)
        m.call_void(m.main + 0x190, m.u64(m.main + 0x46D3900), m.main + 0x4765A30, m.main + 0x4383000)
        m.call_void(m.main + 0x343CF20, guard)
    return m.call(m.main + 0x343DA20, m.u32(m.main + 0x4765A30))


@lifted(0xFA6950)
def make_entry_scoped(m, o, out, src, *_):
    """With [o] pushed on the thread's object stack (at most 16, count +0x80): out = {u32 **src, 0x20
    zero bytes}; then popped (the slot keeps [o]). Returns the stack (0 when the thread has none)."""
    from pokeldn.sv.battle.machine import UnliftedCall
    top = m.u64(o)
    t = _tls_stack(m)
    if t:
        n = m.u64(t + 0x80)
        if n >= 0x10:
            raise UnliftedCall("abort: object stack full")
        m.put(t + 8 * n, 8, top)
        m.put(t + 0x80, 8, n + 1)
    m.put(out, 4, m.u32(m.u64(src)))
    m.write(out + 8, bytes(0x20))
    if t:
        m.put(t + 0x80, 8, m.u64(t + 0x80) - 1)
    return t


@lifted(0x16B08E8)
def clear_ref_deque(m, d, *_):
    """std::deque of strong references (map +8..+0x10, start +0x40, size +0x48, 512 per block) cleared:
    each element's control block ([p+0x30], u16 +0x1a) loses one, the last one clearing +0x10 and
    running vf 0x50; size 0, start 0x100 or 0x200 for one or two blocks. Freeing blocks beyond two
    goes through the allocator, which the engine refuses."""
    from pokeldn.sv.battle.machine import UnliftedCall
    begin, end = m.u64(d + 8), m.u64(d + 0x10)
    if (end - begin) >> 3 >= 3:
        raise UnliftedCall("deque clear freeing blocks")
    x0 = d
    if begin != end:
        start, size = m.u64(d + 0x40), m.u64(d + 0x48)
        bp = begin + (start >> 9) * 8
        it = m.u64(bp) + (start & 0x1FF) * 8
        stop = m.u64(begin + ((start + size) >> 9) * 8) + ((start + size) & 0x1FF) * 8
        while it != stop:
            x0 = p = m.u64(it)
            if p:
                c = m.u64(p + 0x30)
                n = m.u16(c + 0x1A)
                m.put(c + 0x1A, 2, n - 1)
                if n == 1:
                    m.put(c + 0x10, 8, 0)
                    x0 = _tail(m, m.u64(m.u64(p) + 0x50), p)
                elif n == 0:
                    raise UnliftedCall("ReleaseReference abort")
            it += 8
            if it - m.u64(bp) == 0x1000:
                bp += 8
                it = m.u64(bp)
        begin, end = m.u64(d + 8), m.u64(d + 0x10)
    m.put(d + 0x48, 8, 0)
    blocks = (end - begin) >> 3
    if blocks in (1, 2):
        m.put(d + 0x40, 8, 0x100 * blocks)
    return x0


@lifted(0xFA4064)
def release_eleven(m, o, *_):
    """Clear and release (u32 count +0x28, vf 0x10 on the last one) the eleven references at +0..+0x50,
    in the game's order."""
    x0 = 0
    for off in (0, 8, 0x30, 0x10, 0x38, 0x18, 0x40, 0x20, 0x48, 0x28, 0x50):
        x0 = p = m.u64(o + off)
        m.put(o + off, 8, 0)
        if p:
            x0 = _release_ref(m, p)
    return x0


@lifted(0xFAEFFC)
def reset_slots_at_8(m, o, *_):
    """The tail call of 0x12702c0 on o+8."""
    return _tail(m, m.main + 0x12702C0, o + 8)


@lifted(0xFA7B98)
def assign_strong_3(m, holder, p, *_):
    return _assign_strong(m, holder, p, "old")


@lifted(0xFAED8C)
def clear_map(m, t, *_):
    """unordered_map clear: when it holds entries (count +0x58), free the node list (+0x30) through
    0x151aadc, then zero the buckets (+0, count +8), the list head and the count."""
    if m.u64(t + 0x58) == 0:
        return t
    r = m.call(m.main + 0x151AADC, t, m.u64(t + 0x30))
    n = m.u64(t + 8)
    m.put(t + 0x30, 8, 0)
    if n:
        m.write(m.u64(t), bytes(8 * n))
    m.put(t + 0x58, 8, 0)
    return r


@lifted(0xFAECA8)
def release_pairs_and_clear(m, o, *_):
    """Clear and release the two strong references (+0x18, +0x20) of every node of the list at +0x1d0,
    then the tail call of 0xfaed8c on the map at +0x1a0."""
    from pokeldn.sv.battle.machine import FUNCTIONS, UnliftedCall
    if m.u64(o + 0x1A0 + 0x58) and 0x151AADC not in FUNCTIONS:
        raise UnliftedCall("main+0x151aadc")
    node = m.u64(o + 0x1D0)
    while node:
        for off in (0x18, 0x20):
            p = m.u64(node + off)
            m.put(node + off, 8, 0)
            if p:
                c = m.u64(p + 0x30)
                n = m.u16(c + 0x1A)
                m.put(c + 0x1A, 2, n - 1)
                if n == 1:
                    m.put(c + 0x10, 8, 0)
                    m.vcall_void(p, 0x50)
                elif n == 0:
                    raise UnliftedCall("ReleaseReference abort")
        node = m.u64(node)
    return _tail(m, m.main + 0xFAED8C, o + 0x1A0)


@lifted(0xFAEF9C)
def reset_round_state(m, o, *_):
    """Reset the parts of the state at +0x10 (0xfaf048), +0xb0 (0xfafb78), +0x110 (0x127381c), +0xf0
    (0xfaf004), +0x150 (0xfaeff4), +0x170 (0xfaf010) and +0x190 (0xfaeffc); then 0xfaf024 on [o+0x1b0],
    inlined: the bytes +0x5c, +0x64, +0x6c, +0x74 and the u32s +0x60, +0x68, +0x70 and u64 +0x78
    cleared."""
    for off, fn in ((0x10, 0xFAF048), (0xB0, 0xFAFB78), (0x110, 0x127381C), (0xF0, 0xFAF004),
                    (0x150, 0xFAEFF4), (0x170, 0xFAF010), (0x190, 0xFAEFFC)):
        m.call_void(m.main + fn, m.u64(o + off))
    t = m.u64(o + 0x1B0)
    for k in range(3):
        m.put(t + 0x5C + 8 * k, 1, 0)
        m.put(t + 0x60 + 8 * k, 4, 0)
    m.put(t + 0x74, 1, 0)
    m.put(t + 0x78, 8, 0)
    return t


@lifted(0x288C240)
def note_kind(m, o, b, a, kind, *_):
    """Kinds 1, 0x11, 0x1a and 0x23 first record (b's id, a, 0x10a) in a fresh 0x139b698 entry through
    0x282410c; every kind goes to 0x1482e80; kinds 2, 3 and 4 then queue 0x2a, 0x2e or 0x2d for b
    (0x114ade8, the tail call); kind 0x17 builds an entry (0x1480a6c), sends it through 0x1581080 and
    0x288c444, then queues 0x2a."""
    from pokeldn.sv.battle.machine import FUNCTIONS, UnliftedCall
    k = kind & 0xFF
    marked = k <= 0x23 and (1 << k) & 0x804020002
    for need, when in ((0x282410C, marked), (0x1581080, k == 0x17), (0x288C444, k == 0x17)):
        if when and need not in FUNCTIONS:          # reached after the first writes
            raise UnliftedCall(f"main+0x{need:x}")
    if marked:
        e = m.call(m.main + 0x139B698, o)
        e2 = m.call(m.main + 0x139B698, o)
        m.put(e + 8, 4, m.vcall(b, 0x98))
        m.put(e + 6, 2, a)
        m.put(e + 0xC, 2, 0x10A)
        m.call_void(m.main + 0x282410C, m.call(m.main + 0x1578F00, o), e, e2 + 0x10)
    r = _tail(m, m.main + 0x1482E80, m.call(m.main + 0x1143584, o), b, a & 0xFFFFFFFF, kind & 0xFFFFFFFF)
    if k in (2, 3, 4):
        msg = {2: 0x2A, 3: 0x2E, 4: 0x2D}[k]
        return _tail(m, m.main + 0x114ADE8, m.call(m.main + 0x1143584, o), b, msg)
    if k != 0x17:
        return r
    r1 = m.call(m.main + 0x11440E8, m.call(m.main + 0x1482534, o))
    r2 = m.call(m.main + 0x114ACBC, o)
    h = m.call(m.main + 0x14D96D8, m.call(m.main + 0x1482534, o))
    pair = m.call(m.main + 0x1480A6C, h, 2, m.vcall(b, 0x98) & 0xFFFFFFFF, r1, r2)
    with m.frame(0x10) as sp:
        m.put(sp, 8, pair[0]); m.put(sp + 8, 8, pair[1])
        m.call_void(m.main + 0x1581080, m.call(m.main + 0x1143584, o), m.vcall(b, 0x98) & 0xFFFFFFFF, 0)
        m.call_void(m.main + 0x288C444, m.call(m.main + 0x1143584, o), b, 2, sp)
        return _tail(m, m.main + 0x114ADE8, m.call(m.main + 0x1143584, o), b, 0x2A)


@lifted(0xC1A58C)
def weak_handle(m, o, obj, *_):
    """A weak handle to `obj`, written to the struct x8 points at: an id from the pool at +0x8040
    (0xc1a7a0) names a 0x20-byte slot in blocks of 0x400 (block table +0x30, stride 0x20, count +0x8000;
    the current block at +0x8038), filled with fresh slots up to it; the slot takes obj at +0x10, its
    generation +4 steps (0 wraps to 1) and its u16 count +0x18 gains one. Under the lock +0x8130,
    released by signalling +0x8138 (the tail call)."""
    from pokeldn.sv.battle.machine import FUNCTIONS, UnliftedCall
    out = m.x8
    if m.u64(o + 0x8130):
        raise UnliftedCall("weak handle table locked")
    blk_i = m.u64(o + 0x8038)
    if m.u64(m.u64(o + 0x30 + blk_i * 0x20) + 0x8000) >= 0x400 and 0xC1ADEC not in FUNCTIONS:
        raise UnliftedCall("main+0xc1adec")
    idx = m.call(m.main + 0xC1A7A0, o + 0x8040) & 0xFFFFFFFF
    m.put(o + 0x8130, 8, m.call(m.main + 0x343C290))
    blk_i = m.u64(o + 0x8038)
    blk = m.u64(o + 0x30 + blk_i * 0x20)
    cnt = m.u64(blk + 0x8000)
    total = (cnt + (blk_i << 10)) & 0xFFFFFFFFFFFFFFFF
    while total <= idx:
        if cnt == 0x400:
            m.call_void(m.main + 0xC1ADEC, o + 0x28)
            blk_i = (m.u64(o + 0x8038) + 1) & 0xFFFFFFFFFFFFFFFF
            m.put(o + 0x8038, 8, blk_i)
            blk = m.u64(o + 0x30 + blk_i * 0x20)
            cnt = m.u64(blk + 0x8000)
        if cnt >= 0x400:
            raise UnliftedCall("abort: weak handle block full")
        e = blk + cnt * 0x20
        m.put(e, 8, total & 0xFFFFFFFF)
        m.put(e + 8, 8, 0)
        m.put(e + 0x10, 8, 0)
        m.put(e + 0x18, 8, 0xFFFFFFFF00000000)
        m.put(blk + 0x8000, 8, m.u64(blk + 0x8000) + 1)
        blk_i = m.u64(o + 0x8038)
        blk = m.u64(o + 0x30 + blk_i * 0x20)
        cnt = m.u64(blk + 0x8000)
        total = (cnt + (blk_i << 10)) & 0xFFFFFFFFFFFFFFFF
    blk = m.u64(o + 0x30 + (idx >> 10) * 0x20)
    j = idx & 0x3FF
    if m.u64(blk + 0x8000) <= j:
        raise UnliftedCall("abort: weak handle slot out of range")
    e = blk + j * 0x20
    n = m.u32(e + 4)
    m.put(e + 0x10, 8, obj)
    m.put(e + 4, 4, n + 1 if n != 0xFFFFFFFF else 1)
    m.put(out, 8, e)
    if blk:
        h = m.u16(e + 0x18)
        if h == 0xFFFF:
            raise UnliftedCall("AddWeakReference abort")
        m.put(e + 0x18, 2, h + 1)
    m.put(o + 0x8130, 8, 0)
    return m.call(m.main + 0x343E5E0, o + 0x8138)


def _counted_copy(m, out, p):
    """*out = p with a reference taken (u32 count +0x28)."""
    from pokeldn.sv.battle.machine import UnliftedCall
    if p and m.u32(p + 0x28) == 0xFFFFFFFF:
        raise UnliftedCall("IncrementReference abort")
    m.put(out, 8, p)
    if p:
        m.put(p + 0x28, 4, m.u32(p + 0x28) + 1)


@lifted(0x1142424)
def counted_130(m, o, *_):
    """The counted reference [o+0x130], written to the struct x8 points at."""
    _counted_copy(m, m.x8, m.u64(o + 0x130))
    return o


@lifted(0xFA6CC8)
def counted_by_id(m, o, ident, *_):
    """The counted reference the map at +0x98 holds for the u32 id (0xfa6e40), or 0, written to the struct
    x8 points at."""
    from pokeldn.sv.battle.engine.containers import find
    out = m.x8
    ident &= 0xFFFFFFFF
    if m.u64(o + 0xA0) == 0:
        m.put(out, 8, 0)
        return o
    if find(m, o + 0x98, ident, 4) == 0:
        m.put(out, 8, 0)
        return o + 0x98
    with m.frame(0x10) as key:
        m.put(key, 4, ident)
        slot = m.call(m.main + 0xFA6E40, o + 0x98, key)
    _counted_copy(m, out, m.u64(slot))
    return slot
