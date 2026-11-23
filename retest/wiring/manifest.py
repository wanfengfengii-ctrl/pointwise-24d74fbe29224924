from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from retest.wiring.intake import ReceivedEvidence
from retest.wiring.ports import PortRef, index_public_ports, resolve_public_port


Destination = PortRef | None


@dataclass(frozen=True)
class Manifest:
    manifest_id: str
    source: str
    parents: tuple[str, str]
    connections: tuple[tuple[PortRef, Destination], ...]

    def to_record(self) -> dict:
        return {
            'id': self.manifest_id,
            'source': self.source,
            'parents': list(self.parents),
            'connections': [[outlet.to_record(), None if destination is None else destination.to_record()]
                            for outlet, destination in self.connections],
        }

    @classmethod
    def from_record(cls, record: dict) -> 'Manifest':
        first, second = record['parents']
        connections = tuple((PortRef.from_record(outlet), None if target is None else PortRef.from_record(target))
                            for outlet, target in record['connections'])
        return cls(record['id'], record['source'], (first, second), connections)


def build_manifest(manifest_id: str, source: str, pair: Sequence[ReceivedEvidence],
                   connections: Iterable[tuple[PortRef, Destination]]) -> Manifest:
    if any(not isinstance(value, str) or not value.strip() for value in (manifest_id, source)):
        raise ValueError('manifest identity and wiring source are required')
    if len(pair) != 2:
        raise ValueError('exactly two received station pieces are required')
    first, second = pair
    first_origin = first.evidence.origin
    second_origin = second.evidence.origin
    if first_origin.station == second_origin.station:
        raise ValueError('received pieces must come from distinct stations')
    if (first_origin.work_order, first_origin.round_id) != (second_origin.work_order, second_origin.round_id):
        raise ValueError('received pieces must share a work order and round')
    entrances, exits = index_public_ports((first.evidence, second.evidence))
    routes: dict[PortRef, Destination] = {}
    try:
        candidates = iter(connections)
    except TypeError as error:
        raise ValueError('a sequence of outlet and destination pairs is required') from error
    for candidate in candidates:
        if not isinstance(candidate, (list, tuple)) or len(candidate) != 2:
            raise ValueError('invalid wiring entry')
        outlet, destination = candidate
        outlet = resolve_public_port(outlet, exits)
        if outlet in routes:
            raise ValueError('outlet has more than one wiring entry')
        if destination is not None:
            destination = resolve_public_port(destination, entrances)
        routes[outlet] = destination
    if routes.keys() != exits:
        raise ValueError('every received outlet requires a wiring entry')
    return Manifest(manifest_id, source, (first.piece_id, second.piece_id), tuple(sorted(routes.items())))
