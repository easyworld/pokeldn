"""The heap the battle server allocates from: the game's guarded pair of nn::mem::StandardAllocator
(main+0x4740ee0) and the SDK allocator under it, a thread cache over a page heap of spans
(docs/sv_raid.md, The house engine). SDK functions are keyed by their offset from main (SDK address
minus main), as the replay maps them. Every SDK entry runs on a transaction: a path this port does not
reproduce refuses the call with nothing written.

Layout, as the code reads it:
  allocator (0x48): +1 u8 thread cache on, +0x10 u32 TLS slot of the thread cache
  thread cache: +8 alloc fn, +0x10 free fn, +0x38 u64 XOR key of the free-list links, +0x40 heap,
    +0x48 u64 large-request limit (x4), +0x54 s32 cached bytes, +0x58 s32 class with the most cached
    bytes, +0x60 + 8*class list head (key ^ object; each object holds the next head), +0x228 + 4*class
    s32 cached bytes, +0x30c + class u8 refill batch
  heap: +0 u64 pages, +8 page -> span table, +0x10 page -> class bytes, +0x24/+0x28 s32 release
    thresholds, +0x2c u8 commit flag, +0x30 nn::os::Mutex, +0x50/+0x58 descriptor page lists,
    +0x60 + 8*(pages-1) free run lists (>= 0x100 pages share +0x858), +0x860 4-word non-empty bitmap,
    +0x880 + 8*class partial span lists
  span (0x70, in a descriptor page at +0x90 + 0x70*i): +0 next, +8 prev link, +0x10 u16 objects out,
    +0x12 u8 class, +0x13 u8 state (1 used, 2 free run, 3 skipped), +0x14 u32 core, +0x18 start,
    +0x20 pages, +0x28 raw free list, +0x30 8-word object bitmap
  descriptor page: +0 next, +8 prev link, +0x10 u64 slot bitmap from the top bit, +0x18 u16 free slots
  class table: [main+0x5b54fe8] u8 class by (size + 15) >> 4; [main+0x5b54f78] 4 bytes per class:
    +0 u16 pages per span, +2 u16 object size
"""

from pokeldn.sv.battle.machine import FUNCTIONS, MASK, Machine, UnliftedCall, lifted

M64 = MASK[8]
M32 = MASK[4]
PAGE = 0x1000

ALLOCATORS = 0x4740EE0          # two StandardAllocator, +0x98/+0xa0 the first one's range
ALLOCATORS_GUARD = 0x4740F88
CLASS_INDEX = 0x5B54FE8         # SDK data: pointer to the class-by-size bytes
CLASS_INFO = 0x5B54F78          # SDK data: pointer to the class records
CANCEL_KEY = 0x5B0EDF8          # SDK data: u32, -1 when no thread cancellation state exists
TC_ALLOC = 0x5189EF0
TC_FREE = 0x518A220
CLASSES = 0x39
SLOT_DIV7 = 0x6DB6DB6DB6DB6DB7  # the inverse of 7: descriptor offset / 0x70


class _Tx(Machine):
    """Reads through to `base`, buffers every write; `commit` stores the bytes that changed."""

    def __init__(self, base):
        super().__init__(pages=None, main=base.main, stack=base.sp, tls=base.tls)
        self.base = base
        self.cache = {}
        self.orig = {}

    def page(self, address):
        p = address & ~(PAGE - 1)
        b = self.cache.get(p)
        if b is None:
            b = self.cache[p] = bytearray(self.base.read(p, PAGE))
        return b

    def write(self, address, data):
        i = 0
        while i < len(data):
            p = address & ~(PAGE - 1)
            if p not in self.orig:
                self.orig[p] = bytes(self.page(p))
            o = address & (PAGE - 1); k = min(len(data) - i, PAGE - o)
            self.cache[p][o:o + k] = data[i:i + k]; address += k; i += k

    def commit(self):
        for p, old in self.orig.items():
            new = self.cache[p]
            i = 0
            while i < PAGE:
                if new[i] == old[i]:
                    i += 1; continue
                j = i
                while j < PAGE and new[j] != old[j]:
                    j += 1
                self.base.write(p + i, bytes(new[i:j]))
                i = j


def _transaction(m, fn, *args):
    t = _Tx(m)
    r = fn(t, *args)
    t.commit()
    return r


def _s32(v):
    v &= M32
    return v - (1 << 32) if v >> 31 else v


def _refuse(why):
    raise UnliftedCall(why)


def _cinfo(t):
    return t.u64(t.main + CLASS_INFO)


def _object_size(t, cls):
    return t.u16(_cinfo(t) + 4 * cls + 2)


def _unlink(t, n):
    nx = t.u64(n)
    if nx:
        t.put(nx + 8, 8, t.u64(n + 8))
    pv = t.u64(n + 8)
    if pv:
        t.put(pv, 8, t.u64(n))
    t.put(n, 8, 0); t.put(n + 8, 8, 0)


def _push(t, head, n):
    t.put(n, 8, t.u64(head)); t.put(n + 8, 8, head)
    first = t.u64(head)
    if first:
        t.put(first + 8, 8, n)
    t.put(head, 8, n)


def _run_list(pages):
    return 0xFF if pages > 0xFF else pages - 1


def _bitmap_set(t, heap, i):
    w = heap + ((i >> 3) & 0x1FFFFFFFFFFFFFF8) + 0x860
    t.put(w, 8, t.u64(w) | (1 << (i & 63)))


def _bitmap_clear_if_empty(t, heap, i):
    if t.u64(heap + 0x60 + 8 * i) == 0:
        w = heap + ((i >> 3) & 0x1FFFFFFFFFFFFFF8) + 0x860
        t.put(w, 8, t.u64(w) & ~(1 << (i & 63)) & M64)


def _table_slot(t, heap, address):
    return t.u64(heap + 8) + ((((address - heap) & M64) >> 9) & 0x7FFFFFFFFFFFF8)


def _slot_bit(d):
    """The descriptor's bit in its page's bitmap: slot ((d & 0xfff) - 0x90) / 0x70 from the top."""
    return (1 << 63) >> ((((d & 0xFFF) - 0x90) >> 4) * SLOT_DIV7 & 63)


def _release_descriptor(t, heap, d):
    """A span descriptor goes back to its page; a page that was full rejoins the list at +0x50."""
    t.put(d + 0x13, 1, 0)
    page = d & ~0xFFF & M64
    t.put(page + 0x10, 8, t.u64(page + 0x10) & ~_slot_bit(d) & M64)
    free = t.u16(page + 0x18)
    t.put(page + 0x18, 2, free + 1)
    if free == 0:
        _unlink(t, page)
        _push(t, heap + 0x50, page)


# --- nn::os ----------------------------------------------------------------------------------------

def _cancel_state(t):
    """0x51882f0 (pthread_setcancelstate): nothing to do while no cancellation key exists."""
    if t.u32(t.main + CANCEL_KEY) != M32:
        _refuse("thread cancellation state")


def _lock(t, mutex, cancel=True):
    """nn::os::LockMutex 0x51e2be0 on an uncontended non-recursive mutex (+0x18 the owner handle);
    `cancel`: the pthread wrapper's cancel-state calls around it."""
    if cancel:
        _cancel_state(t)
    thread = t.u64(t.tls + 0x1F8)
    if t.u8(mutex + 1):
        _refuse("recursive mutex")
    if t.u32(mutex + 0x18):
        _refuse("contended mutex")
    t.put(mutex + 0x18, 4, t.u32(thread + 0x1B0))
    t.put(mutex + 8, 4, t.u32(mutex + 8) + 1)
    t.put(mutex + 0x10, 8, thread)
    if cancel:
        _cancel_state(t)


def _unlock(t, mutex):
    """nn::os::UnlockMutex 0x51e2ca0; a waiter bit in the lock word needs the kernel."""
    n = (t.u32(mutex + 8) - 1) & M32
    t.put(mutex + 8, 4, n)
    if n:
        return
    t.put(mutex + 0x10, 8, 0)
    handle = t.u32(t.u64(t.tls + 0x1F8) + 0x1B0)
    if t.u32(mutex + 0x18) != handle or handle & 0x40000000:
        _refuse("mutex with waiters")
    t.put(mutex + 0x18, 4, 0)


# --- the page heap ---------------------------------------------------------------------------------

def _find_run(t, heap, n):
    """0x518bcf8: the free run for `n` pages: the first non-empty exact-or-larger list below 0xff;
    in the shared list the smallest run (lowest address on ties, highest for n >= 0x100)."""
    if n >= 0x100:
        best, cur = 0, t.u64(heap + 0x858)
        while cur:
            size = t.u64(cur + 0x20)
            if size >= n:
                if best == 0:
                    best = cur
                else:
                    other = t.u64(best + 0x20)
                    if size < other:
                        best = cur
                    elif size == other and t.u64(cur + 0x18) > t.u64(best + 0x18):
                        best = cur
            cur = t.u64(cur)
        return best
    x10 = (n - 1) & M64
    if x10 > 0xFF:
        return 0
    word = x10 >> 6
    bits = t.u64(heap + 0x860 + 8 * word) & ((M64 << (x10 & 63)) & M64)
    while not bits:
        word += 1
        if word > 3:
            return 0
        bits = t.u64(heap + 0x860 + 8 * word)
    i = ((bits & -bits).bit_length() - 1) | (word << 6)
    if i == 0x100:
        return 0
    head = t.u64(heap + 0x60 + 8 * i)
    if i != 0xFF:
        if head == 0:
            _refuse("free run bitmap out of step")
        return head
    best = cur = head
    while cur:
        size, other = t.u64(cur + 0x20), t.u64(best + 0x20)
        if size < other or (size == other and t.u64(cur + 0x18) < t.u64(best + 0x18)):
            best = cur
        cur = t.u64(cur)
    return best


def _carve(t, heap, run, n, d):
    """0x518be64: `n` pages off free run `run` into descriptor `d` (from the end when n > 0xff)."""
    start, pages = t.u64(run + 0x18), t.u64(run + 0x20)
    rest = (pages - n) & M64
    big = n > 0xFF
    kept = (start + (0 if big else n << 12)) & M64
    taken = (start + ((rest << 12) if big else 0)) & M64
    if rest > 0xFF:
        slot = _table_slot(t, heap, start)
        if big:
            if pages != 1:
                t.put(slot + 8 * pages - 8, 8, 0)
            t.put(slot + 8 * rest - 8, 8, run)
        else:
            t.put(slot, 8, 0)
            t.put(slot + 8 * t.u64(run + 0x20) - 8, 8, 0)
            slot = _table_slot(t, heap, kept)
            t.put(slot, 8, run)
            t.put(slot + 8 * rest - 8, 8, run)
            t.put(run + 0x18, 8, kept)
        t.put(run + 0x20, 8, rest)
    else:
        i = _run_list(pages)
        _unlink(t, run)
        _bitmap_clear_if_empty(t, heap, i)
        first = t.u64(run + 0x18)
        slot = _table_slot(t, heap, first)
        i = rest - 1
        if first == kept:
            old = t.u64(run + 0x20)
            if old != 1:
                t.put(slot + 8 * old - 8, 8, 0)
            t.put(slot + 8 * i, 8, run)
        else:
            t.put(slot, 8, 0)
            t.put(slot + 8 * t.u64(run + 0x20) - 8, 8, 0)
            slot = _table_slot(t, heap, kept)
            t.put(slot, 8, run)
            t.put(slot + 8 * i, 8, run)
            t.put(run + 0x18, 8, kept)
        t.put(run + 0x20, 8, rest)
        _push(t, heap + 0x60 + 8 * i, run)
        _bitmap_set(t, heap, i)
    t.put(d + 0x18, 8, taken); t.put(d + 0x20, 8, n)
    t.put(d + 0x12, 2, 0x100)
    t.put(d + 0x14, 4, 0); t.put(d + 0x28, 4, 0); t.put(run + 0x28, 4, 0)
    if t.u8(heap + 0x2C):
        _refuse("heap commits pages")
    t.put(d + 0x12, 1, 0)
    slot = _table_slot(t, heap, t.u64(d + 0x18))
    t.put(slot, 8, d)
    t.put(slot + 8 * t.u64(d + 0x20) - 8, 8, d)
    return d


def _page_alloc(t, heap, n):
    """0x518b7c4: a span of `n` pages: a free run of exactly that size, or a new descriptor carved
    from a larger one."""
    if n >= t.u64(heap) >> 2:
        _refuse("page request over a quarter of the heap")
    run = _find_run(t, heap, n)
    if not run:
        _refuse("no free run")
    size = t.u64(run + 0x20)
    if size == n:
        if t.u8(heap + 0x2C):
            _refuse("heap commits pages")
        i = _run_list(t.u64(run + 0x20))
        _unlink(t, run)
        _bitmap_clear_if_empty(t, heap, i)
        t.put(run + 0x13, 1, 1); t.put(run + 0x14, 4, 0); t.put(run + 0x28, 4, 0)
        return run
    start = t.u64(run + 0x18)
    page = t.u64(heap + 0x50)
    while page and (t.u8(page + 0x1A) == 1 or t.u64(page + 0x10) == M64):
        page = t.u64(page)
    if not page:
        _refuse("new descriptor page")
    used = t.u64(page + 0x10)
    i = 64 - ((~used) & M64).bit_length()
    t.put(page + 0x10, 8, used | ((1 << 63) >> i))
    free = (t.u16(page + 0x18) - 1) & 0xFFFF
    t.put(page + 0x18, 2, free)
    d = page + i * 0x70 + 0x90
    t.put(d, 8, 0); t.put(d + 0x10, 4, 0); t.put(d + 8, 8, 0)
    if free == 0:
        _unlink(t, page)
        _push(t, heap + 0x58, page)
    k = ((start - heap) & M64) >> 12
    run = t.u64(t.u64(heap + 8) + 8 * k) if k < t.u64(heap) else 0
    if not run or t.u64(run + 0x20) != size:
        _refuse("free run moved")
    return _carve(t, heap, run, n, d)


def _coalesce(t, heap, span):
    """0x518ccec: free run `span` joins the lists, merged with a following free run under 0x100
    pages; a free run before it is not reproduced."""
    start, total, table = t.u64(span + 0x18), t.u64(heap), t.u64(heap + 8)
    k = ((start - heap - 1) & M64) >> 12
    before = t.u64(table + 8 * k) if k < total else 0
    pages = t.u64(span + 0x20)
    k = ((start + (pages << 12) - heap) & M64) >> 12
    after = t.u64(t.u64(heap + 8) + 8 * k) if k < total else 0
    if before and t.u8(before + 0x13) == 2:
        _refuse("merge with the run before")
    if after and t.u8(after + 0x13) == 2:
        n = t.u64(after + 0x20)
        if n >= 0x100:
            _refuse("merge with a large run after")
        _unlink(t, after)
        _bitmap_clear_if_empty(t, heap, n - 1)
        a_start, a_pages = t.u64(after + 0x18), t.u64(after + 0x20)
        k = ((a_start - heap) & M64) >> 12
        s_start, s_pages = t.u64(span + 0x18), t.u64(span + 0x20)
        t.put(t.u64(heap + 8) + 8 * k, 8, 0)
        merged = (a_pages + s_pages) & M64
        t.put(t.u64(heap + 8) + 8 * (k + t.u64(after + 0x20)) - 8, 8, 0)
        _release_descriptor(t, heap, after)
        first = t.u64(span + 0x18)
        slot = _table_slot(t, heap, first)
        if first == s_start:
            old = t.u64(span + 0x20)
            if old != 1:
                t.put(slot + 8 * old - 8, 8, 0)
            t.put(slot + 8 * merged - 8, 8, span)
        else:
            t.put(slot, 8, 0)
            t.put(slot + 8 * t.u64(span + 0x20) - 8, 8, 0)
            slot = _table_slot(t, heap, s_start)
            t.put(slot, 8, span)
            t.put(slot + 8 * merged - 8, 8, span)
            t.put(span + 0x18, 8, s_start)
        t.put(span + 0x20, 8, merged)
        pages = t.u64(span + 0x20)
    i = _run_list(pages)
    _push(t, heap + 0x60 + 8 * i, span)
    _bitmap_set(t, heap, i)


def _free_span(t, heap, span):
    """0x518af2c: a span's pages become a free run."""
    if t.u8(span + 0x13) == 2:
        _refuse("span freed twice")
    t.put(span + 0x13, 1, 2)
    if t.u8(heap + 0x2C):
        _refuse("heap decommits pages")
    _coalesce(t, heap, span)


# --- spans of small objects ------------------------------------------------------------------------

def _take_objects(t, span, tc, most):
    """0x518ec30: up to `most` objects off a span's raw free list, relinked under the cache's key.
    Returns (count, first link, last object)."""
    x8 = t.u64(span + 0x28)
    if x8 == 0:
        return 0, 0, 0
    first = t.u64(tc + 0x38) ^ x8
    base = t.u64(span + 0x18)
    if base > x8:
        _refuse("free list outside its span")
    end = (base + (t.u64(span + 0x20) << 12)) & M64
    if end <= x8:
        _refuse("free list outside its span")
    size = _object_size(t, t.u8(span + 0x12))
    n = 0
    x9 = x8
    while True:
        k = ((x9 - base) & M64) // size
        if (k * size + base) & M64 != x9:
            _refuse("misaligned free object")
        w = span + 0x30 + ((k >> 3) & 0x1FFFFFFFFFFFFFF8)
        bit = 1 << (k & 63)
        v = t.u64(w)
        if v & bit:
            _refuse("free object already out")
        t.put(w, 8, v | bit)
        x9 = t.u64(x8)
        n += 1
        t.put(x8, 8, t.u64(tc + 0x38) ^ x9)
        if most <= n & 0xFFFF or x9 == 0:
            break
        base = t.u64(span + 0x18)
        if base > x9 or end <= x9:
            _refuse("free list outside its span")
        x8 = x9
    t.put(x8, 8, 0)
    t.put(span + 0x28, 8, x9)
    t.put(span + 0x10, 2, t.u16(span + 0x10) + n)
    return n & 0xFFFF, first, x8


def _new_span(t, heap, cls, core):
    """0x518e82c..: a fresh span for `cls`, its objects chained in address order."""
    cinfo = _cinfo(t)
    span = _page_alloc(t, heap, t.u16(cinfo + 4 * cls))
    if not span:
        _refuse("out of pages")
    start, pages = t.u64(span + 0x18), t.u64(span + 0x20)
    k = ((start - heap) & M64) >> 12
    t.put(span + 0x12, 1, cls)
    table = t.u64(heap + 8)
    for i in range(pages):
        t.put(table + 8 * (k + i), 8, span)
    t.write(t.u64(heap + 0x10) + k, bytes([cls]) * t.u64(span + 0x20))
    _push(t, heap + 0x880 + 8 * cls, span)
    t.put(span + 0x10, 2, 0)
    start, pages = t.u64(span + 0x18), t.u64(span + 0x20)
    t.put(span + 0x28, 8, start)
    t.put(span + 0x12, 1, cls)
    t.put(span + 0x14, 4, core)
    size = t.u16(cinfo + 4 * cls + 2)
    total = (((pages << 12) & M64) // size) * size
    x8 = start
    if total != size:
        if total < 2 * size:
            _refuse("span holds no object")
        end, x11, x12 = start + total, start + size, start
        while True:
            x8 += size
            x13 = x8 + size
            t.put(x12, 8, x8)
            x12 = x11
            x11 += size
            if x13 == end:
                break
    t.put(x8, 8, 0)
    t.write(span + 0x30, bytes(0x40))
    return span


def _refill(t, heap, tc, cls, want, core):
    """0x518e750: up to `want` objects of `cls` from the partial spans of this core, then a new span.
    Returns (count, first link)."""
    got, head, link = 0, 0, None

    def store(v):
        nonlocal head
        if link is None:
            head = v
        else:
            t.put(link, 8, v)

    span = None
    s = t.u64(heap + 0x880 + 8 * cls)
    while s:
        if t.u8(s + 0x13) != 3 and t.u32(s + 0x14) == core:
            n, first, last = _take_objects(t, s, tc, (want - got) & M64)
            if n:
                store(first); link = last
                got += n
                t.put(link, 8, 0)
                if got >= want:
                    span = s
                    break
            nx = t.u64(s)
            _unlink(t, s)
            s = nx
            continue
        s = t.u64(s)
    if span is None:
        span = _new_span(t, heap, cls, core)
        n, first, last = _take_objects(t, span, tc, (want - got) & M64)
        store(first)
        got += n
        t.put(last, 8, 0)
    if t.u64(span + 0x28) == 0:
        _unlink(t, span)
    return got, head


def _span_free(t, heap, p):
    """0x518eda0: object `p` back to its span; an emptied span returns its pages."""
    k = ((p - heap) & M64) >> 12
    if k >= t.u64(heap):
        _refuse("free outside the heap")
    span = t.u64(t.u64(heap + 8) + 8 * k)
    if not span or not t.u8(span + 0x12):
        _refuse("free of no small object")
    cls = t.u8(span + 0x12)
    if t.u64(span + 0x28) == 0:
        _push(t, heap + 0x880 + 8 * cls, span)
        cls = t.u8(span + 0x12)
    off = (p - t.u64(span + 0x18)) & M64
    size = _object_size(t, cls)
    i = off // size
    if i * size != off:
        _refuse("misaligned free")
    w = span + 0x30 + ((i >> 3) & 0x1FFFFFFFFFFFFFF8)
    bit = 1 << (i & 63)
    v = t.u64(w)
    if not v & bit:
        _refuse("object freed twice")
    t.put(w, 8, v & ~bit)
    t.put(p, 8, t.u64(span + 0x28))
    n = (t.u16(span + 0x10) - 1) & 0xFFFF
    t.put(span + 0x28, 8, p)
    t.put(span + 0x10, 2, n)
    if n:
        return
    t.put(span + 0x28, 8, 0)
    _unlink(t, span)
    k = ((t.u64(span + 0x18) - heap) & M64) >> 12
    slot = t.u64(heap + 8) + 8 * k
    size = (t.u64(span + 0x20) << 3) & M64
    t.write(slot, bytes(size))
    t.put(span + 0x12, 1, 0)
    t.put(slot, 8, span)
    t.put(slot + size - 8, 8, span)
    t.write(t.u64(heap + 0x10) + k, bytes(t.u64(span + 0x20)))
    _free_span(t, heap, span)


def _release(t, heap, tc, chain):
    """0x5188f94: a cache list (`chain`, a key-linked head) back to the spans, under the heap lock."""
    _lock(t, heap + 0x30)
    while chain:
        p = t.u64(tc + 0x38) ^ chain
        chain = t.u64(p)
        _span_free(t, heap, p)
    _unlock(t, heap + 0x30)


# --- the thread cache ------------------------------------------------------------------------------

def _large(t, tc, size):
    """0x5189fc8: whole pages from the heap under its lock."""
    if size >= t.u64(tc + 0x48) >> 2:
        _refuse("cache flush before a large allocation")
    heap = t.u64(tc + 0x40)
    _lock(t, heap + 0x30)
    span = _page_alloc(t, heap, ((size + 0xFFF) & M64) >> 12)
    r = t.u64(span + 0x18) if span else 0
    _unlock(t, heap + 0x30)
    return r


def _tc_alloc(t, tc, size, align):
    """0x5189ef0: the thread cache's allocate."""
    if size >> 63 or bin(align).count("1") > 1:
        return 0
    if align > PAGE:
        _refuse("allocation aligned past a page")
    n = (size + align - 1) & (-align & M64) & M64
    cidx, cinfo = t.u64(t.main + CLASS_INDEX), _cinfo(t)
    if n + 0xF >= 0xC00:
        return _large(t, tc, n)
    if n == 0:
        if t.u8(cidx):
            return 0
        _refuse("allocation of nothing")
    c = t.u8(cidx + ((n + 0xF) >> 4))
    size = None
    while c:
        s = t.u16(cinfo + 4 * c + 2)
        if (align + 0xFFFF) & s == 0:
            size = s
            break
        c = (c + 1) & 0xFF
        if c == CLASSES:
            break
    if size is None:
        return _large(t, tc, PAGE)
    if size >= 0xBF1:
        return _large(t, tc, size)
    cls = t.u8(cidx + ((size + 0xF) >> 4))
    if cls == 0:
        return _large(t, tc, size)
    if size == 0:
        return 0
    slot = tc + 0x60 + 8 * cls
    head = t.u64(slot)
    if head == 0:
        batch = t.u8(tc + 0x30C + cls)
        heap = t.u64(tc + 0x40)
        core = 0    # svc 0x10 GetCurrentProcessorNumber, as the replay answers it (classes 0..7 only)
        _lock(t, heap + 0x30)
        got, head = _refill(t, heap, tc, cls, batch, core)
        _unlock(t, heap + 0x30)
        if got == 0:
            return 0
        b = batch + 1 if batch < 0x40 else batch
        t.put(tc + 0x30C + cls, 1, got if got & 0xFF > b & 0xFF else b)
        add = ((got - 1) * t.u16(cinfo + 4 * cls + 2)) & M32
        cached = (t.u32(tc + 0x228 + 4 * cls) + add) & M32
        t.put(tc + 0x228 + 4 * cls, 4, cached)
        if _s32(cached) > _s32(t.u32(tc + 0x228 + 4 * _s32(t.u32(tc + 0x58)))):
            t.put(tc + 0x58, 4, cls)
        t.put(tc + 0x54, 4, t.u32(tc + 0x54) + add)
    p = t.u64(tc + 0x38) ^ head
    t.put(slot, 8, t.u64(p))
    return p


def _tc_free(t, tc, p):
    """0x518a220: the thread cache's free; past a threshold the class holding the most bytes goes
    back to the heap."""
    heap = t.u64(tc + 0x40)
    k = ((p - heap) & M64) >> 12
    if k >= t.u64(heap):
        _refuse("free outside the heap")
    cls = t.u8(t.u64(heap + 0x10) + k)
    if cls == 0:
        if p & 0xFFF:
            _refuse("free of a misaligned page")
        _lock(t, heap + 0x30)
        span = t.u64(t.u64(heap + 8) + 8 * k)
        if not span:
            _refuse("free of no span")
        _free_span(t, heap, span)
        _unlock(t, heap + 0x30)
        return 0
    slot = tc + 0x60 + 8 * cls
    t.put(p, 8, t.u64(slot))
    t.put(slot, 8, t.u64(tc + 0x38) ^ p)
    size = _object_size(t, cls)
    total = (t.u32(tc + 0x54) + size) & M32
    t.put(tc + 0x54, 4, total)
    cached = (t.u32(tc + 0x228 + 4 * cls) + size) & M32
    t.put(tc + 0x228 + 4 * cls, 4, cached)
    most = _s32(t.u32(tc + 0x58))
    if _s32(cached) > _s32(t.u32(tc + 0x228 + 4 * most)):
        most = cls
        t.put(tc + 0x58, 4, cls)
    heap = t.u64(tc + 0x40)
    if _s32(t.u32(heap + 0x28)) > _s32(total) and _s32(t.u32(heap + 0x24)) > _s32(total):
        return 0
    _release(t, heap, tc, t.u64(tc + 0x60 + 8 * most))
    most = _s32(t.u32(tc + 0x58))
    t.put(tc + 0x60 + 8 * most, 8, 0)
    t.put(tc + 0x54, 4, t.u32(tc + 0x54) - t.u32(tc + 0x228 + 4 * most))
    t.put(tc + 0x228 + 4 * most, 4, 0)
    best, value = 0, -1
    for i in range(CLASSES):
        v = _s32(t.u32(tc + 0x228 + 4 * i))
        if value < v:
            best, value = i, v
    t.put(tc + 0x58, 4, best)
    return 0


# --- making a thread's cache ----------------------------------------------------------------------

RANDOM_LOCK = 0x5B13248         # SDK data: nn::os::Mutex over the generator below
RANDOM_READY = 0x5BD9430        # SDK data: u8, bit 0 once the generator is seeded
RANDOM_STATE = 0x5BD9434        # SDK data: TinyMT32 state, 4 u32
CACHE_FUNCTIONS = 0x5B54F80     # SDK GOT: 7 pairs of cache functions, the second of each pair
                                # when flag bit 2 is clear (+0x5189ef0 / +0x518a220 at +8 / +0x10)


def _tinymt(t, state):
    """One TinyMT32 output (mat1 0x8f7011ee, mat2 0xfc78ff1f, tmat 0x3793fdff), state advanced."""
    s0, s1, s2, s3 = (t.u32(state + 4 * i) for i in range(4))
    x = ((s0 & 0x7FFFFFFF) ^ s1 ^ s2) & M32
    x = (x ^ (x << 1)) & M32
    y = (s3 ^ (s3 >> 1) ^ x) & M32
    n2 = (x ^ (y << 10)) & M32
    n1 = s2
    if y & 1:
        n1 ^= 0x8F7011EE
        n2 ^= 0xFC78FF1F
    t.put(state, 4, s1); t.put(state + 4, 4, n1); t.put(state + 8, 4, n2); t.put(state + 0xC, 4, y)
    t1 = (s1 + (n2 >> 8)) & M32
    t0 = y ^ t1
    return t0 ^ 0x3793FDFF if t1 & 1 else t0


def _random(t, dst, n):
    """0x51e2ce0 (through 0x5183970): `n` bytes of the SDK's TinyMT32 generator, under its lock;
    0x525f448 fills whole aligned words only here."""
    lock = t.main + RANDOM_LOCK
    _lock(t, lock, cancel=False)
    if not t.u8(t.main + RANDOM_READY) & 1:
        _refuse("random generator not seeded")
    if dst & 3 or n & 3:
        _refuse("random bytes off a word boundary")
    for i in range(0, n, 4):
        t.put(dst + i, 4, _tinymt(t, t.main + RANDOM_STATE))
    _unlock(t, lock)


def _heap_object(t, heap, cls):
    """0x518e0f8(heap, cls, 0, 1): one object for the allocator's own use, off the first partial span
    of `cls` in state 3 (plain free links); an emptied span leaves the list."""
    cinfo = _cinfo(t)
    s = t.u64(heap + 0x880 + 8 * cls)
    while s:
        if t.u8(s + 0x13) != 3:
            s = t.u64(s)
            continue
        p, base = t.u64(s + 0x28), t.u64(s + 0x18)
        if base > p or (base + (t.u64(s + 0x20) << 12)) & M64 <= p:
            if p:
                _refuse("abort: free list outside its span")
            t.put(s + 0x28, 8, 0)
            nx = t.u64(s)
            _unlink(t, s)
            s = nx
            continue
        size = t.u16(cinfo + 4 * t.u8(s + 0x12) + 2)
        k = (p - base) // size
        if k * size + base != p:
            _refuse("abort: misaligned free object")
        w = s + 0x30 + ((k >> 3) & 0x1FFFFFFFFFFFFFF8)
        bit = 1 << (k & 63)
        v = t.u64(w)
        if v & bit:
            _refuse("abort: free object already out")
        t.put(w, 8, v | bit)
        t.put(s + 0x28, 8, t.u64(p))
        t.put(p, 8, 0)
        t.put(s + 0x10, 2, t.u16(s + 0x10) + 1)
        if t.u64(s + 0x28) == 0:
            _unlink(t, s)
        return p
    _refuse("allocator object needs a new span")


def _construct_cache(t, tc, heap, flags):
    """0x51892e4: function table, XOR key (random | 1), heap, large limit, empty lists, batches."""
    g = t.main + CACHE_FUNCTIONS
    pick = 8 if flags & 4 == 0 else 0
    for field, pair in ((0, 0), (8, 0x10), (0x10, 0x20), (0x18, 0x30), (0x30, 0x50)):
        t.put(tc + field, 8, t.u64(g + pair + pick))
    t.put(tc + 0x20, 8, t.u64(g + 0x60))
    t.put(tc + 0x28, 8, t.u64(g + 0x40 + (0 if pick else 8)))
    _random(t, tc + 0x38, 8)        # 0x5183970 returns 0: the key is always the random word
    t.put(tc + 0x38, 8, t.u64(tc + 0x38) | 1)
    t.put(tc + 0x40, 8, heap)
    t.put(tc + 0x50, 4, flags)
    t.put(tc + 0x48, 8, (t.u64(heap) << 12) & M64)
    t.put(tc + 0x54, 8, 0)
    t.write(tc + 0x60, bytes(0x2AC))
    t.write(tc + 0x30C, bytes([1, 0x40, 0x40, 0x40, 0x20, 0x20, 0x20, 0x10, 0x10, 0x10]) + b"\1" * 0x2F)


def _create_cache(t, allocator):
    """0x51908b4 (with the holder calls 0x5191f54 / 0x5191f88 / 0x5191f28 and nn::os::SetTlsValue
    0x51e6fe0): a cache object from the heap, built, counted in the heap's release threshold
    (+0x20 caches, +0x28 = heap bytes / (2 * caches)), and stored in the thread's slot."""
    src = allocator + 0x18
    heap = t.u64(src)
    _lock(t, heap + 0x30)
    tc = _heap_object(t, heap, t.u8(t.u64(t.main + CLASS_INDEX) + 0x35))
    _unlock(t, heap + 0x30)
    _construct_cache(t, tc, t.u64(src), t.u32(src + 0xC))
    heap = t.u64(src)
    _lock(t, heap + 0x30)
    n = (_s32(t.u32(heap + 0x20)) + 1) & M64
    t.put(heap + 0x20, 4, n)
    d = (n << 1) & M64
    t.put(heap + 0x28, 4, ((t.u64(heap) << 12) & M64) // d if d else 0)     # udiv by 0 is 0
    _unlock(t, heap + 0x30)
    t.put(_tls_slot(t, t.u32(allocator + 0x10)), 8, tc)
    return tc


def _tls_slot(t, slot):
    return t.u64(t.tls + 0x1F8) + 0x80 + 8 * slot


def _thread_cache(t, allocator, fn):
    """The calling thread's cache (nn::os::GetTlsValue of the allocator's slot), checked to run the
    cache functions this port reproduces; Allocate makes a missing one, Free falls to the heap."""
    if not t.u8(allocator + 1):
        _refuse("allocator without thread cache")
    tc = t.u64(_tls_slot(t, t.u32(allocator + 0x10)))
    if not tc:
        if fn != TC_ALLOC:
            _refuse("free on a thread without a cache (0x5433630)")
        tc = _create_cache(t, allocator)
    if t.u64(tc + (8 if fn == TC_ALLOC else 0x10)) != t.main + fn:
        _refuse("thread cache with other functions")
    return tc


def _allocate(t, allocator, size, align):
    r = _tc_alloc(t, _thread_cache(t, allocator, TC_ALLOC), size, align)
    if not r:
        _refuse("allocation failed: the allocator retries after a cleanup")
    return r


def _free(t, allocator, p):
    return _tc_free(t, _thread_cache(t, allocator, TC_FREE), p)


@lifted(0x5192224)
def standard_allocate(m, allocator, size, align, *_):
    """nn::mem::StandardAllocator::Allocate(size, alignment)."""
    return _transaction(m, _allocate, allocator, size, align)


@lifted(0x343EF50)
def standard_allocate_import(m, allocator, size, align, *_):
    return standard_allocate(m, allocator, size, align)


@lifted(0x5192320)
def standard_free(m, allocator, p, *_):
    """nn::mem::StandardAllocator::Free(pointer); a null pointer returns the allocator."""
    if p == 0:
        return allocator
    return _transaction(m, _free, allocator, p)


@lifted(0x343EF90)
def standard_free_import(m, allocator, p, *_):
    return standard_free(m, allocator, p)


@lifted(0x5189EF0)
def thread_cache_allocate(m, tc, size, align, *_):
    return _transaction(m, _tc_alloc, tc, size, align)


@lifted(0x518A220)
def thread_cache_free(m, tc, p, *_):
    return _transaction(m, _tc_free, tc, p)


# --- the game's side -------------------------------------------------------------------------------

def _guarded(m):
    """The allocator pair behind the guarded static 0x4740f88; its first construction is not
    reproduced."""
    if not m.u8(m.main + ALLOCATORS_GUARD) & 1:
        raise UnliftedCall("allocator pair not constructed")
    return m.main + ALLOCATORS


@lifted(0xB40E9C)
def heap_allocate(m, _self, size, align, *_):
    """Size and alignment to the pair: the second allocator for over 0x10000 bytes or alignment over
    0x10, the other one when the first choice fails."""
    a = _guarded(m)
    if size == 0:
        return 0
    i = int(size > 0x10000) | int(align > 0x10)
    r = standard_allocate(m, a + i * 0x48, size, align)
    if r:
        return r
    return standard_allocate(m, a + (i ^ 1) * 0x48, size, align)


@lifted(0x27B4D7C)
def heap_free(m, _self, p, *_):
    """The first allocator frees what lies in its range (+0x98, +0xa0), the second one the rest."""
    a = _guarded(m)
    i = int(m.u64(a + 0x98) > p) | int(m.u64(a + 0xA0) <= p)
    return standard_free(m, a + i * 0x48, p)


@lifted(0x2A64AF8)
def counted_allocate(m, this, size, align, *_):
    """Allocate through the allocator at +0x20 and count it: +0x38 the bytes (the size class when
    +0x50 is set, else the allocator's own measure, vtable +0x38), +0x40 the allocations."""
    if not m.u8(this + 0x50) and m.u64(m.u64(this) + 0x38) - m.main not in FUNCTIONS:
        raise UnliftedCall("allocation measure not lifted")
    inner = m.u64(this + 0x20)
    r = m.vcall(inner, 0x10, size, align)
    if r == 0:
        if size:
            raise UnliftedCall("allocation failed: AbortImpl")
        return 0
    n = m.call(m.main + 0xEE5860, size, align) if m.u8(this + 0x50) else m.vcall(this, 0x38, r)
    m.put(this + 0x38, 8, m.u64(this + 0x38) + n)
    m.put(this + 0x40, 8, m.u64(this + 0x40) + 1)
    return r


@lifted(0x2A64BC4)
def counted_free(m, this, p, size, align, *_):
    """Free through the allocator at +0x20 and uncount it; +0x38 stops at 0."""
    if p == 0:
        return this
    inner = m.u64(this + 0x20)
    for fn in (m.u64(inner) + 0xF8, m.u64(inner) + 0x18):
        if m.u64(fn) - m.main not in FUNCTIONS:
            raise UnliftedCall(f"main+0x{m.u64(fn) - m.main:x}")
    if size and align and m.u8(this + 0x50):
        n = m.call(m.main + 0xEE5860, size, align)
    else:
        n = m.vcall(this, 0x38, p)
    if m.vcall(inner, 0xF8) & 1:
        raise UnliftedCall("allocation tracing on: main+0xb48fe8")
    r = m.vcall(inner, 0x18, p, n, align)
    m.put(this + 0x40, 8, m.u64(this + 0x40) - 1)
    old = m.u64(this + 0x38)
    m.put(this + 0x38, 8, 0 if old < n else old - n)
    return r


# --- objects made on the heap ----------------------------------------------------------------------

def _scope_push(t, owner):
    """Push `owner` on the thread's allocator-scope stack (TLS slot [0x4765a30], count +0x80, at most
    16); refused while its static is not built. Returns the stack."""
    if t.u8(t.main + 0x4765A38) & 1 == 0:
        _refuse("static 0x4765a30 not built")
    stack = t.call(t.main + 0x343DA20, t.u32(t.main + 0x4765A30))
    if not stack:
        _refuse("thread without an allocator-scope stack")
    n = t.u64(stack + 0x80)
    if n >= 0x10:
        _refuse("abort: allocator-scope stack full")
    t.put(stack + 8 * n, 8, owner)
    t.put(stack + 0x80, 8, t.u64(stack + 0x80) + 1)
    return stack


def _scope_pop(t, stack):
    t.put(stack + 0x80, 8, t.u64(stack + 0x80) - 1)


def _new(t, owner, size):
    """`size` bytes, 8-aligned, from `owner`'s allocator (vtable +0x10); a failure aborts."""
    o = t.vcall(owner, 0x10, size, 8)
    if not o:
        _refuse("allocation failed: abort")
    return o


def _make_127d65c(t, owner):
    stack = _scope_push(t, owner)
    o = _new(t, owner, 0x38)
    t.put(o + 0x28, 8, 0); t.put(o + 0x30, 8, 0); t.put(o + 0x20, 8, 0)
    t.put(o, 8, t.u64(t.main + 0x46D66F8) + 0x10); t.put(o + 8, 8, 0)
    t.put(o + 0x10, 8, 0); t.put(o + 0x18, 8, 0); t.put(o + 0x18, 4, 0)
    if t.u8(t.main + 0x4765A38) & 1 == 0:
        _refuse("static 0x4765a30 not built")
    t.call(t.main + 0x343DA20, t.u32(t.main + 0x4765A30))
    t.put(o + 0x28, 4, 0)
    t.put(o, 8, t.main + 0x44EE4E0); t.put(o + 8, 8, owner)
    t.put(o + 0x20, 8, t.main + 0x44EE518)
    t.put(o + 0x30, 8, 0); t.put(o + 0x10, 8, o); t.put(o + 0x18, 4, 0x80038)
    _scope_pop(t, stack)
    return o


@lifted(0x127D65C)
def make_127d65c(m, _x0, owner, *_):
    """A 0x38-byte object from `owner`'s allocator (in its scope): vtables 0x44ee4e0 / 0x44ee518 at +0,
    +0x20, +8 the owner, +0x10 itself, u32 +0x18 0x80038 (size and alignment)."""
    return _transaction(m, _make_127d65c, owner)


def _make_fa19f8(t, owner, pa, pb):
    stack = _scope_push(t, owner)
    o = _new(t, owner, 0x720)
    t.call_void(t.main + 0xFA21A8, o, t.u64(pa), t.u64(pb))
    vt = t.u64(t.main + 0x46E2728)
    t.put(o + 0x71C, 4, 0); t.put(o + 0x710, 8, 0)
    t.put(o + 0x20, 8, vt + 0x838); t.put(o + 0x28, 8, vt + 0x888)
    t.put(o, 8, vt + 0x10); t.put(o + 8, 8, owner)
    t.put(o + 0x40, 8, vt + 0x8E0)
    t.put(o + 0x718, 2, 0)
    t.put(o + 0x10, 8, o); t.put(o + 0x18, 4, 0x80720)
    _scope_pop(t, stack)
    return o


@lifted(0xFA19F8)
def make_fa19f8(m, owner, pa, pb, *_):
    """A 0x720-byte object from `owner`'s allocator (in its scope), built by 0xfa21a8(o, *pa, *pb), then
    vtable [0x46e2728] (+0x10, +0x838, +0x888, +0x8e0 at +0, +0x20, +0x28, +0x40), +8 the owner, +0x10
    itself, u32 +0x18 0x80720, +0x710..+0x720 cleared."""
    return _transaction(m, _make_fa19f8, owner, pa, pb)
