from dataclasses import dataclass


@dataclass(frozen=True)
class LocalReportWriter:
    name: str = "local_report_writer_stub"

    def assert_local_only(self) -> None:
        return None
