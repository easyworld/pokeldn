"""The battle's end on the server: the result judged from the parties (0xe7d58c), kept in N (0xe7d570) and
in the server's 0x29 body (0xe7d4c8), and the next steps' choices (docs/sv_raid.md, The battle's end).
A job's context [job+0x40] holds N at +8, the module at +0x10 and the server at +0x18."""

from pokeldn.sv.battle.engine.calls import M32, _tail
from pokeldn.sv.battle.engine.requests import _add_ref, _release
from pokeldn.sv.battle.machine import UnliftedCall, lifted

SIDES = ((0, 1, 2, 2, 2), (0, 1, 0, 1, 2), (0, 1, 0, 0, 0))   # each slot's side by battle mode, 0x3c6a450
UNDECIDED = 2


def _s32(v):
    v &= M32
    return v - (1 << 32) if v >> 31 else v


def _map(m, module):
    return m.call(m.main + 0xE7E27C, module)


# --- job context getters --------------------------------------------------------------------------------

lifted(0x1397D84)(lambda m, job, *_: m.u64(m.u64(job + 0x40) + 8))
lifted(0x13F5F08)(lambda m, job, *_: m.u64(m.u64(job + 0x40) + 0x10))
lifted(0x16E4FE4)(lambda m, job, *_: m.u64(m.u64(job + 0x40) + 0x18))
lifted(0x1398338)(lambda m, job, *_: m.u64(job + 0x40))
lifted(0x1397D74)(lambda m, job, *_: m.put(job + 0x68, 4, (m.u32(job + 0x68) + 1) & M32))
lifted(0xE7D508)(lambda m, n, *_: m.u8(n + 0x94))
lifted(0x113F5B0)(lambda m, module, *_: m.u64(module + 0x110))
lifted(0x2823B0C)(lambda m, module, *_: m.u64(module + 0x1B0))
lifted(0xE7D738)(lambda m, _mode, kind, *_: int(kind & 0xFFFFFFFE == 2))
lifted(0xE7D7E4)(lambda m, _mode, side, *_: int(side & 0xFF < 2))


@lifted(0xE7D7D8)
def side_exists(m, setup_map, side, *_):
    """Whether `side` (u8) is a side of the battle: 0 and 1 in every mode (the mode [[map+8]+0x36c] is read
    and not used, 0xe7d7e4)."""
    return _tail(m, m.main + 0xE7D7E4, m.u32(m.u64(setup_map + 8) + 0x36C), side)


@lifted(0xE7E3E0)
def side_of(m, setup_map, slot, *_):
    """A slot's side in the battle mode [[map+8]+0x36c] (table 0x3c6a450, five slots a mode); 2 otherwise."""
    mode = m.u32(m.u64(setup_map + 8) + 0x36C)
    slot &= 0xFF
    if mode > 2 or slot > 4:
        return 2
    return SIDES[mode][slot]


@lifted(0x2823B14)
def slot_word(m, o, slot, *_):
    """u16 [o + 0xa + 2 slot] for a slot 0..4, else 0."""
    return m.u16(o + 0xA + 2 * (slot & 0xFF)) if slot & 0xFF <= 4 else 0


@lifted(0x2823B34)
def first_entry_value(m, o, *_):
    """For the first of four 0x98-byte entries whose count byte +0x9e is set, its u32 +8 + 4 (count - 1);
    0 when none is set."""
    for i in range(4):
        n = m.u8(o + 0x9E + 0x98 * i)
        if n:
            return m.u32(o + 0x98 * i + 8 + 4 * ((n - 1) & M32))
    return 0


# --- the result ----------------------------------------------------------------------------------------

@lifted(0xE7DE94)
def count_sides(m, able, members, empty, n, module, *_):
    """Per side (u8 each, two sides): the able members (0xe7e454) and members of every seated slot's party;
    with no setup +0x710 and a u16 N+0x8c, the slots whose word in [module+0x1b0] (0x2823b14) is 0."""
    for p in (able, members, empty):
        m.put(p, 1, 0); m.put(p + 1, 1, 0)
    for slot in range(5):
        if not m.call(m.main + 0xE7E28C, _map(m, module), slot) & 1:
            continue
        side = m.call(m.main + 0xE7E3E0, _map(m, module), slot) & 0xFF
        party = m.call(m.main + 0xE7E3C8, m.call(m.main + 0xE7E284, module), slot)
        if m.call(m.main + 0xE7E274, party) & 0xFF:
            m.put(able + side, 1, (m.u8(able + side) + m.call(m.main + 0xE7E454, party)) & 0xFF)
            m.put(members + side, 1, (m.u8(members + side) + m.call(m.main + 0xE7E274, party)) & 0xFF)
        if m.u8(m.u64(n + 0x38) + 0x710) or not m.u16(n + 0x8C):
            continue
        if not m.call(m.main + 0x2823B14, m.call(m.main + 0x2823B0C, module), slot) & 0xFFFF:
            m.put(empty + side, 1, (m.u8(empty + side) + 1) & 0xFF)


@lifted(0xE7D748)
def by_able(m, module, able, *_):
    """The side still standing when the other has no able member: 0 or 1; 2 when both or neither stand."""
    gone0 = 1
    r = 2
    if m.call(m.main + 0xE7D7D8, _map(m, module), 0) & 1:
        gone0 = int(m.u8(able) == 0)
        r = gone0 << 1
    if not m.call(m.main + 0xE7D7D8, _map(m, module), 1) & 1:
        return r
    gone1 = m.u8(able + 1) == 0
    if not gone1:
        r = 1
    return r if (gone0 | gone1) == 1 else 2


@lifted(0xE7E520)
def by_empty(m, counts, module, *_):
    """The side with fewer empty slots (counts u8 [0], [1]): 0 or 1; 2 when equal."""
    c0, c1 = m.u8(counts), m.u8(counts + 1)
    if m.call(m.main + 0xE7D7D8, _map(m, module), 0) & 1:
        a, has0, none0, r = c0, 1, 0, 0
    else:
        a, has0, none0, r = 0, 0, 1, 2
    if not m.call(m.main + 0xE7D7D8, _map(m, module), 1) & 1:
        return r
    if none0 | (a > c1):
        return 1
    return 2 if has0 + (a == c1) > 1 else r


@lifted(0xE7ECD8)
def by_rule(m, able, module, *_):
    """When neither side has an able member: the rule value of [module+0x110] (0x2823b34) through
    0x144e790; 2 otherwise or with no value."""
    if m.call(m.main + 0xE7D7D8, _map(m, module), 0) & 1 and m.u8(able):
        return 2
    if m.call(m.main + 0xE7D7D8, _map(m, module), 1) & 1 and m.u8(able + 1):
        return 2
    v = m.call(m.main + 0x2823B34, m.call(m.main + 0x113F5B0, module)) & M32
    if not v:
        return 2
    return _tail(m, m.main + 0x144E790, _map(m, module), v)


@lifted(0xE7F160)
def by_fainted(m, module, able, members, *_):
    """The side that lost fewer members (members - able, signed): 0 or 1; 2 when equal."""
    lost0 = (m.u8(members) - m.u8(able)) & M32
    m1, a1 = m.u8(members + 1), m.u8(able + 1)
    has0 = m.call(m.main + 0xE7D7D8, _map(m, module), 0) & 1
    base, lost0 = (0, lost0) if has0 else (2, 0)
    has1 = m.call(m.main + 0xE7D7D8, _map(m, module), 1) & 1
    r = 1 if has1 else base
    if not has0 or not has1:
        return r
    lost1 = _s32(m1 - a1)
    if lost1 < _s32(lost0):
        return 1
    return 2 if lost1 == _s32(lost0) else base


@lifted(0x282361C)
def hp_share(m, hp, share, module, side, *_):
    """The HP (vf 0x108) and maximum HP (vf 0x110) of every member on `side` summed; *hp the sum, *share
    100 hp / max (u32, 0 for a zero maximum)."""
    m.put(hp, 4, 0)
    m.put(share, 4, 0)
    if not m.call(m.main + 0xE7D7D8, _map(m, module), side) & 1:
        return
    total = 0
    for slot in range(5):
        if not m.call(m.main + 0xE7E28C, _map(m, module), slot) & 1:
            continue
        if m.call(m.main + 0xE7E3E0, _map(m, module), slot) & 0xFF != side & 0xFF:
            continue
        party = m.call(m.main + 0xE7E3C8, m.call(m.main + 0xE7E284, module), slot)
        count = m.call(m.main + 0xE7E274, party) & 0xFF
        for i in range(count):
            p = m.call(m.main + 0x114E4C0, party, i)
            total = (total + (m.vcall(p, 0x110) & 0xFFFF)) & M32
            m.put(hp, 4, (m.u32(hp) + (m.vcall(p, 0x108) & 0xFFFF)) & M32)
    v = (m.u32(hp) * 100) & M32
    m.put(share, 4, v // total if total else 0)


def _by_pair(m, module, p):
    """0x28239ac / 0x2823a5c: the side with the larger u32 of the pair p (signed): 0 or 1; 2 when equal."""
    if m.call(m.main + 0xE7D7D8, _map(m, module), 0) & 1:
        v0, none0, base, has0 = m.u32(p), 0, 0, 1
    else:
        v0, none0, base, has0 = 0, 1, 2, 0
    has1 = m.call(m.main + 0xE7D7D8, _map(m, module), 1) & 1
    r = 1 if has1 else base
    if none0 or not has1:
        return r
    v1 = m.u32(p + 4)
    if _s32(v0) < _s32(v1):
        return 1
    return 2 if has0 + (v1 == v0) > 1 else base


lifted(0x28239AC)(lambda m, module, p, *_: _by_pair(m, module, p))
lifted(0x2823A5C)(lambda m, module, p, *_: _by_pair(m, module, p))


@lifted(0xE7D58C)
def judge(m, n, module, out, *_):
    """The battle's result for N's own slot: 1 when its side wins, 0 when it loses, 2 undecided. Sides
    are compared by able members (0xe7d748); with N+0x8c by empty slots (0xe7e520); in the modes of
    setup +0x30 2 and 3 by the rule value (0xe7ecd8), members lost (0xe7f160), HP share (0x28239ac) and HP
    (0x2823a5c). *out (u8): 0 decided by a standing side with setup +0x49c bit 1, else 1 or 2."""
    m.put(out, 1, 0)
    with m.frame(0x20) as f:
        share, hp, empty, members, able = f + 4, f + 0xC, f + 0x14, f + 0x18, f + 0x1C
        m.call_void(m.main + 0xE7DE94, able, members, empty, n, module)
        setup = m.u64(n + 0x38)
        if m.u8(setup + 0x49C) & 2:
            if m.u8(able + 1):
                r = 1
            else:
                m.put(out, 1, 1)
                r = 0
        else:
            r = _judge_steps(m, n, module, out, setup, share, hp, empty, members, able)
    r &= 0xFF
    if r == UNDECIDED:
        return UNDECIDED
    own = m.call(m.main + 0x149FE8C, n)
    return int(r == m.call(m.main + 0xE7E3E0, _map(m, module), own) & 0xFF)


def _judge_steps(m, n, module, out, setup, share, hp, empty, members, able):
    r = m.call(m.main + 0xE7D748, module, able)
    if r & 0xFF != 2:
        m.put(out, 1, 1)
        return r
    if not m.u8(setup + 0x710) and m.u16(n + 0x8C):
        r = m.call(m.main + 0xE7E520, empty, module)
        if r & 0xFF != 2:
            m.put(out, 1, 2)
            return r
        setup = m.u64(n + 0x38)
    if not m.call(m.main + 0xE7D738, m.u32(module + 0x36C), m.u32(setup + 0x30)) & 1:
        return 2
    r = m.call(m.main + 0xE7ECD8, able, module)
    if r & 0xFF != 2:
        m.put(out, 1, 1)
        return r
    m.put(out, 1, 2)
    r = m.call(m.main + 0xE7F160, module, able, members)
    if r & 0xFF != 2:
        return r
    m.call_void(m.main + 0x282361C, hp, share, module, 0)
    m.call_void(m.main + 0x282361C, hp + 4, share + 4, module, 1)
    r = m.call(m.main + 0x28239AC, module, share)
    if r & 0xFF != 2:
        return r
    return m.call(m.main + 0x2823A5C, module, hp)


@lifted(0xE7D570)
def keep_result(m, n, result, how, force, *_):
    """The result into N+0x90 (u32) and N+0x94 (u8) while N+0x90 is 7 (none yet) or when forced."""
    if m.u32(n + 0x90) == 7 or force & 1:
        m.put(n + 0x90, 4, result & M32)
        m.put(n + 0x94, 1, how & 0xFF)


@lifted(0x16688C8)
def by_listed_slots(m, lst, module, own, kind, *_):
    """The outcome from the slots a list names (count u32 +8, slots from +0xc) against own's (0x1142ecc):
    4 when none answers, 3 when all do, else 2 (3 for setup kinds 0 and 1)."""
    count = m.u32(lst + 8)
    if not count:
        return 4
    some = every_not = 0
    for i in range(count):
        r = m.call(m.main + 0x1142ECC, _map(m, module), m.u8(lst + 0xC + i), own) & M32
        some |= r
        every_not |= r ^ 1
    if not some & 1:
        return 4
    if every_not & 1:
        return 3 if kind & M32 < 2 else 2
    return 3


@lifted(0x166882C)
def battle_outcome(m, n, *_):
    """The outcome code, also kept at [N+0x40]+0x30: 1 for setup kind 4; 5 with N+0x9e bit 0; from the
    listed slots of [[N+0x150]+0x230] (0x16688c8); else N+0x90, its 7 (none yet) read as 1 and written
    back, or 7 written with setup +0x710 and no +0x49b bit 1."""
    setup = m.u64(n + 0x38)
    kind = m.u32(setup + 0x30)
    if kind == 4:
        r = 1
    elif m.u8(n + 0x9E) & 1:
        r = 5
    else:
        module = m.u64(n + 0x150)
        lst = m.u64(module + 0x230)
        if m.u32(lst + 8):
            r = m.call(m.main + 0x16688C8, lst, module, m.u8(n + 0x95), kind)
        elif m.u8(setup + 0x710):
            if m.u8(setup + 0x49B) & 2:
                r = m.u32(n + 0x90)
            else:
                r = 7
                m.put(n + 0x90, 4, 7)
        else:
            r = m.u32(n + 0x90)
            if r == 7:
                r = 1
                m.put(n + 0x90, 4, 1)
    m.put(m.u64(n + 0x40) + 0x30, 4, r & M32)
    return r


@lifted(0xE7D4C8)
def end_body(m, server, *_):
    """The six bytes message 0x29 carries: server+0x208 u16 N's own slot, +0x20a u16 the outcome
    (0x166882c), +0x20c u8 how it was decided (N+0x94)."""
    n = m.u64(server + 0x30)
    m.put(server + 0x20A, 2, m.call(m.main + 0x166882C, n) & 0xFFFF)
    m.put(server + 0x20C, 1, m.call(m.main + 0xE7D508, m.u64(server + 0x30)) & 0xFF)
    m.put(server + 0x208, 2, m.u8(m.u64(server + 0x30) + 0x95))


@lifted(0x16E5120)
def judge_into_n(m, job, *_):
    """The result (0xe7d58c on the context's N and module) kept in N (0xe7d570, not forced)."""
    n = m.call(m.main + 0x1397D84, job)
    module = m.call(m.main + 0x13F5F08, job)
    with m.frame(0x10) as how:
        r = m.call(m.main + 0xE7D58C, n, module, how)
        m.call_void(m.main + 0xE7D570, m.call(m.main + 0x1397D84, job), r, m.u8(how), 0)


@lifted(0x16E59A4)
def intruder_source(m, job, *_):
    """[[N+0x48]+0x138], referenced and released around the read; 0 when there is none."""
    o = m.u64(m.call(m.main + 0xE7ECD0, m.call(m.main + 0x1397D84, job)) + 0x138)
    if o:
        _add_ref(m, o)
        with m.frame(0x10) as h:
            m.put(h, 8, o)
            _release(m, h)
    return o


lifted(0x2A0FB40)(lambda m, *_: 0)     # vf 0x90 of the source class (vtable 0x4492e58): it never accepts


@lifted(0x16E56A0)
def intrude(m, job, *_):
    """Whether a Pokemon joins the battle at its end: the source (0x16e59a4) asked through its vf 0x90 with
    {N, module}; 0 when it has none or declines. Its accepting branch (0x20183a8) is not lifted."""
    if not m.call(m.main + 0x16E59A4, job):
        return 0
    with m.frame(0x20) as f:
        m.put(f, 8, m.call(m.main + 0x1397D84, job))
        m.put(f + 8, 8, m.call(m.main + 0x13F5F08, job))
        m.put(f + 0x10, 8, 0)
        o = m.call(m.main + 0x16E59A4, job)
        if m.vcall(o, 0x90, f) & 1:
            raise UnliftedCall("0x16e56a0: an intruding Pokemon (ServerCommandIntrudePokeIn)")
        if m.u64(f + 0x10):
            _release(m, f + 0x10)
    return 0


@lifted(0x1882B14)
def exit_message(m, job, *_):
    """The message the battle's exit sends by setup kind (+0x30): kind 0 by the outcome (0x166882c),
    0x29 for 1, 0x2b for 0 or 2, 0x2d for 6, else 0; kind 1 0x31, 2 0x33, 3 0x2f; 0 above."""
    outcome = m.call(m.main + 0x166882C, m.call(m.main + 0x1397D84, job)) & M32
    kind = m.call(m.main + 0x144B6C8, m.call(m.main + 0x1397D84, job)) & M32
    if kind > 3:
        return 0
    if kind == 0:
        if outcome == 1:
            return 0x29
        if outcome & 0xFFFFFFFD == 0:
            return 0x2B
        return 0x2D if outcome == 6 else 0
    return (0, 0x31, 0x33, 0x2F)[kind]
