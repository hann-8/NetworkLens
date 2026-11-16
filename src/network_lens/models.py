"""Immutable records shared by the collector, tracker and presentation."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class Endpoint:
    ip: str
    port: int

    def __str__(self) -> str:
        host = f"[{self.ip}]" if ":" in self.ip else self.ip
        return f"{host}:{self.port}"


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int | None
    started_at: float | None


@dataclass(frozen=True)
class ConnectionIdentity:
    process: ProcessIdentity
    family: str
    local: Endpoint
    remote: Endpoint | None
    protocol: str = "TCP"


@dataclass(frozen=True)
class Connection:
    pid: int | None
    process_name: str
    process_started_at: float | None
    family: str
    local: Endpoint
    remote: Endpoint | None
    status: str
    sampled_at: datetime
    protocol: str = "TCP"

    @property
    def process(self) -> ProcessIdentity:
        return ProcessIdentity(self.pid, self.process_started_at)

    @property
    def identity(self) -> ConnectionIdentity:
        return ConnectionIdentity(self.process, self.family, self.local, self.remote, self.protocol)


@dataclass(frozen=True)
class Snapshot:
    sampled_at: datetime
    connections: tuple[Connection, ...] = ()
    error: str | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObservedConnection:
    connection: Connection
    first_observed: datetime
    last_observed: datetime


@dataclass(frozen=True)
class Observation:
    kind: Literal["FIRST_OBSERVED", "NO_LONGER_OBSERVED"]
    observed_at: datetime
    connection: ObservedConnection
