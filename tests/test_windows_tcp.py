"""Real loopback sockets: verify Windows collection, identities and observed disappearance."""

import os
import socket
import sys
import time
from collections.abc import Callable
from contextlib import ExitStack

import pytest

from network_lens.collector import collect_snapshot
from network_lens.models import Endpoint, Snapshot
from network_lens.tracker import TrackingState, advance

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows TCP integration check")


def wait_snapshot(predicate: Callable[[Snapshot], bool]) -> Snapshot:
    deadline = time.monotonic() + 5
    while True:
        snapshot = collect_snapshot()
        assert snapshot.error is None, snapshot.error
        if predicate(snapshot):
            return snapshot
        if time.monotonic() >= deadline:
            pytest.fail("Controlled loopback sockets were not reflected within 5 seconds")
        time.sleep(0.1)


@pytest.mark.parametrize("family,host", [(socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")])
def test_real_tcp_snapshots_and_observation_events(family, host):
    baseline = collect_snapshot()
    assert baseline.error is None, baseline.error
    pid = os.getpid()
    with ExitStack() as sockets:
        listener = sockets.enter_context(socket.socket(family, socket.SOCK_STREAM))
        try:
            listener.bind((host, 0))
        except OSError:
            if family == socket.AF_INET6:
                pytest.skip("IPv6 loopback is unavailable on this host")
            raise
        listener.listen(2)
        listener.settimeout(3)
        server_endpoint = Endpoint(host, listener.getsockname()[1])
        pairs = {(server_endpoint, None)}
        for _ in range(2):
            client = sockets.enter_context(socket.socket(family, socket.SOCK_STREAM))
            client.settimeout(3)
            client.connect(listener.getsockname())
            accepted, _ = listener.accept()
            sockets.enter_context(accepted)
            client_endpoint = Endpoint(host, client.getsockname()[1])
            pairs.update(((client_endpoint, server_endpoint), (server_endpoint, client_endpoint)))

        active = wait_snapshot(
            lambda snapshot: (
                pairs <= {(c.local, c.remote) for c in snapshot.connections if c.pid == pid}
            )
        )
        controlled = [
            c for c in active.connections if c.pid == pid and (c.local, c.remote) in pairs
        ]
        assert len(controlled) == 5
        assert {c.family for c in controlled} == {"IPv6" if family == socket.AF_INET6 else "IPv4"}
        assert sum(c.status == "LISTEN" for c in controlled) == 1
        assert sum(c.status == "ESTABLISHED" for c in controlled) == 4
        assert all(c.process_name != "Unknown" and c.process_started_at for c in controlled)
        identities = {c.identity for c in controlled}
        state = advance(advance(TrackingState(), baseline), active)
        assert identities <= {
            e.connection.connection.identity for e in state.events if e.kind == "FIRST_OBSERVED"
        }

    closed = wait_snapshot(
        lambda snapshot: not identities.intersection(c.identity for c in snapshot.connections)
    )
    state = advance(state, closed)
    assert identities <= {
        e.connection.connection.identity for e in state.events if e.kind == "NO_LONGER_OBSERVED"
    }
