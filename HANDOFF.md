# Network Lens V0.1 交接

## 当前状态

2026-11-16：已完成采集、跟踪、NiceGUI 页面与启动入口；正在进行最终 Windows 验证及 README 编写。

## 目标与边界

- 以 [NETWORK_LENS_V0.1_SPEC.md](NETWORK_LENS_V0.1_SPEC.md) 为冻结范围；只读、本机 TCP 快照、无云服务、无历史持久化。
- Python 3.12+、psutil、NiceGUI ui.echart；不增加抓包、DNS、流量统计、代理推断等功能。
- 每完成一个可验证步骤执行中文 Git commit；不提交环境或真实网络数据。
- 用户原有规格文件保持内容不变，纳入项目基础提交。

## 实施步骤与成功标准

1. 建立最小工程、数据模型、采集器、纯函数快照对比及测试。采样失败保留成功快照，连接身份包含 PID、进程启动时间（可读时）、地址族和双端点。
2. 接入单个后台采样循环与页面：进程搜索、稳定拓扑、连接列表、详情、最多 100 条观察事件；验证页面交互。
3. 在 Windows 上运行自动化测试和真实 TCP 采集验证；更新 README 的安装、运行、交叉检查及已知限制。

## 验证与下一步

- 当前主机：Windows，系统 Python 3.13.2；项目将创建独立 .venv。
- `.venv` 已安装项目及开发依赖；固定 psutil 7.2.2、NiceGUI 4.0.0。
- `python -m pytest -q`：31 passed；`python -m ruff check .`：通过。
- 已覆盖身份隔离、IPv6、LISTEN、进程读取错误、事件上限、失败采样和恢复，以及页面选择、详情、失败保留与 PID 复用。
- Windows 实际启动成功（127.0.0.1:8879），已查看真实进程拓扑、搜索、LISTEN 和表格点击详情。
- 采集保留 PID 0 的系统原值，但不把它错误归属到空闲进程。图表仅在内容变化时更新，使用稳定 ID；不发送 zoom/center 重置。
- Windows 11 10.0.26100 真实 IPv4/IPv6 回环集成测试通过：两条客户端连接对应 1 LISTEN + 4 ESTABLISHED；关闭后身份消失并记录 NO_LONGER_OBSERVED。
- `scripts/tcp_demo.py` 可交互复现同一远端上的两条客户端连接，无外部网络访问。
- 尚需：用演示脚本复查浏览器图表点击及交互稳定性；完善 README；最终检查并提交。
