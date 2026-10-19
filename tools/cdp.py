"""Minimal Chrome DevTools Protocol driver (no external deps beyond `websockets`).

Attaches to an already-running browser that was started with
--remote-debugging-port=<PORT>. Nothing is launched here: on Windows the
DSH sandbox blocks Chromium's mojo named-pipe setup, so the browser must be
started by the user outside the sandbox.
"""
from __future__ import annotations

import asyncio
import base64
import json
import sys
import time
import urllib.request
from typing import Any

DEFAULT_PORT = 9333


def http_json(path: str, port: int = DEFAULT_PORT, timeout: float = 8.0) -> Any:
    url = f"http://127.0.0.1:{port}{path}"
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def version(port: int = DEFAULT_PORT) -> dict:
    return http_json("/json/version", port)


def targets(port: int = DEFAULT_PORT) -> list[dict]:
    return http_json("/json/list", port)


def pages(port: int = DEFAULT_PORT) -> list[dict]:
    return [t for t in targets(port) if t.get("type") == "page"]


def pick_page(port: int = DEFAULT_PORT, match: str | None = None) -> dict:
    ps = pages(port)
    if not ps:
        raise RuntimeError("no page targets; open a tab in the browser")
    if match:
        hit = [p for p in ps if match in (p.get("url") or "") or match in (p.get("title") or "")]
        if hit:
            return hit[0]
    return ps[0]


class CDP:
    def __init__(self, ws_url: str, timeout: float = 30.0):
        self.ws_url = ws_url
        self.timeout = timeout
        self._ws = None
        self._id = 0
        self.events: list[dict] = []

    async def __aenter__(self) -> "CDP":
        from websockets.asyncio.client import connect
        self._ws = await connect(self.ws_url, max_size=64 * 1024 * 1024, open_timeout=self.timeout)
        return self

    async def __aexit__(self, *exc) -> None:
        if self._ws is not None:
            await self._ws.close()

    async def send(self, method: str, params: dict | None = None, session_id: str | None = None) -> dict:
        self._id += 1
        mid = self._id
        msg = {"id": mid, "method": method, "params": params or {}}
        if session_id:
            msg["sessionId"] = session_id
        assert self._ws is not None
        await self._ws.send(json.dumps(msg))
        deadline = time.time() + self.timeout
        while True:
            left = max(0.1, deadline - time.time())
            raw = await asyncio.wait_for(self._ws.recv(), timeout=left)
            data = json.loads(raw)
            if data.get("id") == mid:
                if "error" in data:
                    raise RuntimeError(f"{method} failed: {data['error']}")
                return data.get("result", {})
            if "method" in data:
                self.events.append(data)

    # ---- page helpers -------------------------------------------------
    async def js(self, expr: str, await_promise: bool = True) -> Any:
        res = await self.send("Runtime.evaluate", {
            "expression": expr,
            "returnByValue": True,
            "awaitPromise": await_promise,
            "userGesture": True,
        })
        if res.get("exceptionDetails"):
            raise RuntimeError(json.dumps(res["exceptionDetails"], ensure_ascii=False)[:2000])
        return res.get("result", {}).get("value")

    async def goto(self, url: str, wait: float = 2.5) -> None:
        await self.send("Page.enable")
        await self.send("Page.navigate", {"url": url})
        await asyncio.sleep(wait)

    async def shot(self, path: str, full: bool = False) -> str:
        params: dict = {"format": "png"}
        if full:
            params["captureBeyondViewport"] = True
        res = await self.send("Page.captureScreenshot", params)
        with open(path, "wb") as f:
            f.write(base64.b64decode(res["data"]))
        return path

    async def url(self) -> str:
        return await self.js("location.href") or ""

    async def text(self, limit: int = 4000) -> str:
        t = await self.js("document.body ? document.body.innerText : ''") or ""
        return t[:limit]

    async def click(self, selector: str = "", text: str = "", index: int = 0) -> dict:
        """Click an element by CSS selector or by visible text. Uses real mouse events."""
        js_find = f"""
        (() => {{
          let els = [];
          const sel = {json.dumps(selector)};
          const txt = {json.dumps(text)};
          if (sel) {{
            els = Array.from(document.querySelectorAll(sel));
          }} else if (txt) {{
            const all = Array.from(document.querySelectorAll('a,button,[role=button],input,summary,span,div,li'));
            els = all.filter(e => (e.innerText || e.value || '').trim().includes(txt) &&
                                  e.offsetParent !== null);
            // prefer the smallest / deepest matching node
            els.sort((a, b) => (a.innerText || '').length - (b.innerText || '').length);
          }}
          const el = els[{index}];
          if (!el) return {{ok: false, count: els.length}};
          el.scrollIntoView({{block: 'center', inline: 'center'}});
          const r = el.getBoundingClientRect();
          return {{ok: true, count: els.length, x: r.left + r.width / 2, y: r.top + r.height / 2,
                   tag: el.tagName, label: (el.innerText || el.value || el.getAttribute('aria-label') || '').slice(0, 120)}};
        }})()
        """
        info = await self.js(js_find)
        if not info or not info.get("ok"):
            return {"clicked": False, **({"count": info.get("count")} if info else {})}
        x, y = info["x"], info["y"]
        for kind in ("mouseMoved", "mousePressed", "mouseReleased"):
            p = {"type": kind, "x": x, "y": y, "button": "left", "clickCount": 1}
            await self.send("Input.dispatchMouseEvent", p)
        return {"clicked": True, **{k: info[k] for k in ("tag", "label")}}

    async def type_text(self, selector: str, value: str, enter: bool = False) -> bool:
        ok = await self.js(f"""
        (() => {{
          const el = document.querySelector({json.dumps(selector)});
          if (!el) return false;
          el.focus();
          el.value = {json.dumps(value)};
          el.dispatchEvent(new Event('input', {{bubbles: true}}));
          el.dispatchEvent(new Event('change', {{bubbles: true}}));
          return true;
        }})()
        """)
        if enter:
            await self.key("Enter")
        return bool(ok)

    async def key(self, key: str, code: str | None = None) -> None:
        base = {"key": key, "code": code or key, "windowsVirtualKeyCode": _vk(key)}
        await self.send("Input.dispatchKeyEvent", {"type": "keyDown", **base})
        await self.send("Input.dispatchKeyEvent", {"type": "keyUp", **base})

    async def scroll(self, dy: int = 800) -> None:
        await self.js(f"window.scrollBy(0, {dy})")
        await asyncio.sleep(0.4)

    async def cookies(self, urls: list[str] | None = None) -> list[dict]:
        res = await self.send("Network.getCookies", {"urls": urls} if urls else {})
        return res.get("cookies", [])


_VK = {"Enter": 13, "Tab": 9, "Escape": 27, "ArrowDown": 40, "ArrowUp": 38, " ": 32}


def _vk(key: str) -> int:
    return _VK.get(key, ord(key.upper()[0]) if key else 0)


def run(coro):
    return asyncio.run(coro)
