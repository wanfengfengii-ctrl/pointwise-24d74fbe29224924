import sqlite3
from dataclasses import dataclass

from retest.reports.receipts import Receipt, make_receipt
from retest.reports.snapshot import ReportSnapshot, decode_snapshot, encode_snapshot


@dataclass(frozen=True)
class IssuedReport:
    snapshot: ReportSnapshot
    receipt: Receipt

    @property
    def report_id(self) -> int:
        return self.receipt.report_id


class ReportLedger:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def initialize(self) -> None:
        self.db.execute('''CREATE TABLE IF NOT EXISTS reports (
            report_id INTEGER PRIMARY KEY, snapshot TEXT NOT NULL
        )''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS receipts (
            report_id INTEGER PRIMARY KEY REFERENCES reports(report_id),
            status TEXT NOT NULL CHECK(status = 'issued')
        )''')

    def commit_issue(self, snapshot: ReportSnapshot) -> IssuedReport:
        if self.db.in_transaction:
            raise RuntimeError('report ledger requires an idle connection')
        body = encode_snapshot(snapshot)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            staged = self.db.execute('INSERT INTO reports(snapshot) VALUES (?)', (body,))
            if staged.rowcount != 1 or staged.lastrowid is None:
                raise sqlite3.IntegrityError('report insert did not stage a record')
            receipt = make_receipt(staged.lastrowid)
            written = self.db.execute('INSERT INTO receipts VALUES (?, ?)', (receipt.report_id, receipt.status))
            if written.rowcount != 1:
                raise sqlite3.IntegrityError('receipt insert did not stage a record')
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise
        return IssuedReport(snapshot, receipt)

    def read_issue(self, report_id: int) -> IssuedReport:
        row = self.db.execute('''SELECT reports.snapshot, receipts.status FROM reports
            JOIN receipts USING(report_id) WHERE report_id = ?''', (report_id,)).fetchone()
        if row is None:
            raise KeyError(report_id)
        return IssuedReport(decode_snapshot(row[0]), Receipt(report_id, row[1]))
