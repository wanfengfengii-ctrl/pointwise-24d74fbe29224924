import json
from fractions import Fraction as F

from retest.evidence.encoding import decode_evidence
from retest.revisions.model import Transition
from retest.wiring.ports import PortRef
from tests.support import Workbench, draft, outcome, port


class ReviewTests(Workbench):
    def test_offline_serial_finish(self):
        pair, routes = self.serial_pair()
        manifest = self.bind_pair('serial', pair, routes)
        self.stop_sources()
        self.assertEqual(list(self.root.glob('[AB].sqlite')), [])
        early = self.sign('serial', port(pair[0]), 1)
        ready = self.sign('serial', port(pair[0]), 2)
        self.assertEqual((outcome(early), outcome(ready)), ((0, 0), (1, 0)))
        self.assertEqual(ready.snapshot.manifest, manifest)
        self.assertEqual(self.retrieve(ready.report_id), ready)

    def test_invalid_request(self):
        pair, routes = self.serial_pair()
        self.bind_pair('serial', pair, routes)
        cases = [('missing', port(pair[0]), 1, KeyError), ('serial', PortRef('missing', 'x'), 1, ValueError),
                 ('serial', port(pair[0], 'out'), 1, ValueError), ('serial', port(pair[0]), -1, ValueError),
                 ('serial', port(pair[0]), True, ValueError), ('serial', port(pair[0]), 1.0, ValueError)]
        for manifest, start, deadline, error in cases:
            with self.subTest(manifest=manifest, start=start, deadline=deadline), self.assertRaises(error):
                self.sign(manifest, start, deadline)
        self.assertEqual(self.center_counts(), (1, 0, 0))

    def test_retest_reenters(self):
        pair = self.retest_pair(1, 2)
        self.stop_sources()
        manifest = self.bind_pair('retest', pair, self.retest_routes(pair))
        reports = [self.sign('retest', port(pair[0]), tick) for tick in (1, 3)]
        actual = [outcome(report) for report in reports]
        expected = [(F(1, 2), F(0)), (F(3, 4), F(0))]
        self.assertEqual(actual, expected, 'RETEST_DEADLINE_MISMATCH')
        reread = [self.retrieve(report.report_id) for report in reports]
        self.assertEqual(reread, reports)
        self.assertEqual([report.snapshot.manifest.parents for report in reread], [manifest.parents, manifest.parents])
        print('POINTWISE_SCENARIO ' + json.dumps({
            'case_id': 'v6', 'input': {'finish_tick': 1, 'retest_tick': 2, 'branch_mass': '1/2', 'deadlines': [1, 3]},
            'expected': [[str(value) for value in row] for row in expected],
            'actual': [[str(value) for value in row] for row in actual],
            'downstream_expected': {'outcomes': [[str(value) for value in row] for row in expected], 'receipts': ['issued', 'issued']},
            'downstream_actual': {'outcomes': [[str(value) for value in outcome(report)] for report in reread],
                                  'receipts': [report.receipt.status for report in reread]},
            'code_paths': ['retest/evidence/first_exit.py', 'retest/wiring/storage.py', 'retest/analysis/deadline.py',
                           'retest/analysis/noncompletion.py', 'retest/reports/ledger.py'],
            'oracle': 'First pass contributes 1/2 at tick 1 and the second pass contributes 1/4 at tick 3. The probability of n consecutive returns is (1/2)^n.',
        }, sort_keys=True, separators=(',', ':')))

    def test_same_marginals_offline(self):
        original = self.retest_pair(1, 2)
        revised = self.issued(draft('A', 'r2', predecessor='r1', exits=('done', 'retest'), edges=(
            Transition('done', '1/2', 2, True), Transition('retest', '1/2', 1, True),
        )))
        self.stop_sources()
        cases = [('original', original, (F(1, 2), F(3, 4))), ('swapped', (revised, original[1]), (0, F(3, 4)))]
        for key, pair, expected in cases:
            self.bind_pair(key, pair, self.retest_routes(pair))
            reports = [self.sign(key, port(pair[0]), tick) for tick in (1, 3)]
            self.assertEqual([outcome(report) for report in reports], [(expected[0], 0), (expected[1], 0)])
        self.assertEqual(self.sign('original', port(original[0]), 1).snapshot.origins[0].revision_id, 'r1')

    def test_zero_tick_cycles(self):
        exit_pair = self.retest_pair(0, 0)
        closed = self.issued(draft('A', 'r2', predecessor='r1', exits=('done', 'retest'), edges=(
            Transition('retest', 1, 0, True),
        )))
        self.stop_sources()
        cases = [('instant', exit_pair, (1, 0)), ('closed', (closed, exit_pair[1]), (0, 1))]
        for manifest_id, pair, expected in cases:
            self.bind_pair(manifest_id, pair, self.retest_routes(pair))
            self.assertEqual(outcome(self.sign(manifest_id, port(pair[0]), 0)), expected)

    def test_station_trap(self):
        first = self.issued(draft('A', edges=(Transition('out', '1/2', 0, True), Transition('private-lock', '1/2', 0)),
                                 extra={'private-lock': (Transition('private-lock', 1, 0),)}))
        second = self.issued(draft('B', edges=(Transition('out', 1, 0, True),)))
        self.assertEqual(dict(decode_evidence(first).entries)['x'].never_exit, F(1, 2))
        self.stop_sources()
        self.bind_pair('trap', (first, second), [(port(first, 'out'), port(second)), (port(second, 'out'), None)])
        self.assertEqual(outcome(self.sign('trap', port(first), 0)), (F(1, 2), F(1, 2)))
        self.assertEqual(outcome(self.sign('trap', port(first), 10)), (F(1, 2), F(1, 2)))

    def test_positive_tick_recurring_path_can_finish_late(self):
        first, second = self.retest_pair(1, 2)
        self.stop_sources()
        self.bind_pair('late', (first, second), self.retest_routes((first, second)))
        self.assertEqual(outcome(self.sign('late', port(first), 0)), (0, 0))
        self.assertEqual(outcome(self.sign('late', port(first), 9)), (F(31, 32), 0))
