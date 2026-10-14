"""Reading the flatbuffer tables the server keeps its scripted data in: a table starts with an s32
back to its vtable (u16 size, u16 table size, then one u16 offset per field; 0 means absent)."""


def field(m, table, index):
    """Offset of field `index` inside `table`, 0 when absent."""
    vt = table - m.s(table, 4)
    if m.u16(vt) < 4 + 2 * index + 1:
        return 0
    return m.u16(vt + 4 + 2 * index)


def u32(m, table, index, default=0):
    off = field(m, table, index)
    return m.u32(table + off) if off else default


def s32(m, table, index, default=0):
    off = field(m, table, index)
    return m.s(table + off, 4) if off else default


def u8(m, table, index, default=0):
    off = field(m, table, index)
    return m.u8(table + off) if off else default


def vector(m, table, index):
    """(count, address of the first element) of a vector field; (0, 0) when absent."""
    off = field(m, table, index)
    if not off:
        return 0, 0
    v = table + off + m.u32(table + off)
    return m.u32(v), v + 4


def element_table(m, first, i):
    """Table i of a vector of tables."""
    slot = first + 4 * i
    return slot + m.u32(slot)
