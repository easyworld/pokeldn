"""The game data the server reads at run time: tables held in function-local statics. The engine reads
them where the state holds them; its own copies of the tables fill that memory."""

from pokeldn.sv.battle.engine import flatbuffer as fb
from pokeldn.sv.battle.engine.calls import M32, _tail
from pokeldn.sv.battle.engine.containers import data_record
from pokeldn.sv.battle.machine import UnliftedCall, lifted


def static_table(m, guard, slot, last):
    """The table a function-local static holds (built on first use), also noted in a second static."""
    if m.u8(m.u64(m.main + guard)) & 1 == 0:
        raise UnliftedCall(f"static 0x{slot:x} not built")
    table = m.u64(m.u64(m.main + slot))
    m.put(m.u64(m.main + last), 8, table)
    return table


@lifted(0xFECCD8)
def move_flag_6(m, key_holder, *_):
    """Field 6 of the record for the u16 id at key_holder+8, as a bool."""
    table = static_table(m, 0x46DDAA8, 0x46DDAB0, 0x46DDAB8)
    return int(fb.u8(m, data_record(m, table, m.u16(key_holder + 8)), 6) != 0)


@lifted(0x201423C)
def id_of_hash(m, owner, key, *_):
    """The u16 id a 64-bit name hash stands for (282 entries of 0x18 bytes from +0x30); 0 if unknown."""
    table = static_table(m, 0x46D8900, 0x46D8908, 0x46D8910)
    for i in range(0x11A):
        if m.u64(table + 0x30 + 0x18 * i) == key:
            return m.u16(table + 0x38 + 0x18 * i)
    return 0


@lifted(0xBF5FE0)
def boosted_field_7(m, ident, level, *_):
    """Field 7 (u8) of record `ident` raised by 20% per level, levels above 2 counting as 3."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    rec = m.call(m.main + 0xBF60CC, table, ident & 0xFFFFFFFF)
    v = fb.u8(m, rec, 7)
    level &= 0xFFFFFFFF
    if level & 0xFF >= 3:
        level = 3
    f = (level * 5 & 0x3F) << 2
    return (v + ((v * f) & 0xFFFFFFFF) // 100) & 0xFFFFFFFF


def _record_field11(at, size):
    """Bytes at `at` of the inline struct in field 11 of the data record for the u16 id at o+8."""
    def fn(m, o, *_):
        from pokeldn.sv.battle.engine.containers import data_record
        table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
        rec = data_record(m, table, m.u16(o + 8))
        off = m.u16(rec - m.s(rec, 4) + 0x1A)   # read without the vtable size check, as the game does
        return m.u(rec + off + at, size)
    return fn


for _addr, _at, _size in ((0x179412C, 0, 2), (0x17942D0, 2, 1), (0x17947C8, 5, 1)):
    lifted(_addr)(_record_field11(_at, _size))


@lifted(0x1380E28)
def field18_count(m, ident, *_):
    """How many of the three bytes in field 18 of the data record for `ident` are set (0x1380ea4)."""
    with m.frame(0x10) as key:
        m.put(key, 8, m.u64(m.main + 0x46DDAD8) + 0x10); m.put(key + 8, 2, ident)
        return sum(int(m.call(m.main + 0x1380EA4, key, i) & 0xFF != 0) for i in range(3))


@lifted(0x1793E2C)
def record_field11_u16(m, ident, *_):
    """0x179412c on a stack key (vtable [0x46ddad8] + 0x10, u16 id at +8); the game returns its w0."""
    with m.frame(0x10) as key:
        m.put(key, 8, m.u64(m.main + 0x46DDAD8) + 0x10); m.put(key + 8, 2, ident)
        return m.call(m.main + 0x179412C, key)


@lifted(0x20FEAE8)
def record_flag_56(m, o, *_):
    """Field 56 of the data record for the u16 id at o+8, as a bool."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.containers import data_record
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    return int(fb.u8(m, data_record(m, table, m.u16(o + 8)), 56) != 0)


@lifted(0x17710A4)
def field18_entry(m, ident, i, out, *_):
    """For i below 3: *out = the s8 0x1771130 gives for byte i of field 18 of record `ident` when that
    byte (0x1380ea4) is set, else 0; returns 0x1380ea4's result (0 for i >= 3)."""
    i &= 0xFFFFFFFF
    if i >= 3:
        m.put(out, 4, 0)
        return 0
    with m.frame(0x10) as key:
        m.put(key, 8, m.u64(m.main + 0x46DDAD8) + 0x10); m.put(key + 8, 2, ident)
        r = m.call(m.main + 0x1380EA4, key, i) & 0xFFFFFFFF
        v = 0
        if r & 0xFF:
            v = m.call(m.main + 0x1771130, key, i) & 0xFF
            v = v - 0x100 if v & 0x80 else v
        m.put(out, 4, v)
        return r


@lifted(0xB860E0)
def record_field10_by_pair(m, o, *_):
    """Field 10 (u8) of the record keyed u16 +8 * 10000 + u16 +0xa in the table static 0x46d7438."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.containers import find
    table = static_table(m, 0x46D7430, 0x46D7438, 0x46D7440)
    key = m.u16(o + 8) * 10000 + m.u16(o + 0xA)
    node = find(m, table + 0x68, key, 8)
    rec = m.u64(node + 0x18) if node else m.u64(table + 0xD0)
    return fb.u8(m, rec, 10)


@lifted(0x287A7D4)
def boosted_field_7_of(m, o, level, *_):
    """Tail call of 0xbf5fe0 with the record id 0xdedbc8 and the level 0xbf61d4 give for [[o+0x48]+0x70]."""
    p = m.u64(m.u64(o + 0x48) + 0x70)
    ident = m.call(m.main + 0xDEDBC8, p, level) & 0xFFFFFFFF   # x1 still holds level
    lv = m.call(m.main + 0xBF61D4, m.u64(m.u64(o + 0x48) + 0x70), level & 0xFFFFFFFF) & 0xFFFFFFFF
    return m.call(m.main + 0xBF5FE0, ident, lv)


def _pair_record(m, o):
    """The record keyed u16 +8 * 10000 + u16 +0xa in the table static 0x46d7438, else its default."""
    from pokeldn.sv.battle.engine.containers import find
    table = static_table(m, 0x46D7430, 0x46D7438, 0x46D7440)
    node = find(m, table + 0x68, m.u16(o + 8) * 10000 + m.u16(o + 0xA), 8)
    return m.u64(node + 0x18) if node else m.u64(table + 0xD0)


@lifted(0x1046124)
def record_field6_by_pair(m, o, *_):
    from pokeldn.sv.battle.engine import flatbuffer as fb
    return fb.u8(m, _pair_record(m, o), 6)


def _pair_struct22(at):
    """Byte `at` of the inline struct in field 22 of the pair-keyed record (no vtable size check)."""
    def fn(m, o, *_):
        rec = _pair_record(m, o)
        return m.u8(rec + m.u16(rec - m.s(rec, 4) + 0x30) + at)
    return fn


for _addr, _at in ((0xCEDBF4, 0), (0xCEDF60, 2), (0xCEE488, 4)):
    lifted(_addr)(_pair_struct22(_at))


@lifted(0x1380EA4)
def record_field18_byte(m, o, i, *_):
    """Byte i of the 3-byte entry in field 18 of the data record for the u16 id at o+8; 0 when i > 2."""
    i &= 0xFF
    if i > 2:
        return 0
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    rec = data_record(m, table, m.u16(o + 8))
    off = m.u16(rec - m.s(rec, 4) + 0x28)   # read without the vtable size check, as the game does
    return m.u8(rec + off + 3 * i)


@lifted(0xF74860)
def data_record_f74860(m, table, key, *_):
    return data_record(m, table, key)


@lifted(0x1382AE8)
def record_flag_34(m, o, *_):
    """Field 34 of the data record for the u16 id at o+8, as a bool."""
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    return int(fb.u8(m, data_record(m, table, m.u16(o + 8)), 34) != 0)


@lifted(0x20FB1E0)
def record_field16_pos(m, o, *_):
    """Field 16 (s8) of the data record for the u16 id at o+8, negatives as 0."""
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    rec = data_record(m, table, m.u16(o + 8))
    off = fb.field(m, rec, 16)
    return max(m.s(rec + off, 1), 0) if off else 0


@lifted(0x114D360)
def check_114da8c(m, o, a, *_):
    return m.call(m.main + 0x114DA8C, m.call(m.main + 0x11440E8, m.u64(o + 0x10)), a) & 1


@lifted(0x1794478)
def record_field11_byte3(m, o, *_):
    """Byte 3 of field 11 of the data record for the u16 id at o+8 (read without the vtable size check)."""
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    rec = data_record(m, table, m.u16(o + 8))
    return m.u8(rec + m.u16(rec - m.s(rec, 4) + 0x1A) + 3)


@lifted(0x1793E60)
def run_17942d0_with(m, v, *rest):
    """0x17942d0's result for a stack object (vtable [0x46ddad8] + 0x10, u16 v at +8)."""
    with m.frame(0x10) as f:
        m.put(f, 8, m.u64(m.main + 0x46DDAD8) + 0x10)
        m.put(f + 8, 2, v)
        return m.call(m.main + 0x17942D0, f, *rest[:6])


def _personal(m, key_holder):
    """The personal record for (u16 +8) * 10000 + (u16 +0xa) from the static map (0x46d7438 guard
    0x46d7430, last 0x46d7440): node value +0x18, or the default at +0xd0."""
    from pokeldn.sv.battle.engine.containers import find
    table = static_table(m, 0x46D7430, 0x46D7438, 0x46D7440)
    key = m.u16(key_holder + 8) * 10000 + m.u16(key_holder + 0xA)
    node = find(m, table + 0x68, key, 8)
    return m.u64(node + 0x18) if node else m.u64(table + 0xD0)


def _personal_byte(k):
    """Byte k of the struct at vtable slot +0x30 (no presence check)."""
    def fn(m, key_holder, *_):
        t = _personal(m, key_holder)
        return m.u8(t + m.u16(t - m.s(t, 4) + 0x30) + k)
    return fn


for _a, _k in ((0xCEDDA8, 1), (0xCEE2D0, 3)):
    lifted(_a)(_personal_byte(_k))


@lifted(0x1012D44)
def personal_field_5(m, key_holder, *_):
    return fb.u8(m, _personal(m, key_holder), 5)


@lifted(0x13B1F10)
def move_field_6(m, key_holder, *_):
    """Field 6 (a byte) of the record for the u16 id at key_holder+8; 0x65 reads as 0x64."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    from pokeldn.sv.battle.engine.containers import data_record
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    v = fb.u8(m, data_record(m, table, m.u16(key_holder + 8)), 6)
    return 0x64 if v == 0x65 else v


def _keyed(m, address, key):
    """Call `address` with a stack object (vtable [0x46ddad8]+0x10, u16 key at +8)."""
    with m.frame(0x10) as p:
        m.put(p, 8, m.u64(m.main + 0x46DDAD8) + 0x10)
        m.put(p + 8, 2, key)
        return m.call(m.main + address, p)


@lifted(0x1382AB0)
def keyed_flag(m, key, *_): return _keyed(m, 0x1382AE8, key) & 1


@lifted(0x20FB1A8)
def keyed_byte(m, key, *_):
    return (((_keyed(m, 0x20FB1E0, key) & 0xFF) ^ 0x80) - 0x80) & 0xFFFFFFFF


def _negative_field(index):
    """The record's signed byte field `index`, negated when below zero, else 0."""
    def fn(m, key_holder, *_):
        from pokeldn.sv.battle.engine import flatbuffer as fb
        from pokeldn.sv.battle.engine.containers import data_record
        table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
        v = fb.u8(m, data_record(m, table, m.u16(key_holder + 8)), index)
        return (0x100 - v) if v & 0x80 else 0
    return fn


lifted(0x1419734)(_negative_field(15))
lifted(0x141A340)(_negative_field(16))


@lifted(0x1794620)
def record_byte_11(m, key_holder, *_):
    """The byte 4 past field 11 of the record for the u16 id at key_holder+8; the field is read without
    a vtable size check."""
    from pokeldn.sv.battle.engine.containers import data_record
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    rec = data_record(m, table, m.u16(key_holder + 8))
    return m.u8(rec + m.u16(rec - m.s(rec, 4) + 0x1A) + 4)


def _triple_byte(k):
    """Byte k of the i-th (0..2) three-byte entry at field 18 of the record for the u16 id at
    key_holder+8; the field is read without a vtable size check."""
    def fn(m, key_holder, i, *_):
        from pokeldn.sv.battle.engine.containers import data_record
        i &= 0xFF
        if i > 2:
            return 0
        table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
        rec = data_record(m, table, m.u16(key_holder + 8))
        return m.u8(rec + m.u16(rec - m.s(rec, 4) + 0x28) + 3 * i + k)
    return fn


lifted(0x1771130)(_triple_byte(1))
lifted(0x1384070)(_triple_byte(2))


@lifted(0x1793E94)
def packed_move_info(m, key, *_):
    """Bits 0..3: 0x1794478 of the record for u16 `key`; when it is non-zero, bits 4..9 0x1794620 and
    bits 10..15 0x17947c8."""
    with m.frame(0x10) as p:
        m.put(p, 8, m.u64(m.main + 0x46DDAD8) + 0x10)
        m.put(p + 8, 2, key)
        r = m.call(m.main + 0x1794478, p)
        v = r & 0xF
        if r & 0xFF:
            a = m.call(m.main + 0x1794620, p)
            c = m.call(m.main + 0x17947C8, p)
            v = v | (a & 0x3F) << 4 | (c & 0x3FFFFF) << 10
        return v & 0xFFFF


@lifted(0x1384028)
def keyed_triple_byte_2(m, key, i, *_):
    if i & 0xFFFFFFFF > 2:
        return 0
    with m.frame(0x10) as p:
        m.put(p, 8, m.u64(m.main + 0x46DDAD8) + 0x10)
        m.put(p + 8, 2, key)
        return m.call(m.main + 0x1384070, p, i) & 0xFF


def _personal_table(m, key_holder):
    """The personal record for (u16 +8) * 10000 + (u16 +0xa) (static map 0x46d7438), else its default."""
    from pokeldn.sv.battle.engine.containers import find
    table = static_table(m, 0x46D7430, 0x46D7438, 0x46D7440)
    key = m.u16(key_holder + 8) * 10000 + m.u16(key_holder + 0xA)
    node = find(m, table + 0x68, key, 8)
    return m.u64(node + 0x18) if node else m.u64(table + 0xD0)


@lifted(0xCEE118)
def personal_byte_5(m, key_holder, *_):
    """Byte 5 of the personal record's struct at field +0x30."""
    t = _personal_table(m, key_holder)
    return m.u8(t + m.u16(t - m.s(t, 4) + 0x30) + 5)


@lifted(0x2014160)
def hash_of_id(m, owner, key, *_):
    """The 64-bit name hash of u16 id `key` (282 entries of 0x18 bytes from +0x30); 0 if unknown."""
    table = static_table(m, 0x46D8900, 0x46D8908, 0x46D8910)
    key &= 0xFFFF
    if key:
        for i in range(0x11A):
            if m.u16(table + 0x38 + 0x18 * i) == key:
                return m.u64(table + 0x30 + 0x18 * i)
    return 0


@lifted(0x20FAD50)
def item_field_3(m, ident, *_):
    """Field 3 (u8) of record `ident` in the table of the static at 0x46d7948."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    return fb.u8(m, m.call(m.main + 0xBF60CC, table, ident & M32), 3)


@lifted(0x20FCBD0)
def item_flag_41(m, key, *_):
    """Field 41 (u8 != 0) of the record for the u16 id at key+8 in the table of the static at 0x46d7948."""
    from pokeldn.sv.battle.engine import flatbuffer as fb
    table = static_table(m, 0x46D7940, 0x46D7948, 0x46D7950)
    return int(fb.u8(m, m.call(m.main + 0xBF60CC, table, m.u16(key + 8)), 41) != 0)


@lifted(0x20FCB98)
def item_flag_41_of(m, ident, *_):
    with m.frame(0x10) as k:
        m.put(k, 8, m.u64(m.main + 0x46DDAD8) + 0x10); m.put(k + 8, 2, ident)
        return m.call(m.main + 0x20FCBD0, k) & 1


@lifted(0x2823E90)
def item_flag_41_tail(m, ident, *_):
    return _tail(m, m.main + 0x20FCB98, ident)
