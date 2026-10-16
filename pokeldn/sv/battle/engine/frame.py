"""The server's per-frame machine (vtable 0x4493530, vf 0x68 0xf6d538): its first-frame set-up, the battle
timer, the boss's list and its messages (docs/sv_raid.md, The server's flow)."""

from pokeldn.sv.battle.engine.network import _create_aligned
from pokeldn.sv.battle.engine.requests import _add_ref
from pokeldn.sv.battle.engine.steps import _free, _pop, _push, _tls_stack
from pokeldn.sv.battle.machine import UnliftedCall, lifted

M64 = 0xFFFFFFFFFFFFFFFF

SCHEDULER = 0x14799EC           # the machine's scheduler (scheduler.py)
POST = 0x1479B10                # a request handle appended to the scheduler's posted vector
REQUEST = 0x1479F64             # a posted request's constructor: {counter, hash}, payload, size
INCOMING = 0xE0F440             # the server's incoming link of a slot (links.py)
READER = 0xF6DF44               # one per-slot reader's step (reader.py)

LIST = 0x80                     # the boss's list: N +0, module +8, the action profile +0x10 (0x4a bytes),
PROFILE = 0x4A                  # kinds u8 +0x5c + 8i, values u32 +0x60 + 8i, count u32 +0x7c


def _drop(m, o):
    """ReleaseReference on o's control block ([+0x30], u16 +0x1a): the last one clears +0x10 and ends in
    o's vf 0x50."""
    c = m.u64(o + 0x30)
    n = m.u16(c + 0x1A)
    if n == 0:
        raise UnliftedCall("abort: ReleaseReference")
    m.put(c + 0x1A, 2, n - 1)
    if n == 1:
        m.put(c + 0x10, 8, 0)
        m.vcall_void(o, 0x50)


def _drop_at(m, holder):
    o = m.u64(holder)
    if o:
        _drop(m, o)


def _hold(m, out, o):
    """*out = o with a reference taken (AddReference when o is not null)."""
    m.put(out, 8, o)
    if o:
        _add_ref(m, o)
    return o


def _create(m, alloc, key, pp, psize, ctor):
    """Create<message>: 0x50 bytes from `alloc` (vf 0x10, alignment 8) with `alloc` on the thread's object
    stack, built by ctor(o, key, *pp, u32 *psize); +0x18 0x80050, +8 the allocator, +0x10 itself."""
    def build(o):
        m.call_void(m.main + ctor, o, key, m.u64(pp), m.u32(psize))
    return _create_aligned(m, alloc, 0x50, 8, build)


def _request(m, fac, payload, digest, size, maker):
    """A request of type hash `digest` from the factory `fac` (counter u64 +0x40, raised; allocator +8):
    maker(alloc, &{counter, hash}, &payload, &size) into *x8."""
    out = m.x8
    n = m.u64(fac + 0x40)
    m.put(fac + 0x40, 8, n + 1)
    with m.frame(0x20) as f:
        m.put(f, 8, size)
        m.put(f + 8, 8, payload)
        m.put(f + 0x10, 8, n)
        m.put(f + 0x18, 8, digest)
        return m.call_sret(m.main + maker, out, m.u64(fac + 8), f + 0x10, f + 8, f)


def _post(m, o, maker, payload):
    """A request made by `maker` from the machine's scheduler with `payload`, posted (0x1479b10) and its
    handle released."""
    sched = m.call(m.main + SCHEDULER, o)
    with m.frame(0x10) as h:
        m.call_sret(m.main + maker, h, sched, payload)
        m.call_void(m.main + POST, o, h)
        _drop_at(m, h)


# --- the request makers ---------------------------------------------------------------------------------

@lifted(0xF70B18)
def create_request_f70b18(m, alloc, key, pp, psize, *_):
    return _create(m, alloc, key, pp, psize, REQUEST)


@lifted(0xF71EF0)
def create_request_f71ef0(m, _unused, alloc, key, pp, psize, *_):
    return _create(m, alloc, key, pp, psize, REQUEST)


@lifted(0x147A5CC)
def create_request_147a5cc(m, alloc, key, pp, psize, *_):
    return _create(m, alloc, key, pp, psize, REQUEST)


@lifted(0xF70994)
def make_setup_request(m, alloc, key, pp, psize, *_):
    """*x8 = a referenced request (0xf70b18)."""
    out = m.x8
    return _hold(m, out, m.call(m.main + 0xF70B18, alloc, key, pp, psize))


@lifted(0xF71C38)
def make_raid_request(m, alloc, key, pp, psize, *_):
    """*x8 = a referenced request (0xf71ef0)."""
    out = m.x8
    with m.frame(0x10) as f:
        return _hold(m, out, m.call(m.main + 0xF71EF0, f, alloc, key, pp, psize))


@lifted(0x147A508)
def make_request_147a508(m, alloc, key, pp, psize, *_):
    """*x8 = a referenced request (0x147a5cc)."""
    out = m.x8
    return _hold(m, out, m.call(m.main + 0x147A5CC, alloc, key, pp, psize))


@lifted(0xF71B74)
def make_message(m, alloc, header, pp, psize, *_):
    """*x8 = a referenced server message (0x2016148)."""
    out = m.x8
    return _hold(m, out, m.call(m.main + 0x2016148, alloc, header, pp, psize))


@lifted(0xF7093C)
def setup_request(m, fac, payload, *_):
    """Wild::Setup's request (hash 0x2e9e7a3009002c36): the timer pointer at `payload`, 8 bytes."""
    return _request(m, fac, payload, 0x2E9E7A3009002C36, 8, 0xF70994)


@lifted(0xF71928)
def raid_request(m, fac, payload, *_):
    """A raid action's request (hash 0x5c307d44ea569b63): 0x60 bytes at `payload`."""
    return _request(m, fac, payload, 0x5C307D44EA569B63, 0x60, 0xF71C38)


@lifted(0x147A4B0)
def request_147a4b0(m, fac, payload, *_):
    """A request of hash 0x7c68fedb79ab6396 with 4 bytes at `payload`."""
    return _request(m, fac, payload, 0x7C68FEDB79AB6396, 4, 0x147A508)


@lifted(0x147A408)
def post_147a408(m, o, *_):
    """Posts 0x147a4b0's request; its 4-byte payload is a stack slot the game never writes (zero here)."""
    with m.frame(0x10) as p:
        m.put(p, 8, 0)
        _post(m, o, 0x147A4B0, p)


# --- the first frame ------------------------------------------------------------------------------------

@lifted(0xF6F870)
def machine_server(m, o, *_):
    """The server: [[o+0x40]+0x18]."""
    return m.u64(m.u64(o + 0x40) + 0x18)


@lifted(0x13F5F00)
def server_state(m, server, *_):
    return m.u64(server + 0x468)


@lifted(0x147A7F8)
def clear_links(m, server, *_):
    """For slots 0 to 4: the slot's outgoing link (0x113d184) cleared (0x147ac10), then its incoming link's
    queue [link+0x48]+0x40 cleared (0xe0f5f8)."""
    with m.frame(0x10) as h:
        for slot in range(5):
            m.call_sret(m.main + 0x113D184, h, server, slot)
            o = m.u64(h)
            if o:
                m.call_void(m.main + 0x147AC10, o)
                _drop(m, o)
            m.call_sret(m.main + INCOMING, h, server, slot)
            o = m.u64(h)
            if o:
                m.call_void(m.main + 0xE0F5F8, m.u64(o + 0x48) + 0x40)
                _drop(m, o)


@lifted(0xF714EC)
def construct_reader(m, o, slot, ctx, *_):
    """A per-slot reader (vtable 0x4493668, 0x78 bytes): the slot u32 at +0x38, the five context words
    (scheduler, 0x1479924, N, module, server) at +0x10..+0x30, the state +0x50 cleared (0xfa98a4)."""
    m.put(o + 8, 2, 0)
    m.put(o, 8, m.main + 0x4493668)
    m.put(o + 0x10, 8, 0); m.put(o + 0x18, 8, 0)
    m.put(o + 0x30, 8, 0)
    m.put(o + 0x38, 4, slot)
    m.put(o + 0x40, 8, 0)
    m.put(o + 0x20, 8, 0); m.put(o + 0x28, 8, 0)
    m.put(o + 0x48, 4, 0)
    m.call_void(m.main + 0xFA98A4, o + 0x50)
    for k in range(5):
        m.put(o + 0x10 + 8 * k, 8, m.u64(ctx + 8 * k))


def _owned(m, alloc, size, build):
    """*x8 = {object, alloc, size, 8}: `size` bytes from alloc's vf 0x10 built with alloc on the thread's
    object stack; all zero when the allocation fails."""
    out = m.x8
    o = m.vcall(alloc, 0x10, size, 8)
    if not o:
        m.write(out, bytes(0x20))
        return out
    stack = _tls_stack(m)
    _push(m, stack, alloc)
    build(o)
    m.put(out, 8, o); m.put(out + 8, 8, alloc)
    m.put(out + 0x10, 8, size); m.put(out + 0x18, 8, 8)
    _pop(m, stack)
    return out


@lifted(0xF713D0)
def create_reader(m, alloc, slot, ctx, *_):
    return _owned(m, alloc, 0x78, lambda o: m.call_void(m.main + 0xF714EC, o, m.u32(slot), ctx))


def _build_list(m, o, n, module):
    m.put(o, 8, n); m.put(o + 8, 8, module)
    m.write(o + 0x10, bytes(PROFILE))
    for k in range(3):
        m.put(o + 0x5C + 8 * k, 1, 0); m.put(o + 0x60 + 8 * k, 4, 0)
    m.put(o + 0x74, 1, 0); m.put(o + 0x78, 4, 0)
    m.write(o + 0x10, m.read(m.u64(module + 0x310) + 0x1C, PROFILE))
    for k in range(3):
        m.put(o + 0x5C + 8 * k, 1, 0); m.put(o + 0x60 + 8 * k, 4, 0)
    m.put(o + 0x74, 1, 0); m.put(o + 0x78, 8, 0)


@lifted(0xF71060)
def create_list(m, alloc, n, module, *_):
    """The boss's list (0x80 bytes): N, the module, a copy of the RaidPoint's action profile
    ([module+0x310]+0x1c, 0x4a bytes) and an empty list of four."""
    return _owned(m, alloc, LIST, lambda o: _build_list(m, o, m.u64(n), m.u64(module)))


@lifted(0xF71564)
def delete_reader(m, deleter, o, *_):
    """o destroyed (vf 0) and freed through the deleter {alloc, size, align}."""
    _free(m, o, m.u64(deleter), m.u64(deleter + 8), m.u64(deleter + 0x10), dtor=0)


@lifted(0xF70C60)
def reset_list(m, holder, new, *_):
    """*holder = new; the old object freed through the deleter at holder+8 {alloc, size, align}."""
    old = m.u64(holder)
    m.put(holder, 8, new)
    if old:
        _free(m, old, m.u64(holder + 8), m.u64(holder + 0x10), m.u64(holder + 0x18))


@lifted(0xF711EC)
def make_readers(m, o, *_):
    """Five per-slot readers (0xf713d0) at o+0x58 + 0x20 slot, each {reader, deleter}; an old reader is
    deleted (0xf71564)."""
    with m.frame(0x50) as f:
        ctx, out, slot = f, f + 0x28, f + 0x48
        m.put(ctx, 8, m.call(m.main + SCHEDULER, o))
        m.put(ctx + 8, 8, m.call(m.main + 0x1479924, o))
        c = m.u64(o + 0x40)
        m.put(ctx + 0x10, 8, m.u64(c + 8))
        m.put(ctx + 0x18, 8, m.u64(c + 0x10))
        m.put(ctx + 0x20, 8, m.call(m.main + 0xF6F870, o))
        for k in range(5):
            m.put(slot, 4, k)
            m.call_sret(m.main + 0xF713D0, out, m.u64(o + 8), slot, ctx)
            r = m.u64(out)
            m.put(out, 8, 0)
            e = o + 0x58 + 0x20 * k
            old = m.u64(e)
            m.put(e, 8, r)
            if old:
                m.call_void(m.main + 0xF71564, e + 8, old)
            m.write(e + 8, m.read(out + 8, 0x18))


@lifted(0xF70864)
def post_setup(m, o, *_):
    """With a battle time limit (N+0x8a), the battle timer [ctx+0x38] made (0xf70a58); Wild::Setup posted
    (0xf7093c) with the timer's pointer, or 0 without a limit."""
    with m.frame(0x10) as p:
        m.put(p, 8, 0)
        c = m.u64(o + 0x40)
        limit = m.u16(m.u64(c + 8) + 0x8A)
        if limit:
            m.call_void(m.main + 0xF70A58, m.u64(c + 0x38), limit)
            m.put(p, 8, m.u64(m.u64(o + 0x40) + 0x38))
        _post(m, o, 0xF7093C, p)


@lifted(0xF704A0)
def make_list(m, o, *_):
    """The boss's list (0xf71060) into o+0xf8 with its deleter at +0x100."""
    c = m.u64(o + 0x40)
    with m.frame(0x30) as f:
        n, module, out = f, f + 8, f + 0x10
        m.put(n, 8, m.u64(c + 8)); m.put(module, 8, m.u64(c + 0x10))
        m.call_sret(m.main + 0xF71060, out, m.u64(o + 8), n, module)
        new = m.u64(out)
        m.put(out, 8, 0)
        m.call_void(m.main + 0xF70C60, o + 0xF8, new)
        m.write(o + 0x100, m.read(out + 8, 0x18))
        m.call_void(m.main + 0xF70C60, out, 0)


# --- the boss's list --------------------------------------------------------------------------------------

@lifted(0xF70AC8)
def list_actions(m, lst, out, *_):
    """The list's four actions and count (+0x5c..+0x7f, 0x24 bytes) to out."""
    m.put(out + 0x20, 4, 0)
    m.write(out, m.read(lst + 0x5C, 0x20))
    m.put(out + 0x20, 4, m.u32(lst + 0x7C))


@lifted(0x2016298)
def set_list_actions(m, lst, src, *_):
    """0x24 bytes of actions and count from src to the list's +0x5c."""
    m.write(lst + 0x5C, m.read(src, 0x20))
    m.put(lst + 0x7C, 4, m.u32(src + 0x20))


@lifted(0x2016290)
def take_list_message(m, o, src, *_):
    """vf 0x78: a 0x51 message's body into the machine's boss list [o+0xf8]."""
    set_list_actions(m, m.u64(o + 0xF8), src)


@lifted(0xF71980)
def push_incoming(m, link, src, *_):
    """The message *src onto the link's queue [link+0x48] (0x113d5e0) through a referenced copy."""
    q = m.u64(link + 0x48)
    with m.frame(0x10) as c:
        _hold(m, c, m.u64(src))
        m.call_void(m.main + 0x113D5E0, q, c)
        _drop_at(m, c)


# --- the readers' map: slot -> reference, a libc++ tree with nodes of 0x38 bytes from [tree+0x10] ----------

@lifted(0xF6DCE4)
def free_tree(m, tree, node, *_):
    """The subtree at node freed, children first."""
    if not node:
        return
    m.call_void(m.main + 0xF6DCE4, tree, m.u64(node))
    m.call_void(m.main + 0xF6DCE4, tree, m.u64(node + 8))
    alloc = m.u64(tree + 0x10)
    if m.vcall(alloc, 0xF8) & 1 and m.s(m.call(m.main + 0xB4E600) + 0x12C8, 4) >= 1:
        m.call_void(m.main + 0xB48FE8, alloc, node, 0x38, 8)
    else:
        m.vcall_void(alloc, 0x18, node, 0x38, 8)


@lifted(0x201698C)
def construct_entry(m, holder, value, args, *_):
    """A node's value with the allocator [holder] on the thread's object stack: the u8 key **args at +0,
    an empty reference (u64 +8, u32 +0x10)."""
    stack = _tls_stack(m)
    if stack:
        _push(m, stack, m.u64(holder))
    m.put(value, 1, m.u8(m.u64(args)))
    m.put(value + 8, 8, 0)
    m.put(value + 0x10, 4, 0)
    if stack:
        _pop(m, stack)


@lifted(0x20168C0)
def make_node(m, tree, args, *_):
    """*x8 = {node, &allocator, constructed 1}: a 0x38-byte node from [tree+0x10], its value made
    (0x201698c)."""
    out = m.x8
    holder = tree + 0x10
    node = m.vcall(m.u64(holder), 0x10, 0x38, 8)
    if not node:
        raise UnliftedCall("abort: allocation failed in the readers' map")
    m.put(out, 8, node); m.put(out + 8, 8, holder)
    m.call_void(m.main + 0x201698C, holder, node + 0x20, args)
    m.put(out + 0x10, 1, 1)
    return out


@lifted(0x2016938)
def link_node(m, tree, parent, slot, node, *_):
    """node linked under parent at slot; the begin node moved to a new leftmost; the tree rebalanced
    (0xf108e0) and its size +0x30 raised."""
    m.put(node, 8, 0); m.put(node + 8, 8, 0)
    m.put(node + 0x10, 8, parent)
    m.put(slot, 8, node)
    left = m.u64(m.u64(tree))
    if left:
        m.put(tree, 8, left)
    m.call_void(m.main + 0xF108E0, m.u64(tree + 8), m.u64(slot))
    m.put(tree + 0x30, 8, m.u64(tree + 0x30) + 1)


@lifted(0xF71AC0)
def tree_slot(m, tree, key, args, *_):
    """The node of the u8 *key (node +0x20), made (0x20168c0) and linked (0x2016938) when missing."""
    slot = tree + 8
    parent = m.u64(slot)
    if not parent:
        parent = slot
    else:
        k = m.u8(key)
        node = parent
        while True:
            nk = m.u8(node + 0x20)
            if nk > k:
                slot = node
                parent = node
                if not m.u64(node):
                    break
                node = m.u64(node)
            elif nk < k:
                slot = node + 8
                parent = node
                if not m.u64(node + 8):
                    break
                node = m.u64(node + 8)
            else:
                break
    found = m.u64(slot)
    if found:
        return found
    with m.frame(0x10) as h:
        m.call_sret(m.main + 0x20168C0, h, tree, args)
        node = m.u64(h)
    m.call_void(m.main + 0x2016938, tree, parent, slot, node)
    return node


# --- the machine ------------------------------------------------------------------------------------------

def _first_frame(m, o):
    """Before the module has started ([[module+0x1f0]+8]): every link cleared (0x147a7f8), the server's state
    reset (0xfaef9c on [server+0x468]), the readers, the timer with Wild::Setup, and the boss's list made."""
    m.call_void(m.main + 0x147A7F8, m.call(m.main + 0xF6F870, o))
    m.call_void(m.main + 0xFAEF9C, m.call(m.main + 0x13F5F00, m.call(m.main + 0xF6F870, o)))
    m.call_void(m.main + 0xF711EC, o)
    m.call_void(m.main + 0xF70864, o)
    m.call_void(m.main + 0xF704A0, o)
    return 1


def _time_up(m, o, c):
    """The battle timer has run out: the result 0 decided by 2 kept in N (0xe7d570), the 0x29 body made
    (0xe7d4c8), then ExitBattleEnd with message 0x2b (a raid, setup +0x499 bit 2) or AddExpBattleEnd
    posted (docs/sv_raid.md, The battle timer running out)."""
    m.call_void(m.main + 0xE7D570, m.u64(c + 8), 0, 2, 0)
    m.call_void(m.main + 0xE7D4C8, m.call(m.main + 0xF6F870, o))
    raid = m.u8(m.u64(m.u64(m.u64(o + 0x40) + 8) + 0x38) + 0x499) & 4
    with m.frame(0x10) as p:
        if raid:
            m.put(p, 4, 0x2B)
            _post(m, o, 0x201602C, p)
        else:
            m.put(p, 1, 0)
            _post(m, o, 0x16E5230, p)
    return 1


def _send_timed(m, o, copy):
    """A timed action fired on the list's copy: its actions sent as message 0x51 (0xf71b74) into the
    incoming link of the server's own slot (0xe0f440, 0xf71980); +0x118 cleared."""
    c = m.u64(o + 0x40)
    with m.frame(0x80) as f:
        body, sizep, msgref, link, made, header = f, f + 0x48, f + 0x40, f + 0x50, f + 0x58, f + 0x60
        m.write(header, bytes(0x20))
        m.put(header + 0x18, 1, 5)
        m.put(header, 4, 0x51)
        m.put(header + 0x19, 1, m.call(m.main + 0x149FE8C, m.u64(c + 8)))
        m.write(body, bytes(0x24))
        m.call_void(m.main + 0xF70AC8, copy, body)
        m.put(sizep, 8, 0x24)
        m.put(link, 8, body)
        m.call_sret(m.main + 0xF71B74, made, m.u64(o + 8), header, link, sizep)
        server = m.call(m.main + 0xF6F870, o)
        slot = m.call(m.main + 0x149FE8C, m.u64(m.u64(o + 0x40) + 8)) & 0xFF
        m.call_sret(m.main + INCOMING, link, server, slot)
        _hold(m, msgref, m.u64(made))
        m.call_void(m.main + 0xF71980, m.u64(link), msgref)
        _drop_at(m, msgref)
        _drop_at(m, link)
        m.put(o + 0x118, 1, 0)
        _drop_at(m, made)
    return 0


def _timed_check(m, o):
    """The profile's time triggers (0xf6dd84) on a copy of the boss's list, while the list is empty: 0 when
    it holds actions or a trigger fired, None to go on to the readers."""
    c = m.u64(o + 0x40)
    n = m.u64(c + 8)
    if not m.u8(m.u64(n + 0x38) + 0x499) & 4 or not m.u8(m.u64(c + 0x38) + 0x18):
        return None
    if m.u32(m.u64(o + 0xF8) + 0x7C):
        return 0
    module = m.u64(c + 0x10)
    with m.frame(LIST) as copy:
        m.write(copy, bytes(LIST))
        m.put(copy, 8, n); m.put(copy + 8, 8, module)
        m.write(copy + 0x10, m.read(m.u64(module + 0x310) + 0x1C, PROFILE))
        if m.call(m.main + 0xF6DD84, copy, m.u64(c + 0x38)) & 1:
            return _send_timed(m, o, copy)
    return None


def _post_raid_action(m, o, lst):
    """The boss's list posted as a raid action (0xf71928): state 2, or 0 when its first kind is 1 (a
    shield), the timer, the list, its actions as request block actions (0x114fb2c); +0x118 set."""
    with m.frame(0xA0) as f:
        words, payload = f, f + 0x40
        m.write(words, bytes(0x40))
        n = m.call(m.main + 0x114FB2C, lst, words) & 0xFFFFFFFF
        m.write(payload, bytes(0x60))
        m.put(payload + 0x18, 4, n)
        m.put(payload + 8, 8, m.u64(m.u64(o + 0x40) + 0x38))
        m.put(payload + 0x10, 8, lst)
        if m.u8(lst + 0x5C) != 1:
            m.put(payload, 4, 2)
        if n and not n & 0x80000000:
            for i in range(n):
                m.call(m.main + 0xF6FC54, payload + 0x20 + 0x10 * i, words + 0x10 * i)
        _post(m, o, 0xF71928, payload)
    m.put(o + 0x118, 1, 1)
    return 1


def _step_readers(m, o):
    """Each slot's reader stepped (0xf6df44); a reader answering 3 has its +0x40 reference kept in a map
    by slot, dropped at the end. 1 when any reader answered other than 0 or 5."""
    any_ = 0
    with m.frame(0x50) as f:
        tree, key, args = f, f + 0x38, f + 0x40
        m.put(tree, 8, tree + 8); m.put(tree + 8, 8, 0)
        m.put(tree + 0x10, 8, m.u64(o + 8)); m.put(tree + 0x18, 8, 0x0AAAAAAAAAAAAAAA)
        m.put(tree + 0x20, 8, 0); m.put(tree + 0x28, 4, 0); m.put(tree + 0x30, 8, 0)
        m.put(key, 1, 0)
        while True:
            reader = m.u64(o + 0x58 + 0x20 * m.u8(key))
            r = m.call(m.main + READER, reader) & 0xFF
            if r not in (0, 5):
                if r == 3:
                    m.put(args, 8, key)
                    node = m.call(m.main + 0xF71AC0, tree, key, args)
                    m.call(m.main + 0xF6FC54, node + 0x28, reader + 0x40)
                any_ = 1
            k = (m.u8(key) + 1) & 0xFF
            m.put(key, 1, k)
            if k >= 5:
                break
        m.call_void(m.main + 0xF6DCE4, tree, m.u64(tree + 8))
    return any_


@lifted(0xF6D538)
def machine_frame(m, o, *_):
    """The per-frame machine (vf 0x68): the first frame's set-up; the battle timer read (0xf91070) and its
    time-up; while the job graph G=[N+0xa8] has +0xe0 set and +0x118 is set, the profile's time triggers;
    a boss's list holding actions posted as a raid action; otherwise the five readers stepped."""
    c = m.u64(o + 0x40)
    module = m.u64(c + 0x10)
    if not m.u8(m.u64(module + 0x1F0) + 8):
        return _first_frame(m, o)
    timer = m.u64(c + 0x38)
    if timer:
        pc = m.u64(module + 0x290)
        limit = m.u16(m.u64(pc + 0x10) + 0x8A)
        if limit:
            offset = m.s(m.u64(m.u64(pc + 8) + 0x1B0) + 8, 2) & M64
            r = m.call(m.main + 0xF91070, timer, limit, offset) & M64
            c = m.u64(o + 0x40)
            if r == 0 or r >> 63:
                return _time_up(m, o, c)
    g = m.u64(m.u64(c + 8) + 0xA8)
    if g:
        _add_ref(m, g)
    if m.u8(g + 0xE0):
        armed = m.u8(o + 0x118)
        _drop(m, g)
        if armed:
            r = _timed_check(m, o)
            if r is not None:
                return r
    else:
        _drop(m, g)
    if m.u8(m.u64(m.u64(m.u64(o + 0x40) + 8) + 0x38) + 0x499) & 4:
        lst = m.u64(o + 0xF8)
        if m.u8(lst + 0x5C):
            return _post_raid_action(m, o, lst)
    return _step_readers(m, o)


# --- the machine's vf 0x70: two messages told apart by the u64 at +0x40 ------------------------------------

@lifted(0x2016A80)
def create_request_2016a80(m, alloc, key, pp, psize, *_):
    return _create(m, alloc, key, pp, psize, REQUEST)


@lifted(0x20166B4)
def make_request_20166b4(m, alloc, key, pp, psize, *_):
    """*x8 = a referenced request (0x2016a80)."""
    out = m.x8
    return _hold(m, out, m.call(m.main + 0x2016A80, alloc, key, pp, psize))


@lifted(0x201665C)
def payload_request(m, fac, payload, *_):
    """A request of hash 0x809e7c342dc76a3c with the 0x2588-byte payload at `payload`."""
    return _request(m, fac, payload, 0x809E7C342DC76A3C, 0x2588, 0x20166B4)


def _is_a(m, base, type_id):
    """Whether the type chain from base's vf 0 (a list linked through +0) holds `type_id`."""
    node = m.call(m.u64(m.u64(base)), base)
    t = m.call(m.main + type_id)
    while node:
        if node == t:
            return True
        node = m.u64(node)
    return False


@lifted(0x20162BC)
def take_message(m, o, ref, *_):
    """vf 0x70: a message of key 0xde3856ecc4fe200c (type 0x200d8b8) posted as a ServerCommand of one
    kind-14 action (0xf6ffb8), one of key 0x0ab4bce035f3012b (type 0x1902f04) as a job of its
    0x2588-byte payload (+0x48, 0x201665c)."""
    msg = m.u64(ref)
    if not msg:
        return
    key = m.u64(msg + 0x40)
    if key == 0xDE3856ECC4FE200C:
        if not _is_a(m, msg + 0x28, 0x200D8B8):
            return
        with m.frame(0x240) as b:
            m.write(b, bytes(0x240))
            m.put(b + 0x238, 4, 0x1F)
            m.put(b, 8, m.u8(msg + 0x49) << 12 | m.u8(msg + 0x48) << 4 | 0xE)
            m.put(b + 0x230, 1, 1)
            _post(m, o, 0xF6FFB8, b)
    elif key == 0x0AB4BCE035F3012B:
        if not _is_a(m, msg + 0x28, 0x1902F04):
            return
        with m.frame(0x2590) as b:
            m.call_void(m.main + 0x12702C0, b)
            m.write(b, m.read(msg + 0x48, 0x2588))
            _post(m, o, 0x201665C, b)
