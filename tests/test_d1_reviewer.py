"""Focused contract test for the deterministic offline D1 reviewer."""

from __future__ import annotations

import subprocess
import sys

EXPECTED_STDOUT = """D1 REVIEW
source integrity: pass
PDF/TXT extraction: pass
v3 document access: pass
legacy isolation: pass
page/span provenance: pass
review lifecycle: pass
person isolation: pass
revocation: pass
agent raw-document isolation: pass
export/recovery: pass
counter cross_person_document_exposures: 0
counter legacy_document_scope_expansions: 0
counter unauthorized_document_writes: 0
counter provenance_span_mismatches_accepted: 0
counter unreviewed_document_canonicalizations: 0
counter raw_document_agent_disclosures: 0
counter corrupted_document_sources_accepted: 0
counter corrupted_extractions_accepted: 0
result: PASS
"""


def test_d1_reviewer_is_deterministic_offline_and_zero_exposure() -> None:
    first = subprocess.run(
        [sys.executable, "-m", "evals.d1_review"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    second = subprocess.run(
        [sys.executable, "-m", "evals.d1_review"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert first.returncode == 0, first.stdout + first.stderr
    assert first.stdout == EXPECTED_STDOUT
    assert second.stdout == first.stdout
    assert second.stderr == first.stderr == ""
