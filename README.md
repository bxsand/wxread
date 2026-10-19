# wxread · 微信读书自动阅读（个人 fork）

本仓库 fork 自 [findmover/wxread](https://github.com/findmover/wxread)，用于个人每日自动阅读，**不是上游官方版本**。
脚本原理、字段含义、抓包方法、Docker 部署方式均沿用上游，请优先阅读 [上游 README](https://github.com/findmover/wxread#readme)。
本文档只说明**本仓库相对上游做了哪些改动**，以及据此需要如何配置。

## 目录

- [相对上游的改动](#相对上游的改动)
- [当前配置](#当前配置)
- [部署（GitHub Actions）](#部署github-actions)
- [日常维护](#日常维护)
- [已知限制](#已知限制)
- [免责声明](#免责声明)

## 相对上游的改动

| # | 文件 | 改动 | 动机 |
| - | ---- | ---- | ---- |
| 1 | `config.py` | 阅读目标由《三体》改为《木心全集（典藏套装十六册）》，`book` / `chapter` / `data` 全部按真实抓包重写 | 上游默认书目不再使用 |
| 2 | `config.py` | 新增 `positions` 位置池（9 组 `c` / `ci` / `co` / `sm` / `pr`），每组来自一次真实翻页请求 | 让上报的阅读位置自身一致 |
| 3 | `main.py` | 位置池由「随机取一组」改为**顺序游标**：按 `(ci, co)` 排序后逐页推进，5% 概率回退一页 | 消除随机跳页、同页重复等非真人特征 |
| 4 | `.github/workflows/deploy.yml` | 定时由 `01:07` 改为北京时间 `02:06` 与 `04:02`（`6 18 * * *` / `2 20 * * *`），第二次兼作补跑 | 每天两次机会，降低单次失败影响 |
| 5 | `.github/workflows/docker-publish.yml` | 在仓库设置中停用（文件保留） | 镜像构建对本仓库无意义，且每次 push 都会失败告警 |
| 6 | `README.md`、`CHANGELOG.md` | 补充本仓库说明与变更记录 | 便于回溯改动来源 |

**`positions` 是怎么来的**：在网页版阅读器翻页时截获 `POST https://weread.qq.com/web/book/read` 的请求体，取其中 `c`（章节内容 id）、`ci`（章节序）、`co`（字符偏移）、`sm`（该位置正文摘要）、`pr`（页内位置）。这五个字段来自同一次请求，因此天然自洽，不存在拼装。

`main.py` 的改动保持了向后兼容：当 `positions` 为空列表时，行为与上游完全一致（仍走 `random.choice(chapter)`）。

## 当前配置

| 项 | 值 |
| - | - |
| 书名 | 木心全集（典藏套装十六册） |
| `book` | `35032fe071f6e47f3506809` |
| 位置池 | 9 组，覆盖第 397~406 章 |
| `READ_NUM` | 60（每次 30 秒，共 30 分钟） |
| 推送 | 未配置（`PUSH_METHOD` 留空即跳过推送） |

## 部署（GitHub Actions）

1. Fork 本仓库或直接使用本仓库。
2. 打开 **Actions** 页：
   - fork 仓库的 workflow 默认被禁用，点 `I understand my workflows, go ahead and enable them`；
   - 再点 `Enable workflow` 恢复 `schedule`（fork 的定时任务默认关闭）。
3. **Settings → Secrets and variables → Actions**
   - Secret `WXREAD_CURL_BASH`（必填）：微信读书 `read` 接口的 curl bash，含 Cookie；
   - Secret `PUSH_METHOD`（可选）及对应 token；
   - Variable `READ_NUM = 60`。
4. **Settings → Environments**：新建 `AutoRead`。workflow 中声明了 `environment: AutoRead`，缺失时 job 会卡住。
5. 手动执行一次 `Run workflow`，确认日志依次出现「密钥刷新成功」「阅读进度」「阅读脚本已完成」。

`WXREAD_CURL_BASH` 的抓取方法见上游 README 的「抓包准备」。

## 日常维护

### 更新 Cookie

出现 `-2012 登录超时` 且脚本多次自动续期仍失败时，重新抓包并覆盖 Secret `WXREAD_CURL_BASH`。

### 扩展位置池

```bash
python tools/collect_positions.py --book 35032fe071f6e47f3506809 --count 20 --interval 40
python tools/patch_config.py   # 把抓到的位置写回 config.py
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

- **单会话限制**：同一微信读书账号同时只有一个有效 `wr_skey`。任务运行期间不要在本机打开微信读书网页版，否则会互相顶下线；脚本会自动续期恢复，但会丢失一次计数。
- **定时不精确**：GitHub 定时任务在高峰期可能延迟 10~40 分钟，极端情况下当天可能跳过。
- **私有仓库成本**：若改为私有仓库，Actions 按分钟计费（免费额度 2000 分钟/月，本配置约 1800 分钟/月）。
- **位置池规模**：当前 9 组，游标约 4.5 分钟回到起点。

## 免责声明

本项目仅供学习与技术研究，请勿用于商业用途。使用本脚本产生的任何后果（包括但不限于账号异常、挑战赛判定、数据丢失）由使用者自行承担。请遵守微信读书用户协议。

## 致谢

- [findmover/wxread](https://github.com/findmover/wxread)：本仓库的全部核心逻辑（接口逆向、`sg` 签名、Cookie 续期、推送渠道）均来自上游。
- 上游 README 中的字段解释与抓包步骤。

## 许可

上游仓库未附许可证文件，本仓库沿用上游的授权状态。若需商用或再分发，请先联系上游作者。
