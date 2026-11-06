# -*- coding: utf-8 -*-
"""
华为云 FunctionGraph 定时函数：按需触发 GitHub Actions 里的 wxread workflow。

为什么要有它
------------
GitHub 的 `schedule` 事件在高负载时会延迟甚至丢弃排队作业（官方文档原文），
实测延迟 2~7 小时且无上界。而 `workflow_dispatch`（相当于点 Run workflow 按钮）
走普通触发路径，几秒内就开始跑。所以：用华为云函数按点触发 dispatch，
等于把"手动点按钮"自动化，延迟从小时级降到秒级。

设计要点
--------
1. **不盲发**：每次被触发先查"今天（北京时间）已经成功了几次"，
   够了就什么都不做，不够才 dispatch → 同一天多次触发不会重复跑。
2. **不抢跑**：已有 queued / in_progress 的运行就跳过，避免撞上
   workflow 里的 `concurrency: cancel-in-progress: true` 把正在跑的那次取消掉。
3. **自己报活**：无论走哪条分支都向 healthchecks 发一次 ping，
   逻辑失败发 `<url>/fail` → "函数没触发"这件事也能被告警出来。
4. **只用标准库**：不用 requests，免去打依赖包 / requirements.txt。

部署：见同目录 README.md
本地自测：设好环境变量后 `python huawei_fn/github_dispatch.py`
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api.github.com"
TZ_BJ = timezone(timedelta(hours=8))

REPO = os.environ.get("REPO", "bxsand/wxread")
WORKFLOW_FILE = os.environ.get("WORKFLOW_FILE", "deploy.yml")
REF = os.environ.get("REF", "main")
NEEDED = int(os.environ.get("NEEDED", "2"))
TOKEN = (os.environ.get("GITHUB_PAT") or "").strip()
PING = (os.environ.get("HEALTHCHECK_URL") or "").strip()
DRY_RUN = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes", "on")


def log(msg):
    print("[%s] %s" % (datetime.now(TZ_BJ).strftime("%Y-%m-%d %H:%M:%S"), msg), flush=True)


def api(method, path, body=None):
    """调 GitHub REST，返回 (status, json)。"""
    url = API + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "huawei-fg-wxread-dispatcher")
    if TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read().decode("utf-8", "replace")
        return r.status, (json.loads(raw) if raw.strip() else {})


def ping(suffix=""):
    """向 healthchecks 发心跳；suffix='/fail' 表示上报失败。"""
    if not PING:
        return
    target = PING.rstrip("/") + suffix
    try:
        with urllib.request.urlopen(target, timeout=10) as r:
            log("healthcheck ping -> HTTP %s%s" % (r.status, suffix or " (ok)"))
    except Exception as e:  # 心跳失败不影响主逻辑
        log("healthcheck ping 失败: %r" % (e,))


def today_runs():
    """取最近 40 次运行里、开始时间落在北京今天的那部分。"""
    _, data = api("GET", "/repos/%s/actions/runs?per_page=40" % REPO)
    today = datetime.now(TZ_BJ).date()
    out = []
    for r in data.get("workflow_runs") or []:
        ts = r.get("run_started_at") or r.get("created_at")
        if not ts:
            continue
        dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        dt = dt.astimezone(TZ_BJ)
        if dt.date() != today:
            continue
        out.append(
            {
                "num": r.get("run_number"),
                "event": r.get("event"),
                "status": r.get("status"),
                "conclusion": r.get("conclusion"),
                "started": dt.strftime("%H:%M:%S"),
                "url": r.get("html_url"),
            }
        )
    out.sort(key=lambda x: x["started"])
    return out


def dispatch():
    """触发一次 workflow_dispatch。"""
    path = "/repos/%s/actions/workflows/%s/dispatches" % (REPO, WORKFLOW_FILE)
    status, _ = api("POST", path, {"ref": REF})
    log("dispatch -> HTTP %s" % status)
    return status in (201, 204)


def find_new_run(since_epoch):
    """dispatch 后确认真的起了新运行（最多等 3 次共 ~12 秒）。"""
    for i in range(3):
        time.sleep(4)
        _, data = api("GET", "/repos/%s/actions/runs?per_page=5" % REPO)
        for r in data.get("workflow_runs") or []:
            ts = r.get("created_at") or ""
            if not ts:
                continue
            dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if dt.timestamp() >= since_epoch - 5 and r.get("event") == "workflow_dispatch":
                log("已确认新运行 #%s %s status=%s" % (r.get("run_number"), ts, r.get("status")))
                return True
        log("第 %d 次确认：还没看到新运行，继续等" % (i + 1))
    return False


def handler(event, context):
    trig = ""
    if isinstance(event, dict):
        trig = "%s @ %s" % (event.get("trigger_name", "?"), event.get("time", "?"))
    log("触发：%s | repo=%s workflow=%s needed=%d" % (trig or "(手动测试)", REPO, WORKFLOW_FILE, NEEDED))

    try:
        if not TOKEN:
            log("提醒：未配置 GITHUB_PAT，只能做只读判断，无法 dispatch")

        runs = today_runs()
        success = [r for r in runs if r.get("conclusion") == "success"]
        busy = [r for r in runs if r.get("status") in ("queued", "in_progress", "waiting", "requested", "pending")]
        failed = [r for r in runs if r.get("conclusion") == "failure"]

        log("今天（北京）共 %d 次运行：成功 %d / 失败 %d / 进行中 %d"
            % (len(runs), len(success), len(failed), len(busy)))
        for r in runs:
            log("   #%-3s %-18s %s  %s" % (r["num"], r["event"], r["started"], r["conclusion"] or r["status"]))

        if busy:
            msg = "已有运行在进行中（#%s），本次跳过，不抢跑" % ",".join(str(r["num"]) for r in busy)
            log(msg)
            ping()
            return {"ok": True, "action": "skip_busy", "detail": msg, "success": len(success)}

        if len(success) >= NEEDED:
            msg = "今天已成功 %d 次（目标 %d），无需触发" % (len(success), NEEDED)
            log(msg)
            ping()
            return {"ok": True, "action": "skip_enough", "detail": msg, "success": len(success)}

        if DRY_RUN:
            msg = "DRY_RUN：本应触发，已跳过"
            log(msg)
            ping()
            return {"ok": True, "action": "dry_run", "success": len(success)}

        if not TOKEN:
            raise RuntimeError("需要 dispatch 但环境变量 GITHUB_PAT 未配置")

        t0 = int(time.time())
        if not dispatch():
            raise RuntimeError("dispatch 返回非 201/204")
        ok = find_new_run(t0)
        msg = "已触发 dispatch，新运行确认：%s" % ("是" if ok else "未确认（可能仍在建队列）")
        log(msg)
        if ok:
            ping()
        else:
            ping("/fail")
        return {"ok": ok, "action": "dispatched", "detail": msg, "success": len(success)}

    except Exception as e:
        log("异常：%r" % (e,))
        ping("/fail")
        return {"ok": False, "action": "error", "detail": repr(e)}


if __name__ == "__main__":
    # 本地自测：GITHUB_PAT=xxx python huawei_fn/github_dispatch.py
    sys.exit(0 if handler({"trigger_name": "LOCAL", "time": "manual"}, None).get("ok") else 1)
