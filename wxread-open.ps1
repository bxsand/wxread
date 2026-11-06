<#
  用固定 profile 打开微信读书网页版。

  为什么需要它
  ------------
  GitHub Actions 里存的是 WXREAD_CURL_BASH —— 一份微信读书网页登录态的快照。
  如果你在日常浏览器里打开微信读书网页版，可能需要重新扫码登录，而登录会铸出
  新的 wr_skey / 轮换会话，那份快照就有失效风险（失效是静默的：Actions 在
  30 秒内退出，只在 healthchecks 上留一个 fail）。

  这个脚本改用固定的、独立的 Edge profile（%USERPROFILE%\edge-wxread-profile）：
  扫码登录一次之后长期保持，而且它同时就是 rebuild_curl.py / refresh_secret.py
  抓 cookie 的那个 profile —— 浏览器和云端用的是同一份登录态，不会互相打架。

  用法
  ----
    powershell -NoProfile -ExecutionPolicy Bypass -File .\wxread-open.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File .\wxread-open.ps1 -NoDebug

  桌面上放个快捷方式最省事，目标填：
    msedge.exe --user-data-dir="%USERPROFILE%\edge-wxread-profile" --remote-debugging-port=9333 https://weread.qq.com/

  关于调试端口
  ------------
  默认开着 --remote-debugging-port=9333（只监听 127.0.0.1）。好处是任何时候都能
  用 python tools\rebuild_curl.py 从浏览器现取 cookie，不用关掉浏览器重开；
  代价是本机任何进程都能通过这个端口读到这个 profile 的 cookie。
  个人机器上接受；想更保守就加 -NoDebug（但那样抓 cookie 前得先关掉浏览器）。
#>
param(
    [switch]$NoDebug,
    [string]$Url = 'https://weread.qq.com/'
)

$ErrorActionPreference = 'Stop'

$profileDir = Join-Path $env:USERPROFILE 'edge-wxread-profile'
$candidates = @(
    (Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'),
    (Join-Path $env:ProgramFiles      'Microsoft\Edge\Application\msedge.exe')
)
$edge = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if (-not $edge) { throw '找不到 msedge.exe，请确认 Edge 已安装' }

if (-not (Test-Path -LiteralPath $profileDir)) {
    New-Item -ItemType Directory -Path $profileDir | Out-Null
    Write-Host "新建 profile 目录：$profileDir"
}

$argList = @("--user-data-dir=$profileDir", '--no-first-run', '--no-default-browser-check')
if (-not $NoDebug) {
    $argList += @('--remote-debugging-port=9333', '--remote-allow-origins=*')
}
$argList += $Url

Start-Process -FilePath $edge -ArgumentList $argList
Write-Host "已用固定 profile 打开微信读书"
Write-Host "  profile : $profileDir"
Write-Host "  CDP     : $(if ($NoDebug) { '关闭' } else { 'http://127.0.0.1:9333' })"
