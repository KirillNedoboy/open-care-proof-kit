from enum import StrEnum


class CoverageStatus(StrEnum):
    SUPPORTED_DEMO_MARKER = "supported_demo_marker"
    INSUFFICIENT_COVERAGE = "insufficient_coverage"
    NOT_ASSESSED = "not_assessed"
