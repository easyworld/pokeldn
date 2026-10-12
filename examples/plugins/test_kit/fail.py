"""Fails on purpose."""
import argparse
import sys

import testkit_common as kit


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--how", choices=("error", "exit"), default="error")
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    kit.say("About to fail on purpose.")
    if args.how == "exit":
        sys.exit(3)
    raise RuntimeError("The Test Kit failed on purpose. This is what a failing plugin looks like.")
