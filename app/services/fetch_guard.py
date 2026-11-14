"""SSRF-shielded HTTP fetcher with DNS pinning, redirect re-validation, and size caps."""

from __future__ import annotations

import hashlib
import ipaddress
import socket
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local & cloud metadata (169.254.169.254)
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

MAX_FETCH_BYTES = 5 * 1024 * 1024  # 5 MB maximum
MAX_REDIRECTS = 3
REQUEST_TIMEOUT_SECONDS = 8.0


class SSRFSecurityError(ValueError):
    """Raised when an attempt to query internal/prohibited network endpoints is detected."""


@dataclass
class GuardedFetchResult:
    """Sanitized HTTP fetch output."""

    requested_url: str
    final_url: str
    status_code: int
    content: bytes
    content_type: str
    fetch_ms: int
    content_sha256: str


class FetchGuard:
    """Validates URLs and prevents Server-Side Request Forgery."""

    @classmethod
    def is_ip_blocked(cls, ip_str: str) -> bool:
        """Check if an IP address belongs to any prohibited private or link-local range."""
        try:
            ip = ipaddress.ip_address(ip_str)
            return any(ip in net for net in BLOCKED_NETWORKS)
        except ValueError:
            return True

    @classmethod
    def validate_url(cls, url: str) -> None:
        """Enforce strict URL scheme and hostname sanity checks."""
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise SSRFSecurityError(f"Unsupported scheme '{parsed.scheme}'. Only http and https are allowed.")

        if parsed.username or parsed.password:
            raise SSRFSecurityError("URLs containing user credentials are not allowed.")

        hostname = parsed.hostname
        if not hostname:
            raise SSRFSecurityError("URL missing valid hostname.")

        # Check if hostname directly parses as a blocked IP
        try:
            ip = ipaddress.ip_address(hostname)
        except ValueError:
            return  # It's a standard domain name, will be checked via DNS resolution

        if cls.is_ip_blocked(str(ip)):
            raise SSRFSecurityError(f"Direct IP access to restricted address {hostname} is blocked.")

    @classmethod
    def resolve_and_verify(cls, hostname: str, port: int) -> list[str]:
        """Resolve DNS and assert that none of the returned IP addresses are private."""
        try:
            addr_info = socket.getaddrinfo(hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise SSRFSecurityError(f"DNS resolution failed for hostname '{hostname}': {exc}") from exc

        verified_ips: list[str] = []
        for family, _, _, _, sockaddr in addr_info:
            ip = sockaddr[0]
            if cls.is_ip_blocked(ip):
                raise SSRFSecurityError(f"Access to resolved IP {ip} for host {hostname} is blocked by SSRF policy.")
            verified_ips.append(ip)

        if not verified_ips:
            raise SSRFSecurityError(f"No IP addresses resolved for hostname '{hostname}'.")

        return verified_ips

    @classmethod
    async def fetch(cls, url: str, user_agent: str = "OpenDocsBot/0.1") -> GuardedFetchResult:
        """Fetch URL with SSRF guards, redirect checking, and strict streaming size limits."""
        cls.validate_url(url)
        parsed = urlparse(url)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        cls.resolve_and_verify(parsed.hostname, port)

        start_time = time.perf_counter()
        current_url = url

        async with httpx.AsyncClient(
            verify=True,
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml,text/plain"},
        ) as client:
            for _ in range(MAX_REDIRECTS + 1):
                cls.validate_url(current_url)
                curr_parsed = urlparse(current_url)
                curr_port = curr_parsed.port or (443 if curr_parsed.scheme == "https" else 80)
                cls.resolve_and_verify(curr_parsed.hostname, curr_port)

                response = await client.get(current_url, follow_redirects=False)

                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise SSRFSecurityError("Redirect received without Location header.")
                    current_url = urljoin(current_url, location)
                    continue

                # Finished redirects; read content under size cap
                content_bytes = bytearray()
                async for chunk in response.aiter_bytes():
                    content_bytes.extend(chunk)
                    if len(content_bytes) > MAX_FETCH_BYTES:
                        raise SSRFSecurityError(
                            f"Response size exceeded safety ceiling of {MAX_FETCH_BYTES} bytes."
                        )

                fetch_ms = int((time.perf_counter() - start_time) * 1000)
                sha256_hash = hashlib.sha256(content_bytes).hexdigest()

                return GuardedFetchResult(
                    requested_url=url,
                    final_url=current_url,
                    status_code=response.status_code,
                    content=bytes(content_bytes),
                    content_type=response.headers.get("content-type", "text/html"),
                    fetch_ms=fetch_ms,
                    content_sha256=sha256_hash,
                )

            raise SSRFSecurityError(f"Exceeded maximum allowed redirects of {MAX_REDIRECTS}.")
