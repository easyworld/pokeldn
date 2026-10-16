"""Function-local statics: the __cxa guards, the constructors they run, and the class checks against the
statics they build."""

from pokeldn.sv.battle.engine.calls import M32
from pokeldn.sv.battle.machine import UnliftedCall, lifted


@lifted(0x343CF20)
def guard_release(m, guard, *_):
    """__cxa_guard_release (the SDK's, through [0x46ca088]): byte 0 and byte 1 (complete) set to 1 under
    the guard mutex; a waiter (byte 1 bit 2) needs the condition variable."""
    from pokeldn.sv.battle.machine import UnliftedCall
    if m.u8(guard + 1) >> 2 & 1:
        raise UnliftedCall("guard release with a waiter")
    m.put(guard, 1, 1)
    m.put(guard + 1, 1, 1)
    return 0


def _static_chain(m, levels):
    """Function-local statics nested in each other: each (guard GOT, slot GOT) level, once built, holds
    the address of the next level's slot (the last holds 0)."""
    guard, slot = (m.u64(m.main + a) for a in levels[0])
    if m.u8(guard) & 1 or m.call(m.main + 0x343CF10, guard) & 0xFFFFFFFF == 0:
        return
    if len(levels) > 1:
        _static_chain(m, levels[1:])
        m.put(slot, 8, m.u64(m.main + levels[1][1]))
    else:
        m.put(slot, 8, 0)
    m.call_void(m.main + 0x343CF20, guard)


@lifted(0x1A07AA4)
def static_1a07aa4(m, *_):
    """A four-level static chain (guards 0x46d3e70, 0x46d3aa8, 0x46d39b0, 0x46d39c0); its outer slot."""
    _static_chain(m, ((0x46D3E70, 0x46D3E78), (0x46D3AA8, 0x46D3AB0), (0x46D39B0, 0x46D39B8),
                      (0x46D39C0, 0x46D39C8)))
    return m.u64(m.main + 0x46D3E78)


def _holds_pokeparam_type(m, p):
    """Whether the type chain p+0x28 vf 0 returns (linked by +0) holds the static 0x46dcd58 (built by
    0x19f5520 on first use); with x0 as the game leaves it when the chain does not."""
    t = x0 = m.vcall(p + 0x28, 0)
    guard = m.u64(m.main + 0x46DCD50)
    if m.u8(guard) & 1 == 0:
        x0 = m.call(m.main + 0x343CF10, guard) & 0xFFFFFFFF
        if x0:
            m.put(m.u64(m.main + 0x46DCD58), 8, m.call(m.main + 0x19F5520))
            x0 = m.call(m.main + 0x343CF20, guard)
    want = m.u64(m.main + 0x46DCD58)
    while t:
        if t == want:
            return True, x0
        t = m.u64(t)
    return False, x0


def _holds_static(m, pp):
    x = m.vcall(pp + 0x28, 0)
    static = m.u64(m.main + 0x46DCD58)
    while x and x != static:
        x = m.u64(x)
    return x != 0


@lifted(0x87C6F4)
def static_87c6f4(m, *_):
    """Thunk (this - 0x28) tail-calling 0x87c3c0, a function-local static: [0x46d3ab0], read only once
    its guard [0x46d3aa8] is set."""
    if m.u8(m.u64(m.main + 0x46D3AA8)) & 1 == 0:
        raise UnliftedCall("static 0x46d3ab0 not built")
    return m.u64(m.main + 0x46D3AB0)


@lifted(0xF53840)
def static_4765a30(m, *_):
    """A function-local static, built on first use; the engine only reads one already built."""
    if m.u8(m.main + 0x4765A38) & 1 == 0:
        raise UnliftedCall("static 0x4765a30 not built")
    return m.main + 0x4765A30


@lifted(0x2D1FF04)
def static_46dcd58(m, *_):
    """The Pokemon parameter class's static [0x46dcd58] (guard [0x46dcd50]), built from 0x19f5520 on
    first use; returns its address."""
    guard = m.u64(m.main + 0x46DCD50)
    if m.u8(guard) & 1 == 0 and m.call(m.main + 0x343CF10, guard) & M32:
        m.put(m.u64(m.main + 0x46DCD58), 8, m.call(m.main + 0x19F5520))
        m.call_void(m.main + 0x343CF20, guard)
    return m.u64(m.main + 0x46DCD58)


@lifted(0x19F5520)
def static_19f5520(m, *_):
    """A four-level static chain (guards 0x46d3ca8, 0x46d3aa8, 0x46d39b0, 0x46d39c0); its outer slot."""
    _static_chain(m, ((0x46D3CA8, 0x46D3CB0), (0x46D3AA8, 0x46D3AB0), (0x46D39B0, 0x46D39B8),
                      (0x46D39C0, 0x46D39C8)))
    return m.u64(m.main + 0x46D3CB0)


def _static_46d3f08(m):
    """The address of the static built by 0x1a07aa4; the engine only reads one already built."""
    if m.u8(m.u64(m.main + 0x46D3F00)) & 1 == 0:
        raise UnliftedCall("static 0x46d3f08 not built")
    return m.u64(m.main + 0x46D3F08)


def _has_static(m, obj):
    """Whether the list returned by the first virtual of the subobject at +0x28 holds that static."""
    node = m.vcall(obj + 0x28, 0)
    target = _static_46d3f08(m)
    while node:
        if node == target:
            return True
        node = m.u64(node)
    return False


def _held_static(m, b):
    """Whether b's list at +0x28 (vf 0 of that subobject) holds the static at 0x46d3f08."""
    node = m.vcall(b + 0x28, 0)
    static = m.call(m.main + 0x2D1FD38)
    while node and node != static:
        node = m.u64(node)
    return node != 0


@lifted(0x2D02BE8)
def static_476a198(m, *_):
    """The function-local static at main+0x476a198 (guard byte 0x476a1a0), built from 0x28024a0."""
    guard = m.main + 0x476A1A0
    if m.u8(guard) & 1 == 0 and m.call(m.main + 0x343CF10, guard) & M32:
        m.put(m.main + 0x476A198, 8, m.call(m.main + 0x28024A0))
        m.call_void(m.main + 0x343CF20, guard)
    return m.main + 0x476A198


@lifted(0x2D37AA8)
def static_46e2f70(m, *_):
    """The function-local static [0x46e2f70] (guard [0x46e2f68]), built from 0x28024a0."""
    guard = m.u64(m.main + 0x46E2F68)
    if m.u8(guard) & 1 == 0 and m.call(m.main + 0x343CF10, guard) & M32:
        slot = m.u64(m.main + 0x46E2F70)
        m.put(slot, 8, m.call(m.main + 0x28024A0))
        m.call_void(m.main + 0x343CF20, guard)
    return m.u64(m.main + 0x46E2F70)


def _raid_class(m, b):
    """Whether battler b's class list (vf 0 of b+0x28) holds the static 0x46d3f08; refuses while the
    static is not built (0x2d1fd38 builds it)."""
    node = m.vcall(b + 0x28, 0)
    static = m.call(m.main + 0x2D1FD38)
    while node:
        if node == static:
            return True
        node = m.u64(node)
    return False


def _static_built(m, guard_got):
    """A function-local static's guard (its address at main+guard_got); the engine never builds one."""
    if m.u8(m.u64(m.main + guard_got)) & 1 == 0:
        raise UnliftedCall(f"static guard [main+0x{guard_got:x}] not built")


def _in_class(m, obj, static_got):
    """Whether obj's class list (vf 0 of obj) holds the static whose address is at main+static_got."""
    node, static = m.vcall(obj, 0), m.u64(m.main + static_got)
    while node:
        if node == static:
            return True
        node = m.u64(node)
    return False


@lifted(0x343CF10)
def guard_acquire(m, guard, *_):
    """__cxa_guard_acquire (the SDK's 0x53c49a0, through [0x46ca080]): 0 when byte 0 says built or byte 1
    reads 1 (released); else byte 1 = 2 (in progress) and 1. A guard in progress elsewhere waits on the
    condition variable 0x5b318b8: refused. The guard mutex 0x5b318c0 is taken and given back (no net write)."""
    if m.u8(guard):
        return 0
    b = m.u8(guard + 1)
    if b & 2:
        raise UnliftedCall("guard acquire while another construction is in progress")
    if b == 1:
        return 0
    m.put(guard + 1, 1, 2)
    return 1


@lifted(0x2D1FD38)
def static_46d3f08(m, *_):
    """The raid battler class's static [0x46d3f08] (guard [0x46d3f00]), built from 0x1a07aa4 on first use."""
    guard = m.u64(m.main + 0x46D3F00)
    if m.u8(guard) & 1 == 0 and m.call(m.main + 0x343CF10, guard) & M32:
        slot = m.u64(m.main + 0x46D3F08)
        m.put(slot, 8, m.call(m.main + 0x1A07AA4))
        m.call_void(m.main + 0x343CF20, guard)
    return m.u64(m.main + 0x46D3F08)


@lifted(0x28024A0)
def static_46e2578(m, *_):
    """The static chain [0x46e2578] -> [0x46d3ab0] -> [0x46d39b8] -> [0x46d39c8] (0), each level under its
    own guard; the outer slot."""
    _static_chain(m, ((0x46E2570, 0x46E2578), (0x46D3AA8, 0x46D3AB0), (0x46D39B0, 0x46D39B8),
                      (0x46D39C0, 0x46D39C8)))
    return m.u64(m.main + 0x46E2578)
