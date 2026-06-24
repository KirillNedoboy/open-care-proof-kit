from pathlib import Path

from app.vault.loader import load_health_vault


def test_load_demo_vault() -> None:
    vault = load_health_vault(Path("data/demo_patients/demo_patient_a.json"))
    assert vault.patient_id == "demo-patient-a"
    assert vault.data_classification == "synthetic_demo_only"
