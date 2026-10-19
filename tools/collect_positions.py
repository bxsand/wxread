"""Collect real reading positions by turning pages in the weread reader.

Each page turn makes the reader POST /web/book/read; every captured payload is a
consistent (c, ci, co, sm, pr) tuple that can be replayed at random.

usage: python tools/collect_positions.py --book <id> --count 8 --interval 34
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cdp  # noqa: E402

NEXT_BTN = ".renderTarget_pager_button_right"


async def drain(c, until: float, found: dict) -> None:
    while time.time() < until:
        try:
            ev = await asyncio.wait_for(c._ws.recv(), timeout=max(0.1, until - time.time()))
        except asyncio.TimeoutError:
            return
        data = json.loads(ev)
        if data.get("method") != "Network.requestWillBeSent":
            continue
        req = data.get("params", {}).get("request", {})
        if "/web/book/read" not in req.get("url", ""):
            continue
        body = req.get("postData")
        if not body:
            continue
        try:
            pd = json.loads(body)
        except ValueError:
            continue
        key = (pd.get("c"), pd.get("co"))
        found[key] = {k: pd.get(k) for k in ("c", "ci", "co", "pr", "sm")}


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default="35032fe071f6e47f3506809")
    ap.add_argument("--count", type=int, default=8)
    ap.add_argument("--interval", type=int, default=34)
    ap.add_argument("--out", default="capture/positions.json")
    a = ap.parse_args()

    page = cdp.pick_page(9333, "weread")
    found: dict = {}
    async with cdp.CDP(page["webSocketDebuggerUrl"], timeout=120) as c:
        await c.send("Network.enable")
        await c.send("Page.navigate", {"url": f"https://weread.qq.com/web/reader/{a.book}"})
        await asyncio.sleep(10)
        await drain(c, time.time() + 3, found)
        print("after load:", len(found), flush=True)

        for i in range(a.count):
            r = await c.js(f"""(()=>{{const b=document.querySelector('{NEXT_BTN}');if(!b)return 'no button';b.click();return 'ok';}})()""")
            print(f"turn {i+1}: {r}", flush=True)
            await drain(c, time.time() + a.interval, found)
            print(f"   collected={len(found)}", flush=True)
            if len(found) >= a.count:
                break

    items = list(found.values())
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(items, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("saved", len(items), "positions ->", a.out)
    for it in items:
        print("  ci=%-4s co=%-6s pr=%-4s c=%s" % (it.get("ci"), it.get("co"), it.get("pr"), it.get("c")))
    return 0 if items else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
