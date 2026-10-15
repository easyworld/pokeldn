"""Long-upload diagnostic: exercise the real host framing, flow control and final accounting."""

import pytest

import esp32_bench
from pokeldn.ldn import esp32, esp32_sim


@pytest.mark.parametrize("failure", [None, "write", "missing"])
def test_soak_counts_upload_frames_and_fails_on_a_dead_link_or_missing_frame(monkeypatch, capsys, failure):
    import serial

    class Board(esp32_sim.SimulatedBoard):
        def __init__(self):
            super().__init__(esp32_sim.Air())
            self.frames = []
            self.stopped = False

        def _command(self, t, p):
            if t == esp32.CMD_ETH_TX:
                self.frames.append(p)
            elif t == esp32.CMD_STATUS:
                count = len(self.frames) - int(failure == "missing" and bool(self.frames))
                self._emit(esp32.MSG_STATUS, f"tx_eth={count} tx_eth_failed=0 wire_rx_bad=0".encode())
            else:
                self.stopped |= t == esp32.CMD_STOP
                super()._command(t, p)

    board = Board()

    class Port(esp32_sim.UartPort):
        closed = False

        def write(self, data):
            if failure == "write" and len(board.frames) >= 32:
                raise TimeoutError("Write timeout")
            super().write(data)
            return len(data)

        def close(self):
            self.closed = True

    port = Port(board)
    monkeypatch.setattr(serial, "Serial", lambda: port)
    if failure:
        with pytest.raises(esp32.RadioError, match="Write timeout|board counted"):
            esp32_bench.soak("COM5", 115200, 0.1, size=1400, rate=0)
    else:
        esp32_bench.soak("COM5", 115200, 0.1, size=1400, rate=0)
        assert board.stopped
    assert board.frames and all(len(frame) == 1400 for frame in board.frames)
    assert board.stopped == (failure != "write")
    assert port.closed
    output = capsys.readouterr().out
    assert "soak starting" in output
    assert ("soak stopped after" in output) == bool(failure)


def test_soak_cli_reports_failure_and_never_opens_for_invalid_arguments(monkeypatch, capsys):
    calls = []

    def fail(*args):
        calls.append(args)
        raise esp32.RadioError("The board stopped answering over USB")

    monkeypatch.setattr(esp32_bench, "soak", fail)
    assert esp32_bench.main(["--port", "COM5", "--soak", "7200", "--bauds", "921600"]) == 1
    assert len(calls) == 1 and "soak FAILED" in capsys.readouterr().out
    for options in (["--size", "2"], ["--no-flow"], ["--rate", "-1"]):
        with pytest.raises(SystemExit) as exc:
            esp32_bench.main(["--port", "COM5", "--soak", "7200", *options])
        assert exc.value.code == 2
    assert len(calls) == 1
