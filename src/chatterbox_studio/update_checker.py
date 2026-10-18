"""Safe, read-only checks for official Plague's Voice Studio GitHub releases.

No third-party update server, executable download, unattended installation,
model replacement, project migration, or telemetry collection.
Only the GitHub Releases API is contacted when a user opts in or checks now.
"""
from __future__ import annotations

from dataclasses import dataclass
from json import JSONDecodeError, loads
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


LATEST_RELEASE_API = "https://api.github.com/repos/kaotickj/plagues-voice-studio/releases/latest"
RELEASE_PREFIX = "/kaotickj/plagues-voice-studio/releases/tag/"
MAX_METADATA_BYTES = 256 * 1024
_VERSION_PATTERN = re.compile(r"^v?(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)(?:(a|b|rc)(0|[1-9][0-9]*))?$", re.IGNORECASE)
_STAGE_ORDER = {"a": 0, "b": 1, "rc": 2}


class UpdateCheckError(RuntimeError):
    """A non-fatal error querying the official release metadata."""


@dataclass(frozen=True)
class ReleaseInfo:
    tag: str
    version: str
    url: str
    name: str


def version_key(value: str) -> tuple[int, int, int, int, int]:
    """Compare simple Python/PEP 440 versions including alpha/beta/RC/final."""
    match = _VERSION_PATTERN.fullmatch(str(value).strip())
    if not match:
        raise ValueError(f"Unsupported application version: {value!r}")
    major, minor, patch, stage, stage_no = match.groups()
    if stage is None:
        return int(major), int(minor), int(patch), 3, 0
    return int(major), int(minor), int(patch), _STAGE_ORDER[stage.lower()], int(stage_no)


def trusted_release_url(url: str, tag: str) -> bool:
    """Open only the release tag on our official github.com repository."""
    parts = urlsplit(str(url))
    return (
        parts.scheme == "https"
        and parts.netloc.lower() == "github.com"
        and not parts.query and not parts.fragment
        and parts.path == RELEASE_PREFIX + tag
        and bool(_VERSION_PATTERN.fullmatch(tag))
    )


def latest_stable_release(*, opener=urlopen, timeout: float = 8.0) -> ReleaseInfo | None:
    """Look up stable releases; missing releases are normal before first launch."""
    req = Request(
        LATEST_RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "PlaguesVoiceStudio-UpdateChecker/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with opener(req, timeout=timeout) as response:
            raw = response.read(MAX_METADATA_BYTES + 1)
    except HTTPError as exc:
        if exc.code == 404:
            return None  # No published stable release yet.
        raise UpdateCheckError(f"GitHub returned HTTP {exc.code}; try again later.") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise UpdateCheckError("Could not reach GitHub to check for updates.") from exc
    if len(raw) > MAX_METADATA_BYTES:
        raise UpdateCheckError("GitHub release metadata exceeded its size limit.")
    try:
        data = loads(raw.decode("utf-8"))
    except (UnicodeError, JSONDecodeError) as exc:
        raise UpdateCheckError("GitHub returned unreadable release metadata.") from exc
    if not isinstance(data, dict):
        raise UpdateCheckError("GitHub returned invalid release metadata.")
    if data.get("draft") or data.get("prerelease"):
        return None
    tag = data.get("tag_name")
    url = data.get("html_url")
    if not isinstance(tag, str) or not isinstance(url, str):
        raise UpdateCheckError("GitHub release is missing a valid version or link.")
    if not trusted_release_url(url, tag):
        raise UpdateCheckError("GitHub returned an unexpected release link; refusing to open it.")
    name = data.get("name")
    return ReleaseInfo(
        tag=tag, version=tag.removeprefix("v"), url=url,
        name=name[:160] if isinstance(name, str) else tag,
    )


def find_update(current_version: str, *, opener=urlopen) -> ReleaseInfo | None:
    """Return a newer official stable release or None, without updating anything."""
    local = version_key(current_version)
    candidate = latest_stable_release(opener=opener)
    if candidate is None:
        return None
    if version_key(candidate.tag) > local:
        return candidate
    return None
