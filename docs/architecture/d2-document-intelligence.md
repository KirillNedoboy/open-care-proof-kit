# D2.1 Document Intelligence Contract

D2.1 automatically extracts only document-stated medication, condition, and lab
facts from persisted D1 page text. It creates source-backed `pending`
CandidateFacts; it never confirms canonical records, timeline events, Visit Brief
evidence, or normal agent context. Review remains explicit and unchanged.

The extraction contract is `opencare-document-facts/1`. Each suggestion must
contain an exact page number and a verbatim quote of at most 600 characters. The
server resolves exactly one Unicode occurrence and constructs the closed D1
`document_text_span` locator. Input is capped at 60,000 Unicode code points,
output at 32 facts, and there is one provider call per document (no chunking).

External providers require a truthful provider/model disclosure and explicit
per-call consent. Local real providers may execute after prepare. Deterministic
demo mode reports unavailable and never fabricates medical facts. Raw PDF bytes,
paths, credentials, unrelated records, and raw genome are never sent.

Product Core migration v10 stores run identity, bounded status/counts, provider
descriptor identity, request fingerprints, and run-to-candidate items. A
database fingerprint registry makes repeated and concurrent extraction
idempotent. Procedures, recommendations, and follow-up extraction are deferred
to D2.2.
