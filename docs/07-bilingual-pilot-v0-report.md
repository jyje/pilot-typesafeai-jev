# Bilingual triage pilot: v0 report

**Snapshot:** 2026-10-22
**Status:** exploratory reference labels; not an independently adjudicated gold set

## Executive summary

This report records a small English-Korean annotation pilot and the operational checkpoint of the separate bilingual availability screen. It is a descriptive progress report, not a model-quality evaluation. The local review snapshot contains a complete 60-item label pass and a second, partial pass on 8 items. The overlap is too small and incomplete to establish a final gold set or support broad agreement claims.

## Annotation snapshot

The pilot contains 60 bilingual message items labeled on intent, urgency, prompt-injection attempt, and recommended route. One reviewer labeled all 60 items. A second reviewer labeled 8 of them. Those 8 overlapping items are not documented as a random sample, and the remaining 52 have only one recorded label.

Descriptive agreement on the 8 overlapping items:

| Dimension | Matching labels |
| --- | ---: |
| Intent | 6 / 8 (75%) |
| Urgency | 6 / 8 (75%) |
| Prompt-injection attempt | 8 / 8 (100%) |
| Recommended route | 6 / 8 (75%) |
| Exact match on all four dimensions | 2 / 8 (25%) |

These are raw counts for a very small partial overlap. No chance-corrected agreement statistic or population estimate is reported.

The full 60-item pass has the following marginal counts. They describe one reviewer’s labels and must not be read as validated prevalence or ground truth.

| Dimension | Label counts |
| --- | --- |
| Intent | Account 17; billing 18; technical 13; chitchat 6; other/unclear 6 |
| Urgency | 0: 27; 1: 14; 2: 19 |
| Prompt-injection attempt | No 43; yes 17 |
| Recommended route | Answer 32; refuse 17; human review 9; escalate 2 |

## Separate availability-screen checkpoint

The experiment ledger is operational metadata, not evidence of accuracy. Its recorded cycle 291 completed 8 requests; cycle 292 completed with no pending screen work added. This report does not publish item-level prompts, provider outputs, request identifiers, or per-model performance. The availability screen and this annotation pilot are distinct from the confirmation and stability stages.

## Interpretation and limits

- A single complete label pass does not establish a gold standard.
- Only 8 of 60 items have two recorded labels, with no evidence that the overlap was sampled randomly.
- The observed matches are descriptive only. They do not estimate agreement on the full item set.
- The task set is small and hand-curated. It does not establish production performance, language parity, safety, accuracy, or calibration.
- This report intentionally excludes raw messages, reviewer codes, per-item annotations, private database contents, and model response data.
- The aggregate counts were read from a local annotation snapshot. The underlying private annotation records are not included in the repository, so a remote reader cannot independently recompute these figures from this report alone.

## Next steps

1. Have a second reviewer independently label the remaining 52 items without seeing the existing labels.
2. Preserve the two independent labels for every item, then jointly review disagreements using the written criteria. Record consensus labels separately from the original judgments.
3. Freeze and version a two-reviewer reference manifest only after all 60 items have two reviews and disagreements are resolved or explicitly marked unresolved. Keep provenance and a content hash with the private source records; publish only a privacy-reviewed, sanitized artifact.
4. Until that gate is met, do not present these labels as final gold and do not use them for confirmation accuracy or stability claims.

## Reproducibility note

This v0 is a snapshot of locally recorded aggregate annotation and ledger status. It does not bundle the private source data. Reproduction of the annotation aggregates requires a later privacy-reviewed export with a documented schema and validation procedure. No additional inference or provider requests are part of this report.
