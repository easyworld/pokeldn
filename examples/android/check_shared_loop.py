import sys
import threading
import socket
from pathlib import Path
from types import SimpleNamespace
root = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(root), str(root / 'bin'), str(root / 'tests'), str(root / 'vendor/LDN'), str(Path(__file__).parent / 'src/python')]
import trio
import android_host_loop
from test_host_app_runtime import _Network, _Injector, _session, _Peer, _RuntimeApplication

class Network(_Network):
    def start(self, preflight=True):
        super().start(preflight)
        self._rx, self.writer = socket.socketpair()
        self._rx.setblocking(False)
        self.ready, self.exit = threading.Event(), threading.Event()
        async def main():
            self.loop_thread = threading.get_ident()
            self._network = SimpleNamespace(_tap=SimpleNamespace(_token=trio.lowlevel.current_trio_token()))
            self.ready.set()
            while not self.exit.is_set():
                await trio.sleep(0.01)
        self.worker = threading.Thread(target=lambda: trio.run(main))
        self.worker.start()
        assert self.ready.wait(3)
    def stop(self):
        super().stop()
        self.exit.set()
        self.worker.join(3)
        assert not self.worker.is_alive()
        self._rx.close()
        self.writer.close()

network = Network([('switch',)])
session = _session()
threads = []
def tick(peer):
    threads.append(threading.get_ident())
    if peer.ticks == 1:
        session.trade.close_confirmed = True
        network.participants.clear()
    elif peer.ticks == 4:
        session.trade.done = True
peer = _Peer(session, network, tick)
app = _RuntimeApplication(network, _Injector(), session, peer)
app._timing = {}
assert android_host_loop.run(app) is True
assert peer.ticks == 4 and peer.joined == 1
assert session.leave_calls == 0
assert set(threads) == {network.loop_thread}
assert network.loop_thread != threading.get_ident()
assert network.stopped == 1
print('PASS shared Trio scheduler: tick thread, close grace, and network cleanup')
