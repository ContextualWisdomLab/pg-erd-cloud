from __future__ import annotations

import ipaddress
import socket
from urllib.parse import parse_qs, urlparse

from app.settings import settings

POSTGRES_SCHEMES = {"postgres", "postgresql"}


class DsnTargetError(ValueError):
    """Raised when a PostgreSQL DSN points at a disallowed network target."""


def _configured_allowed_hosts() -> tuple[str, ...]:
    return tuple(
        item.strip().lower().rstrip(".")
        for item in settings.db_introspection_allowed_hosts.split(",")
        if item.strip()
    )


def _host_matches_allowed_entry(host: str, entry: str) -> bool:
    if entry.startswith("*."):
        suffix = entry[1:]
        return host.endswith(suffix) and host != suffix.lstrip(".")
    return host == entry


def _validate_allowed_host(host: str) -> None:
    allowed_hosts = _configured_allowed_hosts()
    if not allowed_hosts:
        return
    if any(_host_matches_allowed_entry(host, entry) for entry in allowed_hosts):
        return
    raise DsnTargetError("database host is not in the introspection allowlist")


def _is_restricted_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _parse_ip_literal(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return None


def _resolved_ips(host: str, port: int | None) -> set[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        addrinfo = socket.getaddrinfo(host, port or 5432, type=socket.SOCK_STREAM)
    except socket.gaierror as err:
        raise DsnTargetError("database host could not be resolved") from err

    resolved: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
    for entry in addrinfo:
        sockaddr = entry[4]
        if not sockaddr:
            continue
        resolved.add(ipaddress.ip_address(sockaddr[0]))
    if not resolved:
        raise DsnTargetError("database host did not resolve to an IP address")
    return resolved


def validate_postgres_dsn_target(dsn: str) -> None:
    """Reject PostgreSQL DSNs that could target internal network resources."""

    parsed = urlparse(dsn)
    if parsed.scheme.lower() not in POSTGRES_SCHEMES:
        raise DsnTargetError("database DSN must use postgres or postgresql scheme")

    host = parsed.hostname
    if not host:
        raise DsnTargetError("database DSN must include a host")
    try:
        port = parsed.port
    except ValueError as err:
        raise DsnTargetError("database DSN port is invalid") from err
    query = parse_qs(parsed.query)

    port_override = query.get("port", [])
    if port_override:
        try:
            port = int(port_override[0])
        except ValueError as err:
            raise DsnTargetError("database DSN query port is invalid") from err

    hosts_to_check = [host]
    hosts_to_check.extend(query.get("host", []))
    hosts_to_check.extend(query.get("hostaddr", []))

    for h in hosts_to_check:
        normalized = h.lower().rstrip(".")

        if normalized == "localhost" or normalized.endswith(".localhost"):
            raise DsnTargetError("database host must not be localhost")

        _validate_allowed_host(normalized)

        literal_ip = _parse_ip_literal(normalized)
        if literal_ip is not None:
            if _is_restricted_ip(literal_ip):
                raise DsnTargetError("database host resolves to a restricted IP range")
            continue

        for ip in _resolved_ips(normalized, port):
            if _is_restricted_ip(ip):
                raise DsnTargetError("database host resolves to a restricted IP range")
