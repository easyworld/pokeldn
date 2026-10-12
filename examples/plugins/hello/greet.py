"""The tool's script: the app imports it for build_parser(), then runs it."""
import argparse


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--greeting", default="Hello")
    parser.add_argument("--trainer", default="trainer")
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    print(f"{args.greeting}, {args.trainer}! This line comes from a plugin.")
