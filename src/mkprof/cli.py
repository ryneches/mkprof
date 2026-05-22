"""
mkprof.cli — entry point for the `mkprof` command.
"""

import sys
from pathlib import Path


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="mkprof",
        description="Companion tool for mkdocs-material notebook blogs.",
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        type=Path,
        default=None,
        help="Path to mkdocs.yml (default: mkdocs.yml in the current directory)",
    )

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("build", help="Convert notebooks and build the site (default)")
    subparsers.add_parser("serve", help="Convert notebooks and start mkdocs serve")
    subparsers.add_parser("convert", help="Convert notebooks only; skip running mkdocs")

    init_p = subparsers.add_parser("init", help="Scaffold a new mkprof/mkdocs site")
    init_p.add_argument(
        "dir",
        nargs="?",
        default=".",
        metavar="DIR",
        help="Directory to scaffold (default: current directory)",
    )

    args = parser.parse_args()

    if args.command == "init":
        from mkprof.init_cmd import run_init
        run_init(Path(args.dir))
        return

    # All other sub-commands (and the bare `mkprof` default) need config.
    from mkprof.config import resolve

    try:
        cfg = resolve(args.config)
    except FileNotFoundError as exc:
        print(f"mkprof: {exc}", file=sys.stderr)
        sys.exit(1)

    mode_map = {None: "build", "build": "build", "serve": "serve", "convert": "convert"}
    mode = mode_map[args.command]

    from mkprof.build import BuildApp
    BuildApp(cfg=cfg, mode=mode).run()


if __name__ == "__main__":
    main()
