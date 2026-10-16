#!/usr/bin/env python3
"""Map an NSO's imported symbols to the GOT slots that hold them.

Calls into another module go through GOT slots filled by JUMP_SLOT or GLOB_DAT relocations;
nso_relocs.py reads only the RELATIVE ones.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pokeldn.switch.nso import R_GLOB_DAT, R_JUMP_SLOT, dynamic, imports, mod0  # noqa: E402,F401


if __name__ == "__main__":
    img = open(sys.argv[1], "rb").read()
    want = [a.lower() for a in sys.argv[2:]]
    got = imports(img)
    print(f"{len(got):,} imported symbols", file=sys.stderr)
    for slot, name in sorted(got):
        if not want or any(w in name.lower() for w in want):
            print(f"got 0x{slot:08x}  {name}")
