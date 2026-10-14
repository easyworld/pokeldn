"""A battler's stored Pokemon: the 0x148-byte core record (encryption constant at +0, flags at +4,
checksum at +6, four 0x50-byte blocks from +8 shuffled by (EC >> 13) & 31, the whole tail XORed by
an LCG seeded with the EC) and the 16-byte party record, behind an accessor object:

    +0x08  party record      +0x10  core record     +0x18  u8 encrypted     +0x19  u8 keep plain
    +0x20  lock owner        +0x28  light event
"""

from pokeldn.sv.battle.engine.libc import FAKE_THREAD, signal_light_event
from pokeldn.sv.battle.machine import UnliftedCall, lifted

# Where logical block k sits for each shuffle value (0x3c62e18).
BLOCK_POSITION = (
    (0, 1, 2, 3), (0, 1, 3, 2), (0, 2, 1, 3), (0, 3, 1, 2), (0, 2, 3, 1), (0, 3, 2, 1),
    (1, 0, 2, 3), (1, 0, 3, 2), (2, 0, 1, 3), (3, 0, 1, 2), (2, 0, 3, 1), (3, 0, 2, 1),
    (1, 2, 0, 3), (1, 3, 0, 2), (2, 1, 0, 3), (3, 1, 0, 2), (2, 3, 0, 1), (3, 2, 0, 1),
    (1, 2, 3, 0), (1, 3, 2, 0), (2, 1, 3, 0), (3, 1, 2, 0), (2, 3, 1, 0), (3, 2, 1, 0),
    (0, 1, 2, 3), (0, 1, 3, 2), (0, 2, 1, 3), (0, 3, 1, 2), (0, 2, 3, 1), (0, 3, 2, 1),
    (1, 0, 2, 3), (1, 0, 3, 2))
# Static records in main's .bss standing in for a record flagged bad: one read from, one written to.
BAD_READ_PARTY, BAD_READ_CORE = 0x4742280, 0x4742288
BAD_WRITE_PARTY, BAD_WRITE_CORE = 0x47423D0, 0x47423D8
CORE, BLOCKS = 0x148, 8


def _lcg(seed):
    return (seed * 0x41C64E6D + 0x6073) & 0xFFFFFFFF


def _xor_words(m, address, count, seed):
    data = bytearray(m.read(address, 2 * count))
    for i in range(count):
        seed = _lcg(seed)
        v = (data[2 * i] | data[2 * i + 1] << 8) ^ (seed >> 16)
        data[2 * i], data[2 * i + 1] = v & 0xFF, v >> 8
    m.write(address, bytes(data))


def _checksum(m, core):
    data = m.read(core + BLOCKS, CORE - BLOCKS)
    return sum(data[i] | data[i + 1] << 8 for i in range(0, len(data), 2)) & 0xFFFF


def _crypt(m, acc):
    core, party = m.u64(acc + 0x10), m.u64(acc + 8)
    ec = m.u32(core)
    _xor_words(m, core + BLOCKS, (CORE - BLOCKS) // 2, ec)
    if party:
        _xor_words(m, party, 8, ec)


def block(m, core, logical, write=False):
    """Address of logical block `logical` of a plain core record (a static stand-in when it is bad)."""
    if m.u8(core + 4) >> 2 & 1:
        return m.main + (BAD_WRITE_CORE if write else BAD_READ_CORE) + BLOCKS + 0x50 * logical
    return core + BLOCKS + 0x50 * BLOCK_POSITION[(m.u32(core) >> 13) & 0x1F][logical]


def party_record(m, acc, write=False):
    """Address of the 16-byte party record (a static stand-in when the core is bad)."""
    if m.u8(m.u64(acc + 0x10) + 4) >> 2 & 1:
        return m.main + (BAD_WRITE_PARTY if write else BAD_READ_PARTY)
    return m.u64(acc + 8)


def access(m, acc, read):
    """Lock the record, decrypt it, call read(core), encrypt it again as the game does, unlock."""
    if m.u64(acc + 0x20) != 0:
        raise UnliftedCall("pokemon record already locked")
    m.put(acc + 0x20, 8, FAKE_THREAD)
    if m.u8(acc + 0x18):
        _crypt(m, acc)
        m.put(acc + 0x18, 1, 0)
        core = m.u64(acc + 0x10)
        if m.u16(core + 6) != _checksum(m, core):
            m.put(core + 4, 2, m.u16(core + 4) | 4)
    value = read(m.u64(acc + 0x10))
    if m.u8(acc + 0x18) == 0 and m.u8(acc + 0x19) == 0:
        core = m.u64(acc + 0x10)
        if core:
            m.put(core + 6, 2, _checksum(m, core))
            ec = m.u32(core)
            _xor_words(m, core + BLOCKS, (CORE - BLOCKS) // 2, ec)
        party = m.u64(acc + 8)
        if party and m.u64(acc + 0x10):
            _xor_words(m, party, 8, m.u32(m.u64(acc + 0x10)))
        m.put(acc + 0x18, 1, 1)
    m.put(acc + 0x20, 8, 0)
    signal_light_event(m, acc + 0x28)
    return value


@lifted(0xBF4CFC)
def is_egg(m, acc, *_):
    """Bit 30 of the IV word (block B +0x34)."""
    return access(m, acc, lambda core: m.u32(block(m, core, 1) + 0x34) >> 30 & 1)


@lifted(0x287A948)
def egg_test(m, o, mode, *_):
    """mode 0: an egg and not a bad record; 1: a bad record; 2: either."""
    acc = m.u64(m.u64(o + 0x48) + 0x70)
    egg = is_egg(m, acc)
    bad = m.u16(m.u64(acc + 0x10) + 4) >> 2 & 1
    mode &= 0xFF
    if mode == 0:
        return egg & (bad ^ 1)
    if mode == 1:
        return bad
    if mode == 2:
        return egg | bad
    return 0


def access_if(m, acc, read, condition):
    """Like access, but when `condition` fails the record is neither decrypted nor read: 0."""
    if m.u64(acc + 0x20) != 0:
        raise UnliftedCall("pokemon record already locked")
    if not condition:
        m.put(acc + 0x20, 8, FAKE_THREAD)
        m.put(acc + 0x20, 8, 0)
        signal_light_event(m, acc + 0x28)
        return 0
    return access(m, acc, read)


def access_if_party(m, acc, read):
    return access_if(m, acc, read, m.u64(acc + 8) != 0)


# Accessors of the record (PK9 layout: block A = 0x08.., B = 0x58.., C = 0xa8.., D = 0xf8..; party = the
# 16-byte tail). (address, where, offset, size, per-index step, stand-in, party required)
_GETTERS = (
    (0xC75438, "party", 2, 2, 0, BAD_READ_PARTY, True),
    (0x12E8170, "party", 6, 2, 0, BAD_READ_PARTY, True),
    (0x12E84A4, "party", 0xC, 2, 0, BAD_READ_PARTY, True),
    (0x12E87D8, "party", 4, 2, 0, BAD_READ_PARTY, True),
    (0x12E8B0C, "party", 0xA, 2, 0, BAD_READ_PARTY, True),
    (0x12E8E40, "party", 8, 2, 0, BAD_READ_PARTY, True),
    (0xD9987C, "party", 0, 1, 0, BAD_READ_PARTY, True),
    (0xCDF348, 1, 0x32, 2, 0, 0x47422E0, True),            # current HP (0x8a)
    (0xB80208, 1, 0x38, 4, 0, 0x47422E0, True),
    (0xDEDBC8, 1, 0x1A, 2, 2, 0x47422E0, False),           # move i (0x72)
    (0xDEE950, 1, 0x22, 1, 1, 0x47422E0, False),           # PP of move i (0x7a)
    (0xBF61D4, 1, 0x26, 1, 1, 0x47422E0, False),           # PP Ups of move i (0x7e)
    (0xD974E0, 0, 2, 2, 0, 0x4742290, False),              # held item (0x0a)
    (0xE14B64, 0, 8, 4, 0, 0x4742290, False),              # experience (0x10)
    (0x103B8A0, 0, 0xC, 2, 0, 0x4742290, False),           # ability (0x14)
    (0xD97B78, 0, 0x18, 1, 0, 0x4742290, False),
    (0x1693148, 3, 0x27, 1, 0, 0x4742380, False),
)
_SETTERS = (
    (0xE14810, 1, 0x32, 2, 0, 0x4742430, True),
    (0xCEB388, 1, 0x38, 4, 0, 0x4742430, True),
    (0xDEE5F0, 1, 0x1A, 2, 2, 0x4742430, False),
    (0xDEE290, 1, 0x26, 1, 1, 0x4742430, False),
    (0xDEDF30, 1, 0x22, 1, 1, 0x4742430, False),
    (0xDF0AF0, 0, 2, 2, 0, 0x47423E0, False),
    (0x18B7A68, 3, 0x27, 1, 0, 0x4742380, False),
)


def _target(m, acc, core, where, standin):
    if where == "party":
        return m.main + standin if m.u8(core + 4) >> 2 & 1 else m.u64(acc + 8)
    if m.u8(core + 4) >> 2 & 1:
        return m.main + standin
    return core + BLOCKS + 0x50 * BLOCK_POSITION[(m.u32(core) >> 13) & 0x1F][where]


def _run(m, acc, fn, need_party, i, step):
    if need_party:
        return access_if_party(m, acc, fn)
    if step:                                  # an indexed field: one of the four moves
        return access_if(m, acc, fn, i < 4)
    return access(m, acc, fn)


def _getter(where, off, size, step, standin, need_party):
    def fn(m, acc, *args):
        i = (args[0] & 0xFF) if step else 0
        read = lambda core: m.u(_target(m, acc, core, where, standin) + off + step * i, size)
        return _run(m, acc, read, need_party, i, step)
    return fn


def _setter(where, off, size, step, standin, need_party):
    def fn(m, acc, *args):
        i, v = ((args[0] & 0xFF), args[1]) if step else (0, args[0])
        def write(core):
            m.put(_target(m, acc, core, where, standin) + off + step * i, size, v)
            return 0
        _run(m, acc, write, need_party, i, step)
        return acc + 0x28
    return fn


for _a, *_spec in _GETTERS:
    lifted(_a)(_getter(*_spec))
for _a, *_spec in _SETTERS:
    lifted(_a)(_setter(*_spec))


# Stat i (0 HP, 1 Atk, 2 Def, 3 SpA, 4 SpD, 5 Spe): the party record's accessor, or the computation from
# the core record when there is none (0x12e8070's jump table 0x3c62caa).
_STAT = ((0xC75438, 0xE13EF0), (0x12E87D8, 0xE1415C), (0x12E8170, 0xE142B0),
         (0x12E8B0C, 0xE14560), (0x12E84A4, 0xE146B8), (0x12E8E40, 0xE14408))


@lifted(0x12E8070)
def stat(m, pp, i, *_):
    i &= 0xFF
    if i > 5:
        return 0
    acc = m.u64(pp + 0x70)
    party_fn, computed = _STAT[i]
    if m.u64(acc + 8):
        return m.call(m.main + party_fn, acc) & 0xFFFF
    return m.call(m.main + computed, pp) & 0xFFFF


@lifted(0x12E8068)
def stat_of(m, core, i, *_):
    return stat(m, m.u64(core + 0x48), i)


@lifted(0xBEC030)
def gender(m, acc, *_):
    """Bits 1..2 of block A +0x1a (0x22)."""
    return access(m, acc, lambda core: m.u8(_target(m, acc, core, 0, 0x4742290) + 0x1A) >> 1 & 3)
