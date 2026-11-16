from dataclasses import replace
from datetime import UTC, datetime, timedelta

from network_lens.models import Connection, Endpoint, Snapshot
from network_lens.tracker import TrackingState, advance

T0 = datetime(2026, 11, 16, tzinfo=UTC)
T1 = T0 + timedelta(seconds=1)
T2 = T0 + timedelta(seconds=2)


def connection(**changes) -> Connection:
    record = Connection(
        42,
        "example.exe",
        1234.5,
        "IPv4",
        Endpoint("127.0.0.1", 50000),
        Endpoint("127.0.0.1", 443),
        "ESTABLISHED",
        T0,
    )
    return replace(record, **changes)


def test_first_snapshot_records_first_observation():
    record = connection()
    state = advance(TrackingState(), Snapshot(T0, (record,)))
    assert list(state.connections) == [record.identity]
    assert [event.kind for event in state.events] == ["FIRST_OBSERVED"]
    assert state.connections[record.identity].first_observed == T0


def test_disappearance_keeps_last_seen_and_records_observation_time():
    state = advance(TrackingState(), Snapshot(T0, (connection(),)))
    state = advance(state, Snapshot(T1))
    assert state.connections == {}
    assert state.events[-1].kind == "NO_LONGER_OBSERVED"
    assert state.events[-1].observed_at == T1
    assert state.events[-1].connection.last_observed == T0


def test_continuing_connection_updates_status_without_resetting_first_seen_or_mutation():
    record = connection()
    old = advance(TrackingState(), Snapshot(T0, (record,)))
    changed = replace(record, status="CLOSE_WAIT", sampled_at=T1, process_name="renamed.exe")
    state = advance(old, Snapshot(T1, (changed,)))
    observed = state.connections[record.identity]
    assert observed.first_observed == T0
    assert observed.last_observed == T1
    assert observed.connection.status == "CLOSE_WAIT"
    assert len(state.events) == 1
    assert old.connections[record.identity].last_observed == T0


def test_same_remote_different_local_ports_are_distinct():
    first = connection()
    second = connection(local=Endpoint("127.0.0.1", 50001))
    state = advance(TrackingState(), Snapshot(T0, (first, second)))
    assert len(state.connections) == 2
    state = advance(state, Snapshot(T1, (second,)))
    assert list(state.connections) == [second.identity]
    assert state.events[-1].connection.connection.local.port == 50000


def test_unknown_pid_and_listening_socket_are_valid():
    record = connection(
        pid=None, process_name="Unknown", process_started_at=None, remote=None, status="LISTEN"
    )
    state = advance(TrackingState(), Snapshot(T0, (record,)))
    assert state.connections[record.identity].connection.pid is None
    assert state.connections[record.identity].connection.remote is None


def test_failed_samples_do_not_generate_disappearance_and_recovery_compares_successes():
    record = connection()
    old = advance(TrackingState(), Snapshot(T0, (record,)))
    failed = advance(old, Snapshot(T1, error="AccessDenied"))
    assert failed.connections == old.connections
    assert failed.events == old.events
    assert failed.last_success == T0
    assert failed.error == "AccessDenied"
    recovered = advance(failed, Snapshot(T2, (replace(record, sampled_at=T2),)))
    assert len(recovered.events) == 1
    assert recovered.connections[record.identity].first_observed == T0
    assert recovered.error is None
    disappeared = advance(failed, Snapshot(T2))
    assert disappeared.events[-1].observed_at == T2


def test_initial_error_does_not_claim_success():
    state = advance(TrackingState(), Snapshot(T0, error="AccessDenied"))
    assert not state.connections and not state.events
    assert state.last_success is None


def test_pid_reuse_with_known_start_time_is_a_new_identity():
    state = advance(TrackingState(), Snapshot(T0, (connection(),)))
    reused = connection(process_started_at=5678.9, sampled_at=T1)
    state = advance(state, Snapshot(T1, (reused,)))
    assert len(state.connections) == 1
    assert {e.kind for e in state.events[1:]} == {"FIRST_OBSERVED", "NO_LONGER_OBSERVED"}
    assert state.connections[reused.identity].first_observed == T1


def test_family_pid_and_endpoints_participate_in_identity():
    record = connection()
    records = (
        record,
        replace(record, pid=43),
        replace(record, family="IPv6"),
        replace(record, remote=Endpoint("127.0.0.2", 443)),
    )
    state = advance(TrackingState(), Snapshot(T0, records))
    assert len(state.connections) == 4


def test_events_are_bounded_to_100_and_duplicates_do_not_duplicate_events():
    records = tuple(connection(local=Endpoint("127.0.0.1", 50000 + i)) for i in range(120))
    state = advance(TrackingState(), Snapshot(T0, records + records))
    assert len(state.connections) == 120
    assert len(state.events) == 100
    state = advance(state, Snapshot(T1))
    assert len(state.events) == 100
    assert all(e.kind == "NO_LONGER_OBSERVED" for e in state.events)


def test_ipv6_endpoint_format():
    assert str(Endpoint("::1", 443)) == "[::1]:443"
    assert str(Endpoint("127.0.0.1", 443)) == "127.0.0.1:443"
