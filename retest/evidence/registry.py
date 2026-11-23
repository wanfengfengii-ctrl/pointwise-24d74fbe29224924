import sqlite3

from retest.evidence.encoding import decode_evidence, encode_evidence


class EvidenceRegistry:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def initialize(self) -> None:
        self.db.execute('''CREATE TABLE IF NOT EXISTS issued_evidence (
            piece_id TEXT PRIMARY KEY NOT NULL, body TEXT NOT NULL
        )''')

    def record(self, body: str) -> str:
        if self.db.in_transaction:
            raise RuntimeError('evidence registry requires an idle connection')
        value = decode_evidence(body)
        piece_id = value.piece_id
        canonical = encode_evidence(value)
        with self.db:
            self.db.execute('''INSERT INTO issued_evidence VALUES (?, ?)
                ON CONFLICT(piece_id) DO NOTHING''', (piece_id, canonical))
            if self.read(piece_id) != canonical:
                raise ValueError('station evidence identity conflicts with the stored body')
        return piece_id

    def read(self, piece_id: str) -> str:
        row = self.db.execute('SELECT body FROM issued_evidence WHERE piece_id = ?', (piece_id,)).fetchone()
        if row is None:
            raise KeyError(piece_id)
        return row[0]
