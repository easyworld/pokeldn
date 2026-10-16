"""A battler's stored Pokemon: the 0x148-byte core record (encryption constant at +0, flags at +4,
checksum at +6, four 0x50-byte blocks from +8 shuffled by (EC >> 13) & 31, the whole tail XORed by
an LCG seeded with the EC) and the 16-byte party record, behind an accessor object:

    +0x08  party record      +0x10  core record     +0x18  u8 encrypted     +0x19  u8 keep plain
    +0x20  lock owner        +0x28  light event
"""

from pokeldn.sv.battle.engine.calls import M32, M64, _f32, _need, _s32, _tail
from pokeldn.sv.battle.engine.containers import battler
from pokeldn.sv.battle.engine.data import static_table
from pokeldn.sv.battle.engine.libc import FAKE_THREAD, signal_light_event
from pokeldn.sv.battle.engine.statics import _has_static, _holds_pokeparam_type, _static_built
from pokeldn.sv.battle.machine import FUNCTIONS, UnliftedCall, lifted

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


@lifted(0x287A5E8)
def pokemon_species(m, o, *rest):
    """0xcdf348 of the Pokemon record [[o+0x48]+0x70] when its +8 is set, else 0xe13ef0 of [o+0x48] (u16)."""
    p = m.u64(m.u64(o + 0x48) + 0x70)
    if m.u64(p + 8):
        return _tail(m, m.main + 0xCDF348, p, *rest[:7])
    return m.call(m.main + 0xE13EF0, m.u64(o + 0x48), *rest[:7]) & 0xFFFF


@lifted(0xEF2F38)
def bind_record(m, acc, core, party, *_):
    """Point a record accessor at a plain core and party record, then seal them (checksum, encrypt)."""
    m.put(acc + 0x18, 2, 0)
    m.put(acc + 8, 8, party)
    m.put(acc + 0x10, 8, core)
    if core:
        m.put(core + 6, 2, _checksum(m, core))
        _xor_words(m, core + BLOCKS, (CORE - BLOCKS) // 2, m.u32(core))
    if party and core:
        _xor_words(m, party, 8, m.u32(core))
    m.put(acc + 0x18, 1, 1)
    return acc


@lifted(0xE14EA8)
def load_record(m, acc, core, party, *_):
    """Copy a sealed core record (0x148 bytes) and party record (16) into an accessor's buffers, check the
    checksum (bad: flag bit 2 at +4) and seal them again."""
    r = acc
    if core:
        r = m.u64(acc + 0x10)
        m.write(r, m.read(core, CORE))
    if party:
        m.write(m.u64(acc + 8), m.read(party, 16))
    c = m.u64(acc + 0x10)
    m.put(acc + 0x18, 2, 1)
    _xor_words(m, c + BLOCKS, (CORE - BLOCKS) // 2, m.u32(c))
    p = m.u64(acc + 8)
    if p:
        _xor_words(m, p, 8, m.u32(m.u64(acc + 0x10)))
    c = m.u64(acc + 0x10)
    m.put(acc + 0x18, 1, 0)
    if m.u16(c + 6) != _checksum(m, c):
        m.put(c + 4, 2, m.u16(c + 4) | 4)
    if m.u8(acc + 0x19) == 0:
        c = m.u64(acc + 0x10)
        if c:
            m.put(c + 6, 2, _checksum(m, c))
            _xor_words(m, c + BLOCKS, (CORE - BLOCKS) // 2, m.u32(c))
        p = m.u64(acc + 8)
        if p and m.u64(acc + 0x10):
            _xor_words(m, p, 8, m.u32(m.u64(acc + 0x10)))
        m.put(acc + 0x18, 1, 1)
    return r


def _record_accessors():
    """More accessors of the stored Pokemon record (pokemon._GETTERS / _SETTERS layout)."""
    for a, *spec in ((0xD90170, 0, 0x20, 1, 0, 0x4742290, False),
                     (0xD90B3C, 0, 0x23, 1, 0, 0x4742290, False),
                     (0xD9782C, 1, 0x3C, 1, 0, 0x47422E0, False)):
        lifted(a)(_getter(*spec))
    for a, *spec in ((0xE15484, "party", 4, 2, 0, 0x47423D0, True),
                     (0xE15E20, "party", 0xA, 2, 0, 0x47423D0, True)):
        lifted(a)(_setter(*spec))


_record_accessors()


def _record_accessors_2():
    lifted(0xC4EA44)(_getter(0, 0x19, 1, 0, 0x4742290, False))


_record_accessors_2()


@lifted(0x287A9CC)
def pokeparam_103b7d0(m, o, *_):
    """The tail call of 0x103b7d0 on [o+0x48]."""
    return _tail(m, m.main + 0x103B7D0, m.u64(o + 0x48))


@lifted(0xFA13D0)
def form_by_item(m, o, holder, *_):
    """For the Pokemon at *holder: species 0x2cc runs 0x133b218(1, 0); species 0x378 / 0x379 in form 0
    whose held item's name hash ([o+0x190] vf 0x30) is the matching one also do, as the tail call."""
    from pokeldn.sv.battle.machine import FUNCTIONS, UnliftedCall
    if 0x133B218 not in FUNCTIONS:          # reached after the getters write
        raise UnliftedCall("main+0x133b218")
    acc = lambda: m.u64(m.u64(holder) + 0x70)
    species = m.call(m.main + 0xBF44F4, acc()) & 0xFFFFFFFF
    form = m.call(m.main + 0xBF41A8, acc()) & 0xFFFFFFFF
    item = m.call(m.main + 0xD974E0, acc()) & 0xFFFFFFFF
    if species & 0xFFFF == 0x2CC:
        m.call_void(m.main + 0x133B218, m.u64(holder), 1, 0)
    t = m.u64(o + 0x190)
    if t:
        n = m.u32(t + 0x28)
        m.put(t + 0x28, 4, n + 1)
        if n == 0xFFFFFFFF:
            raise UnliftedCall("IncrementReference abort")
    r = m.vcall(t, 0x30, item)
    h = r
    if t:
        n = m.u32(t + 0x28)
        m.put(t + 0x28, 4, n - 1)
        if n == 1:
            r = _tail(m, m.u64(m.u64(t) + 0x10), t)
        elif n == 0:
            raise UnliftedCall("DecrementReference abort")
    if form & 0xFFFF == 0 and (species & 0xFFFF, h) in ((0x378, 0x8DF6C2E67AAFBBDF),
                                                          (0x379, 0x082F905FCEFDE31B)):
        return m.call(m.main + 0x133B218, m.u64(holder), 1, 0)
    return r


@lifted(0xD8FA80)
def effort(m, o, i, *_):
    """EV i (0 HP .. 5 Spe) of [[o+0x48]+0x70]; 0 for i above 5 (0xd8fa88, jump table 0x3c62c98)."""
    i &= 0xFF
    if i > 5:
        return 0
    getter = (0xD8FAE8, 0xD8FE2C, 0xD90170, 0xD904B4, 0xD90B3C, 0xD907F8)[i]
    return m.call(m.main + getter, m.u64(m.u64(o + 0x48) + 0x70))


@lifted(0xE14560)
def computed_spa(m, pp, *_):
    """Sp. Atk computed from the core record (pokemon._computed_stat: base 0xcee2d0, hyper-training bit 3,
    IV 0xd9894c, EV 0xd904b4, nature column 2)."""
    return _computed_stat(0xCEE2D0, 3, 0xD9894C, 0xD904B4, 2)(m, pp)


@lifted(0x287A330)
def refresh_pokeparam(m, o, full, a, b, again, *_):
    """Copy values of the Pokemon object [o+0x48] into the battler: when `full`, +0x5a (vf 0x80) and
    +0x58 (vf 0x70(0) * u16 +0x3f4 / 10); +0x54 (vf 0xb8); own vf 0x7f8(b, a); when b, +0x47e (vf 0x140);
    when `again`, own vf 0x810 before and (as the tail call) after; the form (0xbf41a8) at +0x718 when
    the object's type chain holds 0x46dcd58."""
    from pokeldn.sv.battle.machine import FUNCTIONS, UnliftedCall
    if 0x103B7D0 not in FUNCTIONS:          # reached after the first writes (vf 0x7f8, vf 0x350, 0x287a9cc)
        raise UnliftedCall("main+0x103b7d0")
    if full & 1:
        p = m.u64(o + 0x48)
        m.put(o + 0x5A, 2, m.vcall(p, 0x80))
        v = m.vcall(m.u64(o + 0x48), 0x70, 0) & 0xFFFF
        m.put(o + 0x58, 2, ((v * m.u16(o + 0x3F4)) & 0xFFFFFFFF) // 10)
    m.put(o + 0x54, 4, m.vcall(m.u64(o + 0x48), 0xB8))
    m.vcall_void(o, 0x7F8, b & 1, a & 1)
    if b & 1:
        m.put(o + 0x47E, 2, m.vcall(m.u64(o + 0x48), 0x140))
    if again & 1:
        m.vcall_void(o, 0x810)
    p = m.u64(o + 0x48)
    found, x0 = _holds_pokeparam_type(m, p)
    if found:
        x0 = m.call(m.main + 0xBF41A8, m.u64(m.u64(p + 0x48) + 0x70))
        m.put(o + 0x718, 2, x0)
    if again & 1:
        return _tail(m, m.u64(m.u64(o) + 0x810), o)
    return x0


@lifted(0xFA1220)
def form_by_item_all(m, o, holder, *_):
    """0xfa13d0 for each of the [*holder+0x60] members (+0x30, at most 6) whose type chain holds
    0x46dcd58, through a counted reference to its Pokemon object (+0x48)."""
    from pokeldn.sv.battle.machine import FUNCTIONS, UnliftedCall
    if 0x133B218 not in FUNCTIONS:          # 0xfa13d0 reaches it after this writes
        raise UnliftedCall("main+0x133b218")
    n = m.u8(m.u64(holder) + 0x60)
    x0 = o
    for i in range(n):
        p = m.u64(m.u64(holder) + 0x30 + 8 * i) if i <= 5 else 0
        if not _holds_pokeparam_type(m, p)[0]:
            x0 = 0
            continue
        pp = m.u64(p + 0x48)
        with m.frame(0x10) as local:
            m.put(local, 8, pp)
            if pp == 0:
                x0 = m.call(m.main + 0xFA13D0, o, local)
                continue
            c = m.u32(pp + 0x28)
            m.put(pp + 0x28, 4, c + 1)
            if c == 0xFFFFFFFF:
                raise UnliftedCall("IncrementReference abort")
            x0 = m.call(m.main + 0xFA13D0, o, local)
        c = m.u32(pp + 0x28)
        m.put(pp + 0x28, 4, c - 1)
        if c == 1:
            x0 = _tail(m, m.u64(m.u64(pp) + 0x10), pp)
        elif c == 0:
            raise UnliftedCall("DecrementReference abort")
    return x0


def _pokemon_getters():
    lifted(0xBF41A8)(_getter(0, 0x1C, 2, 0, 0x4742290, False))     # block A +0x1c (u16)


_pokemon_getters()


@lifted(0xE14018)
def clamp_pp(m, pp, *_):
    """For each of the first n moves (n = how many of the four are set): PP above its maximum
    (0xbf5fe0(move, PP Ups)) is lowered to it."""
    acc = lambda: m.u64(pp + 0x70)
    n = sum(1 for i in range(4) if m.call(m.main + 0xDEDBC8, acc(), i) & 0xFFFF)
    for i in range(n):
        mx = m.call(m.main + 0xBF5FE0, m.call(m.main + 0xDEDBC8, acc(), i), m.call(m.main + 0xBF61D4, acc(), i))
        if mx & 0xFF < m.call(m.main + 0xDEE950, acc(), i) & 0xFF:
            again = m.call(m.main + 0xBF5FE0, m.call(m.main + 0xDEDBC8, acc(), i), m.call(m.main + 0xBF61D4, acc(), i))
            m.call_void(m.main + 0xDEDF30, acc(), i, again if again & 0xFF < mx & 0xFF else mx)


@lifted(0x287A6B8)
def level(m, o, *_):
    """The party record's level, or 0xe13da0(species, form, experience) when there is none."""
    acc = m.u64(m.u64(o + 0x48) + 0x70)
    if m.u64(acc + 8):
        return m.call(m.main + 0xD9987C, acc)
    species = m.call(m.main + 0xBF44F4, acc)
    form = m.call(m.main + 0xBF41A8, m.u64(m.u64(o + 0x48) + 0x70))
    exp = m.call(m.main + 0xE14B64, m.u64(m.u64(o + 0x48) + 0x70))
    return m.call(m.main + 0xE13DA0, species, form, exp) & 0xFF


@lifted(0x287A880)
def pp_ups_of(m, o, i, *_):
    return m.call(m.main + 0xBF61D4, m.u64(m.u64(o + 0x48) + 0x70), i)


@lifted(0x287A9DC)
def species_form_115b968(m, o, *_):
    """0x115b968 on {[0x46d8ee0] + 0x10, u16 species, u16 form}."""
    species = m.call(m.main + 0xBF44F4, m.u64(m.u64(o + 0x48) + 0x70))
    form = m.call(m.main + 0xBF41A8, m.u64(m.u64(o + 0x48) + 0x70))
    with m.frame(0x10) as p:
        m.put(p, 8, m.u64(m.main + 0x46D8EE0) + 0x10)
        m.put(p + 8, 2, species); m.put(p + 0xA, 2, form)
        return m.call(m.main + 0x115B968, p)


@lifted(0x287AAC0)
def release_plain(m, o, flag, *_):
    """When the record is kept plain (+0x19) and bit 0 of flag: 0xd679f0(record accessor), 1."""
    acc = m.u64(m.u64(o + 0x48) + 0x70)
    if m.u8(acc + 0x19) and flag & 1:
        m.call_void(m.main + 0xD679F0, acc)
        return 1
    return 0


@lifted(0x287AA90)
def keep_plain_once(m, o, *_):
    """0xd677e8 on the record accessor unless it is already kept plain: 1 when it was called."""
    acc = m.u64(m.u64(o + 0x48) + 0x70)
    if m.u8(acc + 0x19):
        return 0
    m.call_void(m.main + 0xD677E8, acc)
    return 1


_BASE_STAT = (0xCEDBF4, 0xCEDDA8, 0xCEDF60, 0xCEE2D0, 0xCEE488, 0xCEE118)   # jump table 0x3c62ca4


@lifted(0xCEDAA8)
def base_stat(m, pp, i, *_):
    """Base stat i (0..5) of the Pokemon's species and form, through a {[0x46d8ee0]+0x10, species,
    form} key; 0 out of range."""
    species = m.call(m.main + 0xBF44F4, m.u64(pp + 0x70))
    form = m.call(m.main + 0xBF41A8, m.u64(pp + 0x70))
    i &= 0xFF
    if i > 5:
        return 0
    with m.frame(0x10) as k:
        m.put(k, 8, m.u64(m.main + 0x46D8EE0) + 0x10); m.put(k + 8, 2, species); m.put(k + 0xA, 2, form)
        return m.call(m.main + _BASE_STAT[i], k) & 0xFF


@lifted(0xE13CB8)
def refresh_max_hp(m, pp, keep_fainted, *_):
    """Recompute the stats (0xe16488 with 0xe13ef0's max HP) and move current HP by the max HP's change,
    capped at the new maximum; a fainted Pokemon stays at 0 when keep_fainted."""
    def max_hp():
        acc = m.u64(pp + 0x70)
        return m.call(m.main + 0xC75438, acc) if m.u64(acc + 8) else m.call(m.main + 0xE13EF0, pp) & 0xFFFF
    old = max_hp() & 0xFFFFFFFF
    acc = m.u64(pp + 0x70)
    cur = (m.call(m.main + 0xCDF348, acc) if m.u64(acc + 8) else m.call(m.main + 0xE13EF0, pp) & 0xFFFF) & 0xFFFFFFFF
    m.call_void(m.main + 0xE16488, m.u64(pp + 0x70), m.call(m.main + 0xE13EF0, pp) & 0xFFFFFFFF)
    if cur == 0 and keep_fainted & 1:
        return
    new = max_hp() & 0xFFFFFFFF
    hp = (min(new, cur) if new < old else (cur - old + new)) & 0xFFFFFFFF
    top = m.call(m.main + 0xC75438, m.u64(pp + 0x70)) & 0xFFFFFFFF
    return _tail(m, m.main + 0xE14810, m.u64(pp + 0x70), min(top, hp))


@lifted(0xCEDA90)
def base_stat_of(m, o, i, *_):
    return m.call(m.main + 0xCEDAA8, m.u64(o + 0x48), i)


# Nature modifiers (s8, 25 natures x 5 stats Atk Def SpA SpD Spe) at 0x3c62e98.
_NATURE_3C62E98 = (
    0, 0, 0, 0, 0, 1, -1, 0, 0, 0, 1, 0, 0, 0, -1, 1, 0, -1, 0, 0, 1, 0, 0, -1, 0, -1, 1, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 1, 0, 0, -1, 0, 1, -1, 0, 0, 0, 1, 0, -1, 0, -1, 0, 0, 0, 1, 0, -1, 0, 0, 1, 0, 0, 0, 0,
    0, 0, 0, -1, 0, 1, 0, 0, 0, -1, 1, -1, 0, 1, 0, 0, 0, -1, 1, 0, 0, 0, 0, 1, 0, -1, 0, 0, 0, 0, 0, 0,
    0, 1, -1, 0, -1, 0, 0, 1, 0, 0, -1, 0, 1, 0, 0, 0, 0, 1, -1, 0, 0, -1, 1, 0, 0, 0, 0, 0, 0)


def _computed_stat(base_fn, iv_bit, iv_fn, ev_fn, col):
    """A stat computed from the core record: ((IV + 2 base + EV/4) * level / 100 + 5), times 0.9 or
    1.1 by nature; a hyper-trained IV (0xc1eb6c bit) counts 31."""
    def fn(m, pp, *_):
        acc = m.u64(pp + 0x70)
        if m.u64(acc + 8):
            level = m.call(m.main + 0xD9987C, acc)
        else:
            sp = m.call(m.main + 0xBF44F4, acc)
            fo = m.call(m.main + 0xBF41A8, m.u64(pp + 0x70))
            level = m.call(m.main + 0xE13DA0, sp, fo, m.call(m.main + 0xE14B64, m.u64(pp + 0x70))) & 0xFF
        sp = m.call(m.main + 0xBF44F4, m.u64(pp + 0x70))
        fo = m.call(m.main + 0xBF41A8, m.u64(pp + 0x70))
        with m.frame(0x10) as k:
            m.put(k, 8, m.u64(m.main + 0x46D8EE0) + 0x10); m.put(k + 8, 2, sp); m.put(k + 0xA, 2, fo)
            base = m.call(m.main + base_fn, k)
        if m.call(m.main + 0xC1EB6C, m.u64(pp + 0x70)) >> iv_bit & 1:
            iv = 0x1F
        else:
            iv = m.call(m.main + iv_fn, m.u64(pp + 0x70)) & 0xFFFF
        ev = m.call(m.main + ev_fn, m.u64(pp + 0x70))
        nature = m.call(m.main + 0xC4EA44, m.u64(pp + 0x70)) & 0xFFFF
        v = ((iv + 2 * (base & 0xFF) + (ev >> 2 & 0x3FFF)) * (level & 0xFF)) & 0xFFFFFFFF
        v = (v // 100 + 5) & 0xFFFFFFFF
        i = 5 * nature + col
        mod = _NATURE_3C62E98[i] if i < len(_NATURE_3C62E98) else m.s(m.main + 0x3C62E98 + i, 1)
        if mod in (-1, 1):
            v = ((v * (0x5A if mod == -1 else 0x6E)) & 0xFFFE) // 100
        return v
    return fn


lifted(0xE1415C)(_computed_stat(0xCEDDA8, 1, 0xD982BC, 0xD8FE2C, 0))
lifted(0xE14408)(_computed_stat(0xCEE118, 5, 0xD98C94, 0xD907F8, 4))


def _locked(m, acc, fn, *args):
    """Run 0x<fn>(acc, *args) holding the record accessor's lock (owner +0x20, light event +0x28)."""
    cur = m.call(m.main + 0x343C290)
    if m.u64(acc + 0x20):
        raise UnliftedCall("record accessor held by another thread")
    m.put(acc + 0x20, 8, cur)
    m.call_void(m.main + fn, acc, *args)
    m.put(acc + 0x20, 8, 0)
    m.call_void(m.main + 0x343E5E0, acc + 0x28)


@lifted(0xEEEA48)
def copy_core_record(m, pp, src, *_):
    """Copy src's core record into pp's: read it out of [src+0x70] (0xe32a60) and write it into
    [pp+0x70] (0xe14ea8), each under the accessor's lock, then recompute the stats (0xe13b9c(pp, 1))
    and tail-call 0xe14018(pp)."""
    with m.frame(0x160) as buf:
        _locked(m, m.u64(src + 0x70), 0xE32A60, buf, buf + 0x148)
        _locked(m, m.u64(pp + 0x70), 0xE14EA8, buf, buf + 0x148)
    m.call_void(m.main + 0xE13B9C, pp, 1)
    return _tail(m, m.main + 0xE14018, pp)


@lifted(0x2D3BAE0)
def species_402_406(m, b, *_):
    p = m.u64(b + 0x700)
    return m.u16(b + 0x402) if p and m.u32(p + 0xB8) else m.u16(b + 0x406)


@lifted(0x115B968)
def form_record_u16(m, key_holder, *_):
    """The u16 at +0xa past field 0 of the record keyed by u16(+8) * 10000 + u16(+0xa) in the static
    table 0x46d7438 (its default at +0xd0); the field is read without a vtable size check."""
    from pokeldn.sv.battle.engine.containers import find
    from pokeldn.sv.battle.engine.data import static_table
    table = static_table(m, 0x46D7430, 0x46D7438, 0x46D7440)
    key = m.u16(key_holder + 8) * 10000 + m.u16(key_holder + 0xA)
    node = find(m, table + 0x68, key, 8)
    rec = m.u64(node + 0x18) if node else m.u64(table + 0xD0)
    return m.u16(rec + m.u16(rec - m.s(rec, 4) + 4) + 0xA)


@lifted(0x287F270)
def raise_on_species_271(m, o, holder, pk, *_):
    """When the Pokemon holds the static, is species 0x271 (+0x710) and the 0x4690abda0b4ec6c4 query
    holds, raise the holder's battler's stat 3 by one (vf 0x550) and queue message 0x37."""
    if holder == 0 or pk == 0 or m.u64(holder) == 0:
        return
    if not _has_static(m, pk) or m.u16(pk + 0x710) != 0x271:
        return
    v = m.vcall(pk, 0x2A8) & 0xFFFFFFFF
    if m.call(m.main + 0x151BB5C, m.u64(o + 8), 0x4690ABDA0B4EC6C4, v) & 1 == 0:
        return
    ident = m.vcall(m.u64(holder), 0x98) & 0xFFFFFFFF
    q = m.u64(o + 0x20)
    b = battler(m, m.u64(m.u64(m.u64(q + 0x20) + 0x10) + 0x30), ident)
    m.vcall_void(b, 0x550, 3, 1)
    return _tail(m, m.main + 0x119AFF0, m.u64(q + 0x18), 0x37, ident, 3, 1)


@lifted(0xBF44F4)
def species(m, acc, *_):
    """The species: the u16 at the start of block A."""
    return access(m, acc, lambda core: m.u16(block(m, core, 0)))


@lifted(0x287A8C0)
def form_check_133b78c(m, b, *_):
    core = m.u64(b + 0x48)
    r = m.call(m.main + 0x103B8A0, m.u64(core + 0x70))
    if r & 0xFFFF < 0x137:
        return r
    s = m.call(m.main + 0xBF44F4, m.u64(core + 0x70))
    f = m.call(m.main + 0xBF41A8, m.u64(core + 0x70))
    g = m.call(m.main + 0xD99784, core)
    return _tail(m, m.main + 0x133B78C, s & 0xFFFFFFFF, f & 0xFFFFFFFF, g & 0xFFFFFFFF)


@lifted(0xD679F0)
def seal_record(m, acc, *_):
    """Under the record's lock clear keep-plain (+0x19) and, when the record is plain, store its
    checksum and encrypt the core and party records."""
    from pokeldn.sv.battle.engine.libc import FAKE_THREAD, signal_light_event
    if m.u64(acc + 0x20) != 0:
        raise UnliftedCall("pokemon record already locked")
    m.put(acc + 0x20, 8, FAKE_THREAD)
    m.put(acc + 0x19, 1, 0)
    if m.u8(acc + 0x18) == 0:
        core = m.u64(acc + 0x10)
        if core:
            m.put(core + 6, 2, _checksum(m, core))
            _xor_words(m, core + BLOCKS, (CORE - BLOCKS) // 2, m.u32(core))
        party = m.u64(acc + 8)
        if party and m.u64(acc + 0x10):
            _xor_words(m, party, 8, m.u32(m.u64(acc + 0x10)))
        m.put(acc + 0x18, 1, 1)
    m.put(acc + 0x20, 8, 0)
    return signal_light_event(m, acc + 0x28)


@lifted(0x287A5B4)
def party_or_stored_c75438(m, b, *rest):
    """0xc75438 of the record accessor when it holds a party record, else 0xe13ef0 of the core."""
    core = m.u64(b + 0x48)
    acc = m.u64(core + 0x70)
    if m.u64(acc + 8):
        return _tail(m, m.main + 0xC75438, acc, *rest[:6])
    return m.call(m.main + 0xE13EF0, core, *rest[:6]) & 0xFFFF


@lifted(0xE13DA0)
def level_for_exp(m, species, form, exp, *_):
    """The level (1..100) whose experience threshold the growth rate (0xb860e0) puts at or below exp:
    the u32 thresholds at [table field 0] + rate * 0x194 + level * 4 of the static at 0x46da7c8."""
    exp &= 0xFFFFFFFF
    level = 1
    with m.frame(0x10) as p:
        while True:
            m.put(p, 8, m.u64(m.main + 0x46D8EE0) + 0x10)
            m.put(p + 8, 2, species); m.put(p + 0xA, 2, form)
            rate = m.call(m.main + 0xB860E0, p) & 0xFF
            table = static_table(m, 0x46DA7C0, 0x46DA7C8, 0x46DA7D0)
            root = m.vcall(m.u64(table + 0x30), 0x70)
            if root == 0:
                need = 1
            else:
                t = root + m.u32(root)
                rows = t + m.u16(t - m.s(t, 4) + 4)
                need = m.u32(rows + (0 if rate > 8 else rate) * 0x194 + level * 4)
            if need > exp:
                break
            level += 1
            if level == 0x65:
                return 100
    return level - 1 if level & 0xFF >= 2 else 1


@lifted(0xE13EF0)
def computed_max_hp(m, pp, *_):
    """Max HP from the core record: (IV + 2 * base + EV / 4) * level / 100 + level + 10; 1 for species
    0x124. The level is the party record's, or the one the experience gives."""
    for a in (0xBF41A8, 0xCEDBF4, 0xD97F74, 0xE14B64, 0xE13DA0, 0xD9987C, 0xC1EB6C, 0xD8FAE8):
        _need(m, m.main + a)
    acc = m.u64(pp + 0x70)
    species = m.call(m.main + 0xBF44F4, acc) & 0xFFFF
    if m.u64(acc + 8):
        level = m.call(m.main + 0xD9987C, acc) & 0xFF
    else:
        s = m.call(m.main + 0xBF44F4, acc)
        f = m.call(m.main + 0xBF41A8, m.u64(pp + 0x70))
        e = m.call(m.main + 0xE14B64, m.u64(pp + 0x70))
        level = m.call(m.main + 0xE13DA0, s & 0xFFFFFFFF, f & 0xFFFFFFFF, e & 0xFFFFFFFF) & 0xFF
    s = m.call(m.main + 0xBF44F4, m.u64(pp + 0x70))
    f = m.call(m.main + 0xBF41A8, m.u64(pp + 0x70))
    with m.frame(0x10) as p:
        m.put(p, 8, m.u64(m.main + 0x46D8EE0) + 0x10)
        m.put(p + 8, 2, s); m.put(p + 0xA, 2, f)
        base = m.call(m.main + 0xCEDBF4, p) & 0xFF
    if m.call(m.main + 0xC1EB6C, m.u64(pp + 0x70)) & 1:
        iv = 0x1F
    else:
        iv = m.call(m.main + 0xD97F74, m.u64(pp + 0x70)) & 0xFFFF
    ev = m.call(m.main + 0xD8FAE8, m.u64(pp + 0x70)) & 0xFFFFFFFF
    if species == 0x124:
        return 1
    return (((iv + 2 * base + (ev >> 2 & 0x3FFF)) * level & 0xFFFFFFFF) // 100 + level + 10) & 0xFFFFFFFF


# Nature modifiers (0x3c62e98, 5 bytes per nature: Atk, Def, Spe, SpA, SpD; 1 raised, 0xff lowered).
_NATURE = (
    (0, 0, 0, 0, 0), (1, 255, 0, 0, 0), (1, 0, 0, 0, 255), (1, 0, 255, 0, 0), (1, 0, 0, 255, 0),
    (255, 1, 0, 0, 0), (0, 0, 0, 0, 0), (0, 1, 0, 0, 255), (0, 1, 255, 0, 0), (0, 1, 0, 255, 0),
    (255, 0, 0, 0, 1), (0, 255, 0, 0, 1), (0, 0, 0, 0, 0), (0, 0, 255, 0, 1), (0, 0, 0, 255, 1),
    (255, 0, 1, 0, 0), (0, 255, 1, 0, 0), (0, 0, 1, 0, 255), (0, 0, 0, 0, 0), (0, 0, 1, 255, 0),
    (255, 0, 0, 1, 0), (0, 255, 0, 1, 0), (0, 0, 0, 1, 255), (0, 0, 255, 1, 0), (0, 0, 0, 0, 0))


def _computed_stat_checked(base_fn, trained_bit, iv_fn, ev_fn, column):
    """A stat from the core record: (IV, or 31 when hyper trained, + 2 * base + EV / 4) * level / 100 + 5,
    times 1.1 or 0.9 for the nature."""
    def fn(m, pp, *_):
        for a in (0xBF41A8, base_fn, iv_fn, ev_fn, 0xC4EA44, 0xE14B64, 0xE13DA0, 0xD9987C):
            _need(m, m.main + a)
        acc = m.u64(pp + 0x70)
        if m.u64(acc + 8):
            level = m.call(m.main + 0xD9987C, acc) & 0xFF
        else:
            s = m.call(m.main + 0xBF44F4, acc)
            f = m.call(m.main + 0xBF41A8, m.u64(pp + 0x70))
            e = m.call(m.main + 0xE14B64, m.u64(pp + 0x70))
            level = m.call(m.main + 0xE13DA0, s & 0xFFFFFFFF, f & 0xFFFFFFFF, e & 0xFFFFFFFF) & 0xFF
        s = m.call(m.main + 0xBF44F4, m.u64(pp + 0x70))
        f = m.call(m.main + 0xBF41A8, m.u64(pp + 0x70))
        with m.frame(0x10) as p:
            m.put(p, 8, m.u64(m.main + 0x46D8EE0) + 0x10)
            m.put(p + 8, 2, s); m.put(p + 0xA, 2, f)
            base = m.call(m.main + base_fn, p) & 0xFF
        if m.call(m.main + 0xC1EB6C, m.u64(pp + 0x70)) >> trained_bit & 1:
            iv = 0x1F
        else:
            iv = m.call(m.main + iv_fn, m.u64(pp + 0x70)) & 0xFFFF
        ev = m.call(m.main + ev_fn, m.u64(pp + 0x70)) & 0xFFFFFFFF
        nature = m.call(m.main + 0xC4EA44, m.u64(pp + 0x70)) & 0xFFFF
        v = (((iv + 2 * base + (ev >> 2 & 0x3FFF)) * level & 0xFFFFFFFF) // 100 + 5) & 0xFFFFFFFF
        mod = _NATURE[nature][column] if nature < len(_NATURE) else m.u8(m.main + 0x3C62E98 + 5 * nature + column)
        if mod == 0xFF:
            return (v * 90 & 0xFFFE) // 100
        if mod == 1:
            return (v * 110 & 0xFFFE) // 100
        return v
    return fn


for _a, _spec in ((0xE142B0, (0xCEDF60, 2, 0xD98604, 0xD90170, 1)), (0xE146B8, (0xCEE488, 4, 0xD98FDC, 0xD90B3C, 3))):
    lifted(_a)(_computed_stat_checked(*_spec))


@lifted(0xE13B9C)
def recompute_stats(m, pp, keep, *_):
    """Keep the record plain (0xd677e8) unless it already is, then store the level for its experience
    and every stat (0xe13cb8(keep & 1) for HP, then Atk, Def, SpA, SpD, Spe) into the party record;
    drop the plain hold again (0xd679f0) when this call took it."""
    for a in (0xD677E8, 0xBF41A8, 0xE14B64, 0xE13DA0, 0xE15150, 0xE13CB8, 0xE1415C, 0xE15484, 0xE142B0,
              0xE157B8, 0xE14560, 0xE15E20, 0xE146B8, 0xE16154, 0xE14408, 0xE15AEC, 0xD679F0):
        _need(m, m.main + a)
    took = m.u8(m.u64(pp + 0x70) + 0x19) == 0
    if took:
        m.call(m.main + 0xD677E8, m.u64(pp + 0x70))
    s = m.call(m.main + 0xBF44F4, m.u64(pp + 0x70)) & 0xFFFFFFFF
    f = m.call(m.main + 0xBF41A8, m.u64(pp + 0x70)) & 0xFFFFFFFF
    e = m.call(m.main + 0xE14B64, m.u64(pp + 0x70)) & 0xFFFFFFFF
    lv = m.call(m.main + 0xE13DA0, s, f, e) & 0xFFFFFFFF
    m.call_void(m.main + 0xE15150, m.u64(pp + 0x70), lv)
    m.call_void(m.main + 0xE13CB8, pp, keep & 1)
    r = None
    for get, put in ((0xE1415C, 0xE15484), (0xE142B0, 0xE157B8), (0xE14560, 0xE15E20), (0xE146B8, 0xE16154),
                     (0xE14408, 0xE15AEC)):
        v = m.call(m.main + get, pp) & 0xFFFFFFFF
        r = _tail(m, m.main + put, m.u64(pp + 0x70), v)
    if took and m.u8(m.u64(pp + 0x70) + 0x19):
        return _tail(m, m.main + 0xD679F0, m.u64(pp + 0x70))
    return r


@lifted(0x287E240)
def form_change_allowed(m, o, out, p, *_):
    """out (byte) = whether battler [p] may change form: a fainted one passes; event 0xde must not refuse,
    then with p+9 set event 0xdf decides the result."""
    b = m.u64(p)
    if m.vcall(b, 0x200) & 1:
        m.put(out, 1, 1)
        return
    ident = m.vcall(b, 0x98) & M32
    form = m.vcall(b, 0xF0) & M32
    if m.call(m.main + 0x283B434, m.call(m.main + 0x1146E90, o), ident, form, m.u8(p + 8)) & 1:
        m.put(out, 1, 0)
        return
    m.put(out, 1, 1)
    if m.u8(p + 9):
        return _tail(m, m.main + 0x283B83C, m.call(m.main + 0x1146E90, o), ident, form, m.u8(p + 8))


@lifted(0x287DD60)
def form_change_allowed_of(m, o, b, *_):
    with m.frame(0x20) as f:
        m.put(f + 0x10, 8, b); m.put(f + 0x18, 2, 0x100)
        m.call_void(m.main + 0x287E240, m.call(m.main + 0x287E238, m.call(m.main + 0x1361214, o)), f + 8, f + 0x10)
        return m.u8(f + 8)


def _personal_by_species(getter):
    def fn(m, pp, *_):
        """Personal-table value `getter` reads for the Pokemon's species and form; for Arceus (0x1ed) with
        ability 0x79 and Silvally (0x305) with ability 0xe1, the type from the held item instead."""
        acc = lambda: m.u64(pp + 0x70)
        species = m.call(m.main + 0xBF44F4, acc())
        ability = m.call(m.main + 0x103B8A0, acc()) & 0xFFFF
        if species & 0xFFFF == 0x1ED and ability == 0x79:
            return _tail(m, m.main + 0x20F8278, m.call(m.main + 0xD974E0, acc()))
        if species & 0xFFFF == 0x305 and ability == 0xE1:
            return _tail(m, m.main + 0x20F77F4, m.call(m.main + 0xD974E0, acc()))
        form = m.call(m.main + 0xBF41A8, acc())
        with m.frame(0x10) as k:
            m.put(k, 8, m.u64(m.main + 0x46D8EE0) + 0x10); m.put(k + 8, 2, species); m.put(k + 0xA, 2, form)
            return m.call(m.main + getter, k)
    return fn


lifted(0x103B7D0)(_personal_by_species(0x1012D44))
lifted(0x1055170)(_personal_by_species(0x1046124))


@lifted(0x287A9D4)
def pokeparam_1055170(m, o, *_):
    return _tail(m, m.main + 0x1055170, m.u64(o + 0x48))


@lifted(0x121C054)
def friendship(m, acc, *_):
    """The current handler's friendship: byte +0x20 of logical block 2 when its +0x1c is set, else byte
    +0x1a of logical block 3 (stand-ins 0x4742330 / 0x4742380 for a record flagged bad)."""
    def read(core):
        c = _target(m, acc, core, 2, 0x4742330)
        if m.u8(c + 0x1C):
            return m.u8(c + 0x20)
        return m.u8(_target(m, acc, core, 3, 0x4742380) + 0x1A)
    return access(m, acc, read)


@lifted(0x149FE94)
def friendship_event(m, s, b, close, *_):
    """Outside raids (rule 0x499 bit 2) and battles of kind [s+0x30] > 1: 0x13801c0 with the hashed event
    name 0x91878d2e67dac9bc (close in level) or 0xed853956cb8c2ca7."""
    if m.u8(m.u64(s + 0x38) + 0x499) >> 2 & 1 or m.u32(m.u64(s + 0x38) + 0x30) > 1:
        return s
    key = 0x91878D2E67DAC9BC if close & 1 else 0xED853956CB8C2CA7
    return _tail(m, m.main + 0x13801C0, s, b, key)


@lifted(0x13801C0)
def friendship_both_sides(m, s, b, key, *_):
    """0x1380220 for b's id on the members [s+0x170] and [s+0x150], with {&key, key} on the stack."""
    with m.frame(0x10) as f:
        m.put(f, 8, f + 8); m.put(f + 8, 8, key)
        ident = m.vcall(b, 0x98) & M32
        m.call_void(m.main + 0x1380220, f, m.u64(s + 0x170), ident)
        return _tail(m, m.main + 0x1380220, f, m.u64(s + 0x150), ident)


@lifted(0x1380220)
def friendship_member(m, ctx, side, ident, *_):
    """When member `ident` of [side+0x30] (0xf79790) is of the class 0x46d3f08: 0x13802f4 on its stored
    Pokemon (0x1380644) with the key **ctx."""
    r = m.call(m.main + 0xF79790, m.u64(side + 0x30), ident & M32)
    lst = m.vcall(r + 0x28, 0)
    static = m.call(m.main + 0x2D1FD38)
    while lst:
        if lst == static:
            pp = m.call(m.main + 0x1380644, r)
            return _tail(m, m.main + 0x13802F4, pp, m.u64(m.u64(ctx)))
        lst = m.u64(lst)
    return 0


@lifted(0x1380644)
def stored_pokemon(m, r, *_):
    """[[r+0x48]+0x48] when [r+0x48]+0x28 is of the class at [main+0x46dcd58], else 0."""
    x = m.u64(r + 0x48) + 0x28
    node = m.vcall(x, 0)
    _static_built(m, 0x46DCD50)
    static = m.u64(m.main + 0x46DCD58)
    while node:
        if node == static:
            return m.u64(x + 0x20)
        node = m.u64(node)
    return 0


@lifted(0x13802F4)
def friendship_apply(m, pp, key, *_):
    """0x1380380 on the friendship table (the static at [main+0x46d78e0], also stored at main+0x4742260)."""
    _static_built(m, 0x46D78D8)
    t = m.u64(m.u64(m.main + 0x46D78E0))
    m.put(m.main + 0x4742260, 8, t)
    return _tail(m, m.main + 0x1380380, t, pp, key)


@lifted(0x1380380)
def friendship_change(m, t, pp, key, *_):
    """The u64-keyed map at t+0x28 maps an event name to three s32 deltas (friendship below 100, below
    160, above): unless the record is an egg or bad, friendship += 0x1380500's delta, clamped to 0..255
    (0xdf7530), then the stats are recomputed (0xe13b9c(pp, 1))."""
    from pokeldn.sv.battle.engine.containers import find
    node = find(m, t + 0x28, key & M64, 8)
    if not node:
        return
    acc = m.u64(pp + 0x70)
    if m.call(m.main + 0xBF4CFC, acc) & 1:
        return
    if m.u16(m.u64(acc + 0x10) + 4) >> 2 & 1:
        return
    cur = m.call(m.main + 0x121C054, acc) & M32
    d = m.call(m.main + 0x1380500, cur, pp, node + 0x18)
    v = _s32(d + cur)
    v = min(max(v, 0), 0xFF)
    m.call_void(m.main + 0xDF7530, m.u64(pp + 0x70), v)
    return _tail(m, m.main + 0xE13B9C, pp, 1)


@lifted(0x1380500)
def friendship_delta(m, _x, pp, deltas, *_):
    """deltas[0 / 1 / 2] by friendship (< 100, < 160, else); a gain gets +1 in a Luxury Ball (0xb) and
    x1.5 (float32, truncated) when the item lookup at [[main+0x46d90c8]]+0x250 answers 0x5c for the held
    item."""
    import struct
    acc = m.u64(pp + 0x70)
    f = _s32(m.call(m.main + 0x121C054, acc))
    v = _s32(m.u32(deltas + 4 * (0 if f < 0x64 else 1 if f < 0xA0 else 2)))
    if v < 1:
        return v & M32
    ball = m.call(m.main + 0x1300BA8, m.u64(pp + 0x70)) & 0xFF
    bonus = int((ball - 1) & 0xFF < 0x1A and ball == 0xB)
    item = m.call(m.main + 0xD974E0, m.u64(pp + 0x70)) & 0xFFFF
    _static_built(m, 0x46D89B0)
    g = m.u64(m.u64(m.main + 0x46D90C8))
    fn = m.u64(g + 0x250)
    if fn and fn - m.main not in FUNCTIONS:
        raise UnliftedCall(f"main+0x{fn - m.main:x}")
    m.put(m.u64(m.main + 0x46D89C0), 8, m.u64(m.u64(m.main + 0x46D89B8)))
    v = (v + bonus) & M32
    if not fn:
        return v
    with m.frame(0x10) as k:
        m.put(k, 2, item)
        r = m.call(fn, g + 0x270, k)
    if r & 0xFFFF == 0x5C:
        x = struct.unpack("<f", struct.pack("<f", float(_s32(v))))[0] * 1.5
        return int(_f32(x)) & M32
    return v


@lifted(0x1300BA8)
def ball(m, acc, *_):
    """Byte +0x2c of logical block 3 (stand-in 0x4742380 for a bad record)."""
    return _getter(3, 0x2C, 1, 0, 0x4742380, False)(m, acc)


@lifted(0xDF7530)
def set_friendship(m, acc, v, *_):
    """The current handler's friendship: block 2 +0x20 when block 2 +0x1c is set, else block 3 +0x1a
    (stand-ins 0x4742480 / 0x47424d0 for a bad record, chosen by the read stand-in's +0x1c at
    0x474234c)."""
    def write(core):
        if m.u8(core + 4) >> 2 & 1:
            if m.u8(m.main + 0x474234C):
                m.put(m.main + 0x4742480 + 0x20, 1, v)
            else:
                m.put(m.main + 0x47424D0 + 0x1A, 1, v)
        elif m.u8(block(m, core, 2) + 0x1C):
            m.put(block(m, core, 2) + 0x20, 1, v)
        else:
            m.put(block(m, core, 3) + 0x1A, 1, v)
        return 0
    access(m, acc, write)
    return acc + 0x28
