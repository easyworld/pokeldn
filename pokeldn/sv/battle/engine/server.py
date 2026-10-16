"""The battle server's sends: a step's message (0x113bad8: header, body from the builder, a 0x50-byte
message object) queued in the link of every station it goes to, in the per-slot store entries and in the
server's own log (docs/sv_raid.md, The server's messages)."""

import struct

from pokeldn.sv.battle.engine.calls import _tail
from pokeldn.sv.battle.engine.containers import _hash_find_u32
from pokeldn.sv.battle.engine.references import _construct_counted_base
from pokeldn.sv.battle.engine.requests import _add_ref, _release
from pokeldn.sv.battle.engine.session import _map_push_back, _map_push_front
from pokeldn.sv.battle.engine.steps import _create, _pop, _push, _tls_stack
from pokeldn.sv.battle.machine import UnliftedCall, lifted

MESSAGE = 0x44ED338             # vtable of the message object 0x1227714 makes (+0x78, +0xc8 at +0x20, +0x28)
HEADER = 0x20                   # u32 type, u32 pad, u64 step, u64 round, u8 destination, u8 5, 6 pad bytes
ALL = 5                         # the destination byte of a message for every station
FPS = 30                        # the server's frames a second


def _counted_copy(m, at, o):
    """A strong reference copied into the slot `at` (AddReference when o is set)."""
    m.put(at, 8, o)
    if o:
        _add_ref(m, o)


# --- deque<message*> of a link or a store entry: map {first, begin, end, cap} at +0x40, map allocator
# +0x60, start +0x80, size +0x88, block allocator +0x90, bound byte +0xb0; 0x200 pointers a block -------

def _scoped_store(m, alloc, dst, value):
    stack = _tls_stack(m)
    if stack:
        _push(m, stack, alloc)
    m.put(dst, 8, value)
    if stack:
        _pop(m, stack)


@lifted(0x113D698)
def construct_ref(m, holder, dst, src, *_):
    """*dst = a strong reference to *src, with the allocator [holder] on the thread's object stack."""
    alloc = m.u64(holder)
    stack = _tls_stack(m)
    if stack:
        _push(m, stack, alloc)
    o = m.u64(src)
    m.put(dst, 8, o)
    if o:
        _add_ref(m, o)
    if stack:
        _pop(m, stack)
    return stack


@lifted(0x113D810)
def add_back_capacity(m, d, *_):
    """libc++ deque<T*>::__add_back_capacity at d (map +0..+0x18, its allocator +0x20, start +0x40, block
    allocator +0x50): a spare front block rotated to the back; else a new 0x1000-byte block (align 8)
    pushed onto the map, at the back when there is room, else at the front and rotated; else a new map of
    max(2 * capacity, 1) pointers holding the new block and the old pointers, the old map freed."""
    blocks = m.u64(d + 0x50)
    if m.u64(d + 0x40) >= 0x200:
        m.put(d + 0x40, 8, m.u64(d + 0x40) - 0x200)
        begin = m.u64(d + 8)
        pt = m.u64(begin)
        m.put(d + 8, 8, begin + 8)
        _map_push_back(m, d, pt, m.u64(d + 0x20))
        return
    first, begin, end, cap = (m.u64(d + i) for i in (0, 8, 0x10, 0x18))
    size = (end - begin) >> 3
    if size < (cap - first) >> 3:
        blk = m.vcall(blocks, 0x10, 0x1000, 8)
        if not blk:
            raise UnliftedCall("allocator out of memory: vf 0xe8")
        if cap != end:
            _map_push_back(m, d, blk, m.u64(d + 0x20))
        else:
            _map_push_front(m, d, blk, m.u64(d + 0x20))
            begin = m.u64(d + 8)
            pt = m.u64(begin)
            m.put(d + 8, 8, begin + 8)
            _map_push_back(m, d, pt, m.u64(d + 0x20))
        return
    span = cap - first
    count = (span >> 2) if span else 1
    if count == size:
        raise UnliftedCall("0x113da3c: a full new map")
    alloc = m.u64(d + 0x20)
    new = m.vcall(alloc, 0x10, count * 8, 8)
    if not new:
        raise UnliftedCall("allocator out of memory: vf 0xe8")
    with m.frame(0x30) as sb:
        mid = new + size * 8
        m.put(sb, 8, new); m.put(sb + 8, 8, mid); m.put(sb + 0x10, 8, mid)
        m.put(sb + 0x18, 8, new + count * 8); m.put(sb + 0x20, 8, d + 0x20)
        blk = m.vcall(blocks, 0x10, 0x1000, 8)
        if not blk:
            raise UnliftedCall("allocator out of memory: vf 0xe8")
        _scoped_store(m, alloc, mid, blk)
        m.put(sb + 0x10, 8, mid + 8)
        p = m.u64(d + 0x10)
        while p != m.u64(d + 8):
            p -= 8
            _map_push_front(m, sb, m.u64(p), alloc)
        old = m.u64(d)
        old_cap = m.u64(d + 0x18)
        for i in (0, 8, 0x10, 0x18):
            m.put(d + i, 8, m.u64(sb + i))
    if old:
        a = m.u64(d + 0x20)
        if m.vcall(a, 0xF8) & 1 and m.s(m.call(m.main + 0xB4E600) + 0x12C8, 4) >= 1:
            m.call_void(m.main + 0xB48FE8, a, old, old_cap - old, 8)
        else:
            m.vcall_void(a, 0x18, old, old_cap - old, 8)


@lifted(0x113D5E0)
def push_message(m, q, src, *_):
    """push_back of a strong reference to *src on q's deque; a bound at +0xb0 (pop the front when full)
    is not lifted."""
    if m.u8(q + 0xB0):
        raise UnliftedCall("0x2801764: a bounded deque")
    begin, end = m.u64(q + 0x48), m.u64(q + 0x50)
    cap = (((end - begin) << 6) - 1) & 0xFFFFFFFFFFFFFFFF if end != begin else 0
    if cap == m.u64(q + 0x80) + m.u64(q + 0x88):
        m.call_void(m.main + 0x113D810, q + 0x40)
    begin, end = m.u64(q + 0x48), m.u64(q + 0x50)
    i = m.u64(q + 0x80) + m.u64(q + 0x88)
    slot = m.u64(begin + ((i >> 6) & 0x3FFFFFFFFFFFFF8)) + 8 * (i & 0x1FF) if end != begin else 0
    r = m.call(m.main + 0x113D698, q + 0x90, slot, src)
    m.put(q + 0x88, 8, m.u64(q + 0x88) + 1)
    return r


def _push_copy(m, q, o):
    """A reference to o copied to the stack, pushed on q (0x113d5e0), the copy released."""
    with m.frame(0x10) as c:
        _counted_copy(m, c, o)
        m.call_void(m.main + 0x113D5E0, q, c)
        _release(m, c)


@lifted(0x113D4A0)
def link_push(m, link, src, *_):
    """The message *src onto the link's outgoing deque [link+0x48]."""
    _push_copy(m, m.u64(link + 0x48), m.u64(src))


@lifted(0x113D184)
def find_link(m, server, slot, *_):
    """Writes to x8 a strong reference to the link the server keeps for `slot` (u32-keyed map at
    server+0x1a0), or 0."""
    out = m.x8
    node = _hash_find_u32(m, server + 0x1A0, slot & 0xFFFFFFFF)
    if not node:
        m.put(out, 8, 0)
        return out
    o = m.u64(node + 0x18)
    _counted_copy(m, out, o)
    return out


@lifted(0x113D33C)
def link_send(m, server, link, src, *_):
    """When the server's links are live (u8 server+0x490): *src onto the link *link (0x113d4a0)."""
    if not m.u8(server + 0x490):
        return
    o = m.u64(link)
    with m.frame(0x10) as c:
        _counted_copy(m, c, m.u64(src))
        m.call_void(m.main + 0x113D4A0, o, c)
        _release(m, c)


def _send_on(m, server, link_ref, msg):
    """link_send through copies of the link and message references, both released after."""
    with m.frame(0x20) as c:
        _counted_copy(m, c, m.u64(link_ref))
        _counted_copy(m, c + 8, msg)
        m.call_void(m.main + 0x113D33C, server, c, c + 8)
        _release(m, c + 8)
        _release(m, c)


@lifted(0x113E17C)
def send_to_slot(m, server, src, slot, *_):
    """*src onto the link of `slot` (u8), when the server has one."""
    with m.frame(0x10) as ln:
        m.call_sret(m.main + 0x113D184, ln, server, slot & 0xFF)
        if not m.u64(ln):
            return
        _send_on(m, server, ln, m.u64(src))
        _release(m, ln)


@lifted(0x113CD5C)
def send_to_all(m, server, src, *_):
    """*src onto the link of every slot 0..4 the server has one for, then of slot 0xff."""
    for slot in (0, 1, 2, 3, 4, 0xFF):
        with m.frame(0x10) as ln:
            m.call_sret(m.main + 0x113D184, ln, server, slot)
            if m.u64(ln):
                _send_on(m, server, ln, m.u64(src))
                _release(m, ln)


@lifted(0xF6F324)
def store_entry(m, store, slot, *_):
    """Writes to x8 a strong reference to the store's entry for the u8 `slot` (u32-keyed map at
    store+0xc8), or 0."""
    out = m.x8
    node = _hash_find_u32(m, store + 0xC8, slot & 0xFF)
    o = m.u64(node + 0x18) if node else 0
    _counted_copy(m, out, o)
    return out


def _step_of(m, msg):
    return m.u64(m.u64(msg + 0x40) + 8)


@lifted(0x113C718)
def log_message(m, server, src, *_):
    """The message *src onto the server's log [server+0x50], unless the log holds its step already."""
    msg = m.u64(src)
    step = _step_of(m, msg)
    if not step:
        return
    with m.frame(0x10) as f:
        m.call_sret(m.main + 0xE63734, f, m.u64(server + 0x50), step)
        if m.u64(f):
            _release(m, f)
            return
        _push_copy(m, m.u64(server + 0x50), msg)


@lifted(0x113C4CC)
def queue_for_slot(m, server, src, slot, *_):
    """For a slot the battle mode seats (0xe7e2a0 on [[server+0x38]+0x290]+8's +0x36c, +0x370), the
    message *src onto the slot's store entry (0xf6f324), unless the entry holds its step already."""
    msg = m.u64(src)
    step = _step_of(m, msg)
    if not step:
        return
    o = m.u64(m.u64(m.u64(server + 0x38) + 0x290) + 8)
    if not m.call(m.main + 0xE7E2A0, m.u32(o + 0x36C), m.u8(o + 0x370), slot & 0xFF) & 1:
        return
    with m.frame(0x20) as f:
        m.call_sret(m.main + 0xF6F324, f, server, slot & 0xFFFFFFFF)
        e = m.u64(f)
        if not e:
            return
        m.call_sret(m.main + 0xE63734, f + 8, e, step)
        if m.u64(f + 8):
            _release(m, f + 8)
        else:
            _push_copy(m, e, msg)
        _release(m, f)


@lifted(0x1227714)
def make_message(m, o, header, body, size, *_):
    """The message object: the counted base, vtable 0x44ed338, a buffer of size + 0x20 bytes from [o+8]
    at +0x40 (its length at +0x48) holding the 32-byte header then the body."""
    _construct_counted_base(m, o)
    m.put(o, 8, m.main + MESSAGE)
    m.put(o + 0x20, 8, m.main + MESSAGE + 0x78)
    m.put(o + 0x28, 8, m.main + MESSAGE + 0xC8)
    m.put(o + 0x40, 8, 0)
    n = (size + HEADER) & 0xFFFFFFFF
    m.put(o + 0x48, 4, 0)
    data = m.vcall(m.u64(o + 8), 0x10, n, 8)
    m.put(o + 0x40, 8, data)
    m.put(o + 0x48, 4, n)
    m.write(data, m.read(header, HEADER))
    m.write(m.u64(o + 0x40) + HEADER, m.read(body, size & 0xFFFFFFFF))
    return m.u64(o + 0x40) + HEADER


@lifted(0x28015B4)
def destroy_message(m, o, *_):
    """The message object's destructor: its buffer back to [o+8] (0xb48fe8 while frees are deferred, else
    vf 0x18), the base vtables, the weak handle at +0x30 released."""
    from pokeldn.sv.battle.engine.references import _release_weak
    alloc = m.u64(o + 8)
    m.put(o, 8, m.main + MESSAGE)
    m.put(o + 0x20, 8, m.main + MESSAGE + 0x78); m.put(o + 0x28, 8, m.main + MESSAGE + 0xC8)
    data, n = m.u64(o + 0x40), m.u32(o + 0x48)
    if m.vcall(alloc, 0xF8) & 1 and m.s(m.call(m.main + 0xB4E600) + 0x12C8, 4) >= 1:
        m.call_void(m.main + 0xB48FE8, alloc, data, n, 8)
    else:
        m.vcall_void(alloc, 0x18, data, n, 8)
    v = m.u64(m.main + 0x46D8C78)
    m.put(o, 8, v + 0x10); m.put(o + 0x20, 8, v + 0x88); m.put(o + 0x28, 8, v + 0xD8)
    p = m.u64(o + 0x30)
    return _release_weak(m, p, o) if p else o


@lifted(0x113BAD8)
def send_step(m, server, kind, dest, *_):
    """One server step: the step counter server+0x198 raised; the body already received for that step in
    [[server+0x448]+0x38] (0xe63734), or else the builder 0x113c8a0 (kind, round server+0x488); the
    header {kind, step, round, dest, 5}; the message (0x1227714, 0x50 bytes from [server+8]) onto every
    link (dest 5, 0x113cd5c) or dest's (0x113e17c), the server's log (0x113c718) and the store entry of
    every slot (dest 5) or dest's (0x113c4cc). Writes to x8 {u8 [[server+0x448]+0xc4a5], u64 step, u8
    +0xc4a4}. The header's pad bytes +0x1a..+0x1f are stack the game never writes; they are zero here."""
    out = m.x8
    kind &= 0xFFFFFFFF
    m.put(out, 1, 0); m.put(out + 8, 8, 0); m.put(out + 0x10, 1, 0)
    with m.frame(0x60) as sp:
        hdr, got, body, size = sp, sp + 0x20, sp + 0x30, sp + 0x38
        m.write(sp, bytes(0x60))
        step = (m.u64(server + 0x198) + 1) & 0xFFFFFFFFFFFFFFFF
        m.put(server + 0x198, 8, step)
        b = m.u64(server + 0x448)
        received = 0
        if m.u64(b + 0x38):
            m.call_sret(m.main + 0xE63734, hdr, m.u64(b + 0x38), step)
            received = m.u64(hdr)
        if received:
            m.put(body, 8, m.u64(received + 0x40) + HEADER)
            m.put(size, 4, m.u32(received + 0x48) - HEADER)
            _release(m, hdr)
        else:
            m.call_void(m.main + 0x113C8A0, b, body, size, server + 0x488, kind)
        m.put(hdr + 0x19, 1, 5)
        m.put(hdr, 4, kind)
        m.put(hdr + 0x18, 1, dest)
        m.put(hdr + 8, 8, m.u64(server + 0x198)); m.put(hdr + 0x10, 8, m.u64(server + 0x488))
        alloc = m.u64(server + 8)
        msg = _create(m, alloc, 0x50, lambda o: m.call_void(m.main + 0x1227714, o, hdr, m.u64(body), m.u32(size)))
        m.put(got, 8, msg)
        _add_ref(m, msg)
        if dest & 0xFF == ALL:
            with m.frame(0x10) as c:
                _counted_copy(m, c, msg)
                m.call_void(m.main + 0x113CD5C, server, c)
                _release(m, c)
        else:
            with m.frame(0x10) as c:
                _counted_copy(m, c, msg)
                m.call_void(m.main + 0x113E17C, server, c, dest)
                _release(m, c)
        with m.frame(0x10) as c:
            _counted_copy(m, c, msg)
            m.call_void(m.main + 0x113C718, server, c)
            _release(m, c)
        if dest & 0xFF == ALL:
            _add_ref(m, msg)
        for slot in (range(5) if dest & 0xFF == ALL else (dest,)):
            with m.frame(0x10) as c:
                _counted_copy(m, c, msg)
                m.call_void(m.main + 0x113C4CC, server, c, slot & 0xFFFFFFFF)
                _release(m, c)
        if dest & 0xFF == ALL:
            m.put(got + 8, 8, msg)
            _release(m, got + 8)
        m.put(out + 8, 8, m.u64(server + 0x198))
        r = m.u64(server + 0x448) + 0xC4A4
        m.put(out, 1, m.u8(r + 1))
        m.put(out + 0x10, 1, m.u8(r))
        _release(m, got)
    return out


@lifted(0x113BAB8)
def send_all(m, server, kind, *_):
    return _tail(m, m.main + 0x113BAD8, server, kind, ALL)


# --- the server's per-slot message stores: what it sent each slot (server+0xc8, 0xf6f324) and what each
# slot sent it (server+0x130, 0xe634c8); each entry a message deque as above -------------------------------

@lifted(0xE634C8)
def receive_entry(m, server, slot, *_):
    """Writes to x8 a strong reference to the entry of what `slot` (u8) sent (u32-keyed map at
    server+0x130), or 0."""
    out = m.x8
    node = _hash_find_u32(m, server + 0x130, slot & 0xFF)
    _counted_copy(m, out, m.u64(node + 0x18) if node else 0)
    return out


def _deque_at(m, q, i):
    """The element slot of index i (map +0x48, 0x200 a block)."""
    return m.u64(m.u64(q + 0x48) + 8 * (i >> 9)) + 8 * (i & 0x1FF)


def _find_type(m, q, key):
    """The index of the first message whose header type (u32 [msg+0x40]) is `key`, each looked at taken
    and dropped around the read (as 0xf6f0a8 and 0xf6fd7c walk), or None."""
    if m.u64(q + 0x50) == m.u64(q + 0x48):
        return None
    start, size = m.u64(q + 0x80), m.u64(q + 0x88)
    for i in range(start, start + size):
        e = m.u64(_deque_at(m, q, i))
        if not e:
            continue
        _add_ref(m, e)
        t = m.u32(m.u64(e + 0x40))
        with m.frame(0x10) as h:
            m.put(h, 8, e)
            _release(m, h)
        if t == key:
            return i
    return None


@lifted(0xF6F0A8)
def find_type(m, q, key, *_):
    """Writes to x8 a strong reference to the first message of type `key` (u32) in q's deque, or 0."""
    out = m.x8
    i = _find_type(m, q, key & 0xFFFFFFFF)
    _counted_copy(m, out, 0 if i is None else m.u64(_deque_at(m, q, i)))
    return out


def _free_block(m, alloc, block):
    if m.vcall(alloc, 0xF8) & 1 and m.s(m.call(m.main + 0xB4E600) + 0x12C8, 4) >= 1:
        m.call_void(m.main + 0xB48FE8, alloc, block, 0x1000, 8)
    else:
        m.vcall_void(alloc, 0x18, block, 0x1000, 8)


@lifted(0x131BE1C)
def erase_at(m, d, _block, it, *_):
    """libc++ deque<T*>::erase at the element slot `it` (d: map +0..+0x18, start +0x40, size +0x48, block
    allocator +0x50): the elements on the shorter side shifted over it by move-assignment (the erased one
    released by the first move), the vacated end destroyed, start/size updated, and a block freed when two
    spare blocks gather at that end. The returned iterator is not reproduced."""
    first = m.u64(d + 8)
    if m.u64(d + 0x10) == first:
        raise UnliftedCall("0x131be1c on an empty map")
    start, size = m.u64(d + 0x40), m.u64(d + 0x48)
    at = lambda i: m.u64(first + 8 * (i >> 9)) + 8 * (i & 0x1FF)
    pos = next(i for i in range(start, start + size) if at(i) == it)
    n = pos - start
    if n <= (size - 1) >> 1:
        for i in range(pos, start, -1):            # move_backward: [start, pos) onto [start+1, pos+1)
            old = m.u64(at(i))
            m.put(at(i), 8, 0)
            if old:
                with m.frame(0x10) as h:
                    m.put(h, 8, old)
                    _release(m, h)
            v = m.u64(at(i - 1))
            m.put(at(i - 1), 8, 0)
            m.put(at(i), 8, v)
        old = m.u64(at(start))
        if old:
            with m.frame(0x10) as h:
                m.put(h, 8, old)
                _release(m, h)
        m.put(d + 0x40, 8, start + 1); m.put(d + 0x48, 8, size - 1)
        if start + 1 >= 0x400:
            blk = m.u64(m.u64(d + 8))
            _free_block(m, m.u64(d + 0x50), blk)
            m.put(d + 8, 8, m.u64(d + 8) + 8)
            m.put(d + 0x40, 8, m.u64(d + 0x40) - 0x200)
        return
    end = start + size
    for i in range(pos, end - 1):                  # move: [pos+1, end) onto [pos, end-1)
        old = m.u64(at(i))
        m.put(at(i), 8, 0)
        if old:
            with m.frame(0x10) as h:
                m.put(h, 8, old)
                _release(m, h)
        v = m.u64(at(i + 1))
        m.put(at(i + 1), 8, 0)
        m.put(at(i), 8, v)
    old = m.u64(at(end - 1))
    if old:
        with m.frame(0x10) as h:
            m.put(h, 8, old)
            _release(m, h)
    m.put(d + 0x48, 8, size - 1)
    b, e = m.u64(d + 8), m.u64(d + 0x10)
    cap = ((e - b) << 6) - 1 if e != b else 0
    if cap - (start + size - 1) >= 0x400:
        _free_block(m, m.u64(d + 0x50), m.u64(e - 8))
        m.put(d + 0x10, 8, m.u64(d + 0x10) - 8)


@lifted(0xE0F5F8)
def clear(m, d, *_):
    """libc++ deque<T*>::clear at d (map +0..+0x18, start +0x40, size +0x48, block allocator +0x50): every
    element released in order, size 0, blocks freed from the front while three or more remain, start then
    0x100 with one block left and 0x200 with two."""
    begin, end = m.u64(d + 8), m.u64(d + 0x10)
    if end != begin:
        start, size = m.u64(d + 0x40), m.u64(d + 0x48)
        for i in range(start, start + size):
            slot = m.u64(begin + 8 * (i >> 9)) + 8 * (i & 0x1FF)
            if m.u64(slot):
                with m.frame(0x10) as h:
                    m.put(h, 8, m.u64(slot))
                    _release(m, h)
    m.put(d + 0x48, 8, 0)
    while (m.u64(d + 0x10) - m.u64(d + 8)) >> 3 >= 3:
        _free_block(m, m.u64(d + 0x50), m.u64(m.u64(d + 8)))
        m.put(d + 8, 8, m.u64(d + 8) + 8)
    n = (m.u64(d + 0x10) - m.u64(d + 8)) >> 3
    if n in (1, 2):
        m.put(d + 0x40, 8, 0x100 * n)


@lifted(0xF6FD7C)
def erase_type(m, q, key, *_):
    """The first message of type `key` (u32) erased from q's deque (0x131be1c)."""
    i = _find_type(m, q, key & 0xFFFFFFFF)
    if i is None:
        return
    it = _deque_at(m, q, i)
    return _tail(m, m.main + 0x131BE1C, q + 0x40, m.u64(q + 0x48) + 8 * (i >> 9), it)


def _seated(m, server, slot):
    o = m.u64(m.u64(m.u64(server + 0x38) + 0x290) + 8)
    return m.call(m.main + 0xE7E2A0, m.u32(o + 0x36C), m.u8(o + 0x370), slot & 0xFF) & 1


def _entry_has(m, server, getter, key, slot):
    """Whether the entry `getter` gives for slot holds a message of type key: None when there is no entry."""
    with m.frame(0x10) as f:
        m.call_sret(m.main + getter, f, server, slot & 0xFFFFFFFF)
        if not m.u64(f):
            return None
        m.call_sret(m.main + 0xF6F0A8, f + 8, m.u64(f), key & 0xFFFFFFFF)
        found = m.u64(f + 8) != 0
        if found:
            _release(m, f + 8)
        _release(m, f)
        return found


@lifted(0xF6EF64)
def sent_to(m, server, key, slot, *_):
    """Whether the server's entry for a seated slot still holds a message of type `key` it sent."""
    if not _seated(m, server, slot):
        return 0
    return int(bool(_entry_has(m, server, 0xF6F324, key, slot)))


@lifted(0xF6F590)
def received_from(m, server, key, slot, *_):
    """Whether a slot sent a message of type `key`: 1 also for a slot the mode does not seat or one with
    no entry."""
    if not _seated(m, server, slot):
        return 1
    r = _entry_has(m, server, 0xE634C8, key, slot)
    return 1 if r is None else int(r)


@lifted(0xE63380)
def answered(m, server, step, slot, *_):
    """Whether what a seated slot sent holds a message of header step `step` (0xe63734); 1 for a slot the
    mode does not seat or one with no entry."""
    if not _seated(m, server, slot):
        return 1
    with m.frame(0x10) as f:
        m.call_sret(m.main + 0xE634C8, f, server, slot & 0xFFFFFFFF)
        if not m.u64(f):
            return 1
        m.call_sret(m.main + 0xE63734, f + 8, m.u64(f), step)
        found = m.u64(f + 8) != 0
        if found:
            _release(m, f + 8)
        _release(m, f)
        return int(found)


@lifted(0xF6EDF4)
def take_answered(m, reader, key, answer, *_):
    """When the server sent the reader's slot a message of type `key` and the slot sent one of type
    `answer`: the first of each erased (0xf6fd7c) from the two entries; 1 then."""
    server, slot = m.u64(reader + 0x30), m.u32(reader + 0x38)
    if not m.call(m.main + 0xF6EF64, server, key, slot) & 1:
        return 0
    if not m.call(m.main + 0xF6F590, server, answer, slot) & 1:
        return 0
    for getter, k in ((0xF6F324, key), (0xE634C8, answer)):
        with m.frame(0x10) as f:
            m.call_sret(m.main + getter, f, server, slot)
            if m.u64(f):
                m.call_void(m.main + 0xF6FD7C, m.u64(f), k & 0xFFFFFFFF)
                _release(m, f)
    return 1


@lifted(0xF91070)
def time_left(m, timer, limit, offset, *_):
    """Seconds left of a `limit`-second timer (start ns +0, accumulated ns +8, paused bytes +0x19/+0x1a):
    paused, limit - accumulated; running, limit + offset - (now - start) - accumulated (whole seconds,
    truncated toward zero); 1 for a zero limit."""
    if not limit:
        return 1
    s = lambda v: v - (1 << 64) if v >> 63 else v
    sec = lambda ns: ns // 1000000000 if ns >= 0 else -(-ns // 1000000000)
    acc = s(m.u64(timer + 8))
    if m.u8(timer + 0x19) or m.u8(timer + 0x1A):
        return (limit - sec(acc)) & 0xFFFFFFFFFFFFFFFF
    now = m.call(m.main + 0x343D5B0, m.call(m.main + 0x343C280))
    return (limit + offset - sec(s((now - m.u64(timer)) & 0xFFFFFFFFFFFFFFFF)) - sec(acc)) & 0xFFFFFFFFFFFFFFFF


def _now(m):
    return m.call(m.main + 0x343D5B0, m.call(m.main + 0x343C280))


@lifted(0xF70A58)
def create_timer(m, timer, limit, *_):
    """A battle timer: zeroed, `limit` at +0x20, started (+0x18) and at once paused for reason 0 (0x18c9a68's
    steps)."""
    m.put(timer + 8, 8, 0); m.put(timer + 0x10, 8, 0); m.put(timer, 8, 0)
    m.put(timer + 0x20, 8, limit)
    m.put(timer + 0x18, 1, 0)
    m.put(timer, 8, _now(m))
    m.put(timer + 0x18, 1, 1)
    if not m.u8(timer + 0x19) and not m.u8(timer + 0x1A):
        now = _now(m)
        acc = (now - m.u64(timer) + m.u64(timer + 8)) & 0xFFFFFFFFFFFFFFFF
        m.put(timer, 8, 0)
        m.put(timer + 8, 8, acc); m.put(timer + 0x10, 8, now)
    m.put(timer + 0x19, 1, 1)


@lifted(0x18C9A68)
def pause_timer(m, timer, reason, *_):
    """Pause for `reason` (byte +0x19 + reason): a running timer adds now - start (+0) to its accumulated ns
    (+8), keeps the pause time (+0x10) and clears its start."""
    if not m.u8(timer + 0x19) and not m.u8(timer + 0x1A):
        now = _now(m)
        acc = (now - m.u64(timer) + m.u64(timer + 8)) & 0xFFFFFFFFFFFFFFFF
        m.put(timer, 8, 0)
        m.put(timer + 8, 8, acc); m.put(timer + 0x10, 8, now)
    m.put(timer + 0x19 + (reason & 0xFF), 1, 1)


@lifted(0xE63AC4)
def resume_timer(m, timer, reason, *_):
    """A paused timer's `reason` cleared; with no reason left it runs again from now (+0), pause time 0."""
    if not m.u8(timer + 0x19) and not m.u8(timer + 0x1A):
        return
    m.put(timer + 0x19 + (reason & 0xFF), 1, 0)
    if m.u8(timer + 0x19) or m.u8(timer + 0x1A):
        return
    m.put(timer, 8, _now(m))
    m.put(timer + 0x10, 8, 0)


@lifted(0xE63A6C)
def start_timer(m, timer, reason, *_):
    """A timer never started (+0x18) starts now; a paused one resumes for `reason` (0xe63ac4)."""
    if not m.u8(timer + 0x18):
        m.put(timer, 8, _now(m))
        m.put(timer + 0x18, 1, 1)
        return
    if m.u8(timer + 0x19) or m.u8(timer + 0x1A):
        return _tail(m, m.main + 0xE63AC4, timer, reason)


# --- the server's flow: the raid step's server part each frame (docs/sv_raid.md, The server's flow) -----

class Server:
    """A battle server over a session the engine built (N): stations' messages in (receive), the messages
    it queues for each station out (sent), and between them the game's own frames (run): the server's
    incoming links (0xe0f040, 0xe0fd68, 0xe0f854), then the job graph 0xfc363c([N+0xa8], 1), and message
    0x46 (0x2898350) when that step moved, as the raid run step 0x2d383b8 does at 0x2d38694."""

    def __init__(self, m, n):
        self.m, self.n = m, n
        self.c = m.u64(n + 0xB0)
        self.graph = m.u64(n + 0xA8)
        self.seen = {s: 0 for s in range(5)}
        self.origin = None              # (seconds, ticks) when `at` was first given
        self.t = None                   # the clock, in seconds
        self.frames = 0

    # --- in and out --------------------------------------------------------------------------------

    def receive(self, slot, raw):
        """A station's message (32-byte header and body) into what `slot` sent (0xe634c8's entry), as
        the frame reader's 0xe106a4 stores it (0x113d5e0)."""
        m = self.m
        with m.frame(0x40) as h:
            m.write(h, raw[:HEADER])
            with m.frame((len(raw) + 0x20) & ~0xF) as body:
                m.write(body, raw[HEADER:])
                msg = _create(m, m.u64(self.c + 8), 0x50,
                              lambda o: m.call_void(m.main + 0x1227714, o, h, body, len(raw) - HEADER))
        with m.frame(0x20) as f:
            m.put(f + 8, 8, msg)
            _add_ref(m, msg)
            m.call_sret(m.main + 0xE634C8, f, self.c, slot)
            if m.u64(f):
                m.call_void(m.main + 0x113D5E0, m.u64(f), f + 8)
                _release(m, f)
            _release(m, f + 8)

    def sent(self, slot):
        """The messages queued for `slot`'s link since the last call."""
        m, out = self.m, []
        node = _hash_find_u32(m, self.c + 0x1A0, slot)
        if node:
            q = m.u64(m.u64(node + 0x18) + 0x48)
            start, size = m.u64(q + 0x80), m.u64(q + 0x88)
            for i in range(start + self.seen[slot], start + size):
                msg = m.u64(_deque_at(m, q, i))
                out.append(m.read(m.u64(msg + 0x40), m.u32(msg + 0x48)))
            self.seen[slot] = size
        return out

    def frame(self, slot, msg):
        """A message on the wire: key 0x7b, the address (setup u32 +0x2c, 1, slot), the length."""
        m = self.m
        return struct.pack("<HIIII", 0x7B, m.u32(m.u64(self.n + 0x38) + 0x2C), 1, slot, len(msg)) + msg

    def clock(self, at):
        """The console's clock at `at` seconds: the machine's tick counter (19.2 MHz) moved forward to it,
        counted from the first time given."""
        m = self.m
        if self.origin is None:
            self.origin = (at, m.ticks)
        t = self.origin[1] + int(round((at - self.origin[0]) * 19200000))
        if t > m.ticks:
            m.ticks = t
        self.t = at

    def handle(self, messages, at=None, stations=(2,)):
        """Serve: frames up to `at` seconds (when given), each (slot, message) received in turn and a frame
        period run after it; returns the frames queued for each slot in `stations`."""
        if at is not None:
            self.run(at)
        for slot, raw in messages:
            self.receive(slot, raw)
            self.run(self.t + 1 / FPS)
        return {s: [self.frame(s, msg) for msg in self.sent(s)] for s in stations}

    def setup(self):
        """Nothing to do: the per-frame machine's first frame makes the battle timer and posts Wild::Setup
        (0xf70864)."""

    # --- the frames ------------------------------------------------------------------------------------

    def step(self):
        """One frame of the server: 0x2d38694..0x2d386c4."""
        m = self.m
        self.frames += 1
        for f in (0xE0F040, 0xE0FD68, 0xE0F854):
            m.call_void(m.main + f, self.c)
        moved = m.call(m.main + 0xFC363C, self.graph, 1) & 1
        if moved:
            m.call_void(m.main + 0x2898350, self.c)
        return moved

    def run(self, until=None):
        """Frames at FPS a second on the clock, from the current time up to `until` (at least one frame;
        one at the current time when `until` is not given), as the console runs them; the clock ends at
        `until` (the tick counter never goes back)."""
        if self.t is None:
            raise ValueError("Server.clock first")
        until = self.t if until is None else until
        t = self.t
        while True:
            self.clock(t)
            self.step()
            t += 1 / FPS
            if t > until:
                break
        self.clock(until)
