from datetime import datetime
from pathlib import Path
from xml.dom import minidom

import pytest

from iaqdash.__main__ import main
from iaqdash.analysis import Reading, episodes, html_dashboard, load, summary

EX = Path(__file__).resolve().parent.parent / "examples"
GOOD = str(EX / "sensors.csv")
BAD = str(EX / "sensors_with_errors.csv")


def r(hour, co2, rh=45, room="A", day=14):
    return Reading(datetime(2026, 9, day, hour), room, co2, rh)


@pytest.fixture(scope="module")
def data():
    return load(GOOD)[0]


def test_sample_loads_clean():
    items, problems = load(GOOD)
    assert len(items) == 360 and problems == []


def test_bad_rows_are_described():
    items, problems = load(BAD)
    assert len(items) == 3 and len(problems) == 5
    assert any("co2_ppm or humidity_pct is not a number" in p for p in problems)
    assert any("bad timestamp 'yesterday'" in p for p in problems)
    assert any("room is empty" in p for p in problems)
    assert any("co2_ppm 99999" in p for p in problems)
    assert any("humidity_pct 140" in p for p in problems)


def test_missing_column(tmp_path):
    f = tmp_path / "s.csv"
    f.write_text("timestamp,room\n2026-09-14T06:00:00,A\n")
    with pytest.raises(ValueError, match="co2_ppm"):
        load(str(f))


def test_summary_has_room_per_row_and_worst_first(data):
    s = summary(data)
    assert len(s) == 5 and s[0]["room"] == "Conference 1"
    pcts = [x["co2_over_pct"] for x in s]
    assert pcts == sorted(pcts, reverse=True)


def test_summary_math():
    s = summary([r(8, 800), r(9, 1200), r(10, 1000), r(11, 400, rh=70)])[0]
    assert s["readings"] == 4 and s["co2_avg"] == 850 and s["co2_max"] == 1200
    assert s["co2_over_pct"] == 25 and s["rh_out_pct"] == 25


def test_limit_is_strictly_above():
    assert summary([r(8, 1000)])[0]["co2_over_pct"] == 0


def test_server_closet_is_dry(data):
    closet = next(x for x in summary(data) if x["room"] == "Server Closet")
    assert closet["rh_out_pct"] > 90


def test_episodes_group_consecutive_readings():
    eps = episodes([r(8, 1100), r(9, 1300), r(10, 900), r(11, 1200)])
    assert [(e["readings"], e["peak"]) for e in eps] == [(2, 1300), (1, 1200)]
    assert eps[0]["start"].hour == 8 and eps[0]["end"].hour == 9


def test_episode_open_at_end_is_kept():
    assert len(episodes([r(8, 900), r(9, 1500)])) == 1


def test_episodes_are_per_room():
    eps = episodes([r(8, 1100, room="A"), r(9, 1100, room="B")])
    assert len(eps) == 2


def test_humidity_episodes():
    eps = episodes([r(8, 500, rh=20), r(9, 500, rh=25), r(10, 500, rh=45)], "rh")
    assert len(eps) == 1 and eps[0]["peak"] == 20


def test_sample_conference_has_daily_episodes(data):
    eps = [e for e in episodes(data) if e["room"] == "Conference 1"]
    assert len(eps) == 3


def test_html_is_wellformed_and_escaped():
    page = html_dashboard([r(8, 800, room="A & <B>"), r(9, 1200, room="A & <B>")])
    assert "A &amp; &lt;B&gt;" in page and "<B>" not in page
    minidom.parseString(page.split("<!doctype html>\n", 1)[1].replace("<meta charset=\"utf-8\">", "<meta charset=\"utf-8\"/>")
                        .replace("<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">",
                                 "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"/>"))


def test_cli_summary_alerts_html(tmp_path, capsys):
    assert main(["summary", GOOD]) == 0
    assert main(["alerts", GOOD]) == 0
    assert main(["alerts", GOOD, "--metric", "rh"]) == 0
    out = tmp_path / "d.html"
    assert main(["html", GOOD, "-o", str(out)]) == 0
    assert "<svg" in out.read_text(encoding="utf-8")
    assert "Conference 1" in capsys.readouterr().out


def test_cli_errors():
    assert main(["summary", "nope.csv"]) == 2
    assert main(["summary", BAD, "--strict"]) == 1
    assert main(["summary", BAD]) == 0
