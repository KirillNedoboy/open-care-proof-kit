from app.vault.schema import HealthVault


def validate_vault(vault: HealthVault) -> list[str]:
    errors: list[str] = []
    if vault.data_classification != "synthetic_demo_only":
        errors.append("Only synthetic demo data is allowed in v0.1.")
    if not vault.patient_id:
        errors.append("patient_id is required.")
    return errors
