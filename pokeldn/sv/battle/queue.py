"""The server command queue of a Scarlet / Violet battle round: the bytes a type-0x15 record carries
from +0x23c (docs/sv_raid.md, The server command queue).

A command is its id as a big-endian u16, then its arguments packed by the id's format as one
big-endian bit stream, padded at the front to whole bytes. The writer is `0x119bf58`; the id to
format map is built from the 208 rows at `0x3c6abe4`, a later row winning. Ids 0xce to 0xd4 are
read by the reader `0xe515f0` itself (jump table `0x3c6a90c`): 0xcf and 0xd2 are groups (a u8 byte
count, then that many bytes of nested commands), 0xd0 is a u8 count and that many bytes (at most 4),
0xd1 two bytes, 0xd3 one byte, 0xd4 nothing.
"""

# format byte -> argument widths in bits, in argument order
FORMATS = {
    0x00: (),
    0x01: (8,),
    0x02: (8, 8),
    0x04: (5, 3, 8, 16),
    0x10: (32, 16, 32, 32, 32, 32, 32, 32, 32, 32),
    0x11: (16,),
    0x12: (8, 16),
    0x14: (5, 3, 5, 3),
    0x17: (16, 16, 16, 16, 16, 16, 16),
    0x1a: (16, 16, 16, 16, 16, 16, 16, 16, 16, 16),
    0x20: (32, 16, 32, 32, 32, 32, 32, 32, 32, 32),
    0x21: (32,),
    0x22: (8, 32),
    0x23: (5, 5, 5),
    0x28: (32, 32, 32, 32, 32, 32, 32, 32),
    0x29: (32, 8, 8, 8, 8, 8, 8, 8, 8),
    0x42: (5, 3),
    0x43: (8, 8, 8),
    0x45: (16, 16, 16, 32, 16),
    0x52: (32, 8),
    0x53: (8, 8, 16),
    0x57: (32, 8, 8, 8, 8, 8, 8),
    0x62: (32, 16),
    0x63: (8, 8, 32),
    0x65: (32, 16, 16, 16, 16),
    0x66: (8, 32, 32, 32, 32, 32),
    0x67: (32, 16, 16, 16, 16, 16, 16),
    0x72: (32, 32),
    0x75: (32, 8, 32, 32, 32),
    0x83: (32, 32, 32),
    0x84: (8, 32, 32, 32),
    0x85: (8, 8, 32, 32, 32),
    0x86: (8, 8, 8, 8, 8, 8),
    0x93: (32, 8, 8),
    0x96: (32, 32, 32, 32, 32, 32),
    0xa3: (32, 8, 16),
    0xa4: (32, 8, 8, 8),
    0xb3: (32, 8, 32),
    0xc3: (32, 32, 16),
    0xc4: (32, 32, 16, 16),
    0xd3: (32, 16, 16),
    0xd4: (32, 32, 16, 8),
}

# command id -> format byte
COMMAND_FORMAT = (
    0x00, 0xd4, 0xd4, 0x62, 0x21, 0x93, 0x93, 0x52, 0x52, 0x52, 0x93, 0x93,
    0x93, 0x93, 0x29, 0x21, 0x21, 0x21, 0x72, 0x75, 0x21, 0x62, 0x04, 0xa3,
    0x62, 0x62, 0xa3, 0x93, 0x62, 0x67, 0x52, 0x52, 0x52, 0x52, 0x52, 0x21,
    0x62, 0x21, 0x62, 0x65, 0x21, 0x21, 0x21, 0x11, 0x11, 0x01, 0x02, 0x02,
    0x84, 0x22, 0x84, 0x52, 0x01, 0x93, 0x63, 0xb3, 0x21, 0x72, 0x72, 0x62,
    0x21, 0x01, 0x01, 0x21, 0x21, 0x72, 0x67, 0x21, 0x01, 0x57, 0x63, 0x02,
    0x63, 0xc3, 0x85, 0x02, 0x02, 0x43, 0x21, 0x52, 0x01, 0x52, 0x52, 0x01,
    0x00, 0x23, 0x72, 0x93, 0xc4, 0x72, 0x83, 0x62, 0x62, 0x21, 0x62, 0x21,
    0x72, 0x21, 0x21, 0x28, 0x02, 0x85, 0x02, 0x02, 0x02, 0x02, 0x01, 0x21,
    0x21, 0xa3, 0x02, 0x01, 0x00, 0x52, 0xc4, 0xa3, 0xa3, 0x22, 0x02, 0x21,
    0x01, 0x45, 0x01, 0x83, 0x00, 0x84, 0x86, 0x21, 0x21, 0x11, 0x53, 0x72,
    0x57, 0x22, 0x62, 0x02, 0xc3, 0xd3, 0xc4, 0x1a, 0x52, 0xa3, 0x53, 0x21,
    0x52, 0x21, 0xa4, 0xa4, 0x52, 0x21, 0x22, 0x12, 0x14, 0x01, 0x72, 0x52,
    0x66, 0x52, 0x23, 0x00, 0x28, 0x00, 0x17, 0x42, 0x53, 0x21, 0x11, 0x12,
    0x53, 0x53, 0x11, 0x12, 0x21, 0x01, 0x01, 0x72, 0xa3, 0x21, 0x01, 0x52,
    0x96, 0x01, 0x02, 0x52, 0x00, 0x52, 0x00, 0x52, 0x01, 0x01, 0x11, 0x93,
    0x52, 0x22, 0x83, 0x72, 0x52, 0x01, 0x02, 0x62, 0x21, 0x65, 0x10, 0x10,
    0x20, 0x20,
)



GROUPS = (0xCF, 0xD2)
RAW = {0xD1: 2, 0xD3: 1, 0xD4: 0}        # special id -> fixed byte count, kept raw
LIST = 0xD0                              # a u8 count, then that many bytes


def encode_group(command, body):
    """A group command around already encoded commands."""
    if command not in GROUPS or len(body) > 0xFF:
        raise ValueError(f"group {command:#x} of {len(body)} bytes")
    return command.to_bytes(2, "big") + bytes([len(body)]) + body


def encode(command, args=()):
    """One command's bytes. Each argument is truncated to its field's width. A special id takes its
    raw bytes as `args`."""
    if command in GROUPS:
        return encode_group(command, bytes(args))
    if command in RAW:
        if len(args) != RAW[command]:
            raise ValueError(f"command {command:#x} takes {RAW[command]} bytes")
        return command.to_bytes(2, "big") + bytes(args)
    if command == LIST:
        if len(args) > 4:
            raise ValueError("command 0xd0 takes at most 4 bytes")
        return command.to_bytes(2, "big") + bytes([len(args)]) + bytes(args)
    widths = FORMATS[COMMAND_FORMAT[command]]
    if len(args) != len(widths):
        raise ValueError(f"command {command} takes {len(widths)} arguments, got {len(args)}")
    acc, nbits = 0, 0
    for w, v in zip(widths, args):
        acc = acc << w | (v & ((1 << w) - 1)); nbits += w
    return command.to_bytes(2, "big") + acc.to_bytes((nbits + 7) // 8, "big")


def decode(queue):
    """[(command, args)] for a whole queue, a group's args being its raw body; raises ValueError on an
    unknown id or a short command."""
    out, i = [], 0
    while i < len(queue):
        if i + 2 > len(queue):
            raise ValueError(f"truncated command id at {i}")
        command = int.from_bytes(queue[i:i + 2], "big")
        if command in GROUPS:
            if i + 3 > len(queue) or i + 3 + queue[i + 2] > len(queue):
                raise ValueError(f"group {command:#x} at {i} runs past the queue")
            n = queue[i + 2]
            out.append((command, bytes(queue[i + 3:i + 3 + n]))); i += 3 + n
            continue
        if command in RAW or command == LIST:
            n = RAW[command] if command in RAW else 1 + (queue[i + 2] if i + 2 < len(queue) else 0)
            if i + 2 + n > len(queue):
                raise ValueError(f"command {command:#x} at {i} runs past the queue")
            body = bytes(queue[i + 2:i + 2 + n])
            out.append((command, body if command in RAW else body[1:])); i += 2 + n
            continue
        if command >= len(COMMAND_FORMAT):
            raise ValueError(f"unknown command {command} at {i}")
        widths = FORMATS[COMMAND_FORMAT[command]]
        n = (sum(widths) + 7) // 8
        if i + 2 + n > len(queue):
            raise ValueError(f"command {command} at {i} runs past the queue")
        acc, shift, args = int.from_bytes(queue[i + 2:i + 2 + n], "big"), sum(widths), []
        for w in widths:
            shift -= w; args.append(acc >> shift & ((1 << w) - 1))
        out.append((command, tuple(args))); i += 2 + n
    return out
