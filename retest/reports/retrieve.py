from retest.reports.ledger import IssuedReport, ReportLedger


def get(ledger: ReportLedger, report_id: int) -> IssuedReport:
    if type(report_id) is not int or report_id <= 0:
        raise ValueError('report identity must be a positive integer')
    return ledger.read_issue(report_id)
