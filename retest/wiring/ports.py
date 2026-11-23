from collections.abc import Collection, Iterable
from dataclasses import dataclass

from retest.evidence.encoding import StationEvidence


@dataclass(frozen=True, order=True)
class PortRef:
    piece_id: str
    name: str

    def to_record(self) -> list[str]:
        return [self.piece_id, self.name]

    @classmethod
    def from_record(cls, value: list[str]) -> 'PortRef':
        if not isinstance(value, list) or len(value) != 2 or any(not isinstance(part, str) for part in value):
            raise ValueError('invalid stored port reference')
        return cls(*value)


def index_public_ports(evidences: Iterable[StationEvidence]) -> tuple[frozenset[PortRef], frozenset[PortRef]]:
    entrances = set()
    exits = set()
    for evidence in evidences:
        piece_id = evidence.piece_id
        entrances.update(PortRef(piece_id, name) for name, _ in evidence.entries)
        exits.update(PortRef(piece_id, name) for name in evidence.exits)
    return frozenset(entrances), frozenset(exits)


def resolve_public_port(ref: PortRef, available: Collection[PortRef]) -> PortRef:
    if (not isinstance(ref, PortRef) or not isinstance(ref.piece_id, str)
            or not isinstance(ref.name, str) or ref not in available):
        raise ValueError(f'unknown public port for this direction: {ref!r}')
    return ref
