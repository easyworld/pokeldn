"""The server's job graph G = [N+0xa8]: the step 0xfc363c, the executor's job stack, the source's pick, the
scheduler's posted requests and the requests' factories (docs/sv_raid.md, The server's flow)."""

from pokeldn.sv.battle.engine import server
from pokeldn.sv.battle.engine.calls import _tail
from pokeldn.sv.battle.engine.references import _construct_counted_base
from pokeldn.sv.battle.engine.requests import _add_ref
from pokeldn.sv.battle.engine.steps import _create, _free_node, _pop, _push, _tls_stack
from pokeldn.sv.battle.machine import UnliftedCall, lifted

M64 = 0xFFFFFFFFFFFFFFFF
M32 = 0xFFFFFFFF

RAID_ACTION = 0x5C307D44EA569B63    # the source's first pick in a raid (setup +0x498 bit 0x400)
WILD_SETUP = 0x2E9E7A3009002C36     # the source's pick before the module's started flag
EXIT_BATTLE_END = 0x2DA7B4584624A364
REQUEST_E91B = 0xE91BA31DDC795017   # the hash 0x14799f4 posts

# the executor's request-to-job conversion 0x17b410c: request hash -> the job maker
MAKERS = {
    0x935ACB1823E1803F: 0x17B4A78,
    0xAE1B39FCCFD09053: 0x17B4EDC,  # ServerCommand
    WILD_SETUP: 0x17B5318,
    0x23607A0597B3A656: 0x17B5744,  # AddExpBattleEnd
    RAID_ACTION: 0x17B5B74,
    0x6871028D4BE52AA1: 0x17B5FB4,
    0x685BE0E82E7E3258: 0x17B6178,
    0x96D97E076DA4D5E5: 0x17B633C,
    0x503D3EFF7DA04A9C: 0x17B6500,
    0x809E7C342DC76A3C: 0x17B6888,
    EXIT_BATTLE_END: 0x17B66C4,
}


def _unref(m, o):
    """ReleaseReference on o's control block ([+0x30], u16 +0x1a); the last one clears +0x10 and ends in
    o's vf 0x50."""
    c = m.u64(o + 0x30)
    n = m.u16(c + 0x1A)
    if n == 0:
        raise UnliftedCall("abort: ReleaseReference underflow")
    m.put(c + 0x1A, 2, n - 1)
    if n == 1:
        m.put(c + 0x10, 8, 0)
        m.vcall_void(o, 0x50)


def _ref(m, o):
    if o:
        _add_ref(m, o)


def _drop(m, o):
    if o:
        _unref(m, o)


def _slots(begin, end):
    """A deque<T*>'s slot capacity: 512 a block, minus one; 0 without a map."""
    return 0 if end == begin else (((end - begin) << 6) - 1) & M64


def _slot(m, begin, i):
    return m.u64(begin + ((i >> 9) << 3)) + ((i & 0x1FF) << 3)


# --- the job graph's step and the executor (vtable 0x4493688): a deque<job*> with its map at +0x58,
# begin +0x60, end +0x68, cap +0x70, map allocator +0x78, start +0x98, size +0xa0, block allocator +0xa8 ---

@lifted(0xFC363C)
def step(m, g, run, *_):
    """One frame of the job graph: with `run` set and an empty executor, the per-frame machine's vf 0x68,
    then the source's pick moved from the scheduler into the executor; then the executor. Returns 1 when
    a request started, else the machine's result, bit 0."""
    w = 0
    if run & 1 and m.u64(m.u64(g + 0xB8) + 0xA0) == 0:
        w = m.vcall(m.u64(g + 0xB0), 0x68)
        with m.frame(0x20) as f:
            pick, a, b = f, f + 8, f + 0x10
            src = m.u64(g + 0xA8)
            m.call_sret(m.u64(m.u64(src) + 0x68), pick, src)
            req = m.u64(pick)
            if req:
                sched = m.u64(g + 0xA0)
                m.put(b, 8, req)
                _add_ref(m, req)
                m.call_void(m.main + 0xFC3F58, sched, b)
                _drop(m, m.u64(b))
                ex = m.u64(g + 0xB8)
                o = m.u64(pick)
                m.put(a, 8, o)
                _ref(m, o)
                m.call_void(m.main + 0xFC41A8, ex, a)
                _drop(m, m.u64(a))
                _drop(m, m.u64(pick))
                w = 1
    m.call_void(m.main + 0xFC38DC, m.u64(g + 0xB8))
    return w & 1


@lifted(0xFC38DC)
def run_jobs(m, ex, *_):
    """Runs the top job's vf 0x68 while the stack holds one: 0 ends the frame; 2 pops it (the back block
    freed once 0x400 slots are spare), pushes its continuation [job+0x70] when it has one and ends the
    frame; any other value runs the top job again."""
    while m.u64(ex + 0xA0):
        i = m.u64(ex + 0x98) + m.u64(ex + 0xA0) - 1
        job = m.u64(_slot(m, m.u64(ex + 0x60), i))
        _ref(m, job)
        r = m.vcall(job, 0x68) & M32
        if r == 0:
            _unref(m, job)
            return
        if r != 2:
            _unref(m, job)
            continue
        start, size = m.u64(ex + 0x98), m.u64(ex + 0xA0)
        _drop(m, m.u64(_slot(m, m.u64(ex + 0x60), start + size - 1)))
        start, size = m.u64(ex + 0x98), m.u64(ex + 0xA0) - 1
        begin, end = m.u64(ex + 0x60), m.u64(ex + 0x68)
        m.put(ex + 0xA0, 8, size)
        if (_slots(begin, end) - (start + size)) & M64 >= 0x400:
            _free_node(m, m.u64(ex + 0xA8), m.u64(end - 8), 0x1000, 8)
            m.put(ex + 0x68, 8, m.u64(ex + 0x68) - 8)
        nxt = m.u64(job + 0x70)
        if nxt:
            _add_ref(m, nxt)
            with m.frame(0x10) as loc:
                m.put(loc, 8, nxt)
                _add_ref(m, nxt)
                if _slots(m.u64(ex + 0x60), m.u64(ex + 0x68)) == (m.u64(ex + 0x98) + m.u64(ex + 0xA0)) & M64:
                    m.call_void(m.main + 0xFC444C, ex + 0x58)
                begin, end = m.u64(ex + 0x60), m.u64(ex + 0x68)
                at = 0 if end == begin else _slot(m, begin, m.u64(ex + 0x98) + m.u64(ex + 0xA0))
                m.call_void(m.main + 0xFC3DE0, ex + 0xA8, at, loc)
                m.put(ex + 0xA0, 8, m.u64(ex + 0xA0) + 1)
                _drop(m, m.u64(loc))
            _unref(m, nxt)
        _unref(m, job)
        return


@lifted(0xFC3DE0)
def construct_job_ref(m, holder, dst, src, *_):
    """*dst = a strong reference to *src, with the allocator [holder] on the thread's object stack."""
    return server.construct_ref(m, holder, dst, src)


@lifted(0xFC3F58)
def unpost(m, sched, req, *_):
    """Erases the first entry of the scheduler's posted vector (+0x40..+0x48) equal to *req: the entries
    after it moved down one (each overwritten handle released), the vacated tail released."""
    p, end = m.u64(sched + 0x40), m.u64(sched + 0x48)
    while p != end:
        e = m.u64(p)
        if e == 0:
            if m.u64(req) == 0:
                break
        else:
            _add_ref(m, e)
            want = m.u64(req)
            _unref(m, e)
            if want == e:
                break
        p += 8
    found = p
    end = m.u64(sched + 0x48)
    if found == end:
        return
    dst, src = found, found + 8
    if src != end:
        while src != end:
            old = m.u64(dst)
            m.put(dst, 8, 0)
            _drop(m, old)
            v = m.u64(src)
            m.put(src, 8, 0)
            m.put(dst, 8, v)
            dst += 8
            src += 8
        end = m.u64(sched + 0x48)
    while end != dst:
        end -= 8
        _drop(m, m.u64(end))
    m.put(sched + 0x48, 8, dst)


@lifted(0xFC41A8)
def push_job(m, ex, req, *_):
    """The job the executor's vf 0x68 (0x17b410c) makes from *req, pushed on its stack."""
    with m.frame(0x20) as f:
        r, job, loc = f, f + 8, f + 0x10
        o = m.u64(req)
        m.put(r, 8, o)
        _ref(m, o)
        m.call_sret(m.u64(m.u64(ex) + 0x68), job, ex, r)
        _drop(m, m.u64(r))
        o = m.u64(job)
        m.put(loc, 8, o)
        _ref(m, o)
        if _slots(m.u64(ex + 0x60), m.u64(ex + 0x68)) == (m.u64(ex + 0x98) + m.u64(ex + 0xA0)) & M64:
            m.call_void(m.main + 0xFC444C, ex + 0x58)
        begin, end = m.u64(ex + 0x60), m.u64(ex + 0x68)
        at = 0 if end == begin else _slot(m, begin, m.u64(ex + 0x98) + m.u64(ex + 0xA0))
        m.call_void(m.main + 0xFC3DE0, ex + 0xA8, at, loc)
        m.put(ex + 0xA0, 8, m.u64(ex + 0xA0) + 1)
        _drop(m, m.u64(loc))
        _drop(m, m.u64(job))


@lifted(0xFC444C)
def add_back_capacity(m, d, *_):
    """libc++ deque<job*>::__add_back_capacity at d (map +0..+0x18, its allocator +0x20, start +0x40, block
    allocator +0x50): a spare front block rotated to the back; else a new 0x1000-byte block pushed onto
    the map; else a new map of max(2 * capacity, 1) pointers holding the new block then the old ones."""
    with m.frame(0x50) as sp:
        if m.u64(d + 0x40) >= 0x200:
            m.put(d + 0x40, 8, m.u64(d + 0x40) - 0x200)
            _rotate(m, d, sp)
            return
        first, begin, end, cap = (m.u64(d + i) for i in (0, 8, 0x10, 0x18))
        size = ((end - begin) & M64) >> 3
        if size < ((cap - first) & M64) >> 3:
            blk = _new_block(m, d)
            m.put(sp + 0x28, 8, blk)
            if cap != end:
                m.call_void(m.main + 0x2824704, d, sp + 0x28)
                return
            m.call_void(m.main + 0x2824898, d, sp + 0x28)
            _rotate(m, d, sp)
            return
        span = (cap - first) & M64
        count = (span >> 2) if span else 1
        m.put(sp + 0x40, 8, 0); m.put(sp + 0x48, 8, d + 0x20)
        new = m.vcall(m.u64(d + 0x20), 0x10, count * 8, 8)
        if not new:
            raise UnliftedCall("allocator out of memory: vf 0xe8")
        mid = new + size * 8
        m.put(sp + 0x28, 8, new); m.put(sp + 0x30, 8, mid)
        m.put(sp + 0x38, 8, mid); m.put(sp + 0x40, 8, new + count * 8)
        blk = _new_block(m, d)
        m.put(sp + 8, 8, blk); m.put(sp + 0x18, 8, d + 0x50); m.put(sp + 0x20, 8, 0x200)
        m.call_void(m.main + 0xFC47EC, sp + 0x28, sp + 8)
        m.put(sp + 0x10, 8, 0)
        p = m.u64(d + 0x10)
        while p != m.u64(d + 8):
            p -= 8
            m.call_void(m.main + 0xFC4BF0, sp + 0x28, p)
        old_begin, old_end = m.u64(d + 8), m.u64(d + 0x10)
        old_first = m.u64(d)
        m.put(d, 8, m.u64(sp + 0x28)); m.put(d + 8, 8, m.u64(sp + 0x30)); m.put(d + 0x10, 8, m.u64(sp + 0x38))
        m.put(sp + 0x28, 8, old_first); m.put(sp + 0x30, 8, old_begin); m.put(sp + 0x38, 8, old_end)
        old_cap = m.u64(d + 0x18)
        m.put(d + 0x18, 8, m.u64(sp + 0x40)); m.put(sp + 0x40, 8, old_cap)
        m.call_void(m.main + 0xFC4684, sp + 0x10)
        m.call_void(m.main + 0xFC4728, sp + 0x28)


def _new_block(m, d):
    blk = m.vcall(m.u64(d + 0x50), 0x10, 0x1000, 8)
    if not blk:
        raise UnliftedCall("allocator out of memory: vf 0xe8")
    return blk


def _rotate(m, d, sp):
    """The map's front block taken off and pushed at its back (0xfc4a5c)."""
    begin = m.u64(d + 8)
    m.put(sp + 0x28, 8, m.u64(begin))
    m.put(d + 8, 8, begin + 8)
    m.call_void(m.main + 0xFC4A5C, d, sp + 0x28)


def _free_buffer(m, alloc, p, size):
    """The tail of a buffer's destructor: vf 0x18 of alloc, or 0xb48fe8 while frees are deferred."""
    _free_node(m, alloc, p, size, 8)


@lifted(0xFC4684)
def drop_block(m, up, *_):
    """A held block ({pointer, allocator holder, count of 8-byte slots}) freed and the pointer cleared."""
    p = m.u64(up)
    m.put(up, 8, 0)
    if p:
        _free_buffer(m, m.u64(m.u64(up + 8)), p, (m.u64(up + 0x10) << 3) & M64)


@lifted(0xFC4728)
def destroy_split_buffer(m, sb, *_):
    """split_buffer<T*> destructor (first, begin, end, cap, allocator holder +0x20): end back to begin,
    the buffer freed."""
    if m.u64(sb + 0x10) != m.u64(sb + 8):
        m.put(sb + 0x10, 8, m.u64(sb + 8))
    first = m.u64(sb)
    if first:
        _free_buffer(m, m.u64(m.u64(sb + 0x20)), first, (m.u64(sb + 0x18) - first) & M64)


@lifted(0xFC47EC)
def split_push_back(m, sb, val, *_):
    """split_buffer<T*>::push_back(*val): room at the back, or the elements slid to the front half of the
    spare room (memmove), or a new buffer of max(2 * capacity, 1) starting a quarter in."""
    end = m.u64(sb + 0x10)
    if end == m.u64(sb + 0x18):
        first, begin = m.u64(sb), m.u64(sb + 8)
        if begin > first:
            d = (begin - first) >> 3
            shift = (d + 1) >> 1
            n = (end - begin) & M64
            to = begin - shift * 8
            if n:
                m.write(to, m.read(begin, n))
            m.put(sb + 8, 8, m.u64(sb + 8) - shift * 8)
            end = to + n
            m.put(sb + 0x10, 8, end)
        else:
            holder = m.u64(sb + 0x20)
            span = (m.u64(sb + 0x18) - first) & M64
            count = (span >> 2) if span else 1
            with m.frame(0x30) as t:
                m.put(t + 0x18, 8, 0); m.put(t + 0x20, 8, holder)
                new = m.vcall(m.u64(holder), 0x10, count * 8, 8)
                if not new:
                    raise UnliftedCall("allocator out of memory: vf 0xe8")
                nb = new + (count >> 2) * 8
                ncap = new + count * 8
                m.put(t, 8, new); m.put(t + 8, 8, nb); m.put(t + 0x10, 8, nb); m.put(t + 0x18, 8, ncap)
                ob, oe = m.u64(sb + 8), m.u64(sb + 0x10)
                ne = nb + (oe - ob)
                dst, src = nb, ob
                while src != oe:
                    m.call_void(m.main + 0xFC4980, holder, dst, src)
                    dst += 8
                    src += 8
                ob, oe, of = m.u64(sb + 8), m.u64(sb + 0x10), m.u64(sb)
                m.put(sb, 8, new); m.put(sb + 8, 8, nb)
                m.put(t + 0x10, 8, oe); m.put(t, 8, of); m.put(t + 8, 8, ob)
                oc = m.u64(sb + 0x18)
                m.put(sb + 0x10, 8, ne); m.put(sb + 0x18, 8, ncap)
                m.put(t + 0x18, 8, oc)
                m.call_void(m.main + 0xFC4728, t)
            end = m.u64(sb + 0x10)
    m.call_void(m.main + 0xFC4980, m.u64(sb + 0x20), end, val)
    m.put(sb + 0x10, 8, m.u64(sb + 0x10) + 8)


@lifted(0xFC4980)
def scoped_store(m, holder, dst, src, *_):
    """*dst = *src (a plain pointer), with the allocator [holder] on the thread's object stack."""
    alloc = m.u64(holder)
    stack = _tls_stack(m)
    if stack:
        _push(m, stack, alloc)
    m.put(dst, 8, m.u64(src))
    if stack:
        _pop(m, stack)


# --- the source (vtable 0x44947d8): [+0x40] the jobs' context, [+0x48] the scheduler -------------------

def _first_of(m, sched, out, key, n):
    """The first posted request whose payload hash is `key`, referenced into *out; None when none is."""
    i = 0
    while True:
        b, e = m.u64(sched + 0x40), m.u64(sched + 0x48)
        if i >= ((e - b) & M64) >> 3:
            raise UnliftedCall("0x14641ec: the posted vector shrank under the pick")
        o = m.u64(b + 8 * i)
        m.put(out, 8, o)
        if not o:
            raise UnliftedCall("0x14641ec: a null posted request")
        _add_ref(m, o)
        o = m.u64(out)
        if m.u64(m.call(m.main + 0x1464570, o) + 8) == key:
            return o
        _unref(m, o)
        i = (i + 1) & M32
        if i == n:
            return None


@lifted(0x14641EC)
def pick(m, src, *_):
    """The request to start, referenced into *x8 (0 when none is posted): in a raid (setup +0x498 bit
    0x400) the first raid action, before the module's started flag ([[module+0x1f0]+8]) the first
    Wild::Setup, otherwise the first posted."""
    out = m.x8
    ctx, sched = m.u64(src + 0x40), m.u64(src + 0x48)
    n = (((m.u64(sched + 0x48) - m.u64(sched + 0x40)) & M64) >> 3) & M32
    setup = m.u64(m.u64(ctx + 8) + 0x38)
    if n and m.u64(setup + 0x498) & 0x400:
        if _first_of(m, sched, out, RAID_ACTION, n) is not None:
            return out
        ctx = m.u64(src + 0x40)
    if n and m.u8(m.u64(m.u64(ctx + 0x10) + 0x1F0) + 8) == 0:
        if _first_of(m, sched, out, WILD_SETUP, n) is not None:
            return out
    b, e = m.u64(sched + 0x40), m.u64(sched + 0x48)
    if e == b:
        m.put(out, 8, 0)
        return out
    o = m.u64(b)
    m.put(out, 8, o)
    _ref(m, o)
    return out


@lifted(0x1464570)
def request_payload(m, o, *_):
    """A posted request's buffer [+0x40]: u64 counter, u64 job type hash, the job's payload."""
    return m.u64(o + 0x40)


# --- the scheduler (vtable 0x44eea68): posted requests in a vector {begin +0x40, end +0x48, cap +0x50},
# its allocator holder +0x58; the per-frame machine keeps the factory at +0x48 and the scheduler at +0x50 ---

@lifted(0x1479924)
def machine_scheduler(m, o, *_):
    return m.u64(o + 0x50)


@lifted(0x14799EC)
def machine_factory(m, o, *_):
    return m.u64(o + 0x48)


@lifted(0x1479944)
def post_e91b(m, owner, *_):
    """Posts a request of hash 0xe91ba31ddc795017 whose 4-byte payload is the game's uninitialised stack
    (zero here)."""
    f = m.call(m.main + 0x14799EC, owner)
    with m.frame(0x20) as t:
        m.put(t, 8, 0); m.put(t + 8, 8, 0)
        m.call_sret(m.main + 0x14799F4, t + 8, f, t)
        m.call_void(m.main + 0x1479B10, owner, t + 8)
        _drop(m, m.u64(t + 8))
    return 0


@lifted(0x14799F4)
def request_e91b(m, f, payload, *_):
    """A request of hash 0xe91ba31ddc795017 with the factory's next counter (+0x40) and 4 payload bytes,
    into *x8."""
    out = m.x8
    with m.frame(0x20) as t:
        n = m.u64(f + 0x40)
        m.put(f + 0x40, 8, n + 1)
        m.put(t, 8, 4); m.put(t + 8, 8, payload); m.put(t + 0x10, 8, n); m.put(t + 0x18, 8, REQUEST_E91B)
        return m.call_sret(m.main + 0x1479A4C, out, m.u64(f + 8), t + 0x10, t + 8, t)


@lifted(0x1479A4C)
def make_request_ref(m, alloc, header, payload, size, *_):
    """A request made by 0x1479e1c, referenced into *x8."""
    out = m.x8
    o = m.call(m.main + 0x1479E1C, alloc, header, payload, size)
    m.put(out, 8, o)
    _ref(m, o)
    return o


@lifted(0x1479E1C)
def create_request(m, alloc, header, payload, size, *_):
    """Create the 0x50-byte request object (0x1479f64 with the 16-byte header, *payload, u32 *size)."""
    return _create(m, alloc, 0x50, lambda o: m.call_void(
        m.main + 0x1479F64, o, header, m.u64(payload), m.u32(size)))


@lifted(0x1479B10)
def post(m, owner, req, *_):
    """*req appended to the scheduler [owner+0x50]'s posted vector."""
    sched = m.u64(owner + 0x50)
    with m.frame(0x10) as loc:
        o = m.u64(req)
        m.put(loc, 8, o)
        _ref(m, o)
        m.call_void(m.main + 0x1479C50, sched, loc)
        _drop(m, m.u64(loc))


@lifted(0x1479C50)
def posted_push_back(m, sched, val, *_):
    """vector<request*>::push_back(*val) on sched+0x40, growing it through 0x147a0d4 when full."""
    end = m.u64(sched + 0x48)
    if end < m.u64(sched + 0x50):
        m.call_void(m.main + 0x1479CA4, sched + 0x58, end, val)
        m.put(sched + 0x48, 8, end + 8)
        return
    m.call_void(m.main + 0x147A0D4, sched + 0x40, val)


@lifted(0x1479CA4)
def construct_request_ref(m, holder, dst, src, *_):
    """*dst = a strong reference to *src, with the allocator [holder] on the thread's object stack."""
    return server.construct_ref(m, holder, dst, src)


@lifted(0x1479F64)
def construct_request(m, o, header, payload, size, *_):
    """The request object: the counted base, vtable 0x44ee948, a buffer of size + 0x10 bytes from [o+8] at
    +0x40 (its length u32 at +0x48) holding the 16-byte header then `size` bytes of payload."""
    _construct_counted_base(m, o)
    m.put(o, 8, m.main + 0x44EE948)
    m.put(o + 0x20, 8, m.main + 0x44EE9C0)
    m.put(o + 0x28, 8, m.main + 0x44EEA10)
    m.put(o + 0x40, 8, 0)
    n = (size + 0x10) & M32
    m.put(o + 0x48, 4, 0)
    buf = m.vcall(m.u64(o + 8), 0x10, n, 8)
    m.put(o + 0x40, 8, buf)
    m.put(o + 0x48, 4, n)
    m.write(buf, m.read(header, 0x10))
    m.write(m.u64(o + 0x40) + 0x10, m.read(payload, size & M32))


@lifted(0x147A0D4)
def posted_grow(m, v, val, *_):
    """vector<request*>::__push_back_slow_path: a new buffer of the recommended size, *val referenced at
    the old size, the old elements moved below it, the old buffer freed."""
    holder = v + 0x18
    n = ((((m.u64(v + 8) - m.u64(v)) & M64) >> 3) + 1) & M64
    r = m.call(m.main + 0x147A1B8, v, n)
    begin, end = m.u64(v), m.u64(v + 8)
    with m.frame(0x30) as sb:
        m.put(sb + 0x18, 8, 0); m.put(sb + 0x20, 8, holder)
        new = 0
        if r:
            new = m.vcall(m.u64(holder), 0x10, r * 8, 8)
            if not new:
                raise UnliftedCall("allocator out of memory: vf 0xe8")
        at = new + (end - begin)
        m.put(sb, 8, new); m.put(sb + 8, 8, at); m.put(sb + 0x18, 8, new + r * 8)
        m.call_void(m.main + 0x1479CA4, holder, at, val)
        m.put(sb + 0x10, 8, at + 8)
        m.call_void(m.main + 0x147A208, v, sb)
        m.call_void(m.main + 0x147A2B0, sb)


@lifted(0x147A1B8)
def recommend(m, v, n, *_):
    """vector::__recommend: max(2 * capacity, n), capped at the maximum size [v+0x20]."""
    ms = min(m.u64(v + 0x20), 0x7FFFFFFFFFFFFFFF)
    if ms < n:
        raise UnliftedCall("vector length_error")
    capb = (m.u64(v + 0x10) - m.u64(v)) & M64
    x = n if capb >> 2 < n else capb >> 2
    return x if capb >> 3 < ms >> 1 else ms


@lifted(0x147A208)
def swap_out(m, v, sb, *_):
    """vector::__swap_out_circular_buffer: v's elements moved below sb's begin, then v and sb exchange
    their buffers."""
    first = m.u64(v)
    p = m.u64(v + 8)
    if p != first:
        while True:
            p -= 8
            m.call_void(m.main + 0x147A714, v + 0x18, m.u64(sb + 8) - 8, p)
            m.put(sb + 8, 8, m.u64(sb + 8) - 8)
            if first == p:
                break
        first = m.u64(v)
    m.put(v, 8, m.u64(sb + 8))
    m.put(sb + 8, 8, first)
    e = m.u64(v + 8)
    m.put(v + 8, 8, m.u64(sb + 0x10)); m.put(sb + 0x10, 8, e)
    c = m.u64(v + 0x10)
    m.put(v + 0x10, 8, m.u64(sb + 0x18)); m.put(sb + 0x18, 8, c)
    m.put(sb, 8, m.u64(sb + 8))


@lifted(0x147A2B0)
def destroy_posted_buffer(m, sb, *_):
    """split_buffer<request*> destructor: its handles released from the back, the buffer freed."""
    m.call_void(m.main + 0x147A35C, sb, m.u64(sb + 8))
    first = m.u64(sb)
    if first:
        _free_buffer(m, m.u64(m.u64(sb + 0x20)), first, (m.u64(sb + 0x18) - first) & M64)


@lifted(0x147A35C)
def destruct_at_end(m, sb, to, *_):
    """split_buffer<request*>::__destruct_at_end: each handle from the end down to `to` released."""
    while m.u64(sb + 0x10) != to:
        e = m.u64(sb + 0x10) - 8
        m.put(sb + 0x10, 8, e)
        _drop(m, m.u64(e))


@lifted(0x147A714)
def scoped_move(m, holder, dst, src, *_):
    """*dst = *src, *src = 0, with the allocator [holder] on the thread's object stack."""
    alloc = m.u64(holder)
    stack = _tls_stack(m)
    if stack:
        _push(m, stack, alloc)
    v = m.u64(src)
    m.put(src, 8, 0)
    m.put(dst, 8, v)
    if stack:
        _pop(m, stack)


@lifted(0x147AC10)
def clear_link(m, link, *_):
    """The link's outgoing deque [link+0x48]+0x40 emptied (0xe0f5f8)."""
    return _tail(m, m.main + 0xE0F5F8, m.u64(link + 0x48) + 0x40)


# --- the executor's request-to-job conversion and its job makers ------------------------------------

@lifted(0x177D7E0)
def job_context(m, o, *_):
    return m.u64(o + 0x40)


@lifted(0x177D7E8)
def request_body(m, o, *_):
    """A request's payload after its 16-byte header."""
    return m.u64(o + 0x40) + 0x10


@lifted(0x177D7F4)
def assign_ref(m, holder, o, *_):
    """*holder = o as a strong reference, the old one released."""
    _ref(m, o)
    old = m.u64(holder)
    m.put(holder, 8, o)
    _drop(m, old)


@lifted(0x17B410C)
def make_job(m, ex, req, *_):
    """The executor's vf 0x68: the job the request's hash names, made by its maker into *x8; 0 for a
    hash it does not know."""
    out = m.x8
    h = m.u64(m.call(m.main + 0x1464570, m.u64(req)) + 8)
    maker = MAKERS.get(h)
    if maker is None:
        m.put(out, 8, 0)
        return out
    with m.frame(0x10) as loc:
        r = m.u64(req)
        m.put(loc, 8, r)
        _ref(m, r)
        m.call_sret(m.main + maker, out, ex, loc)
        _drop(m, r)
    return out


def _maker(m, ex, req, factory):
    """A job maker: the request held, then factory(allocator [ex+8], &context [ex+0x40], the request's
    payload) into *x8."""
    out = m.x8
    r = m.u64(req)
    _ref(m, r)
    with m.frame(0x20) as f:
        loc, ctx, res = f, f + 8, f + 0x10
        m.put(loc, 8, 0)
        m.call_void(m.main + 0x177D7F4, loc, r)
        _drop(m, r)
        alloc = m.u64(ex + 8)
        m.put(ctx, 8, m.call(m.main + 0x177D7E0, ex))
        body = m.call(m.main + 0x177D7E8, m.u64(loc))
        m.call_sret(m.main + factory, res, alloc, ctx, body)
        m.put(out, 8, m.u64(res))
        _drop(m, m.u64(loc))
    return out


def _referenced(m, create, alloc, ctx, body):
    out = m.x8
    o = m.call(m.main + create, alloc, ctx, body)
    m.put(out, 8, o)
    _ref(m, o)
    return o


def _create_job(m, alloc, ctx, body, size, ctor):
    return _create(m, alloc, size, lambda o: m.call_void(m.main + ctor, o, m.u64(ctx), body))


@lifted(0x17B4EA4)
def construct_job(m, o, key, name, ctx, *_):
    """The executor's job base: 0x13989a4 (hash, name descriptor, context), vtable 0x44938f0."""
    m.call_void(m.main + 0x13989A4, o, key, name, ctx)
    m.put(o, 8, m.main + 0x44938F0)
    m.put(o + 0x20, 8, m.main + 0x4493970)
    m.put(o + 0x28, 8, m.main + 0x44939C0)


def _job_head(m, o, key, name, vtable, ctx):
    m.call_void(m.main + 0x17B4EA4, o, key, m.main + name, ctx)
    m.put(o, 8, m.main + vtable)
    m.put(o + 0x20, 8, m.main + vtable + 0x80)
    m.put(o + 0x28, 8, m.main + vtable + 0xD0)


@lifted(0x17B4A78)
def maker_935a(m, ex, req, *_):
    return _maker(m, ex, req, 0x17B4C3C)


@lifted(0x17B4C3C)
def job_935a_ref(m, alloc, ctx, body, *_):
    return _referenced(m, 0x17B4D00, alloc, ctx, body)


@lifted(0x17B4D00)
def create_job_935a(m, alloc, ctx, body, *_):
    return _create_job(m, alloc, ctx, body, 0x98, 0x17B4E40)


@lifted(0x17B4E40)
def construct_job_935a(m, o, ctx, body, *_):
    """Job of hash 0x935acb1823e1803f: vtable 0x44942d8, +0x78 the payload's u64, +0x80..+0x98 zero."""
    _job_head(m, o, 0x935ACB1823E1803F, 0x44943F0, 0x44942D8, ctx)
    m.put(o + 0x78, 8, m.u64(body)); m.put(o + 0x80, 8, 0)
    m.put(o + 0x88, 8, 0); m.put(o + 0x90, 8, 0)


@lifted(0x17B4EDC)
def maker_command(m, ex, req, *_):
    return _maker(m, ex, req, 0x17B50A0)


@lifted(0x17B50A0)
def job_command_ref(m, alloc, ctx, body, *_):
    return _referenced(m, 0x17B5164, alloc, ctx, body)


@lifted(0x17B5164)
def create_job_command(m, alloc, ctx, body, *_):
    return _create_job(m, alloc, ctx, body, 0x2D0, 0x17B52A4)


@lifted(0x17B52A4)
def construct_job_command(m, o, ctx, body, *_):
    """ServerCommand (hash 0xae1b39fccfd09053): vtable 0x4494198, the 0x240-byte payload (a request block)
    at +0x78, +0x2b8..+0x2d0 zero."""
    _job_head(m, o, 0xAE1B39FCCFD09053, 0x44942B0, 0x4494198, ctx)
    m.write(o + 0x78, m.read(body, 0x240))
    m.put(o + 0x2B8, 8, 0); m.put(o + 0x2C0, 8, 0); m.put(o + 0x2C8, 8, 0)


@lifted(0x17B5318)
def maker_setup(m, ex, req, *_):
    return _maker(m, ex, req, 0x17B54DC)


@lifted(0x17B54DC)
def job_setup_ref(m, alloc, ctx, body, *_):
    return _referenced(m, 0x17B55A0, alloc, ctx, body)


@lifted(0x17B55A0)
def create_job_setup(m, alloc, ctx, body, *_):
    return _create_job(m, alloc, ctx, body, 0x98, 0x17B56E0)


@lifted(0x17B56E0)
def construct_job_setup(m, o, ctx, body, *_):
    """Wild::Setup's job (hash 0x2e9e7a3009002c36): vtable 0x44937b0, +0x78 the payload's u64, +0x80..+0x98
    zero."""
    _job_head(m, o, WILD_SETUP, 0x44938C8, 0x44937B0, ctx)
    m.put(o + 0x78, 8, m.u64(body)); m.put(o + 0x80, 8, 0)
    m.put(o + 0x88, 8, 0); m.put(o + 0x90, 8, 0)


@lifted(0x17B5744)
def maker_exp_end(m, ex, req, *_):
    return _maker(m, ex, req, 0x17B5908)


@lifted(0x17B5908)
def job_exp_end_ref(m, alloc, ctx, body, *_):
    return _referenced(m, 0x17B59CC, alloc, ctx, body)


@lifted(0x17B59CC)
def create_job_exp_end(m, alloc, ctx, body, *_):
    return _create_job(m, alloc, ctx, body, 0x98, 0x17B5B0C)


@lifted(0x17B5B0C)
def construct_job_exp_end(m, o, ctx, body, *_):
    """AddExpBattleEnd (hash 0x23607a0597b3a656): vtable 0x4493a18, u8 +0x78 the payload's kind byte,
    +0x80..+0x98 zero."""
    _job_head(m, o, 0x23607A0597B3A656, 0x4493B30, 0x4493A18, ctx)
    m.put(o + 0x78, 1, m.u8(body))
    m.put(o + 0x80, 8, 0); m.put(o + 0x88, 8, 0); m.put(o + 0x90, 8, 0)


@lifted(0x17B5B74)
def maker_raid_action(m, ex, req, *_):
    return _maker(m, ex, req, 0x17B5D38)


@lifted(0x17B5D38)
def job_raid_action_ref(m, alloc, ctx, body, *_):
    return _referenced(m, 0x17B5DFC, alloc, ctx, body)


@lifted(0x17B5DFC)
def create_job_raid_action(m, alloc, ctx, body, *_):
    return _create_job(m, alloc, ctx, body, 0xF0, 0x17B5F3C)


@lifted(0x17B5F3C)
def construct_job_raid_action(m, o, ctx, body, *_):
    """RaidAction (hash 0x5c307d44ea569b63): vtable 0x4494698, the 0x60-byte payload at +0x78, +0xd8..+0xf0
    zero, the payload's u32 state also at +0x68 (0x1742f80)."""
    _job_head(m, o, RAID_ACTION, 0x44947B0, 0x4494698, ctx)
    m.write(o + 0x78, m.read(body, 0x60))
    m.put(o + 0xD8, 8, 0); m.put(o + 0xE0, 8, 0); m.put(o + 0xE8, 8, 0)
    m.put(o + 0x68, 4, m.u32(o + 0x78))


@lifted(0x17B5FB4)
def maker_6871(m, ex, req, *_):
    return _maker(m, ex, req, 0x2016E5C)


@lifted(0x17B6178)
def maker_685b(m, ex, req, *_):
    return _maker(m, ex, req, 0x2016F20)


@lifted(0x17B633C)
def maker_96d9(m, ex, req, *_):
    return _maker(m, ex, req, 0x2016FE4)


@lifted(0x17B6500)
def maker_503d(m, ex, req, *_):
    return _maker(m, ex, req, 0x20170A8)


@lifted(0x17B66C4)
def maker_exit_end(m, ex, req, *_):
    """ExitBattleEnd's maker (hash 0x2da7b4584624a364): its job made by 0x201716c."""
    return _maker(m, ex, req, 0x201716C)


@lifted(0x17B6888)
def maker_809e(m, ex, req, *_):
    return _maker(m, ex, req, 0x2017230)


# --- the request factory (G+0x98, 0x48 bytes): [+8] its allocator, +0x40 the request counter ----------

@lifted(0x201602C)
def post_exit_battle_end(m, f, payload, *_):
    """An ExitBattleEnd request (hash 0x2da7b4584624a364) with the factory's next counter and the 4-byte
    message kind at *payload, into *x8."""
    out = m.x8
    with m.frame(0x20) as t:
        n = m.u64(f + 0x40)
        m.put(f + 0x40, 8, n + 1)
        m.put(t, 8, 4); m.put(t + 8, 8, payload); m.put(t + 0x10, 8, n); m.put(t + 0x18, 8, EXIT_BATTLE_END)
        return m.call_sret(m.main + 0x2016084, out, m.u64(f + 8), t + 0x10, t + 8, t)


@lifted(0x2016084)
def make_request_ref_2016084(m, alloc, header, payload, size, *_):
    """A request made by 0x2016778, referenced into *x8."""
    out = m.x8
    o = m.call(m.main + 0x2016778, alloc, header, payload, size)
    m.put(out, 8, o)
    _ref(m, o)
    return o


@lifted(0x2016778)
def create_request_2016778(m, alloc, header, payload, size, *_):
    """Create the 0x50-byte request object (0x1479f64 with the 16-byte header, *payload, u32 *size)."""
    return _create(m, alloc, 0x50, lambda o: m.call_void(
        m.main + 0x1479F64, o, header, m.u64(payload), m.u32(size)))


@lifted(0x2016148)
def create_message(m, alloc, header, body, size, *_):
    """Create the 0x50-byte message object (0x1227714 with the 32-byte header, *body, u32 *size)."""
    return _create(m, alloc, 0x50, lambda o: m.call_void(
        m.main + 0x1227714, o, header, m.u64(body), m.u32(size)))
