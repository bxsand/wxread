# wxread · 微信读书自动阅读（个人 fork）

本仓库 fork 自 [findmover/wxread](https://github.com/findmover/wxread)，用于个人每日自动阅读，**不是上游官方版本**，也不面向他人部署。
脚本原理、字段含义、抓包方法、Docker 部署方式均沿用上游，请优先阅读 [上游 README](https://github.com/findmover/wxread#readme)。
本文档说明**本仓库相对上游做了哪些改动**、**怎么部署**、**怎么判断它真的在工作**，以及**坏了怎么修**。

## 目录

- [相对上游的改动](#相对上游的改动)
- [当前配置](#当前配置)
- [部署（GitHub Actions）](#部署github-actions)
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
| 4 | `.github/workflows/deploy.yml` | 两个定时：`23 17 * * *` 与 `47 19 * * *`（UTC）= **北京时间 01:23 与 03:47**；上线时加上两个 healthcheck 上报步骤（成功 / 失败各一个） | 每天两次机会；并让"没跑"也能被发现 |
| 5 | `.github/workflows/docker-publish.yml` | 在仓库设置中停用（文件保留） | 镜像构建对本仓库无意义，且每次 push 都会失败告警 |
| 6 | `README.md`、`CHANGELOG.md` | 补充本仓库说明与变更记录 | 便于回溯改动来源 |

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
| 死信监控 | healthchecks.io（`HEALTHCHECK_PING_URL`，周期 1 天、宽限 1 小时） |

## 部署（GitHub Actions）

1. Fork 本仓库或直接使用本仓库。
2. 打开 **Actions** 页：
   - fork 仓库的 workflow 默认被禁用，点 `I understand my workflows, go ahead and enable them`；
   - 再点 `Enable workflow` 恢复 `schedule`（fork 的定时任务默认关闭）。
   - **fork 的 workflow 会被 GitHub 周期性再次停用**，表现为"定时运行静默消失"。发现运行缺失时先回来看这里。
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

- **定时延迟 2~7 小时**：实测 12 次定时样本，延迟区间 `+2h14m ~ +6h43m`，**没有可靠上界**。所以**不能用"几点看到运行"判断健康**，也不能用"今天只看到一次运行"判断丢槽（第二个槽可能几小时后才出现）。GitHub 的 `schedule` 不承诺时间精度。
- **可能丢槽**：GitHub 官方说明高峰期排队作业可能被丢弃。目前的对策只是把定时从整点后挪开（见上），以及用结果差值兜底。
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
