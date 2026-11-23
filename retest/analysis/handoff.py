from dataclasses import dataclass

from retest.evidence.encoding import EvidenceOrigin
from retest.evidence.series import ExitSeries
from retest.wiring.manifest import Destination, Manifest
from retest.wiring.ports import PortRef, index_public_ports, resolve_public_port
from retest.wiring.storage import ManifestStore


@dataclass(frozen=True)
class RoutedExit:
    outlet: PortRef
    destination: Destination
    series: ExitSeries


@dataclass(frozen=True)
class Handoff:
    manifest: Manifest
    origins: tuple[EvidenceOrigin, EvidenceOrigin]
    start: PortRef
    routes: tuple[tuple[PortRef, tuple[RoutedExit, ...]], ...]


def resolve_handoff(store: ManifestStore, manifest_id: str, start: PortRef) -> Handoff:
    if not isinstance(manifest_id, str) or not manifest_id.strip():
        raise ValueError('manifest identity is required')
    manifest, (first, second) = store.load(manifest_id)
    entrances, _ = index_public_ports((first.evidence, second.evidence))
    start = resolve_public_port(start, entrances)
    destinations = dict(manifest.connections)
    routes = []
    for item in (first, second):
        piece_id = item.piece_id
        for name, evidence in item.evidence.entries:
            exits = []
            for exit_name, series in evidence.exits:
                outlet = PortRef(piece_id, exit_name)
                exits.append(RoutedExit(outlet, destinations[outlet], series))
            routes.append((PortRef(piece_id, name), tuple(exits)))
    return Handoff(manifest, (first.evidence.origin, second.evidence.origin), start, tuple(routes))
