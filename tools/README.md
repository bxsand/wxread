# tools

维护本仓库时用到的小工具。除 `bcd.py` 外都是单文件脚本，直接 `python tools/<name>.py` 运行。

## 阅读与抓包

| 脚本 | 用途 |
| ---- | ---- |
| `collect_positions.py` | 在网页版阅读器里翻页，抓 `POST /web/book/read`，把每组 `(c, ci, co, sm, pr)` 存进 `capture/positions.json` |
| `write_positions.py` | 把 `capture/positions.json` 写回 `config.py` 的 `positions` 段（只动这一段，可重复执行） |
| `rebuild_curl.py` | 从当前浏览器会话重新生成 `WXREAD_CURL_BASH`（含 Cookie），输出到 `capture/curl_bash.txt` |

采集注意：阅读器只在页面**可见且持续停留**时每 60~70 秒上报一次，采集期间不要切走窗口或最小化，否则会很久抓不到一条。

## 浏览器控制（CDP）

本机 Edge 需以 `--remote-debugging-port=9333` 启动（沙箱内无法启动 Chromium）。

| 脚本 | 用途 |
| ---- | ---- |
| `cdp.py` | 极简 CDP 客户端：导航、执行 JS、截图、真实鼠标点击、Cookie、Network 事件 |
| `bcd.py` | `cdp.py` 的命令行封装：`status / goto / text / eval / shot / click / clicktext / type / key / scroll` |
| `gh_commit.py` | 用 GitHub 网页编辑器提交单个文件，提交后用 API 逐字节校验 |
| `gh_secret.py` | 通过网页表单写入 Repository Secret（前端会做 libsodium 加密） |
| `wait_run.py` | 轮询 Actions run 直到结束，打印状态变化 |

`bcd.py` 支持用环境变量 `BCD_MATCH` 指定标签页，例如：

```bash
BCD_MATCH=weread python tools/bcd.py text 9333
```

## 依赖

仅需 `requests` 与 `websockets`（Python 3.10+）。不需要 Playwright / Selenium，也不需要 Node。
