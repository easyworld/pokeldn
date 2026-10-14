"""The round's random numbers: one xoroshiro128+ (state +8 and +0x10, seed +0x18, draws +0x20) seeded
with the RaidPoint's randSeed (docs/sv_raid.md, The battle's random numbers)."""

from pokeldn.sv.battle.machine import lifted

M64 = 0xFFFFFFFFFFFFFFFF


def _rotl(x, k):
    return ((x << k) | (x >> (64 - k))) & M64


def step(s0, s1):
    """(output, next s0, next s1)."""
    out = (s0 + s1) & M64
    s1 ^= s0
    return out, _rotl(s0, 24) ^ s1 ^ ((s1 << 16) & M64), _rotl(s1, 37)


@lifted(0x11440F0)
def below(m, rand, n, *_):
    """A u64 below n (masked to the bits of n - 1, redrawn while too large); 0 without a draw for n < 2."""
    if n < 2:
        return 0
    m.put(rand + 0x20, 8, m.u64(rand + 0x20) + 1)
    mask = (1 << (n - 1).bit_length()) - 1
    s0, s1 = m.u64(rand + 8), m.u64(rand + 0x10)
    while True:
        out, s0, s1 = step(s0, s1)
        if out & mask < n:
            break
    m.put(rand + 8, 8, s0); m.put(rand + 0x10, 8, s1)
    return out & mask


@lifted(0x114DA8C)
def chance(m, rand, percent, *_):
    """(s0 + s1) & 0x7f redrawn while 100 or more; 1 when below `percent`."""
    m.put(rand + 0x20, 8, m.u64(rand + 0x20) + 1)
    s0, s1 = m.u64(rand + 8), m.u64(rand + 0x10)
    while True:
        out, s0, s1 = step(s0, s1)
        if out & 0x7F < 100:
            break
    m.put(rand + 8, 8, s0); m.put(rand + 0x10, 8, s1)
    return int(out & 0x7F < percent & 0xFFFFFFFF)
