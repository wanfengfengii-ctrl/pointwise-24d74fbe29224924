from fractions import Fraction
from itertools import accumulate

from retest.analysis.handoff import Handoff
from retest.analysis.same_tick import build_same_tick_closure


ZERO = Fraction(0)


def calculate_deadline_probability(handoff: Handoff, deadline: int) -> Fraction:
    if type(deadline) is not int or deadline < 0:
        raise ValueError('deadline must be a nonnegative integer tick')
    positions = {entrance: index for index, (entrance, _) in enumerate(handoff.routes)}
    size = len(positions)
    same_tick = [[ZERO] * size for _ in range(size)]
    terminal = []
    delayed = []
    for index, (_, routes) in enumerate(handoff.routes):
        finish_at = [ZERO] * (deadline + 1)
        transfers = []
        for route in routes:
            coefficients = route.series.coefficients_through(deadline)
            if any(mass < 0 for mass in coefficients) or sum(coefficients, ZERO) > route.series.total_mass():
                raise ValueError('exit coefficients contradict their probability mass')
            if route.destination is None:
                for tick, mass in enumerate(coefficients):
                    finish_at[tick] += mass
            else:
                target = positions[route.destination]
                same_tick[index][target] += coefficients[0]
                transfers.extend((tick, target, mass) for tick, mass in enumerate(coefficients[1:], 1) if mass)
        terminal.append(tuple(accumulate(finish_at)))
        delayed.append(sorted(transfers))

    closure = build_same_tick_closure(same_tick)
    values = []
    for remaining in range(deadline + 1):
        rhs = []
        for finish, transfers in zip(terminal, delayed):
            contribution = finish[remaining]
            for ticks, target, mass in transfers:
                if ticks > remaining:
                    break
                contribution += mass * values[remaining - ticks][target]
            rhs.append(contribution)
        values.append(closure.solve(rhs))
    return values[-1][positions[handoff.start]]
