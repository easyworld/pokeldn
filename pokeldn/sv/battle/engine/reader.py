"""The server's per-slot readers (0xf6df44): requests, commands gathered into request blocks, answered pairs
erased (docs/sv_raid.md, The server's flow)."""

from pokeldn.sv.battle.engine.requests import _add_ref, _release, posted
from pokeldn.sv.battle.engine.steps import _pop, _push, _tls_stack
from pokeldn.sv.battle.machine import UnliftedCall, lifted

REQUEST = 0x935ACB1823E1803F    # hash of an 8-byte request payload {u32 slot, u32 kind} (0xf6f6d8)
BLOCK = 0xAE1B39FCCFD09053      # hash of a 0x240-byte request block payload (0xf6ffb8)
WAIT = (5, 0xD, 0xB, 0xF, 9, 7, 0x21, 3, 0x23, 0x15, 0x17, 0x19, 0x13, 0x47, 0x1F, 0x1D)   # 0xf6e22c..0xf6e368
PAIRS = ((0x15, 0x16), (0x23, 0x24), (0x11, 0x12), (0x13, 0x14), (0x17, 0x18), (0x19, 0x1A), (0x1B, 0x1C),
         (0x1D, 0x1E), (0x25, 0x26), (0x1F, 0x20))                                              # 0xf6e410..
SIDES = {                       # a slot's side by battle mode: 0x3c6a450, 0x3c6a455, 0x3c6a45a
    0: (0, 1, 2, 2, 2), 1: (0, 1, 0, 1, 2), 2: (0, 1, 0, 0, 0)}
RANKS = (5, 10, 15, 20, 25, 30)                     # 0x3c69d1c


def _ref(m, o):
    """AddReference on o; x0 as the game leaves it: the resolved object on the first reference, else o."""
    c = m.u64(o + 0x30)
    first = m.u64(c + 0x10) and m.u16(c + 0x1A) == 0
    _add_ref(m, o)
    return m.u64(c + 8) if first else o


def _make(m, stack, alloc, key, payload, size):
    """A 0x50-byte posted request from alloc with alloc on the thread's object stack: 0x1479f64 with the
    {counter, hash} pair, the payload pointer and its u32 size, then +0x18 0x80050, +8 alloc, +0x10 itself."""
    _push(m, stack, alloc)
    o = m.vcall(alloc, 0x10, 0x50, 8)
    if not o:
        m.vcall_void(alloc, 0xE8)
        raise UnliftedCall("abort: allocation failed in Create")
    m.call_void(m.main + 0x1479F64, o, key, m.u64(payload), m.u32(size))
    m.put(o + 0x18, 4, 0x80050)
    m.put(o + 8, 8, alloc); m.put(o + 0x10, 8, o)
    _pop(m, stack)
    return o


@lifted(0xF70204)
def create_request(m, _x0, alloc, key, payload, size, *_):
    """Create for 0xf7012c, the object stack from the TLS slot 0xf53840 names."""
    stack = m.call(m.main + 0x343DA20, m.u32(m.call(m.main + 0xF53840)))
    return _make(m, stack, alloc, key, payload, size)


@lifted(0xF70514)
def create_block(m, _x0, alloc, key, payload, size, *_):
    """Create for 0xf703c8, the object stack from the TLS slot [0x4765a30] (built under guard 0x4765a38)."""
    return _make(m, _tls_stack(m), alloc, key, payload, size)


def _made(m, out, o):
    m.put(out, 8, o)
    return _ref(m, o) if o else 0


@lifted(0xF7012C)
def make_request(m, alloc, key, payload, size, *_):
    """Writes to x8 a strong reference to a new posted request (0xf70204)."""
    out = m.x8
    with m.frame(0x10) as t:
        return _made(m, out, m.call(m.main + 0xF70204, t, alloc, key, payload, size))


@lifted(0xF703C8)
def make_block(m, alloc, key, payload, size, *_):
    """Writes to x8 a strong reference to a new posted request (0xf70514)."""
    out = m.x8
    with m.frame(0x10) as t:
        return _made(m, out, m.call(m.main + 0xF70514, t, alloc, key, payload, size))


def _post(m, factory, payload, key, size, maker):
    """A factory's request: counter [factory+0x40] taken and raised, {counter, key} with the payload pointer
    and the size, made from the factory's allocator [+8] into x8."""
    out = m.x8
    n = m.u64(factory + 0x40)
    m.put(factory + 0x40, 8, n + 1)
    with m.frame(0x20) as f:
        m.put(f, 8, size)
        m.put(f + 8, 8, payload)
        m.put(f + 0x10, 8, n)
        m.put(f + 0x18, 8, key)
        return m.call_sret(m.main + maker, out, m.u64(factory + 8), f + 0x10, f + 8, f)


@lifted(0xF6F6D8)
def post_request(m, factory, payload, *_):
    """Writes to x8 a request of the 8-byte payload {u32 slot, u32 kind} (hash 0x935acb1823e1803f)."""
    return _post(m, factory, payload, REQUEST, 8, 0xF7012C)


@lifted(0xF6FFB8)
def post_block(m, factory, payload, *_):
    """Writes to x8 a request of a 0x240-byte request block (hash 0xae1b39fccfd09053)."""
    return _post(m, factory, payload, BLOCK, 0x240, 0xF703C8)


@lifted(0xF6F730)
def schedule(m, reader, src, *_):
    """The request *src onto the reader's scheduler [reader+0x18] (0x1479c50), through a counted copy."""
    sched = m.u64(reader + 0x18)
    with m.frame(0x10) as c:
        o = m.u64(src)
        m.put(c, 8, o)
        if o:
            _add_ref(m, o)
        m.call_void(m.main + 0x1479C50, sched, c)
        _release(m, c)


def _post_and_schedule(m, reader, payload, poster):
    with m.frame(0x10) as h:
        m.call_sret(m.main + poster, h, m.u64(reader + 0x10), payload)
        m.call_void(m.main + 0xF6F730, reader, h)
        _release(m, h)


def _request(m, reader, slot, kind):
    with m.frame(0x10) as p:
        m.put(p, 4, slot)
        m.put(p + 4, 4, kind)
        _post_and_schedule(m, reader, p, 0xF6F6D8)


@lifted(0xF70078)
def request(m, reader, *_):
    """A ServerRequest for the reader's slot: the payload {u8 slot, 5} posted and scheduled."""
    _request(m, reader, m.u8(reader + 0x38), 5)


@lifted(0xF71D10)
def post_gathered(m, reader, kind, done_key, key, *_):
    """A zeroed request block of `kind` with the slot's message `key` gathered in (0xf702ec, done key
    `done_key`), posted and scheduled."""
    with m.frame(0x240) as b:
        m.write(b, posted(kind & 0xFFFFFFFF))
        m.call_void(m.main + 0xF702EC, reader, b, done_key, key)
        _post_and_schedule(m, reader, b, 0xF6FFB8)


@lifted(0x2016BC8)
def post_ready(m, reader, *_):
    """A zeroed request block of kind 0x23 whose slot entry holds one action, word kind 8; the slot's sent
    0x21 erased from the reader's store; the block posted and scheduled."""
    slot = m.u8(reader + 0x38)
    with m.frame(0x240) as b:
        m.write(b, posted(0x23))
        a = b + slot * 0x70
        m.put(a, 4, (m.u32(a) & 0xFFFFFFF0) | 8)
        m.put(b + 0x230 + slot, 1, m.u8(b + 0x230 + slot) + 1)
        with m.frame(0x10) as f:
            m.call_sret(m.main + 0xF6F324, f, m.u64(reader + 0x30), slot)
            if m.u64(f):
                m.call_void(m.main + 0xF6FD7C, m.u64(f), 0x21)
                _release(m, f)
        _post_and_schedule(m, reader, b, 0xF6FFB8)


@lifted(0xF71020)
def timer_out(m, timer, *_):
    """Whether a battle timer has no time left: 1 when time_left (0xf91070, offset 0) is 0 or less; a timer
    not started reads its limit; a started one with a zero limit never runs out."""
    left = m.u64(timer + 0x20)
    if m.u8(timer + 0x18):
        if not left:
            return 0
        left = m.call(m.main + 0xF91070, timer, left, 0)
    return int((left - (1 << 64) if left >> 63 else left) < 1)


@lifted(0x2823610)
def setup_490(m, o, *_):
    """The u16 at setup +0x490 ([o+0x38])."""
    return m.u16(m.u64(o + 0x38) + 0x490)


@lifted(0x1FFE4E8)
def time_limit(m, o, slot, *_):
    """The battle timer's limit for a slot: setup +0x490 (0x2823610 on [o+0x10]); in a raid (setup +0x499
    bit 2) the slot's first party member's vf 0x560 with 8, when 1 or more, picks from 0x3c69d1c."""
    r = m.call(m.main + 0x2823610, m.u64(o + 0x10)) & 0xFFFFFFFF
    if not m.u8(m.u64(m.u64(o + 0x10) + 0x38) + 0x499) & 4:
        return r
    slot &= 0xFF
    party = 0 if slot > 4 else m.u64(m.u64(o + 8) + 0x30) + slot * 0x38 + 0x28
    if not m.u8(party + 0x30):
        return r
    p = m.u64(party)
    if not p:
        return r
    v = m.vcall(p, 0x560, 8) & 0xFFFFFFFF
    v = v - (1 << 32) if v >> 31 else v
    if v < 1:
        return r
    return RANKS[min(v, 6) - 1]


@lifted(0x1743160)
def message_body(m, msg, *_):
    """A message's body: its buffer [+0x40] past the 32-byte header."""
    return (m.u64(msg + 0x40) + 0x20) & 0xFFFFFFFFFFFFFFFF


@lifted(0x2897AF0)
def abort_2897af0(m, *_):
    """abort."""
    raise UnliftedCall("abort: 0x2897af0")


def _able(m, module, slot, width):
    """How many of a slot's party members ([module+0x30] + 0x38 slot + 0x28, count u8 +0x30) answer vf
    0x208 with bit 0; None for an empty party."""
    party = 0 if (slot & width) > 4 else m.u64(module + 0x30) + (slot & width) * 0x38 + 0x28
    if not m.u8(party + 0x30):
        return None
    n = 0
    i = 0
    while True:
        n += m.vcall(m.u64(party + 8 * i), 0x208) & 1
        i += 1
        if i >= m.u8(party + 0x30):
            return n & 0xFF


def _same_side(m, module, slot):
    """Whether a slot is on the side of N's own slot ([[module+0x290]+0x10]+0x95) by the battle mode's table
    (u32 [[module+0x290]+8]+0x36c); side 3 matches both, 4 side 1, 5 side 0."""
    o = m.u64(module + 0x290)
    mode = m.u32(m.u64(o + 8) + 0x36C)
    if mode not in SIDES:
        return False
    table = SIDES[mode]
    mine = table[slot] if slot <= 4 else 2
    own = m.u8(m.u64(o + 0x10) + 0x95)
    if own > 4:
        return False
    own = table[own]
    if own > 1:
        return False
    if own == mine or mine == 3:
        return True
    if mine == 4:
        return own != 0
    if mine == 5:
        return own != 1
    return False


def _erase(m, server, getter, slot, key):
    with m.frame(0x10) as f:
        m.call_sret(m.main + getter, f, server, slot)
        e = m.u64(f)
        if e:
            m.call_void(m.main + 0xF6FD7C, e, key)
            _release(m, f)
        return e


def _taken_0d(m, r, server, slot):
    """0xf6e93c: the slot answered 0xd with 0xe: a block of kind 0x1b when the 0xe body's first byte is set,
    else the request {slot, 7}; both erased. False when the entry or its 0xe is missing (0xd erased alone)."""
    with m.frame(0x10) as e:
        msg = e + 8
        m.call_sret(m.main + 0xE634C8, e, server, slot)
        if not m.u64(e):
            _erase(m, server, 0xF6F324, slot, 0xD)
            return False
        m.call_sret(m.main + 0xF6F0A8, msg, m.u64(e), 0xE)
        if not m.u64(msg):
            _release(m, e)
            _erase(m, server, 0xF6F324, slot, 0xD)
            return False
        if m.u8(m.call(m.main + 0x1743160, m.u64(msg))):
            with m.frame(0x240) as b:
                m.write(b, posted(0x1B))
                _post_and_schedule(m, r, b, 0xF6FFB8)
        else:
            _request(m, r, slot, 7)
        _erase(m, server, 0xF6F324, slot, 0xD)
        m.call_void(m.main + 0xF6FD7C, m.u64(e), 0xE)
        _release(m, msg)
        _release(m, e)
        return True


def _answers(m, r, server, slot):
    """0xf6e3ac: a slot's answers to messages 0xd, 7, 0xb, 0xf and 9 posted as blocks, else every answered
    pair erased (0xf6edf4): 1 for a post, 6 for an erase, 0 for nothing."""
    sent = lambda k: m.call(m.main + 0xF6EF64, server, k, slot) & 1
    got = lambda k: m.call(m.main + 0xF6F590, server, k, slot) & 1
    if sent(0xD) and got(0xE) and _taken_0d(m, r, server, slot):
        return 1
    for k, a, kind in ((7, 8, 0x17), (0xB, 0xC, 0x19), (0xF, 0x10, 0x15)):
        if sent(k) and got(a):
            m.call_void(m.main + 0xF71D10, r, kind, k, a)
            return 1
    if got(0xA):
        m.call_void(m.main + 0xF71D10, r, 0x17, 9, 0xA)
        return 1
    hit = 0
    for k, a in PAIRS:
        hit |= m.call(m.main + 0xF6EDF4, r, k, a)
    return 6 if hit & 1 else 0


def _raid_ready(m, r, server, module, slot):
    """0xf6e014: a raid slot on N's side (sub-state u8 +9). 0: with no able member, the request {slot,
    0x21} (state 3). 3: 0x21 answered with 0x22, the timer +0x50 made with the slot's limit (0x1ffe4e8) and
    started, the pair erased (state 1). 1: the timer run out, the 0x23 block posted (0x2016bc8, state 2).
    2: 0x23 answered with 0x24 (state 0). Returns 4, or None to go on to the reader's states."""
    sub = m.u8(r + 9)
    if sub == 0:
        if _able(m, module, slot, 0xFF):
            return None
        _request(m, r, slot, 0x21)
        m.put(r + 9, 1, 3)
        return 4
    if sub == 1:
        if m.call(m.main + 0xF71020, r + 0x50) & 1:
            m.call_void(m.main + 0x2016BC8, r)
            m.put(r + 9, 1, 2)
        return 4
    if sub == 2:
        if m.call(m.main + 0xF6EDF4, r, 0x23, 0x24) & 1:
            m.put(r + 9, 1, 0)
        return 4
    if sub == 3:
        if not m.call(m.main + 0xF6EF64, server, 0x21, slot) & 1:
            return 4
        if not m.call(m.main + 0xF6F590, server, 0x22, slot) & 1:
            return 4
        limit = m.call(m.main + 0x1FFE4E8, m.u64(module + 0x290), slot)
        m.call_void(m.main + 0xF70A58, r + 0x50, limit & 0xFFFFFFFF)
        m.call_void(m.main + 0xE63A6C, r + 0x50, 0)
        m.call(m.main + 0xF6EDF4, r, 0x21, 0x22)
        m.put(r + 9, 1, 1)
        return 4
    return None


@lifted(0xF6DF44)
def read_slot(m, r, *_):
    """One step of a per-slot reader (+0x10 the factory, +0x18 the scheduler, +0x20 N, +0x28 the module,
    +0x30 the server, u32 +0x38 the slot, u8 +8 its state): 0 for a slot the mode does not seat; a slot
    that sent 4 has 3 answered as a block of kind 0x13; a raid slot on N's side runs its timer states
    (_raid_ready); a slot on N's side, or with no able member, requests (state 0 -> 1), posts its command
    block of kind 0x15 once it answered 5 with 6 (1 -> 2) and returns idle once it answered the round
    (2 -> 0); every other case reads the slot's answers (_answers)."""
    server = m.u64(r + 0x30)
    slot = m.u8(r + 0x38)
    o = m.u64(m.u64(m.u64(server + 0x38) + 0x290) + 8)
    if not m.call(m.main + 0xE7E2A0, m.u32(o + 0x36C), m.u8(o + 0x370), slot) & 1:
        return 0
    if m.call(m.main + 0xF6F590, server, 4, slot) & 1:
        m.call_void(m.main + 0xF71D10, r, 0x13, 3, 4)
        return 1
    module = m.u64(r + 0x28)
    if m.u8(m.u64(m.u64(r + 0x20) + 0x38) + 0x499) & 4 and _same_side(m, module, slot):
        done = _raid_ready(m, r, server, module, slot)
        if done is not None:
            return done
    server = m.u64(r + 0x30)
    o = m.u64(m.u64(module + 0x290) + 8)
    if not m.call(m.main + 0xE7E2A0, m.u32(o + 0x36C), m.u8(o + 0x370), m.u8(r + 0x38)) & 1:
        return _answers(m, r, server, slot)
    who = m.u32(r + 0x38)
    if _able(m, module, who, 0xFFFFFFFF):
        who = m.u8(r + 0x38)
        if not _same_side(m, m.u64(r + 0x28), who):
            return _answers(m, r, server, slot)
    st = m.u8(r + 8)
    if st == 1:
        if not (m.call(m.main + 0xF6EF64, server, 5, who) & 1 and m.call(m.main + 0xF6F590, server, 6, who) & 1):
            return 5
        with m.frame(0x240) as b:
            m.write(b, posted(0x15))
            m.call_void(m.main + 0xF702EC, r, b, 5, 6)
            m.put(b + 0x238, 4, 0x15)
            _post_and_schedule(m, r, b, 0xF6FFB8)
        m.put(r + 8, 1, 2)
        return 1
    if st == 0:
        if any(m.call(m.main + 0xF6EF64, server, k, who) & 1 for k in WAIT):
            return _answers(m, r, server, slot)
        m.call_void(m.main + 0xF70078, r)
        m.put(r + 8, 1, 1)
        return 1
    if st == 2:
        if not m.call(m.main + 0xF6EDF4, r, 0x15, 0x16) & 1:
            return 5
        m.put(r + 8, 1, 0)
        return 6
    return _answers(m, r, server, slot)
