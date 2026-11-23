import json
from dataclasses import asdict, dataclass
from fractions import Fraction

from retest.evidence.encoding import EvidenceOrigin
from retest.wiring.manifest import Manifest
from retest.wiring.ports import PortRef


@dataclass(frozen=True)
class ReportSnapshot:
    manifest: Manifest
    origins: tuple[EvidenceOrigin, EvidenceOrigin]
    start: PortRef
    deadline: int
    on_time: Fraction
    never_complete: Fraction


def build_snapshot(manifest: Manifest, origins: tuple[EvidenceOrigin, EvidenceOrigin], start: PortRef,
                   deadline: int, on_time: Fraction, never_complete: Fraction) -> ReportSnapshot:
    if len(origins) != 2 or start.piece_id not in manifest.parents:
        raise ValueError('report requires its pinned pair and starting entrance')
    if type(deadline) is not int or deadline < 0:
        raise ValueError('invalid snapshot deadline')
    if not isinstance(on_time, Fraction) or not isinstance(never_complete, Fraction):
        raise ValueError('report probabilities must be exact')
    if on_time < 0 or never_complete < 0 or on_time + never_complete > 1:
        raise ValueError('invalid probability judgment')
    return ReportSnapshot(manifest, origins, start, deadline, on_time, never_complete)


def encode_snapshot(snapshot: ReportSnapshot) -> str:
    return json.dumps({
        'manifest': snapshot.manifest.to_record(),
        'origins': [asdict(origin) for origin in snapshot.origins],
        'start': snapshot.start.to_record(),
        'deadline': snapshot.deadline,
        'on_time': str(snapshot.on_time),
        'never_complete': str(snapshot.never_complete),
    }, sort_keys=True, separators=(',', ':'))


def decode_snapshot(body: str) -> ReportSnapshot:
    data = json.loads(body)
    first, second = data['origins']
    return build_snapshot(Manifest.from_record(data['manifest']),
                          (EvidenceOrigin(**first), EvidenceOrigin(**second)),
                          PortRef.from_record(data['start']), data['deadline'],
                          Fraction(data['on_time']), Fraction(data['never_complete']))
