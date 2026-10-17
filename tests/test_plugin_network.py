"""pokeldn.ldn.network, the LDN surface a plugin uses: a host and a joiner on two simulated boards
carry another IP protocol and UDP both ways, across fragmentation, and join only their comm id."""

import contextlib
import os
import queue
import threading

import pytest

from ldn import wlan

from pokeldn.ldn import esp32, esp32_sim, esp32_wlan, network, userspace_ip

COMM_ID = 0x0100000000001234
PASSWORD = b"pokeldn-plugin-network-test".ljust(32, b"\0")


@pytest.fixture
def boards(tmp_path, monkeypatch):
    """Two boards on one air: the first thread to open the radio (the host) gets the first board,
    every later one the second."""
    monkeypatch.setenv("POKELDN_RADIO", "esp32:simulated")
    keys = tmp_path / "prod.keys"
    keys.write_text("".join(f"{name} = {os.urandom(16).hex()}\n" for name in (
        "aes_kek_generation_source", "aes_key_generation_source", "master_key_00", "master_key_12")))
    air = esp32_sim.Air()
    radios = [esp32.Radio(esp32_sim.SimulatedBoard(air).host_stream()) for _ in range(2)]
    owners: dict[int, esp32.Radio] = {}
    lock = threading.Lock()

    @contextlib.asynccontextmanager
    async def factory():
        with lock:
            radio = owners.setdefault(threading.get_ident(), radios[1] if owners else radios[0])
        esp = esp32_wlan.EspFactory(radio, port_factory=userspace_ip.userspace_port, join_timeout=5)
        try:
            yield esp
        finally:
            esp.router.close()

    wlan.set_factory(factory)
    try:
        yield str(keys)
    finally:
        wlan.set_factory(None)
        for radio in radios:
            radio.close()


def test_a_plugin_hosts_and_joins_and_carries_its_own_ip_protocol(boards):
    lines = []
    with network.host(COMM_ID, keys=boards, password=PASSWORD, application_data=b"lcs",
                      log=lines.append, timeout=10) as hosted:
        with network.join(COMM_ID, keys=boards, password=PASSWORD, nickname="JOINER",
                          name="Match Version", log=lines.append, timeout=10) as joined:
            assert joined.application_data == b"lcs"
            assert joined.host_ip == hosted.ip
            assert [p.ip for p in hosted.participants] == [joined.ip]
            got_host, got_joiner = queue.Queue(), queue.Queue()
            hosted.add_protocol(6, lambda src, dst, payload: got_host.put((src, dst, payload)))
            joined.add_protocol(6, lambda src, dst, payload: got_joiner.put((src, dst, payload)))
            segment = os.urandom(4000)                # three fragments at the 1500-byte MTU
            for _ in range(50):                       # the first sends resolve the neighbour by ARP
                if joined.send_ip(6, hosted.ip, segment):
                    break
                threading.Event().wait(0.1)
            assert got_host.get(timeout=5) == (joined.ip, hosted.ip, segment)
            assert hosted.send_ip(6, joined.ip, b"ack")
            assert got_joiner.get(timeout=5) == (hosted.ip, joined.ip, b"ack")

            sock = hosted.udp_socket(45000)
            sock.settimeout(5)
            out = joined.udp_socket(45001)
            out.sendto(b"datagram", (hosted.ip, 45000))
            assert sock.recvfrom(100) == (b"datagram", (joined.ip, 45001))
            with pytest.raises(ValueError):
                hosted.add_protocol(17, lambda *a: None)
            with pytest.raises(RuntimeError):
                joined.set_application_data(b"")
    assert "Scanning for the Match Version network..." in lines


def test_a_plugin_joins_only_its_own_comm_id(boards):
    """FRLG's joiner takes the only joinable network; a plugin's never does."""
    lines = []
    with network.host(COMM_ID, keys=boards, password=PASSWORD, log=lines.append, timeout=10):
        with pytest.raises(RuntimeError, match="no joinable Match Version network"):
            network.join(COMM_ID + 1, keys=boards, password=PASSWORD, name="Match Version",
                         log=lines.append, timeout=10)


def test_a_handler_that_raises_drops_the_packet_and_keeps_the_stack():
    sent, lines = [], []
    stack = userspace_ip.Stack("plugin-test", b"\x02\x00\x00\x00\x00\x01", sent.append)
    stack.set_address("169.254.9.1", "169.254.9.255")
    link = type("Link", (), {"_tx": None, "_rx": None, "iface": "plugin-test", "stop": lambda self: None})()
    userspace_ip._stacks["plugin-test"] = stack
    try:
        net = network.Network(link, lines.append)
        net.add_protocol(6, lambda *a: 1 / 0)
        console = b"\x02\x00\x00\x00\x00\x02"
        for packet in userspace_ip.build_ipv4("169.254.9.2", "169.254.9.1", 6, b"x"):
            stack.deliver(stack.mac + console + b"\x08\x00" + packet)
        assert lines == ["[ldn] IP protocol 6 handler failed: ZeroDivisionError: division by zero"]
        net.close()
        with pytest.raises(ValueError):
            stack.add_protocol(256, lambda *a: None)
        stack.add_protocol(6, lambda *a: None)      # close gave the protocol back
    finally:
        userspace_ip._stacks.pop("plugin-test", None)
