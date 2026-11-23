from retest.reports.ledger import IssuedReport, ReportLedger
from retest.reports.snapshot import ReportSnapshot


def publish(ledger: ReportLedger, snapshot: ReportSnapshot) -> IssuedReport:
    return ledger.commit_issue(snapshot)
