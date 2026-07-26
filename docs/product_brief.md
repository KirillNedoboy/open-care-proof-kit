# Product Brief (Historical Product Intent)

> This document records earlier product intent. The approved product direction
> is [ADR 0001](adr/0001-opencare-product-direction.md); current repository
> capability is in [project status](project-status.md). This file is not the
> current roadmap.

## Product

OpenCare is an open-source, privacy-first, agent-ready personal medical and genomics workspace for a person and family.

The current repository is OpenCare Proof Kit: a validated local-first proof kit that demonstrates the trust, evidence, safety, audit, and eval discipline through a narrow synthetic Medication-to-Doctor Briefing workflow.

## Product Direction

OpenCare should become a patient-owned workspace for maintaining:

- personal medical history;
- family context;
- medications;
- symptoms;
- labs;
- visits;
- documents;
- questions;
- source and provenance records;
- optional genetic data later.

The product must be useful without DNA. Genetics is an optional enhancement layer that can deepen the workspace after the Health/Family Vault Core exists.

## Current Reference Workflow

Medication-to-Doctor Briefing is the current synthetic/demo workflow. It generates a clinician-reviewable medication discussion briefing from structured health context, genotype-like demo data, local evidence packs, deterministic rules, safety policy, and report writing.

This workflow remains the validated runtime behavior until new vault-first phases are implemented.

## User

Primary users for the next product direction:

- privacy-focused people organizing their own health context;
- families maintaining shared medical context and questions;
- open-source AI builders who need an agent-ready health data substrate;
- clinicians, pharmacists, or genetic counselors evaluating future review workflows;
- grant reviewers evaluating trustworthy sensitive-data infrastructure.

## Pain

Personal and family health context is scattered across PDFs, portals, notes, labs, prescriptions, visit summaries, and memory. The current choices are weak:

1. Upload sensitive data into closed cloud tools.
2. Ask a generic LLM and risk hallucinated or unsupported advice.
3. Manually assemble context before every appointment.
4. Treat genetics as the starting point instead of one optional layer of the record.

## Core Benefit

OpenCare gives a person or family a local, inspectable workspace for organizing medical context, tracking provenance, preparing questions, and making the data usable by controlled AI agents.

The LLM is a copilot/interface. It can explain, summarize, ask follow-up questions, and help navigate the vault. It is not the source of truth.

## Product Rules

- Vault first.
- Genetics second.
- LLM third as interface.
- Family as differentiator.
- Evidence as discipline.
- Important claims map to evidence or are marked otherwise.
- The product must remain useful without genetics.

## Non-Goals

No diagnosis, dosage advice, treatment recommendation, medication selection advice, real patient data in the demo, real genetic data support in the current MVP, FASTQ/WGS pipeline, inheritance risk inference, SaaS, auth, payments, Telegram, or cloud raw genotype upload by default.
