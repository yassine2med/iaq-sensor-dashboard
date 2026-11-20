"""Command line: python -m iaqdash summary|alerts|html SENSORS.csv"""

from __future__ import annotations

import argparse
import sys

from .analysis import CO2_LIMIT, RH_RANGE, episodes, html_dashboard, load, summary


def main(argv: list[str] | None = None) -> int:
    """Return 0 on success, 1 when rows were skipped with --strict, 2 for an unreadable file."""
    parser = argparse.ArgumentParser(prog="iaqdash", description="CO2 and humidity dashboard from sensor CSV")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, text in (("summary", "per-room numbers, worst room first"), ("alerts", "periods above the CO2 limit or outside the humidity range"),
                       ("html", "write a one-page HTML dashboard")):
        p = sub.add_parser(name, help=text)
        p.add_argument("file")
        p.add_argument("--strict", action="store_true", help="exit 1 when any row was skipped")
        if name == "alerts":
            p.add_argument("--metric", choices=("co2", "rh"), default="co2")
        if name == "html":
            p.add_argument("-o", "--output", required=True)
    args = parser.parse_args(argv)
    try:
        items, problems = load(args.file)
    except FileNotFoundError:
        print(f"File not found: {args.file}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"Cannot read {args.file}: {exc}", file=sys.stderr)
        return 2
    for p in problems:
        print(f"skipped {p}", file=sys.stderr)
    if args.command == "summary":
        print(f"{'room':<14} {'n':>4} {'CO2 avg':>8} {'CO2 max':>8} {'>' + str(CO2_LIMIT):>6} {'RH avg':>7} {'RH out':>7}")
        for s in summary(items):
            print(f"{s['room']:<14} {s['readings']:>4} {s['co2_avg']:>8.0f} {s['co2_max']:>8.0f} {s['co2_over_pct']:>5.0f}% "
                  f"{s['rh_avg']:>6.0f}% {s['rh_out_pct']:>6.0f}%")
    elif args.command == "alerts":
        eps = episodes(items, args.metric)
        unit = "ppm" if args.metric == "co2" else "%"
        for e in eps:
            print(f"{e['room']:<14} {e['start']:%Y-%m-%d %H:%M} to {e['end']:%H:%M}  {e['readings']:>2} readings  peak {e['peak']:.0f} {unit}")
        limit = f"above {CO2_LIMIT} ppm" if args.metric == "co2" else f"outside {RH_RANGE[0]:g} to {RH_RANGE[1]:g}%"
        print(f"{len(eps)} period(s) {limit}")
    else:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(html_dashboard(items))
        print(f"Dashboard for {len(items)} readings written to {args.output}")
    return 1 if (args.strict and problems) else 0


if __name__ == "__main__":
    sys.exit(main())
