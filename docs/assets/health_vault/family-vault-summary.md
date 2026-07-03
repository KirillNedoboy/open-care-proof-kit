# Health/Family Vault Summary

## Safety Boundary
- This artifact is synthetic/demo-only.
- It is a deterministic summary of recorded context.
- It is not diagnosis.
- It is not treatment recommendation.
- It is not dosage guidance.
- It is not medication selection.
- It is not start/stop medication advice.
- There is no genetics in V1C.

## Family Overview
- Family: Synthetic Demo Family (family-demo-01)
- People: 3
- Relationships: 2

## People
- Demo Adult Alex (person-alex); role: self; synthetic: True
- Demo Adult Jordan (person-jordan); role: spouse; synthetic: True
- Demo Teen Sam (person-sam); role: child; synthetic: True

## Relationships
- person-alex -> person-jordan (spouse)
- person-alex -> person-sam (child)

## Recorded Medications
- person-alex: sertraline (current); Medication question recorded for clinician-review preparation.; recorded_medication_context_not_recommendation; sources: Synthetic medication list, March 2026
- person-jordan: loratadine (past); Past medication recorded as synthetic family context.; recorded_medication_context_not_recommendation; sources: Synthetic medication list, March 2026

## Recorded Conditions / Concerns
- person-alex: Sleep concern recorded by demo user (active); User-recorded context for clinician discussion; not an OpenCare clinical conclusion.; recorded_context_not_system_diagnosis; sources: Synthetic primary care note, January 2026
- person-sam: Seasonal allergy context recorded by demo user (historical); Demo-recorded family context only; not an OpenCare clinical conclusion.; recorded_context_not_system_diagnosis; sources: Synthetic primary care note, January 2026

## Recorded Labs
- person-alex: A1c on 2026-02-14; Within synthetic reference context; recorded_lab_context_not_interpretation; sources: Synthetic lab panel, February 2026
- person-jordan: Vitamin D on 2026-02-14; Flagged in synthetic record for clinician discussion; recorded_lab_context_not_interpretation; sources: Synthetic lab panel, February 2026

## Visits / Encounters
- person-alex: primary care on 2026-01-22; Synthetic visit summary focused on organizing medication and sleep questions.; recorded_visit_context_not_medical_advice; sources: Synthetic primary care note, January 2026
- person-sam: family check-in on 2026-03-04; Synthetic family visit summary for vault timeline demonstration.; recorded_visit_context_not_medical_advice; sources: Synthetic primary care note, January 2026

## Timeline
- 2026-01-22: person-alex - Primary care visit recorded (visit); sources: Synthetic primary care note, January 2026
- 2026-02-14: person-alex - A1c lab result recorded (lab); sources: Synthetic lab panel, February 2026
- 2026-02-14: person-jordan - Vitamin D lab result recorded (lab); sources: Synthetic lab panel, February 2026
- 2026-03-04: person-sam - Family check-in recorded (visit); sources: Synthetic primary care note, January 2026

## Question Workspace
- question-alex-sleep: What context should Demo Adult Alex bring to a clinician about sleep concerns? (person, open); recorded_question_not_answer; sources: Synthetic primary care note, January 2026
- question-family-missing-sources: Which family records still need stronger source documents? (family, needs_source); recorded_question_not_answer; sources: Synthetic primary care note, January 2026

## Provenance Coverage
- Total important records: 14
- Records with source: 14
- Records missing source: 0
- Missing source item IDs: none

## What This Artifact Does Not Do
- Does not create medical interpretation.
- Does not use LLM generation.
- Does not add API routes, CLI commands, UI, or templates.
- Does not add genetic data support or genome_profile implementation.
- Does not change PGx behavior or Medication-to-Doctor Briefing.
