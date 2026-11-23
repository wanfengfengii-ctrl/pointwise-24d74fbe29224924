from dataclasses import dataclass

from retest.evidence.encoding import StationEvidence, decode_evidence


@dataclass(frozen=True)
class ReceivedEvidence:
    body: str
    evidence: StationEvidence

    @property
    def piece_id(self) -> str:
        return self.evidence.piece_id


def receive_evidence(body: str) -> ReceivedEvidence:
    return ReceivedEvidence(body, decode_evidence(body))
