from retest.evidence.encoding import EvidenceOrigin, StationEvidence, encode_evidence
from retest.evidence.first_exit import compile_first_exits
from retest.evidence.registry import EvidenceRegistry
from retest.revisions.history import select_revision
from retest.revisions.storage import RevisionStore


def issue(revisions: RevisionStore, registry: EvidenceRegistry, station: str, revision_id: str) -> str:
    revision = select_revision(revisions, station, revision_id)
    source = revision.source
    origin = EvidenceOrigin(revision.station, revision.revision_id, source.work_order,
                            source.round_id, source.trial_id, revision.predecessor)
    evidence = StationEvidence(origin, revision.exits, compile_first_exits(revision))
    body = encode_evidence(evidence)
    registry.record(body)
    return body
