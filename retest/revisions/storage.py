import json
import sqlite3
from dataclasses import asdict
from fractions import Fraction

from retest.revisions.model import Revision, Transition, TrialSource


def _encode(revision: Revision) -> str:
    return json.dumps({
        'source': asdict(revision.source),
        'entries': revision.entries,
        'exits': revision.exits,
        'predecessor': revision.predecessor,
        'transitions': [
            (state, [(edge.target, str(edge.probability), edge.ticks, edge.is_exit) for edge in edges])
            for state, edges in revision.transitions
        ],
    }, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _decode(station: str, revision_id: str, body: str) -> Revision:
    payload = json.loads(body)
    return Revision(
        station, revision_id, TrialSource(**payload['source']),
        tuple((name, state) for name, state in payload['entries']),
        tuple(payload['exits']),
        tuple((state, tuple(Transition(target, Fraction(mass), ticks, is_exit)
                            for target, mass, ticks, is_exit in edges))
              for state, edges in payload['transitions']),
        payload['predecessor'],
    )


class RevisionStore:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def initialize(self) -> None:
        self.db.execute('''CREATE TABLE IF NOT EXISTS revisions (
            station TEXT NOT NULL, revision_id TEXT NOT NULL, body TEXT NOT NULL,
            PRIMARY KEY (station, revision_id)
        )''')

    def insert(self, revision: Revision) -> None:
        if self.db.in_transaction:
            raise RuntimeError('revision store requires an idle connection')
        body = _encode(revision)
        with self.db:
            inserted = self.db.execute('''INSERT INTO revisions VALUES (?, ?, ?)
                ON CONFLICT(station, revision_id) DO NOTHING''',
                (revision.station, revision.revision_id, body))
            if inserted.rowcount != 1:
                raise ValueError('revision identity already exists')

    def read(self, station: str, revision_id: str) -> Revision:
        row = self.db.execute('SELECT body FROM revisions WHERE station = ? AND revision_id = ?',
                              (station, revision_id)).fetchone()
        if row is None:
            raise KeyError((station, revision_id))
        return _decode(station, revision_id, row[0])
