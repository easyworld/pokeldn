"""The game heap built from nothing: the state Scarlet 4.0.0's memory initialisation (`0x2b7da90`, which
runs the allocator pair's setup `0x167d510`) leaves, on a machine whose pages are made on demand
(docs/sv_raid.md, Reproducing a round). Layouts are in `heap`'s docstring.

What the console's process supplies is a parameter (`Environment`): the load base, the address range
the SDK reserves for the second allocator, that allocator's allocatable size (one fifth of it becomes
the first allocator), `nn::os::QueryMemoryInfo`, the thread's kernel handle and the kernel entropy that
seeds the SDK's generator. The defaults are the values the snapshots' process measured.

Not reproduced (nothing the battle reads): `__cxa_atexit` registrations and the SDK's TLS slot table
with its destructors (slots are numbered in allocation order).
"""

import dataclasses
import struct

from pokeldn.sv.battle.engine import heap
from pokeldn.sv.battle.machine import FORMAT, MASK, Machine, UnliftedCall, lifted

M64 = MASK[8]
M32 = MASK[4]
PAGE = 0x1000
_UNPACK = {n: struct.Struct(f).unpack_from for n, f in FORMAT.items()}
_PACK = {n: struct.Struct(f).pack_into for n, f in FORMAT.items()}

ARENA_TLS = 0x7F0000000         # stand-in tpidrro_el0 block; +0x1f8 the thread object
ARENA_THREAD = 0x7F0001000      # stand-in nn::os ThreadType (+0x80 + 8 * slot TLS values, +0x1b0 handle)
ARENA_STACK = 0x7F0020000       # top of the engine's scratch stack, 16 pages below it

INNER = 0x47639C8               # the heap allocator object: vtable [0x46e2480] + 0x10 / + 0x130
COUNTED = (0x4763918, 0x4763970)   # the two counted allocators over it (0x13eca54)
COUNTED_SLOTS = (0x4759418, 0x4759420)
SCOPE_SLOT, SCOPE_GUARD = 0x4765A30, 0x4765A38          # TLS slot of the allocator-scope stack
BLOCK_SLOT, BLOCK_GUARD = 0x4759408, 0x4759410          # TLS slot of the 0x12d0-byte thread block
BLOCK_ALLOC, BLOCK_ALLOC_GUARD = 0x4759430, 0x4759438   # = [0x4759418]


@dataclasses.dataclass
class Environment:
    """What the console's process answered during the initialisation (defaults: the snapshots')."""
    main: int = 0x8504000
    reserved: int = 0x15C0000000            # nn::os address-region reservation (0x5183a90), 0x300000000 bytes
    allocatable: int = 0xC4C80000           # allocator 1 GetAllocatableSize at 0x167d55c
    allocatable_after: int = 0xC4B0F000     # allocators 0 + 1 GetAllocatableSize, as 0x2a28e70 reports them
    memory_total: int = 0x100000000         # nn::os::MemoryInfo +0: over 0x100000000 sets main+0x475942c
    program_size: int = 0x5C19000           # nn::os::MemoryInfo +0x20
    thread_handle: int = 0x10801D           # ThreadType +0x1b0
    entropy: bytes = bytes(16)              # svc GetInfo(RandomEntropy, 0) and (.., 1), seeding 0x51ed380


class Arena(Machine):
    """A machine over an empty address space: a page is made when first touched, from `static(page)`
    (the loaded image: main, SDK) when it returns bytes, else zeroed."""

    def __init__(self, static=None, env=None):
        self.env = env or Environment()
        super().__init__(pages={}, main=self.env.main, stack=ARENA_STACK, tls=ARENA_TLS)
        self.static = static
        self.tls_slots = 0
        self.reservations = [self.env.reserved]

    def page(self, address):
        p = address & ~(PAGE - 1)
        b = self.pages.get(p)
        if b is None:
            s = self.static(p) if self.static else None
            b = self.pages[p] = bytearray(s) if s is not None else bytearray(PAGE)
        return b

    def u(self, address, size):
        o = address & (PAGE - 1)
        if o + size <= PAGE and self._direct_read:
            b = self.pages.get(address - o)
            return _UNPACK[size](b if b is not None else self.page(address), o)[0]
        return Machine.u(self, address, size)

    def put(self, address, size, value):
        o = address & (PAGE - 1)
        if o + size <= PAGE and self._direct_write:
            b = self.pages.get(address - o)
            _PACK[size](b if b is not None else self.page(address), o, value & MASK[size])
            return
        Machine.put(self, address, size, value)

    def made(self, address):
        """Whether reading `address` gives anything but a zero: a page exists or the image backs it."""
        p = address & ~(PAGE - 1)
        return p in self.pages or (self.static is not None and self.static(p) is not None)

    def allocate_tls_slot(self, destructor):
        slot = self.tls_slots
        self.tls_slots += 1
        return slot

    def reserve(self, size):
        return self.reservations.pop(0)


def _fill(m, address, byte, n):
    """memset (0x53ef1c8); zeros over an arena page nobody made are left unmade."""
    if byte == 0 and isinstance(m, Arena):
        a, end = address, address + n
        while a < end:
            p = a & ~(PAGE - 1)
            k = min(end, p + PAGE) - a
            if m.made(a):
                m.write(a, bytes(k))
            a += k
        return
    m.write(address, bytes([byte]) * n)


def _guard_acquire(m, guard):
    """__cxa_guard_acquire (0x53c49a0) on one thread: True when the caller constructs."""
    if m.u8(guard):
        return False
    m.put(guard + 1, 1, 2)
    return True


def _guard_release(m, guard):
    """__cxa_guard_release (0x53c4a58): byte 0 done, byte 1 1."""
    m.put(guard, 1, 1)
    m.put(guard + 1, 1, 1)


def _mutex_init(m, mutex):
    """pthread_mutex_init(mutex, NULL) 0x527d090 -> nn::os::InitializeMutex(non-recursive, level 0)."""
    m.write(mutex, bytes(0x20))
    m.put(mutex + 0x18, 4, 0)
    m.put(mutex + 1, 1, 0)
    m.put(mutex + 4, 4, 0); m.put(mutex + 8, 4, 0)
    m.put(mutex + 0x10, 8, 0)
    m.put(mutex, 1, 1)


# --- SDK: the heap over a range (0x518b388) and its holder (0x51906e4) ---

def _heap_init(m, h, start, size, commit):
    """0x518b388: the page heap at `h` over [start, start + size): page -> span table, class bytes,
    (commit bitmap), one descriptor page whose first two slots hold the metadata span (state 3) and
    the free run after the descriptor page. Returns the SDK result (0 or 0x16)."""
    _mutex_init(m, h + 0x30)
    pages = size >> 12
    table = start + 0xA48
    classes = table + 8 * pages
    _fill(m, h + 0x50, 0, 0x9F8)
    m.put(h, 8, pages); m.put(h + 8, 8, table); m.put(h + 0x10, 8, classes)
    end = classes + pages
    if commit & 1:
        m.put(h + 0x18, 8, end)
        chunks = ((((start + size + 0x3FFFF) & ~0x3FFFF) - (start & ~0x3FFFF)) & M64) >> 18
        desc = (end + chunks + 0xFFF) & ~0xFFF
        # 0x51841f0 commits [start, min(size, ...)): the arena's pages exist on demand
        _fill(m, m.u64(h + 0x18), 0, chunks)
        _fill(m, m.u64(h + 0x18), 1, ((desc + 0x40FFF) >> 18) - (start >> 18))
    else:
        m.put(h + 0x18, 8, 0)
        desc = (end + 0xFFF) & ~0xFFF
    _fill(m, table, 0, 8 * pages)
    _fill(m, m.u64(h + 0x10), 0, pages)
    p = desc
    m.put(p + 0x18, 2, 0x23)
    m.put(p + 8, 8, 0); m.put(p + 0x10, 8, 0x1FFFFFFF)
    m.put(p + 0x1A, 1, 0)
    m.put(p, 8, 0); m.put(p + 0x48, 8, 0)
    m.write(p + 0x20, bytes(0x28))
    m.put(p, 8, m.u64(h + 0x50)); m.put(p + 8, 8, h + 0x50)
    if m.u64(h + 0x50):
        m.put(m.u64(h + 0x50) + 8, 8, p)
    m.put(h + 0x50, 8, p)
    first = p + PAGE
    if first >= start + size:
        return 0x16
    run = heap._take_descriptor(m, h, p)
    meta = heap._take_descriptor(m, h, p)
    m.put(p + 0x1A, 1, 1)
    m.put(run + 0x18, 8, first); m.put(run + 0x20, 8, (start + size - first) >> 12)
    m.put(run + 0x13, 1, 2); m.put(run + 0x28, 8, 0); m.put(run + 0x10, 2, 0); m.put(run + 0x14, 4, 0)
    m.put(p + 0x38, 8, p); m.put(p + 0x40, 8, 1)          # the descriptor page as its own span
    m.put(p + 0x30, 2, 0); m.put(p + 0x33, 1, 3); m.put(p + 0x48, 8, 0); m.put(p + 0x34, 4, 0)
    m.put(meta + 0x20, 8, (p - start) >> 12); m.put(meta + 0x28, 8, 0)
    m.put(meta + 0x10, 8, 0x3000000); m.put(meta + 0x18, 8, start)
    heap._table_span(m, h, meta)
    m.put(p + 0x32, 1, 0)
    heap._table_span(m, h, p + 0x20)
    m.put(run + 0x12, 1, 0)
    heap._table_span(m, h, run)
    i = heap._run_list(m.u64(run + 0x20))
    heap._push(m, h + 0x60 + 8 * i, run)
    heap._bitmap_set(m, h, i)
    limit = (m.u64(h) << 9) & 0x1FFFFFFFFFFFFE00
    limit = limit if limit < 0x200000 else 0x200000
    m.put(h + 0x2C, 1, commit & 1)
    m.put(h + 0x20, 4, 1); m.put(h + 0x24, 4, limit); m.put(h + 0x28, 4, limit)
    return 0


def _holder_init(m, holder, addr, size, flags):
    """0x51906e4: the allocator's heap holder (+0 heap, +8 u8 reserved by it, +0xc flags, +0x10/+0x18
    range) over [addr, addr + size), or over a range it reserves and commits when `addr` is 0."""
    if size == 0 or size & 0xFFF:
        return 0x16
    if m.u64(holder + 0x10):
        return 0x11
    if addr:
        start, end = (addr + 0xFFF) & ~0xFFF & M64, (addr + size) & ~0xFFF & M64
        if start >= end:
            return 0x16
        m.put(holder + 0xC, 4, flags); m.put(holder + 0x10, 8, start); m.put(holder + 0x18, 8, end)
        m.put(start, 8, 0)
        m.put(holder, 8, start)
        r = _heap_init(m, start, start, end - start, 0)
        if r:
            raise UnliftedCall("heap init failed: the holder finalises it")
        m.put(holder + 8, 1, 0)
        return 0
    reserve = getattr(m, "reserve", None)
    if reserve is None:
        raise UnliftedCall("nn::os address-region reservation (0x5183a90)")
    base = reserve(size)
    if base & 0xFFF:
        raise UnliftedCall("reservation off a page boundary")
    m.put(holder + 0x10, 8, base); m.put(holder + 0x18, 8, base + size)
    m.put(holder + 0xC, 4, flags)
    m.put(base, 8, 0)
    m.put(holder, 8, base)
    if _heap_init(m, base, base, size, 1):
        raise UnliftedCall("heap init failed: the holder finalises it")
    m.put(holder + 8, 1, 1)
    return 0


@lifted(0x519205C)
def standard_allocator(m, a, *_):
    """nn::mem::StandardAllocator::StandardAllocator(): uninitialised, no thread cache, empty holder."""
    m.put(a, 2, 0); m.put(a + 8, 8, 0); m.put(a + 0x18, 8, 0); m.put(a + 0x20, 1, 0)
    m.put(a + 0x24, 8, 0); m.put(a + 0x2C, 8, 0); m.put(a + 0x34, 4, 0)


@lifted(0x343EF40)
def standard_allocator_import(m, a, *_):
    standard_allocator(m, a)


@lifted(0x51920CC)
def standard_initialize(m, a, addr, size, cache, *_):
    """nn::mem::StandardAllocator::Initialize(address, size, thread cache): the holder over the
    page-aligned range (a range of its own when `address` is null), then the cache's TLS slot."""
    if m.u8(a):
        raise UnliftedCall("abort: allocator initialised twice")
    start = (addr + 0xFFF) & ~0xFFF & M64
    n = (((addr + size) & ~0xFFF) - start) & M64
    if addr:
        if (addr + size) & ~0xFFF & M64 <= start or n >> 14 == 0:
            raise UnliftedCall("abort: allocator range under 16 KB")
        r = _holder_init(m, a + 0x18, start, n, 0)
    else:
        r = _holder_init(m, a + 0x18, 0, size, 0)
    if r:
        raise UnliftedCall(f"abort: holder init 0x{r:x}")
    m.put(a + 1, 1, cache & 1)
    if cache & 1:
        m.put(a + 0x10, 4, _tls_slot(m, m.main + 0x51921C0))
    m.put(a, 1, 1)


@lifted(0x343EFF0)
def standard_initialize_import(m, a, addr, size, cache, *_):
    standard_initialize(m, a, addr, size, cache)


def _tls_slot(m, destructor):
    allocate = getattr(m, "allocate_tls_slot", None)
    if allocate is None:
        raise UnliftedCall("nn::os::AllocateTlsSlot: the SDK's slot table is not modelled")
    return allocate(destructor)


@lifted(0x343DA10)
def allocate_tls_slot(m, slot, destructor, *_):
    """nn::os::AllocateTlsSlot(slot, destructor) (SDK 0x51e6f20)."""
    m.put(slot, 4, _tls_slot(m, destructor))
    return 0


@lifted(0xF538C0)
def allocate_tls_slot_or_abort(m, slot, destructor, *_):
    if m.call(m.main + 0x343DA10, slot, destructor) & M32:
        raise UnliftedCall("abort: nn::os::AllocateTlsSlot failed")


# --- the game's type nodes (a static chain of parent links behind guards) ---

def _node(m, guard_got, node_got, parent):
    """A guarded static node: [node] = parent node (0 for a root), built on first use."""
    guard, node = m.u64(m.main + guard_got), m.u64(m.main + node_got)
    if not m.u8(guard) & 1 and _guard_acquire(m, guard):
        m.put(node, 8, parent() if parent else 0)
        _guard_release(m, guard)
    return node


def _node_root(m):
    return _node(m, 0x46D39C0, 0x46D39C8, None)


def _node_1(m):
    return _node(m, 0x46D8A88, 0x46D8A90, lambda: _node_root(m))


@lifted(0x11E29AC)
def type_node_allocator(m, *_):
    """The type node a counted allocator's inner allocator must derive from."""
    return _node(m, 0x46D8A60, 0x46D8A68, lambda: _node_1(m))


@lifted(0x14128A0)
def type_node_heap(m, *_):
    """The heap allocator's type node (its parent: 0x11e29ac's)."""
    return _node(m, 0x46DD948, 0x46DD950, lambda: type_node_allocator(m))


@lifted(0x2B7DF08)
def heap_type_node(m, *_):
    return type_node_heap(m)


@lifted(0x11E2A88)
def derives_from_heap(m, node, *_):
    """1 when `node` or one of its parents is the heap allocator's type node."""
    want = _node(m, 0x46DD948, 0x46DD950, lambda: type_node_allocator(m))
    while node:
        if node == want:
            return 1
        node = m.u64(node)
    return 0


@lifted(0x13ECB40)
def counted_sizes_enabled(m, *_):
    return 1


@lifted(0x2A64EC8)
def heap_measures_itself(m, *_):
    return 0


@lifted(0x167D630)
def pair_thread_cache(m, *_):
    """Whether the first allocator of the pair keeps a thread cache."""
    return 1


@lifted(0x13123B8)
def set_name(m, this, name, *_):
    m.put(this + 0x10, 8, name)


@lifted(0x13ECA54)
def counted_allocator(m, this, plimit, pinner, *_):
    """A counted allocator over [*pinner] with limit [*plimit]: +0x20 the inner allocator when it derives
    from 0x11e29ac's type, +0x28 the limit, +0x38 / +0x40 / +0x48 counters, +0x50 count by size class
    (0x13ecb40, then the inner's vf 0xb8 or its type deriving from the heap's)."""
    limit, inner = m.u64(plimit), m.u64(pinner)
    m.put(this + 0x10, 8, 0); m.put(this + 0x18, 2, 0)
    vt = m.u64(m.main + 0x46DDA10)
    m.put(this, 8, vt + 0x10); m.put(this + 8, 8, vt + 0x130)
    node = m.vcall(inner + 8, 0)
    want = m.call(m.main + 0x11E29AC)
    found = 0
    while node:
        if node == want:
            found = inner
            break
        node = m.u64(node)
    m.put(this + 0x20, 8, found); m.put(this + 0x28, 8, limit)
    m.put(this + 0x30, 4, 0); m.put(this + 0x48, 8, 0); m.put(this + 0x50, 1, 0)
    m.put(this + 0x38, 8, 0); m.put(this + 0x40, 8, 0)
    flag = 0
    if m.call(m.main + 0x13ECB40) & 1:
        if m.vcall(inner, 0xB8) & 1:
            flag = 1
        else:
            flag = m.call(m.main + 0x11E2A88, m.vcall(inner + 8, 0))
    m.put(this + 0x50, 1, flag & 1)


def _slot_static(m, slot, guard, destructor):
    if not m.u8(m.main + guard) & 1 and _guard_acquire(m, m.main + guard):
        m.call_void(m.main + 0xF538C0, m.main + slot, m.main + destructor)
        _guard_release(m, m.main + guard)


def _block_allocator(m):
    """main+0x4759430 = [0x4759418], guarded."""
    g = m.main + BLOCK_ALLOC_GUARD
    if not m.u8(g) & 1 and _guard_acquire(m, g):
        m.put(m.main + BLOCK_ALLOC, 8, m.u64(m.main + COUNTED_SLOTS[0]))
        _guard_release(m, g)
    return m.u64(m.main + BLOCK_ALLOC)


@lifted(0x13041AC)
def scope_stack(m, owner, *_):
    """The thread's allocator-scope stack (TLS slot [0x4765a30]), made on first use: 0x98 bytes from
    [0x4759430], +0x80 count 0, +0x88 `owner`, u32 +0x90 -1."""
    _slot_static(m, SCOPE_SLOT, SCOPE_GUARD, 0x27BF190)
    if m.call(m.main + 0x343DA20, m.u32(m.main + SCOPE_SLOT)):
        return
    block = m.vcall(_block_allocator(m), 0x10, 0x98, 8)
    if not block:
        raise UnliftedCall("allocation failed: the store faults")
    m.put(block + 0x80, 8, 0); m.put(block + 0x88, 8, owner); m.put(block + 0x90, 4, M32)
    _slot_static(m, SCOPE_SLOT, SCOPE_GUARD, 0x27BF190)
    m.call_void(m.main + 0x343DA30, m.u32(m.main + SCOPE_SLOT), block)


@lifted(0x51E7D00)
def set_malloc_hooks(m, allocate, free, *_):
    """The SDK's malloc / free hooks (sdk 0x5bdc008 / 0x5bdc010), set once."""
    hooks = m.main + 0x5BDC008
    if not allocate or m.u64(hooks) or not free or m.u64(hooks + 8):
        raise UnliftedCall("abort: malloc hooks set twice")
    m.put(hooks, 8, allocate); m.put(hooks + 8, 8, free)


@lifted(0x343FA50)
def set_malloc_hooks_import(m, allocate, free, *_):
    set_malloc_hooks(m, allocate, free)


def _fs_set_allocator(m, allocate, free):
    """nn::fs::SetAllocator (0x507e570 through 0x343fa60): the file system's allocator pair (sdk
    0x5b07ee0 / 0x5b07ee8) replaces the defaults 0x507e960 / 0x507e970 before the file system's first
    use (u8 sdk 0x5ba689c); its result logging writes nothing on success."""
    pair = m.main + 0x5B07EE0
    if m.u64(pair) != m.main + 0x507E960 or m.u64(pair + 8) != m.main + 0x507E970:
        raise UnliftedCall("abort: file system allocator set twice")
    if not allocate or not free or m.u8(m.main + 0x5BA689C) & 1:
        raise UnliftedCall("abort: file system allocator after its first use")
    m.put(pair, 8, allocate); m.put(pair + 8, 8, free)


# --- the builder ---

def tinymt_init(key):
    """tinymt32_init_by_array (SDK 0x525eefc) with the generator's parameters (mat1 0x8f7011ee, mat2
    0xfc78ff1f, tmat 0x3793fdff): period certification and 8 pre-loop steps. Returns the 4 state words."""
    f1 = lambda x: ((x ^ (x >> 27)) * 1664525) & M32           # noqa: E731
    f2 = lambda x: ((x ^ (x >> 27)) * 1566083941) & M32        # noqa: E731
    n = len(key)
    st = [0, 0x8F7011EE, 0xFC78FF1F, 0x3793FDFF]
    count = max(n + 1, 8)
    r = f1(st[0] ^ st[1] ^ st[3])
    st[1] = (st[1] + r) & M32
    r = (r + n) & M32
    st[2] = (st[2] + r) & M32
    st[0] = r
    count -= 1
    i = 1
    for j in range(count):
        r = f1(st[i] ^ st[(i + 1) % 4] ^ st[(i + 3) % 4])
        st[(i + 1) % 4] = (st[(i + 1) % 4] + r) & M32
        r = (r + (key[j] if j < n else 0) + i) & M32
        st[(i + 2) % 4] = (st[(i + 2) % 4] + r) & M32
        st[i] = r
        i = (i + 1) % 4
    for _ in range(4):
        r = f2((st[i] + st[(i + 1) % 4] + st[(i + 3) % 4]) & M32)
        st[(i + 1) % 4] ^= r
        r = (r - i) & M32
        st[(i + 2) % 4] ^= r
        st[i] = r
        i = (i + 1) % 4
    if not st[0] & 0x7FFFFFFF and not st[1] and not st[2] and not st[3]:
        st = [ord("T"), ord("I"), ord("N"), ord("Y")]
    for _ in range(8):
        x = ((st[0] & 0x7FFFFFFF) ^ st[1] ^ st[2]) & M32
        x = (x ^ (x << 1)) & M32
        y = (st[3] ^ (st[3] >> 1) ^ x) & M32
        n2 = (x ^ (y << 10)) & M32
        n1 = st[2]
        if y & 1:
            n1 ^= 0x8F7011EE
            n2 ^= 0xFC78FF1F
        st = [st[1], n1, n2, y]
    return st


def _seed_generator(m, entropy):
    """The SDK generator as its first use (0x51e2ce0 -> 0x51ed380) leaves it: TinyMT32 seeded from the
    kernel's 16 bytes of entropy, ready bit set."""
    key = [int.from_bytes(entropy[i:i + 4], "little") for i in range(0, 16, 4)]
    for i, w in enumerate(tinymt_init(key)):
        m.put(m.main + heap.RANDOM_STATE + 4 * i, 4, w)
    m.put(m.main + heap.RANDOM_READY, 1, 1)


def _pair(m, env):
    """0x167d510: the pair (two StandardAllocator, +0x90 size of the first, +0x98/+0xa0 its range):
    the second over a reserved 0x300000000 bytes, no cache; the first over one fifth of what the
    second can allocate, carved from the end of the second's range, with a thread cache."""
    a = m.main + heap.ALLOCATORS
    g = m.main + heap.ALLOCATORS_GUARD
    if not m.u8(g) & 1 and _guard_acquire(m, g):
        m.call_void(m.main + 0x343EF40, a)
        m.call_void(m.main + 0x343EF40, a + 0x48)
        m.put(a + 0x90, 8, 0); m.put(a + 0x98, 8, 0); m.put(a + 0xA0, 8, 0)
        _guard_release(m, g)
    cache = m.call(m.main + 0x167D630)
    second = a + 0x48
    m.call_void(m.main + 0x343EFF0, second, 0, 0x300000000, 0)
    # GetAllocatableSize, Allocate(it) and Free leave the second heap as initialised (env.allocatable)
    size = int(float(env.allocatable) * 0.2) & M64     # fcvtzu of d * 0.2 (0x3fc999999999999a)
    m.put(a + 0x90, 8, size)
    first = _second_allocate(m, second, size)
    m.call_void(m.main + 0x343EFF0, a, first, size, cache & 1)
    m.put(a + 0x98, 8, first); m.put(a + 0xA0, 8, first + size)


def _second_allocate(m, allocator, size):
    """The second allocator's Allocate(size) at init: whole pages carved from the end of its free run
    (heap._page_alloc), after the descriptor page that Allocate(allocatable) took off the run's start
    (its span merges back into the run on Free, the run's descriptor surviving, 0x518ccec). The commit
    bitmap (a byte per 0x40000 bytes from +0x18) marks the chunks Allocate(allocatable) committed 2
    and those of this span 1, as the SDK's code leaves them run under unicorn."""
    h = m.u64(allocator + 0x18)
    commit = m.u8(h + 0x2C)
    m.put(h + 0x2C, 1, 0)
    heap._new_descriptor_page(m, h)
    run = m.u64(h + 0x60 + 8 * 0xFF)
    end = m.u64(run + 0x18) + (m.u64(run + 0x20) << 12)
    span = heap._page_alloc(m, h, ((size + 0xFFF) & M64) >> 12)
    m.put(h + 0x2C, 1, commit)
    first = m.u64(span + 0x18)
    if commit:
        bitmap = m.u64(h + 0x18)
        for lo, value in ((end - ((m.env.allocatable + 0xFFF) & ~0xFFF), 2), (first, 1)):
            i, j = (lo - h) >> 18, (end - 1 - h) >> 18
            m.write(bitmap + i, bytes([value]) * (j + 1 - i))
    return first


def build(m):
    """Lay the game's heap and allocator statics into arena `m` as 0x2b7da90 leaves them, then the
    thread-block slot (0xb4e600's static). Returns `m`."""
    env = m.env
    m.put(m.tls + 0x1F8, 8, ARENA_THREAD)
    m.put(ARENA_THREAD + 0x1B0, 4, env.thread_handle)
    _seed_generator(m, env.entropy)
    if env.memory_total >= 0x100000001:
        m.put(m.main + 0x475942C, 1, 1)
    _pair(m, env)
    inner = m.main + INNER
    m.put(inner + 0x10, 8, 0); m.put(inner + 0x18, 8, 0)
    vt = m.u64(m.main + 0x46E2480)
    m.put(inner, 8, vt + 0x10); m.put(inner + 8, 8, vt + 0x130)
    limits = ((env.program_size + 0xB6800000) & M64, (env.allocatable_after - 0xBEA00000) & M64)
    names = (0x3B78A9B, 0x3B935D3)
    with m.frame(0x20) as f:
        m.put(f + 0x10, 8, inner)
        for obj, slot, limit, name in zip(COUNTED, COUNTED_SLOTS, limits, names):
            m.put(f, 8, limit)
            m.call_void(m.main + 0x13ECA54, m.main + obj, f, f + 0x10)
            m.put(m.main + slot, 8, m.main + obj)
            m.vcall_void(m.main + obj, 0xE0, m.main + name)
    m.call_void(m.main + 0x343FA50, m.main + 0x2B7DBE8, m.main + 0x2B7DC04)
    _fs_set_allocator(m, m.main + 0x2B7DC94, m.main + 0x2B7DCB0)
    # 0x2a28e70's size queries of the committing heap cache nn::os::IsVirtualAddressMemoryEnabled
    # (0x51e80c0) in u8 sdk 0x5bc1690 under pthread_once 0x5bc1694 (done: -1)
    m.put(m.main + 0x5BC1690, 1, 1); m.put(m.main + 0x5BC1694, 4, M32)
    m.call_void(m.main + 0x13041AC, 0)
    m.put(m.main + 0x4759428, 1, 1)
    _slot_static(m, BLOCK_SLOT, BLOCK_GUARD, 0x2AAAD48)
    return m


def new(static, env=None):
    """An arena with the game's heap built: `static(page)` gives the loaded image's bytes or None."""
    return build(Arena(static, env))
