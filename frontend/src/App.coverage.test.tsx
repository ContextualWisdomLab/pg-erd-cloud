import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  getMe: vi.fn(),
  listProjects: vi.fn(),
  listConnections: vi.fn(),
  listSnapshots: vi.fn(),
  createProject: vi.fn(),
  createConnection: vi.fn(),
  createSnapshot: vi.fn(),
  getSnapshot: vi.fn(),
  createShareLink: vi.fn(),
}))

const exports = vi.hoisted(() => ({
  downloadText: vi.fn(),
  exportDDL: vi.fn(() => 'DDL'),
  exportDiagramSvg: vi.fn(() => '<svg/>'),
  exportDictionaryCsv: vi.fn(() => 'csv'),
  exportDictionaryMarkdown: vi.fn(() => 'markdown'),
  exportPlantUml: vi.fn(() => '@startuml'),
  exportMermaid: vi.fn(() => 'graph TD'),
  exportDbml: vi.fn(() => 'Table users {}'),
  inferRelationships: vi.fn(),
}))

vi.mock('./api', () => api)
vi.mock('./erd/export', () => ({
  downloadText: exports.downloadText,
  exportDDL: exports.exportDDL,
  exportDiagramSvg: exports.exportDiagramSvg,
  exportDictionaryCsv: exports.exportDictionaryCsv,
  exportDictionaryMarkdown: exports.exportDictionaryMarkdown,
  exportPlantUml: exports.exportPlantUml,
}))
vi.mock('./erd/mermaid', () => ({ exportMermaid: exports.exportMermaid }))
vi.mock('./erd/dbml', () => ({ exportDbml: exports.exportDbml }))
vi.mock('./erd/autoInfer', () => ({ inferRelationships: exports.inferRelationships }))

vi.mock('@xyflow/react', async () => {
  const React = await import('react')
  const initialNode = {
    id: 'table-1',
    type: 'tableNode',
    position: { x: 5, y: 10 },
    data: {
      title: 'public.users',
      columns: [
        { column_name: 'id', data_type: 'bigint', is_not_null: true, is_pk: true },
        { column_name: 'email', data_type: 'text', is_not_null: false, is_pk: false },
      ],
      badges: { pk: true, fk: false },
    },
  }
  const otherNode = {
    ...initialNode,
    id: 'table-2',
    position: { x: 50, y: 100 },
    data: { ...initialNode.data, title: 'public.orders' },
  }
  const edge = { id: 'edge-1', source: 'table-1', target: 'table-2', label: 'fk_old' }

  function ReactFlowMock(props: Record<string, any>) {
    React.useEffect(() => {
      props.onInit?.({ fitView: vi.fn() })
    }, [props.onInit])
    return (
      <div data-testid="react-flow">
        <span data-testid="node-count">{props.nodes.length}</span>
        <span data-testid="edge-count">{props.edges.length}</span>
        <button type="button" data-testid="flow-connect" onClick={() => props.onConnect?.({ source: 'table-1', target: 'table-2' })} />
        <button type="button" data-testid="flow-edge" onClick={(event) => props.onEdgeClick?.(event, props.edges[0] ?? edge)} />
        <button type="button" data-testid="flow-edge-unlabeled" onClick={(event) => props.onEdgeClick?.(event, { ...edge, label: undefined })} />
        <button type="button" data-testid="flow-node" onDoubleClick={(event) => props.onNodeDoubleClick?.(event, props.nodes[0] ?? initialNode)} />
        {props.children}
      </div>
    )
  }

  return {
    Background: () => <span />,
    Controls: () => <span />,
    MiniMap: () => <span />,
    Handle: () => <span />,
    Position: { Top: 'top', Left: 'left', Right: 'right', Bottom: 'bottom' },
    ReactFlow: ReactFlowMock,
    ReactFlowProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    addEdge: (next: unknown, current: unknown[]) => [...current, next],
    useNodesState: (initial: unknown[]) => {
      const [value, setValue] = React.useState(initial)
      return [value, setValue, vi.fn()]
    },
    useEdgesState: (initial: unknown[]) => {
      const [value, setValue] = React.useState(initial)
      return [value, setValue, vi.fn()]
    },
    __fixtures: { initialNode, otherNode, edge },
  }
})

vi.mock('./erd/convert', async () => {
  const flow = (await import('@xyflow/react')) as any
  return {
    snapshotToGraph: vi.fn(() => ({
      nodes: [flow.__fixtures.initialNode, flow.__fixtures.otherNode],
      edges: [flow.__fixtures.edge],
    })),
  }
})

vi.mock('./components/modals', () => ({
  AddTableModal: (props: any) => (
    <div data-testid="add-modal" data-open={props.isOpen}>
      <button type="button" data-testid="add-guard" onClick={props.onAddTableSubmit} />
      {props.isOpen ? (
        <>
          <button type="button" data-testid="add-name" onClick={() => props.setNewTableName('audit_log')} />
          <button type="button" data-testid="add-submit" onClick={props.onAddTableSubmit} />
          <button type="button" data-testid="add-cancel" onClick={props.onAddTableCancel} />
        </>
      ) : null}
    </div>
  ),
  EditEdgeModal: (props: any) => (
    <div data-testid="edge-modal" data-open={Boolean(props.editingEdge)}>
      <button type="button" data-testid="edge-guard-submit" onClick={props.onRelSubmit} />
      <button type="button" data-testid="edge-guard-delete" onClick={props.onRelDelete} />
      {props.editingEdge ? (
        <>
          <button type="button" data-testid="edge-label" onClick={() => props.setRelLabel(' fk_new ')} />
          <button type="button" data-testid="edge-submit" onClick={props.onRelSubmit} />
          <button type="button" data-testid="edge-cancel" onClick={props.onRelCancel} />
          <button type="button" data-testid="edge-delete" onClick={props.onRelDelete} />
        </>
      ) : null}
    </div>
  ),
  ExportModal: (props: any) => (
    <div data-testid="export-modal" data-open={props.isOpen}>
      <span data-testid="share-url">{props.shareLinkUrl}</span>
      <span data-testid="share-error">{props.shareLinkError}</span>
      <button type="button" data-testid="share-copy-guard" onClick={props.onCopyShareLink} />
      {props.isOpen ? (
        <>
          <button type="button" data-testid="export-close" onClick={props.onCloseExport} />
          <button type="button" data-testid="export-copy-ddl" onClick={props.onCopyExportDdl} />
          <button type="button" data-testid="export-svg" onClick={props.onDownloadSvg} />
          <button type="button" data-testid="export-uml" onClick={props.onDownloadUml} />
          <button type="button" data-testid="export-mermaid" onClick={props.onDownloadMermaid} />
          <button type="button" data-testid="export-dbml" onClick={props.onDownloadDbml} />
          <button type="button" data-testid="export-csv" onClick={props.onExportDictionaryCsv} />
          <button type="button" data-testid="export-md" onClick={props.onExportDictionaryMarkdown} />
          <button type="button" data-testid="share-create" onClick={props.onCreateShareLink} />
          <button type="button" data-testid="share-copy" onClick={props.onCopyShareLink} />
        </>
      ) : null}
    </div>
  ),
  GroupModal: (props: any) => (
    <div data-testid="group-modal" data-open={props.isOpen}>
      <button type="button" data-testid="group-create-guard" onClick={props.onCreateBusinessGroup} />
      {props.isOpen ? (
        <>
          <button type="button" data-testid="group-name" onClick={() => props.setNewGroupName('Billing')} />
          <button type="button" data-testid="group-create" onClick={props.onCreateBusinessGroup} />
          <button type="button" data-testid="group-assign-missing" onClick={() => props.onAssignBusinessGroup(props.nodes[0]?.id ?? 'missing-node', 'missing')} />
          <button type="button" data-testid="group-assign" onClick={() => props.onAssignBusinessGroup(props.nodes[0]?.id ?? 'missing-node', props.businessGroups[0]?.id ?? '')} />
          <button type="button" data-testid="group-delete" onClick={() => props.onDeleteBusinessGroup(props.businessGroups[0]?.id ?? 'missing')} />
          <button type="button" data-testid="group-close" onClick={props.onCloseGroupManager} />
        </>
      ) : null}
    </div>
  ),
  CardinalityModal: (props: any) => {
    const recommendation = {
      index_name: 'idx_users_email',
      columns: ['email'],
      access_method: 'btree',
      estimated_distinct: 50,
      cardinality_ratio: 0.5,
      strength: 'recommended',
      reason: 'selective',
      source: 'cardinality-wizard',
    }
    return (
      <div data-testid="cardinality-modal" data-open={props.isOpen}>
        <span data-testid="card-format">{props.formatPercent(0.5)}</span>
        <span data-testid="card-strength-recommended">{props.strengthLabel('recommended')}</span>
        <span data-testid="card-strength-consider">{props.strengthLabel('consider')}</span>
        <span data-testid="card-strength-skip">{props.strengthLabel('skip')}</span>
        <button type="button" data-testid="card-skip-guard" onClick={() => props.onApplyCardinalityRecommendation({ ...recommendation, strength: 'skip' })} />
        {props.isOpen ? (
          <>
            <button type="button" data-testid="card-table-missing" onClick={() => props.onCardinalityTableChange('missing')} />
            <button type="button" data-testid="card-table" onClick={() => props.onCardinalityTableChange('table-2')} />
            <button type="button" data-testid="card-toggle" onClick={() => props.onCardinalityColumnToggle('email', true)} />
            <button type="button" data-testid="card-distinct-invalid" onClick={() => props.onCardinalityDistinctCountChange('email', 'bad')} />
            <button type="button" data-testid="card-distinct" onClick={() => props.onCardinalityDistinctCountChange('email', '50')} />
            <button type="button" data-testid="card-apply" onClick={() => props.onApplyCardinalityRecommendation(recommendation)} />
            <button type="button" data-testid="card-apply-duplicate" onClick={() => props.onApplyCardinalityRecommendation(recommendation)} />
            <button type="button" data-testid="card-apply-no-columns" onClick={() => props.onApplyCardinalityRecommendation({ ...recommendation, columns: undefined })} />
            <button type="button" data-testid="card-apply-empty" onClick={() => props.onApplyCardinalityRecommendation({ ...recommendation, index_name: '', columns: [], strength: 'consider' })} />
            <button type="button" data-testid="card-apply-second" onClick={() => props.onApplyCardinalityRecommendation({ ...recommendation, index_name: 'idx_users_second', columns: ['id'] })} />
            <button
              type="button"
              data-testid="card-clear-apply"
              onClick={() => {
                const clearButton = document.querySelector<HTMLButtonElement>('[aria-label="모든 노드 지우기"]')
                clearButton?.click()
                props.onApplyCardinalityRecommendation(recommendation)
              }}
            />
            <button type="button" data-testid="card-close" onClick={props.onCloseCardinalityWizard} />
          </>
        ) : null}
      </div>
    )
  },
  EditTableModal: (props: any) => (
    <div data-testid="table-modal" data-open={props.isOpen}>
      <button type="button" data-testid="table-delete-guard" onClick={props.onDeleteTable} />
      <form data-testid="table-submit-guard" onSubmit={props.onEditTableSubmit} />
      {props.isOpen && props.editingNode ? (
        <>
          <form data-testid="table-form" onSubmit={props.onEditTableSubmit}>
            <input name="title" defaultValue=" public.accounts " />
            <input name="comment" defaultValue=" " />
            <input name="col_name_0" defaultValue=" " />
            <input name="col_type_0" defaultValue=" " />
            <input name="col_pk_0" type="checkbox" defaultChecked />
            <input name="col_nn_0" type="checkbox" defaultChecked />
            <button type="submit">submit edit</button>
          </form>
          <form data-testid="table-empty-form" onSubmit={props.onEditTableSubmit}>
            <input name="title" defaultValue=" " />
            <input name="comment" defaultValue=" " />
          </form>
          <button type="button" data-testid="table-delete" onClick={props.onDeleteTable} />
          <button type="button" data-testid="table-cancel" onClick={props.onEditTableCancel} />
        </>
      ) : null}
    </div>
  ),
}))

import App, { DiagramTable } from './App'
import { snapshotToGraph } from './erd/convert'

const projects = [
  { project_space_uuid: 'p1', project_name: '<Billing & Core>' },
  { project_space_uuid: 'p2', project_name: 'HR' },
]
const connections = [{ db_connection_uuid: 'c1', conn_name: 'Warehouse' }]
const snapshots = [
  { schema_snapshot_uuid: 's1', status: 'succeeded', schema_filter: 'billing' },
  { schema_snapshot_uuid: 's2', status: 'failed', schema_filter: null },
]

beforeEach(() => {
  vi.clearAllMocks()
  api.getMe.mockResolvedValue({ subject: 'user', display_name: 'User', user_account_uuid: 'u' })
  api.listProjects.mockResolvedValue(projects)
  api.listConnections.mockResolvedValue(connections)
  api.listSnapshots.mockResolvedValue(snapshots)
  api.createProject.mockResolvedValue({ project_space_uuid: 'p3', project_name: 'New' })
  api.createConnection.mockResolvedValue({ db_connection_uuid: 'c2', conn_name: 'New DB' })
  api.createSnapshot.mockResolvedValue({ schema_snapshot_uuid: 's3', status: 'queued', schema_filter: 'public' })
  api.getSnapshot.mockResolvedValue({
    schema_snapshot_uuid: 's3',
    status: 'succeeded',
    schema_filter: 'public',
    error_message: null,
    snapshot_json: { relations: [], columns: [], pk_columns: [], fk_edges: [] },
  })
  api.createShareLink.mockResolvedValue({ url: 'http://localhost/api/share/one' })
  exports.inferRelationships.mockReturnValue([
    { id: 'inferred', source: 'table-1', target: 'table-2', label: 'fk_inferred' },
  ])
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
    callback(0)
    return 1
  })
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
  })
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

async function renderReadyApp() {
  render(<App />)
  await screen.findByRole('heading', { name: '대시보드' })
}

function forceClick(button: HTMLButtonElement) {
  button.disabled = false
  button.removeAttribute('disabled')
  button.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }))
}

describe('App orchestration coverage', () => {
  it('shows loading and explicit authentication failure', async () => {
    let rejectMe!: (reason?: unknown) => void
    api.getMe.mockReturnValueOnce(new Promise((_resolve, reject) => { rejectMe = reject }))
    render(<App />)
    expect(screen.getByText('Authenticating…')).toBeInTheDocument()
    await act(async () => rejectMe(new Error('denied')))
    expect(await screen.findByRole('heading', { name: 'Authentication required' })).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('denied')
  })

  it('navigates dashboard, project, and diagram states including empty/search branches', async () => {
    await renderReadyApp()
    expect(screen.getAllByText('&lt;Billing &amp; Core&gt;').length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: '전체 보기' }))
    expect(screen.getByRole('heading', { name: '프로젝트' })).toBeInTheDocument()
    fireEvent.click(screen.getAllByRole('button', { name: '열기' })[1]!)
    expect(screen.getByRole('heading', { name: '다이어그램' })).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('다이어그램 검색'), { target: { value: 'no-match' } })
    expect(screen.getByText('검색 결과가 없습니다.')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('다이어그램 검색'), { target: { value: 'failed' } })
    expect(screen.getByText('ERD_all_2')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '편집기 열기' }))
    expect(screen.getByRole('toolbar', { name: 'ERD 캔버스 도구' })).toBeInTheDocument()

    cleanup()
    api.listProjects.mockResolvedValueOnce([])
    await act(async () => render(<App />))
    await screen.findByText('아직 프로젝트가 없습니다. 편집기에서 프로젝트를 생성하세요.')
    fireEvent.click(screen.getByRole('button', { name: '전체 보기' }))
    expect(screen.getByText('프로젝트가 없습니다. 이름을 입력해 새 프로젝트를 만드세요.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '다이어그램' }))
    expect(screen.getByText('프로젝트를 선택하세요.')).toBeInTheDocument()
  })

  it('creates projects, validates and creates connections, and starts a snapshot', async () => {
    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '편집기' }))

    fireEvent.change(screen.getByLabelText('New project'), { target: { value: '  New  ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create' }))
    await waitFor(() => expect(api.createProject).toHaveBeenCalledWith('New'))

    const dsn = screen.getByLabelText('Connection DSN')
    fireEvent.change(dsn, { target: { value: 'postgresql://[' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save connection' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Connection DSN must use')
    fireEvent.change(dsn, { target: { value: 'http://bad.example/db' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save connection' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Connection DSN must use')
    expect(dsn).toHaveValue('')

    fireEvent.change(dsn, { target: { value: 'postgresql://db.example/test' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save connection' }))
    await waitFor(() => expect(api.createConnection).toHaveBeenCalledWith('p3', 'target-db', 'postgresql://db.example/test'))

    fireEvent.change(screen.getByLabelText('Schema filter (optional)'), { target: { value: ' public ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Reverse engineer → snapshot' }))
    await waitFor(() => expect(api.createSnapshot).toHaveBeenCalledWith('p3', 'c2', 'public'))
    expect(screen.getByText('스냅샷 생성 중...')).toBeInTheDocument()
  })

  it('polls a terminal snapshot, builds graph state, and exercises editor handlers', async () => {
    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '다이어그램' }))
    const openButtons = await screen.findAllByRole('button', { name: '열기' })
    vi.useFakeTimers()
    fireEvent.click(openButtons[0]!)
    await act(async () => {
      vi.advanceTimersByTime(1000)
      await Promise.resolve()
      await Promise.resolve()
    })
    expect(api.getSnapshot).toHaveBeenCalledWith('s1')
    expect(screen.getByTestId('node-count')).toHaveTextContent('2')

    fireEvent.change(screen.getByLabelText('테이블 또는 컬럼 검색'), { target: { value: 'users' } })
    expect(screen.getByText('1개 테이블 일치', { exact: false })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'ERD 자동 정렬' }))
    await act(async () => {
      vi.runOnlyPendingTimers()
      await Promise.resolve()
    })
    expect(screen.getByText('정렬 완료', { exact: false })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '정렬 되돌리기' }))
    expect(screen.getByText('되돌렸습니다', { exact: false })).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('flow-connect'))
    fireEvent.click(screen.getByTestId('edge-label'))
    fireEvent.click(screen.getByTestId('edge-submit'))
    fireEvent.click(screen.getByTestId('flow-edge'))
    fireEvent.click(screen.getByTestId('edge-cancel'))
    fireEvent.click(screen.getByTestId('flow-edge-unlabeled'))
    fireEvent.click(screen.getByTestId('edge-cancel'))
    fireEvent.click(screen.getByTestId('flow-edge'))
    vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    fireEvent.click(screen.getByTestId('edge-delete'))
    fireEvent.click(screen.getByTestId('edge-delete'))

    fireEvent.doubleClick(screen.getByTestId('flow-node'))
    fireEvent.submit(screen.getByTestId('table-empty-form'))
    fireEvent.click(screen.getByTestId('table-cancel'))
    fireEvent.doubleClick(screen.getByTestId('flow-node'))
    fireEvent.submit(screen.getByTestId('table-form'))
    fireEvent.doubleClick(screen.getByTestId('flow-node'))
    fireEvent.click(screen.getByTestId('table-cancel'))
    fireEvent.doubleClick(screen.getByTestId('flow-node'))
    vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    fireEvent.click(screen.getByTestId('table-delete'))
    fireEvent.click(screen.getByTestId('table-delete'))
  })

  it('adds nodes and exercises groups, cardinality, exports, inference, and clearing', async () => {
    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '편집기' }))
    fireEvent.click(screen.getAllByRole('button', { name: '테이블 추가' })[0]!)
    fireEvent.click(screen.getByTestId('add-name'))
    fireEvent.click(screen.getByTestId('add-submit'))
    expect(screen.getByTestId('node-count')).toHaveTextContent('1')

    fireEvent.click(screen.getByRole('button', { name: '업무 그룹' }))
    fireEvent.click(screen.getByTestId('group-create-guard'))
    fireEvent.click(screen.getByTestId('group-name'))
    fireEvent.click(screen.getByTestId('group-create'))
    fireEvent.click(screen.getByTestId('group-assign-missing'))
    fireEvent.click(screen.getByTestId('group-assign'))
    vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    fireEvent.click(screen.getByTestId('group-delete'))
    fireEvent.click(screen.getByTestId('group-delete'))
    fireEvent.click(screen.getByTestId('group-close'))

    fireEvent.click(screen.getByRole('button', { name: '인덱스 카디널리티 계산' }))
    expect(screen.getByTestId('card-format')).toHaveTextContent('50%')
    expect(screen.getByTestId('card-strength-recommended')).toHaveTextContent('추천')
    expect(screen.getByTestId('card-strength-consider')).toHaveTextContent('검토')
    expect(screen.getByTestId('card-strength-skip')).toHaveTextContent('보류')
    fireEvent.click(screen.getByTestId('card-table-missing'))
    fireEvent.click(screen.getByTestId('card-table'))
    fireEvent.click(screen.getByTestId('card-toggle'))
    fireEvent.click(screen.getByTestId('card-distinct-invalid'))
    fireEvent.click(screen.getByTestId('card-distinct'))
    fireEvent.click(screen.getByTestId('card-apply'))
    fireEvent.click(screen.getByTestId('card-apply-duplicate'))
    fireEvent.click(screen.getByTestId('card-apply-no-columns'))
    fireEvent.click(screen.getByTestId('card-apply-empty'))
    fireEvent.click(screen.getByTestId('card-apply-second'))
    fireEvent.click(screen.getByTestId('card-close'))

    fireEvent.click(screen.getByRole('button', { name: 'DDL 내보내기' }))
    for (const id of ['export-copy-ddl', 'export-svg', 'export-uml', 'export-mermaid', 'export-dbml', 'export-csv', 'export-md']) {
      fireEvent.click(screen.getByTestId(id))
    }
    fireEvent.click(screen.getByTestId('share-create'))
    await waitFor(() => expect(screen.getByTestId('share-url')).toHaveTextContent('/api/share/one'))
    fireEvent.click(screen.getByTestId('share-copy'))
    fireEvent.click(screen.getByTestId('export-close'))
    expect(exports.downloadText).toHaveBeenCalledTimes(6)

    fireEvent.click(screen.getByRole('button', { name: '관계 자동 추론' }))
    expect(exports.inferRelationships).toHaveBeenCalled()
    exports.inferRelationships.mockReturnValueOnce([])
    fireEvent.click(screen.getByRole('button', { name: '관계 자동 추론' }))
    vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    fireEvent.click(screen.getByRole('button', { name: '모든 노드 지우기' }))
    fireEvent.click(screen.getByRole('button', { name: '모든 노드 지우기' }))
    expect(screen.getByText('ERD 캔버스가 비어 있습니다')).toBeInTheDocument()
  })

  it('covers guarded editor actions, navigation callbacks, and form selectors', async () => {
    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '편집기' }))

    for (const id of [
      'edge-guard-submit',
      'edge-guard-delete',
      'share-copy-guard',
      'table-delete-guard',
      'add-guard',
      'group-create-guard',
      'card-skip-guard',
    ]) {
      fireEvent.click(screen.getByTestId(id))
    }
    fireEvent.submit(screen.getByTestId('table-submit-guard'))

    for (const name of [
      'ERD 자동 정렬',
      '정렬 되돌리기',
      '업무 그룹',
      '인덱스 카디널리티 계산',
    ]) {
      const button = screen.getByRole('button', { name }) as HTMLButtonElement
      forceClick(button)
    }
    fireEvent.click(screen.getByRole('button', { name: '공유 및 내보내기' }))
    fireEvent.click(screen.getByTestId('export-close'))

    fireEvent.change(screen.getByLabelText('Project'), { target: { value: 'p2' } })
    fireEvent.change(screen.getByLabelText('Connection'), { target: { value: 'c1' } })
    fireEvent.change(screen.getByLabelText('New connection (DSN)'), { target: { value: 'Analytics' } })

    fireEvent.change(screen.getByLabelText('New project'), { target: { value: ' ' } })
    forceClick(screen.getByRole('button', { name: 'Create' }))
    fireEvent.change(screen.getByLabelText('New project'), { target: { value: 'demo' } })

    fireEvent.change(screen.getByLabelText('Project'), { target: { value: '' } })
    forceClick(screen.getByRole('button', { name: 'Save connection' }))
    fireEvent.change(screen.getByLabelText('Project'), { target: { value: 'p1' } })
    fireEvent.change(screen.getByLabelText('New connection (DSN)'), { target: { value: ' ' } })
    forceClick(screen.getByRole('button', { name: 'Save connection' }))
    fireEvent.change(screen.getByLabelText('Connection'), { target: { value: '' } })
    forceClick(screen.getByRole('button', { name: 'Reverse engineer → snapshot' }))
    fireEvent.click(screen.getAllByRole('button', { name: '테이블 추가' })[0]!)
    fireEvent.click(screen.getByTestId('add-cancel'))

    fireEvent.click(screen.getByRole('button', { name: '대시보드' }))
    fireEvent.click(screen.getByRole('button', { name: /Billing.*다이어그램 보기/ }))
    expect(screen.getByRole('heading', { name: '다이어그램' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '대시보드' }))
    await waitFor(() => expect(screen.getAllByRole('button', { name: '열기' }).length).toBeGreaterThan(0))
    fireEvent.click(screen.getAllByRole('button', { name: '열기' })[0]!)
    expect(screen.getByRole('toolbar', { name: 'ERD 캔버스 도구' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '대시보드' }))
    fireEvent.click(screen.getByRole('button', { name: '편집기로 이동' }))
    expect(screen.getByRole('toolbar', { name: 'ERD 캔버스 도구' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '대시보드' }))
    fireEvent.click(screen.getByRole('button', { name: '새 모델링' }))
    expect(screen.getByRole('toolbar', { name: 'ERD 캔버스 도구' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '프로젝트' }))
    fireEvent.change(screen.getByLabelText('새 프로젝트 이름'), { target: { value: 'Roadmap' } })
    fireEvent.click(screen.getByRole('button', { name: '새 프로젝트' }))
    await waitFor(() => expect(api.createProject).toHaveBeenCalledWith('Roadmap'))
    fireEvent.click(screen.getAllByRole('button', { name: '열기' })[0]!)
    expect(screen.getByRole('heading', { name: '다이어그램' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '대시보드' }))
    fireEvent.click(screen.getByRole('button', { name: '목록 보기' }))
  })

  it('clears replacement copy timers and pending timers during close and unmount', async () => {
    vi.useFakeTimers()
    await act(async () => {
      render(<App />)
      await Promise.resolve()
      await Promise.resolve()
    })
    fireEvent.click(screen.getByRole('button', { name: '편집기' }))
    fireEvent.click(screen.getAllByRole('button', { name: '테이블 추가' })[0]!)
    fireEvent.click(screen.getByTestId('add-name'))
    fireEvent.click(screen.getByTestId('add-submit'))
    fireEvent.click(screen.getByRole('button', { name: '공유 및 내보내기' }))
    fireEvent.click(screen.getByTestId('export-copy-ddl'))
    fireEvent.click(screen.getByTestId('export-copy-ddl'))
    fireEvent.click(screen.getByTestId('share-create'))
    await act(async () => {
      await Promise.resolve()
      await Promise.resolve()
    })
    fireEvent.click(screen.getByTestId('share-copy'))
    await act(async () => { await Promise.resolve() })
    fireEvent.click(screen.getByTestId('share-copy'))
    await act(async () => { await Promise.resolve() })
    await act(async () => {
      vi.advanceTimersByTime(2000)
      await Promise.resolve()
    })
    fireEvent.click(screen.getByTestId('export-close'))

    fireEvent.click(screen.getByRole('button', { name: '공유 및 내보내기' }))
    fireEvent.click(screen.getByTestId('export-copy-ddl'))
    fireEvent.click(screen.getByTestId('share-create'))
    await act(async () => { await Promise.resolve() })
    fireEvent.click(screen.getByTestId('share-copy'))
    await act(async () => { await Promise.resolve() })
    fireEvent.click(screen.getByTestId('export-close'))

    fireEvent.click(screen.getByRole('button', { name: '공유 및 내보내기' }))
    fireEvent.click(screen.getByTestId('export-copy-ddl'))
    fireEvent.click(screen.getByTestId('share-create'))
    await act(async () => { await Promise.resolve() })
    fireEvent.click(screen.getByTestId('share-copy'))
    await act(async () => { await Promise.resolve() })
    cleanup()
  })

  it('ignores authentication completions after unmount', async () => {
    let resolveMe!: (value: any) => void
    api.getMe.mockReturnValueOnce(new Promise((resolve) => { resolveMe = resolve }))
    render(<App />)
    cleanup()
    await act(async () => resolveMe({ subject: 'late', display_name: 'Late' }))

    let rejectMe!: (reason: unknown) => void
    api.getMe.mockReturnValueOnce(new Promise((_resolve, reject) => { rejectMe = reject }))
    render(<App />)
    cleanup()
    await act(async () => rejectMe(new Error('late failure')))
  })

  it('logs auto-layout failures and preserves nodes added after the undo snapshot', async () => {
    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '다이어그램' }))
    vi.useFakeTimers()
    fireEvent.click(screen.getAllByRole('button', { name: '열기' })[0]!)
    await act(async () => {
      vi.advanceTimersByTime(1000)
      await Promise.resolve()
      await Promise.resolve()
    })
    vi.useRealTimers()

    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.stubGlobal('requestAnimationFrame', () => { throw new Error('frame unavailable') })
    fireEvent.click(screen.getByRole('button', { name: 'ERD 자동 정렬' }))
    await waitFor(() => expect(screen.getByText('정렬에 실패했습니다. 다시 시도해 주세요.', { exact: false })).toBeInTheDocument())
    expect(consoleError).toHaveBeenCalled()

    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { callback(0); return 1 })
    fireEvent.click(screen.getByRole('button', { name: 'ERD 자동 정렬' }))
    await screen.findByText('정렬 완료', { exact: false })
    fireEvent.click(screen.getAllByRole('button', { name: '테이블 추가' })[0]!)
    fireEvent.click(screen.getByTestId('add-name'))
    fireEvent.click(screen.getByTestId('add-submit'))
    fireEvent.click(screen.getByRole('button', { name: '정렬 되돌리기' }))
    expect(screen.getByTestId('node-count')).toHaveTextContent('3')
  })

  it('shows terminal refresh failures from the polling loop', async () => {
    api.listSnapshots
      .mockResolvedValueOnce(snapshots)
      .mockRejectedValueOnce(new Error('terminal refresh down'))
    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '다이어그램' }))
    vi.useFakeTimers()
    fireEvent.click(screen.getAllByRole('button', { name: '열기' })[0]!)
    await act(async () => {
      vi.advanceTimersByTime(1000)
      await Promise.resolve()
      await Promise.resolve()
    })
    expect(screen.getByRole('alert')).toHaveTextContent('terminal refresh down')
  })

  it('ignores stale project metadata failures after changing projects', async () => {
    let rejectConnections!: (reason: unknown) => void
    let rejectSnapshots!: (reason: unknown) => void
    api.listConnections
      .mockReturnValueOnce(new Promise((_resolve, reject) => { rejectConnections = reject }))
      .mockResolvedValueOnce(connections)
    api.listSnapshots
      .mockReturnValueOnce(new Promise((_resolve, reject) => { rejectSnapshots = reject }))
      .mockResolvedValueOnce(snapshots)
    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '편집기' }))
    fireEvent.change(screen.getByLabelText('Project'), { target: { value: 'p2' } })
    await act(async () => {
      rejectConnections(new Error('stale connections'))
      rejectSnapshots(new Error('stale snapshots'))
      await Promise.resolve()
    })
    expect(screen.queryByText(/stale (connections|snapshots)/)).not.toBeInTheDocument()
  })

  it('renders snapshot failures and polls without a selected project', async () => {
    api.getSnapshot.mockResolvedValue({
      schema_snapshot_uuid: 's3',
      status: 'failed',
      schema_filter: null,
      error_message: 'database rejected snapshot',
      snapshot_json: null,
    })
    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '편집기' }))
    fireEvent.change(screen.getByLabelText('Connection DSN'), { target: { value: 'postgresql://db.example/test' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save connection' }))
    await waitFor(() => expect(api.createConnection).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('button', { name: 'Reverse engineer → snapshot' }))
    await waitFor(() => expect(api.createSnapshot).toHaveBeenCalledWith('p1', 'c2', undefined))

    vi.useFakeTimers()
    fireEvent.change(screen.getByLabelText('Project'), { target: { value: '' } })
    await act(async () => {
      vi.advanceTimersByTime(1000)
      await Promise.resolve()
      await Promise.resolve()
    })
    expect(screen.getByRole('alert')).toHaveTextContent('database rejected snapshot')
  })

  it('renders user identity fallbacks and a diagram list without a project label', async () => {
    api.getMe.mockResolvedValueOnce({ subject: 'subject-only', display_name: null })
    await renderReadyApp()
    expect(screen.getByText('subject-only')).toBeInTheDocument()

    cleanup()
    api.getMe.mockResolvedValueOnce({ subject: '', display_name: null })
    await renderReadyApp()
    expect(screen.getByText('인증 필요')).toBeInTheDocument()

    cleanup()
    const onOpenEditor = vi.fn()
    render(
      <DiagramTable
        snapshots={snapshots}
        selectedProjectName=""
        onOpenEditor={onOpenEditor}
      />,
    )
    expect(screen.getAllByText('현재 프로젝트')).toHaveLength(2)
    fireEvent.click(screen.getAllByRole('button', { name: '열기' })[0]!)
    expect(onOpenEditor).toHaveBeenCalledWith('s1')
  })

  it('ignores duplicate share creation while a request is pending', async () => {
    let resolveShare!: (value: { url: string }) => void
    api.createShareLink.mockReturnValueOnce(new Promise((resolve) => { resolveShare = resolve }))
    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '편집기' }))
    fireEvent.click(screen.getByRole('button', { name: '공유 및 내보내기' }))
    fireEvent.click(screen.getByTestId('share-create'))
    fireEvent.click(screen.getByTestId('share-create'))
    expect(api.createShareLink).toHaveBeenCalledTimes(1)
    await act(async () => resolveShare({ url: 'http://localhost/api/share/done' }))
  })

  it('preserves positions across graph refresh and applies recommendations with sibling nodes', async () => {
    let pollCount = 0
    api.getSnapshot.mockImplementation(async () => ({
      schema_snapshot_uuid: 's3',
      status: pollCount++ === 0 ? 'running' : 'succeeded',
      schema_filter: 'public',
      error_message: null,
      snapshot_json: { relations: [], columns: [], pk_columns: [], fk_edges: [] },
    }))
    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '다이어그램' }))
    vi.useFakeTimers()
    fireEvent.click(screen.getAllByRole('button', { name: '열기' })[0]!)
    await act(async () => {
      vi.advanceTimersByTime(1000)
      await Promise.resolve()
      await Promise.resolve()
    })
    expect(screen.getByTestId('node-count')).toHaveTextContent('2')
    await act(async () => {
      vi.advanceTimersByTime(1000)
      await Promise.resolve()
      await Promise.resolve()
    })
    vi.useRealTimers()
    expect(screen.getByTestId('node-count')).toHaveTextContent('2')

    fireEvent.click(screen.getByRole('button', { name: '업무 그룹' }))
    fireEvent.click(screen.getByTestId('group-name'))
    fireEvent.click(screen.getByTestId('group-create'))
    fireEvent.click(screen.getByTestId('group-assign'))
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    fireEvent.click(screen.getByTestId('group-delete'))
    fireEvent.click(screen.getByTestId('group-close'))

    fireEvent.click(screen.getByRole('button', { name: '인덱스 카디널리티 계산' }))
    fireEvent.click(screen.getByTestId('card-table'))
    fireEvent.click(screen.getByTestId('card-apply'))
    fireEvent.click(screen.getByTestId('card-clear-apply'))
  })

  it('falls back to node ids when auto-layout receives legacy nodes without titles', async () => {
    vi.mocked(snapshotToGraph).mockReturnValueOnce({
      nodes: [
        { id: 'z-node', type: 'tableNode', position: { x: 0, y: 0 }, data: { columns: [], badges: { pk: false, fk: false } } },
        { id: 'a-node', type: 'tableNode', position: { x: 1, y: 1 }, data: { columns: [], badges: { pk: false, fk: false } } },
      ] as any,
      edges: [],
    })
    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '다이어그램' }))
    await waitFor(() => expect(screen.getAllByRole('button', { name: '열기' }).length).toBeGreaterThan(0))
    vi.useFakeTimers()
    fireEvent.click(screen.getAllByRole('button', { name: '열기' })[0]!)
    await act(async () => {
      vi.advanceTimersByTime(1000)
      await Promise.resolve()
      await Promise.resolve()
    })
    vi.useRealTimers()
    fireEvent.click(screen.getByRole('button', { name: 'ERD 자동 정렬' }))
    await screen.findByText('정렬 완료', { exact: false })
  })

  it('reports API effect failures, snapshot polling failures, share failures, and clipboard failures', async () => {
    api.listConnections.mockRejectedValueOnce(new Error('connections down'))
    api.listSnapshots.mockRejectedValueOnce(new Error('snapshots down'))
    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '편집기' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/down/)
    fireEvent.click(screen.getAllByRole('button', { name: '테이블 추가' })[0]!)
    fireEvent.click(screen.getByTestId('add-name'))
    fireEvent.click(screen.getByTestId('add-submit'))
    fireEvent.click(screen.getByRole('button', { name: '공유 및 내보내기' }))
    api.createShareLink.mockRejectedValueOnce(new Error('share down'))
    fireEvent.click(screen.getByTestId('share-create'))
    await waitFor(() => expect(screen.getByTestId('share-error')).toHaveTextContent('share down'))

    api.createShareLink.mockResolvedValueOnce({ url: 'http://localhost/api/share/fail-copy' })
    fireEvent.click(screen.getByTestId('share-create'))
    await waitFor(() => expect(screen.getByTestId('share-url')).toHaveTextContent('fail-copy'))
    vi.mocked(navigator.clipboard.writeText).mockRejectedValueOnce(new Error('copy down'))
    fireEvent.click(screen.getByTestId('share-copy'))
    await waitFor(() => expect(screen.getByTestId('share-error')).toHaveTextContent('복사에 실패'))

    cleanup()
    vi.useRealTimers()
    api.listConnections.mockResolvedValue(connections)
    api.listSnapshots.mockResolvedValue(snapshots)
    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '다이어그램' }))
    await waitFor(() => expect(screen.getAllByRole('button', { name: '열기' }).length).toBeGreaterThan(0))
    vi.useFakeTimers()
    api.getSnapshot.mockRejectedValueOnce(new Error('poll down'))
    fireEvent.click(screen.getAllByRole('button', { name: '열기' })[0]!)
    await act(async () => {
      vi.advanceTimersByTime(1000)
      await Promise.resolve()
    })
    expect(screen.getByRole('alert')).toHaveTextContent('poll down')
  })
})
