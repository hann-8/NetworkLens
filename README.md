# Network Lens V0.1

在 Windows 11 本机浏览器中，以进程为中心查看 IPv4 / IPv6 TCP 连接。数据来自 `psutil.net_connections(kind="tcp")` 和进程名称、启动时间查询，每秒左右采集一次。

支持进程搜索与选择、可交互 ECharts 拓扑、连接列表（包括 LISTEN）、连接详情，以及最近 100 条全局观察事件。只读，仅监听 `127.0.0.1`，不上传数据、不使用云服务或遥测、不持久化连接历史。安装依赖需要访问 Python 包索引，安装后运行不依赖外部 API 或 LLM Token。

## Windows PowerShell 安装与启动

需要 Python **3.12 或更新版本（64 位）**、现代浏览器（例如 Edge），以及源码目录。以下命令不要求激活虚拟环境，也无需修改 PowerShell 执行策略：

```powershell
cd E:\_Github\NetworkLens
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m network_lens
```

程序默认自动打开 [http://127.0.0.1:8080](http://127.0.0.1:8080)。保持终端运行，按 `Ctrl+C` 停止。若 `python` 不是所需版本，可用 `py -3.12 -m venv .venv` 创建环境。

端口被占用时选择其他本机端口；不自动打开浏览器：

```powershell
.\.venv\Scripts\python.exe -m network_lens --port 8081 --no-browser
# 然后手动打开 http://127.0.0.1:8081
```

也可使用安装后的 `.\.venv\Scripts\network-lens.exe`。启动参数仅支持端口和是否打开浏览器，不开放远程监听配置。不做 exe 打包或开机启动。

## 如何使用

1. 在顶部输入进程名（如 `msedge.exe`、`codex.exe`）或 PID，选择一个进程。只列出最近成功快照中有 TCP 记录的进程；同名的不同 PID 分别显示。浏览器等多进程程序的连接可能属于其子进程。
2. 拓扑只展开当前进程。节点显示进程名 / PID 和远端 IP:Port；每条连线是一条具体连接，同一远端的不同连接使用独立曲线。LISTEN 等没有远端的记录只显示在连接列表中。
3. 点击进程节点查看当前进程连接；点击连线、表格行或选择框查看详情。橙色连线和表格勾选表示当前选中连接。可以拖拽节点、平移图表和滚轮缩放。
4. 详情显示系统提供的地址族、TCP 协议、进程、状态和双端点，以及工具的首次 / 最近观察时间。IPv6 格式为 `[::1]:443`；所有时间按本机时区显示，带时区偏移。
5. 连接不再出现时移出实时图表和列表，当前进程选择保持不变，已选连接的详情保留并明确标注为最近观察数据。清空进程选择可返回空视图。

页面采集失败时显示错误和上次成功时间，并保留上次成功的数据。恢复后比较相邻的成功快照；失败本身不会制造“不再观察到”事件。页面多个标签共用一个后台采样器，阻塞的系统查询在工作线程执行，不会为每个页面重复采集。

## 可复现的本地验证

先启动 Network Lens，再在**另一个 PowerShell 终端**运行：

```powershell
cd E:\_Github\NetworkLens
.\.venv\Scripts\python.exe .\scripts\tcp_demo.py
```

脚本仅在 `127.0.0.1` 创建临时监听端口和两条 TCP 连接，打印 PID、监听端口和两个客户端端口，按回车关闭退出。不会连接外部服务器或修改系统网络设置。

- 在页面按打印的 PID 搜索，等待至少两个采样周期。应看到 **1 条 LISTEN + 4 条 ESTABLISHED**：客户端和服务端都在同一演示进程，所以两端的四个已连接套接字都会显示。
- 拓扑应有一个进程节点和三个远端端点节点、四条连线。其中两条连线通向相同的监听端口，分别对应两个不同的本地客户端端口；点击各条曲线，核对详情。
- 点击 LISTEN 表格行，应显示“无远端”，不出现一条虚构的远端连线。
- 拖动 / 缩放图表并等待数秒，确认采样更新时间前进、进程选择和图表视角保持。连接集合变化时力导向布局可能小幅重新平衡。
- 在脚本终端按回车退出，等待下一次成功采样。该 PID 的连接会移除，选择仍保留并显示无当前连接；最近观察中可查看 `NO_LONGER_OBSERVED`。全局事件较多时，旧事件可能很快移出 100 条窗口。

用系统命令交叉检查（将 `12345` 替换为演示脚本打印的 PID）：

```powershell
Get-NetTCPConnection -OwningProcess 12345 |
    Select-Object LocalAddress, LocalPort, RemoteAddress, RemotePort, State, OwningProcess

Get-NetTCPConnection -State Established | Select-Object -First 20

# 核对 Network Lens 的监听地址（替换为实际启动端口）
Get-NetTCPConnection -LocalPort 8080 -State Listen |
    Select-Object LocalAddress, LocalPort, OwningProcess
```

监听地址应为 `127.0.0.1`。连接变化很快，系统命令与页面是不同时间的快照，不应要求所有行严格相同。Windows 命令还可能显示 psutil TCP 表未返回的 `Bound` 记录；演示时按共同的 LISTEN / ESTABLISHED 端点交叉检查。还可以启动 Edge 浏览网页，观察其有 TCP 连接的进程；HTTP/3 / QUIC 使用 UDP，不在 V0.1 范围。

## 数据含义、权限和局限

- `FIRST_OBSERVED` 表示本工具首次看到一个连接身份；启动时已经存在的连接也会产生此事件。`NO_LONGER_OBSERVED` 表示它从相邻成功快照中消失，**不是精确 TCP 建连 / 断连事件**。后一事件保留的 TCP 状态是最后一次看到的状态，不是工具判定的“关闭状态”。
- 大约 1 秒的快照轮询会漏掉短连接；慢速系统查询会拉长间隔。同一身份的连接若在两次采样之间断开又重建，无法识别。首次 / 最近观察时间不是连接创建时间或生命周期证明。
- 连接身份包含 PID、可读取的进程启动时间、地址族、协议、本地端点和远端端点；不以远端 IP 合并。进程名和 TCP 状态变化不单独产生新连接事件。
- 名称或启动时间读取失败会显示 `Unknown` / 不可读并提示数据可能不完整；PID 可以为空。系统返回 PID 0 时保留 0 并显示 Unknown，不把连接归属到空闲进程。无法读取启动时间时不伪造，因此不能可靠区分这类 PID 复用。进程信息的可读性或 PID 归属发生变化时，工具可能把它记录为不同的观察身份。
- 普通用户可能无法读取部分系统 / 受保护进程信息，某些环境可能拒绝整个 TCP 表查询。程序不会自动提权；若确实需要更完整数据，可以自行决定是否使用管理员终端。自动化测试使用模拟错误验证权限不足和采集失败，不通过改变系统权限制造故障。
- 无 TCP 记录不等于进程已退出；PID 不可读的记录只能作为未知进程分组展示，无法识别它们是否来自同一进程。网络表与进程信息也不是一次原子查询，进程可能在查询间隙退出。
- 只观察本机操作系统返回的 TCP 套接字，不抓包，不解析 TLS / HTTP 内容，不统计带宽，不查询域名 / GEO-IP，也不推断代理链路、最终服务器或 Clash 节点。
- 当前快照、100 条事件及当前选中连接的详情仅存在内存中，重启清除。刷新浏览器会重置该页面的选择 / 图表视角，但服务端观察状态持续到程序退出。布局针对桌面使用；很多远端端点时可以缩放或使用表格查看，不保证所有标签完全不重叠。

## 测试与已验证范围

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check
```

测试覆盖采集规范化、IPv6、LISTEN、独立端口 / PID / 启动时间身份、持续状态与观察时间、未知 PID、进程读取错误、失败采样与恢复、100 条事件上限、图表独立连线和页面选择 / 详情联动。Windows 集成测试创建真实的 IPv4 / IPv6 回环套接字，核对快照及新增 / 消失事件；非 Windows 环境跳过这两项，未启用 IPv6 回环的 Windows 也会跳过相应项。

2026-11-16 在 Windows 11（10.0.26100）、Python 3.13.2、psutil 7.2.2、NiceGUI 4.0.0 上完成 31 项测试。本机浏览器已核对进程搜索、图表与表格点击、LISTEN 及进程退出后的空状态；拖拽 / 缩放的手工复核步骤见上文，页面模拟测试不验证浏览器渲染。权限错误通过模拟验证。其他 Python 3.12+ 版本声明兼容，尚未逐一实机验证。

## 工程结构

```text
src/network_lens/
  models.py          # 不可变数据记录与连接身份
  collector.py       # psutil TCP 快照及进程关联
  tracker.py         # 纯函数成功快照对比、100 条观察事件
  presentation.py    # 表格和 ECharts 的确定性数据投影
  ui.py              # 共享后台采样器与单页面交互
  __main__.py        # 仅回环地址的启动入口
scripts/tcp_demo.py  # 人工验证用的本地 TCP 样例
tests/               # 核心、页面模拟和 Windows 实机集成测试
```

需求以 [NETWORK_LENS_V0.1_SPEC.md](NETWORK_LENS_V0.1_SPEC.md) 为准；项目交接状态见 [HANDOFF.md](HANDOFF.md)。所用公共接口可参考 [psutil 文档](https://psutil.readthedocs.io/)、[NiceGUI ECharts](https://nicegui.io/documentation/echart) 和 [Get-NetTCPConnection](https://learn.microsoft.com/en-us/powershell/module/nettcpip/get-nettcpconnection)。
