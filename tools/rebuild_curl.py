"""Rebuild the WXREAD_CURL_BASH value from a live browser session.

Captures one /web/book/read request, combines its headers with the full cookie
jar (incl. HttpOnly), and writes a single-line curl that config.convert() parses.

usage: python tools/rebuild_curl.py [--book 35032fe071f6e47f3506809]
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

DROP = {"cookie", "content-length", "host", "accept-encoding", "x-wrpa-0",
        "sentry-trace", "baggage", "priority", "dnt", "connection"}
ADD = {"origin": "https://weread.qq.com", "accept-language": "zh-CN,zh;q=0.9,en;q=0.8"}
WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default="35032fe071f6e47f3506809")
    a = ap.parse_args()

    v = cdp.version(9333)
    async with cdp.CDP(v["webSocketDebuggerUrl"], timeout=60) as b:
        t = await b.send("Target.createTarget",
                         {"url": f"https://weread.qq.com/web/reader/{a.book}", "background": False})
        print("tab:", t["targetId"])
    await asyncio.sleep(7)

    page = cdp.pick_page(9333, "weread")
    hits: dict = {}
    cookies: list = []

    async with cdp.CDP(page["webSocketDebuggerUrl"], timeout=120) as c:
        await c.send("Network.enable")
        await c.send("Page.bringToFront")
        # reader posts a read on load; reload to force one more if needed
        for attempt in range(2):
            await c.send("Page.reload")
            end = time.time() + 12
            while time.time() < end:
                try:
                    ev = await asyncio.wait_for(c._ws.recv(), timeout=max(0.1, end - time.time()))
                except asyncio.TimeoutError:
                    break
                d = json.loads(ev)
                if d.get("method") != "Network.requestWillBeSent":
                    continue
                req = d["params"].get("request", {})
                if "/web/book/read" in req.get("url", "") and req.get("headers"):
                    hits[req.get("url")] = req
            if hits:
                break
        cookies = await c.cookies(["https://weread.qq.com/web/book/read"])

    if not hits:
        print("no read request captured (session may be expired)")
        return 1

    req = list(hits.values())[-1]
    jar = "; ".join(f"{x['name']}={x['value']}" for x in sorted(cookies, key=lambda x: x["name"]))
    headers = {k: v for k, v in req["headers"].items() if k.lower() not in DROP}
    for k, val in ADD.items():
        headers.setdefault(k, val)
    headers["cookie"] = jar

    order = ["accept", "accept-language", "content-type", "origin", "referer",
             "user-agent", "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform"]
    ordered: dict = {}
    for key in order:
        for k, val in headers.items():
            if k.lower() == key:
                ordered[k] = val
    for k, val in headers.items():
        if k not in ordered:
            ordered[k] = val

    parts = [f"curl '{req['url']}'"]
    for k, val in ordered.items():
        parts.append(f"-H '{k}: {val}'")
    curl = " ".join(parts)

    out = os.path.join(WS, "capture", "curl_bash.txt")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8", newline="\n").write(curl)

    names = [x["name"] for x in cookies]
    print("headers:", len(ordered), [k.lower() for k in ordered])
    print("cookies:", len(cookies), "wr_skey" in names, "wr_vid" in names, "wr_rt" in names)
    print("length:", len(curl), "-> saved", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
