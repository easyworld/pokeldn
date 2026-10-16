"""The memory and call model the house engine runs on: the server state laid out as Scarlet 4.0.0 lays
it out, addressed by u64, and the engine's functions keyed by the address of the game function each one
reproduces (docs/sv_raid.md, Reproducing a round). Every load and store truncates to its width.
"""

import contextlib
import struct

PAGE = 0x1000
MASK = {1: 0xFF, 2: 0xFFFF, 4: 0xFFFFFFFF, 8: 0xFFFFFFFFFFFFFFFF}
FORMAT = {1: "<B", 2: "<H", 4: "<I", 8: "<Q"}
SIGNED = {1: "<b", 2: "<h", 4: "<i", 8: "<q"}

FUNCTIONS = {}          # game address -> Python function(machine, *args) -> int


def lifted(address):
    """Register a function as the engine's version of the game function at `address`."""
    def register(fn):
        if address in FUNCTIONS:
            raise ValueError(f"0x{address:x} lifted twice")
        FUNCTIONS[address] = fn
        fn.address = address
        return fn
    return register


class Pair(tuple):
    """A result returned in x0 and x1 (a 16-byte struct)."""
    def __new__(cls, x0, x1):
        return super().__new__(cls, (x0 & MASK[8], x1 & MASK[8]))


class Float32(float):
    """A result returned in s0 (a single-precision float)."""


class UnliftedCall(Exception):
    """The engine reached a game function it has no version of: the round is refused."""


class Machine:
    """State as pages of bytes, plus the call interface the lifted functions use."""

    def __init__(self, pages=None, main=0, stack=None, tls=0):
        self.pages = pages if pages is not None else {}
        self.main = main            # where the game's main image sits in this state's address space
        self.sp = stack             # top of the engine's own scratch stack (locals of lifted functions)
        self.tls = tls              # tpidrro_el0: the thread's TLS block, +0x1f8 its nn::os ThreadType
        self.x8 = 0                 # the result address of a call returning a struct through x8

    def page(self, address):
        p = self.pages.get(address & ~(PAGE - 1))
        if p is None:
            raise MemoryError(f"no state at 0x{address:x}")
        return p

    def read(self, address, n):
        out = bytearray()
        while n:
            p = self.page(address); o = address & (PAGE - 1); k = min(n, PAGE - o)
            out += p[o:o + k]; address += k; n -= k
        return bytes(out)

    def write(self, address, data):
        i = 0
        while i < len(data):
            p = self.page(address); o = address & (PAGE - 1); k = min(len(data) - i, PAGE - o)
            p[o:o + k] = data[i:i + k]; address += k; i += k

    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        cls._direct_read = cls.read is Machine.read
        cls._direct_write = cls.write is Machine.write

    _direct_read = _direct_write = True     # a field inside one page goes straight to it (same bytes)

    def u(self, address, size):
        o = address & (PAGE - 1)
        if self._direct_read and o + size <= PAGE:
            return struct.unpack_from(FORMAT[size], self.page(address), o)[0]
        return struct.unpack(FORMAT[size], self.read(address, size))[0]

    def s(self, address, size):
        o = address & (PAGE - 1)
        if self._direct_read and o + size <= PAGE:
            return struct.unpack_from(SIGNED[size], self.page(address), o)[0]
        return struct.unpack(SIGNED[size], self.read(address, size))[0]

    def put(self, address, size, value):
        o = address & (PAGE - 1)
        if self._direct_write and o + size <= PAGE:
            struct.pack_into(FORMAT[size], self.page(address), o, value & MASK[size])
            return
        self.write(address, struct.pack(FORMAT[size], value & MASK[size]))

    def u8(self, a): return self.u(a, 1)
    def u16(self, a): return self.u(a, 2)
    def u32(self, a): return self.u(a, 4)
    def u64(self, a): return self.u(a, 8)

    @contextlib.contextmanager
    def frame(self, size):
        """Scratch memory for a lifted function's locals, like a stack frame."""
        size = (size + 15) & ~15
        self.sp -= size
        try:
            yield self.sp
        finally:
            self.sp += size

    def call(self, address, *args):
        """Call the engine's version of the game function at `address` (an absolute address in this
        state's address space, as a vtable or a pointer holds it)."""
        fn = FUNCTIONS.get(address - self.main)
        if fn is None:
            raise UnliftedCall(f"main+0x{address - self.main:x}")
        r = fn(self, *args)
        if r is None:
            raise TypeError(f"main+0x{address - self.main:x} returned nothing to a caller that reads it")
        return r

    def call_void(self, address, *args):
        """Call a function whose result the caller ignores."""
        fn = FUNCTIONS.get(address - self.main)
        if fn is None:
            raise UnliftedCall(f"main+0x{address - self.main:x}")
        fn(self, *args)

    def call_sret(self, address, result, *args):
        """Call a function that writes its struct result to `result` (passed in x8)."""
        self.x8 = result
        return self.call(address, *args)

    def vcall_void(self, obj, slot, *args):
        self.call_void(self.u64(self.u64(obj) + slot), obj, *args)

    def vcall(self, obj, slot, *args):
        """A virtual call: the function at byte offset `slot` of `obj`'s vtable."""
        return self.call(self.u64(self.u64(obj) + slot), obj, *args)
