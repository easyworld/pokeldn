"""Progress a run reports to the app (docs/plugins.md, A tool's script): `show` prints
`[progress] DONE TOTAL UNIT TITLE`, which the session panel draws as a bar with the rate and the time
left, in place of a log line. `Rate` is the app's side: the rate over the last RATE_WINDOW seconds.
"""
import collections
import math
import re
import time

PREFIX = "[progress] "
UNITS = ("bytes", "items")
EVERY = 0.25                 # seconds between two lines of one title; the last one always prints
RATE_WINDOW = 30.0
LINE = re.compile(r"^\[progress\] (\d+) (\d+) (bytes|items) (.+)$")

_shown: dict[str, float] = {}


def show(done: int, total: int, title: str, unit: str = "bytes") -> None:
    """`done` of `total` `unit` (bytes or items) of the work `title` names, such as "Sending the
    update". Call it as often as the work moves; at most four lines a second reach the app."""
    if unit not in UNITS:
        raise ValueError(f"a progress unit is one of {', '.join(UNITS)}, not {unit!r}")
    done, total, title = int(done), int(total), " ".join(str(title).split())
    if not title or done < 0 or total < 0:
        raise ValueError("progress needs a title and counts of zero or more")
    now = time.monotonic()
    if done < total and now - _shown.get(title, -math.inf) < EVERY:
        return
    _shown[title] = now
    print(f"{PREFIX}{done} {total} {unit} {title}", flush=True)


def read(line: str) -> tuple[int, int, str, str] | None:
    """(done, total, unit, title) from a `[progress]` line, or None."""
    match = LINE.match(line.strip())
    return (int(match[1]), int(match[2]), match[3], match[4]) if match else None


class Rate:
    """One title's rate and time left, from the counts it reported."""

    def __init__(self):
        self.samples: collections.deque = collections.deque()

    def add(self, done: int, now: float) -> None:
        if self.samples and done < self.samples[-1][1]:     # the work started again
            self.samples.clear()
        self.samples.append((now, done))
        while len(self.samples) > 2 and now - self.samples[1][0] >= RATE_WINDOW:
            self.samples.popleft()

    @property
    def per_second(self) -> float:
        """Units a second over the window; 0 until two counts a second apart."""
        if len(self.samples) < 2:
            return 0.0
        (t0, d0), (t1, d1) = self.samples[0], self.samples[-1]
        return (d1 - d0) / (t1 - t0) if t1 - t0 >= 1 else 0.0

    def left(self, total: int) -> float | None:
        """Seconds until `total` at the current rate, or None while there is no rate."""
        rate = self.per_second
        return (total - self.samples[-1][1]) / rate if rate > 0 else None
