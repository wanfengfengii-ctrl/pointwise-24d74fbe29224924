from retest.revisions.history import check_predecessor
from retest.revisions.model import Revision, RevisionDraft
from retest.revisions.storage import RevisionStore
from retest.revisions.validation import validate_revision


def register(store: RevisionStore, draft: RevisionDraft) -> Revision:
    revision = validate_revision(draft)
    check_predecessor(store, revision)
    store.insert(revision)
    return revision
