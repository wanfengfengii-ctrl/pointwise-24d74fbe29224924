from dataclasses import dataclass
from fractions import Fraction


Polynomial = tuple[tuple[int, Fraction], ...]
ZERO = Fraction(0)
ONE = Fraction(1)
UNIT: Polynomial = ((0, ONE),)


def _terms(values: dict[int, Fraction]) -> Polynomial:
    return tuple((degree, value) for degree, value in sorted(values.items()) if value)


def _add(left: Polynomial, right: Polynomial, scale: Fraction = ONE) -> Polynomial:
    values = dict(left)
    for degree, value in right:
        values[degree] = values.get(degree, ZERO) + scale * value
    return _terms(values)


def _product(left: Polynomial, right: Polynomial) -> Polynomial:
    values: dict[int, Fraction] = {}
    for left_degree, left_value in left:
        for right_degree, right_value in right:
            degree = left_degree + right_degree
            values[degree] = values.get(degree, ZERO) + left_value * right_value
    return _terms(values)


def _divide(dividend: Polynomial, divisor: Polynomial) -> tuple[Polynomial, Polynomial]:
    divisor_degree, divisor_lead = divisor[-1]
    remainder = dict(dividend)
    quotient = {}
    while remainder:
        highest = max(remainder)
        if highest < divisor_degree:
            break
        shift = highest - divisor_degree
        factor = remainder[highest] / divisor_lead
        quotient[shift] = factor
        for degree, value in divisor:
            position = degree + shift
            updated = remainder.get(position, ZERO) - factor * value
            if updated:
                remainder[position] = updated
            else:
                remainder.pop(position, None)
    return _terms(quotient), _terms(remainder)


def _check_polynomial(terms: Polynomial) -> None:
    previous = -1
    for degree, mass in terms:
        if type(degree) is not int or degree <= previous or not isinstance(mass, Fraction) or not mass:
            raise ValueError('polynomial terms must be nonzero exact coefficients in degree order')
        previous = degree


def _reduce(numerator: Polynomial, denominator: Polynomial) -> tuple[Polynomial, Polynomial]:
    if not numerator:
        return (), UNIT
    # A monomial shares no nonconstant factor with a denominator regular at zero.
    if len(numerator) > 1 and len(denominator) > 1:
        left, right = numerator, denominator
        while right and right[-1][0] > 0:
            _, remainder = _divide(left, right)
            left, right = right, remainder
        if not right:
            numerator, _ = _divide(numerator, left)
            denominator, _ = _divide(denominator, left)
    constant = denominator[0][1]
    return (tuple((degree, mass / constant) for degree, mass in numerator),
            tuple((degree, mass / constant) for degree, mass in denominator))


@dataclass(frozen=True)
class ExitSeries:
    """An exact rational formal series, regular at tick zero."""

    numerator: Polynomial
    denominator: Polynomial = UNIT

    def __post_init__(self) -> None:
        _check_polynomial(self.numerator)
        _check_polynomial(self.denominator)
        if not self.denominator or self.denominator[0][0] != 0:
            raise ValueError('series denominator must have a nonzero constant')
        numerator, denominator = _reduce(self.numerator, self.denominator)
        object.__setattr__(self, 'numerator', numerator)
        object.__setattr__(self, 'denominator', denominator)

    @classmethod
    def monomial(cls, ticks: int, mass: Fraction) -> 'ExitSeries':
        return cls(((ticks, mass),) if mass else ())

    def __bool__(self) -> bool:
        return bool(self.numerator)

    def _combine(self, other: 'ExitSeries', scale: Fraction) -> 'ExitSeries':
        if self.denominator == other.denominator:
            return ExitSeries(_add(self.numerator, other.numerator, scale), self.denominator)
        left = _product(self.numerator, other.denominator)
        right = _product(other.numerator, self.denominator)
        return ExitSeries(_add(left, right, scale), _product(self.denominator, other.denominator))

    def __add__(self, other: 'ExitSeries') -> 'ExitSeries':
        return self._combine(other, ONE)

    def __sub__(self, other: 'ExitSeries') -> 'ExitSeries':
        return self._combine(other, -ONE)

    def __mul__(self, other: 'ExitSeries') -> 'ExitSeries':
        return ExitSeries(_product(self.numerator, other.numerator), _product(self.denominator, other.denominator))

    def __truediv__(self, other: 'ExitSeries') -> 'ExitSeries':
        if not other or other.numerator[0][0] != 0:
            raise ZeroDivisionError('series divisor has zero constant coefficient')
        return ExitSeries(_product(self.numerator, other.denominator), _product(self.denominator, other.numerator))

    def coefficients_through(self, ticks: int) -> tuple[Fraction, ...]:
        if type(ticks) is not int or ticks < 0:
            raise ValueError('prefix requires a nonnegative integer tick')
        numerator = dict(self.numerator)
        tail = self.denominator[1:]
        values: list[Fraction] = []
        for tick in range(ticks + 1):
            value = numerator.get(tick, ZERO)
            for lag, coefficient in tail:
                if lag > tick:
                    break
                value -= coefficient * values[tick - lag]
            values.append(value)
        return tuple(values)

    def total_mass(self) -> Fraction:
        denominator = sum((mass for _, mass in self.denominator), ZERO)
        if not denominator:
            raise ValueError('exit series has no finite evaluation at one')
        return sum((mass for _, mass in self.numerator), ZERO) / denominator


@dataclass(frozen=True)
class EntryExitEvidence:
    exits: tuple[tuple[str, ExitSeries], ...]
    never_exit: Fraction
