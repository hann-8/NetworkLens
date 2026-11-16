import socket
from types import SimpleNamespace
from unittest.mock import Mock

import psutil
import pytest

from network_lens.collector import collect_snapshot


def raw_connection(pid=42, family=socket.AF_INET, remote=True):
    return SimpleNamespace(
        pid=pid,
        family=family,
        laddr=SimpleNamespace(ip="::1" if family == socket.AF_INET6 else "127.0.0.1", port=50000),
        raddr=SimpleNamespace(ip="::1", port=443) if remote else (),
        status="ESTABLISHED" if remote else "LISTEN",
    )


def test_normalization_and_one_process_lookup_per_snapshot(monkeypatch):
    net = Mock(
        return_value=[raw_connection(), raw_connection(family=socket.AF_INET6, remote=False)]
    )
    process = Mock()
    process.name.return_value = "example.exe"
    process.create_time.return_value = 1234.5
    factory = Mock(return_value=process)
    monkeypatch.setattr(psutil, "net_connections", net)
    monkeypatch.setattr(psutil, "Process", factory)
    snapshot = collect_snapshot()
    net.assert_called_once_with(kind="tcp")
    factory.assert_called_once_with(42)
    assert snapshot.error is None
    assert not snapshot.warnings
    first, second = snapshot.connections
    assert first.process_name == "example.exe"
    assert first.process_started_at == 1234.5
    assert first.protocol == "TCP" and first.family == "IPv4"
    assert str(first.remote) == "[::1]:443"
    assert second.remote is None and second.status == "LISTEN" and second.family == "IPv6"
    assert first.sampled_at == second.sampled_at == snapshot.sampled_at


@pytest.mark.parametrize(
    "error", [psutil.AccessDenied(42), psutil.NoSuchProcess(42), OSError("gone")]
)
def test_process_lookup_failure_does_not_fail_snapshot(monkeypatch, error):
    monkeypatch.setattr(psutil, "net_connections", Mock(return_value=[raw_connection()]))
    monkeypatch.setattr(psutil, "Process", Mock(side_effect=error))
    snapshot = collect_snapshot()
    assert snapshot.error is None
    assert snapshot.connections[0].process_name == "Unknown"
    assert snapshot.connections[0].process_started_at is None
    assert snapshot.warnings


def test_name_denied_does_not_hide_readable_start_time(monkeypatch):
    process = Mock()
    process.name.side_effect = psutil.AccessDenied(42)
    process.create_time.return_value = 1234.5
    monkeypatch.setattr(psutil, "net_connections", Mock(return_value=[raw_connection()]))
    monkeypatch.setattr(psutil, "Process", Mock(return_value=process))
    snapshot = collect_snapshot()
    assert snapshot.connections[0].process_name == "Unknown"
    assert snapshot.connections[0].process_started_at == 1234.5
    assert snapshot.warnings


def test_start_time_denied_is_not_fabricated(monkeypatch):
    process = Mock()
    process.name.return_value = "example.exe"
    process.create_time.side_effect = psutil.AccessDenied(42)
    monkeypatch.setattr(psutil, "net_connections", Mock(return_value=[raw_connection()]))
    monkeypatch.setattr(psutil, "Process", Mock(return_value=process))
    snapshot = collect_snapshot()
    assert snapshot.connections[0].process_name == "example.exe"
    assert snapshot.connections[0].process_started_at is None


def test_missing_pid_is_explicit_without_process_lookup(monkeypatch):
    factory = Mock()
    monkeypatch.setattr(psutil, "net_connections", Mock(return_value=[raw_connection(pid=None)]))
    monkeypatch.setattr(psutil, "Process", factory)
    snapshot = collect_snapshot()
    factory.assert_not_called()
    assert snapshot.connections[0].pid is None
    assert snapshot.warnings


@pytest.mark.parametrize("error", [psutil.AccessDenied(), OSError("table unavailable")])
def test_table_failure_returns_failed_snapshot(monkeypatch, error):
    monkeypatch.setattr(psutil, "net_connections", Mock(side_effect=error))
    snapshot = collect_snapshot()
    assert snapshot.error is not None and type(error).__name__ in snapshot.error
    assert snapshot.connections == ()
