import json
import sqlite3

from retest.wiring.intake import ReceivedEvidence, receive_evidence
from retest.wiring.manifest import Manifest, build_manifest


class ManifestStore:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def initialize(self) -> None:
        self.db.execute('''CREATE TABLE IF NOT EXISTS manifests (
            manifest_id TEXT PRIMARY KEY NOT NULL, binding TEXT NOT NULL
        )''')

    def save(self, manifest: Manifest, pair: tuple[ReceivedEvidence, ReceivedEvidence]) -> None:
        if self.db.in_transaction:
            raise RuntimeError('manifest store requires an idle connection')
        if manifest.parents != tuple(piece.piece_id for piece in pair):
            raise ValueError('manifest does not refer to the supplied received pair')
        binding = json.dumps({'manifest': manifest.to_record(), 'pieces': [piece.body for piece in pair]},
                             sort_keys=True, separators=(',', ':'))
        with self.db:
            inserted = self.db.execute('''INSERT INTO manifests VALUES (?, ?)
                ON CONFLICT(manifest_id) DO NOTHING''', (manifest.manifest_id, binding))
            if inserted.rowcount != 1:
                raise ValueError('manifest identity already exists')

    def load(self, manifest_id: str) -> tuple[Manifest, tuple[ReceivedEvidence, ReceivedEvidence]]:
        row = self.db.execute('SELECT binding FROM manifests WHERE manifest_id = ?', (manifest_id,)).fetchone()
        if row is None:
            raise KeyError(manifest_id)
        payload = json.loads(row[0])
        manifest = Manifest.from_record(payload['manifest'])
        first, second = payload['pieces']
        pair = (receive_evidence(first), receive_evidence(second))
        checked = build_manifest(manifest_id, manifest.source, pair, manifest.connections)
        if checked != manifest:
            raise ValueError('stored manifest does not match its received evidence')
        return manifest, pair
