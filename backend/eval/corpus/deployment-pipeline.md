# Deployment Pipeline

## Stages

Every change moves through four gates before it reaches customers: continuous
integration, a staging soak, a canary slice, then the general fleet. A commit
that fails any gate stops there and does not advance on a timer.

Continuous integration runs the unit suite, the type checker, and a dependency
audit. The audit fails the build on any advisory rated high or above, which
occasionally blocks unrelated work; the tradeoff is deliberate.

## Staging soak

Merged changes deploy to staging automatically and must sit for at least thirty
minutes under synthetic load before promotion is offered. The soak exists to
surface issues that only appear under sustained traffic, such as connection
pool exhaustion or a memory leak that a short test run never reveals.

Staging uses a scrubbed copy of production data refreshed every Sunday night.
Direct copies are prohibited, and the scrubbing job replaces all personal
fields with generated values that preserve length and character class so that
validation logic behaves the same way.

## Canary releases

Promotion sends the build to two percent of traffic for twenty minutes while
the pipeline watches error rate, p99 latency, and saturation. If any of the
three drifts beyond its threshold the canary is withdrawn automatically and the
previous version resumes serving. No human approval is required to roll back,
and the engineer who shipped is notified rather than consulted.

The canary slice is chosen by consistent hashing on account identifier, so the
same accounts see the new build throughout the window. Random per-request
selection was tried and abandoned because it made customer reports impossible
to reproduce.

## Rolling back

A rollback restores the previously deployed artifact rather than reverting the
commit and rebuilding. Rebuilding takes eleven minutes and a restore takes
under ninety seconds, and during an active incident that gap decides whether
customers notice at all. Reverting in version control happens afterwards, once
service is stable.

Database migrations are the exception, because they cannot generally be undone
by swapping the artifact. Migrations must therefore be backward compatible with
the previous release, which in practice means adding columns before writing to
them and removing them at least one release after the last reader is gone.
