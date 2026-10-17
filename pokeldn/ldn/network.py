"""An LDN network joined or hosted for a plugin, with the radio's userspace IPv4 stack: the stable
surface docs/plugins.md names under "LDN networks (1.7)". It needs a radio with no kernel interface
(the ESP32 board, ldnrs); the transports behind it may change, this module's names do not.
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Callable

from pokeldn.ldn import transport, userspace_ip


@dataclass(frozen=True)
class Participant:
    index: int
    ip: str
    mac: bytes
    name: bytes


class Network:
    """One joined or hosted network. Close it, or use it as a context manager."""

    def __init__(self, link, log: Callable):
        self._link = link
        self._log = log
        self._protocols: list[int] = []
        self._sockets: list = []
        # Only this object's sockets carry traffic: the transport's own Pia sockets would queue
        # every frame for nobody.
        for sock in (link._tx, link._rx):
            if sock is not None:
                sock.close()
        link._tx = link._rx = None
        self._stack = userspace_ip.lookup(link.iface)
        if self._stack is None:
            link.stop()
            raise RuntimeError("an LDN network for a plugin needs the ESP32 board or ldnrs "
                               "(POKELDN_RADIO); a kernel interface has no userspace stack")

    @property
    def ip(self) -> str:
        return self._link.our_ip

    @property
    def mac(self) -> bytes:
        return bytes(self._link.our_mac or b"")

    @property
    def host_ip(self) -> str:
        return self._link.host_ip

    @property
    def broadcast(self) -> str:
        return self._link.broadcast

    @property
    def ssid(self) -> bytes:
        return bytes(self._link.ssid or b"")

    @property
    def comm_id(self) -> int:
        return self._link.LOCAL_COMMUNICATION_ID

    @property
    def application_data(self) -> bytes:
        """The advertisement's application data: the host's when joined, ours when hosting."""
        return bytes(self._link.app_data or b"")

    @property
    def participants(self) -> list[Participant]:
        """The stations seated on a network this program hosts; empty when joined."""
        return [Participant(i, str(ip), bytes(mac), bytes(name))
                for i, ip, mac, name in getattr(self._link, "participants", [])]

    @property
    def error(self) -> str:
        """Why the network ended, or "" while it is up."""
        return self._link._err or ""

    def add_protocol(self, number: int, handler: Callable[[str, str, bytes], None]) -> None:
        """`handler(src_ip, dst_ip, payload)` takes every reassembled IPv4 packet of protocol
        `number` (6 for TCP; never 17, UDP) sent to us. It runs on the radio's loop: queue the
        payload and return. An exception from it is logged and the packet dropped."""
        def safe(src, dst, payload):
            try:
                handler(src, dst, payload)
            except Exception as error:
                self._log(f"[ldn] IP protocol {number} handler failed: {type(error).__name__}: {error}")
        self._stack.add_protocol(number, safe)
        self._protocols.append(number)

    def remove_protocol(self, number: int) -> None:
        self._stack.remove_protocol(number)
        if number in self._protocols:
            self._protocols.remove(number)

    def send_ip(self, protocol: int, dst_ip: str, payload: bytes) -> bool:
        """Sends `payload` as one IPv4 packet, fragmented at 1500 bytes. False while `dst_ip`'s
        hardware address is unknown: an ARP request went out, so send again shortly."""
        ipaddress.IPv4Address(dst_ip)
        return self._stack.send_ip(protocol, dst_ip, bytes(payload))

    def udp_socket(self, port: int):
        """A UDP socket bound to `port` on this network: `sendto`, `recvfrom`, `setblocking`,
        `settimeout`, `fileno` (for select and trio) and `close`."""
        sock = self._stack.udp_socket(port)
        self._sockets.append(sock)
        return sock

    def set_application_data(self, data: bytes) -> None:
        """Replaces the advertisement's application data of a network this program hosts."""
        if not isinstance(self._link, transport.HostTransport):
            raise RuntimeError("only a hosted network advertises application data")
        self._link.set_app_data_later(bytes(data))

    def close(self) -> None:
        for number in list(self._protocols):
            self.remove_protocol(number)
        for sock in self._sockets:
            sock.close()
        self._sockets.clear()
        self._link.stop()

    def __enter__(self) -> "Network":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def join(comm_id: int, *, keys: str, password: bytes, nickname: str = "POKELDN",
         app_version: int | None = None, name: str = "LDN", log: Callable = print,
         timeout: float = 30) -> Network:
    """Scans and joins the network whose local communication id is `comm_id`, and no other.
    `keys` is the path of prod.keys, `password` the title's LDN passphrase, `name` what the
    player's messages call the network. Raises RuntimeError when no such network answers."""
    link = transport.LiveTransport(password=password, nickname=nickname, keys_path=keys,
                                   local_comm_id=comm_id, app_version=app_version, log=log,
                                   exact_comm_id=True, network=name)
    return Network(link.start(timeout=timeout), log)


def host(comm_id: int, *, keys: str, password: bytes, nickname: str = "POKELDN",
         application_data: bytes = b"", scene_id: int = 0, app_version: int = 0,
         max_participants: int = 2, channel: int | None = None, protocol: int = 3,
         log: Callable = print, timeout: float = 30) -> Network:
    """Opens a network advertising `comm_id` that consoles join; `participants` lists them."""
    phy = transport.find_ap_phy(log=log)
    link = transport.HostTransport(app_data=application_data, password=password, nickname=nickname,
                                   keys_path=keys, local_comm_id=comm_id, scene_id=scene_id,
                                   app_version=app_version, max_participants=max_participants,
                                   phyname=phy, channel=channel, protocol=protocol, log=log)
    return Network(link.start(timeout=timeout, preflight=False), log)
