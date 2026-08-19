# Data Retention

## Retention windows

Meridian keeps different classes of record for different lengths of time.
Application logs are held for ninety days and then deleted irreversibly.
Aggregated usage metrics, which carry no identifiers, are kept indefinitely
because they inform capacity planning years out. Billing records are retained
for seven years to satisfy tax obligations in the jurisdictions where the
company operates.

Uploaded customer documents live until the owning account deletes them or
closes the account. There is no automatic expiry on customer content, and any
proposal to add one requires explicit consent captured at upload time.

## Deletion requests

When an account holder asks for erasure, the request is honoured within thirty
days. Deletion cascades from the account record through documents, extracted
text, and derived vector embeddings, because an embedding computed from a
private document is itself derived personal data and cannot be retained after
the source is gone.

Backups are the awkward case. Restoring an old backup would resurrect deleted
records, so the deletion log is replayed against any restored snapshot before
that snapshot is allowed to serve traffic. This is verified during the annual
restore drill rather than assumed.

## Access controls

Engineers do not hold standing access to customer content. Access is granted
for a named incident, expires after eight hours, and writes an audit entry that
the customer can request. Three people have permanent break-glass credentials
and every use of them triggers a review by someone outside the team.

## Encryption

Documents are encrypted at rest with keys held in a managed key service, and
key rotation happens every ninety days. Rotation re-encrypts the data
encryption key rather than the documents themselves, which keeps rotation cheap
enough to actually perform on schedule instead of deferring it indefinitely.

Transport is TLS 1.3 with older versions refused outright. A small number of
enterprise customers asked for an exception during migration and were given a
fixed end date rather than an open-ended allowance.
