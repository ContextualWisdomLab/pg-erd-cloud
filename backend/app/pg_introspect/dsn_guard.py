from __future__ import annotations

import asyncio
from dataclasses import dataclass
import ipaddress
import socket
from urllib.parse import parse_qsl, urlparse

from app.settings import settings

POSTGRES_SCHEMES = {"postgres", "postgresql"}


class DsnTargetError(ValueError):
    """Raised when a PostgreSQL DSN points at a disallowed network target."""


@dataclass(frozen=True)
class ValidatedDsnTarget:
    """Connection target values that were checked for restricted IP ranges."""

    hosts: tuple[str, ...]
    port: int | None


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
        raise DsnTargetError("database host allowlist is not configured")
    if any(_host_matches_allowed_entry(host, entry) for entry in allowed_hosts):
        return
    raise DsnTargetError("database host is not in the introspection allowlist")


def _is_restricted_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped

    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _parse_ip_literal(
    host: str,
) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return None


def _connection_host_for_ip(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> str:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return str(ip.ipv4_mapped)
    return str(ip)


async def _resolved_ips(
    host: str, port: int | None
) -> set[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        loop = asyncio.get_running_loop()
        addrinfo = await loop.getaddrinfo(host, port or 5432, type=socket.SOCK_STREAM)
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


def _parse_query_params(query: str) -> dict[str, list[str]]:
    params: dict[str, list[str]] = {}
    for key, value in parse_qsl(query, keep_blank_values=True):
        params.setdefault(key.lower(), []).append(value)
    return params


def _split_query_host_values(values: list[str], parameter: str) -> list[str]:
    if not values:
        return []
    hosts = [h.strip() for h in ",".join(values).split(",")]
    if not all(hosts):
        raise DsnTargetError(f"database DSN query {parameter} is invalid")
    return hosts


def _validate_query_ports(values: list[str]) -> int | None:
    if not values:
        return None

    first_port: int | None = None
    for port_value in ",".join(values).split(","):
        normalized = port_value.strip()
        if not normalized:
            raise DsnTargetError("database DSN query port is invalid")
        try:
            port = int(normalized)
        except ValueError as err:
            raise DsnTargetError("database DSN query port is invalid") from err
        if port < 1 or port > 65535:
            raise DsnTargetError("database DSN query port is invalid")
        if first_port is None:
            first_port = port
    return first_port


def _unique_hosts(hosts: list[str]) -> tuple[str, ...]:
    unique: list[str] = []
    seen: set[str] = set()
    for host in hosts:
        if host in seen:
            continue
        seen.add(host)
        unique.append(host)
    return tuple(unique)


async def _validated_ip_hosts(
    h: str, is_hostaddr: bool, port: int | None
) -> tuple[str, ...]:
    normalized = h.lower().rstrip(".")

    if normalized == "localhost" or normalized.endswith(".localhost"):
        raise DsnTargetError("database host must not be localhost")

    _validate_allowed_host(normalized)

    literal_ip = _parse_ip_literal(normalized)
    if literal_ip is not None:
        if _is_restricted_ip(literal_ip):
            raise DsnTargetError("database host resolves to a restricted IP range")
        return (_connection_host_for_ip(literal_ip),)

    if is_hostaddr:
        raise DsnTargetError("database DSN query hostaddr is invalid")

    resolved_ips = await _resolved_ips(normalized, port)
    for ip in resolved_ips:
        if _is_restricted_ip(ip):
            raise DsnTargetError("database host resolves to a restricted IP range")
    return tuple(_connection_host_for_ip(ip) for ip in sorted(resolved_ips, key=str))


async def validate_postgres_dsn_target(dsn: str) -> ValidatedDsnTarget:
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
    query = _parse_query_params(parsed.query)

    port_override = _validate_query_ports(query.get("port", []))
    if port_override is not None:
        port = port_override

    primary_hosts = await _validated_ip_hosts(host, False, port)
    query_hosts = []
    for query_host in _split_query_host_values(query.get("host", []), "host"):
        query_hosts.append(await _validated_ip_hosts(query_host, False, port))
    query_hostaddrs = []
    for query_hostaddr in _split_query_host_values(
        query.get("hostaddr", []), "hostaddr"
    ):
        query_hostaddrs.append(await _validated_ip_hosts(query_hostaddr, True, port))

    connection_host_groups = query_hosts + query_hostaddrs
    if not connection_host_groups:
        connection_host_groups = [primary_hosts]

    return ValidatedDsnTarget(
        hosts=_unique_hosts(
            [host for group in connection_host_groups for host in group]
        ),
        port=port,
    )
