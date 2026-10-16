"""One round of the battle: the per-kind message builder, the round's run and the state reset between
rounds."""

from pokeldn.sv.battle.engine.calls import M32, _need, _tail
from pokeldn.sv.battle.engine.containers import _map_free_all
from pokeldn.sv.battle.machine import UnliftedCall, lifted


@lifted(0x113E9B0)
def run_113f4f8(m, o, *rest):
    p = m.call(m.main + 0x113E9DC, m.u64(o + 0x78), *rest[:7])
    with m.frame(0x10) as f:
        m.call_void(m.main + 0x113F4F8, p, f, f + 8)


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


@lifted(0xFAF048)
def fill_format_map(m, o, *_):
    """Clear +0x68, then set every (u16 key, byte) pair of the 0xd0-entry table at 0x3c6abe4 in the
    command-format map (0xfaf09c)."""
    m.put(o + 0x68, 8, 0)
    for i in range(0xD0):
        e = m.main + 0x3C6ABE4 + 4 * i
        v = m.u8(e + 2)
        m.put(m.call(m.main + 0xFAF09C, o, e), 1, v)


@lifted(0x127D824)
def reset_127d824(m, o, cfg, *_):
    """Reset the state's tables for a new round from cfg: +0x36c / +0x370 from cfg +0x10 / +0x14, each
    sub-table's reset (0x127e8b4, 0x127deec, 0x127ddc8, 0x127dcb8, 0x127eb14, 0x127dcfc, 0x127e2b8,
    0x127e548, 0x127e6e8, 0x127e0c8) or clear, the maps at [+0x2b0] / [+0x2f0] emptied (0x20 / 0x28
    byte nodes), 0x4a bytes copied into [+0x310]+0x1c, the seed 0x82a2b175229d6a5b at [+0x10]+0x10.
    Returns memcpy's result."""
    from pokeldn.sv.battle.machine import FUNCTIONS
    for a in (0x127E8B4, 0x127DEEC, 0x127DDC8, 0x127DCB8, 0x127EB14, 0x127DCFC, 0x127E2B8, 0xF785A8,
              0x127E548, 0x127E6E8, 0x127E0C8):     # 0xf785a8: 0x127e2b8's map insert
        if a not in FUNCTIONS:
            raise UnliftedCall(f"main+0x{a:x}")
    m.put(o + 0x36C, 4, m.u32(cfg + 0x10)); m.put(o + 0x370, 1, m.u8(cfg + 0x14))
    m.call_void(m.main + 0x127E8B4, m.u64(o + 0xD0))
    m.call_void(m.main + 0x127DEEC, m.u64(o + 0x30))
    m.call_void(m.main + 0x127DDC8, m.u64(o + 0x50))
    m.call_void(m.main + 0x127DCB8, m.u64(o + 0x70))
    m.call_void(m.main + 0x127EB14, m.u64(o + 0x90))
    m.call_void(m.main + 0x127DCFC, m.u64(o + 0xB0))
    m.call_void(m.main + 0x127E2B8, m.u64(o + 0xF0), o)
    m.call_void(m.main + 0x127E548, m.u64(o + 0x110))
    m.write(m.u64(o + 0x130) + 8, bytes(0x12C4))
    x = m.u64(o + 0x150); m.put(x + 8, 8, 0); m.put(x + 0x10, 4, 0)
    m.call_void(m.main + 0x127E6E8, m.u64(o + 0x170))
    m.put(m.u64(o + 0x190) + 8, 4, 0)
    x = m.u64(o + 0x1B0); m.put(x + 0x10, 4, 0); m.put(x + 8, 8, 0)
    x = m.u64(o + 0x1D0); m.put(x + 0x48, 1, 0); m.put(x + 0x18, 8, 0)
    m.put(m.u64(o + 0x1F0) + 8, 1, 0)
    m.write(m.u64(o + 0x210) + 8, bytes(0xD8))
    x = m.u64(o + 0x230)
    m.put(x + 8, 8, 0x0505050500000000); m.put(x + 0x10, 1, 5); m.put(x + 0x13, 1, 0); m.put(x + 0x11, 2, 0)
    m.call_void(m.main + 0x127E0C8, m.u64(o + 0x250))
    m.put(m.u64(o + 0x270) + 8, 8, 0)
    for off, node in ((0x2B0, 0x20), (0x2F0, 0x28)):
        x = m.u64(o + off)
        if m.u64(x + 0x60):
            _map_free_all(m, x, node)
    x = m.u64(o + 0x310)
    m.write(x + 0x1C, m.read(m.u64(m.u64(x + 8) + 0x38) + 0x514, 0x4A))
    m.write(x + 0x68, bytes(0x28))
    x = m.u64(o + 0x330)
    m.put(x + 0x10, 8, m.u64(m.u64(x) + 0x38) + 0x5B8)
    m.put(o + 0x35D, 8, 0); m.put(o + 0x358, 8, 0); m.put(o + 0x350, 8, 0); m.put(o + 0x368, 4, 0)
    x = m.u64(o + 0x10); v = m.u64(cfg + 0x20)
    m.put(x + 0x18, 8, v); m.put(x + 0x20, 8, 0); m.put(x + 8, 8, v); m.put(x + 0x10, 8, 0x82A2B175229D6A5B)
    m.put(m.u64(o + 8) + 0x30, 8, m.u64(cfg + 8))
    return (m.u64(o + 0x310) + 0x1C) & 0xFFFFFFFFFFFFFFFF


@lifted(0xFAF010)
def fill_five_from_28(m, p, *_):
    v = m.u64(p + 0x28)
    for k in range(5):
        m.put(p + 8 * k, 8, v)


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


@lifted(0x114C634)
def stat_entry(m, o, ident, *_):
    """The value (+0x14) of the u32-keyed node for `ident` in the map at o+8, or 0."""
    with m.frame(0x10) as k:
        m.put(k, 4, ident)
        node = m.call(m.main + 0x114C668, o + 8, k)
    return node + 0x14 if node else 0


@lifted(0x114C458)
def side_has_entries(m, o, side, *_):
    """For each member of side `side` (0x114e498) with an entry (0x114c634 on [[o+0x10]+0x2f0]) holding a
    nonzero u32 or u16 sum: a 16-byte record {u32 id, bytes +6, +8, +0xa, +0xc, +0xe, +0xd = 1}; with any,
    0x1141994 on [0x1361214(o)+0x640] decides. 0 without."""
    lst = m.call(m.main + 0x114E498, o, side)
    with m.frame(0xA0) as sp:
        recs = sp + 0x20
        for i in range(6):
            r = recs + 0x10 * i
            m.put(r, 8, 0); m.put(r + 5, 8, 0); m.put(r + 0xD, 1, 1)
        n = m.call(m.main + 0xE7E274, lst) & 0xFF
        found = 0
        for i in range(n):
            b = m.call(m.main + 0x114C614, lst, i)
            stats = m.call(m.main + 0x114C60C, m.call(m.main + 0x1482534, o))
            e = m.call(m.main + 0x114C634, stats, m.vcall(b, 0x98) & M32)
            if not e:
                continue
            v = m.u32(e)
            if v == 0 and sum(m.u16(e + k) for k in range(4, 0x10, 2)) == 0:
                continue
            r = recs + 0x10 * i
            m.put(r, 4, v)
            for j, k in enumerate((6, 8, 0xA, 0xC, 0xE)):
                m.put(r + 5 + j, 1, m.u8(e + k))
            found += 1
        if not found:
            return 0
        m.put(sp + 0x18, 1, 0)
        m.put(sp + 0x98, 1, 0)
        m.put(sp + 8, 8, lst); m.put(sp + 0x10, 8, recs)
        x = m.call(m.main + 0x113FD24, m.call(m.main + 0x1361214, o))
        m.call_void(m.main + 0x1141994, x, sp + 0x98, sp + 8)
        return int(m.u8(sp + 0x98) != 0)


@lifted(0x114C3CC)
def any_side_has_entries(m, o, out, *_):
    """out[0] = whether 0x114c458 answers yes for any of the sides 0..4 (all five are asked)."""
    hits = [m.call(m.main + 0x114C458, o, k) & 1 for k in range(5)]
    m.put(out, 1, int(sum(hits[:4]) != (M32 if hits[4] else 0)))


@lifted(0x114C390)
def check_side_entries(m, o, req, *_):
    """0x114c3cc on [[o+0x18]+0x1da0]; its answer is dropped."""
    with m.frame(0x10) as sp:
        m.put(sp + 8, 8, req)
        m.put(sp, 1, 0)
        m.call_void(m.main + 0x114C3CC, m.call(m.main + 0x114C3C4, m.u64(o + 0x18)), sp, sp + 8)


@lifted(0x114C220)
def build_round_message(m, o, out, size, count, *_):
    """Message kind 37: the queue's formats reset (0xfaf048 inlined, as kind 21), the 0x5060-byte buffer o+0x58 zeroed
    and opened with the 0x238 bytes of [o+0x40], 0x114c390, the queue bytes copied to o+0x294 (length
    o+0x290), *out = o+0x58, *size = 0x5060, *count += 1, and [o+0x40]'s request block cleared."""
    q = m.u64(o + 0x10)
    m.put(q + 0x68, 8, 0)
    for i, fmt in enumerate(_ROUND_FORMATS):
        m.put(m.call(m.main + 0xFAF09C, q, m.main + 0x3C6ABE4 + 4 * i), 1, fmt)
    buf = o + 0x58
    m.write(buf, bytes(0x5060))
    req = m.u64(o + 0x40)
    m.write(buf, m.read(req, 0x238))
    m.call_void(m.main + 0x114C390, m.u64(o + 8), req)
    q = m.u64(o + 0x10)
    n = m.u32(q + 0x68)
    m.put(o + 0x290, 4, n)
    m.write(o + 0x294, m.read(q + 0x70, n))
    m.put(out, 8, buf); m.put(size, 4, 0x5060)
    m.put(count, 8, m.u64(count) + 1)
    req = m.u64(o + 0x40)
    for off in range(0, 0x230, 0x10):
        m.put(req + off, 8, 0)
    m.put(req + 0x234, 1, 0); m.put(req + 0x230, 4, 0)


@lifted(0x288D734)
def replace_fainted_of(m, o, req, *_):
    """0x2887c60 on [[o+0x18]+0x1d80] with the request block `req`; its answer is dropped."""
    with m.frame(0x10) as sp:
        m.put(sp + 8, 8, req)
        m.put(sp, 1, 0)
        x = m.call(m.main + 0x288D768, m.u64(o + 0x18))
        m.call_void(m.main + 0x2887C60, x, sp, sp + 8)


@lifted(0x1153350)
def build_replace_message(m, o, out, size, count, *_):
    """Message kind 35: as kind 37 (0x114c220) with 0x288d734 in place of 0x114c390: the fainted slots'
    members replaced by the request block of [o+0x40]."""
    q = m.u64(o + 0x10)
    m.put(q + 0x68, 8, 0)
    for i, fmt in enumerate(_ROUND_FORMATS):
        m.put(m.call(m.main + 0xFAF09C, q, m.main + 0x3C6ABE4 + 4 * i), 1, fmt)
    buf = o + 0x58
    m.write(buf, bytes(0x5060))
    req = m.u64(o + 0x40)
    m.write(buf, m.read(req, 0x238))
    m.call_void(m.main + 0x288D734, m.u64(o + 8), req)
    q = m.u64(o + 0x10)
    n = m.u32(q + 0x68)
    m.put(o + 0x290, 4, n)
    m.write(o + 0x294, m.read(q + 0x70, n))
    m.put(out, 8, buf); m.put(size, 4, 0x5060)
    m.put(count, 8, m.u64(count) + 1)
    req = m.u64(o + 0x40)
    for off in range(0, 0x230, 0x10):
        m.put(req + off, 8, 0)
    m.put(req + 0x234, 1, 0); m.put(req + 0x230, 4, 0)


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
