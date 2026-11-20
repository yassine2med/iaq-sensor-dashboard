"""Load indoor air quality readings, summarise them per room and find episodes above a limit."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from html import escape

CO2_LIMIT = 1000          # ppm; above this a room is poorly ventilated for its occupancy
CO2_PLAUSIBLE = (250, 10000)
RH_RANGE = (30.0, 60.0)   # percent; comfort and mould guidance
FIELDS = ("timestamp", "room", "co2_ppm", "humidity_pct")


@dataclass(frozen=True)
class Reading:
    when: datetime
    room: str
    co2: float
    rh: float


def load(path: str) -> tuple[list[Reading], list[str]]:
    """Read the CSV. Bad rows are skipped and described. Raises ValueError for missing columns."""
    items, problems = [], []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = [f for f in FIELDS if f not in (reader.fieldnames or [])]
        if missing:
            raise ValueError("missing column(s): " + ", ".join(missing))
        for n, row in enumerate(reader, start=2):
            room = (row["room"] or "").strip()
            try:
                when = datetime.fromisoformat((row["timestamp"] or "").strip())
            except ValueError:
                problems.append(f"row {n}: bad timestamp '{row['timestamp']}'")
                continue
            if not room:
                problems.append(f"row {n}: room is empty")
                continue
            try:
                co2, rh = float(row["co2_ppm"]), float(row["humidity_pct"])
            except (TypeError, ValueError):
                problems.append(f"row {n}: {room}: co2_ppm or humidity_pct is not a number")
                continue
            if not CO2_PLAUSIBLE[0] <= co2 <= CO2_PLAUSIBLE[1]:
                problems.append(f"row {n}: {room}: co2_ppm {co2:g} is outside {CO2_PLAUSIBLE[0]} to {CO2_PLAUSIBLE[1]}")
            elif not 0 <= rh <= 100:
                problems.append(f"row {n}: {room}: humidity_pct {rh:g} is outside 0 to 100")
            else:
                items.append(Reading(when, room, co2, rh))
    return items, problems


def by_room(items: list[Reading]) -> dict[str, list[Reading]]:
    rooms: dict[str, list[Reading]] = {}
    for r in sorted(items, key=lambda r: r.when):
        rooms.setdefault(r.room, []).append(r)
    return rooms


def summary(items: list[Reading]) -> list[dict]:
    """One dict per room, worst CO2 first: counts, averages, peak and percent of readings out of range."""
    out = []
    for room, rs in by_room(items).items():
        n = len(rs)
        out.append({
            "room": room, "readings": n,
            "co2_avg": sum(r.co2 for r in rs) / n, "co2_max": max(r.co2 for r in rs),
            "co2_over_pct": 100 * sum(r.co2 > CO2_LIMIT for r in rs) / n,
            "rh_avg": sum(r.rh for r in rs) / n,
            "rh_out_pct": 100 * sum(not RH_RANGE[0] <= r.rh <= RH_RANGE[1] for r in rs) / n,
        })
    return sorted(out, key=lambda d: (-d["co2_over_pct"], -d["co2_max"], d["room"]))


def episodes(items: list[Reading], metric: str = "co2") -> list[dict]:
    """Runs of consecutive readings out of range. metric is 'co2' (above the limit) or 'rh' (outside the range)."""
    def bad(r: Reading) -> bool:
        return r.co2 > CO2_LIMIT if metric == "co2" else not RH_RANGE[0] <= r.rh <= RH_RANGE[1]

    out = []
    for room, rs in by_room(items).items():
        run: list[Reading] = []
        for r in rs + [None]:
            if r is not None and bad(r):
                run.append(r)
                continue
            if run:
                key = (lambda x: x.co2) if metric == "co2" else (lambda x: abs(x.rh - sum(RH_RANGE) / 2))
                peak = max(run, key=key)
                out.append({"room": room, "start": run[0].when, "end": run[-1].when, "readings": len(run),
                            "peak": peak.co2 if metric == "co2" else peak.rh})
                run = []
    return sorted(out, key=lambda e: (e["start"], e["room"]))


def _line(values: list[float], lo: float, hi: float, w: int = 300, h: int = 70) -> str:
    if len(values) < 2 or hi == lo:
        return ""
    pts = " ".join(f"{i * w / (len(values) - 1):.1f},{h - (min(max(v, lo), hi) - lo) / (hi - lo) * h:.1f}"
                   for i, v in enumerate(values))
    return f'<polyline fill="none" stroke="#2b6cb0" stroke-width="1.5" points="{pts}"/>'


def html_dashboard(items: list[Reading], title: str = "Indoor air quality") -> str:
    """A single self-contained HTML page: one card per room with a CO2 chart and its numbers."""
    cards = []
    rooms = by_room(items)
    for s in summary(items):
        rs = rooms[s["room"]]
        co2 = [r.co2 for r in rs]
        hi = max(max(co2), CO2_LIMIT * 1.2)
        limit_y = 70 - (CO2_LIMIT - 400) / (hi - 400) * 70
        chart = (f'<svg viewBox="0 0 300 70" width="100%" height="70" role="img" aria-label="CO2 over time">'
                 f'<line x1="0" x2="300" y1="{limit_y:.1f}" y2="{limit_y:.1f}" stroke="#c53030" stroke-dasharray="4 3"/>'
                 f'{_line(co2, 400, hi)}</svg>')
        flag = "warn" if s["co2_over_pct"] > 0 or s["rh_out_pct"] > 0 else "ok"
        cards.append(
            f'<section class="{flag}"><h2>{escape(s["room"])}</h2>{chart}'
            f'<p>CO2 average {s["co2_avg"]:.0f} ppm, peak {s["co2_max"]:.0f} ppm, '
            f'{s["co2_over_pct"]:.0f}% of readings above {CO2_LIMIT}.</p>'
            f'<p>Humidity average {s["rh_avg"]:.0f}%, {s["rh_out_pct"]:.0f}% outside {RH_RANGE[0]:g} to {RH_RANGE[1]:g}%.</p></section>')
    return ("<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{escape(title)}</title><style>body{{font-family:sans-serif;margin:24px;background:#f7fafc;color:#1a202c}}"
            "main{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}"
            "section{background:#fff;border:1px solid #cbd5e0;border-left:6px solid #38a169;padding:12px;border-radius:6px}"
            "section.warn{border-left-color:#dd6b20}h1{font-size:22px}h2{font-size:16px;margin:0 0 8px}p{margin:6px 0;font-size:14px}"
            "</style></head><body>"
            f"<h1>{escape(title)}</h1><p>{len(items)} readings in {len(rooms)} rooms. Dashed line: {CO2_LIMIT} ppm CO2.</p>"
            f"<main>{''.join(cards)}</main></body></html>\n")
