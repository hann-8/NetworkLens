"""Small, deterministic projections for tables and ECharts."""

import json
from collections import defaultdict
from datetime import datetime
from math import cos, pi, sin
from typing import Any

from .models import ConnectionIdentity, ObservedConnection, ProcessIdentity


def process_id(process: ProcessIdentity) -> str:
    return f"{process.pid}:{process.started_at}"


def connection_id(identity: ConnectionIdentity) -> str:
    remote = [identity.remote.ip, identity.remote.port] if identity.remote else None
    return json.dumps(
        [
            identity.process.pid,
            identity.process.started_at,
            identity.family,
            identity.protocol,
            identity.local.ip,
            identity.local.port,
            remote,
        ],
        separators=(",", ":"),
    )


def display_time(value: datetime | None) -> str:
    return value.astimezone().isoformat(sep=" ", timespec="seconds") if value else "尚无成功采样"


def connection_row(observed: ObservedConnection) -> dict[str, Any]:
    connection = observed.connection
    return {
        "id": connection_id(connection.identity),
        "process": connection.process_name,
        "pid": connection.pid if connection.pid is not None else "不可读",
        "local": str(connection.local),
        "remote": str(connection.remote) if connection.remote else "—（无远端）",
        "status": connection.status,
    }


def graph_options(
    connections: list[ObservedConnection],
    selected_id: str | None = None,
) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    if connections:
        first = connections[0].connection
        root = f"process:{process_id(first.process)}"
        pid = first.pid if first.pid is not None else "不可读"
        nodes.append(
            {
                "id": root,
                "name": f"{first.process_name}\nPID {pid}",
                "kind": "process",
                "x": 0,
                "y": 0,
                "symbol": "roundRect",
                "symbolSize": [112, 52],
                "itemStyle": {"color": "#0f766e"},
                "label": {"position": "inside", "color": "#ffffff", "fontSize": 12},
            }
        )
        remotes: dict[str, list[ObservedConnection]] = defaultdict(list)
        for observed in connections:
            connection = observed.connection
            if connection.remote is not None:
                remotes[f"{connection.family}:{connection.remote}"].append(observed)

        for index, (endpoint, group) in enumerate(sorted(remotes.items())):
            target = f"remote:{root}:{endpoint}"
            angle = 2 * pi * index / len(remotes) - pi / 2
            nodes.append(
                {
                    "id": target,
                    "name": str(group[0].connection.remote),
                    "kind": "remote",
                    "x": 240 * cos(angle),
                    "y": 160 * sin(angle),
                    "symbolSize": 20,
                    "itemStyle": {"color": "#64748b"},
                    "label": {"position": "top", "color": "#334155", "fontSize": 11},
                }
            )
            for offset, observed in enumerate(
                sorted(
                    group,
                    key=lambda item: connection_id(item.connection.identity),
                )
            ):
                connection = observed.connection
                identity = connection_id(connection.identity)
                selected = identity == selected_id
                links.append(
                    {
                        "id": identity,
                        "source": root,
                        "target": target,
                        "name": f"{connection.local} ↔ {connection.remote}\n{connection.status}",
                        "lineStyle": {
                            "curveness": (offset - (len(group) - 1) / 2)
                            * min(0.22, 1 / len(group)),
                            "color": "#d97706" if selected else "#94a3b8",
                            "width": 4 if selected else 2,
                            "opacity": 1,
                        },
                    }
                )

    return {
        "animation": False,
        "tooltip": {
            "trigger": "item",
            "renderMode": "richText",
            ":formatter": "params => params.data.name",
        },
        "series": [
            {
                "id": "connections",
                "type": "graph",
                "layout": "force",
                "roam": True,
                "draggable": True,
                "top": 50,
                "bottom": 50,
                "left": 85,
                "right": 85,
                # Stable IDs let ECharts retain positions; unchanged options are never resent.
                "force": {
                    "repulsion": 180,
                    "gravity": 0.2,
                    "edgeLength": 100,
                    "layoutAnimation": False,
                },
                "label": {"show": True},
                "emphasis": {"focus": "adjacency"},
                "data": nodes,
                "links": links,
            }
        ],
    }
