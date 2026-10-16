"""A retail Switch title's RomFS, read in place: the metadata tables, a file's bytes, a search over
file data. hactool's --listromfs segfaults on a sparse NCA. docs/switch_re.md "Reading the RomFS".
"""

import struct

from Crypto.Cipher import AES

SECTOR = 0x10


class CtrReader:
    """A seekable window onto one AES-128-CTR section of a container."""

    def __init__(self, path, base, key, ctr_high):
        self.fh = open(path, "rb")
        self.base = base          # where the NCA starts inside the container
        self.key = key
        self.ctr_high = ctr_high  # the section CTR's high 8 bytes

    def read(self, nca_offset, size):
        """Decrypt `size` bytes at `nca_offset` (relative to the NCA's start)."""
        if size <= 0:
            return b""
        pad = nca_offset % SECTOR
        aligned = nca_offset - pad
        raw_len = pad + size
        self.fh.seek(self.base + aligned)
        raw = self.fh.read(raw_len)
        if len(raw) < raw_len:
            raise EOFError(f"short read at {nca_offset:#x}: {len(raw)} of {raw_len}")
        ctr = self.ctr_high + struct.pack(">Q", aligned >> 4)
        clear = AES.new(self.key, AES.MODE_CTR, nonce=b"", initial_value=ctr).decrypt(raw)
        return clear[pad:pad + size]

    def close(self):
        self.fh.close()


class RomFs:
    """The RomFS metadata tables, parsed once and held in memory."""

    HEADER_FMT = "<10Q"

    def __init__(self, reader, romfs_offset):
        self.reader = reader
        self.romfs_offset = romfs_offset   # NCA-relative start of the level-5 data
        head = struct.unpack(self.HEADER_FMT, reader.read(romfs_offset, 0x50))
        (self.header_size,
         self.dir_hash_off, self.dir_hash_size,
         self.dir_meta_off, self.dir_meta_size,
         self.file_hash_off, self.file_hash_size,
         self.file_meta_off, self.file_meta_size,
         self.file_data_off) = head
        if self.header_size != 0x50:
            raise ValueError(
                f"header_size is {self.header_size:#x}, not 0x50 - the CTR or the "
                f"offset is wrong, and nothing read past here means anything")
        self.dir_meta = reader.read(romfs_offset + self.dir_meta_off, self.dir_meta_size)
        self.file_meta = reader.read(romfs_offset + self.file_meta_off, self.file_meta_size)

    def _dir(self, off):
        parent, sibling, child_dir, child_file, _hash, name_len = struct.unpack_from(
            "<6I", self.dir_meta, off)
        name = self.dir_meta[off + 24:off + 24 + name_len].decode("utf-8", "replace")
        return parent, sibling, child_dir, child_file, name

    def _file(self, off):
        parent, sibling = struct.unpack_from("<2I", self.file_meta, off)
        data_off, data_size = struct.unpack_from("<2Q", self.file_meta, off + 8)
        _hash, name_len = struct.unpack_from("<2I", self.file_meta, off + 24)
        name = self.file_meta[off + 32:off + 32 + name_len].decode("utf-8", "replace")
        return parent, sibling, data_off, data_size, name

    def walk(self):
        """Yield (path, data_offset, data_size) for every file, depth first."""
        stack = [(0, "")]
        while stack:
            dir_off, prefix = stack.pop()
            _p, _s, child_dir, child_file, _n = self._dir(dir_off)
            off = child_file
            while off != 0xFFFFFFFF:
                _p, sibling, data_off, data_size, name = self._file(off)
                yield prefix + "/" + name, data_off, data_size
                off = sibling
            off = child_dir
            while off != 0xFFFFFFFF:
                _p, sibling, _cd, _cf, name = self._dir(off)
                stack.append((off, prefix + "/" + name))
                off = sibling

    def read_file(self, data_off, size):
        return self.reader.read(self.romfs_offset + self.file_data_off + data_off, size)


def scan(romfs, needles, names=None, chunk=8 << 20):
    """Search every file's DATA for any of `needles`, streamed; yield (path, offset, needle)."""
    overlap = max(len(n) for n in needles) - 1
    for path, data_off, size in romfs.walk():
        if names is not None and not any(n in path.lower() for n in names):
            continue
        pos = 0
        tail = b""
        while pos < size:
            n = min(chunk, size - pos)
            buf = tail + romfs.read_file(data_off + pos, n)
            for needle in needles:
                start = 0
                while True:
                    hit = buf.find(needle, start)
                    if hit < 0:
                        break
                    yield path, pos - len(tail) + hit, needle
                    start = hit + 1
            tail = buf[-overlap:] if overlap else b""
            pos += n
