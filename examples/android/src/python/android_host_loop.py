import time

import trio

from pokeldn.app import runner, screen
from pokeldn.frlg.link.host_app import HOST_CONTROL_POLL_SECONDS
from pokeldn.frlg.link.host_beacon import NullBeaconInjector


async def wait_readable(app, timeout):
    started = time.monotonic()
    cpu_started = time.thread_time()
    with trio.move_on_after(max(0, timeout)):
        await trio.lowlevel.wait_readable(app.network._rx)
    elapsed = time.monotonic() - started
    stat = app._timing.setdefault('async_wait', [0, 0.0, 0.0, 0.0])
    stat[0] += 1
    stat[1] += elapsed
    stat[2] = max(stat[2], elapsed)
    stat[3] += time.thread_time() - cpu_started


async def protocol(self):
    joined_once = False
    rfu_ni_logged = False
    last_peer_activity = time.monotonic()
    while True:
        if self.injector.error is not None:
            raise RuntimeError(f"802.11 beacon injector stopped: {self.injector.error}")
        if self.network.participants and not joined_once:
            joined_once = True
            last_peer_activity = time.monotonic()
            self.peer.on_participant_joined()
            self.info("Switch joined the Linux LDN host successfully.")
        if joined_once and not self.network.participants:
            reason = self._absence_stop_reason(time.monotonic())
            if reason is not None:
                self.session.on_ldn_leave()
                self.info(reason)
                break

        received = self.network.recv()
        if received:
            last_peer_activity = time.monotonic()
        for datagram, src_ip in received:
            events = self.peer.receive(datagram, src_ip)
            self._log_protocol_events(events)
            self._send_pending(self.peer.drain())

        now = time.monotonic()
        idle_timeout = self._idle_timeout_seconds()
        if idle_timeout is not None and now - last_peer_activity >= idle_timeout:
            self.idle_timed_out = True
            self.info(f"No meaningful Switch traffic for {idle_timeout}s; stopping host.")
            break
        self._send_pending(self.peer.tick(now))
        self._log_activity_progress()
        self._poll_chat_file(now)
        if self.session.rfu.ni_complete and not rfu_ni_logged:
            rfu_ni_logged = True
            self.info(self._rfu_ready_message())
        if (self._activity().done and (
                not self.network.participants
                or (self._end_on_success() and self._activity_succeeded()))):
            self.info(self._completion_message())
            break
        timeout = self.peer.next_deadline(now, HOST_CONTROL_POLL_SECONDS)
        await wait_readable(self, timeout)

    return joined_once


def run(self):
    try:
        link_player = self._build_components()
        self._log_identity(link_player)
        self._show_screen()
        self.network.start(preflight=not self.options.skip_preflight)
        self.injector = NullBeaconInjector(channel=self.options.channel, log=self.log)
        self.injector.start()
        self.info(self._hosting_instructions())
        token = self.network._network._tap._token
        scopes = []

        async def cancellable():
            with trio.CancelScope() as scope:
                scopes.append(scope)
                return await protocol(self)
            raise KeyboardInterrupt   # the app's Stop: InProcess.stop treats it as a clean stop

        def stop():
            # This thread waits in from_thread.run, where InProcess.stop's injected KeyboardInterrupt
            # never lands: cancel the protocol on LDN's Trio thread instead.
            if scopes:
                trio.from_thread.run_sync(scopes[0].cancel, trio_token=token)

        runner.at_app_close(stop)
        try:
            return trio.from_thread.run(cancellable, trio_token=token)
        finally:
            runner._closing.remove(stop)
    finally:
        screen.drain()
        if self.injector is not None:
            self.injector.stop()
        if self.network is not None:
            self.network.stop()
        if self.tracer is not None:
            self.tracer.close()
