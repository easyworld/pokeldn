"""The stored Pokemon record through its accessor: block reads and writes, encryption, keep-plain and
sealing, and form changes (the layout is in pokemon.py)."""

from pokeldn.sv.battle.engine import pokemon as _pk
from pokeldn.sv.battle.engine.calls import _need, _tail
from pokeldn.sv.battle.engine.statics import _holds_static
from pokeldn.sv.battle.machine import UnliftedCall, lifted


def _iv(shift):
    """IV word (block B +0x34) bits shift..shift+4."""
    def fn(m, acc, *_):
        return _pk.access(m, acc, lambda core: m.u32(_pk._target(m, acc, core, 1, 0x47422E0) + 0x34) >> shift & 0x1F)
    return fn


for _a, _shift in ((0xD97F74, 0), (0xD982BC, 5), (0xD98604, 10), (0xD98C94, 15), (0xD9894C, 20), (0xD98FDC, 25)):
    lifted(_a)(_iv(_shift))


def _block_a_byte(off):
    def fn(m, acc, *_):
        return _pk.access(m, acc, lambda core: m.u8(_pk._target(m, acc, core, 0, 0x4742290) + off))
    return fn


for _a, _off in ((0xD8FE2C, 0x1F), (0xD907F8, 0x21)):
    lifted(_a)(_block_a_byte(_off))

for _a, _off in ((0xE157B8, 6), (0xE16154, 0xC)):
    lifted(_a)(_pk._setter("party", _off, 2, 0, _pk.BAD_WRITE_PARTY, True))


@lifted(0xD677E8)
def keep_plain(m, acc, *_):
    """Lock the record, decrypt it, mark it kept plain (+0x19), unlock."""
    _pk.access(m, acc, lambda core: m.put(acc + 0x19, 1, 1))
    return acc + 0x28


def _peek_form(m, acc):
    """The form (u16 +0x1c of logical block 0) as the record's accessor reads it, decrypted on a
    copy (records._peek_block_u16)."""
    from pokeldn.sv.battle.engine import pokemon as _pk
    data = bytearray(m.read(m.u64(acc + 0x10), _pk.CORE))
    if m.u8(acc + 0x18):
        seed = int.from_bytes(data[0:4], "little")
        for i in range(_pk.BLOCKS, _pk.CORE, 2):
            seed = _pk._lcg(seed)
            v = (data[i] | data[i + 1] << 8) ^ (seed >> 16)
            data[i], data[i + 1] = v & 0xFF, v >> 8
        total = sum(data[i] | data[i + 1] << 8 for i in range(_pk.BLOCKS, _pk.CORE, 2)) & 0xFFFF
        if total != (data[6] | data[7] << 8):
            data[4] |= 4
    if data[4] >> 2 & 1:
        return m.u16(m.main + _pk.BAD_READ_CORE + _pk.BLOCKS + 0x1C)
    pos = _pk.BLOCK_POSITION[(int.from_bytes(data[0:4], "little") >> 13) & 0x1F][0]
    at = _pk.BLOCKS + 0x50 * pos + 0x1C
    return data[at] | data[at + 1] << 8


def _need_form_change(m, pp, form):
    """Refuse before any write when 0x133b218(pp, form) would change the form through a callee not
    lifted."""
    from pokeldn.sv.battle.machine import FUNCTIONS
    if 0x133B218 not in FUNCTIONS:
        raise UnliftedCall("main+0x133b218")
    if _peek_form(m, m.u64(pp + 0x70)) != form & 0xFFFF:
        for a in (0xBF41A8, 0xBF44F4, 0x133BA0C, 0xDF289C, 0xD99784, 0x133B78C, 0xDF2550, 0xBEC030,
                  0x133B4B4, 0xDF644C, 0xE13B9C):
            if a not in FUNCTIONS:
                raise UnliftedCall(f"form change: main+0x{a:x}")


@lifted(0x2D1F4BC)
def refresh_form_hp(m, b, *_):
    """After 0x2d3dc58: when the Pokemon's +0x28 list (vf 0) holds the static 0x46dcd58, take its form
    (+0x718: the record's form when +0x6f, else +0x712 applied through 0x133b218), set +0x58 = stat 0 *
    u16 +0x3f4 / 10, move HP toward it (vf 0x2e8 up, vf 0x2e0 down) and tail-call vf 0x810. The
    0x133b218 branch refuses before any write when it would change the form through a callee not
    lifted."""
    if m.u8(m.u64(m.main + 0x46DCD50)) & 1 == 0:
        raise UnliftedCall("static 0x46dcd58 not built")
    if m.u8(b + 0x6F) == 0 and _holds_static(m, m.u64(b + 0x48)):
        _need_form_change(m, m.u64(m.u64(b + 0x48) + 0x48), m.u16(b + 0x712))
    m.call_void(m.main + 0x2D3DC58, b)
    pp = m.u64(b + 0x48)
    if not _holds_static(m, pp):
        return 0
    if m.u8(b + 0x6F):
        m.put(b + 0x718, 2, m.call(m.main + 0xBF41A8, m.u64(m.u64(pp + 0x48) + 0x70)))
    else:
        form = m.u16(b + 0x712)
        m.put(b + 0x718, 2, form)
        m.call_void(m.main + 0x133B218, m.u64(pp + 0x48), form, 0)
    hp = m.vcall(b, 0x108) & 0xFFFFFFFF
    cur = m.vcall(b, 0x110) & 0xFFFFFFFF
    v = m.vcall(m.u64(b + 0x48), 0x70, 0) & 0xFFFF
    top = ((v * m.u16(b + 0x3F4)) & 0xFFFFFFFF) // 10
    m.put(b + 0x58, 2, top)
    if cur & 0xFFFF < top & 0xFFFF:
        m.vcall_void(b, 0x2E8, (top - cur) & 0xFFFFFFFF)
    if cur & 0xFFFF > top & 0xFFFF and hp & 0xFFFF > top & 0xFFFF:
        m.vcall_void(b, 0x2E0, (hp - top) & 0xFFFFFFFF)
    fn = m.u64(m.u64(b) + 0x810)
    return _tail(m, fn, b, fn)


# Record accessors in the layout of pokemon._GETTERS / _SETTERS.
for _a, *_spec in ((0xC1EB6C, 3, 0x2E, 1, 0, 0x4742380, False), (0xD8FAE8, 0, 0x1E, 1, 0, 0x4742290, False),
                   (0xD904B4, 0, 0x22, 1, 0, 0x4742290, False)):
    lifted(_a)(_pk._getter(*_spec))
for _a, *_spec in ((0xE16488, "party", 2, 2, 0, 0x47423D0, True), (0xE15AEC, "party", 8, 2, 0, 0x47423D0, True),
                   (0xE15150, "party", 0, 1, 0, 0x47423D0, True)):
    lifted(_a)(_pk._setter(*_spec))


def _encrypt(m, acc):
    core = m.u64(acc + 0x10)
    if core:
        m.put(core + 6, 2, _pk._checksum(m, core))
        _pk._xor_words(m, core + _pk.BLOCKS, (_pk.CORE - _pk.BLOCKS) // 2, m.u32(core))
    party = m.u64(acc + 8)
    if party and m.u64(acc + 0x10):
        _pk._xor_words(m, party, 8, m.u32(m.u64(acc + 0x10)))
    m.put(acc + 0x18, 1, 1)


def _decrypt(m, acc):
    _pk._crypt(m, acc)
    m.put(acc + 0x18, 1, 0)
    core = m.u64(acc + 0x10)
    if m.u16(core + 6) != _pk._checksum(m, core):
        m.put(core + 4, 2, m.u16(core + 4) | 4)


@lifted(0xFCA6E8)
def unlocked_block1_3d(m, acc, *_):
    """Byte 0x3d of block B, decrypting and re-encrypting the record without taking its lock."""
    if m.u8(acc + 0x18):
        _decrypt(m, acc)
    core = m.u64(acc + 0x10)
    v = m.u8(_pk._target(m, acc, core, 1, 0x47422E0) + 0x3D)
    if m.u8(acc + 0x18) == 0 and m.u8(acc + 0x19) == 0:
        _encrypt(m, acc)
    return v


@lifted(0xE32A60)
def copy_encrypted(m, acc, core_out, party_out, *_):
    """Copy the encrypted core record (0x148 bytes) and party record (16) out, encrypting a record kept
    plain (+0x19) for the copy and restoring it after."""
    plain = m.u8(acc + 0x19)
    if plain:
        m.put(acc + 0x19, 1, 0)
        if m.u8(acc + 0x18) == 0:
            _encrypt(m, acc)
    if core_out:
        m.write(core_out, m.read(m.u64(acc + 0x10), _pk.CORE))
    if party_out:
        m.write(party_out, m.read(m.u64(acc + 8), 16))
    if plain:
        if m.u8(acc + 0x18):
            _decrypt(m, acc)
        m.put(acc + 0x19, 1, 1)
    return core_out if core_out else acc


def _peek_block_u16(m, acc, logical, off):
    """The u16 at `off` of logical block `logical` as an accessor would read it, without touching the
    record (decrypted on a copy)."""
    core = m.u64(acc + 0x10)
    data = bytearray(m.read(core, _pk.CORE))
    if m.u8(acc + 0x18):
        seed = int.from_bytes(data[0:4], "little")
        for i in range(_pk.BLOCKS, _pk.CORE, 2):
            seed = _pk._lcg(seed)
            v = (data[i] | data[i + 1] << 8) ^ (seed >> 16)
            data[i], data[i + 1] = v & 0xFF, v >> 8
        total = sum(data[i] | data[i + 1] << 8 for i in range(_pk.BLOCKS, _pk.CORE, 2)) & 0xFFFF
        if total != (data[6] | data[7] << 8):
            data[4] |= 4
    if data[4] >> 2 & 1:
        return m.u16(m.main + _pk.BAD_READ_CORE + _pk.BLOCKS + 0x50 * logical + off)
    pos = _pk.BLOCK_POSITION[(int.from_bytes(data[0:4], "little") >> 13) & 0x1F][logical]
    at = _pk.BLOCKS + 0x50 * pos + off
    return data[at] | data[at + 1] << 8


@lifted(0x133B218)
def change_form(m, pp, form, ctx, *_):
    """Give the Pokemon form `form` unless it has it: 0x133ba0c, the form (0xdf289c), the ability for
    (species, form, 0xd99784) (0x133b78c, 0xdf2550), 0x133b4b4 of the gender (0xdf644c), then the stats
    (0xe13b9c(pp, 1))."""
    _need(m, m.main + 0xBF41A8)
    if _peek_block_u16(m, m.u64(pp + 0x70), 0, 0x1C) != form & 0xFFFF:
        for a in (0x133BA0C, 0xDF289C, 0xD99784, 0x133B78C, 0xDF2550, 0xBEC030, 0x133B4B4, 0xDF644C, 0xE13B9C):
            _need(m, m.main + a)
    acc = m.u64(pp + 0x70)
    species = m.call(m.main + 0xBF44F4, acc) & 0xFFFFFFFF
    if m.call(m.main + 0xBF41A8, m.u64(pp + 0x70)) & 0xFFFF == form & 0xFFFF:
        return
    form &= 0xFFFFFFFF
    m.call_void(m.main + 0x133BA0C, pp, form, ctx)
    m.call_void(m.main + 0xDF289C, m.u64(pp + 0x70), form)
    g = m.call(m.main + 0xD99784, pp)
    a = m.call(m.main + 0x133B78C, species, form, g & 0xFFFFFFFF)
    m.call_void(m.main + 0xDF2550, m.u64(pp + 0x70), a & 0xFFFFFFFF)
    g = m.call(m.main + 0xBEC030, m.u64(pp + 0x70))
    a = m.call(m.main + 0x133B4B4, species, form, g & 0xFFFFFFFF)
    m.call_void(m.main + 0xDF644C, m.u64(pp + 0x70), a & 0xFFFFFFFF)
    return _tail(m, m.main + 0xE13B9C, pp, 1)
