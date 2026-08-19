# Engineering Onboarding

## Before the first day

Hardware ships to arrive two days early so nobody spends their first morning
waiting for a courier. Accounts are provisioned from the offer record, which
means the identity directory, the code host, and the observability stack are
all ready before anyone logs in. A buddy is assigned from a different team, on
the theory that someone outside the immediate reporting line is easier to ask
naive questions of.

## The first week

The goal for week one is a merged change in production, however small. Fixing a
typo in a log message counts. The point is to exercise every step of the path
from checkout to deploy while somebody experienced is sitting alongside, rather
than to contribute anything of consequence.

New engineers are deliberately kept off the on-call rotation for their first
sixty days. Shadowing is encouraged from week three, where the newcomer joins
the responder for alerts without carrying the pager themselves.

## Reading order

The recommended sequence is the architecture overview, then the deployment
pipeline, then incident response. Reading them in that order means each
document assumes only what the previous one established. People who start with
incident response tend to bounce off the severity definitions because they lack
the vocabulary for the subsystems being described.

## Mentorship and review

Every new engineer has a weekly thirty-minute session with their buddy for the
first quarter. These are not status meetings, and managers do not attend. The
agenda belongs entirely to the newcomer.

Code review expectations are explicit: a first review arrives within one
business day, and reviewers comment on the change in front of them rather than
the change they would have written. Stylistic preferences that the linter does
not enforce are not grounds for blocking a merge.
