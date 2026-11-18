"""Source adapters: local files and S3 objects share one batch discovery contract."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class DiscoveredObject:
    """Internal batch contract produced by every adapter."""

    uri: str
    display_name: str
    content_sha256: str
    size_bytes: int
    object_version: str | None
    discovered_at: datetime
    source_track: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class SourceAdapter(ABC):
    @abstractmethod
    def list_objects(self, source_track: str) -> list[DiscoveredObject]:
        raise NotImplementedError

    @abstractmethod
    def open_bytes(self, obj: DiscoveredObject) -> bytes:
        raise NotImplementedError


class LocalFileAdapter(SourceAdapter):
    """Discover CSV/ZIP inputs under a local directory."""

    def __init__(self, root: Path, patterns: tuple[str, ...] = ("*.csv", "*.zip")) -> None:
        self.root = root
        self.patterns = patterns

    def list_objects(self, source_track: str) -> list[DiscoveredObject]:
        found: list[DiscoveredObject] = []
        if not self.root.exists():
            return found
        paths: list[Path] = []
        for pattern in self.patterns:
            paths.extend(sorted(self.root.glob(pattern)))
        now = datetime.now(UTC)
        for path in paths:
            if not path.is_file():
                continue
            found.append(
                DiscoveredObject(
                    uri=path.resolve().as_uri(),
                    display_name=path.name,
                    content_sha256=sha256_path(path),
                    size_bytes=path.stat().st_size,
                    object_version=None,
                    discovered_at=now,
                    source_track=source_track,
                )
            )
        return found

    def open_bytes(self, obj: DiscoveredObject) -> bytes:
        path = Path(obj.uri.removeprefix("file://"))
        return path.read_bytes()


class S3Adapter(SourceAdapter):
    """S3 discovery — implemented when AWS credentials / role are available."""

    def __init__(self, bucket: str, prefix: str) -> None:
        self.bucket = bucket
        self.prefix = prefix.rstrip("/") + "/"

    def list_objects(self, source_track: str) -> list[DiscoveredObject]:
        raise NotImplementedError(
            "S3Adapter.list_objects requires boto3 wiring in Phase 12 deployment work. "
            f"Configured bucket={self.bucket!r} prefix={self.prefix!r}."
        )

    def open_bytes(self, obj: DiscoveredObject) -> bytes:
        raise NotImplementedError("S3Adapter.open_bytes not yet implemented.")


def build_adapter(
    *,
    local_dir: Path | None = None,
    s3_bucket: str | None = None,
    s3_prefix: str | None = None,
) -> SourceAdapter:
    if s3_bucket:
        return S3Adapter(s3_bucket, s3_prefix or "")
    if local_dir is None:
        raise ValueError("local_dir is required when S3 is not configured")
    return LocalFileAdapter(local_dir)
