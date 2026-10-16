"""The battle network object N (0x1b0 bytes, vtable 0x44ff468) and what hangs off it, made by the game's
own creators: the session handler 0x18915c4 builds N+0x48 (vtable 0x44fef38), the counted resources in
its maps, the named-parameter table, the election object and N itself (0x16af068 -> 0x16b0fb8); N's
start states 0x1269824 run the server build and the raid step machine (docs/sv_raid.md, Reproducing a
round). The session manager, S and the setup they start from are in `session`."""

from pokeldn.sv.battle.engine.steps import (
    _create, _do_rehash, _find, _insert, _pop, _push, _rehash, _stores, _tls_stack, _tls_top)
from pokeldn.sv.battle.engine.calls import _tail
from pokeldn.sv.battle.engine.references import _assign_strong, _move_ref, _release_ref, copy_ref
from pokeldn.sv.battle.machine import MASK, UnliftedCall, lifted

M32 = MASK[4]
M64 = MASK[8]
ONE_F = 0x3F800000


# --- shared shapes ----------------------------------------------------------------------------------

def _base(m, o):
    """The common base constructor's head: vtable [0x46d66f8]+0x10, +0x10 / u32 +0x18 zero; returns the
    top of the thread's object stack (the owner a constructor stores at +8)."""
    m.put(o + 0x10, 8, 0); m.put(o + 0x18, 4, 0)
    m.put(o, 8, m.u64(m.main + 0x46D66F8) + 0x10)
    return _tls_top(m)


def _make(m, alloc, size, ctor):
    """Create: `size` bytes from alloc with alloc on the thread's object stack, the constructor at
    `ctor`, then the header (+8 alloc, +0x10 itself, u32 +0x18 size | 0x80000)."""
    return _create(m, alloc, size, lambda o: m.call_void(m.main + ctor, o))


def _make_z(m, alloc, size, ctor, got, b, c):
    """Create with the block zeroed, the constructor, then vtables [got]+0x10 (+0x20 its +b, +0x28 its +c)."""
    def build(o):
        m.write(o, bytes(size))
        m.call_void(m.main + ctor, o)
        vt = m.u64(m.main + got)
        m.put(o + 0x10, 8, o)
        m.put(o + 0x20, 8, vt + b); m.put(o + 0x28, 8, vt + c)
        m.put(o, 8, vt + 0x10)
    return _create(m, alloc, size, build)


def _class_static(m, slot, guard):
    """A class static at main+slot (guard main+guard) holding the four-level chain's slot [0x46d3ab0]
    (guards 0x46d3aa8, 0x46d39b0, 0x46d39c0)."""
    from pokeldn.sv.battle.engine.statics import _static_chain
    g = m.main + guard
    if m.u8(g) & 1 or m.call(m.main + 0x343CF10, g) & M32 == 0:
        return
    _static_chain(m, ((0x46D3AA8, 0x46D3AB0), (0x46D39B0, 0x46D39B8), (0x46D39C0, 0x46D39C8)))
    m.put(m.main + slot, 8, m.u64(m.main + 0x46D3AB0))
    m.call_void(m.main + 0x343CF20, g)


def _inc(m, p):
    c = m.u32(p + 0x28)
    if c == M32:
        raise UnliftedCall("abort: IncrementReferenceInternal")
    m.put(p + 0x28, 4, c + 1)


def _set_counted(m, holder, p):
    """*holder = p for an intrusive pointer (u32 count +0x28): p gains one, the old value loses one, the
    last running its vf 0x10. Returns x0 as the game leaves it."""
    if p:
        _inc(m, p)
    old = m.u64(holder)
    m.put(holder, 8, p)
    if not old:
        return 0
    return _release_ref(m, old)


def _release_strong(m, holder):
    """ReleaseReference on *holder's control block ([+0x30], u16 +0x1a): the last one clears +0x10 and
    ends in the object's vf 0x50."""
    o = m.u64(holder)
    if not o:
        return 0
    c = m.u64(o + 0x30)
    n = m.u16(c + 0x1A)
    if n == 0:
        raise UnliftedCall("abort: ReleaseReference")
    m.put(c + 0x1A, 2, n - 1)
    if n != 1:
        return o
    m.put(c + 0x10, 8, 0)
    return m.vcall(o, 0x50)


for _a in (0x2A0F670, 0x2A0F7BC):
    lifted(_a)(_move_ref)
lifted(0x2A0F75C)(copy_ref)


@lifted(0x1838590)
def release_counted_holder(m, holder, *_):
    p = m.u64(holder)
    return _release_ref(m, p) if p else 0


@lifted(0x18385FC)
def release_strong_holder(m, holder, *_):
    return _release_strong(m, holder)


for _a in (0x16F6B18, 0x16F6BD4, 0x1722538, 0x17225F4, 0x16AF3E8):
    lifted(_a)(lambda m, holder, p, *_: _set_counted(m, holder, p))

for _a in (0x2A0F8A4, 0x16F6C90, 0x16F6DCC):
    lifted(_a)(lambda m, holder, p, *_: _assign_strong(m, holder, p, "old"))


# --- N+0x48 (0x150 bytes, vtable 0x44fef38) and its two u32-keyed maps of counted resources ----------

@lifted(0x1746CD0)
def construct_n48(m, o, *_):
    """vtable 0x44fef38 (+0x20 0x44fef70), two empty u32-keyed maps at +0x30 and +0x98 over the owner
    (max load 1.0), +0x100..+0x14f zero."""
    top = _base(m, o)
    m.put(o + 0x28, 4, 0)
    m.put(o, 8, m.main + 0x44FEF38); m.put(o + 8, 8, top)
    m.put(o + 0x20, 8, m.main + 0x44FEF70)
    big = 0x0FFFFFFFFFFFFFFF
    for off, v in ((0x30, 0), (0x38, 0), (0x50, 0), (0x88, 0), (0xB8, 0), (0xF0, 0)):
        m.put(o + off, 8, v)
    for off in (0x58, 0x80, 0xC0, 0xE8):
        m.put(o + off, 4, 0)
    m.put(o + 0x90, 4, ONE_F); m.put(o + 0xF8, 4, ONE_F)
    for off, v in ((0x40, top), (0x48, big), (0x60, 0), (0x68, top), (0x70, big), (0x78, 0),
                   (0x98, 0), (0xA0, 0), (0xA8, top), (0xB0, big), (0xC8, 0), (0xD0, top), (0xD8, big),
                   (0xE0, 0)):
        m.put(o + off, 8, v)
    m.write(o + 0x100, bytes(0x50))


@lifted(0x1746BA8)
def create_n48(m, alloc, *_):
    return _make(m, alloc, 0x150, 0x1746CD0)


@lifted(0x1746B3C)
def make_n48(m, alloc, *_):
    """*x8 = a new N+0x48 object holding one reference."""
    out = m.x8
    p = m.call(m.main + 0x1746BA8, alloc)
    m.put(out, 8, p)
    if p:
        _inc(m, p)
    return p


@lifted(0x1655594)
def do_rehash_1655594(m, table, n, *_):
    """__do_rehash of N+0x48's u32 map at +0x30 (bucket arrays aligned 8, freed through 0x165581c)."""
    _do_rehash(m, table, n, 8, 4)


@lifted(0x1655D94)
def do_rehash_1655d94(m, table, n, *_):
    """__do_rehash of N+0x48's u32 map at +0x98."""
    _do_rehash(m, table, n, 8, 4)


@lifted(0x1655490)
def rehash_1655490(m, table, n, *_):
    _rehash(m, table, n, 0x1655594)


@lifted(0x1655C90)
def rehash_1655c90(m, table, n, *_):
    _rehash(m, table, n, 0x1655D94)


def _free_buckets(m, ref, arr):
    """Free a bucket array of [ref] pointers through the allocator [ref+8] (0xb48fe8 when it defers)."""
    n, alloc = m.u64(ref), m.u64(ref + 8)
    size = n << 3
    if m.vcall(alloc, 0xF8) & 1 and m.s(m.call(m.main + 0xB4E600) + 0x12C8, 4) >= 1:
        return m.call(m.main + 0xB48FE8, alloc, arr, size, 8)
    return m.vcall(alloc, 0x18, arr, size, 8)


for _a in (0x165581C, 0x165601C):
    lifted(_a)(lambda m, ref, arr, *_: _free_buckets(m, ref, arr))


def _slot_u32(m, table, key_ptr, do):
    """operator[] of an unordered_map<u32, u64> (node 0x20 {next, hash, u32 key, value}): the value's
    address; a missing key gets a node from [table+0x38] (pushed on the thread's object stack while its
    key and value are stored)."""
    key = m.u32(key_ptr)
    node = _find(m, table, key, 4)
    if node:
        return node + 0x18
    alloc = m.u64(table + 0x38)
    node = m.vcall(alloc, 0x10, 0x20, 8)
    if not node:
        raise UnliftedCall("allocator out of memory: vf 0xe8")
    owner = m.u64(table + 0x38)
    stack = _tls_stack(m)
    if stack:
        _push(m, stack, owner)
    m.put(node + 0x10, 4, m.u32(key_ptr)); m.put(node + 0x18, 8, 0)
    if stack:
        _pop(m, stack)
    m.put(node, 8, 0); m.put(node + 8, 8, key)
    _insert(m, table, node, key, do)
    return node + 0x18


@lifted(0x1655190)
def slot_1655190(m, table, key_ptr, *_):
    return _slot_u32(m, table, key_ptr, 0x1655594)


@lifted(0x1655990)
def slot_1655990(m, table, key_ptr, *_):
    return _slot_u32(m, table, key_ptr, 0x1655D94)


def _set_resource(m, o, key, src, table, slot):
    """For key below 5 or 0xff: map[key] = *src (a counted resource, one reference taken; the old one
    released)."""
    key &= M32
    if key < 5 or key >= 0x80000000 or key == 0xFF:          # a signed compare with 5
        with m.frame(0x10) as k:
            m.put(k, 4, key)
            p = m.call(m.main + slot, o + table, k)
        v = m.u64(src)
        if v:
            _inc(m, v)
        old = m.u64(p)
        m.put(p, 8, v)
        if old:
            return _release_ref(m, old)
        return 0
    return o


@lifted(0x16550A4)
def set_resource_30(m, o, key, src, *_):
    """N+0x48's map at +0x30: key (0..4, or 0xff) -> the counted resource *src."""
    return _set_resource(m, o, key, src, 0x30, 0x1655190)


@lifted(0x16558A4)
def set_resource_98(m, o, key, src, *_):
    """N+0x48's map at +0x98: key (0..4, or 0xff) -> the counted resource *src."""
    return _set_resource(m, o, key, src, 0x98, 0x1655990)


# --- the counted resources N+0x48 maps key 0..4 to: 0x3e8 bytes (vtable 0x4484d40) and 0xb70 bytes
# (vtable 0x4485218) ----------------------------------------------------------------------------------

@lifted(0x1609500)
def resource_base_1609500(m, o, *_):
    """vtable [0x46dcd40]+0x10 (+0x20 its +0x70), +8 the owner, u32 +0x28 and +0x30..+0x47 zero."""
    top = _base(m, o)
    m.put(o + 0x28, 4, 0); m.put(o + 0x30, 8, 0); m.put(o + 0x38, 8, 0)
    vt = m.u64(m.main + 0x46DCD40)
    m.put(o, 8, vt + 0x10); m.put(o + 8, 8, top)
    m.put(o + 0x20, 8, vt + 0x70)
    m.put(o + 0x40, 8, 0)


@lifted(0x16092A4)
def construct_resource_3e8(m, o, *_):
    """vtable 0x4484d40 (+0x20 0x4484da0); a xoroshiro128+ at +0xb0 (vtable [0x46dcd38]+0x10, state
    0x0f4b17a579f18960 / 0x82a2b175229d6a5b, count 0), five u32 5 at +0x348..+0x378, +0x3ad = 1, the rest
    of the fields zero."""
    m.call_void(m.main + 0x1609500, o)
    m.put(o, 8, m.main + 0x4484D40)
    _stores(m, o, ((0x70, 8, 0), (0x78, 4, 0)))
    m.put(o + 0x20, 8, m.main + 0x4484DA0)
    _stores(m, o, ((0x80, 1, 0), (0x88, 8, 0), (0x90, 4, 0)))
    m.put(o + 0xB0, 8, m.u64(m.main + 0x46DCD38) + 0x10)
    _stores(m, o, ((0xB8, 8, 0x0F4B17A579F18960), (0x98, 1, 0), (0xF0, 8, 0)))
    for off in range(0x140, 0x200, 0x10):
        _stores(m, o, ((off, 8, 0), (off + 8, 4, 0)))
    for off in range(0x230, 0x2E0, 0x10):
        _stores(m, o, ((off, 8, 0), (off + 8, 4, 0)))
    _stores(m, o, (
        (0x31C, 4, 0), (0x320, 2, 0), (0xC0, 8, 0x82A2B175229D6A5B), (0xC8, 8, 0), (0xD0, 8, 0), (0xD8, 8, 0),
        (0xE0, 8, 0), (0xE8, 8, 0), (0x33C, 8, 0), (0x334, 8, 0), (0x32C, 8, 0), (0x324, 8, 0), (0x220, 8, 0),
        (0x228, 4, 0), (0x348, 4, 5), (0x350, 8, 0), (0x358, 8, 0), (0x360, 8, 0x500000005), (0x39A, 2, 0),
        (0x39C, 1, 0), (0x37C, 2, 0), (0x382, 2, 0), (0x388, 4, 0), (0x394, 2, 0), (0x368, 8, 0x500000005),
        (0x37E, 1, 0), (0x384, 1, 0), (0x38C, 2, 0), (0x396, 1, 0), (0x370, 8, 0x500000005), (0x37F, 2, 0),
        (0x385, 2, 0), (0x38E, 4, 0), (0x397, 2, 0), (0x378, 4, 5), (0x381, 1, 0), (0x387, 1, 0),
        (0x392, 2, 0), (0x399, 1, 0), (0x3D0, 8, 0), (0x3C0, 8, 0), (0x3C7, 4, 0), (0x214, 2, 0)))
    m.put(o + 0x12C, 1, m.u8(o + 0x12C) & 0xFC)
    _stores(m, o, (
        (0x3B0, 8, 0), (0x3B8, 8, 0), (0x48, 8, 0), (0x210, 1, 0), (0x218, 8, 0), (0x12E, 1, 0), (0x208, 8, 0),
        (0x200, 4, 0), (0x204, 2, 0), (0x3E0, 4, 0), (0x122, 1, 0), (0x11C, 4, 0), (0x12D, 1, 0), (0xA8, 8, 0),
        (0x120, 1, 0), (0x3AD, 1, 1), (0x3A0, 1, 0), (0x3AC, 1, 0), (0x3A4, 8, 0)))


@lifted(0x1668D44)
def construct_resource_b70(m, o, *_):
    """vtable 0x4485218 (+0x20 0x44854a0): sixteen 0x90-byte blocks from +0x2b8 with their first 0x41
    bytes zero, u32 +0x120 0x0a0a0000, the 7-filled run +0x12d..+0x14d, u32 +0x170 1, +0x1a4 5."""
    top = _base(m, o)
    m.put(o + 8, 8, top); m.put(o + 0x28, 4, 0)
    m.write(o + 0xD0, bytes(0x41))
    m.write(o + 0x48, bytes(0x48))
    _stores(m, o, (
        (0x120, 4, 0x0A0A0000), (0x124, 8, 0xFFFF000000000000), (0x12C, 1, 0), (0x160, 8, 0), (0x150, 8, 0),
        (0x158, 8, 0), (0x135, 8, 0x0007000007000007), (0x12D, 8, 0x0000070000070000),
        (0x145, 8, 0x0000070000070000), (0x13D, 8, 0x0700000700000700), (0x14D, 1, 7), (0x170, 4, 1)))
    m.put(o, 8, m.main + 0x4485218)
    m.put(o + 0x20, 8, m.main + 0x44854A0)
    _stores(m, o, ((0x184, 8, 0), (0x18C, 8, 0), (0x194, 8, 0), (0x19C, 8, 0), (0x17A, 8, 0), (0x1A4, 1, 5)))
    for off in range(0x2B8, 0xB29, 0x90):
        m.write(o + off, bytes(0x41))
    _stores(m, o, ((0xB6C, 2, 0), (0x1B8, 8, 0), (0x1A8, 8, 0), (0x1B0, 8, 0)))


@lifted(0x1668C1C)
def create_resource_b70(m, alloc, *_):
    return _make(m, alloc, 0xB70, 0x1668D44)


def _create_resource_3e8(m, alloc):
    """0x18915c4's inline Create of a 0x3e8-byte resource (0x16092a4)."""
    return _make(m, alloc, 0x3E8, 0x16092A4)


# --- N+0x48 +0x110: a 0x38-byte counted object (vtable 0x4484cb0) ------------------------------------

@lifted(0x1772DC4)
def construct_1772dc4(m, o, *_):
    """vtable 0x4484cb0 (+0x20 0x4484d10), +8 the owner, u32 +0x28 and +0x30 zero."""
    m.put(o + 0x10, 8, 0); m.put(o + 0x18, 4, 0)
    m.put(o, 8, m.u64(m.main + 0x46D66F8) + 0x10)
    t = m.call(m.main + 0x343DA20, m.u32(m.call(m.main + 0xF53840)))
    top = m.u64(t + 8 * m.u64(t + 0x80) - 8) if t and m.u64(t + 0x80) else 0
    m.put(o + 0x28, 4, 0)
    m.put(o, 8, m.main + 0x4484CB0); m.put(o + 8, 8, top)
    m.put(o + 0x20, 8, m.main + 0x4484D10)
    m.put(o + 0x30, 8, 0)


@lifted(0x1772C9C)
def create_1772c9c(m, alloc, *_):
    return _make(m, alloc, 0x38, 0x1772DC4)


# --- the named-parameter table N+0x48 +0x148 (0xa8 bytes, vtable 0x4485568) --------------------------

# The 29 values 0x146496c stores, in its order, one per 0x10-byte entry of main 0x3c60f80 (u64 name hash,
# then the same value as a u32 at +8).
PARAMETER_TABLE = 0x3C60F80
PARAMETER_VALUES = (2, 4, 25, 50, 20, 8, 16, 16, 50, 33, 40, 2, 4, 50, 4, 4, 5, 150, 150, 15, 150, 75, 25, 150,
                    50, 200, 4, 8, 60)


def _scope_owner(m, h):
    """An allocator holder {owner, max 0x0fffffffffffffff, 0, u32 0}: the owner is the top of the thread's
    object stack (0xf60ed0's default when the stack is empty)."""
    top = _tls_top(m)
    if not top:
        raise UnliftedCall("main+0xf60ed0")
    m.put(h + 0x18, 4, 0)
    m.put(h, 8, top); m.put(h + 8, 8, 0x0FFFFFFFFFFFFFFF); m.put(h + 0x10, 8, 0)


for _a in (0x14647FC, 0x14648B4):
    lifted(_a)(lambda m, h, *_: _scope_owner(m, h))


@lifted(0x14647BC)
def empty_map_14647bc(m, t, *_):
    """An empty unordered_map<u64, u32> over the thread's current owner (max load 1.0)."""
    m.put(t, 8, 0); m.put(t + 8, 8, 0)
    m.call_void(m.main + 0x14647FC, t + 0x10)
    m.put(t + 0x30, 8, 0)
    m.call_void(m.main + 0x14648B4, t + 0x38)
    m.put(t + 0x58, 8, 0); m.put(t + 0x60, 4, ONE_F)


@lifted(0x1464FA4)
def do_rehash_1464fa4(m, table, n, *_):
    """__do_rehash of the named-parameter map (u64 keys, bucket arrays aligned 8)."""
    _do_rehash(m, table, n, 8, 8)


@lifted(0x1464EA0)
def rehash_1464ea0(m, table, n, *_):
    _rehash(m, table, n, 0x1464FA4)


@lifted(0x1464BB4)
def parameter_slot(m, table, key_ptr, *_):
    """operator[] of the unordered_map<u64 name hash, u32> (node 0x20 {next, hash, key, u32 value}):
    the value's address; a missing key gets a node from [table+0x38] with value 0."""
    key = m.u64(key_ptr)
    node = _find(m, table, key, 8)
    if node:
        return node + 0x18
    node = m.vcall(m.u64(table + 0x38), 0x10, 0x20, 8)
    if not node:
        raise UnliftedCall("allocator out of memory: vf 0xe8")
    owner = m.u64(table + 0x38)
    stack = _tls_stack(m)
    if stack:
        _push(m, stack, owner)
    m.put(node + 0x10, 8, m.u64(key_ptr)); m.put(node + 0x18, 4, 0)
    if stack:
        _pop(m, stack)
    m.put(node, 8, 0); m.put(node + 8, 8, key)
    _insert(m, table, node, key, 0x1464FA4)
    return node + 0x18


@lifted(0x146496C)
def fill_parameters(m, o, *_):
    """The 29 named parameters into the map at +0x40, in the order of their entries at 0x3c60f80."""
    for i, value in enumerate(PARAMETER_VALUES):
        m.put(m.call(m.main + 0x1464BB4, o + 0x40, m.main + PARAMETER_TABLE + 0x10 * i), 4, value)


@lifted(0x14646A0)
def construct_parameters(m, o, *_):
    """vtable 0x4485568 (+0x20 0x44855e8, +0x28 0x4485638), a weak handle at +0x30 to its +0x28 part,
    the map at +0x40 (0x14647bc) filled by 0x146496c."""
    top = _base(m, o)
    vt = m.u64(m.main + 0x46D8C78)
    m.put(o, 8, vt + 0x10); m.put(o + 8, 8, top)
    m.put(o + 0x20, 8, vt + 0x88); m.put(o + 0x28, 8, vt + 0xD8)
    m.put(o + 0x38, 8, 0); m.put(o + 0x30, 8, 0)
    m.call_void(m.main + 0xC1A3F4, o + 0x30, o + 0x28)
    m.put(o, 8, m.main + 0x4485568); m.put(o + 0x20, 8, m.main + 0x44855E8)
    m.put(o + 0x28, 8, m.main + 0x4485638)
    m.call_void(m.main + 0x14647BC, o + 0x40)
    return _tail(m, m.main + 0x146496C, o)


@lifted(0x1464578)
def create_parameters(m, alloc, *_):
    return _make(m, alloc, 0xA8, 0x14646A0)


lifted(0x170B3F0)(lambda m, *_: _class_static(m, 0x4740BF0, 0x4740BF8))


@lifted(0x2A145B8)
def parameters_class(m, *_):
    """vf 0 of the named-parameter table's shared part: its class static 0x4740bf0."""
    m.call_void(m.main + 0x170B3F0)
    return m.main + 0x4740BF0


def _acquire_into(m, dst, p):
    """*dst = p with one strong reference taken on p's control block [p+0x30] (u16 +0x1a; the first one
    stores vf 0 of +0x10 at +8 and -2 at +0x1c)."""
    m.put(dst, 8, p)
    if not p:
        return dst
    c = m.u64(p + 0x30)
    if m.u64(c + 0x10) == 0:
        raise UnliftedCall("abort: AddReference m_object")
    n = m.u16(c + 0x1A)
    if n == 0xFFFF:
        raise UnliftedCall("abort: AddReference overflow")
    m.put(c + 0x1A, 2, n + 1)
    if n == 0:
        obj = m.u64(c + 0x10)
        m.put(c + 8, 8, m.vcall(obj, 0))
        m.put(c + 0x1C, 4, 0xFFFFFFFE)
    return dst


lifted(0x2A10010)(lambda m, dst, p, *_: _acquire_into(m, dst, p))


# --- N+0x190: 0x108 bytes, vtable 0x44920f8, two empty maps at +0x38 and +0xa0 ------------------------

def _top_f53840(m):
    """The top of the thread's object stack through the slot 0xf53840 returns, or 0."""
    t = m.call(m.main + 0x343DA20, m.u32(m.call(m.main + 0xF53840)))
    return m.u64(t + 8 * m.u64(t + 0x80) - 8) if t and m.u64(t + 0x80) else 0


for _a in (0x1559520, 0x1559578, 0x15595D0, 0x1559628):
    lifted(_a)(lambda m, h, *_: _scope_owner(m, h))


def _empty_map(m, t, owner_a, owner_b):
    m.put(t, 8, 0); m.put(t + 8, 8, 0)
    m.call_void(m.main + owner_a, t + 0x10)
    m.put(t + 0x30, 8, 0)
    m.call_void(m.main + owner_b, t + 0x38)
    m.put(t + 0x58, 8, 0); m.put(t + 0x60, 4, ONE_F)


lifted(0x15594A0)(lambda m, t, *_: _empty_map(m, t, 0x1559520, 0x1559578))
lifted(0x15594E0)(lambda m, t, *_: _empty_map(m, t, 0x15595D0, 0x1559628))


@lifted(0x1559680)
def base_1559680(m, o, *_):
    """vtable 0x4492278 (+0x20 0x44922b0, +0x30 0x44922e0), +8 the owner, u32 +0x28 zero."""
    m.put(o + 0x10, 8, 0); m.put(o + 0x18, 4, 0)
    m.put(o, 8, m.u64(m.main + 0x46D66F8) + 0x10)
    top = _top_f53840(m)
    m.put(o + 0x28, 4, 0)
    m.put(o, 8, m.main + 0x4492278); m.put(o + 8, 8, top)
    m.put(o + 0x20, 8, m.main + 0x44922B0); m.put(o + 0x30, 8, m.main + 0x44922E0)


@lifted(0x1559454)
def construct_1559454(m, o, *_):
    """vtable [0x46dcda8]+0x10 (+0x20 its +0x100, +0x30 its +0x130), maps at +0x38 and +0xa0."""
    m.call_void(m.main + 0x1559680, o)
    vt = m.u64(m.main + 0x46DCDA8)
    m.put(o, 8, vt + 0x10); m.put(o + 0x20, 8, vt + 0x100); m.put(o + 0x30, 8, vt + 0x130)
    m.call_void(m.main + 0x15594A0, o + 0x38)
    return _tail(m, m.main + 0x15594E0, o + 0xA0)


@lifted(0x1559418)
def construct_1559418(m, o, *_):
    """vtable 0x44920f8 (+0x20 0x44921f0, +0x30 0x4492220) over 0x1559454."""
    m.call_void(m.main + 0x1559454, o)
    m.put(o, 8, m.main + 0x44920F8); m.put(o + 0x20, 8, m.main + 0x44921F0)
    m.put(o + 0x30, 8, m.main + 0x4492220)


@lifted(0x15592F0)
def create_15592f0(m, alloc, *_):
    return _make(m, alloc, 0x108, 0x1559418)


# --- objects with a weak handle to their +0x28 part ---------------------------------------------------

def _weak_base(m, o):
    """The weakly referenced base: vtable [0x46d8c78]+0x10 (+0x20 its +0x88, +0x28 its +0xd8), +8 the
    owner, a weak handle at +0x30 (id +0x38) to the +0x28 part (0xc1a3f4)."""
    top = _base(m, o)
    vt = m.u64(m.main + 0x46D8C78)
    m.put(o, 8, vt + 0x10); m.put(o + 8, 8, top)
    m.put(o + 0x20, 8, vt + 0x88); m.put(o + 0x28, 8, vt + 0xD8)
    m.put(o + 0x38, 8, 0); m.put(o + 0x30, 8, 0)
    m.call_void(m.main + 0xC1A3F4, o + 0x30, o + 0x28)


def _vtables(m, o, vt, b, c):
    m.put(o, 8, m.main + vt); m.put(o + 0x20, 8, m.main + vt + b); m.put(o + 0x28, 8, m.main + vt + c)


def _make_strong(m, create, alloc):
    """*x8 = a new object from `create` holding one strong reference (0x2a10010's acquire)."""
    out = m.x8
    p = m.call(m.main + create, alloc)
    _acquire_into(m, out, p)
    return p


@lifted(0x16B0668)
def two_deques_16b0668(m, d, alloc, *_):
    """Two empty deque headers {map first, begin, end, cap, allocator, max 0x1fffffffffffffff, 0, u32 0}
    at d and d+0x30, copied from a stack temporary whose padding (d+0x3c, d+0x6c) holds whatever the
    stack held (zero here)."""
    for off in (0, 8, 0x10, 0x18, 0x30, 0x40, 0x48, 0x60):
        m.put(d + off, 8, 0)
    m.put(d + 0x20, 8, alloc); m.put(d + 0x28, 8, 0x1FFFFFFFFFFFFFFF); m.put(d + 0x38, 8, 0)
    m.put(d + 0x50, 8, alloc); m.put(d + 0x58, 8, 0x1FFFFFFFFFFFFFFF); m.put(d + 0x68, 8, 0)


@lifted(0x16B0548)
def construct_16b0548(m, o, *_):
    """vtable 0x44eede8 (+0x20 0x44eee68, +0x28 0x44eeeb8), +0x40..+0x57 zero, two deques at +0x58."""
    _weak_base(m, o)
    _vtables(m, o, 0x44EEDE8, 0x80, 0xD0)
    m.put(o + 0x40, 8, 0); m.put(o + 0x48, 8, 0); m.put(o + 0x50, 8, 0)
    return _tail(m, m.main + 0x16B0668, o + 0x58, m.u64(o + 8))


@lifted(0x16B02DC)
def construct_16b02dc(m, o, *_):
    """vtable 0x44eeb88 (+0x20 0x44eec18, +0x28 0x44eec68), +0x40..+0x57 zero."""
    _weak_base(m, o)
    _vtables(m, o, 0x44EEB88, 0x90, 0xE0)
    m.put(o + 0x50, 8, 0); m.put(o + 0x40, 8, 0); m.put(o + 0x48, 8, 0)


@lifted(0x16B0C80)
def construct_16b0c80(m, o, *_):
    """vtable 0x44eef10 (+0x20 0x44eef90, +0x28 0x44eefe0), +0x40..+0x4f zero."""
    _weak_base(m, o)
    _vtables(m, o, 0x44EEF10, 0x80, 0xD0)
    m.put(o + 0x40, 8, 0); m.put(o + 0x48, 8, 0)


@lifted(0x1849CBC)
def create_1849cbc(m, alloc, *_):
    return _make_z(m, alloc, 0xD0, 0x16B0548, 0x46DCD10, 0x90, 0xE0)


@lifted(0x1849ED4)
def create_1849ed4(m, alloc, *_):
    return _make_z(m, alloc, 0x50, 0x16B0C80, 0x46DCD18, 0x90, 0xE0)


@lifted(0x17E1D84)
def construct_17e1d84(m, o, *_):
    """vtable 0x4493530 (+0x20 0x44935c0, +0x28 0x4493610) over 0x16b02dc, +0x58..+0x117 zero, +0x118 1."""
    m.call_void(m.main + 0x16B02DC, o)
    _vtables(m, o, 0x4493530, 0x90, 0xE0)
    m.write(o + 0x58, bytes(0xC0))
    m.put(o + 0x118, 1, 1)


@lifted(0x17E1C5C)
def create_17e1c5c(m, alloc, *_):
    return _make(m, alloc, 0x120, 0x17E1D84)


for _a, _c in ((0x1849BF8, 0x1849CBC), (0x17E1B98, 0x17E1C5C), (0x1849E10, 0x1849ED4)):
    lifted(_a)(lambda m, alloc, *_, c=_c: _make_strong(m, c, alloc))


# --- the election object N+0x138 (0x100 bytes, vtable 0x4492a48) -------------------------------------

@lifted(0x18D9710)
def construct_election(m, o, *_):
    """vtable 0x4492a48 (+0x20 0x4492b00, +0x28 0x4492b50, +0x40 0x4492ba8, +0x48 0x4492bc0), server slot
    +0x58 and own slot +0x5c 5, two empty containers over the owner at +0x60 and +0x90 (max
    0x0666666666666666), max load 1.0 at +0xc0."""
    _weak_base(m, o)
    _vtables(m, o, 0x4492A48, 0xB8, 0x108)
    owner = m.u64(o + 8)
    _stores(m, o, ((0x80, 8, 0), (0x50, 8, 0), (0x58, 8, 0x500000005), (0x88, 4, 0), (0xB0, 4, 0),
                   (0xB8, 8, 0), (0xD0, 1, 0), (0xCC, 1, 0), (0xC8, 4, 0)))
    m.put(o + 0x40, 8, m.main + 0x4492BA8); m.put(o + 0x48, 8, m.main + 0x4492BC0)
    _stores(m, o, ((0x70, 8, owner), (0x78, 8, 0x0666666666666666), (0xA0, 8, 0x0666666666666666),
                   (0xA8, 8, 0), (0xC0, 4, ONE_F), (0x60, 8, 0), (0x68, 8, 0), (0x90, 8, 0), (0x98, 8, owner),
                   (0xF0, 8, 0), (0xF8, 8, 0)))


@lifted(0x18D95E8)
def create_election(m, alloc, *_):
    return _make(m, alloc, 0x100, 0x18D9710)


lifted(0x18D9524)(lambda m, alloc, *_: _make_strong(m, 0x18D95E8, alloc))


@lifted(0x2A1DBB8)
def static_46dccf0(m, *_):
    """The election class's static [0x46dccf0] (guard [0x46dcce8]) over the four-level chain; returns
    the slot's address."""
    from pokeldn.sv.battle.engine.statics import _static_chain
    _static_chain(m, ((0x46DCCE8, 0x46DCCF0), (0x46D3AA8, 0x46D3AB0), (0x46D39B0, 0x46D39B8),
                      (0x46D39C0, 0x46D39C8)))
    return m.u64(m.main + 0x46DCCF0)


@lifted(0x2A1DCEC)
def election_class(m, part, *_):
    """vf 0 of the election object's +0x28 part: its class static (0x2a1dbb8)."""
    m.call(m.main + 0x2A1DBB8, part - 0x28)
    return m.u64(m.main + 0x46DCCF0)


# --- the election object's start (0x2a1cd74): slots from the setup ----------------------------------
# The console's Pia session (the network manager static [0x46d6ca0]) gives the station ids; the arena has
# none, so the ids are 0 and the manager is not told about the election (0x1968860).

def _optional_empty(m, o):
    return m.u8(o) == 0


@lifted(0x1891340)
def copy_optional_1891340(m, dst, src, *_):
    """An optional {flag, handle, weak reference} copied: here only an empty one."""
    m.put(dst, 1, 0)
    if not _optional_empty(m, src):
        raise UnliftedCall("main+0x1891340 with a value")
    return dst


@lifted(0x201522C)
def assign_optional_201522c(m, dst, src, *_):
    if not (_optional_empty(m, dst) and _optional_empty(m, src)):
        raise UnliftedCall("main+0x201522c with a value")
    return dst


def _network_manager(m):
    """The network manager static [[0x46d6ca0]] (guard [0x46d6c98]; its __cxa_atexit registration is not
    reproduced), also noted at [[0x46d6ca8]]."""
    guard = m.u64(m.main + 0x46D6C98)
    if m.u8(guard) & 1 == 0 and m.call(m.main + 0x343CF10, guard) & M32:
        m.call_void(m.main + 0x343CF20, guard)
    mgr = m.u64(m.u64(m.main + 0x46D6CA0))
    m.put(m.u64(m.main + 0x46D6CA8), 8, mgr)
    return mgr


@lifted(0x2015170)
def own_station(m, net, *_):
    """This console's own station id ([[0x46d0a08]]+0xb8) when a network manager exists, else 0."""
    if m.u8(net + 0xD0):
        raise UnliftedCall("main+0x2015170 with a session handle")
    if _network_manager(m) == 0:
        return 0
    s = m.u64(m.u64(m.main + 0x46D0A08))
    return m.u64(s + 0xB8) if s else 0


@lifted(0x2015064)
def station_of_code(m, net, code_ptr, *_):
    """The station id of a member code: 0 with no network manager."""
    if m.u8(net + 0xD0):
        raise UnliftedCall("main+0x2015064 with a session handle")
    mgr = _network_manager(m)
    if mgr == 0 or m.u64(mgr + 0x70) == 0:
        return 0
    raise UnliftedCall("main+0xca4118: a station lookup in the Pia session")


@lifted(0x1968860)
def register_election(m, net, *_):
    """Registers the election object with the network manager (0x1567c7c); nothing without one."""
    if m.u8(net + 0xD0):
        raise UnliftedCall("main+0x1968860 with a session handle")
    if _network_manager(m) == 0:
        return 0
    raise UnliftedCall("main+0x1567c7c: a network manager listener")


@lifted(0x18BE64C)
def do_rehash_18be64c(m, table, n, *_):
    """__do_rehash of the election's slot map (u32 keys, bucket arrays aligned 8)."""
    _do_rehash(m, table, n, 8, 4)


@lifted(0x18BE548)
def rehash_18be548(m, table, n, *_):
    _rehash(m, table, n, 0x18BE64C)


@lifted(0x18BE1C4)
def election_slot(m, table, key_ptr, *_):
    """operator[] of the election's unordered_map<u32 slot, 0x20-byte node data> (node 0x38): a new
    node's data is {u8 0, u64 5 at +4, 0 at +0x10, u8 0 at +0x18} built with [table+0x38] on the
    thread's object stack. Returns the data's address (node +0x18)."""
    key = m.u32(key_ptr)
    node = _find(m, table, key, 4)
    if node:
        return node + 0x18
    owner = m.u64(table + 0x38)
    node = m.vcall(owner, 0x10, 0x38, 8)
    if not node:
        raise UnliftedCall("allocator out of memory")
    stack = _tls_stack(m)
    if stack:
        _push(m, stack, owner)
    v = node + 0x10
    m.put(v + 0x18, 8, 0); m.put(v, 4, m.u32(key_ptr)); m.put(v + 0xC, 8, 5)
    m.put(v + 8, 1, 0); m.put(v + 0x20, 1, 0)
    if stack:
        _pop(m, stack)
    m.put(node, 8, 0); m.put(node + 8, 8, key)
    _insert(m, table, node, key, 0x18BE64C)
    return node + 0x18


@lifted(0x2A1CD74)
def start_election(m, net, setup, opt, *_):
    """The election object's start: the optional session handle (+0xd0), its own station (+0xf0), the
    setup (+0x50), the server slot setup+0x94 (+0x58) and its own slot setup+0x90 (+0x5c); one slot
    node per battle slot s that 0xe7e2a0(mode, rule, s) admits and whose member code setup+0x99+s is not
    0xff: {server s == +0x58, slot s, 1, station, code}."""
    m.call_void(m.main + 0x201522C, net + 0xD0, opt)
    m.put(net + 0xF0, 8, m.call(m.main + 0x2015170, net))
    m.put(net + 0x50, 8, setup)
    m.put(net + 0x58, 4, m.u32(setup + 0x94)); m.put(net + 0x5C, 4, m.u32(setup + 0x90))
    mode, rule = m.u32(setup + 0x34), m.u8(setup + 0x8D)
    for s in range(5):
        if not m.call(m.main + 0xE7E2A0, mode, rule, s) & 1:
            continue
        code = m.u8(setup + 0x99 + s)
        if code == 0xFF:
            continue
        with m.frame(0x10) as f:
            m.put(f, 1, code)
            station = m.call(m.main + 0x2015064, net, f)
            m.put(f + 8, 4, s)
            d = m.call(m.main + 0x18BE1C4, net + 0x60, f + 8)
        m.put(d + 0x18, 1, code)
        m.put(d, 8, (1 if m.u32(net + 0x58) == s else 0) | s << 32)
        m.put(d + 8, 8, 1); m.put(d + 0x10, 8, station)
    if m.u8(setup + 0x710):
        raise UnliftedCall("main+0x2a1cd74 with setup+0x710 (not a raid)")
    r = m.call(m.main + 0x1968860, net)
    if m.u8(net + 0xD0):
        return r
    mode, rule = m.u32(setup + 0x34), m.u8(m.u64(net + 0x50) + 0x8D)
    if mode == 2 and (rule == 0 or 3 <= rule <= 6):
        return r
    raise UnliftedCall("main+0x2a1cd74 outside a raid (0x168e4dc)")


# --- N+0x48 +0x138 when setup+0x499 bit 2: a 0x48-byte holder (vtable 0x4492e58) of a 0x1b0-byte
# battle-record object (vtable 0x4492fb8) --------------------------------------------------------------

@lifted(0x18D4DE4)
def construct_18d4de4(m, p, *_):
    """u32 0x0a0a0000, 0xffff000000000000 at +4, the 7-filled run +0xd..+0x2d, +0x30..+0x47 zero."""
    _stores(m, p, ((0, 4, 0x0A0A0000), (4, 8, 0xFFFF000000000000), (0x15, 8, 0x0007000007000007),
                   (0xD, 8, 0x0000070000070000), (0x25, 8, 0x0000070000070000), (0xC, 1, 0), (0x40, 8, 0),
                   (0x1D, 8, 0x0700000700000700), (0x2D, 1, 7), (0x30, 8, 0), (0x38, 8, 0)))


@lifted(0x18D4CEC)
def construct_18d4cec(m, o, *_):
    """+8..+0x178 zero, vtable 0x4492fb8 (+0x20 0x4493240), +0x120 by 0x18d4de4, u32 +0x170 1."""
    m.write(o + 8, bytes(0x171))
    m.put(o + 0x10, 8, 0); m.put(o + 0x18, 4, 0)
    m.put(o, 8, m.u64(m.main + 0x46D66F8) + 0x10)
    top = _top_f53840(m)
    m.put(o + 0x28, 4, 0)
    vt = m.u64(m.main + 0x46DCD48)
    m.put(o, 8, vt + 0x10); m.put(o + 8, 8, top); m.put(o + 0x20, 8, vt + 0x298)
    m.write(o + 0xD0, bytes(0x41))
    m.write(o + 0x48, bytes(0x48))
    m.call_void(m.main + 0x18D4DE4, o + 0x120)
    m.put(o + 0x170, 4, 1)
    m.put(o, 8, m.main + 0x4492FB8); m.put(o + 0x20, 8, m.main + 0x4493240)
    m.put(o + 0x179, 2, 0)
    _stores(m, o, ((0x19C, 8, 0), (0x1A1, 8, 0), (0x17C, 8, 0), (0x184, 8, 0), (0x18C, 8, 0), (0x194, 8, 0)))


@lifted(0x18D4BC4)
def create_18d4bc4(m, alloc, *_):
    return _make(m, alloc, 0x1B0, 0x18D4CEC)


lifted(0x18D4B58)(lambda m, holder, *_: release_counted_holder(m, holder))


@lifted(0x18D49BC)
def construct_18d49bc(m, o, *_):
    """vtable 0x4492e58 (+0x20 0x4492f10, +0x28 0x4492f60) holding a new 0x1b0-byte object at +0x40."""
    _weak_base(m, o)
    _vtables(m, o, 0x4492E58, 0xB8, 0x108)
    m.put(o + 0x40, 8, 0)
    p = m.call(m.main + 0x18D4BC4, m.u64(o + 8))
    if p:
        _inc(m, p)
    old = m.u64(o + 0x40)
    m.put(o + 0x40, 8, p)
    if old:
        _release_ref(m, old)


@lifted(0x18D4894)
def create_18d4894(m, alloc, *_):
    return _make(m, alloc, 0x48, 0x18D49BC)


lifted(0x18D47D0)(lambda m, alloc, *_: _make_strong(m, 0x18D4894, alloc))


@lifted(0x19F969C)
def static_46d3da8(m, *_):
    """The four-level static chain [0x46d3da8] (guard [0x46d3da0]); returns its slot's address."""
    from pokeldn.sv.battle.engine.statics import _static_chain
    _static_chain(m, ((0x46D3DA0, 0x46D3DA8), (0x46D3AA8, 0x46D3AB0), (0x46D39B0, 0x46D39B8),
                      (0x46D39C0, 0x46D39C8)))
    return m.u64(m.main + 0x46D3DA8)


@lifted(0x1268808)
def static_46dcd30(m, *_):
    """The static [0x46dcd30] (guard [0x46dcd28]) holding 0x19f969c's slot; returns its address."""
    guard = m.u64(m.main + 0x46DCD28)
    if m.u8(guard) & 1 == 0 and m.call(m.main + 0x343CF10, guard) & M32:
        m.put(m.u64(m.main + 0x46DCD30), 8, m.call(m.main + 0x19F969C))
        m.call_void(m.main + 0x343CF20, guard)
    return m.u64(m.main + 0x46DCD30)


lifted(0x2A1E620)(lambda m, *_: m.call(m.main + 0x1268808))


# --- N itself (0x1b0 bytes, vtable 0x44ff468) and its own objects ------------------------------------

def _create_aligned(m, alloc, size, align, build):
    """Create aligned to `align` (u32 +0x18 size | align << 16)."""
    stack = _tls_stack(m)
    _push(m, stack, alloc)
    o = m.vcall(alloc, 0x10, size, align)
    if not o:
        raise UnliftedCall("abort: allocation failed in Create")
    build(o)
    m.put(o + 0x18, 4, align << 16 | size)
    m.put(o + 8, 8, alloc); m.put(o + 0x10, 8, o)
    _pop(m, stack)
    return o


def _move_strong(m, dst, src):
    """dst = move(src) for strong references: the old *dst is released (its last reference ending in
    vf 0x50)."""
    old = m.u64(dst)
    m.put(dst, 8, 0)
    if old:
        _release_strong_value(m, old)
    m.put(dst, 8, m.u64(src)); m.put(src, 8, 0)
    return dst


def _release_strong_value(m, o):
    c = m.u64(o + 0x30)
    n = m.u16(c + 0x1A)
    if n == 0:
        raise UnliftedCall("abort: ReleaseReference")
    m.put(c + 0x1A, 2, n - 1)
    if n == 1:
        m.put(c + 0x10, 8, 0)
        return m.vcall(o, 0x50)
    return o


for _a in (0x16B14A4, 0x16B153C):
    lifted(_a)(lambda m, dst, src, *_: _move_strong(m, dst, src))
for _a in (0x16B138C, 0x16B1418):
    lifted(_a)(_move_ref)
for _a in (0x16AF4A4, 0x16B15D4, 0x16AFB74, 0x16AFC30):
    lifted(_a)(lambda m, dst, p, *_: _acquire_into(m, dst, p))
for _a in (0x16B1314, 0x16AF9D8, 0x16AFA50):
    lifted(_a)(lambda m, holder, *_: _release_strong(m, holder))


@lifted(0x16AF368)
def take_release_strong(m, holder, *_):
    """*holder released and cleared."""
    o = m.u64(holder)
    m.put(holder, 8, 0)
    return _release_strong_value(m, o) if o else 0


@lifted(0x16B1CC0)
def construct_16b1cc0(m, o, *_):
    """vtable 0x44ff540 (+0x20 0x44ff578), +0x30..+0x4f zero (N+0x128's object)."""
    top = _base(m, o)
    m.put(o + 0x28, 4, 0)
    m.put(o, 8, m.main + 0x44FF540); m.put(o + 8, 8, top); m.put(o + 0x20, 8, m.main + 0x44FF578)
    for off in (0x30, 0x38, 0x40, 0x48):
        m.put(o + off, 8, 0)


@lifted(0x16B1B88)
def create_16b1b88(m, alloc, *_):
    def build(o):
        m.write(o, bytes(0xB0))
        m.call_void(m.main + 0x16B1CC0, o)
    return _create_aligned(m, alloc, 0xB0, 0x10, build)


@lifted(0x16B2480)
def reset_owned_16b2480(m, holder, p, *_):
    """unique_ptr reset of {object, owner, size, align}: the old object destroyed and freed."""
    from pokeldn.sv.battle.engine.steps import _destroy
    old = m.u64(holder)
    m.put(holder, 8, p)
    if old:
        _destroy(m, old, m.u64(holder + 8), m.u64(holder + 0x10), m.u64(holder + 0x18))


RNG_STATE = (0x0F4B17A579F18960, 0x82A2B175229D6A5B)


@lifted(0x16B2308)
def construct_random_holder(m, o, *_):
    """N+0x1a0 (0x60 bytes, vtable 0x44ee2c8 (+0x20 0x44ee300)): a 0x28-byte xoroshiro128+ (vtable
    [0x46dcd38]+0x10, state 0x0f4b17a579f18960 / 0x82a2b175229d6a5b, seed and count 0) owned at
    +0x30 {object, owner, 0x28, 8}, u32 +0x58 zero."""
    m.put(o + 0x10, 8, 0); m.put(o + 0x18, 4, 0)
    m.put(o, 8, m.u64(m.main + 0x46D66F8) + 0x10)
    owner = _top_f53840(m)
    m.put(o + 0x28, 4, 0)
    m.put(o, 8, m.main + 0x44EE2C8); m.put(o + 8, 8, owner); m.put(o + 0x20, 8, m.main + 0x44EE300)
    m.put(o + 0x58, 4, 0)
    for off in (0x30, 0x38, 0x40, 0x48, 0x50):
        m.put(o + off, 8, 0)
    r = m.vcall(owner, 0x10, 0x28, 8)
    if not r:
        raise UnliftedCall("allocator out of memory")
    t = m.call(m.main + 0x343DA20, m.u32(m.call(m.main + 0xF53840)))
    _push(m, t, owner)
    m.put(r, 8, m.u64(m.main + 0x46DCD38) + 0x10); m.put(r + 8, 8, RNG_STATE[0])
    m.put(r + 0x10, 8, RNG_STATE[1]); m.put(r + 0x18, 8, 0); m.put(r + 0x20, 8, 0)
    _pop(m, t)
    m.call_void(m.main + 0x16B2480, o + 0x30, r)
    m.put(o + 0x38, 8, owner); m.put(o + 0x40, 8, 0x28); m.put(o + 0x48, 8, 8)


@lifted(0x16B1818)
def create_random_holder(m, alloc, *_):
    return _make(m, alloc, 0x60, 0x16B2308)


def _scope_owner_max(m, h, big):
    top = _tls_top(m)
    if not top:
        raise UnliftedCall("main+0xf60ed0")
    m.put(h + 0x18, 4, 0)
    m.put(h, 8, top); m.put(h + 8, 8, big); m.put(h + 0x10, 8, 0)


lifted(0x16B2000)(lambda m, h, *_: _scope_owner_max(m, h, 0x1FFFFFFFFFFFFFFF))


@lifted(0x16B1ED4)
def construct_16b1ed4(m, o, *_):
    """N+0x118 (0xb0 bytes, vtable 0x44ff5a8): two allocator holders at +0x58 and +0x90, the rest zero."""
    _weak_base(m, o)
    _vtables(m, o, 0x44FF5A8, 0x78, 0xC8)
    m.put(o + 0x50, 8, 0); m.put(o + 0x40, 8, 0); m.put(o + 0x48, 8, 0)
    m.call_void(m.main + 0x16B2000, o + 0x58)
    m.put(o + 0x80, 8, 0); m.put(o + 0x88, 8, 0); m.put(o + 0x78, 8, 0)
    return _tail(m, m.main + 0x16B2000, o + 0x90)


@lifted(0x16B1D9C)
def create_16b1d9c(m, alloc, *_):
    def build(o):
        m.write(o, bytes(0xB0))
        m.call_void(m.main + 0x16B1ED4, o)
    return _create(m, alloc, 0xB0, build)


@lifted(0x16B1A68)
def construct_16b1a68(m, o, *_):
    """N+0x120 (0x228 bytes, vtable 0x44ff878): u32 +0x40 zero, +0x48..+0x227 zero."""
    _weak_base(m, o)
    _vtables(m, o, 0x44FF878, 0x88, 0xD8)
    m.put(o + 0x40, 4, 0)
    m.write(o + 0x48, bytes(0x1E0))


@lifted(0x16B1940)
def create_16b1940(m, alloc, *_):
    return _make(m, alloc, 0x228, 0x16B1A68)


@lifted(0x16B21F0)
def construct_16b21f0(m, o, *_):
    """N+0x110 (0x58 bytes, vtable 0x44ff6c8): u32 +0x40 and +0x48..+0x57 zero."""
    _weak_base(m, o)
    _vtables(m, o, 0x44FF6C8, 0x78, 0xC8)
    m.put(o + 0x40, 4, 0); m.put(o + 0x48, 8, 0); m.put(o + 0x50, 8, 0)


@lifted(0x16B20B8)
def create_16b20b8(m, alloc, *_):
    def build(o):
        m.write(o, bytes(0x58))
        m.call_void(m.main + 0x16B21F0, o)
    return _create(m, alloc, 0x58, build)


for _a, _c in ((0x16B1690, 0x16B1D9C), (0x16B1754, 0x16B20B8)):
    lifted(_a)(lambda m, alloc, *_, c=_c: _make_strong(m, c, alloc))


@lifted(0x16B0FB8)
def construct_network(m, n, *_):
    """N: vtable 0x44ff468 (+0x20 0x44ff4a0), +0x30..+0x7c and +0xa8..+0x1af zero, u8 +0x88 1, +0x128
    0x16b1b88's object, +0x1a0 the random holder (0x16b1818), +0x118 0x16b1d9c's, +0x120 0x16b1940's,
    +0x110 0x16b20b8's."""
    top = _base(m, n)
    m.put(n + 0x28, 4, 0)
    m.put(n, 8, m.main + 0x44FF468); m.put(n + 8, 8, top)
    m.put(n + 0x20, 8, m.main + 0x44FF4A0); m.put(n + 0x80, 8, 0)
    m.write(n + 0x30, bytes(0x4D))
    m.put(n + 0x88, 1, 1)
    m.write(n + 0xA8, bytes(0x108))
    m.put(n + 0x8A, 8, 0); m.put(n + 0x92, 8, 0); m.put(n + 0x99, 8, 0)
    with m.frame(0x10) as t:
        p = m.call(m.main + 0x16B1B88, top)
        m.put(t + 8, 8, p)
        if p:
            _inc(m, p)
        m.call_void(m.main + 0x16B138C, n + 0x128, t + 8)
        release_counted_holder(m, t + 8)
        p = m.call(m.main + 0x16B1818, m.u64(n + 8))
        m.put(t + 8, 8, p)
        if p:
            _inc(m, p)
        m.call_void(m.main + 0x16B1418, n + 0x1A0, t + 8)
        release_counted_holder(m, t + 8)
        m.call_sret(m.main + 0x16B1690, t + 8, m.u64(n + 8))
        m.call_void(m.main + 0x16B14A4, n + 0x118, t + 8)
        _release_strong(m, t + 8)
        p = m.call(m.main + 0x16B1940, m.u64(n + 8))
        m.call_void(m.main + 0x16B15D4, t, p)
        m.put(t + 8, 8, m.u64(n + 0x120)); m.put(n + 0x120, 8, 0)
        m.call_void(m.main + 0x16B1314, t + 8)
        x = m.u64(t); m.put(t, 8, 0); m.put(n + 0x120, 8, x)
        m.call_void(m.main + 0x16B1314, t)
        m.call_sret(m.main + 0x16B1754, t + 8, m.u64(n + 8))
        m.call_void(m.main + 0x16B153C, n + 0x110, t + 8)
        _release_strong(m, t + 8)


# --- N+0xa8 (0xe8 bytes, vtable 0x44ee6e8) and its five members ---------------------------------------

@lifted(0x16B2850)
def delete_owned_16b2850(m, info, obj, *_):
    """Destroy and free obj through {owner, size, align} at info."""
    from pokeldn.sv.battle.engine.steps import _destroy
    _destroy(m, obj, m.u64(info), m.u64(info + 8), m.u64(info + 0x10))


@lifted(0x16B0D94)
def create_16b0d94(m, alloc, *_):
    """A 0x48-byte object (vtable 0x44ee828 (+0x20 0x44ee8a0, +0x28 0x44ee8f0), +0x40 zero) built inline."""
    def build(o):
        _stores(m, o, ((0x38, 8, 0), (0x40, 8, 0), (0x20, 8, 0), (0x28, 8, 0), (0x30, 8, 0)))
        _weak_base(m, o)
        _vtables(m, o, 0x44EE828, 0x78, 0xC8)
        m.put(o + 8, 8, alloc); m.put(o + 0x40, 8, 0)
    return _create(m, alloc, 0x48, build)


@lifted(0x16B0060)
def construct_16b0060(m, o, *_):
    """vtable 0x44eea68 (+0x20 0x44eeae0, +0x28 0x44eeb30), an empty container over the owner at +0x50
    (max 0x1fffffffffffffff)."""
    _weak_base(m, o)
    _vtables(m, o, 0x44EEA68, 0x78, 0xC8)
    owner = m.u64(o + 8)
    _stores(m, o, ((0x40, 8, 0), (0x48, 8, 0), (0x70, 4, 0), (0x50, 8, 0), (0x58, 8, owner),
                   (0x60, 8, 0x1FFFFFFFFFFFFFFF), (0x68, 8, 0)))


@lifted(0x16AFF38)
def create_16aff38(m, alloc, *_):
    return _make(m, alloc, 0x78, 0x16B0060)


@lifted(0x16B0188)
def create_16b0188(m, alloc, *_):
    return _make_z(m, alloc, 0x58, 0x16B02DC, 0x46E26A8, 0xA0, 0xF0)


@lifted(0x16B03F4)
def create_16b03f4(m, alloc, *_):
    return _make_z(m, alloc, 0xD0, 0x16B0548, 0x46E26B0, 0x90, 0xE0)


@lifted(0x16B0B2C)
def create_16b0b2c(m, alloc, *_):
    return _make_z(m, alloc, 0x50, 0x16B0C80, 0x46E26B8, 0x90, 0xE0)


for _a, _c in ((0x16AFCEC, 0x16B0188), (0x16AFDB0, 0x16B03F4), (0x16AFE74, 0x16B0B2C)):
    lifted(_a)(lambda m, alloc, *_, c=_c: _make_strong(m, c, alloc))


@lifted(0x16AFAD0)
def make_owned_random(m, alloc, *_):
    """*x8 = {a 0x28-byte object from alloc built by 0xfa98a4 with alloc on the thread's object stack,
    alloc, 0x28, 8}."""
    out = m.x8
    r = m.vcall(alloc, 0x10, 0x28, 8)
    if not r:
        raise UnliftedCall("main+0x16afad0 allocation failure")
    t = m.call(m.main + 0x343DA20, m.u32(m.call(m.main + 0xF53840)))
    _push(m, t, alloc)
    m.call_void(m.main + 0xFA98A4, r)
    m.put(out, 8, r); m.put(out + 8, 8, alloc); m.put(out + 0x10, 8, 0x28); m.put(out + 0x18, 8, 8)
    _pop(m, t)
    return out


@lifted(0x16AF688)
def construct_16af688(m, o, *_):
    """N+0xa8: vtable 0x44ee6e8 (+0x20 0x44ee760, +0x28 0x44ee7b0, +0x40 0x44ee808), +0x48..+0xdf zero,
    +0xe0 1; strong references at +0x98 (0x16b0d94), +0xa0 (0x16aff38), +0xb0 (0x16b0188), +0xb8
    (0x16b03f4), +0xa8 (0x16b0b2c); an owned 0x28-byte object at +0xc0 {object, owner, size, align}."""
    _weak_base(m, o)
    _vtables(m, o, 0x44EE6E8, 0x78, 0xC8)
    m.put(o + 0x40, 8, m.main + 0x44EE808)
    m.write(o + 0x48, bytes(0x98))
    m.put(o + 0xE0, 1, 1)
    with m.frame(0x30) as f:
        t, u = f + 8, f + 0x28                    # sp+8 and x29-8
        for create, wrap, slot in ((0x16B0D94, 0x16AFB74, 0x98), (0x16AFF38, 0x16AFC30, 0xA0)):
            p = m.call(m.main + create, m.u64(o + 8))
            m.call_void(m.main + wrap, u, p)
            m.put(t, 8, m.u64(o + slot)); m.put(o + slot, 8, 0)
            _release_strong(m, t)
            x = m.u64(u); m.put(u, 8, 0); m.put(o + slot, 8, x)
            _release_strong(m, u)
        for make, slot in ((0x16AFCEC, 0xB0), (0x16AFDB0, 0xB8), (0x16AFE74, 0xA8)):
            m.call_sret(m.main + make, t, m.u64(o + 8))
            old = m.u64(o + slot)
            m.put(o + slot, 8, 0)
            if old:
                _release_strong_value(m, old)
            m.put(o + slot, 8, m.u64(t))
        m.call_sret(m.main + 0x16AFAD0, t, m.u64(o + 8))
        x = m.u64(t); m.put(t, 8, 0)
        old = m.u64(o + 0xC0)
        m.put(o + 0xC0, 8, x)
        if old:
            m.call_void(m.main + 0x16B2850, o + 0xC8, old)
        m.put(o + 0xC8, 8, m.u64(t + 8)); m.put(o + 0xD0, 8, m.u64(t + 0x10)); m.put(o + 0xD8, 8, m.u64(t + 0x18))
        m.put(t, 8, 0)


@lifted(0x16AF560)
def create_16af560(m, alloc, *_):
    return _make(m, alloc, 0xE8, 0x16AF688)


@lifted(0x16AF204)
def construct_network_from(m, n, params, *_):
    """N from {setup, S+0xe8's object, N+0x48}: 0x16b0fb8, then counted references to the three at
    +0x38, +0x40 and +0x48, and N+0xa8 (0x16af560) held strongly."""
    m.call_void(m.main + 0x16B0FB8, n)
    for i, off in enumerate((0x38, 0x40)):
        p = m.u64(params + 8 * i)
        if p:
            _inc(m, p)
        old = m.u64(n + off)
        m.put(n + off, 8, p)
        if old:
            _release_ref(m, old)
    m.call_void(m.main + 0x16AF3E8, n + 0x48, m.u64(params + 0x10))
    p = m.call(m.main + 0x16AF560, m.u64(n + 8))
    with m.frame(0x10) as t:
        m.call_void(m.main + 0x16AF4A4, t, p)
        m.call_void(m.main + 0x16AF368, n + 0xA8)
        m.put(n + 0xA8, 8, m.u64(t))


@lifted(0x16AF0D4)
def create_network(m, alloc, params, *_):
    return _create(m, alloc, 0x1B0, lambda o: m.call_void(m.main + 0x16AF204, o, params))


@lifted(0x16AF068)
def make_network(m, alloc, params, *_):
    """*x8 = a new N holding one reference."""
    out = m.x8
    p = m.call(m.main + 0x16AF0D4, alloc, params)
    m.put(out, 8, p)
    if p:
        _inc(m, p)
    return p


# --- the session handler 0x18915c4: N+0x48, its members, the election object and N -------------------

def _acquire_temp(m, p):
    """AddReference on p's control block (a temporary strong reference); the first one resolves vf 0."""
    c = m.u64(p + 0x30)
    if m.u64(c + 0x10) == 0:
        raise UnliftedCall("abort: AddReference m_object")
    n = m.u16(c + 0x1A)
    if n == 0xFFFF:
        raise UnliftedCall("abort: AddReference overflow")
    m.put(c + 0x1A, 2, n + 1)
    if n == 0:
        obj = m.u64(c + 0x10)
        m.put(c + 8, 8, m.vcall(obj, 0))
        m.put(c + 0x1C, 4, 0xFFFFFFFE)


def _assign_through(m, slot, p, assign):
    """assign(slot, p) with p held by a temporary strong reference (0x18915c4's pattern); a null p
    clears the slot through the same call (or, for the plain holders, a release)."""
    if p:
        _acquire_temp(m, p)
        m.call_void(m.main + assign, slot, p)
        _release_strong_value(m, p)
    else:
        m.call_void(m.main + assign, slot, 0)


def _clear_strong(m, slot):
    old = m.u64(slot)
    m.put(slot, 8, 0)
    if old:
        _release_strong_value(m, old)


def _replace_strong(m, holder, value):
    """holder = value (already one strong reference), the old value released."""
    _clear_strong(m, holder)
    m.put(holder, 8, value)


def _setup_resource(m, setup, name):
    """0x1ffbb68: setup+0x720 = a resource handle for `name` from the resource system (0xbf9884,
    [0x46d4248]). The resource system is not reproduced; the battle never reads setup+0x720."""
    from pokeldn.sv.battle.machine import FUNCTIONS
    if 0x1FFBB68 in FUNCTIONS:
        m.call_void(m.main + 0x1FFBB68, setup, name)


@lifted(0x18915C4)
def start_session(m, s, mgr_ref, opt, *_):
    """The session handler: S+0xf0 = a new N+0x48; five counted resources of each kind (0x3e8 bytes at
    S+0x58.., 0xb70 bytes at S+0x80..) into N+0x48's maps under keys 0..4; for a raid setup (+0x710
    clear) N+0x48 +0x110 (0x1772c9c), +0x148 the named-parameter table (0x1464578, also S+0xb8), +0x140
    0x15592f0's object; with mode 2 (setup+0x34) +0x118/+0x120/+0x128 from 0x1849bf8, 0x17e1b98,
    0x1849e10 (also S+0xc8, +0xd0, +0xd8); with setup+0x8c the election object at +0x108 (0x2a1cd74);
    with setup+0x499 bit 2 0x18d47d0's object at +0x138; then N (0x16af068 from {setup, S+0xe8,
    N+0x48}) into S+0x48, S+0x100 = 1 and S+0x108 = setup+0x90."""
    alloc = m.u64(s + 8)
    with m.frame(0x80) as f:
        sp10, xm40, xm20, xm10, xm8, sp30 = f, f + 0x10, f + 0x28, f + 0x30, f + 0x38, f + 0x40
        m.call_sret(m.main + 0x1746B3C, sp10, alloc)
        m.call_void(m.main + 0x2A0F670, s + 0xF0, sp10)
        release_counted_holder(m, sp10)
        for i in range(5):
            r = _create_resource_3e8(m, alloc)
            _inc(m, r)
            slot = s + 0x58 + 8 * i
            old = m.u64(slot); m.put(slot, 8, 0)
            if old:
                _release_ref(m, old)
            m.put(slot, 8, r)
            r = m.call(m.main + 0x1668C1C, alloc)
            if r:
                _inc(m, r)
            slot2 = s + 0x80 + 8 * i
            old = m.u64(slot2); m.put(slot2, 8, 0)
            if old:
                _release_ref(m, old)
            m.put(slot2, 8, r)
            for src, tmp, setter in ((slot, xm8, 0x16550A4), (slot2, xm10, 0x16558A4)):
                n48 = m.u64(s + 0xF0)
                v = m.u64(src)
                m.put(tmp, 8, v)
                if v:
                    _inc(m, v)
                m.call_void(m.main + setter, n48, i, tmp)
                if v:
                    _release_ref(m, v)
        setup = m.u64(s + 0xE0)
        if m.u8(setup + 0x710):
            raise UnliftedCall("main+0x18915c4 with setup+0x710 (not a raid)")
        x = m.call(m.main + 0x1772C9C, alloc)
        m.put(xm40, 8, x)
        if x:
            _inc(m, x)
        m.put(sp10, 8, m.u64(s + 0xC0)); m.put(s + 0xC0, 8, 0)
        m.call_void(m.main + 0x1838590, sp10)
        m.put(xm40, 8, 0); m.put(s + 0xC0, 8, x)
        m.call_void(m.main + 0x1838590, xm40)
        n48 = m.u64(s + 0xF0)
        m.call_void(m.main + 0x2A0F75C, xm20, s + 0xC0)
        v = m.u64(xm20)
        m.call_void(m.main + 0x16F6B18, n48 + 0x110, v)
        if v:
            _release_ref(m, v)
        p = m.call(m.main + 0x1464578, alloc)
        m.call_void(m.main + 0x2A10010, xm40, p)
        m.put(sp10, 8, m.u64(s + 0xB8)); m.put(s + 0xB8, 8, 0)
        m.call_void(m.main + 0x18385FC, sp10)
        x = m.u64(xm40); m.put(xm40, 8, 0); m.put(s + 0xB8, 8, x)
        m.call_void(m.main + 0x18385FC, xm40)
        _assign_through(m, m.u64(s + 0xF0) + 0x148, m.u64(s + 0xB8), 0x2A0F8A4)
        p = m.call(m.main + 0x15592F0, alloc)
        if p:
            _inc(m, p); _inc(m, p)
            m.call_void(m.main + 0x16F6BD4, m.u64(s + 0xF0) + 0x140, p)
            _release_ref(m, p); _release_ref(m, p)
        else:
            m.call_void(m.main + 0x16F6BD4, m.u64(s + 0xF0) + 0x140, 0)
        if m.u32(setup + 0x34) == 2:
            for make, holder in ((0x1849BF8, 0xC8), (0x17E1B98, 0xD0), (0x1849E10, 0xD8)):
                m.call_sret(m.main + make, sp10, alloc)
                _replace_strong(m, s + holder, m.u64(sp10))
            for holder, slot, assign in ((0xD0, 0x120, 0xFA4800), (0xC8, 0x118, 0xFA4A78), (0xD8, 0x128, 0xFA493C)):
                n48 = m.u64(s + 0xF0)
                p = m.u64(s + holder)
                if p:
                    _assign_through(m, n48 + slot, p, assign)
                else:
                    _clear_strong(m, n48 + slot)
        flags = m.u64(setup + 0x498)
        if flags >> 11 & 1:
            raise UnliftedCall("main+0x19784d8: setup+0x498 bit 11")
        if flags >> 12 & 1:
            m.put(setup + 0x1B0, 2, m.u16(setup + 0x1B0) | 2)
        p = m.u64(s + 0xF8)
        if p:
            _assign_through(m, m.u64(s + 0xF0) + 0x138, p, 0x16F6DCC)
        m.put(xm40 + 8, 8, 0); m.put(xm40 + 0x10, 8, 0); m.put(xm40, 8, 0)
        m.call_void(m.main + 0x1722538, xm40, setup)
        m.call_void(m.main + 0x17225F4, xm40 + 8, m.u64(s + 0xE8))
        m.call_void(m.main + 0x16AF3E8, xm40 + 0x10, m.u64(s + 0xF0))
        if m.u8(setup + 0x8C):
            n48 = m.u64(s + 0xF0)
            p = m.u64(mgr_ref)
            if p:
                _assign_through(m, n48 + 0x100, p, 0x16A01CC)
            else:
                _clear_strong(m, n48 + 0x100)
            m.call_sret(m.main + 0x18D9524, sp10, m.u64(s + 8))
            e = m.u64(sp10)
            m.call_void(m.main + 0x1891340, sp30, opt)
            m.call_void(m.main + 0x2A1CD74, e, setup, sp30)
            if m.u8(sp30):
                raise UnliftedCall("main+0xc8e444: an optional session handle")
            n48 = m.u64(s + 0xF0)
            if e:
                _assign_through(m, n48 + 0x108, e, 0x16F6C90)
                _release_strong(m, sp10)
            else:
                m.call_void(m.main + 0x16F6C90, n48 + 0x108, 0)
            if m.u8(setup + 0x499) >> 2 & 1:
                m.call_sret(m.main + 0x18D47D0, sp10, alloc)
                t = m.u64(sp10)
                _assign_through(m, m.u64(s + 0xF0) + 0x138, t, 0x16F6DCC)
                _release_strong(m, sp10)
        flags = m.u64(setup + 0x498)
        if flags >> 10 & 1:
            with m.frame(0x20) as name:
                m.put(name, 8, 0xB6629F6E8797836C); m.put(name + 8, 8, m.main + 0x3B51048)   # "avalon/data/"
                m.put(name + 0x10, 8, 0xC); m.put(name + 0x18, 8, 0)
                _setup_resource(m, setup, name)
        elif not flags >> 25 & 1 and (m.u16(setup + 0x48A) or m.u16(setup + 0x48C) or m.u16(setup + 0x48E)):
            raise UnliftedCall("main+0x1ffb950: the time-limit object outside a raid")
        if not m.u8(setup + 0x499) >> 2 & 1:
            m.put(setup + 0x490, 2, 0)
        m.call_sret(m.main + 0x16AF068, sp10, alloc, xm40)
        m.call_void(m.main + 0x2A0F7BC, s + 0x48, sp10)
        release_counted_holder(m, sp10)
        m.put(s + 0x100, 8, 1)
        m.put(s + 0x108, 4, m.u32(setup + 0x90))
        for off in (0x10, 8, 0):
            release_counted_holder(m, xm40 + off)


lifted(0x16A01CC)(lambda m, holder, p, *_: _assign_strong(m, holder, p, "old"))


# --- N's state 0 (0x1269824 case 0) and the step machine ----------------------------------------------

lifted(0x2D37B54)(lambda m, dst, src, *_: _move_strong(m, dst, src))
for _a in (0x2D37BEC, 0x2D37C78, 0x1730C78):
    lifted(_a)(_move_ref)


@lifted(0x1730C18)
def copy_n48_110(m, n48, *_):
    """*x8 = [n48+0x110] with a reference taken."""
    p = m.u64(n48 + 0x110)
    m.put(m.x8, 8, p)
    if p:
        _inc(m, p)
    return p


@lifted(0x1730AC8)
def hold_n48_110(m, n, *_):
    """N+0x130 = [N+0x48]+0x110 (a counted reference)."""
    with m.frame(0x10) as t:
        m.call_sret(m.main + 0x1730C18, t, m.u64(n + 0x48))
        release_counted_holder(m, t)
        m.call_sret(m.main + 0x1730C18, t, m.u64(n + 0x48))
        m.call_void(m.main + 0x1730C78, n + 0x130, t)
        release_counted_holder(m, t)


@lifted(0x281C260)
def seed_random_holder(m, rh, seed_ref, *_):
    """The random holder: +0x50 the seed, its xoroshiro128+ (+0x30) seeded (0xfa9ba8), u32 +0x58 a first
    draw below 100 (0x11440f0)."""
    seed = m.u64(seed_ref)
    m.put(rh + 0x50, 8, seed)
    m.call_void(m.main + 0xFA9BA8, m.u64(rh + 0x30), seed)
    m.put(rh + 0x58, 4, m.call(m.main + 0x11440F0, m.u64(rh + 0x30), 100))


@lifted(0x2A1D9B8)
def election_waiting(m, net, *_):
    """Election vf 0x88: whether a slot node 0..4 is present with a state (+0x20) other than 1."""
    for s in range(5):
        node = _find(m, net + 0x60, s, 4)
        if node and m.u32(node + 0x20) != 1:
            return 1
    return 0


@lifted(0x132F45C)
def assign_strong_132f45c(m, holder, p, *_):
    return _assign_strong(m, holder, p, "old")


@lifted(0x132EEF4)
def make_command_pair(m, o, i, j, *_):
    """For slot i and index j: a 0x60-byte part A ([0x46e2f78]'s vtables, 0x132f6e8) and a 0x58-byte part
    B ([0x46e2f80]'s, 0x132f598) keyed {[o+0x40], i, j}; A+0x58 holds B, o+0x48+0x28i+8j holds A and
    o+0x138+0x28i+8j holds B (strong references)."""
    i &= M32; j &= M32
    alloc = m.u64(o + 8)
    with m.frame(0x10) as key:
        m.put(key, 4, m.u32(o + 0x40)); m.put(key + 4, 4, i); m.put(key + 8, 4, j)

        def build_a(a):
            m.call_void(m.main + 0x132F6E8, a, key)
            vt = m.u64(m.main + 0x46E2F78)
            m.put(a, 8, vt + 0x10); m.put(a + 0x20, 8, vt + 0x90); m.put(a + 0x28, 8, vt + 0xE0)
            m.put(a + 0x58, 8, 0)
        a = _create(m, alloc, 0x60, build_a)
        _acquire_temp(m, a)
        b = _make_z_from(m, m.u64(o + 8), 0x58, lambda x: m.call_void(m.main + 0x132F598, x, key), 0x46E2F80)
        _acquire_temp(m, b)
        _acquire_temp(m, b)
        m.call_void(m.main + 0x132F45C, a + 0x58, b)
        _release_strong_value(m, b)
        _acquire_temp(m, a)
        slot = o + 0x48 + 0x28 * i + 8 * j
        old = m.u64(slot)
        m.put(slot, 8, a)
        if old:
            _release_strong_value(m, old)
        m.call_void(m.main + 0x132F45C, o + 0x138 + 0x28 * i + 8 * j, b)
        _release_strong_value(m, b)
        _release_strong_value(m, a)


def _make_z_from(m, alloc, size, ctor, got):
    """Create without zeroing: the constructor, then vtables [got]+0x10 (+0x20 its +0x90, +0x28 its +0xe0)."""
    def build(o):
        ctor(o)
        vt = m.u64(m.main + got)
        m.put(o + 0x10, 8, o)
        m.put(o + 0x20, 8, vt + 0x90); m.put(o + 0x28, 8, vt + 0xE0)
        m.put(o, 8, vt + 0x10)
    return _create(m, alloc, size, build)


@lifted(0x132ECFC)
def make_command_pairs(m, o, *_):
    """The 6 x 5 command pairs (0x132eef4) of N+0x120."""
    for i in range(6):
        for j in range(5):
            m.call_void(m.main + 0x132EEF4, o, i, j)


@lifted(0x16A0190)
def set_battle_field(m, o, info, *_):
    """o+0x40 = u32 info, o+0x48 and o+0x50 strong references to info's +8 and +0x10."""
    m.put(o + 0x40, 4, m.u32(info))
    m.call_void(m.main + 0x16A01CC, o + 0x48, m.u64(info + 8))
    return _tail(m, m.main + 0x16A01CC, o + 0x50, m.u64(info + 0x10))


@lifted(0x169FFA0)
def set_n110(m, n, *_):
    """[N+0x110] gets {setup+0x2c, N+0x120, [N+0x48]+0x100} (0x16a0190)."""
    with m.frame(0x20) as info:
        m.put(info + 8, 8, 0); m.put(info + 0x10, 8, 0)
        m.put(info, 4, m.u32(m.u64(n + 0x38) + 0x2C))
        m.call_void(m.main + 0x16A01CC, info + 8, m.u64(n + 0x120))
        p = m.u64(m.u64(n + 0x48) + 0x100)
        if p:
            _acquire_temp(m, p)
        _clear_strong(m, info + 0x10)
        m.put(info + 0x10, 8, p)
        m.call_void(m.main + 0x16A0190, m.u64(n + 0x110), info)
        _clear_strong(m, info + 0x10)
        _clear_strong(m, info + 8)


def _battle_loader(m, n, setup):
    """0x1802edc: N+0x1a8 = the loader of the battle's field and model files (0x220 bytes, ctor
    0x180301c), whose file requests go to the resource system (0x1929dc4) and whose completion state 1
    (0x18389d0) waits for. The resource system is not reproduced: no loader is made; no battle code
    reads N+0x1a8."""
    return None


@lifted(0x1269824)
def network_state(m, n, state_ref, *_):
    """N's start states: 0 (the bootstrap: N's limits, the election object at +0x138, +0x190, the server
    build 0x2891748, the random holder seeded, N+0x30 the battle seed, the command pairs, [N+0x110]'s
    battle field, the loader), 1 (the loader's files, not reproduced), 2 (the step machine at +0x50 by
    mode, 0x2d37d04), 3 (the step machine 0x126a15c). Returns 1 when done."""
    state = m.u32(state_ref)
    if state == 0:
        setup = m.u64(n + 0x38)
        for off in (0x8A, 0x8C, 0x8E):
            m.put(n + off, 2, m.u16(setup + 0x400 + off))
        with m.frame(0x10) as t:
            e = m.u64(m.u64(n + 0x48) + 0x108)
            m.put(t, 8, e)
            if e:
                _acquire_temp(m, e)
            m.call_void(m.main + 0x2D37B54, n + 0x138, t)
            _release_strong(m, t)
            p = m.u64(m.u64(n + 0x48) + 0x140)
            m.put(t, 8, p)
            if p:
                _inc(m, p)
            m.call_void(m.main + 0x2D37BEC, n + 0x190, t)
            release_counted_holder(m, t)
        m.put(n + 0x9E, 1, m.u8(n + 0x9E) & 0xE4)
        m.put(n + 0x98, 1, 0); m.put(n + 0x90, 4, 7); m.put(n + 0x94, 1, 0)
        m.call_void(m.main + 0x1730AC8, n)
        m.call_void(m.main + 0x2891748, n, m.u64(n + 8))
        setup = m.u64(n + 0x38)
        with m.frame(0x10) as t:
            m.put(t, 8, m.u64(setup + 0x718))
            m.call_void(m.main + 0x281C260, m.u64(n + 0x1A0), t)
        setup = m.u64(n + 0x38)
        m.put(n + 0x88, 1, 2 if m.u8(setup + 0x8C) else m.u8(setup + 0x4A5))
        m.put(n + 0x9E, 1, m.u8(n + 0x9E) | 4)
        m.put(n + 0x50, 8, 0); m.put(n + 0x58, 8, 0)
        m.put(n + 0x78, 4, 0); m.put(n + 0x7C, 1, 0)
        m.put(n + 0x30, 8, m.u64(setup + 0x718))
        m.put(n + 0x80, 4, m.u32(setup + 0x4AC)); m.put(n + 0x84, 4, 0)
        if m.u8(setup + 0x8C) and m.u64(n + 0x138):
            e = m.u64(n + 0x138)
            _acquire_temp(m, e); _acquire_temp(m, e)
            waiting = m.vcall(e, 0x88)
            _release_strong_value(m, e); _release_strong_value(m, e)
            if waiting & 1:
                e = m.u64(n + 0x138)
                _acquire_temp(m, e)
                m.vcall_void(e, 0x70)
                _release_strong_value(m, e)
            e = m.u64(n + 0x138)
            if e:
                _acquire_temp(m, e); _acquire_temp(m, e)
                lost = m.vcall(e, 0x68)
                _release_strong_value(m, e); _release_strong_value(m, e)
                if lost & 1:
                    m.put(n + 0x9E, 1, m.u8(n + 0x9E) | 3)
        m.put(m.u64(n + 0x120) + 0x40, 4, m.u32(m.u64(n + 0x38) + 0x2C))
        m.call_void(m.main + 0x132ECFC, m.u64(n + 0x120))
        m.call_void(m.main + 0x169FFA0, n)
        setup = m.u64(n + 0x38)
        m.put(n + 0x96, 1, 0)
        m.put(n + 0x96, 1, m.u32(setup + 0x498) >> 26 & 1)
        _battle_loader(m, n, setup)
        m.put(state_ref, 4, state + 1)
        return 0
    if state == 1:
        if m.u64(n + 0x1A8):
            raise UnliftedCall("main+0x18389d0: the loader's files")
        m.put(state_ref, 4, state + 1)               # no loader (_battle_loader): nothing to wait for
        return 0
    if state == 2:
        setup = m.u64(n + 0x38)
        e = m.u64(n + 0x138)
        if m.u8(setup + 0x8C) and e:
            _acquire_temp(m, e); _acquire_temp(m, e)
            lost = m.vcall(e, 0x68)
            _release_strong_value(m, e); _release_strong_value(m, e)
            if lost & 1:
                m.put(n + 0x9E, 1, m.u8(n + 0x9E) | 3)
        m.call_void(m.main + 0x2D37D04, n)
        m.put(n + 0x60, 4, 0)
        m.put(state_ref, 4, state + 1)
        return 0
    if state == 3:
        if not m.call(m.main + 0x126A15C, n) & 1:
            return 0
        if m.u8(n + 0x9E) & 1:
            m.put(n + 0x9E, 1, m.u8(n + 0x9E) | 2)
            return 1
        raise UnliftedCall("main+0x2d37d94: after the step machine")
    return 0


@lifted(0x2D37D04)
def choose_step_machine(m, n, *_):
    """N+0x50 = the step machine for the setup's mode (+0x34) and +0x8c/+0x8d: 0x2d380a4 for a raid (mode
    2 with +0x8c), N+0x58 0, u32 N+0x60 0."""
    setup = m.u64(n + 0x38)
    mode, mp = m.u32(setup + 0x34), m.u8(setup + 0x8C)
    if mp:
        fn = {2: 0x2D380A4, 1: 0x2D37FFC, 0: 0x2D37F6C}.get(mode, 0xF9FC94)
    elif mode == 1:
        fn = 0x2D37EE8 if m.u8(setup + 0x8D) else 0x28922F0
    else:
        fn = 0xF9FC94
    m.put(n + 0x50, 8, m.main + fn); m.put(n + 0x58, 8, 0)
    m.put(n + 0x60, 4, 0)


@lifted(0x126A15C)
def run_step_machine(m, n, *_):
    """The member function at N+0x50 (adjustment N+0x58) on (N, N+0x60); 1 when there is none."""
    fn, adj = m.u64(n + 0x50), m.u64(n + 0x58)
    if fn == 0 and (adj == 0 or adj & 1 == 0):
        return 1
    this = n + (adj >> 1)
    if adj & 1:
        fn = m.u64(m.u64(this) + fn)
    return m.call(fn, this, n + 0x60)


STEPS = 0x44FF4F0                   # {step, this adjustment} per state, from state 1


@lifted(0x2D380A4)
def raid_steps(m, n, state_ref, *_):
    """The raid's step machine: state 0 sets the battle format bytes N+0x98.. by the rule (setup+0x8d),
    N+0x95 = this console's slot; states 1..3 run the steps 0x2892ac0, 0x2d381a4, 0x2892dd4 (N, N+0x64)
    until each returns 1. Returns 1 past state 3."""
    state = m.s(state_ref, 4)
    if state == 0:
        setup = m.u64(n + 0x38)
        rule = m.u8(setup + 0x8D)
        if rule <= 3:
            m.put(n + 0x98, 2, 0x101)
        elif rule == 4:
            m.put(n + 0x98, 4, 0x03040104); m.put(n + 0x9C, 1, 2)
        elif rule == 5:
            m.put(n + 0x98, 4, 0x03040103)
        elif rule == 6:
            m.put(n + 0x98, 2, 0x102); m.put(n + 0x9A, 1, 4)
        m.put(n + 0x64, 4, 0)
        m.put(n + 0x95, 1, m.u32(setup + 0x90))
        m.put(state_ref, 4, m.u32(state_ref) + 1)
        return 0
    if not 0 < state <= 3:
        return 1
    fn = m.u64(m.main + STEPS + 0x10 * state)
    adj = m.u64(m.main + STEPS + 0x10 * state + 8)
    if not m.call(fn, n + (adj >> 1), n + 0x64) & 1:
        return 0
    m.put(n + 0x64, 4, 0)
    m.put(state_ref, 4, m.u32(state_ref) + 1)
    return 0
