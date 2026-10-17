"""The radio board's host link over Bluetooth LE: the same COBS byte stream as the cable, for a host
with no USB serial (an iPhone). The board needs the POKELDN_BLE firmware build
(docs/hardware_esp32.md, Bluetooth). `POKELDN_RADIO=esp32:ble` selects it."""

import asyncio
import threading
import time

NAME = "POKELDN-RADIO"
SERVICE = "7a1e0101-5d2c-4c3e-9f4b-504f4b454c44"
RX = "7a1e0102-5d2c-4c3e-9f4b-504f4b454c44"   # host writes
TX = "7a1e0103-5d2c-4c3e-9f4b-504f4b454c44"   # board notifies


class BleStream:
    """A pyserial-shaped stream (`read`, `write`, `in_waiting`, `baudrate`) over one BLE connection;
    bleak runs on its own event loop thread."""

    def __init__(self, name: str = NAME, timeout: float = 0.02, connect_timeout: float = 15.0):
        self.timeout = timeout
        self.baudrate = 115200   # Radio's rate search reads and sets it; nothing on BLE has a rate
        self.out_waiting = 0
        self._buffer = bytearray()
        self._cv = threading.Condition()
        self._lost: Exception | None = None
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, name="esp32-ble", daemon=True)
        self._thread.start()
        self._client = None
        self._run(self._connect(name, connect_timeout), connect_timeout + 15)

    def _run(self, coro, timeout=None):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    async def _connect(self, name, timeout):
        from bleak import BleakClient, BleakScanner
        device = await BleakScanner.find_device_by_name(name, timeout=timeout)
        if device is None:
            raise ConnectionError(f"no {name} found over Bluetooth: is the board running the "
                                  "Bluetooth radio firmware and powered?")
        self._client = BleakClient(device, disconnected_callback=self._disconnected)
        await self._client.connect()
        await self._client.start_notify(TX, self._notified)
        # macOS and iOS take the board's 247 byte MTU; a write carries mtu - 3 bytes.
        self._piece = max(20, (self._client.mtu_size or 23) - 3)

    def _notified(self, _characteristic, data: bytearray) -> None:
        with self._cv:
            self._buffer += data
            self._cv.notify_all()

    def _disconnected(self, _client) -> None:
        with self._cv:
            self._lost = ConnectionError("the board's Bluetooth link dropped")
            self._cv.notify_all()

    @property
    def in_waiting(self) -> int:
        return len(self._buffer)

    def read(self, n: int = 1) -> bytes:
        deadline = time.monotonic() + self.timeout
        with self._cv:
            while not self._buffer:
                if self._lost:
                    raise self._lost
                left = deadline - time.monotonic()
                if left <= 0 or not self._cv.wait(left):
                    return b""
            out = bytes(self._buffer[:n])
            del self._buffer[:n]
            return out

    def write(self, data: bytes) -> int:
        if self._lost:
            raise self._lost
        self._run(self._write(bytes(data)), 10)
        return len(data)

    async def _write(self, data: bytes) -> None:
        # CoreBluetooth drops a write without response its queue cannot take, and bleak never asks
        # canSendWriteWithoutResponse (docs/hardware_pad.md, The Bluetooth side).
        peripheral = getattr(getattr(self._client, "_backend", None), "_peripheral", None)
        ready = getattr(peripheral, "canSendWriteWithoutResponse", None)
        for first in range(0, len(data), self._piece):
            piece = data[first:first + self._piece]
            if ready is not None:
                for _ in range(1000):
                    if ready():
                        break
                    await asyncio.sleep(0.001)
                else:
                    await self._client.write_gatt_char(RX, piece, response=True)
                    continue
            await self._client.write_gatt_char(RX, piece, response=False)

    def close(self) -> None:
        try:
            if self._client is not None and self._client.is_connected:
                self._run(self._client.disconnect(), 5)
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)
