"""Create/overwrite a repository secret through the GitHub web form.

The form encrypts the value client-side (libsodium) on submit, so typing into the
textarea and clicking "Add secret" is the reliable path without extra deps.

usage: python tools/gh_secret.py --name WXREAD_CURL_BASH --file capture/curl_bash.txt
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cdp  # noqa: E402

REPO = "bxsand/wxread"


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--file", required=True)
    a = ap.parse_args()

    value = open(a.file, encoding="utf-8").read().strip()

    v = cdp.version(9333)
    async with cdp.CDP(v["webSocketDebuggerUrl"], timeout=60) as b:
        await b.send("Target.createTarget",
                     {"url": f"https://github.com/{REPO}/settings/secrets/actions/new", "background": False})
    await asyncio.sleep(6)

    page = [p for p in cdp.pages(9333) if "secrets/actions/new" in p["url"]][0]
    async with cdp.CDP(page["webSocketDebuggerUrl"], timeout=120) as c:
        await c.click(selector="#secret_name")
        await c.send("Input.insertText", {"text": a.name})
        await c.click(selector="#secret_value")
        await c.send("Input.insertText", {"text": value})
        await asyncio.sleep(0.5)
        print("name:", await c.js("document.querySelector('#secret_name').value"))
        print("value len:", await c.js("document.querySelector('#secret_value').value.length"))
        r = await c.js("""(()=>{const b=Array.from(document.querySelectorAll('button[type=submit], button')).find(x=>/Add secret/i.test(x.innerText));if(!b)return 'nf';b.click();return 'ok';})()""")
        print("submit:", r)
        await asyncio.sleep(6)
        print("url:", await c.url())
        t = await c.js("document.body.innerText") or ""
        print("added:", "added" in t.lower() or a.name in t)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
