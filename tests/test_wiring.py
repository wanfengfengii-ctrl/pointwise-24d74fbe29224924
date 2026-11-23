import json

from retest.revisions.model import Transition
from retest.wiring.ports import PortRef
from retest.wiring.storage import ManifestStore
from tests.support import Workbench, draft, outcome, port


class WiringTests(Workbench):
    def test_intake_body(self):
        pair, routes = self.serial_pair()
        first, second = pair
        tampered = json.loads(second)
        tampered['origin']['trial_id'] = 'different trial'
        for invalid in ('{broken', json.dumps(tampered), second.replace('"version":1', '"version":1,"version":1')):
            with self.subTest(body=invalid), self.assertRaises(ValueError):
                self.bind_pair('bad', (first, invalid), routes)
        self.assertEqual(self.center_counts(), (0, 0, 0))
        exact_received = f'  {second}\n'
        manifest = self.bind_pair('valid', (first, exact_received), routes)
        with self.center() as db:
            loaded, received = ManifestStore(db).load('valid')
        self.assertEqual(loaded, manifest)
        self.assertEqual(received[1].body, exact_received)

    def test_same_named_ports(self):
        first = self.issued(draft('A', exits=('x',), edges=(Transition('x', 1, 1, True),)))
        second = self.issued(draft('B', exits=('x',), edges=(Transition('x', 1, 1, True),)))
        self.stop_sources()
        routes = [(port(first), port(second)), (port(second), None)]
        manifest = self.bind_pair('names', (first, second), routes)
        self.assertEqual(dict(manifest.connections)[port(first)], port(second))
        self.assertNotEqual(port(first), port(second))
        self.assertEqual(outcome(self.sign('names', port(first), 2)), (1, 0))
        self.assertEqual(outcome(self.sign('names', port(second), 1)), (1, 0))

    def test_dangling_or_missing(self):
        pair, routes = self.serial_pair()
        first, second = pair
        cases = [((first,), routes), ((first, first), routes), (pair, routes[:1]),
                 (pair, routes + [routes[0]]),
                 (pair, [(port(first, 'out'), PortRef('unknown', 'x')), routes[1]]),
                 (pair, [(port(first, 'x'), port(second)), routes[1]]),
                 (pair, [(port(first, 'out'), port(second, 'out')), routes[1]])]
        for bodies, connections in cases:
            with self.subTest(connections=connections), self.assertRaises(ValueError):
                self.bind_pair('invalid', bodies, connections)
        self.assertEqual(self.center_counts(), (0, 0, 0))
        original = self.bind_pair('kept', pair, routes)
        with self.assertRaises(ValueError):
            self.bind_pair('kept', pair, [(routes[0][0], None), routes[1]])
        with self.center() as db:
            self.assertEqual(ManifestStore(db).load('kept')[0], original)
        self.assertEqual(self.center_counts(), (1, 0, 0))

    def _assert_mixed_pair_rejected(self, **other):
        first = self.issued(draft('A'))
        second = self.issued(draft('B', **other))
        self.stop_sources()
        routes = [(port(first, 'out'), port(second)), (port(second, 'out'), None)]
        with self.assertRaisesRegex(ValueError, 'work order and round'):
            self.bind_pair('mixed', (first, second), routes)
        with self.assertRaises(KeyError):
            self.sign('mixed', port(first), 2)
        self.assertEqual(self.center_counts(), (0, 0, 0))

    def test_mixed_order_rejected(self):
        self._assert_mixed_pair_rejected(order='different-work')

    def test_mixed_round(self):
        self._assert_mixed_pair_rejected(round_id='round-2')
