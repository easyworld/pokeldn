"""A plugin tool among FireRed and LeafGreen's own."""
import argparse

import testkit_common as kit


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trainer", default="")
    return parser


if __name__ == "__main__":
    kit.say(f"Hello {build_parser().parse_args().trainer or 'trainer'}! This tool comes from the Plugin Test Kit.")
