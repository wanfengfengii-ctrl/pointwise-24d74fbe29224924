from collections import defaultdict
from fractions import Fraction

from retest.evidence.series import EntryExitEvidence, ExitSeries
from retest.revisions.model import Revision, Transition


ZERO = ExitSeries(())
UNIT = ExitSeries.monomial(0, Fraction(1))


def _states_reaching_an_exit(rows: dict[str, tuple[Transition, ...]]) -> list[str]:
    predecessors: dict[str, set[str]] = defaultdict(set)
    reachable = set()
    for state, edges in rows.items():
        for edge in edges:
            if edge.probability == 0:
                continue
            if edge.is_exit:
                reachable.add(state)
            else:
                predecessors[edge.target].add(state)
    pending = list(reachable)
    while pending:
        new_states = predecessors[pending.pop()] - reachable
        reachable.update(new_states)
        pending.extend(new_states)
    return sorted(reachable)


def _solve(augmented: list[list[ExitSeries]]) -> None:
    # I - Q(0) on the exit-capable states is transient, as are its leading
    # principal submatrices. Every pivot is therefore invertible at zero.
    for column in range(len(augmented)):
        pivot = augmented[column][column]
        normalized = [value / pivot for value in augmented[column]]
        augmented[column] = normalized
        for index, row in enumerate(augmented):
            if index != column and row[column]:
                factor = row[column]
                augmented[index] = [value - factor * coefficient for value, coefficient in zip(row, normalized)]


def compile_first_exits(revision: Revision) -> tuple[tuple[str, EntryExitEvidence], ...]:
    rows = dict(revision.transitions)
    states = _states_reaching_an_exit(rows)
    state_index = {state: index for index, state in enumerate(states)}
    count = len(states)
    exit_index = {name: count + index for index, name in enumerate(revision.exits)}
    size = count + len(exit_index)
    equations = [[ZERO] * size for _ in states]
    for index, state in enumerate(states):
        row = equations[index]
        row[index] = UNIT
        for edge in rows[state]:
            if not edge.probability:
                continue
            term = ExitSeries.monomial(edge.ticks, Fraction(edge.probability))
            if edge.is_exit:
                column = exit_index[edge.target]
                row[column] = row[column] + term
            elif edge.target in state_index:
                column = state_index[edge.target]
                row[column] = row[column] - term
    _solve(equations)

    result = []
    zero_row = [ZERO] * size
    for entrance, state in revision.entries:
        row = equations[state_index[state]] if state in state_index else zero_row
        exits = tuple((name, row[exit_index[name]]) for name in revision.exits)
        exit_mass = sum((series.total_mass() for _, series in exits), Fraction(0))
        result.append((entrance, EntryExitEvidence(exits, 1 - exit_mass)))
    return tuple(result)
