from dataclasses import dataclass
from fractions import Fraction

from retest.analysis.deadline import calculate_deadline_probability
from retest.analysis.handoff import resolve_handoff
from retest.analysis.noncompletion import calculate_noncompletion_probability
from retest.reports.ledger import IssuedReport, ReportLedger
from retest.reports.publish import publish
from retest.reports.snapshot import build_snapshot
from retest.wiring.ports import PortRef
from retest.wiring.storage import ManifestStore


@dataclass(frozen=True)
class ReviewRequest:
    manifest_id: str
    start: PortRef
    deadline: int


@dataclass(frozen=True)
class Judgment:
    on_time: Fraction
    never_complete: Fraction

    def __post_init__(self) -> None:
        if self.on_time < 0 or self.never_complete < 0 or self.on_time + self.never_complete > 1:
            raise ValueError('inconsistent completion probabilities')


def review(manifests: ManifestStore, ledger: ReportLedger, request: ReviewRequest) -> IssuedReport:
    if not isinstance(request, ReviewRequest) or type(request.deadline) is not int or request.deadline < 0:
        raise ValueError('review requires a nonnegative integer deadline')
    handoff = resolve_handoff(manifests, request.manifest_id, request.start)
    judgment = Judgment(calculate_deadline_probability(handoff, request.deadline),
                        calculate_noncompletion_probability(handoff))
    snapshot = build_snapshot(handoff.manifest, handoff.origins, handoff.start, request.deadline,
                              judgment.on_time, judgment.never_complete)
    return publish(ledger, snapshot)
