"""The battle server's jobs as the executor runs them (vf 0x68, 0 waits, 2 done): ServerRequest, ServerCommand,
RaidAction, Wild::Setup, the battle's end jobs and the fade-out (docs/sv_raid.md, The server's flow).
A job holds its context at +0x40 (N +8, module +0x10, server +0x18, factory +0x20, scheduler +0x28, battle
timer +0x38), its state u32 at +0x68, its continuation at +0x70 and its payload from +0x78."""

from pokeldn.sv.battle.engine import requests
from pokeldn.sv.battle.engine.calls import M32, M64, _tail
from pokeldn.sv.battle.engine.requests import _add_ref, _release
from pokeldn.sv.battle.engine.steps import _base_dtor, _create, _tls_top, _vt
from pokeldn.sv.battle.machine import UnliftedCall, lifted

ALL = 5


def _unref(m, o):
    """ReleaseReference on o's control block ([o+0x30], u16 +0x1a); the last one clears +0x10 and runs vf 0x50."""
    c = m.u64(o + 0x30)
    n = m.u16(c + 0x1A)
    if n == 0:
        raise UnliftedCall("abort: ReleaseReference")
    m.put(c + 0x1A, 2, n - 1)
    if n == 1:
        m.put(c + 0x10, 8, 0)
        m.vcall_void(o, 0x50)


def _server(m, job):
    return m.u64(m.u64(job + 0x40) + 0x18)


def _keep(m, job, at, r):
    """A send's 0x18-byte result {u8, u64 step, u8} copied into the job at `at` as the game copies it (its +1..+7
    included)."""
    m.put(job + at, 8, m.u64(r)); m.put(job + at + 8, 8, m.u64(r + 8)); m.put(job + at + 0x10, 1, m.u8(r + 0x10))


def _send(m, job, at, kind, dest=None):
    """A message to every station (0x113bab8) or through 0x113bad8 to `dest`, its result kept at job+at."""
    server = _server(m, job)
    with m.frame(0x20) as r:
        m.write(r, bytes(0x20))
        if dest is None:
            m.call_sret(m.main + 0x113BAB8, r, server, kind)
        else:
            m.call_sret(m.main + 0x113BAD8, r, server, kind, dest)
        _keep(m, job, at, r)


def _every_answered(m, server, step):
    """0xe63380 for slots 0..4 in turn, stopping at the first that has not answered `step`."""
    return all(m.call(m.main + 0xE63380, server, step, s) & 1 for s in range(5))


def _seated(m, server, slot):
    """0xe7e2a0 on the setup's mode [x+0x36c] and byte +0x370, x = [[[server+0x38]+0x290]+8] (0x18c99a4)."""
    x = m.u64(m.u64(m.u64(server + 0x38) + 0x290) + 8)
    return m.call(m.main + 0xE7E2A0, m.u32(x + 0x36C), m.u8(x + 0x370), slot & 0xFF) & 1


def _shared(m, out, o):
    """*out = o with a reference taken (the sret wrappers around a Create)."""
    m.put(out, 8, o)
    if o:
        _add_ref(m, o)
    return o


def _continue(m, job, maker, arg=None):
    """The job's continuation [job+0x70] set (0x1398340) to the job the sret `maker` makes from the job's
    allocator [job+8], its context and `arg` (a stack slot the makers here never read when None)."""
    alloc = m.u64(job + 8)
    with m.frame(0x30) as f:
        m.write(f, bytes(0x30))
        m.put(f + 8, 8, m.call(m.main + 0x1398338, job))
        if arg is not None:
            m.put(f + 0x18, 4, arg)
        m.call_sret(m.main + maker, f + 0x10, alloc, f + 8, f + 0x18)
        _shared(m, f, m.u64(f + 0x10))
        m.call_void(m.main + 0x1398340, job, f)
        _release(m, f)
        _release(m, f + 0x10)


def _post(m, job, f):
    """0x16e54a8 with the posted request in the slot f, then the slot's reference released."""
    m.call_void(m.main + 0x16E54A8, job, f)
    _release(m, f)


# --- the job base: constructor 0x13989a4, destructor 0x1384748, continuation 0x1398340 ---------------------

lifted(0x145A574)(lambda m, job, *_: m.u32(job + 0x68))


@lifted(0x1742F80)
def set_state(m, job, state, *_):
    """The job's state u32 +0x68."""
    m.put(job + 0x68, 4, state)


@lifted(0x13989A4)
def construct_job(m, o, hash_, desc, ctx, *_):
    """The job base on the weak-object base: vtable 0x44eecc0, +0x40 the context, +0x48 the job type hash,
    +0x50..+0x60 the three words at desc, state +0x68 and continuation +0x70 zero."""
    m.put(o + 0x10, 8, 0); m.put(o + 0x18, 4, 0)
    m.put(o, 8, _vt(m, 0x46D66F8))
    top = _tls_top(m)
    vt = m.u64(m.main + 0x46D8C78)
    m.put(o, 8, vt + 0x10); m.put(o + 8, 8, top)
    m.put(o + 0x20, 8, vt + 0x88); m.put(o + 0x28, 8, vt + 0xD8)
    m.put(o + 0x38, 8, 0); m.put(o + 0x30, 8, 0)
    r = m.call(m.main + 0xC1A3F4, o + 0x30, o + 0x28)
    m.put(o, 8, m.main + 0x44EECC0)
    m.put(o + 0x20, 8, m.main + 0x44EED40); m.put(o + 0x28, 8, m.main + 0x44EED90)
    m.put(o + 0x40, 8, ctx); m.put(o + 0x48, 8, hash_)
    m.put(o + 0x50, 8, m.u64(desc)); m.put(o + 0x58, 8, m.u64(desc + 8)); m.put(o + 0x60, 8, m.u64(desc + 0x10))
    m.put(o + 0x68, 4, 0); m.put(o + 0x70, 8, 0)
    return r


@lifted(0x1384748)
def destroy_job(m, o, *_):
    """The job base destructor: vtable 0x44eecc0, the continuation +0x70 released, then the weak-object base."""
    m.put(o, 8, m.main + 0x44EECC0)
    m.put(o + 0x20, 8, m.main + 0x44EED40); m.put(o + 0x28, 8, m.main + 0x44EED90)
    c = m.u64(o + 0x70)
    if c:
        _unref(m, c)
    _base_dtor(m, o)


lifted(0x2017BA0)(lambda m, o, *_: destroy_job(m, o))      # b 0x1384748, every server job's vf 0


@lifted(0x13985A8)
def assign_ref(m, holder, o, *_):
    """*holder = o with a reference taken; the reference the slot held before is released."""
    if o:
        _add_ref(m, o)
    old = m.u64(holder)
    m.put(holder, 8, o)
    if old:
        _unref(m, old)


@lifted(0x1398340)
def set_continuation(m, job, src, *_):
    """The job's continuation +0x70 = *src (0x13985a8)."""
    return assign_ref(m, job + 0x70, m.u64(src))


@lifted(0xE632FC)
def every_answered(m, server, step, *_):
    """Whether slots 0..4 each sent a message of `step` (0xe63380), stopping at the first that did not."""
    for s in range(4):
        if not m.call(m.main + 0xE63380, server, step, s) & 1:
            return 0
    return _tail(m, m.main + 0xE63380, server, step, 4)


@lifted(0x2824410)
def destroy_posted(m, o, *_):
    """A posted request's destructor (vtable 0x44ee948): its payload buffer (+0x40, u32 size +0x48) back to
    [o+8] (0xb48fe8 while frees are deferred, else vf 0x18), then the weak-object base."""
    alloc = m.u64(o + 8)
    m.put(o, 8, m.main + 0x44EE948)
    m.put(o + 0x20, 8, m.main + 0x44EE9C0); m.put(o + 0x28, 8, m.main + 0x44EEA10)
    data, n = m.u64(o + 0x40), m.u32(o + 0x48)
    if m.vcall(alloc, 0xF8) & 1 and m.s(m.call(m.main + 0xB4E600) + 0x12C8, 4) >= 1:
        m.call_void(m.main + 0xB48FE8, alloc, data, n, 8)
    else:
        m.vcall_void(alloc, 0x18, data, n, 8)
    _base_dtor(m, o)


# --- ServerRequest (vtable 0x44942d8): message +0x7c to slot +0x78 -----------------------------------------

@lifted(0x138D178)
def server_request(m, job, *_):
    """State 0 sends the request (0x138d1b0) and moves on; the job is done in one call."""
    if m.call(m.main + 0x145A574, job) & M32 == 0:
        m.call_void(m.main + 0x138D1B0, job)
        m.call_void(m.main + 0x1397D74, job)
    return 2


@lifted(0x138D1B0)
def request_send(m, job, *_):
    """Message u32 +0x7c to the slot u32 +0x78 (0x138d1e4); the result is dropped."""
    server = m.call(m.main + 0x16E4FE4, job)
    with m.frame(0x20) as r:
        m.write(r, bytes(0x20))
        return m.call_sret(m.main + 0x138D1E4, r, server, m.u32(job + 0x7C), m.u32(job + 0x78))


lifted(0x138D1E4)(lambda m, server, kind, dest, *_: _tail(m, m.main + 0x113BAD8, server, kind, dest))


# --- ServerCommand (vtable 0x4494198): the request block +0x78 (0x238 bytes, kind u32 +0x2b0) sent as a round,
# its result at +0x2b8, then the result's next step (0x16e4ff0) ------------------------------------------------

@lifted(0x16E4F10)
def server_command(m, job, *_):
    """State 0 sends the round and runs again (1); state 1 takes the result's next step and ends (2)."""
    st = m.call(m.main + 0x145A574, job) & M32
    if st == 1:
        m.call_void(m.main + 0x16E4F6C, job)
        r = 2
    elif st == 0:
        m.call_void(m.main + 0x16E4F84, job)
        r = 1
    else:
        return 2
    m.call_void(m.main + 0x1397D74, job)
    return r


@lifted(0x16E4F6C)
def command_next(m, job, *_):
    """The next step of the round's result: 8 when its byte +0x2c8 is set, else its byte +0x2b8."""
    return _tail(m, m.main + 0x16E4FF0, job, 8 if m.u8(job + 0x2C8) else m.u8(job + 0x2B8))


@lifted(0x16E4F84)
def command_send(m, job, *_):
    """With a kind (+0x2b0): the block into the server (0x113bac0) and the round to every station, its result
    kept at +0x2b8."""
    kind = m.u32(job + 0x2B0)
    if not kind:
        return
    m.call(m.main + 0x113BAC0, m.call(m.main + 0x16E4FE4, job), job + 0x78)
    _send(m, job, 0x2B8, kind)


@lifted(0x16E4FF0)
def next_step(m, job, k, *_):
    """The step after a round by its result byte (jump table 0x3c61c38): 0 none, 4 an empty round, 6 the
    boss's shield actions, 7 the battle's end, 8 and 9 AddExpBattleEnd, 5 and above 9 0x1882e24."""
    k &= 0xFF
    if k == 0:
        return
    if k > 9 or k == 5:
        return _tail(m, m.main + 0x1882E24, job)
    if k == 1:
        return _tail(m, m.main + 0x16E5E8C, job)
    if k == 2:
        if m.call(m.main + 0x16E55F0, job) & 1:
            return _tail(m, m.main + 0x2017F6C, job)
        return _tail(m, m.main + 0x2018030, job)
    if k == 3:
        return _tail(m, m.main + 0x16E61F0, job)
    if k == 4:
        return _tail(m, m.main + 0x16E5CAC, job)
    if k == 6:
        return _tail(m, m.main + 0x16E5AD0, job)
    if k == 7:
        if m.call(m.main + 0x16E56A0, job) & 1:
            return
        m.call_void(m.main + 0x16E5120, job)
        m.call_void(m.main + 0xE7D4C8, m.call(m.main + 0x16E4FE4, job))
    elif k == 9:
        m.call_void(m.main + 0xE7D570, m.call(m.main + 0x1397D84, job), 6, 3, 0)
        m.call_void(m.main + 0xE7D4C8, m.call(m.main + 0x16E4FE4, job))
    return _tail(m, m.main + 0x16E5180, job, k)


@lifted(0x16E5180)
def post_exp_end(m, job, kind, *_):
    """AddExpBattleEnd posted (0x16e5230) with the byte `kind` as its payload."""
    with m.frame(0x20) as f:
        m.write(f, bytes(0x20))
        m.put(f + 0x10, 1, kind)
        m.call_sret(m.main + 0x16E5230, f, m.u64(m.call(m.main + 0x1398338, job) + 0x20), f + 0x10)
        _post(m, job, f)


@lifted(0x16E5230)
def request_exp_end(m, factory, payload, *_):
    """*x8 = a posted request of AddExpBattleEnd (hash 0x23607a0597b3a656) with the factory's next counter
    (+0x40) and the payload pointer (0x16e5288)."""
    out = m.x8
    with m.frame(0x20) as f:
        m.put(f + 0x18, 8, 0x23607A0597B3A656)
        n = m.u64(factory + 0x40)
        m.put(factory + 0x40, 8, n + 1)
        m.put(f + 8, 8, payload); m.put(f + 0x10, 8, n)
        m.put(f, 8, 1)
        return m.call_sret(m.main + 0x16E5288, out, m.u64(factory + 8), f + 0x10, f + 8, f)


@lifted(0x16E5288)
def make_request(m, alloc, key, payload, one, *_):
    """*x8 = the request 0x16e5360 makes, with a reference taken."""
    out = m.x8
    with m.frame(0x10) as d:
        return _shared(m, out, m.call(m.main + 0x16E5360, d, alloc, key, payload, one))


@lifted(0x16E5360)
def create_request(m, _x0, alloc, key, payload, one, *_):
    """Create a 0x50-byte posted request (0x1479f64 with the key {counter, hash}, *payload and u32 *one)."""
    return _create(m, alloc, 0x50,
                   lambda o: m.call_void(m.main + 0x1479F64, o, key, m.u64(payload), m.u32(one)))


@lifted(0x16E54A8)
def post_request(m, job, src, *_):
    """A reference to *src handed to the scheduler [ctx+0x28] (0x1479c50), then released."""
    sched = m.u64(m.call(m.main + 0x1398338, job) + 0x28)
    with m.frame(0x10) as f:
        _shared(m, f, m.u64(src))
        m.call_void(m.main + 0x1479C50, sched, f)
        _release(m, f)


lifted(0x16E5C90)(lambda m, module, *_: m.u64(module + 0x1B0))


@lifted(0x16E5C98)
def boss_entry(m, lst, i, *_):
    """The boss list's entry i (+0x5c + 8 i) for i < 4 (signed), else 0."""
    i &= M32
    if i >> 31:
        i -= 1 << 32
    return (lst + 0x5C + 8 * i) & M64 if i < 4 else 0


@lifted(0x16E5AD0)
def post_shield(m, job, *_):
    """When the round's boss list (0x16e5c90) holds a shield (0x1142804) and its first kind is 1: a raid
    action posted (0xf71928) from its actions (0x114fb2c, 0xf6fc54), the list and the battle timer."""
    def boss_list():
        return m.call(m.main + 0x16E5C90, m.call(m.main + 0x13F5F00, m.call(m.main + 0x16E4FE4, job)))
    if not m.call(m.main + 0x1142804, boss_list()) & 1:
        return
    lst = boss_list()
    if m.u8(m.call(m.main + 0x16E5C98, lst, 0)) != 1:
        return
    with m.frame(0xC0) as f:
        acts, p, req = f + 0x70, f, f + 0xB0
        m.write(f, bytes(0xC0))
        n = m.call(m.main + 0x114FB2C, lst, acts) & M32
        m.put(p + 0x10, 8, lst)
        m.put(p + 8, 8, m.u64(m.call(m.main + 0x1398338, job) + 0x38))
        m.put(p + 0x18, 4, n)
        if not n >> 31:
            for i in range(n):
                m.call(m.main + 0xF6FC54, p + 0x20 + 0x10 * i, acts + 0x10 * i)
        m.call_sret(m.main + 0xF71928, req, m.u64(m.call(m.main + 0x1398338, job) + 0x20), p)
        _post(m, job, req)


@lifted(0x16E5CAC)
def post_empty_round(m, job, *_):
    """An empty round posted: a zeroed request block of kind 0x15 (0xf6ffb8)."""
    with m.frame(0x250) as f:
        m.write(f, bytes(0x10))
        m.write(f + 0x10, requests.posted(0x15))
        m.call_sret(m.main + 0xF6FFB8, f, m.u64(m.call(m.main + 0x1398338, job) + 0x20), f + 0x10)
        _post(m, job, f)


# --- RaidAction (vtable 0x4494698): the payload of 0xf6d8d4 at +0x78 (u32 first state, timer +0x80, list
# +0x88, u32 count +0x90, actions from +0x98), the result at +0xd8 ------------------------------------------

@lifted(0x18C99A4)
def slot_seated(m, server, slot, *_):
    """0xe7e2a0 on the battle's mode for `slot` (u8)."""
    x = m.u64(m.u64(m.u64(server + 0x38) + 0x290) + 8)
    return _tail(m, m.main + 0xE7E2A0, m.u32(x + 0x36C), m.u8(x + 0x370), slot & 0xFF)


@lifted(0x18C99C0)
def erase_sent(m, server, key, slot, *_):
    """The messages of type `key` erased from what the server sent `slot` (0xf6f324, 0xf6fd7c)."""
    with m.frame(0x10) as f:
        m.put(f, 8, 0)
        m.call_sret(m.main + 0xF6F324, f, server, slot)
        o = m.u64(f)
        if o:
            m.call_void(m.main + 0xF6FD7C, o, key)
            _unref(m, o)


@lifted(0x18C92A8)
def raid_action(m, job, *_):
    """0 message 0x47, the timer paused; 1 every slot's answer awaited; 2 the actions as a slot-1 round
    (count +0x231), the timer resumed; 3 the result's next step (0x16e4ff0), the list cleared, and after a
    0x47 each answering slot's 0x47 and 0x48 erased."""
    st = m.u32(job + 0x68)
    server = _server(m, job)
    if st == 1:
        if _every_answered(m, server, m.u64(job + 0xE0)):
            m.call_void(m.main + 0x1397D74, job)
        return 0
    if st == 0:
        _send(m, job, 0xD8, 0x47)
        timer = m.u64(job + 0x80)
        if timer:
            m.call_void(m.main + 0x18C9A68, timer, 0)
        m.call_void(m.main + 0x1397D74, job)
        return 0
    if st == 2:
        n = m.u32(job + 0x90)
        with m.frame(0x240) as b:
            m.write(b, requests.posted(0))
            for i in range(n):
                m.call(m.main + 0xF6FC54, b + 0x70 + 0x10 * i, job + 0x98 + 0x10 * i)
            m.put(b + 0x231, 1, n)
            timer = m.u64(job + 0x80)
            if timer:
                m.call_void(m.main + 0xE63AC4, timer, 0)
            m.call(m.main + 0x113BAC0, _server(m, job), b)
        _send(m, job, 0xD8, 0x15)
        m.call_void(m.main + 0x1397D74, job)
        return 0
    if st != 3:
        return 2
    m.call_void(m.main + 0x16E4FF0, job, m.u8(job + 0xD8))
    lst = m.u64(job + 0x88)
    if lst:
        m.call_void(m.main + 0xFAF024, lst)
    if m.u32(job + 0x78) != 2:
        for s in range(5):
            server = _server(m, job)
            if not (m.call(m.main + 0x18C99A4, server, s) & 1
                    and m.call(m.main + 0xF6EF64, server, 0x47, s) & 1
                    and m.call(m.main + 0xF6F590, _server(m, job), 0x48, s) & 1):
                continue
            m.call_void(m.main + 0x18C99C0, _server(m, job), 0x47, s)
            with m.frame(0x10) as f:
                m.put(f, 8, 0)
                m.call_sret(m.main + 0xE634C8, f, _server(m, job), s)
                if m.u64(f):
                    m.call_void(m.main + 0xF6FD7C, m.u64(f), 0x48)
                    _release(m, f)
    m.call_void(m.main + 0x1397D74, job)
    return 2


# --- Wild::Setup (vtable 0x44937b0): the battle timer at +0x78, the result of its last send at +0x80 ----------

@lifted(0x2A1D814)
def map_flag(m, o, key, *_):
    """Whether the unordered map at o+0x60 (u32 keys) holds `key` with the u32 value +0x20 equal to 1."""
    from pokeldn.sv.battle.engine.containers import _hash_find_u32
    node = _hash_find_u32(m, o + 0x60, key & M32)
    return int(bool(node) and m.u32(node + 0x20) == 1)


def _erase_seated(m, job, s):
    """State 10's erase for a seated slot: 3 from what it was sent, 4 from what it sent."""
    server = _server(m, job)
    with m.frame(0x10) as f:
        m.put(f, 8, 0)
        m.call_sret(m.main + 0xF6F324, f, server, s)
        o = m.u64(f)
        if o:
            m.call_void(m.main + 0xF6FD7C, o, 3)
            _unref(m, o)
        m.call_sret(m.main + 0xE634C8, f, _server(m, job), s)
        if m.u64(f):
            m.call_void(m.main + 0xF6FD7C, m.u64(f), 4)
            if m.u64(f):
                _release(m, f)


@lifted(0x2A1F54C)
def wild_setup(m, job, *_):
    """Eleven states (jump table 0x3c61c1e): 0 message 1; 1 its answers; 2 setup kind 4 leaves through
    0x2017ba4; 3 message 0x11; 4 its answers, what each seated slot sent cleared, message 3 when the result
    byte is 1; 5 its answers gathered (0x139834c) into the server's block, message 0x13; 10 each seated slot's
    3 and 4 erased and the battle timer started or resumed."""
    st = m.u32(job + 0x68)
    if st > 10 or 6 <= st <= 9:
        return 2
    if st in (0, 3):
        _send(m, job, 0x80, 1 if st == 0 else 0x11, ALL)
        m.put(job + 0x68, 4, st + 1)
        return 0
    server = _server(m, job)
    if st in (1, 4, 5) and not _every_answered(m, server, m.u64(job + 0x88)):
        return 0
    if st == 1:
        m.put(job + 0x68, 4, 2)
        return 1
    if st == 2:
        ctx = m.u64(job + 0x40)
        if m.u32(m.u64(m.u64(ctx + 8) + 0x38) + 0x30) != 4:
            m.put(job + 0x68, 4, 3)
            return 1
        m.call_void(m.main + 0xE7D4C8, m.u64(ctx + 0x18))
        m.call_void(m.main + 0x2017BA4, job)
        return 2
    if st == 4:
        for s in range(5):
            if not _seated(m, _server(m, job), s):
                continue
            with m.frame(0x10) as f:
                m.put(f, 8, 0)
                m.call_sret(m.main + 0xE634C8, f, _server(m, job), s)
                m.call_void(m.main + 0xE0F5F8, (m.u64(f) + 0x40) & M64)
                if m.u64(f):
                    _release(m, f)
        if m.u8(job + 0x80) == 1:
            _send(m, job, 0x80, 3, ALL)
            m.put(job + 0x68, 4, 5)
        else:
            m.put(job + 0x68, 4, 10)
        return 0
    if st == 5:
        with m.frame(0x240) as b:
            m.write(b, requests.posted(0))
            m.call_void(m.main + 0x139834C, server, b, m.u64(job + 0x88))
            server = _server(m, job)
            m.put(server + 0x444, 1, 0); m.put(server + 0x440, 4, 0)
            m.write(server + 0x210, m.read(b, 0x238))
        _send(m, job, 0x80, 0x13, ALL)
        m.put(job + 0x68, 4, 10)
        return 0
    for s in range(5):
        if _seated(m, _server(m, job), s):
            _erase_seated(m, job, s)
    timer = m.u64(job + 0x78)
    if not timer:
        return 2
    if not m.u8(timer + 0x18):
        m.put(timer, 8, m.call(m.main + 0x343D5B0, m.call(m.main + 0x343C280)))
        m.put(timer + 0x18, 1, 1)
    elif m.u8(timer + 0x19) or m.u8(timer + 0x1A):
        m.call_void(m.main + 0xE63AC4, timer, 0)
    return 2


# --- the battle's end (docs/sv_raid.md, The battle's end) --------------------------------------------------

@lifted(0x18826D8)
def exp_end(m, job, *_):
    """AddExpBattleEnd (payload u8 +0x78, result +0x80): 0 a zeroed block into the server and message 0x25;
    1 every slot's answer awaited; 2 for kind 8 0x1882e24, otherwise ExitBattleEnd with the exit message
    (0x1882b14, 0x35 for none) as the continuation."""
    st = m.u32(job + 0x68)
    if st == 1:
        if _every_answered(m, _server(m, job), m.u64(job + 0x88)):
            m.call_void(m.main + 0x1397D74, job)
        return 0
    if st == 0:
        with m.frame(0x240) as b:
            m.write(b, requests.posted(0))
            m.call(m.main + 0x113BAC0, _server(m, job), b)
        _send(m, job, 0x80, 0x25)
        m.call_void(m.main + 0x1397D74, job)
        return 0
    if st != 2:
        return 2
    if m.u8(job + 0x78) == 8:
        m.call_void(m.main + 0x1882E24, job)
        return 2
    kind = m.call(m.main + 0x1882B14, job) & M32 or 0x35
    alloc = m.u64(job + 8)
    with m.frame(0x30) as f:
        m.write(f, bytes(0x30))
        m.put(f + 0x18, 4, kind)
        m.put(f + 8, 8, m.u64(job + 0x40))
        m.call_sret(m.main + 0x1882BB8, f + 0x10, alloc, f + 8, f + 0x18)
        o = m.u64(f + 0x10)
        if o:
            _add_ref(m, o)
            m.call_void(m.main + 0x13985A8, job + 0x70, o)
            _unref(m, o)
        else:
            old = m.u64(job + 0x70)
            m.put(job + 0x70, 8, 0)
            if old:
                _unref(m, old)
        _release(m, f + 0x10)
    return 2


@lifted(0x1882BB8)
def make_exit_end(m, alloc, ctx, kind, *_):
    """*x8 = an ExitBattleEnd (0x1882c7c) with a reference taken."""
    out = m.x8
    return _shared(m, out, m.call(m.main + 0x1882C7C, alloc, ctx, kind))


@lifted(0x1882C7C)
def create_exit_end(m, alloc, ctx, kind, *_):
    """Create a 0x98-byte ExitBattleEnd (0x1882dbc) for the context *ctx and the message *kind."""
    return _create(m, alloc, 0x98, lambda o: m.call_void(m.main + 0x1882DBC, o, m.u64(ctx), kind))


@lifted(0x1882DBC)
def construct_exit_end(m, o, ctx, kind, *_):
    """ExitBattleEnd (hash 0x2da7b4584624a364, vtable 0x4493b58): message u32 *kind at +0x78, result +0x80
    zero."""
    m.call_void(m.main + 0x17B4EA4, o, 0x2DA7B4584624A364, m.main + 0x4493C70, ctx)
    m.put(o, 8, m.main + 0x4493B58)
    m.put(o + 0x20, 8, m.main + 0x4493BD8); m.put(o + 0x28, 8, m.main + 0x4493C28)
    m.put(o + 0x78, 4, m.u32(kind))
    m.put(o + 0x80, 8, 0); m.put(o + 0x88, 8, 0); m.put(o + 0x90, 8, 0)


@lifted(0x1882E24)
def exp_end_other(m, job, *_):
    """The fade-out (0x186d934) as the job's continuation."""
    _continue(m, job, 0x186D934)


@lifted(0x20185AC)
def exit_end(m, job, *_):
    """ExitBattleEnd (message u32 +0x78, result +0x80): 0 the message; 1 every slot's answer awaited, then the
    next job (0x186d680)."""
    st = m.u32(job + 0x68)
    if st == 1:
        if not _every_answered(m, _server(m, job), m.u64(job + 0x88)):
            return 0
        m.call_void(m.main + 0x186D680, job)
        return 2
    if st != 0:
        return 2
    _send(m, job, 0x80, m.u32(job + 0x78))
    m.call_void(m.main + 0x1397D74, job)
    return 0


@lifted(0x186D680)
def after_exit_end(m, job, *_):
    """RaidCapture (0x186dba4) after message 0x29 with setup +0x498 bit 0x400, otherwise the fade-out
    (0x186d934), as the job's continuation."""
    if m.call(m.main + 0xFA9B4C, m.call(m.main + 0x1397D84, job), 0x400) & 1 and m.u32(job + 0x78) == 0x29:
        _continue(m, job, 0x186DBA4)
    else:
        _continue(m, job, 0x186D934)


@lifted(0x186D934)
def make_fade_out(m, alloc, ctx, arg, *_):
    """*x8 = an ExitFadeOut (0x186da08) with a reference taken."""
    out = m.x8
    with m.frame(0x10) as d:
        return _shared(m, out, m.call(m.main + 0x186DA08, d, alloc, ctx, arg))


@lifted(0x186DA08)
def create_fade_out(m, _x0, alloc, ctx, arg, *_):
    """Create a 0x90-byte ExitFadeOut (0x186db48)."""
    return _create(m, alloc, 0x90, lambda o: m.call_void(m.main + 0x186DB48, o, m.u64(ctx), arg))


def _construct_wait_job(m, o, ctx, hash_, desc, vt):
    """A job that sends one message and awaits its answers: result +0x78..+0x88 zero."""
    m.call_void(m.main + 0x17B4EA4, o, hash_, m.main + desc, ctx)
    m.put(o, 8, m.main + vt)
    m.put(o + 0x88, 8, 0)
    m.put(o + 0x20, 8, m.main + vt + 0x80); m.put(o + 0x28, 8, m.main + vt + 0xD0)
    m.put(o + 0x78, 8, 0); m.put(o + 0x80, 8, 0)


lifted(0x186DB48)(lambda m, o, ctx, *_: _construct_wait_job(m, o, ctx, 0x96D97E076DA4D5E5, 0x4493EF0, 0x4493DD8))
lifted(0x186DDA8)(lambda m, o, ctx, *_: _construct_wait_job(m, o, ctx, 0x5D3761E2D6EBCBAD, 0x4493DB0, 0x4493C98))
lifted(0x171DAB4)(lambda m, o, ctx, *_: _construct_wait_job(m, o, ctx, 0x503D3EFF7DA04A9C, 0x4494030, 0x4493F18))


@lifted(0x186DBA4)
def make_capture(m, alloc, ctx, arg, *_):
    """*x8 = a RaidCapture (0x186dc68) with a reference taken."""
    out = m.x8
    return _shared(m, out, m.call(m.main + 0x186DC68, alloc, ctx, arg))


@lifted(0x186DC68)
def create_capture(m, alloc, ctx, arg, *_):
    """Create a 0x90-byte RaidCapture (0x186dda8)."""
    return _create(m, alloc, 0x90, lambda o: m.call_void(m.main + 0x186DDA8, o, m.u64(ctx), arg))


def _wait_job(m, job, kind, then=None):
    """A job of states 0 (message `kind`, result +0x78) and 1 (every answer to step +0x80); `then` runs once
    every slot answered."""
    st = m.u32(job + 0x68)
    if st == 1:
        if not m.call(m.main + then[0], job) & 1:
            return 0
        if then[1]:
            m.call_void(m.main + then[1], job)
        return 2
    if st != 0:
        return 2
    m.call_void(m.main + kind, job)
    m.call_void(m.main + 0x1397D74, job)
    return 0


@lifted(0x1934808)
def raid_capture(m, job, *_):
    """RaidCapture: 0 message 0x49 (result +0x78); 1 every slot's answer awaited; 2 the fade-out (0x1934910)."""
    st = m.u32(job + 0x68)
    if st == 1:
        if _every_answered(m, _server(m, job), m.u64(job + 0x80)):
            m.call_void(m.main + 0x1397D74, job)
        return 0
    if st == 2:
        m.call_void(m.main + 0x1934910, job)
        return 2
    if st != 0:
        return 2
    _send(m, job, 0x78, 0x49)
    m.call_void(m.main + 0x1397D74, job)
    return 0


lifted(0x1934910)(lambda m, job, *_: _continue(m, job, 0x186D934))


@lifted(0x171D648)
def fade_out(m, job, *_):
    """ExitFadeOut: 0 message 0x35; 1 every slot's answer awaited, then the 0x37 job as the continuation."""
    return _wait_job(m, job, 0x171D6CC, (0x171D6A8, 0x171D710))


lifted(0x171D6A8)(lambda m, job, *_: _tail(m, m.main + 0xE632FC, _server(m, job), m.u64(job + 0x80)))
lifted(0x171D6CC)(lambda m, job, *_: _send(m, job, 0x78, 0x35))
lifted(0x171D710)(lambda m, job, *_: _continue(m, job, 0x171D8B0))


@lifted(0x171D8B0)
def make_fade_end(m, alloc, ctx, arg, *_):
    """*x8 = the 0x37 job (0x171d974) with a reference taken."""
    out = m.x8
    return _shared(m, out, m.call(m.main + 0x171D974, alloc, ctx, arg))


@lifted(0x171D974)
def create_fade_end(m, alloc, ctx, arg, *_):
    """Create the 0x90-byte job that sends 0x37 (0x171dab4)."""
    return _create(m, alloc, 0x90, lambda o: m.call_void(m.main + 0x171DAB4, o, m.u64(ctx), arg))


@lifted(0x163B220)
def fade_end(m, job, *_):
    """The fade-out's last job: 0 message 0x37; 1 every slot's answer awaited. Nothing follows it."""
    return _wait_job(m, job, 0x163B29C, (0x163B278, 0))


lifted(0x163B278)(lambda m, job, *_: _tail(m, m.main + 0xE632FC, _server(m, job), m.u64(job + 0x80)))
lifted(0x163B29C)(lambda m, job, *_: _send(m, job, 0x78, 0x37))


@lifted(0x201716C)
def make_exit_end_2(m, alloc, ctx, kind, *_):
    """*x8 = an ExitBattleEnd (0x20178ac) with a reference taken."""
    out = m.x8
    return _shared(m, out, m.call(m.main + 0x20178AC, alloc, ctx, kind))


@lifted(0x20178AC)
def create_exit_end_2(m, alloc, ctx, kind, *_):
    """Create a 0x98-byte ExitBattleEnd (0x1882dbc)."""
    return _create(m, alloc, 0x98, lambda o: m.call_void(m.main + 0x1882DBC, o, m.u64(ctx), kind))
