from collections.abc import Iterable, Sequence

from retest.wiring.intake import receive_evidence
from retest.wiring.manifest import Destination, Manifest, build_manifest
from retest.wiring.ports import PortRef
from retest.wiring.storage import ManifestStore


def bind(store: ManifestStore, manifest_id: str, source: str, bodies: Sequence[str],
         connections: Iterable[tuple[PortRef, Destination]]) -> Manifest:
    if not isinstance(bodies, Sequence) or isinstance(bodies, (str, bytes)) or len(bodies) != 2:
        raise ValueError('exactly two station bodies are required')
    first, second = bodies
    received = (receive_evidence(first), receive_evidence(second))
    manifest = build_manifest(manifest_id, source, received, connections)
    store.save(manifest, received)
    return manifest
