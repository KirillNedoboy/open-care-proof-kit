from urllib.parse import urlparse

ALLOWED_SOURCE_DOMAINS = (
    "cpicpgx.org",
    "clinpgx.org",
    "ncbi.nlm.nih.gov",
    "fda.gov",
)


def _is_allowed_domain(hostname: str) -> bool:
    lowered = hostname.lower()
    return any(
        lowered == domain or lowered.endswith(f".{domain}")
        for domain in ALLOWED_SOURCE_DOMAINS
    )


def validate_source_url(url: str) -> str:
    normalized = url.strip()
    if not normalized:
        raise ValueError("source_url is required.")

    parsed = urlparse(normalized)
    if parsed.scheme.lower() != "https":
        raise ValueError("source_url must use https.")
    if not parsed.hostname:
        raise ValueError("source_url must include a hostname.")
    if not _is_allowed_domain(parsed.hostname):
        raise ValueError("source_url must use an allowed source domain.")

    return normalized


def is_allowed_source_url(url: str) -> bool:
    try:
        validate_source_url(url)
    except ValueError:
        return False
    return True
