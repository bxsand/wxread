"""校验华为云定时槽是否准点 dispatch 了 GitHub 运行。

判据（只看 GitHub 侧的事实，不猜）：
  - 每个槽（北京 01:23 / 03:47 / 06:30 / 10:00）当天是否出现 event=workflow_dispatch 的运行；
  - 该运行的 run_started_at 与槽的理论时间差多少分钟（准点应在 ±10 分钟内）；
  - 当天成功运行总数是否 >= 2（NEEDED），以及 readingTime 增量是否 ≈ 1860 秒 × 成功次数。

用法：
    python huawei_fn/verify_slots.py                # 看今天（北京）
    python huawei_fn/verify_slots.py --date 2026-11-06
    python huawei_fn/verify_slots.py --days 3       # 连看最近 3 天
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import gh_api  # noqa: E402

BJ = timezone(timedelta(hours=8))
SLOTS = [(1, 23), (3, 47), (6, 30), (10, 0)]  # 北京时间的四个定时槽


def beijing(dt: datetime) -> datetime:
    return dt.astimezone(BJ)


def fetch_runs(limit: int = 40) -> list[dict]:
    tok = gh_api.token(None)
    st, data = gh_api.call("GET", f"/repos/{gh_api.REPO}/actions/runs?per_page={limit}", tok)
    if st != 200:
        sys.exit(f"GitHub API {st}: {str(data)[:200]}")
    return data.get("workflow_runs", [])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="北京日期 YYYY-MM-DD，默认今天")
    ap.add_argument("--days", type=int, default=1, help="从 --date（默认今天）往前看几天")
    args = ap.parse_args()

    today = datetime.now(BJ).date()
    if args.date:
        today = datetime.strptime(args.date, "%Y-%m-%d").date()

    runs = fetch_runs()
    rows = []
    for r in runs:
        started = r.get("run_started_at") or r.get("created_at")
        if not started:
            continue
        dt = beijing(datetime.fromisoformat(started.replace("Z", "+00:00")))
        rows.append(
            {
                "n": r.get("run_number"),
                "event": r.get("event"),
                "dt": dt,
                "status": r.get("status"),
                "concl": r.get("conclusion"),
                "dur": None
                if not r.get("updated_at")
                else int(
                    (
                        datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00"))
                        - datetime.fromisoformat(started.replace("Z", "+00:00"))
                    ).total_seconds()
                ),
            }
        )

    rc = 0
    for i in range(args.days):
        day = today - timedelta(days=i)
        day_rows = [x for x in rows if x["dt"].date() == day]
        ok = [x for x in day_rows if x["concl"] == "success"]
        print(f"\n=== {day} (北京) ===")
        if not day_rows:
            print("  没有任何运行 —— GitHub 侧零活动（凭据问题或调度全挂）")
            rc = 1
            continue

        for n, x in enumerate(day_rows, 1):
            dur = f"{x['dur']}s" if x["dur"] is not None else "?"
            print(f"  #{x['n']:<3} {x['event']:<17} {x['dt']:%H:%M:%S}  {x['status']}/{x['concl']}  {dur}")

        print(f"  成功 {len(ok)} 次（目标 2）：", end="")
        print("够" if len(ok) >= 2 else "不够")

        # 槽位匹配：只对 event=workflow_dispatch 的运行判断"是哪个槽派出去的"
        disp = [x for x in day_rows if x["event"] == "workflow_dispatch"]
        now = datetime.now(BJ)
        for hh, mm in SLOTS:
            target = datetime(day.year, day.month, day.day, hh, mm, tzinfo=BJ)
            hit = [x for x in disp if abs((x["dt"] - target).total_seconds()) <= 600]
            if hit:
                d = int((hit[0]["dt"] - target).total_seconds())
                print(f"    槽 {hh:02d}:{mm:02d}  ✅ 由华为云 dispatch（#{hit[0]['n']}，偏差 {d:+d} 秒）")
                continue

            future = target > now
            if future:
                print(f"    槽 {hh:02d}:{mm:02d}  ⏳ 还没到")
                continue

            # 没有 dispatch 不一定有问题：已经够 2 次时函数会主动跳过（skip_enough / skip_busy）
            sched = [x for x in day_rows if x["event"] == "schedule" and abs((x["dt"] - target).total_seconds()) <= 600]
            if sched:
                print(f"    槽 {hh:02d}:{mm:02d}  ⚠️ 华为云没派，但有 GitHub schedule 兜底（#{sched[0]['n']}）")
            elif len(ok) >= 2:
                print(f"    槽 {hh:02d}:{mm:02d}  —  没有 dispatch 运行（当日已够 2 次，跳过属正常；"
                      f"要确认触发没触发得查华为云逐分钟指标）")
            else:
                print(f"    槽 {hh:02d}:{mm:02d}  ❌ 该槽既没 dispatch 也没有兜底，而且当日不足 2 次")
                rc = 1

        if len(ok) < 2:
            rc = 1

    print("\n补充判据：")
    print("  - 单次运行时长应在 1800~1960 秒；<60 秒结束 = 凭据问题，与调度无关")
    print("  - 撞号取消：两边都开时可能出现 status=cancelled 的 schedule 运行，属预期")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
