"""CLI wrapper around cdp.py:  python tools/bcd.py <cmd> [args]

Commands:
  status [port]                  list tabs + browser version
  goto <url> [port]              navigate current page
  newtab <url> [port]            open a new tab
  text [limit] [port]            body innerText of current page
  url [port]                     current page URL + title
  eval <js> [port]               evaluate JS, print value
  shot <path> [port]             screenshot to png
  html <path> [port]             dump outerHTML to file
  click <selector> [port]        click by CSS selector
  clicktext <text> [port]        click by visible text
  type <selector> <value> [port] type into input
  key <Key> [port]               press a key
  scroll <dy> [port]             scroll
  wait <ms> [port]               sleep
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cdp  # noqa: E402


async def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    cmd, rest = argv[0], argv[1:]

    if cmd == "status":
        port = int(rest[0]) if rest else cdp.DEFAULT_PORT
        v = cdp.version(port)
        print("browser:", v.get("Browser"))
        print("ws:", v.get("webSocketDebuggerUrl"))
        for p in cdp.targets(port):
            print(f"  [{p.get('type')}] {p.get('title','')[:60]!r} {p.get('url','')[:100]}")
        return 0

    def take_port(args: list[str]) -> tuple[list[str], int]:
        if args and args[-1].isdigit() and len(args[-1]) == 4:
            return args[:-1], int(args[-1])
        return args, cdp.DEFAULT_PORT

    rest, port = take_port(rest)
    page = cdp.pick_page(port, os.environ.get("BCD_MATCH") or None)
    async with cdp.CDP(page["webSocketDebuggerUrl"]) as c:
        if cmd == "goto":
            await c.goto(rest[0])
            print("->", await c.url())
        elif cmd == "newtab":
            print("use: curl http://127.0.0.1:%d/json/new?%s (POST)" % (port, rest[0] if rest else ""))
            return 2
        elif cmd == "text":
            limit = int(rest[0]) if rest else 4000
            print(await c.text(limit))
        elif cmd == "url":
            print(await c.url())
            print("title:", await c.js("document.title"))
        elif cmd == "eval":
            if not rest:
                print("need js expression")
                return 1
            v = await c.js(" ".join(rest))
            print(v if isinstance(v, str) else repr(v))
        elif cmd == "shot":
            path = rest[0] if rest else "shot.png"
            await c.shot(path)
            print("saved", path)
        elif cmd == "html":
            path = rest[0] if rest else "page.html"
            h = await c.js("document.documentElement.outerHTML")
            with open(path, "w", encoding="utf-8") as f:
                f.write(h or "")
            print("saved", path, len(h or ""))
        elif cmd == "click":
            print(await c.click(selector=rest[0]))
        elif cmd == "clicktext":
            print(await c.click(text=" ".join(rest)))
        elif cmd == "type":
            print(await c.type_text(rest[0], " ".join(rest[1:])))
        elif cmd == "key":
            await c.key(rest[0])
        elif cmd == "scroll":
            await c.scroll(int(rest[0]) if rest else 800)
        elif cmd == "wait":
            await asyncio.sleep((int(rest[0]) if rest else 1000) / 1000)
        else:
            print(__doc__)
            return 1
    return 0


if __name__ == "__main__":
    sys.path.insert(0, __file__.rsplit("\\", 1)[0])
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
