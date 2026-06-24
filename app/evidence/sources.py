ALLOWED_SOURCE_DOMAINS = (
    "cpicpgx.org",
    "clinpgx.org",
    "ncbi.nlm.nih.gov",
    "fda.gov",
)


def is_allowed_source_url(url: str) -> bool:
    return any(domain in url for domain in ALLOWED_SOURCE_DOMAINS)
