from dataclasses import dataclass


@dataclass(frozen=True)
class Receipt:
    report_id: int
    status: str


def make_receipt(report_id: int) -> Receipt:
    if type(report_id) is not int or report_id <= 0:
        raise ValueError('success receipt requires a positive report identity')
    return Receipt(report_id, 'issued')
