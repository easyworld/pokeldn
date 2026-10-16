"""What a battle session holds before the build steps run, made on an arena (`arena.new`): the data
tables in their function-local statics, the weak-handle table, the battle session manager (made at
boot, 0x168ca58), the session S under it (0x159dba0 -> ctor 0x159e860) with its battle setup (0x730
bytes, vtable 0x44ff070) and the session start that makes N (`network`) (docs/sv_raid.md, Reproducing
a round).

The table creators are the game's (personal 0x164498c, id-hash 0x1730f6c); the files they load come
from the romfs as bytes (`files`), laid into the maps as the loaders leave them: each map reserved to
its record count, then filled in file order, the default record the one for key 0. The weak-handle
table is the game's (0x165dd08) with its growth paths (0xc1adec, 0xc1aa80, 0xb44724). The raid start's
setup fields, which the game writes from Lua through the setup's bindings, come from the bootstrap and
RAID_SETUP (`raid_setup`); `build_session` makes the rest with the game's own code.
"""

import struct

from pokeldn.sv.battle.engine.steps import _create, _insert, _pop, _push, _rehash, _tls_stack, _tls_top
from pokeldn.sv.battle.machine import MASK, UnliftedCall, lifted

M64 = MASK[8]
ONE_F = 0x3F800000
MAX_NODES = 0x0FFFFFFFFFFFFFFF          # the map allocators' max_size

APPLICATION_NAME = 0x3B78D3D            # "Application"
APPLICATION_LIMIT = 0xA0000000

# name, static slot, GOT word of the slot, guard GOT word, file, key rule
TABLES = (
    ("personal", 0x47420B8, 0x46D7438, 0x46D7430, "avalon/data/personal_array.bin", "pair"),
    ("growth", 0x47420D8, 0x46DA7C8, 0x46DA7C0, "avalon/data/growTable.bin", None),
    ("moves", 0x4742568, 0x46D7948, 0x46D7940, "avalon/data/waza_array.bin", "u16"),
    ("abilities", 0x4742548, 0x46DDAB0, 0x46DDAA8, "avalon/data/tokusei_array.bin", "u16"),
)
IDHASH = ("idhash", 0x4734E50, 0x46D8908, 0x46D8900,
          "world/data/battle/battle_item_conversion/battle_item_conversion_array.bin")
IDHASH_HASHES = 0x3C61260               # 282 u64 name hashes, main .rodata [0x1821674]
IDHASH_ENTRIES = 282

# Objects the loaders make, as a snapshot holds them: vtable, the second vtable at +0x20, the word at
# +0x28, object size.
LAYOUT = {
    "growth": (0x44A8FA0, 0x44A8FD0, 0x4440090, 0x68),
    "moves": (0x44A9678, 0x44A96A8, 0x44A9658, 0xE0),
    "abilities": (0x44A9598, 0x44A95C8, 0x44A9578, 0xE0),
}
RESOURCE_VT = 0x4440368                 # the file resource [T+0x30]; vf 0x70 (0x92e438) returns +0x1f0
RESOURCE_SIZE = 0x210
FILES = 0x3000000000                    # where the loaded files sit: outside the game heap, never freed


def _fnv1a64(data):
    """FNV-1a 64 as the romfs names files."""
    h = 0xCBF29CE484222645           # the basis the game uses (tools/switch/trpfs_read.py)
    for c in data:
        h = ((h ^ c) * 0x100000001B3) & M64
    return h


# --- allocators -----------------------------------------------------------------------------------

@lifted(0x2A64D40)
def counted_type_node(m, *_):
    """The counted allocator's type node (its parent: 0x11e29ac's), built on first use."""
    from pokeldn.sv.battle.engine.arena import _node, type_node_allocator
    return _node(m, 0x46DD938, 0x46DD940, lambda: type_node_allocator(m))


@lifted(0x2A6487C)
def counted_sizes_kept(m, o, *_):
    """Whether a counted allocator keeps counts by size class: u8 +0x50."""
    return m.u8(o + 0x50)


def application_allocator(m):
    """The counted allocator "Application" (limit 0xa0000000) over the GlobalHeap counted allocator
    main+0x4763918: the allocator at N+8, of every data table and of the main modules."""
    inner = m.main + 0x4763918
    a = m.vcall(inner, 0x10, 0x58, 8)
    with m.frame(0x10) as f:
        m.put(f, 8, APPLICATION_LIMIT); m.put(f + 8, 8, inner)
        m.call_void(m.main + 0x13ECA54, a, f, f + 8)
    m.vcall_void(a, 0xE0, m.main + APPLICATION_NAME)
    return a


# --- the personal table's creator ---------------------------------------------------------------

@lifted(0x1644B38)
def table_base_1644b38(m, o, *_):
    """Base constructor of the personal table: vtable 0x44a8df0 (+0x20 its +0x30), +8 the top of the
    thread's object stack, +0x10 / u32 +0x18 zero; the class static [0x46d7438] gets byte +8 = 1."""
    m.put(o, 8, m.u64(m.main + 0x46D66F8) + 0x10)
    m.put(o + 0x10, 8, 0); m.put(o + 0x18, 4, 0)
    top = _tls_top(m)
    m.put(o, 8, m.main + 0x44A8DF0); m.put(o + 8, 8, top)
    m.put(o + 0x20, 8, m.main + 0x44A8E20)
    _static_guard(m, 0x46D7430)
    m.put(m.u64(m.main + 0x46D7438) + 8, 1, 1)


@lifted(0x1644AB4)
def construct_personal(m, o, *_):
    """The personal table: vtables [0x46dda68] + 0x10 / + 0x40, +0x28 0x44a8e40, an empty map at +0x68
    over the allocator +8 (max load 1.0), no default record, +0xd8 not loaded."""
    m.call_void(m.main + 0x1644B38, o)
    vt = m.u64(m.main + 0x46DDA68)
    _empty_table(m, o, vt + 0x10, vt + 0x40, m.main + 0x44A8E40)


@lifted(0x164498C)
def create_personal(m, alloc, *_):
    """Create the 0xe0-byte personal table from alloc (0x1644ab4)."""
    return _create(m, alloc, 0xE0, lambda o: m.call_void(m.main + 0x1644AB4, o))


def _static_guard(m, guard_got):
    """A function-local static's guard (its address in the GOT word): acquired and released when unset;
    the __cxa_atexit registration between them is not reproduced."""
    g = m.u64(m.main + guard_got)
    if m.u8(g) & 1 == 0 and m.call(m.main + 0x343CF10, g) & 1:
        m.call_void(m.main + 0x343CF20, g)


def _empty_table(m, o, vt, vt20, w28):
    for off in (0x30, 0x38, 0x40, 0x48, 0x50, 0x58, 0x60, 0x68, 0x70, 0x88, 0x98, 0xB0, 0xC0, 0xD0):
        m.put(o + off, 8, 0)
    m.put(o + 0x90, 4, 0); m.put(o + 0xB8, 4, 0); m.put(o + 0xD8, 1, 0)
    m.put(o, 8, vt); m.put(o + 0x20, 8, vt20); m.put(o + 0x28, 8, w28)
    alloc = m.u64(o + 8)
    m.put(o + 0x78, 8, alloc); m.put(o + 0x80, 8, MAX_NODES)
    m.put(o + 0xA0, 8, alloc); m.put(o + 0xA8, 8, MAX_NODES)
    m.put(o + 0xC8, 4, ONE_F)


# --- the id-hash table's creator -----------------------------------------------------------------

@lifted(0x1731190)
def idhash_base_1731190(m, o, *_):
    """Base constructor of the id-hash table: vtable 0x4492008 (+0x20 its +0x30), +8 the top of the
    thread's object stack; the class static [0x46d8908] gets byte +8 = 1."""
    m.put(o + 0x10, 8, 0); m.put(o + 0x18, 4, 0)
    m.put(o, 8, m.u64(m.main + 0x46D66F8) + 0x10)
    top = _tls_top(m)
    m.put(o, 8, m.main + 0x4492008); m.put(o + 8, 8, top)
    m.put(o + 0x20, 8, m.main + 0x4492038)
    _static_guard(m, 0x46D8900)
    m.put(m.u64(m.main + 0x46D8908) + 8, 1, 1)


@lifted(0x1731094)
def construct_idhash(m, o, *_):
    """The id-hash table: vtable 0x4491fb8 (+0x20 its +0x30), 282 zeroed 0x18-byte entries from +0x28
    (u32 index, u64 hash +8, u16 id +0x10), four resource handles at +0x1a98, +0x1ad8, +0x1b30 and
    +0x1b70 (each [0x46d8e88] + 0x10 and seven zero words)."""
    m.call_void(m.main + 0x1731190, o)
    m.put(o, 8, m.main + 0x4491FB8); m.put(o + 0x20, 8, m.main + 0x4491FE8)
    e = o + 0x28
    while e != o + 0x1A98:
        m.put(e, 4, 0); m.put(e + 8, 8, 0); m.put(e + 0x10, 2, 0)
        e += 0x18
    for off in range(0x1AA0, 0x1AD8, 8):
        m.put(o + off, 8, 0)
    vt = m.u64(m.main + 0x46D8E88) + 0x10
    for off in range(0x1AE0, 0x1B18, 8):
        m.put(o + off, 8, 0)
    m.put(o + 0x1AD8, 8, vt); m.put(o + 0x1A98, 8, vt)
    for off in range(0x1B38, 0x1B70, 8):
        m.put(o + off, 8, 0)
    m.put(o + 0x1B30, 8, vt)
    for off in range(0x1B78, 0x1BB0, 8):
        m.put(o + off, 8, 0)
    m.put(o + 0x1B70, 8, vt)


@lifted(0x1730F6C)
def create_idhash(m, alloc, *_):
    """Create the 0x1bb0-byte id-hash table from alloc (0x1731094)."""
    return _create(m, alloc, 0x1BB0, lambda o: m.call_void(m.main + 0x1731094, o))


# --- loading the files ---------------------------------------------------------------------------

def _fb_records(data):
    """Offsets of the tables in field 0 (a vector of tables) of a FlatBuffers file's root."""
    def field(t, i):
        vt = t - struct.unpack_from("<i", data, t)[0]
        if struct.unpack_from("<H", data, vt)[0] < 4 + 2 * i + 2:
            return 0
        return struct.unpack_from("<H", data, vt + 4 + 2 * i)[0]
    root = struct.unpack_from("<I", data, 0)[0]
    f = field(root, 0)
    v = root + f + struct.unpack_from("<I", data, root + f)[0]
    n = struct.unpack_from("<I", data, v)[0]
    out = []
    for i in range(n):
        s = v + 4 + 4 * i
        out.append(s + struct.unpack_from("<I", data, s)[0])
    return out, field


def _load(m, alloc, path, data):
    """The file in memory (page-aligned from FILES; the resource system's own heap is not reproduced)
    with its resource object (vtable 0x4440368, 0x210 bytes): +0x48 the path's FNV-1a 64, +0x50 / +0x58
    the path and its length, +0x1d8 the size, +0x1f0 the bytes."""
    buf = getattr(m, "files_end", FILES)
    m.files_end = (buf + len(data) + 0xFFF) & ~0xFFF
    m.write(buf, data)
    name = m.vcall(alloc, 0x10, len(path) + 1, 1)
    m.write(name, path.encode() + b"\0")

    def build(r):
        m.write(r, bytes(RESOURCE_SIZE))
        m.put(r, 8, m.main + RESOURCE_VT)
        m.put(r + 0x20, 8, m.main + RESOURCE_VT + 0x98); m.put(r + 0x28, 8, m.main + RESOURCE_VT + 0xE8)
        m.put(r + 0x48, 8, _fnv1a64(path.encode()))
        m.put(r + 0x50, 8, name); m.put(r + 0x58, 8, len(path))
        m.put(r + 0x1D8, 8, len(data)); m.put(r + 0x1E8, 8, 0x10001)
        m.put(r + 0x1F0, 8, buf); m.put(r + 0x1F8, 8, alloc)
    return _create(m, alloc, RESOURCE_SIZE, build), buf


def _fill_map(m, t, buf, data, rule):
    """The u16 (or species * 10000 + form) map at +0x68: reserved to the record count, one 0x20-byte
    node {next, hash = key, key, record} per record in file order, the default (+0xd0) key 0's record,
    +0xd8 loaded."""
    recs, field = _fb_records(data)
    keyed = {}
    for r in recs:
        f0 = field(r, 0)
        a, b = struct.unpack_from("<HH", data, r + f0) if f0 else (0, 0)
        keyed.setdefault(a * 10000 + b if rule == "pair" else a, r)
    table = t + 0x68
    width = 4 if rule == "pair" else 2
    do = 0xF7BB84 if width == 4 else 0x127D27C        # __do_rehash with bucket arrays aligned 4 / 8
    _rehash(m, table, len(keyed), do)
    for key, r in keyed.items():
        node = m.vcall(m.u64(table + 0x38), 0x10, 0x20, 8)
        m.put(node, 8, 0); m.put(node + 8, 8, key)
        m.put(node + 0x10, 8, 0); m.put(node + 0x10, width, key)
        m.put(node + 0x18, 8, buf + r)
        _insert(m, table, node, key, do)
    m.put(t + 0xD0, 8, buf + keyed[0] if 0 in keyed else 0)
    m.put(t + 0xD8, 1, 1)


def _set_slot(m, slot_got, guard_got, obj):
    """The function-local static [slot_got] holds obj (its guard set, the slot empty before)."""
    _static_guard(m, guard_got)
    slot = m.u64(m.main + slot_got)
    if m.u64(slot):
        raise UnliftedCall("table static already holds an object")
    m.put(slot, 8, obj)


def build_tables(m, alloc, files):
    """The five data tables from `files` (romfs path -> bytes) into their statics. Returns name -> table."""
    out = {}
    for name, _slot, slot_got, guard_got, path, rule in TABLES:
        data = files[path]
        if name == "personal":
            t = m.call(m.main + 0x164498C, alloc)
        else:
            vt, vt20, w28, size = LAYOUT[name]

            def build(o, vt=vt, vt20=vt20, w28=w28, size=size):
                m.write(o, bytes(size))
                m.put(o + 8, 8, _tls_top(m))
                if size > 0x68:
                    _empty_table(m, o, m.main + vt, m.main + vt20, m.main + w28)
                else:
                    m.put(o, 8, m.main + vt); m.put(o + 0x20, 8, m.main + vt20)
                    m.put(o + 0x28, 8, m.main + w28)
            t = _create(m, alloc, size, build)
        res, buf = _load(m, alloc, path, data)
        m.put(t + 0x30, 8, res)
        if rule:
            _fill_map(m, t, buf, data, rule)
        _set_slot(m, slot_got, guard_got, t)
        out[name] = t
    name, _slot, slot_got, guard_got, path = IDHASH
    data = files[path]
    t = m.call(m.main + 0x1730F6C, alloc)
    recs, field = _fb_records(data)
    for i, r in enumerate(recs[:IDHASH_ENTRIES]):
        g = (lambda j: struct.unpack_from("<I", data, r + field(r, j))[0] if field(r, j) else 0)
        item, index = g(0), g(1)
        e = t + 0x28 + 0x18 * i
        m.put(e, 4, index); m.put(e + 4, 4, 0)
        m.put(e + 8, 8, m.u64(m.main + IDHASH_HASHES + 8 * index))
        m.put(e + 0x10, 2, item)
    for i in range(len(recs), IDHASH_ENTRIES):
        m.put(t + 0x28 + 0x18 * i, 4, 0xFFFFFFFF)
    _set_slot(m, slot_got, guard_got, t)
    out[name] = t
    return out


# --- the weak-handle table: static 0x4700930 (GOT 0x46d3910, guard GOT 0x46d3908) ------------------

@lifted(0x165E1C4)
def handles_base_165e1c4(m, o, *_):
    """Base constructor of the weak-handle table: vtable 0x44e8b00 (+0x20 its +0x30), +8 the top of the
    thread's object stack; the class static [0x46d3910] gets byte +8 = 1."""
    m.put(o + 0x10, 8, 0); m.put(o + 0x18, 4, 0)
    m.put(o, 8, m.u64(m.main + 0x46D66F8) + 0x10)
    top = _tls_top(m)
    m.put(o, 8, m.main + 0x44E8B00); m.put(o + 8, 8, top)
    m.put(o + 0x20, 8, m.main + 0x44E8B30)
    _static_guard(m, 0x46D3908)
    m.put(m.u64(m.main + 0x46D3910) + 8, 1, 1)


@lifted(0xC1ADEC)
def handles_new_block(m, o, *_):
    """Append a block of 0x400 handle entries (0x8008 bytes, the count at +0x8000 zeroed with the
    allocator on the thread's object stack) from the allocator [o] to the block table at o+8 (entries
    {block, allocator, 0x8008, 8}; count at o+0x8008, at most 0x400); a failed allocation appends
    {0, 0, 0, 0}."""
    alloc = m.u64(o)
    blk = m.vcall(alloc, 0x10, 0x8008, 8)
    if blk:
        stack = _tls_stack(m)
        _push(m, stack, alloc)
        m.put(blk + 0x8000, 8, 0)
        _pop(m, stack)
        size, align = 0x8008, 8
    else:
        alloc = size = align = 0
    count = m.u64(o + 0x8008)
    if count >= 0x400:
        raise UnliftedCall("abort: handle block table full")
    e = o + (count << 5)
    m.put(e + 8, 8, blk); m.put(e + 0x10, 8, alloc)
    m.put(e + 0x18, 8, size); m.put(e + 0x20, 8, align)
    m.put(o + 0x8008, 8, m.u64(o + 0x8008) + 1)


@lifted(0x165E080)
def construct_handles(m, o, *_):
    """The weak-handle table (vtable 0x44e8ab0): +0x28 its allocator (+8), the block table at +0x30 with
    one block (0xc1adec), current block +0x8038 0; at +0x8040 the id pool (base 0, next 0, live 0, two
    empty deques over the allocator, the live bitset +0x88..+0xc0, lock +0xd0, light event +0xe0);
    u32 +0x8144 1 and the light event +0x8138."""
    p = o + 0x8040
    m.call_void(m.main + 0x165E1C4, o)
    alloc = m.u64(o + 8)
    m.put(o, 8, m.main + 0x44E8AB0); m.put(o + 0x20, 8, m.main + 0x44E8AE0)
    m.put(o + 0x28, 8, alloc)
    m.put(o + 0x8030, 8, 0); m.put(o + 0x8038, 8, 0)
    m.call_void(m.main + 0xC1ADEC, o + 0x28)
    alloc = m.u64(o + 8)
    m.put(p, 8, 0); m.put(p + 8, 4, 0)
    m.put(p + 0x10, 8, 0); m.put(p + 0x18, 8, 0); m.put(p + 0x20, 8, 0)
    # two 0x28-byte deque headers copied from a stack temporary: {0, allocator, max, 0, u32 0} (the
    # temporary's last four bytes are never written; zero here)
    for at in (p + 0x28, p + 0x58):
        m.write(at, struct.pack("<QQQQQ", 0, alloc, 0x3FFFFFFFFFFFFFFF, 0, 0))
    m.put(p + 0x50, 8, 0)
    m.put(p + 0xB8, 4, 0); m.put(p + 0xC0, 8, 0)
    m.put(p + 0x88, 8, 0); m.put(p + 0x90, 8, 0)
    m.put(p + 0xEC, 4, 1)
    m.put(p + 0x98, 8, 0); m.put(p + 0xA0, 8, alloc)
    m.put(p + 0xA8, 8, 0x1FFFFFFFFFFFFFFF); m.put(p + 0xB0, 8, 0)
    m.put(p + 0xD0, 8, 0); m.put(p + 0xD8, 8, 0)
    m.call_void(m.main + 0x343E6D0, p + 0xE0, 0, 1)
    m.put(p + 0xF0, 8, 0)
    m.put(o + 0x8144, 4, 1)
    m.call_void(m.main + 0x343E6D0, o + 0x8138, 0, 1)


@lifted(0x165DD08)
def create_handles(m, alloc, *_):
    """Create the 0x8150-byte weak-handle table from alloc (align 0x10, 0x165e080)."""
    stack = _tls_stack(m)
    _push(m, stack, alloc)
    o = m.vcall(alloc, 0x10, 0x8150, 0x10)
    if not o:
        raise UnliftedCall("abort: allocation failed in Create")
    m.call_void(m.main + 0x165E080, o)
    m.put(o + 0x18, 4, 0x108150)
    m.put(o + 8, 8, alloc); m.put(o + 0x10, 8, o)
    _pop(m, stack)
    return o


def build_handles(m, alloc):
    """The weak-handle table into its static 0x4700930."""
    t = m.call(m.main + 0x165DD08, alloc)
    _set_slot(m, 0x46D3910, 0x46D3908, t)
    return t


def _scoped_copy(m, alloc, dst, src):
    """*dst = *src (u64) with alloc on the thread's object stack, when the thread has one."""
    stack = _tls_stack(m)
    if stack:
        _push(m, stack, alloc)
    m.put(dst, 8, m.u64(src))
    if stack:
        _pop(m, stack)


@lifted(0xC1AF5C)
def construct_backward_c1af5c(m, alloc_ref, begin, end, out, *_):
    """Copy the u64 range [begin, end) backward to end at *out (lowered as it goes), each element with
    the allocator [alloc_ref] on the thread's object stack."""
    while end != begin:
        _scoped_copy(m, m.u64(alloc_ref), m.u64(out) - 8, end - 8)
        end -= 8
        m.put(out, 8, m.u64(out) - 8)


@lifted(0xC1AA80)
def vector_append_c1aa80(m, v, n, value, *_):
    """vector<u64>::__append(n, value) of {begin, end, capacity, allocator*, max_size}: in place when
    it fits, else a new buffer of max(2 * capacity, size + n) elements (max_size when capacity is past
    half of it) from the allocator, the old elements moved behind the new ones (0xc1af5c) and the old
    buffer freed (0xb48fe8 when the allocator defers frees)."""
    begin, end, cap = m.u64(v), m.u64(v + 8), m.u64(v + 0x10)
    if n <= (cap - end) >> 3:
        for i in range(n):
            _scoped_copy(m, m.u64(v + 0x18), end + 8 * i, value)
        m.put(v + 8, 8, end + 8 * n)
        return
    size = (end - begin) >> 3
    want = n + size
    top = min(m.u64(v + 0x20), 0x7FFFFFFFFFFFFFFF)
    if top < want:
        raise UnliftedCall("vector length_error")
    have = (cap - begin) >> 3
    grow = max(2 * have, want)
    count = grow if have < top >> 1 else top
    alloc_ref = v + 0x18
    new = 0
    if count:
        new = m.vcall(m.u64(alloc_ref), 0x10, count * 8, 8)
        if not new:
            raise UnliftedCall("allocator out of memory: vf 0xe8")
    with m.frame(0x30) as sb:
        mid = new + size * 8
        m.put(sb + 8, 8, new); m.put(sb + 0x10, 8, mid)
        m.put(sb + 0x18, 8, mid); m.put(sb + 0x20, 8, new + count * 8); m.put(sb + 0x28, 8, alloc_ref)
        for i in range(n):
            _scoped_copy(m, m.u64(alloc_ref), mid + 8 * i, value)
        m.put(sb + 0x18, 8, mid + 8 * n)
        m.call_void(m.main + 0xC1AF5C, alloc_ref, m.u64(v), m.u64(v + 8), sb + 0x10)
        old = m.u64(v)
        old_cap = m.u64(v + 0x10)
        m.put(v, 8, m.u64(sb + 0x10)); m.put(v + 8, 8, m.u64(sb + 0x18))
        m.put(v + 0x10, 8, m.u64(sb + 0x20))
    if old:
        alloc = m.u64(alloc_ref)
        size = old_cap - old
        if m.vcall(alloc, 0xF8) & 1 and m.s(m.call(m.main + 0xB4E600) + 0x12C8, 4) >= 1:
            m.call_void(m.main + 0xB48FE8, alloc, old, size, 8)
        else:
            m.vcall_void(alloc, 0x18, old, size, 8)


# --- deque<u32> of freed handle ids: map {first, begin, end, cap, allocator} at +0, start +0x40, size
# +0x48, block allocator +0x50; blocks of 0x400 ids (0x1000 bytes, align 4) --------------------------

def _scoped_store(m, alloc, dst, value):
    stack = _tls_stack(m)
    if stack:
        _push(m, stack, alloc)
    m.put(dst, 8, value)
    if stack:
        _pop(m, stack)


def _map_push_back(m, sb, value, alloc):
    """split_buffer<T*>::push_back (0xb44a40, 0xb451d8, 0xb44f54): room at the back, or the elements
    shifted to the front half of the spare room (memmove); a reallocation is refused."""
    first, begin, end, cap = (m.u64(sb + i) for i in (0, 8, 0x10, 0x18))
    if end == cap:
        if begin <= first:
            raise UnliftedCall("split_buffer push_back reallocates")
        d = (((begin - first) >> 3) + 1) >> 1
        nb = begin - 8 * d
        m.write(nb, m.read(begin, end - begin))
        end = nb + (end - begin)
        m.put(sb + 8, 8, nb); m.put(sb + 0x10, 8, end)
    _scoped_store(m, alloc, end, value)
    m.put(sb + 0x10, 8, m.u64(sb + 0x10) + 8)


def _map_push_front(m, sb, value, alloc):
    """split_buffer<T*>::push_front (0xb44cc0, 0xb45458): room at the front, or the elements shifted to
    the back half of the spare room; a reallocation is refused."""
    first, begin, end, cap = (m.u64(sb + i) for i in (0, 8, 0x10, 0x18))
    if begin == first:
        if end >= cap:
            raise UnliftedCall("split_buffer push_front reallocates")
        d = (((cap - end) >> 3) + 1) >> 1
        nb = end + 8 * d - (end - begin)
        m.write(nb, m.read(begin, end - begin))
        begin = nb
        m.put(sb + 8, 8, nb); m.put(sb + 0x10, 8, end + 8 * d)
    _scoped_store(m, alloc, begin - 8, value)
    m.put(sb + 8, 8, m.u64(sb + 8) - 8)


@lifted(0xB44724)
def deque_add_back_capacity(m, d, *_):
    """libc++ deque<u32>::__add_back_capacity: a spare front block rotated to the back; else a new
    block (0x1000, align 4, from [d+0x50]) pushed onto the map, at the back when it has room there,
    else at the front and rotated; else a new map of max(2 * capacity, 1) pointers (align 4, from
    [d+0x20]) holding the old ones and the new block, the old map freed."""
    blocks = m.u64(d + 0x50)
    if m.u64(d + 0x40) >= 0x400:
        m.put(d + 0x40, 8, m.u64(d + 0x40) - 0x400)
        begin = m.u64(d + 8)
        pt = m.u64(begin)
        m.put(d + 8, 8, begin + 8)
        _map_push_back(m, d, pt, m.u64(d + 0x20))
        return
    first, begin, end, cap = (m.u64(d + i) for i in (0, 8, 0x10, 0x18))
    size = (end - begin) >> 3
    if size < (cap - first) >> 3:
        blk = m.vcall(blocks, 0x10, 0x1000, 4)
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
    bytes_ = cap - first
    count = (bytes_ >> 2) if bytes_ else 1
    alloc = m.u64(d + 0x20)
    new = m.vcall(alloc, 0x10, count * 8, 4)
    if not new:
        raise UnliftedCall("allocator out of memory: vf 0xe8")
    with m.frame(0x30) as sb:
        mid = new + size * 8
        m.put(sb, 8, new); m.put(sb + 8, 8, mid); m.put(sb + 0x10, 8, mid)
        m.put(sb + 0x18, 8, new + count * 8); m.put(sb + 0x20, 8, d + 0x20)
        blk = m.vcall(blocks, 0x10, 0x1000, 4)
        if not blk:
            raise UnliftedCall("allocator out of memory: vf 0xe8")
        _map_push_back(m, sb, blk, alloc)
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
            m.call_void(m.main + 0xB48FE8, a, old, old_cap - old, 4)
        else:
            m.vcall_void(a, 0x18, old, old_cap - old, 4)


# --- the battle setup's party holders ------------------------------------------------------------

PARTY_RECORD = 0x158                    # the bootstrap's record: 0x148 sealed core, 0x10 party block


def build_party(m, alloc, record):
    """A setup party holder (0x68 bytes, 0xfa0d38) holding one Pokemon parameter object (0xeee5dc)
    made from a 0x158-byte sealed record: a Pokemon record (0xeee8fc) loads it into its accessor under
    the accessor's lock (0xe14ea8), recomputes its stats (0xe13b9c(r, 1)) and clamps its PP (0xe14018),
    as 0xeeea48 does; the parameter object copies it. Holder: u8 count +0x60 = 1, the parameter object
    at +0x30 with one weak reference, its own count +0x28 = 1."""
    from pokeldn.sv.battle.engine.pokemon import _locked
    from pokeldn.sv.battle.engine.steps import _acquire, _inc
    if len(record) != PARTY_RECORD:
        raise ValueError(f"a party record is {PARTY_RECORD:#x} bytes")
    with m.frame(0x10) as f:
        r = m.call(m.main + 0xEEE8FC, f, alloc)
    with m.frame(0x160) as buf:
        m.write(buf, record)
        _locked(m, m.u64(r + 0x70), 0xE14EA8, buf, buf + 0x148)
    m.call_void(m.main + 0xE13B9C, r, 1)
    m.call_void(m.main + 0xE14018, r)
    with m.frame(0x10) as f:
        p = m.call(m.main + 0xEEE5DC, f, alloc, r)
    _acquire(m, p)
    with m.frame(0x10) as f:
        h = m.call(m.main + 0xFA0D38, f, alloc)
    _inc(m, h)
    m.put(h + 0x30, 8, p)
    m.put(h + 0x60, 1, 1)
    return h


from pokeldn.sv.battle.engine.calls import _tail
from pokeldn.sv.battle.engine.network import (
    M32, M64, _acquire_into, _base, _class_static, _clear_strong, _empty_map, _inc, _make, _network_manager,
    _release_strong, _scope_owner, _stores, _top_f53840, _vtables, _weak_base, release_counted_holder,
    take_release_strong)
from pokeldn.sv.battle.engine.references import _release_ref
from pokeldn.sv.battle.engine.steps import _do_rehash, _find


# --- the default resource handle: the resource system's null handle [0x46d4260] ----------------------

@lifted(0x2B80A64)
def resource_add_ref_null(m, *_):
    """vf 0x18 of the null resource handle: nothing."""
    return None


@lifted(0x1A1FB4C)
def construct_null_resource(m, o, *_):
    """The null resource handle (0x48 bytes): vtable [0x46d4268]+0x10 (+0x20 its +0x48), the name
    [[0x46d4270]] at +0x38 and its FNV-1a 64 at +0x30 (basis 0xcbf29ce484222645), +8 0, +0x10 itself."""
    m.put(o, 8, m.main + 0x441DAB0); m.put(o + 0x10, 8, 0); m.put(o + 0x18, 4, 0)
    top = _tls_top(m)
    h = 0xCBF29CE484222645
    m.put(o + 0x28, 4, 0); m.put(o + 0x30, 8, h); m.put(o + 0x40, 8, 0)
    vt = m.u64(m.main + 0x46D4268)
    m.put(o, 8, vt + 0x10); m.put(o + 8, 8, top); m.put(o + 0x20, 8, vt + 0x48)
    name = m.u64(m.u64(m.main + 0x46D4270))
    m.put(o + 0x38, 8, name)
    i = 0
    while True:
        c = m.u8(name + i)
        if not c:
            break
        h = ((h ^ c) * 0x100000001B3) & M64
        i += 1
    m.put(o + 0x30, 8, h); m.put(o + 0x40, 8, 0)
    m.put(o + 8, 8, 0); m.put(o + 0x10, 8, o)


@lifted(0xC44228)
def null_resource(m, *_):
    """The null resource handle [0x46d4260] (guard [0x46d4258]), built with no owner on the thread's
    object stack; returns its address."""
    stack = _tls_stack(m)
    _push(m, stack, 0)
    guard = m.u64(m.main + 0x46D4258)
    if m.u8(guard) & 1 == 0 and m.call(m.main + 0x343CF10, guard) & M32:
        m.call_void(m.main + 0x1A1FB4C, m.u64(m.main + 0x46D4260))
        m.call_void(m.main + 0x343CF20, guard)
    _pop(m, stack)
    return m.u64(m.main + 0x46D4260)


@lifted(0xC1E764)
def resource_handle_from(m, dst, src, *_):
    """*dst = a handle for *src's name: the null handle (one reference, vf 0x18) when the name is empty;
    a named one comes from the resource system (0xbf9884), not reproduced."""
    m.put(dst, 8, 0)
    s = m.u64(src)
    name = m.u64(s + 0x38) if s else 0
    if name and m.u8(name):
        raise UnliftedCall("main+0xbf9884: the resource system")
    h = m.call(m.main + 0xC44228)
    if h:
        m.vcall_void(h, 0x18)
    old = m.u64(dst)
    m.put(dst, 8, h)
    if old:
        m.vcall_void(old, 0x20)
    return dst


def _setup_default_resource(m):
    """The static [0x46d8c30] (guard [0x46d8c28]): a handle copied from the null one (its __cxa_atexit
    registration is not reproduced)."""
    guard = m.u64(m.main + 0x46D8C28)
    if m.u8(guard) & 1 == 0 and m.call(m.main + 0x343CF10, guard) & M32:
        with m.frame(0x10) as f:
            m.put(f, 8, m.call(m.main + 0xC44228))
            m.call_void(m.main + 0xC1E764, m.u64(m.main + 0x46D8C30), f)
        m.call_void(m.main + 0x343CF20, guard)


# --- the battle setup (0x730 bytes, vtable 0x44ff070) -------------------------------------------------

PARTICIPANT = (0x0, 0xC8, 0x188, 0x248, 0x308, 0x3C8)        # +0xc8 + 0xc0 * i: the five participants

_PARTICIPANT_RESET = (
    (0x0, 8, 0), (0xC, 2, 0xFFFF), (0x8, 4, 0xFFFFFFFF), (0x18, 1, 0), (0x10, 8, 0), (0x1A, 2, 0xA),
    (0x20, 1, 0xA), (0x1C, 4, 0x0A0A0A0A), (0x24, 2, 0), (0x26, 1, 0), (0x28, 2, 0), (0x34, 1, 0),
    (0x2C, 8, 0), (0x36, 2, 0xA), (0x3C, 1, 0xA), (0x38, 4, 0x0A0A0A0A), (0x40, 2, 0), (0x42, 1, 0),
    (0x44, 2, 0), (0x50, 1, 0), (0x48, 8, 0), (0x52, 2, 0xA), (0x58, 1, 0xA), (0x54, 4, 0x0A0A0A0A),
    (0x5C, 2, 0), (0x5E, 1, 0), (0x60, 2, 0), (0x6C, 1, 0), (0x64, 8, 0), (0x6E, 2, 0xA), (0x74, 1, 0xA),
    (0x70, 4, 0x0A0A0A0A), (0x78, 2, 0), (0x7A, 1, 0), (0x7C, 2, 0), (0x88, 1, 0), (0x80, 8, 0),
    (0x8A, 2, 0xA), (0x90, 1, 0xA), (0x8C, 4, 0x0A0A0A0A), (0x94, 2, 0), (0x96, 1, 0), (0x98, 2, 0),
    (0xA4, 1, 0), (0x9C, 8, 0), (0xA6, 2, 0xA), (0xAC, 1, 0xA), (0xA8, 4, 0x0A0A0A0A), (0xB0, 2, 0),
    (0xB2, 1, 0), (0xB4, 2, 0))


def _participant_tail(m, p):
    """A participant's reference (+0) released and its seven stat-stage blocks reset."""
    old = m.u64(p)
    m.put(p, 8, 0)
    if old:
        _release_ref(m, old)
    _stores(m, p, _PARTICIPANT_RESET)


@lifted(0x15A0110)
def reset_participant(m, p, *_):
    """A participant (0xc0 bytes): u32 +0xb8 0x64640000, +0xbc 100, then the reset."""
    m.put(p + 0xB8, 4, 0x64640000); m.put(p + 0xBC, 1, 0x64)
    _participant_tail(m, p)


@lifted(0x159FBB0)
def construct_participant(m, p, *_):
    """A participant's fields stored once (the reset's values, +0xb8/+0xbc), then the reset."""
    _stores(m, p, (
        (0x0, 8, 0), (0xC, 2, 0xFFFF), (0x8, 4, 0xFFFFFFFF), (0x10, 8, 0), (0x20, 2, 0xA), (0x1C, 4, 0x0A0A0A0A),
        (0x18, 1, 0), (0x1A, 2, 0xA), (0x24, 2, 0), (0x26, 1, 0), (0x28, 2, 0), (0x2C, 8, 0),
        (0x38, 4, 0x0A0A0A0A), (0x34, 1, 0), (0x36, 2, 0xA), (0x3C, 2, 0xA), (0x40, 2, 0), (0x42, 1, 0),
        (0x44, 2, 0), (0x59, 1, 0), (0x48, 8, 0), (0x54, 4, 0x0A0A0A0A), (0x50, 1, 0), (0x52, 2, 0xA),
        (0x58, 1, 0xA), (0x5C, 2, 0), (0x5E, 1, 0), (0x60, 2, 0), (0x64, 8, 0), (0x70, 4, 0x0A0A0A0A),
        (0x6C, 1, 0), (0x6E, 2, 0xA), (0x74, 2, 0xA), (0x78, 2, 0), (0x7A, 1, 0), (0x7C, 2, 0), (0x80, 8, 0),
        (0x91, 1, 0), (0x88, 1, 0), (0x90, 1, 0xA), (0x8C, 4, 0x0A0A0A0A), (0x8A, 2, 0xA), (0x94, 2, 0),
        (0x96, 1, 0), (0x98, 2, 0), (0x9C, 8, 0), (0xA8, 4, 0x0A0A0A0A), (0xB8, 4, 0x64640000), (0xA4, 1, 0),
        (0xA6, 2, 0xA), (0xAC, 2, 0xA), (0xB0, 2, 0), (0xB2, 1, 0), (0xB4, 2, 0), (0xBC, 1, 0x64)))
    _participant_tail(m, p)


@lifted(0x159FE68)
def reset_setup(m, o, *_):
    """The setup's battle fields reset: member codes +0x99..+0x9d 0xff, the five party holders released
    and the participants reset, flags +0x498 zero, the float factors 1.0, +0x4e4..+0x4f7 -1."""
    _stores(m, o, ((0x8C, 2, 0), (0x90, 8, 0), (0x2C, 8, 0), (0x31, 8, 0), (0x99, 4, 0xFFFFFFFF),
                   (0x9D, 1, 0xFF), (0x708, 8, 0), (0x98, 1, 0)))
    for i in range(5):
        h = o + 0xA0 + 8 * i
        old = m.u64(h)
        m.put(h, 8, 0)
        if old:
            _release_ref(m, old)
        m.call_void(m.main + 0x15A0110, o + PARTICIPANT[i + 1])
    _stores(m, o, (
        (0x492, 1, 0), (0x488, 8, 0), (0x498, 8, 0), (0x49E, 8, 0), (0x4A8, 8, 0), (0x4B0, 8, 0), (0x4B8, 1, 0),
        (0x704, 4, 0), (0x710, 4, 0), (0x4BC, 8, 0x3F8000003F800000), (0x4D4, 4, ONE_F),
        (0x4C4, 8, 0x3F8000003F800000), (0x4CC, 8, 0x3F8000003F800000), (0x714, 1, 0), (0x4D8, 8, 0),
        (0x4E0, 2, 0), (0x4F4, 4, 0xFFFFFFFF), (0x4E4, 8, M64), (0x4EC, 8, M64)))
    _setup_default_resource(m)
    _stores(m, o, ((0x6F4, 8, 0), (0x6FC, 8, 0), (0x6DC, 8, 0), (0x6E4, 8, 0), (0x6EC, 8, 0),
                   (0x4C0, 4, ONE_F), (0x4F8, 2, 0), (0x6D8, 2, 0), (0x490, 2, 0)))


@lifted(0x159F8F0)
def construct_setup(m, o, *_):
    """The battle setup: vtable 0x44ff070 (+0x20 0x44ff0a8), five participants (0x159fbb0), the boss
    action profile block at +0x500 (vtable [0x46e2f48]+0x10) and +0x560 ([0x46e2f50]+0x10), the reset
    (0x159fe68)."""
    top = _base(m, o)
    m.put(o + 0x28, 4, 0)
    m.put(o, 8, m.main + 0x44FF070); m.put(o + 8, 8, top); m.put(o + 0x20, 8, m.main + 0x44FF0A8)
    _stores(m, o, ((0x3C, 1, 0), (0x3E, 2, 0), (0x40, 4, 0x1000000), (0x44, 2, 0), (0x46, 1, 0), (0x48, 8, 0),
                   (0x4D, 8, 0), (0x58, 8, 0), (0x5F, 8, 0), (0x88, 4, 0), (0xA0, 8, 0), (0x78, 8, 0),
                   (0x80, 8, 0), (0x68, 8, 0), (0x70, 8, 0), (0xB8, 8, 0), (0xC0, 8, 0), (0xA8, 8, 0),
                   (0xB0, 8, 0)))
    for p in PARTICIPANT[1:]:
        m.call_void(m.main + 0x159FBB0, o + p)
    m.put(o + 0x508, 4, 0)
    m.put(o + 0x500, 8, m.u64(m.main + 0x46E2F48) + 0x10)
    m.put(o + 0x50C, 1, 0)
    m.write(o + 0x510, bytes(0x4E))
    m.put(o + 0x560, 8, m.u64(m.main + 0x46E2F50) + 0x10)
    m.write(o + 0x568, bytes(0x4A))
    _stores(m, o, (
        (0x5C6, 2, 0xA), (0x5C8, 4, 0x0A0A0A0A), (0x5CC, 2, 0xA), (0x5D8, 8, 0), (0x5E0, 8, 0), (0x5E8, 8, 0),
        (0x5F0, 8, 0), (0x5F8, 8, 0), (0x600, 8, 0), (0x608, 8, 0), (0x610, 1, 0), (0x612, 2, 0xA),
        (0x614, 4, 0x0A0A0A0A), (0x618, 2, 0xA), (0x61C, 2, 0), (0x61E, 1, 0), (0x620, 2, 0), (0x635, 1, 0),
        (0x624, 8, 0), (0x62C, 1, 0), (0x62E, 2, 0xA), (0x634, 1, 0xA), (0x630, 4, 0x0A0A0A0A), (0x638, 2, 0),
        (0x63A, 1, 0), (0x63C, 2, 0), (0x648, 1, 0), (0x640, 8, 0), (0x64A, 2, 0xA), (0x64C, 4, 0x0A0A0A0A),
        (0x650, 2, 0xA), (0x654, 2, 0), (0x656, 1, 0), (0x658, 2, 0), (0x66D, 1, 0), (0x65C, 8, 0),
        (0x664, 1, 0), (0x666, 2, 0xA), (0x668, 4, 0x0A0A0A0A), (0x66C, 1, 0xA), (0x670, 2, 0), (0x672, 1, 0),
        (0x674, 2, 0), (0x678, 8, 0), (0x680, 1, 0), (0x682, 2, 0xA), (0x688, 2, 0xA), (0x684, 4, 0x0A0A0A0A),
        (0x68C, 2, 0), (0x68E, 1, 0), (0x690, 2, 0), (0x6A5, 1, 0), (0x694, 8, 0), (0x69C, 1, 0),
        (0x69E, 2, 0xA), (0x6A4, 1, 0xA), (0x6A0, 4, 0x0A0A0A0A), (0x6A8, 2, 0), (0x6AA, 1, 0), (0x6AC, 2, 0),
        (0x6D0, 8, 0), (0x6C8, 8, 0), (0x6C0, 8, 0), (0x6B8, 8, 0), (0x6B0, 8, 0), (0x5B8, 4, 0), (0x5D0, 2, 0),
        (0x728, 8, 0), (0x720, 8, 0), (0x718, 8, 0)))
    return _tail(m, m.main + 0x159FE68, o)


@lifted(0x159F0EC)
def create_setup(m, out, alloc, *_):
    return _make(m, alloc, 0x730, 0x159F8F0)


@lifted(0x159EEE8)
def make_setup(m, alloc, *_):
    """*x8 = a new setup holding one reference."""
    out = m.x8
    with m.frame(0x10) as f:
        p = m.call(m.main + 0x159F0EC, f, alloc)
    m.put(out, 8, p)
    if p:
        _inc(m, p)
    return p


# --- S+0xe8: 0x288 bytes (vtable 0x44fefa0) with a 0x98-byte map holder (vtable 0x44ff008) at +0x38 -----

lifted(0x159F840)(lambda m, h, *_: _scope_owner(m, h))
lifted(0x159F898)(lambda m, h, *_: _scope_owner(m, h))
lifted(0x159F800)(lambda m, t, *_: _empty_map(m, t, 0x159F840, 0x159F898))


@lifted(0x159F788)
def construct_159f788(m, o, *_):
    """vtable 0x44ff008 (+0x20 0x44ff040), an empty map at +0x30."""
    m.put(o + 0x10, 8, 0); m.put(o + 0x18, 4, 0)
    m.put(o, 8, m.u64(m.main + 0x46D66F8) + 0x10)
    top = _top_f53840(m)
    m.put(o + 0x28, 4, 0)
    m.put(o, 8, m.main + 0x44FF008); m.put(o + 8, 8, top); m.put(o + 0x20, 8, m.main + 0x44FF040)
    return _tail(m, m.main + 0x159F800, o + 0x30)


@lifted(0x159F660)
def create_159f660(m, alloc, *_):
    return _make(m, alloc, 0x98, 0x159F788)


lifted(0x159F5F4)(lambda m, holder, *_: release_counted_holder(m, holder))


@lifted(0x159EDC8)
def clear_map_159edc8(m, t, *_):
    if m.u64(t + 0x58):
        raise UnliftedCall("main+0x159edc8 clearing a filled map")
    return None


@lifted(0x159ED18)
def reset_159ed18(m, o, *_):
    """S+0xe8's battle fields reset: u32 5 / 6 bytes from +0x2c, zero runs, +0x110..+0x275 zero, +0x278
    -1, then its map at [+0x38]+0x30 cleared."""
    _stores(m, o, ((0xF0, 8, 0), (0x2C, 8, 0x700000000), (0x34, 2, 0x506), (0xA7, 8, 0), (0xA0, 8, 0),
                   (0x40, 8, 0x0506050605060506), (0x48, 8, 0x0506050605060506), (0x50, 4, 0x05060506),
                   (0xB0, 8, 0), (0xB7, 8, 0), (0xC0, 8, 0), (0xC7, 8, 0), (0xD0, 8, 0), (0xD7, 8, 0),
                   (0xE0, 8, 0), (0xE7, 8, 0), (0x106, 8, 0), (0x97, 8, 0), (0x80, 8, 0), (0xF8, 8, 0),
                   (0x100, 8, 0), (0x88, 8, 0), (0x90, 8, 0)))
    m.write(o + 0x110, bytes(0x166))
    m.put(o + 0x278, 8, M64)
    return _tail(m, m.main + 0x159EDC8, m.u64(o + 0x38) + 0x30)


@lifted(0x159F47C)
def construct_159f47c(m, o, *_):
    """vtable 0x44fefa0 (+0x20 0x44fefd8), a new 0x98-byte map holder at +0x38, then the reset."""
    top = _base(m, o)
    m.put(o + 0x28, 4, 0)
    m.put(o, 8, m.main + 0x44FEFA0); m.put(o + 8, 8, top); m.put(o + 0x20, 8, m.main + 0x44FEFD8)
    _stores(m, o, ((0x38, 8, 0), (0x78, 8, 0), (0x280, 4, 0), (0x284, 2, 0), (0x58, 8, 0), (0x60, 8, 0),
                   (0x68, 8, 0), (0x70, 8, 0)))
    p = m.call(m.main + 0x159F660, top)
    if p:
        _inc(m, p)
    old = m.u64(o + 0x38)
    m.put(o + 0x38, 8, p)
    if old:
        _release_ref(m, old)
    return _tail(m, m.main + 0x159ED18, o)


@lifted(0x159F214)
def create_159f214(m, alloc, *_):
    return _make(m, alloc, 0x288, 0x159F47C)


@lifted(0x159EE7C)
def make_159ee7c(m, alloc, *_):
    out = m.x8
    p = m.call(m.main + 0x159F214, alloc)
    m.put(out, 8, p)
    if p:
        _inc(m, p)
    return p


# --- the battle session S (0x110 bytes, vtable 0x4484008) ---------------------------------------------

lifted(0x159EF5C)(lambda m, dst, p, *_: _acquire_into(m, dst, p))
lifted(0x159ECA0)(lambda m, holder, *_: _release_strong(m, holder))


@lifted(0x159EC64)
def assign_strong_159ec64(m, holder, p, *_):
    """*holder = p (a strong reference); the old value released."""
    with m.frame(0x10) as t:
        m.call_void(m.main + 0x159EF5C, t, p)
        x = m.u64(t)
        m.put(t, 8, m.u64(holder)); m.put(holder, 8, x)
        return m.call(m.main + 0x159ECA0, t)


@lifted(0xD220F4)
def link_job(m, job, before, after, *_):
    """Links a job after `before` and before `after` in the engine's job graph; with both null (no job
    scheduler: the session runs on no thread) it does nothing."""
    if before or after:
        raise UnliftedCall("main+0xd220f4: the job scheduler")
    return job


def bare_job(m, alloc, *_):
    """A stand-in for the job 0x159f018 makes (0x400 bytes from alloc; its constructor 0xca3348 needs
    the engine's job scheduler at +0x1e8, which no arena holds): a Create'd block, zero but for its
    header and a weak handle at +0x30 to its +0x28. S keeps it at +0x40; no battle code reads it."""
    def build(o):
        m.write(o, bytes(0x400))
        m.call_void(m.main + 0xC1A3F4, o + 0x30, o + 0x28)
    return _create(m, alloc, 0x400, build)


@lifted(0x159E860)
def construct_session(m, s, before, after, *_):
    """S: vtable 0x4484008 (+0x20 0x4484080, +0x28 0x44840d0), +0x40..+0x10b zero, its job (0x159f018,
    the callback 0x126753c over S at +0x380..+0x3a0, linked by 0xd220f4) at +0x40, +0xf8 cleared, the
    setup at +0xe0 (0x159eee8, reset by 0x159fe68, +0x718 eight random bytes), the 0x288-byte object
    at +0xe8 (0x159ee7c, reset by 0x159ed18)."""
    _weak_base(m, s)
    _vtables(m, s, 0x4484008, 0x78, 0xC8)
    m.write(s + 0x40, bytes(0xCC))
    with m.frame(0x20) as f:
        sp8, fp18 = f, f + 8
        m.put(fp18, 8, s)
        m.call_sret(m.main + 0x159F018, sp8, m.u64(s + 8), fp18)
        job = m.u64(sp8)
        if m.u64(job + 0x388):
            raise UnliftedCall("main+0x159e860: the job already holds a callback")
        m.put(job + 0x380, 8, m.main + 0x126753C); m.put(job + 0x390, 8, m.main + 0x2A0F9E4)
        m.put(job + 0x3A0, 8, s); m.put(job + 0x388, 8, m.main + 0x2A0F9E0)
        m.put(job + 0x398, 8, m.main + 0x2A0F9F0)
        thread = m.call(m.main + 0x343C290)
        if m.u64(job + 0x1D0):
            raise UnliftedCall("main+0x159e860: the job is locked")
        m.put(job + 0x1D0, 8, thread)
        m.call_void(m.main + 0xD220F4, job, before, 0)
        m.call_void(m.main + 0xD220F4, job, 0, after)
        _clear_strong(m, s + 0x40)
        m.put(sp8, 8, 0); m.put(s + 0x40, 8, job)
        m.call_void(m.main + 0x159EC64, s + 0xF8, 0)
        alloc = m.u64(s + 8)
        m.call_sret(m.main + 0x159EEE8, fp18, alloc)
        old = m.u64(s + 0xE0); m.put(s + 0xE0, 8, 0)
        if old:
            _release_ref(m, old)
        m.put(s + 0xE0, 8, m.u64(fp18))
        m.call_sret(m.main + 0x159EE7C, fp18, alloc)
        old = m.u64(s + 0xE8); m.put(s + 0xE8, 8, 0)
        if old:
            _release_ref(m, old)
        m.put(s + 0xE8, 8, m.u64(fp18))
        m.call_void(m.main + 0x159FE68, m.u64(s + 0xE0))
        setup = m.u64(s + 0xE0)
        m.call_void(m.main + 0x343DD20, fp18, 8)
        m.put(setup + 0x718, 8, m.u64(fp18))
        m.call_void(m.main + 0x159ED18, m.u64(s + 0xE8))
        m.put(s + 0x100, 4, 0)
        m.put(job + 0x1D0, 8, 0)
        m.call_void(m.main + 0x343E5E0, job + 0x1D8)


@lifted(0x159E0E0)
def create_session(m, alloc, before_ref, after_ref, *_):
    """S from alloc (0x110 bytes) with the job's scheduler links *before_ref and *after_ref."""
    return _create(m, alloc, 0x110, lambda o: m.call_void(m.main + 0x159E860, o, m.u64(before_ref),
                                                          m.u64(after_ref)))


@lifted(0x343DD20)
def generate_random_bytes(m, dst, n, *_):
    """nn::crypto::GenerateCryptographicallyRandomBytes: the Machine's random_bytes(n)."""
    from pokeldn.sv.battle.engine.steps import _random
    _random(m, dst, n)


# --- the battle session manager [[0x46d38e0]] (0xc0 bytes, vtable 0x4483f68), made at boot ------------

@lifted(0x343C300)
def initialize_mutex(m, mutex, recursive, level, *_):
    """nn::os::InitializeMutex: u8 +0 1, u8 +1 recursive, u32 +4 level, u32 +8 count 0, +0x10 owner 0,
    u32 +0x18 lock 0 (+0xc and +0x1c untouched)."""
    m.put(mutex, 1, 1); m.put(mutex + 1, 1, recursive & 1); m.put(mutex + 4, 4, level)
    m.put(mutex + 8, 4, 0); m.put(mutex + 0x10, 8, 0); m.put(mutex + 0x18, 4, 0)


lifted(0x168B604)(lambda m, *_: _class_static(m, 0x4740CA8, 0x4740CB0))


@lifted(0x2A1C9C8)
def comm_buffers_class(m, *_):
    """vf 0 of the 0x7660-byte communication object's +0x28 part: its class static 0x4740ca8."""
    m.call_void(m.main + 0x168B604)
    return m.main + 0x4740CA8


def _fresh_storage(m, vec, size, align, n, elem):
    """A custom vector {allocator, max, ..} at vec gets n elements of `size` bytes (vf 0x10 of the
    allocator, `align`): the pointer at +0x20, count 0 at +0x28 and capacity n at +0x30 (0x168d8b8,
    0x168d97c for a vector that held nothing)."""
    if m.u64(vec + 8) < n:
        raise UnliftedCall("vector length error")
    p = m.vcall(m.u64(vec), 0x10, n * size, align)
    if not p:
        raise UnliftedCall("allocator out of memory")
    if m.u64(vec + 0x20):
        raise UnliftedCall("main+0x168d8b8 replacing a vector's storage")
    m.put(vec + 0x30, 8, n); m.put(vec + 0x20, 8, p); m.put(vec + 0x28, 8, 0)


lifted(0x168D770)(lambda m, vec, n, *_: _fresh_storage(m, vec, 0xC, 4, n, 0))
lifted(0x168D7AC)(lambda m, vec, n, *_: _fresh_storage(m, vec, 0x18, 8, n, 0))


@lifted(0x168D59C)
def construct_comm_buffers(m, o, alloc, port_ref, slots, frames, *_):
    """The 0x7660-byte communication object (vtable 0x4492468 (+0x20 0x44924e8, +0x28 0x4492538,
    +0x40 0x4492590)): u16 +0x50 *port_ref, a vector of `slots` 12-byte entries over alloc at +0x78
    (storage +0x98, capacity +0xa8) and one of `frames` 0x18-byte entries at +0xd0 (storage +0xf0),
    +0x108..+0x763f zero, a mutex at +0x7640. +0x94 and +0xec copy +0x74 and +0xcc, which nothing
    writes (heap contents; zero here)."""
    m.put(o + 0x10, 8, 0); m.put(o + 0x18, 4, 0)
    _weak_base(m, o)
    _vtables(m, o, 0x4492468, 0x80, 0xD0)
    m.put(o + 0x40, 8, m.main + 0x4492590); m.put(o + 0x48, 8, alloc)
    port = m.u16(port_ref)
    v = o + 0x78
    m.put(v, 8, alloc); m.put(o + 0x70, 4, 0); m.put(o + 0x50, 2, port)
    tail = m.u64(o + 0x70)
    _stores(m, o, ((0x60, 8, 0x1555555555555555), (0x68, 8, 0), (0x58, 8, alloc), (0x80, 8, 0x1555555555555555),
                   (0x88, 8, 0), (0xA0, 8, 0), (0xA8, 8, 0), (0x90, 8, tail), (0x98, 8, 0)))
    if slots & M32:
        m.call_void(m.main + 0x168D770, v, slots & M32)
    v = o + 0xD0
    m.put(v, 8, alloc); m.put(o + 0xC8, 4, 0)
    _stores(m, o, ((0xB8, 8, 0x0AAAAAAAAAAAAAAA), (0xC0, 8, 0), (0xB0, 8, alloc), (0xD8, 8, 0x0AAAAAAAAAAAAAAA),
                   (0xE0, 8, 0)))
    tail = m.u64(o + 0xC8)
    _stores(m, o, ((0xE8, 8, tail), (0xF0, 8, 0), (0xF8, 8, 0), (0x100, 8, 0)))
    if frames & M32:
        m.call_void(m.main + 0x168D7AC, v, frames & M32)
    m.write(o + 0x108, bytes(0x7538))
    return _tail(m, m.main + 0x343C300, o + 0x7640, 0, 0)


@lifted(0x168D444)
def create_comm_buffers(m, alloc, alloc_ref, port_ref, slots_ref, frames_ref, *_):
    return _create(m, alloc, 0x7660, lambda o: m.call_void(
        m.main + 0x168D59C, o, m.u64(alloc_ref), port_ref, m.u32(slots_ref), m.u32(frames_ref)))


@lifted(0x168D380)
def make_comm_buffers(m, alloc, alloc_ref, port_ref, slots_ref, frames_ref, *_):
    return _make_strong_args(m, 0x168D444, alloc, alloc_ref, port_ref, slots_ref, frames_ref)


def _make_strong_args(m, create, *args):
    out = m.x8
    p = m.call(m.main + create, *args)
    _acquire_into(m, out, p)
    return p


@lifted(0x168DA40)
def register_comm_buffers(m, o, *_):
    """Registers the communication object with the network manager (0x168e4dc); nothing without one or
    when it is registered (+0x7638)."""
    if m.u64(o + 0x7638):
        return o
    if _network_manager(m) == 0:
        return 0
    raise UnliftedCall("main+0x168e4dc: a network manager")


@lifted(0x168D210)
def construct_comm(m, o, alloc, port_ref, slots, frames, *_):
    """The 0x48-byte holder (vtable 0x4492338 (+0x20 0x44923c0, +0x28 0x4492410)) of the communication
    object at +0x40 (0x168d380 from alloc, *port_ref, slots, frames), then its registration."""
    _stores(m, o, ((0x30, 8, 0), (0x38, 8, 0), (0x20, 8, 0), (0x28, 8, 0)))
    m.put(o, 8, m.u64(m.main + 0x46D66F8) + 0x10); m.put(o + 8, 8, 0)
    m.put(o + 0x10, 8, 0); m.put(o + 0x18, 8, 0); m.put(o + 0x18, 4, 0)
    _weak_base(m, o)
    _vtables(m, o, 0x4492338, 0x88, 0xD8)
    with m.frame(0x10) as f:
        m.put(f, 8, alloc); m.put(f + 8, 4, slots); m.put(f + 0xC, 4, frames)
        m.call_sret(m.main + 0x168D380, o + 0x40, m.u64(o + 8), f, port_ref, f + 8, f + 0xC)
    p = m.u64(o + 0x40)
    if p:
        return _tail(m, m.main + 0x168DA40, p)
    return None


@lifted(0x168D0B8)
def create_comm(m, alloc, alloc_ref, port_ref, slots_ref, frames_ref, *_):
    return _create(m, alloc, 0x48, lambda o: m.call_void(
        m.main + 0x168D210, o, m.u64(alloc_ref), port_ref, m.u32(slots_ref), m.u32(frames_ref)))


@lifted(0x168CDC0)
def make_comm(m, alloc, alloc_ref, port_ref, slots_ref, frames_ref, *_):
    return _make_strong_args(m, 0x168D0B8, alloc, alloc_ref, port_ref, slots_ref, frames_ref)


lifted(0x168CD48)(lambda m, holder, *_: _release_strong(m, holder))


@lifted(0x168E23C)
def do_rehash_168e23c(m, table, n, *_):
    """__do_rehash of the manager's session map (u32 id keys, bucket arrays aligned 8)."""
    _do_rehash(m, table, n, 8, 4)


@lifted(0x168CE84)
def rehash_168ce84(m, table, n, *_):
    _rehash(m, table, n, 0x168E23C)


@lifted(0x168CF8C)
def manager_base(m, o, *_):
    """vtable 0x4483fb8 (+0x20 0x4483fe8), +8 the owner; the manager static's byte +8 = 1 (its guard
    [0x46d38d8], whose __cxa_atexit registration is not reproduced)."""
    top = _base(m, o)
    m.put(o, 8, m.main + 0x4483FB8); m.put(o + 8, 8, top); m.put(o + 0x20, 8, m.main + 0x4483FE8)
    guard = m.u64(m.main + 0x46D38D8)
    if m.u8(guard) & 1 == 0 and m.call(m.main + 0x343CF10, guard) & M32:
        m.call_void(m.main + 0x343CF20, guard)
    m.put(m.u64(m.main + 0x46D38E0) + 8, 1, 1)


@lifted(0x168CC48)
def construct_manager(m, o, *_):
    """The battle session manager: the session map at +0x28 (id -> S, 64 buckets), a mutex at +0x90,
    the next id u32 +0xb0, and at +0xb8 a strong reference to the communication holder 0x168cdc0 makes
    (port 0x7b, 16 slots, 32 frames)."""
    m.call_void(m.main + 0x168CF8C, o)
    owner = m.u64(o + 8)
    m.put(o, 8, m.main + 0x4483F68); m.put(o + 0x20, 8, m.main + 0x4483F98)
    _stores(m, o, ((0x28, 8, 0), (0x30, 8, 0), (0x38, 8, owner), (0x58, 8, 0), (0x60, 8, owner), (0x50, 4, 0),
                   (0x78, 4, 0), (0x80, 8, 0), (0x88, 4, ONE_F), (0x40, 8, 0x0FFFFFFFFFFFFFFF), (0x48, 8, 0),
                   (0x68, 8, 0x0FFFFFFFFFFFFFFF), (0x70, 8, 0)))
    m.call_void(m.main + 0x343C300, o + 0x90, 0, 0)
    m.put(o + 0xB0, 4, 0); m.put(o + 0xB8, 8, 0)
    m.call_void(m.main + 0x168CE84, o + 0x28, 64)
    with m.frame(0x30) as f:
        alloc_ref, port, frames, slots, out, old = f, f + 8, f + 0x10, f + 0x14, f + 0x18, f + 0x20
        m.put(alloc_ref, 8, owner); m.put(port, 2, 0x7B); m.put(frames, 4, 0x20); m.put(slots, 4, 0x10)
        m.call_sret(m.main + 0x168CDC0, out, owner, alloc_ref, port, slots, frames)
        m.put(old, 8, m.u64(o + 0xB8)); m.put(o + 0xB8, 8, 0)
        m.call_void(m.main + 0x168CD48, old)
        x = m.u64(out); m.put(out, 8, 0); m.put(o + 0xB8, 8, x)
        m.call_void(m.main + 0x168CD48, out)


@lifted(0x168CB20)
def create_manager(m, alloc, *_):
    return _make(m, alloc, 0xC0, 0x168CC48)


@lifted(0x168FF70)
def reset_manager_static(m, slot, p, *_):
    """unique_ptr reset of the manager static: the old manager would be destroyed (not reproduced)."""
    old = m.u64(slot)
    m.put(slot, 8, p)
    if old:
        raise UnliftedCall("main+0x168ff70 destroying a manager")


@lifted(0x168CA58)
def make_manager(m, alloc, *_):
    """The boot step: the manager static [[0x46d38e0]] (guard [0x46d38d8]) = a new manager from alloc, its
    +0x20 appended to the registry at 0x4763a18 (count u32 0x4765a18, at most 0x400)."""
    guard = m.u64(m.main + 0x46D38D8)
    if m.u8(guard) & 1 == 0 and m.call(m.main + 0x343CF10, guard) & M32:
        m.call_void(m.main + 0x343CF20, guard)
    p = m.call(m.main + 0x168CB20, alloc)
    slot = m.u64(m.main + 0x46D38E0)
    m.call_void(m.main + 0x168FF70, slot, p)
    n = m.u32(m.main + 0x4765A18)
    if n >= 0x400:
        raise UnliftedCall("main+0x1cace90: registry full")
    mgr = m.u64(slot)
    m.put(m.main + 0x4763A18 + 8 * n, 8, mgr + 0x20 if mgr else 0)
    m.put(m.main + 0x4765A18, 4, n + 1)


# --- sessions in the manager: id -> S (strong references) ---------------------------------------------

@lifted(0x159E42C)
def emplace_session(m, table, key_ptr, value_ref, *_):
    """emplace(*key_ptr, move(*value_ref)) in the manager's map (node 0x20 {next, hash, u32 id, S}): a
    present key leaves the map and *value_ref as they are."""
    key = m.u32(key_ptr)
    if _find(m, table, key, 4):
        return None
    owner = m.u64(table + 0x38)
    node = m.vcall(owner, 0x10, 0x20, 8)
    if not node:
        raise UnliftedCall("allocator out of memory")
    stack = _tls_stack(m)
    if stack:
        _push(m, stack, owner)
    m.put(node + 0x10, 4, m.u32(key_ptr))
    v = m.u64(value_ref); m.put(value_ref, 8, 0); m.put(node + 0x18, 8, v)
    if stack:
        _pop(m, stack)
    m.put(node, 8, 0); m.put(node + 8, 8, key)
    _insert(m, table, node, key, 0x168E23C)
    return None


@lifted(0x159E220)
def session_slot(m, table, key_ptr, *_):
    """operator[] of the manager's map: the S slot (node +0x18) of *key_ptr, a new node holding none when
    absent."""
    key = m.u32(key_ptr)
    node = _find(m, table, key, 4)
    if node:
        return node + 0x18
    owner = m.u64(table + 0x38)
    node = m.vcall(owner, 0x10, 0x20, 8)
    if not node:
        raise UnliftedCall("allocator out of memory")
    stack = _tls_stack(m)
    if stack:
        _push(m, stack, owner)
    m.put(node + 0x10, 4, m.u32(key_ptr)); m.put(node + 0x18, 8, 0)
    if stack:
        _pop(m, stack)
    m.put(node, 8, 0); m.put(node + 8, 8, key)
    _insert(m, table, node, key, 0x168E23C)
    return node + 0x18


lifted(0x159E024)(lambda m, dst, p, *_: _acquire_into(m, dst, p))
lifted(0x159DFA4)(lambda m, holder, *_: take_release_strong(m, holder))


def _job_links(m):
    """The job graph S's job joins: 0x1193e44 (the engine's job manager, found by its class through the
    static [0x46d9108]) and 0x11fd13c([0x46d4e00], 1)'s phase. The statics on the way are built as the
    game builds them (no __cxa_atexit registration); the engine's job system is not reproduced, so S's
    job gets no links."""
    from pokeldn.sv.battle.engine.statics import _static_chain
    guard = m.u64(m.main + 0x46D6C20)
    if m.u8(guard) & 1 == 0 and m.call(m.main + 0x343CF10, guard) & M32:
        m.call_void(m.main + 0x343CF20, guard)
    m.put(m.u64(m.main + 0x46D6C30), 8, m.u64(m.u64(m.main + 0x46D6C28)))
    _static_chain(m, ((0x46D9100, 0x46D9108), (0x46D3AA8, 0x46D3AB0), (0x46D39B0, 0x46D39B8),
                      (0x46D39C0, 0x46D39C8)))
    guard = m.u64(m.main + 0x46D4DF8)
    if m.u8(guard) & 1 == 0 and m.call(m.main + 0x343CF10, guard) & M32:
        m.call_void(m.main + 0x343CF20, guard)
    m.put(m.u64(m.main + 0x46D4E08), 8, m.u64(m.u64(m.main + 0x46D4E00)))
    return 0, 0


@lifted(0x159DC10)
def new_session(m, mgr, *_):
    """A new session under the manager's next id (u32 +0xb0, then +1 mod 64): S from the manager's
    allocator (0x159e0e0) in its map at +0x28 (lock +0x90). Returns the id."""
    m.call_void(m.main + 0x343C340, mgr + 0x90)
    with m.frame(0x20) as f:
        ident, held, links = f, f + 8, f + 0x10
        m.put(ident, 4, m.u32(mgr + 0xB0))
        m.put(held, 8, 0)
        m.call_void(m.main + 0x159E42C, mgr + 0x28, ident, held)
        if m.u64(held):
            raise UnliftedCall("main+0x159dc10 replacing a live session")
        alloc = m.u64(mgr + 8)
        before, after = _job_links(m)
        m.put(links, 8, before); m.put(links + 8, 8, after)
        s = m.call(m.main + 0x159E0E0, alloc, links, links + 8)
        m.call_void(m.main + 0x159E024, held, s)
        slot = m.call(m.main + 0x159E220, mgr + 0x28, ident)
        m.call_void(m.main + 0x159DFA4, slot)
        x = m.u64(held); m.put(held, 8, 0); m.put(slot, 8, x)
        r = m.u32(ident)
    m.put(mgr + 0xB0, 4, (m.u32(mgr + 0xB0) + 1) & 0x3F)
    m.call_void(m.main + 0x343C360, mgr + 0x90)
    return r


def manager(m):
    """The manager static [[0x46d38e0]] (guard [0x46d38d8], no destructor registered), also noted at
    0x4700900."""
    guard = m.u64(m.main + 0x46D38D8)
    if m.u8(guard) & 1 == 0 and m.call(m.main + 0x343CF10, guard) & M32:
        m.call_void(m.main + 0x343CF20, guard)
    mgr = m.u64(m.u64(m.main + 0x46D38E0))
    m.put(m.main + 0x4700900, 8, mgr)
    return mgr


@lifted(0x159DBA0)
def create_session_id(m, *_):
    """A new session in the manager (0x159dc10); returns its id."""
    return _tail(m, m.main + 0x159DC10, manager(m))


lifted(0x16D9BDC)(lambda m, *_: _class_static(m, 0x4740BA8, 0x4740BB0))


@lifted(0x2A0F878)
def session_class(m, *_):
    """vf 0 of S's +0x28 part: its class static 0x4740ba8."""
    m.call_void(m.main + 0x16D9BDC)
    return m.main + 0x4740BA8


@lifted(0x1891440)
def start_session_by_id(m, mgr, ident, opt, *_):
    """Under the manager's lock: the session with this id, if any, starts (0x18915c4 with the manager's
    communication holder +0xb8 and a copy of the optional session handle)."""
    m.call_void(m.main + 0x343C340, mgr + 0x90)
    node = _find(m, mgr + 0x28, ident & M32, 4)
    if node:
        s = m.u64(node + 0x18)
        with m.frame(0x20) as o2:
            m.call_void(m.main + 0x1891340, o2, opt)
            m.call_void(m.main + 0x18915C4, s, mgr + 0xB8, o2)
            if m.u8(o2):
                raise UnliftedCall("main+0xc8e444: an optional session handle")
    m.call_void(m.main + 0x343C360, mgr + 0x90)


@lifted(0x1891274)
def start_session_id(m, ident, opt, *_):
    """The session start by id (a Lua binding's native): 0x1891440 on the manager."""
    mgr = manager(m)
    with m.frame(0x20) as o2:
        m.call_void(m.main + 0x1891340, o2, opt)
        m.call_void(m.main + 0x1891440, mgr, ident, o2)
        if m.u8(o2):
            raise UnliftedCall("main+0xc8e444: an optional session handle")


# --- the session: the manager, S, the raid start's setup fields, the start ----------------------------

# The raid start's writes into the setup through its Lua bindings (Lua 0.4455 -> 0.4893 -> 0.4945; the
# setup's bindings 0x441cc10..0x441d958): fields equal in the ch1, ch2, ch5 and ch6 consoles' setups.
# (offset, size, value, the binding that writes it when known)
RAID_SETUP = (
    (0x2C, 4, 0x2713, "fD8E195CA"), (0x34, 4, 2, "f62A8F7B6"), (0x8C, 1, 1, None), (0x8D, 1, 5, None),
    (0x90, 4, 2, "f67B478AC"), (0x94, 4, 0, "f4891D27C"), (0x99, 1, 0, "fD185AB33"), (0x9B, 1, 1, "fD185AB33"),
    (0x488, 1, 1, "f9BFB0E4D"), (0x489, 1, 1, "f6A5B5505"), (0x498, 8, 0x400, "f4FD8C069"),
    (0x4B0, 4, 12000, "f52BC8073"), (0x4B4, 4, 400, "f8E89EF89"), (0x4DD, 1, 1, None), (0x4DF, 1, 1, None),
    (0x4EC, 4, 0, "f11DA56AD"), (0x706, 1, 1, None), (0x714, 1, 8, "fBF4C224C"),
)


def raid_setup(m, alloc, setup, bootstrap, partners, slot=None):
    """The raid start's setup fields: RAID_SETUP; per participant p and entry e (0x1c bytes from +0x18 of
    +0xc8 + 0xc0 * p) u16 +0x10 30 (26 for the boss, p = 1) and u8 +0xd 1 for the host's entries 1..5 and
    the guest's 0..5; from the bootstrap (0xaa0 plaintext) the RaidPoint's randSeed at +0x718, its
    raidTimeData limits at +0x48a/+0x48c/+0x48e (300, 0, 60 when inactive), its boss action profile as
    u16 at +0x514, and the five party holders (our Pokemon, the boss, the guest, the two NPC partners'
    records from `partners`). `slot` replaces RAID_SETUP's console slot u32 +0x90 (0: the host's)."""
    for off, size, value, _ in RAID_SETUP:
        m.put(setup + off, size, value)
    if slot is not None:
        m.put(setup + 0x90, 4, slot)
    for p in range(5):
        for e in range(6):
            a = setup + 0xC8 + 0xC0 * p + 0x18 + 0x1C * e
            m.put(a + 0x10, 2, 26 if p == 1 else 30)
            if (p == 0 and e) or p == 2:
                m.put(a + 0xD, 1, 1)
    point = 5 * PARTY_RECORD
    m.put(setup + 0x718, 8, int.from_bytes(bootstrap[point + 0x3D8:point + 0x3E0], "little"))
    active, game, client, command = struct.unpack_from("<4I", bootstrap, point + 0x30)
    if not active & 0xFF:                   # the Lua timer initializer's group defaults (docs/sv_raid.md)
        game, client, command = 300, 0, 60
    m.put(setup + 0x48A, 2, game); m.put(setup + 0x48C, 2, client); m.put(setup + 0x48E, 2, command)
    for i, value in enumerate(struct.unpack_from("<37I", bootstrap, point + 0x4C)):
        m.put(setup + 0x514 + 2 * i, 2, value)
    records = [bootstrap[0:PARTY_RECORD], bootstrap[4 * PARTY_RECORD:5 * PARTY_RECORD],
               bootstrap[PARTY_RECORD:2 * PARTY_RECORD]] + list(partners)
    for i, rec in enumerate(records):
        m.put(setup + 0xA0 + 8 * i, 8, build_party(m, alloc, rec))


def _session_of(m, mgr, ident):
    from pokeldn.sv.battle.engine.steps import _find
    node = _find(m, mgr + 0x28, ident, 4)
    return m.u64(node + 0x18) if node else 0


def build_session(m, alloc, bootstrap, partners, slot=None):
    """The battle session as the console makes it: the session manager (0x168ca58, at boot), a session
    S under it (0x159dba0; S's job is bare_job: the engine's job scheduler is not reproduced),
    the raid start's setup fields (raid_setup), the session start (0x1891274: N+0x48, N and what hangs
    off them). Returns N, ready for its start states (0x1269824)."""
    from pokeldn.sv.battle.machine import FUNCTIONS
    m.call_void(m.main + 0x168CA58, alloc)

    def job(m, owner, *_):
        p = bare_job(m, owner)
        m.put(m.x8, 8, p)
        return p
    FUNCTIONS[0x159F018] = job
    try:
        ident = m.call(m.main + 0x159DBA0)
    finally:
        del FUNCTIONS[0x159F018]
    mgr = manager(m)
    s = _session_of(m, mgr, ident)
    raid_setup(m, alloc, m.u64(s + 0xE0), bootstrap, partners, slot)
    with m.frame(0x20) as opt:
        m.put(opt, 8, 0)
        m.call_void(m.main + 0x1891274, ident, opt)
    return m.u64(s + 0x48)


def start_states(m, n, steps=None):
    """N's start states (0x1269824 from state 0) until its raid step machine (N+0x60) has run the three
    build steps; steps(name) is called after each of 0x2891748 (in state 0), 0x2892ac0, 0x2d381a4 and
    0x2892dd4."""
    with m.frame(0x10) as st:
        m.put(st, 4, 0)
        while m.u32(st) < 3:
            m.call(m.main + 0x1269824, n, st)
            if m.u32(st) == 1 and steps:
                steps("0x2891748")
        names = {2: "0x2892ac0", 3: "0x2d381a4", 4: "0x2892dd4"}
        while m.u32(n + 0x60) < 4:
            m.call(m.main + 0x1269824, n, st)
            if steps and m.u32(n + 0x60) in names:
                steps(names[m.u32(n + 0x60)])
