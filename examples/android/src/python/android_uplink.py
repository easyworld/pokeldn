import json
import os
import sys
import time
from types import SimpleNamespace


def run(usb, ui):
    import android_compat
    android_compat.install()
    from android_probe import AndroidStream
    from pokeldn.ldn import esp32, crypto, host_pia
    network = SimpleNamespace(our_ip='169.254.4.1')
    cipher = crypto.PiaCrypto(bytes(range(16)))
    payload = bytes(range(128)) * 2
    nonce = host_pia.PiaNonceSequence(native=True, initial=1)
    radio = esp32.Radio(AndroidStream(usb))
    original_interval = sys.getswitchinterval()
    selected_cpu = android_compat.performance_cpu()
    if selected_cpu is None:
        raise ValueError('CPU capacity information is unavailable for the affinity benchmark')
    native_ids = (0, radio._thread.native_id, radio._writer.native_id)
    original_masks = {tid: os.sched_getaffinity(tid) for tid in native_ids}
    def status():
        return dict(p.split('=', 1) for p in radio.status().split() if '=' in p)
    try:
        radio.info = esp32.Info.parse(radio.request(esp32.CMD_HELLO, b'', esp32.MSG_INFO))
        radio.stop()
        for queued, affinity in ((False, None), (False, None), (False, {selected_cpu}), (False, {selected_cpu}), (False, None), (True, {selected_cpu})):
            for tid in native_ids:
                os.sched_setaffinity(tid, affinity if affinity is not None else original_masks[tid])
            usb.setQueuedWrites(queued)
            for interval in (0.005,):
                sys.setswitchinterval(interval)
                before = status()
                assert before['mode'] == '0'
                started = time.perf_counter()
                cpu_started = time.thread_time()
                maximum_gap = 0
                previous = started
                for index in range(300):
                    now = time.perf_counter()
                    maximum_gap = max(maximum_gap, now - previous)
                    previous = now
                    packet = host_pia.build_messages(network, cipher, [(0, payload)], dst_var=1,
                        src_var=198, pktid=index + 1, auto_compress=True, footer_var=1, nonce_source=nonce)
                    parsed, error = host_pia.decode_datagram(packet, network.our_ip, cipher)
                    assert error is None and parsed[1][0].payload == payload
                    radio.send_ethernet(b'\xff' * 6 + bytes.fromhex('0200000000be') + b'\x08\x00' + packet)
                compute = time.perf_counter() - started
                cpu = time.thread_time() - cpu_started
                assert radio.drain(30)
                assert usb.flushWrites(10000)
                after = status()
                elapsed = time.perf_counter() - started
                counted = sum(int(after[k]) - int(before[k]) for k in ('tx_eth', 'tx_eth_failed'))
                result = dict(queued=queued, affinity=sorted(affinity) if affinity else None, interval=interval, count=300, board_counted=counted,
                    compute_seconds=compute, cpu_seconds=cpu, total_seconds=elapsed,
                    hz=300/elapsed, max_gap_ms=maximum_gap*1000, dropped=radio.tx_dropped,
                    wire_bad_delta=int(after['wire_rx_bad'])-int(before['wire_rx_bad']))
                ui.report('UPLINK_PROFILE=' + json.dumps(result))
                assert counted == 300 and result['dropped'] == 0 and result['wire_bad_delta'] == 0
        ui.report('UPLINK_PROFILE_DONE')
    finally:
        for tid in native_ids:
            os.sched_setaffinity(tid, original_masks[tid])
        sys.setswitchinterval(original_interval)
        radio.close()
