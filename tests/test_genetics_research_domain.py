import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.genetics.comparison import compare_ibs
from app.genetics.consumer import parse_consumer_genotypes
from app.genetics.evidence import assess_evidence, intersect_pgx_medications, load_genetics_evidence_pack
from app.genetics.models import (
    CoverageState,
    EpistemicStatus,
    GenomeBuild,
    OrientationState,
    ResearchMode,
)
from app.genetics.research import (
    ResearchClaim,
    ResearchOutput,
    build_research_packet,
    validate_research_output,
)


PACK_PATH = Path("data/evidence_packs/genetics_demo_pack.json")


def synthetic_input(*rows: str):
    body = "# rsid\tchromosome\tposition\tgenotype\n" + "\n".join(rows)
    return body.encode("utf-8")


def test_import_normalizes_no_call_and_selects_only_requested_loci() -> None:
    result = parse_consumer_genotypes(
        synthetic_input("rsDemoA\t1\t101\tta", "rsDemoB\t2\t202\t--", "rsIgnored\t3\t303\tGG"),
        genome_build=GenomeBuild.GRCH37,
        selected_rsids={"rsDemoA", "rsDemoB"},
    )

    assert result.parsed_locus_count == 3
    assert [item.rsid for item in result.observations] == ["rsDemoA", "rsDemoB"]
    assert result.observations[0].normalized_genotype == "AT"
    assert result.observations[0].orientation is OrientationState.AMBIGUOUS
    assert result.observations[1].no_call is True
    assert result.observations[1].normalized_genotype is None
    assert "raw" not in result.model_dump_json().lower()


def test_evidence_assessment_fails_closed_for_absent_no_call_build_and_orientation() -> None:
    pack = load_genetics_evidence_pack(PACK_PATH)
    imported = parse_consumer_genotypes(
        synthetic_input("rsDemoPGX\t10\t1001\tAG", "rsDemoNoCall\t11\t1101\t--", "rsDemoAmbiguous\t12\t1201\tAT"),
        genome_build=GenomeBuild.GRCH37,
        selected_rsids=set(entry.rsid for entry in pack.entries if entry.rsid),
    )

    results = {result.evidence_id: result for result in assess_evidence(imported.observations, pack)}
    assert results["ev-absent"].coverage is CoverageState.NOT_PRESENT
    assert results["ev-no-call"].coverage is CoverageState.NO_CALL
    assert results["ev-build-mismatch"].coverage is CoverageState.BUILD_INCOMPATIBLE
    assert results["ev-orientation"].coverage is CoverageState.UNRESOLVED
    assert all(results[key].finding is None for key in ("ev-absent", "ev-no-call", "ev-build-mismatch", "ev-orientation"))
    assert results["ev-pgx"].coverage is CoverageState.PRESENT
    assert results["ev-pgx"].finding is not None


def test_research_packet_is_selective_deterministic_and_contains_no_raw_bytes() -> None:
    pack = load_genetics_evidence_pack(PACK_PATH)
    imported = parse_consumer_genotypes(
        synthetic_input("rsDemoPGX\t10\t1001\tAG", "rsIgnored\t3\t303\tGG"),
        genome_build=GenomeBuild.GRCH37,
        selected_rsids={"rsDemoPGX", "rsIgnored"},
    )
    finding = next(result.finding for result in assess_evidence(imported.observations, pack) if result.finding)

    packet = build_research_packet(
        person_id="person-synthetic-a",
        mode=ResearchMode.EXPLORE,
        observations=imported.observations,
        evidence_entries=pack.entries,
        findings=(finding,),
        selected_observation_ids={imported.observations[0].observation_id},
        selected_evidence_ids={"ev-pgx"},
        selected_finding_ids={finding.finding_id},
        selected_health_records={"med-synthetic": {"kind": "medication", "name": "DemoMed"}},
    )

    encoded = packet.model_dump_json()
    assert "rsIgnored" not in encoded
    assert set(packet.selected_evidence) == {"ev-pgx"}
    assert packet.context_hash == build_research_packet(
        person_id="person-synthetic-a",
        mode=ResearchMode.EXPLORE,
        observations=imported.observations,
        evidence_entries=pack.entries,
        findings=(finding,),
        selected_observation_ids={imported.observations[0].observation_id},
        selected_evidence_ids={"ev-pgx"},
        selected_finding_ids={finding.finding_id},
        selected_health_records={"med-synthetic": {"kind": "medication", "name": "DemoMed"}},
    ).context_hash
    assert "raw" not in encoded.lower()


def test_ibs_zero_common_fails_closed() -> None:
    left = parse_consumer_genotypes(
        synthetic_input("rsLeft\t1\t101\tAA"), genome_build=GenomeBuild.GRCH37, selected_rsids={"rsLeft"}
    ).observations
    right = parse_consumer_genotypes(
        synthetic_input("rsRight\t2\t202\tGG"), genome_build=GenomeBuild.GRCH37, selected_rsids={"rsRight"}
    ).observations

    comparison = compare_ibs(left, right)
    assert comparison.common_loci == 0
    assert comparison.similarity is None
    assert comparison.insufficient_coverage is True


def valid_output(**claim_overrides: object) -> ResearchOutput:
    claim = {
        "claim": "A synthetic association may be worth discussing.",
        "epistemic_status": EpistemicStatus.PLAUSIBLE,
        "supporting_evidence_ids": ["ev-pgx"],
        "contradicting_evidence_ids": [],
        "person_record_ids": ["med-synthetic"],
        "reasoning_summary": "The selected synthetic evidence supports a limited association.",
        "limitations": ["Synthetic evidence only."],
        "missing_information": ["Independent confirmation."],
    }
    claim.update(claim_overrides)
    return ResearchOutput(
        what_may_be_happening="A bounded synthetic hypothesis.",
        evidence_supporting_it=["ev-pgx"],
        evidence_against_it=["No contradictory selected evidence."],
        alternative_explanations=["The marker may not explain the observation."],
        missing_information=["Independent confirmation."],
        confidence_epistemic_status=EpistemicStatus.PLAUSIBLE,
        questions_worth_investigating=["What evidence would change this interpretation?"],
        claims=[ResearchClaim(**claim)],
    )


def test_output_validation_rejects_invented_citations_and_requires_devil_advocate_sections() -> None:
    packet = _packet_for_validation()
    with pytest.raises(ValueError, match="unauthorized evidence"):
        validate_research_output(valid_output(supporting_evidence_ids=["ev-invented"]), packet)

    with pytest.raises(ValidationError):
        ResearchOutput.model_validate({
            **valid_output().model_dump(),
            "evidence_against_it": [],
            "alternative_explanations": [],
        })


def test_speculative_model_background_must_be_explicitly_labelled() -> None:
    packet = _packet_for_validation()
    with pytest.raises(ValueError, match="model-background"):
        validate_research_output(valid_output(model_background=True, epistemic_status=EpistemicStatus.SUPPORTED), packet)

    validate_research_output(
        valid_output(model_background=True, epistemic_status=EpistemicStatus.SPECULATIVE), packet
    )


def test_pgx_intersection_uses_exact_normalized_confirmed_medications_only() -> None:
    pack = load_genetics_evidence_pack(PACK_PATH)
    imported = parse_consumer_genotypes(
        synthetic_input("rsDemoPGX\t10\t1001\tAG"),
        genome_build=GenomeBuild.GRCH37,
        selected_rsids={"rsDemoPGX"},
    )
    finding = next(result.finding for result in assess_evidence(imported.observations, pack) if result.finding)

    matches = intersect_pgx_medications(
        findings=(finding,),
        evidence_entries=pack.entries,
        confirmed_normalized_medications=("demomed", "DemoMed Extended", "unconfirmed-demo"),
    )
    assert [(match.medication_name, match.evidence_id) for match in matches] == [("demomed", "ev-pgx")]


def _packet_for_validation():
    pack = load_genetics_evidence_pack(PACK_PATH)
    imported = parse_consumer_genotypes(
        synthetic_input("rsDemoPGX\t10\t1001\tAG"), genome_build=GenomeBuild.GRCH37, selected_rsids={"rsDemoPGX"}
    )
    finding = next(result.finding for result in assess_evidence(imported.observations, pack) if result.finding)
    return build_research_packet(
        person_id="person-synthetic-a",
        mode=ResearchMode.EXPLORE,
        observations=imported.observations,
        evidence_entries=pack.entries,
        findings=(finding,),
        selected_observation_ids={imported.observations[0].observation_id},
        selected_evidence_ids={"ev-pgx"},
        selected_finding_ids={finding.finding_id},
        selected_health_records={"med-synthetic": {"kind": "medication", "name": "DemoMed"}},
    )
