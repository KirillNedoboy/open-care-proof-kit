"""Sentient G5 ecosystem-validation harness.

Eval-only code: an adversarial corpus, its driver, security-invariant and
quality metrics, and the deterministic reviewer report. Nothing in this package
changes the G1/G2/G3/G4 trust contracts — it *proves* them by driving the real
``app.agent.g2_runtime.G2Runtime`` and the trusted builders/validators with
synthetic identities and scripted providers.
"""

from __future__ import annotations
