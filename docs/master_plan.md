# Open Care Master Plan (Historical)

> Historical planning document. Use [ADR 0001](adr/0001-opencare-product-direction.md)
> and [the Product Core roadmap](roadmap/product-core-roadmap.md) for approved
> current direction and next work.

## What We Are Building

OpenCare is an open-source, privacy-first, agent-ready personal medical and genomics workspace for a person and family.

The product should help a user or family maintain:

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

OpenCare must be useful without DNA. Genetics is an enhancement layer, not the entry requirement. A user should be able to start with medical history, documents, labs, medications, symptoms, visits, and questions, then add genetic context only when the vault foundation can support it safely.

The system should be agent-ready by design: structured enough for AI tools to navigate, inspect, summarize, and ask follow-up questions without turning the LLM into the source of truth.

## What We Are Not Building

OpenCare is not:

- a medical chatbot;
- a generic trust layer as the only product surface;
- clinical decision support;
- a diagnosis system;
- automated treatment assignment;
- a genetic horoscope UI;
- a giant all-in-one platform for clinics, insurers, EHR vendors, and consumers at once.

The product should not promise an AI doctor. It should help a person organize context, prepare questions, preserve provenance, and make sensitive health data usable by local or controlled agents without inventing clinical authority.

## Real Product Value

The value chain starts with a patient-owned data vault. A private workspace that can hold medical history, documents, labs, medications, symptoms, visits, and questions is useful before any genetic feature exists.

Genomics can deepen the workspace later. Once the vault has structured context and provenance, selected genetics features can add drug-response context, question-driven interpretation, raw-to-insight workflows, and family/inheritance workflows. Those layers should arrive only after the base vault can carry sources, limitations, audit, and safe unsupported states.

Family context is a differentiator. Most personal health products treat the user as an isolated profile. OpenCare should support a person and family as first-class context, while keeping production inheritance claims out of scope until the evidence and safety model can handle them.

The long-term substrate is open and agent-ready: folders, schemas, provenance records, audit metadata, and policy gates that other builders can inspect, fork, self-host, and adapt.

## Product Thesis

OpenCare turns scattered medical and genetic context into a personal workspace for understanding, preparation, longitudinal tracking, and AI-assisted navigation.

The LLM should help users ask better questions, summarize what is already in the vault, prepare for clinician conversations, and navigate records. It should not become the clinical source of truth. Important claims must map to stored evidence or be marked as unsupported, uncertain, or out of scope.

## Moat And Non-Moat

Non-moat:

- using an LLM;
- medical chat;
- dashboard UI;
- PDF summaries;
- generic retrieval-augmented generation.

Potential moat:

- a well-designed personal and family data model;
- usefulness without genetics, with genetics as a deeper layer later;
- raw-to-insight workflows once the vault and evidence model are mature;
- family intelligence layer;
- agent-ready open-source substrate;
- trust, evidence, provenance, safety, and audit discipline.

The moat is not one model call. It is the durable structure around sensitive personal context.

## Architecture Direction

Future architecture should organize around these layers:

- Data layer: local files, structured records, source files, metadata, and exportable formats.
- Medical Vault: person profiles, family profiles, history, medications, conditions, labs, symptoms, visits, documents, questions, and timeline events.
- Genomics Layer: optional genetic imports and selected evidence-backed cards after the vault foundation exists.
- Family / Inheritance Layer: family graph, relationships, shared context, and future inheritance-aware workflows with strict evidence gates.
- Evidence / Policy / Safety Layer: provenance, source requirements, limitations, unsupported-state handling, safety checks, and audit logs.
- LLM Layer: interface, summaries, explanations, follow-up questions, and navigation help.
- UI Layer: local workspace for viewing, editing, reviewing, and exporting records and audit-backed outputs.

The current validated runtime remains Medication-to-Doctor Briefing until new phases are implemented.

## Deterministic vs LLM-powered

Deterministic parts:

- schema and storage;
- imports and normalization;
- provenance tagging;
- family relationship graph;
- policy enforcement;
- audit logs;
- unsupported state handling.

LLM-powered parts:

- explanations;
- summaries;
- doctor-prep notes;
- question understanding;
- follow-up questions;
- navigation help.

The LLM can interpret the workspace for the user. It must not decide what is true when the vault, evidence, or policy layer does not support the claim.

## MVP Strategy

The MVP must start with:

- Person / Family profiles;
- Medical documents vault;
- Labs / meds / conditions structured storage;
- Timeline / events;
- Question workspace;
- Evidence/provenance model;
- Agent-ready folder/schema conventions;
- Minimal AI-assisted summaries later.

Good-to-have later:

- consumer DNA raw import;
- basic PGx / selected genetics cards;
- family relationship support;
- drug briefing scaffold.

Not in MVP:

- full exome/WGS pipeline;
- advanced trait dashboards;
- personality/RPG genomics as central value;
- clinician/institutional platform;
- FASTQ/WGS raw reconstruction pipeline.

## 90-Day Build Strategy

### Phase 0: scope and data model

Lock the vault-first scope, define person/family entities, define medical record categories, and document what remains out of scope.

### Phase 1: vault core

Implement V1 Health/Family Vault Core schemas and a synthetic family demo dataset. This is the immediate next implementation phase.

### Phase 2: ingest + provenance

Add local ingestion conventions for documents, labs, medications, visits, and notes. Every imported or entered item should carry source/provenance metadata.

### Phase 3: usable non-genetic product

Create a useful workspace without DNA: profiles, timeline, document index, medication and lab views, question workspace, and exportable doctor-prep summaries.

### Phase 4: genetic layer v1

Bring back the Genome Expansion / Genome Trust Console as an optional layer after the vault foundation exists. Start with selected synthetic/demo genetic examples and fail-closed evidence rules.

### Phase 5: family/drug-response differentiation

Build family-aware views, synthetic family examples, and drug-response lenses that reuse the evidence and audit discipline without making treatment recommendations.

### Phase 6: grant/demo/repo packaging

Refresh reviewer docs, screenshots, demo scripts, validation notes, and grant materials to match the implemented vault-first product.

## Sentient Positioning

The strongest grant story is:

- open-source substrate;
- agent-ready workspace;
- sensitive personal data use case;
- model-agnostic architecture;
- reusable by others;
- privacy-first and inspectable.

OpenCare fits the Sentient/public-goods direction best when it is framed as an open workspace for sensitive personal agents, not as a closed medical chatbot or a speculative genomics app.

## Product Risks

- Banality: a generic medical notes dashboard is not enough.
- Pseudoscience: genetics content can drift into trait claims and horoscope-style UX if not controlled.
- Scope explosion: trying to serve consumers, clinics, insurers, EHR vendors, and researchers at once will dilute the product.
- LLM-first trap: chat should not become the product core.
- Over-investing in deep genomics too early: advanced genome workflows before the vault exists would weaken the product and the safety story.

## Product Rules

- Usefulness without genetics is mandatory.
- Genetics is enhancement, not entry requirement.
- LLM is interpreter/copilot, not product core.
- Important claims map to evidence or are marked otherwise.
- Family support is first-class.
- Open-source reuse matters.
- Avoid pseudo-clinical swagger.
- Do not promise AI doctor.

## Bottom Line

Vault first. Genetics second. LLM third as interface. Family as differentiator. Evidence as discipline.
