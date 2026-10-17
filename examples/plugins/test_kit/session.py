"""Pretends to run a session of several trades: asks how many with a choice, shows them under a progress bar,
and the app ticks one off per [done] line."""
import argparse
import queue
import time

import testkit_common as kit


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trades", type=int, default=3)
    parser.add_argument("--pause", type=float, default=2)
    return parser


def ask(trades: int) -> int:
    """The player's pick: all the trades, one, or none; all of them with no app to ask."""
    from pokeldn import popup
    if not popup.available():
        return trades
    answers = queue.Queue()
    popup.set_dispatcher(answers.put)
    popup.choose("Simulated session", f"The kit can pretend {trades} trades.",
                 [f"Trade {trades}", "Trade one", "Leave"],
                 on_choice=lambda i: kit.say(f"chose option {i + 1}") or setattr(ask, "picked", (trades, 1, 0)[i]),
                 on_dismiss=lambda: setattr(ask, "picked", 0))
    while not hasattr(ask, "picked"):
        try:
            answers.get(timeout=0.2)()
        except queue.Empty:
            pass
    return ask.picked


if __name__ == "__main__":
    args = build_parser().parse_args()
    from pokeldn import progress
    from pokeldn.ldn import show_done
    done = 0
    try:
        trades = ask(args.trades)
        kit.say(f"Simulating {trades} trades, {args.pause:g} s each. Press Stop to end early.")
        for n in range(1, trades + 1):
            for step in ("waiting for the partner", "exchanging", "saving"):
                kit.say(f"trade {n} of {trades}: {step}")
                time.sleep(args.pause / 3)
            show_done()
            done = n
            progress.show(done, trades, "Simulated trades", unit="items")
        kit.say("All simulated trades done.")
    except KeyboardInterrupt:
        kit.say(f"Stopped by the app after {done} trade(s).")
