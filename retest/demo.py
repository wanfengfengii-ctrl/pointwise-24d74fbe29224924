import json
import sqlite3
from contextlib import closing
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

from retest.analysis.review import ReviewRequest, review
from retest.evidence.encoding import decode_evidence
from retest.evidence.issue import issue
from retest.evidence.registry import EvidenceRegistry
from retest.reports.ledger import IssuedReport, ReportLedger
from retest.reports.retrieve import get
from retest.revisions.model import RevisionDraft, Transition, TrialSource
from retest.revisions.registry import register
from retest.revisions.storage import RevisionStore
from retest.wiring.binding import bind
from retest.wiring.ports import PortRef
from retest.wiring.storage import ManifestStore


EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'


def _load(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding='utf-8'))


def _install(path: Path, data: dict) -> str:
    draft = RevisionDraft(
        data['station'], data['revision_id'], TrialSource(**data['source']),
        data['entries'], data['exits'],
        {state: [Transition(**item) for item in row] for state, row in data['transitions'].items()},
        data.get('predecessor'),
    )
    with closing(sqlite3.connect(path)) as db:
        revisions, registry = RevisionStore(db), EvidenceRegistry(db)
        revisions.initialize()
        registry.initialize()
        register(revisions, draft)
        return issue(revisions, registry, draft.station, draft.revision_id)


def _sign(center: Path, settings: dict, bodies: tuple[str, str]) -> tuple[IssuedReport, ...]:
    identities = {}
    for body in bodies:
        evidence = decode_evidence(body)
        identities[evidence.origin.station] = evidence.piece_id

    def port(endpoint: list[str]) -> PortRef:
        station, name = endpoint
        return PortRef(identities[station], name)

    routes = [(port(outlet), port(target) if target is not None else None) for outlet, target in settings['routes']]
    with closing(sqlite3.connect(center)) as db:
        store, ledger = ManifestStore(db), ReportLedger(db)
        store.initialize()
        ledger.initialize()
        manifest = bind(store, settings['manifest_id'], settings['wiring_source'], bodies, routes)
        start = port(settings['start'])
        return tuple(review(store, ledger, ReviewRequest(manifest.manifest_id, start, tick))
                     for tick in settings['deadlines'])


def _result(report: IssuedReport) -> dict:
    snapshot = report.snapshot
    return {'id': report.report_id, 'deadline': snapshot.deadline, 'on_time': str(snapshot.on_time),
            'never_complete': str(snapshot.never_complete), 'manifest': snapshot.manifest.manifest_id,
            'revisions': [item.revision_id for item in snapshot.origins], 'receipt': report.receipt.status}


def main() -> None:
    day = _load('day.json')
    correction = _load('correction.json')
    with TemporaryDirectory(prefix='retest-demo-') as work:
        root = Path(work)
        a_path, b_path, center = root / 'a.sqlite', root / 'b.sqlite', root / 'center.sqlite'
        a = _install(a_path, day['stations'][0])
        b = _install(b_path, day['stations'][1])
        b_path.unlink()
        initial = _sign(center, day, (a, b))
        corrected_a = _install(a_path, correction['station'])
        a_path.unlink()
        updated = _sign(center, {**day, **correction['wiring']}, (corrected_a, b))
        with closing(sqlite3.connect(center)) as db:
            ledger = ReportLedger(db)
            ledger.initialize()
            retrieved = tuple(get(ledger, previous.report_id) for previous in initial)
        if ([item.snapshot.on_time for item in initial] != [Fraction(1, 2), Fraction(3, 4)]
                or [item.snapshot.on_time for item in updated] != [0, Fraction(3, 4)]
                or any(item.snapshot.never_complete for item in (*initial, *updated))
                or retrieved != initial):
            raise RuntimeError('demo calculation or report retrieval does not match the sample')
        print(json.dumps({'initial': [_result(report) for report in initial],
                          'corrected': [_result(report) for report in updated],
                          'retrieved': [_result(report) for report in retrieved]}, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
