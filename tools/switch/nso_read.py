#!/usr/bin/env python3
"""Decompress a Switch NSO (exefs module) into its three segments, laid out at their memory offsets.

No lz4 dependency: NSO segments use the LZ4 block format. Usage: nso_read.py <nso> <out.bin>
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pokeldn.switch.nso import SEGMENTS, lz4_block, segments  # noqa: E402,F401


def read_nso(path):
    d = open(path, "rb").read()
    segs = segments(d)
    flags = struct.unpack_from("<I", d, 0x0C)[0]
    for idx, (name, _h, _c) in enumerate(SEGMENTS):
        moff, seg = segs[name]
        print(f"  {name:7s} mem=0x{moff:08x} size=0x{len(seg):x} {'lz4' if (flags >> idx) & 1 else 'raw'}")
    return segs


def main():
    segs = read_nso(sys.argv[1])
    end = max(m + len(s) for m, s in segs.values())
    img = bytearray(end)
    for m, s in segs.values():
        img[m:m + len(s)] = s
    open(sys.argv[2], "wb").write(img)
    print(f"wrote {sys.argv[2]}, 0x{end:x} bytes (segments at their memory offsets)")


if __name__ == "__main__":
    main()
