# Incident Response

## Severity levels

Meridian classifies incidents on a four-point scale. A Sev1 means customer data
is unreachable or being served incorrectly to more than five percent of active
accounts, and it pages the on-call engineer immediately at any hour. A Sev2
covers degraded performance that customers can perceive but work around, such
as search latency above four seconds. Sev3 is a defect with a known workaround
and no revenue impact. Sev4 is cosmetic and waits for the next planning cycle.

The declaring engineer sets the initial severity. Nobody needs permission to
declare, and over-declaring is explicitly encouraged: the retrospective cost of
a downgraded Sev1 is far smaller than the cost of an unnoticed outage.

## The on-call rotation

Each team keeps a weekly rotation with a primary and a secondary responder. The
primary acknowledges within five minutes; if they do not, the alert escalates
automatically to the secondary, and after a further ten minutes to the
engineering manager on duty. Handover happens every Tuesday at 10:00 local
time, and the outgoing responder writes a short note covering anything still
smouldering.

Responders are not expected to fix everything themselves. The first duty is to
restore service, and pulling in whoever wrote the subsystem is considered good
practice rather than an admission of defeat.

## Communication during an incident

Every declared incident opens a dedicated channel named for the incident
identifier. Status updates go out every thirty minutes for a Sev1, even when
the update is that nothing has changed, because silence is read as absence.
Customer-facing language is drafted by the incident commander and approved by
support before it reaches the status page.

## Postmortems

Any Sev1 or Sev2 requires a written postmortem within five working days. The
document is blameless by policy: it describes what the system did and what
information each person had at the time, never what someone should have known.
Action items carry a named owner and a due date, and they are tracked in the
same backlog as feature work rather than a separate list that quietly rots.

A postmortem is considered complete when the contributing factors are written
down, not when the fix ships. Waiting for the repair to land before publishing
delays the learning for everyone else.
