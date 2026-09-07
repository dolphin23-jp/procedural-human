from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
import json

from .ingest import sha256_file


@dataclass(frozen=True)
class SourceArchiveFile:
    relative_path: str
    sha256: str
    byte_size: int


@dataclass(frozen=True)
class SourceArchiveSnapshot:
    source_archive_id: str
    retrieved_at: str
    root_path: str
    files: tuple[SourceArchiveFile, ...]

    def to_json_dict(self) -> dict[str, object]:
        return asdict(self)


def snapshot_source_archive(
    root: str | Path,
    paths: Iterable[str | Path],
    *,
    source_archive_id: str,
    retrieved_at: datetime | None = None,
) -> SourceArchiveSnapshot:
    root_path = Path(root).resolve()
    timestamp = retrieved_at or datetime.now(timezone.utc)
    files: list[SourceArchiveFile] = []
    for relative in sorted(
        (Path(path) for path in paths),
        key=lambda item: item.as_posix(),
    ):
        source = (root_path / relative).resolve()
        if not source.is_relative_to(root_path):
            raise ValueError("source path escapes archive root")
        if not source.is_file():
            raise FileNotFoundError(source)
        files.append(
            SourceArchiveFile(
                relative_path=relative.as_posix(),
                sha256=sha256_file(source),
                byte_size=source.stat().st_size,
            )
        )
    if not files:
        raise ValueError("archive snapshot requires at least one file")
    return SourceArchiveSnapshot(
        source_archive_id=source_archive_id,
        retrieved_at=timestamp.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        root_path=root_path.as_posix(),
        files=tuple(files),
    )


def write_source_archive_snapshot(
    snapshot: SourceArchiveSnapshot,
    output: str | Path,
) -> None:
    Path(output).write_text(
        json.dumps(snapshot.to_json_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
