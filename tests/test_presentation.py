from dataclasses import replace
from datetime import UTC, datetime

from network_lens.models import Connection, Endpoint, ObservedConnection
from network_lens.presentation import connection_id, connection_row, graph_options, process_id

NOW = datetime(2026, 11, 16, tzinfo=UTC)


def observed(**changes):
    connection = Connection(
        42,
        "example.exe",
        1234.5,
        "IPv4",
        Endpoint("127.0.0.1", 50000),
        Endpoint("127.0.0.1", 443),
        "ESTABLISHED",
        NOW,
    )
    return ObservedConnection(replace(connection, **changes), NOW, NOW)


def test_parallel_connections_are_distinct_edges_to_one_endpoint():
    first = observed()
    second = observed(local=Endpoint("127.0.0.1", 50001))
    series = graph_options([first, second])["series"][0]
    assert len(series["data"]) == 2
    assert len(series["links"]) == 2
    assert len({link["id"] for link in series["links"]}) == 2
    assert len({link["lineStyle"]["curveness"] for link in series["links"]}) == 2


def test_listen_only_appears_in_table_without_remote_graph_node_or_edge():
    record = observed(remote=None, status="LISTEN")
    series = graph_options([record])["series"][0]
    assert len(series["data"]) == 1
    assert series["links"] == []
    assert connection_row(record)["remote"] == "—（无远端）"


def test_graph_ids_survive_reordering_and_timestamp_only_refresh_does_not_change_options():
    first = observed()
    second = observed(local=Endpoint("127.0.0.1", 50001))
    assert graph_options([first, second]) == graph_options([second, first])
    later = replace(first, last_observed=NOW.replace(second=5))
    assert graph_options([first]) == graph_options([later])
    series = graph_options([first])["series"][0]
    assert "zoom" not in series and "center" not in series


def test_selected_edge_is_highlighted_and_unknown_pid_is_explicit():
    record = observed(pid=None, process_name="Unknown", process_started_at=None)
    series = graph_options([record], connection_id(record.connection.identity))["series"][0]
    assert series["links"][0]["lineStyle"]["color"] == "#d97706"
    assert "不可读" in series["data"][0]["name"]
    assert connection_row(record)["pid"] == "不可读"


def test_process_identity_changes_when_pid_is_reused():
    first = observed().connection.process
    reused = replace(first, started_at=2345.6)
    assert process_id(first) != process_id(reused)


def test_empty_graph_is_valid():
    series = graph_options([])["series"][0]
    assert series["data"] == [] and series["links"] == []
