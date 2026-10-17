"""Pop-ups a program shows in the app (docs/gui.md, Pop-ups): an acknowledgement, with one button, a
confirmation, with agree and disagree, or a choice among several options; Esc or a click outside dismisses
the last two.

Opening one never waits: `acknowledge`, `confirm` and `choose` return the pop-up's id at once, and the player's answer comes
later as a callback, which may fire at any time. Callbacks run on the pop-up thread (the one reading the app's
answers) unless `set_dispatcher` hands them to the program's own loop. `cancel(id)` closes a pop-up; no callback
of a pop-up fires once `cancel`, or a pop-up opened again under its id, has returned, but one an earlier answer
already handed to the dispatcher still runs.

A process the app started (POKELDN_POPUPS set) sends its pop-ups as `[popup]` lines on stdout and reads the
answers on stdin (pokeldn.app.runner); code in the app talks to the app's manager directly (`attach`,
pokeldn.app.popups). With no app, a pop-up is a log line, no answer comes (`available`), and it never counts toward
LIMIT.
"""

import itertools
import json
import os
import sys
import threading
import traceback
import uuid

PREFIX = "[popup] "
LIMIT = 32                          # pop-ups a program may hold unanswered
TONES = ("info", "warning", "error")
ANSWERS = {"ack": ("ack",), "confirm": ("agree", "disagree", "dismiss"), "choose": ("dismiss",)}
CHOICES = 8                         # options a choice may offer; each one's answer is its index, "0".."7"

_lock = threading.RLock()           # orders the messages of one id, whatever thread sends them
_live: dict[str, "_Popup"] = {}     # id -> the pop-up open under it, until answered or cancelled
_serial = itertools.count(1)        # tells a pop-up from the one opened again under its id
_sink = None                        # the app's manager, for code in the app (`attach`)
_dispatch = None                    # the program's own loop (`set_dispatcher`)


class _Popup:
    __slots__ = ("n", "kind", "callbacks")

    def __init__(self, n, kind, callbacks):
        self.n, self.kind, self.callbacks = n, kind, callbacks


def acknowledge(title: str, text: str = "", *, id: str | None = None, label: str = "OK", on_ack=None,
                tone: str = "info") -> str:
    """Shows `text` under `title` with one button, `label`; -> the pop-up's id. `on_ack()` fires when the player
    presses it, or presses Esc or clicks outside. See `confirm` for the rest."""
    return _open("ack", id, {"title": title, "text": text, "label": label}, {"ack": on_ack}, tone)


def confirm(title: str, text: str, agree: str, disagree: str, *, id: str | None = None, on_agree=None,
            on_disagree=None, on_dismiss=None, tone: str = "info") -> str:
    """Asks with two buttons, `agree` and `disagree`, the caller's labels; -> the pop-up's id. Each fires its
    callback, if given; Esc and a click outside fire `on_dismiss`.

    `id` names the pop-up; one opened under the id of a pop-up still open replaces it in place, its callbacks
    dropped. `tone` (info, warning or error) picks its icon. A program holding LIMIT pop-ups unanswered gets RuntimeError."""
    if not (agree and disagree):
        raise ValueError("a confirmation names its agree and disagree buttons")
    return _open("confirm", id, {"title": title, "text": text, "agree": agree, "disagree": disagree},
                 {"agree": on_agree, "disagree": on_disagree, "dismiss": on_dismiss}, tone)


def choose(title: str, text: str, options, *, id: str | None = None, on_choice=None, on_dismiss=None,
           tone: str = "info") -> str:
    """Asks the player to pick one of `options`, 2 to CHOICES labels, each a button; -> the pop-up's id.
    `on_choice(index)` fires with the index of the one pressed; Esc and a click outside fire `on_dismiss`.
    See `confirm` for `id` and `tone`."""
    options = [str(o) for o in options]
    if not 2 <= len(options) <= CHOICES or not all(options):
        raise ValueError(f"a choice offers 2 to {CHOICES} named options")
    callbacks = {str(i): (None if on_choice is None else lambda i=i: on_choice(i)) for i in range(len(options))}
    return _open("choose", id, {"title": title, "text": text}, {**callbacks, "dismiss": on_dismiss}, tone,
                 options=options)


def cancel(id: str) -> None:
    """Closes the pop-up `id`; its callbacks never fire. An answered or unknown id is nothing to cancel."""
    with _lock:
        popup = _live.pop(str(id), None)
        if popup is None:
            return
        _send({"op": "cancel", "id": str(id)})


def available() -> bool:
    """Whether an app is there to show pop-ups and answer them: in the app, or in a run it started."""
    return _sink is not None or bool(os.environ.get("POKELDN_POPUPS"))


def set_dispatcher(dispatch) -> None:
    """`dispatch(callback)` runs each callback where the program wants it, such as its own event loop or a queue its
    loop polls; None runs them on the pop-up thread again. A callback that raises prints its traceback."""
    global _dispatch
    _dispatch = dispatch


def _open(kind, id, fields, callbacks, tone, **extra):
    if tone not in TONES:
        raise ValueError(f"a pop-up's tone is one of {', '.join(TONES)}, not {tone!r}")
    with _lock:
        id = uuid.uuid4().hex if id is None else str(id)
        if _live.pop(id, None) is None and len(_live) >= LIMIT:
            raise RuntimeError(f"{LIMIT} pop-ups wait for an answer already: cancel one first")
        popup = _Popup(next(_serial), kind, callbacks)
        if available():                 # with no app, nothing ever answers one
            _live[id] = popup
        _send({"op": "open", "id": id, "n": popup.n, "kind": kind, **{k: str(v) for k, v in fields.items()},
               "tone": tone, **extra})
    return id


def answered(message: dict) -> None:
    """The app's answer to one of the pop-ups: {"id", "n", "answer"}. It fires that pop-up's callback, unless the
    pop-up was cancelled, replaced or answered since."""
    id, n, answer = str(message.get("id")), message.get("n"), message.get("answer")
    with _lock:
        popup = _live.get(id)
        if popup is None or popup.n != n or answer not in popup.callbacks:
            return
        del _live[id]
    _fire(popup.callbacks.get(answer))


def receive(text: str) -> bool:
    """A line the app sent on stdin: -> whether it was an answer (`answered`)."""
    message = read(text)[1]
    if message is None or "answer" not in message:
        return False
    answered(message)
    return True


def _fire(callback):
    if callback is None:
        return

    def run():
        try:
            callback()
        except Exception:
            traceback.print_exc()
    (_dispatch or (lambda fn: fn()))(run)


# The messages, as lines: `[popup]` and a JSON object.

def line(message: dict) -> str:
    return PREFIX + json.dumps(message)


def read(text: str) -> tuple[str, dict | None]:
    """-> (what came before it, the message) for a line carrying a `[popup]` message, wherever in the line another
    thread's print left it; (text, None) for any other line."""
    at = text.find(PREFIX)
    if at < 0:
        return text, None
    try:
        message = json.loads(text[at + len(PREFIX):])
    except ValueError:
        return text, None
    return (text[:at], message) if isinstance(message, dict) else (text, None)


def _send(message):
    if _sink is not None:
        _sink(message)
    elif os.environ.get("POKELDN_POPUPS"):
        sys.stdout.write(line(message) + "\n")      # one write: a line another thread prints cannot split it
        sys.stdout.flush()
    elif message["op"] == "open":
        buttons = {"confirm": lambda: f"{message['agree']} / {message['disagree']}",
                   "choose": lambda: " / ".join(message["options"]),
                   "ack": lambda: message["label"]}[message["kind"]]()
        print(f"[pop-up] {message['title']}: {message['text']} [{buttons}]", flush=True)


def attach(sink) -> None:
    """Code in the app: `sink(message)` takes each message to the app's manager, which answers through
    `answered` (gui.app); None detaches it."""
    global _sink
    _sink = sink
