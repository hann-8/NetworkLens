"""Read psutil's system TCP table; never modify networking or processes."""

import socket
from datetime import UTC, datetime

import psutil

from .models import Connection, Endpoint, Snapshot


def _process_info(pid: int | None) -> tuple[str, float | None, str | None]:
    if pid is None:
        return "Unknown", None, "部分连接的 PID 不可读；无法确定所属进程。"
    if pid == 0:
        return "Unknown", None, "系统返回 PID 0 的记录保留原值，不将它关联到空闲进程。"
    try:
        process = psutil.Process(pid)
    except (psutil.Error, OSError) as exc:
        return "Unknown", None, f"部分进程信息不可读（{type(exc).__name__}），数据可能不完整。"

    name = "Unknown"
    started_at = None
    errors: set[str] = set()
    # Read attributes independently so one denied attribute does not hide the other.
    try:
        name = process.name() or "Unknown"
    except (psutil.Error, OSError) as exc:
        errors.add(type(exc).__name__)
    try:
        started_at = process.create_time()
    except (psutil.Error, OSError) as exc:
        errors.add(type(exc).__name__)
    warning = None
    if errors:
        warning = f"部分进程信息不可读（{', '.join(sorted(errors))}），数据可能不完整。"
    return name, started_at, warning


def collect_snapshot() -> Snapshot:
    try:
        raw_connections = psutil.net_connections(kind="tcp")
    except (psutil.Error, OSError) as exc:
        message = f"采集失败（{type(exc).__name__}）：{exc}。保留上次成功快照。"
        if isinstance(exc, psutil.AccessDenied) or isinstance(exc, PermissionError):
            message += " 当前权限不足；本工具不会自动请求管理员权限。"
        return Snapshot(datetime.now(UTC), error=message)

    sampled_at = datetime.now(UTC)
    processes: dict[int | None, tuple[str, float | None, str | None]] = {}
    warnings: set[str] = set()
    records = []
    for raw in raw_connections:
        if raw.pid not in processes:
            processes[raw.pid] = _process_info(raw.pid)
        name, started_at, warning = processes[raw.pid]
        if warning:
            warnings.add(warning)
        records.append(
            Connection(
                pid=raw.pid,
                process_name=name,
                process_started_at=started_at,
                family="IPv6" if raw.family == socket.AF_INET6 else "IPv4",
                local=Endpoint(raw.laddr.ip, raw.laddr.port),
                remote=Endpoint(raw.raddr.ip, raw.raddr.port) if raw.raddr else None,
                status=raw.status,
                sampled_at=sampled_at,
            )
        )
    return Snapshot(sampled_at, tuple(records), warnings=tuple(sorted(warnings)))
