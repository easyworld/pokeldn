"""Helpers the lifted functions share: tail calls into the engine's other functions, the refusal of a callee
the engine has no version of, and 32-bit integer views."""

from pokeldn.sv.battle.machine import FUNCTIONS, UnliftedCall


def _udiv32(a, b):
    """AArch64 udiv: division by zero gives 0."""
    return (a & 0xFFFFFFFF) // (b & 0xFFFFFFFF) if b & 0xFFFFFFFF else 0


def m_s32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v & 0x80000000 else v


def _tail(m, address, *args):
    """A tail call: the callee's result, or None when the callee is void."""
    fn = FUNCTIONS.get(address - m.main)
    if fn is None:
        raise UnliftedCall(f"main+0x{address - m.main:x}")
    return fn(m, *args)


def _need(m, address):
    """Refuse the round before any write when a callee reached later is not lifted."""
    if address - m.main not in FUNCTIONS:
        raise UnliftedCall(f"main+0x{address - m.main:x}")


def _vtail(m, obj, slot, *args):
    return _tail(m, m.u64(m.u64(obj) + slot), obj, *args)


def _s32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v & 0x80000000 else v


M32 = 0xFFFFFFFF
M64 = 0xFFFFFFFFFFFFFFFF


def _f32(x):
    import struct
    return struct.unpack("<f", struct.pack("<f", x))[0]


def _pow2(n):
    return n & (n - 1) == 0
