import cProfile
import io
import json
from pathlib import Path
import pstats
import time
from types import SimpleNamespace


def measure(folder, capture, keys):
    import ldn
    from pokeldn.frlg import config
    from pokeldn.frlg.link.host_session import HostSession
    from pokeldn.frlg.link.host_beacon import build_trade_app_data
    from pokeldn.frlg.save.mon import Mon
    from pokeldn.ldn.host_pia import HostPeerProtocol

    records = [json.loads(line) for line in capture.read_text().splitlines() if line.strip()]
    advert = next(r for r in records if r.get('kind') == 'advert')
    frame = ldn.AdvertisementFrame(ldn.KeyDerivation(ldn.load_keys(str(keys)), 3), 3)
    frame.decode(bytes.fromhex(advert['hex']))
    incoming = [r for r in records if r.get('kind') == 'udp_in']
    assert incoming
    local_ip = incoming[0]['dst']
    guest_ip = incoming[0]['src']
    network = SimpleNamespace(ssid=frame.network_id.ssid, our_ip=local_ip,
        our_mac=bytes(frame.payload.participants[0].mac_address), max_participants=6,
        participants=[(1, guest_ip, b'', b'')], broadcast=local_ip.rsplit('.', 1)[0] + '.255',
        SCENE_ID=frame.network_id.scene_id, set_application_data=lambda data: None)
    plan = config.TradePlan(party_paths=(str(folder / 'offer.pk3'),), trade_slot=0, trust_pia=True)
    session = HostSession([Mon.from_file(folder / 'offer.pk3')], plan=plan, profile=config.DEFAULT_TRAINER)
    _, active = build_trade_app_data(config.DEFAULT_TRAINER, session.rfu.host_session_id)
    peer = HostPeerProtocol(network, config.DEFAULT_TRAINER, session, active,
        native_nonce_sequence=True, session_response_first=True)
    virtual = [1000.0]
    original_clock = time.monotonic
    profiler = cProfile.Profile()
    emitted = 0
    started = time.perf_counter()
    try:
        time.monotonic = lambda: virtual[0]
        profiler.enable()
        peer.on_participant_joined()
        next_tick = virtual[0]
        first = incoming[0]['ts']
        for record in incoming:
            at = 1000 + record['ts'] - first
            while next_tick <= at:
                virtual[0] = next_tick
                emitted += len(peer.tick(next_tick))
                next_tick += 1 / 59.727
            virtual[0] = at
            peer.receive(bytes.fromhex(record['hex']), record['src'], now=at)
            emitted += len(peer.drain())
    finally:
        profiler.disable()
        time.monotonic = original_clock
    seconds = time.perf_counter() - started
    result = {'incoming': len(incoming), 'outgoing': emitted, 'seconds': seconds,
        'recorded_seconds': incoming[-1]['ts'] - first, 'state': session.trade.state,
        'commits': session.trade.commits}
    out = io.StringIO()
    pstats.Stats(profiler, stream=out).strip_dirs().sort_stats('cumtime').print_stats(30)
    profiler.dump_stats(str(folder / 'replay.pstats'))
    (folder / 'replay-profile.txt').write_text(json.dumps(result) + '\n' + out.getvalue())
    return result, out.getvalue()


def run(usb, ui):
    import android_compat
    android_compat.install()
    folder = Path(str(ui.getFilesDir().getAbsolutePath())) / 'trade'
    captures = sorted(folder.glob('run-*/host.jsonl'))
    if not captures:
        raise ValueError('No private host capture is available to replay')
    capture = captures[-1]
    ui.report('REPLAY_START: recorded host logic, no Switch connection needed')
    result, stats = measure(folder, capture, folder / 'prod.keys')
    ui.report('REPLAY_RESULT=' + json.dumps(result))
    ui.report('REPLAY_PROFILE\n' + stats)
