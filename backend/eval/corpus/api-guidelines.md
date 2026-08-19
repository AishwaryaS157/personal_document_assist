# API Guidelines

## Versioning

The public interface is versioned in the path, as `/v1/`, and a version is
supported for eighteen months after its successor ships. Breaking changes never
land inside an existing version. Adding an optional field is not breaking;
changing the type of an existing field, tightening validation, or removing an
enum member all are.

Clients are expected to ignore fields they do not recognise. This is stated in
the contract precisely so that additive changes stay cheap for everyone.

## Pagination

Collection endpoints return a cursor, never a numeric page offset. Offsets
produce duplicated and skipped records when the underlying set changes between
requests, which is the normal case for anything ordered by recency. The cursor
is opaque and clients must not attempt to decode it, because its internal shape
changes without notice.

The default page size is twenty five and the maximum is two hundred. Requests
above the maximum are clamped rather than rejected, and the response reports
the size actually applied.

## Errors

Error responses carry a stable machine-readable code alongside the human
message. The message is for a developer reading a log and may be reworded at
any time; the code is part of the contract and never changes meaning. Codes are
namespaced by domain, such as `billing.card_expired`.

Validation failures return a list covering every field that failed rather than
stopping at the first problem, because a form that reveals one error per
round trip is miserable to fill in.

## Rate limits

Limits are applied per account rather than per credential, so issuing extra
keys does not multiply the allowance. Every response carries the remaining
budget and the reset timestamp in headers. Clients that exceed the limit
receive a 429 with a retry hint, and repeated disregard of that hint results in
a longer cooling period rather than a permanent block.

Bulk operations have a separate and much lower ceiling. The intent is that an
interactive application never notices the limits exist while a runaway script
is stopped quickly.
