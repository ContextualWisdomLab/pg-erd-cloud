import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  getMe: vi.fn(),
  publicShareIdFromPath: vi.fn<(pathname: string) => string | null>(() => null),
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
  exportPrisma: vi.fn(() => 'model Users {}'),
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
vi.mock('./erd/prisma', () => ({ exportPrisma: exports.exportPrisma }))
vi.mock('./erd/autoInfer', () => ({ inferRelationships: exports.inferRelationships }))
vi.mock('./components/SharedDiagramView', () => ({
  SharedDiagramView: ({ shareLinkId, colorMode }: { shareLinkId: string; colorMode: string }) => (
    <main aria-label="공유 ERD 테스트" data-color-mode={colorMode}>{shareLinkId}</main>
  ),
}))

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
      <div data-testid="react-flow" data-color-mode={String(props.colorMode)}>
        <span data-testid="node-count">{props.nodes.length}</span>
        <span data-testid="edge-count">{props.edges.length}</span>
        <button type="button" data-testid="flow-connect" onClick={() => props.onConnect?.({ source: 'table-1', target: 'table-2' })} />
        <button type="button" data-testid="flow-edge" onClick={(event) => props.onEdgeClick?.(event, props.edges[0] ?? edge)} />
        <button
          type="button"
          data-testid="flow-edge-keyboard"
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              props.onSelectionChange?.({
                nodes: [],
                edges: [props.edges[0] ?? edge],
              })
            }
          }}
        />
        <button type="button" data-testid="flow-edge-unlabeled" onClick={(event) => props.onEdgeClick?.(event, { ...edge, label: undefined })} />
        <button
          type="button"
          data-testid="flow-node"
          onClick={() => props.onSelectionChange?.({
            nodes: [props.nodes[0] ?? initialNode],
            edges: [],
          })}
          onDoubleClick={(event) => props.onNodeDoubleClick?.(event, props.nodes[0] ?? initialNode)}
        />
        <button
          type="button"
          data-testid="flow-clear-selection"
          onClick={() => props.onSelectionChange?.({ nodes: [], edges: [] })}
        />
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
      <span data-testid="share-copied">{String(props.isShareLinkCopied)}</span>
      <button type="button" data-testid="share-copy-guard" onClick={props.onCopyShareLink} />
      {props.isOpen ? (
        <>
          <button type="button" data-testid="export-close" onClick={props.onCloseExport} />
          <button type="button" data-testid="export-copy-ddl" onClick={props.onCopyExportDdl} />
          <button type="button" data-testid="export-svg" onClick={props.onDownloadSvg} />
          <button type="button" data-testid="export-uml" onClick={props.onDownloadUml} />
          <button type="button" data-testid="export-mermaid" onClick={props.onDownloadMermaid} />
          <button type="button" data-testid="export-dbml" onClick={props.onDownloadDbml} />
          <button type="button" data-testid="export-prisma" onClick={props.onDownloadPrisma} />
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
import type { SnapshotDetail } from './types'

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
  Object.values(api).forEach((mock) => mock.mockReset())
  Object.values(exports).forEach((mock) => mock.mockReset())
  api.publicShareIdFromPath.mockReturnValue(null)
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
  exports.exportDDL.mockReturnValue('DDL')
  exports.exportDiagramSvg.mockReturnValue('<svg/>')
  exports.exportDictionaryCsv.mockReturnValue('csv')
  exports.exportDictionaryMarkdown.mockReturnValue('markdown')
  exports.exportPlantUml.mockReturnValue('@startuml')
  exports.exportMermaid.mockReturnValue('graph TD')
  exports.exportDbml.mockReturnValue('Table users {}')
  exports.exportPrisma.mockReturnValue('model Users {}')
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

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

describe('App orchestration coverage', () => {
  it('shows loading and explicit authentication failure', async () => {
    let rejectMe!: (reason?: unknown) => void
    api.getMe.mockReturnValueOnce(new Promise((_resolve, reject) => { rejectMe = reject }))
    render(<App />)
    expect(screen.getByText('인증 정보를 확인하는 중입니다.')).toBeInTheDocument()
    await act(async () => rejectMe(new Error('denied')))
    expect(await screen.findByRole('heading', { name: 'Cloud ERD' })).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('인증이 필요합니다')
    expect(screen.getByRole('alert')).not.toHaveTextContent('denied')
    expect(screen.getByRole('button', { name: '다시 시도' })).toBeInTheDocument()
  })

  it('renders the public share route instead of the authenticated shell', () => {
    api.publicShareIdFromPath.mockReturnValueOnce('share-public')
    render(<App />)
    expect(screen.getByRole('main', { name: '공유 ERD 테스트' })).toHaveTextContent('share-public')
    expect(screen.getByRole('main', { name: '공유 ERD 테스트' })).toHaveAttribute('data-color-mode', 'system')
    expect(api.getMe).not.toHaveBeenCalled()
  })

  it('keeps the authenticated workspace when the project list fails', async () => {
    api.listProjects.mockRejectedValueOnce(new Error('projects down'))
    await renderReadyApp()
    expect(screen.getByText('User')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('프로젝트 목록을 불러오지 못했습니다')
    expect(screen.getByRole('alert')).not.toHaveTextContent('projects down')
  })

  it('keeps the connection selector empty when a project has no connections', async () => {
    api.listConnections.mockResolvedValueOnce([])
    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '편집기' }))
    expect(screen.getByLabelText('Connection')).toHaveValue('')
  })

  it('navigates dashboard, project, and diagram states including empty/search branches', async () => {
    await renderReadyApp()
    expect(screen.getAllByText('<Billing & Core>').length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: '전체 보기' }))
    expect(screen.getByRole('heading', { name: '프로젝트' })).toBeInTheDocument()
    fireEvent.click(screen.getAllByRole('button', { name: '열기' })[1]!)
    expect(screen.getByRole('heading', { name: '다이어그램' })).toBeInTheDocument()
    await screen.findByText('ERD_all_2')
    fireEvent.change(screen.getByLabelText('다이어그램 검색'), { target: { value: 'no-match' } })
    expect(screen.getByText('검색 결과가 없습니다.')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('다이어그램 검색'), { target: { value: 'failed' } })
    expect(screen.getByText('ERD_all_2')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '편집기 열기' }))
    expect(screen.getByRole('toolbar', { name: 'ERD 캔버스 도구' })).toBeInTheDocument()
    expect(screen.getByTestId('react-flow')).toHaveAttribute('data-color-mode', 'system')

    cleanup()
    api.listProjects.mockResolvedValueOnce([])
    await act(async () => render(<App />))
    await screen.findByText('아직 프로젝트가 없습니다. 편집기에서 프로젝트를 생성하세요.')
    fireEvent.click(screen.getByRole('button', { name: '전체 보기' }))
    expect(screen.getByText('프로젝트가 없습니다. 이름을 입력해 새 프로젝트를 만드세요.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '다이어그램' }))
    expect(screen.getByText('프로젝트를 선택하세요.')).toBeInTheDocument()
  })

  it('describes why inspector share and export actions are unavailable', async () => {
    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '편집기' }))

    expect(screen.getByRole('button', { name: '내보내기 열기' })).toHaveAccessibleDescription(
      '내보내려면 캔버스에 테이블을 추가하세요.',
    )

    fireEvent.change(screen.getByLabelText('Project'), { target: { value: '' } })
    expect(screen.getByRole('button', { name: '공유 열기' })).toHaveAccessibleDescription(
      '공유 링크를 만들려면 프로젝트를 선택하세요.',
    )
  })

  it('creates projects, validates and creates connections, and starts a snapshot', async () => {
    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '편집기' }))

    fireEvent.change(screen.getByLabelText('New project'), { target: { value: '  New  ' } })
    fireEvent.submit(screen.getByRole('form', { name: '사이드바 프로젝트 생성' }))
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
    fireEvent.submit(screen.getByRole('form', { name: '연결 생성' }))
    await waitFor(() => expect(api.createConnection).toHaveBeenCalledWith('p3', 'target-db', 'postgresql://db.example/test'))

    fireEvent.change(screen.getByLabelText('Schema filter (optional)'), { target: { value: ' public ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Reverse engineer → snapshot' }))
    await waitFor(() => expect(api.createSnapshot).toHaveBeenCalledWith('p3', 'c2', 'public'))
    expect(screen.getByText('스냅샷 생성 중...')).toBeInTheDocument()
  })

  it('keeps create failures recoverable without exposing API diagnostics', async () => {
    api.createProject.mockRejectedValueOnce(new Error('project database secret'))
    api.createConnection.mockRejectedValueOnce(new Error('connection database secret'))
    api.createSnapshot.mockRejectedValueOnce(new Error('snapshot database secret'))
    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '편집기' }))

    fireEvent.change(screen.getByLabelText('New project'), { target: { value: 'New' } })
    fireEvent.submit(screen.getByRole('form', { name: '사이드바 프로젝트 생성' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('프로젝트를 만들지 못했습니다')
    expect(screen.getByRole('alert')).not.toHaveTextContent('project database secret')

    fireEvent.change(screen.getByLabelText('Connection DSN'), {
      target: { value: 'postgresql://db.example/test' },
    })
    fireEvent.submit(screen.getByRole('form', { name: '연결 생성' }))
    await waitFor(() => expect(api.createConnection).toHaveBeenCalled())
    expect(screen.getByRole('alert')).toHaveTextContent('데이터베이스 연결을 만들지 못했습니다')
    expect(screen.getByRole('alert')).not.toHaveTextContent('connection database secret')

    fireEvent.click(screen.getByRole('button', { name: 'Reverse engineer → snapshot' }))
    await waitFor(() => expect(api.createSnapshot).toHaveBeenCalled())
    expect(screen.getByRole('alert')).toHaveTextContent('스냅샷을 만들지 못했습니다')
    expect(screen.getByRole('alert')).not.toHaveTextContent('snapshot database secret')
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

    await act(async () => {
      fireEvent.click(screen.getByTestId('flow-node'))
      await Promise.resolve()
    })
    const properties = screen.getByRole('complementary', { name: 'ERD 속성' })
    expect(properties).toHaveTextContent('public.users')
    expect(properties).toHaveTextContent('email')
    expect(properties).toHaveTextContent('text')
    fireEvent.click(screen.getByTestId('flow-clear-selection'))
    expect(properties).toHaveTextContent('캔버스에서 테이블을 선택하면')
    const edgeKeyboardTarget = screen.getByTestId('flow-edge-keyboard')
    edgeKeyboardTarget.focus()
    fireEvent.keyDown(edgeKeyboardTarget, { key: 'Enter' })
    expect(properties).toHaveTextContent('fk_old')
    fireEvent.click(screen.getByRole('button', { name: '관계 편집' }))
    expect(screen.getByTestId('edge-modal')).toHaveAttribute('data-open', 'true')
    fireEvent.click(screen.getByTestId('edge-cancel'))
    fireEvent.click(screen.getByTestId('flow-node'))

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
    const relationshipConfirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    fireEvent.click(screen.getByTestId('edge-delete'))
    expect(screen.getByTestId('edge-count')).toHaveTextContent('2')
    fireEvent.click(screen.getByTestId('edge-delete'))
    expect(relationshipConfirm).toHaveBeenCalledTimes(2)
    expect(relationshipConfirm).toHaveBeenNthCalledWith(1, '정말로 이 관계를 삭제하시겠습니까?')
    expect(relationshipConfirm).toHaveBeenNthCalledWith(2, '정말로 이 관계를 삭제하시겠습니까?')
    expect(screen.getByTestId('edge-count')).toHaveTextContent('1')

    fireEvent.doubleClick(screen.getByTestId('flow-node'))
    fireEvent.submit(screen.getByTestId('table-empty-form'))
    fireEvent.click(screen.getByTestId('table-cancel'))
    fireEvent.doubleClick(screen.getByTestId('flow-node'))
    fireEvent.submit(screen.getByTestId('table-form'))
    fireEvent.doubleClick(screen.getByTestId('flow-node'))
    fireEvent.click(screen.getByTestId('table-cancel'))
    fireEvent.doubleClick(screen.getByTestId('flow-node'))
    const tableConfirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    tableConfirm.mockClear()
    fireEvent.click(screen.getByTestId('table-delete'))
    fireEvent.click(screen.getByTestId('table-delete'))
    expect(tableConfirm).toHaveBeenNthCalledWith(1, "'public.accounts' 테이블을 삭제하시겠습니까?")
    expect(tableConfirm).toHaveBeenNthCalledWith(2, "'public.accounts' 테이블을 삭제하시겠습니까?")
  })

  it('renders and edits an unnamed relationship when endpoint tables are unavailable', async () => {
    vi.mocked(snapshotToGraph).mockReturnValueOnce({
      nodes: [],
      edges: [
        {
          id: 'orphan-edge',
          source: 'missing-source',
          target: 'missing-target',
          label: undefined,
        },
      ],
    })

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

    const edgeKeyboardTarget = screen.getByTestId('flow-edge-keyboard')
    edgeKeyboardTarget.focus()
    fireEvent.keyDown(edgeKeyboardTarget, { key: 'Enter' })

    const properties = screen.getByRole('complementary', { name: 'ERD 속성' })
    expect(properties).toHaveTextContent('이름 없는 관계')
    expect(properties).toHaveTextContent('missing-source → missing-target')
    fireEvent.click(screen.getByRole('button', { name: '관계 편집' }))
    expect(screen.getByTestId('edge-modal')).toHaveAttribute('data-open', 'true')
  })

  it('clears the table selection when a different graph replaces the canvas', async () => {
    const selectedNode = {
      id: 'table-1',
      type: 'tableNode',
      position: { x: 0, y: 0 },
      data: {
        title: 'public.users',
        columns: [{ column_name: 'id', data_type: 'bigint', is_not_null: true, is_pk: true }],
        badges: { pk: true, fk: false },
      },
    }
    const replacementNode = {
      ...selectedNode,
      data: { ...selectedNode.data, title: 'public.audit_log' },
    }
    vi.mocked(snapshotToGraph)
      .mockReturnValueOnce({ nodes: [selectedNode], edges: [] })
      .mockReturnValueOnce({ nodes: [replacementNode], edges: [] })
    api.getSnapshot
      .mockResolvedValueOnce({
        schema_snapshot_uuid: 's1',
        status: 'succeeded',
        schema_filter: null,
        error_message: null,
        snapshot_json: { version: 1 },
      })
      .mockResolvedValueOnce({
        schema_snapshot_uuid: 's2',
        status: 'succeeded',
        schema_filter: null,
        error_message: null,
        snapshot_json: { version: 2 },
      })

    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '다이어그램' }))
    const firstDiagramButtons = await screen.findAllByRole('button', { name: '열기' })
    vi.useFakeTimers()
    fireEvent.click(firstDiagramButtons[0]!)
    await act(async () => {
      vi.advanceTimersByTime(1000)
      await Promise.resolve()
      await Promise.resolve()
    })

    fireEvent.click(screen.getByTestId('flow-node'))
    expect(screen.getByRole('complementary', { name: 'ERD 속성' })).toHaveTextContent('public.users')

    fireEvent.click(screen.getByRole('button', { name: '다이어그램' }))
    fireEvent.click(screen.getAllByRole('button', { name: '열기' })[1]!)
    await act(async () => {
      vi.advanceTimersByTime(1000)
      await Promise.resolve()
      await Promise.resolve()
    })

    const properties = screen.getByRole('complementary', { name: 'ERD 속성' })
    expect(properties).toHaveTextContent('캔버스에서 테이블을 선택하면')
    expect(properties).not.toHaveTextContent('public.audit_log')
  })

  it('shows selected table metadata, an empty-column state, and opens editing from Properties', async () => {
    vi.mocked(snapshotToGraph).mockReturnValueOnce({
      nodes: [
        {
          id: 'grouped-table',
          type: 'tableNode',
          position: { x: 0, y: 0 },
          data: {
            title: 'public.billing',
            comment: '결제 원장',
            columns: [],
            badges: { pk: false, fk: false },
            businessGroup: { id: 'billing', name: 'Billing', color: '#2563eb' },
          },
        },
      ] as any,
      edges: [],
    })
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
    vi.useRealTimers()

    fireEvent.click(screen.getByTestId('flow-node'))
    const properties = screen.getByRole('complementary', { name: 'ERD 속성' })
    expect(properties).toHaveTextContent('결제 원장')
    expect(properties).toHaveTextContent('등록된 컬럼이 없습니다.')
    expect(screen.getByLabelText('Billing 그룹 색상')).toHaveStyle({ background: '#2563eb' })
    fireEvent.click(screen.getByRole('button', { name: '테이블 편집' }))
    expect(screen.getByTestId('table-modal')).toHaveAttribute('data-open', 'true')
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
    const groupConfirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    fireEvent.click(screen.getByTestId('group-delete'))
    fireEvent.click(screen.getByTestId('group-delete'))
    expect(groupConfirm).toHaveBeenCalledTimes(2)
    expect(groupConfirm).toHaveBeenNthCalledWith(
      1,
      '이 그룹을 삭제하면 포함된 모든 테이블에서 그룹 지정이 해제됩니다. 정말로 삭제하시겠습니까?',
    )
    expect(groupConfirm).toHaveBeenNthCalledWith(
      2,
      '이 그룹을 삭제하면 포함된 모든 테이블에서 그룹 지정이 해제됩니다. 정말로 삭제하시겠습니까?',
    )
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
    for (const id of ['export-copy-ddl', 'export-svg', 'export-uml', 'export-mermaid', 'export-dbml', 'export-prisma', 'export-csv', 'export-md']) {
      fireEvent.click(screen.getByTestId(id))
    }
    fireEvent.click(screen.getByTestId('share-create'))
    await waitFor(() => expect(screen.getByTestId('share-url')).toHaveTextContent('/api/share/one'))
    fireEvent.click(screen.getByTestId('share-copy'))
    fireEvent.click(screen.getByTestId('export-close'))
    fireEvent.click(screen.getByRole('button', { name: 'SVG 이미지 내보내기' }))
    fireEvent.click(screen.getByRole('button', { name: 'PlantUML 내보내기' }))
    fireEvent.click(screen.getByRole('button', { name: 'Mermaid 내보내기' }))
    expect(exports.downloadText).toHaveBeenCalledTimes(10)

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

    vi.spyOn(window, 'confirm').mockReturnValue(true)
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
    fireEvent.submit(screen.getByRole('form', { name: '프로젝트 생성' }))
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

  it('ignores connection and snapshot creation completions after unmount', async () => {
    const connectionRequest = deferred<{ db_connection_uuid: string; conn_name: string }>()
    api.createConnection.mockReturnValueOnce(connectionRequest.promise)
    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '편집기' }))
    fireEvent.change(screen.getByLabelText('Connection DSN'), {
      target: { value: 'postgresql://db.example/unmount' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save connection' }))
    cleanup()
    await act(async () =>
      connectionRequest.resolve({ db_connection_uuid: 'late-c', conn_name: 'Late connection' }),
    )

    const snapshotRequest = deferred<{
      schema_snapshot_uuid: string
      status: string
      schema_filter: string | null
    }>()
    api.createSnapshot.mockReturnValueOnce(snapshotRequest.promise)
    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '편집기' }))
    await waitFor(() => expect(screen.getByLabelText('Connection')).toHaveValue('c1'))
    fireEvent.click(screen.getByRole('button', { name: 'Reverse engineer → snapshot' }))
    cleanup()
    await act(async () =>
      snapshotRequest.resolve({
        schema_snapshot_uuid: 'late-s',
        status: 'queued',
        schema_filter: null,
      }),
    )

    expect(api.getSnapshot).not.toHaveBeenCalledWith('late-s')
  })

  it('logs auto-layout failures and preserves nodes added after the undo snapshot', async () => {
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
    expect(screen.getByRole('alert')).toHaveTextContent('스냅샷 목록을 새로고침하지 못했습니다')
    expect(screen.getByRole('alert')).not.toHaveTextContent('terminal refresh down')
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

  it('clears project-scoped connections and diagrams before replacement metadata arrives', async () => {
    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '다이어그램' }))
    expect(await screen.findByText('ERD_billing_1')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '편집기' }))
    expect(screen.getByLabelText('Connection')).toHaveValue('c1')

    let rejectConnections!: (reason: unknown) => void
    let rejectSnapshots!: (reason: unknown) => void
    api.listConnections.mockReturnValueOnce(
      new Promise((_resolve, reject) => { rejectConnections = reject }),
    )
    api.listSnapshots.mockReturnValueOnce(
      new Promise((_resolve, reject) => { rejectSnapshots = reject }),
    )

    fireEvent.change(screen.getByLabelText('Project'), { target: { value: 'p2' } })
    expect(screen.getByLabelText('Connection')).toHaveValue('')
    expect(screen.getByLabelText('Connection')).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByLabelText('Connection')).toHaveTextContent('Loading…')
    fireEvent.click(screen.getByRole('button', { name: '프로젝트' }))
    expect(screen.getByText('불러오는 중')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '다이어그램' }))
    expect(screen.queryByText('ERD_billing_1')).not.toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('스냅샷 목록을 불러오는 중입니다.')
    expect(screen.queryByText('아직 다이어그램 스냅샷이 없습니다.', { exact: false })).not.toBeInTheDocument()

    await act(async () => {
      rejectConnections(new Error('project-b connections unavailable'))
      rejectSnapshots(new Error('project-b snapshots unavailable'))
      await Promise.resolve()
    })
    expect(screen.queryByText('ERD_billing_1')).not.toBeInTheDocument()
    expect(screen.getByText('아직 다이어그램 스냅샷이 없습니다.', { exact: false })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '편집기' }))
    expect(screen.getByLabelText('Connection')).toHaveAttribute('aria-busy', 'false')
    expect(screen.getByLabelText('Connection')).toHaveTextContent('Select…')
  })

  it('clears a previous project metadata error when another project is selected', async () => {
    api.listConnections
      .mockRejectedValueOnce(new Error('project-a metadata failed'))
      .mockResolvedValueOnce(connections)

    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '편집기' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      '데이터베이스 연결 목록을 불러오지 못했습니다',
    )

    fireEvent.change(screen.getByLabelText('Project'), { target: { value: 'p2' } })
    await waitFor(() => expect(api.listConnections).toHaveBeenLastCalledWith('p2'))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('does not commit a connection created for a project that is no longer selected', async () => {
    const projectAConnection = deferred<{ db_connection_uuid: string; conn_name: string }>()
    api.createConnection
      .mockReturnValueOnce(projectAConnection.promise)
      .mockResolvedValueOnce({ db_connection_uuid: 'c-b', conn_name: 'Project B DB' })

    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '편집기' }))
    fireEvent.change(screen.getByLabelText('Connection DSN'), {
      target: { value: 'postgresql://db.example/project-a' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save connection' }))
    expect(api.createConnection).toHaveBeenLastCalledWith(
      'p1',
      'target-db',
      'postgresql://db.example/project-a',
    )

    fireEvent.change(screen.getByLabelText('Project'), { target: { value: 'p2' } })
    fireEvent.change(screen.getByLabelText('Connection DSN'), {
      target: { value: 'postgresql://db.example/project-b' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save connection' }))
    await waitFor(() => expect(screen.getByLabelText('Connection')).toHaveValue('c-b'))

    await act(async () =>
      projectAConnection.resolve({ db_connection_uuid: 'c-a', conn_name: 'Project A DB' }),
    )
    expect(screen.getByLabelText('Connection')).toHaveValue('c-b')
    expect(screen.queryByRole('option', { name: 'Project A DB' })).not.toBeInTheDocument()
  })

  it('commits a connection when its project is selected again after another project request', async () => {
    const projectAConnection = deferred<{ db_connection_uuid: string; conn_name: string }>()
    api.createConnection.mockReturnValueOnce(projectAConnection.promise)

    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '편집기' }))
    fireEvent.change(screen.getByLabelText('Connection DSN'), {
      target: { value: 'postgresql://db.example/project-a' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save connection' }))
    expect(api.createConnection).toHaveBeenLastCalledWith(
      'p1',
      'target-db',
      'postgresql://db.example/project-a',
    )

    fireEvent.change(screen.getByLabelText('Project'), { target: { value: 'p2' } })
    fireEvent.change(screen.getByLabelText('Connection DSN'), {
      target: { value: 'postgresql://db.example/project-b' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save connection' }))
    await waitFor(() => expect(screen.getByLabelText('Connection')).toHaveValue('c2'))
    fireEvent.change(screen.getByLabelText('Project'), { target: { value: 'p1' } })
    await waitFor(() => expect(screen.getByLabelText('Connection')).toHaveValue('c1'))
    expect(screen.getByRole('button', { name: 'Saving…' })).toBeDisabled()

    await act(async () =>
      projectAConnection.resolve({ db_connection_uuid: 'c-a', conn_name: 'Project A DB' }),
    )
    expect(screen.getByLabelText('Connection')).toHaveValue('c-a')
    expect(screen.getByRole('option', { name: 'Project A DB' })).toBeInTheDocument()
  })

  it('does not poll a snapshot created for a project that is no longer selected', async () => {
    const projectASnapshot = deferred<{
      schema_snapshot_uuid: string
      status: string
      schema_filter: string | null
    }>()
    api.createSnapshot.mockReturnValueOnce(projectASnapshot.promise)

    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '편집기' }))
    await waitFor(() => expect(screen.getByLabelText('Connection')).toHaveValue('c1'))
    fireEvent.click(screen.getByRole('button', { name: 'Reverse engineer → snapshot' }))
    expect(api.createSnapshot).toHaveBeenLastCalledWith('p1', 'c1', undefined)

    fireEvent.change(screen.getByLabelText('Project'), { target: { value: 'p2' } })
    vi.useFakeTimers()
    await act(async () =>
      projectASnapshot.resolve({
        schema_snapshot_uuid: 'snapshot-project-a',
        status: 'queued',
        schema_filter: null,
      }),
    )
    await act(async () => {
      vi.advanceTimersByTime(1000)
      await Promise.resolve()
    })

    expect(api.getSnapshot).not.toHaveBeenCalledWith('snapshot-project-a')
  })

  it('polls a snapshot when its project is selected again before completion', async () => {
    const projectASnapshot = deferred<{
      schema_snapshot_uuid: string
      status: string
      schema_filter: string | null
    }>()
    api.createSnapshot.mockReturnValueOnce(projectASnapshot.promise)

    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '편집기' }))
    await waitFor(() => expect(screen.getByLabelText('Connection')).toHaveValue('c1'))
    fireEvent.click(screen.getByRole('button', { name: 'Reverse engineer → snapshot' }))

    fireEvent.change(screen.getByLabelText('Project'), { target: { value: 'p2' } })
    await waitFor(() => expect(screen.getByLabelText('Connection')).toHaveValue('c1'))
    fireEvent.click(screen.getByRole('button', { name: 'Reverse engineer → snapshot' }))
    await waitFor(() => expect(api.createSnapshot).toHaveBeenLastCalledWith('p2', 'c1', undefined))
    fireEvent.change(screen.getByLabelText('Project'), { target: { value: 'p1' } })
    await waitFor(() => expect(screen.getByLabelText('Connection')).toHaveValue('c1'))
    expect(screen.getByRole('button', { name: 'Starting…' })).toBeDisabled()

    vi.useFakeTimers()
    await act(async () =>
      projectASnapshot.resolve({
        schema_snapshot_uuid: 'snapshot-project-a',
        status: 'queued',
        schema_filter: null,
      }),
    )
    await act(async () => {
      vi.advanceTimersByTime(1000)
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(api.getSnapshot).toHaveBeenCalledWith('snapshot-project-a')
  })

  it('keeps a newly created connection when an older metadata request finishes last', async () => {
    const initialConnections = deferred<typeof connections>()
    api.listConnections.mockReturnValueOnce(initialConnections.promise)
    api.createConnection.mockResolvedValueOnce({
      db_connection_uuid: 'c-new',
      conn_name: 'Newer DB',
    })

    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '편집기' }))
    fireEvent.change(screen.getByLabelText('Connection DSN'), {
      target: { value: 'postgresql://db.example/newer' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save connection' }))
    await waitFor(() => expect(screen.getByLabelText('Connection')).toHaveValue('c-new'))

    await act(async () => initialConnections.resolve(connections))
    expect(screen.getByLabelText('Connection')).toHaveValue('c-new')
    expect(screen.getByLabelText('Connection')).toHaveAttribute('aria-busy', 'false')
    expect(screen.getByRole('option', { name: 'Newer DB' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Warehouse' })).toBeInTheDocument()
  })

  it('keeps a terminal snapshot refresh when the initial list finishes last', async () => {
    const initialSnapshots = deferred<typeof snapshots>()
    const refreshedSnapshots = [
      { schema_snapshot_uuid: 's-new', status: 'succeeded', schema_filter: 'newer' },
    ]
    api.listSnapshots
      .mockReturnValueOnce(initialSnapshots.promise)
      .mockResolvedValueOnce(refreshedSnapshots)

    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '편집기' }))
    await waitFor(() => expect(screen.getByLabelText('Connection')).toHaveValue('c1'))
    vi.useFakeTimers()
    fireEvent.click(screen.getByRole('button', { name: 'Reverse engineer → snapshot' }))
    await act(async () => {
      await Promise.resolve()
      await Promise.resolve()
    })
    await act(async () => {
      vi.advanceTimersByTime(1000)
      await Promise.resolve()
      await Promise.resolve()
    })
    vi.useRealTimers()

    fireEvent.click(screen.getByRole('button', { name: '다이어그램' }))
    expect(await screen.findByText('ERD_newer_1')).toBeInTheDocument()
    await act(async () => initialSnapshots.resolve(snapshots))
    expect(screen.getByText('ERD_newer_1')).toBeInTheDocument()
    expect(screen.queryByText('ERD_billing_1')).not.toBeInTheDocument()
  })

  it('renders sanitized snapshot failures while the project remains selected', async () => {
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
    vi.useFakeTimers()
    fireEvent.click(screen.getByRole('button', { name: 'Reverse engineer → snapshot' }))
    await act(async () => {
      await Promise.resolve()
      await Promise.resolve()
    })
    expect(api.createSnapshot).toHaveBeenCalledWith('p1', 'c2', undefined)

    await act(async () => {
      vi.advanceTimersByTime(1000)
      await Promise.resolve()
      await Promise.resolve()
    })
    expect(screen.getByRole('alert')).toHaveTextContent('스냅샷 생성에 실패했습니다')
    expect(screen.getByRole('alert')).not.toHaveTextContent('database rejected snapshot')
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

    cleanup()
    render(
      <DiagramTable
        snapshots={[{ schema_snapshot_uuid: 'queued', status: 'queued', schema_filter: 'public' }]}
        selectedProjectName=""
        onOpenEditor={onOpenEditor}
      />,
    )
    expect(screen.getByText('queued')).toHaveClass('statusPill')
    expect(screen.getByText('queued')).not.toHaveClass('statusPill--queued')
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

  it('does not restore a stale share link after switching projects', async () => {
    let resolveFirstShare!: (value: { url: string }) => void
    api.createShareLink
      .mockReturnValueOnce(new Promise((resolve) => { resolveFirstShare = resolve }))
      .mockResolvedValueOnce({ url: 'http://localhost/api/share/project-b' })

    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '편집기' }))
    fireEvent.click(screen.getByRole('button', { name: '공유 및 내보내기' }))
    fireEvent.click(screen.getByTestId('share-create'))
    expect(api.createShareLink).toHaveBeenLastCalledWith('p1')

    fireEvent.click(screen.getByTestId('export-close'))
    fireEvent.change(screen.getByLabelText('Project'), { target: { value: 'p2' } })
    fireEvent.click(screen.getByRole('button', { name: '공유 및 내보내기' }))
    expect(screen.getByTestId('share-url')).toBeEmptyDOMElement()

    fireEvent.click(screen.getByTestId('share-create'))
    await waitFor(() => expect(screen.getByTestId('share-url')).toHaveTextContent('/project-b'))
    expect(api.createShareLink).toHaveBeenLastCalledWith('p2')

    await act(async () => resolveFirstShare({ url: 'http://localhost/api/share/project-a' }))
    expect(screen.getByTestId('share-url')).toHaveTextContent('/project-b')
    expect(screen.getByTestId('share-url')).not.toHaveTextContent('/project-a')
  })

  it('ignores a clipboard completion after the share context is invalidated', async () => {
    const clipboardWrite = deferred<void>()
    vi.mocked(navigator.clipboard.writeText).mockReturnValueOnce(clipboardWrite.promise)

    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '편집기' }))
    fireEvent.click(screen.getByRole('button', { name: '공유 및 내보내기' }))
    fireEvent.click(screen.getByTestId('share-create'))
    await waitFor(() => expect(screen.getByTestId('share-url')).toHaveTextContent('/api/share/one'))
    fireEvent.click(screen.getByTestId('share-copy'))

    fireEvent.click(screen.getByTestId('export-close'))
    fireEvent.change(screen.getByLabelText('Project'), { target: { value: 'p2' } })
    await act(async () => clipboardWrite.resolve())

    fireEvent.click(screen.getByRole('button', { name: '공유 및 내보내기' }))
    expect(screen.getByTestId('share-copied')).toHaveTextContent('false')
    expect(screen.getByTestId('share-error')).toBeEmptyDOMElement()
  })

  it('clears active share copy feedback when changing projects', async () => {
    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '편집기' }))
    fireEvent.click(screen.getByRole('button', { name: '공유 및 내보내기' }))
    fireEvent.click(screen.getByTestId('share-create'))
    await waitFor(() => expect(screen.getByTestId('share-url')).toHaveTextContent('/api/share/one'))
    fireEvent.click(screen.getByTestId('share-copy'))
    await waitFor(() => expect(screen.getByTestId('share-copied')).toHaveTextContent('true'))

    fireEvent.change(screen.getByLabelText('Project'), { target: { value: 'p2' } })
    expect(screen.getByTestId('share-copied')).toHaveTextContent('false')
  })

  it('serializes snapshot polling and ignores a late response after project change', async () => {
    const firstPoll = deferred<SnapshotDetail>()
    api.getSnapshot.mockReturnValueOnce(firstPoll.promise)

    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '다이어그램' }))
    const openButtons = await screen.findAllByRole('button', { name: '열기' })
    vi.useFakeTimers()
    fireEvent.click(openButtons[0]!)
    await act(async () => {
      vi.advanceTimersByTime(2000)
      await Promise.resolve()
    })
    expect(api.getSnapshot).toHaveBeenCalledTimes(1)

    fireEvent.change(screen.getByLabelText('Project'), { target: { value: 'p2' } })
    await act(async () =>
      firstPoll.resolve({
        schema_snapshot_uuid: 's1',
        status: 'succeeded',
        schema_filter: 'project-a',
        error_message: null,
        snapshot_json: { relations: [], columns: [], pk_columns: [], fk_edges: [] },
      }),
    )

    expect(api.listSnapshots.mock.calls.filter(([projectId]) => projectId === 'p1')).toHaveLength(1)
    expect(screen.getByTestId('node-count')).toHaveTextContent('0')
  })

  it('ignores a late polling failure after changing projects', async () => {
    const firstPoll = deferred<SnapshotDetail>()
    api.getSnapshot.mockReturnValueOnce(firstPoll.promise)

    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '다이어그램' }))
    const openButtons = await screen.findAllByRole('button', { name: '열기' })
    vi.useFakeTimers()
    fireEvent.click(openButtons[0]!)
    await act(async () => {
      vi.advanceTimersByTime(1000)
      await Promise.resolve()
    })

    fireEvent.change(screen.getByLabelText('Project'), { target: { value: 'p2' } })
    await act(async () => firstPoll.reject(new Error('late project-a polling failure')))

    expect(screen.queryByText('스냅샷 상태를 확인하지 못했습니다.', { exact: false })).not.toBeInTheDocument()
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
    const openButtons = await screen.findAllByRole('button', { name: '열기' })
    vi.useFakeTimers()
    fireEvent.click(openButtons[0]!)
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
    const openButtons = await screen.findAllByRole('button', { name: '열기' })
    vi.useFakeTimers()
    fireEvent.click(openButtons[0]!)
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
    expect(await screen.findByRole('alert')).toHaveTextContent(/목록을 불러오지 못했습니다/)
    expect(screen.getByRole('alert')).not.toHaveTextContent(/down/)
    fireEvent.click(screen.getAllByRole('button', { name: '테이블 추가' })[0]!)
    fireEvent.click(screen.getByTestId('add-name'))
    fireEvent.click(screen.getByTestId('add-submit'))
    fireEvent.click(screen.getByRole('button', { name: '공유 및 내보내기' }))
    api.createShareLink.mockRejectedValueOnce(new Error('share down'))
    fireEvent.click(screen.getByTestId('share-create'))
    await waitFor(() => expect(screen.getByTestId('share-error')).toHaveTextContent('공유 링크를 만들지 못했습니다'))
    expect(screen.getByTestId('share-error')).not.toHaveTextContent('share down')

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
    expect(screen.getByRole('alert')).toHaveTextContent('스냅샷 상태를 확인하지 못했습니다')
    expect(screen.getByRole('alert')).not.toHaveTextContent('poll down')
  })
})
