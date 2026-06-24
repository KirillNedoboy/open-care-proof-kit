import json
from pathlib import Path

from app.evidence.pack_schema import EvidencePack


def load_evidence_pack(path: Path) -> EvidencePack:
    raw = json.loads(path.read_text(encoding="utf-8"))
    pack = EvidencePack.model_validate(raw)
    pack.assert_demo_pack()
    return pack
