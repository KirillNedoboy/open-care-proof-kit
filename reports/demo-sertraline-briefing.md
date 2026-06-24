# Medication-to-Doctor Briefing

## Safety note

This report is not medical advice. It does not diagnose, prescribe, recommend dosage, or tell anyone to start or stop medication. It is a clinician-reviewable briefing generated from synthetic/demo data.

## Patient context used

- Patient profile: Synthetic Demo Patient A

- Data classification: synthetic_demo_only

- Age range: adult

- Current medications listed: sertraline

- Problems listed: demo mood symptoms

## Medication question

What should be discussed with a clinician before or during use of `sertraline`?

## Relevant findings

### CYP2C19 / rs4244285
- Genotype observed in demo data: `AG`
- Evidence level: `demo_evidence_reference_required`
- Clinician review required: `True`
- Summary: A demo CYP2C19 marker matched the synthetic genotype. This is a clinician-discussion item only and must be verified against official pharmacogenomics guidance before any real clinical use.
- Limitations: Demo rule only. It does not determine medication choice, dose, diagnosis, safety, or efficacy.

## Not found / insufficient data

This MVP uses a small local demo evidence pack. Absence of a finding means only that no demo rule matched. It does not prove absence of pharmacogenomic relevance.

## Uncertain / not actionable

Unsupported variants, variants of uncertain significance, weak associations, and model-only predictions are not actionable in this project.

## Questions for clinician

1. Is pharmacogenomic testing or review relevant for this medication in this clinical context?

2. Are medication history, side-effect history, or comorbidities more important than the demo genetic finding?

3. Should any official guideline or drug label be reviewed before making a clinical decision?

## Sources

- CPIC guidelines index / demo reference: https://cpicpgx.org/guidelines/

## Audit metadata

- Evidence pack: `pgx-demo-pack`

- Evidence pack version: `0.1.0`

- Report mode: `local-first demo`

- Raw health/genetic data exported: `false`
