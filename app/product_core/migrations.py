from __future__ import annotations

# ruff: noqa: E501
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
                provider_descriptor_hash TEXT NOT NULL CHECK (
                    length(provider_descriptor_hash) = 64
                ),
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
    Migration(
        version=7,
        statements=(
            "PRAGMA defer_foreign_keys=ON",
            """
            CREATE TABLE candidate_facts_v7 (
                id TEXT PRIMARY KEY,
                person_id TEXT NOT NULL REFERENCES people(person_id),
                source_id TEXT NOT NULL REFERENCES sources(id),
                fact_type TEXT NOT NULL CHECK (
                    fact_type IN ('medication', 'condition', 'lab')
                ),
                status TEXT NOT NULL CHECK (
                    status IN ('pending', 'confirmed', 'corrected', 'rejected', 'unsupported')
                ),
                created_at TEXT NOT NULL,
                reviewed_at TEXT,
                predecessor_candidate_id TEXT REFERENCES candidate_facts_v7(id),
                provenance_locator_json TEXT CHECK (
                    provenance_locator_json IS NULL
                    OR json_valid(provenance_locator_json)
                ),
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
            CREATE TABLE candidate_medication_details (
                candidate_id TEXT PRIMARY KEY REFERENCES candidate_facts_v7(id),
                display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
                normalized_name TEXT NOT NULL CHECK (length(trim(normalized_name)) > 0),
                schedule_text TEXT,
                note TEXT
            )
            """,
            """
            CREATE TABLE candidate_condition_details (
                candidate_id TEXT PRIMARY KEY REFERENCES candidate_facts_v7(id),
                display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
                normalized_name TEXT NOT NULL CHECK (length(trim(normalized_name)) > 0),
                status_text TEXT,
                onset_date TEXT CHECK (
                    onset_date IS NULL OR (
                        length(onset_date) = 10 AND date(onset_date) = onset_date
                    )
                ),
                note TEXT
            )
            """,
            """
            CREATE TABLE candidate_lab_details (
                candidate_id TEXT PRIMARY KEY REFERENCES candidate_facts_v7(id),
                test_name TEXT NOT NULL CHECK (length(trim(test_name)) > 0),
                normalized_test_name TEXT NOT NULL CHECK (
                    length(trim(normalized_test_name)) > 0
                ),
                result_text TEXT NOT NULL,
                unit_text TEXT,
                reference_range_text TEXT,
                observed_date TEXT CHECK (
                    observed_date IS NULL OR (
                        length(observed_date) = 10 AND date(observed_date) = observed_date
                    )
                ),
                source_flag_text TEXT,
                note TEXT
            )
            """,
            """
            CREATE TABLE canonical_records_v7 (
                id TEXT PRIMARY KEY,
                person_id TEXT NOT NULL REFERENCES people(person_id),
                candidate_id TEXT NOT NULL UNIQUE REFERENCES candidate_facts_v7(id),
                source_id TEXT NOT NULL REFERENCES sources(id),
                fact_type TEXT NOT NULL CHECK (
                    fact_type IN ('medication', 'condition', 'lab')
                ),
                confirmed_at TEXT NOT NULL,
                is_active INTEGER NOT NULL CHECK (is_active IN (0, 1)),
                superseded_by_record_id TEXT REFERENCES canonical_records_v7(id),
                CHECK (
                    superseded_by_record_id IS NULL OR superseded_by_record_id <> id
                ),
                CHECK (
                    (is_active = 1 AND superseded_by_record_id IS NULL)
                    OR (is_active = 0 AND superseded_by_record_id IS NOT NULL)
                )
            )
            """,
            """
            CREATE TABLE canonical_medication_details (
                record_id TEXT PRIMARY KEY REFERENCES canonical_records_v7(id),
                display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
                normalized_name TEXT NOT NULL CHECK (length(trim(normalized_name)) > 0),
                schedule_text TEXT,
                note TEXT
            )
            """,
            """
            CREATE TABLE canonical_condition_details (
                record_id TEXT PRIMARY KEY REFERENCES canonical_records_v7(id),
                display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
                normalized_name TEXT NOT NULL CHECK (length(trim(normalized_name)) > 0),
                status_text TEXT,
                onset_date TEXT CHECK (
                    onset_date IS NULL OR (
                        length(onset_date) = 10 AND date(onset_date) = onset_date
                    )
                ),
                note TEXT
            )
            """,
            """
            CREATE TABLE canonical_lab_details (
                record_id TEXT PRIMARY KEY REFERENCES canonical_records_v7(id),
                test_name TEXT NOT NULL CHECK (length(trim(test_name)) > 0),
                normalized_test_name TEXT NOT NULL CHECK (
                    length(trim(normalized_test_name)) > 0
                ),
                result_text TEXT NOT NULL,
                unit_text TEXT,
                reference_range_text TEXT,
                observed_date TEXT CHECK (
                    observed_date IS NULL OR (
                        length(observed_date) = 10 AND date(observed_date) = observed_date
                    )
                ),
                source_flag_text TEXT,
                note TEXT
            )
            """,
            """
            CREATE TABLE timeline_events_v7 (
                id TEXT PRIMARY KEY,
                person_id TEXT NOT NULL REFERENCES people(person_id),
                canonical_record_id TEXT NOT NULL REFERENCES canonical_records_v7(id),
                source_id TEXT NOT NULL REFERENCES sources(id),
                fact_type TEXT NOT NULL CHECK (
                    fact_type IN ('medication', 'condition', 'lab')
                ),
                event_type TEXT NOT NULL CHECK (length(trim(event_type)) > 0),
                event_at TEXT NOT NULL,
                title TEXT NOT NULL CHECK (length(trim(title)) > 0),
                UNIQUE (canonical_record_id, event_type)
            )
            """,
            """
            CREATE TABLE visit_brief_evidence_selections_v7 (
                revision_id TEXT NOT NULL REFERENCES visit_brief_revisions(revision_id),
                position INTEGER NOT NULL CHECK (position >= 0),
                canonical_record_id TEXT NOT NULL REFERENCES canonical_records_v7(id),
                source_id TEXT NOT NULL REFERENCES sources(id),
                snapshot_json TEXT NOT NULL,
                PRIMARY KEY (revision_id, position),
                UNIQUE (revision_id, canonical_record_id)
            )
            """,
            """
            INSERT INTO candidate_facts_v7 (
                id, person_id, source_id, fact_type, status, created_at,
                reviewed_at, predecessor_candidate_id, provenance_locator_json
            )
            SELECT candidate.id, candidate.person_id, candidate.source_id,
                   'medication', candidate.status, candidate.created_at,
                   candidate.reviewed_at, candidate.predecessor_candidate_id,
                   CASE WHEN source.source_type = 'manual_entry'
                        THEN '{"kind":"structured_field","path":"medication"}'
                        ELSE NULL END
            FROM candidate_facts AS candidate
            JOIN sources AS source ON source.id = candidate.source_id
            """,
            """
            INSERT INTO candidate_medication_details (
                candidate_id, display_name, normalized_name, schedule_text, note
            )
            SELECT id, display_name, normalized_name, schedule_text, note
            FROM candidate_facts
            """,
            """
            INSERT INTO canonical_records_v7 (
                id, person_id, candidate_id, source_id, fact_type,
                confirmed_at, is_active, superseded_by_record_id
            )
            SELECT id, person_id, candidate_id, source_id, 'medication',
                   confirmed_at, is_active, NULL
            FROM canonical_medication_records
            """,
            """
            INSERT INTO canonical_medication_details (
                record_id, display_name, normalized_name, schedule_text, note
            )
            SELECT id, display_name, normalized_name, schedule_text, note
            FROM canonical_medication_records
            """,
            """
            INSERT INTO timeline_events_v7 (
                id, person_id, canonical_record_id, source_id, fact_type,
                event_type, event_at, title
            )
            SELECT id, person_id, canonical_record_id, source_id, 'medication',
                   event_type, event_at, title
            FROM timeline_events
            """,
            """
            INSERT INTO visit_brief_evidence_selections_v7 (
                revision_id, position, canonical_record_id, source_id, snapshot_json
            )
            SELECT revision_id, position, canonical_record_id, source_id, snapshot_json
            FROM visit_brief_evidence_selections
            """,
            """
            ALTER TABLE person_access_assignments
            ADD COLUMN scope_generation TEXT NOT NULL DEFAULT 'family-access-v1'
                CHECK (length(trim(scope_generation)) > 0)
            """,
            "DROP TABLE visit_brief_evidence_selections",
            "DROP TABLE timeline_events",
            "DROP TABLE canonical_medication_records",
            "DROP TABLE candidate_facts",
            "ALTER TABLE candidate_facts_v7 RENAME TO candidate_facts",
            ("ALTER TABLE canonical_records_v7 RENAME TO canonical_records"),
            "ALTER TABLE timeline_events_v7 RENAME TO timeline_events",
            (
                "ALTER TABLE visit_brief_evidence_selections_v7 "
                "RENAME TO visit_brief_evidence_selections"
            ),
            """
            CREATE TRIGGER candidate_facts_predecessor_same_person_insert
            BEFORE INSERT ON candidate_facts
            WHEN NEW.predecessor_candidate_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM candidate_facts AS predecessor
                WHERE predecessor.id = NEW.predecessor_candidate_id
                  AND predecessor.person_id <> NEW.person_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'predecessor_candidate_person_mismatch');
            END
            """,
            """
            CREATE TRIGGER candidate_facts_predecessor_same_person_update
            BEFORE UPDATE OF person_id, predecessor_candidate_id ON candidate_facts
            WHEN NEW.predecessor_candidate_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM candidate_facts AS predecessor
                WHERE predecessor.id = NEW.predecessor_candidate_id
                  AND predecessor.person_id <> NEW.person_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'predecessor_candidate_person_mismatch');
            END
            """,
            "CREATE INDEX candidate_facts_person_status_idx ON candidate_facts(person_id, status)",
            (
                "CREATE INDEX canonical_records_person_active_idx "
                "ON canonical_records(person_id, is_active)"
            ),
            ("CREATE INDEX canonical_records_candidate_idx ON canonical_records(candidate_id)"),
            (
                "CREATE INDEX timeline_events_person_event_at_idx "
                "ON timeline_events(person_id, event_at, id)"
            ),
            (
                "CREATE INDEX visit_brief_evidence_revision_position_idx "
                "ON visit_brief_evidence_selections(revision_id, position)"
            ),
        ),
    ),
    Migration(
        version=8,
        statements=(
            "PRAGMA defer_foreign_keys=ON",
            """
            CREATE TABLE sources_v8 (
                id TEXT PRIMARY KEY,
                person_id TEXT NOT NULL REFERENCES people(person_id),
                source_type TEXT NOT NULL CHECK (
                    source_type IN ('manual_entry', 'plain_text', 'document')
                ),
                relative_path TEXT NOT NULL CHECK (length(trim(relative_path)) > 0),
                content_hash TEXT NOT NULL CHECK (
                    length(content_hash) = 64
                    AND content_hash = lower(content_hash)
                    AND content_hash NOT GLOB '*[^0-9a-f]*'
                ),
                size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
                media_type TEXT NOT NULL CHECK (length(trim(media_type)) > 0),
                created_at TEXT NOT NULL,
                provenance_json TEXT NOT NULL,
                original_filename TEXT,
                document_kind TEXT CHECK (document_kind IN ('pdf', 'text')),
                CHECK (
                    (source_type = 'document' AND document_kind IS NOT NULL)
                    OR (source_type <> 'document' AND document_kind IS NULL
                        AND original_filename IS NULL)
                ),
                UNIQUE (person_id, source_type, content_hash),
                UNIQUE (id, person_id)
            )
            """,
            """
            INSERT INTO sources_v8 (
                id, person_id, source_type, relative_path, content_hash, size_bytes,
                media_type, created_at, provenance_json, original_filename, document_kind
            )
            SELECT id, person_id, source_type, relative_path, content_hash, size_bytes,
                   media_type, created_at, provenance_json, NULL, NULL
            FROM sources
            """,
            "DROP TABLE sources",
            "ALTER TABLE sources_v8 RENAME TO sources",
            """
            CREATE TABLE document_extractions (
                extraction_id TEXT PRIMARY KEY CHECK (length(trim(extraction_id)) > 0),
                source_id TEXT NOT NULL,
                person_id TEXT NOT NULL,
                extractor TEXT NOT NULL CHECK (length(trim(extractor)) > 0),
                extractor_version TEXT NOT NULL CHECK (length(trim(extractor_version)) > 0),
                status TEXT NOT NULL CHECK (status = 'complete'),
                text_hash TEXT NOT NULL CHECK (
                    length(text_hash) = 64
                    AND text_hash = lower(text_hash)
                    AND text_hash NOT GLOB '*[^0-9a-f]*'
                ),
                total_chars INTEGER NOT NULL CHECK (
                    total_chars >= 0 AND total_chars <= 1000000
                ),
                page_count INTEGER NOT NULL CHECK (
                    page_count >= 1 AND page_count <= 200
                ),
                extracted_at TEXT NOT NULL,
                UNIQUE (source_id, extractor, extractor_version, text_hash),
                UNIQUE (extraction_id, source_id, person_id),
                FOREIGN KEY (source_id, person_id)
                    REFERENCES sources(id, person_id)
            )
            """,
            """
            CREATE TABLE document_extraction_pages (
                extraction_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                person_id TEXT NOT NULL,
                page_number INTEGER NOT NULL CHECK (
                    page_number >= 1 AND page_number <= 200
                ),
                normalized_text TEXT NOT NULL,
                decoded_content_bytes INTEGER NOT NULL CHECK (
                    decoded_content_bytes >= 0 AND decoded_content_bytes <= 200000
                ),
                extracted_chars INTEGER NOT NULL CHECK (
                    extracted_chars >= 0
                    AND extracted_chars <= 100000
                    AND extracted_chars = length(normalized_text)
                ),
                page_hash TEXT NOT NULL CHECK (
                    length(page_hash) = 64
                    AND page_hash = lower(page_hash)
                    AND page_hash NOT GLOB '*[^0-9a-f]*'
                ),
                PRIMARY KEY (extraction_id, page_number),
                FOREIGN KEY (extraction_id, source_id, person_id)
                    REFERENCES document_extractions(extraction_id, source_id, person_id)
            )
            """,
            """
            CREATE TRIGGER document_extractions_source_type_insert
            BEFORE INSERT ON document_extractions
            WHEN NOT EXISTS (
                SELECT 1 FROM sources
                WHERE id = NEW.source_id
                  AND person_id = NEW.person_id
                  AND source_type = 'document'
            )
            BEGIN
                SELECT RAISE(ABORT, 'document_extraction_source_mismatch');
            END
            """,
            """
            CREATE TRIGGER document_extractions_immutable_update
            BEFORE UPDATE ON document_extractions
            BEGIN
                SELECT RAISE(ABORT, 'document_extraction_immutable');
            END
            """,
            """
            CREATE TRIGGER document_extractions_immutable_delete
            BEFORE DELETE ON document_extractions
            BEGIN
                SELECT RAISE(ABORT, 'document_extraction_immutable');
            END
            """,
            """
            CREATE TRIGGER document_extraction_pages_immutable_update
            BEFORE UPDATE ON document_extraction_pages
            BEGIN
                SELECT RAISE(ABORT, 'document_extraction_page_immutable');
            END
            """,
            """
            CREATE TRIGGER document_extraction_pages_immutable_delete
            BEFORE DELETE ON document_extraction_pages
            BEGIN
                SELECT RAISE(ABORT, 'document_extraction_page_immutable');
            END
            """,
            """
            CREATE INDEX document_extractions_person_source_idx
            ON document_extractions(person_id, source_id, extracted_at, extraction_id)
            """,
            """
            CREATE INDEX document_extraction_pages_source_idx
            ON document_extraction_pages(person_id, source_id, extraction_id, page_number)
            """,
        ),
    ),
    Migration(
        version=9,
        statements=(
            "PRAGMA defer_foreign_keys=ON",
            """
            CREATE TABLE sources_v9 (
                id TEXT PRIMARY KEY,
                person_id TEXT NOT NULL REFERENCES people(person_id),
                source_type TEXT NOT NULL CHECK (
                    source_type IN ('manual_entry', 'plain_text', 'document', 'genetics')
                ),
                relative_path TEXT NOT NULL CHECK (length(trim(relative_path)) > 0),
                content_hash TEXT NOT NULL CHECK (
                    length(content_hash) = 64
                    AND content_hash = lower(content_hash)
                    AND content_hash NOT GLOB '*[^0-9a-f]*'
                ),
                size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
                media_type TEXT NOT NULL CHECK (length(trim(media_type)) > 0),
                created_at TEXT NOT NULL,
                provenance_json TEXT NOT NULL,
                original_filename TEXT,
                document_kind TEXT CHECK (document_kind IN ('pdf', 'text')),
                CHECK (
                    (source_type = 'document' AND document_kind IS NOT NULL)
                    OR (source_type <> 'document' AND document_kind IS NULL
                        AND (source_type <> 'genetics' OR original_filename IS NOT NULL))
                ),
                UNIQUE (person_id, source_type, content_hash),
                UNIQUE (id, person_id)
            )
            """,
            """
            INSERT INTO sources_v9 (
                id, person_id, source_type, relative_path, content_hash, size_bytes,
                media_type, created_at, provenance_json, original_filename, document_kind
            )
            SELECT id, person_id, source_type, relative_path, content_hash, size_bytes,
                   media_type, created_at, provenance_json, original_filename, document_kind
            FROM sources
            """,
            "DROP TRIGGER document_extractions_source_type_insert",
            "DROP TABLE sources",
            "ALTER TABLE sources_v9 RENAME TO sources",
            """
            CREATE TRIGGER document_extractions_source_type_insert
            BEFORE INSERT ON document_extractions
            WHEN NOT EXISTS (
                SELECT 1 FROM sources
                WHERE id = NEW.source_id
                  AND person_id = NEW.person_id
                  AND source_type = 'document'
            )
            BEGIN
                SELECT RAISE(ABORT, 'document_extraction_source_mismatch');
            END
            """,
            """
            CREATE TABLE genetic_access_grants (
                grant_id TEXT PRIMARY KEY CHECK (length(trim(grant_id)) > 0),
                actor_id TEXT NOT NULL REFERENCES actors(actor_id),
                person_id TEXT NOT NULL REFERENCES people(person_id),
                scopes_json TEXT NOT NULL,
                consent_confirmed INTEGER NOT NULL CHECK (consent_confirmed IN (0, 1)),
                granted_by_actor_id TEXT NOT NULL REFERENCES actors(actor_id),
                created_at TEXT NOT NULL,
                revoked_at TEXT,
                CHECK (json_valid(scopes_json)),
                UNIQUE (actor_id, person_id, created_at)
            )
            """,
            """
            CREATE TABLE genetic_datasets (
                dataset_id TEXT PRIMARY KEY CHECK (length(trim(dataset_id)) > 0),
                person_id TEXT NOT NULL REFERENCES people(person_id),
                source_id TEXT NOT NULL,
                source_hash TEXT NOT NULL CHECK (
                    length(source_hash) = 64
                    AND source_hash = lower(source_hash)
                    AND source_hash NOT GLOB '*[^0-9a-f]*'
                ),
                format TEXT NOT NULL CHECK (format = 'consumer_genotype'),
                original_filename TEXT NOT NULL CHECK (length(trim(original_filename)) > 0),
                genome_build TEXT NOT NULL CHECK (
                    genome_build IN ('GRCh37/hg19', 'GRCh38/hg38', 'unknown')
                ),
                parser TEXT NOT NULL CHECK (length(trim(parser)) > 0),
                parser_version TEXT NOT NULL CHECK (length(trim(parser_version)) > 0),
                imported_at TEXT NOT NULL,
                parsed_loci_count INTEGER NOT NULL CHECK (parsed_loci_count >= 0),
                indexed_loci_count INTEGER NOT NULL CHECK (indexed_loci_count >= 0),
                metadata_json TEXT NOT NULL CHECK (json_valid(metadata_json)),
                UNIQUE (dataset_id, person_id),
                UNIQUE (source_id, person_id),
                FOREIGN KEY (source_id, person_id) REFERENCES sources(id, person_id)
            )
            """,
            """
            CREATE TABLE genetic_variant_observations (
                observation_id TEXT PRIMARY KEY CHECK (length(trim(observation_id)) > 0),
                dataset_id TEXT NOT NULL,
                person_id TEXT NOT NULL REFERENCES people(person_id),
                rsid TEXT,
                chromosome TEXT NOT NULL CHECK (length(trim(chromosome)) > 0),
                position INTEGER NOT NULL CHECK (position > 0),
                reported_genotype TEXT NOT NULL CHECK (length(reported_genotype) > 0),
                normalized_genotype TEXT NOT NULL CHECK (length(normalized_genotype) > 0),
                no_call INTEGER NOT NULL CHECK (no_call IN (0, 1)),
                genome_build TEXT NOT NULL CHECK (
                    genome_build IN ('GRCh37/hg19', 'GRCh38/hg38', 'unknown')
                ),
                orientation_state TEXT NOT NULL CHECK (
                    orientation_state IN ('resolved', 'unresolved', 'ambiguous', 'not_applicable')
                ),
                coverage_state TEXT NOT NULL CHECK (
                    coverage_state IN ('present', 'no_call', 'indexed')
                ),
                source_locator_json TEXT NOT NULL CHECK (json_valid(source_locator_json)),
                UNIQUE (dataset_id, rsid, chromosome, position),
                FOREIGN KEY (dataset_id, person_id)
                    REFERENCES genetic_datasets(dataset_id, person_id)
            )
            """,
            """
            CREATE TABLE genetic_evidence_entries (
                evidence_entry_id TEXT PRIMARY KEY CHECK (length(trim(evidence_entry_id)) > 0),
                pack_id TEXT NOT NULL CHECK (length(trim(pack_id)) > 0),
                pack_version TEXT NOT NULL CHECK (length(trim(pack_version)) > 0),
                evidence_id TEXT NOT NULL CHECK (length(trim(evidence_id)) > 0),
                rsid TEXT,
                chromosome TEXT,
                position INTEGER CHECK (position IS NULL OR position > 0),
                gene TEXT,
                genome_build TEXT NOT NULL CHECK (
                    genome_build IN ('GRCh37/hg19', 'GRCh38/hg38', 'unknown')
                ),
                genotype_condition TEXT NOT NULL CHECK (length(trim(genotype_condition)) > 0),
                category TEXT NOT NULL CHECK (length(trim(category)) > 0),
                title TEXT NOT NULL CHECK (length(trim(title)) > 0),
                association TEXT NOT NULL CHECK (length(trim(association)) > 0),
                effect_direction TEXT,
                evidence_level TEXT NOT NULL CHECK (
                    evidence_level IN ('Clinical', 'High', 'Moderate', 'Low', 'Exploratory', 'Conflicting')
                ),
                source_name TEXT NOT NULL CHECK (length(trim(source_name)) > 0),
                source_citation TEXT NOT NULL CHECK (length(trim(source_citation)) > 0),
                source_url TEXT,
                source_version_date TEXT,
                limitations_json TEXT NOT NULL CHECK (json_valid(limitations_json)),
                orientation_metadata TEXT NOT NULL CHECK (length(trim(orientation_metadata)) > 0),
                tags_json TEXT NOT NULL CHECK (json_valid(tags_json)),
                UNIQUE (pack_id, pack_version, evidence_id)
            )
            """,
            """
            CREATE TABLE genetic_findings (
                finding_id TEXT PRIMARY KEY CHECK (length(trim(finding_id)) > 0),
                person_id TEXT NOT NULL REFERENCES people(person_id),
                observation_id TEXT NOT NULL REFERENCES genetic_variant_observations(observation_id),
                evidence_entry_id TEXT NOT NULL
                    REFERENCES genetic_evidence_entries(evidence_entry_id),
                status TEXT NOT NULL CHECK (
                    status IN ('pending', 'reviewed', 'dismissed', 'unsupported', 'conflicting')
                ),
                category TEXT NOT NULL CHECK (length(trim(category)) > 0),
                evidence_level TEXT NOT NULL CHECK (
                    evidence_level IN ('Clinical', 'High', 'Moderate', 'Low', 'Exploratory', 'Conflicting')
                ),
                title TEXT NOT NULL CHECK (length(trim(title)) > 0),
                gene TEXT,
                association TEXT NOT NULL CHECK (length(trim(association)) > 0),
                provenance_json TEXT NOT NULL CHECK (json_valid(provenance_json)),
                created_at TEXT NOT NULL,
                reviewed_at TEXT,
                UNIQUE (observation_id, evidence_entry_id)
            )
            """,
            """
            CREATE TABLE genetic_finding_reviews (
                review_id TEXT PRIMARY KEY CHECK (length(trim(review_id)) > 0),
                finding_id TEXT NOT NULL REFERENCES genetic_findings(finding_id),
                person_id TEXT NOT NULL REFERENCES people(person_id),
                actor_id TEXT NOT NULL REFERENCES actors(actor_id),
                prior_status TEXT NOT NULL,
                new_status TEXT NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE genetics_research_sessions (
                session_id TEXT PRIMARY KEY CHECK (length(trim(session_id)) > 0),
                person_id TEXT NOT NULL REFERENCES people(person_id),
                actor_id TEXT NOT NULL REFERENCES actors(actor_id),
                mode TEXT NOT NULL CHECK (mode IN ('evidence', 'explore')),
                question TEXT NOT NULL CHECK (length(trim(question)) > 0),
                selected_context_json TEXT NOT NULL CHECK (json_valid(selected_context_json)),
                provider_class TEXT NOT NULL CHECK (length(trim(provider_class)) > 0),
                disclosure_consent_id TEXT,
                context_hash TEXT NOT NULL CHECK (length(context_hash) = 64),
                validation_result TEXT NOT NULL CHECK (
                    validation_result IN ('accepted', 'rejected')
                ),
                output_json TEXT NOT NULL CHECK (json_valid(output_json)),
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE genetics_research_claims (
                claim_id TEXT PRIMARY KEY CHECK (length(trim(claim_id)) > 0),
                session_id TEXT NOT NULL REFERENCES genetics_research_sessions(session_id),
                person_id TEXT NOT NULL REFERENCES people(person_id),
                claim_text TEXT NOT NULL CHECK (length(trim(claim_text)) > 0),
                epistemic_status TEXT NOT NULL CHECK (
                    epistemic_status IN (
                        'observed', 'supported', 'plausible', 'speculative',
                        'unsupported/conflicting'
                    )
                ),
                supporting_evidence_json TEXT NOT NULL CHECK (json_valid(supporting_evidence_json)),
                contradicting_evidence_json TEXT NOT NULL CHECK (
                    json_valid(contradicting_evidence_json)
                ),
                person_record_ids_json TEXT NOT NULL CHECK (json_valid(person_record_ids_json)),
                reasoning_summary TEXT NOT NULL,
                limitations_json TEXT NOT NULL CHECK (json_valid(limitations_json)),
                missing_information_json TEXT NOT NULL CHECK (json_valid(missing_information_json)),
                lifecycle TEXT NOT NULL CHECK (lifecycle IN ('kept', 'dismissed')),
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TRIGGER genetic_datasets_immutable_update
            BEFORE UPDATE ON genetic_datasets
            BEGIN
                SELECT RAISE(ABORT, 'genetic_dataset_immutable');
            END
            """,
            """
            CREATE TRIGGER genetic_datasets_immutable_delete
            BEFORE DELETE ON genetic_datasets
            BEGIN
                SELECT RAISE(ABORT, 'genetic_dataset_immutable');
            END
            """,
            """
            CREATE TRIGGER genetic_observations_immutable_update
            BEFORE UPDATE ON genetic_variant_observations
            BEGIN
                SELECT RAISE(ABORT, 'genetic_observation_immutable');
            END
            """,
            """
            CREATE TRIGGER genetic_observations_immutable_delete
            BEFORE DELETE ON genetic_variant_observations
            BEGIN
                SELECT RAISE(ABORT, 'genetic_observation_immutable');
            END
            """,
            "CREATE INDEX genetic_datasets_person_import_idx ON genetic_datasets(person_id, imported_at)",
            (
                "CREATE INDEX genetic_observations_person_locus_idx ON "
                "genetic_variant_observations(person_id, chromosome, position, rsid)"
            ),
            (
                "CREATE INDEX genetic_findings_person_status_idx ON "
                "genetic_findings(person_id, status, evidence_level)"
            ),
            (
                "CREATE INDEX genetics_research_sessions_person_created_idx ON "
                "genetics_research_sessions(person_id, created_at)"
            ),
            (
                "CREATE INDEX genetic_access_grants_actor_person_active_idx ON "
                "genetic_access_grants(actor_id, person_id, revoked_at)"
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
        if migration.version in {8, 9}:
            # SQLite cannot rebuild a referenced parent table while foreign-key
            # enforcement is active, even when all final references are valid.
            connection.execute("PRAGMA foreign_keys=OFF")
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
            foreign_key_violations = connection.execute("PRAGMA foreign_key_check").fetchall()
            if foreign_key_violations:
                raise sqlite3.IntegrityError("migration left foreign key violations")
            connection.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (migration.version, applied_at),
            )
            connection.commit()
            if migration.version in {8, 9}:
                connection.execute("PRAGMA foreign_keys=ON")
        except BaseException:
            connection.rollback()
            if migration.version in {8, 9}:
                connection.execute("PRAGMA foreign_keys=ON")
            raise
