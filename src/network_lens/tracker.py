"""Pure comparison of consecutive successful snapshots."""

from dataclasses import dataclass, field
from datetime import datetime

from .models import ConnectionIdentity, Observation, ObservedConnection, Snapshot


@dataclass(frozen=True)
class TrackingState:
    connections: dict[ConnectionIdentity, ObservedConnection] = field(default_factory=dict)
    events: tuple[Observation, ...] = ()
    last_success: datetime | None = None
    error: str | None = None
    warnings: tuple[str, ...] = ()


def advance(state: TrackingState, snapshot: Snapshot) -> TrackingState:
    """Return a new state without mutating either input; errors never remove connections."""
    if snapshot.error is not None:
        return TrackingState(
            state.connections,
            state.events,
            state.last_success,
            snapshot.error,
            state.warnings,
        )

    current: dict[ConnectionIdentity, ObservedConnection] = {}
    new_events = []
    for connection in snapshot.connections:
        identity = connection.identity
        if identity in current:
            continue
        previous = state.connections.get(identity)
        observed = ObservedConnection(
            connection,
            previous.first_observed if previous else snapshot.sampled_at,
            snapshot.sampled_at,
        )
        current[identity] = observed
        if previous is None:
            new_events.append(Observation("FIRST_OBSERVED", snapshot.sampled_at, observed))

    for identity, previous in state.connections.items():
        if identity not in current:
            new_events.append(Observation("NO_LONGER_OBSERVED", snapshot.sampled_at, previous))

    return TrackingState(
        current,
        (state.events + tuple(new_events))[-100:],
        snapshot.sampled_at,
        warnings=snapshot.warnings,
    )
