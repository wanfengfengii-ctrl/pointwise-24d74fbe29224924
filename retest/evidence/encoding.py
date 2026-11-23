import json
from dataclasses import asdict, dataclass
from fractions import Fraction
from hashlib import sha256

from retest.evidence.series import EntryExitEvidence, ExitSeries, Polynomial


@dataclass(frozen=True)
class EvidenceOrigin:
    station: str
    revision_id: str
    work_order: str
    round_id: str
    trial_id: str
    predecessor: str | None


@dataclass(frozen=True)
class StationEvidence:
    origin: EvidenceOrigin
    exits: tuple[str, ...]
    entries: tuple[tuple[str, EntryExitEvidence], ...]

    @property
    def piece_id(self) -> str:
        return _identity(_payload(self))


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'))


def _identity(payload: dict) -> str:
    return sha256(_json(payload).encode('ascii')).hexdigest()


def _name(value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError('blank or invalid public identity')


def _probability(value: Fraction) -> Fraction:
    if not 0 <= value <= 1:
        raise ValueError('evidence mass outside [0, 1]')
    return value


def _polynomial(value: Polynomial) -> list[list]:
    return [[degree, str(coefficient)] for degree, coefficient in value]


def _payload(evidence: StationEvidence) -> dict:
    origin = asdict(evidence.origin)
    for key, value in origin.items():
        if key != 'predecessor' or value is not None:
            _name(value)
    if origin['predecessor'] == origin['revision_id']:
        raise ValueError('invalid evidence predecessor')
    for name in evidence.exits:
        _name(name)
    exit_set = set(evidence.exits)
    if not exit_set or len(exit_set) != len(evidence.exits) or not evidence.entries:
        raise ValueError('evidence requires distinct exits and at least one entrance')
    entries = {}
    for entrance, evidence_row in evidence.entries:
        _name(entrance)
        if entrance in entries:
            raise ValueError('duplicate entrance evidence')
        series_by_name = {}
        total = _probability(evidence_row.never_exit)
        for name, series in evidence_row.exits:
            if name in series_by_name:
                raise ValueError('duplicate exit evidence')
            mass = _probability(series.total_mass())
            immediate = series.coefficients_through(0)[0]
            if not 0 <= immediate <= mass or (not mass and series):
                raise ValueError('exit series contradicts its total mass')
            total += mass
            series_by_name[name] = {
                'numerator': _polynomial(series.numerator),
                'denominator': _polynomial(series.denominator),
            }
        if series_by_name.keys() != exit_set or total != 1:
            raise ValueError('entrance evidence is missing exits or does not conserve mass')
        entries[entrance] = {'exits': series_by_name, 'never_exit': str(evidence_row.never_exit)}
    return {'version': 1, 'kind': 'station-evidence', 'origin': origin,
            'body': {'exits': list(sorted(exit_set)), 'entries': entries}}


def encode_evidence(evidence: StationEvidence) -> str:
    payload = _payload(evidence)
    return _json({**payload, 'id': _identity(payload)})


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate field in evidence JSON')
        result[key] = value
    return result


def _fields(value: object, *keys: str) -> dict:
    if not isinstance(value, dict) or value.keys() != set(keys):
        raise ValueError('invalid evidence fields')
    return value


def _fraction(value: object) -> Fraction:
    if not isinstance(value, str):
        raise ValueError('evidence rational must be a string')
    return Fraction(value)


def _read_polynomial(value: object) -> Polynomial:
    if not isinstance(value, list):
        raise ValueError('evidence polynomial must be a list of terms')
    terms = []
    for term in value:
        if not isinstance(term, list) or len(term) != 2:
            raise ValueError('invalid evidence polynomial term')
        terms.append((term[0], _fraction(term[1])))
    return tuple(terms)


def decode_evidence(body: str) -> StationEvidence:
    if not isinstance(body, str):
        raise ValueError('evidence must be JSON text')
    try:
        raw = _fields(json.loads(body, object_pairs_hook=_unique_object), 'version', 'kind', 'id', 'origin', 'body')
        if type(raw['version']) is not int or raw['version'] != 1 or raw['kind'] != 'station-evidence':
            raise ValueError('unsupported evidence envelope')
        origin = EvidenceOrigin(**_fields(raw['origin'], 'station', 'revision_id', 'work_order', 'round_id', 'trial_id', 'predecessor'))
        data = _fields(raw['body'], 'exits', 'entries')
        if not isinstance(data['exits'], list) or not isinstance(data['entries'], dict):
            raise ValueError('invalid public port evidence')
        entries = []
        for name, row in sorted(data['entries'].items()):
            row = _fields(row, 'exits', 'never_exit')
            if not isinstance(row['exits'], dict):
                raise ValueError('invalid exit evidence map')
            exits = []
            for exit_name, item in sorted(row['exits'].items()):
                item = _fields(item, 'numerator', 'denominator')
                exits.append((exit_name, ExitSeries(_read_polynomial(item['numerator']), _read_polynomial(item['denominator']))))
            entries.append((name, EntryExitEvidence(tuple(exits), _fraction(row['never_exit']))))
        evidence = StationEvidence(origin, tuple(data['exits']), tuple(entries))
        if _json(raw) != encode_evidence(evidence):
            raise ValueError('station evidence identity or canonical values do not match')
        return evidence
    except (ZeroDivisionError, RecursionError) as error:
        raise ValueError('invalid evidence body') from error
