# wxread · 微信读书自动阅读（个人 fork）

本仓库 fork 自 [findmover/wxread](https://github.com/findmover/wxread)，用于个人每日自动阅读，**不是上游官方版本**，也不面向他人部署。
脚本原理、字段含义、抓包方法、Docker 部署方式均沿用上游，请优先阅读 [上游 README](https://github.com/findmover/wxread#readme)。
本文档说明**本仓库相对上游做了哪些改动**、**怎么部署**、**怎么判断它真的在工作**，以及**坏了怎么修**。

## 目录

- [相对上游的改动](#相对上游的改动)
- [当前配置](#当前配置)
- [部署（GitHub Actions）](#部署github-actions)
- [调度：为什么换到华为云函数](#调度为什么换到华为云函数)
- [监控与验收：怎么确认它真的在读](#监控与验收怎么确认它真的在读)
- [日常维护](#日常维护)
- [已知限制](#已知限制)
- [免责声明](#免责声明)

## 相对上游的改动

| # | 文件 | 改动 | 动机 |
| - | ---- | ---- | ---- |
| 1 | `config.py` | 阅读目标由《三体》改为《木心全集（典藏套装十六册）》，`book` / `chapter` / `data` 全部按真实抓包重写 | 上游默认书目不再使用 |
| 2 | `config.py` | 新增 `positions` 位置池（9 组 `c` / `ci` / `co` / `sm` / `pr`），每组来自一次真实翻页请求 | 让上报的阅读位置自身一致 |
| 3 | `main.py` | 位置池由「随机取一组」改为**顺序游标**：按 `(ci, co)` 排序后逐页推进，5% 概率回退一页 | 消除随机跳页、同页重复等非真人特征 |
| 4 | `.github/workflows/deploy.yml` | 原有两个定时 `23 17 * * *` / `47 19 * * *`（UTC）= 北京 01:23 / 03:47，**2026-11-06 起已注释掉**，只保留 `workflow_dispatch`；同时加两个 healthcheck 上报步骤（成功 / 失败各一个） | 定时改由云函数派发（见[下一节](#调度为什么换到华为云函数)）；让"没跑"也能被发现 |
| 5 | `.github/workflows/docker-publish.yml` | 在仓库设置中停用（文件保留） | 镜像构建对本仓库无意义，且每次 push 都会失败告警 |
| 6 | `README.md`、`CHANGELOG.md` | 补充本仓库说明与变更记录 | 便于回溯改动来源 |
| 7 | `huawei_fn/` | 新增华为云 FunctionGraph 定时函数（只负责按点 `workflow_dispatch`）+ `verify_slots.py` 验证脚本 | GitHub `schedule` 延迟 2~7 小时且会丢槽，把"点 Run workflow"这件事自动化 |
| 8 | `wxread-open.ps1` | 用固定 profile 打开微信读书网页版 | 让浏览器登录态和 Actions 里的 Cookie 快照始终是同一份 |

**定时为什么是 01:23 / 03:47**：GitHub 官方文档明确说 `schedule` 事件在整点（Actions 高负载窗口）会延迟，"如果负载足够高，部分排队的作业可能被丢弃"，并建议把定时放到小时的非常规位置。原配置是 `6 17` / `2 19`（分钟数 :06 / :02，正落在整点后的高危区），2026-11-03 改为 `23 17` / `47 19`。
**注意：这只降低被延迟或丢弃的概率，不改变下面「已知限制」里 2~7 小时的常态延迟。**

**`positions` 是怎么来的**：在网页版阅读器翻页时截获 `POST https://weread.qq.com/web/book/read` 的请求体，取其中 `c`（章节内容 id）、`ci`（章节序）、`co`（字符偏移）、`sm`（该位置正文摘要）、`pr`（页内位置）。这五个字段来自同一次请求，因此天然自洽，不存在拼装。

`main.py` 的改动保持了向后兼容：当 `positions` 为空列表时，行为与上游完全一致（仍走 `random.choice(chapter)`）。

**关于 `data` 字段的优先级**（容易踩坑）：`main.py` 每次循环先取 `book` 里的书 id，再用 `positions` 里的一组覆盖 `c` / `ci` / `co` / `sm` / `pr`。也就是说 **`data` 里这五个字段实际不生效**，真正起作用的是 `data` 中的 `appId`、`ps`、`pc`（设备标识）以及 `positions`。修改书目时请改 `book` + `positions`，而不是 `data`。

## 当前配置

| 项 | 值 |
| - | - |
| 书名 | 木心全集（典藏套装十六册） |
| `book` | `35032fe071f6e47f3506809` |
| 官方 `bookId`（用于查进度，和上面不是同一个 id） | `32957567` |
| 位置池 | 以 `config.py` 的 `positions` 为准（当前 9 组，覆盖第 397~406 章） |
| `READ_NUM` | 60（每次 30 秒，共 30 分钟） |
| 每次运行耗时 | 实测 31 分 11 秒 ~ 31 分 53 秒 |
| 单次计入时长 | 实测 **≈ +1,860 秒**（1 次 `read` ≈ +30 秒） |
| 推送 | Server酱（`PUSH_METHOD=serverchan` + `SERVERCHAN_SPT`） |
| 调度 | **华为云 FunctionGraph 定时触发器 × 4**：北京 01:23 / 03:47 / 06:30 / 10:00；实际跑满 2 次即停 |
| 死信监控 | healthchecks.io 两个 check：`wxread`（Actions 侧，`HEALTHCHECK_PING_URL`，周期 1 天、宽限 1 小时）与 `wxread-dispatcher`（云函数侧，宽限 2 小时） |

## 部署（GitHub Actions）

1. Fork 本仓库或直接使用本仓库。
2. 打开 **Actions** 页：
   - fork 仓库的 workflow 默认被禁用，点 `I understand my workflows, go ahead and enable them`；
   - 再点 `Enable workflow` **启用工作流**。这一步现在是必须的：工作流被禁用时，`workflow_dispatch` API 也会返回 404，云函数直接派不出去。
   - **fork 的 workflow 会被 GitHub 周期性再次停用**，表现为"定时运行静默消失"。2026-11-06 起这个症状还会表现为**云函数日志里的 dispatch 失败**。发现运行缺失时先回来看这里。
3. **Settings → Secrets and variables → Actions**

   | 类型 | 名称 | 必填 | 说明 |
   | - | - | - | - |
   | Secret | `WXREAD_CURL_BASH` | ✅ | 微信读书 `read` 接口的 curl bash，含 Cookie。**最关键，会周期性失效** |
   | Secret | `PUSH_METHOD` | 可选 | 固定值 `serverchan`；留空则跳过推送 |
   | Secret | `SERVERCHAN_SPT` | 可选 | Server酱 SendKey |
   | Secret | `HEALTHCHECK_PING_URL` | 可选 | healthchecks.io 的 ping URL |
   | Variable | `READ_NUM` | ✅ | `60` |

4. **Settings → Environments**：新建 `AutoRead`。workflow 中声明了 `environment: AutoRead`，缺失时 job 会卡住。
5. 手动执行一次 `Run workflow`，确认：耗时约 31 分钟、日志依次出现「密钥刷新成功」「阅读进度」「阅读脚本已完成」、微信收到一条推送。

> **更新已有 Secret 可能需要输 GitHub 密码**（GitHub 的 sudo 模式）。若页面跳到「Confirm access」，输一次密码即可；sudo 窗口期内（约 2~3 小时）后续更新不会再问。

`WXREAD_CURL_BASH` 的抓取方法见上游 README 的「抓包准备」，或见下文「更新 Cookie」。

## 调度：为什么换到华为云函数

### 结论先说

| | GitHub `schedule`（旧） | 华为云 FunctionGraph（现用） |
| - | - | - |
| 触发精度 | 延迟 **+2h14m ~ +6h43m**，无上界 | 实测 **+0 ~ +5 秒**（4 次抽验） |
| 丢槽 | 高峰期排队作业会被丢弃，2026-11-06 当天两槽全丢 | 未观察到漏触发 |
| 失败可见性 | 延迟与丢槽都不报错 | 云函数自己 ping healthchecks，停摆 2 小时即告警 |
| 成本 | 免费 | 免费额度内（每月 1M 次 / 400,000 GB·s，实际用掉 4 次 × 4 秒 × 128MB） |

GitHub 官方文档原话是 `schedule` 事件在高负载时会延迟、"如果负载足够高，部分排队的作业可能被丢弃"，并建议把定时放到小时的非常规位置。本仓库曾据此把 `6 17`/`2 19` 改成 `23 17`/`47 19`，**但实测证明这只能降低概率**：12 次样本延迟 2h14m~6h43m，2026-11-06 更是整槽消失。所以把"调度"这一段从 GitHub 摘出来，交给一个只做 HTTP 调用的云函数。

### 架构

```
华为云 TIMER 触发器 × 4        北京 01:23 / 03:47 / 06:30 / 10:00
        │  （Quartz 六段 cron，精确到秒）
        ▼
FunctionGraph 函数  huawei_fn/github_dispatch.py
        │  1) 查今天（北京时间）已成功几次 → 够 2 次就 skip
        │  2) 查有没有 queued / in_progress → 有就 busy，不派
        │  3) 都没有 → POST /repos/bxsand/wxread/actions/workflows/deploy.yml/dispatches
        │  4) 无论走哪条分支都 ping healthchecks（失败分支 ping .../fail）
        ▼
GitHub Actions  deploy.yml（已无 cron，仅 workflow_dispatch）
        │  31 分钟重放 60 次 read 请求
        ▼
微信读书 readingTime ≈ +1,860 秒  ＋ Server酱 推送 ＋ Actions 侧 healthcheck
```

**只换调度、不搬脚本**是刻意的：31 分钟的阅读循环、依赖、推送渠道、签名逻辑都在 Actions 里验证过 20 天；云函数的职责被压缩到"几秒钟内决定要不要点那个按钮"。云函数本身不含任何微信读书逻辑，也不持有 `WXREAD_CURL_BASH`。

### 为什么不用云函数直接跑阅读脚本

技术上可行（FunctionGraph 异步调用上限 259,200 秒 = 3 天，31 分钟绰绰有余，同步 15 分钟的限制不适用），但没有采用：

- **收益为零**：调度问题已经解决，把爬虫搬进云函数不会让时长多涨一秒；
- **风险变高**：无 VPC 的函数出口是固定共享 SNAT 地址，等于把 60 次/天的阅读请求固定在一个 IP 上，风控暴露面未知；GitHub 的出口 IP 已被验证无异常；
- **维护成本**：依赖打包、Cookie Secret 托管、推送渠道都要在云上再配一遍。

若将来确实要整体上云（例如想让脚本在你所有设备都不在时也能跑），再评估出口 IP 这一条即可。

### 函数行为（三条分支，都已实测）

| 返回 | 含义 | 何时出现 |
| - | - | - |
| `skip_enough` | 今天已成功 ≥ `NEEDED` 次，不派 | 后两个槽——**这是正常的，不是故障** |
| `busy` | 已有 queued / in_progress 运行 | 两个槽挨得太近，或手动触发了 |
| `dispatched` | 已派发，返回 run id | 前两个槽 |

**为什么需要 `busy` 这道闸**：workflow 里有 `concurrency: cancel-in-progress: true`，盲目再派一次会把正在跑的那次取消掉，等于白跑 31 分钟。

### 部署清单（复现步骤）

1. 函数：Python 3.9 运行时、128MB、超时 60 秒、公网访问，代码为 `huawei_fn/github_dispatch.py`（只用标准库，无需打依赖包）。
2. 环境变量 7 个：`GITHUB_PAT`（细粒度 PAT，需要 Actions: Read and write）、`REPO=bxsand/wxread`、`WORKFLOW_FILE=deploy.yml`、`REF=main`、`NEEDED=2`、`DRY_RUN=0`、`HEALTHCHECK_URL`。
3. 触发器 4 个，类型 `定时触发器 (TIMER)`，**Quartz 六段**：`秒 分 时 日 月 周`（周用 `?`），例如 `0 23 1 * * ?`。不加时区前缀也按东八区解析（区域 `cn-south-1`）。
4. 验证：`python huawei_fn/verify_slots.py`（读 GitHub 侧事实，判断每个槽是不是由云函数派出去的）。

### 部署时踩过的坑（留个记录）

- **控制台「监控 → 指标」的调用次数是滚动汇总数，会骗人。** 我曾据此判定"触发器没生效"，把 4 个触发器全删了准备重建。真相是那份数据刷新慢。要判断定时器到底触发没有，只能用逐分钟接口：`.../functions/statistics?filter=monitor_data&period=1&metric_type=aom_prom_fixed_count`，返回的桶还比实际触发时刻**晚 2 分钟**（4/4 样本一致）。
- **触发器没有"编辑"按钮**，改 cron 只能删了重建。
- **改完环境变量必须刷新页面再读一遍表格。** 我把测试用的 `NEEDED=3` 改回 2 之后，界面上其实一直是 3——弹窗关闭 ≠ 保存成功。`NEEDED=3` 会让函数每天多派一次。
- **`page.evaluate(fn, a, b)` 只接受一个参数**（浏览器自动化时），传两个第二个会变成 `undefined`，于是 cron 被写成字符串 `"undefined"`，建出一个每 3 分钟触发一次的坏触发器。
- **FunctionGraph 的日志服务（LTS）要钱**，没开。排障用控制台「测试」按钮看返回体和 print 输出即可；今天的运行情况查 GitHub 侧，触发情况查逐分钟指标。

## 监控与验收：怎么确认它真的在读

三个信号各有盲区，必须合起来看：

| 信号 | 能说明什么 | 盲区 |
| - | - | - |
| Actions 运行 `success` + 耗时 ≈31 分钟 | 脚本跑完了、没有报错 | 跑完了也可能一次都没计入（例如位置被服务端拒绝） |
| **官方 `readingTime` 增量 ≈ +1,860 秒** | 时长**真的**涨了 | 需要额外一次 API 调用 |
| 微信收到 Server酱 推送 | 推送链路通 | 推送在脚本末尾，失败运行只发 fail 通知 |
| healthchecks 心跳 | "今天有没有跑过" | **抓不到"只跑了一次"或"跑了但没计入"** |

**唯一可靠的判据是第四列之外的"结果差值"**：用官方只读 API 查这本书的累计阅读秒数，运行前后相减。

```bash
# 需要微信读书官方 Agent API Key（wrk- 开头，申请见 https://weread.qq.com/r/weread-skills）
curl -s https://i.weread.qq.com/api/agent/gateway \
  -H "Authorization: Bearer $WEREAD_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"api_name":"/book/getprogress","skill_version":"1.0.5","bookId":"32957567"}'
# 返回里的 book.readingTime 就是累计阅读秒数（单调递增）
```

判定标准：一次成功运行后 `readingTime` 应增加 **1,500~1,950 秒**；**几十秒的增量说明这次运行没有生效**。
注意 `bookId` 要用官方 id `32957567`，不是 `config.py` 里的 `35032fe071f6e47f3506809`（混用会返回 `-2003 参数格式错误`）。

**失败的第一判据是耗时，不是日志**：运行若在 **60 秒内**结束，几乎一定是凭据问题（见下节）。正常的凭据故障不会给你任何中间状态。

## 日常维护

### 更新 Cookie（最常见的维护）

**现象**：运行在 60 秒内以 `failure` 结束；或日志里连续出现 `-2012 登录超时` / `-2013 鉴权失败` 且没有「密钥刷新成功」。

**为什么需要重抓**：Secret 里存的是一份**登录态快照**。它在下列情况下会失效——用户在别的浏览器登录过微信读书网页、服务端会话被吊销、或原因不明的静默失效（本项目遇到过两次，其中一次的具体原因至今未查清）。**失效没有任何前置信号**，只能靠"60 秒内失败"事后识别。

**流程**（三步，关键是第二步：预检不过就不要上传，因为 Secret 是 write-only，传上去只会得到一次静默失败）：

1. **抓新 curl**：在已登录微信读书的浏览器里，抓一条真实的 `POST https://weread.qq.com/web/book/read` 请求，连同完整 Cookie 导出成 curl（仓库内 `tools/rebuild_curl.py` 是这条路子的自动化版本，走 CDP 从浏览器会话取 Cookie）。
   - 判定"抓对了"的最低要求：Cookie 里必须含 **`wr_rt` + `wr_vid` + `wr_fp`** 三枚。缺任意一枚都是**游客态**，传上去必然失败。
2. **预检**：拿新 curl 先真的发一次 `read` 请求，必须返回 `{"succ":1, ...}`。**不要**只看 Cookie 里有没有 `wr_skey`——它不是必需项，而且每次页面加载都会轮换。
3. **写 Secret**：`Settings → Secrets → WXREAD_CURL_BASH → Update secret`，页面回到列表并出现 `Secret updated.` 即成功。

想立刻验证而不是等下一个定时：`Actions → Run workflow` 手动跑一次。**注意手动触发会取消正在跑的定时运行**（workflow 里 `concurrency: cancel-in-progress: true`），不要在定时槽附近手动跑。

### 凭据的结构（踩过坑，记下来）

| 事实 | 说明 |
| - | - |
| `wr_skey` **不是**必需项 | 每次页面加载都会轮换，且删掉后 `renewal` 仍能自铸新 key |
| 真正的锚点是 **`wr_rt` + `wr_vid` + `wr_fp`** | 逐枚删除实测：缺 `wr_rt`/`wr_vid` → `-2013 params error`；缺 `wr_fp` → `-2003 参数格式错误` |
| `read` / `renewal` 请求**不占**会话槽 | 所以浏览器与 Actions 可以同时成功 |
| 网页端**登录**可能让旧快照失效 | 但**不是必然**：实测存在新旧两份凭据同时有效的情况。所以"别在别处登录"是降低风险，不是铁律 |
| 失效机制**未完全查清** | 已知的两次事故中，有一次的具体原因至今没有解释 |

### 浏览器登录态：让 Actions 的 Cookie 永远不过期

**问题**：Secret 里存的是一份 cookie 快照，快照会死；而死因大概率是"你在别的浏览器里登录了微信读书网页版"。

**做法**：不要在日常浏览器里开微信读书网页版，改用下面这个固定 profile：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\wxread-open.ps1
```

它做的事就是用 `--user-data-dir=%USERPROFILE%\edge-wxread-profile` 启动 Edge 并打开 `https://weread.qq.com/`。这个目录里的登录态是持久的（扫码登录过一次就够了），而且**它就是 `rebuild_curl.py` / `refresh_secret.py` 抓 cookie 的那个 profile**——浏览器和 Actions 用的是同一份凭据，不存在"两边打架"。

桌面上放一个快捷方式更省事（目标填 `powershell -NoProfile -ExecutionPolicy Bypass -File "C:\path\to\wxread-open.ps1"`，或直接指向 `msedge.exe` 加参数）。

**万一还是失效了**（换机器、清过缓存、服务端吊销）：

```powershell
python weread-skill/refresh_secret.py
```

一条命令做完「从 profile 抓 cookie → 用新快照真发一次 renewal + read 预检 → 通过才上传 Secret」。预检不过就不上传，避免把死凭据写进去导致一次静默失败。

### 位置池与登录态的关系

位置池（`config.py` 的 `positions`）与登录态无关，失效只影响 `cookies`。但反过来要注意：**换书或换章节后**位置池里的 `ci`/`co` 会和真实进度对不上，届时需要重新采集（见下文）。

### 扩展位置池

```bash
python tools/collect_positions.py --book 35032fe071f6e47f3506809 --count 20 --interval 40
python tools/write_positions.py   # 把 capture/positions.json 写回 config.py 的 positions 段
```

阅读器只会在页面**可见且持续停留**时每 60~70 秒上报一次，采集期间不要切走窗口或最小化。

### 与上游同步

```bash
git remote add upstream https://github.com/findmover/wxread.git
git fetch upstream
git merge upstream/main
```

冲突通常集中在 `main.py` 的游标分支和 `config.py` 的 `book` / `chapter` / `data` / `positions` 段。

## 已知限制

- **GitHub `schedule` 不可靠（已绕开）**：实测 12 次样本延迟 `+2h14m ~ +6h43m`，无上界，且可能整槽丢弃。2026-11-06 起定时改由华为云函数派发，GitHub 侧 cron 已注释掉，只保留 `workflow_dispatch`。**回滚方式**：把 `deploy.yml` 里两行 cron 取消注释、并停用云函数的 4 个触发器（不要两边同时开，`concurrency` 会互相取消）。
- **云函数是新的单点**：4 个槽全压在一个函数上，函数所在区域/账号出问题就没有兜底。目前靠 `wxread-dispatcher` 这个 healthchecks check（宽限 2 小时）告警。
- **手动触发会挤掉定时运行**：`concurrency: cancel-in-progress: true`。
- **healthchecks 抓不到"只跑了一半"**：只要当天有一次成功 ping，计时器就重置。要抓这种情况只能看 `readingTime` 增量。
- **凭据会静默失效**：见上节。恢复成本已压到"抓包 → 预检 → 更新 Secret"三步。
- **位置池规模**：以 `config.py` 为准，组数决定游标一轮的时长（当前 9 组约 4.5 分钟一轮）；`400 → 404 → 406` 之间还有断档。
- **私有仓库成本**：若改为私有仓库，Actions 按分钟计费（本配置约 1,800 分钟/月）。

## 免责声明

本项目仅供学习与技术研究，请勿用于商业用途。使用本脚本产生的任何后果（包括但不限于账号异常、挑战赛判定、数据丢失）由使用者自行承担。请遵守微信读书用户协议。

## 致谢

- [findmover/wxread](https://github.com/findmover/wxread)：本仓库的全部核心逻辑（接口逆向、`sg` 签名、Cookie 续期、推送渠道）均来自上游。
- 上游 README 中的字段解释与抓包步骤。
- 微信读书官方只读 Agent API（`/book/getprogress` 等）：用于"时长是否真的涨了"的独立验收。

## 许可

上游仓库未附许可证文件，本仓库沿用上游的授权状态。若需商用或再分发，请先联系上游作者。
