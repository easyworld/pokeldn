import hashlib
import cProfile
import io
import json
import os
import sys
from pathlib import Path
import threading
import time

_cancel = threading.Event()
_experiment = None


def cancel():
    _cancel.set()


def experiment(name):
    global _experiment
    if name == 'stop':
        cancel()
        return
    if name.startswith('switch_us_'):
        sys.setswitchinterval(int(name.rsplit('_', 1)[1]) / 1_000_000)
        return
    _experiment = name


def run(usb, ui):
    import android_compat
    android_compat.install()
    import pokeldn
    root = Path(pokeldn.__file__).resolve().parent.parent
    folder = Path(str(ui.getFilesDir().getAbsolutePath())) / 'trade'
    folder.mkdir(exist_ok=True)
    if (folder / 'crypto_hold_gil').exists():
        import ctypes
        from Crypto.Util import _raw_api
        assert _raw_api.backend == 'ctypes'
        _raw_api.CDLL = ctypes.PyDLL
        from Crypto.Cipher import AES
        cipher = AES.new(bytes(16), AES.MODE_GCM, nonce=bytes(12), mac_len=8)
        ciphertext, tag = cipher.encrypt_and_digest(bytes(16))
        assert ciphertext.hex() == '0388dace60b6a392f328c2b971b2fe78'
        assert tag.hex() == 'ab6e47d42cec13bd'
        assert AES.new(bytes(16), AES.MODE_GCM, nonce=bytes(12), mac_len=8).decrypt_and_verify(ciphertext, tag) == bytes(16)
        import android_test_esp32
        android_test_esp32.test_userspace_stack_carries_udp_both_ways_on_simulated_boards()
        ui.report('PASS GIL-retaining crypto: NIST AES-GCM vector and simulated bidirectional LDN')
    os.environ['POKELDN_DATA'] = str(folder / 'data')
    os.environ['POKELDN_RADIO'] = 'esp32:android'
    run_folder = folder / time.strftime('run-%Y%m%d-%H%M%S')
    run_folder.mkdir()
    os.environ['POKELDN_ESP32_TRACE'] = str(run_folder / 'radio.trace')
    os.chdir(root)
    _cancel.clear()
    offer = folder / 'offer.pk3'
    manifest = json.loads((folder / 'offer.json').read_text())
    # A desktop import records PKHeX legality; a phone import records only its checksum (android_app).
    if hashlib.sha256(offer.read_bytes()).hexdigest() != manifest['sha256'] or manifest['legal'] is False:
        raise ValueError('The offer differs from the record that was checked on import')
    keys = folder / 'prod.keys'
    if not keys.is_file():
        raise ValueError('Switch keys have not been provisioned into the app')
    ui.report('Offering %s, level %s, OT %s (%s)' % (manifest['species'], manifest['level'], manifest['ot'],
              'validated on desktop' if manifest['legal'] else 'checksum checked on the phone'))

    from android_probe import AndroidStream
    from pokeldn.ldn import esp32, esp32_wlan
    from pokeldn.frlg import config
    from pokeldn.frlg.link.host_app import HostApplication
    from pokeldn.frlg.link.trade_runtime import ConsoleLog
    from ldn import wlan

    class Cancelled(Exception):
        pass

    class AndroidHost(HostApplication):
        def run(self):
            import android_host_loop
            ui.report('HOST_SCHEDULER=shared_trio_loop')
            return android_host_loop.run(self)

        def _build_components(self):
            result = super()._build_components()
            self._timing = {}
            self._timing_at = time.monotonic()
            self._timing_file = (run_folder / 'timing.jsonl').open('a', buffering=1)
            self._live_profile = None
            self._profile_finished = False
            self._memory_traces = []

            def wrap(target, name, label):
                original = getattr(target, name)
                def measured(*args, **kwargs):
                    started = time.monotonic()
                    cpu_started = time.thread_time()
                    try:
                        return original(*args, **kwargs)
                    finally:
                        elapsed = time.monotonic() - started
                        stat = self._timing.setdefault(label, [0, 0.0, 0.0, 0.0])
                        stat[0] += 1
                        stat[1] += elapsed
                        stat[2] = max(stat[2], elapsed)
                        stat[3] += time.thread_time() - cpu_started
                        if label == 'wait' and args:
                            budget = self._timing.setdefault('wait_requested', [0, 0.0, 0.0, 0.0])
                            budget[0] += 1
                            budget[1] += args[0]
                            budget[2] = max(budget[2], args[0])
                setattr(target, name, measured)

            for target, name, label in ((self.network, 'recv', 'recv'),
                    (self.network, 'send', 'send'), (self.network, 'wait_readable', 'wait'),
                    (self.peer, 'receive', 'peer_receive'), (self.peer, 'tick', 'peer_tick')):
                wrap(target, name, label)
            return result

        def _send_pending(self, datagrams):
            if _cancel.is_set():
                raise Cancelled()
            result = super()._send_pending(datagrams)
            now = time.monotonic()
            global _experiment
            if _experiment == 'memory_trace' and not self._memory_traces:
                class RetainedTrace(io.StringIO):
                    def close(self):
                        pass
                for owner, attribute in ((self.tracer, '_f'), (radio, '_trace')):
                    if owner is not None and getattr(owner, attribute, None) is not None:
                        original = getattr(owner, attribute)
                        original.flush()
                        memory = RetainedTrace()
                        setattr(owner, attribute, memory)
                        self._memory_traces.append((owner, attribute, original, memory))
                ui.report('EXPERIMENT_APPLIED=memory_trace')
                _experiment = None
            if (folder / 'enable_profile').exists() and self.network.participants and not self._profile_finished:
                if self._live_profile is None:
                    self._live_profile = cProfile.Profile()
                    self._profile_started = now
                    self._live_profile.enable()
                elif now - self._profile_started >= 15:
                    self._live_profile.disable()
                    self._live_profile.dump_stats(str(run_folder / 'live.pstats'))
                    self._profile_finished = True
                    ui.report('LIVE_PROFILE_READY: 15 seconds of connected host processing saved.')
            if now - self._timing_at >= 5:
                row = {'seconds': now - self._timing_at, 'state': self.session.trade.state,
                    'calls': {name: {'count': count, 'total_ms': total * 1000, 'max_ms': peak * 1000, 'cpu_ms': cpu * 1000}
                              for name, (count, total, peak, cpu) in self._timing.items()}}
                text = json.dumps(row, sort_keys=True)
                self._timing_file.write(text + '\n')
                ui.report('HOST_TIMING=' + text)
                self._timing.clear()
                self._timing_at = now
            return result

        def _hosting_instructions(self):
            ui.report('ANDROID_HOST_READY: open FireRed/LeafGreen wireless Trade Center and choose JOIN.')
            return super()._hosting_instructions()

        def _idle_timeout_seconds(self):
            return 600

    output = lambda *parts: ui.report(' '.join(map(str, parts)))
    log = ConsoleLog(False, output=output)
    original_affinity = os.sched_getaffinity(0)
    selected_cpu = android_compat.performance_cpu()
    if selected_cpu is not None:
        os.sched_setaffinity(0, {selected_cpu})
        ui.report('PYTHON_CPU_AFFINITY=' + str(selected_cpu))
    radio = esp32.Radio(AndroidStream(usb), on_lost=lambda error: cancel())
    app = None
    original_interval = sys.getswitchinterval()
    sys.setswitchinterval(0.001)
    ui.report('Python thread switch interval: 1 ms (live-traffic experiment)')
    try:
        for attempt in range(10):
            try:
                radio.info = esp32.Info.parse(radio.request(esp32.CMD_HELLO, b'', esp32.MSG_INFO, timeout=1))
                break
            except esp32.RadioError:
                if attempt == 9:
                    raise
        assert radio.info.version == esp32.PROTOCOL_VERSION
        ui.report('Radio: ' + radio.info.text)
        esp32_wlan.use(radio=radio)
        if esp32.firmware_version(radio.info) >= esp32.ALIVE_FIRMWARE:
            threading.Thread(target=radio._keep_alive, daemon=True).start()
        threading.Thread(target=radio._poll_status, daemon=True).start()
        run_config = config.TradeRunConfig(
            config.DEFAULT_TRAINER,
            config.TradePlan(party_paths=(str(offer),), trade_slot=0,
                             output_path=str(run_folder / 'received.pk3'), trust_pia=True),
            config.LdnConfig(phy='esp32', keys_path=str(keys), capture_path=str(run_folder / 'host.jsonl')),
            config.HostOptions(channel=11, max_participants=6, skip_preflight=True,
                               skip_encryption=True, accept_decrypted_ccmp=True,
                               native_nonce_sequence=True, session_response_first=True))
        app = AndroidHost(run_config, log=log)
        try:
            app.run()
        except Cancelled:
            ui.report('Trade stopped by request.')
        commits = getattr(getattr(app.session, 'trade', None), 'commits', 0)
        ui.report('ANDROID_TRADE_RESULT=' + json.dumps({'commits': commits,
                  'run_folder': str(run_folder), 'received': (run_folder / 'received.pk3').exists()}))
    finally:
        sys.setswitchinterval(original_interval)
        if app is not None:
            for owner, attribute, original, memory in getattr(app, '_memory_traces', []):
                setattr(owner, attribute, original)
                original.write(memory.getvalue())
                original.flush()
                if owner is app.tracer:
                    original.close()
            profiler = getattr(app, '_live_profile', None)
            if profiler is not None:
                profiler.disable()
                profiler.dump_stats(str(run_folder / 'live.pstats'))
            timing_file = getattr(app, '_timing_file', None)
            if timing_file is not None:
                timing_file.close()
        try:
            ui.report('FINAL_BOARD_STATUS=' + radio.status())
            radio.stop()
        except Exception as error:
            ui.report('Radio cleanup: ' + repr(error))
        radio.close()
        os.sched_setaffinity(0, original_affinity)
        wlan.set_factory(None)
        esp32_wlan._radio = None
        os.environ.pop('POKELDN_ESP32_TRACE', None)
