"""The round's per-action commands the server writes into the queue: the target summary rows (0x7e),
the action summary (0x8b), the effect record (0xc9) and the totals (0x9c)."""

from pokeldn.sv.battle.engine.queue import push, write_at
from pokeldn.sv.battle.machine import lifted

# Byte offsets in the summary record of the three target rows' five bytes each (0x15799f0).
_ROW_BYTES = ((0xD, 0x10, 0x13, 0x16, 0x19), (0xE, 0x11, 0x14, 0x17, 0x1A), (0xF, 0x12, 0x15, 0x18, 0x1B))


@lifted(0x1579490)
def queue_length(m, que, *_): return m.u32(que + 0x68)


@lifted(0x15799F0)
def push_target_row(m, que, info, row, *_):
    row &= 0xFF
    if row > 2:
        return
    push(m, que, 0x7E, row, *(m.u8(info + o) for o in _ROW_BYTES[row]))


@lifted(0x1942118)
def push_effect(m, o, a, b, c, d, *_):
    push(m, m.u64(o + 0x18), 0xC9, a, 0, b & 0xFFFF, c & 0xFF, d & 1)


@lifted(0x157FE4C)
def write_totals(m, o, info, pos, *_):
    write_at(m, m.u64(o + 0x18), pos, 0x9C, *(m.u32(info + 0x30 + 4 * i) for i in range(6)))


@lifted(0x1579498)
def write_summary(m, o, base, info, slots, *_):
    """The action's summary: totals (0x9c) when any, the three target rows (0x7e) and the line 0x8b, into
    the positions reserved in `slots` (u16 at +2.. ; 0xffff at +2 means append instead)."""
    que = m.u64(o + 0x18)
    if m.u32(info + 0x30) != 0:
        write_totals(m, o, info, m.u16(slots))
    move = m.u16(info) or m.u16(base)
    args = (m.u8(info + 2), m.u8(info + 3), move, m.u8(base + 8), m.u8(info + 4), m.u8(info + 6),
            m.u8(info + 0xC), m.u8(info + 7), m.u8(base + 0xA), m.u8(info + 5))
    if m.u16(slots + 2) != 0xFFFF:
        for row in range(3):
            write_at(m, que, m.u16(slots + 4 + 2 * row), 0x7E, row,
                     *(m.u8(info + o) for o in _ROW_BYTES[row]))
        write_at(m, que, m.u16(slots + 2), 0x8B, *args)
        return
    for row in range(3):
        push_target_row(m, que, info, row)
    push(m, que, 0x8B, *args)


@lifted(0x1941FB4)
def close_effect(m, o, rec, info, *_):
    """Close an effect record: note where the queue stands, find whether the queue holds a command in
    0x88..0xcd between the record's start and info's end (the read cursor is restored), then write
    0xc9 at the reserved position or append it."""
    from pokeldn.sv.battle.engine.queue import read_command
    que = m.u64(o + 8)
    pos = m.u16(rec + 2)
    if pos == 0xFFFF:
        pos = queue_length(m, que) & 0xFFFF
    m.put(rec + 4, 2, pos)
    if m.u8(rec + 0xD):
        found = 1
    else:
        found = 0
        end = m.u16(info + 0xA)
        if pos != 0xFFFF and end != 0xFFFF:
            saved = m.u32(que + 0x6C)
            m.put(que + 0x6C, 4, pos)
            at = pos
            with m.frame(0x50) as out:
                while not (end <= at and at != m.u32(que + 0x68)):
                    m.put(out + 0x40, 4, 0xFFFFFFFF)
                    command = read_command(m, que, out, 0x10, out + 0x40)
                    where = m.u32(out + 0x40)
                    if (command - 0x88) & 0xFFFF < 0x46 and pos <= where < end:
                        found = 1
                        break
                    at = m.u32(que + 0x6C)
            m.put(que + 0x6C, 4, saved)
    if m.s(rec + 2, 2) == -1:
        push_effect(m, m.u64(o + 0x10), m.u32(rec + 8), m.u16(rec + 6), m.u8(rec + 0xC), found)
    else:
        write_at(m, m.u64(m.u64(o + 0x10) + 0x18), m.u16(rec + 2), 0xC9, m.u32(rec + 8), 0,
                 m.u16(rec + 6), m.u8(rec + 0xC), found)
    m.put(rec, 1, 1)
