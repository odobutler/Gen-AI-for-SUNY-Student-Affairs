# ETP PY24 9171 Resubmittal Pipeline — Code Review

Reviewed files:
- `STEP_1_ETPL_SCHOOLS_Update_PY24.txt`
- `STEP_2_ETPL_PY24_FINAL_FILE_Update.txt`
- `STEP_3a_Append_BIG3_Data.txt`
- `STEP_3b_Append_NONSCB_Data.txt`
- `STEP_4_WIPS_ERROR_FIXES.txt`
- `ETP_SelfCheck__Website.xlsx` (used as the validation spec these scripts must satisfy)

The self-check workbook's `3a. ETP Self-Check Results` tab confirms the rules this pipeline needs to
satisfy, most importantly: it flags a program as a **data quality concern** when
`WIOA Participants (DE133) = All Students Served (DE120)` or `WIOA Exiters (DE134) = All Students
Exiters (DE121)`, and it separately flags numerator/denominator mismatches (`NUM = 0`, `DEN = 0`,
"RATE Too High or Low", "misaligned with earnings") for every outcome measure. That checklist is
the right lens for reviewing this code, and several findings below map directly onto it.

## Critical

**1. `STEP_3a`, line 20 — the literal string `' APPEND'` leaks into the government-facing provider name field.**
```sql
SELECT DISTINCT SA.DE101||' APPEND' A101, ...
```
This `A101` (with `' APPEND'` baked in) is carried unchanged through `SUB_AGG_W_ETP_PY24` →
`ETP_SUB_AGG_PY24_ROLLUP` → the final `MERGE`'s `WHEN NOT MATCHED THEN INSERT` branch (lines
242–252), which writes it into both `F.PROVIDER_NAME_UPR` and `F.A101`. The script's own comment
says **104 rows merged** as new inserts (line 254), so this isn't theoretical — any of those 104
programs will show a provider name like `"Example College APPEND"` in the extract that ultimately
gets built in `STEP_2` and submitted to WIPS/DOL. `STEP_3b` (NONSCB) does not have this problem —
`ENA.PROVIDER_NAME DE101` has no suffix — so this is a one-sided bug in the BIG3 path. Recommend
tagging these rows in a separate internal flag/audit column instead of concatenating into the name
field, and re-checking whether any past submissions already contain `" APPEND"` in `A101`/`PROVIDER_NAME_UPR`.

**2. `STEP_1`, lines 172–251 — the "All-Student floor" fix trades one self-check flag for another.**
```sql
update etp_annual_py24_merge a
set a.A120 = a.A133
where (nvl(a.A120,0) = 0 or (a.A120 < a.A133))
and a.provider_service_id in (select provider_service_id from ETP_SUNY_ROLLUP_0729);
```
This pattern (repeated for A120–A130) sets All-Student fields equal to the WIOA fields whenever
All-Student is missing or lower. That does stop the "All-Student < WIOA" logical impossibility, but
it also drives All-Student **exactly equal to** WIOA for every affected row — which is precisely
the condition the self-check flags separately (`WIOA Participants (DE133) = All Students Served
(DE120)`, `WIOA Exiters (DE134) = All Students Exiters (DE121)`). In other words, this UPDATE block
is a floor of last resort, not a fix for the underlying ask ("track outcomes separately for all
students including non-WIOA"). It should be documented as such, and the team's actual lever for
reducing these flags is capturing real non-WIOA counts (which is what `STEP_1`/`3a`/`3b`'s data
intake is for) — the floor should only apply to programs where a genuine non-WIOA count truly
couldn't be obtained.

**3. `STEP_1`, lines 224–236 — A127/A128 (average earnings) are zero-filled instead of inheriting the WIOA value like every sibling field.**
```sql
update etp_annual_py24_merge a
set a.A127 = 0
where a.A127 is null
and a.provider_service_id in (select provider_service_id from ETP_SUNY_ROLLUP_0729);
```
Every other "floor" update (A120–A126, A129, A130) pulls the matching WIOA field forward
(`a.A125 = a.A141`, etc.). A127/A128 instead get hard-coded to `0`. If a program's A123/A124
(employment count numerators) are positive but A127/A128 (average earnings) get forced to `0`,
that directly produces the self-check's "ERQ2/ERQ4 - Earnings Misaligned" and "Earnings Not
Available" flags — the opposite of the intended effect. This looks like a copy-paste gap; it should
almost certainly be `a.A127 = a.A141` / `a.A128 = a.A142` to match the pattern used for A125/A126.

## High

**4. `STEP_1`, lines 100–110 — DE122 (completers) is computed identically to DE121 (all exiters), so completion rate is always 100%.**
```sql
COUNT(CASE WHEN EXIT_DATE BETWEEN '01-APR-2021' AND '31-MAR-2025' THEN 1 END) DE121,
COUNT(CASE WHEN EXIT_DATE BETWEEN '01-APR-2021' AND '31-MAR-2025' THEN 1 END) DE122,
```
DE121 is "completed, withdrew, or transferred" and DE122 is "program of study completed" — a
subset. Both are computed from the exact same `CASE WHEN EXIT_DATE BETWEEN ...` with no filter
distinguishing completion from withdrawal/transfer, so DE122 will always equal DE121 for any row
that flows through this table. That means every program touched by this script reports a 100%
completion rate, which is exactly the kind of statistically-improbable value the self-check's "All
Students Completion Rate Too High or Low" check exists to catch. The source tables
(`ETP_SUNY_BUFF_EOC_MATCH_0729`, `ETP_SUNY_SUFFOLK2_MATCH_0729`) need some completion/exit-type
indicator for DE122 to filter on; if that field genuinely doesn't exist in the SUNY feed, that's a
data-source gap worth raising with OWD/ITS rather than a query fix.

**5. Hardcoded, date-suffixed table names throughout `STEP_1` (`ETP_SUNY_MATCH_0729`, `ETP_SUNY_ROLLUP_0729`, `ETP_SUNY_BUFF_EOC_MATCH_0729`, `ETP_SUNY_SUFFOLK2_MATCH_0729`).**
Every new intake day requires manually editing the `MMDD` suffix across ~10 `DROP`/`CREATE`/`GRANT`/
`SELECT`/`MERGE`/`UPDATE` statements. This is a high-probability source of copy/paste errors (e.g.
updating the `CREATE` but missing one of the five `UPDATE ... WHERE provider_service_id IN (SELECT
... FROM ETP_SUNY_ROLLUP_0729)` clauses, silently reusing a prior day's rollup). Recommend a
permanent staging table with a `LOAD_DATE`/`BATCH_ID` column (loaded via `TRUNCATE` + `INSERT`, or
just `INSERT` with a batch key) instead of a new physical table per day. This also removes the need
to re-run the `GRANT` statements every time.

**6. `STEP_2`, lines 32–110 — this `MERGE` has no `WHEN NOT MATCHED` branch and no regression protection.**
Unlike `STEP_1`'s merge (`GREATEST(NVL(...))`) and `STEP_3a`/`3b`'s merges (same pattern), this one:
- blindly overwrites `F.A1xx = M.A1xx` with no floor/guard, so a stale or partially-recomputed
  `ETP_ANNUAL_PY24_MERGE` row could regress previously-corrected data in the final file back down
  (including to `NULL`), and
- silently drops any program present in `ETP_ANNUAL_PY24_MERGE` but not already in
  `ETP_ANNUAL_PY24_ALL_UPDATE_FINAL_FILE` (no insert branch), with no comment explaining why that's
  intentional here when `STEP_3a`/`3b` both insert unmatched rows.
Given this step is described as "THE MAJOR UPDATE" for PY24, it's worth confirming this asymmetry
is deliberate.

**7. `STEP_3a`/`STEP_3b` boost outcome numerators (A123–A128) without touching the corresponding denominators (A129/A130).**
The `MERGE ... WHEN MATCHED` in both files only updates A120–A128; A129 (Q2 denominator) and A130
(Q4 denominator) are never adjusted. Per the Teams note quoted at the top of `STEP_3a`, the intent
is to "boost any relevant numerators in the wage-based metrics" — but the self-check explicitly
flags `NUM > 0` with `DEN = 0` and "RATE Too High or Low." Increasing A123/A124 without ensuring
A129/A130 are populated/consistent risks creating exactly the flags this whole exercise is meant to
reduce.

## Medium

**8. Bare date-string literals throughout (`'01-JUL-2021'`, `'30-JUN-2025'`, etc.) instead of explicit `TO_DATE(...)` or ANSI `DATE '...'` literals.**
These implicit conversions depend on the session's `NLS_DATE_FORMAT`/`NLS_DATE_LANGUAGE`. Since
this pipeline is apparently run by hand from different analysts' SQL clients, a different locale
setting will either throw `ORA-01858`/`ORA-01861` or — worse — silently misparse day/month with no
error. The reporting-period boundaries are also repeated as magic literals in 4+ different windows
across `STEP_1` alone (`JUL2021–JUN2025`, `APR2021–MAR2025`, `JUL2020–JUN2024`, `JAN2020–DEC2023`)
with no comment explaining why each measure uses a different window — worth centralizing as named
constants (a small reference table or bind variables) so next year's PY rollover is a single edit
instead of a global find-and-replace across four files.

**9. `CREDENTIAL IN ('Y','Yes')` (STEP_1, line 106) — fragile categorical matching.**
Two different truthy spellings in the same column suggests unvalidated free text from the source
system; likely candidates for silent misses include lowercase `'y'`, trailing whitespace, `NULL`,
or other spellings. Recommend `SELECT DISTINCT CREDENTIAL FROM ...` before trusting this filter, and
wrapping with `UPPER(TRIM(CREDENTIAL))` defensively.

**10. Ten separate single-column `UPDATE` statements in `STEP_1` (lines 175–250) instead of one `UPDATE ... SET col1=.., col2=..`.**
Same source table, same `WHERE` shape, run ten times — each pass is a full extra scan and
redo/undo generation, and if the script is interrupted partway through, the row is left in a
half-updated state (e.g., A120 fixed but A127 not). Consolidating into a single `UPDATE` with all
ten `SET` clauses is both cheaper and atomic.

**11. `DROP TABLE` with no existence check or `PURGE`, repeated 6× across the four scripts.**
On the very first run for a new day-suffixed table name, `DROP TABLE` will throw `ORA-00942` (table
or view does not exist) before the `CREATE TABLE AS SELECT` that follows it — relies on the
operator knowing to ignore that specific error. None of the drops use `PURGE`, so old versions pile
up in the recycle bin indefinitely; given these tables carry individual-level wage/earnings data,
that's worth cleaning up.

**12. Statistical drift from repeated averaging of medians.**
`STEP_3a`, line 23: `ROUND(AVG(SA.DE125)) A125` averages an already-computed median across grouped
rows, and `ETP_SUB_AGG_PY24_ROLLUP` (line 188) does `ROUND(AVG(DE125))` again on top of that. An
"average of medians" is not the same statistic as a true median over the combined population, and
compounding it twice loses more meaning each pass. Likely an acceptable approximation given the
data available (aggregate phone-call/file submissions, not individual wage records), but worth a
one-line comment acknowledging the tradeoff so a future reader doesn't assume it's exact.

**13. `STEP_3b`, line 21 — `WHERE A.END_DT < '01-JUL-2025'` has no lower bound.**
Unlike `STEP_1`'s explicit `BETWEEN` windows, this only bounds the upper end, so if
`BCCAK3.ETP_NONSCB_AGG_PY24@OSOR` ever contains older data than expected, it would silently be
included. Consider a symmetric `BETWEEN` with an explicit PY start date.

## Minor / Housekeeping

- **PII sprawl**: day-stamped staging tables (`ETP_SUNY_BUFF_EOC_MATCH_0729`, etc.) containing
  individual-level exit dates and earnings are granted to named users and left in the schema
  indefinitely with no retention/purge step once merged. Worth a defined cleanup policy.
- **Row-count comments are undocumented assertions**: `--104 rows merged.`, `--301 ROWS`, etc. are
  useful documentation but aren't enforced anywhere — a re-run producing a wildly different count
  wouldn't be caught automatically. If this pipeline becomes a scheduled job rather than a
  hand-run script, converting these into real `IF SQL%ROWCOUNT ...` sanity checks (logged or
  raised) would catch silent regressions.
- **No source control**: these are ad hoc `.txt` files (`STEP_1`, `STEP_1a` referenced-but-superseded,
  `STEP_2`, `STEP_3a`, `STEP_3b`) apparently shared via Teams/email. Given how much of this review
  is about preventing hand-edit mistakes across near-duplicate blocks, putting this pipeline under
  version control (even a simple git repo) would make the "what changed since last month" question
  answerable and let the team review diffs instead of re-reading the whole script each time.
- **`STEP_1`, lines 133–151** — the `MERGE`'s `USING` subquery inner-joins `etp_annual_py24_merge`
  to `ETP_SUNY_ROLLUP_0729` and then the outer `MERGE ... ON` re-joins back to
  `etp_annual_py24_merge` on `provider_id AND provider_service_id`. Since `provider_service_id`
  alone is treated elsewhere in these scripts as the unique program key, requiring `provider_id` to
  also match is redundant, and risky if the two tables' `PROVIDER_ID` values come from different
  lineages (the rollup's `PROVIDER_ID` is sourced from `OSOS_PROVIDER_ID` in the raw SUNY file,
  which may not always agree in format with the final file's `PROVIDER_ID`). Recommend merging on
  `provider_service_id` alone, and simplifying by joining directly to `ETP_SUNY_ROLLUP_0729` in the
  `USING` clause instead of round-tripping through `etp_annual_py24_merge` twice.

## STEP_4 (`STEP_4_WIPS_ERROR_FIXES.txt`) — WIPS Edit-Check Cleanup

This file runs after `STEP_2`/`3a`/`3b`, right before the final extract goes to the 9171
Self-Checker / WIPS. It's structured as three passes (valid values, duplicates, logical
relationships), and the review below follows that order.

### Critical

**14. Lines 123–428 — blanket `SET <col> = 0 WHERE <col> IS NULL` across ~35 WIOA/outcome/demographic fields (A125, A127–A171) silently converts "data not reported" into "confirmed zero."**
This is the single biggest data-integrity concern in the pipeline. A `NULL` in a WIOA
characteristic field (e.g. a barrier-to-employment flag, A143–A169) or an outcome field (e.g.
A139/A141, WIOA employment count/earnings) means "we don't know" — zero-filling it asserts "we
checked, and the answer is no / $0." That's a materially different (and often false) claim in a
federal performance report, and it has knock-on effects:
- It does make the self-check's "Missing Info" flags disappear — but for the wrong reason (the
  data isn't actually present, it's just no longer `NULL`), not because the underlying reporting
  gap was closed.
- For earnings fields specifically (A141, A142), a forced `0` is exactly the value the self-check's
  own "Earnings Not Available" / "Median Earnings" checks are designed to catch — this guarantees
  that flag will fire for every program where WIOA earnings data was genuinely just missing rather
  than actually zero.
- It's also what manufactures Finding 15 below (a fabricated `$1` earnings entry), because a later
  block in this same file assumes any `A125 = 0` alongside `A123 > 0` needs "fixing," without
  distinguishing a real reported `$0` from a `NULL` that this file itself zeroed out a few hundred
  lines earlier.

If WIPS' file format genuinely can't accept a null in a positional field, that's a real constraint
— but even so, this should likely be scoped to fields where `0` is a defensible default (raw
counts) and not blanket-applied to earnings and rate-adjacent fields, and ideally logged/flagged so
someone can distinguish "we know it's zero" from "we don't have this data" for audit purposes.

**15. Lines 558–566 — `A125` (median earnings) gets set to a literal `1` to satisfy "if employed, earnings must be > 0."**
```sql
UPDATE ETP_ANNUAL_PY24_ALL_UPDATE_FINAL_FILE a
SET a.A125 = 1
WHERE a.A123 > 0
AND a.A125 = 0;
```
`$1` median earnings is not a plausible value for anyone — this passes the ">0" edit check while
submitting fabricated data to DOL. Trace back why `A125` is `0` here in the first place: this same
file's own line 123–127 (`SET A125 = 0 WHERE A125 IS NULL`, Finding 14) runs earlier and is the
most likely source of these zeros. The real fix is to not zero-fill `A125` for rows where `A123 >
0` in the first place (or to actually source the missing earnings value), not to paper over the
resulting inconsistency with a dollar amount that means nothing.

### High

**16. Lines 19–29 — the `A102` "collapse repeated periods" fix only fires when the repeated dots are at the very end of the string.**
```sql
UPDATE ETP_ANNUAL_PY24_ALL_UPDATE_FINAL_FILE a
   SET a.A102 = REPLACE(a.A102,'....','.')
 WHERE SUBSTR(a.A102, -4) LIKE '%....';
```
`SUBSTR(a.A102, -4)` only looks at the last 4 characters, so `"...."` occurring mid-string (e.g.
`"Level II.... Advanced Certificate"`) never satisfies the `WHERE` and is left uncleaned, even
though the `REPLACE` itself (once triggered) would fix the whole string. `STEP_2`'s equivalent fix
for `A106` (`REPLACE(F.A106,'..','.')`) has no such positional restriction — worth aligning `A102`
to the same unconditional approach, since a mid-string run of periods is exactly as likely to be a
WIPS parsing problem as a trailing one. Also note: a 5+ character run of dots at the end won't fully
collapse to a single `.` in one pass of this 3-statement ladder (see review notes on why `REPLACE`'s
non-overlapping matching can leave a residual `..`) — worth testing against real 3+ dot data before
relying on it.

**17. Lines 534–555 — the `A123`/`A129` and `A124`/`A130` "numerator ≤ denominator" fixes don't implement the rule stated in their own comments, and are inconsistent with the very next block.**
```sql
--A) IF A129 > 0, then A123 <= A129
UPDATE ... SET a.A129 = a.A123
WHERE a.A129 = 0
AND a.A123 > 0;
```
The comment describes "numerator exceeds a positive denominator"; the code instead only handles
"denominator is exactly zero." A row where `A129 > 0` but `A123 > A129` (the case the comment
actually describes) is never touched by either statement and would still trip the self-check's
"RATE Too High or Low" check on submission. The very next block, for `A126`/`A130`, gets this
right with a strictly simpler condition:
```sql
UPDATE ... SET a.A130 = a.A126
WHERE a.A126 > A130;
```
`a.A126 > A130` correctly covers both the "denominator is zero" and "numerator exceeds a positive
denominator" cases in one clause. Recommend rewriting the two blocks above it the same way:
`WHERE a.A123 > a.A129` and `WHERE a.A124 > a.A130`. (Also note line 585's bare `A130` — every
other line in the file qualifies columns with the `a.` alias; it happens to resolve correctly here
since there's only one table in scope, but it's an inconsistency worth cleaning up.)

**18. Lines 64–74 — the `A105` backfill's `EXISTS` guard checks the table against itself, not against `OSOS.PROVIDER_SERVICE`.**
```sql
UPDATE ETP_ANNUAL_PY24_ALL_UPDATE_FINAL_FILE a
SET a.A105 = (SELECT SUBSTR(PROVIDER_SERVICE_NAME_UPR,0,250) FROM OSOS.PROVIDER_SERVICE PS
              WHERE a.PROVIDER_SERVICE_ID = PS.PROVIDER_SERVICE_ID)
WHERE EXISTS (SELECT b.PROVIDER_SERVICE_ID FROM ETP_ANNUAL_PY24_ALL_UPDATE_FINAL_FILE b
              WHERE a.PROVIDER_SERVICE_ID = b.PROVIDER_SERVICE_ID)
AND a.A105 IS NULL;
```
The `EXISTS` subquery joins `a` back to `b`, both aliases of the same
`ETP_ANNUAL_PY24_ALL_UPDATE_FINAL_FILE` table — every row trivially finds itself, so this condition
is always true whenever `PROVIDER_SERVICE_ID` is non-null and does nothing. It looks like it was
meant to guard against the scalar subquery finding no match in `OSOS.PROVIDER_SERVICE` (i.e.
`WHERE EXISTS (SELECT 1 FROM OSOS.PROVIDER_SERVICE PS WHERE a.PROVIDER_SERVICE_ID =
PS.PROVIDER_SERVICE_ID)`). Currently harmless (the scalar subquery just returns `NULL` on no match,
which is a no-op since `A105` was already `NULL`), but it's dead logic that could mislead a future
reader into thinking there's a check here that isn't actually happening.

**19. The duplicate-removal block (lines 437–495) is a hand-curated list of one-off `DELETE`s from a past submission cycle, not a general dedup query.**
Every statement hardcodes a specific `PROVIDER_SERVICE_ID` plus a specific field value (an exit
date in `A172`, an earnings value in `A125`, a `PROVIDER_ID`) apparently copied from a prior WIPS
rejection report. Since `STEP_2`'s merge only matches on `PROVIDER_SERVICE_ID`, duplicate rows for
the same program shouldn't be possible to begin with — worth tracing why they occur upstream (most
likely in the base `OSOS.ETPL_ANN_RPT_9171_ALL_FINAL_2025` extract or in how `STEP_3a`/`3b` insert
new rows) and fixing there. As written, this section:
- won't catch next cycle's duplicates (different IDs), so it has to be manually rewritten every
  submission,
- could silently do nothing if the underlying row's values have since changed, or
- could delete the wrong row on a future run if some other program coincidentally matches the same
  literal `PROVIDER_SERVICE_ID` + value combination.

A generic `ROW_NUMBER() OVER (PARTITION BY <true duplicate key> ORDER BY <tiebreak>)` deleting
`WHERE rn > 1` would be reusable across cycles and would actually match the section's own stated
intent ("if a set of fields have the same data... keep 1, delete others") instead of independently
reasoned single-row deletes.

### Medium

**20. Lines 40–42 and 91–93 — missing `A102`/`A106` descriptions get replaced with one canned sentence for every program, regardless of what the program actually is.**
```sql
SET a.A102 = 'Adult Continuing Education.' WHERE a.A102 IS NULL;
...
SET a.A106 = 'Adult educational program or course providing knowledge enhancement with the goal of suitable employment.' WHERE a.A106 IS NULL;
```
This clears the "not null" edit check but injects identical generic boilerplate across
unrelated programs (a welding certificate and a nursing program would get the same description if
both were missing one). Reasonable as a last-resort default to avoid a hard reject, but worth a
comment flagging it as a placeholder and, ideally, periodically checking how many rows actually
rely on it — a high count would indicate a real upstream data-collection gap rather than a rare
edge case.

**21. Carriage-return/line-feed stripping (lines 44–50) is only applied to `A102`, not to `A105`/`A106`/`A103`, which are equally free text.**
An embedded `CHR(13)`/`CHR(10)` in a program title (`A105`) or description (`A106`) would corrupt
the flat file's record structure the same way it would in `A102`. Worth applying the same strip to
every free-text field, not just the one where it happened to be observed.

**22. The `A121`/`A122` fix (lines 522–531) and the `A126`/`A130` fix (lines 578–586) resolve a numerator/denominator (or subset/superset) mismatch by inflating the smaller field up to match the larger one, without knowing which side is actually wrong.**
`A122` (completers) should be a subset of `A121` (all exiters); when `A122 > A121`, this file raises
`A121` to close the gap rather than investigating whether `A122` was over-counted instead. Given
`STEP_1` was already found to compute `A121` and `A122` identically for some sources (prior review,
Finding 4) and `STEP_3a`/`3b` only ever update some of these fields together (prior review, Finding
7), the more likely root cause is that the multi-source merge pipeline updates paired
numerator/denominator or subset/superset fields asymmetrically — this file's fixes mask that
symptom rather than addressing it upstream.

### Minor / Housekeeping

- **35 sequential single-column `UPDATE ... WHERE ... IS NULL` statements (lines 123–428), each with its own `COMMIT`.** Same issue as the earlier review's Finding 10, at a larger scale — one `UPDATE` with 35 `SET` clauses would be both cheaper and atomic.
- **Line 116–120 (`A114`) has no explanatory comment**, unlike the `A113` rule immediately above it which quotes the exact WIPS edit-check text. A future reader has no way to know why `A114 = 0` is invalid without independently finding the DOL edit-check spec.
- **The final extract (lines 593–671) re-applies `WHERE PS.PROVIDER_SERVICE_DESC LIKE '%ETP%'`.** Since `STEP_3a`/`3b` insert new rows without checking this condition, it's worth confirming all appended BIG3/NONSCB programs' `OSOS.PROVIDER_SERVICE` records actually satisfy it — otherwise this filter could silently drop some of the rows `STEP_3a`/`3b` worked to append, with no warning that it happened.
- **No automated re-check that the hand-curated duplicate `DELETE`s (Finding 19) actually resolved everything** before the final extract runs — a `GROUP BY PROVIDER_SERVICE_ID HAVING COUNT(*) > 1` check immediately before the final `SELECT` would catch anything missed.

## What's working well

- The `GREATEST(NVL(x,0), NVL(y,0))` pattern used in `STEP_1`'s merge and both `STEP_3a`/`3b`
  merges is a solid, deliberate guard against regressing good data — `STEP_2` should adopt the same
  pattern (see Finding 6).
- Every derived column is commented with its `DE###` federal field code, and the header block in
  `STEP_1` documents the DE120–DE130 field meanings up front — good practice, worth extending to
  the WIOA-side fields (A133+) and to the date-window choices (Finding 8).
- The three-tier layering (SUNY/CUNY/BOCES individual matches → BIG3 aggregate → non-SCB aggregate)
  is a sensible way to combine heterogeneous data sources of decreasing granularity, and the
  row-count `SELECT COUNT(...)` checks after each step show good manual QA discipline.
- `STEP_4`'s "LOGICAL ERRORS" section (lines 502–586) quotes the actual WIPS edit-check rule text
  in a comment above most of the fixes (e.g. A108/A109, A113, A121/A122) — that's exactly the kind
  of documentation the rest of the pipeline is missing, and it's what made it possible to spot that
  the A123/A129 and A124/A130 code doesn't actually match its own stated rule (Finding 17).
