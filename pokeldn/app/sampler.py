"""Where a phone's Python spends its time: every 10 ms, the innermost pokeldn, gui, flet, ldn, trio or
web-server frame of each thread, counted per thread, written to a file every 10 s, busiest first. On a
phone the run shares the interface's interpreter (examples/ios/README.md, examples/android/README.md)."""
import collections
import sys
import threading
import time

OURS = ("/pokeldn/", "/gui/", "/flet", "/ldn/", "/trio/", "/uvicorn", "/starlette")


def _where(frame) -> str:
    stack = []
    while frame is not None:
        stack.append(frame)
        frame = frame.f_back
    for f in stack:   # innermost first
        path = f.f_code.co_filename
        if any(part in path for part in OURS):
            return f"{path.rsplit('/app', 1)[-1]}:{f.f_lineno} {f.f_code.co_name}"
    return f"{stack[0].f_code.co_filename.rsplit('/', 1)[-1]}:{stack[0].f_lineno} {stack[0].f_code.co_name}"


def start(path: str, every: float = 0.01, write_every: float = 10.0, prepare=None) -> None:
    """Never on Android: a frame the sampler drops last may free a Java object on its thread, and
    Chaquopy aborts the app (JNI DeleteRef, JNIEnv from another thread), attached or not."""
    counts = collections.Counter()

    def sample():
        if prepare is not None:
            prepare()
        last, names = time.monotonic(), {}
        while True:
            time.sleep(every)
            names.update({t.ident: t.name for t in threading.enumerate()})
            me = threading.get_ident()
            for ident, frame in sys._current_frames().items():
                if ident != me:
                    counts[(names.get(ident, str(ident)), _where(frame))] += 1
            if time.monotonic() - last >= write_every:
                last = time.monotonic()
                with open(path, "w") as out:
                    for (thread, place), n in counts.most_common(80):
                        out.write(f"{n:7d}  {thread:24.24}  {place}\n")

    threading.Thread(target=sample, name="profile", daemon=True).start()


def trace_updates(path: str, write_every: float = 10.0) -> None:
    """Every Flet patch the interface computes: how often, how long, for which control type, called
    from which gui function, written to `path` every 10 s, costliest first. It runs on the updating
    thread itself, so it is safe where `start` is not (Chaquopy, examples/android/README.md)."""
    from flet.messaging import session
    totals = collections.Counter()
    counts = collections.Counter()
    state = {"last": time.monotonic()}
    patch = session.Session.patch_control

    def caller() -> str:
        frame = sys._getframe(2)
        while frame is not None:
            if "/gui/" in frame.f_code.co_filename:
                return f"{frame.f_code.co_filename.rsplit('/gui/', 1)[-1]}:{frame.f_lineno} {frame.f_code.co_name}"
            frame = frame.f_back
        return "flet"

    def traced(self, control, *args, **kwargs):
        start = time.perf_counter()
        try:
            return patch(self, control, *args, **kwargs)
        finally:
            key = (type(control).__name__, caller())
            totals[key] += time.perf_counter() - start
            counts[key] += 1
            if time.monotonic() - state["last"] >= write_every:
                state["last"] = time.monotonic()
                with open(path, "w") as out:
                    for k, seconds in totals.most_common(40):
                        if k[0] != "Page notify":
                            out.write(f"{seconds:8.2f} s {counts[k]:6d}x  {k[0]:20.20}  {k[1]}\n")
                    for k, n in counts.most_common():
                        if k[0] == "Page notify":
                            out.write(f"  notify {n:6d}x  {k[1]}\n")

    session.Session.patch_control = traced

    # What makes Flet re-diff the whole page: the page property whose change queued it.
    from flet.controls.page import Page
    notify = Page._Page__notify

    def notified(self, name, value):
        key = ("Page notify", f"{name} <- {caller()}")
        counts[key] += 1
        totals[key] += 0.0
        return notify(self, name, value)

    Page._Page__notify = notified

    # The events the browser sends: each one ends in an automatic update of the nearest isolated control.
    dispatch = session.Session.dispatch_event

    async def dispatched(self, control_id, event_name, event_data, *args, **kwargs):
        control = self.index.get(control_id) if hasattr(self, "index") else None
        key = ("Page notify", f"event {type(control).__name__ if control is not None else control_id}.{event_name}")
        counts[key] += 1
        totals[key] += 0.0
        return await dispatch(self, control_id, event_name, event_data, *args, **kwargs)

    session.Session.dispatch_event = dispatched
