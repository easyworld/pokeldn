"""Checks the move and effect handlers (main+0x157xxxx, 0x113fxxx) run on an attacker and a target."""

from pokeldn.sv.battle.engine.slots import within_side
from pokeldn.sv.battle.machine import lifted


def _at_99(m, o, b):
    """Within its side's room and answering 99 to vf 0xf8."""
    return within_side(m, m.u64(o + 0xF0), o, m.vcall(b, 0x98)) & 1 and m.vcall(b, 0xF8) & 0xFFFF == 99


@lifted(0x157C614)
def protected_from(m, o, attacker, target, *_):
    """1 unless the target has flag 0x1a (vf 0x4d0); then by conditions 0x1d, 0x1e (bound to the
    target) on the attacker and 0x2d on the target."""
    if m.vcall(target, 0x4D0, 0x1A) & 1:
        return 0
    if _at_99(m, o, attacker) or _at_99(m, o, target) or m.vcall(attacker, 0x220, 0x1D) & 1:
        return 1
    if m.vcall(attacker, 0x220, 0x1E) & 1:
        bound = m.vcall(attacker, 0x238, 0x1E) & 0xFF
        if m.vcall(target, 0x98) & 0xFFFFFFFF == bound:
            return 1
    return m.vcall(target, 0x220, 0x2D)


@lifted(0x113FA64)
def round_check(m, o, out, *_):
    """*out = whether the six-record pass (0x113fb60 then 0x113fcc8) found anything to do; only in
    battle modes 0 and 1 with +0x706 clear."""
    m.put(out, 1, 0)
    setup = m.u64(m.u64(o + 8) + 0x38)
    if m.u32(setup + 0x30) > 1 or m.u8(setup + 0x706):
        return
    with m.frame(0x60) as recs:
        for i in range(6):
            m.write(recs + 0x10 * i, bytes(0xD) + b"\x01")
        m.call_void(m.main + 0x113FB60, o, recs)
        if not any(m.u32(recs + 0x10 * i) for i in range(6)):
            return
        if m.call(m.main + 0x113FC80, o) & 1:
            m.call_void(m.main + 0x114221C, o)
        m.put(out, 1, m.call(m.main + 0x113FCC8, o, recs) & 1)
