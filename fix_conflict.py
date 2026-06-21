import sys

def main():
    with open('backend/tests/test_dsn_guard.py', 'r') as f:
        content = f.read()

    conflict_start = content.find('<<<<<<< HEAD')
    conflict_end = content.find('>>>>>>> origin/main') + len('>>>>>>> origin/main')

    if conflict_start == -1 or conflict_end == -1:
        print("Conflict markers not found")
        return

    resolved_block = """        await validate_postgres_dsn_target(
            "postgresql://user:pass@other.example.com/app"
        )


def test_unique_hosts_empty_list() -> None:
    assert _unique_hosts([]) == ()


@pytest.mark.asyncio
async def test_dsn_guard_rejects_unresolvable_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_gaierror(*args, **kwargs):
        raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        raise_gaierror,
    )
    monkeypatch.setattr(
        settings,
        "db_introspection_allowed_hosts",
        "db.example.com",
    )

    with pytest.raises(DsnTargetError, match="database host could not be resolved"):
        await validate_postgres_dsn_target("postgresql://user:pass@db.example.com/app")"""

    new_content = content[:conflict_start] + resolved_block + content[conflict_end:]

    with open('backend/tests/test_dsn_guard.py', 'w') as f:
        f.write(new_content)

    print("Conflict resolved")

if __name__ == '__main__':
    main()
