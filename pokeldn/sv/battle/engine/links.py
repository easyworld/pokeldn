"""The raid battle's run step 0x2d383b8 and the server's incoming links (0xe0f040, 0xe0fd68, 0xe0f854)
(docs/sv_raid.md, The server's flow)."""

from pokeldn.sv.battle.engine.calls import M32, _s32
from pokeldn.sv.battle.engine.containers import _hash_find_u32
from pokeldn.sv.battle.engine.requests import _add_ref
from pokeldn.sv.battle.engine.steps import _create
from pokeldn.sv.battle.machine import UnliftedCall, lifted  # noqa: F401

M64 = 0xFFFFFFFFFFFFFFFF


def _drop(m, o):
    """ReleaseReference on o's control block; the last one clears +0x10 and runs o's vf 0x50."""
    c = m.u64(o + 0x30)
    n = m.u16(c + 0x1A)
    if n == 0:
        raise UnliftedCall("abort: ReleaseReference underflow")
    m.put(c + 0x1A, 2, n - 1)
    if n == 1:
        m.put(c + 0x10, 8, 0)
        m.vcall_void(o, 0x50)


def _lend(m, o, call):
    """A strong copy of o on the stack, passed by address to call(at); the copy's reference on o is
    released after the call (the game releases the value it copied, not the slot)."""
    with m.frame(0x10) as t:
        m.put(t, 8, o)
        if o:
            _add_ref(m, o)
        r = call(t)
        if o:
            _drop(m, o)
    return r


def _at(m, q, i):
    """The element slot of deque<T*> q (map begin +0x48, 0x200 pointers a block) at absolute index i."""
    i &= M64
    return m.u64(m.u64(q + 0x48) + ((i >> 6) & 0x3FFFFFFFFFFFFF8)) + 8 * (i & 0x1FF)


def _element(m, q, i):
    """deque q's element i (start +0x80 plus the sign-extended i) when i is below the u32 size +0x88,
    else 0."""
    if (i & M32) < (m.u64(q + 0x88) & M32):
        return m.u64(_at(m, q, m.u64(q + 0x80) + _s32(i)))
    return 0


@lifted(0xE0F440)
def incoming_link(m, server, slot, *_):
    """Writes to x8 a strong reference to what `slot` sent the server: the link at node+0x20 of the
    u32-keyed map at server+0x1a0 (node+0x18 is the outgoing link), or 0."""
    out = m.x8
    node = _hash_find_u32(m, server + 0x1A0, slot & M32)
    o = m.u64(node + 0x20) if node else 0
    m.put(out, 8, o)
    if o:
        _add_ref(m, o)
    return out


@lifted(0xE0F040)
def drain_slots(m, server, *_):
    """For slots 0 to 4: every message of the slot's incoming link [link+0x48] pushed (0x113d5e0) onto
    the queue [server+0x58], then the link's deque cleared (0xe0f5f8)."""
    with m.frame(0x10) as f:
        for slot in range(5):
            m.call_sret(m.main + 0xE0F440, f + 8, server, slot)
            link = m.u64(f + 8)
            if not link:
                continue
            q = m.u64(link + 0x48)
            if q:
                _add_ref(m, q)
            n = m.u64(q + 0x88)
            if n & M32:
                i = 0
                while True:
                    e = _element(m, q, i)
                    m.put(f, 8, e)
                    if e:
                        _add_ref(m, e)
                        _add_ref(m, e)
                    m.call_void(m.main + 0x113D5E0, m.u64(server + 0x58), f)
                    t = m.u64(f)
                    if t:
                        _drop(m, t)
                    if e:
                        _drop(m, e)
                    i = (i + 1) & M32
                    if i == n & M32:
                        break
            m.call_void(m.main + 0xE0F5F8, m.u64(m.u64(f + 8) + 0x48) + 0x40)
            _drop(m, q)
            link = m.u64(f + 8)
            if link:
                _drop(m, link)


@lifted(0xE0F854)
def drain_own(m, server, *_):
    """The incoming link of slot 0xff (the server's own): each message in turn, while the result stays
    0 or 4: a step-0 header gives 4; with 0x16f814c([server+0x30]) set, type 2 goes to 0xe106a4(server, 0xff)
    and other types give 0; unset, type 0x3f pushes a message of 0x2897dec onto the server's own link
    (0x113d184, 0x113d4a0) and gives 2 (stop), other types 0. Then the link's deque is cleared."""
    with m.frame(0x20) as f:
        m.call_sret(m.main + 0xE0F440, f + 0x18, server, 0xFF)
        link = m.u64(f + 0x18)
        if not link:
            return
        q = m.u64(link + 0x48)
        if q:
            _add_ref(m, q)
        n = m.u64(q + 0x88)
        if n & M32:
            i = 0
            while True:
                e = _element(m, q, i)
                _add_ref(m, e)
                hdr = m.u64(e + 0x40)
                if m.u64(hdr + 8) == 0:
                    r = 4
                else:
                    kind = m.u32(hdr)
                    r = 0
                    if m.call(m.main + 0x16F814C, m.u64(server + 0x30)) & 0xFF:
                        if kind == 2:
                            _lend(m, e, lambda t: m.call_void(m.main + 0xE106A4, server, 0xFF, t))
                    elif kind == 0x3F:
                        m.call_sret(m.main + 0x113D184, f + 0x10, server, 0xFF)
                        own = m.u64(f + 0x10)
                        if own:
                            m.call_sret(m.main + 0x2897DEC, f + 8, server)
                            m.call_void(m.main + 0x113D4A0, own, f + 8)
                            t = m.u64(f + 8)
                            if t:
                                _drop(m, t)
                        t = m.u64(f + 0x10)
                        if t:
                            _drop(m, t)
                        r = 2
                _drop(m, e)
                if r == 2:
                    break
                i = (i + 1) & M32
                if i == n & M32:
                    break
            m.call_void(m.main + 0xE0F5F8, m.u64(m.u64(f + 0x18) + 0x48) + 0x40)
        _drop(m, q)
        link = m.u64(f + 0x18)
        if link:
            _drop(m, link)


@lifted(0xE10384)
def take_at(m, q, i, *_):
    """Writes to x8 a strong reference to deque q's element i (u32 size +0x88) and erases it from q
    (0x131be1c on q+0x40); 0 when i is out of range or the element is null."""
    out = m.x8
    e = m.u64(_at(m, q, m.u64(q + 0x80) + _s32(i))) if (m.u32(q + 0x88) > (i & M32)) else 0
    m.put(out, 8, e)
    if e:
        _add_ref(m, e)
    if not m.u64(out):
        m.put(out, 8, 0)
        return out
    start = m.u64(q + 0x80)
    begin, end = m.u64(q + 0x48), m.u64(q + 0x50)
    mp = begin + ((start >> 6) & 0x3FFFFFFFFFFFFF8)
    it = m.u64(mp) + 8 * (start & 0x1FF) if end != begin else 0
    if i & M32:
        off = ((it - m.u64(mp)) >> 3) + _s32(i)
        if off >= 1:
            mp += (off >> 6) & 0x3FFFFFFFFFFFFF8
            it = m.u64(mp) + 8 * (off & 0x1FF)
        else:
            back = 0x1FF - off
            lo = 0x3FE - off if back < 0 else back
            mp -= 8 * (lo >> 9)
            it = (m.u64(mp) + 8 * ((lo & ~0x1FF) - back) + 0xFF8) & M64
    m.call_void(m.main + 0x131BE1C, q + 0x40, mp, it)
    return out


@lifted(0xE11010)
def push_outgoing(m, link, src, *_):
    """The message *src onto the outgoing link [link+0x58] (0x113d4a0), through a strong copy."""
    out = m.u64(link + 0x58)
    _lend(m, m.u64(src), lambda t: m.call_void(m.main + 0x113D4A0, out, t))


@lifted(0xE10544)
def forward(m, server, src, *_):
    """The message *src onto [server+0x40]'s outgoing link (0xe11010) when [server+0x40] is set."""
    target = m.u64(server + 0x40)
    if not target:
        return
    _lend(m, m.u64(src), lambda t: m.call_void(m.main + 0xE11010, target, t))


@lifted(0x2897FC4)
def ref_a8(m, o, *_):
    """Writes to x8 a strong reference to [o+0xa8]."""
    out = m.x8
    v = m.u64(o + 0xA8)
    m.put(out, 8, v)
    if v:
        _add_ref(m, v)
    return out


@lifted(0x2898084)
def ref_b0(m, o, *_):
    """Writes to x8 a strong reference to [o+0xb0]."""
    out = m.x8
    v = m.u64(o + 0xB0)
    m.put(out, 8, v)
    if v:
        _add_ref(m, v)
    return out


@lifted(0x2897CEC)
def boss_list_in(m, server, src, *_):
    """Message 0x51: its body (header +0x20) to the per-frame machine's vf 0x78 (0x2016290), the machine
    being [[[server+0x30]+0xa8]+0xb0]."""
    body = m.u64(m.u64(src) + 0x40) + 0x20
    with m.frame(0x10) as f:
        m.call_sret(m.main + 0x2897FC4, f, m.u64(server + 0x30))
        m.call_sret(m.main + 0x2898084, f + 8, m.u64(f))
        m.vcall_void(m.u64(f + 8), 0x78, body)
        o = m.u64(f + 8)
        if o:
            _drop(m, o)
        o = m.u64(f)
        if o:
            _drop(m, o)


@lifted(0xE0FD68)
def drain_queue(m, server, *_):
    """The first message taken from the queue [server+0x58] (0xe10384 index 0). A step-0 header: type 0x51
    to the per-frame machine (0x2897cec) and forwarded (0xe10544), 0x4f to 0x2897b08 with the header's
    slot +0x19, 0x46 to 0x2897afc([server+0x48]). Otherwise, when 0xe106a4 (server, slot) accepts it:
    0xe108b4, forwarded (0xe10544) and 0xe10d38."""
    with m.frame(0x10) as f:
        m.call_sret(m.main + 0xE10384, f, m.u64(server + 0x58), 0)
        msg = m.u64(f)
        if not msg:
            return
        hdr = m.u64(msg + 0x40)
        slot = m.u8(hdr + 0x19)
        if m.u64(hdr + 8) == 0:
            kind = m.u32(hdr)
            if kind == 0x51:
                _lend(m, msg, lambda t: m.call_void(m.main + 0x2897CEC, server, t))
                _lend(m, m.u64(f), lambda t: m.call_void(m.main + 0xE10544, server, t))
            elif kind == 0x4F:
                _lend(m, msg, lambda t: m.call_void(m.main + 0x2897B08, server, slot, t))
            elif kind == 0x46:
                x = m.u64(server + 0x48)
                if x:
                    m.call_void(m.main + 0x2897AFC, x)
        else:
            ok = _lend(m, msg, lambda t: m.call(m.main + 0xE106A4, server, slot, t))
            if ok & 1:
                _lend(m, m.u64(f), lambda t: m.call_void(m.main + 0xE108B4, server, slot, t))
                _lend(m, m.u64(f), lambda t: m.call_void(m.main + 0xE10544, server, t))
                _lend(m, m.u64(f), lambda t: m.call_void(m.main + 0xE10D38, server, t))
        msg = m.u64(f)
        if msg:
            _drop(m, msg)


@lifted(0xF5B444)
def oldest_pending(m, o, keep, *_):
    """Writes to x8 a strong reference to the message of least step (header +8) in the deque
    [[o+0x60]+0x48] whose type is none of 0x11..0x20, 0x23..0x26, 0x4d, 0x4e and whose header +0x10 is at
    most [o+0xe8] (0xf5b304 assigns it); 0 when none. Without bit 0 of `keep`, a found one goes to
    0xf5bd98 with its step."""
    out = m.x8
    p = m.u64(o + 0x60)
    q = m.u64(p + 0x48) if p else 0
    if not q:
        m.put(out, 8, 0)
        return out
    _add_ref(m, q)
    m.put(out, 8, 0)
    n = m.u64(q + 0x88)
    if n & M32:
        i = 0
        while True:
            e = _element(m, q, i)
            if e:
                _add_ref(m, e)
            hdr = m.u64(e + 0x40)
            t = m.u32(hdr)
            u = (t - 0x23) & M32
            if ((t - 0x11) & M32) >= 0x10 and not (u <= 0x2B and (0xC000000000F >> u) & 1) \
                    and m.u64(hdr + 0x10) <= m.u64(o + 0xE8):
                cur = m.u64(out)
                if not cur or m.u64(hdr + 8) < m.u64(m.u64(cur + 0x40) + 8):
                    m.call_void(m.main + 0xF5B304, out, e)
            if e:
                _drop(m, e)
            i = (i + 1) & M32
            if i == n & M32:
                break
    if not keep & 1:
        cur = m.u64(out)
        if cur:
            m.call_void(m.main + 0xF5BD98, m.u64(m.u64(o + 0x60) + 0x48), m.u64(m.u64(cur + 0x40) + 8))
    _drop(m, q)
    return out


@lifted(0x2898350)
def send_46(m, server, *_):
    """When [server+0x40] is set: a message of type 0x46 (step 0, destination 5, slot [[server+0x30]+0x95],
    a 4-byte zero body) made from [server+8] and pushed onto [server+0x40]'s outgoing link (0xe11010)."""
    target = m.u64(server + 0x40)
    if not target:
        return
    with m.frame(0x30) as f:
        body, hdr = f + 0xC, f + 0x10
        m.write(f, bytes(0x30))
        m.put(hdr, 4, 0x46)
        m.put(hdr + 0x18, 1, 5)
        m.put(hdr + 0x19, 1, m.u8(m.u64(server + 0x30) + 0x95))
        msg = _create(m, m.u64(server + 8), 0x50,
                      lambda o: m.call_void(m.main + 0x1227714, o, hdr, body, 4))
        _add_ref(m, msg)
        target = m.u64(server + 0x40)
        _lend(m, msg, lambda t: m.call_void(m.main + 0xE11010, target, t))
        _drop(m, msg)


@lifted(0x2893870)
def client_finish(m, client, *_):
    """Byte client+0xe5 = 1: the client's step 0xf59e54 then answers 1 at once."""
    m.put(client + 0xE5, 1, 1)


@lifted(0x2893238)
def finish_clients(m, n, *_):
    """0x2893870 on each client object N+0xb8 + 8i that is set, then on [N+0x108]."""
    for off in (0xB8, 0xC0, 0xC8, 0xD0, 0xD8, 0x108):
        o = m.u64(n + off)
        if o:
            m.call_void(m.main + 0x2893870, o)


def _member_call(m, obj):
    """The pointer to member {fn +0xd0, adj +0xd8} of obj, called on obj (Itanium ARM64: adj bit 0 marks
    a virtual function, fn then a vtable offset)."""
    fn, adj = m.u64(obj + 0xD0), m.u64(obj + 0xD8)
    this = (obj + (adj >> 1 if adj < 1 << 63 else (adj - (1 << 64)) >> 1)) & M64
    if adj & 1:
        fn = m.u64(m.u64(this) + fn)
    return m.call(fn, this)


def _source_call(m, n, slot, *args):
    """vf `slot` of the object [N+0x138], under the two references the game takes around the call."""
    a = m.u64(n + 0x138)
    _add_ref(m, a)
    b = m.u64(n + 0x138)
    if b:
        _add_ref(m, b)
    r = m.vcall(b, slot, *args)
    if b:
        _drop(m, b)
    _drop(m, a)
    return r


@lifted(0x2D383B8)
def raid_run_step(m, n, *_):
    """One frame of the raid battle: until N+0x9e bit 0, [N+0x138]'s vf 0x68 is asked and a yes sets the
    bit and runs 0x2893238(N); with the bit set, bit 1 ends the battle at once (1). With setup [N+0x38]
    +0x34 = 2 and +0x8d in 1..3, 5 or 6, each empty seat N+0xb8 + 8i the battle mode admits (0xe7e2a0)
    and [N+0x138]'s vf 0x80 refuses goes to 0x18a827c(N, i). Then the incoming server of [N+0xb0]
    (0xe0f040, 0xe0fd68, 0xe0f854), the job graph 0xfc363c([N+0xa8], 1) and on its yes 0x2898350([N+0xb0]),
    and each seated slot object's member call until it answers 1 (done bytes N+0x78..0x7c). The result:
    1 when every seated slot is done, else N+0xa0 != 0."""
    flags = m.u8(n + 0x9E)
    if flags & 1:
        if flags & 2:
            return 1
    elif m.u64(n + 0x138):
        if _source_call(m, n, 0x68) & 1:
            m.put(n + 0x9E, 1, m.u8(n + 0x9E) | 1)
            m.call_void(m.main + 0x2893238, n)
    setup = m.u64(n + 0x38)
    if m.u32(setup + 0x34) == 2:
        kind = m.u8(setup + 0x8D)
        if ((kind - 5) & M32) < 2 or ((kind - 1) & M32) <= 2:
            rules = m.u64(m.u64(m.u64(n + 0x170) + 0x290) + 8)
            for i in range(5):
                if m.u64(n + 0xB8 + 8 * i):
                    continue
                if not m.call(m.main + 0xE7E2A0, m.u32(rules + 0x36C), m.u8(rules + 0x370), i) & 1:
                    continue
                if not m.u64(n + 0x138):
                    continue
                if not _source_call(m, n, 0x80, i) & 1:
                    m.call_void(m.main + 0x18A827C, n, i)
    server = m.u64(n + 0xB0)
    m.call_void(m.main + 0xE0F040, server)
    m.call_void(m.main + 0xE0FD68, server)
    m.call_void(m.main + 0xE0F854, server)
    if m.call(m.main + 0xFC363C, m.u64(n + 0xA8), 1) & 1:
        m.call_void(m.main + 0x2898350, m.u64(n + 0xB0))
    for i in range(5):
        obj = m.u64(n + 0xB8 + 8 * i)
        if obj and not m.u8(n + 0x78 + i):
            m.put(n + 0x78 + i, 1, _member_call(m, obj) & 1)
    for i in range(5):
        if m.u64(n + 0xB8 + 8 * i) and not m.u8(n + 0x78 + i):
            return 1 if m.u8(n + 0xA0) else 0
    return 1
