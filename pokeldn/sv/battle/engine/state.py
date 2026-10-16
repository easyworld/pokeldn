"""Constructors, resets and copies of the server's state objects and their tables."""

from pokeldn.sv.battle.engine.calls import M32, M64, _tail
from pokeldn.sv.battle.engine.containers import _map_clear
from pokeldn.sv.battle.engine.heap import _dealloc, _need_free
from pokeldn.sv.battle.engine.references import (
    _addref_shared, _construct_counted_base, _move_counted, _release_ref, _tls_stack, _tls_stack_built,
    _tls_top,
)
from pokeldn.sv.battle.machine import UnliftedCall, lifted


@lifted(0x283E210)
def init_283e210(m, p, *_):
    m.put(p, 8, 0); m.put(p + 8, 2, 0)
    m.call_void(m.main + 0x179372C, p + 0x10)
    m.put(p + 0x20, 8, 0x100000000)
    m.call_void(m.main + 0x1146154, p + 0x28)


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


@lifted(0x12D0848)
def init_0x80(m, o, src, *_):
    """Vtable 0x44fcd70 at +0, then the 0x78 bytes of src at +8."""
    m.put(o, 8, m.main + 0x44FCD70)
    m.write(o + 8, m.read(src, 0x78))


@lifted(0x12702C0)
def init_slots(m, o, *_):
    """Zero 0x2588 bytes, then give each of the 25 0x180-byte slots from +0x160 its defaults (kind 5,
    four 0xa bytes at +0x10, 0xa at +0xe and +0x14)."""
    m.write(o, bytes(0x2588))
    for k in range(25):
        b = o + 0x160 + 0x180 * k
        m.put(b, 1, 5); m.put(b + 0xE, 2, 0xA); m.put(b + 0x10, 4, 0x0A0A0A0A); m.put(b + 0x14, 1, 0xA)


@lifted(0xFA9BA8)
def init_fa9ba8(m, o, p, *_):
    m.put(o + 0x18, 8, p); m.put(o + 0x20, 8, 0)
    m.put(o + 8, 8, p); m.put(o + 0x10, 8, 0x82A2B175229D6A5B)


@lifted(0xFAEB40)
def clear_entries_35(m, o, *_):
    """Clear 35 (u64, u32) entries 0x10 apart, then the u32 at +0x230 and the byte at +0x234."""
    for k in range(35):
        m.put(o + 0x10 * k, 8, 0); m.put(o + 0x10 * k + 8, 4, 0)
    m.put(o + 0x230, 4, 0); m.put(o + 0x234, 1, 0)


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


@lifted(0xF79260)
def copy_50_entries(m, o, src, *_):
    """Copy the first 12 bytes of each of the 50 entries of 0x18 bytes from +0x10."""
    for k in range(50):
        e = 0x10 + 0x18 * k
        m.write(o + e, m.read(src + e, 12))
    return o


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


@lifted(0x10E2464)
def clear_id_byte(m, p, *_):
    m.put(p, 4, 0); m.put(p + 4, 1, 10)


@lifted(0x1149604)
def init_0x4b(m, p, *_):
    m.put(p, 8, 0xE00000000); m.put(p + 8, 2, 0); m.put(p + 0x18, 8, 0); m.put(p + 0x10, 4, 0)
    m.put(p + 0x20, 2, 0x9C)
    for o in (0x24, 0x2C, 0x34, 0x3C, 0x43):
        m.put(p + o, 8, 0)


@lifted(0x1380C4C)
def clear_0x19(m, p, *_):
    m.put(p + 0x18, 1, 0); m.put(p, 8, 0); m.put(p + 8, 8, 0); m.put(p + 0x10, 8, 0)


@lifted(0xFA24B4)
def init_fa24b4(m, p, *_):
    m.put(p, 8, 0)
    for o in range(0x38, 0x340, 0x10):
        m.put(p + o + 8, 8, 0); m.put(p + o, 4, 0)
    m.put(p + 0x3A2, 2, 10); m.put(p + 0x3A8, 1, 10); m.put(p + 0x3A4, 4, 0x0A0A0A0A); m.put(p + 0x3A9, 1, 0)
    m.put(p + 0x3AC, 2, 10); m.put(p + 0x3B2, 1, 10); m.put(p + 0x3AE, 4, 0x0A0A0A0A); m.put(p + 0x3B3, 1, 0)
    return p


@lifted(0x127EB14)
def reset_38_entries(m, o, *_):
    """For each of 38 entries of 0x28 bytes from +0x18 whose u32 +0x10 is set: clear its u64 +0xc and
    the low 3 bits of its u64 +0."""
    for k in range(38):
        e = o + 0x18 + 0x28 * k
        if m.u32(e + 0x10):
            m.put(e + 0xC, 8, 0)
            m.put(e, 8, m.u64(e) & ~7)


@lifted(0x127381C)
def reset_127381c(m, o, *_):
    p = m.u64(o + 8)
    m.put(p + 0xA, 4, 0xFFFFFFFF); m.put(p + 0x938, 1, 0); m.put(p + 8, 1, 0); m.put(p + 0xE, 2, 0)
    m.put(p + 0x10, 4, 0); m.put(p + 0x14, 2, 10)
    m.call_void(m.main + 0x127399C, p + 0x18)
    r = m.call(m.main + 0x343C220, p + 0x60, 0, 0x6B)
    m.put(m.u64(o + 0x28), 1, 0)
    q = m.u64(o + 0x48)
    m.put(q + 8, 4, 0x05050505); m.put(q + 0xC, 1, 5)
    q = m.u64(o + 0x68)
    m.put(q + 0x18, 8, 0); m.put(q + 8, 8, 0); m.put(q + 0x10, 8, 0); m.put(q + 0x1E, 8, 0); m.put(q + 0x28, 4, 0)
    for k in range(0x98, 0x188, 8):
        m.put(o + k, 4, 0); m.put(o + k + 4, 1, 0)
    m.put(o + 0x88, 1, 0); m.put(o + 0x90, 8, 0)
    return r


@lifted(0x127D5CC)
def init_127d5cc(m, o, a, *_):
    m.put(o + 0xB0, 4, 0); m.put(o, 8, m.main + 0x44EE690)
    m.put(o + 0x4E, 2, 0); m.put(o + 0x56, 2, 0); m.put(o + 0x5E, 8, 0); m.put(o + 0x66, 8, 0)
    m.put(o + 0x6E, 2, 0); m.put(o + 0x80, 8, 0); m.put(o + 0x88, 4, 0); m.put(o + 0xB8, 8, 0)
    m.put(o + 0xC, 1, 0); m.put(o + 8, 4, 0); m.put(o + 0xE, 2, 0); m.put(o + 0x10, 4, 0)
    m.put(o + 0x70, 8, a); m.put(o + 0x78, 8, 0x1FFFFFFFFFFFFFFF)
    m.put(o + 0xA0, 8, 0x1FFFFFFFFFFFFFFF); m.put(o + 0xA8, 8, 0)
    m.put(o + 0xC0, 4, 0x3F800000); m.put(o + 0xD, 1, 5)
    for k in range(0x14, 0x5C, 8):
        m.put(o + k, 8, 0x500)
    m.put(o + 0x5C, 4, 0x500)
    m.put(o + 0x90, 8, 0); m.put(o + 0x98, 8, a)
    return o


@lifted(0xFAEFF4)
def clear_1b(m, o, *_):
    m.put(o + 0x1B, 1, 0)


lifted(0xFA3AE0)(lambda m, o, src, *_: _move_counted(m, o, src))


@lifted(0xF79BE8)
def copy_38_entries(m, dst, src, *_):
    """The 0x20 bytes at +0x10 of each of 38 entries of 0x28 bytes."""
    for k in range(38):
        m.write(dst + 0x10 + 0x28 * k, m.read(src + 0x10 + 0x28 * k, 0x20))


# (offset, size) pairs 0xf575d4 copies, in its order.
_COPY_F575D4 = ((0x400, 0x14), (0x414, 7), (0x47E, 4), (0x482, 5), (0x488, 7), (0x490, 6), (0x6EF, 2),
                (0x6F2, 4), (0x6F8, 4), (0x487, 1), (0x426, 0x58), (0x496, 8), (0x4A0, 0x100), (0x5A0, 8),
                (0x5A8, 0x24), (0x5CC, 0x120), (0x6EC, 3))


@lifted(0xF575D4)
def copy_f575d4(m, dst, src, *_):
    for off, n in _COPY_F575D4:
        m.write(dst + off, m.read(src + off, n))


@lifted(0xF57514)
def copy_f57514(m, dst, src, *_):
    """0xf575d4, then the u16s +0x716/+0x718 when src's +0x28 list (vf 0) holds the static 0x46d3f08
    (the game addresses them from src+0x28, after a pre-indexed load)."""
    m.call_void(m.main + 0xF575D4, dst, src)
    x = m.vcall(src + 0x28, 0)
    if m.u8(m.u64(m.main + 0x46D3F00)) & 1 == 0:
        raise UnliftedCall("static 0x46d3f08 not built")
    static = m.u64(m.main + 0x46D3F08)
    while x:
        if x == static:
            m.put(dst + 0x716, 2, m.u16(src + 0x716)); m.put(dst + 0x718, 2, m.u16(src + 0x718))
            return
        x = m.u64(x)


@lifted(0xF78964)
def copy_entries_f78964(m, dst, src, *_):
    """For each node of src's map list (+0x38): the dst node of the same u16 key (map at dst+8) takes its
    u16s +0x28..+0x2c and 0x58 bytes from +0x30; then the u16s +0x70/+0x72."""
    from pokeldn.sv.battle.engine.containers import find_u16
    node = m.u64(src + 0x38)
    while node:
        d = find_u16(m, dst + 8, m.u16(node + 0x10))
        if not d:
            raise UnliftedCall("0xf78964 on a key dst lacks (the game faults)")
        for k in (0x28, 0x2A, 0x2C):
            m.put(d + k, 2, m.u16(node + k))
        m.write(d + 0x30, m.read(node + 0x30, 0x58))
        node = m.u64(node)
    m.put(dst + 0x70, 2, m.u16(src + 0x70)); m.put(dst + 0x72, 2, m.u16(src + 0x72))


@lifted(0xFB0194)
def construct_fb0194(m, o, src, *_):
    """vtable main+0x4500158; +8..+0x50 from src (+0x38 a referenced shared object); 0xfaeb40(+0x58); 25
    entries of 0x180 bytes from +0x50b8 reset; then the game clears +0x58..+0xc468 again
    (0xc410 bytes) and +0x7640..+0xc464, and the tail +0xc468..+0xc4a0, +0xc4a3..+0xc4a5."""
    m.put(o, 8, m.main + 0x4500158)
    for k in range(7):
        m.put(o + 8 + 8 * k, 8, m.u64(src + 8 * k))
    shared = m.u64(src + 0x30)
    if shared:
        _addref_shared(m, shared)
    for k in range(3):
        m.put(o + 0x40 + 8 * k, 8, m.u64(src + 0x38 + 8 * k))
    m.call_void(m.main + 0xFAEB40, o + 0x58)
    for e in range(o + 0x50B8, o + 0x7638, 0x180):
        m.write(e, bytes(0x180))
        m.put(e + 0x160, 1, 5); m.put(e + 0x164, 8, 0); m.put(e + 0x16C, 1, 0); m.put(e + 0x16E, 2, 10)
        m.put(e + 0x170, 4, 0x0A0A0A0A); m.put(e + 0x174, 1, 10); m.put(e + 0x178, 2, 0)
        m.put(e + 0x17A, 1, 0); m.put(e + 0x17C, 2, 0)
    m.call_void(m.main + 0x12702C0, o + 0x50B8)
    m.put(o + 0xC4A3, 2, 0); m.put(o + 0xC4A5, 1, 0)
    m.write(o + 0x58, bytes(0xC410))
    m.call_void(m.main + 0x12702C0, o + 0x50B8)
    m.write(o + 0x7640, bytes(0x4E24))
    m.write(o + 0xC484, bytes(0x1C))
    m.write(o + 0xC468, bytes(0x1A))


@lifted(0xFA97BC)
def construct_fa97bc(m, o, *_):
    """Constructor: vtables 0x44ff200 / 0x44ff238, +8 the object on top of the thread's stack (or 0),
    three empty 0x28-byte lists at +0x30, +0x58, +0x80 (0xfa98a4, the last a tail call)."""
    t = _tls_stack_built(m)
    m.put(o + 0x10, 8, 0); m.put(o + 0x18, 4, 0)
    m.put(o, 8, m.u64(m.main + 0x46D66F8) + 0x10)
    top = 0
    if t:
        n = m.u64(t + 0x80)
        if n:
            top = m.u64(t + 8 * n - 8)
    m.put(o + 0x28, 4, 0)
    m.put(o, 8, m.main + 0x44FF200); m.put(o + 8, 8, top)
    m.put(o + 0x20, 8, m.main + 0x44FF238)
    m.call_void(m.main + 0xFA98A4, o + 0x30)
    m.call_void(m.main + 0xFA98A4, o + 0x58)
    m.call_void(m.main + 0xFA98A4, o + 0x80)
    return (o + 0x80) & 0xFFFFFFFFFFFFFFFF      # the leaf 0xfa98a4 leaves x0 as it got it


@lifted(0xFAE2C8)
def construct_fae2c8(m, o, flag, *_):
    """Constructor: the counted base, vtables 0x44ed458 (+0x78, +0xc8), two empty lists (+0x40..+0x78
    and +0x80..+0xa8, each with the owner +8 and 0x1fffffffffffffff), the byte +0xb0 = flag."""
    r = _construct_counted_base(m, o)
    vt = m.main + 0x44ED458
    m.put(o, 8, vt); m.put(o + 0x20, 8, vt + 0x78); m.put(o + 0x28, 8, vt + 0xC8)
    top = m.u64(o + 8)
    m.put(o + 0x40, 8, 0); m.put(o + 0x48, 8, 0)
    m.put(o + 0x70, 8, 0); m.put(o + 0x78, 4, 0)
    m.put(o + 0xA0, 8, 0); m.put(o + 0xA8, 4, 0)
    m.put(o + 0xB0, 1, flag)
    m.put(o + 0x50, 8, 0); m.put(o + 0x58, 8, 0)
    m.put(o + 0x80, 8, 0); m.put(o + 0x88, 8, 0)
    m.put(o + 0x60, 8, top); m.put(o + 0x68, 8, 0x1FFFFFFFFFFFFFFF)
    m.put(o + 0x90, 8, top); m.put(o + 0x98, 8, 0x1FFFFFFFFFFFFFFF)
    return r


@lifted(0xFA21A8)
def construct_fa21a8(m, o, a, b, *_):
    """Constructor: vtables 0x45001e8 (+0x828, +0x878, +0x8d0 at +0x20, +0x28, +0x40), +8 the object on
    top of the thread's stack, 0xc1a3f4(+0x30, +0x28), 0xfa24b4(+0x48), the fields from +0x400 cleared
    (bytes +0x40d 2, +0x48e 10, 18 records of 16 bytes at +0x5d8 with byte 10), +0x700 a, +0x708 b.
    Returns o + 0x490 (memset's result)."""
    _construct_counted_base(m, o)
    vt = m.main + 0x45001E8
    m.put(o, 8, vt); m.put(o + 0x20, 8, vt + 0x828)
    m.put(o + 0x28, 8, vt + 0x878); m.put(o + 0x40, 8, vt + 0x8D0)
    m.call_void(m.main + 0xFA24B4, o + 0x48)
    for off, size, val in ((0x405, 8, 0), (0x400, 8, 0), (0x40D, 1, 2), (0x41C, 8, 0), (0x424, 1, 0),
                           (0x426, 8, 0), (0x42E, 1, 0), (0x410, 8, 0), (0x417, 4, 0), (0x430, 8, 0),
                           (0x438, 1, 0), (0x43A, 1, 0), (0x43C, 8, 0), (0x444, 1, 0), (0x44E, 1, 0),
                           (0x446, 8, 0), (0x450, 1, 0), (0x45A, 1, 0), (0x452, 8, 0), (0x464, 1, 0),
                           (0x45C, 8, 0), (0x466, 1, 0), (0x468, 8, 0), (0x470, 1, 0), (0x472, 8, 0),
                           (0x47A, 1, 0), (0x47C, 1, 0), (0x47E, 4, 0x10000), (0x482, 8, 0),
                           (0x48A, 4, 0), (0x48E, 1, 10)):
        m.put(o + off, size, val)
    m.write(o + 0x490, bytes(0x25C))
    for r in range(0x5D8, 0x6E8, 0x10):
        m.put(o + r, 1, 10); m.put(o + r + 0xC, 4, 0); m.put(o + r + 4, 4, 0); m.put(o + r + 8, 2, 0)
    m.put(o + 0x6E8, 1, 10)
    m.put(o + 0x6F2, 4, 0); m.put(o + 0x6F8, 4, 0); m.put(o + 0x6F0, 1, 0); m.put(o + 0x6EC, 4, 0)
    m.put(o + 0x700, 8, a); m.put(o + 0x708, 8, b)
    return o + 0x490


def _construct_keyed(m, o, key, mid, vt_got):
    """0x132f598 / 0x132f6e8: the counted base, an intermediate vtable, then the final one ([vt_got]
    +0x10, +0x90, +0xe0), +0x40 the u64 and +0x48 the u32 of key, +0x50 = 0."""
    r = _construct_counted_base(m, o)
    m.put(o, 8, mid[0]); m.put(o + 0x20, 8, mid[1]); m.put(o + 0x28, 8, mid[2])
    vt = m.u64(m.main + vt_got)
    x, w = m.u64(key), m.u32(key + 8)
    m.put(o, 8, vt + 0x10); m.put(o + 0x40, 8, x); m.put(o + 0x20, 8, vt + 0x90)
    m.put(o + 0x48, 4, w); m.put(o + 0x28, 8, vt + 0xE0); m.put(o + 0x50, 8, 0)
    return r


@lifted(0x132F598)
def construct_132f598(m, o, key, *_):
    vt = m.main + 0x44ED578
    return _construct_keyed(m, o, key, (vt, vt + 0x78, vt + 0xC8), 0x46E2558)


@lifted(0x132F6E8)
def construct_132f6e8(m, o, key, *_):
    vt = m.u64(m.main + 0x46E2560)
    return _construct_keyed(m, o, key, (vt + 0x10, vt + 0x88, vt + 0xD8), 0x46E2568)


@lifted(0x16B070C)
def destroy_deque_16b070c(m, d, *_):
    """Deque destructor: clear it (0x16b08e8), free each 0x1000-byte block of the map [d+8, d+0x10)
    to [d+0x50], empty the map and free its storage [d] (capacity [d+0x18]) to [d+0x20] (0x16b0828,
    a tail call)."""
    m.call_void(m.main + 0x16B08E8, d)
    p, end = m.u64(d + 8), m.u64(d + 0x10)
    while p != end:
        alloc = m.u64(d + 0x50)
        _dealloc(m, alloc, m.u64(p), 0x1000, 8)
        p += 8
    begin, end = m.u64(d + 8), m.u64(d + 0x10)
    if end != begin:
        m.put(d + 0x10, 8, begin)
    store = m.u64(d)
    if store == 0:
        return d
    return _dealloc(m, m.u64(d + 0x20), store, (m.u64(d + 0x18) - store) & 0xFFFFFFFFFFFFFFFF, 8)


@lifted(0x2D14150)
def clear_core_48(m, b, *_): m.put(m.u64(b + 0x48) + 0x48, 4, 0)


@lifted(0x15808D0)
def init_0x19(m, p, *_):
    m.write(p, bytes(0x18)); m.put(p + 0x18, 1, 1)


@lifted(0x2880944)
def clear_0x24b(m, p, *_): m.write(p, bytes(0x24))


@lifted(0x147ACC4)
def clear_id(m, o, ident, *_):
    """Clear the first of ten (u32 id, flag byte) entries from +8 that is flagged and holds `ident`."""
    ident &= 0xFFFFFFFF
    for i in range(10):
        if m.u8(o + 0xC + 8 * i) and m.u32(o + 8 + 8 * i) == ident:
            m.put(o + 8 + 8 * i, 4, 0)
            return


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


@lifted(0xFAF004)
def clear_2420(m, p, *_): m.put(p + 0x2420, 1, 0)


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


@lifted(0xF7C238)
def clear_40(m, rec, *_):
    m.put(rec + 0x40, 1, 0)


@lifted(0x158125C)
def clear_ffff(m, p, *_):
    m.put(p, 8, M64); m.put(p + 8, 2, 0xFFFF)


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


@lifted(0x1145AA8)
def clear_byte(m, p, *_):
    m.put(p, 1, 0)
    return p


@lifted(0x11466DC)
def init_list_44fce50(m, p, *_):
    """An object of vtable main+0x44fce50 with an empty list (byte +8, +0xc..+0x33 zero)."""
    m.write(p + 0xC, bytes(0x28)); m.put(p, 8, m.main + 0x44FCE50); m.put(p + 8, 1, 0)
    return p
