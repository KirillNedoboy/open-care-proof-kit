from typing import Final, Literal

from fastapi import Request

Locale = Literal["en", "ru"]

SUPPORTED_LOCALES: Final[tuple[Locale, ...]] = ("en", "ru")
DEFAULT_LOCALE: Final[Locale] = "en"
LOCALE_COOKIE_NAME: Final = "opencare_locale"

TRANSLATIONS: Final[dict[Locale, dict[str, str]]] = {
    "en": {
        "app.name": "OpenCare",
        "page.workspace_title": "OpenCare Health Workspace",
        "workspace.heading": "Welcome to your workspace",
        "workspace.intro": (
            "See what is recorded for the Person you are viewing, then choose where to continue."
        ),
        "workspace.safety": (
            "OpenCare organizes source-backed records. It does not interpret results or "
            "make medical recommendations."
        ),
        "workspace.active_person": "Viewing Person",
        "workspace.no_active_person": "No Person selected",
        "workspace.loading_person": "Loading selected Person…",
        "workspace.choose_person": "Choose an accessible Person to begin.",
        "workspace.switcher_label": "Switch Person",
        "workspace.selector_loading": "Loading accessible People…",
        "workspace.selector_placeholder": "Choose a Person",
        "workspace.selector_empty": "No accessible People",
        "workspace.no_accessible_persons": "No health profile is available yet.",
        "workspace.no_accessible_persons_help": (
            "Create a profile through the existing owner flow, or ask someone to share "
            "access with you."
        ),
        "workspace.overview_title": "Overview",
        "workspace.overview_summary": (
            "A factual snapshot of the records available to this account for the active Person."
        ),
        "workspace.metric_records": "Confirmed records",
        "workspace.metric_documents": "Documents",
        "workspace.metric_medications": "Current medications",
        "workspace.metric_activity": "Recent activity",
        "workspace.metric_pending": "Items awaiting review",
        "workspace.no_health_data": "No health data has been added for this Person yet.",
        "workspace.no_health_data_help": (
            "Start with a source document or an entry for review. Nothing is inferred or "
            "filled in automatically."
        ),
        "workspace.quick_actions": "Next actions",
        "workspace.add_document": "Add a document",
        "workspace.open_records": "Open records",
        "workspace.open_genetics": "Open Genetics",
        "workspace.ask_opencare": "Ask OpenCare",
        "workspace.family_access": "Manage family access",
        "workspace.recent_activity": "Recent activity",
        "workspace.no_recent_activity": "No recent activity is available for this Person.",
        "workspace.viewing": "Viewing",
        "workspace.date_of_birth": "Date of birth",
        "workspace.clear_selection": "Clear Person",
        "workspace.create_profile": "Create another Person",
        "workspace.create_profile_help": (
            "Creating a Person assigns your signed-in account full owner access. Other "
            "people do not receive access automatically."
        ),
        "workspace.edit_profile": "Edit selected Person",
        "workspace.edit_profile_title": "Edit Person",
        "workspace.save_profile": "Save Person",
        "workspace.no_profile_selected": "No Person selected",
        "workspace.profile_choice_help": "Choose an accessible Person to load their workspace.",
        "workspace.loading_workspace": "Loading workspace…",
        "workspace.workspace_loaded": "Workspace loaded.",
        "workspace.selection_cleared": "Person selection cleared.",
        "workspace.person_not_available": "That Person is not available.",
        "workspace.select_before_load": "Choose a Person before loading the workspace.",
        "workspace.select_profile": "Select a Person",
        "workspace.section_person": "Person",
        "workspace.section_review": "Review",
        "workspace.section_records": "Records",
        "workspace.section_timeline": "Timeline",
        "workspace.section_visits": "Visits & Brief",
        "workspace.section_export": "Export",
        "workspace.records_empty": "No confirmed records are available.",
        "workspace.activity_empty": "No recent activity is available.",
        "workspace.pending_empty": "No entries are waiting for review.",
        "workspace.person_count": "accessible People",
        "workspace.records_count": "records",
        "workspace.documents_count": "documents",
        "workspace.activity_count": "events",
        "workspace.pending_count": "waiting for review",
        "status.session_expired": "Your session has expired. Sign in again.",
        "status.action_unavailable": "This action is no longer available.",
        "status.record_changed": "This record changed. Refresh to see the latest version.",
        "status.check_values": "Check the entered values and try again.",
        "status.integrity_failure": "Integrity: stored evidence could not be verified.",
        "status.storage_unavailable": (
            "Local Product Core storage is unavailable. Try again shortly."
        ),
        "status.request_failed": "The request could not be completed. Try again.",
        "workspace.latest_record": "Latest confirmed record",
        "workspace.selected_visit": "Selected Visit",
        "workspace.review_summary": "Source-backed candidates available for this Person.",
        "workspace.documents_summary": "Source documents available for this Person.",
        "workspace.records_summary": "Current confirmed records and their history.",
        "workspace.timeline_summary": "Record lifecycle events for this Person.",
        "workspace.visits_summary": ("Plan questions and prepare a source-backed Visit Brief."),
        "workspace.export_summary": (
            "Download a portable copy of this Person and reachable sources."
        ),
        "workspace.medications": "Medications",
        "workspace.conditions": "Recorded conditions",
        "workspace.labs": "Labs",
        "workspace.visits": "Visits",
        "workspace.fact_type": "Fact type",
        "workspace.all_fact_types": "All fact types",
        "workspace.status": "Status",
        "workspace.all_statuses": "All statuses",
        "workspace.waiting_review": "Waiting for review",
        "workspace.confirmed": "Confirmed",
        "workspace.corrected": "Corrected",
        "workspace.rejected": "Rejected",
        "workspace.unsupported": "Unsupported by source",
        "workspace.search_loaded_candidates": "Search loaded candidates",
        "workspace.no_documents": "No documents have been added for this profile.",
        "workspace.document_upload_label": "Add a PDF or plain-text document",
        "workspace.document_upload_help": (
            "Files are stored as source evidence. Uploads are bounded and never rendered as "
            "rich content."
        ),
        "workspace.upload_document": "Upload document",
        "workspace.page_text": "Page text",
        "workspace.page": "Page",
        "workspace.choose_page": "Choose a page to inspect.",
        "workspace.select_span": "Select text to attach a precise source span.",
        "workspace.add_typed_candidate": "Add typed candidate for review",
        "workspace.typed_candidate_help": (
            "Enter a Medication, Condition, or Lab exactly as recorded. Nothing is "
            "auto-extracted or prefilled."
        ),
        "workspace.name_or_test_name": "Name / test name",
        "workspace.details_as_reported": "Details as reported",
        "workspace.add_for_review": "Add for review",
        "workspace.add_medication": "Add medication",
        "workspace.add_condition": "Add recorded condition",
        "workspace.add_lab": "Add lab record",
        "workspace.review_pending_help": (
            "New entries wait for review before becoming confirmed records."
        ),
        "workspace.condition_safety": (
            "Condition wording is stored as source text and is not an OpenCare diagnosis."
        ),
        "workspace.lab_safety": "Values are shown as reported, without interpretation.",
        "workspace.medication_name": "Medication display name",
        "workspace.schedule_optional": "Schedule (optional, as recorded)",
        "workspace.note_optional": "Note (optional)",
        "workspace.recorded_condition_name": "Recorded condition name",
        "workspace.status_optional_source": "Status (optional, source text)",
        "workspace.onset_optional": "Onset date (as recorded, optional)",
        "workspace.test_name": "Test name",
        "workspace.result_as_reported": "Result (as reported)",
        "workspace.unit_as_reported": "Unit (as reported, optional)",
        "workspace.reference_range_as_reported": "Reference range (as reported, optional)",
        "workspace.observed_date_as_reported": "Observed date (as reported, optional)",
        "workspace.flag_as_reported": "Flag (as reported, optional)",
        "workspace.historical_superseded": "Historical and superseded records",
        "workspace.no_current_records": "No current confirmed records.",
        "workspace.no_historical_records": "No historical or superseded records.",
        "workspace.no_pending_fact": "No entries are waiting for review.",
        "workspace.no_confirmed_fact": "No records have been confirmed.",
        "workspace.no_historical": "No historical records.",
        "workspace.recorded_status": "Recorded status",
        "workspace.recorded_onset": "Recorded onset",
        "workspace.result_reported": "Result as reported",
        "workspace.unit_reported": "Unit as reported",
        "workspace.reference_range_reported": "Reference range as reported",
        "workspace.observed": "Observed",
        "workspace.flag_reported": "Flag as reported",
        "workspace.confirmed_at": "Confirmed",
        "workspace.superseded": "Superseded",
        "workspace.recorded_in_opencare": "Recorded in OpenCare",
        "workspace.record_lifecycle_help": (
            "Record lifecycle events. Scheduled visits remain separate below."
        ),
        "workspace.all": "All",
        "workspace.create_visit": "Create visit",
        "workspace.visit_title": "Visit title",
        "workspace.specialist_optional": "Specialist (optional)",
        "workspace.scheduled_visit_optional": "Scheduled visit (optional)",
        "workspace.no_visits": "No visits have been created for this profile.",
        "workspace.select_visit": "Select visit",
        "workspace.selected_visit_button": "Selected visit",
        "workspace.questions_for": "Questions for",
        "workspace.no_questions": "No questions have been added for this visit.",
        "workspace.question": "Question",
        "workspace.move_question_up": "Move question up",
        "workspace.move_question_down": "Move question down",
        "workspace.remove": "Remove",
        "workspace.edit": "Edit",
        "workspace.visit_brief": "Visit Brief",
        "workspace.brief_help": "Evidence and questions are snapshotted into immutable revisions.",
        "workspace.initialize_brief": "Initialize Visit Brief",
        "workspace.select_visit_brief": "Select a Visit to prepare its Brief.",
        "workspace.initialize_persistent_brief": "Initialize a persistent Brief for this Visit.",
        "workspace.no_persistent_brief": "No persistent Brief is available for this Visit.",
        "workspace.select_confirmed_evidence": "Select confirmed evidence",
        "workspace.validate_evidence": "Validate evidence",
        "workspace.generate_revision": "Generate revision",
        "workspace.preparation_notes": "Preparation notes",
        "workspace.save_notes_revision": "Save notes as revision",
        "workspace.unsaved_warning": (
            "Unsaved preparation notes will be discarded if you switch Person or Visit."
        ),
        "workspace.revision_history": "Revision history",
        "workspace.no_revisions": "No revisions have been created.",
        "workspace.view_revision": "View revision",
        "workspace.restore_revision": "Restore revision",
        "workspace.revision_unavailable": "Revision unavailable",
        "workspace.current": "Current",
        "workspace.evidence_changed": "Evidence changed since this revision",
        "workspace.selected_record_changed": "Selected record or source changed",
        "workspace.no_eligible_evidence": "No eligible confirmed evidence.",
        "workspace.evidence_record": "Evidence record",
        "workspace.revision": "Revision",
        "workspace.copy_markdown": "Copy Markdown",
        "workspace.download_markdown": "Download Markdown",
        "workspace.export_vault": "Export vault",
        "workspace.export_warning_title": "Export sensitive vault data?",
        "workspace.export_warning_help": (
            "This download may contain health information and source evidence. Store it only "
            "where you control access."
        ),
        "workspace.download_vault": "Download vault",
        "workspace.cancel": "Cancel",
        "workspace.reset": "Reset",
        "workspace.save_visit": "Save visit",
        "workspace.add_question": "Add question",
        "workspace.edit_question": "Edit question",
        "workspace.question_text": "Question text",
        "workspace.save_question": "Save question",
        "workspace.correct_record": "Create correction",
        "workspace.reject_candidate": "Reject candidate",
        "workspace.mark_unsupported": "Mark unsupported by source",
        "workspace.confirm_record": "Confirm record",
        "workspace.reject_confirm": "Reject this candidate?",
        "workspace.candidate_marked_unsupported": "Candidate marked unsupported by source.",
        "workspace.record_confirmed": "Record confirmed.",
        "workspace.candidate_rejected": "Candidate rejected.",
        "workspace.fact": "Fact",
        "workspace.created": "Created",
        "workspace.onset_date": "Onset date (as recorded)",
        "workspace.observed_date": "Observed date (as reported)",
        "workspace.revision_viewing": "Viewing revision",
        "workspace.revision_origin": "origin",
        "workspace.no_eligible_confirmed_evidence": "No eligible confirmed evidence.",
        "workspace.no_entries_match": "No entries match this view.",
        "workspace.medication_confirmed": "Medication record confirmed",
        "workspace.condition_confirmed": "Condition record confirmed",
        "workspace.lab_confirmed": "Lab record confirmed",
        "workspace.record_superseded": "Record superseded by reviewed correction",
        "workspace.no_specialist": "No specialist",
        "workspace.no_scheduled_date": "No scheduled date",
        "workspace.medication_pending": "Medication entry is waiting for review.",
        "workspace.whole_source": "Whole source",
        "workspace.manual_medication_name": "Medication name in a manual entry",
        "workspace.manual_condition_name": "Recorded condition name in a manual entry",
        "workspace.manual_lab_name": "Lab test name in a manual entry",
        "workspace.manual_field": "Recorded field in a manual entry",
        "workspace.document_page": "Document page",
        "workspace.codepoints": "codepoints",
        "workspace.source_text_characters": "Source text characters",
        "workspace.specific_source_location": "Specific location recorded in the source",
        "workspace.origin_generated": "Generated",
        "workspace.origin_user_edit": "User edit",
        "workspace.origin_restored": "Restored",
        "workspace.source_provenance": "Source & provenance",
        "workspace.source_id": "Source ID",
        "workspace.registered": "Registered",
        "workspace.size": "Size",
        "workspace.media_type": "Media type",
        "workspace.integrity_verified": "Integrity verified",
        "workspace.integrity_not_verified": "Integrity not verified",
        "workspace.source_metadata_unavailable": "Source metadata unavailable.",
        "workspace.source_location": "Source location",
        "workspace.correction_lineage": "Correction lineage",
        "workspace.manual_entry": "Manual entry",
        "workspace.source": "Source",
        "workspace.document": "Document",
        "workspace.text": "Text",
        "workspace.bytes": "bytes",
        "workspace.correction_superseded": (
            "Correction lineage: superseded by a newer confirmed record."
        ),
        "workspace.document_uploaded": "Document uploaded.",
        "workspace.typed_candidate_pending": "Typed candidate is waiting for review.",
        "workspace.condition_pending": "Condition entry is waiting for review.",
        "workspace.lab_pending": "Lab entry is waiting for review.",
        "workspace.question_order_updated": "Question order updated.",
        "workspace.question_removed": "Question removed.",
        "workspace.save_correction": "Save correction",
        "workspace.correct_medication": "Correct medication entry",
        "workspace.correct_condition": "Correct condition entry",
        "workspace.correct_lab": "Correct lab entry",
        "workspace.correction_pending": "Correction is waiting for review.",
        "workspace.profile_updated": "Profile updated.",
        "workspace.visit_created": "Visit created.",
        "workspace.visit_updated": "Visit updated.",
        "workspace.question_added": "Question added.",
        "workspace.question_updated": "Question updated.",
        "workspace.brief_initialized": "Visit Brief initialized.",
        "workspace.evidence_valid": "Selected evidence is valid.",
        "workspace.brief_revision_generated": "Visit Brief revision generated.",
        "workspace.notes_saved": "Preparation notes saved as a new revision.",
        "workspace.brief_restored": "Current Brief revision restored.",
        "workspace.markdown_copied": "Markdown copied.",
        "workspace.copy_unavailable": "Copy is unavailable in this browser.",
        "workspace.markdown_downloaded": "Markdown download prepared.",
        "workspace.vault_downloaded": "Vault download prepared.",
        "optional": "optional",
        "page.genetics_title": "OpenCare Genetics Workspace",
        "genetics.kicker": "Genetics Workspace",
        "genetics.heading": "Evidence before interpretation",
        "genetics.intro": (
            "Review selectively indexed observations, their evidence, and research questions "
            "without exposing the raw genome."
        ),
        "genetics.person_label": "Current genetics profile",
        "genetics.person_selector_label": "Switch Person",
        "genetics.no_person": "Select a Person to view genetics.",
        "genetics.no_access": "Genetics access is not available for this Person.",
        "genetics.empty_title": "No genetic data yet.",
        "genetics.empty_help": "Import a supported consumer genotype file to begin.",
        "genetics.live_badge": "Live",
        "genetics.import_cta": "Import genetic data",
        "genetics.privacy_note": (
            "The original source remains local to this OpenCare installation. Only "
            "selected/indexed observations participate in Genetics features. Raw genome is "
            "excluded from supported model/provider context."
        ),
        "genetics.sections_label": "Genetics sections",
        "genetics.tab_overview": "Overview",
        "genetics.tab_overview_sub": "Source and coverage",
        "genetics.tab_variants": "Variants",
        "genetics.tab_variants_sub": "Indexed observations",
        "genetics.tab_pgx": "Pharmacogenomics",
        "genetics.tab_pgx_sub": "Medication relevance",
        "genetics.tab_health": "Health associations",
        "genetics.tab_health_sub": "Reviewed findings",
        "genetics.tab_traits": "Traits & systems",
        "genetics.tab_traits_sub": "Exploratory pathways",
        "genetics.tab_evidence": "Evidence",
        "genetics.tab_evidence_sub": "Sources and limits",
        "genetics.tab_family": "Family comparison",
        "genetics.tab_family_sub": "Consent required",
        "genetics.tab_research": "Research Studio",
        "genetics.tab_research_sub": "Bounded exploration",
        "genetics.overview_title": "Overview",
        "genetics.overview_help": "A bounded view of one consumer-genotype dataset.",
        "genetics.overview_dataset": "Dataset record",
        "genetics.overview_coverage": "Selective coverage",
        "genetics.overview_findings": "Findings summary",
        "genetics.overview_evidence": "Evidence distribution",
        "genetics.import_title": "Import genetic data",
        "genetics.import_help": (
            "Local consumer genotype TXT only. The original bytes are immutable and never sent to "
            "a provider."
        ),
        "genetics.import_file_label": "Genotype file",
        "genetics.import_build_label": "Genome build",
        "genetics.build_unknown": "Unknown",
        "genetics.import_confirmation": (
            "I understand genetic data is uniquely identifying and can reveal information about "
            "relatives."
        ),
        "genetics.import_submit": "Import locally",
        "genetics.import_success": (
            "Imported locally. The source is immutable; indexed coverage is ready to review."
        ),
        "genetics.import_coverage_note": (
            "Consumer genotype coverage is incomplete. Missing loci are not treated as reference "
            "genotype."
        ),
        "genetics.upload_limit": "Maximum upload size: 32,000,000 bytes.",
        "genetics.import_error_too_large": "File too large. Maximum size is 32,000,000 bytes.",
        "genetics.import_error_confirmation": "Confirmation is required before import.",
        "genetics.import_error_build": "Unsupported genome build.",
        "genetics.import_error_invalid": "The file could not be read as a valid genotype file.",
        "genetics.import_error_generic": "The local import failed.",
        "genetics.variants_title": "Variants",
        "genetics.variants_help": "Only loci selected by installed evidence packs are shown.",
        "genetics.variants_empty": (
            "No selectively indexed observations match this view. An absent chip locus is "
            "untested, not a reference genotype."
        ),
        "genetics.coverage_present": "Present",
        "genetics.coverage_no_call": "No-call",
        "genetics.coverage_not_present": "Not present",
        "genetics.coverage_note_title": "Not present does not mean reference.",
        "genetics.coverage_note_body": (
            "A consumer chip may not test a target locus. Untested, no-call, and confirmed "
            "reference are different states."
        ),
        "genetics.pgx_title": "Pharmacogenomics",
        "genetics.pgx_help": "Medication relevance, not prescribing advice.",
        "genetics.pgx_boundary": "Association only",
        "genetics.pgx_boundary_note": (
            "This surface does not recommend a medication, dose, start, or stop."
        ),
        "genetics.pgx_empty": "No pharmacogenomic intersections are available for this Person.",
        "genetics.health_title": "Health associations",
        "genetics.health_help": (
            "Reviewed genetics findings remain separate from diagnosed conditions."
        ),
        "genetics.health_empty": "No reviewed health associations are available.",
        "genetics.traits_title": "Traits & systems",
        "genetics.traits_help": "Possible pathway relevance with evidence always in view.",
        "genetics.traits_empty": "No trait observations are available.",
        "genetics.evidence_title": "Evidence",
        "genetics.evidence_help": "Source quality, version, review state, and limitations.",
        "genetics.evidence_empty": "No evidence entries are available.",
        "genetics.family_title": "Family comparison",
        "genetics.family_help": (
            "Deterministic coverage comparison with separate permission for each Person."
        ),
        "genetics.family_warning": (
            "Genetics access is never inherited from family access. Both profiles must grant "
            "genetics comparison. Hidden profiles and datasets are never revealed."
        ),
        "genetics.family_limit": (
            "These statistics describe compatible indexed observations only. They do not prove "
            "biological or legal kinship."
        ),
        "genetics.family_person_b_label": "Second profile",
        "genetics.family_compare_submit": "Compare coverage",
        "genetics.family_no_access": (
            "The selected profile does not have genetics comparison access."
        ),
        "genetics.research_title": "Research Studio",
        "genetics.research_help": (
            "Build a bounded question from selected evidence and health records."
        ),
        "genetics.research_evidence_mode": "Evidence",
        "genetics.research_evidence_mode_help": "Use supplied evidence only",
        "genetics.research_explore_mode": "Explore",
        "genetics.research_explore_mode_help": "Label hypotheses and background",
        "genetics.research_mode_label": "Research mode",
        "genetics.research_mode_help": "Choose how far synthesis may go.",
        "genetics.research_question_label": "Question",
        "genetics.research_disclosure_confirm": (
            "I confirm this genetics-specific external disclosure for the selected context."
        ),
        "genetics.research_run": "Run bounded research",
        "genetics.research_readiness_confirm": "Confirm external disclosure to continue.",
        "genetics.research_readiness_confirmed": "Disclosure confirmed for this run only.",
        "genetics.research_running": "Running bounded research…",
        "genetics.status_pending": "Pending",
        "genetics.status_reviewed": "Reviewed",
        "genetics.status_dismissed": "Dismissed",
        "genetics.status_unsupported": "Unsupported",
        "genetics.status_conflicting": "Conflicting",
        "genetics.loading": "Loading genetics…",
        "genetics.load_error": "Genetics could not be loaded.",
        "genetics.observation_label": "Indexed observation",
        "genetics.category_pgx": "Pharmacogenomics",
        "genetics.category_health": "Health association",
        "genetics.category_trait": "Trait",
        "genetics.provenance_label": "Provenance",
        "genetics.raw_source_note": "Selected observation only. Raw source rows are not rendered.",
        "genetics.filter_search": "Search rsID or gene",
        "genetics.filter_coverage": "Coverage",
        "genetics.filter_category": "Category",
        "genetics.filter_all": "All",
        "genetics.family_person_a_label": "First profile",
        "genetics.family_compared_with": "compared with",
        "genetics.family_choose_person_b": "Choose a second profile to compare.",
        "genetics.context_selected": "Selected context",
        "genetics.research_provider_label": "External provider",
        "genetics.research_provider_name": "Deterministic local research",
        "genetics.research_context_none": (
            "Select reviewed findings or medication records to build the context."
        ),
        "genetics.research_context_summary": (
            "Disclosed context: {findings} reviewed findings and {records} medication records. No "
            "raw genotype or unrestricted vault content is included."
        ),
        "genetics.research_output_title": "Research output",
        "genetics.research_supported": "Supported synthesis",
        "genetics.research_plausible": "Plausible hypothesis",
        "genetics.research_what_may_be_happening": "What may be happening",
        "genetics.research_evidence_supporting": "Evidence supporting it",
        "genetics.research_evidence_against": "Devil's advocate: evidence against it",
        "genetics.research_alternative_explanations": "Alternative explanations",
        "genetics.research_missing_information": "Missing information",
        "genetics.research_questions": "Questions worth investigating",
        "genetics.research_claims": "Bounded claims",
        "genetics.research_session": "Research session",
        "genetics.context_count": "{count} selected items",
        "genetics.findings_reviewed": "Reviewed findings",
        "genetics.evidence_entries": "Evidence entries",
        "genetics.loci_indexed": "Indexed loci",
        "genetics.dataset_imported": "Imported",
        "genetics.dataset_parser": "Parser",
        "genetics.dataset_raw": "Raw source",
        "genetics.dataset_immutable": "Immutable, local only",
        "genetics.variants_count": "{count} shown",
        "genetics.compare_shared": "Shared covered loci",
        "genetics.compare_matching": "Matching observations",
        "genetics.compare_differing": "Differing observations",
        "genetics.compare_incompatible": (
            "Comparison unavailable: incompatible build or unresolved orientation."
        ),
        "genetics.family_no_access_help": "Grant genetics comparison for both profiles to compare.",
        "page.vault_title": "Private Person vault · OpenCare",
        "page.family_title": "Family and access · OpenCare",
        "nav.overview": "Overview",
        "nav.health": "Health",
        "nav.workspace": "Workspace",
        "nav.documents": "Documents",
        "nav.activity": "Activity",
        "nav.chat": "Chat",
        "chat.title": "OpenCare chat",
        "chat.kicker": "Source-backed conversation",
        "chat.subtitle": "Answers stay within the authorized Person scope.",
        "chat.empty_title": "Ask about your recorded vault",
        "chat.empty_intro": (
            "OpenCare summarizes source-backed records, identifies unknown information, "
            "and prepares clinician discussion questions."
        ),
        "chat.empty_safety": (
            "Answers are policy-checked and validated before display. Validation cannot "
            "guarantee medical correctness."
        ),
        "chat.new_conversation": "New conversation",
        "chat.active_vault": "Active vault",
        "chat.family_context": "Person context",
        "chat.suggested_questions": "Suggested safe questions",
        "chat.prompt_doctor": "Prepare questions for my doctor",
        "chat.prompt_changed": "What changed since the latest recorded visit?",
        "chat.prompt_sources": "Which information is source-backed?",
        "chat.evidence_sources": "Evidence & sources",
        "chat.boundary_read_only": "Read-only",
        "chat.boundary_notice": "Not medical advice",
        "chat.ask_label": "Ask a question about this vault",
        "chat.placeholder": "Ask about recorded information and sources…",
        "chat.send": "Send",
        "chat.status_prepare": "Preparing an exact disclosure…",
        "chat.status_check": "Checking vault context and sources…",
        "chat.answer_fallback": "No answer was returned.",
        "chat.sources": "Sources",
        "chat.unknown_information": "Unknown information",
        "chat.questions_clinician": "Questions for a clinician",
        "chat.boundaries": "Boundaries",
        "chat.disclosure_preview": "Disclosure preview",
        "chat.local_provider": "Runs on this OpenCare installation",
        "chat.external_provider": "Selected authorized data may leave this OpenCare installation",
        "chat.evidence_items": "Evidence items",
        "chat.retention": "Retention",
        "chat.fields": "Fields",
        "chat.allow_disclosure": "Allow this exact disclosure?",
        "chat.provider": "Provider",
        "chat.model": "Model",
        "chat.external": "External provider",
        "chat.local_only": "Local only",
        "chat.none": "none",
        "chat.not_specified": "not specified",
        "chat.retention_provider_policy": (
            "provider policy; OpenCare does not retain provider payloads"
        ),
        "chat.consent_declined": "No provider call was made because disclosure was not approved.",
        "chat.consent_not_granted": "Consent was not granted.",
        "chat.no_provider_output": "No provider output was displayed.",
        "chat.receipt": "Receipt",
        "chat.status": "status",
        "chat.recorded": "recorded",
        "chat.error": "OpenCare could not process this request.",
        "chat.provider_local_status": "Local deterministic demo",
        "chat.provider_self_hosted_status": "Self-hosted model configured by operator",
        "chat.provider_external_status": "External model configured by operator",
        "nav.genetics": "Genetics",
        "nav.vault": "Vault",
        "nav.family": "Family & access",
        "nav.family_access": "Family & access",
        "nav.settings": "Settings",
        "shell.primary_navigation": "Primary navigation",
        "shell.open_navigation": "Open navigation",
        "shell.close_navigation": "Close navigation",
        "shell.skip_to_content": "Skip to content",
        "shell.account": "Account",
        "shell.person": "Person",
        "shell.no_person_selected": "No person selected",
        "shell.language": "Language",
        "locale.en": "English",
        "locale.ru": "Russian",
        "locale.current": "Current language",
        "person.label": "Person",
        "person.selected": "Selected person",
        "person.no_selection": "No person selected",
        "person.switch": "Switch person",
        "person.choose": "Choose a person",
        "account.label": "Account",
        "account.menu": "Account menu",
        "account.profile": "Profile",
        "account.signed_in_as": "Signed in as",
        "status.loading": "Loading…",
        "status.ready": "Ready",
        "status.error": "Something went wrong",
        "status.unavailable": "Unavailable",
        "status.saving": "Saving…",
        "status.saved": "Saved",
        "action.save": "Save",
        "action.cancel": "Cancel",
        "action.close": "Close",
        "action.retry": "Try again",
        "action.sign_out": "Sign out",
        "action.select": "Select",
        "action.switch": "Switch",
        "action.open_menu": "Open menu",
        "action.close_menu": "Close menu",
        "button.save": "Save",
        "button.cancel": "Cancel",
        "button.close": "Close",
        "button.retry": "Try again",
        "button.sign_out": "Sign out",
        "form.username": "Username",
        "form.password": "Password",
        "form.display_name": "Display name",
        "form.confirm_password": "Confirm password",
        "form.invitation_code": "Invitation code",
        "form.existing_person_ids": "Existing Person IDs (optional, comma-separated)",
        "auth.private_workspace": "Private workspace",
        "auth.welcome_back": "Welcome back",
        "auth.sign_in": "Sign in",
        "auth.sign_in_intro": (
            "Use your local username and password to access your private workspace."
        ),
        "auth.create_account": "Create account",
        "auth.have_invitation": "Have an invitation?",
        "auth.use_invitation": "Use invitation",
        "auth.installation_setup": "Installation setup",
        "auth.open_workspace": "Open Workspace",
        "auth.local_account": "Private account",
        "auth.create_account_title": "Create your account",
        "auth.registration_intro": (
            "Create a private workspace for your own records. An invitation is not required "
            "when public registration is enabled."
        ),
        "auth.registration_status_checking": "Checking account registration…",
        "auth.registration_disabled": (
            "New account registration is not enabled for this installation. Sign in or use "
            "an invitation from someone sharing access with you."
        ),
        "auth.registration_uninitialized": (
            "This installation must be set up by its operator before accounts can be created."
        ),
        "auth.create_account_submit": "Create account",
        "auth.one_time_setup": "One-time installation setup",
        "auth.bootstrap_title": "Create the installation administrator",
        "auth.bootstrap_intro": "This page is used once by the server owner.",
        "auth.administrator_account": "Administrator account",
        "auth.bootstrap_admin_copy": (
            "The administrator manages this installation. Person access is granted only "
            "through the explicit existing-Person controls below."
        ),
        "auth.advanced": "Advanced",
        "auth.existing_person_ids_help": (
            "Use this only when the installation owner must claim existing People. Full "
            "owner confirmation is required."
        ),
        "auth.owner_confirmation": (
            "I understand that every listed Person will grant this Actor full owner access."
        ),
        "auth.create_administrator": "Create administrator",
        "auth.setup_complete": "Installation setup is complete. Sign in to continue.",
        "auth.sign_in_instead": "Sign in instead",
        "auth.private_invitation": "Family sharing invitation",
        "auth.invitation_title": "Use an invitation",
        "auth.invitation_intro": (
            "An invitation grants access shared by another person or family member. It is "
            "not required for normal sign-in or self-registration."
        ),
        "auth.review_invitation": "Review invitation",
        "auth.invitation_details": "Invitation details",
        "auth.owner_invitation": "Owner invitation — full control",
        "auth.caregiver_invitation": "Caregiver invitation",
        "auth.permissions": "Permissions",
        "auth.owner_warning": (
            "This invitation grants full owner control, including access management and export."
        ),
        "auth.create_account_accept": "Create an account and accept",
        "auth.accept_signed_in": "Accept with the signed-in account",
        "auth.accept_invitation": "Accept invitation",
        "auth.invitation_accepted": "Invitation accepted.",
        "status.signing_in": "Signing in…",
        "status.account_request_failed": "The account request could not be completed.",
        "status.bootstrap_status_unavailable": "Setup status is unavailable.",
        "status.creating_administrator": "Creating the first administrator…",
        "status.administrator_created": "Installation administrator created.",
        "status.registration_status_unavailable": "Account registration status is unavailable.",
        "status.password_mismatch": "Passwords do not match.",
        "status.creating_account": "Creating account…",
        "status.account_could_not_created": "Account could not be created.",
        "status.checking_invitation": "Checking invitation…",
        "status.invitation_cannot_be_used": "This invitation cannot be used.",
        "status.review_access": "Review the access before accepting.",
        "page.login_title": "Sign in · OpenCare",
        "page.register_title": "Create account · OpenCare",
        "page.bootstrap_title": "Installation setup · OpenCare",
        "page.invitation_title": "Use invitation · OpenCare",
        "auth.other_options": "Other account options",
        "form.bootstrap_secret": "Operator bootstrap secret",
        "auth.bootstrap_secret_production": (
            "Required in production. It is checked once and never stored."
        ),
        "auth.checking_setup": "Checking setup availability…",
        "family.heading": "Family & Access",
        "family.intro": (
            "Share access to one Person at a time, review who can see their "
            "information, and manage your local account."
        ),
        "family.boundary": (
            "Family relationships describe context. Only an active Person assignment grants access."
        ),
        "family.active_person": "Access for Person",
        "family.access_applies_to": "Access shown here applies to {person}.",
        "family.no_active_person": "No Person selected",
        "family.choose_person": "Choose an authorized Person to review family access.",
        "family.no_accessible_people": "No accessible People",
        "family.people_heading": "People with access",
        "family.people_help": (
            "Active access assignments for the selected Person. Genetics access is separate."
        ),
        "family.no_additional_access": (
            "No one else currently has active Family Access for this Person."
        ),
        "family.read_only_heading": "Family sharing is read-only",
        "family.read_only_help": (
            "You can access this Person, but your account cannot view or change family sharing."
        ),
        "family.you": "You",
        "family.shared_account": "Account with access",
        "family.role_owner": "Owner",
        "family.role_caregiver": "Caregiver",
        "family.status_active": "Active",
        "family.status_revoked": "Revoked",
        "family.status_disabled": "Disabled",
        "family.invite_heading": "Invite someone",
        "family.share_access_to": "Share access to {person}",
        "family.invite_help": (
            "Create a one-time invitation code and send it directly to the "
            "person you trust. It is not ordinary login or public registration."
        ),
        "family.invitation_empty": "No invitation code is displayed.",
        "family.invitation_issued": "Copy this one-time code now",
        "family.invitation_warning": (
            "The code will not be shown again after you clear it, switch Person, "
            "or leave this page."
        ),
        "family.owner_confirmation": (
            "I understand that owner access grants all current Family Access "
            "scopes for this Person. Genetics access remains separate."
        ),
        "family.account_heading": "Your account",
        "family.account_help": "Account security actions are separate from Person sharing.",
        "provider.heading": "AI provider",
        "provider.name_label": "Provider",
        "provider.name_deterministic": "Deterministic test provider",
        "provider.name_ollama": "Ollama",
        "provider.name_openai": "OpenAI",
        "provider.name_openrouter": "OpenRouter",
        "provider.model_label": "Configured model",
        "provider.model_not_applicable": "Not applicable",
        "provider.execution_label": "Execution type",
        "provider.execution_deterministic": "Local deterministic",
        "provider.execution_local": "Local model",
        "provider.execution_external": "External provider",
        "provider.configuration_label": "Configuration",
        "provider.operator_managed": "Managed by the OpenCare installation operator",
        "provider.unavailable": "Unavailable",
        "provider.external_boundary": (
            "Selected authorized data may leave this OpenCare installation when you "
            "approve a disclosure."
        ),
        "provider.local_ollama_boundary": (
            "Model execution occurs on the configured local installation endpoint."
        ),
        "family.current_password": "Current password",
        "family.new_password": "New password",
        "family.password_help": "Changing your password signs out every session.",
        "family.change_password": "Change password",
        "family.advanced_heading": "Advanced",
        "family.advanced_help": (
            "Technical identifiers, exact scopes, access history, installation "
            "accounts, and Family relationship records."
        ),
        "family.family_context_help": (
            "Family records describe relationships only. They never grant Person access."
        ),
        "family.scope_group.health": "Health data",
        "family.scope_group.sources_documents": "Sources & documents",
        "family.scope_group.family": "Family administration",
        "family.scope_group.export": "Exports",
        "family.scope_group.chat": "OpenCare chat",
        "family.switch_person": "Switch Person",
        "family.clear_person": "Clear Person",
        "family.loading_access": "Loading Family Access…",
        "family.access_ready": "Family Access loaded.",
        "family.action_not_allowed": "Your account is not permitted to perform that action.",
        "family.record_not_available": "That item is not available.",
        "family.conflict": "That action conflicts with the current access state.",
        "family.role_label": "Role",
        "family.access_selection": "Access selection",
        "family.caregiver_permissions": "Caregiver permissions",
        "family.revise_access": "Revise access",
        "family.save_permissions": "Save permissions",
        "family.revoke_access": "Revoke access",
        "family.revoke_confirm": (
            "Revoke access for {name}? The final active owner cannot be removed."
        ),
        "family.access_granted": "Access granted.",
        "family.access_revised": "Access updated.",
        "family.access_revoked": "Access revoked.",
        "family.expires_at": "Expires at",
        "family.create_invitation": "Create invitation",
        "family.invitation_created": "Invitation created. Copy the code now.",
        "family.clear_code": "Clear code",
        "family.code_cleared": "Invitation code cleared from this page.",
        "family.password_change_failed": (
            "The password could not be changed. Check the current password and try again."
        ),
        "family.password_changed": "Password changed. Sign in again.",
        "family.signed_out": "Signed out.",
        "family.technical_context": "Technical context",
        "family.actor_id": "Actor ID",
        "family.person_id": "Person ID",
        "family.assignment_id": "Assignment ID",
        "family.consent_id": "Consent event ID",
        "family.audit_id": "Audit event ID",
        "family.family_id": "Family ID",
        "family.membership_id": "Membership ID",
        "family.relationship_id": "Relationship ID",
        "family.created_at": "Created at",
        "family.raw_scopes": "Exact scopes",
        "family.consent_history": "Consent history",
        "family.access_audit": "Access audit",
        "family.no_consent_history": "No visible consent history.",
        "family.no_access_audit": "No visible access audit events.",
        "family.installation_accounts": "Installation accounts",
        "family.installation_accounts_help": (
            "Visible only to an installation administrator. Administrator status "
            "does not grant Person access."
        ),
        "family.deactivate_actor": "Deactivate account",
        "family.deactivate_confirm": "Deactivate {name} and revoke all of their Person access?",
        "family.direct_grant_heading": "Grant access to an existing Actor",
        "family.recipient_actor_id": "Recipient Actor ID",
        "family.grant_access": "Grant access",
        "family.families_heading": "Family records & relationships",
        "family.family_name": "Family name",
        "family.create_family": "Create Family",
        "family.select_family": "Select Family",
        "family.no_family_selected": "No Family selected.",
        "family.no_family_members": "No visible Family members.",
        "family.add_family_member": "Add Person to Family",
        "family.related_person": "Related Person",
        "family.relationship": "Relationship",
        "family.add_relationship": "Add relationship",
        "family.end_membership": "End membership",
        "family.end_relationship": "End relationship",
        "family.relationship_parent": "Parent",
        "family.relationship_child": "Child",
        "family.relationship_spouse": "Spouse",
        "family.relationship_partner": "Partner",
        "family.relationship_sibling": "Sibling",
        "family.relationship_guardian": "Guardian",
        "family.relationship_dependent": "Dependent",
        "family.relationship_other": "Other",
        "family.scope.person_read": "View Person profile",
        "family.scope.person_update": "Edit Person profile",
        "family.scope.source_read": "View sources",
        "family.scope.source_write": "Add sources",
        "family.scope.document_read": "View documents",
        "family.scope.document_write": "Manage documents",
        "family.scope.candidate_read": "View review items",
        "family.scope.candidate_review": "Review candidate records",
        "family.scope.medication_read": "View medications",
        "family.scope.medication_write": "Manage medications",
        "family.scope.condition_read": "View recorded conditions",
        "family.scope.condition_write": "Manage recorded conditions",
        "family.scope.lab_read": "View lab records",
        "family.scope.lab_write": "Manage lab records",
        "family.scope.timeline_read": "View timeline",
        "family.scope.visit_read": "View visits",
        "family.scope.visit_write": "Manage visits",
        "family.scope.brief_read": "View Visit Briefs",
        "family.scope.brief_write": "Manage Visit Briefs",
        "family.scope.brief_export": "Export Visit Briefs",
        "family.scope.vault_export": "Export Person data",
        "family.scope.relationship_read": "View family relationships",
        "family.scope.relationship_manage": "Manage family relationships",
        "family.scope.access_read": "View Family Access",
        "family.scope.access_manage": "Manage Family Access",
        "family.scope.chat_use": "Use OpenCare chat",
    },
    "ru": {
        "app.name": "OpenCare",
        "page.workspace_title": "Рабочая область здоровья OpenCare",
        "workspace.heading": "Добро пожаловать в рабочую область",
        "workspace.intro": "Посмотрите записи выбранного пользователя и выберите следующий шаг.",
        "workspace.safety": (
            "OpenCare организует записи с указанием источника. Система не интерпретирует "
            "результаты и не даёт медицинских рекомендаций."
        ),
        "workspace.active_person": "Вы просматриваете пользователя",
        "workspace.no_active_person": "Пользователь не выбран",
        "workspace.loading_person": "Загружаем выбранного пользователя…",
        "workspace.choose_person": "Выберите доступного пользователя, чтобы начать.",
        "workspace.switcher_label": "Сменить пользователя",
        "workspace.selector_loading": "Загружаем доступных пользователей…",
        "workspace.selector_placeholder": "Выберите пользователя",
        "workspace.selector_empty": "Нет доступных пользователей",
        "workspace.no_accessible_persons": "Профиль здоровья пока недоступен.",
        "workspace.no_accessible_persons_help": (
            "Создайте профиль через существующий сценарий владельца или попросите кого-то "
            "предоставить вам доступ."
        ),
        "workspace.overview_title": "Обзор",
        "workspace.overview_summary": (
            "Фактическая сводка записей, доступных этому аккаунту для выбранного пользователя."
        ),
        "workspace.metric_records": "Подтверждённые записи",
        "workspace.metric_documents": "Документы",
        "workspace.metric_medications": "Текущие лекарства",
        "workspace.metric_activity": "Недавняя активность",
        "workspace.metric_pending": "Ожидают проверки",
        "workspace.no_health_data": "Для этого пользователя пока нет данных о здоровье.",
        "workspace.no_health_data_help": (
            "Начните с исходного документа или записи на проверку. Система ничего не "
            "додумывает и не заполняет автоматически."
        ),
        "workspace.quick_actions": "Следующие шаги",
        "workspace.add_document": "Добавить документ",
        "workspace.open_records": "Открыть записи",
        "workspace.open_genetics": "Открыть генетику",
        "workspace.ask_opencare": "Спросить OpenCare",
        "workspace.family_access": "Управление семейным доступом",
        "workspace.recent_activity": "Недавняя активность",
        "workspace.no_recent_activity": "Для этого пользователя нет доступной недавней активности.",
        "workspace.viewing": "Просмотр",
        "workspace.date_of_birth": "Дата рождения",
        "workspace.clear_selection": "Очистить выбор",
        "workspace.create_profile": "Создать ещё один профиль",
        "workspace.create_profile_help": (
            "Создание профиля предоставляет вошедшему аккаунту полный доступ владельца. "
            "Другие пользователи не получают доступ автоматически."
        ),
        "workspace.edit_profile": "Изменить выбранный профиль",
        "workspace.edit_profile_title": "Изменить профиль",
        "workspace.save_profile": "Сохранить профиль",
        "workspace.no_profile_selected": "Профиль не выбран",
        "workspace.profile_choice_help": (
            "Выберите доступного пользователя, чтобы загрузить его рабочую область."
        ),
        "workspace.loading_workspace": "Загружаем рабочую область…",
        "workspace.workspace_loaded": "Рабочая область загружена.",
        "workspace.selection_cleared": "Выбор пользователя очищен.",
        "workspace.person_not_available": "Этот пользователь недоступен.",
        "workspace.select_before_load": "Выберите пользователя перед загрузкой рабочей области.",
        "workspace.select_profile": "Выбрать пользователя",
        "workspace.section_person": "Пользователь",
        "workspace.section_review": "Проверка",
        "workspace.section_records": "Записи",
        "workspace.section_timeline": "Активность",
        "workspace.section_visits": "Визиты и краткая информация",
        "workspace.section_export": "Экспорт",
        "workspace.records_empty": "Подтверждённых записей нет.",
        "workspace.activity_empty": "Недавней активности нет.",
        "workspace.pending_empty": "Нет записей, ожидающих проверки.",
        "workspace.person_count": "доступных пользователей",
        "workspace.records_count": "записей",
        "workspace.documents_count": "документов",
        "workspace.activity_count": "событий",
        "workspace.pending_count": "ожидают проверки",
        "status.session_expired": "Срок действия сеанса истёк. Войдите снова.",
        "status.action_unavailable": "Это действие больше недоступно.",
        "status.record_changed": "Запись изменилась. Обновите страницу.",
        "status.check_values": "Проверьте введённые значения и повторите попытку.",
        "status.integrity_failure": "Целостность: сохранённые материалы не прошли проверку.",
        "status.storage_unavailable": (
            "Локальное хранилище Product Core недоступно. Повторите попытку позже."
        ),
        "status.request_failed": "Не удалось выполнить запрос. Повторите попытку.",
        "workspace.latest_record": "Последняя подтверждённая запись",
        "workspace.selected_visit": "Выбранный визит",
        "workspace.review_summary": (
            "Исходные записи на проверку, доступные для этого пользователя."
        ),
        "workspace.documents_summary": "Исходные документы, доступные для этого пользователя.",
        "workspace.records_summary": "Текущие подтверждённые записи и их история.",
        "workspace.timeline_summary": "События жизненного цикла записей этого пользователя.",
        "workspace.visits_summary": (
            "Составляйте вопросы и готовьте сводку визита с указанием источников."
        ),
        "workspace.export_summary": (
            "Скачать копию этого пользователя и доступных исходных материалов."
        ),
        "workspace.medications": "Лекарства",
        "workspace.conditions": "Записанные состояния",
        "workspace.labs": "Анализы",
        "workspace.visits": "Визиты",
        "page.genetics_title": "Рабочая область генетики OpenCare",
        "genetics.kicker": "Рабочая область генетики",
        "genetics.heading": "Доказательства прежде интерпретации",
        "genetics.intro": (
            "Просматривайте выборочно индексированные наблюдения, их доказательства и "
            "исследовательские вопросы без раскрытия сырого генома."
        ),
        "genetics.person_label": "Текущий генетический профиль",
        "genetics.person_selector_label": "Сменить пользователя",
        "genetics.no_person": "Выберите пользователя для просмотра генетики.",
        "genetics.no_access": "Доступ к генетике для этого пользователя недоступен.",
        "genetics.empty_title": "Генетических данных пока нет.",
        "genetics.empty_help": (
            "Импортируйте поддерживаемый файл генотипа потребителя, чтобы начать."
        ),
        "genetics.live_badge": "Активно",
        "genetics.import_cta": "Импортировать генетические данные",
        "genetics.privacy_note": (
            "Исходный файл остаётся локальным для этой установки OpenCare. В функциях генетики "
            "участвуют только выбранные/индексированные наблюдения. Сырой геном исключён из "
            "поддерживаемого контекста моделей/провайдеров."
        ),
        "genetics.sections_label": "Разделы генетики",
        "genetics.tab_overview": "Обзор",
        "genetics.tab_overview_sub": "Источник и покрытие",
        "genetics.tab_variants": "Варианты",
        "genetics.tab_variants_sub": "Индексированные наблюдения",
        "genetics.tab_pgx": "Фармакогенетика",
        "genetics.tab_pgx_sub": "Релевантность медикаментов",
        "genetics.tab_health": "Ассоциации со здоровьем",
        "genetics.tab_health_sub": "Рассмотренные находки",
        "genetics.tab_traits": "Признаки и системы",
        "genetics.tab_traits_sub": "Исследовательские пути",
        "genetics.tab_evidence": "Доказательства",
        "genetics.tab_evidence_sub": "Источники и ограничения",
        "genetics.tab_family": "Семейное сравнение",
        "genetics.tab_family_sub": "Требуется согласие",
        "genetics.tab_research": "Исследовательская студия",
        "genetics.tab_research_sub": "Ограниченное исследование",
        "genetics.overview_title": "Обзор",
        "genetics.overview_help": (
            "Ограниченный просмотр одного набора данных генотипа потребителя."
        ),
        "genetics.overview_dataset": "Запись набора данных",
        "genetics.overview_coverage": "Выборочное покрытие",
        "genetics.overview_findings": "Сводка находок",
        "genetics.overview_evidence": "Распределение доказательств",
        "genetics.import_title": "Импорт генетических данных",
        "genetics.import_help": (
            "Только локальный TXT генотипа потребителя. Исходные байты неизменяемы и никогда не "
            "отправляются провайдеру."
        ),
        "genetics.import_file_label": "Файл генотипа",
        "genetics.import_build_label": "Сборка генома",
        "genetics.build_unknown": "Неизвестно",
        "genetics.import_confirmation": (
            "Я понимаю, что генетические данные уникально идентифицируют и могут раскрыть "
            "информацию о родственниках."
        ),
        "genetics.import_submit": "Импортировать локально",
        "genetics.import_success": (
            "Импортировано локально. Источник неизменяем; индексированное покрытие готово к "
            "просмотру."
        ),
        "genetics.import_coverage_note": (
            "Покрытие генотипа потребителя неполное. Отсутствующие локусы не считаются "
            "референсным генотипом."
        ),
        "genetics.upload_limit": "Максимальный размер загрузки: 32 000 000 байт.",
        "genetics.import_error_too_large": (
            "Файл слишком большой. Максимальный размер — 32 000 000 байт."
        ),
        "genetics.import_error_confirmation": "Перед импортом требуется подтверждение.",
        "genetics.import_error_build": "Неподдерживаемая сборка генома.",
        "genetics.import_error_invalid": "Файл не удалось прочитать как корректный файл генотипа.",
        "genetics.import_error_generic": "Локальный импорт не удался.",
        "genetics.variants_title": "Варианты",
        "genetics.variants_help": (
            "Показаны только локусы, выбранные установленными наборами доказательств."
        ),
        "genetics.variants_empty": (
            "Нет индексированных наблюдений, соответствующих этому представлению. Отсутствующий "
            "локус чипа — не тестированный, а не референсный генотип."
        ),
        "genetics.coverage_present": "Присутствует",
        "genetics.coverage_no_call": "Нет вызова",
        "genetics.coverage_not_present": "Отсутствует",
        "genetics.coverage_note_title": "«Отсутствует» не означает референс.",
        "genetics.coverage_note_body": (
            "Чип потребителя может не тестировать целевой локус. Нетестированный, без вызова и "
            "подтверждённый референс — разные состояния."
        ),
        "genetics.pgx_title": "Фармакогенетика",
        "genetics.pgx_help": "Релевантность для медикаментов, а не рекомендации по назначению.",
        "genetics.pgx_boundary": "Только ассоциация",
        "genetics.pgx_boundary_note": (
            "Этот раздел не рекомендует медикамент, дозу, начало или прекращение приёма."
        ),
        "genetics.pgx_empty": "Фармакогенетические пересечения для этого пользователя недоступны.",
        "genetics.health_title": "Ассоциации со здоровьем",
        "genetics.health_help": (
            "Рассмотренные генетические находки остаются отдельными от диагностированных состояний."
        ),
        "genetics.health_empty": "Рассмотренные ассоциации со здоровьем недоступны.",
        "genetics.traits_title": "Признаки и системы",
        "genetics.traits_help": "Возможная релевантность путей с доказательствами всегда на виду.",
        "genetics.traits_empty": "Наблюдения признаков недоступны.",
        "genetics.evidence_title": "Доказательства",
        "genetics.evidence_help": (
            "Качество источника, версия, состояние рассмотрения и ограничения."
        ),
        "genetics.evidence_empty": "Записи доказательств недоступны.",
        "genetics.family_title": "Семейное сравнение",
        "genetics.family_help": (
            "Детерминированное сравнение покрытия с отдельным разрешением для каждого пользователя."
        ),
        "genetics.family_warning": (
            "Доступ к генетике никогда не наследуется от семейного доступа. Оба профиля должны "
            "предоставить разрешение на сравнение. Скрытые профили и наборы данных никогда не "
            "раскрываются."
        ),
        "genetics.family_limit": (
            "Эти статистики описывают только совместимые индексированные наблюдения. Они не "
            "доказывают биологическое или юридическое родство."
        ),
        "genetics.family_person_b_label": "Второй профиль",
        "genetics.family_compare_submit": "Сравнить покрытие",
        "genetics.family_no_access": (
            "Выбранный профиль не имеет доступа к генетическому сравнению."
        ),
        "genetics.research_title": "Исследовательская студия",
        "genetics.research_help": (
            "Сформулируйте ограниченный вопрос из выбранных доказательств и записей здоровья."
        ),
        "genetics.research_evidence_mode": "Доказательства",
        "genetics.research_evidence_mode_help": (
            "Использовать только предоставленные доказательства"
        ),
        "genetics.research_explore_mode": "Исследование",
        "genetics.research_explore_mode_help": "Помечать гипотезы и фоновые знания",
        "genetics.research_mode_label": "Режим исследования",
        "genetics.research_mode_help": "Выберите, насколько далеко может зайти синтез.",
        "genetics.research_question_label": "Вопрос",
        "genetics.research_disclosure_confirm": (
            "Я подтверждаю это генетическое внешнее раскрытие для выбранного контекста."
        ),
        "genetics.research_run": "Запустить ограниченное исследование",
        "genetics.research_readiness_confirm": "Подтвердите внешнее раскрытие, чтобы продолжить.",
        "genetics.research_readiness_confirmed": "Раскрытие подтверждено только для этого запуска.",
        "genetics.research_running": "Выполняется ограниченное исследование…",
        "genetics.status_pending": "Ожидает",
        "genetics.status_reviewed": "Рассмотрено",
        "genetics.status_dismissed": "Отклонено",
        "genetics.status_unsupported": "Не подтверждено",
        "genetics.status_conflicting": "Противоречиво",
        "genetics.loading": "Загрузка генетики…",
        "genetics.load_error": "Не удалось загрузить генетику.",
        "genetics.observation_label": "Индексированное наблюдение",
        "genetics.category_pgx": "Фармакогенетика",
        "genetics.category_health": "Ассоциация со здоровьем",
        "genetics.category_trait": "Признак",
        "genetics.provenance_label": "Провенанс",
        "genetics.raw_source_note": (
            "Только выбранное наблюдение. Строки сырого источника не отображаются."
        ),
        "genetics.filter_search": "Поиск по rsID или гену",
        "genetics.filter_coverage": "Покрытие",
        "genetics.filter_category": "Категория",
        "genetics.filter_all": "Все",
        "genetics.family_person_a_label": "Первый профиль",
        "genetics.family_compared_with": "сравнивается с",
        "genetics.family_choose_person_b": "Выберите второй профиль для сравнения.",
        "genetics.context_selected": "Выбранный контекст",
        "genetics.research_provider_label": "Внешний провайдер",
        "genetics.research_provider_name": "Детерминированное локальное исследование",
        "genetics.research_context_none": (
            "Выберите рассмотренные находки или записи о медикаментах, чтобы сформировать контекст."
        ),
        "genetics.research_context_summary": (
            "Раскрываемый контекст: находок — {findings}, записей о медикаментах — {records}. "
            "Сырой геном и неограниченное содержимое хранилища не включаются."
        ),
        "genetics.research_output_title": "Результат исследования",
        "genetics.research_supported": "Подтверждённый синтез",
        "genetics.research_plausible": "Правдоподобная гипотеза",
        "genetics.research_what_may_be_happening": "Что может происходить",
        "genetics.research_evidence_supporting": "Доказательства в поддержку",
        "genetics.research_evidence_against": "Адвокат дьявола: доказательства против",
        "genetics.research_alternative_explanations": "Альтернативные объяснения",
        "genetics.research_missing_information": "Недостающая информация",
        "genetics.research_questions": "Вопросы, которые стоит изучить",
        "genetics.research_claims": "Ограниченные утверждения",
        "genetics.research_session": "Сессия исследования",
        "genetics.context_count": "Выбрано элементов: {count}",
        "genetics.findings_reviewed": "Рассмотренные находки",
        "genetics.evidence_entries": "Записи доказательств",
        "genetics.loci_indexed": "Индексированные локусы",
        "genetics.dataset_imported": "Импортировано",
        "genetics.dataset_parser": "Парсер",
        "genetics.dataset_raw": "Сырой источник",
        "genetics.dataset_immutable": "Неизменяемый, только локально",
        "genetics.variants_count": "Показано: {count}",
        "genetics.compare_shared": "Общие покрытые локусы",
        "genetics.compare_matching": "Совпадающие наблюдения",
        "genetics.compare_differing": "Различающиеся наблюдения",
        "genetics.compare_incompatible": (
            "Сравнение недоступно: несовместимая сборка или нерешённая ориентация."
        ),
        "genetics.family_no_access_help": (
            "Предоставьте сравнение генетики обоим профилям, чтобы сравнить."
        ),
        "page.vault_title": "Личное хранилище пользователя · OpenCare",
        "page.family_title": "Семья и доступ · OpenCare",
        "optional": "необязательно",
        "workspace.recorded_in_opencare": "Записано в OpenCare",
        "nav.overview": "Обзор",
        "nav.health": "Здоровье",
        "nav.workspace": "Рабочая область",
        "nav.documents": "Документы",
        "nav.activity": "Активность",
        "nav.chat": "Чат",
        "chat.title": "Чат OpenCare",
        "chat.kicker": "Разговор на основе источников",
        "chat.subtitle": "Ответы остаются в пределах разрешённого пользователя.",
        "chat.empty_title": "Спросите о записанных данных",
        "chat.empty_intro": (
            "OpenCare обобщает записи из источников, показывает неизвестные сведения и "
            "готовит вопросы для обсуждения с врачом."
        ),
        "chat.empty_safety": (
            "Ответы проверяются политиками и проходят валидацию до показа. Валидация не "
            "гарантирует медицинскую корректность."
        ),
        "chat.new_conversation": "Новый разговор",
        "chat.active_vault": "Активное хранилище",
        "chat.family_context": "Контекст пользователя",
        "chat.suggested_questions": "Безопасные вопросы",
        "chat.prompt_doctor": "Подготовить вопросы для врача",
        "chat.prompt_changed": "Что изменилось после последнего визита?",
        "chat.prompt_sources": "Какие сведения подтверждены источниками?",
        "chat.evidence_sources": "Источники и подтверждения",
        "chat.boundary_read_only": "Только чтение",
        "chat.boundary_notice": "Не медицинская рекомендация",
        "chat.ask_label": "Задайте вопрос об этом хранилище",
        "chat.placeholder": "Спросите о записанных данных и источниках…",
        "chat.send": "Отправить",
        "chat.status_prepare": "Подготавливаем точное раскрытие…",
        "chat.status_check": "Проверяем контекст хранилища и источники…",
        "chat.answer_fallback": "Ответ не получен.",
        "chat.sources": "Источники",
        "chat.unknown_information": "Неизвестные сведения",
        "chat.questions_clinician": "Вопросы для врача",
        "chat.boundaries": "Ограничения",
        "chat.disclosure_preview": "Предпросмотр раскрытия",
        "chat.local_provider": "Работает в этой установке OpenCare",
        "chat.external_provider": (
            "Выбранные разрешённые данные могут покинуть эту установку OpenCare"
        ),
        "chat.evidence_items": "Элементы подтверждений",
        "chat.retention": "Хранение",
        "chat.fields": "Поля",
        "chat.allow_disclosure": "Разрешить это точное раскрытие?",
        "chat.provider": "Провайдер",
        "chat.model": "Модель",
        "chat.external": "Внешний провайдер",
        "chat.local_only": "Только локально",
        "chat.none": "нет",
        "chat.not_specified": "не указано",
        "chat.retention_provider_policy": (
            "политика провайдера; OpenCare не хранит данные запроса провайдеру"
        ),
        "chat.consent_declined": "Вызов провайдера не выполнен: раскрытие не было одобрено.",
        "chat.consent_not_granted": "Согласие не предоставлено.",
        "chat.no_provider_output": "Ответ провайдера не показан.",
        "chat.receipt": "Квитанция",
        "chat.status": "статус",
        "chat.recorded": "зафиксирован",
        "chat.error": "OpenCare не смог обработать этот запрос.",
        "chat.provider_local_status": "Локальная детерминированная демонстрация",
        "chat.provider_self_hosted_status": (
            "Самостоятельно размещённая модель, настроенная оператором"
        ),
        "chat.provider_external_status": "Внешняя модель, настроенная оператором",
        "nav.genetics": "Генетика",
        "nav.vault": "Хранилище",
        "nav.family": "Семья и доступ",
        "nav.family_access": "Семья и доступ",
        "nav.settings": "Настройки",
        "shell.primary_navigation": "Основная навигация",
        "shell.open_navigation": "Открыть навигацию",
        "shell.close_navigation": "Закрыть навигацию",
        "shell.skip_to_content": "Перейти к содержимому",
        "shell.account": "Аккаунт",
        "shell.person": "Пользователь",
        "shell.no_person_selected": "Пользователь не выбран",
        "shell.language": "Язык",
        "locale.en": "English",
        "locale.ru": "Русский",
        "locale.current": "Текущий язык",
        "person.label": "Пользователь",
        "person.selected": "Выбранный пользователь",
        "person.no_selection": "Пользователь не выбран",
        "person.switch": "Сменить пользователя",
        "person.choose": "Выберите пользователя",
        "account.label": "Аккаунт",
        "account.menu": "Меню аккаунта",
        "account.profile": "Профиль",
        "account.signed_in_as": "Выполнен вход как",
        "status.loading": "Загрузка…",
        "status.ready": "Готово",
        "status.error": "Что-то пошло не так",
        "status.unavailable": "Недоступно",
        "status.saving": "Сохранение…",
        "status.saved": "Сохранено",
        "action.save": "Сохранить",
        "action.cancel": "Отмена",
        "action.close": "Закрыть",
        "action.retry": "Повторить",
        "action.sign_out": "Выйти",
        "action.select": "Выбрать",
        "action.switch": "Сменить",
        "action.open_menu": "Открыть меню",
        "action.close_menu": "Закрыть меню",
        "button.save": "Сохранить",
        "button.cancel": "Отмена",
        "button.close": "Закрыть",
        "button.retry": "Повторить",
        "button.sign_out": "Выйти",
        "form.username": "Имя пользователя",
        "form.password": "Пароль",
        "form.display_name": "Отображаемое имя",
        "form.confirm_password": "Подтвердите пароль",
        "form.invitation_code": "Код приглашения",
        "form.existing_person_ids": "Идентификаторы пользователей (необязательно, через запятую)",
        "auth.private_workspace": "Личное рабочее пространство",
        "auth.welcome_back": "С возвращением",
        "auth.sign_in": "Войти",
        "auth.sign_in_intro": (
            "Введите локальные имя пользователя и пароль для доступа к личному рабочему "
            "пространству."
        ),
        "auth.create_account": "Создать аккаунт",
        "auth.have_invitation": "Есть приглашение?",
        "auth.use_invitation": "Использовать приглашение",
        "auth.installation_setup": "Настройка установки",
        "auth.open_workspace": "Открыть рабочую область",
        "auth.local_account": "Личный аккаунт",
        "auth.create_account_title": "Создайте аккаунт",
        "auth.registration_intro": (
            "Создайте личную рабочую область для собственных записей. При включённой "
            "открытой регистрации приглашение не требуется."
        ),
        "auth.registration_status_checking": "Проверяем доступность регистрации…",
        "auth.registration_disabled": (
            "Регистрация новых аккаунтов отключена для этой установки. Войдите или "
            "используйте приглашение от пользователя, который делится доступом."
        ),
        "auth.registration_uninitialized": "Сначала оператор должен настроить эту установку.",
        "auth.create_account_submit": "Создать аккаунт",
        "auth.one_time_setup": "Однократная настройка установки",
        "auth.bootstrap_title": "Создайте администратора установки",
        "auth.bootstrap_intro": "Эта страница используется один раз владельцем сервера.",
        "auth.administrator_account": "Аккаунт администратора",
        "auth.bootstrap_admin_copy": (
            "Администратор управляет этой установкой. Доступ к пользователям выдаётся только "
            "через явные настройки существующих пользователей ниже."
        ),
        "auth.advanced": "Расширенные настройки",
        "auth.existing_person_ids_help": (
            "Используйте это, только если владельцу установки нужно заявить права на "
            "существующих пользователей. Требуется полное подтверждение прав владельца."
        ),
        "auth.owner_confirmation": (
            "Я понимаю, что каждый указанный пользователь предоставит этому аккаунту полный "
            "доступ владельца."
        ),
        "auth.create_administrator": "Создать администратора",
        "auth.setup_complete": "Установка уже настроена. Войдите, чтобы продолжить.",
        "auth.sign_in_instead": "Войти вместо этого",
        "auth.private_invitation": "Приглашение для семейного доступа",
        "auth.invitation_title": "Использовать приглашение",
        "auth.invitation_intro": (
            "Приглашение предоставляет доступ, которым делится другой пользователь или член "
            "семьи. Для обычного входа или самостоятельной регистрации оно не требуется."
        ),
        "auth.review_invitation": "Проверить приглашение",
        "auth.invitation_details": "Сведения о приглашении",
        "auth.owner_invitation": "Приглашение владельца — полный доступ",
        "auth.caregiver_invitation": "Приглашение помощника",
        "auth.permissions": "Разрешения",
        "auth.owner_warning": (
            "Это приглашение предоставляет полный доступ владельца, включая управление "
            "доступом и экспорт."
        ),
        "auth.create_account_accept": "Создать аккаунт и принять",
        "auth.accept_signed_in": "Принять вошедшим аккаунтом",
        "auth.accept_invitation": "Принять приглашение",
        "auth.invitation_accepted": "Приглашение принято.",
        "status.signing_in": "Выполняем вход…",
        "status.account_request_failed": "Не удалось выполнить запрос аккаунта.",
        "status.bootstrap_status_unavailable": "Статус настройки недоступен.",
        "status.creating_administrator": "Создаём первого администратора…",
        "status.administrator_created": "Администратор установки создан.",
        "status.registration_status_unavailable": "Статус регистрации аккаунта недоступен.",
        "status.password_mismatch": "Пароли не совпадают.",
        "status.creating_account": "Создаём аккаунт…",
        "status.account_could_not_created": "Не удалось создать аккаунт.",
        "status.checking_invitation": "Проверяем приглашение…",
        "status.invitation_cannot_be_used": "Это приглашение нельзя использовать.",
        "status.review_access": "Проверьте предоставляемый доступ перед принятием.",
        "page.login_title": "Вход · OpenCare",
        "page.register_title": "Создание аккаунта · OpenCare",
        "page.bootstrap_title": "Настройка установки · OpenCare",
        "page.invitation_title": "Использование приглашения · OpenCare",
        "auth.other_options": "Другие варианты",
        "form.bootstrap_secret": "Секрет оператора для настройки",
        "auth.bootstrap_secret_production": (
            "Требуется в production. Проверяется один раз и не сохраняется."
        ),
        "auth.checking_setup": "Проверяем доступность настройки…",
        "family.heading": "Семья и доступ",
        "family.intro": (
            "Предоставляйте доступ к одному пользователю за раз, проверяйте, кто "
            "видит его данные, и управляйте локальным аккаунтом."
        ),
        "family.boundary": (
            "Семейные связи описывают контекст. Доступ предоставляет только "
            "активное назначение к пользователю."
        ),
        "family.active_person": "Доступ к пользователю",
        "family.access_applies_to": "Показанный здесь доступ относится к пользователю {person}.",
        "family.no_active_person": "Пользователь не выбран",
        "family.choose_person": (
            "Выберите доступного пользователя, чтобы проверить семейный доступ."
        ),
        "family.no_accessible_people": "Нет доступных пользователей",
        "family.people_heading": "Пользователи с доступом",
        "family.people_help": (
            "Активные назначения доступа для выбранного пользователя. Доступ к "
            "генетике предоставляется отдельно."
        ),
        "family.no_additional_access": (
            "Сейчас ни у кого другого нет активного семейного доступа к этому пользователю."
        ),
        "family.read_only_heading": "Семейный доступ доступен только для чтения",
        "family.read_only_help": (
            "У вас есть доступ к этому пользователю, но ваш аккаунт не может "
            "просматривать или изменять семейный доступ."
        ),
        "family.you": "Вы",
        "family.shared_account": "Аккаунт с доступом",
        "family.role_owner": "Владелец",
        "family.role_caregiver": "Помощник",
        "family.status_active": "Активен",
        "family.status_revoked": "Отозван",
        "family.status_disabled": "Отключён",
        "family.invite_heading": "Пригласить пользователя",
        "family.share_access_to": "Предоставить доступ к пользователю {person}",
        "family.invite_help": (
            "Создайте одноразовый код приглашения и передайте его напрямую "
            "доверенному человеку. Это не обычный вход и не открытая регистрация."
        ),
        "family.invitation_empty": "Код приглашения не отображается.",
        "family.invitation_issued": "Скопируйте одноразовый код сейчас",
        "family.invitation_warning": (
            "Код больше не будет показан после очистки, смены пользователя или выхода со страницы."
        ),
        "family.owner_confirmation": (
            "Я понимаю, что доступ владельца предоставляет все текущие права "
            "семейного доступа для этого пользователя. Доступ к генетике "
            "остаётся отдельным."
        ),
        "family.account_heading": "Ваш аккаунт",
        "family.account_help": (
            "Действия безопасности аккаунта отделены от предоставления доступа к пользователю."
        ),
        "provider.heading": "Провайдер ИИ",
        "provider.name_label": "Провайдер",
        "provider.name_deterministic": "Детерминированный тестовый провайдер",
        "provider.name_ollama": "Ollama",
        "provider.name_openai": "OpenAI",
        "provider.name_openrouter": "OpenRouter",
        "provider.model_label": "Настроенная модель",
        "provider.model_not_applicable": "Не применяется",
        "provider.execution_label": "Тип выполнения",
        "provider.execution_deterministic": "Локальная детерминированная обработка",
        "provider.execution_local": "Локальная модель",
        "provider.execution_external": "Внешний провайдер",
        "provider.configuration_label": "Конфигурация",
        "provider.operator_managed": "Настроено оператором установки OpenCare",
        "provider.unavailable": "Недоступно",
        "provider.external_boundary": (
            "Выбранные разрешённые данные могут покинуть эту установку OpenCare "
            "после одобрения раскрытия."
        ),
        "provider.local_ollama_boundary": (
            "Выполнение модели происходит на настроенной локальной конечной точке установки."
        ),
        "family.current_password": "Текущий пароль",
        "family.new_password": "Новый пароль",
        "family.password_help": "Смена пароля завершит все сеансы.",
        "family.change_password": "Сменить пароль",
        "family.advanced_heading": "Расширенные настройки",
        "family.advanced_help": (
            "Технические идентификаторы, точные права, история доступа, аккаунты "
            "установки и записи семейных связей."
        ),
        "family.family_context_help": (
            "Семейные записи описывают только связи. Они никогда не предоставляют "
            "доступ к пользователю."
        ),
        "family.scope_group.health": "Данные о здоровье",
        "family.scope_group.sources_documents": "Источники и документы",
        "family.scope_group.family": "Управление семейным доступом",
        "family.scope_group.export": "Экспорт",
        "family.scope_group.chat": "Чат OpenCare",
        "family.switch_person": "Сменить пользователя",
        "family.clear_person": "Очистить выбор пользователя",
        "family.loading_access": "Загружаем семейный доступ…",
        "family.access_ready": "Семейный доступ загружен.",
        "family.action_not_allowed": "Вашему аккаунту недоступно это действие.",
        "family.record_not_available": "Этот объект недоступен.",
        "family.conflict": "Это действие противоречит текущему состоянию доступа.",
        "family.role_label": "Роль",
        "family.access_selection": "Настройки доступа",
        "family.caregiver_permissions": "Права помощника",
        "family.revise_access": "Изменить доступ",
        "family.save_permissions": "Сохранить права",
        "family.revoke_access": "Отозвать доступ",
        "family.revoke_confirm": (
            "Отозвать доступ у {name}? Последнего активного владельца удалить нельзя."
        ),
        "family.access_granted": "Доступ предоставлен.",
        "family.access_revised": "Доступ обновлён.",
        "family.access_revoked": "Доступ отозван.",
        "family.expires_at": "Срок действия",
        "family.create_invitation": "Создать приглашение",
        "family.invitation_created": "Приглашение создано. Скопируйте код сейчас.",
        "family.clear_code": "Очистить код",
        "family.code_cleared": "Код приглашения удалён с этой страницы.",
        "family.password_change_failed": (
            "Не удалось сменить пароль. Проверьте текущий пароль и повторите попытку."
        ),
        "family.password_changed": "Пароль изменён. Войдите снова.",
        "family.signed_out": "Выполнен выход.",
        "family.technical_context": "Технические сведения",
        "family.actor_id": "Идентификатор аккаунта",
        "family.person_id": "Идентификатор пользователя",
        "family.assignment_id": "Идентификатор назначения",
        "family.consent_id": "Идентификатор события согласия",
        "family.audit_id": "Идентификатор события аудита",
        "family.family_id": "Идентификатор семьи",
        "family.membership_id": "Идентификатор участия",
        "family.relationship_id": "Идентификатор связи",
        "family.created_at": "Создано",
        "family.raw_scopes": "Точные права",
        "family.consent_history": "История согласий",
        "family.access_audit": "Аудит доступа",
        "family.no_consent_history": "Нет доступной истории согласий.",
        "family.no_access_audit": "Нет доступных событий аудита доступа.",
        "family.installation_accounts": "Аккаунты установки",
        "family.installation_accounts_help": (
            "Видно только администратору установки. Статус администратора не "
            "предоставляет доступ к пользователю."
        ),
        "family.deactivate_actor": "Деактивировать аккаунт",
        "family.deactivate_confirm": (
            "Деактивировать аккаунт {name} и отозвать весь его доступ к пользователям?"
        ),
        "family.direct_grant_heading": "Предоставить доступ существующему аккаунту",
        "family.recipient_actor_id": "Идентификатор аккаунта получателя",
        "family.grant_access": "Предоставить доступ",
        "family.families_heading": "Семейные записи и связи",
        "family.family_name": "Название семьи",
        "family.create_family": "Создать семью",
        "family.select_family": "Выберите семью",
        "family.no_family_selected": "Семья не выбрана.",
        "family.no_family_members": "Нет доступных участников семьи.",
        "family.add_family_member": "Добавить пользователя в семью",
        "family.related_person": "Связанный пользователь",
        "family.relationship": "Родственная связь",
        "family.add_relationship": "Добавить связь",
        "family.end_membership": "Завершить участие",
        "family.end_relationship": "Завершить связь",
        "family.relationship_parent": "Родитель",
        "family.relationship_child": "Ребёнок",
        "family.relationship_spouse": "Супруг или супруга",
        "family.relationship_partner": "Партнёр",
        "family.relationship_sibling": "Брат или сестра",
        "family.relationship_guardian": "Опекун",
        "family.relationship_dependent": "Иждивенец",
        "family.relationship_other": "Другое",
        "family.scope.person_read": "Просмотр профиля пользователя",
        "family.scope.person_update": "Изменение профиля пользователя",
        "family.scope.source_read": "Просмотр источников",
        "family.scope.source_write": "Добавление источников",
        "family.scope.document_read": "Просмотр документов",
        "family.scope.document_write": "Управление документами",
        "family.scope.candidate_read": "Просмотр записей на проверку",
        "family.scope.candidate_review": "Проверка предложенных записей",
        "family.scope.medication_read": "Просмотр лекарств",
        "family.scope.medication_write": "Управление лекарствами",
        "family.scope.condition_read": "Просмотр записанных состояний",
        "family.scope.condition_write": "Управление записанными состояниями",
        "family.scope.lab_read": "Просмотр анализов",
        "family.scope.lab_write": "Управление анализами",
        "family.scope.timeline_read": "Просмотр хронологии",
        "family.scope.visit_read": "Просмотр визитов",
        "family.scope.visit_write": "Управление визитами",
        "family.scope.brief_read": "Просмотр сводок визитов",
        "family.scope.brief_write": "Управление сводками визитов",
        "family.scope.brief_export": "Экспорт сводок визитов",
        "family.scope.vault_export": "Экспорт данных пользователя",
        "family.scope.relationship_read": "Просмотр семейных связей",
        "family.scope.relationship_manage": "Управление семейными связями",
        "family.scope.access_read": "Просмотр семейного доступа",
        "family.scope.access_manage": "Управление семейным доступом",
        "family.scope.chat_use": "Использование чата OpenCare",
    },
}

# Workspace controls added after the initial product-shell catalog. Keeping
# these entries in the same centralized catalog preserves the existing locale
# fallback behavior while covering dynamically rendered workspace chrome.
TRANSLATIONS["ru"].update(
    {
        "workspace.fact_type": "Тип факта",
        "workspace.all_fact_types": "Все типы фактов",
        "workspace.status": "Статус",
        "workspace.all_statuses": "Все статусы",
        "workspace.waiting_review": "Ожидает проверки",
        "workspace.confirmed": "Подтверждено",
        "workspace.corrected": "Исправлено",
        "workspace.rejected": "Отклонено",
        "workspace.unsupported": "Не подтверждено источником",
        "workspace.search_loaded_candidates": "Поиск среди загруженных записей",
        "workspace.no_documents": "Для этого профиля пока нет документов.",
        "workspace.document_upload_label": "Добавить PDF или текстовый документ",
        "workspace.document_upload_help": (
            "Файлы хранятся как исходные материалы. Загрузка ограничена; содержимое не "
            "отображается как форматированный HTML."
        ),
        "workspace.upload_document": "Загрузить документ",
        "workspace.page_text": "Текст страницы",
        "workspace.page": "Страница",
        "workspace.choose_page": "Выберите страницу для просмотра.",
        "workspace.select_span": "Выберите текст, чтобы прикрепить точный фрагмент источника.",
        "workspace.add_typed_candidate": "Добавить запись на проверку",
        "workspace.typed_candidate_help": (
            "Введите лекарство, состояние или анализ точно так, как указано в источнике. "
            "Автоматического извлечения нет."
        ),
        "workspace.name_or_test_name": "Название / название анализа",
        "workspace.details_as_reported": "Подробности как указано",
        "workspace.add_for_review": "Добавить на проверку",
        "workspace.add_medication": "Добавить лекарство",
        "workspace.add_condition": "Добавить записанное состояние",
        "workspace.add_lab": "Добавить анализ",
        "workspace.review_pending_help": "Новые записи проходят проверку до подтверждения.",
        "workspace.condition_safety": (
            "Формулировка состояния хранится как текст источника и не является диагнозом "
            "OpenCare."
        ),
        "workspace.lab_safety": "Значения показаны как указано, без интерпретации.",
        "workspace.medication_name": "Отображаемое название лекарства",
        "workspace.schedule_optional": "Расписание (необязательно, как указано)",
        "workspace.note_optional": "Примечание (необязательно)",
        "workspace.recorded_condition_name": "Название записанного состояния",
        "workspace.status_optional_source": "Статус (необязательно, текст источника)",
        "workspace.onset_optional": "Дата начала (как указано, необязательно)",
        "workspace.test_name": "Название анализа",
        "workspace.result_as_reported": "Результат (как указано)",
        "workspace.unit_as_reported": "Единица (как указано, необязательно)",
        "workspace.reference_range_as_reported": (
            "Референсный диапазон (как указано, необязательно)"
        ),
        "workspace.observed_date_as_reported": "Дата наблюдения (как указано, необязательно)",
        "workspace.flag_as_reported": "Флаг (как указано, необязательно)",
        "workspace.historical_superseded": "Исторические и заменённые записи",
        "workspace.no_current_records": "Текущих подтверждённых записей нет.",
        "workspace.no_historical_records": "Исторических и заменённых записей нет.",
        "workspace.no_pending_fact": "Записей на проверку нет.",
        "workspace.no_confirmed_fact": "Подтверждённых записей нет.",
        "workspace.no_historical": "Исторических записей нет.",
        "workspace.recorded_status": "Записанный статус",
        "workspace.recorded_onset": "Записанное начало",
        "workspace.result_reported": "Результат как указано",
        "workspace.unit_reported": "Единица как указано",
        "workspace.reference_range_reported": "Референсный диапазон как указано",
        "workspace.observed": "Наблюдалось",
        "workspace.flag_reported": "Флаг как указано",
        "workspace.confirmed_at": "Подтверждено",
        "workspace.superseded": "Заменено",
        "workspace.recorded_in_opencare": "Записано в OpenCare",
        "workspace.record_lifecycle_help": (
            "События жизненного цикла записей. Запланированные визиты показаны отдельно "
            "ниже."
        ),
        "workspace.all": "Все",
        "workspace.create_visit": "Создать визит",
        "workspace.visit_title": "Название визита",
        "workspace.specialist_optional": "Специалист (необязательно)",
        "workspace.scheduled_visit_optional": "Запланированный визит (необязательно)",
        "workspace.no_visits": "Для этого профиля визиты ещё не создавались.",
        "workspace.select_visit": "Выбрать визит",
        "workspace.selected_visit_button": "Выбранный визит",
        "workspace.questions_for": "Вопросы для",
        "workspace.no_questions": "Для этого визита вопросы ещё не добавлены.",
        "workspace.question": "Вопрос",
        "workspace.move_question_up": "Переместить вопрос вверх",
        "workspace.move_question_down": "Переместить вопрос вниз",
        "workspace.remove": "Удалить",
        "workspace.edit": "Изменить",
        "workspace.visit_brief": "Краткая информация о визите",
        "workspace.brief_help": "Доказательства и вопросы сохраняются в неизменяемых ревизиях.",
        "workspace.initialize_brief": "Создать краткую информацию о визите",
        "workspace.select_visit_brief": "Выберите визит для подготовки краткой информации.",
        "workspace.initialize_persistent_brief": (
            "Создать постоянную краткую информацию для этого визита."
        ),
        "workspace.no_persistent_brief": (
            "Для этого визита постоянная краткая информация недоступна."
        ),
        "workspace.select_confirmed_evidence": "Выберите подтверждённые материалы",
        "workspace.validate_evidence": "Проверить материалы",
        "workspace.generate_revision": "Создать ревизию",
        "workspace.preparation_notes": "Подготовительные заметки",
        "workspace.save_notes_revision": "Сохранить заметки как ревизию",
        "workspace.unsaved_warning": (
            "Несохранённые заметки будут удалены при смене пользователя или визита."
        ),
        "workspace.revision_history": "История ревизий",
        "workspace.no_revisions": "Ревизий ещё нет.",
        "workspace.view_revision": "Просмотреть ревизию",
        "workspace.restore_revision": "Восстановить ревизию",
        "workspace.revision_unavailable": "Ревизия недоступна",
        "workspace.current": "Текущая",
        "workspace.evidence_changed": "Материалы изменились после этой ревизии",
        "workspace.selected_record_changed": "Выбранная запись или источник изменились",
        "workspace.no_eligible_evidence": "Подходящих подтверждённых материалов нет.",
        "workspace.evidence_record": "Запись-материал",
        "workspace.revision": "Ревизия",
        "workspace.copy_markdown": "Копировать Markdown",
        "workspace.download_markdown": "Скачать Markdown",
        "workspace.export_vault": "Экспорт хранилища",
        "workspace.export_warning_title": "Экспортировать чувствительные данные хранилища?",
        "workspace.export_warning_help": (
            "Загрузка может содержать сведения о здоровье и исходные материалы. Храните её "
            "только там, где контролируете доступ."
        ),
        "workspace.download_vault": "Скачать хранилище",
        "workspace.cancel": "Отмена",
        "workspace.reset": "Сбросить",
        "workspace.save_visit": "Сохранить визит",
        "workspace.add_question": "Добавить вопрос",
        "workspace.edit_question": "Изменить вопрос",
        "workspace.question_text": "Текст вопроса",
        "workspace.save_question": "Сохранить вопрос",
        "workspace.correct_record": "Создать исправление",
        "workspace.reject_candidate": "Отклонить запись",
        "workspace.mark_unsupported": "Отметить как не подтверждённую источником",
        "workspace.confirm_record": "Подтвердить запись",
        "workspace.reject_confirm": "Отклонить эту запись?",
        "workspace.candidate_marked_unsupported": (
            "Запись отмечена как не подтверждённая источником."
        ),
        "workspace.record_confirmed": "Запись подтверждена.",
        "workspace.candidate_rejected": "Запись отклонена.",
        "workspace.fact": "Факт",
        "workspace.created": "Создано",
        "workspace.onset_date": "Дата начала (как указано)",
        "workspace.observed_date": "Дата наблюдения (как указано)",
        "workspace.revision_viewing": "Просмотр ревизии",
        "workspace.revision_origin": "источник",
        "workspace.no_eligible_confirmed_evidence": "Подходящих подтверждённых материалов нет.",
        "workspace.no_entries_match": "Записей, соответствующих этому виду, нет.",
        "workspace.medication_confirmed": "Запись о лекарстве подтверждена",
        "workspace.condition_confirmed": "Запись о состоянии подтверждена",
        "workspace.lab_confirmed": "Запись об анализе подтверждена",
        "workspace.record_superseded": "Запись заменена после проверки",
        "workspace.no_specialist": "Специалист не указан",
        "workspace.no_scheduled_date": "Дата не назначена",
        "workspace.medication_pending": "Лекарство добавлено и ожидает проверки.",
        "workspace.whole_source": "Весь источник",
        "workspace.manual_medication_name": "Название лекарства в ручной записи",
        "workspace.manual_condition_name": "Название записанного состояния в ручной записи",
        "workspace.manual_lab_name": "Название анализа в ручной записи",
        "workspace.manual_field": "Поле ручной записи",
        "workspace.document_page": "Страница документа",
        "workspace.codepoints": "кодовые позиции",
        "workspace.source_text_characters": "Символы исходного текста",
        "workspace.specific_source_location": "Точное место, указанное в источнике",
        "workspace.origin_generated": "Создано",
        "workspace.origin_user_edit": "Изменено пользователем",
        "workspace.origin_restored": "Восстановлено",
        "workspace.source_provenance": "Источник и происхождение",
        "workspace.source_id": "ID источника",
        "workspace.registered": "Зарегистрировано",
        "workspace.size": "Размер",
        "workspace.media_type": "Тип медиа",
        "workspace.integrity_verified": "Целостность подтверждена",
        "workspace.integrity_not_verified": "Целостность не подтверждена",
        "workspace.source_metadata_unavailable": "Метаданные источника недоступны.",
        "workspace.source_location": "Расположение источника",
        "workspace.correction_lineage": "Связь исправления",
        "workspace.manual_entry": "Ручная запись",
        "workspace.source": "Источник",
        "workspace.document": "Документ",
        "workspace.text": "Текст",
        "workspace.bytes": "байт",
        "workspace.correction_superseded": (
            "Связь исправления: запись заменена новой подтверждённой записью."
        ),
        "workspace.document_uploaded": "Документ загружен.",
        "workspace.typed_candidate_pending": "Запись добавлена и ожидает проверки.",
        "workspace.condition_pending": "Состояние добавлено и ожидает проверки.",
        "workspace.lab_pending": "Анализ добавлен и ожидает проверки.",
        "workspace.question_order_updated": "Порядок вопросов обновлён.",
        "workspace.question_removed": "Вопрос удалён.",
        "workspace.save_correction": "Сохранить исправление",
        "workspace.correct_medication": "Исправить запись о лекарстве",
        "workspace.correct_condition": "Исправить запись о состоянии",
        "workspace.correct_lab": "Исправить запись об анализе",
        "workspace.correction_pending": "Исправление добавлено на проверку.",
        "workspace.profile_updated": "Профиль обновлён.",
        "workspace.visit_created": "Визит создан.",
        "workspace.visit_updated": "Визит обновлён.",
        "workspace.question_added": "Вопрос добавлен.",
        "workspace.question_updated": "Вопрос обновлён.",
        "workspace.brief_initialized": "Краткая информация о визите создана.",
        "workspace.evidence_valid": "Выбранные материалы корректны.",
        "workspace.brief_revision_generated": "Ревизия краткой информации создана.",
        "workspace.notes_saved": "Подготовительные заметки сохранены как новая ревизия.",
        "workspace.brief_restored": "Текущая ревизия восстановлена.",
        "workspace.markdown_copied": "Markdown скопирован.",
        "workspace.copy_unavailable": "Копирование недоступно в этом браузере.",
        "workspace.markdown_downloaded": "Загрузка Markdown подготовлена.",
        "workspace.vault_downloaded": "Загрузка хранилища подготовлена.",
    }
)


def _normalize_locale(locale: str | None) -> Locale:
    if locale == "ru":
        return "ru"
    return DEFAULT_LOCALE


def resolve_locale(request: Request) -> Locale:
    """Resolve an exact supported locale from the dedicated locale cookie."""
    return _normalize_locale(request.cookies.get(LOCALE_COOKIE_NAME))


def get_translations(locale: str | None) -> dict[str, str]:
    """Return an isolated catalog with missing entries filled from English."""
    requested = TRANSLATIONS[_normalize_locale(locale)]
    return {**TRANSLATIONS[DEFAULT_LOCALE], **requested}


def translate(locale: str | None, key: str) -> str:
    """Translate a UI key, falling back to English and then the unchanged key."""
    requested = TRANSLATIONS[_normalize_locale(locale)]
    if key in requested:
        return requested[key]
    return TRANSLATIONS[DEFAULT_LOCALE].get(key, key)
