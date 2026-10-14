"""The C library and Horizon calls the server reaches."""

from pokeldn.sv.battle.machine import UnliftedCall, lifted

FAKE_THREAD = 0x7F0001000      # what GetCurrentThread returns in the engine's address space


@lifted(0x343C220)
def memset(m, dst, value, n, *_):
    m.write(dst, bytes([value & 0xFF]) * n)
    return dst


@lifted(0x343C210)
def memcpy(m, dst, src, n, *_):
    m.write(dst, m.read(src, n))
    return dst


@lifted(0x343C6F0)
def memcmp(m, a, b, n, *_):
    x, y = m.read(a, n), m.read(b, n)
    for i in range(n):
        if x[i] != y[i]:
            return (x[i] - y[i]) & 0xFFFFFFFF
    return 0


@lifted(0x343C290)
def get_current_thread(m, *_):
    return FAKE_THREAD


@lifted(0x343E5E0)
def signal_light_event(m, event, *_):
    """nn::os::SignalLightEvent with no waiter: the state word (+4) goes from 0 to 2 and stays 2; state 1
    (a thread waiting) needs the kernel."""
    state = m.u32(event + 4)
    if state == 0:
        m.put(event + 4, 4, 2)
    elif state != 2:
        raise UnliftedCall("light event with a waiter")
    return event


def _tls_slot(m, slot):
    return m.u64(m.tls + 0x1F8) + 0x80 + 8 * (slot & 0xFFFFFFFF)


@lifted(0x343DA20)
def get_tls_value(m, slot, *_):
    """nn::os::GetTlsValue: the slot's word in the thread's ThreadType (+0x80)."""
    return m.u64(_tls_slot(m, slot))


@lifted(0x343DA30)
def set_tls_value(m, slot, value, *_):
    m.put(_tls_slot(m, slot), 8, value)
