"""The server command queue object: u32 length at +0x68, bytes from +0x70 (docs/sv_raid.md, The server
command queue)."""

from pokeldn.sv.battle import queue as codec
from pokeldn.sv.battle.machine import lifted

LENGTH, DATA = 0x68, 0x70


def format_of(command):
    return codec.COMMAND_FORMAT[command] if command < len(codec.COMMAND_FORMAT) else 0


def argument_count(fmt):
    return 10 if fmt in (0x10, 0x20) else fmt & 0xF


@lifted(0x119BF58)
def write(m, que, command, fmt, args_ptr, *_):
    """Append one command whose u32 arguments sit at `args_ptr`."""
    fmt &= 0xFF
    args = [m.u32(args_ptr + 4 * k) for k in range(len(codec.FORMATS[fmt]))]
    append(m, que, command, fmt, args)


def append(m, que, command, fmt, args):
    widths = codec.FORMATS[fmt]
    acc = nbits = 0
    for w, v in zip(widths, args):
        acc = acc << w | (v & ((1 << w) - 1)); nbits += w
    body = (command & 0xFFFF).to_bytes(2, "big") + acc.to_bytes((nbits + 7) // 8, "big")
    n = m.u32(que + LENGTH)
    m.write(que + DATA + n, body)
    m.put(que + LENGTH, 4, n + len(body))


@lifted(0x119AFF0)
def push(m, que, command, *varargs):
    """The variadic push: the id's format from the queue's map, then that many u32 arguments."""
    command &= 0xFFFF
    fmt = format_of(command)
    args = [v & 0xFFFFFFFF for v in varargs[:argument_count(fmt)]]
    args += [0] * (len(codec.FORMATS[fmt]) - len(args))
    append(m, que, command, fmt, args)


@lifted(0x10AFCB8)
def reserve_group(m, que, placeholder, group, size, *_):
    """Reserve a group at the queue's end and return where it starts. With no size, the room is a
    zero-argument `placeholder` command; its first three bytes become the group id and length."""
    start = m.u32(que + LENGTH)
    size &= 0xFFFFFFFF
    if size & 0xFF:
        size = (size + 3) & 0xFFFFFFFF
    else:
        fmt = format_of(placeholder & 0xFFFF)
        append(m, que, placeholder, fmt, [0] * len(codec.FORMATS[fmt]))
        size = (m.u32(que + LENGTH) - start) & 0xFFFFFFFF
    at = start & 0xFFFF
    m.put(que + DATA + at, 1, (group >> 8) & 0xFF)
    m.put(que + DATA + ((at + 1) & 0xFFFFFFFF), 1, group & 0xFF)
    m.put(que + DATA + ((at + 2) & 0xFFFFFFFF), 1, (size - 3) & 0xFF)
    m.put(que + LENGTH, 4, at + (size & 0xFF))
    return start


@lifted(0x1579624)
def write_at(m, que, pos, command, *varargs):
    """Write one command at an earlier reserved position `pos` (0xffff: nowhere), leaving the queue's
    length as it was; group 0xcf is never written this way."""
    command &= 0xFFFF; pos &= 0xFFFF
    fmt = format_of(command)
    args = [v & 0xFFFFFFFF for v in varargs[:argument_count(fmt)]]
    args += [0] * (len(codec.FORMATS[fmt]) - len(args))
    if pos == 0xFFFF:
        return
    m.put(que + 0x6C, 4, m.u16(que + 0x6C))
    if command != 0xCF:
        saved = m.u16(que + LENGTH)
        m.put(que + LENGTH, 4, pos)
        append(m, que, command, fmt, args)
        m.put(que + LENGTH, 4, saved)


CURSOR = 0x6C


@lifted(0x13048D0)
def read_args(m, que, fmt, out, *_):
    """Decode one command's arguments of format `fmt` at the read cursor into the u32 array `out`."""
    fmt &= 0xFF
    widths = codec.FORMATS.get(fmt)
    if widths is None:
        return
    nbytes = (sum(widths) + 7) // 8
    at = m.u32(que + CURSOR)
    acc, shift = int.from_bytes(m.read(que + DATA + at, nbytes), "big"), sum(widths)
    for i, w in enumerate(widths):
        shift -= w
        m.put(out + 4 * i, 4, acc >> shift & ((1 << w) - 1))
    m.put(que + CURSOR, 4, at + nbytes)


@lifted(0xE515EC)
def read_command(m, que, out, room, where, *_):
    """The next command at the read cursor (groups 0xcf and 0xd2 are skipped), its arguments into `out`;
    0xce at the end. `where` receives the command's position."""
    at = m.u32(que + CURSOR)
    if m.u32(que + LENGTH) <= at:
        return 0xCE
    while True:
        command = m.u8(que + DATA + at) << 8 | m.u8(que + DATA + ((at + 1) & 0xFFFFFFFF))
        m.put(que + CURSOR, 4, at + 2)
        if command not in codec.GROUPS:
            break
        at = (at + m.u8(que + DATA + ((at + 2) & 0xFFFFFFFF)) + 3) & 0xFFFFFFFF
        m.put(que + CURSOR, 4, at)
        if m.u32(que + LENGTH) <= at:
            return 0xCE
    if where:
        m.put(where, 4, at)
    if command == 0xCE or command == 0xD4:
        return command
    if command == 0xD0:
        c = m.u32(que + CURSOR); m.put(que + CURSOR, 4, c + 1)
        n = m.u8(que + DATA + c)
        if n < (room - 1) & 0xFFFFFFFF:
            m.put(out, 4, n)
            for i in range(n):
                c = m.u32(que + CURSOR); m.put(que + CURSOR, 4, c + 1)
                m.put(out + 4 + 4 * i, 4, m.u8(que + DATA + c))
        return 0xD0
    if command == 0xD1:
        m.put(que + CURSOR, 4, m.u32(que + CURSOR) + 2)
        return 0xD1
    if command == 0xD3:
        c = m.u32(que + CURSOR); m.put(que + CURSOR, 4, c + 1)
        m.put(out, 4, m.u8(que + DATA + c))
        return 0xD3
    read_args(m, que, format_of(command), out)
    return command
