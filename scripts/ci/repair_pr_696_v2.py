"""Apply deterministic current-head review fixes to PR 696 tests."""

from pathlib import Path


TEST_FILE = Path("frontend/src/App.coverage.test.tsx")


def replace_once(source: str, old: str, new: str, label: str) -> str:
    """Replace one exact block, failing closed when the branch has drifted."""

    matches = source.count(old)
    if matches != 1:
        raise RuntimeError(f"{label}: expected one match, found {matches}")
    return source.replace(old, new, 1)


def main() -> None:
    """Add implicit-submit, invalid-state, and runtime DSN-fixture coverage."""

    source = TEST_FILE.read_text(encoding="utf-8")

    source = replace_once(
        source,
        "function forceClick(button: HTMLButtonElement) {\n"
        "  button.disabled = false\n"
        "  button.removeAttribute('disabled')\n"
        "  button.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }))\n"
        "}\n",
        "function forceClick(button: HTMLButtonElement) {\n"
        "  button.disabled = false\n"
        "  button.removeAttribute('disabled')\n"
        "  button.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }))\n"
        "}\n\n"
        "function buildTestDsn(scheme: string, authority: string, path = ''): string {\n"
        "  return [scheme, '://', authority, path].join('')\n"
        "}\n",
        "runtime DSN helper",
    )

    source = replace_once(
        source,
        "  it('navigates dashboard, project, and diagram states including empty/search branches', async () => {\n"
        "    await renderReadyApp()\n",
        "  it('navigates dashboard, project, and diagram states including empty/search branches', async () => {\n"
        "    const user = userEvent.setup()\n"
        "    await renderReadyApp()\n",
        "diagram search user setup",
    )

    source = replace_once(
        source,
        "    const searchInput = screen.getByLabelText('다이어그램 검색')\n"
        "    // Wait for the snapshots to load before searching\n"
        "    await waitFor(() => expect(screen.queryByText('아직 다이어그램 스냅샷이 없습니다. 편집기에서 데이터베이스를 역공학해 시작하세요.')).not.toBeInTheDocument())\n"
        "    fireEvent.change(searchInput, { target: { value: 'no-match' } })\n\n"
        "    const searchForm = searchInput.closest('form')\n"
        "    const searchSubmitEvent = new Event('submit', { cancelable: true, bubbles: true })\n"
        "    if (searchForm) searchForm.dispatchEvent(searchSubmitEvent)\n"
        "    expect(searchSubmitEvent.defaultPrevented).toBe(true)\n\n"
        "    expect(screen.getByText('검색 결과가 없습니다.')).toBeInTheDocument()\n",
        "    const searchInput = screen.getByLabelText('다이어그램 검색')\n"
        "    await waitFor(() => expect(screen.queryByText('아직 다이어그램 스냅샷이 없습니다. 편집기에서 데이터베이스를 역공학해 시작하세요.')).not.toBeInTheDocument())\n"
        "    const diagramApiCallCount = api.listSnapshots.mock.calls.length\n"
        "    const diagramHistoryLength = window.history.length\n"
        "    await user.clear(searchInput)\n"
        "    await user.type(searchInput, 'no-match{Enter}')\n"
        "    expect(screen.getByText('검색 결과가 없습니다.')).toBeInTheDocument()\n"
        "    expect(api.listSnapshots).toHaveBeenCalledTimes(diagramApiCallCount)\n"
        "    expect(window.history.length).toBe(diagramHistoryLength)\n\n"
        "    const searchForm = searchInput.closest('form')\n"
        "    const searchSubmitEvent = new Event('submit', { cancelable: true, bubbles: true })\n"
        "    searchForm?.dispatchEvent(searchSubmitEvent)\n"
        "    expect(searchSubmitEvent.defaultPrevented).toBe(true)\n",
        "diagram implicit Enter coverage",
    )

    source = replace_once(
        source,
        "    // 2. Editor view New Project via Enter\n"
        "    const newProjectInput = screen.getByLabelText('New project')\n"
        "    await user.clear(newProjectInput)\n"
        "    vi.mocked(api.createProject).mockClear()\n"
        "    await user.type(newProjectInput, 'New{Enter}')\n"
        "    await waitFor(() => expect(api.createProject).toHaveBeenCalledTimes(1))\n"
        "    expect(api.createProject).toHaveBeenCalledWith('New')\n\n"
        "    const dsn = screen.getByLabelText('Connection DSN')\n"
        "    fireEvent.change(dsn, { target: { value: 'postgresql://[' } })\n"
        "    vi.mocked(api.createConnection).mockClear()\n"
        "    await user.type(dsn, '{Enter}')\n"
        "    expect(screen.getByRole('alert')).toHaveTextContent('Connection DSN must use')\n"
        "    expect(api.createConnection).not.toHaveBeenCalled()\n\n"
        "    fireEvent.change(dsn, { target: { value: 'http://bad.example/db' } })\n"
        "    await user.type(dsn, '{Enter}')\n"
        "    expect(screen.getByRole('alert')).toHaveTextContent('Connection DSN must use')\n"
        "    expect(api.createConnection).not.toHaveBeenCalled()\n"
        "    expect(dsn).toHaveValue('')\n\n"
        "    // 3. Editor view New Connection via Enter\n"
        "    fireEvent.change(dsn, { target: { value: 'postgresql://db.example/test' } })\n"
        "    await user.type(dsn, '{Enter}')\n"
        "    await waitFor(() => expect(api.createConnection).toHaveBeenCalledTimes(1))\n"
        "    expect(api.createConnection).toHaveBeenCalledWith('p3', 'target-db', 'postgresql://db.example/test')\n",
        "    // 2. Editor view New Project via Enter\n"
        "    const newProjectInput = screen.getByLabelText('New project')\n"
        "    await user.clear(newProjectInput)\n"
        "    vi.mocked(api.createProject).mockClear()\n"
        "    await user.type(newProjectInput, '   {Enter}')\n"
        "    expect(api.createProject).not.toHaveBeenCalled()\n"
        "    await user.clear(newProjectInput)\n"
        "    await user.type(newProjectInput, 'New{Enter}')\n"
        "    await waitFor(() => expect(api.createProject).toHaveBeenCalledTimes(1))\n"
        "    expect(api.createProject).toHaveBeenCalledWith('New')\n\n"
        "    const projectSelect = screen.getByLabelText('Project')\n"
        "    const connectionName = screen.getByLabelText('New connection (DSN)')\n"
        "    const dsn = screen.getByLabelText('Connection DSN')\n"
        "    const saveConnection = screen.getByRole('button', { name: 'Save connection' })\n"
        "    vi.mocked(api.createConnection).mockClear()\n\n"
        "    fireEvent.change(projectSelect, { target: { value: '' } })\n"
        "    expect(saveConnection).toBeDisabled()\n"
        "    await user.type(dsn, '{Enter}')\n"
        "    expect(api.createConnection).not.toHaveBeenCalled()\n"
        "    fireEvent.change(projectSelect, { target: { value: 'p3' } })\n\n"
        "    await user.clear(connectionName)\n"
        "    await user.type(connectionName, '   {Enter}')\n"
        "    expect(saveConnection).toBeDisabled()\n"
        "    expect(api.createConnection).not.toHaveBeenCalled()\n"
        "    await user.clear(connectionName)\n"
        "    await user.type(connectionName, 'target-db')\n\n"
        "    expect(dsn).toHaveValue('')\n"
        "    expect(saveConnection).toBeDisabled()\n"
        "    await user.type(dsn, '{Enter}')\n"
        "    expect(api.createConnection).not.toHaveBeenCalled()\n\n"
        "    const malformedDsn = buildTestDsn('postgresql', '[')\n"
        "    fireEvent.change(dsn, { target: { value: malformedDsn } })\n"
        "    await user.type(dsn, '{Enter}')\n"
        "    expect(screen.getByRole('alert')).toHaveTextContent('Connection DSN must use')\n"
        "    expect(api.createConnection).not.toHaveBeenCalled()\n\n"
        "    const unsupportedDsn = buildTestDsn('http', 'bad.example', '/db')\n"
        "    fireEvent.change(dsn, { target: { value: unsupportedDsn } })\n"
        "    await user.type(dsn, '{Enter}')\n"
        "    expect(screen.getByRole('alert')).toHaveTextContent('Connection DSN must use')\n"
        "    expect(api.createConnection).not.toHaveBeenCalled()\n"
        "    expect(dsn).toHaveValue('')\n\n"
        "    // 3. Editor view New Connection via Enter\n"
        "    const validDsn = buildTestDsn('postgresql', 'db.example', '/test')\n"
        "    vi.mocked(api.createConnection).mockClear()\n"
        "    fireEvent.change(dsn, { target: { value: validDsn } })\n"
        "    await user.type(dsn, '{Enter}')\n"
        "    await waitFor(() => expect(api.createConnection).toHaveBeenCalledTimes(1))\n"
        "    expect(api.createConnection).toHaveBeenCalledWith('p3', 'target-db', validDsn)\n",
        "editor invalid states and runtime DSN fixtures",
    )

    source = replace_once(
        source,
        "    const openButtons = await screen.findAllByRole('button', { name: '열기' })\n"
        "    vi.useFakeTimers()\n",
        "    const openButtons = await screen.findAllByRole('button', { name: '열기' })\n"
        "    vi.useFakeTimers()\n"
        "    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })\n",
        "canvas user setup",
    )

    source = replace_once(
        source,
        "    const canvasSearchInput = screen.getByLabelText('테이블 또는 컬럼 검색')\n"
        "    fireEvent.change(canvasSearchInput, { target: { value: 'users' } })\n"
        "    const canvasSearchForm = canvasSearchInput.closest('form')\n"
        "    const canvasSubmitEvent = new Event('submit', { cancelable: true, bubbles: true })\n"
        "    if (canvasSearchForm) canvasSearchForm.dispatchEvent(canvasSubmitEvent)\n"
        "    expect(canvasSubmitEvent.defaultPrevented).toBe(true)\n\n"
        "    expect(screen.getByText('1개 테이블 일치', { exact: false })).toBeInTheDocument()\n",
        "    const canvasSearchInput = screen.getByLabelText('테이블 또는 컬럼 검색')\n"
        "    const canvasApiCallCount = api.getSnapshot.mock.calls.length\n"
        "    const canvasHistoryLength = window.history.length\n"
        "    await user.clear(canvasSearchInput)\n"
        "    await user.type(canvasSearchInput, 'users{Enter}')\n"
        "    expect(screen.getByText('1개 테이블 일치', { exact: false })).toBeInTheDocument()\n"
        "    expect(api.getSnapshot).toHaveBeenCalledTimes(canvasApiCallCount)\n"
        "    expect(window.history.length).toBe(canvasHistoryLength)\n\n"
        "    const canvasSearchForm = canvasSearchInput.closest('form')\n"
        "    const canvasSubmitEvent = new Event('submit', { cancelable: true, bubbles: true })\n"
        "    canvasSearchForm?.dispatchEvent(canvasSubmitEvent)\n"
        "    expect(canvasSubmitEvent.defaultPrevented).toBe(true)\n",
        "canvas implicit Enter coverage",
    )

    for complete_dsn in (
        "postgresql://[",
        "http://bad.example/db",
        "postgresql://db.example/test",
    ):
        if complete_dsn in source:
            raise RuntimeError(f"complete DSN literal remains: {complete_dsn}")

    TEST_FILE.write_text(source, encoding="utf-8")


if __name__ == "__main__":
    main()
