from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class TrialSource:
    work_order: str
    round_id: str
    trial_id: str


@dataclass(frozen=True)
class Transition:
    target: str
    probability: Fraction | int | str
    ticks: int
    is_exit: bool = False


@dataclass(frozen=True)
class RevisionDraft:
    station: str
    revision_id: str
    source: TrialSource
    entries: Mapping[str, str]
    exits: Sequence[str]
    transitions: Mapping[str, Sequence[Transition]]
    predecessor: str | None = None


@dataclass(frozen=True)
class Revision:
    station: str
    revision_id: str
    source: TrialSource
    entries: tuple[tuple[str, str], ...]
    exits: tuple[str, ...]
    transitions: tuple[tuple[str, tuple[Transition, ...]], ...]
    predecessor: str | None = None
