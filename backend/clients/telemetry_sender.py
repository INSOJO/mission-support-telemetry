import time
import random
import requests
import argparse
from datetime import datetime, timezone

API_URL = "http://127.0.0.1:8000/telemetry"

parser = argparse.ArgumentParser(description="Telemetry simulator")
parser.add_argument(
    "--mission-id",
    required=True,
    help="Mission identifier (e.g. HASP-001, TEST-01)",
)
parser.add_argument(
    "--count",
    type=int,
    default=0,
    help="How many packets to send (0 = infinite)",
)
parser.add_argument(
    "--interval",
    type=float,
    default=2.0,
    help="Seconds between packets",
)

args = parser.parse_args()

MISSION_ID = args.mission_id

lat = 18.22
lon = -66.59
altitude = 1000.0  # meters


def build_packet():
    global lat, lon, altitude

    lat += random.uniform(-0.0001, 0.0001)
    lon += random.uniform(-0.0001, 0.0001)
    altitude += random.uniform(5.0, 15.0)

    return {
        "mission_id": MISSION_ID,
        "lat": lat,
        "lon": lon,
        "altitude_m": altitude,
        "timestamp": datetime.now(timezone.utc).isoformat(),

        "temperature_c": random.uniform(-10.0, 25.0),
        "pressure_hpa": random.uniform(850.0, 1020.0),
        "humidity_pct": random.uniform(20.0, 90.0),
    }


def main():
    sent = 0

    while True:
        packet = build_packet()
        try:
            response = requests.post(API_URL, json=packet)
            print("Sent:", packet)
            print("Server:", response.status_code, response.text)
        except Exception as e:
            print("Error sending telemetry:", e)

        sent += 1
        if args.count and sent >= args.count:
            break

        time.sleep(args.interval)


if __name__ == "__main__":
    main()
