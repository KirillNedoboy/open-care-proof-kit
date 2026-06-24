# Safety Policy

## Hard blocks

The system must block or fail report validation if generated output includes:

- diagnosis;
- dosage adjustment;
- start medication instruction;
- stop medication instruction;
- unsupported clinical claim;
- claim without source;
- actionable VUS claim;
- hidden uncertainty.

## Required sections

Every report must include:

- safety note;
- clinician review note;
- limitations;
- sources;
- evidence level;
- audit metadata;
- questions for clinician.

## LLM role

The LLM is a report writer and explainer. It is not the source of medical truth.

## Safe output pattern

Use:

> This finding may be worth discussing with a clinician.

Do not use:

> You should take...
> You should stop...
> Your dose should be...
