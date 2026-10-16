"""libc++ unordered_map as the server compiles it: buckets at +0, bucket count at +8; a node is (next,
hash, key, value). A u16 key hashes to itself. Lookups, operator[], rehash, clear and copies."""

from pokeldn.sv.battle.engine.calls import M32, _f32, _pow2, _tail
from pokeldn.sv.battle.engine.heap import _allocator_free
from pokeldn.sv.battle.machine import FUNCTIONS, UnliftedCall, lifted


def _bucket(h, n):
    return h & (n - 1) if n & (n - 1) == 0 else h % n


def find_u16(m, table, key):
    """The node holding the u16 `key`, or 0."""
    return find(m, table, key & 0xFFFF, 2)


def find(m, table, key, size):
    """The node holding `key` (a u16 or u32 at node+0x10), or 0."""
    n = m.u64(table + 8)
    if n == 0:
        return 0
    b = _bucket(key, n)
    node = m.u64(m.u64(table) + b * 8)
    if node == 0:
        return 0
    node = m.u64(node)
    while node:
        h = m.u64(node + 8)
        if h == key:
            if m.u(node + 0x10, size) == key:
                return node
        elif _bucket(h, n) != b:
            return 0
        node = m.u64(node)
    return 0


@lifted(0xF7BA54)
def find_value(m, owner, key, *_):
    """The value slot (+0x18) of the u16-keyed map at owner+8, or 0; key 0xee is never present."""
    key &= 0xFFFF
    if key == 0xEE:
        return 0
    node = find_u16(m, owner + 8, key)
    return node + 0x18 if node else 0


@lifted(0xF21C94)
def battler(m, owner, ident, *_):
    """The battler with id `ident` from the u32-keyed map at owner+0x140, or 0."""
    node = find(m, owner + 0x140, ident & 0xFFFFFFFF, 4)
    return m.u64(node + 0x18) if node else 0


def _lookup(base, size, value, load):
    def fn(m, owner, key, *_):
        node = find(m, owner + base, key & ((1 << 8 * size) - 1), size)
        if not node:
            return 0
        return m.u64(node + value) if load else node + value
    return fn


# Lookups of the same libc++ map shape: (map offset in the owner, key size, value offset, load).
for _addr, _spec in {0x10E2DD4: (8, 4, 0x14, False)}.items():
    lifted(_addr)(_lookup(*_spec))


@lifted(0x119B478)
def find_handler(m, owner, kind, ident, *_):
    """Walk the entry chain from the u16 key at owner+0x70: each node (map at its owner+8) names
    the next key (+0x2c) and owner (+0x20). The first live node (+0x5c set, +0x59 clear) whose kind
    byte (+0x40) and id (+0x4c) match is returned as node+0x18; 0 at the end of the chain."""
    kind &= 0xFF; ident &= 0xFFFFFFFF
    key, table = m.u16(owner + 0x70), owner + 8
    while key != 0xEE:
        node = find(m, table, key, 2)
        if not node:
            return 0
        if m.u8(node + 0x5C) and m.u8(node + 0x40) == kind and m.u32(node + 0x4C) == ident \
                and m.u8(node + 0x59) == 0:
            return node + 0x18
        key, table = m.u16(node + 0x2C), m.u64(node + 0x20) + 8
    return 0


@lifted(0xBF60CC)
def data_record(m, table, key, *_):
    """The record for a u16 id (a move, ...) from a data table's map at +0x68, else its default (+0xd0)."""
    node = find(m, table + 0x68, key & 0xFFFF, 2)
    return m.u64(node + 0x18) if node else m.u64(table + 0xD0)


@lifted(0x114C668)
def find_u32_node(m, table, key_ptr, *_):
    """The node holding the u32 at key_ptr, or 0."""
    return find(m, table, m.u32(key_ptr), 4)


@lifted(0x20049F4)
def value_u64_key(m, owner, key_ptr, *_):
    """The u32 value for the u64 key at key_ptr in the map at owner+0x40 (the key must be present)."""
    key = m.u64(key_ptr)
    table = owner + 0x40
    n = m.u64(table + 8)
    if n == 0:
        return 0
    b = _bucket(key, n)
    node = m.u64(m.u64(table) + b * 8)
    node = m.u64(node) if node else 0
    while node:
        h = m.u64(node + 8)
        if h == key:
            if m.u64(node + 0x10) == key:
                return m.u32(node + 0x18)
        elif _bucket(h, n) != b:
            return 0
        node = m.u64(node)
    return 0


NONE_KEY = 0xEE


def _key_node(m, table, key):
    return 0 if key == NONE_KEY else find(m, table, key, 2)


@lifted(0x127CDF8)
def unlink(m, e, *_):
    """Take an element out of its keyed list: elements live in the map at [e+8]+8, link to their
    neighbours by u16 key (+0x12 previous, +0x14 next; 0xee none) and carry their own key at +0x10."""
    table = m.u64(e + 8) + 8
    prev = _key_node(m, table, m.u16(e + 0x12))
    nxt = _key_node(m, table, m.u16(e + 0x14))
    if prev:
        m.put(prev + 0x18 + 0x14, 2, m.u16(nxt + 0x28) if nxt else NONE_KEY)
    if nxt:
        prev = _key_node(m, table, m.u16(e + 0x12))
        m.put(nxt + 0x18 + 0x12, 2, m.u16(prev + 0x28) if prev else NONE_KEY)
    m.put(e + 0x12, 4, 0xEE00EE)


@lifted(0x13813F4)
def battler_of(m, o, ident, *_):
    return battler(m, m.u64(m.u64(o + 0x10) + 0x30), ident)


@lifted(0x113FEE0)
def head_entry(m, owner, *_):
    """The value (node+0x18) of the entry keyed by the u16 at owner+0x70 in the map at owner+8."""
    key = m.u16(owner + 0x70)
    if key == NONE_KEY:
        return 0
    node = find(m, owner + 8, key, 2)
    return node + 0x18 if node else 0


def _element(m, table, key):
    node = _key_node(m, table, key)
    return node + 0x18 if node else 0


def _next_key(m, e):
    """The key of e's next element, or 0xee when it has none."""
    node = _key_node(m, m.u64(e + 8) + 8, m.u16(e + 0x14))
    return m.u16(node + 0x28) if node else NONE_KEY


@lifted(0x119BAAC)
def take_free(m, owner, key, *_):
    """Take an element off the free list headed at owner+0x72: the one keyed `key`, or the head when
    `key` is negative. Returns it unlinked, or 0 when it is not on the list."""
    head = _element(m, owner + 8, m.u16(owner + 0x72))
    if head == 0:
        return 0
    if key & 0x80000000 == 0:
        e = head
        while m.u16(e + 0x10) != key & 0xFFFF:
            e = _element(m, m.u64(e + 8) + 8, m.u16(e + 0x14))
            if e == 0:
                return 0
        if e != head:
            unlink(m, e)
            return e
    m.put(owner + 0x72, 2, _next_key(m, head))
    unlink(m, head)
    return head


@lifted(0x13608E0)
def release(m, owner, e, *_):
    """Move an element from the active list (head key owner+0x70) to the front of the free list
    (head key owner+0x72), clearing its 0x58-byte payload."""
    if _element(m, owner + 8, m.u16(owner + 0x70)) == e:
        m.put(owner + 0x70, 2, _next_key(m, e))
    unlink(m, e)
    m.put(e + 0x12, 4, 0xEE00EE)
    m.write(e + 0x18, bytes(0x58))
    free = _key_node(m, owner + 8, m.u16(owner + 0x72))
    if free:
        m.put(e + 0x14, 2, m.u16(free + 0x28))
        m.put(free + 0x2A, 2, m.u16(e + 0x10))
    else:
        m.put(e + 0x14, 2, NONE_KEY)
    m.put(owner + 0x72, 2, m.u16(e + 0x10))


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


@lifted(0x157EA98)
def find_u32(m, table, key_ptr, *_):
    """The node of the u32-keyed map holding the key at key_ptr, or 0."""
    return find(m, table, m.u32(key_ptr), 4)


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


@lifted(0x287B7A4)
def flag_of_id(m, o, ident, *_):
    """Whether the u32-keyed map at o+0x2f0 holds `ident` with a nonzero value byte (through its at())."""
    ident &= 0xFFFFFFFF
    if not find(m, o + 0x2F0, ident, 4):
        return 0
    with m.frame(0x10) as f:
        m.put(f, 4, ident)
        return int(m.u8(m.call(m.main + 0x287B8E0, o + 0x2F0, f)) != 0)


@lifted(0x127E6E8)
def map_clear(m, o, *_):
    """Clear +0x70; when the map holds entries (+0x60): free its 0x20-byte nodes (list +0x38, allocator
    +0x40), empty the list and the buckets (+8, count +0x10), size 0."""
    m.put(o + 0x70, 1, 0)
    if m.u64(o + 0x60):
        _map_free_all(m, o, 0x20)


def _map_free_all(m, o, node_size):
    """Free every node of the map at o+8 (list +0x38, allocator +0x40), empty its buckets (+8, count
    +0x10), size (+0x60) 0."""
    node = m.u64(o + 0x38)
    while node:
        nxt = m.u64(node)
        _allocator_free(m, m.u64(o + 0x40), node, node_size)
        node = nxt
    m.put(o + 0x38, 8, 0)
    for i in range(m.u64(o + 0x10)):
        m.put(m.u64(o + 8) + 8 * i, 8, 0)
    m.put(o + 0x60, 8, 0)


@lifted(0xFA6E40)
def map_at_u32(m, table, key_ptr, *_):
    """unordered_map<u32, ...>::at: the value slot (node+0x18); a missing key throws (0x288ddb0)."""
    node = find(m, table, m.u32(key_ptr), 4)
    if not node:
        raise UnliftedCall("unordered_map::at of a missing key (throws)")
    return node + 0x18


@lifted(0xF79060)
def map_assign_8(m, o, src, *_):
    """Empty the map at o+8 (0x20-byte nodes), then o[key] = value for each (u32 key +0x10, u64 value
    +0x14) node of src's list (+0x38), through operator[] 0xf7a448."""
    if m.u64(o + 0x60):
        _map_free_all(m, o, 0x20)
    node = m.u64(src + 0x38)
    while node:
        m.put(m.call(m.main + 0xF7A448, o + 8, node + 0x10), 8, m.u64(node + 0x14))
        node = m.u64(node)


@lifted(0xF78CB8)
def map_reset_16(m, o, *_):
    """Empty the map at o+8 (0x28-byte nodes) when it holds entries; then o[key] = 16 bytes for each
    node still on its own list (operator[] 0xf807f8)."""
    if m.u64(o + 0x60):
        _map_free_all(m, o, 0x28)
    node = m.u64(o + 0x38)
    while node:
        m.write(m.call(m.main + 0xF807F8, o + 8, node + 0x10), m.read(node + 0x14, 0x10))
        node = m.u64(node)


def _bucket_pc(h, n, pc):
    if pc <= 1:
        return h & (n - 1)
    return h if h < n else h % n


@lifted(0x17E5E44)
def push_back12(m, v, src, *_):
    """Vector of 12-byte entries (data +0x20, size +0x28, capacity +0x30): append src (0x17e5ebc in
    place, 0x2014a90 when full)."""
    n = m.u64(v + 0x28)
    if n < m.u64(v + 0x30):
        r = m.call(m.main + 0x17E5EBC, v, m.u64(v + 0x20) + 12 * n, src)
        m.put(v + 0x28, 8, m.u64(v + 0x28) + 1)
        return r
    with m.frame(0x20) as p:
        m.put(p + 0x10, 8, m.u64(v + 0x20) + 12 * n)
        return m.call_sret(m.main + 0x2014A90, p, v, p + 0x10, src)


def _hash_find_u32(m, table, key):
    """The node of key in an unordered map of u32 keys (buckets [table], count [table+8]; node: next,
    hash +8, key +0x10), or 0."""
    n = m.u64(table + 8)
    if n == 0:
        return 0
    pc = bin(n).count("1")
    b = _bucket_pc(key, n, pc)
    x = m.u64(m.u64(table) + 8 * b)
    x = m.u64(x) if x else 0
    while x:
        h = m.u64(x + 8)
        if h == key:
            if m.u32(x + 0x10) == key:
                return x
        elif _bucket_pc(h, n, pc) != b:
            return 0
        x = m.u64(x)
    return 0


@lifted(0x287B530)
def find_u32_287b530(m, table, key_ptr, *_):
    """The node holding the u32 at key_ptr, or 0."""
    return find(m, table, m.u32(key_ptr), 4)


@lifted(0x287B8E0)
def map_at_u32_14(m, table, key_ptr, *_):
    """unordered_map<u32, ...>::at: the value (node+0x14) for the u32 at key_ptr; a missing key throws."""
    node = find(m, table, m.u32(key_ptr), 4)
    if not node:
        raise UnliftedCall("unordered_map::at of a missing key (throws)")
    return node + 0x14


@lifted(0x18B7E00)
def find_u32_at(m, table, key_ptr, *_):
    """The node holding the u32 at key_ptr, or 0."""
    return find(m, table, m.u32(key_ptr), 4)


@lifted(0xFA6BBC)
def at_u32(m, table, key_ptr, *_):
    """unordered_map::at for the u32 at key_ptr: the value slot (node+0x18); a missing key throws."""
    node = find(m, table, m.u32(key_ptr), 4)
    if node == 0:
        raise UnliftedCall("unordered_map::at: key not found")
    return node + 0x18


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


def _u32_map_needs_rehash(m, table, key):
    """True when operator[] of a missing `key` grows the buckets (0xf7c240)."""
    if find(m, table, key & M32, 4):
        return False
    import struct
    n = m.u64(table + 8)
    load = struct.unpack("<f", m.read(table + 0x60, 4))[0]
    return n == 0 or _f32(_f32(load) * _f32(float(n))) < _f32(float(m.u64(table + 0x58) + 1))


@lifted(0xF7A448)
def map_u32_slot(m, table, key_ptr, *_):
    """unordered_map<u32, u32[2]>::operator[]: the value (node+0x14) of the u32 at key_ptr; a missing key
    gets a zeroed node from the allocator [table+0x38] (pushed on the thread's object stack while the
    node is built), growing the buckets through 0xf7c240 past the max load."""
    from pokeldn.sv.battle.engine.references import _tls_stack
    key = m.u32(key_ptr)
    node = find(m, table, key, 4)
    if node:
        return node + 0x14
    n = m.u64(table + 8)
    alloc = m.u64(table + 0x38)
    node = m.vcall(alloc, 0x10, 0x20, 4)
    if not node:
        raise UnliftedCall("allocator out of memory")
    t = _tls_stack(m)
    if t:
        depth = m.u64(t + 0x80)
        if depth >= 0x10:
            raise UnliftedCall("abort: object stack full")
        m.put(t + 8 * depth, 8, m.u64(table + 0x38))
        m.put(t + 0x80, 8, depth + 1)
    m.put(node + 0x10, 4, m.u32(key_ptr)); m.put(node + 0x14, 8, 0)
    if t:
        m.put(t + 0x80, 8, m.u64(t + 0x80) - 1)
    m.put(node, 8, 0); m.put(node + 8, 8, key)
    if _u32_map_needs_rehash(m, table, key):
        import math
        import struct
        load = struct.unpack("<f", m.read(table + 0x60, 4))[0]
        grow = (n << 1) | int(n < 3 or not n & (n - 1) == 0)
        need = math.ceil(_f32(_f32(float(m.u64(table + 0x58) + 1)) / _f32(load)))
        m.call_void(m.main + 0xF7C240, table, max(grow, need))
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
            m.put(buckets + 8 * _bucket(m.u64(nxt + 8), n), 8, node)
    else:
        m.put(node, 8, m.u64(prev))
        m.put(prev, 8, node)
    m.put(table + 0x58, 8, m.u64(table + 0x58) + 1)
    return node + 0x14


def _frees_deferred(m, alloc):
    return m.vcall(alloc, 0xF8) & 1 and m.s(m.call(m.main + 0xB4E600) + 0x12C8, 4) >= 1


@lifted(0x176A354)
@lifted(0x171987C)
def free_buckets(m, pair, ptr, *_):
    """Free a bucket array of [pair] entries through the allocator [pair+8] (vf 0x18, or 0xb48fe8 when
    frees are deferred). 0x176a354 is the same code."""
    size, alloc = m.u64(pair) * 8, m.u64(pair + 8)
    if _frees_deferred(m, alloc):
        return _tail(m, m.main + 0xB48FE8, alloc, ptr, size, 4)
    return _tail(m, m.u64(m.u64(alloc) + 0x18), alloc, ptr, size, 4)


@lifted(0xF8001C)
def do_rehash(m, table, n, *_):
    """libc++ __do_rehash of a u32-keyed map (buckets +0, count +8, bucket allocator +0x10, first node
    +0x30): a fresh zeroed array of n buckets, the old one freed, the node chain regrouped by bucket."""
    return _do_rehash(m, table, n, 0x171987C)


@lifted(0x1589FF0)
def do_rehash_u8(m, table, n, *_):
    """0xf8001c's code for the u32 -> u8 map of 0x1589bc0, freeing through 0x176a354."""
    return _do_rehash(m, table, n, 0x176A354)


def _free_bucket_array(m, table, old, free, align):
    if free is not None:
        return m.call_void(m.main + free, table + 8, old)
    size, alloc = m.u64(table + 8) * 8, m.u64(table + 0x10)
    if _frees_deferred(m, alloc):
        return m.call_void(m.main + 0xB48FE8, alloc, old, size, align)
    m.vcall_void(alloc, 0x18, old, size, align)


def _do_rehash(m, table, n, free, align=4, key=4):
    """`free` is the bucket free's address, or None for the free inlined with `align`; `key` is the
    key's width at node +0x10."""
    old = m.u64(table)
    if old and _frees_deferred(m, m.u64(table + 0x10)) and 0xB48FE8 not in FUNCTIONS:
        raise UnliftedCall("main+0xb48fe8")
    if n == 0:
        m.put(table, 8, 0)
        if old:
            _free_bucket_array(m, table, old, free, align)
        m.put(table + 8, 8, 0)
        return
    arr = m.vcall(m.u64(table + 0x10), 0x10, n * 8, align)
    if not arr:
        raise UnliftedCall("allocator out of memory")
    m.put(table, 8, arr)
    if old:
        _free_bucket_array(m, table, old, free, align)
    m.put(table + 8, 8, n)
    for i in range(n):
        m.put(arr + 8 * i, 8, 0)
    pp = m.u64(table + 0x30)
    if not pp:
        return

    def bucket(h):
        return h & (n - 1) if _pow2(n) else h % n

    phash = bucket(m.u64(pp + 8))
    m.put(arr + 8 * phash, 8, table + 0x30)
    cp = m.u64(pp)
    while cp:
        chash = bucket(m.u64(cp + 8))
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


@lifted(0xFAF460)
def do_rehash_u16(m, table, n, *_):
    """__do_rehash of the u16-keyed command-format map: 0xf8001c's shape with the bucket free inlined
    and alignment 2."""
    return _do_rehash(m, table, n, None, align=2, key=2)


@lifted(0xFAF09C)
def format_slot(m, table, key_ptr, *_):
    """operator[] of the queue's command-format map (u16 key at node +0x10, u8 value at +0x12): the
    value of the key's node, inserting a zero one (0x18-byte node from [table+0x38], align 2, pushed on
    the thread's object stack while built) and growing through 0xfaf460 when the load allows."""
    import math
    import struct
    from pokeldn.sv.battle.engine.references import _tls_stack
    key = m.u16(key_ptr)
    node = find_u16(m, table, key)
    if node:
        return node + 0x12
    n = m.u64(table + 8)
    node = m.vcall(m.u64(table + 0x38), 0x10, 0x18, 2)
    if not node:
        raise UnliftedCall("allocator out of memory")
    alloc = m.u64(table + 0x38)
    t = _tls_stack(m)
    if t:
        depth = m.u64(t + 0x80)
        if depth >= 0x10:
            raise UnliftedCall("abort: object stack full")
        m.put(t + 8 * depth, 8, alloc)
        m.put(t + 0x80, 8, depth + 1)
    m.put(node + 0x10, 2, m.u16(key_ptr)); m.put(node + 0x12, 1, 0)
    if t:
        m.put(t + 0x80, 8, m.u64(t + 0x80) - 1)
    m.put(node, 8, 0); m.put(node + 8, 8, key)
    size1 = _f32(float(m.u64(table + 0x58) + 1))
    load = struct.unpack("<f", m.read(table + 0x60, 4))[0]
    if n == 0 or _f32(load * _f32(float(n))) < size1:
        grow = (n << 1) | int(n < 3 or not _pow2(n))
        need = math.ceil(_f32(size1 / load))
        _rehash(m, table, max(grow, need), 0xFAF460)
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
            m.put(buckets + 8 * _bucket(m.u64(nxt + 8), n), 8, node)
    else:
        m.put(node, 8, m.u64(prev))
        m.put(prev, 8, node)
    m.put(table + 0x58, 8, m.u64(table + 0x58) + 1)
    return node + 0x12


@lifted(0xF7C240)
def rehash(m, table, want, *_):
    """libc++ rehash(want) of a u32-keyed map: grow to want (rounded to a prime unless a power of two);
    shrink only down to what the size and max load (+0x60) allow."""
    return _rehash(m, table, want, 0xF8001C)


@lifted(0x1589EEC)
def rehash_u8(m, table, want, *_):
    """0xf7c240's code, tail-calling 0x1589ff0."""
    return _rehash(m, table, want, 0x1589FF0)


def _rehash(m, table, want, do):
    import math
    import struct
    if want == 1:
        want = 2
    elif want & (want - 1):
        want = m.call(m.main + 0x343D400, want)
    n = m.u64(table + 8)
    if want > n:
        return _tail(m, m.main + do, table, want)
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
        return _tail(m, m.main + do, table, new)


@lifted(0x1589DD4)
def build_u8_node(m, table, key, key_pp, *_):
    """Node of the u32 -> u8 map (0x18 bytes from the allocator [table+0x38]): {next 0, hash key, key
    u32 **key_pp, value 0}; x8 gets {node, table+0x38, constructed 1}."""
    out = m.x8
    alloc = table + 0x38
    node = m.vcall(m.u64(alloc), 0x10, 0x18, 4)
    if not node:
        raise UnliftedCall("allocator out of memory")
    m.put(out, 8, node); m.put(out + 8, 8, alloc)
    m.call_void(m.main + 0x1589E60, alloc, node + 0x10, key_pp)
    m.put(out + 0x10, 1, 1)
    m.put(node, 8, 0); m.put(node + 8, 8, key)


@lifted(0x1589BC0)
def map_u8_slot(m, table, key_ptr, *_):
    """unordered_map<u32, u8>::operator[]: the value (node+0x14) of the u32 at key_ptr; a missing key gets
    a node from 0x1589dd4, growing the buckets through 0x1589eec past the max load."""
    import math
    import struct
    key = m.u32(key_ptr)
    node = find(m, table, key, 4)
    if node:
        return node + 0x14
    n = m.u64(table + 8)
    with m.frame(0x20) as f:
        m.put(f, 8, key_ptr)
        m.x8 = f + 8
        m.call_void(m.main + 0x1589DD4, table, key, f)
        node = m.u64(f + 8)
    size1 = _f32(float(m.u64(table + 0x58) + 1))
    load = struct.unpack("<f", m.read(table + 0x60, 4))[0]
    if n == 0 or _f32(load * _f32(float(n))) < size1:
        grow = (n << 1) | int(n < 3 or not _pow2(n))
        need = math.ceil(_f32(size1 / load))
        m.call_void(m.main + 0x1589EEC, table, max(grow, need))
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
            m.put(buckets + 8 * _bucket(m.u64(nxt + 8), n), 8, node)
    else:
        m.put(node, 8, m.u64(prev))
        m.put(prev, 8, node)
    m.put(table + 0x58, 8, m.u64(table + 0x58) + 1)
    return node + 0x14


@lifted(0xF7BEDC)
def do_rehash_f7bedc(m, table, n, *_):
    """0xf8001c's __do_rehash with the bucket free (0x171987c's code) inlined."""
    return _do_rehash(m, table, n, 0x171987C)


@lifted(0xF785A8)
def _map_u8_slot_inline(m, table, key_ptr, *_):
    """0xf785a8: unordered_map<u32, u8>::operator[] with the node build inlined (0x18-byte node from the allocator
    [table+0x38], pushed on the thread's object stack while its key and zero value are written) and the
    rehash inlined (tail 0xf7bedc)."""
    import math
    import struct
    from pokeldn.sv.battle.engine.references import _tls_stack
    key = m.u32(key_ptr)
    node = find(m, table, key, 4)
    if node:
        return node + 0x14
    n = m.u64(table + 8)
    alloc = m.u64(table + 0x38)
    node = m.vcall(alloc, 0x10, 0x18, 4)
    if not node:
        raise UnliftedCall("allocator out of memory")
    t = _tls_stack(m)
    if t:
        depth = m.u64(t + 0x80)
        if depth >= 0x10:
            raise UnliftedCall("abort: object stack full")
        m.put(t + 8 * depth, 8, m.u64(table + 0x38))
        m.put(t + 0x80, 8, depth + 1)
    m.put(node + 0x10, 4, m.u32(key_ptr)); m.put(node + 0x14, 1, 0)
    if t:
        m.put(t + 0x80, 8, m.u64(t + 0x80) - 1)
    m.put(node, 8, 0); m.put(node + 8, 8, key)
    size1 = _f32(float(m.u64(table + 0x58) + 1))
    load = struct.unpack("<f", m.read(table + 0x60, 4))[0]
    if n == 0 or _f32(load * _f32(float(n))) < size1:
        grow = (n << 1) | int(n < 3 or not _pow2(n))
        need = math.ceil(_f32(size1 / load))
        _rehash(m, table, max(grow, need), 0xF7BEDC)
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
            m.put(buckets + 8 * _bucket(m.u64(nxt + 8), n), 8, node)
    else:
        m.put(node, 8, m.u64(prev))
        m.put(prev, 8, node)
    m.put(table + 0x58, 8, m.u64(table + 0x58) + 1)
    return node + 0x14
