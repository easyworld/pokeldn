import cProfile
import io
import json
import pstats
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace


def run(usb, ui):
    import android_compat
    android_compat.install()
    from Crypto.Util import _raw_api
    hold_gil = (Path(str(ui.getFilesDir().getAbsolutePath())) / 'trade' / 'crypto_hold_gil').exists()
    if hold_gil:
        import ctypes
        assert _raw_api.backend == 'ctypes'
        _raw_api.CDLL = ctypes.PyDLL
    from android_probe import AndroidStream
    from pokeldn.ldn import esp32, crypto, host_pia

    ui.report('PROFILE_START Python=%s switchinterval=%s crypto_backend=%s' %
              (sys.version.split()[0], sys.getswitchinterval(), _raw_api.backend))
    ui.report('CRYPTO_HOLD_GIL=' + str(hold_gil))
    network = SimpleNamespace(our_ip='169.254.4.1')
    cipher = crypto.PiaCrypto(bytes(range(16)))
    payload = bytes(range(128)) * 2
    nonce = host_pia.PiaNonceSequence(native=True, initial=1)

    def workload(count, radio=None, paced=False):
        started = time.monotonic()
        gaps = []
        previous = started
        for index in range(count):
            tick = time.monotonic()
            gaps.append(tick - previous)
            previous = tick
            packet = host_pia.build_messages(network, cipher, [(0, payload)], dst_var=1, src_var=198,
                pktid=index + 1, auto_compress=True, footer_var=1, nonce_source=nonce)
            parsed, error = host_pia.decode_datagram(packet, network.our_ip, cipher)
            assert error is None and parsed[1][0].payload == payload
            if radio is not None:
                radio.send_ethernet(b'\xff' * 6 + bytes.fromhex('0200000000be') + b'\x08\x00' + packet)
            if paced:
                time.sleep(max(0, 1 / 59.727 - (time.monotonic() - tick)))
        if radio is not None:
            assert radio.drain(20)
        elapsed = time.monotonic() - started
        return {'count': count, 'seconds': elapsed, 'hz': count / elapsed,
                'max_gap_ms': max(gaps) * 1000}

    ui.report('PROFILE_NO_RADIO=' + json.dumps(workload(120)))
    barrier = threading.Barrier(2)
    concurrent_results = []
    def competing_workload():
        barrier.wait()
        concurrent_results.append(workload(300))
    competitor = threading.Thread(target=competing_workload)
    competitor.start()
    barrier.wait()
    result = workload(300)
    competitor.join()
    ui.report('PROFILE_TWO_CRYPTO_THREADS=' + json.dumps({'main': result, 'other': concurrent_results}))
    radio = esp32.Radio(AndroidStream(usb))
    original_interval = sys.getswitchinterval()
    try:
        radio.info = esp32.Info.parse(radio.request(esp32.CMD_HELLO, b'', esp32.MSG_INFO))
        radio.stop()
        for buffering in (None, 1, 65536):
            destination = Path(str(ui.getFilesDir().getAbsolutePath())) / 'trade' / 'bench-radio.trace'
            radio._trace = destination.open('w', buffering=buffering) if buffering is not None else None
            first = threading.Event()
            on_bench = lambda kind, data: first.set() if kind == esp32.MSG_BENCH else None
            radio.subscribe(on_bench)
            transfer = []
            worker = threading.Thread(target=lambda: transfer.append(radio.bench(1_000_000, timeout=30)))
            worker.start()
            assert first.wait(5), 'No BENCH input'
            result = workload(300)
            worker.join(35)
            assert not worker.is_alive() and transfer, 'BENCH did not finish'
            radio.unsubscribe(on_bench)
            if radio._trace is not None:
                radio._trace.close()
                radio._trace = None
            ui.report('PROFILE_ACTIVE_USB=' + json.dumps({'buffering': buffering, 'workload': result, 'transfer': transfer}))
        for interval in (0.005, 0.001, 0.0001, 0.005):
            sys.setswitchinterval(interval)
            result = workload(120, radio, paced=True)
            ui.report('PROFILE_TIMING=' + json.dumps({'switchinterval': interval, **result}))
        sys.setswitchinterval(original_interval)
        profiler = cProfile.Profile()
        profiler.enable()
        workload(60, radio)
        profiler.disable()
        out = io.StringIO()
        pstats.Stats(profiler, stream=out).sort_stats('cumtime').print_stats(18)
        ui.report('PROFILE_MAIN\n' + out.getvalue())
        ui.report('PROFILE_STATUS=' + radio.status())
        ui.report('PROFILE_DONE')
    finally:
        sys.setswitchinterval(original_interval)
        radio.close()
