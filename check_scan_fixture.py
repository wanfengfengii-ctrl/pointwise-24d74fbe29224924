import json
import sqlite3
from contextlib import closing
from fractions import Fraction
from pathlib import Path

from retest.analysis.review import ReviewRequest, review
from retest.evidence.encoding import decode_evidence
from retest.evidence.issue import issue
from retest.evidence.registry import EvidenceRegistry
from retest.reports.ledger import ReportLedger
from retest.reports.retrieve import get
from retest.revisions.model import RevisionDraft, Transition, TrialSource
from retest.revisions.registry import register
from retest.revisions.storage import RevisionStore
from retest.wiring.binding import bind
from retest.wiring.ports import PortRef
from retest.wiring.storage import ManifestStore


FIXTURE = Path(__file__).resolve().parent / "examples" / "scan.json"


def load_cases():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def issue_v1_projection(name, model):
    rows = {
        state: [Transition(target, probability, ticks, is_exit)
                for target, probability, ticks, is_exit, _scan in edges]
        for state, edges in model["rows"].items()
    }
    station = model["station"]
    with closing(sqlite3.connect(":memory:")) as db:
        revisions, issued = RevisionStore(db), EvidenceRegistry(db)
        revisions.initialize()
        issued.initialize()
        draft = RevisionDraft(station, name, TrialSource("insulation-42", "night", name),
                              model["entries"], model["exits"], rows)
        register(revisions, draft)
        return issue(revisions, issued, station, name)


def verify(data):
    bodies = {name: issue_v1_projection(name, model) for name, model in data["models"].items()}
    fast = decode_evidence(bodies["fast"])
    slow = decode_evidence(bodies["slow"])
    if fast.entries != slow.entries:
        raise AssertionError("the two revisions must have identical unconditional entrance evidence")
    results = {}
    with closing(sqlite3.connect(":memory:")) as center:
        manifests, ledger = ManifestStore(center), ReportLedger(center)
        manifests.initialize()
        ledger.initialize()
        for case in data["cases"]:
            case_id = case["id"]
            pair = bodies[case["a"]], bodies["confirmation"]
            parents = {piece.origin.station: piece.piece_id for piece in map(decode_evidence, pair)}
            routes = [(PortRef(parents[src[0]], src[1]),
                       None if dst is None else PortRef(parents[dst[0]], dst[1]))
                      for src, dst in data["wiring"][case["wiring"]]]
            bind(manifests, case_id, "night routing card", pair, routes)
            request = ReviewRequest(case_id, PortRef(parents["A"], "in"), case["d"])
            report = review(manifests, ledger, request)
            actual = report.snapshot.on_time, report.snapshot.never_complete
            if actual != tuple(map(Fraction, case["v1"])) or get(ledger, report.report_id) != report:
                raise AssertionError(f"{case_id}: V1 outcome or stored report differs")
            results[case_id] = list(map(str, actual))
    return results


if __name__ == "__main__":
    print(json.dumps(verify(load_cases()), sort_keys=True))
