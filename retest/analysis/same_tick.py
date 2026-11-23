from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction


ZERO = Fraction(0)


@dataclass(frozen=True)
class SameTickClosure:
    size: int
    transient: tuple[int, ...]
    inverse: tuple[tuple[Fraction, ...], ...]

    def solve(self, rhs: Sequence[Fraction]) -> tuple[Fraction, ...]:
        if len(rhs) != self.size:
            raise ValueError('right-hand side does not match continuation matrix')
        active = set(self.transient)
        if any(value and index not in active for index, value in enumerate(rhs)):
            raise ValueError('a closed same-tick component cannot have an exit contribution')
        reduced = tuple(rhs[index] for index in self.transient)
        result = [ZERO] * self.size
        for index, row in zip(self.transient, self.inverse):
            result[index] = sum((coefficient * value for coefficient, value in zip(row, reduced)), ZERO)
        return tuple(result)


def _inverse(matrix: list[list[Fraction]]) -> tuple[tuple[Fraction, ...], ...]:
    size = len(matrix)
    augmented = [row + [Fraction(index == column) for column in range(size)]
                 for index, row in enumerate(matrix)]
    for column in range(size):
        pivot = augmented[column][column]
        if not pivot:
            raise ArithmeticError('transient continuation matrix has a zero pivot')
        scaled = [value / pivot for value in augmented[column]]
        augmented[column] = scaled
        for index, row in enumerate(augmented):
            multiplier = row[column]
            if index != column and multiplier:
                augmented[index] = [value - multiplier * term for value, term in zip(row, scaled)]
    return tuple(tuple(row[size:]) for row in augmented)


def build_same_tick_closure(continuation: Sequence[Sequence[Fraction]]) -> SameTickClosure:
    size = len(continuation)
    predecessors = [set() for _ in range(size)]
    transient = set()
    for index, row in enumerate(continuation):
        if len(row) != size or any(value < 0 for value in row):
            raise ValueError('continuation must be a square nonnegative matrix')
        outgoing = sum(row, ZERO)
        if outgoing > 1:
            raise ValueError('continuation mass exceeds one')
        if outgoing < 1:
            transient.add(index)
        for target, mass in enumerate(row):
            if mass:
                predecessors[target].add(index)
    pending = list(transient)
    while pending:
        new_indices = predecessors[pending.pop()] - transient
        transient.update(new_indices)
        pending.extend(new_indices)
    # The rest are confined to rows that can never lose zero-tick mass.
    order = tuple(sorted(transient))
    equations = [[Fraction(source == target) - continuation[source][target] for target in order] for source in order]
    return SameTickClosure(size, order, _inverse(equations))
