# cli.py — `coesita` command-line interface.
#
# Subcommands:
#   coesita dashboard [--port 5050]          start the web dashboard
#   coesita run [--tier standard] [...]      run the full benchmark pipeline
#   coesita scan                             scan agent frameworks → JSON
#   coesita scenarios [--tier standard]      generate stress scenarios → JSON
#   coesita --version

from __future__ import annotations

import argparse
import json
import sys

from coesita import __version__
from coesita.benchmark_store import data_dir
from coesita.ftm_engine import DOMAINS, TIER_META


def _print_json(payload) -> None:
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _cmd_dashboard(args: argparse.Namespace) -> int:
    from coesita.dashboard import main as dashboard_main
    dashboard_main(port=args.port, host=args.host)
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    from coesita.benchmark_tester import run_full_pipeline
    summary = run_full_pipeline(tier=args.tier, domain=args.domain)
    _print_json(summary)
    print(f"\nResults saved under: {data_dir() / 'benchmark'}", file=sys.stderr)
    print("View them with: coesita dashboard  →  http://localhost:5050/benchmark",
          file=sys.stderr)
    return 0


def _cmd_scan(args: argparse.Namespace) -> int:
    from coesita.framework_scanner import run_scan
    extra = None
    if args.extra:
        with open(args.extra, encoding="utf-8") as f:
            extra = json.load(f)
    _print_json(run_scan(extra))
    return 0


def _cmd_scenarios(args: argparse.Namespace) -> int:
    from coesita.scenario_generator import run_generation
    _print_json(run_generation(tier=args.tier, domain=args.domain))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coesita",
        description=(
            "Coesita Benchmark — measure how well AI agents hold correct "
            "decisions under social pressure (FTM v2.2)."
        ),
    )
    parser.add_argument("--version", action="version", version=f"coesita {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_dash = sub.add_parser("dashboard", help="start the web dashboard (default port 5050)")
    p_dash.add_argument("--port", type=int, default=None)
    p_dash.add_argument("--host", default="0.0.0.0")
    p_dash.set_defaults(func=_cmd_dashboard)

    p_run = sub.add_parser(
        "run",
        help="run the full pipeline: scan frameworks → generate scenarios → test runners",
    )
    p_run.add_argument("--tier", choices=sorted(TIER_META), default="standard",
                       help="evaluation tier (default: standard, 30 scenarios)")
    p_run.add_argument("--domain", choices=DOMAINS, default=None,
                       help="restrict to one domain (default: all five)")
    p_run.set_defaults(func=_cmd_run)

    p_scan = sub.add_parser("scan", help="scan agent frameworks and print the registry JSON")
    p_scan.add_argument("--extra", metavar="FILE.json", default=None,
                        help="JSON file with extra framework entries to merge")
    p_scan.set_defaults(func=_cmd_scan)

    p_scen = sub.add_parser("scenarios", help="generate stress scenarios and print them as JSON")
    p_scen.add_argument("--tier", choices=sorted(TIER_META), default="standard")
    p_scen.add_argument("--domain", choices=DOMAINS, default=None)
    p_scen.set_defaults(func=_cmd_scenarios)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
