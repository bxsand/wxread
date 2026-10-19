"""Commit one file to the fork via the GitHub web editor, robustly.

Each file gets a fresh tab (so a stale beforeunload guard cannot block the
renderer), the editor content is replaced, and the result is verified by
comparing the committed blob through the API.

usage: python tools/gh_commit.py --path main.py --file capture/new_main.py --message "..."
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cdp  # noqa: E402

REPO = "bxsand/wxread"
BRANCH = "main"


async def open_tab(browser, url: str) -> str:
    t = await browser.send("Target.createTarget", {"url": url, "background": False})
    return t["targetId"]


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--message", required=True)
    a = ap.parse_args()

    text = open(a.file, encoding="utf-8").read()
    edit_url = f"https://github.com/{REPO}/edit/{BRANCH}/{a.path}"

    v = cdp.version(9333)
    async with cdp.CDP(v["webSocketDebuggerUrl"], timeout=60) as b:
        tid = await open_tab(b, edit_url)

    await asyncio.sleep(3)
    page = [p for p in cdp.pages(9333) if edit_url.replace("https://", "") in p["url"] or p["id"] == tid]
    if not page:
        print("!! tab not found")
        return 1
    target = page[0]

    async with cdp.CDP(target["webSocketDebuggerUrl"], timeout=180) as c:
        for _ in range(40):
            if await c.js("!!document.querySelector('.cm-content')"):
                break
            await asyncio.sleep(0.5)
        else:
            print("!! editor never appeared")
            return 1
        await asyncio.sleep(1.5)

        await c.click(selector=".cm-content")
        await asyncio.sleep(0.3)
        for kind in ("keyDown", "keyUp"):
            await c.send("Input.dispatchKeyEvent", {"type": kind, "key": "a", "code": "KeyA",
                                                    "modifiers": 2, "windowsVirtualKeyCode": 65})
        await asyncio.sleep(0.4)
        await c.send("Input.insertText", {"text": text})
        await asyncio.sleep(2)

        await c.js("window.scrollTo(0,0)")
        await asyncio.sleep(0.6)

        btn = await c.js("""(()=>{const b=Array.from(document.querySelectorAll('button')).find(x=>/Commit changes/i.test(x.innerText)&&x.offsetParent);if(!b)return 'null';const q=b.getBoundingClientRect();return JSON.stringify({x:q.x+q.width/2,y:q.y+q.height/2});})()""")
        if btn == "null":
            print("!! commit button not found")
            return 1
        import json as _j
        p = _j.loads(btn)
        for kind in ("mouseMoved", "mousePressed", "mouseReleased"):
            await c.send("Input.dispatchMouseEvent", {"type": kind, "x": p["x"], "y": p["y"],
                                                      "button": "left", "clickCount": 1})
        ok = False
        for _ in range(30):
            if await c.js("!!document.querySelector('#commit-message-input')"):
                ok = True
                break
            await asyncio.sleep(0.5)
        if not ok:
            print("!! commit dialog did not open")
            return 1

        await c.click(selector="#commit-message-input")
        for kind in ("keyDown", "keyUp"):
            await c.send("Input.dispatchKeyEvent", {"type": kind, "key": "a", "code": "KeyA",
                                                    "modifiers": 2, "windowsVirtualKeyCode": 65})
        await c.send("Input.insertText", {"text": a.message})
        await asyncio.sleep(0.6)
        r = await c.js("""(()=>{const b=Array.from(document.querySelectorAll('button')).filter(x=>x.offsetParent&&x.closest('[role=dialog]')).find(x=>/^Commit changes$/.test(x.innerText.trim()));if(!b)return 'nf';b.click();return 'ok';})()""")
        print("confirm:", r)
        await asyncio.sleep(6)

    # verify through the API
    for _ in range(20):
        resp = requests.get(f"https://api.github.com/repos/{REPO}/contents/{a.path}",
                            headers={"Accept": "application/vnd.github.raw", "Cache-Control": "no-cache"},
                            timeout=30)
        if resp.status_code == 200:
            remote = resp.text.replace("\r\n", "\n").strip("\n")
            if remote == text.strip("\n"):
                print("VERIFIED identical,", len(remote.encode()), "bytes")
                return 0
        await asyncio.sleep(3)
    print("!! remote content still differs after commit")
    return 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
