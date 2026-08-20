"""Deterministic offline reviewer for the P3 Genetics Research Studio contract."""

from __future__ import annotations

# ruff: noqa: E501
import json
from pathlib import Path

from app.genetics.comparison import compare_ibs
from app.genetics.consumer import parse_consumer_genotypes
from app.genetics.evidence import (
    assess_evidence,
    intersect_pgx_medications,
    load_genetics_evidence_pack,
    summarize_coverage,
)
from app.genetics.models import EpistemicStatus, GenomeBuild, ResearchMode
from app.genetics.research import (
    ResearchClaim,
    ResearchOutput,
    build_research_packet,
    validate_research_output,
)

PACK_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "evidence_packs" / "genetics_demo_pack.json"
)


def _input(*rows: str) -> bytes:
    return ("# synthetic only\n" + "\n".join(rows)).encode("utf-8")


def _run() -> dict[str, object]:
    counters = {
        "cross_person_genetics_exposures": 0,
        "hidden_genetics_dataset_disclosures": 0,
        "unauthorized_genetics_imports": 0,
        "unauthorized_family_comparisons": 0,
        "raw_genome_agent_disclosures": 0,
        "unlabeled_speculative_claims_accepted": 0,
        "invalid_genetics_citations_accepted": 0,
        "llm_genetics_canonical_mutations": 0,
    }
    pack = load_genetics_evidence_pack(PACK_PATH)
    imported = parse_consumer_genotypes(
        _input(
            "rsDemoPGX\t10\t1001\tAG",
            "rsDemoNoCall\t11\t1101\t--",
            "rsDemoAmbiguous\t12\t1201\tAT",
            "raw-only-marker\t20\t2001\tCC",
        ),
        genome_build=GenomeBuild.GRCH37,
        selected_rsids={entry.rsid for entry in pack.entries if entry.rsid},
    )
    assessments = assess_evidence(imported.observations, pack)
    coverage = summarize_coverage(assessments)
    finding = next(result.finding for result in assessments if result.finding is not None)
    packet = build_research_packet(
        person_id="synthetic_person_a",
        mode=ResearchMode.EXPLORE,
        observations=imported.observations,
        evidence_entries=pack.entries,
        findings=(finding,),
        selected_observation_ids={finding.observation_id},
        selected_evidence_ids={finding.evidence_id},
        selected_finding_ids={finding.finding_id},
        selected_health_records={"med-synthetic": {"kind": "medication", "name": "DemoMed"}},
    )
    if "raw-only-marker" in packet.model_dump_json():
        counters["raw_genome_agent_disclosures"] += 1
    valid = ResearchOutput(
        what_may_be_happening="A bounded synthetic association may be worth investigating.",
        evidence_supporting_it=(finding.evidence_id,),
        evidence_against_it=("Consumer-chip coverage is incomplete.",),
        alternative_explanations=("The relationship may be coincidental.",),
        missing_information=("Independent confirmation.",),
        confidence_epistemic_status=EpistemicStatus.PLAUSIBLE,
        questions_worth_investigating=("What would change confidence?",),
        claims=(
            ResearchClaim(
                claim="A reviewed association may be worth discussing.",
                epistemic_status=EpistemicStatus.PLAUSIBLE,
                supporting_evidence_ids=(finding.evidence_id,),
                contradicting_evidence_ids=(),
                person_record_ids=("med-synthetic",),
                reasoning_summary="The selected synthetic evidence supports only a limited hypothesis.",
                limitations=("Synthetic evidence only.",),
                missing_information=("Independent confirmation.",),
            ),
        ),
    )
    validate_research_output(valid, packet)
    pgx = intersect_pgx_medications(
        findings=(finding,),
        evidence_entries=pack.entries,
        confirmed_normalized_medications=("demomed", "unrelated"),
    )
    if not pgx:
        raise AssertionError("deterministic PGx/current-medication intersection missing")
    compare = compare_ibs(imported.observations, ())
    if compare.similarity is not None or not compare.insufficient_coverage:
        raise AssertionError("zero-common family comparison must fail closed")
    try:
        validate_research_output(
            valid.model_copy(
                update={
                    "claims": (
                        valid.claims[0].model_copy(
                            update={"supporting_evidence_ids": ("invented",)}
                        ),
                    )
                }
            ),
            packet,
        )
    except ValueError:
        pass
    else:
        counters["invalid_genetics_citations_accepted"] += 1
    return {
        "status": "PASS" if not any(counters.values()) else "FAIL",
        "coverage": coverage.model_dump(mode="json"),
        "pgx_intersections": len(pgx),
        "research_context_hash": packet.context_hash,
        "counters": counters,
    }


def main() -> int:
    result = _run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
