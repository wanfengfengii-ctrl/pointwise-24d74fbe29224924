from retest.revisions.model import Revision
from retest.revisions.storage import RevisionStore


def select_revision(store: RevisionStore, station: str, revision_id: str) -> Revision:
    if any(not isinstance(name, str) or not name.strip() for name in (station, revision_id)):
        raise ValueError('station and explicit revision identity are required')
    return store.read(station, revision_id)


def check_predecessor(store: RevisionStore, revision: Revision) -> None:
    if revision.predecessor is None:
        return
    try:
        select_revision(store, revision.station, revision.predecessor)
    except KeyError as error:
        raise ValueError('predecessor must be an existing revision of this station') from error
