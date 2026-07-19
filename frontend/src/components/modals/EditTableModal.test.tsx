import '@testing-library/jest-dom/vitest';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { EditTableModal } from './EditTableModal';

describe('EditTableModal', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  const defaultProps = {
    isOpen: true,
    setEditingNode: vi.fn(),
    setNodes: vi.fn(),
    onEditTableCancel: vi.fn(),
    onEditTableSubmit: vi.fn(),
    onDeleteTable: vi.fn(),
  };

  it('assigns unique aria-labels to column inputs in the table edit modal', () => {
    const editingNode = {
      id: 'table-1',
      type: 'table',
      position: { x: 0, y: 0 },
      data: {
        title: 'test_table',
        comment: '',
        columns: [
          {
            column_name: 'test_col',
            data_type: 'text',
            is_pk: true,
            is_not_null: true,
          }
        ]
      }
    };

    render(<EditTableModal {...defaultProps} editingNode={editingNode as any} />);

    expect(screen.getByRole('textbox', { name: 'test_col 컬럼명' })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'test_col 데이터 타입' })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'test_col 코멘트' })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'test_col 예시값' })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'test_col PK 설정' })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'test_col NN 설정' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'test_col 위로 이동' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'test_col 아래로 이동' })).toBeInTheDocument();
  });

  it('returns null if not open or no editingNode', () => {
    const { container } = render(<EditTableModal {...defaultProps} isOpen={false} editingNode={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('adds a column when 컬럼 추가 is clicked', async () => {
    const setNodesMock = vi.fn();
    const setEditingNodeMock = vi.fn();
    const editingNode = {
      id: 'table-1',
      type: 'table',
      position: { x: 0, y: 0 },
      data: {
        title: 'test_table',
        comment: '',
        columns: []
      }
    };

    render(<EditTableModal {...defaultProps} editingNode={editingNode as any} setNodes={setNodesMock} setEditingNode={setEditingNodeMock} />);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: '컬럼 추가' }));

    expect(setNodesMock).toHaveBeenCalled();
    expect(setEditingNodeMock).toHaveBeenCalled();

    // Simulate setNodes state update logic
    const updateFn = setNodesMock.mock.calls[0][0];
    const newNodes = updateFn([editingNode]);
    expect(newNodes[0].data.columns.length).toBe(1);

    // Simulate setEditingNode state update logic
    const updateEditingNodeFn = setEditingNodeMock.mock.calls[0][0];
    const newEditingNode = updateEditingNodeFn(editingNode);
    expect(newEditingNode.data.columns.length).toBe(1);
  });

  it('deletes a column when 삭제 is clicked and confirmed', async () => {
    const setNodesMock = vi.fn();
    const setEditingNodeMock = vi.fn();
    const editingNode = {
      id: 'table-1',
      type: 'table',
      position: { x: 0, y: 0 },
      data: {
        title: 'test_table',
        comment: '',
        columns: [
          {
            column_name: 'test_col',
            data_type: 'text',
            is_pk: false,
            is_not_null: false,
          }
        ]
      }
    };

    vi.spyOn(window, 'confirm').mockReturnValue(true);

    render(<EditTableModal {...defaultProps} editingNode={editingNode as any} setNodes={setNodesMock} setEditingNode={setEditingNodeMock} />);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'test_col 컬럼 삭제' }));

    expect(window.confirm).toHaveBeenCalledWith("'test_col' 컬럼을 삭제하시겠습니까?");
    expect(setNodesMock).toHaveBeenCalled();
    expect(setEditingNodeMock).toHaveBeenCalled();

    const updateFn = setNodesMock.mock.calls[0][0];
    const newNodes = updateFn([editingNode]);
    expect(newNodes[0].data.columns.length).toBe(0);

    const updateEditingNodeFn = setEditingNodeMock.mock.calls[0][0];
    const newEditingNode = updateEditingNodeFn(editingNode);
    expect(newEditingNode.data.columns.length).toBe(0);
  });

  it('reorders columns when up/down buttons are clicked', async () => {
    const setNodesMock = vi.fn();
    const setEditingNodeMock = vi.fn();
    const editingNode = {
      id: 'table-1',
      type: 'table',
      position: { x: 0, y: 0 },
      data: {
        title: 'test_table',
        comment: '',
        columns: [
          { column_name: 'col1', data_type: 'text', is_pk: false, is_not_null: false },
          { column_name: 'col2', data_type: 'int', is_pk: false, is_not_null: false }
        ]
      }
    };

    render(<EditTableModal {...defaultProps} editingNode={editingNode as any} setNodes={setNodesMock} setEditingNode={setEditingNodeMock} />);

    const user = userEvent.setup();

    // col2 위로 이동 클릭
    await user.click(screen.getByRole('button', { name: 'col2 위로 이동' }));

    expect(setNodesMock).toHaveBeenCalled();
    let updateFn = setNodesMock.mock.calls[0][0];
    let newNodes = updateFn([editingNode]);
    expect(newNodes[0].data.columns[0].column_name).toBe('col2');
    expect(newNodes[0].data.columns[1].column_name).toBe('col1');

    setNodesMock.mockClear();

    // col1 (현재 인덱스 0에서 렌더링되지 않았으므로 다시 렌더링된 상태는 모킹상황에서 반영되지 않음, col1의 아래로 버튼 클릭 테스트)
    await user.click(screen.getByRole('button', { name: 'col1 아래로 이동' }));

    expect(setNodesMock).toHaveBeenCalled();
    updateFn = setNodesMock.mock.calls[0][0];
    newNodes = updateFn([editingNode]);
    expect(newNodes[0].data.columns[0].column_name).toBe('col2');
    expect(newNodes[0].data.columns[1].column_name).toBe('col1');
  });

  it('does not delete a column when 삭제 is clicked and canceled', async () => {
    const setNodesMock = vi.fn();
    const editingNode = {
      id: 'table-1',
      type: 'table',
      position: { x: 0, y: 0 },
      data: {
        title: 'test_table',
        comment: '',
        columns: [
          { column_name: 'test_col', data_type: 'text', is_pk: false, is_not_null: false }
        ]
      }
    };

    vi.spyOn(window, 'confirm').mockReturnValue(false);

    render(<EditTableModal {...defaultProps} editingNode={editingNode as any} setNodes={setNodesMock} />);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'test_col 컬럼 삭제' }));

    expect(window.confirm).toHaveBeenCalled();
    expect(setNodesMock).not.toHaveBeenCalled();
  });

  it('duplicates a table when 복제 is clicked', async () => {
    const setNodesMock = vi.fn();
    const onEditTableCancelMock = vi.fn();
    const editingNode = {
      id: 'table-1',
      type: 'table',
      position: { x: 10, y: 10 },
      data: {
        title: 'test_table',
        comment: '',
        columns: [
          { column_name: 'test_col', data_type: 'text', is_pk: false, is_not_null: false }
        ]
      }
    };

    render(<EditTableModal {...defaultProps} editingNode={editingNode as any} setNodes={setNodesMock} onEditTableCancel={onEditTableCancelMock} />);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: '복제' }));

    expect(setNodesMock).toHaveBeenCalled();
    expect(onEditTableCancelMock).toHaveBeenCalled();

    const updateFn = setNodesMock.mock.calls[0][0];
    const newNodes = updateFn([editingNode]);
    expect(newNodes.length).toBe(2);
    expect(newNodes[1].id).toMatch(/^table-1_copy_\d+$/);
    expect(newNodes[1].position).toEqual({ x: 50, y: 50 });
    expect(newNodes[1].data.title).toBe('test_table_copy');
    expect(newNodes[1].data.columns).not.toBe(editingNode.data.columns); // Deep copy check
    expect(newNodes[1].data.columns[0]).toEqual(editingNode.data.columns[0]);
  });
});
