"""The host's quiet gate (pokeldn.ldn.host_pia): while the console says nothing, the host drops its own
retransmissions; with HostSession's hole guard holding new frames, a gap the console never received
then left a FireRed room silent on both sides, the console on "Veuillez patienter"."""
from pokeldn.ldn import host_pia, reliable


class Clock:
    now = 100.0


def peer(monkeypatch, clock):
    p = object.__new__(host_pia.HostPeerProtocol)
    p.pia_crypto, p.guest_var, p.guest_ip, p.network, p.nonces = object(), 0x1234, "169.254.1.2", None, None
    p.reliable_packet_id, p.reliable_messages_out, p.log = 1, 0, lambda *a: None
    p.sent = []
    monkeypatch.setattr(host_pia.time, "monotonic", lambda: clock.now)
    monkeypatch.setattr(host_pia, "build_messages", lambda network, crypto, messages, **kw: messages)
    monkeypatch.setattr(p, "_send", lambda data, destination: p.sent.append(data), raising=False)
    return p


def gap(seq=7):
    return reliable.ReliableEmission(seq, 0x00, 0, b"\x11" * 8, retransmitted=True)


def test_a_quiet_console_still_gets_its_missing_frame_about_once_a_second(monkeypatch):
    clock = Clock()
    p = peer(monkeypatch, clock)
    p._last_rx = clock.now - 5.0          # only RTT answers lately: quiet
    delivered = 0
    for step in range(30):                # three seconds of retransmissions offered every 0.1 s
        clock.now += 0.1
        before = len(p.sent)
        p._send_reliable([gap()])
        delivered += len(p.sent) > before
    assert 2 <= delivered <= 4


def test_a_quiet_console_is_not_flooded_with_retransmissions(monkeypatch):
    clock = Clock()
    p = peer(monkeypatch, clock)
    p._last_rx = clock.now - 5.0
    p._send_reliable([gap(7)])
    clock.now += 0.2
    p._send_reliable([gap(7)])
    assert len(p.sent) == 1
