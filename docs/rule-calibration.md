# Rule calibration profile

This diagnostic describes how accepted findings are distributed. It does not
change rules, rank people or entities, estimate wrongdoing, or make automated
decisions.

Run it after building the accepted warehouse:

```bash
uv run secop-calibrate-rules \
  --output data/curated/rule-calibration.json
```

The report includes:

- unique-contract prevalence for the complete queue and each rule;
- each rule's share of all findings;
- finding and unique-contract counts by contract state;
- the most represented entities per rule.
- overdue-age buckets and extension overlap for
  `REVIEW_ACTIVE_AFTER_END_DATE`.

High prevalence is a signal to inspect rule semantics and operational
usefulness. It is not evidence that the underlying contracts are improper.

Rule logic must not be changed from this report alone. Any revision requires
source-semantic evidence, a versioned rule definition, tests and before/after
acceptance counts.

The command fails closed if state totals do not reconcile with rule totals or
if the detailed active-after-end profile does not reproduce the accepted rule
count.
