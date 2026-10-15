"""libc++ unordered_map lookups as the server compiles them: buckets at +0, bucket count at +8; a
node is (next, hash, key, value). A u16 key hashes to itself."""

from pokeldn.sv.battle.machine import UnliftedCall, lifted


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
