"""One shared sampler and per-browser presentation state."""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime

from nicegui import app, events, ui

from .collector import collect_snapshot
from .models import ObservedConnection
from .presentation import (
    connection_id,
    connection_row,
    display_time,
    graph_options,
    process_id,
)
from .tracker import TrackingState, advance


@dataclass
class Monitor:
    state: TrackingState = field(default_factory=TrackingState)

    async def sample(self) -> None:
        snapshot = await asyncio.to_thread(collect_snapshot)
        self.state = advance(self.state, snapshot)


def columns(fields: list[tuple[str, str]]) -> list[dict]:
    return [
        {"name": key, "field": key, "label": label, "align": "left", "sortable": True}
        for key, label in fields
    ]


CONNECTION_FIELDS = [
    ("process", "进程"),
    ("pid", "PID"),
    ("local", "本地端点"),
    ("remote", "远端端点"),
    ("status", "TCP 状态"),
]


def create_page(monitor: Monitor) -> None:
    ui.add_css("""
        body { background: #f4f7fa; color: #1e293b; }
        .nicegui-content { max-width: 1600px; margin: auto; padding: 24px; gap: 18px; }
        .panel { background: white; border: 1px solid #dde5ed; border-radius: 12px;
                 box-shadow: none; padding: 20px; width: 100%; }
        .explorer { display: grid; grid-template-columns: minmax(0, 2fr) minmax(300px, 1fr);
                    gap: 18px; width: 100%; align-items: start; }
        .hint { color: #64748b; font-size: 13px; }
        .detail-value { overflow-wrap: anywhere; font-family: Consolas, monospace; }
        @media (max-width: 900px) { .explorer { grid-template-columns: minmax(0, 1fr); } }
    """)
    selected_process: str | None = None
    selected_label = ""
    selected_connection: ObservedConnection | None = None
    previous_options: dict = {}
    last_rendered: TrackingState | None = None

    with ui.row().classes("w-full items-center justify-between"):
        with ui.column().classes("gap-0"):
            ui.label("Network Lens").classes("text-3xl font-semibold")
            ui.label("V0.1 · 本机 TCP 观察 · 只读").classes("hint")
        summary = ui.label().classes("hint")
    with ui.row().classes("panel items-center justify-between"):
        selector = ui.select({}, label="搜索进程名或 PID", with_input=True, clearable=True)
        selector.classes("w-96 max-w-full").props("outlined dense options-dense")
        with ui.column().classes("gap-1"):
            sample_status = ui.label("等待首次采样…").classes("font-medium")
            last_update = ui.label().classes("hint")
    error_label = ui.label().classes("text-red-800 bg-red-50 rounded-lg p-3 w-full")
    error_label.set_visibility(False)
    warning_label = ui.label().classes("text-amber-900 text-sm w-full")
    warning_label.set_visibility(False)

    with ui.element("div").classes("explorer"):
        with ui.column().classes("panel gap-2"):
            ui.label("进程 ↔ 远端端点").classes("text-lg font-semibold")
            ui.label("点击进程或连线查看；拖拽节点、滚轮缩放、拖拽空白处平移。").classes("hint")
            graph_hint = ui.label().classes("hint")
            chart = ui.echart(graph_options([]), renderer="svg").classes("w-full h-[400px]")
        with ui.column().classes("panel gap-3"):
            ui.label("Connection Details · 连接详情").classes("text-lg font-semibold")
            detail_state = ui.label("点击连线或连接列表中的一行。").classes("hint")
            detail_labels: dict[str, ui.label] = {}
            for key, label in [
                ("process", "进程"),
                ("pid", "PID"),
                ("family", "地址族 / 协议"),
                ("status", "TCP 状态"),
                ("local", "本地端点"),
                ("remote", "远端端点"),
                ("started", "进程启动时间"),
                ("first", "首次观察时间"),
                ("last", "最近观察时间"),
            ]:
                with ui.column().classes("gap-0 w-full"):
                    ui.label(label).classes("hint")
                    detail_labels[key] = ui.label("—").classes("detail-value text-sm")

    with ui.column().classes("panel gap-2"):
        ui.label("当前进程的 TCP 连接").classes("text-lg font-semibold")
        table_hint = ui.label().classes("hint")
        table = (
            ui.table(
                rows=[],
                columns=columns(CONNECTION_FIELDS),
                row_key="id",
                selection="single",
                pagination=10,
            )
            .classes("w-full")
            .props('flat dense no-data-label="没有当前连接"')
            .mark("connections")
        )

    with ui.column().classes("panel gap-2"):
        ui.label("Recent Observations · 最近观察").classes("text-lg font-semibold")
        ui.label(
            "以下为全局最近 100 条工具观察；FIRST_OBSERVED = 首次看到，"
            "NO_LONGER_OBSERVED = 在采样中不再出现。"
        ).classes("hint")
        ui.label(
            "这不是精确的 TCP 建连/断连事件。约 1 秒轮询可能漏掉短连接；"
            "时间均为工具观察时间，按本机时区显示。"
        ).classes("hint")
        recent_error = ui.label().classes("text-red-800 text-sm")
        event_table = (
            ui.table(
                rows=[],
                columns=columns(
                    [
                        ("time", "观察时间"),
                        ("kind", "观察结果"),
                        *CONNECTION_FIELDS,
                    ]
                ),
                row_key="event_id",
                pagination=8,
            )
            .classes("w-full")
            .props('flat dense no-data-label="尚无观察事件"')
            .mark("observations")
        )

    def render(*, force: bool = False) -> None:
        nonlocal previous_options, last_rendered, selected_label, selected_connection
        state = monitor.state
        if not force and last_rendered is state:
            return
        last_rendered = state
        groups: dict[str, list[ObservedConnection]] = {}
        for observed in state.connections.values():
            groups.setdefault(process_id(observed.connection.process), []).append(observed)
        options = {}
        for key, group in sorted(
            groups.items(),
            key=lambda item: (
                item[1][0].connection.process_name.casefold(),
                item[1][0].connection.pid or -1,
            ),
        ):
            connection = group[0].connection
            pid = connection.pid if connection.pid is not None else "不可读"
            options[key] = f"{connection.process_name} · PID {pid} · {len(group)} 条"
        if selected_process in options:
            selected_label = options[selected_process]
        elif selected_process is not None:
            options[selected_process] = f"{selected_label}（本次无连接）"
        # Avoid resetting a user's in-progress search while the list is open.
        if selector.options != options and not selector.is_showing_popup:
            selector.options = options
            selector.update()
        summary.set_text(f"{len(groups)} 个进程分组 · {len(state.connections)} 条 TCP 记录")
        sample_status.set_text(
            "采集失败 · 显示上次成功数据"
            if state.error
            else ("采样正常 · 约 1 秒 / 次" if state.last_success else "等待首次采样…")
        )
        last_update.set_text(f"上次成功：{display_time(state.last_success)}")
        error_label.set_text(state.error or "")
        error_label.set_visibility(state.error is not None)
        recent_error.set_text(state.error or "")
        warning_label.set_text(" ".join(state.warnings))
        warning_label.set_visibility(bool(state.warnings))

        current = groups.get(selected_process, [])
        if selected_process is None:
            message = "请选择一个进程；选择器只列出成功快照中有 TCP 记录的进程。"
        elif not current:
            message = "当前成功快照中没有该进程的 TCP 记录；已保留选择，进程可能已退出。"
        else:
            message = f"当前 {len(current)} 条记录；没有远端地址的记录仅在下方列表显示。"
        table_hint.set_text(message)
        graph_hint.set_text(
            message
            if not any(o.connection.remote for o in current)
            else ("每条连线代表一条具体连接；同一远端的多条连接使用独立曲线。")
        )
        selected_id = None
        if selected_connection is not None:
            identity = selected_connection.connection.identity
            if identity in state.connections:
                selected_connection = state.connections[identity]
            selected_id = connection_id(identity)
        projected = graph_options(current, selected_id)
        if projected != previous_options:
            chart.options.update(projected)
            chart.update()
            previous_options = projected
        rows = [connection_row(observed) for observed in current]
        if table.rows != rows or force:
            table.rows = rows
            table.selected = [row for row in rows if row["id"] == selected_id]
            table.update()
        if selected_connection is not None:
            row = connection_row(selected_connection)
            connection = selected_connection.connection
            row.update(
                {
                    "family": f"{connection.family} / {connection.protocol}",
                    "started": display_time(
                        datetime.fromtimestamp(connection.process_started_at, UTC)
                    )
                    if connection.process_started_at is not None
                    else "不可读（无法据此区分 PID 复用）",
                    "first": display_time(selected_connection.first_observed),
                    "last": display_time(selected_connection.last_observed),
                }
            )
            detail_state.set_text(
                "当前成功快照中的连接。"
                if (connection.identity in state.connections)
                else "该连接已不再出现在当前成功快照中；以下保留最近观察详情。"
            )
            for key, label in detail_labels.items():
                label.set_text(str(row[key]))
        else:
            detail_state.set_text("点击连线或连接列表中的一行。")
            for label in detail_labels.values():
                label.set_text("—")
        event_rows = []
        for index, event in enumerate(reversed(state.events)):
            event_rows.append(
                {
                    **connection_row(event.connection),
                    "event_id": index,
                    "time": display_time(event.observed_at),
                    "kind": event.kind,
                }
            )
        if event_table.rows != event_rows:
            event_table.rows = event_rows
            event_table.update()

    def choose_process(event: events.ValueChangeEventArguments) -> None:
        nonlocal selected_process, selected_connection, selected_label
        selected_process = event.value
        selected_label = selector.options.get(selected_process, "")
        selected_connection = None
        render(force=True)

    def choose_connection(identity: str) -> None:
        nonlocal selected_connection
        for observed in monitor.state.connections.values():
            if connection_id(observed.connection.identity) == identity:
                selected_connection = observed
                render(force=True)
                return

    def click_chart(event: events.EChartPointClickEventArguments) -> None:
        if event.data_type == "edge":
            choose_connection(event.data["id"])
        elif event.data.get("kind") == "process":
            render(force=True)

    def click_row(event: events.GenericEventArguments) -> None:
        choose_connection(event.args[1]["id"])

    def select_row(event: events.TableSelectionEventArguments) -> None:
        if event.selection:
            choose_connection(event.selection[0]["id"])

    selector.on_value_change(choose_process)
    chart.on_point_click(click_chart)
    table.on("rowClick", click_row)
    table.on_select(select_row)
    ui.timer(0.5, render)
    render()


def serve(port: int, *, show: bool = True) -> None:
    monitor = Monitor()
    app.timer(1.0, monitor.sample)

    @ui.page("/")
    def index() -> None:
        create_page(monitor)

    ui.run(
        host="127.0.0.1",
        port=port,
        title="Network Lens",
        favicon="◉",
        show=show,
        reload=False,
        on_air=False,
        language="zh-CN",
    )
