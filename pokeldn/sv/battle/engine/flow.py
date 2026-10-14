"""The server's round-level checks."""

from pokeldn.sv.battle.engine.slots import slot_matches
from pokeldn.sv.battle.machine import lifted


def party(m, parties, client):
    """(count, member list address) of a client's party in the party container."""
    base = parties + 0x38 * client
    return m.u8(base + 0x58), base + 0x28


def able_count(m, parties, client):
    n, members = party(m, parties, client)
    return sum(m.vcall(m.u64(members + 8 * i), 0x208) & 1 for i in range(n)) & 0xFF


@lifted(0x114A808)
def battle_continues(m, o, *_):
    """1 while every side still has a Pokemon able to fight (vf 0x208 of the party members)."""
    flags = m.u64(m.u64(m.u64(o + 8) + 0x38) + 0x498)
    pokecon = m.u64(o + 0x10)
    if flags >> 10 & 1 == 0:
        if flags >> 33 & 1:
            n, _ = party(m, m.u64(pokecon + 0x30), 0)
            if n == 0 or able_count(m, m.u64(pokecon + 0x30), 0) == 0:
                return 1
        if m.call(m.main + 0x10D3D7C, pokecon) & 1:
            return 1
        p = m.call(m.main + 0x10D3F10, m.u64(pokecon + 0x290))
        return 0 if p == 0 else (m.vcall(p, 0x208) ^ 1) & 1
    setup = m.u64(m.u64(pokecon + 0x290) + 8)
    mode, rule = m.u32(setup + 0x36C), m.u8(setup + 0x370)
    ours = 2 if mode > 2 else 1
    sides = (2 if mode > 2 else 0,
             2 if mode > 2 else 1,
             0 if mode in (1, 2) else 2,
             0 if mode == 2 else (1 if mode == 1 else 2),
             0 if mode == 2 else 2)
    parties = m.u64(pokecon + 0x30)
    for client in range(5):
        if slot_matches(m, mode, rule, client) & 1 and sides[client] == ours:
            n, _ = party(m, parties, client)
            if n and able_count(m, parties, client):
                return 0
    return 1


@lifted(0x1147774)
def first_standing(m, it, *_):
    """Point the iterator at the first party member of the first client (0..4) that is not out of
    the battle (vf 0x200): client at +0x18, index at +0x19; +0x1a stays 1 when there is none."""
    from pokeldn.sv.battle.engine.slots import positions_of_slot
    m.put(it + 0x1A, 1, 1); m.put(it + 0x18, 2, 0)
    pokecon = m.u64(it + 0x10)
    setup = m.u64(m.u64(pokecon + 0x290) + 8)
    for client in range(5):
        mode, rule = m.u32(setup + 0x36C), m.u8(setup + 0x370)
        if slot_matches(m, mode, rule, client) & 1 == 0:
            continue
        parties = m.u64(pokecon + 0x30)
        n = positions_of_slot(m, mode, rule, client)
        count, members = party(m, parties, client)
        for i in range(n):
            if i >= 0x100:
                break
            if i < count:
                b = m.u64(members + 8 * i)
                if b and m.vcall(b, 0x200) & 1 == 0:
                    m.put(it + 0x18, 1, client); m.put(it + 0x19, 1, i); m.put(it + 0x1A, 1, 0)
                    return


def _party_list(m, it, client):
    return m.u64(m.u64(it + 0x10) + 0x30) + 0x28 + 0x38 * client if client < 5 else 0


@lifted(0x1360DBC)
def next_standing(m, it, out, *_):
    """Hand out the iterator's current party member, then move it to the next one still in the battle."""
    from pokeldn.sv.battle.engine.slots import positions_of_slot
    if m.u8(it + 0x1A):
        return 0
    plist, idx = _party_list(m, it, m.u8(it + 0x18)), m.u8(it + 0x19)
    m.put(out, 8, m.u64(plist + 8 * idx) if idx < m.u8(plist + 0x30) else 0)
    m.put(it + 0x19, 1, idx + 1)
    client = m.u8(it + 0x18)
    while client < 5:
        setup = m.u64(m.u64(m.u64(it + 0x10) + 0x290) + 8)
        n = positions_of_slot(m, m.u32(setup + 0x36C), m.u8(setup + 0x370), client)
        i = m.u8(it + 0x19)
        while i < n:
            plist = _party_list(m, it, m.u8(it + 0x18))
            if i < m.u8(plist + 0x30):
                b = m.u64(plist + 8 * i)
                if b:
                    if m.vcall(b, 0x200) & 1 == 0:
                        return 1
                    i = m.u8(it + 0x19)
            i = (i + 1) & 0xFF
            m.put(it + 0x19, 1, i)
        client = (m.u8(it + 0x18) + 1) & 0xFF
        m.put(it + 0x18, 1, client); m.put(it + 0x19, 1, 0)
    m.put(it + 0x1A, 1, 1)
    return 1


@lifted(0x11464B0)
def id_at_position(m, o, pos, *_):
    """The id (vf 0x98) of the battler at battle position `pos`, 0 if none."""
    from pokeldn.sv.battle.engine.slots import client_of_position
    if pos & 0xFF == 10:
        return 0
    parties = m.u64(m.u64(o + 0x10) + 0x30)
    with m.frame(8) as out:
        client_of_position(m, m.u64(m.u64(parties + 0x18) + 0x290), pos, out, out + 4)
        client, idx = m.u8(out), m.u8(out + 4)
    if client != 5 and idx < m.u8(parties + 0x38 * client + 0x58):
        b = m.u64(parties + 0x38 * client + 0x28 + 8 * idx)
        if b:
            return m.vcall(b, 0x98)
    return 0


@lifted(0x13FCED4)
def set_action_state(m, o, ident, state, p4, p5, *_):
    """Give battler `ident` its action state (vf 0x2e0); a battler out of the battle gets vf 0x480 instead
    of the rest; one under condition 6 whose ... gets condition 7 cleared (vf 0x528)."""
    from pokeldn.sv.battle.engine.containers import battler
    from pokeldn.sv.battle.engine.getters import same_side_class
    b = battler(m, m.u64(m.u64(o + 0x10) + 0x30), ident)
    m.vcall_void(b, 0x2E0, state)
    if m.vcall(b, 0x200) & 1:
        m.vcall_void(b, 0x480, p4, p5)
        return
    if m.vcall(b, 0x560, 6) & 0xFFFFFFFF == 0:
        return
    if m.call(m.main + 0xFA9B4C, m.u64(o + 8), 0x1000) & 1 == 0:
        return
    if same_side_class(m, m.u64(o + 8), m.u64(o + 0x10), b) & 1:
        return
    if m.vcall(b, 0x510, 0x19) & 1:
        m.vcall_void(b, 0x528, 7)


def add_member(m, lst, b):
    """Append a battler to a member list (pointers at +0, count +0xa6, high mark +0xa7, at most 11),
    once; its per-entry fields at +0x84, +0x58 and +0x6e start at zero."""
    n = m.u8(lst + 0xA6)
    if n > 10 or any(m.u64(lst + 8 * i) == b for i in range(n)):
        return
    m.put(lst + 8 * n, 8, b)
    m.put(lst + 0x84 + n, 1, 0)
    m.put(lst + 0x58 + 2 * n, 2, 0)
    m.put(lst + 0x6E + 2 * n, 2, 0)
    m.put(lst + 0xA6, 1, n + 1)
    if m.u8(lst + 0xA7) < (n + 1) & 0xFF:
        m.put(lst + 0xA7, 1, n + 1)


@lifted(0x1144704)
def standing_members(m, o, lst, *_):
    """Fill a member list with every party member still in the battle, client by client."""
    m.write(lst, bytes(0x8F))
    m.put(lst + 0xA0, 8, 0); m.put(lst + 0x90, 8, 0); m.put(lst + 0x98, 8, 0); m.put(lst + 0xA8, 2, 0)
    with m.frame(0x20) as it:
        m.put(it, 8, m.u64(m.main + 0x46E2580) + 0x10)
        m.put(it + 8, 8, m.u64(o + 8)); m.put(it + 0x10, 8, m.u64(o + 0x10))
        m.put(it + 0x18, 2, 0); m.put(it + 0x1A, 1, 1)
        first_standing(m, it)
        with m.frame(8) as out:
            while next_standing(m, it, out):
                b = m.u64(out)
                if b:
                    add_member(m, lst, b)
