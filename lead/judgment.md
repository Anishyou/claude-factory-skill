# Judgment

How the human decides on this project, learned from their corrections in the
review queue. The lead writes this file and uses it to recommend. The
factory's agents do not read it: a preference reaches them only when the lead
proposes it as a pull request on `docs/policies.md` and you merge it.

Nothing here can turn an escalation into an approval.

You can edit this file by hand. Delete a preference you no longer hold; the
lead will not bring it back unless you correct it the same way again.

## Preferences

None yet. The lead writes one when two or more observations say the same
thing:

    ### J-001 · <the preference in one line>
    - for: designer, builder
    - rule: <what to do, as narrow as the evidence>
    - evidence: <job rework-k, …>
    - confirmed: 2 · last: <date> · against: —
    - in policies: <PR url | proposed <date> | kept local>

## Observations

One line per correction, in the human's words. Not yet preferences.

## Retired

Preferences the human has since contradicted, with the reason.
