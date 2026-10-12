"""Pretends to run a session of several trades; the app ticks one off per [done] line."""
import argparse
import time

import testkit_common as kit


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trades", type=int, default=3)
    parser.add_argument("--pause", type=float, default=2)
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    from pokeldn.ldn import show_done
    done = 0
    try:
        kit.say(f"Simulating {args.trades} trades, {args.pause:g} s each. Press Stop to end early.")
        for n in range(1, args.trades + 1):
            for step in ("waiting for the partner", "exchanging", "saving"):
                kit.say(f"trade {n} of {args.trades}: {step}")
                time.sleep(args.pause / 3)
            show_done()
            done = n
        kit.say("All simulated trades done.")
    except KeyboardInterrupt:
        kit.say(f"Stopped by the app after {done} trade(s).")
