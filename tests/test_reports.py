import sqlite3
from fractions import Fraction

from retest.evidence.encoding import decode_evidence
from retest.evidence.registry import EvidenceRegistry
from retest.reports.ledger import ReportLedger
from retest.reports.retrieve import get
from retest.revisions.history import select_revision
from retest.revisions.model import Transition
from retest.revisions.storage import RevisionStore
from retest.wiring.storage import ManifestStore
from tests.support import Workbench, draft, outcome, port


class ReportTests(Workbench):
    def test_atomic_success(self):
        pair, routes = self.serial_pair()
        manifest = self.bind_pair('serial', pair, routes)
        issued = self.sign('serial', port(pair[0]), 2)
        self.assertEqual(issued.snapshot.manifest, manifest)
        self.assertIsInstance(issued.snapshot.on_time, Fraction)
        self.assertEqual(outcome(issued), (1, 0))
        with self.center() as db:
            rows = db.execute('SELECT reports.report_id, receipts.report_id, status FROM reports JOIN receipts USING(report_id)').fetchall()
            self.assertEqual(rows, [(issued.report_id, issued.report_id, 'issued')])
            self.assertEqual(get(ReportLedger(db), issued.report_id), issued)
        self.assertEqual(self.center_counts(), (1, 1, 1))

    def test_publication_rollback(self):
        pair, routes = self.serial_pair()
        self.bind_pair('serial', pair, routes)
        original = self.sign('serial', port(pair[0]), 2)
        with self.center() as db:
            db.execute('''CREATE TRIGGER refuse_receipt BEFORE INSERT ON receipts
                WHEN EXISTS (SELECT 1 FROM reports WHERE report_id = NEW.report_id)
                BEGIN SELECT RAISE(ABORT, 'receipt denied after staging'); END''')
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'receipt denied after staging'):
            self.sign('serial', port(pair[0]), 1)
        self.assertEqual(self.center_counts(), (1, 1, 1))
        self.assertEqual(self.retrieve(original.report_id), original)
        with self.assertRaises(KeyError):
            self.retrieve(original.report_id + 1)

    def test_original_report_after_correction(self):
        pair, routes = self.serial_pair()
        original_manifest = self.bind_pair('serial', pair, routes, source='night routing sheet')
        original = self.sign('serial', port(pair[0]), 2)
        corrected = self.issued(draft('A', 'r2', predecessor='r1', edges=(Transition('out', 1, 3, True),)))
        corrected_manifest = self.bind_pair('corrected', (corrected, pair[1]),
                                            [(port(corrected, 'out'), port(pair[1])), routes[1]],
                                            source='handover routing sheet')
        self.stop_sources()
        updated = self.sign('corrected', port(corrected), 2)
        self.assertEqual(outcome(updated), (0, 0))
        self.assertEqual(updated.snapshot.manifest, corrected_manifest)
        self.assertEqual(updated.snapshot.origins[0].revision_id, 'r2')
        self.assertEqual(updated.snapshot.origins[0].predecessor, 'r1')
        original_read = self.retrieve(original.report_id)
        self.assertEqual(original_read, original)
        self.assertEqual(outcome(original_read), (1, 0))
        self.assertEqual(original_read.snapshot.manifest, original_manifest)
        self.assertEqual(original_read.snapshot.origins, tuple(decode_evidence(body).origin for body in pair))
        self.assertEqual(original_read.receipt, original.receipt)

    def test_reinitialize(self):
        pair, routes = self.serial_pair()
        self.bind_pair('serial', pair, routes)
        first = self.sign('serial', port(pair[0]), 2)
        revised = self.issued(draft('A', 'r2', predecessor='r1', edges=(Transition('out', 1, 4, True),)))
        current_manifest = self.bind_pair('corrected', (revised, pair[1]), [(port(revised, 'out'), port(pair[1])), routes[1]])
        current = self.sign('corrected', port(revised), 2)
        before_counts = self.center_counts()
        with self.source('A') as db:
            revisions, registry = RevisionStore(db), EvidenceRegistry(db)
            revisions.initialize()
            registry.initialize()
        with self.center() as db:
            ManifestStore(db).initialize()
            ReportLedger(db).initialize()
        with self.source('A') as db:
            revisions, registry = RevisionStore(db), EvidenceRegistry(db)
            self.assertEqual(select_revision(revisions, 'A', 'r1').source.trial_id, 'trial-A-r1')
            self.assertEqual(select_revision(revisions, 'A', 'r2').predecessor, 'r1')
            for body in (pair[0], revised):
                self.assertEqual(registry.read(decode_evidence(body).piece_id), body)
            self.assertEqual(db.execute('SELECT count(*) FROM revisions').fetchone()[0], 2)
            self.assertEqual(db.execute('SELECT count(*) FROM issued_evidence').fetchone()[0], 2)
        with self.center() as db:
            self.assertEqual(ManifestStore(db).load('corrected')[0], current_manifest)
        self.assertEqual(self.retrieve(first.report_id), first)
        self.assertEqual(self.retrieve(current.report_id), current)
        self.assertEqual(self.center_counts(), before_counts)
        self.assertEqual(before_counts, (2, 2, 2))

    def test_unknown_report(self):
        with self.assertRaises(KeyError):
            self.retrieve(999)
        self.assertEqual(self.center_counts(), (0, 0, 0))
