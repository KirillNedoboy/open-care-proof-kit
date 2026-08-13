from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from app.product_core.models import ensure_utc_datetime, isoformat_utc


@dataclass(frozen=True)
class Migration:
    version: int
    statements: tuple[str, ...]


PRODUCT_MIGRATIONS = (
    Migration(
        version=1,
        statements=(
            """
            CREATE TABLE sources (
                id TEXT PRIMARY KEY,
                person_id TEXT NOT NULL CHECK (length(trim(person_id)) > 0),
                source_type TEXT NOT NULL CHECK (source_type IN ('manual_entry', 'plain_text')),
                relative_path TEXT NOT NULL CHECK (length(trim(relative_path)) > 0),
                content_hash TEXT NOT NULL CHECK (length(content_hash) = 64),
                size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
                media_type TEXT NOT NULL CHECK (length(trim(media_type)) > 0),
                created_at TEXT NOT NULL,
                provenance_json TEXT NOT NULL,
                UNIQUE (person_id, source_type, content_hash)
            )
            """,
            """
            CREATE TABLE candidate_facts (
                id TEXT PRIMARY KEY,
                person_id TEXT NOT NULL CHECK (length(trim(person_id)) > 0),
                source_id TEXT NOT NULL REFERENCES sources(id),
                fact_type TEXT NOT NULL CHECK (fact_type = 'medication'),
                status TEXT NOT NULL CHECK (
                    status IN ('pending', 'confirmed', 'corrected', 'rejected')
                ),
                display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
                normalized_name TEXT NOT NULL CHECK (length(trim(normalized_name)) > 0),
                schedule_text TEXT,
                note TEXT,
                created_at TEXT NOT NULL,
                reviewed_at TEXT,
                predecessor_candidate_id TEXT REFERENCES candidate_facts(id),
                CHECK (
                    predecessor_candidate_id IS NULL OR predecessor_candidate_id <> id
                ),
                CHECK (
                    (status = 'pending' AND reviewed_at IS NULL)
                    OR (status <> 'pending' AND reviewed_at IS NOT NULL)
                )
            )
            """,
            """
            CREATE TABLE canonical_medication_records (
                id TEXT PRIMARY KEY,
                person_id TEXT NOT NULL CHECK (length(trim(person_id)) > 0),
                candidate_id TEXT NOT NULL UNIQUE REFERENCES candidate_facts(id),
                source_id TEXT NOT NULL REFERENCES sources(id),
                display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
                normalized_name TEXT NOT NULL CHECK (length(trim(normalized_name)) > 0),
                schedule_text TEXT,
                note TEXT,
                confirmed_at TEXT NOT NULL,
                is_active INTEGER NOT NULL CHECK (is_active IN (0, 1))
            )
            """,
            """
            CREATE TABLE timeline_events (
                id TEXT PRIMARY KEY,
                person_id TEXT NOT NULL CHECK (length(trim(person_id)) > 0),
                canonical_record_id TEXT NOT NULL REFERENCES canonical_medication_records(id),
                source_id TEXT NOT NULL REFERENCES sources(id),
                event_type TEXT NOT NULL CHECK (length(trim(event_type)) > 0),
                event_at TEXT NOT NULL,
                title TEXT NOT NULL CHECK (length(trim(title)) > 0),
                UNIQUE (canonical_record_id, event_type)
            )
            """,
            "CREATE INDEX candidate_facts_person_status_idx ON candidate_facts(person_id, status)",
            (
                "CREATE INDEX canonical_medication_records_person_active_idx "
                "ON canonical_medication_records(person_id, is_active)"
            ),
            (
                "CREATE INDEX timeline_events_person_event_at_idx "
                "ON timeline_events(person_id, event_at, id)"
            ),
        ),
    ),
    Migration(
        version=2,
        statements=(
            "PRAGMA defer_foreign_keys=ON",
            """
            CREATE TABLE people (
                person_id TEXT PRIMARY KEY CHECK (length(trim(person_id)) > 0),
                display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
                date_of_birth TEXT CHECK (
                    date_of_birth IS NULL OR (
                        length(date_of_birth) = 10 AND date(date_of_birth) = date_of_birth
                    )
                ),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_active INTEGER NOT NULL CHECK (is_active IN (0, 1))
            )
            """,
            """
            INSERT INTO people (
                person_id, display_name, date_of_birth, created_at, updated_at, is_active
            )
            SELECT person_id, 'Imported profile', NULL, ?, ?, 1
            FROM (
                SELECT person_id FROM sources
                UNION SELECT person_id FROM candidate_facts
                UNION SELECT person_id FROM canonical_medication_records
                UNION SELECT person_id FROM timeline_events
            )
            """,
            """
            CREATE TABLE sources_phase_1d (
                id TEXT PRIMARY KEY,
                person_id TEXT NOT NULL REFERENCES people(person_id),
                source_type TEXT NOT NULL CHECK (source_type IN ('manual_entry', 'plain_text')),
                relative_path TEXT NOT NULL CHECK (length(trim(relative_path)) > 0),
                content_hash TEXT NOT NULL CHECK (length(content_hash) = 64),
                size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
                media_type TEXT NOT NULL CHECK (length(trim(media_type)) > 0),
                created_at TEXT NOT NULL,
                provenance_json TEXT NOT NULL,
                UNIQUE (person_id, source_type, content_hash)
            )
            """,
            """
            CREATE TABLE candidate_facts_phase_1d (
                id TEXT PRIMARY KEY,
                person_id TEXT NOT NULL REFERENCES people(person_id),
                source_id TEXT NOT NULL REFERENCES sources_phase_1d(id),
                fact_type TEXT NOT NULL CHECK (fact_type = 'medication'),
                status TEXT NOT NULL CHECK (
                    status IN ('pending', 'confirmed', 'corrected', 'rejected')
                ),
                display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
                normalized_name TEXT NOT NULL CHECK (length(trim(normalized_name)) > 0),
                schedule_text TEXT,
                note TEXT,
                created_at TEXT NOT NULL,
                reviewed_at TEXT,
                predecessor_candidate_id TEXT REFERENCES candidate_facts_phase_1d(id),
                CHECK (predecessor_candidate_id IS NULL OR predecessor_candidate_id <> id),
                CHECK (
                    (status = 'pending' AND reviewed_at IS NULL)
                    OR (status <> 'pending' AND reviewed_at IS NOT NULL)
                )
            )
            """,
            """
            CREATE TABLE canonical_medication_records_phase_1d (
                id TEXT PRIMARY KEY,
                person_id TEXT NOT NULL REFERENCES people(person_id),
                candidate_id TEXT NOT NULL UNIQUE REFERENCES candidate_facts_phase_1d(id),
                source_id TEXT NOT NULL REFERENCES sources_phase_1d(id),
                display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
                normalized_name TEXT NOT NULL CHECK (length(trim(normalized_name)) > 0),
                schedule_text TEXT,
                note TEXT,
                confirmed_at TEXT NOT NULL,
                is_active INTEGER NOT NULL CHECK (is_active IN (0, 1))
            )
            """,
            """
            CREATE TABLE timeline_events_phase_1d (
                id TEXT PRIMARY KEY,
                person_id TEXT NOT NULL REFERENCES people(person_id),
                canonical_record_id TEXT NOT NULL
                    REFERENCES canonical_medication_records_phase_1d(id),
                source_id TEXT NOT NULL REFERENCES sources_phase_1d(id),
                event_type TEXT NOT NULL CHECK (length(trim(event_type)) > 0),
                event_at TEXT NOT NULL,
                title TEXT NOT NULL CHECK (length(trim(title)) > 0),
                UNIQUE (canonical_record_id, event_type)
            )
            """,
            "INSERT INTO sources_phase_1d SELECT * FROM sources",
            "INSERT INTO candidate_facts_phase_1d SELECT * FROM candidate_facts",
            (
                "INSERT INTO canonical_medication_records_phase_1d "
                "SELECT * FROM canonical_medication_records"
            ),
            "INSERT INTO timeline_events_phase_1d SELECT * FROM timeline_events",
            "DROP TABLE timeline_events",
            "DROP TABLE canonical_medication_records",
            "DROP TABLE candidate_facts",
            "DROP TABLE sources",
            "ALTER TABLE sources_phase_1d RENAME TO sources",
            "ALTER TABLE candidate_facts_phase_1d RENAME TO candidate_facts",
            (
                "ALTER TABLE canonical_medication_records_phase_1d "
                "RENAME TO canonical_medication_records"
            ),
            "ALTER TABLE timeline_events_phase_1d RENAME TO timeline_events",
            (
                "CREATE INDEX people_active_display_name_idx ON people("
                "is_active, display_name COLLATE NOCASE, person_id)"
            ),
            "CREATE INDEX candidate_facts_person_status_idx ON candidate_facts(person_id, status)",
            (
                "CREATE INDEX canonical_medication_records_person_active_idx "
                "ON canonical_medication_records(person_id, is_active)"
            ),
            (
                "CREATE INDEX timeline_events_person_event_at_idx "
                "ON timeline_events(person_id, event_at, id)"
            ),
        ),
    ),
    Migration(
        version=3,
        statements=(
            """
            CREATE TABLE visits (
                visit_id TEXT PRIMARY KEY CHECK (length(trim(visit_id)) > 0),
                person_id TEXT NOT NULL REFERENCES people(person_id),
                title TEXT NOT NULL CHECK (length(trim(title)) > 0),
                specialist TEXT,
                scheduled_date TEXT CHECK (
                    scheduled_date IS NULL OR (
                        length(scheduled_date) = 10 AND date(scheduled_date) = scheduled_date
                    )
                ),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE visit_questions (
                question_id TEXT PRIMARY KEY CHECK (length(trim(question_id)) > 0),
                visit_id TEXT NOT NULL REFERENCES visits(visit_id),
                question_text TEXT NOT NULL CHECK (length(trim(question_text)) > 0),
                position INTEGER NOT NULL CHECK (position >= 0),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (visit_id, position)
            )
            """,
            (
                "CREATE INDEX visits_person_created_idx "
                "ON visits(person_id, created_at DESC, visit_id)"
            ),
            (
                "CREATE INDEX visit_questions_visit_position_idx "
                "ON visit_questions(visit_id, position)"
            ),
        ),
    ),
    Migration(
        version=4,
        statements=(
            """
            CREATE TABLE visit_briefs (
                brief_id TEXT PRIMARY KEY CHECK (length(trim(brief_id)) > 0),
                visit_id TEXT NOT NULL UNIQUE REFERENCES visits(visit_id),
                current_revision_id TEXT
                    REFERENCES visit_brief_revisions(revision_id)
                    DEFERRABLE INITIALLY DEFERRED,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE visit_brief_revisions (
                revision_id TEXT PRIMARY KEY CHECK (length(trim(revision_id)) > 0),
                brief_id TEXT NOT NULL REFERENCES visit_briefs(brief_id),
                revision_number INTEGER NOT NULL CHECK (revision_number >= 1),
                origin TEXT NOT NULL CHECK (
                    origin IN ('deterministic_generation', 'user_edit', 'regeneration')
                ),
                parent_revision_id TEXT REFERENCES visit_brief_revisions(revision_id),
                content_schema_version INTEGER NOT NULL CHECK (content_schema_version >= 1),
                render_version INTEGER NOT NULL CHECK (render_version >= 1),
                content_json TEXT NOT NULL,
                rendered_markdown TEXT NOT NULL,
                content_hash TEXT NOT NULL CHECK (length(content_hash) = 64),
                created_at TEXT NOT NULL,
                UNIQUE (brief_id, revision_number)
            )
            """,
            """
            CREATE TABLE visit_brief_evidence_selections (
                revision_id TEXT NOT NULL REFERENCES visit_brief_revisions(revision_id),
                position INTEGER NOT NULL CHECK (position >= 0),
                canonical_record_id TEXT NOT NULL
                    REFERENCES canonical_medication_records(id),
                source_id TEXT NOT NULL REFERENCES sources(id),
                snapshot_json TEXT NOT NULL,
                PRIMARY KEY (revision_id, position),
                UNIQUE (revision_id, canonical_record_id)
            )
            """,
            """
            CREATE TABLE visit_brief_audit_events (
                audit_event_id TEXT PRIMARY KEY CHECK (length(trim(audit_event_id)) > 0),
                visit_id TEXT NOT NULL REFERENCES visits(visit_id),
                brief_id TEXT REFERENCES visit_briefs(brief_id),
                revision_number INTEGER CHECK (
                    revision_number IS NULL OR revision_number >= 1
                ),
                action TEXT NOT NULL CHECK (
                    action IN (
                        'initialize', 'deterministic_generation', 'regeneration',
                        'user_edit', 'restore', 'export', 'concurrency_conflict'
                    )
                ),
                involved_resource_ids_json TEXT NOT NULL,
                outcome TEXT NOT NULL CHECK (outcome IN ('succeeded', 'rejected')),
                reason_code TEXT,
                created_at TEXT NOT NULL
            )
            """,
            "CREATE INDEX visit_briefs_visit_idx ON visit_briefs(visit_id)",
            (
                "CREATE INDEX visit_brief_revisions_brief_number_idx "
                "ON visit_brief_revisions(brief_id, revision_number DESC)"
            ),
            (
                "CREATE INDEX visit_brief_evidence_revision_position_idx "
                "ON visit_brief_evidence_selections(revision_id, position)"
            ),
            (
                "CREATE INDEX visit_brief_audit_events_brief_created_idx "
                "ON visit_brief_audit_events(brief_id, created_at)"
            ),
        ),
    ),
    Migration(
        version=5,
        statements=(
            """
            CREATE TABLE actors (
                actor_id TEXT PRIMARY KEY CHECK (length(trim(actor_id)) > 0),
                username_normalized TEXT NOT NULL UNIQUE
                    CHECK (length(trim(username_normalized)) > 0),
                display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
                status TEXT NOT NULL CHECK (status IN ('active', 'disabled')),
                created_at TEXT NOT NULL,
                disabled_at TEXT,
                disabled_by_actor_id TEXT REFERENCES actors(actor_id),
                CHECK (
                    (status = 'active' AND disabled_at IS NULL)
                    OR (status = 'disabled' AND disabled_at IS NOT NULL)
                )
            )
            """,
            """
            CREATE TABLE actor_credentials (
                credential_id TEXT PRIMARY KEY CHECK (length(trim(credential_id)) > 0),
                actor_id TEXT NOT NULL REFERENCES actors(actor_id),
                credential_type TEXT NOT NULL DEFAULT 'local_password'
                    CHECK (credential_type = 'local_password'),
                algorithm TEXT NOT NULL CHECK (algorithm = 'scrypt'),
                algorithm_version INTEGER NOT NULL CHECK (algorithm_version = 1),
                salt BLOB NOT NULL CHECK (length(salt) >= 16),
                verifier BLOB NOT NULL CHECK (length(verifier) = 64),
                created_at TEXT NOT NULL,
                revoked_at TEXT,
                replaced_by_credential_id TEXT REFERENCES actor_credentials(credential_id),
                CHECK (
                    (revoked_at IS NULL AND replaced_by_credential_id IS NULL)
                    OR revoked_at IS NOT NULL
                )
            )
            """,
            """
            CREATE UNIQUE INDEX actor_credentials_actor_active_idx
            ON actor_credentials(actor_id) WHERE revoked_at IS NULL
            """,
            """
            CREATE TABLE installation_admin_assignments (
                admin_assignment_id TEXT PRIMARY KEY
                    CHECK (length(trim(admin_assignment_id)) > 0),
                actor_id TEXT NOT NULL REFERENCES actors(actor_id),
                assigned_by_actor_id TEXT NOT NULL REFERENCES actors(actor_id),
                is_active INTEGER NOT NULL CHECK (is_active IN (0, 1)),
                assigned_at TEXT NOT NULL,
                revoked_at TEXT,
                revoked_by_actor_id TEXT REFERENCES actors(actor_id),
                reason_code TEXT CHECK (reason_code IS NULL OR length(reason_code) <= 80),
                CHECK (
                    (is_active = 1 AND revoked_at IS NULL AND revoked_by_actor_id IS NULL)
                    OR (is_active = 0 AND revoked_at IS NOT NULL)
                )
            )
            """,
            """
            CREATE UNIQUE INDEX installation_admin_actor_active_idx
            ON installation_admin_assignments(actor_id) WHERE is_active = 1
            """,
            """
            CREATE TABLE families (
                family_id TEXT PRIMARY KEY CHECK (length(trim(family_id)) > 0),
                display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
                created_by_actor_id TEXT NOT NULL REFERENCES actors(actor_id),
                created_at TEXT NOT NULL,
                is_archived INTEGER NOT NULL DEFAULT 0 CHECK (is_archived IN (0, 1)),
                archived_at TEXT,
                archived_by_actor_id TEXT REFERENCES actors(actor_id),
                CHECK (
                    (is_archived = 0 AND archived_at IS NULL AND archived_by_actor_id IS NULL)
                    OR (is_archived = 1 AND archived_at IS NOT NULL)
                )
            )
            """,
            """
            CREATE TABLE family_memberships (
                membership_id TEXT PRIMARY KEY CHECK (length(trim(membership_id)) > 0),
                family_id TEXT NOT NULL REFERENCES families(family_id),
                person_id TEXT NOT NULL REFERENCES people(person_id),
                created_by_actor_id TEXT NOT NULL REFERENCES actors(actor_id),
                is_active INTEGER NOT NULL CHECK (is_active IN (0, 1)),
                created_at TEXT NOT NULL,
                ended_at TEXT,
                ended_by_actor_id TEXT REFERENCES actors(actor_id),
                CHECK (
                    (is_active = 1 AND ended_at IS NULL AND ended_by_actor_id IS NULL)
                    OR (is_active = 0 AND ended_at IS NOT NULL)
                )
            )
            """,
            """
            CREATE UNIQUE INDEX family_memberships_person_active_idx
            ON family_memberships(person_id) WHERE is_active = 1
            """,
            """
            CREATE INDEX family_memberships_family_active_idx
            ON family_memberships(family_id, is_active, person_id)
            """,
            """
            CREATE TABLE person_relationships (
                relationship_id TEXT PRIMARY KEY CHECK (length(trim(relationship_id)) > 0),
                family_id TEXT NOT NULL REFERENCES families(family_id),
                person_id TEXT NOT NULL REFERENCES people(person_id),
                related_person_id TEXT NOT NULL REFERENCES people(person_id),
                relationship_type TEXT NOT NULL CHECK (
                    relationship_type IN (
                        'parent', 'child', 'spouse', 'partner', 'sibling',
                        'guardian', 'dependent', 'other'
                    )
                ),
                created_by_actor_id TEXT NOT NULL REFERENCES actors(actor_id),
                is_active INTEGER NOT NULL CHECK (is_active IN (0, 1)),
                created_at TEXT NOT NULL,
                ended_at TEXT,
                ended_by_actor_id TEXT REFERENCES actors(actor_id),
                CHECK (person_id <> related_person_id),
                CHECK (
                    (is_active = 1 AND ended_at IS NULL AND ended_by_actor_id IS NULL)
                    OR (is_active = 0 AND ended_at IS NOT NULL)
                )
            )
            """,
            """
            CREATE UNIQUE INDEX person_relationships_directed_active_idx
            ON person_relationships(family_id, person_id, related_person_id, relationship_type)
            WHERE is_active = 1
            """,
            """
            CREATE TABLE person_access_consent_history (
                consent_event_id TEXT PRIMARY KEY CHECK (length(trim(consent_event_id)) > 0),
                event_type TEXT NOT NULL CHECK (
                    event_type IN ('grant', 'accept', 'revise', 'revoke', 'expire')
                ),
                acting_owner_actor_id TEXT REFERENCES actors(actor_id),
                recipient_actor_id TEXT NOT NULL REFERENCES actors(actor_id),
                person_id TEXT NOT NULL REFERENCES people(person_id),
                role TEXT NOT NULL CHECK (role IN ('owner', 'caregiver')),
                scopes_json TEXT NOT NULL CHECK (
                    json_valid(scopes_json) AND json_type(scopes_json) = 'array'
                ),
                reason_code TEXT NOT NULL CHECK (
                    length(trim(reason_code)) > 0 AND length(reason_code) <= 80
                ),
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX person_access_consent_person_created_idx
            ON person_access_consent_history(person_id, created_at, consent_event_id)
            """,
            """
            CREATE TABLE person_access_assignments (
                assignment_id TEXT PRIMARY KEY CHECK (length(trim(assignment_id)) > 0),
                actor_id TEXT NOT NULL REFERENCES actors(actor_id),
                person_id TEXT NOT NULL REFERENCES people(person_id),
                role TEXT NOT NULL CHECK (role IN ('owner', 'caregiver')),
                scopes_json TEXT NOT NULL CHECK (
                    json_valid(scopes_json) AND json_type(scopes_json) = 'array'
                ),
                consent_event_id TEXT NOT NULL
                    REFERENCES person_access_consent_history(consent_event_id),
                granted_by_actor_id TEXT NOT NULL REFERENCES actors(actor_id),
                is_active INTEGER NOT NULL CHECK (is_active IN (0, 1)),
                granted_at TEXT NOT NULL,
                revoked_at TEXT,
                revoked_by_actor_id TEXT REFERENCES actors(actor_id),
                revision_of_assignment_id TEXT REFERENCES person_access_assignments(assignment_id),
                CHECK (
                    (is_active = 1 AND revoked_at IS NULL AND revoked_by_actor_id IS NULL)
                    OR (is_active = 0 AND revoked_at IS NOT NULL)
                ),
                CHECK (
                    revision_of_assignment_id IS NULL
                    OR revision_of_assignment_id <> assignment_id
                )
            )
            """,
            """
            CREATE UNIQUE INDEX person_access_actor_person_active_idx
            ON person_access_assignments(actor_id, person_id) WHERE is_active = 1
            """,
            """
            CREATE INDEX person_access_person_role_active_idx
            ON person_access_assignments(person_id, role, is_active, actor_id)
            """,
            """
            CREATE TABLE own_person_links (
                own_person_link_id TEXT PRIMARY KEY CHECK (length(trim(own_person_link_id)) > 0),
                actor_id TEXT NOT NULL REFERENCES actors(actor_id),
                person_id TEXT NOT NULL REFERENCES people(person_id),
                is_active INTEGER NOT NULL CHECK (is_active IN (0, 1)),
                created_at TEXT NOT NULL,
                revoked_at TEXT,
                revoked_by_actor_id TEXT REFERENCES actors(actor_id),
                CHECK (
                    (is_active = 1 AND revoked_at IS NULL AND revoked_by_actor_id IS NULL)
                    OR (is_active = 0 AND revoked_at IS NOT NULL)
                )
            )
            """,
            """
            CREATE UNIQUE INDEX own_person_links_actor_active_idx
            ON own_person_links(actor_id) WHERE is_active = 1
            """,
            """
            CREATE UNIQUE INDEX own_person_links_person_active_idx
            ON own_person_links(person_id) WHERE is_active = 1
            """,
            """
            CREATE TABLE access_invitations (
                invitation_id TEXT PRIMARY KEY CHECK (length(trim(invitation_id)) > 0),
                secret_hash BLOB NOT NULL UNIQUE CHECK (length(secret_hash) = 32),
                inviter_actor_id TEXT NOT NULL REFERENCES actors(actor_id),
                person_id TEXT NOT NULL REFERENCES people(person_id),
                role TEXT NOT NULL CHECK (role IN ('owner', 'caregiver')),
                scopes_json TEXT NOT NULL CHECK (
                    json_valid(scopes_json) AND json_type(scopes_json) = 'array'
                ),
                state TEXT NOT NULL CHECK (state IN ('active', 'revoked', 'redeemed', 'expired')),
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT,
                revoked_by_actor_id TEXT REFERENCES actors(actor_id),
                redeemed_at TEXT,
                redeemed_by_actor_id TEXT REFERENCES actors(actor_id),
                CHECK (
                    (state = 'active' AND revoked_at IS NULL AND redeemed_at IS NULL)
                    OR (state = 'revoked' AND revoked_at IS NOT NULL AND redeemed_at IS NULL)
                    OR (state = 'redeemed' AND redeemed_at IS NOT NULL AND revoked_at IS NULL)
                    OR (state = 'expired' AND redeemed_at IS NULL)
                )
            )
            """,
            """
            CREATE INDEX access_invitations_person_state_idx
            ON access_invitations(person_id, state, expires_at, invitation_id)
            """,
            """
            CREATE TABLE access_audit_events (
                audit_event_id TEXT PRIMARY KEY CHECK (length(trim(audit_event_id)) > 0),
                actor_id TEXT REFERENCES actors(actor_id),
                action_code TEXT NOT NULL CHECK (
                    length(trim(action_code)) > 0 AND length(action_code) <= 80
                ),
                target_class TEXT NOT NULL CHECK (
                    target_class IN (
                        'installation', 'actor', 'credential', 'family', 'membership',
                        'relationship', 'person', 'assignment', 'invitation', 'session'
                    )
                ),
                target_id TEXT CHECK (target_id IS NULL OR length(target_id) <= 128),
                outcome TEXT NOT NULL CHECK (outcome IN ('success', 'denied', 'failure')),
                reason_code TEXT NOT NULL CHECK (
                    length(trim(reason_code)) > 0 AND length(reason_code) <= 80
                ),
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX access_audit_created_idx
            ON access_audit_events(created_at, audit_event_id)
            """,
            """
            CREATE INDEX access_audit_actor_created_idx
            ON access_audit_events(actor_id, created_at, audit_event_id)
            """,
            """
            CREATE TRIGGER actor_disable_requires_privilege_revocation
            BEFORE UPDATE OF status ON actors
            WHEN OLD.status = 'active' AND NEW.status = 'disabled' AND (
                EXISTS (
                    SELECT 1 FROM installation_admin_assignments
                    WHERE actor_id = OLD.actor_id AND is_active = 1
                )
                OR EXISTS (
                    SELECT 1 FROM person_access_assignments
                    WHERE actor_id = OLD.actor_id AND is_active = 1
                )
            )
            BEGIN
                SELECT RAISE(ABORT, 'active_actor_privileges_must_be_revoked_first');
            END
            """,
            """
            CREATE TRIGGER installation_admin_last_active_update
            BEFORE UPDATE OF is_active ON installation_admin_assignments
            WHEN OLD.is_active = 1 AND NEW.is_active = 0
                 AND (
                    SELECT COUNT(*) FROM installation_admin_assignments AS iaa
                    JOIN actors AS a ON a.actor_id = iaa.actor_id
                    WHERE iaa.is_active = 1 AND a.status = 'active'
                 ) <= 1
            BEGIN
                SELECT RAISE(ABORT, 'last_active_installation_admin');
            END
            """,
            """
            CREATE TRIGGER installation_admin_last_active_delete
            BEFORE DELETE ON installation_admin_assignments
            WHEN OLD.is_active = 1
                 AND (
                    SELECT COUNT(*) FROM installation_admin_assignments AS iaa
                    JOIN actors AS a ON a.actor_id = iaa.actor_id
                    WHERE iaa.is_active = 1 AND a.status = 'active'
                 ) <= 1
            BEGIN
                SELECT RAISE(ABORT, 'last_active_installation_admin');
            END
            """,
            """
            CREATE TRIGGER installation_admin_active_actor_insert
            BEFORE INSERT ON installation_admin_assignments
            WHEN NEW.is_active = 1 AND NOT EXISTS (
                SELECT 1 FROM actors
                WHERE actor_id = NEW.actor_id AND status = 'active'
            )
            BEGIN
                SELECT RAISE(ABORT, 'active_admin_requires_active_actor');
            END
            """,
            """
            CREATE TRIGGER installation_admin_active_actor_update
            BEFORE UPDATE OF is_active, actor_id ON installation_admin_assignments
            WHEN NEW.is_active = 1 AND NOT EXISTS (
                SELECT 1 FROM actors
                WHERE actor_id = NEW.actor_id AND status = 'active'
            )
            BEGIN
                SELECT RAISE(ABORT, 'active_admin_requires_active_actor');
            END
            """,
            """
            CREATE TRIGGER person_access_last_owner_update
            BEFORE UPDATE OF is_active, role, person_id ON person_access_assignments
            WHEN OLD.is_active = 1 AND OLD.role = 'owner'
                 AND (
                    NEW.is_active = 0 OR NEW.role <> 'owner'
                    OR NEW.person_id <> OLD.person_id
                 )
                 AND (
                    SELECT COUNT(*) FROM person_access_assignments
                    WHERE person_id = OLD.person_id AND role = 'owner' AND is_active = 1
                 ) <= 1
            BEGIN
                SELECT RAISE(ABORT, 'last_active_person_owner');
            END
            """,
            """
            CREATE TRIGGER person_access_last_owner_delete
            BEFORE DELETE ON person_access_assignments
            WHEN OLD.is_active = 1 AND OLD.role = 'owner'
                 AND (
                    SELECT COUNT(*) FROM person_access_assignments
                    WHERE person_id = OLD.person_id AND role = 'owner' AND is_active = 1
                 ) <= 1
            BEGIN
                SELECT RAISE(ABORT, 'last_active_person_owner');
            END
            """,
            """
            CREATE TRIGGER person_access_active_subject_insert
            BEFORE INSERT ON person_access_assignments
            WHEN NEW.is_active = 1 AND (
                NOT EXISTS (
                    SELECT 1 FROM actors
                    WHERE actor_id = NEW.actor_id AND status = 'active'
                )
                OR NOT EXISTS (
                    SELECT 1 FROM people
                    WHERE person_id = NEW.person_id AND is_active = 1
                )
            )
            BEGIN
                SELECT RAISE(ABORT, 'active_assignment_requires_active_subjects');
            END
            """,
            """
            CREATE TRIGGER person_access_active_subject_update
            BEFORE UPDATE OF is_active, actor_id, person_id ON person_access_assignments
            WHEN NEW.is_active = 1 AND (
                NOT EXISTS (
                    SELECT 1 FROM actors
                    WHERE actor_id = NEW.actor_id AND status = 'active'
                )
                OR NOT EXISTS (
                    SELECT 1 FROM people
                    WHERE person_id = NEW.person_id AND is_active = 1
                )
            )
            BEGIN
                SELECT RAISE(ABORT, 'active_assignment_requires_active_subjects');
            END
            """,
            """
            CREATE TRIGGER own_person_link_requires_owner_insert
            BEFORE INSERT ON own_person_links
            WHEN NEW.is_active = 1 AND NOT EXISTS (
                SELECT 1 FROM person_access_assignments
                WHERE actor_id = NEW.actor_id AND person_id = NEW.person_id
                      AND role = 'owner' AND is_active = 1
            )
            BEGIN
                SELECT RAISE(ABORT, 'own_person_link_requires_active_owner');
            END
            """,
            """
            CREATE TRIGGER own_person_link_requires_owner_update
            BEFORE UPDATE OF is_active, actor_id, person_id ON own_person_links
            WHEN NEW.is_active = 1 AND NOT EXISTS (
                SELECT 1 FROM person_access_assignments
                WHERE actor_id = NEW.actor_id AND person_id = NEW.person_id
                      AND role = 'owner' AND is_active = 1
            )
            BEGIN
                SELECT RAISE(ABORT, 'own_person_link_requires_active_owner');
            END
            """,
            """
            CREATE TRIGGER owner_assignment_preserves_own_link
            BEFORE UPDATE OF is_active, role, actor_id, person_id ON person_access_assignments
            WHEN OLD.is_active = 1 AND OLD.role = 'owner'
                 AND (
                    NEW.is_active = 0 OR NEW.role <> 'owner'
                    OR NEW.actor_id <> OLD.actor_id OR NEW.person_id <> OLD.person_id
                 )
                 AND EXISTS (
                    SELECT 1 FROM own_person_links
                    WHERE actor_id = OLD.actor_id AND person_id = OLD.person_id AND is_active = 1
                 )
            BEGIN
                SELECT RAISE(ABORT, 'active_own_person_link_requires_owner');
            END
            """,
            """
            CREATE TRIGGER owner_assignment_delete_preserves_own_link
            BEFORE DELETE ON person_access_assignments
            WHEN OLD.is_active = 1 AND OLD.role = 'owner'
                 AND EXISTS (
                    SELECT 1 FROM own_person_links
                    WHERE actor_id = OLD.actor_id AND person_id = OLD.person_id AND is_active = 1
                 )
            BEGIN
                SELECT RAISE(ABORT, 'active_own_person_link_requires_owner');
            END
            """,
            """
            CREATE TRIGGER archived_family_membership_insert
            BEFORE INSERT ON family_memberships
            WHEN EXISTS (
                SELECT 1 FROM families
                WHERE family_id = NEW.family_id AND is_archived = 1
            )
            BEGIN
                SELECT RAISE(ABORT, 'archived_family_is_read_only');
            END
            """,
            """
            CREATE TRIGGER archived_family_membership_update
            BEFORE UPDATE ON family_memberships
            WHEN EXISTS (
                SELECT 1 FROM families
                WHERE family_id = OLD.family_id AND is_archived = 1
            ) OR EXISTS (
                SELECT 1 FROM families
                WHERE family_id = NEW.family_id AND is_archived = 1
            )
            BEGIN
                SELECT RAISE(ABORT, 'archived_family_is_read_only');
            END
            """,
            """
            CREATE TRIGGER archived_family_membership_delete
            BEFORE DELETE ON family_memberships
            WHEN EXISTS (
                SELECT 1 FROM families
                WHERE family_id = OLD.family_id AND is_archived = 1
            )
            BEGIN
                SELECT RAISE(ABORT, 'archived_family_is_read_only');
            END
            """,
            """
            CREATE TRIGGER archived_family_relationship_insert
            BEFORE INSERT ON person_relationships
            WHEN EXISTS (
                SELECT 1 FROM families
                WHERE family_id = NEW.family_id AND is_archived = 1
            )
            BEGIN
                SELECT RAISE(ABORT, 'archived_family_is_read_only');
            END
            """,
            """
            CREATE TRIGGER archived_family_relationship_update
            BEFORE UPDATE ON person_relationships
            WHEN EXISTS (
                SELECT 1 FROM families
                WHERE family_id = OLD.family_id AND is_archived = 1
            ) OR EXISTS (
                SELECT 1 FROM families
                WHERE family_id = NEW.family_id AND is_archived = 1
            )
            BEGIN
                SELECT RAISE(ABORT, 'archived_family_is_read_only');
            END
            """,
            """
            CREATE TRIGGER archived_family_relationship_delete
            BEFORE DELETE ON person_relationships
            WHEN EXISTS (
                SELECT 1 FROM families
                WHERE family_id = OLD.family_id AND is_archived = 1
            )
            BEGIN
                SELECT RAISE(ABORT, 'archived_family_is_read_only');
            END
            """,
            """
            CREATE TRIGGER family_relationship_requires_memberships_insert
            BEFORE INSERT ON person_relationships
            WHEN NEW.is_active = 1 AND (
                NOT EXISTS (
                    SELECT 1 FROM family_memberships
                    WHERE family_id = NEW.family_id AND person_id = NEW.person_id AND is_active = 1
                )
                OR NOT EXISTS (
                    SELECT 1 FROM family_memberships
                    WHERE family_id = NEW.family_id
                          AND person_id = NEW.related_person_id AND is_active = 1
                )
            )
            BEGIN
                SELECT RAISE(ABORT, 'relationship_requires_active_family_memberships');
            END
            """,
            """
            CREATE TRIGGER family_relationship_requires_memberships_update
            BEFORE UPDATE OF is_active, family_id, person_id, related_person_id
            ON person_relationships
            WHEN NEW.is_active = 1 AND (
                NOT EXISTS (
                    SELECT 1 FROM family_memberships
                    WHERE family_id = NEW.family_id AND person_id = NEW.person_id AND is_active = 1
                )
                OR NOT EXISTS (
                    SELECT 1 FROM family_memberships
                    WHERE family_id = NEW.family_id
                          AND person_id = NEW.related_person_id AND is_active = 1
                )
            )
            BEGIN
                SELECT RAISE(ABORT, 'relationship_requires_active_family_memberships');
            END
            """,
            """
            CREATE TRIGGER family_membership_update_preserves_relationships
            BEFORE UPDATE OF is_active, family_id, person_id ON family_memberships
            WHEN OLD.is_active = 1
                 AND (
                    NEW.is_active = 0 OR NEW.family_id <> OLD.family_id
                    OR NEW.person_id <> OLD.person_id
                 )
                 AND EXISTS (
                SELECT 1 FROM person_relationships
                WHERE family_id = OLD.family_id AND is_active = 1
                      AND (person_id = OLD.person_id OR related_person_id = OLD.person_id)
            )
            BEGIN
                SELECT RAISE(ABORT, 'active_relationship_requires_membership');
            END
            """,
            """
            CREATE TRIGGER family_membership_delete_preserves_relationships
            BEFORE DELETE ON family_memberships
            WHEN OLD.is_active = 1 AND EXISTS (
                SELECT 1 FROM person_relationships
                WHERE family_id = OLD.family_id AND is_active = 1
                      AND (person_id = OLD.person_id OR related_person_id = OLD.person_id)
            )
            BEGIN
                SELECT RAISE(ABORT, 'active_relationship_requires_membership');
            END
            """,
            """
            CREATE TRIGGER consent_history_immutable_update
            BEFORE UPDATE ON person_access_consent_history
            BEGIN
                SELECT RAISE(ABORT, 'consent_history_is_append_only');
            END
            """,
            """
            CREATE TRIGGER consent_history_immutable_delete
            BEFORE DELETE ON person_access_consent_history
            BEGIN
                SELECT RAISE(ABORT, 'consent_history_is_append_only');
            END
            """,
            """
            CREATE TRIGGER access_audit_immutable_update
            BEFORE UPDATE ON access_audit_events
            BEGIN
                SELECT RAISE(ABORT, 'access_audit_is_append_only');
            END
            """,
            """
            CREATE TRIGGER access_audit_immutable_delete
            BEFORE DELETE ON access_audit_events
            BEGIN
                SELECT RAISE(ABORT, 'access_audit_is_append_only');
            END
            """,
        ),
    ),
    Migration(
        version=6,
        statements=(
            """
            CREATE TABLE agent_disclosure_consents (
                consent_id TEXT PRIMARY KEY CHECK (length(trim(consent_id)) > 0),
                execution_id TEXT NOT NULL UNIQUE CHECK (length(trim(execution_id)) > 0),
                actor_id TEXT NOT NULL REFERENCES actors(actor_id),
                person_id TEXT NOT NULL REFERENCES people(person_id),
                purpose TEXT NOT NULL CHECK (length(trim(purpose)) > 0),
                action TEXT NOT NULL CHECK (length(trim(action)) > 0),
                envelope_id TEXT NOT NULL CHECK (length(trim(envelope_id)) > 0),
                provider_id TEXT NOT NULL CHECK (length(trim(provider_id)) > 0),
                provider_descriptor_hash TEXT NOT NULL CHECK (length(provider_descriptor_hash) = 64),
                disclosure_metadata_json TEXT NOT NULL,
                policy_version TEXT NOT NULL CHECK (length(trim(policy_version)) > 0),
                consented_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                consent_hash TEXT NOT NULL CHECK (length(consent_hash) = 64),
                metadata_json TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE agent_execution_receipts (
                receipt_id TEXT PRIMARY KEY CHECK (length(trim(receipt_id)) > 0),
                execution_id TEXT NOT NULL UNIQUE CHECK (length(trim(execution_id)) > 0),
                consent_id TEXT NOT NULL REFERENCES agent_disclosure_consents(consent_id),
                actor_id TEXT NOT NULL REFERENCES actors(actor_id),
                person_id TEXT NOT NULL REFERENCES people(person_id),
                envelope_id TEXT NOT NULL CHECK (length(trim(envelope_id)) > 0),
                provider_id TEXT NOT NULL CHECK (length(trim(provider_id)) > 0),
                status TEXT NOT NULL CHECK (status IN ('completed', 'refused', 'failed')),
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                used_evidence_ids_json TEXT NOT NULL,
                used_tools_json TEXT NOT NULL,
                output_sha256 TEXT CHECK (output_sha256 IS NULL OR length(output_sha256) = 64),
                mutation_attempted INTEGER NOT NULL CHECK (mutation_attempted IN (0, 1)),
                reason_codes_json TEXT NOT NULL,
                receipt_sha256 TEXT NOT NULL CHECK (length(receipt_sha256) = 64),
                metadata_json TEXT NOT NULL
            )
            """,
            (
                "CREATE INDEX agent_disclosure_consents_person_created_idx "
                "ON agent_disclosure_consents(person_id, consented_at, consent_id)"
            ),
            (
                "CREATE INDEX agent_execution_receipts_person_completed_idx "
                "ON agent_execution_receipts(person_id, completed_at, receipt_id)"
            ),
        ),
    ),
)


class MigrationRunner:
    def __init__(
        self,
        connection_factory: Callable[[], sqlite3.Connection],
        *,
        migrations: tuple[Migration, ...] = PRODUCT_MIGRATIONS,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.connection_factory = connection_factory
        self.migrations = migrations
        self.clock = clock or (lambda: datetime.now(UTC))
        versions = [migration.version for migration in migrations]
        if versions != sorted(set(versions)):
            raise ValueError("migration versions must be unique and sorted")

    def migrate(self) -> None:
        connection = self.connection_factory()
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            self._bootstrap(connection)
            applied_versions = {
                row[0]
                for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
            }
            for migration in self.migrations:
                if migration.version in applied_versions:
                    continue
                self._apply_migration(connection, migration)
        finally:
            connection.close()

    @staticmethod
    def _bootstrap(connection: sqlite3.Connection) -> None:
        connection.execute("BEGIN")
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise

    def _apply_migration(self, connection: sqlite3.Connection, migration: Migration) -> None:
        connection.execute("BEGIN IMMEDIATE")
        try:
            already_applied = connection.execute(
                "SELECT 1 FROM schema_migrations WHERE version = ?",
                (migration.version,),
            ).fetchone()
            if already_applied is not None:
                connection.commit()
                return
            applied_at = isoformat_utc(ensure_utc_datetime(self.clock()))
            for statement in migration.statements:
                if migration.version == 2 and statement.lstrip().startswith("INSERT INTO people"):
                    connection.execute(statement, (applied_at, applied_at))
                else:
                    connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (migration.version, applied_at),
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
