from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import Iterable
from urllib.parse import urlparse


class ScopeViolation(PermissionError):
    pass


@dataclass
class ScopePolicy:
    allowed_hosts: set[str] = field(default_factory=set)
    allowed_url_globs: list[str] = field(default_factory=list)
    denied_hosts: set[str] = field(default_factory=set)
    denied_url_globs: list[str] = field(default_factory=list)
    allow_private_networks: bool = False

    @classmethod
    def from_target(cls, target_url: str | None = None, extra_hosts: Iterable[str] = ()) -> "ScopePolicy":
        hosts = {host.lower() for host in extra_hosts if host}
        if target_url:
            parsed = urlparse(target_url)
            if parsed.hostname:
                hosts.add(parsed.hostname.lower())
        return cls(allowed_hosts=hosts)

    def allows(self, url: str) -> bool:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        normalized = url.lower()
        if not host:
            return False
        if host in self.denied_hosts:
            return False
        if any(fnmatch(normalized, pattern.lower()) for pattern in self.denied_url_globs):
            return False
        if self.allowed_hosts and host not in self.allowed_hosts:
            return False
        if self.allowed_url_globs and not any(fnmatch(normalized, pattern.lower()) for pattern in self.allowed_url_globs):
            return False
        if not self.allow_private_networks and _is_private_like(host):
            return host in self.allowed_hosts
        return True

    def assert_allowed(self, url: str, *, action: str = "request") -> None:
        if not self.allows(url):
            raise ScopeViolation(f"Blocked out-of-scope {action}: {url}")


def _is_private_like(host: str) -> bool:
    return (
        host == "localhost"
        or host.startswith("127.")
        or host.startswith("10.")
        or host.startswith("192.168.")
        or host.startswith("172.16.")
        or host.startswith("172.17.")
        or host.startswith("172.18.")
        or host.startswith("172.19.")
        or host.startswith("172.2")
        or host.startswith("172.30.")
        or host.startswith("172.31.")
    )


scope_guard = ScopePolicy()
