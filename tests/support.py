import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

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


def draft(station, revision_id='r1', *, order='order-12', round_id='round-1', predecessor=None,
          exits=('out',), edges=None, entries=None, extra=None):
    if edges is None:
        edges = (Transition('out', 1, 1, True),)
    return RevisionDraft(station, revision_id, TrialSource(order, round_id, f'trial-{station}-{revision_id}'),
                         {'x': 'private-bench'} if entries is None else entries, exits,
                         {'private-bench': edges, **(extra or {})}, predecessor)


def port(body, name='x'):
    return PortRef(decode_evidence(body).piece_id, name)


def outcome(report):
    return report.snapshot.on_time, report.snapshot.never_complete


class Workbench(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory(prefix='retest-check-')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.center_path = self.root / 'center.sqlite'
        with self.center() as db:
            ManifestStore(db).initialize()
            ReportLedger(db).initialize()

    def center(self):
        return closing(sqlite3.connect(self.center_path))

    def source(self, station):
        return closing(sqlite3.connect(self.root / f'{station}.sqlite'))

    def issued(self, revision):
        with self.source(revision.station) as db:
            revisions, registry = RevisionStore(db), EvidenceRegistry(db)
            revisions.initialize()
            registry.initialize()
            register(revisions, revision)
            return issue(revisions, registry, revision.station, revision.revision_id)

    def stop_sources(self):
        for path in self.root.glob('[AB].sqlite'):
            path.unlink()

    def bind_pair(self, name, pair, routes, source='routing-card-12'):
        with self.center() as db:
            return bind(ManifestStore(db), name, source, pair, routes)

    def sign(self, name, start, deadline):
        with self.center() as db:
            return review(ManifestStore(db), ReportLedger(db), ReviewRequest(name, start, deadline))

    def retrieve(self, report_id):
        with self.center() as db:
            return get(ReportLedger(db), report_id)

    def center_counts(self):
        with self.center() as db:
            return tuple(db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
                         for table in ('manifests', 'reports', 'receipts'))

    def serial_pair(self):
        first, second = self.issued(draft('A')), self.issued(draft('B'))
        return (first, second), [(port(first, 'out'), port(second)), (port(second, 'out'), None)]

    def retest_pair(self, done_ticks, return_ticks, *, revision_id='r1', predecessor=None):
        first = self.issued(draft('A', revision_id, predecessor=predecessor, exits=('done', 'retest'), edges=(
            Transition('done', '1/2', done_ticks, True),
            Transition('retest', '1/2', return_ticks, True),
        )))
        second = self.issued(draft('B', edges=(Transition('out', 1, 0, True),)))
        return first, second

    def retest_routes(self, pair):
        first, second = pair
        return [(port(first, 'done'), None), (port(first, 'retest'), port(second)), (port(second, 'out'), port(first))]
