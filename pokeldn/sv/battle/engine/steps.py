"""The battle-state build steps: the server construction 0x2891748 (the main module pair at N+0x150 and
N+0x170) and the steps 0x2892ac0, 0x2d381a4 and 0x2892dd4 that fill the battlers, copy the state and
finish it, with the game functions they run (docs/sv_raid.md, Reproducing a round). N is the battle
network object (vtable 0x44ff468)."""

import math
import struct

from pokeldn.sv.battle.machine import FUNCTIONS, MASK, UnliftedCall, lifted

M64 = MASK[8]
M32 = MASK[4]
ONE_F = 0x3F800000          # 1.0f, the max load factor of a fresh unordered_map


def _f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def _pow2(n):
    return n & (n - 1) == 0


def _bucket(h, n):
    return h & (n - 1) if _pow2(n) else h % n


def _need(m, address):
    """Refuse before any write when a callee reached later is not lifted."""
    if address - m.main not in FUNCTIONS:
        raise UnliftedCall(f"main+0x{address - m.main:x}")


def _tail(m, address, *args):
    """A tail call: the callee's result, or None when the callee is void."""
    fn = FUNCTIONS.get(address - m.main)
    if fn is None:
        raise UnliftedCall(f"main+0x{address - m.main:x}")
    return fn(m, *args)


def _stores(m, base, items):
    """Store (offset, size, value) items at base."""
    for off, size, value in items:
        m.put(base + off, size, value)


def _vt(m, got):
    """The vtable a constructor stores: the GOT word at main+`got`, +0x10."""
    return m.u64(m.main + got) + 0x10


# --- the thread's allocator-scope stack and owned members -----------------------------------------

def _tls_stack(m):
    """The thread's object stack at the TLS slot [0x4765a30], built on first use (guard 0x4765a38);
    0 when the thread has none."""
    guard = m.main + 0x4765A38
    if m.u8(guard) & 1 == 0 and m.call(m.main + 0x343CF10, guard) & M32:
        m.call_void(m.main + 0xF538C0, m.main + 0x4765A30, m.main + 0x27BF190)
        m.call_void(m.main + 0x190, m.u64(m.main + 0x46D3900), m.main + 0x4765A30, m.main + 0x4383000)
        m.call_void(m.main + 0x343CF20, guard)
    return m.call(m.main + 0x343DA20, m.u32(m.main + 0x4765A30))


def _push(m, stack, owner):
    n = m.u64(stack + 0x80)
    if n >= 0x10:
        raise UnliftedCall("abort: object stack full")
    m.put(stack + 8 * n, 8, owner)
    m.put(stack + 0x80, 8, m.u64(stack + 0x80) + 1)


def _pop(m, stack):
    m.put(stack + 0x80, 8, m.u64(stack + 0x80) - 1)


def _destroy(m, obj, owner, size, align):
    """Delete an owned object: the thread block's depth +0x12c8 raised (its high mark +0x12cc), the
    destructor (vf 0x18), the free through `owner` (vf 0x18, or 0xb48fe8 when vf 0xf8 defers frees),
    the depth lowered; a pending deferred list at +0x12c0 is flushed through 0xb4ea30."""
    tb = m.call(m.main + 0xB4E600)
    d = m.s(tb + 0x12C8, 4)
    m.put(tb + 0x12C8, 4, d + 1)
    if not d < m.s(tb + 0x12CC, 4):
        m.put(tb + 0x12CC, 4, d + 1)
    m.vcall_void(obj, 0x18)
    if m.vcall(owner, 0xF8) & 1 and m.s(m.call(m.main + 0xB4E600) + 0x12C8, 4) >= 1:
        m.call_void(m.main + 0xB48FE8, owner, obj, size, align)
    else:
        m.vcall_void(owner, 0x18, obj, size, align)
    tb = m.call(m.main + 0xB4E600)
    d = (m.u32(tb + 0x12C8) - 1) & M32
    m.put(tb + 0x12C8, 4, d)
    if d == 0:
        if m.u64(m.call(m.main + 0xB4E600) + 0x12C0):
            raise UnliftedCall("deferred frees: main+0xb4ea30")
        m.put(tb + 0x12CC, 4, 0)


def _own(m, holder, owner, size, build, align=8, dtor=0x18, delete=None):
    """holder = {object, owner, size, align}: `size` bytes from `owner` (vf 0x10), built by build(o)
    with `owner` on the thread's object stack; an allocation failure leaves {0, 0, 0, 0}. A previous
    object is destroyed (vf `dtor`, or a call when `dtor` is callable) and freed after the new one is
    stored."""
    o = m.vcall(owner, 0x10, size, align)
    if o:
        stack = _tls_stack(m)
        _push(m, stack, owner)
        build(o)
        _pop(m, stack)
    else:
        owner = size = 0
    old = m.u64(holder)
    m.put(holder, 8, o)
    if old and delete:
        delete(old)
    elif old:
        _free(m, old, m.u64(holder + 8), m.u64(holder + 0x10), m.u64(holder + 0x18),
              (lambda: dtor(old)) if callable(dtor) else dtor)
    m.put(holder + 8, 8, owner); m.put(holder + 0x10, 8, size)
    m.put(holder + 0x18, 8, align if o else 0)
    return o


# --- unordered_map<u16, 0x70-byte value> (node 0x88) ------------------------------------------------

def _do_rehash(m, table, n, align, key):
    """libc++ __do_rehash: n buckets from the allocator at +0x10 (`align`), the old array freed through
    it (0xb48fe8 when it defers frees), the node list (+0x30) relinked; `key` is the key width at
    node +0x10."""
    old = m.u64(table)
    if n == 0:
        m.put(table, 8, 0)
    else:
        arr = m.vcall(m.u64(table + 0x10), 0x10, n * 8, align)
        if not arr:
            raise UnliftedCall("allocator out of memory: vf 0xe8")
        m.put(table, 8, arr)
    if old:
        alloc = m.u64(table + 0x10)
        size = m.u64(table + 8) * 8
        if m.vcall(alloc, 0xF8) & 1 and m.s(m.call(m.main + 0xB4E600) + 0x12C8, 4) >= 1:
            m.call_void(m.main + 0xB48FE8, alloc, old, size, align)
        else:
            m.vcall_void(alloc, 0x18, old, size, align)
    m.put(table + 8, 8, n)
    if n == 0:
        return
    arr = m.u64(table)
    for i in range(n):
        m.put(arr + 8 * i, 8, 0)
    pp = m.u64(table + 0x30)
    if not pp:
        return
    phash = _bucket(m.u64(pp + 8), n)
    m.put(arr + 8 * phash, 8, table + 0x30)
    cp = m.u64(pp)
    while cp:
        chash = _bucket(m.u64(cp + 8), n)
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


def _rehash(m, table, want, do):
    """libc++ rehash(want): grow to want (a prime unless a power of two); shrink only down to what the
    size (+0x58) and max load (+0x60) allow. `do` is the __do_rehash address."""
    if want == 1:
        want = 2
    elif want & (want - 1):
        want = m.call(m.main + 0x343D400, want)
    n = m.u64(table + 8)
    if want > n:
        return m.call_void(m.main + do, table, want)
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
        m.call_void(m.main + do, table, new)


def _find(m, table, key, width):
    n = m.u64(table + 8)
    if n == 0:
        return 0
    b = _bucket(key, n)
    p = m.u64(m.u64(table) + 8 * b)
    if not p:
        return 0
    p = m.u64(p)
    while p:
        h = m.u64(p + 8)
        if h != key and _bucket(h, n) != b:
            return 0
        if m.u(p + 0x10, width) == key:
            return p
        p = m.u64(p)
    return 0


def _insert(m, table, node, key, do):
    """Link a built node for `key` (libc++ __node_insert_unique tail): grow past the max load, then
    put it at its bucket's head."""
    n = m.u64(table + 8)
    size1 = _f32(float(m.u64(table + 0x58) + 1))
    load = struct.unpack("<f", m.read(table + 0x60, 4))[0]
    if n == 0 or _f32(load * _f32(float(n))) < size1:
        grow = (n << 1) | int(n < 3 or not _pow2(n))
        need = math.ceil(_f32(size1 / load))
        _rehash(m, table, max(grow, need), do)
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
            m.put(m.u64(table) + 8 * _bucket(m.u64(nxt + 8), n), 8, node)
    else:
        m.put(node, 8, m.u64(prev))
        m.put(prev, 8, node)
    m.put(table + 0x58, 8, m.u64(table + 0x58) + 1)


@lifted(0x127D27C)
def do_rehash_127d27c(m, table, n, *_):
    """__do_rehash of the u16-keyed map of 0x127c9d4 (bucket arrays aligned 8)."""
    _do_rehash(m, table, n, 8, 2)


@lifted(0x127C9D4)
def map_u16_slot(m, table, key_ptr, *_):
    """operator[] of an unordered_map<u16, 0x70-byte value> (node 0x88): the value (node +0x18) of the
    u16 at key_ptr; a missing key gets a node from the allocator [table+0x38] (pushed on the thread's
    object stack while built): value vtable [0x46e26c0]+0x10, +8 0, u32 +0x10 0xee0000, u16 +0x14 0xee,
    +0x18..+0x70 zero."""
    key = m.u16(key_ptr)
    node = _find(m, table, key, 2)
    if node:
        return node + 0x18
    alloc = m.u64(table + 0x38)
    node = m.vcall(alloc, 0x10, 0x88, 8)
    if not node:
        raise UnliftedCall("allocator out of memory: vf 0xe8")
    owner = m.u64(table + 0x38)
    stack = _tls_stack(m)
    if stack:
        _push(m, stack, owner)
    m.put(node + 0x18, 8, _vt(m, 0x46E26C0)); m.put(node + 0x20, 8, 0)
    m.put(node + 0x28, 4, 0xEE0000)
    m.put(node + 0x10, 2, m.u16(key_ptr)); m.put(node + 0x2C, 2, 0xEE)
    m.write(node + 0x30, bytes(0x58))
    if stack:
        _pop(m, stack)
    m.put(node, 8, 0); m.put(node + 8, 8, key)
    _insert(m, table, node, key, 0x127D27C)
    return node + 0x18


# --- the main module (vtable 0x44ee4a8, 0x378 bytes) --------------------------------------------------

@lifted(0x127F334)
def construct_127f334(m, o, *_):
    """vtable 0x44fc8a8, then 50 entries of 0x18 bytes from +8: vtable [0x46e2730]+0x10, +8 0, u32
    +0x10 k % 5, u8 +0x14 k // 5, u8 +0x15 0, u16 +0x16 0 (+0x18 u32 0 of the next 8 bytes)."""
    m.put(o, 8, m.main + 0x44FC8A8)
    vt = _vt(m, 0x46E2730)
    for k in range(50):
        e = o + 8 + 0x18 * k
        m.put(e, 8, vt); m.put(e + 8, 4, k % 5); m.put(e + 0xC, 1, k // 5)
        m.put(e + 0xD, 1, 0); m.put(e + 0xE, 2, 0); m.put(e + 0x10, 4, 0)
    return o


def _two_maps(m, p, alloc, max_size):
    """Two empty libc++ map headers at +8 and +0x30 (max size `max_size`) sharing `alloc`, max load
    1.0 at +0x68."""
    _stores(m, p, ((0x10, 8, 0), (0x18, 8, alloc), (0x38, 8, 0), (0x40, 8, alloc), (8, 8, 0),
                   (0x20, 8, max_size), (0x28, 8, 0), (0x30, 4, 0), (0x48, 8, max_size), (0x50, 8, 0),
                   (0x58, 4, 0), (0x60, 8, 0), (0x68, 4, ONE_F)))


def _type_map(m, o, owner):
    """The member at +0xd0 (0x78 bytes): a u16 map at +8 holding keys 0..0xed, each value {+8 o,
    u16 +0x10 key, u32 +0x12 0xee00ee, +0x16.. a local's 0x56 bytes (the first two never written)},
    every value then passed to 0x127c86c."""
    m.put(o, 8, _vt(m, 0x46E2618))
    _stores(m, o, ((8, 8, 0), (0x10, 8, 0), (0x18, 8, owner), (0x30, 4, 0), (0x38, 8, 0),
                   (0x40, 8, owner), (0x20, 8, 0x0222222222222222), (0x28, 8, 0),
                   (0x48, 8, 0x0222222222222222), (0x50, 8, 0), (0x58, 4, 0), (0x60, 8, 0),
                   (0x68, 4, ONE_F), (0x70, 4, 0xEE00EE)))
    with m.frame(0x70) as f:
        for i in range(0xEE):
            m.write(f + 2, bytes(0x58))
            m.put(f + 0x60, 2, i)
            v = m.call(m.main + 0x127C9D4, o + 8, f + 0x60)
            m.put(v + 8, 8, o); m.put(v + 0x10, 2, i); m.put(v + 0x12, 4, 0xEE00EE)
            m.write(v + 0x16, m.read(f, 0x56))
    m.put(o + 0x70, 4, 0xEE00EE)
    node = m.u64(o + 0x38)
    while node:
        m.call_void(m.main + 0x127C86C, o, node + 0x18)
        node = m.u64(node)


@lifted(0x12742D0)
def construct_main_module(m, o, a, *_):
    """The main module's constructor: a = {+0 allocator, +8 N, ...}. 27 members, each allocated from
    [a] with it on the thread's object stack and held as {object, owner, size, 8}; ends with
    0x127d824(o, a) and returns its result."""
    alloc = m.u64(a)
    m.put(o, 8, m.main + 0x44EE4A8)
    m.put(o + 0x36B, 1, 0); m.put(o + 0x36C, 4, 0); m.put(o + 0x370, 1, 0)
    m.write(o + 8, bytes(0x35D))

    def rng(p):
        m.put(p, 8, _vt(m, 0x46DCD38)); m.put(p + 8, 8, 0x0F4B17A579F18960)
        m.put(p + 0x10, 8, 0x82A2B175229D6A5B); m.put(p + 0x18, 8, 0); m.put(p + 0x20, 8, 0)
    _own(m, o + 0x10, alloc, 0x28, rng)

    with m.frame(0x10) as f:
        x = m.call(m.main + 0x127D65C, f, m.u64(a))
    if x:
        c = m.u32(x + 0x28)
        if c == M32:
            raise UnliftedCall("abort: reference counter overflows")
        m.put(x + 0x28, 4, c + 1)
    old = m.u64(o + 8)
    m.put(o + 8, 8, 0)
    if old:
        raise UnliftedCall("release of a held reference")
    m.put(o + 8, 8, x)

    def blank(got, size):
        def build(p):
            m.put(p, 8, _vt(m, got))
            m.write(p + 8, bytes(size))
        return build

    def timer(p):
        blank(0x46E2600, 0x420)(p)
        m.call_void(m.main + 0x127DCB8, p)
    _own(m, o + 0x70, m.u64(a), 0x428, timer)

    def container(p):
        x9, x10, x11 = m.u64(a), m.u64(a + 8), m.u64(a + 0x18)
        big = 0x0FFFFFFFFFFFFFFF
        _stores(m, p, ((0x30, 8, 0), (0x38, 8, 0), (0x40, 8, 0), (0x48, 8, 0), (0x50, 8, 0),
                       (0x10, 8, x10), (0x18, 8, o), (0x20, 8, x11), (0x28, 8, 0),
                       (0x58, 1, 0), (0x90, 1, 0), (0xC8, 1, 0), (0x100, 1, 0), (0x138, 1, 0),
                       (0x160, 8, 0), (0x168, 4, 0), (0x190, 4, 0), (0x198, 8, 0),
                       (0xB8, 8, 0), (0xC0, 8, 0), (0xA8, 8, 0), (0xB0, 8, 0),
                       (0, 8, _vt(m, 0x46E2608)), (8, 8, x9), (0x150, 8, x9), (0x158, 8, big),
                       (0x180, 8, big), (0x188, 8, 0), (0x1A0, 4, ONE_F)))
        for off in (0x60, 0x70, 0x80, 0x98, 0xD0, 0xE0, 0xF0, 0x108, 0x118, 0x128, 0x140):
            m.put(p + off, 8, 0); m.put(p + off + 8, 8, 0)
        m.put(p + 0x170, 8, 0); m.put(p + 0x178, 8, x9)
    _own(m, o + 0x30, m.u64(a), 0x1A8, container)

    def maps(got, max_size, tail):
        def build(p):
            _two_maps(m, p, m.u64(a), max_size)
            m.put(p, 8, _vt(m, got))
            if tail:
                m.put(p + 0x70, tail, 0)
        return build
    _own(m, o + 0x50, m.u64(a), 0x78, maps(0x46E2610, 0x1555555555555555, 4))
    _own(m, o + 0x90, m.u64(a), 0x5F8, lambda p: m.call_void(m.main + 0x127EFC0, p))
    _own(m, o + 0xB0, m.u64(a), 0x4B8, lambda p: m.call_void(m.main + 0x127F334, p))
    _own(m, o + 0xD0, m.u64(a), 0x78, lambda p: _type_map(m, p, m.u64(a)))
    _own(m, o + 0xF0, m.u64(a), 0xC8, lambda p: m.call_void(m.main + 0x127D5CC, p, m.u64(a)))

    def turn(p):
        x9 = m.u64(a)
        m.put(p, 8, _vt(m, 0x46E2620))
        _stores(m, p, ((0x330, 8, 0x1FFFFFFFFFFFFFFF), (0x308, 8, 0x1FFFFFFFFFFFFFFF), (0x2F0, 8, 0),
                       (0x2F8, 8, 0), (0x310, 8, 0), (0x318, 4, 0), (0x320, 8, 0), (0x340, 4, 0),
                       (0x348, 8, 0), (0x358, 8, o), (0x350, 4, ONE_F), (0x300, 8, x9),
                       (0x328, 8, x9), (0x338, 8, 0)))
        m.write(p + 8, bytes(0x2E4))
    _own(m, o + 0x110, m.u64(a), 0x360, turn)
    _own(m, o + 0x130, m.u64(a), 0x12D0, blank(0x46E2628, 0x12C4))

    def small(got, items):
        def build(p):
            m.put(p, 8, _vt(m, got))
            _stores(m, p, items)
        return build
    _own(m, o + 0x150, m.u64(a), 0x18, small(0x46E2630, ((0x10, 4, 0), (8, 8, 0))))
    _own(m, o + 0x170, m.u64(a), 0x78, maps(0x46E2638, 0x1555555555555555, 1))
    _own(m, o + 0x190, m.u64(a), 0x10, small(0x46E2640, ((8, 4, 0),)))
    _own(m, o + 0x1B0, m.u64(a), 0x18, small(0x46E2648, ((0x10, 4, 0), (8, 8, 0))))
    _own(m, o + 0x1D0, m.u64(a), 0x58, lambda p: small(0x46E2650, (
        (8, 8, 0), (0x40, 4, 0), (0x50, 8, o), (0x48, 1, 0), (0x10, 8, 0), (0x18, 8, 0), (0x20, 8, 0),
        (0x28, 8, m.u64(a)), (0x30, 8, M64), (0x38, 8, 0)))(p))
    _own(m, o + 0x1F0, m.u64(a), 0x10, small(0x46E2658, ((8, 1, 0),)))
    _own(m, o + 0x210, m.u64(a), 0xE0, blank(0x46E2660, 0xD8))
    _own(m, o + 0x230, m.u64(a), 0x18, small(0x46E2668, (
        (0x13, 1, 0), (0x11, 2, 0), (8, 8, 0x0505050500000000), (0x10, 1, 5))))
    first = m.u64(o + 0x30)

    def entries(p):
        m.put(p, 8, _vt(m, 0x46E2670)); m.put(p + 8, 8, first)
        m.call_void(m.main + 0x127E0C8, p)
    _own(m, o + 0x250, m.u64(a), 0x1F0, entries)
    _own(m, o + 0x270, m.u64(a), 0x18, lambda p: small(0x46E2678, (
        (8, 8, 0), (0x10, 8, m.u64(a + 8))))(p))
    _own(m, o + 0x290, m.u64(a), 0x18, lambda p: small(0x46E2680, (
        (8, 8, o), (0x10, 8, m.u64(a + 8))))(p))
    _own(m, o + 0x2B0, m.u64(a), 0x70, maps(0x46E2688, 0x1555555555555555, 0))

    def flags(p):
        x9 = 0xFFFF0100FFFF0100
        m.put(p + 0x10, 8, x9); m.put(p, 8, _vt(m, 0x46E2690)); m.put(p + 8, 8, x9)
        m.put(p + 0x18, 4, 0xFFFF0100)
    _own(m, o + 0x2D0, m.u64(a), 0x20, flags)
    _own(m, o + 0x2F0, m.u64(a), 0x70, maps(0x46E2698, 0x0CCCCCCCCCCCCCCC, 0))

    def raid(p):
        m.put(p, 8, _vt(m, 0x46E26A0)); m.put(p + 8, 8, m.u64(a + 8)); m.put(p + 0x10, 8, o)
        m.write(p + 0x18, bytes(0x4E))
        _stores(m, p, ((0x68, 8, 0), (0x70, 8, 0), (0x88, 8, 0), (0x90, 4, 0), (0x78, 8, 0),
                       (0x80, 8, 0)))
    _own(m, o + 0x310, m.u64(a), 0x98, raid)

    def link(p):
        m.put(p + 0x18, 8, m.u64(a)); m.put(p, 8, m.u64(a + 8)); m.put(p + 8, 8, o)
    _own(m, o + 0x330, m.u64(a), 0x20, link)
    return m.call(m.main + 0x127D824, o, a)


# --- the server construction ----------------------------------------------------------------------

def _acquire(m, ref):
    """AddReference on the handle [ref+0x30]: u16 count +0x1a raised; the first reference resolves vf 0
    of [+0x10] into +8 and marks u32 +0x1c -2."""
    c = m.u64(ref + 0x30)
    if m.u64(c + 0x10) == 0:
        raise UnliftedCall("abort: m_object != nullptr")
    n = m.u16(c + 0x1A)
    m.put(c + 0x1A, 2, n + 1)
    if n == 0:
        x = m.u64(c + 0x10)
        m.put(c + 8, 8, m.call(m.u64(m.u64(x)), x))
        m.put(c + 0x1C, 4, 0xFFFFFFFE)
    elif n == 0xFFFF:
        raise UnliftedCall("abort: reference counter overflows")


def _release(m, ref):
    """ReleaseReference on [ref+0x30]: the last one clears +0x10 and calls ref's vf 0x50."""
    c = m.u64(ref + 0x30)
    n = m.u16(c + 0x1A)
    m.put(c + 0x1A, 2, n - 1)
    if n == 1:
        m.put(c + 0x10, 8, 0)
        m.vcall_void(ref, 0x50)
    elif n == 0:
        raise UnliftedCall("abort: reference counter underflows")


@lifted(0x2891748)
def build_server(m, n, alloc, *_):
    """Build the battle server's two main modules (0x378 bytes each, constructor 0x12742d0) from
    `alloc` into N+0x170 and N+0x150, each held as {object, alloc, 0x378, 8}, then reset both with
    0x127d824 (N+0x150 first). The constructors read a = {alloc, N, u32 setup+0x34, u8 setup+0x8d,
    the setup's handle, setup+0x718 the seed}."""
    with m.frame(0x30) as a:
        setup = m.u64(n + 0x38)
        m.put(a, 8, alloc); m.put(a + 8, 8, n)
        m.put(a + 0x10, 4, m.u32(setup + 0x34)); m.put(a + 0x14, 1, m.u8(setup + 0x8D))
        m.put(a + 0x18, 8, 0); m.put(a + 0x20, 8, m.u64(setup + 0x718))
        ref = m.u64(m.u64(n + 0x48) + 0x130)
        if ref:
            _acquire(m, ref)
            m.put(a + 0x18, 8, ref)
            _release(m, ref)
        else:
            m.put(a + 0x18, 8, 0)
        for off in (0x170, 0x150):
            o = m.vcall(alloc, 0x10, 0x378, 8)
            if o:
                stack = _tls_stack(m)
                _push(m, stack, alloc)
                m.call(m.main + 0x12742D0, o, a)
                _pop(m, stack)
            old = m.u64(n + off)
            m.put(n + off, 8, o)
            if old:
                _destroy(m, old, m.u64(n + off + 8), m.u64(n + off + 0x10), m.u64(n + off + 0x18))
            if o:
                m.put(n + off + 8, 8, alloc); m.put(n + off + 0x10, 8, 0x378)
            else:
                m.put(n + off + 8, 8, 0); m.put(n + off + 0x10, 8, 0)
            m.put(n + off + 0x18, 8, 8 if o else 0)
        m.call(m.main + 0x127D824, m.u64(n + 0x150), a)
        return m.call(m.main + 0x127D824, m.u64(n + 0x170), a)


# --- step 3 ---------------------------------------------------------------------------------------

@lifted(0x2892DD4)
def step_3(m, n, *_):
    """Choose N's next phase: with the election object [N+0x138] held (two references while its vf
    0x68 runs), a true vf 0x68 sets bit 0 of N+0x9e; otherwise N+0x68 = {0x2d383b8 when 0xfa363c(N),
    else 0x2893004 when setup+0x710 is set, else 0x28932a4; 0}. Returns 1."""
    r = m.u64(n + 0x138)
    if r:
        _acquire(m, r)
        r2 = m.u64(n + 0x138)
        if r2:
            _acquire(m, r2)
        done = m.vcall(r2, 0x68) & 1
        if r2:
            _release(m, r2)
        _release(m, r)
        if done:
            m.put(n + 0x9E, 1, m.u8(n + 0x9E) | 1)
            return 1
    if m.call(m.main + 0xFA363C, n) & 1:
        nxt = 0x2D383B8
    elif m.u8(m.u64(n + 0x38) + 0x710):
        nxt = 0x2893004
    else:
        nxt = 0x28932A4
    m.put(n + 0x68, 8, m.main + nxt); m.put(n + 0x70, 8, 0)
    return 1


# --- step 1: the battlers ---------------------------------------------------------------------------

def _tls_top(m):
    """The last entry of the thread's object stack, or 0 (the owner a base constructor stores at +8)."""
    s = _tls_stack(m)
    if not s:
        return 0
    n = m.u64(s + 0x80)
    return m.u64(s + 8 * n - 8) if n else 0


def _inc(m, p):
    """IncrementReferenceInternal: the u32 count at p+0x28."""
    c = m.u32(p + 0x28)
    if c == M32:
        raise UnliftedCall("abort: reference counter overflows")
    m.put(p + 0x28, 4, c + 1)


def _dec(m, p):
    """DecrementReferenceInternal: the u32 count at p+0x28; the last one deletes p (vf 0x10)."""
    c = m.u32(p + 0x28)
    m.put(p + 0x28, 4, c - 1)
    if c == 1:
        m.vcall_void(p, 0x10)
    elif c == 0:
        raise UnliftedCall("abort: reference counter underflows")


def _free(m, p, owner, size, align, dtor=None, obj=None):
    """_destroy without a destructor when `dtor` is None, else with vf `dtor` of `obj` (default p)."""
    if dtor is not None and not callable(dtor):
        _need(m, m.u64(m.u64(p if obj is None else obj) + dtor))
    tb = m.call(m.main + 0xB4E600)
    d = m.s(tb + 0x12C8, 4)
    m.put(tb + 0x12C8, 4, d + 1)
    if not d < m.s(tb + 0x12CC, 4):
        m.put(tb + 0x12CC, 4, d + 1)
    if callable(dtor):
        dtor()
    elif dtor is not None:
        m.vcall_void(p if obj is None else obj, dtor)
    if m.vcall(owner, 0xF8) & 1 and m.s(m.call(m.main + 0xB4E600) + 0x12C8, 4) >= 1:
        m.call_void(m.main + 0xB48FE8, owner, p, size, align)
    else:
        m.vcall_void(owner, 0x18, p, size, align)
    tb = m.call(m.main + 0xB4E600)
    d = (m.u32(tb + 0x12C8) - 1) & M32
    m.put(tb + 0x12C8, 4, d)
    if d == 0:
        if m.u64(m.call(m.main + 0xB4E600) + 0x12C0):
            raise UnliftedCall("deferred frees: main+0xb4ea30")
        m.put(tb + 0x12CC, 4, 0)


def _slot(m, table, key_ptr, node_size, align, value, init, do):
    """unordered_map<u32, ...>::operator[]: node+`value` for the u32 at key_ptr; a missing key gets a
    node (`node_size`, `align`) from the allocator [table+0x38], filled by init(node) with that
    allocator on the thread's object stack."""
    key = m.u32(key_ptr)
    node = _find(m, table, key, 4)
    if node:
        return node + value
    node = m.vcall(m.u64(table + 0x38), 0x10, node_size, align)
    if not node:
        raise UnliftedCall("allocator out of memory: vf 0xe8")
    owner = m.u64(table + 0x38)
    stack = _tls_stack(m)
    if stack:
        _push(m, stack, owner)
    m.put(node + 0x10, 4, m.u32(key_ptr))
    init(node)
    if stack:
        _pop(m, stack)
    m.put(node, 8, 0); m.put(node + 8, 8, key)
    _insert(m, table, node, key, do)
    return node + value


@lifted(0xF7BB84)
def do_rehash_f7bb84(m, table, n, *_):
    """__do_rehash of 0xf78064's map (bucket arrays aligned 4)."""
    _do_rehash(m, table, n, 4, 4)


@lifted(0xFA2678)
def do_rehash_fa2678(m, table, n, *_):
    """__do_rehash of 0xfa1b68's map (bucket arrays aligned 8)."""
    _do_rehash(m, table, n, 8, 4)


@lifted(0xF78064)
def slot_f78064(m, table, key_ptr, *_):
    """operator[] of an unordered_map<u32, 8 bytes> (node 0x20, align 4, value +0x14 zeroed)."""
    return _slot(m, table, key_ptr, 0x20, 4, 0x14, lambda n: m.put(n + 0x14, 8, 0), 0xF7BB84)


@lifted(0xFA1B68)
def slot_fa1b68(m, table, key_ptr, *_):
    """operator[] of an unordered_map<u32, u64> (node 0x20, align 8, value +0x18 zeroed)."""
    return _slot(m, table, key_ptr, 0x20, 8, 0x18, lambda n: m.put(n + 0x18, 8, 0), 0xFA2678)


@lifted(0xEF306C)
def make_core_buffer(m, alloc, *_):
    """*x8 = {0x148 zero bytes from alloc (align 4, alloc on the thread's object stack), alloc,
    0x148, 4}, or four zeros; returns memset's result on the buffer."""
    out = m.x8
    buf = m.vcall(alloc, 0x10, 0x148, 4)
    if not buf:
        _stores(m, out, ((0x10, 8, 0), (0x18, 8, 0), (0, 8, 0), (8, 8, 0)))
        raise UnliftedCall("memset of a null buffer")
    stack = _tls_stack(m)
    _push(m, stack, alloc)
    m.write(buf, bytes(0x148))
    _stores(m, out, ((0, 8, buf), (8, 8, alloc), (0x10, 8, 0x148), (0x18, 8, 4)))
    _pop(m, stack)
    return m.call(m.main + 0x343C220, m.u64(out), 0, 0x148)


@lifted(0xEF2448)
def make_party_buffer(m, alloc, seed, *_):
    """*x8 = {0x10 bytes from alloc (align 2), alloc, 0x10, 2}, the eight u16 high halves of the
    GBA-style LCG (0x41c64e6d, 0x6073) run from `seed`."""
    out = m.x8
    buf = m.vcall(alloc, 0x10, 0x10, 2)
    if not buf:
        _stores(m, out, ((0x10, 8, 0), (0x18, 8, 0), (0, 8, 0), (8, 8, 0)))
        raise UnliftedCall("party buffer at address 0")
    stack = _tls_stack(m)
    _push(m, stack, alloc)
    m.put(buf, 8, 0); m.put(buf + 8, 8, 0)
    _stores(m, out, ((0, 8, buf), (8, 8, alloc), (0x10, 8, 0x10), (0x18, 8, 2)))
    _pop(m, stack)
    s = seed & M32
    for k in range(8):
        s = (s * 0x41C64E6D + 0x6073) & M32
        m.put(buf + 2 * k, 2, s >> 16)
    return stack


def _take(m, holder, out, dtor=None):
    """holder (+0 object, +8 owner, +0x10 size, +0x18 align) takes the four words at out; a previous
    object is freed (with vf `dtor` first when given)."""
    p = m.u64(out)
    m.put(out, 8, 0)
    old = m.u64(holder)
    m.put(holder, 8, p)
    if old:
        _free(m, old, m.u64(holder + 8), m.u64(holder + 0x10), m.u64(holder + 0x18), dtor)
    m.put(holder + 8, 8, m.u64(out + 8)); m.put(holder + 0x10, 8, m.u64(out + 0x10))
    m.put(holder + 0x18, 8, m.u64(out + 0x18))


@lifted(0xEF2020)
def make_party_record(m, o, alloc, *_):
    """The 0x10-byte party record at +0x50 (holder +0x50..+0x68), scrambled from the core record's
    first u32 ([[o+0x70]+0x10]), then bound in the accessor [o+0x70]: +8 it, +0x10 [o+0x30], u16
    +0x18 1."""
    acc = m.u64(o + 0x70)
    with m.frame(0x20) as out:
        m.x8 = out
        r = m.call(m.main + 0xEF2448, alloc, m.u32(m.u64(acc + 0x10)))
        _take(m, o + 0x50, out)
    acc = m.u64(o + 0x70)
    m.put(acc + 8, 8, m.u64(o + 0x50)); m.put(acc + 0x10, 8, m.u64(o + 0x30))
    m.put(acc + 0x18, 2, 1)
    return r


@lifted(0xEF25C4)
def construct_ef25c4(m, o, *_):
    """A Pokemon record (vtables 0x44a9218 / 0x44a9258): +8 the thread's current owner, a zeroed
    0x148-byte core record held at +0x30, an accessor (0x38 bytes, vtable [0x46dda98], a light event
    at +0x28) held at +0x70, bound to the core record by 0xef2f38."""
    m.put(o + 0x10, 8, 0); m.put(o + 0x18, 4, 0)
    m.put(o, 8, _vt(m, 0x46D66F8))
    top = _tls_top(m)
    m.put(o + 0x28, 4, 0)
    m.put(o, 8, m.main + 0x44A9218); m.put(o + 8, 8, top)
    m.put(o + 0x20, 8, m.main + 0x44A9258)
    m.write(o + 0x30, bytes(0x60))
    with m.frame(0x20) as out:
        m.x8 = out
        m.call_void(m.main + 0xEF306C, top)
        _take(m, o + 0x30, out)
    alloc = m.u64(o + 8)
    acc = m.vcall(alloc, 0x10, 0x38, 8)
    if acc:
        stack = _tls_stack(m)
        _push(m, stack, alloc)
        _stores(m, acc, ((0x20, 8, 0), (0x10, 8, 0), (0x18, 4, 0), (0, 8, _vt(m, 0x46DDA98)), (8, 8, 0),
                         (0x34, 4, 1)))
        m.call_void(m.main + 0x343E6D0, acc + 0x28, 0, 1)
        m.put(acc + 0x18, 2, 0)
        _pop(m, stack)
    else:
        alloc = 0
    old = m.u64(o + 0x70)
    m.put(o + 0x70, 8, acc)
    if old:
        _free(m, old, m.u64(o + 0x78), m.u64(o + 0x80), m.u64(o + 0x88), 0)
    m.put(o + 0x78, 8, alloc); m.put(o + 0x80, 8, 0x38 if acc else 0)
    m.put(o + 0x88, 8, 8 if acc else 0)
    return m.call(m.main + 0xEF2F38, acc, m.u64(o + 0x30), 0)


def _create(m, alloc, size, build):
    """A `size`-byte object from alloc (align 8) with alloc on the thread's object stack: build(o),
    then u32 +0x18 size | 0x80000, +8 alloc, +0x10 itself."""
    stack = _tls_stack(m)
    _push(m, stack, alloc)
    o = m.vcall(alloc, 0x10, size, 8)
    if not o:
        raise UnliftedCall("abort: allocation failed in Create")
    build(o)
    m.put(o + 0x18, 4, 0x80000 | size)
    m.put(o + 8, 8, alloc); m.put(o + 0x10, 8, o)
    _pop(m, stack)
    return o


@lifted(0xEEE8FC)
def create_eee8fc(m, _x0, alloc, *_):
    """Create the 0x90-byte Pokemon record: 0xef25c4, vtable [0x46d69c0] (+0x10 / +0x50 at +0 /
    +0x20), its party record made from [o+8] (0xef2020)."""
    def build(o):
        m.call_void(m.main + 0xEF25C4, o)
        vt = m.u64(m.main + 0x46D69C0)
        m.put(o, 8, vt + 0x10); m.put(o + 0x20, 8, vt + 0x50)
        m.call_void(m.main + 0xEF2020, o, m.u64(o + 8))
    return _create(m, alloc, 0x90, build)


@lifted(0xEEE70C)
def construct_eee70c(m, o, src, *_):
    """The 0x50-byte Pokemon parameter object (vtable [0x46dcdc0], +0x208 / +0x258 / +0x2b0 at +0x20,
    +0x28, +0x40): a weak handle to itself at +0x30 (0xc1a3f4), a new record (0xeee8fc from [o+8])
    held at +0x48 with a reference, then src's core record copied in (0xeeea48)."""
    _weak_base(m, o)
    vt = m.u64(m.main + 0x46DCDC0)
    m.put(o, 8, vt + 0x10); m.put(o + 0x20, 8, vt + 0x208); m.put(o + 0x28, 8, vt + 0x258)
    m.put(o + 0x40, 8, vt + 0x2B0); m.put(o + 0x48, 8, 0)
    with m.frame(0x10) as f:
        r = m.call(m.main + 0xEEE8FC, f, m.u64(o + 8))
    if r:
        _inc(m, r)
    old = m.u64(o + 0x48)
    m.put(o + 0x48, 8, 0)
    if old:
        _dec(m, old)
    m.put(o + 0x48, 8, r)
    return _tail(m, m.main + 0xEEEA48, r, src)


@lifted(0xEEE5DC)
def create_eee5dc(m, _x0, alloc, src, *_):
    """Create a 0x50-byte Pokemon parameter object copying src (0xeee70c)."""
    return _create(m, alloc, 0x50, lambda o: m.call_void(m.main + 0xEEE70C, o, src))


@lifted(0xEEE500)
def clone_param(m, o, *_):
    """vf 0x198 of a Pokemon parameter object: *x8 = a new one copying [o+0x48] from the allocator
    [o+8], with a weak reference added. Returns it."""
    out = m.x8
    with m.frame(0x10) as f:
        r = m.call(m.main + 0xEEE5DC, f, m.u64(o + 8), m.u64(o + 0x48))
    if r:
        _acquire(m, r)
    m.put(out, 8, r)
    return r


@lifted(0xFA0F48)
def copy_party(m, dst, src, *_):
    """dst's u8 count +0x60 and its parameter objects +0x30.. each cloned from src's (vf 0x198); a
    replaced one loses its weak reference."""
    n = m.u8(src + 0x60)
    m.put(dst + 0x60, 1, n)
    k = 0
    with m.frame(0x10) as f:
        while k < m.u8(dst + 0x60) if n else False:
            p = m.u64(src + 0x30 + 8 * k)
            m.x8 = f
            m.vcall_void(p, 0x198)
            slot = dst + 0x30 + 8 * k
            old = m.u64(slot)
            m.put(slot, 8, 0)
            if old:
                _release(m, old)
            m.put(slot, 8, m.u64(f))
            k += 1


@lifted(0xFA0D38)
def create_holder(m, _x0, alloc, *_):
    """Create a 0x68-byte party holder (0xfa0e60)."""
    return _create(m, alloc, 0x68, lambda o: m.call_void(m.main + 0xFA0E60, o, 8, 8))


def _vtail(m, obj, slot, *args):
    return _tail(m, m.u64(m.u64(obj) + slot), obj, *args)


@lifted(0x147FE00)
def init_battler(m, b, s, *_):
    """Fill a battler from s = {+0 / +8 the main module's +8 / +0x10, +0x10 the party parameter
    object, u32 +0x18 its id, +0x1c.. the participant's 0x1a bytes}: a clone of the parameter object
    at +0x48, the stats and flags its virtuals report, the participant fields at +0x3e0..+0x3fa, HP
    scaled by u16 +0x3f4 / 10 when that is not 10, cleared stages and counters; ends with the
    parameter object's vf 0x1a8."""
    p0 = m.u64(s + 0x10)
    with m.frame(0x10) as f:
        m.x8 = f
        m.vcall_void(p0, 0x198)
        old = m.u64(b + 0x48)
        m.put(b + 0x48, 8, 0)
        if old:
            _release(m, old)
        m.put(b + 0x48, 8, m.u64(f))
    p = lambda: m.u64(b + 0x48)
    first = m.vcall(p(), 0x1A0)
    m.put(b + 0x50, 4, m.u32(s + 0x18))
    m.put(b + 0x5A, 2, m.vcall(p(), 0x80))
    m.put(b + 0x58, 2, m.vcall(p(), 0x78))
    m.put(b + 0x3E0, 4, m.u32(s + 0x1C))
    for k in range(5):
        m.put(b + 0x3E4 + k, 1, m.u8(s + 0x20 + k))
    w9 = m.u16(s + 0x26)
    w10, w11, w12, w13, w14 = (m.u8(s + 0x28 + k) for k in range(5))
    m.put(b + 0x3EA, 2, w9)
    m.put(b + 0x3EC, 1, w10); m.put(b + 0x3ED, 1, w11); m.put(b + 0x3EE, 1, w12); m.put(b + 0x3EF, 1, w13)
    m.put(b + 0x3F4, 2, w9); m.put(b + 0x3F6, 1, w10); m.put(b + 0x3F0, 1, w14); m.put(b + 0x3F7, 1, w11)
    m.put(b + 0x3F8, 1, w12); m.put(b + 0x3F9, 1, w13); m.put(b + 0x3FA, 1, w14)
    m.call_void(m.main + 0x14806D0, b, b + 0x3E0)
    if m.u16(b + 0x3F4) != 10:
        hp = m.vcall(b, 0x108) & M32
        cur = m.vcall(b, 0x110) & M32
        top = ((m.vcall(p(), 0x70, 0) & 0xFFFF) * m.u16(b + 0x3F4) & M32) * 0xCCCCCCCD >> 35
        m.put(b + 0x58, 2, top)
        if cur & 0xFFFF < top & 0xFFFF:
            m.vcall_void(b, 0x2E8, (top - cur) & M32)
        elif cur & 0xFFFF > top & 0xFFFF and hp & 0xFFFF > top & 0xFFFF:
            m.vcall_void(b, 0x2E0, (hp - top) & M32)
    v = m.vcall(p(), 0x160)
    m.put(b + 0x5C, 2, v)
    holder = m.u64(m.u64(b + 0x708) + 0x190)
    if holder:
        _inc(m, holder)
    blocked = m.vcall(holder, 0x58, v)
    if holder:
        _dec(m, holder)
    if blocked & 1:
        m.put(b + 0x5C, 2, 0)
    m.put(b + 0x5E, 2, 0); m.put(b + 0x6C, 2, 0); m.put(b + 0x72, 2, 0); m.put(b + 0x74, 4, 0)
    m.put(b + 0x6E, 1, 0)
    m.put(b + 0x65, 1, m.vcall(p(), 0x138))
    for k in range(6):
        m.put(b + 0x66 + k, 1, m.vcall(p(), 0xD8, k))
    m.put(b + 0x60, 2, m.vcall(p(), 0x140))
    m.put(b + 0x62, 1, m.vcall(p(), 0xB0))
    m.put(b + 0x63, 1, m.vcall(p(), 0xD0, 1))
    m.put(b + 0x64, 1, m.vcall(p(), 0xD0, 5))
    m.put(b + 0x7D, 1, 0); m.put(b + 0x6F, 1, 0)
    m.put(b + 0x70, 1, m.u8(s + 0x31)); m.put(b + 0x71, 1, m.u8(s + 0x32))
    m.put(b + 0x3FC, 2, m.u16(s + 0x34))
    m.vcall_void(b, 0x488, 5)
    pp = p()
    m.put(b + 0x41C, 2, 0)
    for k, off in enumerate((0x41E, 0x41F, 0x420, 0x422, 0x423, 0x421)):
        v = m.vcall(pp, 0xE0, k)
        m.put(b + off, 1, v)
        m.put(b + 0x41C, 2, m.u16(b + 0x41C) + (v & 0xFF))
    m.put(b + 0x424, 1, 0)
    m.vcall_void(b, 0x7F0, 0, 1, 1, 1)
    m.put(b + 0x482, 1, m.vcall(b, 0x800, pp, 1))
    m.put(b + 0x485, 1, 0)
    for off in range(0x414, 0x41B):
        if m.u8(b + off) != 6:
            m.put(b + off, 1, 6)
    for off in range(0x88, 0x380, 0x10):
        m.put(b + off, 8, 0)
    m.put(b + 0x3C0, 1, 0)
    for off in range(0x3B8, 0x380, -8):
        m.put(b + off, 8, 0)
    moves = m.vcall(p(), 0xA0)
    if moves & 0xFFFF:
        e = m.call(m.main + 0xE7ECD0, m.u64(b + 0x708))
        ref = m.u64(e + 0x148)
        if ref:
            _acquire(m, ref)
            _release(m, ref)
        party = m.u64(s)
        n = m.vcall(b, 0x98)
        r = m.call(m.main + 0x1480A6C, party, moves & M32, n & M32, m.u64(s + 8), ref)
        i = moves & 0xFFFF
        m.put(b + 0x80 + 16 * i, 8, r[0]); m.put(b + 0x88 + 16 * i, 8, r[1])
        m.put(b + 0x390 + i, 1, 0)
    m.put(b + 0x48A, 4, 0x2710); m.put(b + 0x488, 2, 0); m.put(b + 0x6F2, 4, 0)
    m.put(b + 0x48E, 1, 0); m.put(b + 0x490, 4, 0); m.put(b + 0x486, 1, 0x12); m.put(b + 0x6F8, 4, 0)
    m.put(b + 0x484, 1, 0)
    m.put(b + 0x483, 1, m.vcall(p(), 0x150))
    m.put(b + 0x487, 1, 1); m.put(b + 0x496, 4, 0)
    m.call_void(m.main + 0x14807D0, b)
    m.put(b + 0x49E, 2, 0); m.put(b + 0x3C1, 1, 0)
    m.write(b + 0x5A0, bytes(0x151))
    return _vtail(m, p(), 0x1A8, first & 1)


@lifted(0x147FCD4)
def init_battler_vf68(m, b, s, *_):
    """vf 0x68 of a battler: 0x147fe00, then when the parameter object's sub-object +0x28 (vf 0)
    reaches the static [0x46dcd58] through its list: species / form at +0x710 / +0x712, +0x714 0,
    +0x715 the type (0xfca6e8, 0xd9782c when 0x13, 0 when 0x13 again) and vf 0x1a8."""
    m.call_void(m.main + 0x147FE00, b, s)
    sub = m.u64(b + 0x48) + 0x28
    r = m.call(m.u64(m.u64(sub)), sub)
    guard = m.u64(m.main + 0x46DCD50)
    if not m.u8(guard) & 1:
        raise UnliftedCall("static 0x46dcd58 not built: main+0x19f5520")
    want = m.u64(m.main + 0x46DCD58)
    while r and r != want:
        r = m.u64(r)
    if not r:
        return 0
    p = m.u64(b + 0x48)
    first = m.vcall(p, 0x1A0)
    m.put(b + 0x710, 2, m.call(m.main + 0xBF44F4, m.u64(m.u64(p + 0x48) + 0x70)))
    m.put(b + 0x712, 2, m.call(m.main + 0xBF41A8, m.u64(m.u64(p + 0x48) + 0x70)))
    m.put(b + 0x714, 1, 0)
    rec = m.u64(p + 0x48)
    t = m.call(m.main + 0xFCA6E8, m.u64(rec + 0x70))
    if t & 0xFF == 0x13:
        t = m.call(m.main + 0xD9782C, m.u64(rec + 0x70))
    else:
        t = m.call(m.main + 0xFCA6E8, m.u64(rec + 0x70))
    m.put(b + 0x715, 1, 0 if t & 0xFF == 0x13 else t)
    return _vtail(m, p, 0x1A8, first & 1)


BATTLER_HASH = 0xAA4611A011782F5A    # vf 0x68 of a party parameter object that makes a plain battler


@lifted(0xFA1584)
def add_party_battlers(m, c, side, href, part, *_):
    """For each parameter object of the holder *href: a new id (u32 [[c+0x18]+0x50]+0x70 counted up,
    mapped to {side, k} in that object's map), a battler made from it (0xfa19f8 for the plain kind,
    else [c+0x20] vf 0x68) held with a weak reference in the map at c+0x140, filled by its vf 0x68 from
    the participant entry part + 0x1c*k, and pushed on the side (0xfa1f30). Then 0xfa29d0 and the
    side's members whose vf 0x208 is false moved to the end of its list (c + 0x38*side + 0x28,
    count +0x58)."""
    side8 = side & 0xFF
    n = m.u8(m.u64(href) + 0x60)
    with m.frame(0x60) as f:
        key, handle, s = f, f + 8, f + 0x10
        for k in range(n):
            ids = m.u64(m.u64(c + 0x18) + 0x50)
            v = (m.u32(ids + 0x70) + 1) & M32
            m.put(ids + 0x70, 4, v)
            m.put(key, 4, v)
            r = m.call(m.main + 0xF78064, ids + 8, key)
            m.put(r, 4, side8); m.put(r + 4, 1, k)
            ident = m.u32(key)
            param = m.u64(m.u64(href) + 0x30 + 8 * k)
            h = m.vcall(param, 0x68)
            if h == BATTLER_HASH:
                m.put(s, 8, m.u64(m.u64(c + 0x18) + 0x70))
                x = m.call(m.main + 0xFA19F8, m.u64(c + 8), s, c + 0x10)
                if x:
                    _acquire(m, x)
                m.put(handle, 8, x)
            else:
                maker = m.u64(c + 0x20)
                if maker:
                    m.x8 = handle
                    m.vcall_void(maker, 0x68, h, m.u64(m.u64(c + 0x18) + 0x70), m.u64(c + 0x10))
                else:
                    m.put(handle, 8, 0)
            m.put(key, 4, ident)
            slot = m.call(m.main + 0xFA1B68, c + 0x140, key)
            old = m.u64(slot)
            m.put(slot, 8, 0)
            if old:
                _release(m, old)
            m.put(slot, 8, m.u64(handle))
            m.put(handle, 8, 0)
            b = m.u64(m.call(m.main + 0xFA1B68, c + 0x140, key))
            top = m.u64(c + 0x18)
            m.put(s, 8, m.u64(top + 8)); m.put(s + 8, 8, m.u64(top + 0x10))
            m.put(s + 0x10, 8, param); m.put(s + 0x18, 4, ident)
            m.write(s + 0x1C, m.read(part + 0x1C * k, 0x1A))
            m.vcall_void(b, 0x68, s)
            m.call_void(m.main + 0xFA1F30, c, side, ident)
    m.call_void(m.main + 0xFA29D0, c, side)
    base = c + 0x38 * side8
    count = base + 0x58
    j = i = 0
    while j < m.u8(count) if m.u8(count) else False:
        e = m.u64(base + 0x28 + 8 * i)
        if m.vcall(e, 0x208) & 1:
            i += 1
        else:
            t = i
            while m.u8(count) - 1 > t:
                m.put(base + 0x28 + 8 * t, 8, m.u64(base + 0x28 + 8 * (t + 1)))
                t += 1
            m.put(base + 0x28 + 8 * t, 8, e)
        j += 1


@lifted(0xFA0C4C)
def add_party_battlers_of(m, n, mm, side, pref, *_):
    """0xfa1584 on the main module's battler container [mm+0x30] for side `side`, with the holder at
    *pref referenced for the call and the participant block setup +0xd8 + 0xc0*side."""
    setup = m.u64(n + 0x38)
    with m.frame(0x10) as f:
        h = m.u64(pref)
        m.put(f, 8, h)
        if h:
            _inc(m, h)
        m.call_void(m.main + 0xFA1584, m.u64(mm + 0x30), side & M32, f, setup + 0xC0 * (side & 0xFF) + 0xD8)
        h = m.u64(f)
    if h:
        _dec(m, h)
    return h


@lifted(0x2892AC0)
def step_1(m, n, *_):
    """For each of the five sides that 0xe7e2a0(setup+0x34, setup+0x8d, side) selects: copy the
    setup's party holder (+0xa0 + 8*side) into a new one (0xfa0d38 from [N+8], 0xfa0f48), let
    0xfa1220 pick forms, and add its battlers to both main modules (0xfa0c4c on N+0x150 and N+0x170).
    Returns 1."""
    setup = m.u64(n + 0x38)
    a, b = m.u32(setup + 0x34), m.u8(setup + 0x8D)
    with m.frame(0x30) as f:
        for side in range(5):
            if not m.call(m.main + 0xE7E2A0, a, b, side) & 1:
                continue
            src = m.u64(m.u64(n + 0x38) + 8 * side + 0xA0)
            if src:
                _inc(m, src)
            h = m.call(m.main + 0xFA0D38, f + 0x28, m.u64(n + 8))
            if not h:
                m.call_void(m.main + 0xFA0F48, 0, src)
                m.put(f + 0x10, 8, 0)
                m.call_void(m.main + 0xFA1220, n, f + 0x10)
                m.put(f + 8, 8, 0)
                m.call_void(m.main + 0xFA0C4C, n, m.u64(n + 0x150), side, f + 8)
                m.put(f, 8, 0)
                m.call_void(m.main + 0xFA0C4C, n, m.u64(n + 0x170), side, f)
            else:
                _inc(m, h)
                m.call_void(m.main + 0xFA0F48, h, src)
                for slot, mm, call in ((f + 0x10, None, 0xFA1220), (f + 8, 0x150, 0xFA0C4C),
                                       (f, 0x170, 0xFA0C4C)):
                    m.put(slot, 8, h)
                    _inc(m, h)
                    held = m.u64(slot)
                    if mm is None:
                        m.call_void(m.main + call, n, slot)
                    else:
                        m.call_void(m.main + call, n, m.u64(n + mm), side, slot)
                    if held:
                        _dec(m, held)
                _dec(m, h)
            _dec(m, src)
    return 1


# --- deleting what step 1 drops ------------------------------------------------------------------

@lifted(0x1CBC6A4)
def delete_owned(m, o, *_):
    """The deleting destructor of an owned object: vf 0, then [o+0x10] freed through [o+8] with size
    u16 +0x18 and alignment u16 +0x1a."""
    _free(m, m.u64(o + 0x10), m.u64(o + 8), m.u16(o + 0x18), m.u16(o + 0x1A), 0, o)


@lifted(0x2D3F17C)
def destroy_holder(m, o, *_):
    """The party holder's destructor (vtables 0x4500ae0 / 0x4500b18): the six parameter objects
    +0x58 down to +0x30 lose their weak reference."""
    m.put(o, 8, m.main + 0x4500AE0); m.put(o + 0x20, 8, m.main + 0x4500B18)
    for off in range(0x58, 0x28, -8):
        p = m.u64(o + off)
        if p:
            _release(m, p)


@lifted(0x287ABFC)
def destroy_param(m, o, *_):
    """vf 0x50 of a party parameter object (vtable 0x44fc5a8): its record [o+0x48] loses a reference,
    the base vtables [0x46d8c78] return, and its weak handle entry [o+0x30] is dropped (u16 +0x18; the
    last one marks +0x1c -1 and frees the entry through 0xb44438 on the handle table)."""
    m.put(o, 8, m.main + 0x44FC5A8); m.put(o + 0x20, 8, m.main + 0x44FC7A0)
    m.put(o + 0x28, 8, m.main + 0x44FC7F0); m.put(o + 0x40, 8, m.main + 0x44FC848)
    r = m.u64(o + 0x48)
    if r:
        _dec(m, r)
    vt = m.u64(m.main + 0x46D8C78)
    m.put(o, 8, vt + 0x10); m.put(o + 0x20, 8, vt + 0x88); m.put(o + 0x28, 8, vt + 0xD8)
    h = m.u64(o + 0x30)
    if h:
        _drop_weak(m, h)


def _handle_table(m):
    """The weak-handle table [[0x46d3910]] (guard [0x46d3908]), also stored at [[0x46d3918]]."""
    if not m.u8(m.u64(m.main + 0x46D3908)) & 1:
        raise UnliftedCall("weak handle table static not built")
    table = m.u64(m.u64(m.main + 0x46D3910))
    m.put(m.u64(m.main + 0x46D3918), 8, table)
    return table


def _drop_weak(m, h):
    """ReleaseWeakReference on a handle entry: u16 count +0x18; the last one marks u32 +0x1c -1 and
    frees the entry's id (+0) in the handle table (0xb44438 on table+0x8040)."""
    n = m.u16(h + 0x18)
    m.put(h + 0x18, 2, n - 1)
    if n == 0:
        raise UnliftedCall("abort: weak reference counter underflows")
    if n != 1:
        return
    old = m.u32(h + 0x1C)
    m.put(h + 0x1C, 4, M32)
    if old == M32:
        return
    table = _handle_table(m)
    with m.frame(0x10) as f:
        m.put(f, 8, m.u64(h))
        m.call_void(m.main + 0xB44438, table + 0x8040, f)


def _base_dtor(m, o):
    """The weak-object base destructor: vtables [0x46d8c78] (+0x10 / +0x88 / +0xd8 at +0 / +0x20 /
    +0x28), its handle entry +0x30 dropped."""
    vt = m.u64(m.main + 0x46D8C78)
    m.put(o, 8, vt + 0x10); m.put(o + 0x20, 8, vt + 0x88); m.put(o + 0x28, 8, vt + 0xD8)
    h = m.u64(o + 0x30)
    if h:
        _drop_weak(m, h)


@lifted(0x1851444)
def base_dtor_1851444(m, o, *_):
    """The weak-object base destructor."""
    _base_dtor(m, o)


FUNCTIONS[0x2824B14] = base_dtor_1851444       # the same code


@lifted(0x28245C0)
def dtor_28245c0(m, o, *_):
    """Destructor of class 0x44eede8: the deque at +0x58 (0x16b070c), then the weak-object base."""
    m.put(o, 8, m.main + 0x44EEDE8); m.put(o + 0x20, 8, m.main + 0x44EEE68)
    m.put(o + 0x28, 8, m.main + 0x44EEEB8)
    m.call_void(m.main + 0x16B070C, o + 0x58)
    _base_dtor(m, o)


@lifted(0x151AA54)
def free_array_151aa54(m, holder, p, *_):
    """Free p through the allocator [holder+8], size [holder]*8, alignment 8."""
    alloc = m.u64(holder + 8)
    size = m.u64(holder) * 8
    if _deferred(m, alloc):
        return _tail(m, m.main + 0xB48FE8, alloc, p, size, 8)
    return _vtail(m, alloc, 0x18, p, size, 8)


@lifted(0x168DDB4)
def lock_weak(m, o, *_):
    """*x8 = the weak pair o's vf 0x18 gives when its handle entry still names o (+0x28 of it), else
    {0, 0}; the temporary's weak count is dropped."""
    out = m.x8
    with m.frame(0x10) as f:
        m.x8 = f
        m.vcall_void(o, 0x18)
        e = m.u64(f)
        m.put(out, 8, 0); m.put(out + 8, 8, 0)
        if m.u64(e + 0x10) == (o + 0x28 if o else 0):
            m.call_void(m.main + 0x168DF18, out, f)
            e = m.u64(f)
        if e:
            _drop_weak(m, e)


@lifted(0x17E61DC)
def assign_weak_id(m, dst, src, *_):
    """dst = the weak pair for id [src+8]: the handle table's entry (0xb44204) with its id, or reset
    (0x169222c) when the table has none."""
    ident = m.u64(src + 8)
    table = _handle_table(m)
    with m.frame(0x10) as f:
        m.call_sret(m.main + 0xB44204, f, table, ident)
        if not m.u64(f):
            return _tail(m, m.main + 0x169222C, dst)
        old = m.u64(dst)
        m.put(dst, 8, 0)
        if old:
            _drop_weak(m, old)
        m.put(dst, 8, m.u64(f)); m.put(f, 8, 0)
        m.put(dst + 8, 8, ident)


@lifted(0x2891030)
def reset_owned_2891030(m, holder, x, *_):
    """holder (+0 object, +8 owner, +0x10 size, +0x18 align) takes x; the old object is destroyed
    (0x190c248) and freed."""
    old = m.u64(holder)
    m.put(holder, 8, x)
    if old:
        _need(m, m.main + 0x190C248)
        _free(m, old, m.u64(holder + 8), m.u64(holder + 0x10), m.u64(holder + 0x18),
              dtor=lambda: m.call_void(m.main + 0x190C248, old))


@lifted(0x28950C8)
def copy_28950c8(m, dst, src, *_):
    """dst+0x40..+0x58 = src's three words, then the shared handles +0x58 / +0x60 (0xfa6560) and +0x68
    (0xfa6424) from src+0x18 / +0x20 / +0x28."""
    m.put(dst + 0x40, 8, m.u64(src)); m.put(dst + 0x48, 8, m.u64(src + 8))
    m.put(dst + 0x50, 8, m.u64(src + 0x10))
    m.call_void(m.main + 0xFA6560, dst + 0x58, m.u64(src + 0x18))
    m.call_void(m.main + 0xFA6560, dst + 0x60, m.u64(src + 0x20))
    return _tail(m, m.main + 0xFA6424, dst + 0x68, m.u64(src + 0x28))


def _weak_base(m, o):
    """The weak-object base constructor: +8 the thread's current owner, vtables [0x46d8c78], a weak
    handle to itself at +0x30 (0xc1a3f4). Returns 0xc1a3f4's result."""
    m.put(o + 0x10, 8, 0); m.put(o + 0x18, 4, 0)
    m.put(o, 8, _vt(m, 0x46D66F8))
    top = _tls_top(m)
    vt = m.u64(m.main + 0x46D8C78)
    m.put(o, 8, vt + 0x10); m.put(o + 8, 8, top)
    m.put(o + 0x20, 8, vt + 0x88); m.put(o + 0x28, 8, vt + 0xD8)
    m.put(o + 0x38, 8, 0); m.put(o + 0x30, 8, 0)
    return m.call(m.main + 0xC1A3F4, o + 0x30, o + 0x28)


@lifted(0x28951E8)
def construct_28951e8(m, o, *_):
    """Class 0x44ffd18 on the weak-object base: +0x40..+0x70 zero, u16 +0x70 0."""
    r = _weak_base(m, o)
    m.put(o, 8, m.main + 0x44FFD18); m.put(o + 0x20, 8, m.main + 0x44FFD90)
    m.put(o + 0x28, 8, m.main + 0x44FFDE0)
    m.put(o + 0x70, 2, 0)
    m.write(o + 0x40, bytes(0x30))
    return r


@lifted(0x2D38A8C)
def get_weak_2d38a8c(m, o, key, *_):
    """*x8 = [o + 0x48 + 0x28*s32 key[1] + 8*u32 key[2]] with a weak reference added."""
    x = m.u64(o + 0x48 + 0x28 * m.s(key + 4, 4) + 8 * m.u32(key + 8))
    m.put(m.x8, 8, x)
    if x:
        _acquire(m, x)
    return o


@lifted(0x1095E64)
def destroy_record(m, o, *_):
    """The Pokemon record's destructor (vtables 0x44a9218 / 0x44a9258): the core buffer +0x30 and party
    buffer +0x50 freed, the accessor +0x70 destroyed (vf 0) and freed, each through its holder."""
    m.put(o, 8, m.main + 0x44A9218); m.put(o + 0x20, 8, m.main + 0x44A9258)
    for off, dtor in ((0x30, None), (0x50, None), (0x70, 0), (0x70, 0), (0x50, None), (0x30, None)):
        p = m.u64(o + off)
        m.put(o + off, 8, 0)
        if p:
            _free(m, p, m.u64(o + off + 8), m.u64(o + off + 0x10), m.u64(o + off + 0x18), dtor)


FUNCTIONS[0x1095E60] = destroy_record          # `b 0x1095e64`
FUNCTIONS[0x1A1F788] = delete_owned            # the same code as 0x1cbc6a4


# --- step 2: copying the state ----------------------------------------------------------------------

def _deferred(m, alloc):
    """vf 0xf8 of the allocator says frees are deferred while the thread block's depth is positive."""
    return m.vcall(alloc, 0xF8) & 1 and m.s(m.call(m.main + 0xB4E600) + 0x12C8, 4) >= 1


def _free_node(m, alloc, p, size, align):
    if _deferred(m, alloc):
        m.call_void(m.main + 0xB48FE8, alloc, p, size, align)
    else:
        m.vcall_void(alloc, 0x18, p, size, align)


def _clear_nodes(m, o, size, align):
    """Empty the unordered_map at o+8 (list +0x38, node allocator +0x40, buckets +8 / +0x10, count
    +0x60): every node freed, the buckets zeroed."""
    p = m.u64(o + 0x38)
    while p:
        nxt = m.u64(p)
        _free_node(m, m.u64(o + 0x40), p, size, align)
        p = nxt
    m.put(o + 0x38, 8, 0)
    for i in range(m.u64(o + 0x10)):
        m.put(m.u64(o + 8) + 8 * i, 8, 0)
    m.put(o + 0x60, 8, 0)


@lifted(0xF77F08)
def copy_id_map(m, dst, src, *_):
    """dst's id counter u32 +0x70 and its id -> {side, slot} map (+8) emptied and refilled from src's."""
    m.put(dst + 0x70, 4, m.u32(src + 0x70))
    if m.u64(dst + 0x60):
        _clear_nodes(m, dst, 0x20, 4)
    node = m.u64(src + 0x38)
    while node:
        v = m.call(m.main + 0xF78064, dst + 8, node + 0x10)
        m.put(v, 8, m.u64(node + 0x14))
        node = m.u64(node)


@lifted(0xF78AF4)
def clear_id_map(m, o, *_):
    """Empty the id map at o+8 (0x20-byte nodes)."""
    if m.u64(o + 0x60):
        p = m.u64(o + 0x38)
        while p:
            nxt = m.u64(p)
            alloc = m.u64(o + 0x40)
            if m.vcall(alloc, 0xF8) & 1 and m.s(m.call(m.main + 0xB4E600) + 0x12C8, 4) > 0:
                m.call_void(m.main + 0xB48FE8, alloc, p, 0x20, 4)
            else:
                m.vcall_void(alloc, 0x18, p, 0x20, 4)
            p = nxt
        m.put(o + 0x38, 8, 0)
        for i in range(m.u64(o + 0x10)):
            m.put(m.u64(o + 8) + 8 * i, 8, 0)
        m.put(o + 0x60, 8, 0)
    node = m.u64(o + 0x38)
    while node:
        v = m.call(m.main + 0xF803D0, o + 8, node + 0x10)
        m.put(v, 8, m.u64(node + 0x14))
        node = m.u64(node)


@lifted(0xF9FD40)
def apply_setup(m, n, mm, *_):
    """Copy the setup's per-side flags and values into the main module's member +0x2d0 (u8 +9 + 4k,
    u16 +0xa + 4k from u32 setup+0x4e4 + 4k when the flag is set), then the setup's starting effects
    on battler 1 (vf 0x548 / 0x330 / 0x1b8 / 0x328) and 0xfa0810 for flag bit 32."""
    m.call_void(m.main + 0xFA0154, n, mm)
    m.call_void(m.main + 0xFA0110, n, mm)
    for k in range(5):
        setup = m.u64(n + 0x38)
        t = m.u64(mm + 0x2D0)
        m.put(t + 9 + 4 * k, 1, m.u8(setup + 0x4DD + k))
        if m.u8(setup + 0x4DD + k):
            m.put(t + 0xA + 4 * k, 2, m.u32(setup + 0x4E4 + 4 * k))
    one = lambda: m.call(m.main + 0xFA0028, m.u64(mm + 0x30), 1, 0)
    setup = m.u64(n + 0x38)
    if m.u32(setup + 0x498) & 0x21000 and m.u16(setup + 0x4F8):
        b = one()
        if b:
            m.vcall_void(b, 0x548, 6, m.u16(m.u64(n + 0x38) + 0x4F8))
    if m.u8(m.u64(n + 0x38) + 0x499) & 4:
        b = one()
        m.put(b + 0x714, 1, 1)
        m.vcall_void(b, 0x330, 0x12, 0)
        v = m.u16(m.u64(n + 0x38) + 0x514)
        if v:
            m.vcall_void(one(), 0x1B8, 0, v // 10)
    flags = m.u64(m.u64(n + 0x38) + 0x498)
    if flags >> 33 & 1:
        b = one()
        m.put(b + 0x714, 1, 1)
        m.vcall_void(b, 0x330, 0x12, 0)
        setup = m.u64(n + 0x38)
        b = one()
        if b:
            v = m.u16(setup + 0x6B0)
            if v:
                m.vcall_void(b, 0x548, 6, v)
            x = m.u16(setup + 0x6B2) & 0x1F
            m.vcall_void(b, 0x328, x | x << 5 | 0x4800, 0)
        v = m.u16(m.u64(n + 0x38) + 0x5B8)
        if v:
            m.vcall_void(one(), 0x1B8, 0, v // 10)
    elif flags >> 32 & 1:
        m.call_void(m.main + 0xFA0810, m.u64(mm + 0x330))
    if m.u8(m.u64(n + 0x38) + 0x49A) & 2:
        b = one()
        m.put(b + 0x714, 1, 1)
        return _vtail(m, b, 0x330, 0x12, 0)


@lifted(0xF9FD14)
def apply_setup_both(m, n, *_):
    """0xf9fd40 on the main modules N+0x170, then N+0x150."""
    m.call_void(m.main + 0xF9FD40, n, m.u64(n + 0x170))
    return _tail(m, m.main + 0xF9FD40, n, m.u64(n + 0x150))


def _kind(m, obj, guard_got, static_got):
    """True when the list reached from vf 0 of obj+0x28 holds the static at [main+static_got] (its
    guard [main+guard_got] must be set)."""
    sub = obj + 0x28
    r = m.call(m.u64(m.u64(sub)), sub)
    if not m.u8(m.u64(m.main + guard_got)) & 1:
        raise UnliftedCall(f"static at [0x{static_got:x}] not built")
    want = m.u64(m.main + static_got)
    while r:
        if r == want:
            return True
        r = m.u64(r)
    return False


@lifted(0xFA0334)
def record_side_entries(m, n, side, *_):
    """For a side 0xe7e2a0 selects on the main module's +0x36c / +0x370: for each plain parameter object
    k (< 6) of the setup's holder +0xa0 + 8*side, fill the empty entry +0x10 + 0x60*side + 0x10*k of
    member +0x250 in N+0x170 and N+0x150: u32 its battler id ({side, k} in the id map), u16 species,
    u16 form, u8 vf 0x130, u8 vf 0xb0, u8 vf 0x160 != 0, u8 vf 0x158(2) & 1 at +0x1d."""
    s8 = side & 0xFF
    x = m.u64(m.u64(n + 0x170) + 0x290)
    mm = m.u64(x + 8)
    if not m.call(m.main + 0xE7E2A0, m.u32(mm + 0x36C), m.u8(mm + 0x370), s8) & 1:
        return
    h = m.u64(m.u64(n + 0x38) + 8 * s8 + 0xA0)
    if not h:
        raise UnliftedCall("party holder missing")
    _inc(m, h)
    k = 0
    while k < m.u8(h + 0x60):
        p = m.u64(h + 0x30 + 8 * k) if k <= 5 else 0
        if p and _kind(m, p, 0x46DCD50, 0x46DCD58):
            ident = 0
            node = m.u64(m.u64(m.u64(x + 8) + 0x50) + 0x38)
            while node:
                if m.u32(node + 0x14) == s8 and m.u8(node + 0x18) == k & 0xFF:
                    ident = m.u32(node + 0x10)
                    break
                node = m.u64(node)
            acc = m.u64(m.u64(p + 0x48) + 0x70)
            species = m.call(m.main + 0xBF44F4, acc)
            form = m.call(m.main + 0xBF41A8, m.u64(m.u64(p + 0x48) + 0x70))
            a = m.vcall(p, 0x130)
            b = m.vcall(p, 0xB0)
            c = int(m.vcall(p, 0x160) & 0xFFFF != 0)
            d = m.vcall(p, 0x158, 2) & 1
            if s8 <= 4 and k & 0xFF <= 5:
                for mod in (0x170, 0x150):
                    e = m.u64(m.u64(n + mod) + 0x250) + 0x60 * s8 + 0x10 * k
                    if m.u32(e + 0x10) == 0:
                        m.put(e + 0x10, 4, ident); m.put(e + 0x14, 2, species); m.put(e + 0x16, 2, form)
                        m.put(e + 0x18, 1, a); m.put(e + 0x19, 1, b); m.put(e + 0x1A, 1, c)
                        m.put(e + 0x1D, 1, d)
        k += 1
    c = m.u32(h + 0x28)
    m.put(h + 0x28, 4, c - 1)
    if c == 1:
        return _vtail(m, h, 0x10)
    if c == 0:
        raise UnliftedCall("abort: reference counter underflows")


@lifted(0xFA0210)
def record_entries(m, n, *_):
    """For sides 0..4: 0x2892374(N, side, block) when the setup's participant block +0xc8 + 0xc0*side
    holds something, else 0xfa0334(N, side)."""
    r = None
    for side in range(5):
        p = m.u64(n + 0x38) + 0xC8 + 0xC0 * side      # 0xfa0330 returns its argument
        if m.u64(p):
            r = _tail(m, m.main + 0x2892374, n, side, p)
        else:
            r = _tail(m, m.main + 0xFA0334, n, side)
    return r


@lifted(0xFA3C64)
def assign_weak(m, holder, x, *_):
    """*holder = x with a weak reference added; the one it held is released."""
    if x:
        _acquire(m, x)
    old = m.u64(holder)
    m.put(holder, 8, x)
    if old:
        _release(m, old)


@lifted(0xFA68C4)
def make_node_fa68c4(m, o, h, src, *_):
    """*x8 = {a 0x38-byte node from the allocator [o+0x38], o+0x38, built}: 0xfa6950 fills node+0x10
    from src, node+0 = 0, +8 = h."""
    out = m.x8
    holder = o + 0x38
    node = m.vcall(m.u64(holder), 0x10, 0x38, 8)
    if not node:
        raise UnliftedCall("allocator out of memory: vf 0xe8")
    m.put(out, 8, node); m.put(out + 8, 8, holder)
    r = m.call(m.main + 0xFA6950, holder, node + 0x10, src)
    m.put(out + 0x10, 1, 1)
    m.put(node, 8, 0); m.put(node + 8, 8, h)
    return r


def _create_zeroed(m, alloc, size, ctor, *args):
    """Create with the object zeroed (memset) before its constructor."""
    def build(o):
        m.write(o, bytes(size))
        m.call_void(m.main + ctor, o, *args)
    return _create(m, alloc, size, build)


@lifted(0xFA7F10)
def create_fa7f10(m, _x0, alloc, *_):
    """Create a 0xb8-byte object (0xfae2c8 with 0)."""
    return _create(m, alloc, 0xB8, lambda o: m.call_void(m.main + 0xFAE2C8, o, 0))


@lifted(0xFAE198)
def create_fae198(m, _x0, alloc, flag, *_):
    """Create a 0xb8-byte object (0xfae2c8 with the byte at flag)."""
    return _create(m, alloc, 0xB8, lambda o: m.call_void(m.main + 0xFAE2C8, o, m.u8(flag)))


@lifted(0xFA9684)
def create_fa9684(m, alloc, *_):
    """Create a zeroed 0xa8-byte object (0xfa97bc)."""
    return _create_zeroed(m, alloc, 0xA8, 0xFA97BC)


@lifted(0xFAC268)
def create_fac268(m, alloc, *_):
    """Create a zeroed 0x68-byte object (0xfac3a0)."""
    return _create_zeroed(m, alloc, 0x68, 0xFAC3A0)


@lifted(0xFB00E0)
def make_fb00e0(m, alloc, src, *_):
    """*x8 = {a 0xc4a8-byte object from alloc built by 0xfb0194(o, src) with alloc on the object stack,
    alloc, 0xc4a8, 8}, or four zeros."""
    out = m.x8
    o = m.vcall(alloc, 0x10, 0xC4A8, 8)
    if not o:
        _stores(m, out, ((0x10, 8, 0), (0x18, 8, 0), (0, 8, 0), (8, 8, 0)))
        return 0
    stack = m.call(m.main + 0x343DA20, m.u32(m.call(m.main + 0xF53840)))
    _push(m, stack, alloc)
    r = _tail(m, m.main + 0xFB0194, o, src)
    _stores(m, out, ((0, 8, o), (8, 8, alloc), (0x10, 8, 0xC4A8), (0x18, 8, 8)))
    _pop(m, stack)
    return r


@lifted(0xFA5B04)
def push_weak(m, v, src, *_):
    """vector<weak handle>::push_back(*src): v = {+0 begin, +8 end, +0x10 capacity end, +0x18 the
    allocator, +0x20 max size}; growth doubles, moves the handles (each with the allocator on the
    object stack) and frees the old buffer."""
    end, cap = m.u64(v + 8), m.u64(v + 0x10)
    holder = v + 0x18
    if end != cap:
        m.call_void(m.main + 0xFA5E0C, holder, end, src)
        m.put(v + 8, 8, end + 8)
        return
    begin = m.u64(v)
    size = (end - begin) >> 3
    most = min(m.u64(v + 0x20), 0x7FFFFFFFFFFFFFFF)
    if most < size + 1:
        raise UnliftedCall("vector length error")
    n = max((cap - begin) >> 2, size + 1) if (cap - begin) >> 3 < most >> 1 else most
    buf = 0
    if n:
        buf = m.vcall(m.u64(holder), 0x10, n * 8, 8)
        if not buf:
            raise UnliftedCall("allocator out of memory: vf 0xe8")
    slot = buf + size * 8
    m.call_void(m.main + 0xFA5E0C, holder, slot, src)
    s, d = end, slot
    while s != begin:
        owner = m.u64(holder)
        stack = _tls_stack(m)
        if stack:
            _push(m, stack, owner)
        m.put(d - 8, 8, m.u64(s - 8)); m.put(s - 8, 8, 0)
        if stack:
            _pop(m, stack)
        s -= 8; d -= 8
    old_begin, old_end = m.u64(v), m.u64(v + 8)
    old_cap = m.u64(v + 0x10)
    m.put(v, 8, d); m.put(v + 8, 8, slot + 8); m.put(v + 0x10, 8, buf + n * 8)
    p = old_end
    while p != old_begin:
        p -= 8
        x = m.u64(p)
        if x:
            _release(m, x)
    if old_begin:
        alloc = m.u64(holder)
        if _deferred(m, alloc):
            return _tail(m, m.main + 0xB48FE8, alloc, old_begin, old_cap - old_begin, 8)
        return _vtail(m, alloc, 0x18, old_begin, old_cap - old_begin, 8)


@lifted(0xFA5930)
def add_weak(m, o, pref, *_):
    """Push the handle *pref on o's list +0x40 when its object is of the kind of static [0x46e2f70]
    (guard [0x46e2f68]), else on +0x78."""
    x = m.u64(pref)
    if x:
        _acquire(m, x)
    found = _kind(m, x, 0x46E2F68, 0x46E2F70)
    if x:
        _release(m, x)
    return _tail(m, m.main + 0xFA5B04, o + 0x40 if found else o + 0x78, pref)


@lifted(0x2D381A4)
def step_2(m, n, *_):
    """With the election object [N+0x138] held, its true vf 0x68 sets bit 0 of N+0x9e; then the setup
    applied to both main modules (0xf9fd14), the state built from [N+8] (0xfa2cb0) and the per-side
    entries recorded (0xfa0210). Returns 1."""
    r = m.u64(n + 0x138)
    if r:
        _acquire(m, r)
        r2 = m.u64(n + 0x138)
        if r2:
            _acquire(m, r2)
        done = m.vcall(r2, 0x68) & 1
        if r2:
            _release(m, r2)
        _release(m, r)
        if done:
            m.put(n + 0x9E, 1, m.u8(n + 0x9E) | 1)
    m.call_void(m.main + 0xF9FD14, n)
    m.call_void(m.main + 0xFA2CB0, n, m.u64(n + 8))
    m.call_void(m.main + 0xFA0210, n)
    return 1


@lifted(0xFAE80C)
def do_rehash_fae80c(m, table, n, *_):
    """__do_rehash of a u32-keyed map (bucket arrays aligned 8)."""
    _do_rehash(m, table, n, 8, 4)


@lifted(0xFAE708)
def rehash_fae708(m, table, want, *_):
    """rehash(want) of 0xfae80c's map."""
    _rehash(m, table, want, 0xFAE80C)


BATTLER_FIELDS = ((8, 0x36), (0x38, 0x3A1), (0x3A2, 0x3A9), (0x3AC, 0x3B3), (0x3B4, 0x3B6))


@lifted(0x2A10A68)
def copy_battler_2a10a68(m, dst, src, *_):
    """dst's parameter object a clone of src's ([src] vf 0x198; the one it held loses its weak
    reference), then the fields src+8..+0x3b6 copied (the padding +0x36, +0x3a1, +0x3a9..+0x3ac and
    +0x3b3 left)."""
    with m.frame(0x10) as f:
        m.x8 = f
        m.vcall_void(m.u64(src), 0x198)
        old = m.u64(dst)
        m.put(dst, 8, 0)
        if old:
            _release(m, old)
        m.put(dst, 8, m.u64(f))
    for a, b in BATTLER_FIELDS:
        m.write(dst + a, m.read(src + a, b - a))
    return dst + 0x348



def _battler_block(m, p):
    """The 0x2590-byte battler block: vtable [0x46e25d8]+0x10, 25 records of 0x180 bytes from +8
    (zero, u8 +0x160 5, u16 +0x16e 10, u32 +0x170 0x0a0a0a0a, u8 +0x174 10), then 0x12702c0 twice on
    the records."""
    m.put(p, 8, _vt(m, 0x46E25D8))
    for k in range(25):
        e = p + 8 + 0x180 * k
        m.write(e, bytes(0x180))
        _stores(m, e, ((0x160, 1, 5), (0x164, 8, 0), (0x16C, 1, 0), (0x16E, 2, 10), (0x170, 4, 0x0A0A0A0A),
                       (0x174, 1, 10), (0x178, 2, 0), (0x17A, 1, 0), (0x17C, 2, 0)))
    m.call_void(m.main + 0x12702C0, p + 8)
    m.call_void(m.main + 0x12702C0, p + 8)


@lifted(0x126BFA4)
def construct_server(m, o, a, *_):
    """The battle server's module set (0x1f0 bytes), a = {+0 allocator, +8 N, +0x10 the main module}:
    +0 / +8 from a+8 / a+0x10, then 15 owned members built from [a] (holder +8 owner, +0x10 size,
    +0x18 align): the battler block +0x190, the raid data copy +0x1b0, the setup copy +0x1d0, +0x150,
    +0x170, the command-format map +0x10 (from 0x3c6abe4), +0xf0 (0x12708f4), +0x130, +0x110
    (0x1272468), +0xb0 (0x127102c), +0xd0, +0x90, +0x50, +0x70, the module wiring 0x127f998 and
    +0x30."""
    m.put(o, 8, m.u64(a + 8)); m.put(o + 8, 8, m.u64(a + 0x10))
    m.write(o + 0x10, bytes(0x1E0))
    _own(m, o + 0x190, m.u64(a), 0x2590, lambda p: _battler_block(m, p))

    def raid(p):
        mm = m.u64(a + 0x10)
        m.put(p, 8, m.u64(a + 8)); m.put(p + 8, 8, mm)
        m.write(p + 0x10, bytes(0x4A))
        tail = ((0x5C, 1, 0), (0x60, 4, 0), (0x64, 1, 0), (0x68, 4, 0), (0x6C, 1, 0), (0x70, 4, 0),
                (0x74, 1, 0))
        _stores(m, p, tail + ((0x78, 4, 0),))
        m.write(p + 0x10, m.read(m.u64(mm + 0x310) + 0x1C, 0x4A))
        _stores(m, p, tail + ((0x78, 8, 0),))
    _own(m, o + 0x1B0, m.u64(a), 0x80, raid)

    def setup(p):
        n = m.u64(a + 8)
        m.put(p, 8, n); m.put(p + 8, 8, m.u64(a + 0x10))
        m.write(p + 0x2C, bytes(0x4A))
        m.write(p + 0x2C, m.read(m.u64(n + 0x38) + 0x568, 0x4A))
        _stores(m, p, ((0x24, 8, 0), (0x1C, 8, 0), (0x10, 8, M32), (0x18, 4, 0)))
    _own(m, o + 0x1D0, m.u64(a), 0x78, setup)
    _own(m, o + 0x150, m.u64(a), 0x20, lambda p: _stores(m, p, (
        (0x10, 8, 0), (0, 8, m.u64(a + 8)), (8, 8, m.u64(a + 0x10)), (0x18, 4, 0))))
    _own(m, o + 0x170, m.u64(a), 0x30, lambda p: m.write(p, bytes(0x30)), align=4)

    def formats(p):
        owner = m.u64(a)
        _stores(m, p, ((0x18, 8, 0x3FFFFFFFFFFFFFFF), (0x20, 8, 0), (0x40, 8, 0x3FFFFFFFFFFFFFFF),
                       (0x48, 8, 0), (0, 8, 0), (8, 8, 0), (0x28, 4, 0), (0x50, 4, 0), (0x58, 8, 0),
                       (0x60, 4, ONE_F), (0x10, 8, owner), (0x30, 8, 0), (0x38, 8, owner)))
        m.write(p + 0x68, bytes(0x4E28))
        for i in range(0xD0):
            e = m.main + 0x3C6ABE4 + 4 * i
            v = m.u8(e + 2)
            m.put(m.call(m.main + 0xFAF09C, p, e), 1, v)
    _own(m, o + 0x10, m.u64(a), 0x4E90, formats)
    _own(m, o + 0xF0, m.u64(a), 0x2428, lambda p: m.call_void(m.main + 0x12708F4, p))
    _own(m, o + 0x130, m.u64(a), 0x1FA0, lambda p: m.write(p, bytes(0x1FA0)))
    with m.frame(0x80) as f:
        owner = m.u64(a)
        m.put(f, 8, owner)
        _own(m, o + 0x110, owner, 0x188, lambda p: m.call_void(m.main + 0x1272468, p, f))
        args = (m.u64(a), m.u64(o), m.u64(o + 8), m.u64(o + 0xF0), m.u64(o + 0x150), m.u64(o + 0x170),
                m.u64(o + 0x130), m.u64(o + 0x110))
        for i, v in enumerate(args):
            m.put(f + 8 * i, 8, v)
        _own(m, o + 0xB0, m.u64(a), 0x88, lambda p: m.call_void(m.main + 0x127102C, p, f))
        w = (m.u64(o), m.u64(o + 8))
        _own(m, o + 0xD0, m.u64(a), 0x20, lambda p: _stores(m, p, (
            (0x10, 8, m.u64(o + 0xB0)), (0x18, 8, w[1]), (0, 8, _vt(m, 0x46E25E0)), (8, 8, w[0]))))
        w = (m.u64(o + 0xB0), m.u64(o), m.u64(o + 8), m.u64(o + 0x190))
        _own(m, o + 0x90, m.u64(a), 0x28, lambda p: _stores(m, p, (
            (0x20, 8, w[3]), (0x10, 8, w[2]), (0x18, 8, w[0]), (0, 8, _vt(m, 0x46E25E8)), (8, 8, w[1]))))
        w = (m.u64(o), m.u64(o + 0x90), m.u64(o + 8), m.u64(o + 0x10))
        _own(m, o + 0x50, m.u64(a), 0x28, lambda p: _stores(m, p, (
            (0x20, 8, w[1]), (0x10, 8, w[2]), (0x18, 8, w[3]), (0, 8, _vt(m, 0x46E25F0)), (8, 8, w[0]))))
        w = (m.u64(o + 0x10), m.u64(o + 0x50))
        _own(m, o + 0x70, m.u64(a), 0x18, lambda p: _stores(m, p, (
            (0x10, 8, w[1]), (0, 8, _vt(m, 0x46E25F8)), (8, 8, w[0]))))
        parts = (0, 8, 0x10, 0x50, 0x70, 0xB0, 0xD0, 0x110, 0xF0, 0x150, 0x170, 0x190, 0x1B0, 0x1D0, 0x130)
        for i, off in enumerate(parts):
            m.put(f + 8 * i, 8, m.u64(o + off))
        m.call_void(m.main + 0x127F998, m.u64(o + 0x130), m.u64(a), f)
    w = (m.u64(o), m.u64(o + 8), m.u64(o + 0x10), m.u64(o + 0x130))
    _own(m, o + 0x30, m.u64(a), 0x20, lambda p: _stores(m, p, (
        (0, 8, w[0]), (8, 8, w[1]), (0x10, 8, w[2]), (0x18, 8, w[3]))))


@lifted(0x126B590)
def make_server(m, o, alloc, n, *_):
    """o+0x28 holds a new server module set (0x126bfa4, 0x1f0 bytes from alloc) for a = {alloc, n,
    [o+8]}; a replaced one is destroyed by 0x190c248."""
    with m.frame(0x20) as a:
        m.put(a, 8, alloc); m.put(a + 8, 8, n); m.put(a + 0x10, 8, m.u64(o + 8))
        _own(m, o + 0x28, alloc, 0x1F0, lambda p: m.call_void(m.main + 0x126BFA4, p, a),
             dtor=lambda x: m.call_void(m.main + 0x190C248, x))


@lifted(0x126BA88)
def make_main_module(m, o, alloc, n, mm, *_):
    """o+8 holds a new main module (0x12742d0, 0x378 bytes from alloc) for a = {alloc, n, u32 mm+0x36c,
    u8 mm+0x370, 0, 0}, then reset by 0x127d824."""
    with m.frame(0x30) as a:
        m.put(a + 0x18, 8, 0); m.put(a + 0x20, 8, 0)
        m.put(a, 8, alloc); m.put(a + 8, 8, n)
        m.put(a + 0x10, 4, m.u32(mm + 0x36C)); m.put(a + 0x14, 1, m.u8(mm + 0x370))
        x = _own(m, o + 8, alloc, 0x378, lambda p: m.call(m.main + 0x12742D0, p, a))
        return m.call(m.main + 0x127D824, m.u64(o + 8) if x else x, a)


@lifted(0xFA9EDC)
def make_branch(m, o, s, *_):
    """o+0x38 holds a new 0x48-byte state copy from the allocator [o+8] for s = {N, the main module,
    u8 flag}: {+0 the main module, a fresh main module (0x126ba88), a fresh server (0x126b590)}; the
    old one goes through 0xfaa124. Then [o+0x30] is pointed at it (+0x30 N, u8 +0x38 flag, +0x40
    [N+0x48], +0x48 the main module, +0x50 the copy, +0x58 [N+0x190]) and [o+0x58] +8 / +0x10 =
    N / [o+0x30]."""
    n, mm = m.u64(s), m.u64(s + 8)
    m.put(o + 0x88, 1, m.u8(s + 0x10))
    alloc = m.u64(o + 8)
    m.put(o + 0x78, 8, n); m.put(o + 0x80, 8, mm)

    def build(w):
        m.put(w, 8, mm); m.put(w + 8, 8, 0); m.put(w + 0x10, 8, 0); m.put(w + 0x18, 8, 0)
        m.put(w + 0x40, 8, 0); m.write(w + 0x20, bytes(0x20))
        m.call_void(m.main + 0x126BA88, w, alloc, n, mm)
        m.call_void(m.main + 0x126B590, w, alloc, n)
    _own(m, o + 0x38, alloc, 0x48, build, delete=lambda x: m.call_void(m.main + 0xFAA124, o + 0x40, x))
    flag = m.u8(o + 0x88)
    n, mm = m.u64(o + 0x78), m.u64(o + 0x80)
    a48 = m.u64(n + 0x48)
    h = m.u64(n + 0x190)
    if h:
        _inc(m, h)
        _dec(m, h)
    t = m.u64(o + 0x30)
    m.put(t + 0x30, 8, n); m.put(t + 0x38, 1, flag); m.put(t + 0x40, 8, a48); m.put(t + 0x48, 8, mm)
    m.put(t + 0x50, 8, m.u64(o + 0x38)); m.put(t + 0x58, 8, h)
    x = m.u64(o + 0x58)
    m.put(x + 8, 8, m.u64(o + 0x78)); m.put(x + 0x10, 8, m.u64(o + 0x30))


# 0x12739f4's record (0xc4 bytes, 12 of them from +8): (offset, bytes) runs; the bytes between runs
# are never written.
FIELD_RECORD = (
    (0x00, "00" * 0x1),
    (0x02, "ffffffff0000000000000a00"),
    (0x10, "00000a0a000000000000ffff00000007000007000007000007000007000007"
           "000007000007000007000007000007"),
    (0x40, "00" * 0x19),
    (0x5C, "00" * 0x2C + "0a" * 0xB),
    (0x94, "00" * 0x2C),
)


@lifted(0x12739F4)
def construct_field_records(m, o, *_):
    """Class 0x44f11b8 (0x940 bytes): 12 records of 0xc4 bytes from +8 (FIELD_RECORD), u8 +0x938 0,
    then +0x60..+0xcb zeroed (the tail memset; returns its result)."""
    m.put(o, 8, m.main + 0x44F11B8)
    for k in range(12):
        r = o + 8 + 0xC4 * k
        for off, data in FIELD_RECORD:
            m.write(r + off, bytes.fromhex(data))
    m.put(o + 0x938, 1, 0)
    return m.call(m.main + 0x343C220, o + 0x60, 0, 0x6B)


@lifted(0x1272468)
def construct_1272468(m, o, a, *_):
    """Class 0x44fccf0 (0x98 bytes) from the allocator [a]: +0x90 0, +8..+0x89 zero, then held members
    +8 the field records (0x940, 0x12739f4), +0x28 one zero byte (alignment 1), +0x48 vtable
    [0x46e2f20] with five bytes 5, +0x68 vtable [0x46e2f28] zeroed (0x30); ends with 0x127381c."""
    m.put(o, 8, m.main + 0x44FCCF0); m.put(o + 0x90, 8, 0)
    m.write(o + 8, bytes(0x81))
    _own(m, o + 8, m.u64(a), 0x940, lambda p: m.call_void(m.main + 0x12739F4, p))
    _own(m, o + 0x28, m.u64(a), 1, lambda p: m.put(p, 1, 0), align=1)
    _own(m, o + 0x48, m.u64(a), 0x10, lambda p: _stores(m, p, (
        (0, 8, _vt(m, 0x46E2F20)), (8, 4, 0x05050505), (0xC, 1, 5))))
    _own(m, o + 0x68, m.u64(a), 0x30, lambda p: _stores(m, p, (
        (0x10, 8, 0), (0x18, 8, 0), (0x1E, 8, 0), (0x28, 4, 0), (0, 8, _vt(m, 0x46E2F28)), (8, 8, 0))))
    return _tail(m, m.main + 0x127381C, o)


@lifted(0x1271948)
def make_slots_1271948(m, o, alloc, *_):
    """96 held 0x20-byte records at o+8 + 0x20*i: vtable [0x46e26f8]+0x10, the rest zero."""
    vt = _vt(m, 0x46E26F8)
    for i in range(0x60):
        _own(m, o + 8 + 0x20 * i, alloc, 0x20, lambda p: _stores(m, p, (
            (0, 8, vt), (8, 2, 0), (0xA, 1, 0), (0xC, 8, 0), (0x14, 8, 0), (0x1C, 4, 0))), dtor=0)


@lifted(0x1271ED0)
def make_slots_1271ed0(m, o, alloc, *_):
    """32 held 0x438-byte records at o+8 + 0x20*k: vtable [0x46e26f0]+0x10, the rest zero."""
    vt = _vt(m, 0x46E26F0)

    def build(p):
        m.put(p, 8, vt)
        m.write(p + 8, bytes(0x430))
    for k in range(0x20):
        _own(m, o + 8 + 0x20 * k, alloc, 0x438, build, dtor=0)


def _clear_slots(m, o):
    m.put(o + 0xC08, 4, 0)
    for i in range(0x60):
        m.put(m.u64(o + 8 + 0x20 * i) + 8, 2, 0)


def _clear_records(m, p):
    m.put(p + 0x408, 4, 0)
    for k in range(0x20):
        m.write(m.u64(p + 8 + 0x20 * k) + 8, bytes(0x430))


@lifted(0x127102C)
def construct_127102c(m, o, a, *_):
    """o+0..+0x38 = a+8..+0x40 (seven module pointers), then held +0x38 a slot table (0xc10:
    vtable [0x46e26e0], 96 records from 0x1271948, their u16 +8 cleared) and +0x58 a record table
    (0x410: vtable [0x46e26e8], 32 records from 0x1271ed0, cleared twice); +0x78 0, u32 +0x80 0."""
    for i in range(7):
        m.put(o + 8 * i, 8, m.u64(a + 8 + 8 * i))
    m.write(o + 0x38, bytes(0x4C))

    def slots(p):
        owner = m.u64(a)
        m.put(p, 8, _vt(m, 0x46E26E0))
        m.write(p + 8, bytes(0xC04))
        m.call_void(m.main + 0x1271948, p, owner)
        _clear_slots(m, p)
    _own(m, o + 0x38, m.u64(a), 0xC10, slots)

    def records(p):
        owner = m.u64(a)
        m.put(p, 8, _vt(m, 0x46E26E8))
        m.write(p + 8, bytes(0x404))
        m.call_void(m.main + 0x1271ED0, p, owner)
        _clear_records(m, p)
    p = _own(m, o + 0x58, m.u64(a), 0x410, records)
    m.put(o + 0x80, 4, 0); m.put(o + 0x78, 8, 0)
    _clear_records(m, p)
    _clear_slots(m, m.u64(o + 0x38))


@lifted(0x127F998)
def construct_modules(m, o, alloc, a, *_):
    """The server's 253 battle modules: o + 0x20*i holds a 0x80-byte module from alloc, built by
    0x12d0848(module, a) and given vtable [0x46e2738 + 8*i]+0x10."""
    for i in range(253):
        def build(p, i=i):
            m.call_void(m.main + 0x12D0848, p, a)
            m.put(p, 8, _vt(m, 0x46E2738 + 8 * i))
        _own(m, o + 0x20 * i, alloc, 0x80, build)


def _branch_args(m, f, o, base, extra=None):
    """The 0x18-byte argument of 0xfa9edc at f: {[o+base], [o+base+8], u8 [o+base+0x10]} (+0x18
    `extra` when given)."""
    m.put(f, 8, m.u64(o + base)); m.put(f + 8, 8, m.u64(o + base + 8))
    m.put(f + 0x10, 1, m.u8(o + base + 0x10))
    if extra is not None:
        m.put(f + 0x18, 8, extra)


@lifted(0xFA9C58)
def branch_one(m, o, *_):
    """0xfa9edc([o+0x38], {[o+0x40], [o+0x48], u8 [o+0x50]})."""
    with m.frame(0x20) as f:
        _branch_args(m, f, o, 0x40)
        m.call_void(m.main + 0xFA9EDC, m.u64(o + 0x38), f)


FUNCTIONS[0xFA9D70] = branch_one               # the same code


@lifted(0xFA9C44)
def branch_one_from(m, o, src, *_):
    """o+0x40..+0x60 = src's four words, then 0xfa9c58."""
    for i in range(4):
        m.put(o + 0x40 + 8 * i, 8, m.u64(src + 8 * i))
    return _tail(m, m.main + 0xFA9C58, o)


@lifted(0xFA9D44)
def branch_one_copy(m, o, src, *_):
    """o+0x40..+0x68 = src's 0x28 bytes, then 0xfa9d70."""
    m.write(o + 0x40, m.read(src, 0x28))
    return _tail(m, m.main + 0xFA9D70, o)


@lifted(0xFA9E08)
def branch_five(m, o, src, *_):
    """o+0x80..+0xa0 = src's four words, then 0xfa9edc on [o+0x38], [o+0x40], [o+0x48], [o+0x50] and
    [o+0x58] with {[o+0x80], [o+0x88], u8 [o+0x90]}."""
    for i in range(4):
        m.put(o + 0x80 + 8 * i, 8, m.u64(src + 8 * i))
    with m.frame(0x20) as f:
        for slot in (0x38, 0x40, 0x48, 0x50, 0x58):
            _branch_args(m, f, o, 0x80)
            m.call_void(m.main + 0xFA9EDC, m.u64(o + slot), f)


@lifted(0xFA9BC4)
def branch_five_of(m, o, *_):
    """0xfa9e08([o+0x50], {[o+0x88], [o+0x90], u8 [o+0x98], [o+0x30]})."""
    with m.frame(0x20) as f:
        _branch_args(m, f, o, 0x88, m.u64(o + 0x30))
        m.call_void(m.main + 0xFA9E08, m.u64(o + 0x50), f)


@lifted(0xFA9C04)
def branch_one_of(m, o, *_):
    """0xfa9c44([o+0x60], {[o+0x88], [o+0x90], u8 [o+0x98], [o+0x30]})."""
    with m.frame(0x20) as f:
        _branch_args(m, f, o, 0x88, m.u64(o + 0x30))
        m.call_void(m.main + 0xFA9C44, m.u64(o + 0x60), f)


@lifted(0xFA9C90)
def branch_copy_of(m, o, *_):
    """0xfa9d44([o+0x58], {[o+0x88], [o+0x90], u8 [o+0x98], the reference 0xfa9da8 gives (released at
    once), [o+0x30]})."""
    with m.frame(0x40) as f:
        _branch_args(m, f, o, 0x88)
        m.put(f + 0x20, 8, m.u64(o + 0x30))
        r = f + 0x30
        m.call_sret(m.main + 0xFA9DA8, r, m.u64(o + 0x88))
        x = m.u64(r)
        m.put(f + 0x18, 8, x)
        if x:
            _dec(m, x)
        m.call_void(m.main + 0xFA9D44, m.u64(o + 0x58), f)


@lifted(0xFA9B60)
def make_branches(m, o, src, *_):
    """o+0x88..+0xa8 = src's four words, the RNG [o+0x30] seeded (0xfa9ba8 with [src+0x18]), then
    0xfa9bc4, 0xfa9c90 and 0xfa9c04."""
    w = [m.u64(src + 8 * i) for i in range(4)]
    m.put(o + 0x98, 8, w[2]); m.put(o + 0xA0, 8, w[3]); m.put(o + 0x88, 8, w[0]); m.put(o + 0x90, 8, w[1])
    m.call_void(m.main + 0xFA9BA8, m.u64(o + 0x30), w[3])
    m.call_void(m.main + 0xFA9BC4, o)
    m.call_void(m.main + 0xFA9C90, o)
    return _tail(m, m.main + 0xFA9C04, o)


# --- the per-branch item store (0xfaad84) ----------------------------------------------------------

RNG_SEED = (0x0F4B17A579F18960, 0x82A2B175229D6A5B)     # the RNG object's two state words


def _random(m, dst, n):
    """nn::crypto::GenerateCryptographicallyRandomBytes (0x343dd20): the bytes come from the Machine's
    random_bytes(n)."""
    source = getattr(m, "random_bytes", None)
    if source is None:
        raise UnliftedCall("no random byte source: main+0x343dd20")
    m.write(dst, bytes(source(n))[:n].ljust(n, b"\0"))


@lifted(0x343C280)
def get_system_tick(m, *_):
    """nn::os::GetSystemTick: the Machine's tick()."""
    tick = getattr(m, "tick", None)
    if tick is None:
        raise UnliftedCall("no system tick: main+0x343c280")
    return tick()


def _owned_base(m, o):
    """The owned-object base: +0x10 0, u32 +0x18 0, vtable [0x46d66f8]+0x10. Returns the thread's
    current owner."""
    m.put(o + 0x10, 8, 0); m.put(o + 0x18, 4, 0)
    m.put(o, 8, _vt(m, 0x46D66F8))
    return _tls_top(m)


@lifted(0xFACE64)
def construct_item(m, o, *_):
    """An item (class 0x44ed908): +8 the current owner, +0x30 a referenced 0x88-byte random source
    (vtable [0x46e25b0], seeded with 8 random bytes, built from the owner), +0x58 a held 0x68-byte
    record (class 0x44ed970) with an RNG at +0x40; u8 +0x88 5."""
    top = _owned_base(m, o)
    m.put(o + 0x28, 4, 0)
    m.put(o, 8, m.main + 0x44ED908); m.put(o + 8, 8, top)
    m.put(o + 0x20, 8, m.main + 0x44ED940)
    m.write(o + 0x30, bytes(0x58))
    m.put(o + 0x88, 1, 5)

    def source(p):
        owner = _owned_base(m, p)
        vt = m.u64(m.main + 0x46E25B0)
        _stores(m, p, ((8, 8, owner), (0x28, 4, 0), (0x30, 8, 0), (0x38, 1, 5), (0x40, 8, 0), (0x48, 8, 0),
                       (0, 8, vt + 0x10), (0x20, 8, vt + 0x518), (0x50, 8, 0), (0x58, 8, 0),
                       (0x70, 8, RNG_SEED[1]), (0x78, 8, 0), (0x80, 8, 0), (0x60, 8, _vt(m, 0x46DCD38)),
                       (0x68, 8, RNG_SEED[0])))
        with m.frame(0x10) as f:
            _random(m, f, 8)
            r = m.u64(f)
        _stores(m, p, ((0x78, 8, r), (0x80, 8, 0), (0x68, 8, r), (0x70, 8, RNG_SEED[1])))
    p = _create(m, top, 0x88, source)
    _inc(m, p)
    old = m.u64(o + 0x30)
    m.put(o + 0x30, 8, 0)
    if old:
        _dec(m, old)
    m.put(o + 0x30, 8, p)

    def record(q):
        _stores(m, q, ((0, 8, m.main + 0x44ED970), (8, 8, 0), (0x10, 8, 0), (0x18, 8, 0), (0x18, 2, 0),
                       (0x20, 8, 0), (0x28, 8, 0), (0x60, 8, 0), (0x30, 8, 0), (0x38, 8, 0),
                       (0x40, 8, _vt(m, 0x46DCD38)), (0x48, 8, RNG_SEED[0]), (0x50, 8, RNG_SEED[1]),
                       (0x58, 8, 0)))
    _own(m, o + 0x58, m.u64(o + 8), 0x68, record, dtor=0)


def _pouch(m, o, got):
    m.call_void(m.main + 0xFACE64, o)
    vt = m.u64(m.main + got)
    _stores(m, o, ((0x98, 8, 0), (0xB0, 8, 0), (0xA4, 8, 0), (0xA0, 2, 0x1212), (0xAC, 2, 0x1212),
                   (0xC4, 2, 0x1212), (0, 8, vt + 0x10), (0x20, 8, vt + 0x50), (0xB8, 2, 0x1212),
                   (0xBC, 8, 0)))


POUCHES = ((0xFAC938, 0xFAC860, 0x46E2588), (0xFACA6C, 0xFAC994, 0x46E2590), (0xFACBA0, 0xFACAC8, 0x46E2598),
           (0xFACCD4, 0xFACBFC, 0x46E25A0), (0xFACE08, 0xFACD30, 0x46E25A8), (0xFAD998, 0xFAD860, 0x46E2F60))


def _register_pouches():
    for ctor, create, got in POUCHES:
        def construct(m, o, *_, got=got):
            """An item with vtable [got] and four u16 0x1212 at +0xa0, +0xac, +0xb8, +0xc4."""
            _pouch(m, o, got)
        lifted(ctor)(construct)

        def make(m, alloc, *_, ctor=ctor):
            """Create a zeroed 0xc8-byte pouch item."""
            return _create_zeroed(m, alloc, 0xC8, ctor)
        lifted(create)(make)


_register_pouches()


def _item_kind(got):
    def build(m, p):
        m.write(p, bytes(0x90))
        m.call_void(m.main + 0xFACE64, p)
        vt = m.u64(m.main + got)
        m.put(p + 0x20, 8, vt + 0x50)
        m.put(p, 8, vt + 0x10)
    return build


@lifted(0xFABD50)
def create_fabd50(m, alloc, *_):
    """Create a 0x90-byte item with vtable [0x46e25b8]."""
    return _create(m, alloc, 0x90, lambda p: _item_kind(0x46E25B8)(m, p))


@lifted(0xFAC178)
def create_fac178(m, alloc, *_):
    """Create a 0x90-byte item with vtable [0x46e25c0]."""
    return _create(m, alloc, 0x90, lambda p: _item_kind(0x46E25C0)(m, p))


def _make_ref(m, maker, alloc):
    """*x8 = maker(alloc) with a reference added."""
    out = m.x8
    r = m.call(m.main + maker, alloc)
    m.put(out, 8, r)
    if r:
        _inc(m, r)
    return r


for _addr, _maker in ((0xFABC58, 0xFABD50), (0xFAC080, 0xFAC178), (0xFAB50C, 0xFAC268), (0xFAB578, 0xFAB8EC),
                      (0xFAB5E4, 0xFABA14), (0xFAB650, 0xFABE40), (0xFA9134, 0xFA928C)):
    def _ref(m, alloc, *_, maker=_maker):
        """*x8 = a new object (Create) with a reference added."""
        return _make_ref(m, maker, alloc)
    lifted(_addr)(_ref)


def _hold_ref(m, maker, alloc, mover, slot):
    """mover(slot, &ref) with ref = maker(alloc) referenced; what is left in ref is released."""
    with m.frame(0x10) as f:
        m.call_sret(m.main + maker, f, alloc)
        m.call_void(m.main + mover, slot, f)
        x = m.u64(f)
        if x:
            _dec(m, x)


@lifted(0xFABB3C)
def construct_fabb3c(m, o, *_):
    """Class 0x44ee0f8: +8 the current owner, u8 +0x50 5, +0x38 a referenced 0xfabd50 item (0xfabcc4)."""
    top = _owned_base(m, o)
    _stores(m, o, ((0x30, 4, 0), (0, 8, m.main + 0x44EE0F8), (8, 8, top), (0x20, 8, m.main + 0x44EE140),
                   (0x28, 8, 0), (0x38, 8, 0), (0x50, 1, 5), (0x40, 8, 0), (0x48, 8, 0)))
    m.write(o + 0x58, bytes(0x40))
    _hold_ref(m, 0xFABC58, top, 0xFABCC4, o + 0x38)


@lifted(0xFABF68)
def construct_fabf68(m, o, *_):
    """Class 0x44ee1e0: +8 the current owner, u8 +0x50 5, +0x38 a referenced 0xfac178 item (0xfac0ec)."""
    top = _owned_base(m, o)
    _stores(m, o, ((0x30, 4, 0), (0, 8, m.main + 0x44EE1E0), (8, 8, top), (0x40, 8, 0),
                   (0x20, 8, m.main + 0x44EE228), (0x28, 8, 0), (0x38, 8, 0), (0x68, 8, 0), (0x48, 8, 0),
                   (0x50, 8, 0), (0x50, 1, 5), (0x58, 8, 0), (0x60, 8, 0)))
    _hold_ref(m, 0xFAC080, top, 0xFAC0EC, o + 0x38)


@lifted(0xFAC538)
def construct_fac538(m, o, *_):
    """Class 0x44ed890: +8 the current owner, u8 +0x90 5, five referenced pouches at +0x38..+0x58
    (0xfac860, 0xfac994, 0xfacac8, 0xfacbfc, 0xfacd30)."""
    top = _owned_base(m, o)
    _stores(m, o, ((0x30, 4, 0), (0, 8, m.main + 0x44ED890), (8, 8, top), (0x20, 8, m.main + 0x44ED8D8),
                   (0x28, 8, 0)))
    m.write(o + 0x38, bytes(0x58))
    m.put(o + 0x90, 1, 5)
    m.write(o + 0xA8, bytes(0x64))
    _stores(m, o, ((0x110, 4, 0), (0x114, 2, 0), (0x98, 8, 0), (0x9D, 8, 0)))
    owner = top
    for slot, maker in ((0x38, 0xFAC860), (0x40, 0xFAC994), (0x48, 0xFACAC8), (0x50, 0xFACBFC), (0x58, 0xFACD30)):
        x = m.call(m.main + maker, owner)
        if x:
            _inc(m, x)
        old = m.u64(o + slot)
        m.put(o + slot, 8, 0)
        if old:
            _dec(m, old)
        m.put(o + slot, 8, x)
        owner = m.u64(o + 8)


for _addr, _size, _ctor in ((0xFABA14, 0x98, 0xFABB3C), (0xFABE40, 0x70, 0xFABF68), (0xFAB8EC, 0x118, 0xFAC538),
                            (0xFA928C, 0xF0, 0xFAAD84)):
    def _make(m, alloc, *_, size=_size, ctor=_ctor):
        """Create an object of the given size with its constructor."""
        return _create(m, alloc, size, lambda p: m.call_void(m.main + ctor, p))
    lifted(_addr)(_make)


@lifted(0xFAAD84)
def construct_store(m, o, *_):
    """The item store (class 0x44ed7c0, 0xf0 bytes): +8 the current owner, a light event at +0x78,
    0xfab500 on +0xe0, referenced members +0x68 (0xfab50c), +0x50 (0xfab578), +0x58 (0xfab5e4), +0x60
    (0xfab650), and a held RNG at +0x30."""
    top = _owned_base(m, o)
    _stores(m, o, ((0x28, 4, 0), (0, 8, m.main + 0x44ED7C0), (8, 8, top), (0x20, 8, m.main + 0x44ED7F8)))
    m.write(o + 0x30, bytes(0x48))
    m.put(o + 0x84, 4, 1)
    m.call_void(m.main + 0x343E6D0, o + 0x78, 0, 1)
    _stores(m, o, ((0xA0, 8, 0), (0x88, 8, 0), (0x90, 8, 0), (0x98, 1, 5), (0xA8, 1, 0), (0xD0, 8, 0),
                   (0xD8, 1, 5), (0xB0, 8, 0), (0xB8, 8, 0), (0xC0, 8, 0), (0xC8, 8, 0)))
    m.call_void(m.main + 0xFAB500, o + 0xE0)
    for maker, mover, slot in ((0xFAB50C, 0xFAB6BC, 0x68), (0xFAB578, 0xFAB748, 0x50), (0xFAB5E4, 0xFAB7D4, 0x58),
                               (0xFAB650, 0xFAB860, 0x60)):
        _hold_ref(m, maker, m.u64(o + 8), mover, o + slot)

    def rng(p):
        _stores(m, p, ((0, 8, _vt(m, 0x46DCD38)), (8, 8, RNG_SEED[0]), (0x10, 8, RNG_SEED[1]), (0x18, 8, 0),
                       (0x20, 8, 0)))
    _own(m, o + 0x30, m.u64(o + 8), 0x28, rng)


@lifted(0xFA98B8)
def make_store_branches(m, o, x, *_):
    """0xfa9b60([o+0x48], {[o+0x30], [o+0x38], u8 [o+0xe2], x}); then when rule bit 0x400 is set: a
    new item store at o+0x50 (0xfa9134 / 0xfa9200) branched with flag 1, an extra copy (0xfad860)
    branched and passed to [o+0x50] (0xfaac98); else when the main module's u32 +0x36c is 2: the
    store and its branches only."""
    with m.frame(0x30) as f:
        _branch_args(m, f, o, 0x30)
        m.put(f + 0x10, 1, m.u8(o + 0xE2)); m.put(f + 0x18, 8, x)
        m.call_void(m.main + 0xFA9B60, m.u64(o + 0x48), f)

        def store():
            m.call_sret(m.main + 0xFA9134, f, m.u64(o + 8))
            m.call_void(m.main + 0xFA9200, o + 0x50, f)
            r = m.u64(f)
            if r:
                _dec(m, r)
            _branch_args(m, f, o, 0x30)
            m.put(f + 0x10, 1, 1); m.put(f + 0x18, 8, x)
            m.call_void(m.main + 0xFA9B60, m.u64(o + 0x50), f)
        if m.call(m.main + 0xFA9B4C, m.u64(o + 0x30), 0x400) & 1:
            store()
            c = m.call(m.main + 0xFAD860, m.u64(o + 8))
            if c:
                _inc(m, c)
            _branch_args(m, f, o, 0x30)
            m.put(f + 0x10, 1, 1)
            m.call_void(m.main + 0xFA9EDC, c, f)
            g = f + 0x28
            m.put(g, 8, c)
            if c:
                _inc(m, c)
            m.call_void(m.main + 0xFAAC98, m.u64(o + 0x50), g)
            r = m.u64(g)
            if r:
                _dec(m, r)
            if c:
                _dec(m, c)
        elif m.u32(m.u64(o + 0x38) + 0x36C) == 2:
            store()


@lifted(0xFA94C8)
def start_timer(m, o, i, v, *_):
    """Timer i (< 3) of o, entry o + 0x28*i: +0x50 the u32 v, +0x30 the start time (ns, from
    GetSystemTick); when neither +0x49 nor +0x4a is set it is closed at once into +0x40 / +0x38. u8
    +0x48 and +0x49 end set."""
    i = (i & M32) - ((i & M32) >> 31 << 32)
    if i > 2:
        return
    e = o + 0x28 * i
    m.put(e + 0x30, 8, 0); m.put(e + 0x38, 8, 0); m.put(e + 0x40, 8, 0); m.put(e + 0x50, 8, v & M32)
    m.put(e + 0x48, 1, 0)
    now = lambda: m.call(m.main + 0x343D5B0, m.call(m.main + 0x343C280))
    m.put(e + 0x30, 8, now())
    m.put(e + 0x48, 1, 1)
    if not m.u8(e + 0x49) and not m.u8(o + 0x28 * i + 0x4A):
        t = now()
        m.put(e + 0x40, 8, t)
        m.put(e + 0x38, 8, t - m.u64(e + 0x30) + m.u64(e + 0x38))
        m.put(e + 0x30, 8, 0)
    m.put(e + 0x49, 1, 1)


@lifted(0xFA958C)
def make_timers_ref(m, alloc, *_):
    """*x8 = a new timer block (0xfa9684) with a reference added."""
    return _make_ref(m, 0xFA9684, alloc)


@lifted(0xFA93B4)
def make_timers(m, o, *_):
    """o+0x90 holds a new timer block (0xfa95f8), cleared (0xfa949c), its timers started with
    0x126b004 and 0xfa91f8 of [o+0x30] and u16 [[o+0x30]+0x8e]."""
    _hold_ref(m, 0xFA958C, m.u64(o + 8), 0xFA95F8, o + 0x90)
    m.call_void(m.main + 0xFA949C, m.u64(o + 0x90))
    m.call_void(m.main + 0xFA94C8, m.u64(o + 0x90), 0, m.call(m.main + 0x126B004, m.u64(o + 0x30)))
    m.call_void(m.main + 0xFA94C8, m.u64(o + 0x90), 1, m.call(m.main + 0xFA91F8, m.u64(o + 0x30)))
    return _tail(m, m.main + 0xFA94C8, m.u64(o + 0x90), 2, m.u16(m.u64(o + 0x30) + 0x8E))


@lifted(0xFA8BEC)
def construct_side(m, o, a1, a2, p3, p4, _x5, b6, b7, s0, s1, s2, *_):
    """A side's battle state (class 0x44ff198, 0x138 bytes): +0x30 / +0x38 a1 / a2, references to *p3
    and *p4 at +0x78 / +0x80, an RNG at +0xa8 (seeded from s1 by 0xfa9ba8), u8 +0xe2..+0xe4 = b6, b7,
    s0, an item store at +0x48 (0xfa9134), +0x40 a 0x127d65c object, +0x68 / +0x70 two 0xfae198
    objects (flag s2), the timers (0xfa93b4), 0xfa91a0, and its branches (0xfa98b8 with s1)."""
    top = _owned_base(m, o)
    _stores(m, o, ((0x28, 4, 0), (0, 8, m.main + 0x44FF198), (8, 8, top), (0x20, 8, m.main + 0x44FF1D0),
                   (0x70, 8, 0), (0x30, 8, a1), (0x38, 8, a2), (0x40, 8, 0), (0x48, 8, 0), (0x50, 8, 0),
                   (0x58, 8, 0), (0x60, 8, 0), (0x68, 8, 0)))
    for slot, p in ((0x78, p3), (0x80, p4)):
        x = m.u64(p)
        m.put(o + slot, 8, x)
        if x:
            _inc(m, x)
    _stores(m, o, ((0xA8, 8, _vt(m, 0x46DCD38)), (0xA0, 2, 0), (0x108, 8, 0), (0x110, 8, 0), (0x98, 8, 0),
                   (0x120, 8, 0), (0x128, 8, 0), (0xE0, 2, 0), (0xB0, 8, RNG_SEED[0]), (0xB8, 8, RNG_SEED[1]),
                   (0xE2, 1, b6), (0xE3, 1, b7), (0xE4, 1, s0), (0x128, 2, 0x505), (0x108, 2, 0x505),
                   (0xE5, 2, 0), (0x130, 2, 1), (0x118, 8, 0), (0x132, 1, 0), (0x134, 4, 0), (0x88, 8, 0),
                   (0x90, 8, 0), (0xC0, 8, 0), (0xC8, 8, 0), (0xD0, 8, m.main + 0xF59E54), (0xD8, 8, 0),
                   (0xF8, 8, 0), (0x100, 8, 0), (0xE8, 8, 0), (0xF0, 8, 0)))
    _hold_ref(m, 0xFA9134, m.u64(o + 8), 0xFA9200, o + 0x48)
    with m.frame(0x20) as f:
        x = m.call(m.main + 0x127D65C, f, m.u64(o + 8))
        if x:
            _inc(m, x)
        old = m.u64(o + 0x40)
        m.put(o + 0x40, 8, 0)
        if old:
            _dec(m, old)
        m.put(o + 0x40, 8, x)
        flag = f + 0x10
        m.put(flag, 1, s2)
        for slot in (0x68, 0x70):
            y = m.call(m.main + 0xFAE198, f, m.u64(o + 8), flag)
            if y:
                _acquire(m, y)
            old = m.u64(o + slot)
            m.put(o + slot, 8, 0)
            if old:
                _release(m, old)
            m.put(o + slot, 8, y)
        m.call_void(m.main + 0xFA93B4, o)
        m.call_void(m.main + 0xFA91A0, o)
        m.call_void(m.main + 0xFA9BA8, o + 0xA8, s1)
        m.put(f, 8, m.u64(o + 0x30))
        m.call_void(m.main + 0xFA9128, m.u64(o + 0x40), f)
        m.call_void(m.main + 0xFA98B8, o, s1)


@lifted(0xFA70BC)
def create_side(m, alloc, p1, p2, p3, p4, p5, p6, p7, s0, s1, s2, *_):
    """Create a side state (0x138 bytes, 0xfa8bec) from the pointed-to arguments, *p3 and *p4 held
    referenced for the call."""
    stack = _tls_stack(m)
    _push(m, stack, alloc)
    o = m.vcall(alloc, 0x10, 0x138, 8)
    if not o:
        raise UnliftedCall("abort: allocation failed in Create")
    a1, a2 = m.u64(p1), m.u64(p2)
    with m.frame(0x10) as f:
        for i, p in enumerate((p3, p4)):
            x = m.u64(p)
            m.put(f + 8 * i, 8, x)
            if x:
                _inc(m, x)
        m.call_void(m.main + 0xFA8BEC, o, a1, a2, f, f + 8, m.u8(p5), m.u32(p6), m.u8(p7), m.u32(s0),
                    m.u64(s1), m.u8(s2))
        for i in (1, 0):
            x = m.u64(f + 8 * i)
            if x:
                _dec(m, x)
    m.put(o + 0x18, 4, 0x80138)
    m.put(o + 8, 8, alloc); m.put(o + 0x10, 8, o)
    _pop(m, stack)
    return o


@lifted(0xFA6270)
def create_side_ref(m, alloc, p1, p2, p3, p4, p5, p6, p7, s0, s1, s2, *_):
    """*x8 = a new side state (0xfa70bc) with a reference added."""
    out = m.x8
    r = m.call(m.main + 0xFA70BC, alloc, p1, p2, p3, p4, p5, p6, p7, s0, s1, s2)
    m.put(out, 8, r)
    if r:
        _inc(m, r)
    return r


@lifted(0xFA6134)
def make_side(m, o, side, flag, *_):
    """*x8 = side `side`'s state: built (0xfa6270) from [o], o+0x48, o+0x58, the resource maps' entries
    for it ([o+0x60]: 0xfa6a44, 0xfa6cc8), o+0x1c, the side, the flag, o+0x20, o+0x38, o+0x40; the
    0xfa6a44 entry is pointed at it (0xfa6268)."""
    out = m.x8
    with m.frame(0x20) as f:
        a, b, ident, fl = f, f + 8, f + 0x10, f + 0x18
        m.put(ident, 4, side & M32); m.put(fl, 1, flag)
        m.call_sret(m.main + 0xFA6A44, a, m.u64(o + 0x60), side & M32)
        m.call_sret(m.main + 0xFA6CC8, b, m.u64(o + 0x60), side & M32)
        m.x8 = out
        m.call_void(m.main + 0xFA6270, m.u64(o), o + 0x48, o + 0x58, a, b, o + 0x1C, ident, fl, o + 0x20,
                    o + 0x38, o + 0x40)
        if m.u64(a):
            m.call_void(m.main + 0xFA6268, m.u64(a), m.u64(out))
        for p in (b, a):
            x = m.u64(p)
            if x:
                _dec(m, x)


@lifted(0xFB0E7C)
def make_side_if(m, o, side, held, *_):
    """*x8 = 0xfa6134(o, side, 1) when 0xe7e2a0(u32 [o+0x18], u8 [o+0x1d], side) selects the side and
    `held` is 0, else 0."""
    out = m.x8
    r = m.call(m.main + 0xE7E2A0, m.u32(o + 0x18), m.u8(o + 0x1D), side & M32)
    if r & 1 and not held:
        m.x8 = out
        return _tail(m, m.main + 0xFA6134, o, side & M32, 1)
    m.put(out, 8, 0)
    return r


@lifted(0xFB0A60)
def make_sides(m, o, s, *_):
    """For sides 0..4: the state 0xfb0e7c makes (unless s+8+8*side holds one) referenced at
    s+0x30+8*side and registered with [s] (0x18b7db4)."""
    with m.frame(0x10) as f:
        for side in range(5):
            m.x8 = f
            m.call_void(m.main + 0xFB0E7C, o, side, m.u64(s + 8 + 8 * side))
            x = m.u64(f)
            if not x:
                continue
            _inc(m, x)
            slot = s + 0x30 + 8 * side
            old = m.u64(slot)
            m.put(slot, 8, x)
            if old:
                _dec(m, old)
            x = m.u64(f)
            m.call_void(m.main + 0x18B7DB4, m.u64(s), x)
            if x:
                _dec(m, x)


@lifted(0xFA8974)
def do_rehash_fa8974(m, table, n, *_):
    """__do_rehash of 0xfa66b4's u32 map (bucket arrays aligned 8, freed through 0x151aa54)."""
    _do_rehash(m, table, n, 8, 4)


@lifted(0xFA6FB8)
def rehash_fa6fb8(m, table, want, *_):
    """rehash(want) of 0xfa66b4's map."""
    _rehash(m, table, want, 0xFA8974)


@lifted(0xFA66B4)
def side_slot(m, table, key_ptr, *_):
    """operator[] of an unordered_map<u32, 0x20-byte value> (node 0x38 from 0xfa68c4): the value
    (node +0x18) of the u32 at key_ptr."""
    key = m.u32(key_ptr)
    node = _find(m, table, key, 4)
    if node:
        return node + 0x18
    with m.frame(0x20) as f:
        m.put(f, 8, key_ptr)
        m.call_sret(m.main + 0xFA68C4, f + 8, table, key, f)
        node = m.u64(f + 8)
    _insert(m, table, node, key, 0xFA8974)
    return node + 0x18


@lifted(0xFA62F4)
def set_side_entry(m, o, side, src, *_):
    """The value for `side` in the map at o+0x1a0: its two weak handles released and the four words
    cleared, then +0 = *src (0xfa6424), +8 = src[1] (0xfa6560), +0x10 = src[2]."""
    table = o + 0x1A0
    with m.frame(0x10) as f:
        m.put(f, 4, side & M32)
        v = m.call(m.main + 0xFA66B4, table, f)
        for off in (0, 8):
            x = m.u64(v + off)
            m.put(v + off, 8, 0)
            if x:
                _release(m, x)
        m.put(v + 0x10, 8, 0); m.put(v + 0x18, 8, 0)
        m.call_void(m.main + 0xFA6424, m.call(m.main + 0xFA66B4, table, f), m.u64(src))
        m.call_void(m.main + 0xFA6560, m.call(m.main + 0xFA66B4, table, f) + 8, m.u64(src + 8))
        x = m.u64(src + 0x10)
        m.put(m.call(m.main + 0xFA66B4, table, f) + 0x10, 8, x)


@lifted(0xFA5FF8)
def record_side(m, o, side, src, *_):
    """For side < 5 (or 0xff): o's entry for it set (0xfa62f4) from {*src, src[1], the side's
    0x14b5634 value of 0xe7e284([o+0x38]) (0 for 0xff)}."""
    s = (side & M32) - ((side & M32) >> 31 << 32)
    if s >= 5 and s != 0xFF:
        return
    with m.frame(0x20) as f:
        m.write(f, bytes(0x20))
        if s <= 4:
            m.put(f + 0x10, 8, m.call(m.main + 0x14B5634, m.call(m.main + 0xE7E284, m.u64(o + 0x38)), side & M32))
        m.call_void(m.main + 0xFA6424, f, m.u64(src))
        m.call_void(m.main + 0xFA6560, f + 8, m.u64(src + 8))
        m.call_void(m.main + 0xFA62F4, o, side & M32, f)
        for off in (8, 0):
            x = m.u64(f + off)
            if x:
                _release(m, x)


def _source_call(m, o, key, flag, slot):
    """*x8 = the source [o+0x50] (flag set) or [o+0x48] answering vf `slot`(key), held with a weak
    reference for the call; 0 without a source."""
    out = m.x8
    src = m.u64(o + (0x50 if flag & 1 else 0x48))
    if not src:
        m.put(out, 8, 0)
        return
    _acquire(m, src)
    m.x8 = out
    m.vcall_void(src, slot, key)
    _release(m, src)


@lifted(0xFA766C)
def source_68(m, o, key, flag, *_):
    """vf 0x68 of o's source for the flag."""
    _source_call(m, o, key, flag, 0x68)


@lifted(0xFA77D4)
def source_70(m, o, key, flag, *_):
    """vf 0x70 of o's source for the flag."""
    _source_call(m, o, key, flag, 0x70)


def _wrapper(m, o, cls):
    """A weak object (class `cls`, 0x50 bytes) holding a weakly referenced 0xfa7f10 object at +0x48."""
    _weak_base(m, o)
    m.put(o, 8, m.main + cls); m.put(o + 0x20, 8, m.main + cls + 0x80); m.put(o + 0x28, 8, m.main + cls + 0xD0)
    m.put(o + 0x40, 8, 0); m.put(o + 0x48, 8, 0)
    with m.frame(0x10) as f:
        y = m.call(m.main + 0xFA7F10, f, m.u64(o + 8))
    if y:
        _acquire(m, y)
    old = m.u64(o + 0x48)
    m.put(o + 0x48, 8, 0)
    if old:
        _release(m, old)
    m.put(o + 0x48, 8, y)


@lifted(0xFA7CD4)
def construct_wrapper_ff268(m, o, *_):
    """Weak wrapper of class 0x44ff268."""
    _wrapper(m, o, 0x44FF268)


@lifted(0xFA83D4)
def construct_wrapper_ed698(m, o, *_):
    """Weak wrapper of class 0x44ed698."""
    _wrapper(m, o, 0x44ED698)


def _wrap(m, o, pref, ctor, assign):
    """*x8 = a new 0x50-byte wrapper (Create from [o+8], `ctor`) with a weak reference, its +0x40 set
    from *pref through `assign`."""
    out = m.x8
    w = _create(m, m.u64(o + 8), 0x50, lambda p: m.call_void(m.main + ctor, p))
    m.put(out, 8, w)
    _acquire(m, w)
    with m.frame(0x10) as f:
        m.put(f, 8, 0)
        m.call_void(m.main + assign, f, m.u64(pref))
        m.call_void(m.main + assign, m.u64(out) + 0x40, m.u64(f))
        x = m.u64(f)
        if x:
            _release(m, x)


@lifted(0xFA793C)
def wrap_ff268(m, o, pref, *_):
    """*x8 = a 0x44ff268 wrapper of *pref (0xfa7b98)."""
    _wrap(m, o, pref, 0xFA7CD4, 0xFA7B98)


@lifted(0xFA803C)
def wrap_ed698(m, o, pref, *_):
    """*x8 = a 0x44ed698 wrapper of *pref (0xfa8298)."""
    _wrap(m, o, pref, 0xFA83D4, 0xFA8298)


def _source_pair(m, o, side, flag, first, second):
    """*x8 = {wrapper of source vf 0x68 for key {[o+0x40], first, side}, wrapper of vf 0x70 for
    {[o+0x40], second, side}} (0xfa793c / 0xfa803c), every temporary released."""
    out = m.x8
    fl = flag & 1
    with m.frame(0x60) as f:
        k1, k2, a, b, c, d, t = f, f + 0x10, f + 0x20, f + 0x28, f + 0x30, f + 0x38, f + 0x40
        for k, kind in ((k1, first), (k2, second)):
            m.put(k, 4, m.u32(o + 0x40)); m.put(k + 4, 4, kind); m.put(k + 8, 4, side & M32)
        m.x8 = a
        m.call_void(m.main + 0xFA766C, o, k1, fl)
        m.x8 = b
        m.call_void(m.main + 0xFA77D4, o, k2, fl)
        m.put(out, 8, 0); m.put(out + 8, 8, 0)
        for src, tmp, maker, slot in ((a, c, 0xFA793C, 0), (b, d, 0xFA803C, 8)):
            x = m.u64(src)
            m.put(tmp, 8, x)
            if x:
                _acquire(m, x)
            m.x8 = t
            m.call_void(m.main + maker, o, tmp)
            old = m.u64(out + slot)
            m.put(out + slot, 8, 0)
            if old:
                _release(m, old)
            m.put(out + slot, 8, m.u64(t)); m.put(t, 8, 0)
            x = m.u64(tmp)
            if x:
                _release(m, x)
        for p in (b, a):
            x = m.u64(p)
            if x:
                _release(m, x)


@lifted(0xFA7308)
def source_pair_12(m, o, side, flag, *_):
    """0xfa7308: kinds 1 then 2."""
    _source_pair(m, o, side, flag, 1, 2)


@lifted(0xFA8610)
def source_pair_21(m, o, side, flag, *_):
    """0xfa8610: kinds 2 then 1."""
    _source_pair(m, o, side, flag, 2, 1)


@lifted(0xFA58FC)
def side_sources(m, o, side, flag, *_):
    """*x8 = 0xfa8610([o+8], side, f): f 0 unless u8 [o+0x1c] is set, then (flag + 1) & 0xff < 2
    unless u8 [o+0x2c] is set."""
    if m.u8(o + 0x1C):
        f = 0 if m.u8(o + 0x2C) else int((flag + 1) & 0xFF < 2)
    else:
        f = 0
    return _tail(m, m.main + 0xFA8610, m.u64(o + 8), side & M32, f)


@lifted(0xFA52B0)
def make_side_states(m, o, s, *_):
    """For each selected side (0xe7e2a0): its state (0xfa6134; the host side with flag u8 [o+0x30],
    others only when u8 [o+0x2c] and 0xfa5f84 allow) referenced at s+8+8*side, its source pairs
    0xfa7308 / 0xfa58fc wired (0xfa58c8, 0xfa5ff8 on [s]) and every handle added to [o+0x10]
    (0xfa5930)."""
    with m.frame(0x70) as f:
        L, P, Q, c = f, f + 0x10, f + 0x20, f + 0x30
        for side in range(5):
            m.put(L, 8, 0)
            if not m.call(m.main + 0xE7E2A0, m.u32(o + 0x18), m.u8(o + 0x1D), side) & 1:
                continue
            if side == m.u32(o + 0x24):
                flag = m.u8(o + 0x30)
            elif not m.u8(o + 0x2C):
                continue
            elif not m.call(m.main + 0xFA5F84, m.u32(o + 0x18), m.u8(o + 0x1C), m.u8(o + 0x1D),
                            m.u32(o + 0x28), side) & 1:
                continue
            else:
                flag = 1
            m.x8 = L
            m.call_void(m.main + 0xFA6134, o, side, flag)
            x = m.u64(L)
            if not x:
                continue
            _inc(m, x)
            slot = s + 8 + 8 * side
            old = m.u64(slot)
            m.put(slot, 8, x)
            if old:
                _dec(m, old)
            m.x8 = P
            m.call_void(m.main + 0xFA7308, m.u64(o + 8), side, 0)
            st = m.u64(L)
            w = m.call(m.main + 0xFA58C0, st)
            m.x8 = Q
            m.call_void(m.main + 0xFA58FC, o, side, w)
            m.call_void(m.main + 0xFA58C8, st, Q)
            m.call_void(m.main + 0xFA5FF8, m.u64(s), side, P)
            for src in (P, P + 8, Q, Q + 8):
                y = m.u64(src)
                m.put(c, 8, y)
                if y:
                    _acquire(m, y)
                m.call_void(m.main + 0xFA5930, m.u64(o + 0x10), c)
                y = m.u64(c)
                if y:
                    _release(m, y)
            for p in (Q + 8, Q, P + 8, P):
                y = m.u64(p)
                if y:
                    _release(m, y)
            x = m.u64(L)
            if x:
                _dec(m, x)


def _add_handles(m, dst, words, scratch):
    """0xfa5930(dst, &c) for each handle word, each copy held with a weak reference for the call."""
    for w in words:
        m.put(scratch, 8, w)
        if w:
            _acquire(m, w)
        m.call_void(m.main + 0xFA5930, dst, scratch)
        w = m.u64(scratch)
        if w:
            _release(m, w)


@lifted(0xFA4CF0)
def record_side_sources(m, o, s, *_):
    """For each side without a state in s (s+8+8*side) that 0xe7e2a0 selects: its entry in [s] set
    (0xfa5ff8) from the source pair 0xfa7308([o+8], side, 1) when u8 [o+0x2c], else from {0, 0}; the
    pair's handles added to [o+0x10]. With u8 [o+0x2f] the same for side 0xff (its second handle only
    with u8 [o+0x2e])."""
    with m.frame(0x20) as f:
        P, c = f, f + 0x10
        for side in range(5):
            if m.u64(s + 8 + 8 * side):
                continue
            if not m.call(m.main + 0xE7E2A0, m.u32(o + 0x18), m.u8(o + 0x1D), side) & 1:
                continue
            if m.u8(o + 0x2C):
                m.x8 = P
                m.call_void(m.main + 0xFA7308, m.u64(o + 8), side, 1)
                m.call_void(m.main + 0xFA5FF8, m.u64(s), side, P)
                _add_handles(m, m.u64(o + 0x10), (m.u64(P), m.u64(P + 8)), c)
            else:
                m.put(P, 8, 0); m.put(P + 8, 8, 0)
                m.call_void(m.main + 0xFA5FF8, m.u64(s), side, P)
            for p in (P + 8, P):
                x = m.u64(p)
                if x:
                    _release(m, x)
        if not m.u8(o + 0x2F):
            return
        m.x8 = P
        m.call_void(m.main + 0xFA7308, m.u64(o + 8), 0xFF, 1)
        m.call_void(m.main + 0xFA5FF8, m.u64(s), 0xFF, P)
        words = (m.u64(P), m.u64(P + 8)) if m.u8(o + 0x2E) else (m.u64(P),)
        _add_handles(m, m.u64(o + 0x10), words[:1], c)
        if m.u8(o + 0x2E):
            _add_handles(m, m.u64(o + 0x10), (m.u64(P + 8),), c)
        for p in (P + 8, P):
            x = m.u64(p)
            if x:
                _release(m, x)


# --- the message channel registrations (0x17e5d1c / 0x1842280) --------------------------------------

@lifted(0x343C340)
def lock_mutex(m, mx, *_):
    """nn::os::LockMutex (SDK 0x51e2be0): a recursive mutex its owner holds only counts; otherwise the
    uncontended internal lock (SDK 0x51ed124) stores the thread's handle (ThreadType +0x1b0) at +0x18.
    Count +8, owner +0x10."""
    thread = m.u64(m.tls + 0x1F8)
    if not (m.u8(mx + 1) and m.u64(mx + 0x10) == thread):
        if m.u32(mx + 0x18):
            raise UnliftedCall("contended mutex")
        m.put(mx + 0x18, 4, m.u32(thread + 0x1B0))
    m.put(mx + 8, 4, m.u32(mx + 8) + 1)
    m.put(mx + 0x10, 8, thread)


@lifted(0x343C360)
def unlock_mutex(m, mx, *_):
    """nn::os::UnlockMutex (SDK 0x51e2ca0 / 0x51ed204): the last unlock clears the owner and the lock
    word; a lock word that is not this thread's handle with bit 30 (waiters) needs the kernel."""
    n = (m.u32(mx + 8) - 1) & M32
    m.put(mx + 8, 4, n)
    if n:
        return
    m.put(mx + 0x10, 8, 0)
    word = m.u32(mx + 0x18)
    if word == m.u32(m.u64(m.tls + 0x1F8) + 0x1B0):
        m.put(mx + 0x18, 4, 0)
    elif word & 0x40000000:
        raise UnliftedCall("mutex with waiters")


@lifted(0x343C230)
def memmove(m, dst, src, n, *_):
    m.write(dst, m.read(src, n))
    return dst


@lifted(0x17E5FA8)
def drop_registrations(m, x, key, *_):
    """Under the mutex x+0x7640: every 0x18-byte entry of the array [x+0xf0] (count +0xf8) whose 12-byte
    key equals key's has its buffer (+0x10, size u32 +0xc) freed through [x+8] and is removed."""
    mx = x + 0x7640
    m.call_void(m.main + 0x343C340, mx)
    k = m.read(key, 12)
    i = 0
    while i < m.u64(x + 0xF8):
        e = m.u64(x + 0xF0) + 0x18 * i
        if m.read(e, 12) != k:
            i += 1
            continue
        _free_node(m, m.u64(x + 8), m.u64(e + 0x10), m.u32(e + 0xC), 8)
        base, n = m.u64(x + 0xF0), m.u64(x + 0xF8)
        end = base + 0x18 * n
        if e + 0x18 != end:
            m.call_void(m.main + 0x343C230, e, e + 0x18, end - e - 0x18)
        m.put(x + 0xF8, 8, n - 1)
    return _tail(m, m.main + 0x343C360, mx)


@lifted(0x17E5DA0)
def register_key(m, x, key, *_):
    """Register a 12-byte key with channel x: 0x1893584 when the array [x+0x98] (count +0xa0) already
    holds it, then pushed on x+0x78 (0x17e5e44) and its pending entries dropped (0x17e5fa8)."""
    base, n = m.u64(x + 0x98), m.u64(x + 0xA0)
    k = m.read(key, 12)
    if any(m.read(base + 12 * i, 12) == k for i in range(n)):
        m.call_void(m.main + 0x1893584, x, key)
    m.call_void(m.main + 0x17E5E44, x + 0x78, key)
    return _tail(m, m.main + 0x17E5FA8, x, key)


def _listener(m, o, key, wp, base_ctor, cls):
    m.call_void(m.main + base_ctor, o, key)
    m.put(o, 8, m.main + cls); m.put(o + 0x60, 8, 0)
    m.put(o + 0x20, 8, m.main + cls + 0x80); m.put(o + 0x28, 8, m.main + cls + 0xD0)
    m.put(o + 0x58, 8, 0)
    m.call_void(m.main + 0x17E61DC, o + 0x58, wp)
    e = m.u64(o + 0x58)
    if e and m.u64(e + 0x10):
        return _tail(m, m.main + 0x17E5DA0, m.u64(e + 0x10) - 0x28, key)


@lifted(0x17E5D1C)
def construct_listener_5a8(m, o, key, wp, *_):
    """A key listener (class 0x44925a8, base 0x132f6e8) bound to the weak pair wp (+0x58) and registered
    with its channel."""
    return _listener(m, o, key, wp, 0x132F6E8, 0x44925A8)


@lifted(0x1842280)
def construct_listener_7f8(m, o, key, wp, *_):
    """A key listener (class 0x44927f8, base 0x132f598) bound to wp and registered."""
    return _listener(m, o, key, wp, 0x132F598, 0x44927F8)


for _addr, _ctor in ((0x17E5BDC, 0x17E5D1C), (0x1842140, 0x1842280)):
    def _make_listener(m, alloc, key, wp, *_, ctor=_ctor):
        """Create a 0x68-byte key listener."""
        return _create(m, alloc, 0x68, lambda p: m.call_void(m.main + ctor, p, key, wp))
    lifted(_addr)(_make_listener)

for _addr, _maker in ((0x17E5B18, 0x17E5BDC), (0x184207C, 0x1842140)):
    def _listener_ref(m, alloc, key, wp, *_, maker=_maker):
        """*x8 = a new key listener with a weak reference added."""
        out = m.x8
        r = m.call(m.main + maker, alloc, key, wp)
        m.put(out, 8, r)
        if r:
            _acquire(m, r)
        return r
    lifted(_addr)(_listener_ref)

for _addr, _maker in ((0x17E59A4, 0x17E5B18), (0x1842018, 0x184207C)):
    def _listen(m, src, key, *_, maker=_maker):
        """vf of a message source: *x8 = a listener for key from [src+8], bound to the weak pair of
        [src+0x40] (0x168ddb4, released after)."""
        out = m.x8
        alloc = m.u64(src + 8)
        with m.frame(0x20) as f:
            m.x8 = f
            m.call_void(m.main + 0x168DDB4, m.u64(src + 0x40))
            m.x8 = f + 0x10
            m.call_void(m.main + maker, alloc, key, f)
            m.put(out, 8, m.u64(f + 0x10))
            return _tail(m, m.main + 0x17E5A08, f)
    lifted(_addr)(_listen)


# --- the state copy (0x2898890) -------------------------------------------------------------------------

@lifted(0x2D1F080)
def clone_battler(m, b, data, *_):
    """vf 0x70 of a battler: *x8 = a new 0x720-byte battler (Create from [b+8], 0xfa21a8(p, data,
    [b+0x708]), class 0x44fbcb0) with a weak reference, given b's state (vf 0x7e8), its parameter
    object and fields (0x2a10a68) and +0x710..+0x716, +0x71c."""
    out = m.x8
    alloc = m.u64(b + 8)
    owner = m.u64(b + 0x708)

    def build(p):
        m.call_void(m.main + 0xFA21A8, p, data, owner)
        cls = m.main + 0x44FBCB0
        _stores(m, p, ((0x71C, 4, 0), (0x710, 8, 0), (0x20, 8, cls + 0x828), (0x28, 8, cls + 0x878),
                       (0x40, 8, cls + 0x8D0), (0x718, 2, 0), (0, 8, cls)))
    p = _create(m, alloc, 0x720, build)
    _acquire(m, p)
    m.vcall_void(p, 0x7E8, b)
    r = m.call(m.main + 0x2A10A68, p + 0x48, b + 0x48)
    m.put(p + 0x710, 2, m.u16(b + 0x710)); m.put(p + 0x712, 2, m.u16(b + 0x712))
    m.put(p + 0x714, 1, m.u8(b + 0x714)); m.put(p + 0x715, 1, m.u8(b + 0x715))
    m.put(p + 0x71C, 4, m.u32(b + 0x71C))
    m.put(out, 8, p)
    return r


@lifted(0xF79FE4)
def copy_container(m, dst, src, *_):
    """Battler container copy-assign: dst's id -> battler map (+0x140) emptied (weak handles released,
    0x20-byte nodes freed) and refilled with clones of src's battlers (vf 0x70 with [[dst+0x18]+0x70]),
    the five side lists (+0x28.., counts +0x58, +0x90, +0xc8, +0x100, +0x138) rebuilt from the ids
    (vf 0x98, 0xf21c94), +0x20 copied."""
    if m.u64(dst + 0x198):
        node = m.u64(dst + 0x170)
        while node:
            nxt = m.u64(node)
            w = m.u64(node + 0x18)
            if w:
                _release(m, w)
            _free_node(m, m.u64(dst + 0x178), node, 0x20, 8)
            node = nxt
        m.put(dst + 0x170, 8, 0)
        for i in range(m.u64(dst + 0x148)):
            m.put(m.u64(dst + 0x140) + 8 * i, 8, 0)
        m.put(dst + 0x198, 8, 0)
    with m.frame(0x10) as f:
        node = m.u64(src + 0x170)
        while node:
            b = m.u64(node + 0x18)
            if b:
                m.x8 = f
                m.vcall_void(b, 0x70, m.u64(m.u64(dst + 0x18) + 0x70))
                slot = m.call(m.main + 0xFA1B68, dst + 0x140, node + 0x10)
                old = m.u64(slot)
                m.put(slot, 8, 0)
                if old:
                    _release(m, old)
                m.put(slot, 8, m.u64(f)); m.put(f, 8, 0)
            node = m.u64(node)
    for cnt, arr in ((0x58, 0x28), (0x90, 0x60), (0xC8, 0x98), (0x100, 0xD0), (0x138, 0x108)):
        m.put(dst + cnt, 1, 0)
        m.write(dst + arr, bytes(0x30))
        for j in range(m.u8(src + cnt)):
            b = m.u64(src + arr + 8 * j)
            x = m.call(m.main + 0xF21C94, dst, m.vcall(b, 0x98) & M32)
            k = m.u8(dst + cnt)
            m.put(dst + cnt, 1, k + 1)
            m.put(dst + arr + 8 * k, 8, x)
    m.put(dst + 0x20, 8, m.u64(src + 0x20))


def _rotl64(x, k):
    return ((x << k) | (x >> (64 - k))) & M64


@lifted(0xF77C04)
def copy_main_module(m, dst, src, *_):
    """Main module copy-assign: each member copied from src's (containers, maps, tables, flags), the
    RNG [+0x10] reseeded from src's seed and advanced by its draw count (xoroshiro128+)."""
    d = lambda off: m.u64(dst + off)
    s = lambda off: m.u64(src + off)
    m.call_void(m.main + 0xF79FE4, d(0x30), s(0x30))
    m.call_void(m.main + 0xF77F08, d(0x50), s(0x50))
    m.write(d(0x70) + 8, m.read(s(0x70) + 8, 0x420))
    for off, fn in ((0x90, 0xF79BE8), (0xB0, 0xF79260), (0xD0, 0xF78964), (0xF0, 0xF7842C), (0x110, 0xF78E88)):
        m.call_void(m.main + fn, d(off), s(off))
    m.put(d(0x130) + 8, 4, m.u32(s(0x130) + 8))
    m.write(d(0x130) + 0xC, m.read(s(0x130) + 0xC, 0x12C0))
    m.put(d(0x150) + 0x10, 4, m.u32(s(0x150) + 0x10)); m.put(d(0x150) + 8, 8, m.u64(s(0x150) + 8))
    m.call_void(m.main + 0xF79060, d(0x170), s(0x170))
    m.put(d(0x190) + 8, 4, m.u32(s(0x190) + 8))
    a, b = s(0x1B0), d(0x1B0)
    m.put(b + 8, 2, m.u16(a + 8)); m.put(b + 0x12, 2, m.u16(a + 0x12)); m.put(b + 0xA, 8, m.u64(a + 0xA))
    a, b = s(0x1D0), d(0x1D0)
    n = m.u8(a + 0x48)
    m.put(b + 0x48, 1, n)
    m.put(b + 0x18, 8, 0)
    if n:
        m.call_void(m.main + 0xC7684C, b + 0x10, n, 0)
        for i in range(m.u8(b + 0x48)):
            w = 8 * (i >> 6)
            bit = 1 << (i & 63)
            cur = m.u64(m.u64(b + 0x10) + w)
            on = m.u64(m.u64(a + 0x10) + w) & bit
            m.put(m.u64(b + 0x10) + w, 8, cur | bit if on else cur & ~bit)
    m.put(d(0x1F0) + 8, 1, m.u8(s(0x1F0) + 8))
    a, b = s(0x210), d(0x210)
    m.write(b + 8, m.read(a + 8, 0x28))
    m.write(b + 0x30, m.read(a + 0x30, 0xA0))
    m.put(b + 0xD0, 8, m.u64(a + 0xD0)); m.put(b + 0xD8, 8, m.u64(a + 0xD8))
    a, b = s(0x230), d(0x230)
    m.put(b + 8, 4, m.u32(a + 8))
    for off in range(0xC, 0x11):
        m.put(b + off, 1, m.u8(a + off))
    m.write(d(0x250) + 0x10, m.read(s(0x250) + 0x10, 0x1E0))
    m.put(d(0x270) + 8, 8, m.u64(s(0x270) + 8))
    m.put(dst + 0x360, 8, s(0x360)); m.put(dst + 0x350, 8, s(0x350)); m.put(dst + 0x358, 8, s(0x358))
    m.put(dst + 0x368, 2, m.u16(src + 0x368)); m.put(dst + 0x36A, 1, m.u8(src + 0x36A))
    m.call_void(m.main + 0xF78AF4, d(0x2B0), s(0x2B0))
    m.call_void(m.main + 0xF78CB8, d(0x2F0), s(0x2F0))
    a, b = s(0x310), d(0x310)
    m.write(b + 0x1C, m.read(a + 0x1C, 0x4A))
    m.write(b + 0x68, m.read(a + 0x68, 0x28))
    m.put(b + 0x18, 4, m.u32(a + 0x18))
    m.put(dst + 0x370, 1, m.u8(src + 0x370)); m.put(dst + 0x36C, 4, m.u32(src + 0x36C))
    r, w = s(0x10), d(0x10)
    seed, draws = m.u64(r + 0x18), m.u64(r + 0x20)
    m.put(w + 0x18, 8, seed); m.put(w + 0x20, 8, draws)
    s0, s1 = seed, RNG_SEED[1]
    m.put(w + 8, 8, s0); m.put(w + 0x10, 8, s1)
    for _ in range(draws):
        s1 ^= s0
        s0 = _rotl64(s0, 24) ^ s1 ^ ((s1 << 16) & M64)
        s1 = _rotl64(s1, 37)
    if draws:
        m.put(w + 8, 8, s0); m.put(w + 0x10, 8, s1)


@lifted(0x28908EC)
def make_branch_module(m, o, src_mm, x2, *_):
    """o+0x38 holds a new main module (0x12742d0 from [o+8], a = {alloc, [o+0x30], 0, 0, x2, 0}, the old
    one through 0x2890c54), reset (0x127d824) and copy-assigned from src_mm (0xf77c04)."""
    alloc = m.u64(o + 8)
    with m.frame(0x60) as f:
        a, local = f, f + 0x30
        m.put(a, 8, alloc); m.put(a + 8, 8, m.u64(o + 0x30)); m.put(a + 0x10, 4, 0); m.put(a + 0x14, 1, 0)
        m.put(a + 0x18, 8, x2); m.put(a + 0x20, 8, 0)
        p = m.vcall(alloc, 0x10, 0x378, 8)
        if p:
            stack = _tls_stack(m)
            _push(m, stack, alloc)
            m.call_void(m.main + 0x12742D0, p, a)
            _stores(m, local, ((0, 8, p), (8, 8, alloc), (0x10, 8, 0x378), (0x18, 8, 8)))
            _pop(m, stack)
        else:
            m.write(local, bytes(0x20))
        p = m.u64(local)
        m.put(local, 8, 0)
        m.call_void(m.main + 0x2890C54, o + 0x38, p)
        m.put(o + 0x40, 8, m.u64(local + 8)); m.put(o + 0x48, 8, m.u64(local + 0x10))
        m.put(o + 0x50, 8, m.u64(local + 0x18))
        m.call_void(m.main + 0x2890C54, local, 0)
        m.call_void(m.main + 0x127D824, m.u64(o + 0x38), a)
        return _tail(m, m.main + 0xF77C04, m.u64(o + 0x38), src_mm)


@lifted(0x2890A04)
def make_branch_server(m, o, *_):
    """o+0x58 holds a new server module set (0x126bfa4 from [o+8], a = {alloc, [o+0x30], [o+0x38]},
    the old one through 0x2891030), then 0xfaef9c on it."""
    alloc = m.u64(o + 8)
    with m.frame(0x40) as f:
        a, local = f, f + 0x20
        m.put(a, 8, alloc); m.put(a + 8, 8, m.u64(o + 0x30)); m.put(a + 0x10, 8, m.u64(o + 0x38))
        p = m.vcall(alloc, 0x10, 0x1F0, 8)
        if p:
            stack = _tls_stack(m)
            _push(m, stack, alloc)
            m.call_void(m.main + 0x126BFA4, p, a)
            _stores(m, local, ((0, 8, p), (8, 8, alloc), (0x10, 8, 0x1F0), (0x18, 8, 8)))
            _pop(m, stack)
        else:
            m.write(local, bytes(0x20))
        p = m.u64(local)
        m.put(local, 8, 0)
        m.call_void(m.main + 0x2891030, o + 0x58, p)
        m.put(o + 0x60, 8, m.u64(local + 8)); m.put(o + 0x68, 8, m.u64(local + 0x10))
        m.put(o + 0x70, 8, m.u64(local + 0x18))
        m.call_void(m.main + 0x2891030, local, 0)
        m.call_void(m.main + 0xFAEF9C, m.u64(o + 0x58))


@lifted(0x2890AFC)
def make_branch_builder(m, o, *_):
    """o+0x78 holds a new builder object (0xfb00e0 from [o+8]) for {the server's members (0xfb00c8,
    0xfb00d0, 0x13f5ef8, 0xfb00c0, 0xfb00b8), +0x30 0, o+0xa0, o+0x98, 0xfa01f0([o+0x38])}; the old
    one goes through 0xfb03b0."""
    with m.frame(0x80) as f:
        s, u = f, f + 0x50
        srv = lambda: m.u64(o + 0x58)
        m.put(s + 0x30, 8, 0); m.put(s + 0x38, 8, o + 0xA0); m.put(s + 0x40, 8, o + 0x98)
        m.put(s + 0x48, 8, m.call(m.main + 0xFA01F0, m.u64(o + 0x38)))
        m.put(s, 8, m.call(m.main + 0xFB00C8, srv()))
        m.put(s + 8, 8, m.call(m.main + 0xFB00D0, srv()))
        m.put(s + 0x10, 8, m.call(m.main + 0x13F5EF8, srv()))
        m.put(s + 0x20, 8, m.call(m.main + 0xFB00B8, srv()))
        m.put(s + 0x18, 8, m.call(m.main + 0xFB00C0, srv()))
        m.x8 = u
        m.call_void(m.main + 0xFB00E0, m.u64(o + 8), s)
        x = m.u64(u)
        m.put(u, 8, 0)
        old = m.u64(o + 0x78)
        m.put(o + 0x78, 8, x)
        if old:
            m.call_void(m.main + 0xFB03B0, o + 0x80, old)
        m.put(o + 0x80, 8, m.u64(u + 8)); m.put(o + 0x88, 8, m.u64(u + 0x10)); m.put(o + 0x90, 8, m.u64(u + 0x18))
        m.put(u, 8, 0)
        y = m.u64(s + 0x30)
        if y:
            _release(m, y)


@lifted(0x2890818)
def construct_branch(m, o, a1, src_mm, x3, *_):
    """A state branch (class 0x44ff390, 0x2e8 bytes): +8 the current owner, +0x30 a1, u32 +0x98 5,
    0xfaeb40(+0xa0), its main module copied from src_mm (0x28908ec), its server (0x2890a04) and
    builder (0x2890afc)."""
    top = _owned_base(m, o)
    _stores(m, o, ((0x28, 4, 0), (0, 8, m.main + 0x44FF390), (8, 8, top), (0x20, 8, m.main + 0x44FF3C8),
                   (0x30, 8, a1)))
    m.write(o + 0x38, bytes(0x60))
    m.put(o + 0x9C, 1, 0); m.put(o + 0x98, 4, 5)
    m.call_void(m.main + 0xFAEB40, o + 0xA0)
    m.put(o + 0x2E0, 8, 0); m.put(o + 0x2D8, 8, 0)
    m.call_void(m.main + 0x28908EC, o, src_mm, x3)
    m.call_void(m.main + 0x2890A04, o)
    return _tail(m, m.main + 0x2890AFC, o)


@lifted(0x2898890)
def create_branch(m, alloc, p1, p2, p3, *_):
    """Create a 0x2e8-byte state branch (0x2890818 with *p1, *p2, *p3)."""
    return _create(m, alloc, 0x2E8, lambda o: m.call_void(m.main + 0x2890818, o, m.u64(p1), m.u64(p2),
                                                          m.u64(p3)))


# --- the host state (0xfad9f4) and the step-2 driver (0xfa3824) -------------------------------------

@lifted(0xFAE414)
def slot_fae414(m, table, key_ptr, *_):
    """operator[] of an unordered_map<u32, u64> (node 0x20, align 8, value +0x18 zeroed; rehash
    0xfae708)."""
    return _slot(m, table, key_ptr, 0x20, 8, 0x18, lambda n: m.put(n + 0x18, 8, 0), 0xFAE80C)


def _set_weak(m, slot, x):
    """*slot = x (already referenced); the handle it held is released."""
    old = m.u64(slot)
    m.put(slot, 8, 0)
    if old:
        _release(m, old)
    m.put(slot, 8, x)


def _new_flag_object(m, o, flag):
    """A 0xfae198 object from [o+8] for the flag byte at `flag`, with a weak reference."""
    with m.frame(0x10) as f:
        y = m.call(m.main + 0xFAE198, f, m.u64(o + 8), flag)
    if y:
        _acquire(m, y)
    return y


BIG = 0x0FFFFFFFFFFFFFFF


@lifted(0xFAD9F4)
def construct_host(m, o, a1, a2, a3, flag, *_):
    """The host state (class 0x44ffe38, 0x4b8 bytes): +0x30 / +0x38 a1 / a2, three u32 maps (+0x60,
    +0xc8, +0x130) each holding a 0xfae198 object per side 0..4, +0x50 one more and +0x58 a 0xfa7f10
    object; then either side 0xff's entry and a 0x16afad0 object at +0x498 (when 0x16f814c(a1)), and
    0xfaeca8, its server (0xfaee40) and builder (0xfafe64) from a3."""
    with m.frame(0x10) as fl:
        m.put(fl, 1, flag)
        top = _owned_base(m, o)
        _stores(m, o, ((0x28, 4, 0), (0, 8, m.main + 0x44FFE38), (8, 8, top), (0x20, 8, m.main + 0x44FFE70),
                       (0x80, 8, 0), (0x88, 4, 0), (0xB0, 4, 0), (0xB8, 8, 0), (0xC0, 4, ONE_F), (0x30, 8, a1),
                       (0x38, 8, a2), (0x40, 8, 0), (0x48, 8, 0), (0x50, 8, 0), (0x58, 8, 0), (0x60, 8, 0),
                       (0x68, 8, 0), (0x70, 8, a3), (0x78, 8, BIG), (0x90, 8, 0), (0x98, 8, a3), (0xA0, 8, BIG),
                       (0xA8, 8, 0), (0xC8, 8, 0)))
        _stores(m, o + 0xC8, ((0x28, 4, 0), (0x50, 4, 0), (0x58, 8, 0), (0x60, 4, ONE_F), (8, 8, 0), (0x10, 8, a3),
                              (0x18, 8, BIG), (0x20, 8, 0), (0x30, 8, 0), (0x38, 8, a3), (0x40, 8, BIG),
                              (0x48, 8, 0), (0x68, 8, 0), (0x90, 4, 0), (0xB8, 4, 0), (0xC0, 8, 0), (0xC8, 4, ONE_F),
                              (0x70, 8, 0), (0x78, 8, a3), (0x80, 8, BIG), (0x88, 8, 0), (0x98, 8, 0), (0xA0, 8, a3),
                              (0xA8, 8, BIG), (0xB0, 8, 0), (0xD0, 8, 0), (0xD8, 8, 0)))
        top = m.u64(o + 8)
        _stores(m, o + 0xC8, ((0x100, 4, 0), (0x128, 4, 0), (0x130, 8, 0), (0x138, 4, ONE_F), (0x144, 1, 0),
                              (0xE0, 8, 0), (0xE8, 8, top), (0x108, 8, 0), (0x110, 8, top), (0x140, 4, 5),
                              (0xF0, 8, 0x0666666666666666), (0xF8, 8, 0), (0x118, 8, 0x0666666666666666),
                              (0x120, 8, 0)))
        m.call_void(m.main + 0xFAEB40, o + 0x210)
        for off in (0x4B0, 0x4A8, 0x4A0, 0x498):
            m.put(o + off, 8, 0)
        m.write(o + 0x448, bytes(0x49))
        _set_weak(m, o + 0x50, _new_flag_object(m, o, fl))
        with m.frame(0x10) as f:
            z = m.call(m.main + 0xFA7F10, f, m.u64(o + 8))
        if z:
            _acquire(m, z)
        _set_weak(m, o + 0x58, z)
        with m.frame(0x10) as key:
            for side in range(5):
                m.put(key, 4, side)
                for table in (o + 0xC8, o + 0x130, o + 0x60):
                    y = _new_flag_object(m, o, fl)
                    _set_weak(m, m.call(m.main + 0xFAE414, table, key), y)
            if m.call(m.main + 0x16F814C, m.u64(o + 0x30)) & 0xFF:
                y = _new_flag_object(m, o, fl)
                m.put(key, 4, 0xFF)
                _set_weak(m, m.call(m.main + 0xFB0854, o + 0x60, key), y)
                with m.frame(0x20) as u:
                    m.call_sret(m.main + 0x16AFAD0, u, m.u64(o + 8))
                    x = m.u64(u)
                    m.put(u, 8, 0)
                    old = m.u64(o + 0x498)
                    m.put(o + 0x498, 8, x)
                    if old:
                        raise UnliftedCall("replaced 0x16afad0 object at +0x498")
                    m.put(o + 0x4B0, 8, m.u64(u + 0x18)); m.put(o + 0x4A8, 8, m.u64(u + 0x10))
                    m.put(o + 0x4A0, 8, m.u64(u + 8))
        m.call_void(m.main + 0xFAECA8, o)
        m.call_void(m.main + 0xFAEE40, o, a3)
        m.call_void(m.main + 0xFAFE64, o, a3)


@lifted(0xFAEE40)
def make_host_server(m, o, alloc, *_):
    """o+0x468 holds a new server module set (0x126bfa4 from alloc, a = {alloc, [o+0x30], [o+0x38]},
    the old one through 0xfaf7b0), then 0xfaef9c on it."""
    with m.frame(0x40) as f:
        a, local = f, f + 0x20
        m.put(a, 8, alloc); m.put(a + 8, 8, m.u64(o + 0x30)); m.put(a + 0x10, 8, m.u64(o + 0x38))
        p = m.vcall(alloc, 0x10, 0x1F0, 8)
        if p:
            stack = _tls_stack(m)
            _push(m, stack, alloc)
            m.call_void(m.main + 0x126BFA4, p, a)
            _stores(m, local, ((0, 8, p), (8, 8, alloc), (0x10, 8, 0x1F0), (0x18, 8, 8)))
            _pop(m, stack)
        else:
            m.write(local, bytes(0x20))
        p = m.u64(local)
        m.put(local, 8, 0)
        m.call_void(m.main + 0xFAF7B0, o + 0x468, p)
        m.put(o + 0x480, 8, m.u64(local + 0x18)); m.put(o + 0x478, 8, m.u64(local + 0x10))
        m.put(o + 0x470, 8, m.u64(local + 8))
        m.call_void(m.main + 0xFAF7B0, local, 0)
        m.call_void(m.main + 0xFAEF9C, m.u64(o + 0x468))


@lifted(0xFAFE64)
def make_host_builder(m, o, alloc, *_):
    """o+0x448 holds a new builder object (0xfb00e0 from alloc) for {the server's members (0xfb00c8,
    0xfb00d0, 0x13f5ef8, 0xfb00c0, 0xfb00b8, 0xfb00d8), [o+0x50] referenced, o+0x210, o+0x208,
    0xfa01f0([o+0x38])}; the old one goes through 0xfb03b0."""
    with m.frame(0x80) as f:
        s, u = f, f + 0x50
        h = m.u64(o + 0x50)
        if h:
            _acquire(m, h)
        m.put(s + 0x30, 8, h)
        m.put(s + 0x38, 8, o + 0x210); m.put(s + 0x40, 8, o + 0x208)
        m.put(s + 0x48, 8, m.call(m.main + 0xFA01F0, m.u64(o + 0x38)))
        srv = lambda: m.u64(o + 0x468)
        for off, fn in ((0, 0xFB00C8), (8, 0xFB00D0), (0x10, 0x13F5EF8), (0x18, 0xFB00C0), (0x20, 0xFB00B8),
                        (0x28, 0xFB00D8)):
            m.put(s + off, 8, m.call(m.main + fn, srv()))
        m.x8 = u
        m.call_void(m.main + 0xFB00E0, alloc, s)
        x = m.u64(u)
        m.put(u, 8, 0)
        old = m.u64(o + 0x448)
        m.put(o + 0x448, 8, x)
        if old:
            m.call_void(m.main + 0xFB03B0, o + 0x450, old)
        m.put(o + 0x460, 8, m.u64(u + 0x18)); m.put(o + 0x458, 8, m.u64(u + 0x10)); m.put(o + 0x450, 8, m.u64(u + 8))
        m.put(u, 8, 0)
        y = m.u64(s + 0x30)
        if y:
            _release(m, y)


@lifted(0xFA3B6C)
def create_host(m, alloc, p1, p2, p3, p4, *_):
    """Create the 0x4b8-byte host state (0xfad9f4 with *p1, *p2, *p3 and the byte *p4)."""
    return _create(m, alloc, 0x4B8, lambda o: m.call_void(m.main + 0xFAD9F4, o, m.u64(p1), m.u64(p2),
                                                          m.u64(p3), m.u8(p4)))


@lifted(0xFA3A74)
def create_host_ref(m, alloc, p1, p2, p3, p4, *_):
    """*x8 = a new host state (0xfa3b6c) with a reference added."""
    out = m.x8
    r = m.call(m.main + 0xFA3B6C, alloc, p1, p2, p3, p4)
    m.put(out, 8, r)
    if r:
        _inc(m, r)
    return r


@lifted(0xFA3A68)
def set_490(m, o, flag, *_):
    m.put(o + 0x490, 1, flag & 1)


@lifted(0xFA39B4)
def make_host(m, o, s, *_):
    """s's host state (0xfa3ae0) is a new one (0xfa3a74 from [o], o+0x48, o+0x50, o, o+0x40); its
    u8 +0x490 = u8 [o+0x2c] & 1."""
    with m.frame(0x10) as f:
        m.x8 = f
        m.call_void(m.main + 0xFA3A74, m.u64(o), o + 0x48, o + 0x50, o, o + 0x40)
        m.call_void(m.main + 0xFA3AE0, s, f)
        x = m.u64(f)
        if x:
            _dec(m, x)
    return _tail(m, m.main + 0xFA3A68, m.u64(s), m.u8(o + 0x2C))


@lifted(0xFB0EE8)
def make_branch_of_host(m, o, s, *_):
    """A state branch (0x2898890 from [o], o+0x48, o+0x58 and the handle [[o+0x60]+0x130]) given the
    handle [[o+0x60]+0x138] (0x2891404) and held by the host side's state (0x288fd24)."""
    h = m.u64(m.u64(o + 0x60) + 0x130)
    if h:
        _acquire(m, h)
        _release(m, h)
    with m.frame(0x20) as f:
        L, B, C, D = f, f + 8, f + 0x10, f + 0x18
        m.put(L, 8, h)
        b = m.call(m.main + 0x2898890, m.u64(o), o + 0x48, o + 0x58, L)
        m.put(B, 8, b)
        if b:
            _inc(m, b)
        c = m.u64(m.u64(o + 0x60) + 0x138)
        m.put(C, 8, c)
        if c:
            _acquire(m, c)
        m.call_void(m.main + 0x2891404, b, C)
        c = m.u64(C)
        if c:
            _release(m, c)
        host = m.u64(s + 8 + 8 * m.u32(o + 0x24))
        d = m.u64(B)
        m.put(D, 8, d)
        if d:
            _inc(m, d)
        m.call_void(m.main + 0x288FD24, host, D)
        m.call_void(m.main + 0x175D10C, D)
        return _tail(m, m.main + 0x175D10C, B)


@lifted(0xFA3824)
def build_state(m, o, s, *_):
    """Step 2's state build into s: 0xfa4064(s), the host (0xfa39b4); then either 0xfb1194 (u8
    [o+0x2d]) or the side states (0xfa52b0), their sources (0xfa4cf0), 0xfb0a60 when 0xfa38c8 says so,
    and the branch (0xfb0ee8) unless u8 [o+0x2c]."""
    m.call_void(m.main + 0xFA4064, s)
    m.call_void(m.main + 0xFA39B4, o, s)
    if m.u8(o + 0x2D):
        return _tail(m, m.main + 0xFB1194, o, s)
    m.call_void(m.main + 0xFA52B0, o, s)
    m.call_void(m.main + 0xFA4CF0, o, s)
    if m.call(m.main + 0xFA38C8, m.u32(o + 0x18), m.u8(o + 0x1D)) & 1:
        m.call_void(m.main + 0xFB0A60, o, s)
    if not m.u8(o + 0x2C):
        return _tail(m, m.main + 0xFB0EE8, o, s)


FUNCTIONS[0xFA4800] = assign_weak              # the same code as 0xfa3c64
FUNCTIONS[0xFA493C] = assign_weak
FUNCTIONS[0xFA4A78] = assign_weak


def _sources(m, o, out, specs):
    """out[i] = wrapper(source(key_i)) for each spec (kind, side, flag, source fn, wrapper fn): every
    source answer taken first (key {u32 [o+0x40], kind, side}), then each wrapped (its copy weakly
    referenced for the call) into out with the old handle released; the answers are released last,
    in reverse."""
    n = len(specs)
    with m.frame(0x20 + 0x18 * n) as f:
        tmp, t = f, f + 8
        for i, (kind, side, flag, src, _) in enumerate(specs):
            k = f + 0x10 + 0x10 * i
            m.put(k, 4, m.u32(o + 0x40)); m.put(k + 4, 4, kind); m.put(k + 8, 4, side & M32)
        ans = f + 0x10 + 0x10 * n
        for i, (kind, side, flag, src, _) in enumerate(specs):
            m.x8 = ans + 8 * i
            m.call_void(m.main + src, o, f + 0x10 + 0x10 * i, flag)
        for i in range(n):
            m.put(out + 8 * i, 8, 0)
        for i, (_, _, _, _, wrap) in enumerate(specs):
            x = m.u64(ans + 8 * i)
            m.put(tmp, 8, x)
            if x:
                _acquire(m, x)
            m.x8 = t
            m.call_void(m.main + wrap, o, tmp)
            _set_weak(m, out + 8 * i, m.u64(t))
            m.put(t, 8, 0)
            x = m.u64(tmp)
            if x:
                _release(m, x)
        for i in reversed(range(n)):
            x = m.u64(ans + 8 * i)
            if x:
                _release(m, x)


@lifted(0x28949F4)
def raid_sources(m, o, *_):
    """*x8 = the three side-5 handles: kinds 3 and 4 from vf 0x70 sources wrapped by 0xfa803c, kind 5
    from a vf 0x68 source wrapped by 0xfa793c."""
    _sources(m, o, m.x8, ((3, 5, 1, 0xFA77D4, 0xFA803C), (4, 5, 1, 0xFA77D4, 0xFA803C),
                          (5, 5, 1, 0xFA766C, 0xFA793C)))


@lifted(0x2895120)
def create_2895120(m, alloc, *_):
    """Create a 0x78-byte 0x44ffd18 object (0x28951e8)."""
    return _create(m, alloc, 0x78, lambda o: m.call_void(m.main + 0x28951E8, o))


@lifted(0x2895004)
def create_2895004_ref(m, alloc, *_):
    """*x8 = a new 0x2895120 object with a weak reference added."""
    out = m.x8
    r = m.call(m.main + 0x2895120, alloc)
    m.put(out, 8, r)
    if r:
        _acquire(m, r)
    return r


@lifted(0x2892618)
def make_raid_link(m, n, a1, a2, a3, a4, alloc, *_):
    """*x8 = a new 0x44ffd18 object (0x2895004 from alloc) given {n, a2, a1} and the three side-5
    handles of a3 (0x28949f4), which are also added to a4 (0xfa5930)."""
    out = m.x8
    m.x8 = out
    m.call_void(m.main + 0x2895004, alloc)
    with m.frame(0x60) as f:
        q, c, t = f, f + 0x18, f + 0x20
        m.x8 = q
        m.call_void(m.main + 0x28949F4, a3)
        _add_handles(m, a4, (m.u64(q), m.u64(q + 8), m.u64(q + 0x10)), c)
        _stores(m, t, ((0x20, 8, 0), (0x28, 8, 0), (0x10, 8, a1), (0x18, 8, 0), (0, 8, n), (8, 8, a2)))
        m.call_void(m.main + 0xFA6560, t + 0x18, m.u64(q))
        m.call_void(m.main + 0xFA6560, t + 0x20, m.u64(q + 8))
        m.call_void(m.main + 0xFA6424, t + 0x28, m.u64(q + 0x10))
        m.call_void(m.main + 0x28950C8, m.u64(out), t)
        for p in (t + 0x28, t + 0x20, t + 0x18, q + 0x10, q + 8, q):
            x = m.u64(p)
            if x:
                _release(m, x)


@lifted(0xFB1BBC)
def construct_fb1bbc(m, o, *_):
    """Class 0x44ffbf8 on the weak-object base: +0x40..+0x78 zero."""
    r = _weak_base(m, o)
    m.put(o, 8, m.main + 0x44FFBF8); m.put(o + 0x20, 8, m.main + 0x44FFC70)
    m.put(o + 0x28, 8, m.main + 0x44FFCC0)
    m.write(o + 0x40, bytes(0x38))
    return r


@lifted(0xFB1AF4)
def create_fb1af4(m, alloc, *_):
    """Create a 0x78-byte 0x44ffbf8 object (0xfb1bbc)."""
    return _create(m, alloc, 0x78, lambda o: m.call_void(m.main + 0xFB1BBC, o))


@lifted(0xFB1A30)
def create_fb1a30_ref(m, alloc, *_):
    """*x8 = a new 0xfb1af4 object with a weak reference added."""
    out = m.x8
    r = m.call(m.main + 0xFB1AF4, alloc)
    m.put(out, 8, r)
    if r:
        _acquire(m, r)
    return r


@lifted(0xFB1CDC)
def raid_sources_other(m, o, *_):
    """*x8 = the three side-5 handles: kinds 3 and 4 from 0xfa766c sources wrapped by 0xfa793c, kind 5
    from a 0xfa77d4 source wrapped by 0xfa803c."""
    _sources(m, o, m.x8, ((3, 5, 1, 0xFA766C, 0xFA793C), (4, 5, 1, 0xFA766C, 0xFA793C),
                          (5, 5, 1, 0xFA77D4, 0xFA803C)))


@lifted(0xFB19D8)
def copy_fb19d8(m, dst, src, *_):
    """dst+0x40..+0x58 = src's three words, then the shared handles +0x58 / +0x60 (0xfa6424) and +0x68
    (0xfa6560) from src+0x18 / +0x20 / +0x28."""
    m.put(dst + 0x40, 8, m.u64(src)); m.put(dst + 0x48, 8, m.u64(src + 8))
    m.put(dst + 0x50, 8, m.u64(src + 0x10))
    m.call_void(m.main + 0xFA6424, dst + 0x58, m.u64(src + 0x18))
    m.call_void(m.main + 0xFA6424, dst + 0x60, m.u64(src + 0x20))
    return _tail(m, m.main + 0xFA6560, dst + 0x68, m.u64(src + 0x28))


@lifted(0xFB1544)
def make_raid_link_server(m, n, a1, a2, a3, a4, alloc, *_):
    """*x8 = a new 0x44ffbf8 object (0xfb1a30 from alloc) given {n, a1, a2} and the three side-5
    handles of a3 (0xfb1cdc), which are also added to a4 (0xfa5930)."""
    out = m.x8
    m.x8 = out
    m.call_void(m.main + 0xFB1A30, alloc)
    with m.frame(0x60) as f:
        q, c, t = f, f + 0x18, f + 0x20
        m.x8 = q
        m.call_void(m.main + 0xFB1CDC, a3)
        _add_handles(m, a4, (m.u64(q), m.u64(q + 8), m.u64(q + 0x10)), c)
        _stores(m, t, ((0x20, 8, 0), (0x28, 8, 0), (0, 8, n), (8, 8, a1), (0x10, 8, a2), (0x18, 8, 0)))
        m.call_void(m.main + 0xFA6424, t + 0x18, m.u64(q))
        m.call_void(m.main + 0xFA6424, t + 0x20, m.u64(q + 8))
        m.call_void(m.main + 0xFA6560, t + 0x28, m.u64(q + 0x10))
        m.call_void(m.main + 0xFB19D8, m.u64(out), t)
        for p in (t + 0x28, t + 0x20, t + 0x18, q + 0x10, q + 8, q):
            x = m.u64(p)
            if x:
                _release(m, x)


@lifted(0xFB0774)
def set_shared_fb0774(m, o, x, *_):
    """*o = x with a weak reference added; the old handle goes through 0x18584f0."""
    if x:
        _acquire(m, x)
    with m.frame(0x10) as f:
        m.put(f, 8, m.u64(o))
        m.put(o, 8, x)
        return _tail(m, m.main + 0x18584F0, f)


@lifted(0xFA402C)
def set_link_fa402c(m, o, h, *_):
    """0xfb0774(o+0x40, *h)."""
    return _tail(m, m.main + 0xFB0774, o + 0x40, m.u64(h))


@lifted(0xFA4038)
def drop_fa4038(m, o, *_):
    """o+0x48 released (0x1858568)."""
    with m.frame(0x10) as f:
        m.put(f, 8, m.u64(o + 0x48))
        m.put(o + 0x48, 8, 0)
        return _tail(m, m.main + 0x1858568, f)


def _swap_shared(m, holder, value, release):
    """*holder = value (a moved shared pointer); the old one goes through `release`."""
    with m.frame(0x10) as f:
        m.put(f, 8, m.u64(holder))
        m.put(holder, 8, 0)
        m.call_void(m.main + release, f)
        m.put(holder, 8, value)


@lifted(0xFA4BB4)
def make_raid_link_of(m, n, *_):
    """N+0x148 holds a new raid link (0x2892618 from N, [N+0xb0], [N+0xa8], [N+0x110], [N+0x118], [N+8])
    after N+0x140 is released; then 0x2892ab4([N+0xb0], the link)."""
    alloc = m.u64(n + 8)
    with m.frame(0x20) as f:
        m.put(f, 8, m.u64(n + 0x140))
        m.put(n + 0x140, 8, 0)
        m.call_void(m.main + 0x18584F0, f)
        r = f + 8
        m.x8 = r
        m.call_void(m.main + 0x2892618, n, m.u64(n + 0xB0), m.u64(n + 0xA8), m.u64(n + 0x110),
                    m.u64(n + 0x118), alloc)
        x = m.u64(r)
        m.put(r, 8, 0)
        _swap_shared(m, n + 0x148, x, 0x1858568)
        m.call_void(m.main + 0x1858568, r)
        c = f + 0x10
        x = m.u64(n + 0x148)
        m.put(c, 8, x)
        if x:
            _acquire(m, x)
        m.call_void(m.main + 0x2892AB4, m.u64(n + 0xB0), c)
        m.call_void(m.main + 0x1858568, c)


@lifted(0xFA3EDC)
def make_raid_link_other(m, n, *_):
    """The other raid link: N+0x148 released, N+0x140 a new 0xfb1544 object (from N, [N+0xb0],
    [N+0x138], [N+0x110], [N+0x118], [N+8]), passed to 0xfa402c([N+0xb0]); ends with 0xfa4038."""
    alloc = m.u64(n + 8)
    with m.frame(0x20) as f:
        m.put(f, 8, m.u64(n + 0x148))
        m.put(n + 0x148, 8, 0)
        m.call_void(m.main + 0x1858568, f)
        r = f + 8
        m.x8 = r
        m.call_void(m.main + 0xFB1544, n, m.u64(n + 0xB0), m.u64(n + 0x138), m.u64(n + 0x110),
                    m.u64(n + 0x118), alloc)
        x = m.u64(r)
        m.put(r, 8, 0)
        _swap_shared(m, n + 0x140, x, 0x18584F0)
        m.call_void(m.main + 0x18584F0, r)
        c = f + 0x10
        x = m.u64(n + 0x140)
        m.put(c, 8, x)
        if x:
            _acquire(m, x)
        m.call_void(m.main + 0xFA402C, m.u64(n + 0xB0), c)
        m.call_void(m.main + 0x18584F0, c)
    return _tail(m, m.main + 0xFA4038, m.u64(n + 0xB0))


@lifted(0xFA35C8)
def make_raid_links(m, n, *_):
    """For a raid (setup u32 +0x34 == 2, u8 +0x8d in 1..3 or 5..6): 0xfa3edc when 0xfa363c(N), else
    0xfa4bb4."""
    setup = m.u64(n + 0x38)
    if m.u32(setup + 0x34) != 2:
        return
    k = m.u8(setup + 0x8D)
    if (k - 5) & M32 < 2 or (k - 1) & M32 <= 2:
        if m.call(m.main + 0xFA363C, n) & 1:
            return _tail(m, m.main + 0xFA3EDC, n)
        return _tail(m, m.main + 0xFA4BB4, n)


@lifted(0xFA46D4)
def set_handles(m, o, s, *_):
    """o+0x80..+0x98 = s's first three words, u8 +0xe0 = s+0x30, the weak handles +0xb0 / +0xa8 / +0xb8
    from s+0x20 / +0x18 / +0x28 when set; the view o+0x48..+0x80 refreshed and passed to 0xfa47c8,
    0xfa47b4 and 0xfa47e4."""
    m.put(o + 0x80, 8, m.u64(s)); m.put(o + 0x88, 8, m.u64(s + 8)); m.put(o + 0x90, 8, m.u64(s + 0x10))
    m.put(o + 0xE0, 1, m.u8(s + 0x30))
    for src, slot, fn in ((0x20, 0xB0, 0xFA4800), (0x18, 0xA8, 0xFA493C), (0x28, 0xB8, 0xFA4A78)):
        x = m.u64(s + src)
        if x:
            m.call_void(m.main + fn, o + slot, x)
    w = [m.u64(o + 0x80 + 8 * i) for i in range(5)]
    m.put(o + 0x48, 8, w[0]); m.put(o + 0x50, 8, w[1])
    b8, c0 = m.u64(o + 0xB8), m.u64(o + 0xC0)
    m.put(o + 0x78, 8, c0); m.put(o + 0x58, 8, w[2]); m.put(o + 0x60, 8, w[3])
    m.put(o + 0x68, 8, w[4]); m.put(o + 0x70, 8, b8)
    with m.frame(0x20) as t:
        m.put(t, 8, o + 0x40); m.put(t + 8, 8, w[3]); m.put(t + 0x10, 8, w[4])
        m.call_void(m.main + 0xFA47C8, m.u64(o + 0xB0), t)
        m.put(t, 8, o + 0x40); m.put(t + 8, 8, m.u64(o + 0xA0))
        m.call_void(m.main + 0xFA47B4, m.u64(o + 0xA8), t)
        m.put(t, 8, o + 0x40); m.put(t + 8, 8, m.u64(o + 0xA0)); m.put(t + 0x10, 8, m.u64(o + 0x98))
        m.call_void(m.main + 0xFA47E4, m.u64(o + 0xB8), t)


@lifted(0xFA433C)
def set_net_handles(m, n, *_):
    """0xfa46d4([N+0xa8], {N, [N+0x170], [N+0xb0], h3, h2, h1, u8 0xfa363c(N)}) with h1..h3 the weak
    handles [[N+0x48]+0x118 / +0x120 / +0x128] held for the call."""
    with m.frame(0x40) as s:
        m.put(s + 0x20, 8, 0); m.put(s + 0x28, 8, 0)
        m.put(s, 8, n); m.put(s + 8, 8, m.u64(n + 0x170)); m.put(s + 0x10, 8, m.u64(n + 0xB0))
        m.put(s + 0x18, 8, 0)
        for off, slot in ((0x118, 0x28), (0x120, 0x20), (0x128, 0x18)):
            h = m.u64(m.u64(n + 0x48) + off)
            if h:
                _acquire(m, h)
            _set_weak(m, s + slot, h)
        m.put(s + 0x30, 1, m.call(m.main + 0xFA363C, n) & 1)
        m.call_void(m.main + 0xFA46D4, m.u64(n + 0xA8), s)
        for slot in (0x28, 0x20, 0x18):
            h = m.u64(s + slot)
            if h:
                _release(m, h)


@lifted(0xFA2CB0)
def build_net_state(m, n, a1, *_):
    """Builds N's eleven counted references +0xb8..+0x108 through 0xfa3824 from a request on the stack
    (a1, the weak handles of [N+0x110] / [N+0x118], the setup's mode bytes, N itself), sets the
    first one at N+0xb0 (0xfa38f8), then 0xfa433c and 0xfa35c8."""
    with m.frame(0xD0) as sp:
        m.put(sp + 0x70, 8, 0); m.put(sp + 0x78, 8, 0)
        m.write(sp + 8, bytes(0x60))
        m.put(sp + 0x68, 8, a1)
        m.call_void(m.main + 0xFA3C64, sp + 0x70, m.u64(n + 0x110))
        m.call_void(m.main + 0xFA3DA0, sp + 0x78, m.u64(n + 0x118))
        setup = m.u64(n + 0x38)
        m.put(sp + 0x80, 4, m.u32(setup + 0x34))
        m.put(sp + 0x85, 1, m.u8(setup + 0x8D))
        m.put(sp + 0x84, 1, m.u8(setup + 0x8C))
        w9 = m.u32(setup + 0x30)
        m.put(sp + 0x88, 4, 0)
        m.put(sp + 0x8C, 4, m.u8(n + 0x95)); m.put(sp + 0x90, 4, w9)
        m.put(sp + 0x94, 1, m.call(m.main + 0xFA363C, n) & 1)
        setup = m.u64(n + 0x38)
        m.put(sp + 0x95, 1, m.u8(setup + 0x710))
        m.put(sp + 0x97, 1, int(m.u8(setup + 0x8C) != 0) if m.u8(setup + 0x711) else 0)
        m.put(sp + 0x96, 1, int(m.u8(setup + 0x712) != 0))
        m.put(sp + 0x98, 1, m.u8(setup + 0x707))
        m.put(sp + 0xB0, 8, n)
        m.put(sp + 0xA0, 8, m.u64(n + 0x30))
        m.put(sp + 0xA8, 1, m.u8(setup + 0x38))
        m.put(sp + 0xB8, 8, m.u64(n + 0x170)); m.put(sp + 0xC0, 8, m.u64(n + 0x150))
        m.put(sp + 0xC8, 8, m.u64(n + 0x48))
        m.call_void(m.main + 0xFA3824, sp + 0x68, sp + 8)
        for a, b in ((0x10, 0xB8), (0x38, 0xE0), (0x18, 0xC0), (0x40, 0xE8), (0x20, 0xC8), (0x48, 0xF0),
                     (0x28, 0xD0), (0x50, 0xF8), (0x30, 0xD8), (0x58, 0x100), (0x60, 0x108)):
            v = m.u64(sp + a)
            if v:
                _inc(m, v)
            old = m.u64(n + b)
            m.put(n + b, 8, v)
            if old:
                _dec(m, old)
        m.call_void(m.main + 0xFA38F8, n + 0xB0, m.u64(sp + 8))
        m.call(m.main + 0xFA363C, n)
        m.call_void(m.main + 0xFA433C, n)
        m.call_void(m.main + 0xFA35C8, n)
        for a in range(0x60, 0, -8):
            v = m.u64(sp + a)
            if v:
                _dec(m, v)
        for a in (0x78, 0x70):
            v = m.u64(sp + a)
            if v:
                _release(m, v)
