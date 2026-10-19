"""Poll a GitHub Actions run until it finishes. Prints status transitions.

usage: python tools/wait_run.py <run_id> [--interval 30] [--max-min 45]
"""
from __future__ import annotations

import argparse
import time

import requests

API = "https://api.github.com/repos/bxsand/wxread/actions/runs/{}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--interval", type=int, default=30)
    ap.add_argument("--max-min", type=int, default=45)
    a = ap.parse_args()

    deadline = time.time() + a.max_min * 60
    last = None
    while time.time() < deadline:
        try:
            d = requests.get(API.format(a.run_id), timeout=20).json()
        except Exception as exc:  # noqa: BLE001
            print("poll error:", exc, flush=True)
            time.sleep(a.interval)
            continue
        state = (d.get("status"), d.get("conclusion"))
        if state != last:
            print(f"{time.strftime('%H:%M:%S')} {state[0]} / {state[1]}", flush=True)
            last = state
        if state[0] == "completed":
            print("CONCLUDED:", state[1], flush=True)
            return 0
        time.sleep(a.interval)
    print("TIMEOUT waiting", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
