"""A Trinity packed file system (Scarlet and Violet): `arc/data.trpfd` names the files (FNV-1a 64
path hashes) and the packs; `arc/data.trpfs` holds the packs. An entry of compression type 3 is Oodle,
decompressed by the title's own OodleLZ_Decompress from its main image under unicorn, at the address
the caller passes. docs/za.md "The personal table".
"""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pokeldn.switch import nso  # noqa: E402

FNV_BASIS = 0xCBF29CE484222645
FNV_PRIME = 0x100000001B3
OODLE = 3


def fnv1a64(text):
    h = FNV_BASIS
    for c in text.encode() if isinstance(text, str) else text:
        h = ((h ^ c) * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return h


class Fb:
    """Just enough FlatBuffers to walk an untyped buffer."""

    def __init__(self, buf):
        self.b = buf

    def u32(self, at):
        return struct.unpack_from("<I", self.b, at)[0]

    def u64(self, at):
        return struct.unpack_from("<Q", self.b, at)[0]

    def root(self):
        return self.u32(0)

    def field(self, table, i):
        """Absolute position of field i of the table at `table`, or 0 when absent."""
        vt = table - struct.unpack_from("<i", self.b, table)[0]
        vsize = struct.unpack_from("<H", self.b, vt)[0]
        if 4 + 2 * i >= vsize:
            return 0
        off = struct.unpack_from("<H", self.b, vt + 4 + 2 * i)[0]
        return table + off if off else 0

    def vec(self, table, i):
        """-> (data start, count) of the vector in field i."""
        at = self.field(table, i)
        if not at:
            return 0, 0
        v = at + self.u32(at)
        return v + 4, self.u32(v)

    def u64s(self, table, i):
        start, n = self.vec(table, i)
        return struct.unpack_from(f"<{n}Q", self.b, start) if n else ()

    def tables(self, table, i):
        start, n = self.vec(table, i)
        return [start + 4 * k + self.u32(start + 4 * k) for k in range(n)]

    def string(self, at):
        v = at + self.u32(at)
        return self.b[v + 4:v + 4 + self.u32(v)].decode()


class Oodle:
    """OodleLZ_Decompress from a title's main image, under unicorn; only PLT imports are hooked."""

    BUF = 0x60000000

    def __init__(self, image, entry):
        from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
        img = nso.load(image)
        self.entry = entry
        self.uc = uc = Uc(UC_ARCH_ARM64, UC_MODE_LITTLE_ENDIAN)
        uc.ctl_set_tcg_buffer_size(64 << 20)
        uc.mem_map(0, (len(img) + 0xFFFFF) & ~0xFFFFF)
        uc.mem_write(0, bytes(img))
        self.stubs = nso.plt_stubs(img, dict(nso.imports(bytes(img))))
        self.cap = 0
        if self.stubs:
            uc.hook_add(UC_HOOK_CODE, self._stub, begin=min(self.stubs), end=max(self.stubs) + 16)

    def _stub(self, uc, addr, _size, _):
        from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, \
            UC_ARM64_REG_LR, UC_ARM64_REG_PC
        name = self.stubs.get(addr)
        if name is None:
            return
        x0, x1, x2 = (uc.reg_read(r) for r in (UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2))
        if name in ("memcpy", "memmove"):
            uc.mem_write(x0, bytes(uc.mem_read(x1, x2)))
        elif name == "memset":
            uc.mem_write(x0, bytes([x1 & 0xFF]) * x2)
        else:
            raise RuntimeError(f"OodleLZ_Decompress called import {name}")
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_LR))

    def _room(self, need):
        if need > self.cap:
            if self.cap:
                self.uc.mem_unmap(self.BUF, self.cap)
            self.cap = (need + 0xFFFFF) & ~0xFFFFF
            self.uc.mem_map(self.BUF, self.cap)

    def decompress(self, comp, rawlen):
        """The game's call (0x27ad6b0): fuzz-safe 1, no CRC, no window, 0x80000 bytes of decoder
        memory, thread phase 3."""
        from unicorn.arm64_const import UC_ARM64_REG_SP, UC_ARM64_REG_LR, UC_ARM64_REG_X0
        clen = (len(comp) + 0xFFF) & ~0xFFF
        rlen = (rawlen + 0xFFF) & ~0xFFF
        mem_size, stack = 0x80000, 0x100000
        self._room(clen + rlen + mem_size + stack + 0x1000)
        cin, raw = self.BUF, self.BUF + clen
        mem = raw + rlen
        sp = mem + mem_size + stack - 0x100
        ret = sp + 0x80
        uc = self.uc
        uc.mem_write(cin, bytes(comp))
        uc.mem_write(sp, struct.pack("<6Q", 0, 0, 0, mem, mem_size, 3))
        uc.mem_write(ret, b"\x00\x00\x20\xd4")              # brk: never reached, emu stops first
        uc.reg_write(UC_ARM64_REG_SP, sp)
        uc.reg_write(UC_ARM64_REG_LR, ret)
        for i, v in enumerate((cin, len(comp), raw, rawlen, 1, 0, 0, 0)):
            uc.reg_write(UC_ARM64_REG_X0 + i, v)
        uc.emu_start(self.entry, ret)
        n = uc.reg_read(UC_ARM64_REG_X0)
        if n != rawlen:
            raise RuntimeError(f"OodleLZ_Decompress returned {n}, expected {rawlen}")
        return bytes(uc.mem_read(raw, rawlen))


class Source:
    """Byte ranges of arc/data.trpfd and arc/data.trpfs: `fd` the index, `read_fs(off, size)`."""

    def __init__(self, fd, read_fs, fs_size):
        self.fd, self.read_fs, self.fs_size = fd, read_fs, fs_size

    @classmethod
    def directory(cls, romfs_dir):
        fd = open(os.path.join(romfs_dir, "arc", "data.trpfd"), "rb").read()
        path = os.path.join(romfs_dir, "arc", "data.trpfs")
        fh = open(path, "rb")

        def read_fs(off, size):
            fh.seek(off)
            return fh.read(size)
        return cls(fd, read_fs, os.path.getsize(path))

    @classmethod
    def romfs(cls, romfs):
        """From a RomFs (pokeldn.switch.romfs), e.g. an update's over its base game."""
        files = {p: (o, s) for p, o, s in romfs.walk()}
        fs_off, fs_size = files["/arc/data.trpfs"]
        return cls(romfs.read_file(*files["/arc/data.trpfd"]),
                   lambda off, size: romfs.read_file(fs_off + off, size), fs_size)


class Trpfs:
    def __init__(self, src):
        self.src = src
        fd = self.fd = Fb(src.fd)
        root = fd.root()
        self.file_hashes = fd.u64s(root, 0)
        self.index = {h: i for i, h in enumerate(self.file_hashes)}
        self.pack_names = [fd.string(at) for at in
                           (lambda s, n: [s + 4 * k for k in range(n)])(*fd.vec(root, 1))]
        self.file_pack = [fd.u64(fd.field(t, 0)) if fd.field(t, 0) else 0
                          for t in fd.tables(root, 2)]
        self.pack_size = [fd.u64(fd.field(t, 0)) for t in fd.tables(root, 3)]
        head = src.read_fs(0, 16)
        if head[:7] != b"ONEPACK":
            raise ValueError("data.trpfs: no ONEPACK magic")
        table_at = struct.unpack_from("<Q", head, 8)[0]
        tail = Fb(src.read_fs(table_at, src.fs_size - table_at))
        troot = tail.root()
        self.pack_at = dict(zip(tail.u64s(troot, 0), tail.u64s(troot, 1)))
        self.packs = {}

    def pack(self, i):
        if i not in self.packs:
            name = self.pack_names[i]
            off = self.pack_at[fnv1a64(name)]
            self.packs[i] = Fb(self.src.read_fs(off, self.pack_size[i]))
        return self.packs[i]

    def entry(self, file_hash):
        """-> (pack index, compression type, decompressed size, stored bytes)."""
        i = self.index[file_hash]
        p = self.file_pack[i]
        pk = self.pack(p)
        root = pk.root()
        k = pk.u64s(root, 0).index(file_hash)
        t = pk.tables(root, 1)[k]
        ctype = struct.unpack_from("<b", pk.b, pk.field(t, 1))[0] if pk.field(t, 1) else -1
        dsize = pk.u64(pk.field(t, 3)) if pk.field(t, 3) else 0
        start, n = pk.vec(t, 4)
        return p, ctype, dsize, pk.b[start:start + n]

    def read(self, file_hash, oodle):
        _p, ctype, dsize, data = self.entry(file_hash)
        if ctype == OODLE:
            return oodle.decompress(data, dsize)
        if ctype not in (-1, 0):
            raise ValueError(f"{file_hash:016x}: compression type {ctype}")
        return bytes(data)
