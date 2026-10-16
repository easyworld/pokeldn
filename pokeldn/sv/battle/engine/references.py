"""Reference counting as the server compiles it: intrusive counters at +0x28, shared control blocks at
+0x30, weak handles and their table, the handle id pool, and the thread's object stack."""

from pokeldn.sv.battle.engine.calls import _need, _tail, _vtail
from pokeldn.sv.battle.engine.containers import _bucket_pc, _hash_find_u32
from pokeldn.sv.battle.machine import FUNCTIONS, UnliftedCall, lifted


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


@lifted(0xFA7B98)
def assign_strong_3(m, holder, p, *_):
    return _assign_strong(m, holder, p, "old")


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


@lifted(0x2844160)
def touch_shared_object(m, p, *_):
    """The object at [0xe7ecd0([p])+0x148], after taking and dropping one reference on its shared
    state (+0x30: u16 count +0x1a; the first reference builds the value at +8 through vf 0 of +0x10,
    the last one clears +0x10 and runs the object's vf 0x50). Abort paths are refused."""
    r = m.u64(m.call(m.main + 0xE7ECD0, m.u64(p)) + 0x148)
    if r == 0:
        return 0
    s = m.u64(r + 0x30)
    if m.u64(s + 0x10) == 0:
        raise UnliftedCall("AddReference abort: m_object is null")
    c = m.u16(s + 0x1A)
    m.put(s + 0x1A, 2, c + 1)
    if c == 0:
        m.put(s + 8, 8, m.vcall(m.u64(s + 0x10), 0))
        m.put(s + 0x1C, 4, 0xFFFFFFFE)
    elif c == 0xFFFF:
        raise UnliftedCall("AddReference abort: count overflow")
    s = m.u64(r + 0x30)
    c = m.u16(s + 0x1A)
    m.put(s + 0x1A, 2, c - 1)
    if c == 1:
        m.put(s + 0x10, 8, 0)
        m.vcall_void(r, 0x50)
    elif c == 0:
        raise UnliftedCall("Release abort: count underflow")
    return r


# An id pool: u32 base +0, next fresh id +4, ids in use +8; freed ids in a deque<u32> (block map
# [+0x18, +0x20), allocator +0x60, start +0x50, size +0x58, blocks of 1024); a bitset of ids in use
# (words [+0x88, +0x90), bit count +0xc0); lock (owner, 0) at +0xd0, light event +0xe0.


def _pool_lock(m, pool):
    from pokeldn.sv.battle.engine.libc import FAKE_THREAD
    if m.u64(pool + 0xD0) or m.u64(pool + 0xD8):
        raise UnliftedCall("id pool already locked")
    m.put(pool + 0xD0, 8, FAKE_THREAD); m.put(pool + 0xD8, 8, 0)


def _pool_unlock(m, pool):
    from pokeldn.sv.battle.engine.libc import signal_light_event
    m.put(pool + 0xD0, 8, 0)
    signal_light_event(m, pool + 0xE0)


def _free_block(m, alloc, block):
    if m.vcall(alloc, 0xF8) & 1 and m.s(m.call(m.main + 0xB4E600) + 0x12C8, 4) >= 1:
        m.call_void(m.main + 0xB48FE8, alloc, block, 0x1000, 4)
    else:
        m.vcall_void(alloc, 0x18, block, 0x1000, 4)


@lifted(0xC1A7A0)
def pool_take(m, pool, *_):
    """Take an id: the last freed one (the deque's back, dropping a spare block) or the next fresh one;
    mark it in the bitset (grown to cover it) and count it."""
    _pool_lock(m, pool)
    size = m.u64(pool + 0x58)
    if size == 0:
        ident = m.u32(pool + 4)
        m.put(pool + 4, 4, ident + 1)
    else:
        size -= 1
        i = (m.u64(pool + 0x50) + size) & 0xFFFFFFFFFFFFFFFF
        ident = m.u32(m.u64(m.u64(pool + 0x18) + (i >> 10) * 8) + (i & 0x3FF) * 4)
        m.put(pool + 0x58, 8, size)
        span = (m.u64(pool + 0x20) - m.u64(pool + 0x18)) & 0xFFFFFFFFFFFFFFFF
        cap = (span * 0x80 - 1) & 0xFFFFFFFFFFFFFFFF if span else 0
        if (cap - i) & 0xFFFFFFFFFFFFFFFF >= 0x800:
            _free_block(m, m.u64(pool + 0x60), m.u64(m.u64(pool + 0x20) - 8))
            m.put(pool + 0x20, 8, m.u64(pool + 0x20) - 8)
    idx = (ident - m.u32(pool)) & 0xFFFFFFFF
    if m.u64(pool + 0xC0) <= idx:
        n = (idx + 1) & 0xFFFFFFFF
        words = (n >> 6) + (1 if n & 0x3F else 0)
        cur = ((m.u64(pool + 0x90) - m.u64(pool + 0x88)) & 0xFFFFFFFFFFFFFFFF) >> 3
        if words > cur:
            with m.frame(0x10) as z:
                m.put(z, 8, 0)
                m.call_void(m.main + 0xC1AA80, pool + 0x88, words - cur, z)
        elif words < cur:
            m.put(pool + 0x90, 8, m.u64(pool + 0x88) + words * 8)
        m.put(pool + 0xC0, 8, n)
        if n & 0x3F:
            last = m.u64(pool + 0x90) - 8
            m.put(last, 8, m.u64(last) & ~(0xFFFFFFFFFFFFFFFF << (n & 0x3F)))
    w = m.u64(pool + 0x88) + (idx >> 6) * 8
    m.put(w, 8, m.u64(w) | 1 << (idx & 0x3F))
    m.put(pool + 8, 4, m.u32(pool + 8) + 1)
    _pool_unlock(m, pool)
    return ident


def _move_counted(m, o, src):
    """o = move(src) for a pointer counted at +0x28 (u32); the last reference runs vf 0x10."""
    old = m.u64(o)
    m.put(o, 8, 0)
    r = old
    if old:
        c = m.u32(old + 0x28)
        if c == 0:
            raise UnliftedCall("DecrementReference abort: count underflow")
        m.put(old + 0x28, 4, c - 1)
        if c == 1:
            r = m.vcall(old, 0x10)
    m.put(o, 8, m.u64(src)); m.put(src, 8, 0)
    return r


lifted(0xFAB748)(lambda m, o, src, *_: _move_counted(m, o, src))
lifted(0xFABCC4)(lambda m, o, src, *_: _move_counted(m, o, src))


@lifted(0xFA8298)
def assign_shared(m, o, p, *_):
    """o = p for objects whose shared state (+0x30) counts references (u16 +0x1a); the first reference
    builds +8 through vf 0 of +0x10 (+0x1c = -2), the last clears +0x10 and tail-calls the object's
    vf 0x50. Abort paths are refused."""
    if p:
        s = m.u64(p + 0x30)
        if m.u64(s + 0x10) == 0:
            raise UnliftedCall("AddReference abort: m_object is null")
        c = m.u16(s + 0x1A)
        if c == 0xFFFF:
            raise UnliftedCall("AddReference abort: count overflow")
        m.put(s + 0x1A, 2, c + 1)
        if c == 0:
            m.put(s + 8, 8, m.vcall(m.u64(s + 0x10), 0))
            m.put(s + 0x1C, 4, 0xFFFFFFFE)
    old = m.u64(o)
    m.put(o, 8, p)
    if old == 0:
        return 0
    s = m.u64(old + 0x30)
    c = m.u16(s + 0x1A)
    if c == 0:
        raise UnliftedCall("Release abort: count underflow")
    m.put(s + 0x1A, 2, c - 1)
    if c == 1:
        m.put(s + 0x10, 8, 0)
        return m.vcall(old, 0x50)
    return old


def _addref_28(m, p):
    c = m.u32(p + 0x28)
    if c == 0xFFFFFFFF:
        raise UnliftedCall("IncrementReference abort: count overflow")
    m.put(p + 0x28, 4, c + 1)


def _release_28(m, p):
    """Drop one reference on a pointer counted at +0x28; the last one runs vf 0x10."""
    c = m.u32(p + 0x28)
    if c == 0:
        raise UnliftedCall("DecrementReference abort: count underflow")
    m.put(p + 0x28, 4, c - 1)
    if c == 1:
        m.vcall_void(p, 0x10)


@lifted(0x288FD54)
def assign_counted(m, o, p, *_):
    """o = p (counted at +0x28); the old pointer goes through 0x175d10c."""
    if p:
        _addref_28(m, p)
    with m.frame(0x10) as tmp:
        m.put(tmp, 8, m.u64(o))
        m.put(o, 8, p)
        return _tail(m, m.main + 0x175D10C, tmp)


@lifted(0xFAAC98)
def pass_counted(m, o, src, *_):
    """0xfad6d0([o+0x50], &copy) with a counted copy of [src], released afterwards."""
    with m.frame(0x10) as tmp:
        p = m.u64(src)
        m.put(tmp, 8, p)
        if p:
            _addref_28(m, p)
        m.call_void(m.main + 0xFAD6D0, m.u64(o + 0x50), tmp)
        p = m.u64(tmp)
        if p:
            _release_28(m, p)


def _addref_shared(m, r):
    """AddReference on an object whose shared state (+0x30) counts at u16 +0x1a; the first reference
    builds +8 through vf 0 of +0x10 (+0x1c = -2)."""
    s = m.u64(r + 0x30)
    if m.u64(s + 0x10) == 0:
        raise UnliftedCall("AddReference abort: m_object is null")
    c = m.u16(s + 0x1A)
    if c == 0xFFFF:
        raise UnliftedCall("AddReference abort: count overflow")
    m.put(s + 0x1A, 2, c + 1)
    if c == 0:
        m.put(s + 8, 8, m.vcall(m.u64(s + 0x10), 0))
        m.put(s + 0x1C, 4, 0xFFFFFFFE)


def _release_shared(m, r):
    """ReleaseReference: the last one clears +0x10 of the shared state and runs the object's vf 0x50."""
    s = m.u64(r + 0x30)
    c = m.u16(s + 0x1A)
    if c == 0:
        raise UnliftedCall("ReleaseReference abort: count underflow")
    m.put(s + 0x1A, 2, c - 1)
    if c == 1:
        m.put(s + 0x10, 8, 0)
        m.vcall_void(r, 0x50)


@lifted(0xFA363C)
def check_fa363c(m, o, *_):
    """1 without [o+0x138]; else its vf 0x78(u8 o+0x95) & 1, the object held by a reference around the call
    (and touched once before)."""
    r = m.u64(o + 0x138)
    if r == 0:
        return 1
    _addref_shared(m, r)
    _release_shared(m, r)
    r = m.u64(o + 0x138)
    if r:
        _addref_shared(m, r)
    v = m.vcall(r, 0x78, m.u8(o + 0x95))
    if r:
        _release_shared(m, r)
    return v & 1


def _reset_owned(destroy):
    """unique_ptr reset: o = p; destroying a previous object (vf 0x18 / `destroy`, then freeing it inside
    the 0xb4e600 deferred-free scope) is not lifted and refuses before any write."""
    def fn(m, o, p, *_):
        if m.u64(o):
            raise UnliftedCall(f"unique_ptr reset over an object ({destroy})")
        m.put(o, 8, p)
    return fn


lifted(0xFAF7B0)(_reset_owned("0x190c248"))
lifted(0x2890C54)(_reset_owned("vf 0x18"))


@lifted(0x288FD24)
def hold_counted_88(m, o, pp, *_):
    r = _tail(m, m.main + 0x288FD54, o + 0x88, m.u64(pp))
    m.put(o + 0xE6, 1, 1)
    return r


@lifted(0x2892AB4)
def tail_2897a10(m, o, pp, *_):
    return _tail(m, m.main + 0x2897A10, o + 0x48, m.u64(pp))


@lifted(0xFA58C8)
def set_pair_fa58c8(m, o, pair, *_):
    m.call_void(m.main + 0xFA6424, o + 0x58, m.u64(pair))
    return _tail(m, m.main + 0xFA6560, o + 0x60, m.u64(pair + 8))


@lifted(0x2897A10)
def assign_shared_ref(m, o, p, *_):
    """o = p (shared-state reference); the old one goes through 0x1858568."""
    if p:
        _addref_shared(m, p)
    with m.frame(0x10) as tmp:
        m.put(tmp, 8, m.u64(o))
        m.put(o, 8, p)
        return _tail(m, m.main + 0x1858568, tmp)


def _tls_stack_built(m):
    """The thread's object stack (references._tls_stack), refused before any write while its static is
    not built."""
    if m.u8(m.main + 0x4765A38) & 1 == 0:
        raise UnliftedCall("static 0x4765a30 not built")
    return _tls_stack(m)


@lifted(0x17E5EBC)
def copy12_scoped(m, o, dst, src, *_):
    """With [o] pushed on the thread's object stack: copy 12 bytes src -> dst. Returns the stack."""
    top = m.u64(o)
    t = _tls_stack_built(m)
    if t:
        n = m.u64(t + 0x80)
        if n >= 0x10:
            raise UnliftedCall("abort: object stack full")
        m.put(t + 8 * n, 8, top)
        m.put(t + 0x80, 8, n + 1)
    x = m.u64(src); w = m.u32(src + 8)
    m.put(dst + 8, 4, w); m.put(dst, 8, x)
    if t:
        m.put(t + 0x80, 8, m.u64(t + 0x80) - 1)
    return t


@lifted(0xB44204)
def handle_lookup(m, o, handle, *_):
    """Handle table at o (slot table +0x8040, reader lock +0x8110, light event +0x8120): writes to x8
    the live entry for `handle` (32-byte entries, 0x400 per block at [o + 0x30 + 32 * (handle >> 10)])
    with its u16 count (+0x18) raised, or 0 when the handle is freed or stale."""
    out = m.x8
    base, lock = o + 0x8040, o + 0x8110
    cur = m.call(m.main + 0x343C290)
    owner = m.u64(lock)
    if owner and owner != cur:
        raise UnliftedCall("handle table held by another thread")
    m.put(lock + 8, 8, m.u64(lock + 8) + 1)
    d = (handle - m.u32(base)) & 0xFFFFFFFF
    word = m.u64(m.u64(base + 0x88) + ((d >> 3) & 0x1FFFFFF8))
    m.put(lock + 8, 8, m.u64(lock + 8) - 1)
    r = m.call(m.main + 0x343E5E0, o + 0x8120)
    if (word >> (d & 63)) & 1 == 0:
        m.put(out, 8, 0)
        return r
    blk = m.u64(o + 0x30 + 32 * ((handle >> 10) & 0x3FFFFF))
    j = handle & 0x3FF
    if m.u64(blk + 0x8000) <= j:
        raise UnliftedCall("abort: handle past its block")
    e = blk + 32 * j
    if m.u64(e) != handle:
        m.put(out, 8, 0)
        return r
    m.put(out, 8, e)
    n = m.u16(e + 0x18)
    if n == 0xFFFF:
        raise UnliftedCall("abort: handle count overflow")
    m.put(e + 0x18, 2, n + 1)
    return r


@lifted(0xB44438)
def handle_free(m, o, p, *_):
    """Free the handle u32 *p of the table at o (writer lock +0xd0, light event +0xe0): when its bit in
    the live bitmap ([o + 0x88], index *p - *o) is set, push it on the free deque (map +0x18/+0x20,
    start +0x50, size +0x58, 0x400 u32 per block) under the allocator [o + 0x60] on the thread's object
    stack, clear the bit and lower the live count (+8). Tail-calls SignalLightEvent."""
    if m.u32(p) < m.u32(o):
        return o
    lock = o + 0xD0
    cur = m.call(m.main + 0x343C290)
    if m.u64(lock) or m.u64(lock + 8):
        raise UnliftedCall("handle table locked")
    d = (m.u32(p) - m.u32(o)) & 0xFFFFFFFF
    live = (m.u64(m.u64(o + 0x88) + ((d >> 3) & 0x1FFFFFF8)) >> (d & 63)) & 1
    if live:
        mp, me = m.u64(o + 0x18), m.u64(o + 0x20)
        cap = 0 if me == mp else ((me - mp) * 128 - 1) & 0xFFFFFFFFFFFFFFFF
        back = (m.u64(o + 0x50) + m.u64(o + 0x58)) & 0xFFFFFFFFFFFFFFFF
        if cap == back:
            if 0xB44724 not in FUNCTIONS:
                raise UnliftedCall("free deque grows (0xb44724)")
            m.put(lock, 8, cur); m.put(lock + 8, 8, 0)
            m.call_void(m.main + 0xB44724, o + 0x10)
            mp, me = m.u64(o + 0x18), m.u64(o + 0x20)
            back = (m.u64(o + 0x50) + m.u64(o + 0x58)) & 0xFFFFFFFFFFFFFFFF
        t = _tls_stack_built(m)
    m.put(lock, 8, cur); m.put(lock + 8, 8, 0)
    if live:
        slot = 0 if me == mp else m.u64(mp + 8 * (back >> 10)) + 4 * (back & 0x3FF)
        alloc = m.u64(o + 0x60)
        if t:
            n = m.u64(t + 0x80)
            if n >= 0x10:
                raise UnliftedCall("abort: object stack full")
            m.put(t + 8 * n, 8, alloc)
            m.put(t + 0x80, 8, n + 1)
        m.put(slot, 4, m.u32(p))
        if t:
            m.put(t + 0x80, 8, m.u64(t + 0x80) - 1)
        m.put(o + 0x58, 8, m.u64(o + 0x58) + 1)
        d = (m.u32(p) - m.u32(o)) & 0xFFFFFFFF
        w = m.u64(o + 0x88) + ((d >> 3) & 0x1FFFFFF8)
        m.put(w, 8, m.u64(w) & ~(1 << (d & 63)))
        m.put(o + 8, 4, m.u32(o + 8) - 1)
    m.put(lock, 8, 0)
    return m.call(m.main + 0x343E5E0, o + 0xE0)


@lifted(0x2D38B60)
def ref_slot_2d38b60(m, o, key, *_):
    """Writes to x8 the counted reference [o + 0x138 + 0x28 * s32 key+4 + 8 * u32 key+8] with its
    count (u16 +0x1a of the control block at +0x30) raised; the first reference builds the object
    (vf 0 of [cb + 0x10], kept at cb+8, cb+0x1c = -2)."""
    e = m.u64((o + 0x28 * m.s(key + 4, 4) + 8 * m.u32(key + 8) + 0x138) & 0xFFFFFFFFFFFFFFFF)
    if e:
        cb = m.u64(e + 0x30)
        if m.u64(cb + 0x10) == 0 or m.u16(cb + 0x1A) == 0xFFFF:
            raise UnliftedCall("abort in AddReference")
    m.put(m.x8, 8, e)
    if not e:
        return o
    n = m.u16(cb + 0x1A)
    m.put(cb + 0x1A, 2, n + 1)
    if n:
        return o
    r = m.vcall(m.u64(cb + 0x10), 0)
    m.put(cb + 8, 8, r); m.put(cb + 0x1C, 4, 0xFFFFFFFE)
    return r


def _counted_in_list(m, o, v):
    """1 when the list at [o + 0x90] holds a node (u32 +0x1c != 0xff) whose +0x28 is v."""
    node = m.u64(o + 0x90)
    while node:
        if m.u32(node + 0x1C) != 0xFF and m.u64(node + 0x28) == v:
            return 1
        node = m.u64(node)
    return 0


@lifted(0x2A1D428)
def needs_more_2a1d428(m, o, *_):
    """1 unless fewer of the members counted below are in the list [o + 0x90] than 0x2014e38 says
    (the lookup of u32 +0x58 in the hash map +0x60/+0x68 and the +0xc8/+0xca/+0xcb flags answer
    first); the count walks either the 0x1319488 entries of [[o + 0xd8] + 0x10] (when +0xd0) or the
    static table [0x46d6ca0] through 0xca4118."""
    cfg = m.u64(o + 0x50)
    go_main = True
    if m.u32(cfg + 0x34) == 2:
        k = m.u8(cfg + 0x8D)
        if (k - 3) & 0xFFFFFFFF <= 3:
            return int(m.u8(o + 0xCA) != 0)
        if k == 0:
            key, want = m.u32(o + 0x58), m.u32(o + 0x5C)
            if want != 0xFF:
                if key == want:
                    return 0
            else:
                n = m.u64(o + 0x68)
                if n == 0:
                    return 1
                pc = bin(n).count("1")
                b = _bucket_pc(key, n, pc)
                x = m.u64(m.u64(o + 0x60) + 8 * b)
                if x == 0:
                    return 1
                x = m.u64(x)
                while True:
                    if x == 0:
                        return 1
                    h = m.u64(x + 8)
                    if h == key:
                        if m.u32(x + 0x10) == key:
                            break
                    elif _bucket_pc(h, n, pc) != b:
                        return 1
                    x = m.u64(x)
                if m.u32(x + 0x20) != 1:
                    return 1
            if m.u8(o + 0xCB):
                m.put(o + 0xCB, 1, 1)
                return 1
            g = m.u8(m.main + 0x4739728)
            m.put(o + 0xCB, 1, g)
            if g & 1:
                return 1
    if m.u8(o + 0xC8):
        return 1
    if m.call(m.main + 0x2014F8C, o) & 1 == 0:
        return 1
    cnt = 0
    if m.u8(o + 0xD0) == 0:
        if m.u8(m.u64(m.main + 0x46D6C98)) & 1 == 0:
            raise UnliftedCall("static at [0x46d6ca0] not built")
        tbl = m.u64(m.u64(m.main + 0x46D6CA0))
        m.put(m.u64(m.main + 0x46D6CA8), 8, tbl)
        lim = m.u32(m.main + 0x44DFCB0)
        if tbl and lim:
            src = m.u64(m.main + 0x46D0860)
            i = 0
            while True:
                if m.u64(tbl + 0x70) and lim > (i & 0xFF) and m.u64(src):
                    with m.frame(0x30) as p:
                        m.put(p + 0x28, 8, 0)
                        m.call_sret(m.main + 0xCA4118, p, m.u64(src), p + 0x28, i)
                        if m.u32(p) == 0 and m.u64(p + 0x28):
                            cnt += _counted_in_list(m, o, m.u64(p + 0x28))
                lim = m.u32(m.main + 0x44DFCB0)
                i = (i + 1) & 0xFFFFFFFF
                if i >= lim:
                    break
    else:
        h = m.u64(o + 0xD8)
        n = 0
        if h and m.u16(h + 0x1A) and m.u64(o + 0xD8) and m.u64(h + 0x10):
            n = m.call(m.main + 0x1319488, m.u64(h + 0x10) - 0x28) & 0xFFFF
        for i in range(n):
            v = 0
            h = m.u64(o + 0xD8)
            if h:
                x = m.u64(h + 0x10)
                if x:
                    e = m.u64(x + 0x148)
                    m.put(x + 0x1A8, 8, 0)
                    if e != m.u64(x + 0x150):
                        while True:
                            m.call_void(m.main + 0x12FCB68, x + 0x180, e + 8)
                            e += 0x10
                            if e == m.u64(x + 0x150):
                                break
                        if m.u64(x + 0x1A8) > i:
                            v = m.u64(m.u64(x + 0x1A0) + 8 * i)
            cnt += _counted_in_list(m, o, v)
    r = m.call(m.main + 0x2014E38, o)
    return int((cnt & 0xFFFF) < (r & 0xFF))


def _construct_counted_base(m, o):
    """The base part both 0xfa21a8 and 0xfae2c8 inline: vtable [0x46d8c78] (+0x10, +0x88, +0xd8 at
    +0, +0x20, +0x28), +8 the object on top of the thread's stack, then 0xc1a3f4(+0x30, +0x28), whose
    result it returns."""
    t = _tls_stack_built(m)
    m.put(o + 0x10, 8, 0); m.put(o + 0x18, 4, 0)
    m.put(o, 8, m.u64(m.main + 0x46D66F8) + 0x10)
    top = 0
    if t:
        n = m.u64(t + 0x80)
        if n:
            top = m.u64(t + 8 * n - 8)
    v = m.u64(m.main + 0x46D8C78)
    m.put(o, 8, v + 0x10); m.put(o + 8, 8, top)
    m.put(o + 0x20, 8, v + 0x88); m.put(o + 0x28, 8, v + 0xD8)
    m.put(o + 0x38, 8, 0); m.put(o + 0x30, 8, 0)
    return _tail(m, m.main + 0xC1A3F4, o + 0x30, o + 0x28)


@lifted(0xFA6A44)
def counted_by_key(m, o, key, *_):
    """Writes to x8 the counted pointer (count +0x28 raised) the map at o+0x30 holds for u32 key
    (0xfa6bbc), or 0."""
    out = m.x8
    key &= 0xFFFFFFFF
    if m.u64(o + 0x38) == 0:
        m.put(out, 8, 0)
        return o
    if _hash_find_u32(m, o + 0x30, key) == 0:
        m.put(out, 8, 0)
        return o + 0x30
    with m.frame(0x10) as k:
        m.put(k, 4, key)
        e = m.call(m.main + 0xFA6BBC, o + 0x30, k)
    p = m.u64(e)
    m.put(out, 8, p)
    if p:
        c = m.u32(p + 0x28)
        if c == 0xFFFFFFFF:
            raise UnliftedCall("IncrementReference abort: count overflow")
        m.put(p + 0x28, 4, c + 1)
    return e


def _handle_table(m):
    """The handle table static [[0x46d3910]] (also stored to [[0x46d3918]]), refused while its guard
    [0x46d3908] is clear."""
    if m.u8(m.u64(m.main + 0x46D3908)) & 1 == 0:
        raise UnliftedCall("static at [0x46d3910] not built")
    t = m.u64(m.u64(m.main + 0x46D3910))
    m.put(m.u64(m.main + 0x46D3918), 8, t)
    return t


def _release_weak_entry(m, e):
    """ReleaseWeakReference on a handle-table entry: lower its u16 count (+0x18); the last one marks
    +0x1c = -1 and frees the handle [e] (0xb44438), whose result it returns."""
    c = m.u16(e + 0x18)
    m.put(e + 0x18, 2, c - 1)
    if c == 0:
        raise UnliftedCall("ReleaseWeakReference abort: count underflow")
    if c != 1:
        return None
    old = m.u32(e + 0x1C)
    m.put(e + 0x1C, 4, 0xFFFFFFFF)
    if old == 0xFFFFFFFF:
        return None
    t = _handle_table(m)
    with m.frame(0x10) as p:
        m.put(p, 8, m.u64(e))
        return m.call(m.main + 0xB44438, t + 0x8040, p)


@lifted(0x168DF18)
def move_weak(m, dst, src, *_):
    """Move-assign a weak reference {entry, handle}: the handle (src+8) is looked up again in the table
    (0xb44204); src's entry and dst's old one are released; a stale handle resets dst (0x169222c)."""
    if m.u8(m.u64(m.main + 0x46D3908)) & 1 == 0:
        raise UnliftedCall("static at [0x46d3910] not built")
    h = m.u64(src + 8)
    m.put(src + 8, 8, 0)
    t = _handle_table(m)
    with m.frame(0x10) as p:
        r = m.call_sret(m.main + 0xB44204, p, t, h)
        ent = m.u64(p)
    old = m.u64(src)
    m.put(src, 8, 0)
    if old:
        x = _release_weak_entry(m, old)
        r = r if x is None else x
    if ent == 0:
        return _tail(m, m.main + 0x169222C, dst)
    prev = m.u64(dst)
    m.put(dst, 8, 0)
    if prev:
        x = _release_weak_entry(m, prev)
        r = r if x is None else x
    m.put(dst, 8, ent); m.put(dst + 8, 8, h)
    return r


@lifted(0x169222C)
def reset_weak(m, w, *_):
    """Reset a weak reference {entry, handle}: release the entry (_release_weak), zero both."""
    e = m.u64(w)
    m.put(w, 8, 0)
    r = _release_weak_entry(m, e) if e else None
    m.put(w + 8, 8, 0)
    return w if r is None else r


def _copy_weak(m, dst, src):
    """0xb43ef0 (reached here by falling through): dst = a fresh weak reference to src's handle,
    looked up again in the table (0xb44204); dst's old entry is released; a stale handle leaves dst
    {0, 0}. Returns the last callee's result."""
    if m.u8(m.u64(m.main + 0x46D3908)) & 1 == 0:
        raise UnliftedCall("static at [0x46d3910] not built")
    h = m.u64(src + 8)
    t = _handle_table(m)
    with m.frame(0x10) as p:
        r = m.call_sret(m.main + 0xB44204, p, t, h)
        ent = m.u64(p)
    old = m.u64(dst)
    m.put(dst, 8, 0)
    if old:
        x = _release_weak_entry(m, old)
        r = r if x is None else x
    if ent == 0:
        h = 0
    else:
        m.put(dst, 8, ent)
    m.put(dst + 8, 8, h)
    return r


@lifted(0xB43EE0)
def weak_of_30(m, o, *_):
    """Writes to x8 a weak reference copied from o+0x30 (0xb43ef0)."""
    out = m.x8
    m.put(out, 8, 0); m.put(out + 8, 8, 0)
    return _copy_weak(m, out, o + 0x30)


@lifted(0x1589E60)
def make_key_scoped(m, o, dst, src, *_):
    """With [o] pushed on the thread's object stack (slot from 0xf53840): dst = {u32 **src, byte 0}.
    Returns the stack (0 when the thread has none)."""
    top = m.u64(o)
    t = m.call(m.main + 0x343DA20, m.u32(m.call(m.main + 0xF53840)))
    if t:
        n = m.u64(t + 0x80)
        if n >= 0x10:
            raise UnliftedCall("abort: object stack full")
        m.put(t + 8 * n, 8, top)
        m.put(t + 0x80, 8, n + 1)
    m.put(dst, 4, m.u32(m.u64(src))); m.put(dst + 4, 1, 0)
    if t:
        m.put(t + 0x80, 8, m.u64(t + 0x80) - 1)
    return t


def _assign_strong_16f6dcc(m, slot, p):
    """0x16f6dcc (reached only as a tail call): slot = p, a counted reference (control block +0x30:
    object +0x10, count u16 +0x1a; the first reference builds the object with its vf 0, kept at +8,
    +0x1c = -2); the old one's last reference clears +0x10 and tail-calls its vf 0x50."""
    if p:
        cb = m.u64(p + 0x30)
        if m.u64(cb + 0x10) == 0 or m.u16(cb + 0x1A) == 0xFFFF:
            raise UnliftedCall("abort in AddReference")
        n = m.u16(cb + 0x1A)
        m.put(cb + 0x1A, 2, n + 1)
        if n == 0:
            m.put(cb + 8, 8, m.vcall(m.u64(cb + 0x10), 0))
            m.put(cb + 0x1C, 4, 0xFFFFFFFE)
    old = m.u64(slot)
    m.put(slot, 8, p)
    if old == 0:
        return 0
    cb = m.u64(old + 0x30)
    c = m.u16(cb + 0x1A)
    m.put(cb + 0x1A, 2, c - 1)
    if c == 1:
        m.put(cb + 0x10, 8, 0)
        return _vtail(m, old, 0x50)
    if c == 0:
        raise UnliftedCall("ReleaseReference abort: count underflow")
    return old


@lifted(0x2891404)
def assign_2e0(m, o, pp, *_):
    return _assign_strong_16f6dcc(m, o + 0x2E0, m.u64(pp))


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


def _move_ref_checked(m, dst, src, *_):
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
    lifted(_a)(_move_ref_checked)


@lifted(0xFA6424)
def assign_shared_2(m, dst, new, *_):
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


lifted(0xFA95F8)(_move_ref_checked)


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


def _tls_top(m):
    """(the TLS block of slot u32 0x4765a30, the last of its u64 entries counted at +0x80, or 0)."""
    if m.u8(m.main + 0x4765A38) & 1 == 0:
        raise UnliftedCall("static 0x4765a30 not built")
    v = m.call(m.main + 0x343DA20, m.u32(m.main + 0x4765A30))
    if v == 0 or m.u64(v + 0x80) == 0:
        return v, 0
    return v, m.u64(v + 8 * m.u64(v + 0x80) - 8)


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


def _counted_vf48(m, o, a, b, scratch):
    """vf 0x48(a, b) on the counted object of 0x114e480 (0x1142424), the reference then dropped."""
    x = m.call(m.main + 0x114E480, o)
    m.x8 = scratch
    m.call_void(m.main + 0x1142424, x)
    m.vcall_void(m.u64(scratch), 0x48, a, b)
    obj = m.u64(scratch)
    if obj:
        _release_ref(m, obj)
