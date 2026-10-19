from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from headcount import __version__, generate, pipeline, report


def period_arg(value: str) -> pd.Period:
    try:
        return pd.Period(value, freq="M")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected a month like 2026-09, got {value!r}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="headcount",
        description="Quality checks and headcount statistics for HR and payroll exports.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="check the sources and build the Excel report")
    run.add_argument("--input", type=Path, default=Path("data/sample"), help="folder with exports")
    run.add_argument("--period", type=period_arg, required=True, help="month, e.g. 2026-09")
    run.add_argument("--out", type=Path, default=Path("reports"), help="output folder")
    run.add_argument(
        "--fail-on-errors",
        action="store_true",
        help="exit with code 1 if blocking anomalies are found",
    )

    gen = sub.add_parser("generate", help="write fictional sample exports")
    gen.add_argument("--out", type=Path, default=Path("data/sample"))
    gen.add_argument("--period", type=period_arg, required=True)
    gen.add_argument("--size", type=int, default=600, help="number of employees")
    gen.add_argument("--seed", type=int, default=42)
    return parser


def cmd_run(args: argparse.Namespace) -> int:
    result = pipeline.run(args.input, args.period)
    xlsx = report.write_report(result, args.out)
    csv = report.write_issues_csv(result, args.out)

    s = result.sources
    t = result.totals
    print(f"Period {s.period}: {len(s.employees)} HR rows, {len(s.payroll)} payroll rows")
    print(
        f"Anomalies: {result.errors} blocking, {result.warnings} warnings "
        f"-> {result.excluded_employees} employees excluded"
    )
    print(f"Headcount on {s.reference_date:%Y-%m-%d}: {int(t['headcount'])} ({t['fte']} FTE)")
    print(f"Report: {xlsx}")
    print(f"Anomalies list: {csv}")
    return 1 if args.fail_on_errors and result.errors else 0


def cmd_generate(args: argparse.Namespace) -> int:
    data = generate.generate(args.period, size=args.size, seed=args.seed)
    for path in generate.write_sources(data, args.out, args.period):
        print(f"wrote {path}")
    injected = ", ".join(f"{rule} x{n}" for rule, n in data.injected.items())
    print(f"injected anomalies: {injected}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "run":
            return cmd_run(args)
        return cmd_generate(args)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
