from collections.abc import Mapping, Sequence
from fractions import Fraction

from retest.revisions.model import Revision, RevisionDraft, Transition, TrialSource


def _name(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field} must be a nonempty name')
    return value


def _probability(value: object) -> Fraction:
    if not (type(value) is int or isinstance(value, (Fraction, str))):
        raise ValueError('transition probability must be exact')
    try:
        probability = Fraction(value)
    except (ValueError, ZeroDivisionError) as error:
        raise ValueError('invalid transition probability') from error
    if not 0 <= probability <= 1:
        raise ValueError('transition probability outside [0, 1]')
    return probability


def _sequence(value: object, field: str) -> Sequence:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f'{field} must be a sequence')
    return value


def validate_revision(draft: RevisionDraft) -> Revision:
    if not isinstance(draft, RevisionDraft) or not isinstance(draft.source, TrialSource):
        raise ValueError('a revision draft with a trial source is required')
    station = _name(draft.station, 'station')
    revision_id = _name(draft.revision_id, 'revision')
    source = TrialSource(
        _name(draft.source.work_order, 'work order'),
        _name(draft.source.round_id, 'round'),
        _name(draft.source.trial_id, 'trial'),
    )
    predecessor = draft.predecessor
    if predecessor is not None:
        _name(predecessor, 'predecessor')
        if predecessor == revision_id:
            raise ValueError('a revision cannot correct itself')

    if not isinstance(draft.transitions, Mapping) or not draft.transitions:
        raise ValueError('private states require transition rows')
    states = {_name(state, 'state') for state in draft.transitions}
    if not isinstance(draft.entries, Mapping) or not draft.entries:
        raise ValueError('at least one public entrance is required')
    entries = []
    for entrance, state in draft.entries.items():
        _name(entrance, 'entrance')
        if _name(state, 'entrance state') not in states:
            raise ValueError(f'unknown entrance state {state!r}')
        entries.append((entrance, state))
    exits = tuple(_name(name, 'exit') for name in _sequence(draft.exits, 'exits'))
    exit_names = set(exits)
    if not exits or len(exits) != len(exit_names):
        raise ValueError('public exit names must be present and distinct')

    rows = []
    for state in sorted(states):
        edges = []
        for edge in _sequence(draft.transitions[state], 'transition row'):
            if not isinstance(edge, Transition) or type(edge.is_exit) is not bool:
                raise ValueError(f'invalid transition in {state!r}')
            destinations = exit_names if edge.is_exit else states
            if _name(edge.target, 'transition target') not in destinations:
                raise ValueError(f'unknown transition target {edge.target!r}')
            if type(edge.ticks) is not int or edge.ticks < 0:
                raise ValueError('transition ticks must be nonnegative integers')
            edges.append(Transition(edge.target, _probability(edge.probability), edge.ticks, edge.is_exit))
        if sum(edge.probability for edge in edges) != 1:
            raise ValueError(f'branch mass for {state!r} must sum to 1')
        rows.append((state, tuple(edges)))
    return Revision(station, revision_id, source, tuple(sorted(entries)), tuple(sorted(exits)), tuple(rows), predecessor)
