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


@lifted(0x343D5B0)
def ticks_to_ns(m, ticks, *_):
    """nn::os::ConvertToTimeSpan (the SDK's, through [0x46ca3d0]): ticks of the 19.2 MHz counter as
    nanoseconds, saturated at the s64 limits."""
    t = ticks - (1 << 64) if ticks >> 63 else ticks
    if t > 0x0275254609ABE000:
        return 0x7FFFFFFFFFFFFFFF
    if t < -0x0275254609ABE000:
        return 1 << 63
    div = lambda a, b: abs(a) // b * (1 if a >= 0 else -1)      # C division, toward zero
    q = div(t, 19200000)
    frac = div((t - q * 19200000) * 1000000000, 19200000)
    return (q * 1000000000 + frac) & 0xFFFFFFFFFFFFFFFF


@lifted(0x343E6D0)
def initialize_light_event(m, event, signaled, mode, *_):
    """nn::os::InitializeLightEvent as measured for (not signaled, auto clear 1): bytes +0 and +1 = 1,
    state +4 = 0. Any other arguments are refused."""
    if signaled & 0xFF or mode & 0xFFFFFFFF != 1:
        raise UnliftedCall("InitializeLightEvent with unmeasured arguments")
    m.put(event, 1, 1); m.put(event + 1, 1, 1); m.put(event + 4, 4, 0)
    return event


@lifted(0x2A70AB4)
def destroy_event_holder(m, p, *_):
    """Set the vtable 0x44a92f8 and finalize the light event at +0x28 (nn::os::FinalizeLightEvent
    clears its byte +1)."""
    m.put(p, 8, m.main + 0x44A92F8)
    m.put(p + 0x29, 1, 0)
    return p + 0x28
