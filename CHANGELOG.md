# 变更记录

本仓库是 [findmover/wxread](https://github.com/findmover/wxread) 的 fork，以下仅记录**本仓库相对上游**的改动。
上游自身的更新请查看 [上游提交历史](https://github.com/findmover/wxread/commits/main)。

## 2026-10-20

### 新增

- `config.py`：`positions` 位置池，9 组真实翻页位置（《木心全集》第 397~406 章）
- `main.py`：位置池顺序游标 + 5% 概率回退一页
- `CHANGELOG.md`、README 的「相对上游的改动」章节

### 变更

- 阅读目标：《三体》→《木心全集（典藏套装十六册）》（`book = 35032fe071f6e47f3506809`）
- `data` 字段按真实抓包更新：`appId`、`ps`、`pc`、`ci`、`co`、`sm`、`pr`
- 定时：北京时间 `01:07` → `02:06`（`6 18 * * *`）与 `04:02`（`2 20 * * *`）

### 停用

- `.github/workflows/docker-publish.yml`：仓库设置中停用，文件保留

### 修复

- 原「随机取位置」导致同一页可能连续重复、章节跳变无规律的问题

## 初始导入

- 仓库内容与上游 `main` 一致（`210672a` 及其后版本）

## 说明

- 所有提交均可通过 `git log` 追溯；`positions` 与游标逻辑的取舍理由见 README 的「相对上游的改动」一节。
- 本仓库不打算向上游提交 PR：改动针对个人书目与个人运行环境，不具备普适性。
