import ctypes
import errno
import os
import socket
import threading
from pathlib import Path


def performance_cpu():
    capacities = {}
    for cpu in os.sched_getaffinity(0):
        try:
            capacities[cpu] = int(Path('/sys/devices/system/cpu/cpu%d/cpu_capacity' % cpu).read_text())
        except OSError:
            pass
    if not capacities:
        return None
    return max(capacities, key=lambda cpu: (capacities[cpu], -cpu))


def clear_core(cpu):
    """Moves every thread of this process off `cpu`, except the caller; -> {tid: its old mask}."""
    me = threading.get_native_id()
    moved = {}
    for name in os.listdir('/proc/self/task'):
        tid = int(name)
        try:
            mask = os.sched_getaffinity(tid)
            if tid != me and cpu in mask and len(mask) > 1:
                os.sched_setaffinity(tid, mask - {cpu})
                moved[tid] = mask
        except OSError:      # a thread that ended meanwhile
            pass
    return moved


def restore(moved):
    for tid, mask in moved.items():
        try:
            os.sched_setaffinity(tid, mask)
        except OSError:
            pass


def install():
    libc = ctypes.CDLL(None, use_errno=True)
    name_to_index = libc.if_nametoindex
    name_to_index.argtypes = [ctypes.c_char_p]
    name_to_index.restype = ctypes.c_uint
    index_to_name = libc.if_indextoname
    index_to_name.argtypes = [ctypes.c_uint, ctypes.c_char_p]
    index_to_name.restype = ctypes.c_char_p

    def if_nametoindex(name):
        index = name_to_index(os.fsencode(name))
        if index == 0:
            code = ctypes.get_errno() or errno.ENODEV
            raise OSError(code, os.strerror(code))
        return index

    def if_indextoname(index):
        buffer = ctypes.create_string_buffer(16)
        if index_to_name(index, buffer) is None:
            code = ctypes.get_errno() or errno.ENODEV
            raise OSError(code, os.strerror(code))
        return os.fsdecode(buffer.value)

    if not hasattr(socket, 'if_nametoindex'):
        socket.if_nametoindex = if_nametoindex
    if not hasattr(socket, 'if_indextoname'):
        socket.if_indextoname = if_indextoname
    assert socket.if_indextoname(socket.if_nametoindex('lo')) == 'lo'
