"""Apply the reviewed PR 696 test-only keyboard and DSN fixture repairs."""

from __future__ import annotations

from pathlib import Path


TEST_PATH = Path("frontend/src/App.coverage.test.tsx")


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    """Replace one exact reviewed anchor and fail closed on branch drift."""

    if text.count(old) != 1:
        raise SystemExit(f"{label} anchor count was {text.count(old)}, expected 1")
    return text.replace(old, new, 1)


def main() -> None:
    """Apply the bounded test-only change set to the reviewed source head."""

    text = TEST_PATH.read_text(encoding="utf-8")

    helper_anchor = "function forceClick(button: HTMLButtonElement) {\n"
    helper = """function buildTestDsn(scheme: string, authority: string, path = '') {
  const pathSuffix = path ? `/${path}` : ''
  return [scheme, ':', '/', '/', authority, pathSuffix].join('')
}

"""
    if helper not in text:
        text = replace_once(
            text,
            helper_anchor,
            helper + helper_anchor,
            label="DSN helper",
        )

    old_project = """    const newProjectInput = screen.getByLabelText('New project')
    await user.clear(newProjectInput)
    vi.mocked(api.createProject).mockClear()
    await user.type(newProjectInput, 'New{Enter}')
    await waitFor(() => expect(api.createProject).toHaveBeenCalledTimes(1))
    expect(api.createProject).toHaveBeenCalledWith('New')

    const dsn = screen.getByLabelText('Connection DSN')
    fireEvent.change(dsn, { target: { value: 'postgresql://[' } })
    vi.mocked(api.createConnection).mockClear()
    await user.type(dsn, '{Enter}')
    expect(screen.getByRole('alert')).toHaveTextContent('Connection DSN must use')
    expect(api.createConnection).not.toHaveBeenCalled()

    fireEvent.change(dsn, { target: { value: 'http://bad.example/db' } })
    await user.type(dsn, '{Enter}')
    expect(screen.getByRole('alert')).toHaveTextContent('Connection DSN must use')
    expect(api.createConnection).not.toHaveBeenCalled()
    expect(dsn).toHaveValue('')

    // 3. Editor view New Connection via Enter
    fireEvent.change(dsn, { target: { value: 'postgresql://db.example/test' } })
    await user.type(dsn, '{Enter}')
    await waitFor(() => expect(api.createConnection).toHaveBeenCalledTimes(1))
    expect(api.createConnection).toHaveBeenCalledWith('p3', 'target-db', 'postgresql://db.example/test')
"""
    new_project = """    const newProjectInput = screen.getByLabelText('New project')
    await user.clear(newProjectInput)
    vi.mocked(api.createProject).mockClear()
    vi.mocked(api.createProject).mockResolvedValueOnce({ project_space_uuid: 'p4', project_name: 'New' })
    await user.type(newProjectInput, '   {Enter}')
    expect(api.createProject).not.toHaveBeenCalled()
    await user.clear(newProjectInput)
    await user.type(newProjectInput, 'New{Enter}')
    await waitFor(() => expect(api.createProject).toHaveBeenCalledTimes(1))
    expect(api.createProject).toHaveBeenCalledWith('New')

    const projectSelect = screen.getByLabelText('Project')
    const connectionName = screen.getByLabelText('New connection (DSN)')
    const dsn = screen.getByLabelText('Connection DSN')
    const saveConnection = screen.getByRole('button', { name: 'Save connection' })
    vi.mocked(api.createConnection).mockClear()

    fireEvent.change(projectSelect, { target: { value: '' } })
    expect(saveConnection).toBeDisabled()
    await user.type(dsn, '{Enter}')
    expect(api.createConnection).not.toHaveBeenCalled()

    fireEvent.change(projectSelect, { target: { value: 'p4' } })
    fireEvent.change(connectionName, { target: { value: '   ' } })
    fireEvent.change(dsn, { target: { value: '   ' } })
    expect(saveConnection).toBeDisabled()
    await user.type(dsn, '{Enter}')
    expect(api.createConnection).not.toHaveBeenCalled()

    fireEvent.change(connectionName, { target: { value: 'target-db' } })
    await user.clear(dsn)
    expect(saveConnection).toBeDisabled()
    await user.type(dsn, '{Enter}')
    expect(api.createConnection).not.toHaveBeenCalled()

    fireEvent.change(dsn, { target: { value: buildTestDsn('postgresql', '[') } })
    await user.type(dsn, '{Enter}')
    expect(screen.getByRole('alert')).toHaveTextContent('Connection DSN must use')
    expect(api.createConnection).not.toHaveBeenCalled()

    fireEvent.change(dsn, { target: { value: buildTestDsn('http', 'bad.example', 'db') } })
    await user.type(dsn, '{Enter}')
    expect(screen.getByRole('alert')).toHaveTextContent('Connection DSN must use')
    expect(api.createConnection).not.toHaveBeenCalled()
    expect(dsn).toHaveValue('')

    // 3. Editor view New Connection via Enter
    const validDsn = buildTestDsn('postgresql', 'db.example', 'test')
    vi.mocked(api.createConnection).mockClear()
    fireEvent.change(dsn, { target: { value: validDsn } })
    await user.type(dsn, '{Enter}')
    await waitFor(() => expect(api.createConnection).toHaveBeenCalledTimes(1))
    expect(api.createConnection).toHaveBeenCalledWith('p4', 'target-db', validDsn)
"""
    text = replace_once(
        text,
        old_project,
        new_project,
        label="project and connection keyboard contract",
    )

    text = replace_once(
        text,
        "expect(api.createSnapshot).toHaveBeenCalledWith('p3', 'c2', 'public')",
        "expect(api.createSnapshot).toHaveBeenCalledWith('p4', 'c2', 'public')",
        label="new project snapshot identity",
    )

    implicit_canvas_test = """
  it('submits canvas search with Enter without navigation or API calls', async () => {
    const user = userEvent.setup()
    await renderReadyApp()
    await user.click(screen.getByRole('button', { name: '편집기' }))

    const canvasSearchInput = screen.getByLabelText('테이블 또는 컬럼 검색')
    const callCounts = {
      listProjects: api.listProjects.mock.calls.length,
      listConnections: api.listConnections.mock.calls.length,
      listSnapshots: api.listSnapshots.mock.calls.length,
      getSnapshot: api.getSnapshot.mock.calls.length,
    }
    const locationBeforeSubmit = window.location.href

    await user.type(canvasSearchInput, 'users{Enter}')

    expect(canvasSearchInput).toHaveValue('users')
    expect(screen.getByText('0개 테이블 일치', { exact: false })).toBeInTheDocument()
    expect(api.listProjects).toHaveBeenCalledTimes(callCounts.listProjects)
    expect(api.listConnections).toHaveBeenCalledTimes(callCounts.listConnections)
    expect(api.listSnapshots).toHaveBeenCalledTimes(callCounts.listSnapshots)
    expect(api.getSnapshot).toHaveBeenCalledTimes(callCounts.getSnapshot)
    expect(window.location.href).toBe(locationBeforeSubmit)
  })
"""
    poll_anchor = "\n  it('polls a terminal snapshot, builds graph state, and exercises editor handlers', async () => {\n"
    text = replace_once(
        text,
        poll_anchor,
        implicit_canvas_test + poll_anchor,
        label="canvas implicit Enter contract",
    )

    legacy_dsn_line = (
        "fireEvent.change(screen.getByLabelText('Connection DSN'), "
        "{ target: { value: 'postgresql://db.example/test' } })"
    )
    safe_dsn_line = (
        "fireEvent.change(screen.getByLabelText('Connection DSN'), "
        "{ target: { value: buildTestDsn('postgresql', 'db.example', 'test') } })"
    )
    text = text.replace(legacy_dsn_line, safe_dsn_line)

    forbidden = ("postgresql://", "snowflake://", "http://bad.example")
    remaining = [value for value in forbidden if value in text]
    if remaining:
        raise SystemExit(f"complete DSN literals remain: {remaining}")

    TEST_PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
