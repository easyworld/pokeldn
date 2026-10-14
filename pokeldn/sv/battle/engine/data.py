"""The game data the server reads at run time: tables held in function-local statics. The engine reads
them where the state holds them; its own copies of the tables fill that memory."""

from pokeldn.sv.battle.engine import flatbuffer as fb
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
