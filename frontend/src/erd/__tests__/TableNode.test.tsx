import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ReactFlowProvider } from "@xyflow/react";
import TableNode from "../TableNode";

// Mock ResizeObserver for React Flow
globalThis.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));

describe("TableNode", () => {
  const defaultProps = {
    id: "table-1",
    type: "tableNode" as const,
    position: { x: 0, y: 0 },
    data: {
      title: "users",
      columns: [
        {
          column_name: "id",
          data_type: "integer",
          is_not_null: true,
          is_pk: true,
        },
      ],
      badges: { pk: true, fk: true },
    },
    selected: false,
    zIndex: 0,
    isConnectable: true,
    dragging: false,
    positionAbsoluteX: 0,
    positionAbsoluteY: 0,
    draggable: true,
    selectable: true,
    deletable: true,
  };

  it("renders ARIA labels for abbreviations in table badges", () => {
    render(
      <ReactFlowProvider>
        <TableNode {...defaultProps} />
      </ReactFlowProvider>
    );

    const pkBadges = screen.getAllByText("PK");
    expect(pkBadges[0]).toHaveAttribute("aria-label", "Primary Key");

    const fkBadges = screen.getAllByText("FK");
    expect(fkBadges[0]).toHaveAttribute("aria-label", "Foreign Key");
  });

  it("renders ARIA labels for abbreviations in column badges", () => {
    render(
      <ReactFlowProvider>
        <TableNode {...defaultProps} />
      </ReactFlowProvider>
    );

    const pkBadges = screen.getAllByText("PK");
    // The second PK badge is the column one (first is table title level)
    expect(pkBadges[1]).toHaveAttribute("aria-label", "Primary Key");

    const notNullBadges = screen.getAllByText("NOT NULL");
    expect(notNullBadges[0]).toHaveAttribute("aria-label", "Not Null");
  });

  it("renders group badge and handles optional text nodes", () => {
    const props = {
      ...defaultProps,
      data: {
        ...defaultProps.data,
        comment: "test comment",
        businessGroup: { id: "bg-1", name: "Users Group", color: "blue" },
        columns: [
          {
            column_name: "id",
            data_type: "integer",
            is_not_null: true,
            is_pk: true,
            column_comment: "primary key",
            example_value: "1",
          },
        ],
        indexes: [
          {
            index_name: "idx_id",
            columns: ["id"],
            access_method: "btree",
          },
        ],
      },
    };
    render(
      <ReactFlowProvider>
        <TableNode {...props} />
      </ReactFlowProvider>
    );

    expect(screen.getByText("Users Group")).toBeInTheDocument();
    expect(screen.getByText("test comment")).toBeInTheDocument();
    expect(screen.getByText("primary key")).toBeInTheDocument();
    expect(screen.getByText("e.g. 1")).toBeInTheDocument();
    expect(screen.getByText("idx_id")).toBeInTheDocument();
  });

  it("truncates columns and indexes when exceeding maximums", () => {
    // Generate 30 columns and 10 indexes
    const columns = Array.from({ length: 30 }, (_, i) => ({
      column_name: `col_${i}`,
      data_type: "text",
      is_not_null: false,
    }));
    const indexes = Array.from({ length: 10 }, (_, i) => ({
      index_name: `idx_${i}`,
      columns: [`col_${i}`],
      access_method: "btree",
    }));

    const props = {
      ...defaultProps,
      data: {
        ...defaultProps.data,
        columns,
        indexes,
      },
    };
    render(
      <ReactFlowProvider>
        <TableNode {...props} />
      </ReactFlowProvider>
    );

    // MAX_RENDERED_COLUMNS is 25
    expect(screen.getByText("… 5 more")).toBeInTheDocument();

    // Max rendered indexes is 4
    expect(screen.getByText("… 6 more indexes")).toBeInTheDocument();
  });

  it("exports correctly memoized versions", () => {
    // Tests isSameRenderedColumns logic in memo
    const { rerender } = render(
      <ReactFlowProvider>
        <TableNode {...defaultProps} />
      </ReactFlowProvider>
    );

    // Rerender with identical props should use memoized version
    rerender(
      <ReactFlowProvider>
        <TableNode {...defaultProps} />
      </ReactFlowProvider>
    );

    // Rerender with different title
    rerender(
      <ReactFlowProvider>
        <TableNode {...{...defaultProps, data: {...defaultProps.data, title: "new title"}}} />
      </ReactFlowProvider>
    );
    expect(screen.getByText("new title")).toBeInTheDocument();
  });

  it("exports correctly memoized versions for other edge cases", () => {
    // Tests isSameRenderedColumns logic in memo
    const { rerender } = render(
      <ReactFlowProvider>
        <TableNode {...defaultProps} />
      </ReactFlowProvider>
    );

    // Rerender with different column data type
    rerender(
      <ReactFlowProvider>
        <TableNode {...{...defaultProps, data: {...defaultProps.data, columns: [{...defaultProps.data.columns[0], data_type: "varchar"}]}}} />
      </ReactFlowProvider>
    );
    expect(screen.getByText("varchar")).toBeInTheDocument();

    // Rerender with different column is_not_null
    rerender(
      <ReactFlowProvider>
        <TableNode {...{...defaultProps, data: {...defaultProps.data, columns: [{...defaultProps.data.columns[0], is_not_null: false}]}}} />
      </ReactFlowProvider>
    );
    expect(screen.queryByText("NOT NULL")).not.toBeInTheDocument();

    // Rerender with different column is_pk
    rerender(
      <ReactFlowProvider>
        <TableNode {...{...defaultProps, data: {...defaultProps.data, columns: [{...defaultProps.data.columns[0], is_pk: false}]}}} />
      </ReactFlowProvider>
    );

    // Rerender with different comment
    rerender(
      <ReactFlowProvider>
        <TableNode {...{...defaultProps, data: {...defaultProps.data, columns: [{...defaultProps.data.columns[0], column_comment: "some diff"}]}}} />
      </ReactFlowProvider>
    );
    expect(screen.getByText("some diff")).toBeInTheDocument();

    // Rerender with different example
    rerender(
      <ReactFlowProvider>
        <TableNode {...{...defaultProps, data: {...defaultProps.data, columns: [{...defaultProps.data.columns[0], example_value: "testval2"}]}}} />
      </ReactFlowProvider>
    );
    expect(screen.getByText("e.g. testval2")).toBeInTheDocument();

    // Rerender with empty columns
    rerender(
      <ReactFlowProvider>
        <TableNode {...{...defaultProps, data: {...defaultProps.data, columns: []}}} />
      </ReactFlowProvider>
    );
  });

  it("handles null example properly", () => {
    const props = {
      ...defaultProps,
      data: {
        ...defaultProps.data,
        columns: [
          {
            ...defaultProps.data.columns[0],
            example_value: null,
          }
        ]
      }
    };
    render(
      <ReactFlowProvider>
        <TableNode {...props} />
      </ReactFlowProvider>
    );
    expect(screen.queryByText(/e\.g\./)).not.toBeInTheDocument();
  });

  it("renders when pk/fk is false or missing", () => {
    const props = {
      ...defaultProps,
      data: {
        ...defaultProps.data,
        badges: { pk: false, fk: false }
      }
    };
    render(
      <ReactFlowProvider>
        <TableNode {...props} />
      </ReactFlowProvider>
    );
    // 1 from column, 0 from table badge
    expect(screen.getAllByText("PK").length).toBe(1);
    expect(screen.queryByText("FK")).not.toBeInTheDocument();
  });

  it("handles blank example format correctly", () => {
    const props = {
      ...defaultProps,
      data: {
        ...defaultProps.data,
        columns: [
          {
            ...defaultProps.data.columns[0],
            example_value: "   ",
          }
        ]
      }
    };
    render(
      <ReactFlowProvider>
        <TableNode {...props} />
      </ReactFlowProvider>
    );
    expect(screen.queryByText(/e\.g\./)).not.toBeInTheDocument();
  });

  it("fails memo when badge properties change", () => {
    const { rerender } = render(
      <ReactFlowProvider>
        <TableNode {...defaultProps} />
      </ReactFlowProvider>
    );
    // Change pk badge
    rerender(
      <ReactFlowProvider>
        <TableNode {...{...defaultProps, data: {...defaultProps.data, badges: { pk: false, fk: true }}}} />
      </ReactFlowProvider>
    );

    // Change fk badge
    rerender(
      <ReactFlowProvider>
        <TableNode {...{...defaultProps, data: {...defaultProps.data, badges: { pk: true, fk: false }}}} />
      </ReactFlowProvider>
    );

    // Missing business group color change
    rerender(
      <ReactFlowProvider>
        <TableNode {...{...defaultProps, data: {...defaultProps.data, businessGroup: { id: "1", name: "G1", color: "red" }}}} />
      </ReactFlowProvider>
    );
    rerender(
      <ReactFlowProvider>
        <TableNode {...{...defaultProps, data: {...defaultProps.data, businessGroup: { id: "1", name: "G1", color: "blue" }}}} />
      </ReactFlowProvider>
    );
  });

  it("fails memo when columns array length changes", () => {
    const { rerender } = render(
      <ReactFlowProvider>
        <TableNode {...defaultProps} />
      </ReactFlowProvider>
    );
    rerender(
      <ReactFlowProvider>
        <TableNode {...{...defaultProps, data: {...defaultProps.data, columns: [defaultProps.data.columns[0], {...defaultProps.data.columns[0], column_name: 'test'}]}}} />
      </ReactFlowProvider>
    );
  });

  it("fails memo when column name changes", () => {
    const { rerender } = render(
      <ReactFlowProvider>
        <TableNode {...defaultProps} />
      </ReactFlowProvider>
    );
    rerender(
      <ReactFlowProvider>
        <TableNode {...{...defaultProps, data: {...defaultProps.data, columns: [{...defaultProps.data.columns[0], column_name: "changed_name"}]}}} />
      </ReactFlowProvider>
    );
  });

  it("fails memo when other properties change", () => {
    const { rerender } = render(
      <ReactFlowProvider>
        <TableNode {...defaultProps} />
      </ReactFlowProvider>
    );

    // change data_type
    rerender(
      <ReactFlowProvider>
        <TableNode {...{...defaultProps, data: {...defaultProps.data, columns: [{...defaultProps.data.columns[0], data_type: "text"}]}}} />
      </ReactFlowProvider>
    );
  });

  it("fails memo when example changes", () => {
    const { rerender } = render(
      <ReactFlowProvider>
        <TableNode {...defaultProps} />
      </ReactFlowProvider>
    );

    // Change comment
    rerender(
      <ReactFlowProvider>
        <TableNode {...{...defaultProps, data: {...defaultProps.data, columns: [{...defaultProps.data.columns[0], column_comment: "changed_comment"}]}}} />
      </ReactFlowProvider>
    );

    // change example
    rerender(
      <ReactFlowProvider>
        <TableNode {...{...defaultProps, data: {...defaultProps.data, columns: [{...defaultProps.data.columns[0], example_value: "changed_example"}]}}} />
      </ReactFlowProvider>
    );
  });

  it("fails memo when index arrays differ in length", () => {
    const { rerender } = render(
      <ReactFlowProvider>
        <TableNode {...defaultProps} />
      </ReactFlowProvider>
    );

    rerender(
      <ReactFlowProvider>
        <TableNode {...{...defaultProps, data: {...defaultProps.data, indexes: [{ index_name: "idx1", columns: ["id"], access_method: "btree" }]}}} />
      </ReactFlowProvider>
    );
  });

  it("fails memo when index elements differ", () => {
    const { rerender } = render(
      <ReactFlowProvider>
        <TableNode {...defaultProps} />
      </ReactFlowProvider>
    );

    rerender(
      <ReactFlowProvider>
        <TableNode {...{...defaultProps, data: {...defaultProps.data, indexes: [{ index_name: "idx1", columns: ["id"], access_method: "btree" }]}}} />
      </ReactFlowProvider>
    );

    rerender(
      <ReactFlowProvider>
        <TableNode {...{...defaultProps, data: {...defaultProps.data, indexes: [{ index_name: "idx2", columns: ["id"], access_method: "btree" }]}}} />
      </ReactFlowProvider>
    );
  });

  it("fails memo when index elements fields differ", () => {
    const { rerender } = render(
      <ReactFlowProvider>
        <TableNode {...defaultProps} />
      </ReactFlowProvider>
    );

    rerender(
      <ReactFlowProvider>
        <TableNode {...{...defaultProps, data: {...defaultProps.data, indexes: [{ index_name: "idx1", columns: ["id"], access_method: "btree" }]}}} />
      </ReactFlowProvider>
    );

    rerender(
      <ReactFlowProvider>
        <TableNode {...{...defaultProps, data: {...defaultProps.data, indexes: [{ index_name: "idx1", columns: ["id2"], access_method: "btree" }]}}} />
      </ReactFlowProvider>
    );

    rerender(
      <ReactFlowProvider>
        <TableNode {...{...defaultProps, data: {...defaultProps.data, indexes: [{ index_name: "idx1", columns: ["id2"], access_method: "hash" }]}}} />
      </ReactFlowProvider>
    );
  });

  it("fails memo when index elements access method differ", () => {
    const { rerender } = render(
      <ReactFlowProvider>
        <TableNode {...defaultProps} />
      </ReactFlowProvider>
    );

    rerender(
      <ReactFlowProvider>
        <TableNode {...{...defaultProps, data: {...defaultProps.data, indexes: [{ index_name: "idx1", columns: ["id"], access_method: "btree" }]}}} />
      </ReactFlowProvider>
    );

    rerender(
      <ReactFlowProvider>
        <TableNode {...{...defaultProps, data: {...defaultProps.data, indexes: [{ index_name: "idx1", columns: ["id"], access_method: "hash" }]}}} />
      </ReactFlowProvider>
    );
  });
});
