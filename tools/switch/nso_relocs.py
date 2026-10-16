#!/usr/bin/env python3
"""Resolve an NSO's R_AARCH64_RELATIVE relocations, so vtable slots can be read.

    ./.venv/bin/python tools/switch/nso_relocs.py IMAGE [ADDEND ...]

An NSO's vtable slots are empty in the image and filled from RELATIVE relocations. RELR (DT_RELR,
tag 0x24) carries no addend: the addend is the value stored at the slot. Legends Z-A uses only RELR.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pokeldn.switch.nso import dynamic, mod0, relatives, relr  # noqa: E402,F401

if __name__ == "__main__":
    img = open(sys.argv[1], 'rb').read()
    rels = relatives(img)
    print(f"{len(rels):,} RELATIVE relocations")
    want = {int(a, 0) for a in sys.argv[2:]}
    for slot, add in rels:
        if add in want:
            print(f"  slot 0x{slot:08x} -> 0x{add:08x}")
