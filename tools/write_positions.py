"""把 capture/positions.json 里的位置池写回 config.py 的 positions 段。

只替换 `positions = [...]` 这一块，不动 book/chapter/data，可重复执行。

用法：
    python tools/write_positions.py [--config config.py] [--positions capture/positions.json]
"""
from __future__ import annotations

import argparse
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_block(items: list[dict]) -> str:
    lines = [
        "# 阅读位置池：每组都来自一次真实翻页请求的 (c, ci, co, sm, pr)",
        "# main.py 按 (ci, co) 排序后用游标顺序推进，5% 概率回退一页",
        "positions = [",
    ]
    seen = set()
    for it in items:
        key = (it["c"], it["co"])
        if key in seen:
            continue
        seen.add(key)
        body = json.dumps({k: it[k] for k in ("c", "ci", "co", "pr", "sm")}, ensure_ascii=False)
        lines.append(f"    {body},")
    lines.append("]")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(ROOT, "config.py"))
    ap.add_argument("--positions", default=os.path.join(ROOT, "capture", "positions.json"))
    a = ap.parse_args()

    items = json.load(open(a.positions, encoding="utf-8"))
    items.sort(key=lambda p: (p.get("ci", 0), p.get("co", 0)))
    block = build_block(items)

    src = open(a.config, encoding="utf-8").read()
    new, n = re.subn(r"positions = \[.*?\n\]", lambda m: block, src, count=1, flags=re.S)
    if n == 0:
        print("!! config.py 中未找到 positions 段")
        return 1

    open(a.config, "w", encoding="utf-8", newline="\n").write(new)
    print(f"写入 {len(items)} 组位置 -> {a.config}")
    for it in items:
        print(f"  ci={it['ci']:<4} co={it['co']:<6} pr={it['pr']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
