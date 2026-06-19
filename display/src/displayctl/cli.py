from __future__ import annotations

import argparse

from . import goto, move, move_here, select, spawn


def main() -> None:
    parser = argparse.ArgumentParser(prog="displayctl")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("left")
    subparsers.add_parser("right")
    subparsers.add_parser("reduce")
    subparsers.add_parser("quad")
    subparsers.add_parser("tile")
    subparsers.add_parser("distribute")

    center_parser = subparsers.add_parser("center")
    center_parser.add_argument("--size", type=float)
    center_parser.add_argument("--reverse", "-r", action="store_true")

    cycle_parser = subparsers.add_parser("cycle")
    cycle_parser.add_argument("--third", "-3", action="store_true")

    split_parser = subparsers.add_parser("split")
    split_parser.add_argument("--frontmost-right", "--right", "-r", action="store_true")
    split_parser.add_argument("--frame", "--framed", action="store_true")

    spawn_parser = subparsers.add_parser("spawn-new")
    spawn_parser.add_argument("app_name")
    spawn_parser.add_argument("spawn_script", nargs="?", default="")

    goto_parser = subparsers.add_parser("goto")
    goto_parser.add_argument("app_name")

    select_parser = subparsers.add_parser("select")
    select_parser.add_argument("app_name")

    move_here_parser = subparsers.add_parser("move-here")
    move_here_parser.add_argument("app_name")

    args = parser.parse_args()

    if args.command == "left":
        move.left()
    elif args.command == "right":
        move.right()
    elif args.command == "reduce":
        move.reduce()
    elif args.command == "quad":
        move.quad()
    elif args.command == "tile":
        move.tile()
    elif args.command == "distribute":
        move.distribute()
    elif args.command == "center":
        move.center(size=args.size, reverse=args.reverse)
    elif args.command == "cycle":
        move.cycle(target_index=3 if args.third else 2)
    elif args.command == "split":
        move.split(frontmost_right=args.frontmost_right, frame=args.frame)
    elif args.command == "spawn-new":
        spawn.run(args.app_name, args.spawn_script)
    elif args.command == "goto":
        goto.run(args.app_name)
    elif args.command == "select":
        select.run(args.app_name)
    elif args.command == "move-here":
        move_here.run(args.app_name)
    else:
        parser.error(f"unknown command: {args.command}")


if __name__ == "__main__":
    main()
