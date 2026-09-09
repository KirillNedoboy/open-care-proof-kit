"""Offline, network-forbidden tests for the AlphaGenome connector foundation."""

from __future__ import annotations

import ast
import json
import math
import socket
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import app.scientific_evidence as se
from app.scientific_evidence.alphagenome_atlas import (
    AVI_SCORE,
    AVI_SCORE_FEATURE_IMPORTANCE,
    AlphaGenomeAtlasConnector,
    AlphaGenomeEvidenceResult,
    AlphaGenomeEvidenceValidationError,
    normalize_atlas_response,
)
from app.scientific_evidence.contracts import (
    SelectedVariantQuery,
    UnsupportedGenomeBuildError,
)

RETRIEVED_AT = datetime(2026, 9, 9, 12, 0, 0, tzinfo=UTC)
PKG_DIR = Path(se.__file__).parent


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Socket guard: any network use in this suite is a hard failure."""

    def _blocked(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("network access is forbidden in these tests")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


def query(**overrides: Any) -> SelectedVariantQuery:
    payload: dict[str, Any] = {
        "genome_build": "GRCh38",
        "chromosome": "chr22",
        "position": 36201698,
        "reference": "A",
        "alternate": "C",
    }
    payload.update(overrides)
    return SelectedVariantQuery(**payload)


def response(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "variant": "chr22:36201698:A>C",
        "assembly": "GRCh38",
        "avi_raw": 0.87,
        "avi_phred": 29.7,
        "avi_quantile": 0.99989,
        "top_percentile": 0.1071,
        "top_modality": "Splicing",
        "top_feature_importance": 0.62,
    }
    payload.update(overrides)
    return payload


def normalize(**overrides: Any) -> AlphaGenomeEvidenceResult:
    return normalize_atlas_response(
        response(**overrides),
        request=query(),
        retrieved_at=RETRIEVED_AT,
        response_schema_version="test-v1",
    )


class FakeTransport:
    """Deterministic fake; records payloads, returns a canned record."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.seen: list[dict[str, str]] = []

    def fetch_variant_scores(self, payload: dict[str, str]) -> dict[str, Any]:
        self.seen.append(dict(payload))
        return dict(self.payload)


# --- SelectedVariantQuery ----------------------------------------------------


def test_valid_snv_request() -> None:
    q = query()
    assert q.variant_string == "chr22:36201698:A>C"


def test_reference_equals_alternate_rejected() -> None:
    with pytest.raises(ValidationError, match="reference_equals_alternate"):
        query(alternate="A")


def test_non_acgt_rejected() -> None:
    with pytest.raises(ValidationError, match="invalid_base"):
        query(reference="N")
    with pytest.raises(ValidationError, match="invalid_base"):
        query(alternate="a")


def test_multibase_reference_rejected() -> None:
    with pytest.raises(ValidationError, match="invalid_base"):
        query(reference="AC")


def test_multibase_alternate_rejected() -> None:
    with pytest.raises(ValidationError, match="invalid_base"):
        query(alternate="GGT")


def test_nonpositive_position_rejected() -> None:
    with pytest.raises(ValidationError):
        query(position=0)
    with pytest.raises(ValidationError):
        query(position=-5)


def test_unknown_build_fails_closed_without_liftover() -> None:
    with pytest.raises(UnsupportedGenomeBuildError) as excinfo:
        query(genome_build="hg19")
    assert excinfo.value.reason == "unsupported_genome_build"


def test_serialized_query_is_minimized_variant_data_only() -> None:
    payload = query().to_transport_request()
    assert set(payload) == {"variant", "assembly"}
    assert payload == {"variant": "chr22:36201698:A>C", "assembly": "GRCh38"}
    dumped = json.loads(query().model_dump_json())
    assert set(dumped) == {
        "genome_build",
        "chromosome",
        "position",
        "reference",
        "alternate",
        "provenance_reference",
    }


def test_raw_genome_sentinel_never_leaves_into_request() -> None:
    sentinel = "RAWGENOMESENTINELACGTACGT" * 10
    q = query(provenance_reference="opaque-ref-1")
    assert sentinel not in q.variant_string
    assert sentinel not in json.dumps(q.to_transport_request())
    assert sentinel not in q.model_dump_json()


def test_query_cannot_carry_pii_or_extra_payload() -> None:
    assert {
        "genome_build",
        "chromosome",
        "position",
        "reference",
        "alternate",
        "provenance_reference",
    } == set(SelectedVariantQuery.model_fields)
    for forbidden in ("person_id", "name", "date_of_birth", "genotype", "vcf"):
        with pytest.raises(ValidationError):
            query(**{forbidden: "x"})


# --- Normalizer ---------------------------------------------------------------


def test_valid_atlas_result_normalizes() -> None:
    result = normalize()
    assert result.variant == "chr22:36201698:A>C"
    assert result.avi_phred == pytest.approx(29.7)
    assert result.avi_quantile == pytest.approx(0.99989)
    assert result.top_modality == "Splicing"
    assert result.requested_scorers == (AVI_SCORE,)


def test_queried_result_mismatch_rejected() -> None:
    with pytest.raises(
        AlphaGenomeEvidenceValidationError, match="queried_result_variant_mismatch"
    ):
        normalize(variant="chr22:99999999:A>C")


def test_missing_avi_identity_rejected() -> None:
    with pytest.raises(AlphaGenomeEvidenceValidationError, match="missing_avi_raw"):
        normalize(avi_raw=None)
    with pytest.raises(AlphaGenomeEvidenceValidationError):
        normalize_atlas_response(
            {}, request=query(), retrieved_at=RETRIEVED_AT, response_schema_version="t"
        )


def test_malformed_variant_identity_rejected() -> None:
    for bad in ("22:36201698:A>C", "chr22:0:A>C", "chr22:36201698:AC>C", "chrZZ:5:A>C"):
        with pytest.raises(AlphaGenomeEvidenceValidationError):
            normalize(variant=bad)


def test_non_finite_scores_rejected() -> None:
    for bad in (math.nan, math.inf, -math.inf):
        with pytest.raises(AlphaGenomeEvidenceValidationError, match="non_finite"):
            normalize(avi_raw=bad)


def test_out_of_range_quantile_percentile_phred_rejected() -> None:
    with pytest.raises(AlphaGenomeEvidenceValidationError, match="score_out_of"):
        normalize(avi_quantile=1.5)
    with pytest.raises(AlphaGenomeEvidenceValidationError, match="score_out_of"):
        normalize(top_percentile=101.0)
    with pytest.raises(AlphaGenomeEvidenceValidationError, match="score_out_of"):
        normalize(avi_phred=75.0)


def test_unexpected_build_rejected() -> None:
    with pytest.raises(AlphaGenomeEvidenceValidationError, match="unexpected_genome_build"):
        normalize(assembly="hg19")


def test_bounded_attribution_parsing() -> None:
    result = normalize(
        top_modality="Splicing",
        fi_MERGED_SPLICING=0.62,
        fi_ALPHAMISSENSE=-0.11,
    )
    assert {(a.modality, a.importance) for a in result.feature_attributions} == {
        ("MERGED_SPLICING", 0.62),
        ("ALPHAMISSENSE", -0.11),
    }
    assert result.requested_scorers == (AVI_SCORE, AVI_SCORE_FEATURE_IMPORTANCE)
    with pytest.raises(
        AlphaGenomeEvidenceValidationError, match="unknown_attribution_modality"
    ):
        normalize(fi_NOT_A_MODALITY=0.5)
    with pytest.raises(
        AlphaGenomeEvidenceValidationError, match="malformed_attribution_value"
    ):
        normalize(fi_MERGED_SPLICING="high")
    with pytest.raises(
        AlphaGenomeEvidenceValidationError, match="non_finite_attribution_value"
    ):
        normalize(fi_MERGED_SPLICING=math.nan)


def test_oversized_response_collections_rejected() -> None:
    # Only 18 documented modalities exist, so documented keys alone can never
    # overflow; a bogus 19th key sorting LAST trips the collection bound
    # (checked before the unknown-modality rejection).
    wide = {
        f"fi_{modality}": 0.1 for modality in sorted(MODALITIES_FOR_OVERFLOW(18))
    }
    wide["fi_ZZZ_NOT_A_REAL_MODALITY"] = 0.1
    assert len(wide) == 19
    with pytest.raises(
        AlphaGenomeEvidenceValidationError, match="attribution_collection_overflow"
    ):
        normalize(**wide)


def MODALITIES_FOR_OVERFLOW(count: int) -> list[str]:
    from app.scientific_evidence.alphagenome_atlas import DOCUMENTED_FEATURE_MODALITIES

    return sorted(DOCUMENTED_FEATURE_MODALITIES)[:count]


def test_partial_quantile_layer_not_fabricated() -> None:
    # No calibrated layer at all: typed Nones, never fabricated zeros.
    result = normalize(avi_phred=None, avi_quantile=None, top_percentile=None)
    assert (result.avi_phred, result.avi_quantile, result.top_percentile) == (
        None,
        None,
        None,
    )
    with pytest.raises(AlphaGenomeEvidenceValidationError, match="score_out_of"):
        normalize(avi_quantile=None)  # phred present, quantile absent


# --- Usage/semantics boundaries -------------------------------------------------


def test_research_only_always_true_and_clinical_never_allowed() -> None:
    descriptor = se.ATLAS_CONNECTOR_DESCRIPTOR
    assert descriptor.research_only is True
    assert descriptor.clinical_use_allowed is False
    assert descriptor.external is True
    assert descriptor.requires_api_key is True
    result = normalize()
    assert result.usage_policy.usage_class == "research_only"
    assert result.usage_policy.clinical_decision_support is False
    assert result.usage_policy.medical_advice is False
    assert result.usage_policy.diagnosis is False
    assert result.score_semantics.is_pathogenicity_truth is False
    assert result.score_semantics.measures == "predicted_molecular_functional_impact"


@pytest.mark.parametrize(
    "model", [AlphaGenomeEvidenceResult, SelectedVariantQuery, se.ConnectorDescriptor]
)
def test_no_clinical_label_or_api_key_fields_anywhere(model: Any) -> None:
    names = {name.lower() for name in model.model_fields}
    assert not any(
        forbidden in name
        for name in names
        for forbidden in ("pathogenic", "benign", "vus")
    )
    # Credential fields are forbidden by exact name; ConnectorDescriptor's
    # ``requires_api_key`` boolean capability flag is not credential storage.
    assert not (names & {"api_key", "secret", "token", "credential"})


def test_api_key_absent_from_serialization() -> None:
    result = normalize()
    dumped = json.dumps(result.model_dump(mode="json"))
    assert "api_key" not in dumped.lower()
    assert "ALPHAGENOME_API_KEY" not in dumped
    descriptor = se.ATLAS_CONNECTOR_DESCRIPTOR
    descriptor_dump = json.dumps(descriptor.model_dump(mode="json"))
    assert "ALPHAGENOME_API_KEY" not in descriptor_dump

    def _keys(value: Any) -> set[str]:
        if isinstance(value, dict):
            return set(value) | {k for v in value.values() for k in _keys(v)}
        if isinstance(value, (list, tuple)):
            return {k for item in value for k in _keys(item)}
        return set()

    for payload in (result.model_dump(mode="json"), descriptor.model_dump(mode="json")):
        assert not (_keys(payload) & {"api_key", "secret", "token"})


# --- Transport/connector ------------------------------------------------------------


def test_fake_transport_is_deterministic_and_minimized() -> None:
    transport = FakeTransport(response())
    connector = AlphaGenomeAtlasConnector(transport)
    first = connector.query_variant(query())
    second = connector.query_variant(query())
    assert transport.seen[0] == {"variant": "chr22:36201698:A>C", "assembly": "GRCh38"}
    assert len(transport.seen) == 2
    assert first.variant == second.variant
    assert first.avi_phred == second.avi_phred
    assert first.usage_policy == second.usage_policy


def test_socket_guard_blocks_transport_attempts() -> None:
    with pytest.raises(AssertionError, match="network access is forbidden"):
        socket.create_connection(("alphagenome.example", 443))


# --- Import boundaries ----------------------------------------------------------------


def test_package_never_imports_forbidden_runtime_layers() -> None:
    forbidden_prefixes = (
        "app.product_core",
        "app.family_access",
        "fastapi",
        "sqlite3",
        "SessionStore",
    )
    for path in sorted(PKG_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                assert not any(
                    module == prefix or module.startswith(f"{prefix}.")
                    for prefix in forbidden_prefixes
                ), f"{path.name} imports forbidden module {module}"
