"""IoT simulator: sends HMAC-signed readings to the API exactly like an ESP32 would.
Everything it sends is SIMULATED data. Standard library only.

    python iot/simulator/simulate.py --scenario demo          # soil drying + ghala humidity rising
    python iot/simulator/simulate.py --scenario ghala-humid --interval 2
    python iot/simulator/simulate.py --scenario soil-normal --loop

Devices and secrets match the demo seed (python -m app.seed)."""

import argparse
import hashlib
import hmac
import json
import math
import random
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

DEVICES = {
    "soil": ("ESP32-SOIL-01", "dev-soil-secret"),
    "ghala": ("ESP32-GHALA-01", "dev-ghala-secret"),
}


def curve(start: float, end: float, n: int, i: int, noise: float = 0.3) -> float:
    return round(start + (end - start) * i / max(1, n - 1) + random.uniform(-noise, noise), 1)


SCENARIOS = {
    "soil-drying": ("soil", lambda i, n: {"soil_moisture_pct": curve(31, 20, n, i), "soil_temperature_c": curve(24, 30, n, i)}),
    "soil-normal": ("soil", lambda i, n: {"soil_moisture_pct": curve(32, 31, n, i), "soil_temperature_c": round(25 + 2 * math.sin(i / 3), 1)}),
    "ghala-humid": ("ghala", lambda i, n: {"temperature_c": curve(26, 31, n, i), "humidity_pct": curve(62, 84, n, i)}),
    "ghala-normal": ("ghala", lambda i, n: {"temperature_c": curve(24.5, 25, n, i), "humidity_pct": curve(59, 60, n, i)}),
}
SCENARIOS["demo"] = None  # soil-drying then ghala-humid


def sign(secret: str, device_id: str, ts: str, readings: dict, seq: int) -> str:
    payload = json.dumps({"device_id": device_id, "ts": ts, "readings": readings, "seq": seq}, sort_keys=True, separators=(",", ":"))
    return "hmac-sha256:" + hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def send(api: str, kind: str, readings: dict, seq: int) -> None:
    device_id, secret = DEVICES[kind]
    readings = {k: float(v) for k, v in readings.items()}  # the API signs values as floats
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    body = {"device_id": device_id, "ts": ts, "readings": readings, "seq": seq, "sig": sign(secret, device_id, ts, readings, seq)}
    req = urllib.request.Request(f"{api}/iot/readings", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"[SIMULATED] {device_id} seq={seq} {readings} -> {resp.status} {resp.read().decode()}")
    except urllib.error.HTTPError as e:
        print(f"[SIMULATED] {device_id} seq={seq} -> {e.code} {e.read().decode()}")


def run(api: str, name: str, steps: int, interval: float) -> None:
    kind, fn = SCENARIOS[name]
    # Sequence numbers must always increase per device (replay protection).
    seq_base = int(time.time())
    for i in range(steps):
        send(api, kind, fn(i, steps), seq_base + i)
        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="demo")
    parser.add_argument("--steps", type=int, default=12)
    parser.add_argument("--interval", type=float, default=1.0, help="seconds between readings")
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()
    while True:
        for name in (["soil-drying", "ghala-humid"] if args.scenario == "demo" else [args.scenario]):
            run(args.api, name, args.steps, args.interval)
        if not args.loop:
            break


if __name__ == "__main__":
    main()
