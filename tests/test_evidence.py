from dataclasses import replace
from fractions import Fraction as F

from retest.evidence.encoding import decode_evidence
from retest.evidence.issue import issue
from retest.evidence.registry import EvidenceRegistry
from retest.revisions.history import select_revision
from retest.revisions.model import Transition, TrialSource
from retest.revisions.registry import register
from retest.revisions.storage import RevisionStore
from tests.support import Workbench, draft


class EvidenceTests(Workbench):
    def test_issue_selected_revision(self):
        body = self.issued(draft('A'))
        decoded = decode_evidence(body)
        self.assertEqual((decoded.origin.station, decoded.origin.revision_id, decoded.origin.trial_id),
                         ('A', 'r1', 'trial-A-r1'))
        evidence = dict(decoded.entries)['x']
        series = dict(evidence.exits)['out']
        self.assertEqual(series.coefficients_through(2), (0, 1, 0))
        self.assertEqual((series.total_mass(), evidence.never_exit), (1, 0))
        self.assertNotIn('private-bench', body)
        with self.source('A') as db:
            self.assertEqual(EvidenceRegistry(db).read(decoded.piece_id), body)

    def test_explicit_old_after_correction(self):
        old = self.issued(draft('A'))
        new = self.issued(draft('A', 'r2', predecessor='r1', edges=(Transition('out', 1, 2, True),)))
        with self.source('A') as db:
            revisions, registry = RevisionStore(db), EvidenceRegistry(db)
            reissued = issue(revisions, registry, 'A', 'r1')
            self.assertEqual(reissued, old)
            self.assertEqual(registry.read(decode_evidence(old).piece_id), old)
        previous, current = decode_evidence(reissued), decode_evidence(new)
        self.assertEqual(previous.origin.trial_id, 'trial-A-r1')
        self.assertEqual((current.origin.trial_id, current.origin.predecessor), ('trial-A-r2', 'r1'))
        self.assertEqual(dict(dict(previous.entries)['x'].exits)['out'].coefficients_through(2), (0, 1, 0))
        self.assertEqual(dict(dict(current.entries)['x'].exits)['out'].coefficients_through(2), (0, 0, 1))

    def test_same_marginals(self):
        rows = []
        for revision_id, done, retry in [('r1', 1, 2), ('r2', 2, 1)]:
            body = self.issued(draft('A', revision_id, exits=('done', 'retest'), edges=(
                Transition('done', '1/2', done, True), Transition('retest', '1/2', retry, True),
            )))
            evidence = dict(decode_evidence(body).entries)['x']
            series = dict(evidence.exits)
            prefix = [series[name].coefficients_through(2) for name in ('done', 'retest')]
            self.assertEqual([series[name].total_mass() for name in ('done', 'retest')], [F(1, 2), F(1, 2)])
            self.assertEqual(tuple(map(sum, zip(*prefix))), (0, F(1, 2), F(1, 2)))
            self.assertEqual(evidence.never_exit, 0)
            rows.append(prefix)
        self.assertEqual(rows, [[(0, F(1, 2), 0), (0, 0, F(1, 2))], [(0, 0, F(1, 2)), (0, F(1, 2), 0)]])

    def test_reject_invalid_mass(self):
        original = self.issued(draft('A'))
        invalid = draft('A', 'r2', edges=(Transition('out', '3/4', 1, True), Transition('out', '3/4', 2, True)))
        with self.source('A') as db:
            revisions, registry = RevisionStore(db), EvidenceRegistry(db)
            with self.assertRaisesRegex(ValueError, 'branch mass'):
                register(revisions, invalid)
            with self.assertRaises(KeyError):
                select_revision(revisions, 'A', 'r2')
            with self.assertRaises(KeyError):
                issue(revisions, registry, 'A', 'r2')
            self.assertEqual(issue(revisions, registry, 'A', 'r1'), original)
            self.assertEqual(db.execute('SELECT count(*) FROM revisions').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT count(*) FROM issued_evidence').fetchone()[0], 1)

    def test_invalid_drafts_leave_revision_store_unchanged(self):
        self.issued(draft('B'))
        valid = draft('A')
        with self.source('B') as db:
            revisions = RevisionStore(db)
            invalid = (
                replace(valid, predecessor='r1', revision_id='r2'),
                replace(valid, source=TrialSource('order-12', 'round-1', ' ')),
                replace(valid, entries={'x': 'missing'}),
                replace(valid, transitions={'private-bench': ()}),
                draft('A', edges=(Transition('missing', 1, 0),)),
                draft('A', edges=(Transition('out', 1.0, 0, True),)),
                draft('A', edges=(Transition('out', 1, True, True),)),
                draft('B'),
            )
            for item in invalid:
                with self.subTest(item=item), self.assertRaises(ValueError):
                    register(revisions, item)
            self.assertEqual(db.execute('SELECT station, revision_id FROM revisions').fetchall(), [('B', 'r1')])

    def test_station_closed_branch(self):
        body = self.issued(draft('A', edges=(Transition('out', '1/2', 1, True), Transition('private-lock', '1/2', 0)),
                                 extra={'private-lock': (Transition('private-lock', 1, 2),)}))
        decoded = decode_evidence(body)
        entry = dict(decoded.entries)['x']
        series = dict(entry.exits)['out']
        self.assertEqual(series.coefficients_through(3), (0, F(1, 2), 0, 0))
        self.assertEqual((series.total_mass(), entry.never_exit), (F(1, 2), F(1, 2)))
        self.assertNotIn('private-lock', body)

    def test_station_series_keeps_unbounded_tail_and_entry_identity(self):
        body = self.issued(draft('A', entries={'x': 'private-bench', 'quick': 'private-quick'}, edges=(
            Transition('private-bench', '1/4', 0), Transition('private-bench', '1/4', 2),
            Transition('out', '1/2', 1, True),
        ), extra={'private-quick': (Transition('out', 1, 0, True),)}))
        entries = dict(decode_evidence(body).entries)
        long_tail = dict(entries['x'].exits)['out']
        self.assertEqual(long_tail.coefficients_through(7), (0, F(2, 3), 0, F(2, 9), 0, F(2, 27), 0, F(2, 81)))
        self.assertEqual(long_tail.total_mass(), 1)
        self.assertEqual(dict(entries['quick'].exits)['out'].coefficients_through(1), (1, 0))
