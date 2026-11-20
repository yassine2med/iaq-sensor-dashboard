"""Write sensors.csv and sensors_with_errors.csv in this folder (invented readings, hourly for three days)."""

import math
import random
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
random.seed(5)
rows = ["timestamp,room,co2_ppm,humidity_pct"]
start = datetime(2026, 9, 14, 6)
rooms = {"Office 101": (0.8, 45), "Conference 1": (2.2, 42), "Classroom 2": (1.6, 58), "Lobby": (0.5, 34), "Server Closet": (0.1, 24)}
for room, (occupancy, rh) in rooms.items():
    for i in range(3 * 24):
        t = start + timedelta(hours=i)
        busy = 1 if 8 <= t.hour < 17 else 0
        co2 = 420 + busy * occupancy * 380 * (1 + 0.2 * math.sin(i / 3)) + random.uniform(-15, 15)
        if room == "Classroom 2":
            co2 += busy * 80
        hum = rh + 4 * math.sin(i / 6) + random.uniform(-2, 2)
        if room == "Classroom 2" and busy:
            hum += 8
        rows.append(f"{t.isoformat()},{room},{round(co2)},{round(hum, 1)}")
(HERE / "sensors.csv").write_text("\n".join(rows) + "\n")
bad = rows[:4] + ["2026-09-14T09:00:00,Lobby,abc,40", "yesterday,Lobby,500,40", "2026-09-14T10:00:00,,500,40",
                  "2026-09-14T11:00:00,Lobby,99999,40", "2026-09-14T12:00:00,Lobby,600,140"]
(HERE / "sensors_with_errors.csv").write_text("\n".join(bad) + "\n")
print("wrote sensors.csv and sensors_with_errors.csv")
