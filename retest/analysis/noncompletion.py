from collections import defaultdict
from fractions import Fraction

from retest.analysis.handoff import Handoff
from retest.analysis.same_tick import build_same_tick_closure
from retest.wiring.ports import PortRef


ZERO = Fraction(0)
ONE = Fraction(1)


def calculate_noncompletion_probability(handoff: Handoff) -> Fraction:
    direct: dict[PortRef, Fraction] = {}
    continuation: dict[PortRef, dict[PortRef, Fraction]] = {}
    predecessors: dict[PortRef, set[PortRef]] = defaultdict(set)
    for source, routes in handoff.routes:
        direct[source] = ZERO
        continuation[source] = {}
        for route in routes:
            mass = route.series.total_mass()
            if not mass:
                continue
            target = route.destination
            if target is None:
                direct[source] += mass
            else:
                continuation[source][target] = continuation[source].get(target, ZERO) + mass
                predecessors[target].add(source)

    reachable = {source for source, mass in direct.items() if mass}
    pending = list(reachable)
    while pending:
        newly_reachable = predecessors[pending.pop()] - reachable
        reachable.update(newly_reachable)
        pending.extend(newly_reachable)
    if handoff.start not in reachable:
        return ONE
    order = sorted(reachable)
    matrix = [[continuation[source].get(target, ZERO) for target in order] for source in order]
    eventual = build_same_tick_closure(matrix).solve([direct[source] for source in order])
    return ONE - eventual[order.index(handoff.start)]
