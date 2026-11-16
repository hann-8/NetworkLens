import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from nicegui import ui
from nicegui.testing import user_simulation

from network_lens.models import Connection, Endpoint, Snapshot
from network_lens.presentation import connection_id, process_id
from network_lens.tracker import TrackingState, advance
from network_lens.ui import Monitor, create_page

NOW = datetime(2026, 11, 16, tzinfo=UTC)


def test_page_selection_details_failure_recovery_and_process_disappearance(caplog):
    async def scenario():
        connection = Connection(
            42,
            "example.exe",
            1234.5,
            "IPv6",
            Endpoint("::1", 50000),
            Endpoint("::1", 443),
            "ESTABLISHED",
            NOW,
        )
        listening = replace(connection, remote=None, local=Endpoint("::1", 8000), status="LISTEN")
        monitor = Monitor(advance(TrackingState(), Snapshot(NOW, (connection, listening))))
        async with user_simulation(lambda: create_page(monitor)) as user:
            await user.open("/")
            await user.should_see("Network Lens")
            user.find(ui.select).click()
            user.find("example.exe · PID 42 · 2 条").click()
            selector = next(iter(user.find(ui.select).elements))
            chart = next(iter(user.find(ui.echart).elements))
            table = next(iter(user.find(marker="connections").elements))
            assert selector.value == process_id(connection.process)
            assert len(table.rows) == 2
            assert any(row["status"] == "LISTEN" for row in table.rows)
            assert len(chart.options["series"][0]["links"]) == 1

            user.find(marker="connections").trigger("rowClick", [None, table.rows[0], None])
            await user.should_see("[::1]:50000")
            await user.should_see("IPv6 / TCP")
            assert table.selected[0]["id"] == connection_id(connection.identity)

            edge = chart.options["series"][0]["links"][0]
            user.find(ui.echart).trigger(
                "chart:click",
                {
                    "componentType": "series",
                    "seriesType": "graph",
                    "seriesIndex": 0,
                    "seriesName": "connections",
                    "name": edge["name"],
                    "dataIndex": 0,
                    "data": edge,
                    "dataType": "edge",
                },
            )
            await user.should_see("当前成功快照中的连接。")
            previous_graph = chart.options.copy()
            monitor.state = advance(
                monitor.state,
                Snapshot(
                    NOW + timedelta(seconds=1),
                    error="采集失败：AccessDenied",
                ),
            )
            await asyncio.sleep(0.6)
            await user.should_see("采集失败 · 显示上次成功数据")
            assert selector.value == process_id(connection.process)
            assert chart.options == previous_graph
            assert len(table.rows) == 2

            monitor.state = advance(monitor.state, Snapshot(NOW + timedelta(seconds=2)))
            await asyncio.sleep(0.6)
            await user.should_see("已保留选择，进程可能已退出。")
            await user.should_see("以下保留最近观察详情。")
            assert selector.value == process_id(connection.process)
            assert table.rows == []
            assert selector.options[selector.value] == "example.exe · PID 42（本次无连接）"
            assert chart.options["series"][0]["links"] == []

            reused = replace(connection, process_started_at=5678.9)
            monitor.state = advance(monitor.state, Snapshot(NOW + timedelta(seconds=3), (reused,)))
            await asyncio.sleep(0.6)
            assert selector.value == process_id(connection.process)
            assert table.rows == []
            user.find(ui.select).clear()
            await user.should_see("点击连线或连接列表中的一行。")
            assert table.rows == []

    asyncio.run(scenario())
    assert not [record for record in caplog.records if record.levelname == "ERROR"]


def test_page_handles_initial_sampling_failure(caplog):
    async def scenario():
        monitor = Monitor(advance(TrackingState(), Snapshot(NOW, error="采集失败：AccessDenied")))
        async with user_simulation(lambda: create_page(monitor)) as user:
            await user.open("/")
            await user.should_see("尚无成功采样")
            await user.should_see("采集失败：AccessDenied")
            selector = next(iter(user.find(ui.select).elements))
            assert not selector.options

    asyncio.run(scenario())
    assert not [record for record in caplog.records if record.levelname == "ERROR"]
