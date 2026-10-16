"""A round's request block and the path that fills it: one slot's type-6 command message copied into a
zeroed block on a poster's stack, the block posted as a job, the job copying it to the server and running
the builder (docs/sv_raid.md, Actions)."""

from pokeldn.sv.battle.machine import UnliftedCall, lifted

BLOCK = 0x238                   # five slot blocks of 0x70, then a count byte per slot at +0x230
SLOT = 0x70
ACTION = 0x10                   # u64 word, u32 actor, 4 bytes no poster writes
COUNTS = 0x230
COMMAND = 0xE8                  # a type-6 message: 0x20-byte header, count +0x20, actions from +0x28
SINGLE = 0x30                   # a type-0x10 message: one action, word +0x20, actor +0x28
UNWRITTEN = tuple(o for a in range(COUNTS // ACTION) for o in range(ACTION * a + 0xC, ACTION * a + 0x10)) + \
    (0x235, 0x236, 0x237)       # bytes of a posted block the game copies from uninitialised stack


def _release(m, holder):
    o = m.u64(holder)
    if o:
        c = m.u64(o + 0x30)
        n = m.u16(c + 0x1A)
        if n == 0:
            raise UnliftedCall("abort: ReleaseReference")
        m.put(c + 0x1A, 2, n - 1)
        if n == 1:
            m.put(c + 0x10, 8, 0)
            m.vcall_void(o, 0x50)


def _add_ref(m, o):
    """AddReference on o's control block ([+0x30], u16 +0x1a); the first one builds +8 from +0x10's vf 0
    and sets +0x1c to -2."""
    c = m.u64(o + 0x30)
    if not m.u64(c + 0x10):
        raise UnliftedCall("abort: AddReference on a null object")
    n = m.u16(c + 0x1A)
    m.put(c + 0x1A, 2, n + 1)
    if n == 0:
        src = m.u64(c + 0x10)
        m.put(c + 8, 8, m.call(m.u64(m.u64(src)), src))
        m.put(c + 0x1C, 4, 0xFFFFFFFE)
    elif n == 0xFFFF:
        raise UnliftedCall("abort: AddReference overflow")


@lifted(0xE63734)
def find_step(m, q, step, *_):
    """The first message of q's deque (map +0x48/+0x50, start +0x80, size +0x88, 512 pointers a block)
    whose header step (u64 [msg+0x40]+8) is `step`, into *x8 with a reference taken; 0 when none. Each
    message looked at is referenced and released around the read."""
    out = m.x8
    start = m.u64(q + 0x80)
    mb, me = m.u64(q + 0x48), m.u64(q + 0x50)
    blk = mb + ((start >> 9) << 3)

    def at(i):
        return m.u64(mb + ((i >> 9) << 3)) + ((i & 0x1FF) << 3)
    if me == mb:
        it = end = 0
    else:
        it, end = m.u64(blk) + ((start & 0x1FF) << 3), at(start + m.u64(q + 0x88))
    while it != end:
        e = m.u64(it)
        if e:
            _add_ref(m, e)
            s = m.u64(m.u64(e + 0x40) + 8)
            with m.frame(0x10) as h:
                m.put(h, 8, e)
                _release(m, h)
            if s == step:
                break
        it += 8
        if it - m.u64(blk) == 0x1000:
            blk += 8
            it = m.u64(blk)
    stop = 0 if m.u64(q + 0x50) == m.u64(q + 0x48) else at(m.u64(q + 0x80) + m.u64(q + 0x88))
    if stop == it:
        m.put(out, 8, 0)
        return out
    e = m.u64(it)
    m.put(out, 8, e)
    if e:
        _add_ref(m, e)
    return out


def copy_actions(m, block, slot, payload, count):
    """0xf7065c's copy: `count` actions from payload+0x28 (u64 word, then the actor's low u32) to slot's
    block, each raising the slot's count byte. No bound: a count over 7 runs into the next slot."""
    base = block + SLOT * (slot & 0xFF)
    counter = block + (slot & 0xFF) + COUNTS
    for i in range(count):
        m.put(base + ACTION * i, 8, m.u64(payload + 0x28 + ACTION * i))
        m.put(base + ACTION * i + 8, 4, m.u32(payload + 0x30 + ACTION * i))
        m.put(counter, 1, m.u8(counter) + 1)


@lifted(0xF6FC54)
def copy_action(m, dst, src, *_):
    """One request block action: the u64 word and the u32 actor."""
    m.put(dst, 8, m.u64(src))
    m.put(dst + 8, 4, m.u32(src + 8))
    return dst


@lifted(0xF7065C)
def take_command(m, store, block, key, slot, *_):
    """Slot's count byte cleared, then slot's message `key` from the store (0xe634c8 by slot, 0xf6f0a8
    by key): a 0xe8-byte one has its actions copied into the block (copy_actions); the key is erased
    (0xf6fd7c) and both references dropped."""
    slot &= 0xFFFFFFFF
    m.put(block + (slot & 0xFF) + COUNTS, 1, 0)
    with m.frame(0x10) as f:
        e, msg = f, f + 8
        m.call_sret(m.main + 0xE634C8, e, store, slot)
        if not m.u64(e):
            return
        m.call_sret(m.main + 0xF6F0A8, msg, m.u64(e), key & 0xFFFFFFFF)
        p = m.u64(msg)
        if p:
            if m.u32(p + 0x48) == COMMAND:
                payload = m.u64(p + 0x40)
                count = m.u8(payload + 0x20)
                if count:
                    copy_actions(m, block, slot, payload, count)
            m.call_void(m.main + 0xF6FD7C, m.u64(e), key & 0xFFFFFFFF)
            _release(m, msg)
        _release(m, e)


@lifted(0xF72038)
def take_action(m, store, block, key, slot, *_):
    """take_command for a 0x30-byte message of one action (word +0x20, actor +0x28), taken while the
    slot holds at most six."""
    slot &= 0xFFFFFFFF
    counter = block + (slot & 0xFF) + COUNTS
    m.put(counter, 1, 0)
    with m.frame(0x10) as f:
        e, msg = f, f + 8
        m.call_sret(m.main + 0xE634C8, e, store, slot)
        if not m.u64(e):
            return
        m.call_sret(m.main + 0xF6F0A8, msg, m.u64(e), key & 0xFFFFFFFF)
        p = m.u64(msg)
        if p:
            if m.u32(p + 0x48) == SINGLE:
                n = m.u8(counter)
                if n <= 6:
                    payload = m.u64(p + 0x40)
                    a = block + SLOT * (slot & 0xFF) + ACTION * n
                    m.put(a, 8, m.u64(payload + 0x20))
                    m.put(a + 8, 4, m.u32(payload + 0x28))
                    m.put(counter, 1, m.u8(counter) + 1)
                m.call_void(m.main + 0xF6FD7C, m.u64(e), key & 0xFFFFFFFF)
            _release(m, msg)
        _release(m, e)


@lifted(0xF702EC)
def gather(m, reader, block, done_key, key, *_):
    """A per-slot reader's actions into a posted block: the reader's store [+0x30] and slot u32 [+0x38];
    key 0x10 through take_action, any other through take_command; then `done_key` is erased from the
    reader's entry 0xf6f324(store, slot)."""
    slot = m.u32(reader + 0x38)
    store = m.u64(reader + 0x30)
    if key & 0xFFFFFFFF == 0x10:
        m.call_void(m.main + 0xF72038, store, block, 0x10, slot)
    else:
        m.call_void(m.main + 0xF7065C, store, block, key, slot)
    with m.frame(0x10) as f:
        m.call_sret(m.main + 0xF6F324, f, m.u64(reader + 0x30), slot)
        if m.u64(f):
            m.call_void(m.main + 0xF6FD7C, m.u64(f), done_key & 0xFFFFFFFF)
            _release(m, f)


@lifted(0x113BAC0)
def load_request(m, server, src, *_):
    """The posted block into the server's request block at +0x210 (count bytes +0x440, +0x444 cleared
    first)."""
    m.put(server + 0x444, 1, 0)
    m.put(server + 0x440, 4, 0)
    m.write(server + 0x210, m.read(src, BLOCK))
    return server + 0x210


def command(actions, header=bytes(0x20)):
    """A type-6 command message's 0xe8 bytes: the header, the count at +0x20, then (word, actor) pairs
    as u64 each from +0x28."""
    out = bytearray(COMMAND)
    out[:0x20] = header
    out[0x20] = len(actions)
    for i, (word, actor) in enumerate(actions):
        out[0x28 + ACTION * i:0x38 + ACTION * i] = word.to_bytes(8, "little") + actor.to_bytes(8, "little")
    return bytes(out)


def posted(kind, commands=()):
    """The 0x240 bytes a poster hands the round job (0xf6e6a8 for kind 0x15): every action's word and
    actor zeroed, the counts zeroed, the kind u32 at +0x238, then each (slot, command message) copied in
    as take_command copies it. The bytes the poster never writes are zero here (UNWRITTEN)."""
    from pokeldn.sv.battle.machine import Machine
    t = Machine({0: bytearray(0x1000)})
    t.put(BLOCK, 4, kind)
    for slot, msg in commands:
        t.write(0x400, msg)
        t.put(COUNTS + slot, 1, 0)
        copy_actions(t, 0, slot, 0x400, msg[0x20])
    return t.read(0, 0x240)


def step(m, server, kind, block=None):
    """One builder step as the round job runs it (0x16e4f84 -> 0x113bad8, up to the builder): the posted
    block (`block`, 0x240 bytes, kind at +0x238) into the server (load_request), the step counter
    server+0x198 raised, no body already received for that step in [[server+0x448]+0x38]
    (find_step), the builder 0x113c8a0 on [server+0x448] with the round counter server+0x488.
    Returns the body (b"" when the kind leaves none)."""
    if block is not None:
        with m.frame(0x240) as f:
            m.write(f, block)
            load_request(m, server, f)
    n = m.u64(server + 0x198) + 1
    m.put(server + 0x198, 8, n)
    b = m.u64(server + 0x448)
    with m.frame(0x10) as f:
        if m.u64(b + 0x38):
            m.call_sret(m.main + 0xE63734, f, m.u64(b + 0x38), n)
            if m.u64(f):
                raise UnliftedCall("0x113bad8 with a received body for the step (0x113c234)")
        m.call_void(m.main + 0x113C8A0, b, f, f + 8, server + 0x488, kind)
        size = m.u32(f + 8)
        return m.read(m.u64(f), size) if size else b""


def run_round(m, server, commands):
    """A round (kind 0x15) from each acting slot's command: commands is [(slot, [(word, actor), ...])],
    the slot's actions in the order its station sent them. Returns the round's body."""
    return step(m, server, 0x15, posted(0x15, [(s, command(a)) for s, a in commands]))


def move(move_id, target, flag=0):
    """An action word of kind 1: a move at a battle position (bits 4..7), the move in bits 8..23, bit 25
    the flag the decoder keeps at entry +0x12."""
    return 1 | (target & 0xF) << 4 | (move_id & 0xFFFF) << 8 | (flag & 1) << 25
